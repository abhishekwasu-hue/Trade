"""
sr_bot_level_backtest.py
--------------------------
🎓 वापरकर्त्याचा निर्णय: "5-Min Instant Trader" (dynamic_sr_instant_trader.py) आणि "15M Dynamic SR Reversal"
(srv2_momentum_reversal_strategy.py) मध्ये जुने Dynamic S/R levels (sr_dynamic.compute_dynamic_sr) ऐवजी SR V3 levels
(sr_levels_v3.compute_sr_v3, फक्त grade A/B) वापरायचे — **आधी backtest, मग PAPER**. हा मॉड्यूल फक्त ती तुलना करतो:
दोन्ही bots चे entry/exit नियम तेच, फक्त levels चा स्रोत बदलतो. कुठलाही order/DB/network नाही.

Bot नियम (त्यांच्या कोडमधून/डीफॉल्ट settings मधून; touch/दिशा functions थेट bot फाईलमधूनच वापरले):
  • Touch: शेवटच्या 2 × 1-मिनिट candles चा [low, high] level ला स्पर्श (5M bot: ±0.01%, 15M bot: 0) किंवा gap-through
    (`dynamic_sr_instant_trader.check_level_crossed`).
  • दिशा: किंमत level च्या वर ⇒ BULLISH (support), खाली ⇒ BEARISH — hysteresis (5M: 0.10%, 15M: 0.015%).
  • RSI gate (डीफॉल्ट चालू): Support ⇒ RSI < 40, Resistance ⇒ RSI > 60. 5M bot: RSI(14) 1-मिनिट; 15M bot: RSI(14) 15M.
  • एका level वर दिवसात कमाल 2 trades, SL नंतर 15 मिनिटं cooldown, एका वेळी एकच position, 14:45 नंतर नवीन entry नाही.
  • Exit (spot-proxy; option premium/IV चा इतिहास नाही): naked settings चे spot % — 5M: SL 0.05%, Target 0.20%;
    15M: SL 0.05%, Target 0.40%. एकाच मिनिटात दोन्ही ⇒ SL आधी. EOD: 5M bot 15:00, 15M bot 15:10.
  • PCR gate वगळला (ऐतिहासिक PCR डेटा नाही) — दोन्ही स्रोतांना सारखाच लागू.

Levels (दोन्ही स्रोत त्याच वेळांना, फक्त त्या क्षणापर्यंत *बंद* झालेल्या bars वरून — no-lookahead):
  • पुन्हा-गणना: 09:15 आणि नंतर दर तासाला (10:15 … 14:15). Live मध्ये 5M levels दर 5 मिनिटांनी ताजे होतात — हा फरक
    दोन्ही स्रोतांना सारखाच.
  • Dynamic (जुना): 5M bot — शेवटचे ~10 दिवस 5M (750 bars); 15M bot — शेवटचे ~180 दिवस 15M (4500 bars);
    compute_dynamic_sr(prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2) — refresh scripts प्रमाणे.
  • SR V3: 5M bot — 5M + 15M pivots; 15M bot — 15M + 30M + 1H pivots; दोन्हीत PDH/PDL/PDC/PWH/PWL + gaps;
    फक्त grade A/B, किंमतीपासून 3% आत.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dynamic_sr_instant_trader import check_level_crossed, determine_direction_with_hysteresis
from signals import calculate_rsi
from sr_dynamic import compute_dynamic_sr
from sr_levels_v3 import compute_sr_v3

IS_END = pd.Timestamp("2021-12-31")


@dataclass
class BotSpec:
    name: str
    touch_tol_pct: float
    hysteresis_pct: float
    rsi_tf: str                         # "1min" | "15min"
    sl_pct: float
    target_pct: float
    eod: str
    dyn_tf: str                         # जुन्या levels चा TF
    dyn_bars: int
    v3_frames: tuple                    # (("5minute", "5min", bars), ...)
    rsi_support_max: float = 40.0
    rsi_resistance_min: float = 60.0
    max_hits: int = 2
    cooldown_min: int = 15
    last_entry: str = "14:45"
    recompute: tuple = ("09:15", "10:15", "11:15", "12:15", "13:15", "14:15")
    v3_grades: tuple = ("A", "B")
    v3_max_dist_pct: float = 3.0


BOTS = {
    "5m_instant": BotSpec("5m_instant", touch_tol_pct=0.01, hysteresis_pct=0.10, rsi_tf="1min", sl_pct=0.05, target_pct=0.20, eod="15:00",
                          dyn_tf="5min", dyn_bars=750, v3_frames=(("5minute", "5min", 1500), ("15minute", "15min", 500))),
    "15m_reversal": BotSpec("15m_reversal", touch_tol_pct=0.0, hysteresis_pct=0.015, rsi_tf="15min", sl_pct=0.05, target_pct=0.40, eod="15:10",
                            dyn_tf="15min", dyn_bars=4500,
                            v3_frames=(("15minute", "15min", 1500), ("30minute", "30min", 800), ("1hour", "60min", 500))),
}
SOURCES = ("DYNAMIC", "SR_V3")


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def resample(df1, rule):
    """1-मिनिट (timestamp = bar start) -> rule bars, NSE सत्र 09:15 पासून (label = bar start). अपूर्ण शेवटचा bar वगळत नाही —
    caller फक्त `end <= t` असलेले घेतो."""
    d = df1.set_index("timestamp")
    out = d.resample(rule, label="left", closed="left", origin="start_day", offset="15min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    out["end"] = out["timestamp"] + pd.Timedelta(rule)
    return out


@dataclass
class Prepared:
    df1: pd.DataFrame
    frames: dict                        # rule -> DataFrame (end column)
    ends: dict                          # rule -> numpy datetime64 array of bar ends
    daily: pd.DataFrame
    rsi1: np.ndarray
    rsi15: np.ndarray
    days: list = field(default_factory=list)


def prepare(df1):
    """1-मिनिट इतिहास -> सर्व TF frames, Daily, RSI series (एकदाच)."""
    df1 = df1[["timestamp", "open", "high", "low", "close"]].sort_values("timestamp").reset_index(drop=True)
    t = df1["timestamp"].dt
    mins = t.hour * 60 + t.minute
    df1 = df1[(mins >= 9 * 60 + 15) & (mins <= 15 * 60 + 29)].reset_index(drop=True)
    frames = {r: resample(df1, r) for r in ("5min", "15min", "30min", "60min")}
    ends = {r: f["end"].to_numpy("datetime64[ns]") for r, f in frames.items()}
    d = df1.set_index("timestamp")
    daily = d.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    rsi1 = calculate_rsi(df1, period=14).to_numpy(float, copy=True)
    rsi15 = calculate_rsi(frames["15min"], period=14).to_numpy(float, copy=True)
    days = sorted(df1["timestamp"].dt.normalize().unique())
    return Prepared(df1=df1, frames=frames, ends=ends, daily=daily, rsi1=rsi1, rsi15=rsi15, days=[pd.Timestamp(x) for x in days])


def _closed(prep, rule, t, n):
    i = int(np.searchsorted(prep.ends[rule], np.datetime64(t), side="right"))
    return prep.frames[rule].iloc[max(0, i - n):i]


def levels_at(prep, spec, source, t):
    """`t` क्षणी (त्यापर्यंत बंद bars) त्या bot चे levels — [float]."""
    if source == "DYNAMIC":
        df = _closed(prep, spec.dyn_tf, t, spec.dyn_bars)
        if len(df) < 50:
            return []
        z = compute_dynamic_sr(df, prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        return sorted({round(float(x["level"]), 2) for x in z.get("support", []) + z.get("resistance", [])})
    frames = {}
    for name, rule, n in spec.v3_frames:
        f = _closed(prep, rule, t, n)
        if len(f):
            frames[name] = f[["timestamp", "open", "high", "low", "close"]]
    if not frames:
        return []
    daily = prep.daily[prep.daily["timestamp"] < pd.Timestamp(t).normalize()].tail(30)
    res = compute_sr_v3(frames, daily_df=daily)
    return sorted({round(float(z["level"]), 2) for z in res["levels"]
                   if z["grade"] in spec.v3_grades and abs(z["distance_pct"]) <= spec.v3_max_dist_pct})


def _rsi_at(prep, spec, i1, t):
    if spec.rsi_tf == "1min":
        return prep.rsi1[i1]
    j = int(np.searchsorted(prep.ends["15min"], np.datetime64(t), side="right")) - 1     # शेवटचा बंद 15M bar
    return prep.rsi15[j] if j >= 0 else np.nan


def simulate(prep, spec, source, start=None, end=None, progress=None):
    """एक bot × एक level-स्रोत. रिटर्न trades DataFrame."""
    df1 = prep.df1
    ts = list(df1["timestamp"])
    day_key = df1["timestamp"].dt.normalize()
    o, h, l, c = (df1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    rows = []
    days = [d for d in prep.days if (start is None or d >= pd.Timestamp(start)) and (end is None or d <= pd.Timestamp(end))]
    idx_by_day = df1.groupby(day_key).indices
    eod, last_entry = _hm(spec.eod), _hm(spec.last_entry)
    recompute = {_hm(x) for x in spec.recompute}
    for di, d in enumerate(days):
        if di < 20 and start is None:
            continue                                            # warm-up (levels साठी इतिहास)
        ix = idx_by_day.get(d)
        if ix is None or len(ix) < 30:
            continue
        levels, hits, pos, cooldown_until = [], {}, None, None
        closes_today = []
        for k, i in enumerate(ix):
            t = ts[i]
            m = t.hour * 60 + t.minute
            bar_end = t + pd.Timedelta(minutes=1)
            closes_today.append(c[i])
            if pos is not None:                                 # --- exit ---
                s = pos["sign"]
                sl_hit = (l[i] <= pos["sl"]) if s > 0 else (h[i] >= pos["sl"])
                tg_hit = (h[i] >= pos["target"]) if s > 0 else (l[i] <= pos["target"])
                reason, px = (("SL", pos["sl"]) if sl_hit else ("TARGET", pos["target"]) if tg_hit else
                              ("EOD", c[i]) if m + 1 >= eod else (None, None))
                if reason:
                    pts = (px - pos["entry"]) * s
                    rows.append({**{k2: pos[k2] for k2 in ("date", "entry_time", "level", "direction", "entry")}, "exit_time": bar_end, "exit": px,
                                 "reason": reason, "pts": pts, "r": pts / pos["risk"], "source": source, "bot": spec.name})
                    if reason == "SL":
                        cooldown_until = bar_end + pd.Timedelta(minutes=spec.cooldown_min)
                    pos = None
            if m in recompute:
                levels = levels_at(prep, spec, source, t)       # t = bar start ⇒ फक्त आधीचे बंद bars
            if pos is not None or k == 0 or not levels or m >= last_entry or (cooldown_until is not None and t < cooldown_until):
                continue
            recent = [{"open": o[j], "high": h[j], "low": l[j], "close": c[j]} for j in (ix[k - 1], i)]
            for lv in levels:
                if hits.get(lv, 0) >= spec.max_hits:
                    continue
                hit, _, _ = check_level_crossed(lv, recent, tolerance_pct=spec.touch_tol_pct)
                if not hit:
                    continue
                direction = determine_direction_with_hysteresis(lv, closes_today, buffer_pct=spec.hysteresis_pct)
                rsi = _rsi_at(prep, spec, i, bar_end)
                if not np.isfinite(rsi):
                    continue
                ok = rsi < spec.rsi_support_max if direction == "BULLISH" else rsi > spec.rsi_resistance_min
                if not ok:
                    continue
                s = 1 if direction == "BULLISH" else -1
                entry = c[i]
                risk = entry * spec.sl_pct / 100.0
                hits[lv] = hits.get(lv, 0) + 1
                pos = {"date": d, "entry_time": bar_end, "level": lv, "direction": direction, "entry": entry, "sign": s, "risk": risk,
                       "sl": entry - s * risk, "target": entry + s * entry * spec.target_pct / 100.0}
                break
        if progress and di % 250 == 0:
            progress(spec.name, source, di, len(days), d)
    return pd.DataFrame(rows)


def summarize(tr):
    if tr is None or len(tr) == 0:
        return {"trades": 0, "win_pct": None, "avg_pts": None, "total_pts": 0.0, "avg_r": None, "profit_factor": None, "sl_pct": None, "target_pct": None}
    p = tr["pts"].astype(float)
    wins, losses = p[p > 0], p[p < 0]
    return {"trades": int(len(tr)), "win_pct": round(float((p > 0).mean() * 100), 1), "avg_pts": round(float(p.mean()), 2),
            "total_pts": round(float(p.sum()), 1), "avg_r": round(float(tr["r"].mean()), 3),
            "profit_factor": None if losses.empty else round(float(wins.sum() / abs(losses.sum())), 2),
            "sl_pct": round(float((tr["reason"] == "SL").mean() * 100), 1), "target_pct": round(float((tr["reason"] == "TARGET").mean() * 100), 1)}


def comparison(all_trades):
    """bot × source × (IS / OOS) सारांश — IS आणि OOS वेगळे."""
    rows = []
    if all_trades is None or len(all_trades) == 0:
        return pd.DataFrame()
    for (bot, src), g in all_trades.groupby(["bot", "source"]):
        dt = pd.to_datetime(g["date"])
        for label, part in (("IS 2015→2021", g[dt <= IS_END]), ("OOS 2022→", g[dt > IS_END])):
            rows.append({"bot": bot, "source": src, "period": label, **summarize(part)})
    return pd.DataFrame(rows)


def yearwise(all_trades):
    if all_trades is None or len(all_trades) == 0:
        return pd.DataFrame()
    t = all_trades.assign(year=pd.to_datetime(all_trades["date"]).dt.year)
    rows = [{"bot": b, "source": s, "year": y, **summarize(g)} for (b, s, y), g in t.groupby(["bot", "source", "year"])]
    return pd.DataFrame(rows)
