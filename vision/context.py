"""vision/context.py — chart v2 चा संदर्भ (signal_check_v2): major levels, PDH/PDL/PDC, PWH/PWL, आजचा open + opening range, swing points,
room, वेळ, gap, expiry. **सगळं OHLC वरून, signal पर्यंतच (causal)** — image वरून कधीच नाही; अचूक किंमती signal text मध्ये जातात.

🎓 No-lookahead:
  • इनपुट `cut` = signal पर्यंत **पूर्ण** झालेले 1m bars (`chart.cut_1m`) — पुढचं काहीच नाही.
  • PDH / PDL / PDC = signal च्या आधीचा **पूर्ण** session-दिवस; PWH / PWL = आधीचा **पूर्ण** आठवडा (चालू दिवस / आठवडा नाही).
  • Opening range = आजचे पहिले 15 मिनिटं, फक्त पूर्ण झालेले bars (signal 09:30 आधी ⇒ अपूर्ण, `or_complete = False`).
  • Major levels = `price_action/major_levels.py` (asof = signal, फक्त संपलेले bars). Swing points = setup TF वर fractal (दोन्ही बाजूंना r bars
    आधीच पूर्ण झाले तरच confirmed).
"""
import numpy as np
import pandas as pd

OR_MIN = 15
OPEN_T = pd.Timedelta(hours=9, minutes=15)
LAST_HOUR_T = pd.Timedelta(hours=14, minutes=30)
MERGE_MR = 0.1                       # 0.1 × median range पेक्षा जवळचे overlays ⇒ एकच label
SWING_R = 2
SWINGS_MAX = 8


def _days(cut):
    return cut["timestamp"].dt.normalize()


def prev_day(cut, sig_day, min_bars=200):
    """आधीच्या पूर्ण session-दिवसाचे (high, low, close) किंवा None. Muhurat / special (लहान) sessions वगळले."""
    d = cut[_days(cut) < sig_day]
    if d.empty:
        return None
    n = d.groupby(d["timestamp"].dt.normalize()).size()
    full = n[n >= min_bars]
    if full.empty:
        return None
    last = full.index.max()
    x = d[d["timestamp"].dt.normalize() == last]
    return {"day": str(last.date()), "high": float(x["high"].max()), "low": float(x["low"].min()), "close": float(x["close"].iloc[-1])}


def prev_week(cut, sig_day):
    """आधीच्या पूर्ण (ISO) आठवड्याचे (high, low) किंवा None. चालू आठवडा कधीच नाही."""
    wk0 = sig_day - pd.Timedelta(days=sig_day.weekday())
    d = cut[_days(cut) < wk0]
    if d.empty:
        return None
    last_day = d["timestamp"].dt.normalize().max()
    w0 = last_day - pd.Timedelta(days=last_day.weekday())
    x = d[d["timestamp"].dt.normalize() >= w0]
    return {"week": str(w0.date()), "high": float(x["high"].max()), "low": float(x["low"].min())}


def opening(cut, sig_day, signal_ts):
    """आजचा open आणि opening range (पहिले 15 मिनिटं, पूर्ण bars)."""
    x = cut[_days(cut) == sig_day]
    if x.empty:
        return None
    t_or = sig_day + OPEN_T + pd.Timedelta(minutes=OR_MIN)
    orx = x[x["timestamp"] < t_or]
    return {"open": float(x["open"].iloc[0]), "or_high": float(orx["high"].max()) if len(orx) else None,
            "or_low": float(orx["low"].min()) if len(orx) else None, "or_complete": bool(pd.Timestamp(signal_ts) >= t_or)}


def swings(setup, r=SWING_R, n=SWINGS_MAX):
    """Setup TF वरचे confirmed fractal pivots [(index, "H"/"L", price)] — शेवटचे n. i + r ≤ शेवटचा पूर्ण bar."""
    if setup is None or len(setup) < 2 * r + 1:
        return []
    H, L = setup["high"].to_numpy(float), setup["low"].to_numpy(float)
    out = []
    for i in range(r, len(setup) - r):
        if H[i] > H[i - r:i].max() and H[i] >= H[i + 1:i + r + 1].max():
            out.append((i, "H", float(H[i])))
        if L[i] < L[i - r:i].min() and L[i] <= L[i + 1:i + r + 1].min():
            out.append((i, "L", float(L[i])))
    return out[-n:]


