"""simple_core/engine.py — SIMPLE CORE (Abhi 2026-10-08). फक्त entry चा area आणि confirmation; बाकी सगळं execution settings / context.

  1. Trend: HTF (market_state) — down ⇒ seller area शोधा, up ⇒ buyer area. (Range ⇒ side impulse वरून; F4 विरोध ⇒ signal नाही.)
  2. Area: trade बाजूचे zones (chart_reader.zones: flip, supply/demand base, trendline, PDH / gap edge, swing high/low cluster …),
     area_merge_mr अंतरातले एकत्र ⇒ एक area (trendline चं मूल्य त्या bar वर).
  3. Pause at area: commitment आधी area ला लागलेले (± area_tol_mr) indecision bars — लहान body / median पेक्षा लहान range / दोन्ही
     बाजूंचे wicks. किमान pause_min_bars. Area च्या कडेचा real break (elliott/breaks.py) ⇒ setup रद्द.
  4. Commitment: trend दिशेने मजबूत candle — एकटा bar (टोक area ला लागलेलं) किंवा शेवटचा pause bar (touch) + हा bar (KB "touch → मजबूत
     close"): range commit_strength_min_mr–commit_strength_max_mr × MR, body ≥ commit_body_min, close टोकाजवळ. Bar बंद ⇒ ENTRY SIGNAL.
  5. एक setup = एक entry (Tracker: त्याच area वर पुन्हा नाही). Area पासून दूर ⇒ नाही (chase नाही).

B1 (Abhi K-10): pause + commitment मालिकेतला कोणताही candle area ला लागला (± area_tol_mr) तरी पुरे — commitment स्वतः लागलेला नसला तरी,
   आधीचा pause bar area वर असेल तर valid. Flip zone: pause तुटल्यानंतरच्या (role_since) bars मधूनच.
A2 Testing (protected real break, पुष्टी नाही): फक्त (a) तुटलेल्या protected / PDL / PDH चा flip retest break दिशेने (G4) किंवा (b) range
   च्या कडा (वर bear, खाली bull) — बाकी TESTING_ONLY_FLIP_OR_EDGE.
Motive wave (waves.py): setup label G1 / G8 / G9 आणि ref_levels मध्ये wave3_projection, wave5_projection, wave1_origin, wave1_extreme,
   subwave_origin (gray ⇒ None + ref_notes मध्ये "लागू नाही — कारण"). Wave 1 चं टोक (wave 3 ने पार केलं) ⇒ flip area.

Signal = {side, trigger_time, trigger_price (commitment close), area {id, type, low, high}, pause_bars, commitment {open, high, low, close},
ref_levels {structural_invalidation, commitment_extreme, next_opposite_area, impulse_end}, context_story}. ref_levels फक्त माहिती —
त्यांचा वापर execution settings ठरवतात (execution.py). फक्त बंद bars (no-lookahead).
"""
import numpy as np
import pandas as pd

from . import flags as FL
from . import settings as SS
from . import waves as WV

TESTING_CODE = "TESTING_ONLY_FLIP_OR_EDGE"


def _band(z, back):
    sl = float(z.get("slope") or 0.0)
    return float(z["low"]) - sl * back, float(z["high"]) - sl * back


def areas(zones, side, back=0, merge=0.0):
    """trade बाजूचे जिवंत zones ⇒ merge अंतरातले एकत्र areas [{id, type, low, high, zones}] (bar `back` bars आधीच्या मूल्यावर)."""
    want = "sell" if side < 0 else "buy"
    zs = [z for z in zones or [] if (z.get("side") or ("sell" if z.get("role") == "RESISTANCE" else "buy")) == want
          and z.get("kind", "solid") == "solid" and z.get("state") not in ("BROKEN", "DEAD", "MAGNET")
          and not (z.get("tool") == "f" and z.get("valid") is False)]           # अवैध trendline area नाही
    bands = sorted(((*_band(z, back), z) for z in zs), key=lambda t: t[0])
    out = []
    for lo, hi, z in bands:
        if out and lo <= out[-1]["high"] + merge:
            a = out[-1]
            a["high"] = max(a["high"], hi)
            a["zones"].append(z)
        else:
            out.append({"low": lo, "high": hi, "zones": [z]})
    for a in out:
        a["id"] = " + ".join(str(z.get("zid") or z.get("id")) for z in a["zones"])
        a["type"] = " + ".join(str(z.get("type") or z.get("tool")) for z in a["zones"])
        a["source_ids"] = [z.get("id") for z in a["zones"]]
    return out


def _touch(h, lo, a, side, tol):
    return (h >= a["low"] - tol and lo <= a["high"] + tol)


