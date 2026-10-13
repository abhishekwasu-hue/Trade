"""scripts/golden_vision_check.py — R0 golden days through Vision V4 (design §11.1, §12.5). **Audit only — no order, no rule change.**

Abhi VPS वर चालवतो (VPS चा key; sandbox मध्ये कधीच खऱ्या key ने नाही). प्रत्येक केस (cases JSON — तारखा / अपेक्षा फक्त fixture मध्ये):
  data (policy guard: NIFTY holdout 2024-04 … 2026-06 कधीच load नाही — सगळ्या symbols ना) ⇒ decision bar वर कापलेले W / D / 1H / 15M / 5M
  frames ⇒ **anonymise** (symbol लपवला, तारखा पूर्ण आठवड्यांनी मागे, किंमती × scale, tick ला round) ⇒ charts + OHLC facts + V4 prompt
  (Method Pack cached prefix) ⇒ Vision ⇒ checklist validate (prices facts मध्ये) ⇒ प्रत्येक item वि. Abhi ची अपेक्षा (TODO = अजून नाही).

    set -a && . ./.env && set +a
    python3 scripts/golden_vision_check.py --dry-run --data NIFTY=/root/trade-data/upstox/NIFTY_1m_….csv.gz
    python3 scripts/golden_vision_check.py --cases /root/trade-data/golden_v4/cases.json --out-dir /root/trade-data/review/golden_v4/run1

FUT volume नेहमी (Abhi R0-5): `--futures SYMBOL=PATH` / case "futures" / default collector `data/oe_futures_5min_<SYM>.parquet` +
trade-data exports; decision bar ला नाही ⇒ facts मध्ये स्पष्ट "volume NA" (कधीच शांत pass नाही). Item 6 साठी code मोजतो: decision bar FUT
volume ÷ आधीच्या 8 bars ची सरासरी आणि 5M CHoCH by close (output मध्ये). Case status "confirmed…" नसेल (draft — pending Abhi ✅) ⇒ सगळे
निकाल "PROVISIONAL". प्रत्येक निकालात item ⇒ decision3 ①–⑥ map (R0-1).
--dry-run: सगळं बनवतो (frames, anonymise, charts, prompt), API call नाही; token + $ अंदाज छापतो. खर्च vision_usage मध्ये
(task golden_v4, pack_version); आजचा Vision खर्च + अंदाज > दैनिक budget ($2) ⇒ थांबतो.
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vision import checklist as CK      # noqa: E402
from vision import method_pack as MP    # noqa: E402
from vision import v4 as V4             # noqa: E402

CASES_DEFAULT = os.path.join(ROOT, "tests", "fixtures", "golden_vision_v4_cases.json")
TFS = ("W", "D", "1H", "15M", "5M")
TASK = "golden_v4"
SHIFT_WEEKS = 297                                                          # ≈ 5.7 वर्षं मागे (पूर्ण आठवडे ⇒ वार / वेळ तेच; तारीख-महिना वेगळे)
SCALE = 0.731                                                              # किंमत × scale (tick ला round)
TICK = 0.05
LTF_SESSIONS = 2                                                           # 5M: चालू + मागचा session (design §5)
MAX_TOKENS = 8000
VOL_WINDOW = 8                                                             # decision bar volume ÷ आधीच्या इतक्या 15M bars ची सरासरी
TRADE_DATA = os.environ.get("TRADE_DATA_DIR") or next(
    (p for p in (os.path.join(os.path.dirname(ROOT), "trade-data"), os.path.expanduser("~/trade-data")) if os.path.isdir(p)),
    os.path.join(os.path.dirname(ROOT), "trade-data"))                     # VPS: /root/trade-data


def is_confirmed(case):
    """Abhi ✅ ने निश्चित झालेली अपेक्षाच "confirmed"; बाकी (draft — pending Abhi ✅ / template) ⇒ निकाल provisional."""
    return str(case.get("status") or "").strip().lower().startswith("confirmed")


def default_futures(symbol):
    """FUT 5M volume चे default स्रोत: VPS collector (data/oe_futures_5min_<SYM>.parquet) + trade-data futures* / live_export exports."""
    import glob
    sym = str(symbol).upper()
    return ([os.path.join(ROOT, "data", f"oe_futures_5min_{sym}.parquet")]
            + sorted(glob.glob(os.path.join(TRADE_DATA, "futures*", f"oe_futures_5min_{sym}*.parquet")))
            + sorted(glob.glob(os.path.join(TRADE_DATA, "live_export", "*", f"oe_futures_5min_{sym}.parquet"))))


def load_futures(paths):
    """FUT 5M files ⇒ near-month (legs2.volume) [timestamp, volume, expiry], holdout rows नाहीत. काहीच नाही ⇒ None (volume NA)."""
    from legs2 import volume as LV
    parts = []
    for p in paths or []:
        if p and os.path.exists(p):
            x = pd.read_parquet(p) if str(p).endswith(".parquet") else pd.read_csv(p)
            t = pd.to_datetime(x["timestamp"])
            x["timestamp"] = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None) if t.dt.tz is not None else t
            parts.append(x)
    if not parts:
        return None
    raw = pd.concat(parts, ignore_index=True)
    raw = raw.drop_duplicates(["timestamp"] + (["contract"] if "contract" in raw.columns else []), keep="last")
    nm = LV.near_month(raw)
    return nm if len(nm) else None


def attach_volume(frames, fut, asof):
    """15M / 5M frames ला FUT volume column (asof नंतर संपणारी row कधीच नाही). fut None ⇒ frames तसेच."""
    if fut is None or not len(fut):
        return frames
    from legs2 import volume as LV
    f = fut[pd.to_datetime(fut["timestamp"]) + pd.Timedelta(minutes=5) <= pd.Timestamp(asof)]
    out = dict(frames)
    if "15M" in out and len(out["15M"]):
        out["15M"] = out["15M"].assign(volume=LV.bar_volume(out["15M"], f))
    if "5M" in out and len(out["5M"]):
        v5 = dict(zip(pd.to_datetime(f["timestamp"]), f["volume"].astype(float)))
        out["5M"] = out["5M"].assign(volume=[v5.get(pd.Timestamp(x), float("nan")) for x in out["5M"]["timestamp"]])
    return out


def measure(frames, case, area=None):
    """Item 6 साठी code ने मोजलेलं (खऱ्या frames वर, Vision ला नाही; Abhi च्या तुलनेसाठी): decision bar FUT volume ÷ आधीच्या VOL_WINDOW
    15M bars ची सरासरी, आणि 5M CHoCH by close (decision3.method.ltf_choch; study = decision session, area दिल्यास पहिला स्पर्श)."""
    import numpy as np
    from decision3 import method as M
    out = {"fut_volume": "NA", "ltf_choch": "NA"}
    f15 = frames.get("15M")
    if f15 is not None and len(f15) and "volume" in f15.columns:
        v = f15["volume"].to_numpy(float)
        prev = v[-1 - VOL_WINDOW:-1]
        prev = prev[~np.isnan(prev)]
        if not np.isnan(v[-1]) and len(prev) and prev.mean() > 0:
            out["fut_volume"] = f"{v[-1] / prev.mean():.2f}x the previous {len(prev)} 15M bars' average"
    f5 = frames.get("5M")
    if f5 is not None and len(f5) and f15 is not None and len(f15):
        d = -1 if str(case.get("direction", "")).upper().startswith("BEAR") else 1
        t_end = pd.Timestamp(f15["bar_end"].iloc[-1]) if "bar_end" in f15.columns else pd.Timestamp(f15["timestamp"].iloc[-1]) +             pd.Timedelta(minutes=15)
        days = sorted(pd.to_datetime(f5["timestamp"]).dt.normalize().unique())
        t_start = pd.Timestamp(days[-1]) + pd.Timedelta(hours=9, minutes=15)
        if area:
            day5 = f5[pd.to_datetime(f5["timestamp"]) >= t_start]
            hit = day5[(day5["low"] <= max(area)) & (day5["high"] >= min(area))]
            if len(hit):
                t_start = pd.Timestamp(hit["timestamp"].iloc[0])
        t_ctx = pd.Timestamp(days[0]) + pd.Timedelta(hours=9, minutes=15)
        try:
            ch = M.ltf_choch(M.ltf_frame(f5, 5, "5M"), d, t_ctx, t_start, t_end)
            out["ltf_choch"] = ch.get("line") or ("done" if ch.get("done") else "not done")
        except Exception as exc:                                           # noqa: BLE001
            out["ltf_choch"] = f"NA ({type(exc).__name__})"
    return out


def is_todo(v):
    return isinstance(v, str) and "TODO" in v


# ----------------------------------------------------------------------------------------------------------- data + policy
def guard(decision):
    """Decision bar ला परवानगी आहे का (holdout ⇒ HoldoutError; annotation purpose — golden + illustration काळ)."""
    from elliott import data_policy as DP
    if DP.period(decision) == "HOLDOUT":
        raise DP.HoldoutError(f"{decision}: sealed holdout (2024-04 … 2026-06) — कधीच load नाही")
    if not DP.allowed(decision, "annotation"):
        raise DP.HoldoutError(f"{decision}: purpose annotation ला परवानगी नाही")


def load_data(paths):
    """CSV / parquet ⇒ [timestamp (naive), open, high, low, close(, volume)] + policy: parquet `DP.load_parquet` ने (holdout-only file
    वाचायलाच नकार), नंतर सगळ्यांवर `filter_allowed` (holdout rows कधीच परत येत नाहीत)."""
    from elliott import data_policy as DP
    parts = []
    for p in paths:
        if os.path.basename(str(p)) in DP.HOLDOUT_FILES:                     # DP.load_parquet चाच नकार (वाचायलाच नाही)
            raise DP.HoldoutError(f"{os.path.basename(str(p))} हा sealed holdout काळ आहे — वाचायचा नाही")
        parts.append(pd.read_parquet(p) if str(p).endswith(".parquet") else pd.read_csv(p, parse_dates=["timestamp"]))
    raw = pd.concat(parts, ignore_index=True)
    ts = pd.to_datetime(raw["timestamp"])
    if ts.dtype == object:                                                 # मिश्र offsets ⇒ UTC मार्गे (मग IST)
        ts = pd.to_datetime(raw["timestamp"], utc=True)
    if ts.dt.tz is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    raw["timestamp"] = ts                                                  # IST-naive आधी, मगच policy filter
    raw = raw.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    return DP.filter_allowed(raw, "annotation")


def holdout_gap(frames):
    """कोणतीही frame (W / D / 1H / 15M / 5M) sealed holdout ओलांडून (आधीचा + नंतरचा data, मधे holdout काढलेला) ⇒ True — असा chart खोटा
    trend दाखवतो ⇒ केस नाकारा."""
    from elliott import data_policy as DP
    for tf in frames:
        f = frames.get(tf)
        if f is None or not len(f):
            continue
        ts = pd.to_datetime(f["timestamp"])
        if ts.min() < DP.HOLDOUT_START and ts.max() >= DP.CONTAMINATED_START:
            return True
    return False


def short_history(frames):
    """Policy मुळे W / D इतिहास लहान (blind_test BARS पेक्षा कमी bars) ⇒ [tf]; item 1 (top-down) कमी विश्वासाचा."""
    from vision_led import blind_test as BT
    return [tf for tf in ("W", "D") if tf in frames and len(frames[tf]) < BT.BARS[tf]]


def build_frames(m1, decision):
    """decision bar (15M start) वर कापलेले बंद bars: W / D / 1H / 15M (vision_led.blind_test.frames) + 5M (शेवटचे LTF_SESSIONS)."""
    from market_state import core as MC
    from vision_led import blind_test as BT
    fr, asof = BT.frames(m1, decision)
    cut = m1[pd.to_datetime(m1["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
    f5 = MC.frame(cut, "5m", asof)
    days = sorted(pd.to_datetime(f5["timestamp"]).dt.normalize().unique())[-LTF_SESSIONS:]
    fr = dict(fr)
    fr["5M"] = f5[pd.to_datetime(f5["timestamp"]).dt.normalize().isin(days)].reset_index(drop=True)
    return fr, asof


# ----------------------------------------------------------------------------------------------------------- anonymise
def anonymiser(shift_weeks=SHIFT_WEEKS, scale=SCALE, tick=TICK):
    """(time_fn, price_fn) — तारखा पूर्ण आठवड्यांनी मागे, किंमत × scale tick ला round."""
    shift = pd.Timedelta(days=7 * int(shift_weeks))

    def t(x):
        return pd.Timestamp(x) - shift

    def p(x):
        return round(round(float(x) * scale / tick) * tick, 2)
    return t, p


def anonymise(frames, asof, shift_weeks=SHIFT_WEEKS, scale=SCALE, tick=TICK):
    """Frames ⇒ नवे frames (timestamp / bar_end shift, OHLC × scale); real values परत जात नाहीत. Volume (असल्यास) तसाच (सापेक्ष)."""
    t, p = anonymiser(shift_weeks, scale, tick)
    out = {}
    for tf, f in frames.items():
        g = f.copy()
        for c in ("timestamp", "bar_end"):
            if c in g.columns:
                g[c] = pd.to_datetime(g[c]) - pd.Timedelta(days=7 * int(shift_weeks))
        for c in ("open", "high", "low", "close"):
            if c in g.columns:
                g[c] = [p(x) for x in g[c]]
        out[tf] = g.reset_index(drop=True)
    return out, t(asof)


# ----------------------------------------------------------------------------------------------------------- facts / images
def _vol(x):
    return "NA" if x is None or x != x else f"{int(round(float(x)))}"


def ohlc_table(df, tf):
    from vision_led import blind_test as BT
    has_vol = "volume" in df.columns and tf in ("15M", "5M")
    if tf in ("W", "D", "1H") or (tf == "15M" and not has_vol):
        return BT.ohlc_table(df, tf)
    rows = [f"{pd.Timestamp(r.timestamp):%Y-%m-%d %H:%M},{r.open:.2f},{r.high:.2f},{r.low:.2f},{r.close:.2f}"
            + (f",{_vol(r.volume)}" if has_vol else "") for r in df.itertuples()]
    label = {"15M": "15M (bar start IST)", "5M": "5M (bar start; current + previous session)"}[tf]
    return (f"{label} OHLC — time,open,high,low,close{',fut_volume' if has_vol else ''}; last row = last CLOSED bar:\n"
            + "\n".join(rows))


def facts_text(case, fr, asof, area=None, short_note=False, volume_na=True):
    """Anonymised facts (symbol लपवलेला). area = anonymised [lo, hi] किंवा None."""
    bear = str(case["direction"]).upper().startswith("BEAR")
    dec = fr["15M"]["timestamp"].iloc[-1] if len(fr["15M"]) else asof
    head = [f"Index: hidden (anonymised: dates shifted, prices rescaled — use only the numbers below). Decision bar = the 15M bar "
            f"starting {pd.Timestamp(dec):%Y-%m-%d %H:%M} (closed at {pd.Timestamp(asof):%H:%M}); no data after that close exists.",
            f"Proposal under audit: {'BEARISH — bear call spread' if bear else 'BULLISH — bull put spread'}, entry on the close of the "
            "decision bar (treated as the commitment candle).",
            (f"Proposed area: {area[0]:,.2f}-{area[1]:,.2f} ({'supply' if bear else 'demand'})." if area else
             "Proposed area: not given — judge the area from the charts and tables."),
            ("Futures volume: NA — no futures data for this session. Items 5 and 6: the volume part is NA; never pass an item on "
             "volume." if volume_na else
             "Futures volume: the 15M and 5M tables carry the near-month futures volume (fut_volume; NA where missing). Judge "
             "volume for items 5 and 6 from it.")]
    if short_note:
        head.append("History note: older data is not provided (data policy), so the Weekly / Daily history is short; judge item 1 on "
                    "what is shown and say so in its evidence.")
    return "\n".join(head + [ohlc_table(fr[tf], tf) for tf in TFS if tf in fr])


def render_images(fr, asof):
    from vision_led import blind_test as BT
    return [BT.png(BT.figure(fr[tf], tf, f"INDEX · {tf} · cut at {pd.Timestamp(asof):%Y-%m-%d %H:%M} (closed bars only)"))
            for tf in TFS if tf in fr and len(fr[tf])]


# ----------------------------------------------------------------------------------------------------------- compare
def compare(data, expected):
    """Vision checklist वि. Abhi ची अपेक्षा ⇒ (rows, verdict row). Row = (n, नाव, got, evidence, expected, ✔ / ✘ / TODO)."""
    exp = expected or {}
    rows = []
    items = {it["n"]: it for it in (data or {}).get("items", [])}
    for n, (_, name, _) in CK.ITEMS.items():
        e = exp.get(str(n), "TODO")
        g = items.get(n)
        got = g["status"] if g else None
        mark = "TODO" if is_todo(e) else ("—" if got is None else ("✔" if got == e else "✘"))   # — = Vision ने उत्तर दिलं नाही (dry-run)
        rows.append((n, name, got, g["evidence"] if g else "", e, mark))
    ev = exp.get("verdict", "TODO")
    gv = (data or {}).get("verdict")
    return rows, ("verdict", gv, ev, "TODO" if is_todo(ev) else ("—" if gv is None else ("✔" if gv == ev else "✘")))


def print_case(rec, out=print):
    prov = " · PROVISIONAL (expected answers are a draft — pending Abhi ✅)" if rec.get("provisional") else ""
    out(f"\n=== {rec['id']} · {rec['status']}{prov} ===")
    for k in ("why", "error", "warnings", "volume", "measured"):
        if rec.get(k):
            out(f"  {k}: {rec[k]}")
    if rec.get("estimate"):
        e = rec["estimate"]
        out(f"  tokens: system ≈ {e['system_tokens']:,} (cached prefix) + fresh ≈ {e['fresh_input_tokens']:,} ({rec['n_images']} images)"
            f" + output ≤ {e['max_output_tokens']:,}")
        out(f"  cost est.: uncached ${e['usd_uncached']:.4f} · first call (cache write) ${e['usd_cache_write']:.4f} · cached "
            f"${e['usd_cached']:.4f}" + ("" if rec.get("model") else "  (model not set ⇒ conservative unknown-model prices)"))
    if rec.get("cost_usd"):
        out(f"  cost: ${rec['cost_usd']:.4f}")
    tag = " (provisional)" if rec.get("provisional") else ""
    for n, name, got, ev, exp, mark in rec.get("rows") or []:
        out(f"  {n}. {name:<20} [{CK.DECISION3_MAP[n]}] got {got or '-':<5} expected {exp:<5} {mark}{tag}  {ev[:100]}")
    if rec.get("verdict_row"):
        _, gv, ev, mark = rec["verdict_row"]
        out(f"  verdict: got {gv} · expected {ev} {mark}{tag}")


# ----------------------------------------------------------------------------------------------------------- run
def run_case(case, a, deps, state):
    rec = {"id": case.get("id"), "status": None, "model": a.model, "provisional": not is_confirmed(case),
           "case_status": case.get("status"), "decision3_map": dict(CK.DECISION3_MAP)}
    for k in ("decision", "direction"):
        if is_todo(case.get(k)) or not case.get(k):
            rec.update(status="SKIPPED_TODO", why=f"{k} TODO (Abhi)")
            return rec
    paths = a.data.get(case["symbol"]) or ([] if is_todo(case.get("data")) else list(case.get("data") or []))
    if not paths:
        rec.update(status="SKIPPED_TODO", why=f"data file TODO — pass --data {case['symbol']}=PATH[,PATH]")
        return rec
    decision = pd.Timestamp(case["decision"])
    try:
        deps["guard"](decision)
    except Exception as exc:                                               # noqa: BLE001 — HoldoutError / अवैध तारीख
        rec.update(status="REFUSED_POLICY", why=str(exc))
        return rec
    m1 = deps["load"](paths)
    fr, asof = deps["frames"](m1, decision)
    if not len(fr.get("15M", [])) or pd.Timestamp(fr["15M"]["timestamp"].iloc[-1]) != decision:
        rec.update(status="NO_DATA", why=f"decision bar {decision} not in the data")
        return rec
    if holdout_gap(fr):
        rec.update(status="REFUSED_HOLDOUT_GAP", why="frames span the sealed holdout gap — pass only data on one side of it")
        return rec
    short = short_history(fr)
    if short:
        rec["warnings"] = [f"item 1 unreliable: short {'/'.join(short)} history (data policy)"]
    fpaths = a.futures.get(case["symbol"]) or ([] if is_todo(case.get("futures")) else list(case.get("futures") or [])) \
        or default_futures(case["symbol"])
    fr = attach_volume(fr, deps["load_fut"](fpaths), asof)
    f15 = fr.get("15M")
    vol_ok = bool(f15 is not None and len(f15) and "volume" in f15.columns and f15["volume"].iloc[-1] == f15["volume"].iloc[-1])
    rec["volume"] = "FUT" if vol_ok else "NA"
    if not vol_ok:
        rec.setdefault("warnings", []).append("futures volume NA for the decision bar — items 5 / 6 volume part NA (not a pass)")
    real_area = case.get("area") if isinstance(case.get("area"), (list, tuple)) and len(case.get("area")) == 2 else None
    rec["measured"] = measure(fr, case, real_area)
    afr, aasof = anonymise(fr, asof, a.shift_weeks, a.scale, a.tick)
    _, price = anonymiser(a.shift_weeks, a.scale, a.tick)
    area = case.get("area")
    area = [price(area[0]), price(area[1])] if isinstance(area, (list, tuple)) and len(area) == 2 else None
    facts = facts_text(case, afr, aasof, area, short_note=bool(short), volume_na=not vol_ok)
    images = deps["render"](afr, aasof)
    anchors = CK.facts_prices(afr, area)                                   # OHLC + area फक्त (volume / counts नाहीत)
    known = CK.facts_prices(anchors, facts)
    pack = deps["pack"]()
    rec.update(n_images=len(images), pack_version=pack[1], estimate=V4.estimate(len(images), facts, pack[0], a.model, a.max_tokens))
    if a.out_dir:
        cdir = os.path.join(a.out_dir, str(case["id"]))
        os.makedirs(cdir, exist_ok=True)
        open(os.path.join(cdir, "facts.txt"), "w", encoding="utf-8").write(facts)
        for tf, png in zip([tf for tf in TFS if tf in afr and len(afr[tf])], images):
            open(os.path.join(cdir, f"input_{tf}.png"), "wb").write(png)
    if a.dry_run:
        rec["status"] = "DRY_RUN"
        rec["rows"], rec["verdict_row"] = compare(None, case.get("expected"))
        return rec
    est = rec["estimate"]["usd_uncached"]
    ok, why = V4.budget_ok(est, state["g"], state["by_task"], state["today"], task=TASK)   # दैनिक − signals राखीव, मासिक
    if not ok:
        rec.update(status="NOT_RUN_BUDGET", why=why)
        return rec
    res = V4.audit(deps["client"](), images, facts, a.model, known, pack=pack, on_usage=deps["on_usage"](pack[1]), anchors=anchors,
                   effort=os.environ.get("VISION_SIGNAL_EFFORT") or None, thinking=os.environ.get("VISION_SIGNAL_THINKING") or None)
    d, m, n = state["by_task"].get(TASK, (0.0, 0.0, 0))
    c = res.get("cost_usd") or 0.0
    state["by_task"][TASK] = (d + c, m + c, n + 1)
    rec.update(status=res["status"].upper(), error=res.get("error"), cost_usd=res.get("cost_usd"), usage=res.get("usage"),
               checklist=res.get("data"))
    rec["rows"], rec["verdict_row"] = compare(res.get("data"), case.get("expected"))
    return rec


def default_deps(a):
    def client():
        import anthropic
        return anthropic.Anthropic(timeout=600.0, max_retries=0)           # retry नाही ⇒ दुहेरी billing नाही

    def on_usage(ver):
        from vision import store as VS
        return lambda u, c: VS.add_usage(TASK, a.model, u, c, pack_version=ver)
    return {"guard": guard, "load": load_data, "frames": build_frames, "render": render_images, "pack": MP.load, "client": client,
            "on_usage": on_usage, "load_fut": load_futures}


def _data_arg(items):
    out = {}
    for x in items or []:
        sym, _, paths = x.partition("=")
        if not paths:
            raise SystemExit(f"--data {x!r}: SYMBOL=PATH[,PATH] हवं")
        out[sym.strip().upper()] = [p for p in paths.split(",") if p]
    return out


def main(argv=None, deps=None, out=print):
    ap = argparse.ArgumentParser(description="Golden days through Vision V4 (audit only)")
    ap.add_argument("--cases", default=CASES_DEFAULT, help="cases JSON (Abhi चा भरलेला copy private trade-data मध्ये ठेवता येतो)")
    ap.add_argument("--only", nargs="+", help="फक्त हे case ids")
    ap.add_argument("--data", nargs="+", default=[], help="SYMBOL=PATH[,PATH] (case मधल्या data ऐवजी)")
    ap.add_argument("--futures", nargs="+", default=[], help="SYMBOL=PATH[,PATH] FUT 5M volume (default: collector "
                    "data/oe_futures_5min_<SYM>.parquet + trade-data futures* / live_export); नसेल ⇒ volume NA (स्पष्ट)")
    ap.add_argument("--out-dir", default=None, help="charts / facts इथे (private trade-data); नसेल ⇒ disk वर काही नाही")
    ap.add_argument("--model", default=None, help="default VISION_SIGNAL_MODEL env")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--shift-weeks", type=int, default=SHIFT_WEEKS)
    ap.add_argument("--scale", type=float, default=SCALE)
    ap.add_argument("--tick", type=float, default=TICK)
    ap.add_argument("--dry-run", action="store_true", help="API call नाही — सगळं बनवून token / $ अंदाज")
    a = ap.parse_args(argv)
    a.model = a.model or os.environ.get("VISION_SIGNAL_MODEL") or None
    a.data = _data_arg(a.data)
    a.futures = _data_arg(a.futures)
    deps = {**default_deps(a), **(deps or {})}
    state = {"by_task": {}, "g": None, "today": None}
    if not a.dry_run:
        if not a.model:
            out("⛔ VISION_SIGNAL_MODEL env नाही (किंवा --model)")
            return 1
        from vision import config as VC
        if not VC.api_key_present():
            out("⛔ API key env मध्ये नाही (VPS: set -a && . ./.env && set +a)")
            return 1
        from vision import store as VS
        now = VS.now_ist()
        state.update(by_task=dict(VS.spent_by_task()), g=VC.load("_global"),
                     today=now.replace(tzinfo=None) if getattr(now, "tzinfo", None) else now)
    cases = json.load(open(a.cases, encoding="utf-8"))["cases"]
    if a.only:
        cases = [c for c in cases if c.get("id") in a.only]
    recs = []
    for c in cases:
        try:
            r = run_case(c, a, deps, state)
        except Exception as exc:                                           # noqa: BLE001 — एका केसची चूक बाकी थांबवत नाही
            r = {"id": c.get("id"), "status": "ERROR", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        recs.append(r)
        print_case(r, out)
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
        json.dump(recs, open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    tot = sum((r.get("estimate") or {}).get("usd_uncached", 0.0) for r in recs)
    spent = sum(r.get("cost_usd") or 0.0 for r in recs)
    out(f"\nCases {len(recs)} · est. total (uncached) ${tot:.4f}" + ("" if a.dry_run else f" · spent ${spent:.4f}")
        + (" · results PROVISIONAL until Abhi ✅ confirms the expected answers" if any(r.get("provisional") for r in recs) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
