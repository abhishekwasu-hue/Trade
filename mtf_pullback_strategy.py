"""
mtf_pullback_strategy.py
-------------------------------
🎓 वापरकर्त्याशी चर्चा करून, Dashboard मध्ये जोडण्यासाठी बांधलेलं module — मूळ, वापरकर्त्याने अपलोड
केलेल्या आणि अनेक फेऱ्यांत सुधारलेल्या amw_a1_mtf_pullback.py मधलं established, बग-दुरुस्त core logic
(CSV/CLI/matplotlib भाग काढून — Dashboard साठी थेट DataFrame घेणारी, पुनर्वापर करण्याजोगी functions).

दोन रणनीती:
  १. fib_pullback — 1H swing → 38.2%-61.8%(किंवा वापरकर्ता-निवडित) फिबोनाची पुलबॅक झोन →
     15M Reversal Candle (Hammer/Engulfing/Star) + RSI पुष्टी → पुढच्या candle च्या Open वर Entry.
  २. gap_fill — फक्त खरा overnight gap (मागच्या दिवसाचा शेवटचा 15M close ते पुढच्या दिवसाचा market
     open, किमान min_gap_pct%, सद्य 1H trend च्या दिशेशी जुळणारा) — तो gap कुठल्याही भविष्यातल्या
     दिवशी **पूर्णपणे भरला** गेला (किंमत त्याच्या मूळ किनाऱ्यापर्यंत पोहोचली) की, कुठलीही पुष्टी न
     घेता, त्याच किनाऱ्यावर Entry.
"""
import numpy as np
import pandas as pd


def rsi14(closes, period=14):
    """Wilder's RSI — established पद्धत."""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def pivots(d, left=3, right=3, min_swing_pct=1.0):
    """
    1H स्तंभ (Date/Open/High/Low/Close असलेला DataFrame, reset_index केलेला) वरून confirmed
    swing high/low शोधणे. टक्केवारी-आधारित min_swing_pct — क्षुल्लक स्विंग्स वगळण्यासाठी.
    """
    h = d.High.to_numpy(); l = d.Low.to_numpy(); raw = []
    for i in range(left, len(d) - right):
        if h[i] == np.max(h[i - left:i + right + 1]):
            raw.append({"idx": i, "type": "SH", "price": h[i], "confirmed": i + right})
        if l[i] == np.min(l[i - left:i + right + 1]):
            raw.append({"idx": i, "type": "SL", "price": l[i], "confirmed": i + right})
    raw.sort(key=lambda x: x["confirmed"])
    out = []
    for p in raw:
        if not out:
            out.append(p); continue
        q = out[-1]
        if p["type"] == q["type"]:
            if (p["type"] == "SH" and p["price"] > q["price"]) or (p["type"] == "SL" and p["price"] < q["price"]):
                out[-1] = p
        elif abs(p["price"] - q["price"]) >= q["price"] * min_swing_pct / 100:
            out.append(p)
    return out


def reversal(prev, curr, direction):
    """Hammer/Shooting Star/Engulfing — established पॅटर्न-तर्क."""
    po, ph, pl, pc = prev[["Open", "High", "Low", "Close"]]
    o, h, l, c = curr[["Open", "High", "Low", "Close"]]
    body = abs(c - o); rng = max(h - l, 1e-9)
    upper = h - max(o, c); lower = min(o, c) - l
    bull_eng = (pc < po and c > o and o <= pc and c >= po)
    bear_eng = (pc > po and c < o and o >= pc and c <= po)
    hammer = (c > o and lower >= max(2 * body, .35 * rng) and upper <= .35 * rng)
    star = (c < o and upper >= max(2 * body, .35 * rng) and lower <= .35 * rng)
    if direction == "BUY":
        if bull_eng: return "Bullish Engulfing"
        if hammer: return "Hammer / Bullish Pin Bar"
    else:
        if bear_eng: return "Bearish Engulfing"
        if star: return "Shooting Star / Bearish Pin Bar"
    return None