def _is_pause(o, h, lo, c, mr, s):
    rng = max(h - lo, 1e-9)
    body = abs(c - o) / rng
    up, dn = (h - max(o, c)) / rng, (min(o, c) - lo) / rng
    return body <= s["pause_body_max"] or rng / mr <= s["pause_range_max_mr"] or (up >= s["pause_wick_min"] and dn >= s["pause_wick_min"])


def _commit_ok(o, h, lo, c, side, mr, s):
    rng = max(h - lo, 1e-9)
    cl = (c - lo) / rng
    strong = s["commit_strength_min_mr"] * mr <= rng <= s["commit_strength_max_mr"] * mr and abs(c - o) / rng >= s["commit_body_min"]
    return strong and ((c < o and cl <= s["commit_close_max"]) if side < 0 else (c > o and cl >= 1 - s["commit_close_max"]))


class Tracker:
    """एक setup = एक entry: त्याच बाजूचा, आधी signal दिलेला area — किंमत-पट्टा overlap **किंवा** तेच zones (trendline उतरत / चढत
    गेली तरी). Structural invalidation पलीकडे close (on_bar) किंवा area पलीकडे acceptance ⇒ नोंद मोकळी (नवा setup शक्य)."""

    def __init__(self):
        self.used = []                         # [{side, low, high, ids, inv, at}]

    def _hit(self, side, area):
        ids = set(str(x) for x in area.get("source_ids") or [])
        return next((u for u in self.used if u["side"] == int(side) and ((area["low"] <= u["high"] and u["low"] <= area["high"])
                                                                         or (ids & u["ids"]))), None)

    def seen(self, side, area):
        return self._hit(side, area) is not None

    def at(self, side, area):
        u = self._hit(side, area)
        return u["at"] if u else ""

    def add(self, side, area, t, invalidation=None):
        self.used.append({"side": int(side), "low": float(area["low"]), "high": float(area["high"]),
                          "ids": set(str(x) for x in area.get("source_ids") or []), "inv": invalidation, "at": str(t)})

    def release(self, side, area):
        u = self._hit(side, area)
        self.used = [x for x in self.used if x is not u]

    def on_bar(self, close):
        """नवा बंद bar: ज्या setups ची structural invalidation close ने पार झाली त्या मोकळ्या."""
        self.used = [u for u in self.used if u["inv"] is None or not ((close > u["inv"]) if u["side"] < 0 else (close < u["inv"]))]


def detect(df, zones, ctx, mr, s=None, tracker=None):
    """area pause सुरू होण्याआधी अस्तित्वात हवा (pullback "आपल्या" area ला आला): signal चा area त्याच episode मध्ये जन्मलेल्या zone
    (z["bar"] ≥ पहिला pause bar, उदा. याच rally चा swing high) वर असेल तर तो zone वगळून पुन्हा तपासा.
    Testing (ctx["testing"]) ⇒ फक्त flip retest (G4) / range edge. Signal वर motive wave context (setup, wave refs)."""
    side = int(ctx["side"] or 0) if "side" in ctx else int(ctx.get("trend") or 0)
    if not side and ctx.get("testing"):
        return _testing(df, zones, ctx, mr, s, tracker)
    zs = list(zones or [])
    piv = ctx.get("pivots")
    if side and ctx.get("impulse") and len(df):
        fz = FL.flag_zone(df, ctx["impulse"], side, mr, s)                # G8: flag channel हाच area
        if fz:
            zs.append(fz)
    r = _detect_episode(df, zs, ctx, mr, s, tracker)
    sg = r.get("signal")
    if sg:
        if "flag channel" in str(sg["area"].get("type", "")):
            sg["setup"] = "G8"
            sg["context_story"] += " · G8: flag channel मधून बाहेर commitment"
        _wave_context(sg, df, piv, side, s)
    return r


def _detect_episode(df, zs, ctx, mr, s, tracker):
    for _ in range(4):
        r = _detect(df, zs, ctx, mr, s, None)
        sg = r.get("signal")
        if not sg:
            break
        p0 = int(sg.get("_p0", 0))
        late = [z for z in zs if z.get("id") in (sg["area"].get("source_ids") or []) and z.get("bar") is not None and int(z["bar"]) >= p0]
        if not late:
            break
        bad = {id(z) for z in late}
        zs = [z for z in zs if id(z) not in bad]
    r = _detect(df, zs, ctx, mr, s, tracker)
    if r.get("signal"):
        r["signal"].pop("_p0", None)
        r["signal"]["area"].pop("source_ids", None)
    return r


WAVE_REFS = ("wave3_projection", "wave5_projection", "wave1_origin", "wave1_extreme", "subwave_origin")