def majors(cut, signal_ts, spot, per_side=2):
    """price_action.major_levels (15m chart-TF वरून, asof = signal) ⇒ spot च्या वर / खाली जवळचे per_side. रिटर्न [{name, price, flip}]."""
    try:
        from price_action.major_levels import major_levels
        from .chart import resample
        m15 = resample(cut, 15)
        if len(m15) < 20:
            return []
        df = m15.rename(columns={"start": "timestamp"})[["timestamp", "open", "high", "low", "close"]]
        lv, _, _ = major_levels(df, asof=pd.Timestamp(signal_ts))
    except Exception:
        return []
    up = sorted([x for x in lv if x["price"] > spot], key=lambda x: x["price"])[:per_side]
    dn = sorted([x for x in lv if x["price"] <= spot], key=lambda x: -x["price"])[:per_side]
    out = [{"name": f"M{k + 1}↑", "price": float(x["price"]), "flip": bool(x["role_reversal"])} for k, x in enumerate(up)]
    out += [{"name": f"M{k + 1}↓", "price": float(x["price"]), "flip": bool(x["role_reversal"])} for k, x in enumerate(dn)]
    return out


def merge_labels(items, mr):
    """एकमेकांपासून 0.1 × median range पेक्षा जवळचे overlays ⇒ एक label ("PDH+M1↑"), किंमत = पहिल्याची (L असेल तर L ची)."""
    tol = MERGE_MR * (mr or 0.0)
    out = []
    for it in sorted(items, key=lambda z: z["price"]):
        if out and abs(it["price"] - out[-1]["price"]) <= tol:
            g = out[-1]
            g["names"].append(it["name"])
            g["kinds"].add(it["kind"])
            if it["kind"] == "L":
                g["price"] = it["price"]
            continue
        out.append({"price": it["price"], "names": [it["name"]], "kinds": {it["kind"]}})
    for g in out:
        names = sorted(g["names"], key=lambda n: (n != "L", n))
        g["label"] = "+".join(names)
        g["kinds"] = sorted(g["kinds"])
    return out


def today_role(bars, p, buf, t=None):
    """आज (signal पर्यंतच्या setup bars वर) level कसा वागला: held_as_support / held_as_resistance / broken_down / broken_up / untested.
    बाजू (side) = आजच्या पहिल्या open ची level च्या सापेक्ष बाजू. Real break = बाजू बदलणारा close, level पलीकडे buffer सह, आणि पुढच्या bar ने
    reclaim नाही (शेवटचा bar ⇒ अजून reclaim नाही) — फक्त वरूनच खाली (broken_down) किंवा खालून वर (broken_up); जी बाजू आधीपासून आहे तिथे "break" नाही.
    Break चिकटतो (उलट real break पर्यंत) — break नंतरचा retest "broken" च. Touch (break नाही) ⇒ वरच्या बाजूने held_as_support, खालून held_as_resistance.
    रिटर्न (role, break वेळ | None)."""
    role, at = "untested", None
    if bars is None or len(bars) == 0 or p is None:
        return role, at
    O, H, L, C = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    side = "above" if (O[0] > p or (O[0] == p and C[0] >= p)) else "below"          # open = level ⇒ पहिल्या close ची बाजू
    n = len(C)
    # break फक्त **पूर्ण** bar वर (signal च्या क्षणी चालू असलेला शेवटचा bar break सुरू करू शकत नाही, फक्त reclaim नाही हे पुष्टी करतो)
    fin = n if t is None or "end" not in bars else int((pd.to_datetime(bars["end"]) <= pd.Timestamp(t)).sum())
    for i in range(n):
        nxt = C[i + 1] if i + 1 < n else None
        if i >= fin:
            if L[i] <= p <= H[i] and not role.startswith("broken"):
                role = "held_as_support" if side == "above" else "held_as_resistance"
            continue
        if side == "above" and C[i] < p - buf and (nxt is None or nxt < p):
            side, role, at = "below", "broken_down", str(bars["start"].iloc[i])[11:16]
            continue
        if side == "below" and C[i] > p + buf and (nxt is None or nxt > p):
            side, role, at = "above", "broken_up", str(bars["start"].iloc[i])[11:16]
            continue
        if L[i] <= p <= H[i] and not role.startswith("broken"):
            role = "held_as_support" if side == "above" else "held_as_resistance"
    return role, at


