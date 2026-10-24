"""scripts/vision_cross_check.py — V1 (DECISIONS 88): Vision cross-check = a SECOND OPINION, never the source of truth.
**Audit only: no order, no gate, no rule change, no store write except the vision usage log.**

Reuses the vision blind test (vision_led/blind_test.py: clean candle figure / png, weekly-from-daily, OHLC tables, the request shape,
the usage / price helpers of vision/signal_audit.py and the usage store vision/store.py).

Items:
  • every answer-key item (<trade-data>/review/answer_key/*.json, newest key file): object (tf_band, lo, hi), window, verdict, known_at;
  • every new replay entry: a JSON list (format below).
For each item: CLEAN charts at the decision bar (Weekly, Daily, 1H, 15M; candles only, no marks; only bars whose bar_end ≤ the
decision bar close) + their OHLC tables ⇒ one vision call with FIXED questions (PROMPT_VERSION): higher-TF trend, zones near price,
object state (alive / false break / beyond-not-broken / broken / dead), entry yes / no and side ⇒ structured JSON. Output: table
reader vs vision vs answer key (table.html + table.csv), disagreements listed with their charts, results.json, summary.json (cost).

Replay entries file (JSON list; `id` and `object` optional; reader = the replay's own call):
    [{"symbol": "BANKNIFTY", "decision_bar": "2026-08-17 12:15", "model": "E4", "side": "bear",
      "id": "E01", "object": {"tf_band": "D resistance", "lo": 57286.9, "hi": 57448.5}}]
Reader file for answer-key items (--reader-json): {"L01": {"state": "false_break", "entry": false, "side": "none"}, …} or the
reader's answer-key scorer output (list of {id, tf, found: [{tf, events: [[ts, kind, why], …]}]}) — the state is then replayed
from events ≤ the decision bar close only.

Budget: per-run cap = _global `vision_check_run_cap_usd` (dashboard / `python3 -m vision.config`; --cap overrides lower only); before
each call spent + estimate > cap ⇒ STOP (the rest NOT_RUN_BUDGET). Also the global daily / monthly vision budgets (as the blind test).
Every call ⇒ vision_usage (task "vision_check"); the total is printed and in summary.json.

    python3 scripts/vision_cross_check.py --out-dir <trade-data>/review/vision_check/<date> [--replay-json F] [--reader-json F]
        [--dry-run]   # no API call: charts + request text + table + cost estimate
        [--rebuild]   # no API call: rebuild the table from results.json (e.g. locally with --reader-json)
"""
import argparse
import csv
import glob
import html
import json
import os
import re
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vision_led import blind_test as BT     # noqa: E402

TASK = "vision_check"
PROMPT_VERSION = "vc1"
TFS = BT.TFS                                                             # W, D, 1H, 15M
STATES = ("alive", "false_break", "beyond_not_broken", "broken", "dead")
SIDES = ("bull", "bear", "none")
TRENDS = ("up", "down", "sideways")
PRICED = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")   # = scripts/vision_blind_test.PRICED (signal_audit PRICES)
MAX_TOKENS = 4000

SYSTEM = f"""You are a price-action chart reader giving a SECOND OPINION (prompt {PROMPT_VERSION}). You get four clean candle charts
(Weekly, Daily, 1H, 15M) cut at the decision bar close, and their OHLC tables. Nothing after the decision bar exists. Read the chart
by structure (swings, zones, closes), not by time of day. Answer ONLY the fixed questions, in the JSON schema.

Q1 higher-TF trend: weekly and daily — up / down / sideways (structure of swings).
Q2 zones near price: the support / resistance zones closest to the last close (up to 4), each with its TF, kind and price edges taken
   from the OHLC tables.
Q3 object state at the decision bar close, for the object named in the request (or, when none is named, the zone price is at):
   alive             = not closed beyond, or tested and held;
   false_break       = closed beyond, then back inside before a break was confirmed (the object stays alive);
   beyond_not_broken = closed beyond, no follow-through yet (no close beyond the next swing of the object's own TF), not back inside;
   broken            = after the close beyond, a 15M candle CLOSED beyond the nearest prior confirmed swing of the object's own TF on
                       the far side (a wick through it that closes back is only a sweep); the object now acts from the other side;
   dead              = an already-broken (flipped) object broken back by the same test.
   Use no_object only when no object is named and price is at no zone.
Q4 entry at this bar: yes / no and side (bull / bear / none) — would a price-action trader enter here, on this object.
Give one short reason for Q3 and one for Q4 (bar times from the tables)."""