def _wave_context(sg, df, piv, side, s):
    """टप्पा B §2.5: waves.py चा स्वतंत्र count निर्णयात नाही — फक्त तुलनेसाठी नोंद (`waves_cmp`). Setup label / wave refs count_source
    (एकच preferred count) मधून signal_at मध्ये."""
    w = WV.count(df, piv or [], side, len(df) - 1, s)
    sg["waves_cmp"] = {"setup": w["setup"], "gray": w["gray"], "story": w["story"]}
    why = "लागू नाही — wave refs फक्त एकाच preferred count मधून (G1 / G9), reading layer मध्ये भरतात"
    for kk in WAVE_REFS:                                                   # execution ला "का नाही" कळावं (count नसेल तर तसंच राहतं)
        sg["ref_levels"].setdefault(kk, None)
        sg.setdefault("ref_notes", {})[kk] = why


def _testing(df, zones, ctx, mr, s, tracker):
    """A2: testing state ⇒ (a) तुटलेल्या protected level (आणि flip PDL / PDH / flip zones) चा retest break दिशेने ⇒ G4;
    (b) range edges (वरची कड ⇒ bear, खालची ⇒ bull), zone नियमासह. बाकी ⇒ TESTING_ONLY_FLIP_OR_EDGE."""
    ss = SS.engine_settings(s)
    te = ctx["testing"]
    bd = -int(te["dir"])                                                   # break ची दिशा
    want = "sell" if bd < 0 else "buy"
    why = []
    flips = [z for z in zones or [] if z.get("side") == want and (z.get("state") == "FLIPPED" or str(z.get("type", "")).startswith("flip"))]
    if te.get("protected") is not None:
        px = float(te["protected"])
        pz = {"id": "PROT-BRK", "zid": "P", "side": want, "role": "RESISTANCE" if bd < 0 else "SUPPORT", "tool": "p",
              "type": "broken protected", "kind": "solid", "low": px, "high": px, "state": "FLIPPED"}
        if te.get("break_ts") is not None and "timestamp" in df:          # तुटल्यानंतरचेच bars pause / acceptance मध्ये
            pz["role_since"] = int(np.searchsorted(pd.to_datetime(df["timestamp"]).to_numpy(), np.datetime64(pd.Timestamp(te["break_ts"])),
                                                   side="right")) - 1
        flips.append(pz)
    r = _detect_episode(df, flips, {**ctx, "side": bd}, mr, s, tracker)
    if r.get("signal"):
        r["signal"]["setup"] = "G4"
        _wave_context(r["signal"], df, None, bd, s)
        r["signal"]["context_story"] += " · testing: तुटलेल्या level चा flip retest (G4)"
        return r
    why.append(f"flip: {r['why']}")
    rng = ctx.get("range")
    if rng and mr:
        lo_r, hi_r = float(rng[0]), float(rng[1])
        near = float(ss["area_merge_mr"]) * float(mr)
        for sd, edge in ((-1, hi_r), (1, lo_r)):
            w = "sell" if sd < 0 else "buy"
            ez = [z for z in zones or [] if z.get("side") == w and float(z["low"]) - near <= edge <= float(z["high"]) + near]
            if not ez:
                continue
            r = _detect_episode(df, ez, {**ctx, "side": sd}, mr, s, tracker)
            if r.get("signal"):
                r["signal"]["setup"] = "range_edge"
                _wave_context(r["signal"], df, None, sd, s)
                r["signal"]["context_story"] += f" · testing: range {'वरची' if sd < 0 else 'खालची'} कड {edge:,.1f}"
                return r
            why.append(f"edge {'वर' if sd < 0 else 'खाली'}: {r['why']}")
    return {"signal": None, "why": f"{TESTING_CODE} — " + " · ".join(why), "pause_bars": 0, "area": None}