def make_signals(h1, m15, ps, fib1=.382, fib2=.618, sl_pct=0.25, target_pct=0.70,
                  rsi_buy_lo=20, rsi_buy_hi=55, rsi_sell_lo=50, rsi_sell_hi=80,
                  sl_points=None, target_points=None):
    """Fibonacci Pullback + 15M Reversal + RSI रणनीती — established, बग-दुरुस्त आवृत्ती."""
    legs = []
    for a, b in zip(ps[:-1], ps[1:]):
        if a["type"] == "SL" and b["type"] == "SH":
            legs.append(("BUY", a, b))
        elif a["type"] == "SH" and b["type"] == "SL":
            legs.append(("SELL", a, b))
    m15 = m15.copy()
    m15["RSI"] = rsi14(m15["Close"])
    sig = []
    for direction, a, b in legs:
        lo, hi = sorted([a["price"], b["price"]])
        move = hi - lo
        if direction == "BUY":
            zlow = b["price"] - move * fib2; zhigh = b["price"] - move * fib1
        else:
            zlow = b["price"] + move * fib1; zhigh = b["price"] + move * fib2
        zone_low, zone_high = sorted([zlow, zhigh])
        start = h1.iloc[b["confirmed"]]["Date"]
        x = m15[m15.Date >= start].reset_index(drop=True)
        for j in range(1, len(x) - 1):
            prev, cur, nxt = x.iloc[j - 1], x.iloc[j], x.iloc[j + 1]
            if not (cur.High >= zone_low and cur.Low <= zone_high): continue
            pat = reversal(prev, cur, direction)
            if not pat: continue
            if pd.isna(cur.RSI): continue
            if direction == "BUY" and not (rsi_buy_lo <= cur.RSI <= rsi_buy_hi): continue
            if direction == "SELL" and not (rsi_sell_lo <= cur.RSI <= rsi_sell_hi): continue
            entry = float(nxt.Open)
            if sl_points is not None and target_points is not None:
                if direction == "BUY":
                    sl = entry - sl_points; target = entry + target_points
                else:
                    sl = entry + sl_points; target = entry - target_points
                rr = target_points / sl_points
            else:
                if direction == "BUY":
                    sl = entry * (1 - sl_pct / 100); target = entry * (1 + target_pct / 100)
                else:
                    sl = entry * (1 + sl_pct / 100); target = entry * (1 - target_pct / 100)
                rr = target_pct / sl_pct
            risk = abs(entry - sl)
            if risk <= 0: continue
            sig.append(dict(SignalDate=nxt.Date, ReversalDate=cur.Date, Signal=direction,
                             ReversalPattern=pat, ImpulseStart=a["price"], ImpulseEnd=b["price"],
                             PullbackLow=zone_low, PullbackHigh=zone_high, Entry=entry,
                             StopLoss=sl, Target=target, RiskPoints=risk, RR=rr, RSI=round(float(cur.RSI), 2)))
            break
    return pd.DataFrame(sig)


def detect_gap(prev_high, prev_low, curr_high, curr_low):
    """Up/Down gap ओळखणे — दोन सलग किंमत-बिंदूंमध्ये खरी रिकामी जागा (overlap नाही) असेल तरच."""
    if curr_low > prev_high:
        return "UP_GAP", prev_high, curr_low
    elif curr_high < prev_low:
        return "DOWN_GAP", curr_high, prev_low
    return None, None, None


def find_overnight_gaps(m15, min_gap_pct=0.30):
    """फक्त खरा overnight gap (मागच्या दिवसाचा शेवटचा 15M close ते पुढच्या दिवसाचा market open), किमान min_gap_pct%."""
    m15 = m15.copy()
    m15["_date"] = m15["Date"].dt.date
    days = sorted(m15["_date"].unique())
    gaps = []
    for i in range(1, len(days)):
        prev_rows = m15[m15["_date"] == days[i - 1]]
        next_rows = m15[m15["_date"] == days[i]]
        if prev_rows.empty or next_rows.empty: continue
        prev_last = prev_rows.iloc[-1]; next_first = next_rows.iloc[0]
        kind, glo, ghi = detect_gap(prev_last.High, prev_last.Low, next_first.High, next_first.Low)
        if kind and (ghi - glo) >= glo * min_gap_pct / 100:
            gaps.append({"kind": kind, "gap_low": glo, "gap_high": ghi, "gap_time": next_first.Date})
    return gaps