def crossings(bars, p):
    """आज closes ची level ओलांडण्याची संख्या (बाजू बदल) — ≥ MAGNET_CROSSES ⇒ magnet (वारंवार इकडून तिकडे — no-trade level)."""
    if bars is None or len(bars) < 2:
        return 0
    s = np.sign(bars["close"].to_numpy(float) - p)
    s = s[s != 0]
    return int((s[1:] != s[:-1]).sum()) if len(s) > 1 else 0


MAGNET_CROSSES = 4


def recent_breaks(bars, p, buf, n=4):
    """Signal bar (अपूर्ण असला तरी — breakout veto साठी) किंवा मागच्या 3 bars नी level real-break ने तोडला का: "down" / "up" / None + वेळ.
    फक्त आजच्या उघडण्याच्या बाजूपासून **दूर** जाणारे breaks (परत येणारे = reclaim, मोजत नाही).
    Break = आधीच्या close च्या बाजूपासून दुसऱ्या बाजूला buffer सह close, आणि नंतरचा bar (असेल तर) reclaim नाही."""
    if bars is None or len(bars) < 2:
        return None, None
    C = bars["close"].to_numpy(float)
    O0 = float(bars["open"].iloc[0])
    open_side = "above" if (O0 > p or (O0 == p and C[0] >= p)) else "below"
    N = len(C)
    for i in range(max(1, N - n), N):
        prev = C[i - 1]
        nxt = C[i + 1] if i + 1 < N else None
        # उघडण्याच्या बाजूकडे परत येणारा break = reclaim (false break / spring) ⇒ breakout नाही
        if prev >= p and C[i] < p - buf and (nxt is None or nxt < p) and open_side == "above":
            return "down", str(bars["start"].iloc[i])[11:16]
        if prev <= p and C[i] > p + buf and (nxt is None or nxt > p) and open_side == "below":
            return "up", str(bars["start"].iloc[i])[11:16]
    return None, None


def composite(setup, level, bull, buf, k_max=3):
    """Signal चे composite reversal candles: शेवटच्या k_max bars पैकी level zone ला सर्वात आधी touch केलेल्या bar पासून शेवटपर्यंत. (i0, i1)."""
    n = len(setup)
    if n == 0 or level is None:
        return None
    i0 = n - 1
    for i in range(max(0, n - k_max), n):
        lo, hi = float(setup["low"].iloc[i]), float(setup["high"].iloc[i])
        if (bull and lo <= level + buf) or ((not bull) and hi >= level - buf):
            i0 = i
            break
    return [int(i0), int(n - 1)]


def expiry_days(expiries, sig_day):
    try:
        fut = sorted(pd.Timestamp(e).normalize() for e in expiries or [] if pd.Timestamp(e).normalize() >= sig_day)
    except (TypeError, ValueError):
        return None
    return int((fut[0] - sig_day).days) if fut else None