def _detect(df, zones, ctx, mr, s=None, tracker=None):
    """df = trigger TF (15M) बंद bars (शेवटचा = निर्णयाचा bar). zones = chart_reader.zones (trade बाजू जन्मावरून). ctx = {trend (±1/0),
    side (trade बाजू; नसेल ⇒ trend), protected, impulse_end, story}. रिटर्न {signal | None, why, pause, area}."""
    s = SS.engine_settings(s)
    out = {"signal": None, "why": "", "pause_bars": 0, "area": None}
    side = int(ctx["side"] or 0) if "side" in ctx else int(ctx.get("trend") or 0)   # context_from चा 0 (F4 / testing) ⇒ signal नाही
    if not side:
        out["why"] = ctx.get("block") or "trend / बाजू स्पष्ट नाही"
        return out
    if df is None or len(df) < 3 or not mr or not np.isfinite(float(mr)):
        out["why"] = "bars अपुरे"
        return out
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(c)
    k = n - 1
    if tracker is not None:
        tracker.on_bar(float(c[k]))
    be = pd.Timestamp(df["bar_end"].iloc[k]) if "bar_end" in df else pd.Timestamp(df["timestamp"].iloc[k]) + pd.Timedelta(minutes=15)
    if be <= be.normalize() + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=int(s["opening_block_min"])):
        out["why"] = "opening window"
        return out
    tol, buf = s["area_tol_mr"] * mr, s["accept_buf_mr"] * mr
    cur = areas(zones, side, 0, s["area_merge_mr"] * mr)
    if not cur:
        out["why"] = f"{'seller' if side < 0 else 'buyer'} area नाही"
        return out

    def area_at(a, j):                                                     # area चा पट्टा bar j वर (trendline ⇒ मागे)
        back = k - j
        if back == 0:
            return a
        zs = areas(a["zones"], side, back, s["area_merge_mr"] * mr)
        return {**a, "low": min(x["low"] for x in zs), "high": max(x["high"] for x in zs)} if zs else a

    def pause_run(a, first):
        """first पासून मागे area ला लागलेले indecision bars (flip zone ⇒ role_since नंतरचेच)."""
        since = max([int(z["role_since"]) for z in a["zones"] if z.get("role_since") is not None] or [-1])
        j, n = first, 0
        while j >= max(0, k - int(s["pause_lookback"]), since + 1):
            if _touch(h[j], lo[j], area_at(a, j), side, tol) and _is_pause(o[j], h[j], lo[j], c[j], mr, s):
                n += 1
                j -= 1
                continue
            break
        return n

    # commitment: (1) हा bar, किंवा (2) आधीचा bar (touch) + हा bar (composite). B1: मालिकेतला कोणताही candle (pause किंवा commitment)
    # area ला लागलेला पुरे — commitment लागलेला नसला तरी आधीचा pause bar area वर असेल तर valid.
    best = None
    for a in cur:
        if not FL.breakout_ok(a, float(c[k]), side):                       # flag channel ⇒ commitment रेषेबाहेर close हवा
            continue
        if _commit_ok(o[k], h[k], lo[k], c[k], side, mr, s) and (_touch(h[k], lo[k], area_at(a, k), side, tol) or pause_run(a, k - 1)):
            best = (a, k)
            break
        if k > 0 and _touch(h[k - 1], lo[k - 1], area_at(a, k - 1), side, tol):
            comp = (o[k - 1], max(h[k - 1], h[k]), min(lo[k - 1], lo[k]), c[k])
            if _commit_ok(*comp, side, mr, s) and ((c[k] < o[k]) if side < 0 else (c[k] > o[k])):
                best = (a, k - 1)
                break
    if best is None:
        near = any(_touch(h[j], lo[j], area_at(a, j), side, tol) for a in cur for j in (k, k - 1))
        out["why"] = "area वर commitment candle नाही" if near else "commitment area पासून दूर (area ला लागलेला नाही) — chase नाही"
        return out
    a, k0 = best
    out["area"] = {kk: a[kk] for kk in ("id", "type", "low", "high")}
    # pause: commitment आधी area ला लागलेले indecision bars (k0 composite मध्ये असेल तर तोही pause)
    first = k0 if k0 < k else k - 1
    pause = pause_run(a, first)
    out["pause_bars"] = pause
    # acceptance: **चालू episode** मध्ये (k-1 पासून मागे, area ला लागलेले / पलीकडचे सलग bars — मध्ये area पासून दूर गेलेला bar आला की
    # थांबा) area पलीकडे सलग accept_bars closes ⇒ setup रद्द. Flip आधीचे / जुने closes मोजत नाही.
    ep = k
    since = max([int(z["role_since"]) for z in a["zones"] if z.get("role_since") is not None] or [-1])   # flip आधीचे closes नाहीत
    for jj in range(k - 1, max(-1, k - int(s["pause_lookback"]) - 1, since), -1):
        aj = area_at(a, jj)
        beyond = (c[jj] > aj["high"] + buf) if side < 0 else (c[jj] < aj["low"] - buf)
        if not (_touch(h[jj], lo[jj], aj, side, tol) or beyond):
            break
        ep = jj
    from elliott.breaks import time_accepted
    from price_action.levels_v2 import DEFAULTS as LVD
    cl = c.astype(float)
    for jj in range(ep, k + 1):                                            # B2: area पलीकडे सलग accept_closes closes (buffer आत) ⇒ acceptance
        aj = area_at(a, jj)
        if time_accepted(cl, jj, aj["high"] if side < 0 else aj["low"], "above" if side < 0 else "below", LVD["accept_closes"], ep):
            if tracker is not None:
                tracker.release(side, a)
            out["why"] = f"area {a['id']} पलीकडे acceptance (सलग {LVD['accept_closes']} closes) ⇒ setup रद्द"
            return out
    # Area च्या कडेचा real break (breaks.py — KB G ची एकच व्याख्या: buffer + displacement / no-reclaim; Abhi G-MAP1 निर्णय 8) ⇒ setup रद्द.
    from elliott import breaks as BR
    from elliott import settings as ES
    bs = {**ES.DEFAULTS, "break_accept_closes": LVD["accept_closes"]}
    mra = np.full(len(c), float(mr))
    for jj in range(ep, k + 1):
        aj = area_at(a, jj)
        lvl = aj["high"] if side < 0 else aj["low"]
        if not ((c[jj] > lvl + buf) if side < 0 else (c[jj] < lvl - buf)):
            continue
        r = BR.break_from(df, jj, lvl, "above" if side < 0 else "below", bs, mr=mra)
        if r is not None and 0 <= r <= k:
            if tracker is not None:
                tracker.release(side, a)
            out["why"] = f"area {a['id']} पलीकडे acceptance — real break (breaks.py, {str(df['timestamp'].iloc[r])[11:16]}) ⇒ setup रद्द"
            return out
    if pause < int(s["pause_min_bars"]):
        out["why"] = f"area वर pause नाही (indecision bars {pause} < {int(s['pause_min_bars'])}) — थेट entry नाही"
        return out
    if pause:
        pz0 = first - pause + 1
        avg = float(np.mean(h[pz0:first + 1] - lo[pz0:first + 1]))
        crng = float(max(h[k0:k + 1].max(), h[k]) - min(lo[k0:k + 1].min(), lo[k]))
        if avg > 0 and crng < float(s["commitment_vs_pause"]) * avg:
            out["why"] = f"commitment ({crng:,.1f}) pause सरासरीच्या ({avg:,.1f}) {s['commitment_vs_pause']}× पेक्षा लहान"
            return out
    if tracker is not None and tracker.seen(side, a):
        out["why"] = f"DUP_SETUP — area {a['id']} वर आधीच signal ({tracker.at(side, a)[11:16]})"
        return out
    ck = slice(k0, k + 1)
    com = {"open": float(o[k0]), "high": float(h[ck].max()), "low": float(lo[ck].min()), "close": float(c[k]), "bars": int(k - k0 + 1)}
    p0 = max(0, first - pause + 1)
    pz = slice(min(p0, k0), k + 1)
    struct = (max(float(h[pz].max()), a["high"]) if side < 0 else min(float(lo[pz].min()), a["low"]))
    opp = areas(zones, -side, 0, s["area_merge_mr"] * mr)
    nxt = [x for x in opp if x["high"] < c[k]] if side < 0 else [x for x in opp if x["low"] > c[k]]
    nxt_px = (max(x["high"] for x in nxt) if side < 0 else min(x["low"] for x in nxt)) if nxt else None
    t = pd.Timestamp(df["timestamp"].iloc[k])
    sig = {"side": side, "trigger_time": str(be), "bar_start": str(t), "trigger_price": float(c[k]),
           "pause_from": str(pd.Timestamp(df["timestamp"].iloc[p0])) if pause else None,
           "area": {**{kk: (round(float(a[kk]), 2) if kk in ("low", "high") else a[kk]) for kk in ("id", "type", "low", "high")},
                    "source_ids": list(a["source_ids"])}, "_p0": int(p0),
           "pause_bars": int(pause), "commitment": com,
           "ref_levels": {"structural_invalidation": round(float(struct), 2),
                          "commitment_extreme": round(com["high"] if side < 0 else com["low"], 2),
                          "next_opposite_area": None if nxt_px is None else round(float(nxt_px), 2),
                          "impulse_end": ctx.get("impulse_end")},
           "context_story": (f"trend {'down' if side < 0 else 'up'}" + (f" (protected {ctx['protected']:,.1f})" if ctx.get("protected") else "")
                             + f" · area {a['id']} ({a['type']}) {a['low']:,.1f}–{a['high']:,.1f} · pause {pause} bars · commitment close "
                             f"{c[k]:,.1f}" + (f" · {ctx['story']}" if ctx.get("story") else ""))}
    if tracker is not None:
        tracker.add(side, a, t, invalidation=sig["ref_levels"]["structural_invalidation"])
    out.update(signal=sig, why="ENTRY SIGNAL")
    return out