ZONE = {"type": "object", "additionalProperties": False, "required": ["tf", "kind", "lo", "hi"],
        "properties": {"tf": {"type": "string", "enum": list(TFS)}, "kind": {"type": "string", "enum": ["support", "resistance"]},
                       "lo": {"type": "number"}, "hi": {"type": "number"}}}
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["htf_trend", "zones_near_price", "object_state", "state_reason", "entry", "side", "entry_reason"],
          "properties": {
              "htf_trend": {"type": "object", "additionalProperties": False, "required": ["weekly", "daily"],
                            "properties": {"weekly": {"type": "string", "enum": list(TRENDS)},
                                           "daily": {"type": "string", "enum": list(TRENDS)}}},
              "zones_near_price": {"type": "array", "items": ZONE},
              "object_state": {"type": "string", "enum": list(STATES) + ["no_object"]},
              "state_reason": {"type": "string"},
              "entry": {"type": "boolean"},
              "side": {"type": "string", "enum": list(SIDES)},
              "entry_reason": {"type": "string"}}}


# ---------------------------------------------------------------------------------------------------------------- data
def _naive(s):
    t = pd.to_datetime(s, utc=False)
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return t.astype("datetime64[ns]")


def _read(p):
    d = pd.read_csv(p)
    d["timestamp"] = _naive(d["timestamp"])
    return d[["timestamp", "open", "high", "low", "close"]]


def _merge(frames):
    fr = [f.assign(_k=k) for k, f in enumerate(frames) if f is not None and len(f)]
    if not fr:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])
    d = pd.concat(fr, ignore_index=True).sort_values(["timestamp", "_k"]).drop_duplicates("timestamp", keep="last")
    return d.drop(columns="_k").reset_index(drop=True)


def daily_from_15m(m15):
    g = m15.assign(_d=m15["timestamp"].dt.normalize()).groupby("_d")
    return g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index().rename(
        columns={"_d": "timestamp"})


def load_symbol(symbol, trade_data):
    """{"daily", "m15"} for a symbol, or None (no loader). BANKNIFTY = <trade-data>/banknifty: long Daily history (official closes)
    + 15M (export + newest VPS spot history; later file wins). NIFTY: not wired here (holdout sealed) ⇒ None."""
    if str(symbol).upper() != "BANKNIFTY":
        return None
    bn = os.path.join(trade_data, "banknifty")
    sp = sorted(glob.glob(os.path.join(bn, "vps_spot_history", "*", "BANKNIFTY_15m.csv.gz")))
    m15 = _merge([_read(p) for p in [os.path.join(bn, "BANKNIFTY_15M.csv.gz")] + sp[-1:] if os.path.exists(p)])
    from decision3 import history as HI
    dh = [HI._ohlc_daily(HI._read(p)) for p in sorted(glob.glob(os.path.join(bn, "BANKNIFTY_daily_*.csv"))) +
          sorted(glob.glob(os.path.join(bn, "BANKNIFTY_D.csv*")))]                  # older first; the Upstox Daily wins
    daily = _merge(dh)
    if len(daily):
        daily["timestamp"] = daily["timestamp"].dt.normalize()
        daily = daily.drop_duplicates("timestamp", keep="last")
    if len(m15):                                                         # sessions after the Daily file ⇒ from 15M (official file wins)
        extra = daily_from_15m(m15)
        extra = extra[~extra["timestamp"].isin(set(daily["timestamp"]))] if len(daily) else extra
        daily = _merge([extra, daily])
    return {"daily": daily, "m15": m15}


