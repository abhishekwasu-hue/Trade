"""opportunity_engine/visual_audit/backfill.py — historical visual backfill (spec §17.9): consensus चा backtest करता यावा म्हणून.

🎓 प्रत्येक trading दिवस D साठी Daily आणि 1H charts — फक्त D−1 पर्यंतचे bars (cutoff = D 09:15) आणि timeline चे D चे levels (D−1 पर्यंतच्या डेटावरून).
Resumable: JSONL cache मध्ये ज्या (date, tf) चे overlay + स्वतंत्र दोन्ही OK आहेत ते वगळले जातात; अयशस्वी पुढच्या run मध्ये पुन्हा.
दोन पद्धती: `sync` (एकेक call; SDK retries/backoff) आणि `batch` (Message Batches API — 50% स्वस्त, साधारण 1 तासात; batch ids state फाइलमध्ये, म्हणून
मध्येच थांबलं तरी पुढच्या run ला निकाल गोळा होतात).
"""
import json
import os
import time

import pandas as pd

from . import auditor as A
from . import jobs as J
from . import store as VS

BACKFILL_TFS = ("1d", "1h")


def plan_items(tl, start, end, tfs=BACKFILL_TFS, done=(), symbol="NIFTY"):
    """[(day, tf)] — कालावधीतले, आणि आधी पूर्ण न झालेले (cache key = date|symbol|tf)."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out = []
    for day in tl.days:
        if not (s <= pd.Timestamp(day.date) <= e) or not day.levels:
            continue
        for tf in tfs:
            if f"{pd.Timestamp(day.date).date()}|{symbol}|{tf}" in done:
                continue
            out.append((day, tf))
    return out


def done_keys(cache):
    return {VS.cache_key(r) for r in VS.read_jsonl(cache) if (r.get("overlay") or {}).get("status") in ("OK", "SKIPPED") and (r.get("independent") or {}).get("status") == "OK"}


def states_for(tl, day, tf):
    return tl.htf_state(tf, day.open_t).state if tf in ("1d", "4h", "1h") else None


def chart(tl, frames, day, tf, symbol, render=True):
    return J.prepare_chart(frames, tl.journal, day.levels, tf, symbol, day.open_t, render=render)


def run_sync(client, vcfg, tl, frames, items, cache, symbol="NIFTY", log=print, pause=0.0):
    n = 0
    for day, tf in items:
        ch = chart(tl, frames, day, tf, symbol)
        if ch is None:
            continue
        rec = A.audit_chart(client, vcfg, symbol, tf, pd.Timestamp(day.date).date(), ch["png_overlay"], ch["png_plain"], ch["labels"], day.pool,
                            states_for(tl, day, tf), ch["lo"], ch["hi"])
        rec["components"] = ch["components"]
        VS.append_jsonl(cache, rec)
        n += 1
        if log and n % 20 == 0:
            log(f"  {n}/{len(items)} {day.date:%Y-%m-%d} {tf}")
        if pause:
            time.sleep(pause)
    return n


# ---------------------------------------------------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------------------------------------------------
def custom_id(date, tf, kind):
    return f"{pd.Timestamp(date):%Y%m%d}_{tf}_{kind}"


def parse_custom_id(cid):
    d, tf, kind = cid.split("_")
    return pd.Timestamp(d), tf, kind


def build_requests(vcfg, tl, frames, items, symbol="NIFTY"):
    reqs = []
    for day, tf in items:
        ch = chart(tl, frames, day, tf, symbol)
        if ch is None:
            continue
        if ch["png_overlay"] is not None and ch["labels"]:
            reqs.append({"custom_id": custom_id(day.date, tf, "overlay"),
                         "params": A.build_request(vcfg, "overlay", ch["png_overlay"], symbol, tf, ch["labels"], states_for(tl, day, tf))})
        if ch["png_plain"] is not None:
            reqs.append({"custom_id": custom_id(day.date, tf, "independent"), "params": A.build_request(vcfg, "independent", ch["png_plain"], symbol, tf)})
    return reqs


def _state(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"batches": []}


def _save_state(path, st):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1)


def submit(client, reqs, state_path, chunk=300, log=print):
    """requests -> batches (साधारण `chunk` आकारात; 256 MB मर्यादेखाली राहण्यासाठी). एका chart चे overlay + स्वतंत्र requests कधीच वेगवेगळ्या batches मध्ये
    जात नाहीत (collect त्यांना एका record मध्ये जोडतो). batch ids state फाइलमध्ये."""
    st = _state(state_path)
    groups = {}
    for r in reqs:
        groups.setdefault(r["custom_id"].rsplit("_", 1)[0], []).append(r)
    parts, cur = [], []
    for g in groups.values():
        if cur and len(cur) + len(g) > chunk:
            parts.append(cur)
            cur = []
        cur = cur + g
    if cur:
        parts.append(cur)
    for part in parts:
        b = client.messages.batches.create(requests=part)
        st["batches"].append({"id": b.id, "n": len(part), "collected": False})
        _save_state(state_path, st)
        if log:
            log(f"  batch {b.id}: {len(part)} requests सबमिट")
    return st


def collect(client, tl, frames, cache, state_path, symbol="NIFTY", wait=False, poll=60, log=print):
    """संपलेल्या batches चे निकाल गोळा करून records (overlay + स्वतंत्र जोडून) cache मध्ये. रिटर्न (गोळा केलेले records, अजून चालू batches)."""
    st = _state(state_path)
    days = {pd.Timestamp(d.date).normalize(): d for d in tl.days}
    written, pending = 0, 0
    for b in st["batches"]:
        if b.get("collected"):
            continue
        while True:
            info = client.messages.batches.retrieve(b["id"])
            if info.processing_status == "ended" or not wait:
                break
            time.sleep(poll)
        if info.processing_status != "ended":
            pending += 1
            continue
        parts = {}
        for res in client.messages.batches.results(b["id"]):
            date, tf, kind = parse_custom_id(res.custom_id)
            parts.setdefault((date, tf), {})[kind] = res
        for (date, tf), kinds in parts.items():
            day = days.get(date.normalize())
            if day is None:
                continue
            ch = chart(tl, frames, day, tf, symbol, render=False)
            if ch is None:
                continue
            rec = {"run_id": A.new_run_id(), "audit_date": str(date.date()), "symbol": symbol, "tf": tf, "model": None, "engine_state": states_for(tl, day, tf),
                   "labels": ch["labels"], "components": ch["components"], "usage": {"input_tokens": 0, "output_tokens": 0, "calls": 0}, "batch_id": b["id"]}
            for kind in ("overlay", "independent"):
                r = kinds.get(kind)
                if r is None:
                    rec[kind] = {"status": "SKIPPED" if kind == "overlay" and not ch["labels"] else "FAILED", "data": None, "error": "batch मध्ये उत्तर नाही"}
                    continue
                if r.result.type != "succeeded":
                    rec[kind] = {"status": "FAILED", "data": None, "error": f"batch: {r.result.type}"}
                    continue
                msg = r.result.message
                rec["model"] = getattr(msg, "model", None)
                data, err, tin, tout = A.parse_message(msg, kind, ch["labels"] if kind == "overlay" else None, ch["lo"], ch["hi"])
                rec["usage"]["input_tokens"] += tin
                rec["usage"]["output_tokens"] += tout
                rec["usage"]["calls"] += 1
                rec[kind] = {"status": "OK" if err is None else "FAILED", "data": data, "error": err}
            sugg = []
            for m in ((rec["overlay"].get("data") or {}).get("missing") or []):
                z = A.snap_band(m["approx_low"], m["approx_high"], day.pool, exclude_ids={l["level_id"] for l in ch["labels"]})
                sugg.append({**m, "snapped_level_id": None if z is None else z.get("level_id")})
            rec["suggestions"] = sugg
            VS.append_jsonl(cache, rec)
            written += 1
        b["collected"] = True
        _save_state(state_path, st)
        if log:
            log(f"  batch {b['id']}: {len(parts)} charts गोळा")
    return written, pending