def context_from(ms):
    """market_state.read ⇒ ctx (Simple Core spec: Trend = HTF HH/HL ⇒ up, LH/LL ⇒ down). Confirmed HTF trend ⇒ त्याच बाजूने;
    "testing" (protected real break, पुष्टी नाही) ⇒ side 0 + ctx["testing"] (फक्त flip retest / range edge — A2); HTF range (dir 0) ⇒
    impulse ची बाजू (F4 "unclear" ⇒ नाही). F4 gate (impulse / Elliott विरोध) shadow engine मध्ये — core HTF trend वरच चालतो."""
    tr = (ms or {}).get("trend") or {}
    d = int(tr.get("dir") or 0)
    testing = None
    if tr.get("state") == "testing":
        side = 0
        testing = {"dir": d, "protected": (tr.get("protected") or {}).get("price"), "extreme": tr.get("extreme"),
                   "break_ts": tr.get("break_ts")}
    elif d:
        side = d
    else:
        side = {"bear_call": -1, "bull_put": 1}.get((ms or {}).get("side"), 0)
    imp = (ms or {}).get("impulse") or {}
    out = {"trend": d, "side": side, "protected": (tr.get("protected") or {}).get("price"), "impulse_end": imp.get("to")}
    if testing:
        out["testing"] = testing
    # टप्पा B (नकाशा I8.2): POSSIBLE_REVERSAL flag काढला — त्याची जागा S3 + Gray-1 + reaction test (reading.py) घेतात.
    return out