def h1_from_15m(m15):
    """1H bars anchored at the session open (09:15 … 15:15; the last one ends 15:30)."""
    if not len(m15):
        return pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close"])
    t = m15["timestamp"]
    day = t.dt.normalize()
    k = ((t - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(hours=1)).astype(int)
    start = day + pd.Timedelta(hours=9, minutes=15) + k * pd.Timedelta(hours=1)
    g = m15.assign(_s=start).groupby("_s")
    h = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index()
    h = h.rename(columns={"_s": "timestamp"})
    h["bar_end"] = [min(s + pd.Timedelta(hours=1), s.normalize() + pd.Timedelta(hours=15, minutes=30)) for s in h["timestamp"]]
    return h[["timestamp", "bar_end", "open", "high", "low", "close"]]


def frames_at(data, decision, start=None):
    """Clean frames at the decision bar (15M bar START) ⇒ asof = its close. ONLY bars with bar_end ≤ asof on every TF (no look-ahead:
    the input is cut first, then every frame is checked). start (answer-key window start) widens 1H / 15M to show the window."""
    asof = pd.Timestamp(decision) + pd.Timedelta(minutes=15)
    m15 = data["m15"]
    m15 = m15[m15["timestamp"] + pd.Timedelta(minutes=15) <= asof].copy()
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    d = data["daily"].copy()
    d["bar_end"] = d["timestamp"].dt.normalize() + pd.Timedelta(hours=15, minutes=30)
    d = d[d["bar_end"] <= asof]
    h1 = h1_from_15m(m15[["timestamp", "open", "high", "low", "close"]])
    h1 = h1[h1["bar_end"] <= asof]
    out = {"W": BT.weekly(d[["timestamp", "open", "high", "low", "close"]], asof), "D": d.reset_index(drop=True),
           "1H": h1.reset_index(drop=True), "15M": m15[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)}
    fr = {tf: BT._slice(f, tf, start) for tf, f in out.items()}
    for tf, f in fr.items():
        assert not len(f) or pd.Timestamp(f["bar_end"].max()) <= asof, f"{tf}: a bar after the decision"
    return fr, asof


# ---------------------------------------------------------------------------------------------------------------- items
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def key_state(it):
    """Answer-key expected state: explicit `expected_state`, else from the owner's verdict words (UPPER-case lifecycle words only)."""
    if it.get("expected_state") in STATES:
        return it["expected_state"]
    v = str(it.get("verdict", ""))
    if re.search(r"\bDEAD\b", v):
        return "dead"
    if re.search(r"\bBROKEN\b", v) and not re.search(r"not BROKEN", v):
        return "broken"
    if re.search(r"BEYOND", v):
        return "beyond_not_broken"
    if re.search(r"\bSWEEP\b|FALSE BREAK", v):
        return "false_break"
    if re.search(r"\bALIVE\b", v):
        return "alive"
    return None


def known_times(it):
    """'11 Sep 10:30' style times in known_at (year from the window)."""
    y = pd.Timestamp(it["window"][0]).year
    out = []
    for d, mon, hh, mm in re.findall(r"(\d{1,2}) ([A-Z][a-z]{2})[a-z]* (\d{1,2}):(\d{2})", str(it.get("known_at", ""))):
        if mon.lower() in MONTHS:
            out.append(pd.Timestamp(year=y, month=MONTHS[mon.lower()], day=int(d), hour=int(hh), minute=int(mm)))
    return out


def decision_for(it, m15, at="end"):
    """Decision bar of an answer-key item: explicit `decision_bar`; at = end ⇒ the last 15M bar of the window (the verdict is the state
    there); at = known ⇒ the latest time named in known_at (fallback end)."""
    if it.get("decision_bar"):
        return pd.Timestamp(it["decision_bar"])
    if at == "known" and known_times(it):
        return max(known_times(it))
    end = pd.Timestamp(it["window"][1]) + pd.Timedelta(days=1)
    t = m15["timestamp"][m15["timestamp"] < end] if len(m15) else []
    return pd.Timestamp(t.iloc[-1]) if len(t) else pd.Timestamp(it["window"][1]) + pd.Timedelta(hours=15, minutes=15)


def latest_key(trade_data):
    ps = sorted(glob.glob(os.path.join(trade_data, "review", "answer_key", "*.json")), key=os.path.getmtime)
    return ps[-1] if ps else None


def answer_key_items(path, symbol="BANKNIFTY"):
    k = json.load(open(path, encoding="utf-8"))
    return [{"kind": "answer_key", "id": it["id"], "symbol": it.get("symbol", k.get("symbol", symbol)), "object": it.get("object"),
             "window": it.get("window"), "known_at": it.get("known_at", ""), "verdict": it.get("verdict", ""),
             "key_state": key_state(it), "key_entry": it.get("expected_entry"), "key_side": it.get("expected_side"), "_raw": it}
            for it in k.get("items", [])], k.get("key_version")


def replay_items(path):
    out = []
    for n, e in enumerate(json.load(open(path, encoding="utf-8")), 1):
        miss = [f for f in ("symbol", "decision_bar", "model", "side") if f not in e]
        if miss:
            raise ValueError(f"replay entry {n}: missing {miss}")
        out.append({"kind": "replay", "id": e.get("id") or f"R{n:02d}", "symbol": e["symbol"], "decision_bar": e["decision_bar"],
                    "object": e.get("object"), "window": None, "known_at": "", "verdict": "", "key_state": None,
                    "reader": {"state": e.get("state"), "entry": True, "side": e["side"], "model": e["model"]}})
    return out


EV_STATE = {"sweep": "false_break", "reclaim": "false_break", "beyond": "beyond_not_broken", "broken": "broken", "flip": "broken",
            "dead": "dead"}


def reader_states(path, asof_of):
    """{id: {state, entry, side}} from --reader-json (simple dict, or scorer output with events — replayed ≤ asof only)."""
    if not path:
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items()}
    out = {}
    for r in raw:
        asof = asof_of(r["id"])
        found = r.get("found") or []
        f = next((x for x in found if x.get("tf") == r.get("tf")), found[0] if found else None)
        if f is None or asof is None:
            out[r["id"]] = {"state": None, "note": "object not found by the reader" if f is None else "no decision bar"}
            continue
        st = "alive"
        for ts, kind, *_ in sorted(f.get("events") or [], key=lambda e: e[0]):
            if pd.Timestamp(ts) + pd.Timedelta(minutes=15) <= asof and kind in EV_STATE:
                st = EV_STATE[kind]
        out[r["id"]] = {"state": st}
    return out