def make_gap_fill_signals(h1, m15, ps, sl_pct=0.25, target_pct=0.70, sl_points=None,
                           target_points=None, min_gap_pct=0.30):
    """
    "Unfilled Gap → Full Fill → Instant Entry" रणनीती — established, वापरकर्त्याशी चर्चा करून
    अंतिम केलेली आवृत्ती (कुठलीही candle-pattern/RSI पुष्टी नाही, gap पूर्णपणे भरला गेला तरच entry,
    कालमर्यादा नाही — gap भविष्यात कधीही भरला जाऊ शकतो).
    """
    legs = []
    for a, b in zip(ps[:-1], ps[1:]):
        if a["type"] == "SL" and b["type"] == "SH":
            legs.append(("BUY", a, b))
        elif a["type"] == "SH" and b["type"] == "SL":
            legs.append(("SELL", a, b))
    all_gaps = find_overnight_gaps(m15, min_gap_pct)
    sig = []
    for direction, a, b in legs:
        leg_start = h1.iloc[a["idx"]]["Date"]; leg_end = h1.iloc[b["idx"]]["Date"]
        wanted_kind = "UP_GAP" if direction == "BUY" else "DOWN_GAP"
        gaps = [g for g in all_gaps if g["kind"] == wanted_kind and leg_start <= g["gap_time"] <= leg_end]
        for gap in gaps:
            x = m15[m15.Date > gap["gap_time"]].reset_index(drop=True)
            for j in range(len(x)):
                cur = x.iloc[j]
                fully_filled = (cur.Low <= gap["gap_low"]) if direction == "BUY" else (cur.High >= gap["gap_high"])
                if not fully_filled: continue
                entry = float(gap["gap_low"]) if direction == "BUY" else float(gap["gap_high"])
                if sl_points is not None and target_points is not None:
                    if direction == "BUY":
                        sl = entry - sl_points; target = entry + target_points
                    else:
                        sl = entry + sl_points; target = entry - target_points
                    rr = target_points / sl_points
                else:
                    if direction == "BUY":
                        sl = entry * (1 - sl_pct / 100); target = entry * (1 + target_pct / 100)
                    else:
                        sl = entry * (1 + sl_pct / 100); target = entry * (1 - target_pct / 100)
                    rr = target_pct / sl_pct
                risk = abs(entry - sl)
                if risk <= 0: continue
                sig.append(dict(SignalDate=cur.Date, ReversalDate=cur.Date, Signal=direction,
                                 ReversalPattern="GapFill: Instant (no confirmation)",
                                 ImpulseStart=a["price"], ImpulseEnd=b["price"],
                                 PullbackLow=gap["gap_low"], PullbackHigh=gap["gap_high"], Entry=entry,
                                 StopLoss=sl, Target=target, RiskPoints=risk, RR=rr, RSI=np.nan))
                break
    return pd.DataFrame(sig)


def evaluate(m15, s):
    """प्रत्येक signal चा निकाल (SL/Target/अजून खुला) आणि R-multiple, खऱ्या RR नुसार."""
    if s.empty: return s
    out = []
    for _, r in s.iterrows():
        outcome = "OPEN/NO HIT"; ep = np.nan; ed = pd.NaT
        for _, c in m15[m15.Date > r.SignalDate].iterrows():
            if r.Signal == "BUY":
                sl = c.Low <= r.StopLoss; tp = c.High >= r.Target
            else:
                sl = c.High >= r.StopLoss; tp = c.Low <= r.Target
            if sl:
                outcome = "SL"; ep = r.StopLoss; ed = c.Date; break
            if tp:
                outcome = f"TARGET_{r.RR:g}R"; ep = r.Target; ed = c.Date; break
        q = r.to_dict(); q.update(Outcome=outcome, ExitDate=ed, ExitPrice=ep,
                                   R_Result=r.RR if outcome.startswith("TARGET_") else -1 if outcome == "SL" else np.nan)
        out.append(q)
    return pd.DataFrame(out)


def find_open_gaps_now(h1, m15, ps, min_gap_pct=0.30):
    """
    🎓 Dashboard साठी नवीन — "सध्या अजून न भरलेले" gaps शोधणे (Live monitoring साठी उपयुक्त — हे
    zones आहेत जिथे किंमत पोहोचली की gap_fill रणनीती त्वरित entry घेईल).
    """
    legs = []
    for a, b in zip(ps[:-1], ps[1:]):
        if a["type"] == "SL" and b["type"] == "SH":
            legs.append(("BUY", a, b))
        elif a["type"] == "SH" and b["type"] == "SL":
            legs.append(("SELL", a, b))
    all_gaps = find_overnight_gaps(m15, min_gap_pct)
    open_gaps = []
    for direction, a, b in legs:
        leg_start = h1.iloc[a["idx"]]["Date"]; leg_end = h1.iloc[b["idx"]]["Date"]
        wanted_kind = "UP_GAP" if direction == "BUY" else "DOWN_GAP"
        gaps = [g for g in all_gaps if g["kind"] == wanted_kind and leg_start <= g["gap_time"] <= leg_end]
        for gap in gaps:
            x = m15[m15.Date > gap["gap_time"]]
            filled = False
            for _, cur in x.iterrows():
                fully_filled = (cur.Low <= gap["gap_low"]) if direction == "BUY" else (cur.High >= gap["gap_high"])
                if fully_filled:
                    filled = True; break
            if not filled:
                open_gaps.append({"Direction": direction, "GapLow": gap["gap_low"], "GapHigh": gap["gap_high"],
                                   "GapDate": gap["gap_time"], "FillTriggerPrice": gap["gap_low"] if direction == "BUY" else gap["gap_high"]})
    return pd.DataFrame(open_gaps)