def testing_range(trig, te):
    """Testing range: तुटलेल्या trend चं टोक (extreme) आणि break नंतरचं उलट टोक. माहिती नसेल ⇒ None."""
    if not te or te.get("extreme") is None or te.get("break_ts") is None or trig is None or not len(trig):
        return None
    after = trig[pd.to_datetime(trig["timestamp"]) >= pd.Timestamp(te["break_ts"]) - pd.Timedelta(hours=1)]
    if not len(after):
        return None
    ext = float(te["extreme"])
    return (float(after["low"].min()), ext) if int(te["dir"]) > 0 else (ext, float(after["high"].max()))


def signal_at(df1m, asof, s=None, memory=None, tracker=None, profile="srv2", es=None):
    """Real data: 1m ⇒ 15M बंद bars, market_state trend, zones (chart_reader: सगळी ठोस साधनं ⇒ selling / buying, trendline memory) ⇒ detect.
    रिटर्न detect चा dict + {ms, zones, mr, trig}. Heavy evidence (Elliott, volume, divergence …) इथे नाही — shadow engine मध्ये."""
    import market_state as MS
    from chart_reader import areas as AR
    from chart_reader import evaluate as EV
    from chart_reader import measures as M
    from chart_reader import settings as CS
    from chart_reader import zones as ZN
    from chart_reader.profiles import PROFILES
    from price_action import levels_v2 as LV
    cs = CS.load()
    pr = PROFILES[profile]
    asof = pd.Timestamp(asof)
    trig = EV.frame(df1m, pr["trigger_tf"], asof)
    if len(trig) < 40:
        return {"signal": None, "why": "data अपुरा", "pause_bars": 0, "area": None, "zones": [], "ms": None, "mr": None, "trig": trig}
    mr = M.mr_now(trig)
    cut = df1m[pd.to_datetime(df1m["timestamp"]) + pd.Timedelta(minutes=1) <= asof].reset_index(drop=True)
    ms = MS.read(cut, asof, run_elliott=False)
    horiz = []
    for tf in pr["areas_tfs"]:
        horiz += [{**z, "tf": tf.upper()} for z in LV.build(EV.frame(df1m, tf, asof), tf=tf)["candidates"]]
    try:
        from vision import gap_context as GC
        g = GC.build(cut, asof, mr, None, None, None)
    except Exception:                                                      # noqa: BLE001 — gap नसेल तर gap edge zone नाही
        g = {"has_gap": False}
    cands = AR.tools(trig, horiz, {}, EV._ctx(cut, asof, g, mr), cs, mr, keep=memory.keep() if memory is not None else None)
    if memory is not None:
        memory.update(asof, cands)
    zones = ZN.annotate(cands, trig, cs, mr, tf=pr["trigger_tf"].upper())
    ctx = context_from(ms)
    ctx["pivots"] = [{"ts": p["ts"], "price": p["price"], "kind": p["kind"]} for p in ms.get("swings") or []]
    ctx["impulse"] = ms.get("impulse")
    if ctx.get("testing"):
        ctx["range"] = testing_range(trig, ctx["testing"])
    gl = g.get("class") if g.get("has_gap") else None
    ctx["story"] = f"gap {gl} {g.get('direction')}" if gl else ""
    r = detect(trig, zones, ctx, mr, s, tracker)
    ss = SS.engine_settings(s)
    if not r.get("signal") and ss["g10_enabled"] and not ctx.get("testing"):
        r10 = g10(trig, zones, ctx, mr, s, tracker, ss)                    # S9 / G10 range कड
        if r10.get("signal"):
            r = r10
    h1 = EV.frame(df1m, "1h", asof)
    r = apply_reading(r, trig, h1, df1m, asof, mr, ss, zones, ctx, g, tracker, es)
    r.update(zones=zones, ms=ms, mr=mr, trig=trig, gap=g, ctx=ctx)       # ctx: research replay (sensitivity) साठी
    return r