# ---------------------------------------------------------------------------------------------------------------- request
def object_line(it):
    o = it.get("object")
    if not o:
        return "Object: none named — judge the zone price is at now (or no_object)."
    return f"Object: {o.get('tf_band', '?')} band {float(o['lo']):,.2f} – {float(o['hi']):,.2f}."


def user_text(it, decision, fr):
    head = (f"{it['symbol']}. Decision bar = the 15M bar starting {pd.Timestamp(decision):%Y-%m-%d %H:%M} (closed at "
            f"{pd.Timestamp(decision) + pd.Timedelta(minutes=15):%H:%M}). No data after that close exists anywhere in this request. "
            "Four clean candle charts (Weekly, Daily, 1H, 15M; no marks) and their OHLC tables follow.")
    parts = [head, object_line(it)] + [BT.ohlc_table(fr[tf], tf) for tf in TFS if len(fr[tf])]
    parts.append("Answer the fixed questions Q1–Q4 with the JSON schema.")
    return "\n\n".join(parts)


def build_request(pngs, text, model, effort=None, thinking=None):
    if not model:
        raise ValueError("model env missing (VISION_SIGNAL_MODEL)")
    import base64
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.standard_b64encode(p).decode("utf-8")}} for p in pngs if p]
    content.append({"type": "text", "text": text})
    p = {"model": model, "max_tokens": MAX_TOKENS * (2 if thinking else 1),
         "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
         "messages": [{"role": "user", "content": content}], "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}
    if effort:
        p["output_config"]["effort"] = effort
    if thinking:
        p["thinking"] = {"type": thinking}
    else:
        p["temperature"] = 0.0
    return p


def parse(message):
    from vision.signal_audit import usage_of
    usage = usage_of(message)
    stop = getattr(message, "stop_reason", None)
    if stop in ("refusal", "max_tokens"):
        return None, f"stop_reason {stop}", usage
    text = next((b.text for b in (getattr(message, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, "no text answer", usage
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"JSON parse: {exc}", usage
    miss = [k for k in SCHEMA["required"] if k not in data]
    if miss or data.get("object_state") not in STATES + ("no_object",) or data.get("side") not in SIDES:
        return None, f"JSON shape: missing {miss}" if miss else "JSON shape: bad enum", usage
    return data, None, usage


def estimate_usd(model, text_chars):
    """Cautious: no cache, output = max_tokens. Image ≈ 1,600 tokens, text ≈ 3 chars / token (as BT.estimate_usd)."""
    from vision.signal_audit import cost_usd
    return cost_usd(model, {"input_tokens": len(TFS) * 1600 + len(SYSTEM) // 3 + text_chars // 3, "output_tokens": MAX_TOKENS})


# ---------------------------------------------------------------------------------------------------------------- run
def run_item(it, data, out_dir, model, client, state, dry_run=False, at="end", record=None, log=print):
    """One item ⇒ record (status OK / DRY_RUN / NO_DATA / REFUSED_HOLDOUT / NOT_RUN_BUDGET / API_ERROR / PARSE_ERROR)."""
    rec = {k: it.get(k) for k in ("kind", "id", "symbol", "object", "window", "known_at", "verdict", "key_state", "key_entry", "key_side")}
    rec.update(model=model, prompt_version=PROMPT_VERSION)
    from decision3 import history as HI
    if data is None:
        rec.update(status="NO_DATA", note=f"no data loader for {it['symbol']}")
        return rec
    dec = pd.Timestamp(it["decision_bar"]) if it.get("decision_bar") else decision_for(it.get("_raw", it), data["m15"], at)
    rec["decision_bar"] = f"{dec:%Y-%m-%d %H:%M}"
    if HI.is_nifty(it["symbol"]):
        from elliott import data_policy as DP
        if not DP.allowed(dec, "annotation"):
            rec.update(status="REFUSED_HOLDOUT", note="NIFTY sealed holdout — never loaded")
            return rec
    cdir = os.path.join(out_dir, "items", f"{it['id']}_{dec:%Y-%m-%d_%H%M}")
    os.makedirs(cdir, exist_ok=True)
    prev = os.path.join(cdir, "result.json")
    if not dry_run and client is not None and os.path.exists(prev):
        old = json.load(open(prev, encoding="utf-8"))
        if old.get("status") == "OK" and old.get("prompt_version") == PROMPT_VERSION:   # a re-run never pays twice for a done item
            log(f"  {it['id']}: already OK — no call")
            old["cost_usd"] = 0.0
            return old
    start = pd.Timestamp(it["window"][0]) if it.get("window") else None
    fr, asof = frames_at(data, dec, start)
    if not len(fr["15M"]) or pd.Timestamp(fr["15M"]["timestamp"].iloc[-1]) != dec:
        rec.update(status="NO_DATA", note=f"decision bar {dec} not in the 15M data")
        return rec
    rec["asof"] = f"{asof:%Y-%m-%d %H:%M}"
    rec["bars"] = {tf: [str(fr[tf]["timestamp"].iloc[0]), str(fr[tf]["timestamp"].iloc[-1]), len(fr[tf])] for tf in TFS if len(fr[tf])}
    pngs, files = [], []
    for tf in TFS:
        p = BT.png(BT.figure(fr[tf], tf, f"{it['symbol']} · {tf} · cut at {asof:%Y-%m-%d %H:%M} (closed bars only)"))
        fn = f"clean_{tf}.png"
        open(os.path.join(cdir, fn), "wb").write(p)
        pngs.append(p)
        files.append(os.path.relpath(os.path.join(cdir, fn), out_dir))
    rec["charts"] = files
    text = user_text(it, dec, fr)
    open(os.path.join(cdir, "request_text.txt"), "w", encoding="utf-8").write(text)
    est = estimate_usd(model or "opus", len(text))
    rec["estimate_usd"] = round(est, 4)
    if dry_run or client is None:
        rec["status"] = "DRY_RUN"
        return rec
    if state["costs"]:
        est = max(state["costs"]) * 1.3                                    # after the first call: from real costs
    if state["spent"] + est > state["cap"]:
        state["stopped"] = True
        rec.update(status="NOT_RUN_BUDGET", note=f"spent ${state['spent']:.3f} + estimate ${est:.3f} > cap ${state['cap']}")
        return rec
    from vision.signal_audit import cost_usd
    params = build_request(pngs, text, model, effort=os.environ.get("VISION_SIGNAL_EFFORT") or None,
                           thinking=os.environ.get("VISION_SIGNAL_THINKING") or None)
    t0 = time.monotonic()
    try:
        msg = client.messages.create(**params)
    except Exception as exc:                                               # noqa: BLE001 — maybe billed ⇒ cautious estimate recorded
        state["spent"] += est
        state["costs"].append(est)
        record(TASK, model, {"input_tokens": 0, "output_tokens": 0}, est)
        rec.update(status="API_ERROR", error=f"{type(exc).__name__}: {str(exc)[:200]}", cost_usd=round(est, 5), cost_estimated=True)
        return rec
    v, err, usage = parse(msg)
    c = cost_usd(model, usage)
    state["spent"] += c
    state["costs"].append(c)
    record(TASK, model, usage, c)
    rec.update(latency_ms=int((time.monotonic() - t0) * 1000), usage=usage, cost_usd=round(c, 5))
    if err:
        rec.update(status="PARSE_ERROR", error=err)
        return rec
    rec.update(status="OK", vision=v)
    log(f"  {it['id']}: {v['object_state']} · entry {v['entry']} {v['side']} · ${c:.4f}")
    return rec


# ---------------------------------------------------------------------------------------------------------------- table
COLS = ("id", "kind", "symbol", "decision_bar", "object", "known_at", "key_state", "reader_state", "vision_state", "reader_entry",
        "vision_entry", "vision_htf", "vision_zones", "status", "cost_usd", "disagree", "charts")


def _entry(e, side):
    if e is None:
        return ""
    return f"yes {side}" if e else "no"


def row_of(r, reader):
    v = r.get("vision") or {}
    rd = reader or {}
    o = r.get("object") or {}
    vs = v.get("object_state")
    ve = _entry(v.get("entry"), v.get("side")) if v else ""
    re_ = _entry(rd.get("entry"), rd.get("side")) if rd.get("entry") is not None else ""
    dis = []
    if vs and r.get("key_state") and vs != r["key_state"]:
        dis.append(f"state: vision {vs} ≠ key {r['key_state']}")
    if rd.get("state") and r.get("key_state") and rd["state"] != r["key_state"]:
        dis.append(f"state: reader {rd['state']} ≠ key {r['key_state']}")
    if vs and rd.get("state") and vs != rd["state"]:
        dis.append(f"state: vision {vs} ≠ reader {rd['state']}")
    if ve and re_ and ve != re_:
        dis.append(f"entry: vision {ve} ≠ reader {re_}")
    if ve and r.get("key_entry") is not None and ve != _entry(r["key_entry"], r.get("key_side")):
        dis.append(f"entry: vision {ve} ≠ key {_entry(r['key_entry'], r.get('key_side'))}")
    zones = "; ".join(f"{z['tf']} {z['kind'][:3]} {z['lo']:,.0f}–{z['hi']:,.0f}" for z in (v.get("zones_near_price") or [])[:4])
    htf = f"W {v['htf_trend']['weekly']} / D {v['htf_trend']['daily']}" if v.get("htf_trend") else ""
    return {"id": r.get("id"), "kind": r.get("kind"), "symbol": r.get("symbol"), "decision_bar": r.get("decision_bar", ""),
            "object": f"{o.get('tf_band', '')} {o.get('lo', '')}–{o.get('hi', '')}" if o else "",
            "known_at": r.get("known_at", ""), "key_state": r.get("key_state") or "", "reader_state": rd.get("state") or "",
            "vision_state": vs or "", "reader_entry": re_ + (f" ({rd['model']})" if rd.get("model") else ""), "vision_entry": ve,
            "vision_htf": htf, "vision_zones": zones, "status": r.get("status"), "cost_usd": r.get("cost_usd", 0.0) or 0.0,
            "disagree": " | ".join(dis), "charts": " ".join(r.get("charts") or [])}


def build_table(recs, readers, out_dir, meta):
    rows = [row_of(r, readers.get(r.get("id")) or r.get("reader")) for r in recs]
    with open(os.path.join(out_dir, "table.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    e = html.escape
    head = "".join(f"<th>{e(c)}</th>" for c in COLS if c != "charts")
    body = "".join("<tr class='%s'>%s</tr>" % ("dis" if r["disagree"] else "", "".join(f"<td>{e(str(r[c]))}</td>" for c in COLS
                                                                                     if c != "charts")) for r in rows)
    dis = [(r, rec) for r, rec in zip(rows, recs) if r["disagree"]]
    dsec = "".join(f"<h3>{e(r['id'])} · {e(r['decision_bar'])}</h3><p>{e(r['disagree'])}</p>"
                   f"<p class='why'>vision: {e(str((rec.get('vision') or {}).get('state_reason', '')))} · "
                   f"{e(str((rec.get('vision') or {}).get('entry_reason', '')))}</p>"
                   + "".join(f"<img src='{e(p)}' alt='{e(p)}'>" for p in rec.get("charts") or []) for r, rec in dis)
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vision cross-check</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--line:#ddd;--dis:#fff3e0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0e1117;--fg:#e6e6e6;--line:#333;--dis:#3a2a10}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;margin:16px}}
table{{border-collapse:collapse;display:block;overflow-x:auto}}td,th{{border:1px solid var(--line);padding:4px 6px;font-size:12px;
vertical-align:top}}tr.dis td{{background:var(--dis)}}img{{max-width:100%;width:680px;margin:4px}}.why{{opacity:.8}}</style></head><body>
<h1>Vision cross-check — second opinion, never the source of truth</h1>
<p>{e(meta)}</p><table><tr>{head}</tr>{body}</table>
<h2>Disagreements ({len(dis)})</h2>{dsec or '<p>none</p>'}</body></html>"""
    open(os.path.join(out_dir, "table.html"), "w", encoding="utf-8").write(doc)
    return rows


# ---------------------------------------------------------------------------------------------------------------- guards / main
def run_cap(cli_cap=None, g=None):
    """Per-run cap = _global vision_check_run_cap_usd; --cap may only LOWER it."""
    if g is None:
        from vision import config as VC
        g = VC.load("_global")
    cap = float(g["vision_check_run_cap_usd"])
    return min(cap, float(cli_cap)) if cli_cap is not None else cap


def budget_guard(cap, allow_market_hours=False):
    """(ok, message) — global monthly / daily vision budgets (as the blind test)."""
    from vision import config as VC
    from vision import store as VS
    g = VC.load("_global")
    day, month = VS.spent()
    if month + cap > float(g["vision_monthly_budget_usd"]):
        return False, f"month vision spend ${month:.2f} + cap ${cap:.2f} > monthly ${g['vision_monthly_budget_usd']} — stopped"
    now = VS.now_ist()
    market = now.weekday() < 5 and "09:00" <= now.strftime("%H:%M") <= "15:30"
    if market and day + cap > float(g["vision_daily_budget_usd"]) and not allow_market_hours:
        return False, f"market open: today ${day:.2f} + cap ${cap:.2f} > daily ${g['vision_daily_budget_usd']} — run after 15:30"
    return True, ""


def main(argv=None, client=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA", "/root/trade-data"))
    ap.add_argument("--answer-key", default=None, help="answer key JSON (default: newest <trade-data>/review/answer_key/*.json)")
    ap.add_argument("--no-answer-key", action="store_true")
    ap.add_argument("--replay-json", default=None, help="new replay entries: [{symbol, decision_bar, model, side, id?, object?}]")
    ap.add_argument("--reader-json", default=None, help="reader states for answer-key items (see module doc)")
    ap.add_argument("--at", choices=("end", "known"), default="end", help="answer-key decision bar: window end (default) / known_at time")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default=None, help="default VISION_SIGNAL_MODEL env (the model the vision tools use)")
    ap.add_argument("--cap", type=float, default=None, help="lower the per-run cap for this run ($); never above the setting")
    ap.add_argument("--dry-run", action="store_true", help="no API call: charts + request text + table + estimate")
    ap.add_argument("--rebuild", action="store_true", help="no API call: rebuild table from <out-dir>/results.json")
    ap.add_argument("--allow-market-hours", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    model = a.model or os.environ.get("VISION_SIGNAL_MODEL") or None

    if a.rebuild:
        recs = json.load(open(os.path.join(a.out_dir, "results.json"), encoding="utf-8"))
        asofs = {r["id"]: pd.Timestamp(r["asof"]) for r in recs if r.get("asof")}
        rows = build_table(recs, reader_states(a.reader_json, asofs.get), a.out_dir, f"rebuilt · prompt {PROMPT_VERSION}")
        print(f"table rebuilt: {len(rows)} rows · disagreements {sum(1 for r in rows if r['disagree'])}")
        return 0

    items, key_version = [], None
    if not a.no_answer_key:
        kp = a.answer_key or latest_key(a.trade_data)
        if kp:
            ki, key_version = answer_key_items(kp)
            items += ki
    if a.replay_json:
        items += replay_items(a.replay_json)
    if not items:
        print("no items (answer key / replay entries)")
        return 1

    record, cap = (lambda *x: None), 0.0
    live = not a.dry_run and client is None
    if live:
        if model not in PRICED:
            print(f"model {model!r}: price not known exactly — use one of {', '.join(PRICED)}")
            return 1
        from vision import store as VS
        dbp = VS.db_path()
        if not os.path.exists(dbp):
            print(f"vision DB {dbp} not found — set VISION_DB_PATH to the live vision.db (never a new empty one)")
            return 1
        cap = run_cap(a.cap)
        ok, msg = budget_guard(cap, a.allow_market_hours)
        if not ok:
            print(msg)
            return 1
        import anthropic
        client = anthropic.Anthropic(timeout=900.0, max_retries=0)        # no retry ⇒ never billed twice
        record = VS.add_usage
    elif client is not None and not a.dry_run:                            # tests / local fake client: cap from the setting default
        from vision import config as VC
        from vision import store as VS
        cap = run_cap(a.cap, VC.GLOBAL_DEFAULTS)
        record = VS.add_usage

    data = {}
    state = {"spent": 0.0, "cap": cap, "costs": [], "stopped": False}
    recs = []
    for it in items:
        if state["stopped"]:
            recs.append({**{k: it.get(k) for k in ("kind", "id", "symbol", "key_state")}, "status": "NOT_RUN_BUDGET",
                         "note": "cap reached — stopped", "model": model, "prompt_version": PROMPT_VERSION})
            continue
        sym = it["symbol"]
        if sym not in data:
            data[sym] = load_symbol(sym, a.trade_data)
        r = run_item(it, data[sym], a.out_dir, model, None if a.dry_run else client, state, dry_run=a.dry_run, at=a.at, record=record)
        if it.get("reader"):
            r["reader"] = it["reader"]
        recs.append(r)
        if r.get("decision_bar") and r.get("asof"):
            cdir = os.path.join(a.out_dir, "items", f"{r['id']}_{pd.Timestamp(r['decision_bar']):%Y-%m-%d_%H%M}")
            json.dump(r, open(os.path.join(cdir, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    json.dump(recs, open(os.path.join(a.out_dir, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    asofs = {r["id"]: pd.Timestamp(r["asof"]) for r in recs if r.get("asof")}
    total = round(sum(float(r.get("cost_usd") or 0.0) for r in recs), 5)
    est = round(sum(float(r.get("estimate_usd") or 0.0) for r in recs), 4)
    fake = "FAKE vision client (tests / local sample, no API) · " if (client is not None and not live and not a.dry_run) else ""
    meta = (f"{fake}key {key_version} · prompt {PROMPT_VERSION} · model {model} · cap ${cap} · spent ${total} · "
            f"{'DRY RUN (no call) · estimate $' + str(est) if a.dry_run else ''}")
    rows = build_table(recs, reader_states(a.reader_json, asofs.get), a.out_dir, meta)
    summary = {"task": TASK, "fake_client": bool(fake), "prompt_version": PROMPT_VERSION, "key_version": key_version, "model": model, "cap_usd": cap,
               "spent_usd": total, "estimate_usd": est, "dry_run": a.dry_run, "stopped_by_cap": state["stopped"],
               "items": len(recs), "ok": sum(1 for r in recs if r.get("status") == "OK"),
               "disagreements": sum(1 for r in rows if r["disagree"])}
    json.dump(summary, open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8"), indent=1)
    print(f"vision cross-check: {summary['ok']}/{len(recs)} OK · disagreements {summary['disagreements']} · "
          f"{'estimate $%.4f' % est if a.dry_run else 'cost $%.4f (cap $%.2f)' % (total, cap)}"
          f"{' · STOPPED at cap' if state['stopped'] else ''} · {os.path.join(a.out_dir, 'table.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