def build(cut, setup, sig, median_range=None, daily=None):
    """Signal चा पूर्ण संदर्भ (dict, JSON-able). cut = signal पर्यंतचे पूर्ण 1m bars; setup = setup TF frame (chart.panels).
    sig["ctx_settings"] (ऐच्छिक): inv_buffer_mr, gap_* settings, events {YYYY-MM-DD: नाव}."""
    cs = sig.get("ctx_settings") or {}
    from .chart import to_ist_naive
    t = pd.Timestamp(to_ist_naive(sig["signal_ts"]))                    # tz-aware / string ⇒ naive IST (cut_1m सारखं)
    sig_day = t.normalize()
    spot = float(sig.get("spot") or (cut["close"].iloc[-1] if len(cut) else np.nan))
    mr = median_range
    if mr is None and setup is not None and len(setup):
        mr = float((setup["high"] - setup["low"]).tail(20).median())
    bull = str(sig.get("direction", "")).upper().startswith("BULL")
    level = sig.get("level")
    items = []
    if level is not None:
        items.append({"name": "L", "price": float(level), "kind": "L"})
    for m in majors(cut, t, spot):
        items.append({"name": m["name"] + ("F" if m["flip"] else ""), "price": m["price"], "kind": "major"})
    pd_ = prev_day(cut, sig_day)
    if pd_:
        items += [{"name": "PDH", "price": pd_["high"], "kind": "ref"}, {"name": "PDL", "price": pd_["low"], "kind": "ref"},
                  {"name": "PDC", "price": pd_["close"], "kind": "ref"}]
    pw = prev_week(cut, sig_day)
    if pw:
        items += [{"name": "PWH", "price": pw["high"], "kind": "ref"}, {"name": "PWL", "price": pw["low"], "kind": "ref"}]
    op = opening(cut, sig_day, t)
    if op:
        items.append({"name": "OPEN", "price": op["open"], "kind": "ref"})
        if op["or_high"] is not None:
            items += [{"name": "ORH", "price": op["or_high"], "kind": "ref"}, {"name": "ORL", "price": op["or_low"], "kind": "ref"}]
    inv, inv_src = sig.get("invalidation"), "bot"
    if inv is None and level is not None and mr:                           # bot ने न दिल्यास L ∓ inv_buffer (chart / text साठी; drift guard bot चाच)
        inv = float(level) - float(cs.get("inv_buffer_mr", 0.5)) * mr * (1 if bull else -1)
        inv_src = f"derived (L {'-' if bull else '+'} {cs.get('inv_buffer_mr', 0.5)} x median range)"
    buf = 0.25 * (mr or 0.0)
    from .chart import TF_MAP, resample
    s_tf = TF_MAP.get(str(sig.get("setup_tf")).upper(), (5, 15))[0]
    tb = resample(cut[_days(cut) == sig_day], s_tf) if len(cut) else None    # आजचे सगळे setup bars 09:15 पासून (chart चे शेवटचे 60 नाही)
    groups = merge_labels(items, mr)
    rows = []
    open0 = float(tb["open"].iloc[0]) if tb is not None and len(tb) else None
    for g in groups:
        role, at = today_role(tb, g["price"], buf, t)
        side0 = None if open0 is None else ("above" if open0 >= g["price"] else "below")
        recl = (role == "broken_up" and side0 == "above") or (role == "broken_down" and side0 == "below")
        d = (g["price"] - spot) / mr if mr else None
        rb, rb_at = recent_breaks(tb, g["price"], buf)
        rows.append({"name": g["label"], "price": g["price"], "kinds": g["kinds"], "dist_mr": round(d, 2) if d is not None else None,
                     "position": "above" if g["price"] > spot else ("below" if g["price"] < spot else "at"), "today_role": role,
                     "broken_at": at, "reclaimed": bool(recl), "magnet": crossings(tb, g["price"]) >= MAGNET_CROSSES,
                     "recent_break": rb, "recent_break_at": rb_at})
    # Room: trade दिशेने पुढचा विरोधी level — फक्त न तुटलेले (प्रत्यक्ष विरोध करू शकणारे); L चा group वगळून
    # Room (तुमची दुरुस्ती): trade दिशेने पुढचा कोणताही level — आज तुटलेला (flip: broken support ⇒ आता resistance) आणि untested सुद्धा; फक्त magnet वगळा
    opp = [r for r in rows if "L" not in r["kinds"] and not r["magnet"] and ((bull and r["price"] > spot) or (not bull and r["price"] < spot))]
    nxt = min(opp, key=lambda r: abs(r["price"] - spot)) if opp else None
    room = {"next_name": nxt["name"] if nxt else None, "next_price": nxt["price"] if nxt else None,
            "next_mr": round(abs(nxt["price"] - spot) / mr, 2) if nxt and mr else None,
            "invalidation_mr": round(abs(float(inv) - spot) / mr, 2) if inv is not None and mr else None,
            "next_role": nxt["today_role"] if nxt else None, "next_flip": bool(nxt and nxt["today_role"].startswith("broken") and not nxt["reclaimed"])}
    # signal bar / मागचे 3 bars: trade दिशेने real-break झालेले levels (bear ⇒ down, bull ⇒ up)
    want = "up" if bull else "down"
    recent = [{"name": r["name"], "at": r["recent_break_at"]} for r in rows if r["recent_break"] == want]
    # Traded level L: कुठून आला, आधी कसा वागला, तुटला का
    lline = None
    if level is not None and tb is not None and len(tb):
        ref = tb["close"].iloc[-7] if len(tb) >= 7 else tb["open"].iloc[0]
        early_role, _ = today_role(tb.iloc[:-3] if len(tb) > 3 else tb.iloc[:0], float(level), buf, t)
        now_role, br_at = today_role(tb, float(level), buf, t)
        open_side = "above" if float(tb["open"].iloc[0]) >= float(level) else "below"
        # opening बाजूकडे परतणारा break = reclaim (false break / spring), opening बाजूपासून दूर जाणारा = खरा break
        reclaimed = (now_role == "broken_up" and open_side == "above") or (now_role == "broken_down" and open_side == "below")
        lline = {"approach": "from above" if ref > float(level) else "from below", "earlier_role": early_role, "today_role": now_role,
                 "broken": now_role.startswith("broken") and not reclaimed, "reclaimed": bool(reclaimed), "broken_at": br_at,
                 "opening_side": open_side, "bot_role": str(sig.get("role") or "").upper(), "spot_side": "above" if spot > float(level) else ("below" if spot < float(level) else "at")}
    mins = int((t - (sig_day + OPEN_T)).total_seconds() // 60)
    gap = None
    if pd_ and op:
        g = (op["open"] - pd_["close"]) / pd_["close"] * 100.0
        today = cut[_days(cut) == sig_day]
        filled = bool(len(today)) and bool((g > 0 and today["low"].min() <= pd_["close"]) or (g < 0 and today["high"].max() >= pd_["close"]))
        gap = {"pct": round(g, 2), "filled": filled if abs(g) >= 0.1 else None}
    sw = swings(setup)
    gctx = None
    try:
        from . import gap_context as GC
        gctx = GC.build(cut, t, mr, cs, cs.get("events"), daily)
    except Exception as exc:                                             # gap संदर्भ अपयशी ⇒ text मध्ये "unavailable"
        gctx = {"error": f"{type(exc).__name__}: {str(exc)[:80]}"}
    return {
        "spot": spot, "median_range": mr, "levels": rows, "room": room, "prev_day": pd_, "prev_week": pw, "opening": op,
        "minutes_since_open": mins, "time_flag": "opening" if mins < OR_MIN else ("last_hour" if t >= sig_day + LAST_HOUR_T else "none"),
        "gap": gap, "expiry_days": expiry_days(sig.get("expiries"), sig_day),
        "swings": [{"i": i, "kind": k, "price": p} for i, k, p in sw],
        "overlays": [{"price": r["price"], "label": r["name"], "kinds": r["kinds"], "today_role": r["today_role"], "reclaimed": r["reclaimed"]}
                     for r in rows],
        "level": float(level) if level is not None else None, "recent_breaks": recent,
        "invalidation": inv, "invalidation_source": inv_src, "l_line": lline, "gap_ctx": gctx,
        "composite": composite(setup, level, bull, buf) if setup is not None else None,
    }