EXCEPTIONS = ("G4", "range_edge", "G10", "G7")                             # नकाशा P1: पालक-दिशा / gray filter ने मरत नाहीत


def apply_reading(r, trig, h1, df1m, asof, mr, s, zones, ctx, gap, tracker=None, es=None):
    """टप्पा B reading layer (simple_core/reading.py + count_source.py) candidate signal वर: S#, Gray-1 / Gray-2 / S4 / S11, पालक दिशा
    (`parent_source`), gray धोरण (`get_gray_policy`, default block), target degree (impulse_end + next_opposite_area), एकच count स्रोत
    (G1 / G9 labels, wave refs), commit_vs_impulse (report), 15:15 ⇒ eod recheck. Gray मुळे थांबलेला signal `gray_candidate` मध्ये
    (backtest मध्ये block / reduce दोन्ही निकाल)."""
    from . import count_source as CSRC
    from . import reading as RD
    sg = r.get("signal")
    pd_ms = int(ctx.get("trend") or 0)
    if not sg:
        r["reading"] = {"S": None, "parent_ms": pd_ms, "why": r.get("why")}
        return r
    side = int(sg["side"])
    rd = RD.read_signal(trig, h1, sg, sg["area"], mr, s, asof, gap=gap, es=es)
    imp = rd.get("impulse")
    cnt = CSRC.read(df1m, asof, imp["end_ts"] if imp else None, side, es)
    pref = cnt.get("preferred") or {}
    # एकच count स्रोत: G1 / G9 फक्त preferred count नुसार (G8 / G4 / range_edge / G10 त्यांच्या रचनेवरून)
    if sg.get("setup") not in ("G8", "G4", "range_edge", "G10"):
        sg["setup"] = cnt.get("setup")
        sg["wave"] = {"setup": cnt.get("setup"), "gray": None if cnt.get("setup") else (cnt.get("why") or "count gray at trade degree"),
                      "count": pref.get("pattern"), "wave": pref.get("wave"), "degree": cnt.get("degree")}
        tops = (rd.get("legs") or {}).get("tops") or []
        refs = CSRC.wave_refs(pref, cnt.get("setup"), s, ext=(max(tops) if side < 0 else min(tops)) if tops else None)
        sg["ref_levels"].update(refs)
        for kk, v in refs.items():
            if v is not None:
                (sg.get("ref_notes") or {}).pop(kk, None)
    # target degree (निर्णय 9): impulse_end = याच correction चा origin; next_opposite_area: correction च्या आतले areas वगळून
    sg["ref_levels"]["impulse_end"] = round(float(imp["end"]), 2) if imp else None
    opp = areas(zones, -side, 0, s["area_merge_mr"] * mr)
    c = float(sg["trigger_price"])
    if imp:
        e = float(imp["end"])
        nxt = [x for x in opp if x["high"] < c and x["low"] <= e] if side < 0 else [x for x in opp if x["low"] > c and x["high"] >= e]
    else:
        nxt = [x for x in opp if x["high"] < c] if side < 0 else [x for x in opp if x["low"] > c]
    sg["ref_levels"]["next_opposite_area"] = (round(float(max(x["high"] for x in nxt) if side < 0 else min(x["low"] for x in nxt)), 2)
                                              if nxt else None)
    sg["commit_vs_impulse"] = rd.get("commit_vs_impulse")
    # पालक दिशा
    psrc = s["parent_source"]
    parent = pd_ms if psrc == "market_state" else int(cnt.get("parent_dir") or 0)
    conflict = bool(pd_ms and cnt.get("parent_dir") and pd_ms != int(cnt["parent_dir"]))
    pol = RD.get_gray_policy(pd.Timestamp(asof).normalize())
    rd.update(parent_source=psrc, parent=parent, parent_ms=pd_ms, parent_count=cnt.get("parent_dir"), PARENT_CONFLICT=conflict,
              count={"degree": cnt.get("degree"), "preferred": cnt.get("preferred"), "alternate": cnt.get("alternate"), "why": cnt.get("why"),
                     "degrees": cnt.get("degrees"), "tie": cnt.get("count_tie"), "S11_alpha": cnt.get("S11_alpha"),
                     "setup_alpha": cnt.get("setup_alpha")},
              policy=pol, area_source=f"{sg['area'].get('id')} ({sg['area'].get('type')})",
              invalidation=sg["ref_levels"].get("structural_invalidation"))
    sg["reading"] = rd
    r["reading"] = rd
    exc = sg.get("setup") in EXCEPTIONS

    def stop(why, gray=None):
        if tracker is not None and sg.get("area"):
            tracker.release(side, sg["area"])                               # gray मुळे थांबला ⇒ तोच setup नंतर (धोरण बदलल्यास) शक्य
        r["gray_candidate" if gray else "blocked_candidate"] = sg
        r.update(signal=None, why=why)
        return r

    if not exc:
        if psrc == "preferred_count" and not parent:
            return stop("PARENT_UNKNOWN: preferred count / sequence नाही ⇒ trade नाही (gray नाही)")
        if parent and parent != side:
            return stop(f"पालक दिशा ({psrc}) {'up' if parent > 0 else 'down'} — trade दिशा विरुद्ध")
        if cnt.get("S11"):
            return stop("S11: preferred count नुसार B च्या आत — trade नाही")
        if rd.get("gray") == "S4":
            return stop(rd["gray_why"])
        if rd.get("gray") in ("Gray-1", "Gray-2"):
            ok = pol["policy"] == "reduce" and (rd["gray"] == "Gray-2" or (pol.get("dir") is not None and int(pol["dir"]) == side))
            if not ok:
                return stop(f"{rd['gray']} ({pol['policy']}): {rd['gray_why']}", gray=True)
            sg["gray"] = rd["gray"]                                         # reduce ⇒ GRAY खूण, size gray_size (execution)
    if s["eod_signal_carry"] == "recheck" and pd.Timestamp(sg["bar_start"]).strftime("%H:%M") >= "15:15":
        sg["eod_carry"] = "recheck"                                         # दुसऱ्या दिवशी आपोआप entry नाही; नवी commitment हवी
        if tracker is not None:
            tracker.release(side, sg["area"])
    return r


def g10(trig, zones, ctx, mr, s, tracker, ss):
    """S9 / G10 (नकाशा S9; Abhi): 15M StructureTracker RANGE ⇒ confirmed range कडा. कडेवर Simple Core pause + commitment ⇒ खालची ⇒ bull,
    वरची ⇒ bear. पालक (market_state) trend असेल ⇒ फक्त trend दिशेची कड (S6 + S9 default). Range मध्यात area नाही ⇒ signal नाही.
    Sweep + reclaim (pause / commitment bars मध्ये कडेपलीकडे wick, close आत) ⇒ पुरावा मजबूत (नोंद)."""
    from opportunity_engine.structure import StructureTracker
    out = {"signal": None, "why": "G10: RANGE नाही", "pause_bars": 0, "area": None}
    f = trig.iloc[-int(ss["g10_range_bars"]):]
    st = StructureTracker("15m")
    for b in f.itertuples(index=False):
        st.on_bar(pd.Timestamp(b.bar_end), b.open, b.high, b.low, b.close)
    snap = st.snapshot()
    if snap.get("trend_state") != "RANGE" or snap.get("range_high") is None:
        return out
    hi_r, lo_r = float(snap["range_high"]), float(snap["range_low"])
    parent = int(ctx.get("trend") or 0)
    edges = [(-1, hi_r), (1, lo_r)] if not parent else [(-1, hi_r)] if parent < 0 else [(1, lo_r)]
    why = []
    for sd, edge in edges:
        z = {"id": f"RANGE-{'H' if sd < 0 else 'L'}", "zid": "R", "tool": "d", "type": "range edge", "kind": "solid", "state": "ACTIVE",
             "side": "sell" if sd < 0 else "buy", "role": "RESISTANCE" if sd < 0 else "SUPPORT", "low": edge, "high": edge}
        r = _detect_episode(trig, [z], {**ctx, "side": sd}, mr, s, tracker)
        sg = r.get("signal")
        if sg:
            k = len(trig) - 1
            p0 = k - int(sg.get("pause_bars", 0)) - int(sg["commitment"]["bars"]) + 1
            seg = trig.iloc[max(0, p0):k + 1]                               # pause + commitment bars
            sweep = bool((seg["high"] > edge).any()) if sd < 0 else bool((seg["low"] < edge).any())
            sg["setup"] = "G10"
            sg["g10"] = {"mode": ss["g10_mode"], "edge": round(edge, 2), "range": (round(lo_r, 2), round(hi_r, 2)), "sweep_reclaim": sweep,
                         "s6_s9": bool(parent)}
            sg["ref_levels"]["next_opposite_area"] = round(lo_r if sd < 0 else hi_r, 2)   # target = विरुद्ध कड
            sg["context_story"] += f" · G10: range {'वरची' if sd < 0 else 'खालची'} कड {edge:,.1f}" + (" (sweep + reclaim)" if sweep else "")
            return r
        why.append(r["why"])
    out["why"] = "G10: " + " · ".join(why)
    return out
