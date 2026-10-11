"""
level_bots_replay.py
--------------------
🎓 L6 (Abhi, TRADE_SESSION_LEVEL_BOTS_CONFIRMATION §6): level bots चा replay — जुना "touch" वि. नवा "confirmation" gate, **त्याच**
काळावर, **त्याच** levels वर, तोच cost नियम. कुठलाही order / DB / network नाही (फक्त local data). CLI: scripts/level_bots_replay.py.

दोन्ही बाजू (arms) एकाच दिवसाच्या, एकाच level-संचावर:
  • touch (legacy) — bot चीच functions थेट bot फाईलमधून (copy नाही ⇒ legacy = आजचं touch वर्तन): `check_level_crossed`
    (touch / gap-through, bot ची tolerance), `determine_direction_with_hysteresis` (bot चा buffer), RSI उंबरठे (settings defaults), max hits
    (level + role, दिवसात), cooldowns, एका वेळी एकच position, 14:45 नंतर नवा entry नाही, EOD. Exit = bot च्या naked settings चे spot %
    SL / target (MCX: settings चे points). PCR gate वगळला (ऐतिहासिक PCR नाही).
  • confirmation — `level_reaction.evaluate` (live सारखंच: प्रत्येक बंद confirmation-TF candle ला आजचे बंद bars replay, `entry` फक्त
    commitment candle वरच), trend = ONE `decision3.daily.fold` प्रति symbol + `DD.state_at` प्रति दिवस ⇒ `LR.context_from_state`.
    RSI / PCR gates बंद (confirmation default), breakout नाही; position नियम (एकच position, max hits, cooldowns, 14:45) तेच.
    Exit = gate चा structural SL (area च्या दूरच्या कडेपलीकडे + buffer) / target (पुढचा उलट area).
Levels = bots चे Dynamic S/R (sr_dynamic.compute_dynamic_sr, refresh scripts चेच parameters आणि lookback), सत्राच्या सुरुवातीला आणि नंतर
दर `level_refresh_min` मिनिटांनी फक्त बंद bars वरून पुन्हा (no lookahead). Level memory replay केलेली नाही.
Exit नियम: पुढच्या base bars वर; एकाच bar मध्ये SL आणि target ⇒ SL आधी (pessimistic); gap SL पलीकडे ⇒ open भावाला; EOD ⇒ close.
P&L = index / futures points (option premium चा intraday इतिहास नाही); cost = charges.py चे round-trip शुल्क (1 lot naked ITM option
buy, premium / delta / slippage = `COST_DEFAULTS`, निकाल पाहून ठरवलेले नाहीत) points मध्ये रूपांतरित.
NIFTY: फक्त IS / VAL (elliott.data_policy); HOLDOUT कधीच load होत नाही (`assert_research_only`). BANKNIFTY / MCX sealed नाहीत.
"""
from dataclasses import dataclass, field
import bisect

import numpy as np
import pandas as pd

from bots_common import level_gate_bot as LGB
from bots_common import level_reaction as LR
from elliott import data_policy as DP

TOUCH, CONF = "touch", "confirmation"
MIN_N = 30                                  # Abhi: n < 30 ⇒ निष्कर्ष नाही
SEALED = {"NIFTY"}                          # holdout फक्त NIFTY चा sealed (BANKNIFTY / SENSEX / MCX नाहीत)
TREND_BUCKET = {"UP": "bull", "DOWN": "bear", "RANGE": "range"}
DEFAULTS = {
    "level_refresh_min": 60,                # levels पुन्हा: सत्र सुरुवात + दर इतक्या मिनिटांनी (bars बंद झालेले फक्त)
    "min_level_bars": 100,                  # compute_all_zones / refresh scripts प्रमाणे: किमान इतके bars नसतील ⇒ त्या TF चे levels नाहीत
    "ctx_days": 2,                          # gate bars: आजच्या आधीचे इतके दिवस (median range साठी; live 5 दिवस fetch करते)
    "list_per_reason": 15,                  # अहवालात प्रत्येक कारणाखाली इतकी उदाहरणे (पूर्ण यादी CSV मध्ये)
}
# Dynamic S/R lookback (calendar days) — refresh scripts प्रमाणे: 1M Upstox default (~5 दिवस), 5M refresh_dynamic_sr_5m (~10 दिवस),
# 15M / 30M / 60M refresh_market_zones(_intraday) 180 दिवस; MCX refresh_market_zones_mcx 180 दिवस
LOOKBACK_DAYS = {"1M": 5, "5M": 10, "15M": 180, "30M": 180, "60M": 180}
TF_MIN = {"1M": 1, "5M": 5, "15M": 15, "30M": 30, "60M": 60}
# Cost गृहीतके (निकाल न पाहता): NIFTY / BANKNIFTY ⇒ 1 lot naked ITM option buy (bots चा naked leg, ITM depth 50 / 100);
# premium ₹, delta (ITM ≈ 0.6), slippage ₹ प्रति बाजू. MCX ⇒ 1 lot futures, slippage points प्रति बाजू.
COST_DEFAULTS = {
    "NIFTY": {"kind": "option", "premium": 150.0, "lot": 75, "delta": 0.6, "slip_prem": 0.5},
    "BANKNIFTY": {"kind": "option", "premium": 350.0, "lot": 35, "delta": 0.6, "slip_prem": 1.0},
    "GOLD": {"kind": "future", "lot": 1, "slip_pts": 1.0},
    "SILVER": {"kind": "future", "lot": 30, "slip_pts": 1.0},
    "COPPER": {"kind": "future", "lot": 2500, "slip_pts": 0.05},
}


# ------------------------------------------------------------------------------------------------ bot specs (bot फाईल्स / settings मधून)
@dataclass(frozen=True)
class BotSpec:
    name: str                   # अहवालातलं नाव
    gate_key: str               # LGB.CONFIRM_TF key
    level_tfs: tuple            # ("5M", ...) — market_zones zone_type suffix
    touch_tf: int               # touch तपासणीचे candles (मिनिटे): 1 (1M bots) / 5 (Classic) / 30 (MCX)
    touch_kind: str             # "range" (check_level_crossed) | "price" (|भाव − level| ≤ tol — MCX)
    touch_fn: object
    touch_tol_pct: float
    dir_fn: object
    hyst_pct: float
    hyst_tf: object             # मिनिटे, किंवा None ⇒ level चा TF
    rsi_tf: object              # मिनिटे, किंवा None ⇒ level चा TF
    rsi_bull_max: float         # BULLISH ⇒ RSI < इतका
    rsi_bear_min: float         # BEARISH ⇒ RSI > इतका
    sl: tuple                   # ("pct", x) spot % | ("pts", x)
    target: tuple
    max_hits: int               # (level, role) प्रति दिवस
    level_sl_cooldown: int      # त्याच level वर SL नंतर मिनिटे
    level_trade_gap: int        # त्याच level वर मागच्या entry नंतर किमान मिनिटे (Classic 30)
    symbol_sl_cooldown: int     # symbol-व्यापी SL नंतर मिनिटे (SRv2 30, MCX)
    last_entry: str             # "HH:MM" — या वेळेपासून नवा entry नाही
    eod: str                    # "HH:MM" — EOD square-off
    markets: tuple = ("NSE",)


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def _tfs(choice, both):
    return tuple(both) if str(choice).upper() in ("BOTH", "ALL") else (str(choice),)


def bot_specs():
    """चारही specs — आकडे bot फाईल्स (constants) आणि cloud_db.STRATEGY_SETTINGS_DEFAULTS मधून (copy नाही)."""
    import classic_sr_reversal_trader as CSR
    import dynamic_sr_instant_trader as DSI
    import mcx_futures_trader as MCX
    import srv2_momentum_reversal_strategy as SRV2
    import trading_engine as TE
    from cloud_db import STRATEGY_SETTINGS_DEFAULTS as SSD
    i, v, c, x = SSD["1m_instant"], SSD["15m_dynamic_sr"], SSD["classic_sr_reversal"], SSD["mcx_futures"]
    out = {
        "instant": BotSpec(
            "5M Instant", "dynamic_sr_instant", _tfs(i["timeframe_choice"], DSI.POOLED_TIMEFRAMES), 1, "range", DSI.check_level_crossed,
            DSI.TOUCH_TOLERANCE_PCT, DSI.determine_direction_with_hysteresis, DSI.DIRECTION_HYSTERESIS_BUFFER_PCT, 1, 1,
            float(i["rsi_support_max"]), float(i["rsi_resistance_min"]), ("pct", float(i["naked_sl_spot_pct"])),
            ("pct", float(i["naked_target_spot_pct"])), int(i["max_hits_per_zone"]), int(i["sl_tsl_cooldown_minutes"]), 0, 0,
            f"{DSI.NO_NEW_ENTRY_AFTER_HOUR}:{DSI.NO_NEW_ENTRY_AFTER_MINUTE:02d}", f"{TE.DYNAMIC_SR_EOD_HOUR}:{TE.DYNAMIC_SR_EOD_MINUTE:02d}"),
        "srv2": BotSpec(
            "15M SRv2", "srv2", tuple(v["active_timeframes"]), 1, "range", SRV2.check_level_crossed, SRV2.TOUCH_TOLERANCE_PCT,
            SRV2.determine_direction_with_hysteresis, SRV2.DIRECTION_HYSTERESIS_BUFFER_PCT, None, None, float(v["rsi_support_max"]),
            float(v["rsi_resistance_min"]), ("pct", float(v["naked_sl_spot_pct"])), ("pct", float(v["naked_target_spot_pct"])),
            int(v["max_hits_per_zone"]), int(v["sl_tsl_cooldown_minutes"]), 0, int(SRV2.COOLDOWN_MINUTES),
            f"{SRV2.NO_NEW_ENTRY_AFTER_HOUR}:{SRV2.NO_NEW_ENTRY_AFTER_MINUTE:02d}", f"{int(v['naked_eod_hour'])}:{int(v['naked_eod_minute']):02d}"),
        "classic": BotSpec(
            "Classic", "classic_sr", _tfs(c["timeframe_choice"], CSR.POOLED_TIMEFRAMES), 5, "range", CSR.check_level_crossed,
            CSR.TOUCH_TOLERANCE_PCT, CSR.determine_direction_with_hysteresis, DSI.DIRECTION_HYSTERESIS_BUFFER_PCT, 5, 5,
            float(c["rsi_neutral_level"]), float(c["rsi_neutral_level"]), ("pct", float(c["naked_sl_spot_pct"])),
            ("pct", float(c["naked_target_spot_pct"])), int(c["max_hits_per_zone"]), int(c["sl_tsl_cooldown_minutes"]), 30, 0,
            f"{CSR.NO_NEW_ENTRY_AFTER_HOUR}:{CSR.NO_NEW_ENTRY_AFTER_MINUTE:02d}", f"{TE.CLASSIC_SR_EOD_HOUR}:{TE.CLASSIC_SR_EOD_MINUTE:02d}"),
    }
    pts = str(x.get("sl_target_mode", "POINTS")).upper() == "POINTS"
    out["mcx"] = BotSpec(
        "MCX", "mcx", _tfs(x["timeframe_choice"], ("30M", "60M")), 30, "price", None, MCX.TOUCH_TOLERANCE_PCT,
        MCX.determine_direction_with_hysteresis, MCX.DIRECTION_HYSTERESIS_BUFFER_PCT, None, None, float(x["rsi_support_max"]),
        float(x["rsi_resistance_min"]), ("pts", float(x["sl_points"])) if pts else ("pct", float(x["sl_pct"])),
        ("pts", float(x["target_points"])) if pts else ("pct", float(x["target_pct"])), int(x["max_hits_per_zone"]), 0, 0,
        int(x.get("sl_cooldown_minutes", 0)), f"{MCX.MCX_NO_NEW_ENTRY_AFTER[0]}:{MCX.MCX_NO_NEW_ENTRY_AFTER[1]:02d}",
        f"{MCX.MCX_EOD_HOUR}:{MCX.MCX_EOD_MINUTE:02d}", markets=("MCX",))
    return out


# ------------------------------------------------------------------------------------------------ data
class HoldoutGuardError(DP.HoldoutError):
    pass


def assert_research_only(df, symbol, col="timestamp"):
    """NIFTY च्या data मध्ये IS / VAL (आणि warm-up) शिवाय काहीही ⇒ HoldoutError (sealed holdout कधीच replay होत नाही)."""
    if str(symbol).upper() not in SEALED or df is None or len(df) == 0:
        return True
    ts = pd.to_datetime(df[col])
    if (ts >= DP.HOLDOUT_START).any():
        raise HoldoutGuardError(f"{symbol}: {int((ts >= DP.HOLDOUT_START).sum())} rows ≥ {DP.HOLDOUT_START.date()} — sealed, replay नाही")
    return True


def period_of(symbol, day):
    """अहवालातला काळ: NIFTY ⇒ data_policy (IS / VAL); इतर ⇒ "ALL" (sealed नाहीत)."""
    if str(symbol).upper() in SEALED:
        p = DP.period(day)
        if p not in ("PRE_IS", "IS", "VAL"):
            raise HoldoutGuardError(f"{symbol} {pd.Timestamp(day).date()}: {p} — replay नाही")
        return "IS" if p == "PRE_IS" else p
    return "ALL"


def resample(df, minutes, session_open):
    """base bars ⇒ `minutes` bars (label = सुरुवात, सत्र `session_open` पासून grid); end = सुरुवात + minutes."""
    off = _hm(session_open) % int(minutes)
    d = df.set_index("timestamp")
    out = d.resample(f"{int(minutes)}min", label="left", closed="left", origin="start_day", offset=f"{off}min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    out["end"] = out["timestamp"] + pd.Timedelta(minutes=int(minutes))
    return out


@dataclass
class Market:
    symbol: str
    base: int                                   # सर्वात बारीक bars (मिनिटे)
    session_open: str
    frames: dict                                # minutes -> DataFrame(timestamp, end, open, high, low, close, day)
    daily: pd.DataFrame
    states: list                                # decision3 DState (एकदाच fold)
    days: list
    exchange: str = "NSE"
    ends: dict = field(default_factory=dict)
    starts: dict = field(default_factory=dict)
    day_rows: dict = field(default_factory=dict)
    rsi: dict = field(default_factory=dict)


def prepare_market(symbol, base_df, base_minutes, session_open="09:15", daily_df=None, exchange="NSE", tfs=(1, 5, 15, 30, 60), fold=None):
    """base bars ⇒ सगळे TF frames, RSI, दिवस, आणि Daily trend states — **एकच** `DD.fold` (fold = test साठी बदलता येतो)."""
    from decision3 import daily as DD
    from decision3 import daily_swings as DS
    from signals import calculate_rsi
    b = base_df[["timestamp", "open", "high", "low", "close"]].copy()
    b["timestamp"] = pd.to_datetime(b["timestamp"])
    if getattr(b["timestamp"].dt, "tz", None) is not None:
        b["timestamp"] = b["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    b = b.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    assert_research_only(b, symbol)
    frames = {}
    for m in sorted({int(base_minutes), *[int(t) for t in tfs]}):
        if m < base_minutes or m % base_minutes:
            continue
        f = b.assign(end=b["timestamp"] + pd.Timedelta(minutes=int(m))) if m == base_minutes else resample(b, m, session_open)
        f["day"] = f["timestamp"].dt.normalize()
        frames[m] = f.reset_index(drop=True)
    if daily_df is None:
        daily_df = b.set_index("timestamp").resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    assert_research_only(daily_df, symbol)
    dd = DS.prepare(daily_df)
    states = (fold or DD.fold)(dd)
    mk = Market(symbol=str(symbol).upper(), base=int(base_minutes), session_open=session_open, frames=frames, daily=dd, states=states,
                days=sorted(pd.Timestamp(x) for x in frames[base_minutes]["day"].unique()), exchange=exchange)
    for m, f in frames.items():
        mk.ends[m] = f["end"].to_numpy("datetime64[ns]")
        mk.starts[m] = f["timestamp"].to_numpy("datetime64[ns]")
        mk.day_rows[m] = {pd.Timestamp(k): np.asarray(v) for k, v in f.groupby("day").indices.items()}
        mk.rsi[m] = calculate_rsi(f, period=14).to_numpy(float, copy=True)
    return mk


def trend_ctx(mk, day, gate_s=None):
    """दिवसाचा trend context: state_at(states, दिवसाची सुरुवात) ⇒ कालच्या close पर्यंतची Daily अवस्था (आजचा Daily bar नाही)."""
    from decision3 import daily as DD
    st = DD.state_at(mk.states, pd.Timestamp(day).normalize())
    return LR.context_from_state(st, gate_s, asof=str(pd.Timestamp(day).date()))


def trend_bucket(ctx):
    return TREND_BUCKET.get((ctx or {}).get("trend"), "no trend")


# ------------------------------------------------------------------------------------------------ levels
def refresh_times(day, session_open, last_entry, every_min):
    t0 = pd.Timestamp(day).normalize() + pd.Timedelta(minutes=_hm(session_open))
    t1 = pd.Timestamp(day).normalize() + pd.Timedelta(minutes=_hm(last_entry))
    out, t = [], t0
    while t < t1:
        out.append(t)
        t += pd.Timedelta(minutes=int(every_min))
    return out or [t0]


def levels_at(mk, spec, T, s=None):
    """T क्षणी (फक्त end ≤ T bars) bot चे Dynamic S/R levels — [(suffix, level)] (एकाच किंमतीचा level एकदाच)."""
    from sr_dynamic import compute_dynamic_sr
    s = {**DEFAULTS, **(s or {})}
    out, seen = [], set()
    for suf in spec.level_tfs:
        m = TF_MIN.get(suf)
        if m not in mk.frames:
            continue
        j1 = int(np.searchsorted(mk.ends[m], np.datetime64(pd.Timestamp(T)), side="right"))
        j0 = int(np.searchsorted(mk.starts[m], np.datetime64(pd.Timestamp(T) - pd.Timedelta(days=LOOKBACK_DAYS.get(suf, 180))), side="left"))
        if j1 - j0 < int(s["min_level_bars"]):
            continue
        z = compute_dynamic_sr(mk.frames[m].iloc[j0:j1], prd=10, maxnumpp=20, channel_w_pct=10, maxnumsr=5, min_strength=2)
        for x in z.get("support", []) + z.get("resistance", []):
            lv = round(float(x["level"]), 2)
            if lv not in seen:
                seen.add(lv)
                out.append((suf, lv))
    return out


def gate_area(level):
    """bots चं `_gate_area` गणित: single-price level ⇒ level ± (AREA_PAD_PCT % ÷ 2)."""
    pad = float(level) * float(LGB.AREA_PAD_PCT) / 100.0
    return LGB.areas_from_rows([{"zone_low": float(level), "zone_high": None}], pad)[0]


# ------------------------------------------------------------------------------------------------ costs / exits / metrics (pure)
def cost_points(symbol, price, c=None):
    """round-trip cost (points): charges.py (Upstox दर) ⇒ ₹ ÷ (lot × delta) + slippage. option ⇒ premium वर; future ⇒ futures भावावर."""
    import charges as CH
    from mcx_contract_specs import get_price_multiplier
    c = c or COST_DEFAULTS.get(str(symbol).upper())
    if not c:
        return 0.0
    if c["kind"] == "option":
        rows = [{"quantity": c["lot"], "price": c["premium"], "symbol": str(symbol).upper(), "transaction_type": t} for t in ("BUY", "SELL")]
        rupees = sum(CH._accurate_row_charges(r, "upstox")["charge"] for r in rows)
        return rupees / (c["lot"] * c["delta"]) + 2.0 * c["slip_prem"] / c["delta"]
    mult = get_price_multiplier(symbol)
    rows = [{"quantity": c["lot"], "price": float(price), "symbol": str(symbol).upper(), "transaction_type": t} for t in ("BUY", "SELL")]
    rupees = sum(CH._accurate_row_charges(r, "upstox")["charge"] for r in rows)
    return rupees / (c["lot"] * mult) + 2.0 * c["slip_pts"]


def legacy_stops(spec, entry, direction):
    """legacy SL / target (bot settings): spot % किंवा points."""
    sg = 1 if direction == LR.BULL else -1

    def dist(x):
        return entry * x[1] / 100.0 if x[0] == "pct" else x[1]
    return entry - sg * dist(spec.sl), entry + sg * dist(spec.target)


def exit_on_bar(pos, o, h, l, c, eod_hit):
    """एका bar वर exit? ⇒ (reason, price) किंवा (None, None). SL आधी (एकाच bar मध्ये दोन्ही ⇒ SL); gap SL पलीकडे ⇒ open."""
    sg = 1 if pos["direction"] == LR.BULL else -1
    sl, tg = pos["sl"], pos["target"]
    if (l <= sl) if sg > 0 else (h >= sl):
        px = min(o, sl) if sg > 0 else max(o, sl)
        return "SL", float(px)
    if tg is not None and ((h >= tg) if sg > 0 else (l <= tg)):
        return "TARGET", float(tg)
    if eod_hit:
        return "EOD", float(c)
    return None, None


def take_trades(cands, bars, spec, symbol, cost=None):
    """दिवसाचे उमेदवार (entry time क्रमाने) ⇒ घेतलेले trades. bars = त्या दिवसाचे base bars (timestamp, end, ohlc). नियम: एका वेळी एकच
    position, (level, role) max hits, level SL cooldown, level trade gap, symbol SL cooldown, last_entry, EOD. एकाच bar ला आधी exit, मग entry."""
    by_t = {}
    for cd in sorted(cands, key=lambda x: (x["time"], x.get("order", 0))):
        by_t.setdefault(pd.Timestamp(cd["time"]), []).append(cd)
    last_m, eod_m = _hm(spec.last_entry), _hm(spec.eod)
    pos, out = None, []
    hits, last_entry_at, level_sl_at = {}, {}, {}
    sym_sl_at = None
    E = list(bars["end"])
    O, H, L, C = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    for i in range(len(bars)):
        end = pd.Timestamp(E[i])
        if pos is not None and end > pos["time"]:
            eod_hit = (end.hour * 60 + end.minute) >= eod_m or i == len(bars) - 1
            why, px = exit_on_bar(pos, O[i], H[i], L[i], C[i], eod_hit)
            if why:
                sg = 1 if pos["direction"] == LR.BULL else -1
                gross = (px - pos["entry"]) * sg
                cp = cost_points(symbol, pos["entry"]) if cost is None else float(cost)
                risk = abs(pos["entry"] - pos["sl"])
                out.append({**{k: v for k, v in pos.items() if k != "order"}, "exit_time": end, "exit": px, "exit_reason": why,
                            "gross_pts": gross, "cost_pts": cp, "net_pts": gross - cp, "risk_pts": risk,
                            "r_net": (gross - cp) / risk if risk > 0 else np.nan})
                if why == "SL":
                    level_sl_at[pos["level"]] = end
                    sym_sl_at = end
                pos = None
        if pos is not None or end not in by_t:
            continue
        if (end.hour * 60 + end.minute) >= last_m:
            continue
        if sym_sl_at is not None and (end - sym_sl_at) < pd.Timedelta(minutes=spec.symbol_sl_cooldown):
            continue
        for cd in by_t[end]:
            lv, key = cd["level"], (cd["level"], cd["direction"])
            if hits.get(key, 0) >= spec.max_hits:
                continue
            if lv in level_sl_at and (end - level_sl_at[lv]) < pd.Timedelta(minutes=spec.level_sl_cooldown):
                continue
            if lv in last_entry_at and (end - last_entry_at[lv]) < pd.Timedelta(minutes=spec.level_trade_gap):
                continue
            hits[key] = hits.get(key, 0) + 1
            last_entry_at[lv] = end
            pos = {**cd, "time": end}
            break
    return out


def metrics(net):
    """कालक्रमाने net P&L (points) ⇒ n, win rate, expectancy, total, max drawdown (cumulative, शिखर ते तळ), profit factor."""
    x = np.asarray(list(net), float)
    n = len(x)
    if n == 0:
        return {"n": 0, "win_rate": None, "expectancy": None, "total": 0.0, "max_dd": 0.0, "profit_factor": None}
    eq = np.cumsum(x)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    wins, losses = float(x[x > 0].sum()), float(-x[x < 0].sum())
    pf = (wins / losses) if losses > 0 else (float("inf") if wins > 0 else None)
    return {"n": n, "win_rate": float((x > 0).mean()), "expectancy": float(x.mean()), "total": float(x.sum()),
            "max_dd": float((peak - eq).max()), "profit_factor": pf}


# ------------------------------------------------------------------------------------------------ gate verdict for legacy trades
OTHER_SIDE = "gate confirmed the other side / an earlier visit"
NO_ARRIVAL = "no arrival on closed confirm-TF candles"
CATEGORY_LABEL = {
    "KEPT": "kept — the gate confirmed the same area and side",
    "SKIPPED_GATE_AGAINST_TREND": "against the Daily trend",
    "SKIPPED_GATE_NO_TREND": "Daily trend unclear / entries blocked",
    "SKIPPED_GATE_IMPULSIVE": "impulsive approach",
    "SKIPPED_GATE_WAITING_COMMITMENT": "no commitment yet (still armed)",
    "SKIPPED_GATE_BROKEN": "area broken (real break)",
    "SKIPPED_GATE_TIMEOUT": "timeout — no commitment within max_armed_bars",
    "SKIPPED_GATE_TIMEOUT_ABSORPTION": "timeout — counter side absorbing inside the area",
    "SKIPPED_GATE_RR": "R:R below minimum",
    "SKIPPED_GATE_NO_TARGET": "no opposite area for a target",
    "SKIPPED_GATE_ERROR": "gate error (fail-closed)",
    "SKIPPED_GATE_NOT_AT_AREA": "no arrival (price already inside the area / not at the area on closed candles)",
    "GATE_OTHER_SIDE": "gate confirmed the other side / an earlier visit",
}


def no_trend_detail(ctx):
    """trend unclear चं उप-कारण (English, अहवालासाठी)."""
    ctx = ctx or {}
    tr = ctx.get("trend")
    if tr not in ("UP", "DOWN", "RANGE"):
        return f"Daily {tr}"
    if ctx.get("phase") == "origin_broken":
        return f"Daily {tr}: protected origin closed beyond"
    if ctx.get("origin_risk"):
        return f"Daily {tr}: origin at risk (Q47)"
    if ctx.get("counter") == "correction":
        return f"Daily {tr}: parent correction (A1)"
    return f"Daily {tr}"


def verdict(r, lo_i, hi_i, kept, ctx=None, side=None, area=None):
    """एका legacy trade साठी gate चा निकाल (त्याच area, touch पासून max_armed_bars पर्यंत). रिटर्न (category, reason, detail).
    क्रम gate सारखाच: ① trend (दिवसाचा context नाही ⇒ trend unclear; legacy ची दिशा trend ने नाकारलेली ⇒ against trend), मग area वरचा निकाल."""
    if kept:
        return "KEPT", "confirmed", ""
    if ctx is not None and not ctx.get("ok"):
        return "SKIPPED_GATE_NO_TREND", ctx.get("reason") or LR.R_NO_TREND, no_trend_detail(ctx)
    if ctx is not None and side is not None and area is not None and not LR.side_allowed(ctx, side, area):
        return "SKIPPED_GATE_AGAINST_TREND", LR.R_AGAINST, f"Daily {ctx.get('trend')}"
    evs = [e for e in (r or {}).get("events", []) if lo_i <= e[0] <= hi_i]
    dis = [e for e in evs if e[1] == LR.DISARMED]
    st = (r or {}).get("state")
    if dis:
        reason = dis[-1][2]
    elif st in (LR.DISARMED, "ERROR"):
        reason = r.get("reason") or ""
    elif st == LR.ARMED:
        reason = LR.R_NO_COMMIT
    elif st == LR.CONFIRMED or any(e[1] == LR.CONFIRMED for e in evs):
        return "GATE_OTHER_SIDE", OTHER_SIDE, ""
    elif (r or {}).get("broken"):
        reason = LR.R_BROKEN
    else:
        return "SKIPPED_GATE_NOT_AT_AREA", NO_ARRIVAL, ""
    code = LGB.status_of({"reason": reason, "state": st if not dis else LR.DISARMED})
    if code == "SKIPPED_GATE_TIMEOUT" and any(e[2] == LR.R_ABSORPTION for e in evs):
        code = "SKIPPED_GATE_TIMEOUT_ABSORPTION"
    detail = no_trend_detail(ctx) if code == "SKIPPED_GATE_NO_TREND" else ""
    return code, reason, detail


# ------------------------------------------------------------------------------------------------ one day
def _bars_dicts(f, rows):
    return [{"open": float(f["open"].iat[j]), "high": float(f["high"].iat[j]), "low": float(f["low"].iat[j]), "close": float(f["close"].iat[j])}
            for j in rows]


def confirm_tf(mk, spec):
    m = int(LGB.CONFIRM_TF.get(spec.gate_key, 5))
    return m if m in mk.frames else mk.base


def supported(mk, spec):
    """bot चे सगळे level TFs या market च्या data मधून बनतात का (उदा. BANKNIFTY 15M data ⇒ 5M bots नाहीत)."""
    if mk.exchange not in spec.markets:
        return False
    return all(TF_MIN.get(t) in mk.frames for t in spec.level_tfs)


def replay_day(mk, spec, day, gate_s=None, s=None, cost=None):
    """एक दिवस: levels (refresh वेळा), legacy उमेदवार, gate signals (live सारखे, बंद bars), दोन्ही arms चे trades, legacy trades चा gate निकाल.
    रिटर्न dict: touch (trades), conf (trades), ctx, n_levels."""
    s = {**DEFAULTS, **(s or {})}
    gate_s = LR.settings(gate_s)
    day = pd.Timestamp(day).normalize()
    ctx = trend_ctx(mk, day, gate_s)
    base = mk.frames[mk.base]
    rows = mk.day_rows[mk.base].get(day)
    if rows is None or len(rows) < 2:
        return {"touch": [], "conf": [], "ctx": ctx, "n_levels": 0}
    times = refresh_times(day, mk.session_open, spec.last_entry, s["level_refresh_min"])
    epochs = [levels_at(mk, spec, T, s) for T in times]
    areas = [[gate_area(lv) for _, lv in ep] for ep in epochs]

    def epoch_of(t):
        return max(0, bisect.bisect_right(times, pd.Timestamp(t)) - 1)

    # ---------------- legacy (touch) उमेदवार
    O, H, Lo, Cl = (base[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    TS, EN = base["timestamp"], base["end"]
    ttf = spec.touch_tf if (spec.touch_tf in mk.frames and spec.touch_tf >= mk.base) else mk.base
    cands = []
    form, form_bin = None, None
    for k, i in enumerate(rows):
        c_t = pd.Timestamp(EN.iat[i])
        lv_list = epochs[epoch_of(c_t)]
        if spec.touch_kind == "range" and ttf != mk.base:            # forming touch-TF candle (live: चालू candle सुद्धा)
            b0 = day + pd.Timedelta(minutes=_hm(mk.session_open))
            bin_start = b0 + pd.Timedelta(minutes=((pd.Timestamp(TS.iat[i]) - b0) // pd.Timedelta(minutes=ttf)) * ttf)
            if bin_start != form_bin:
                form_bin, form = bin_start, {"open": O[i], "high": H[i], "low": Lo[i], "close": Cl[i]}
            else:
                form = {"open": form["open"], "high": max(form["high"], H[i]), "low": min(form["low"], Lo[i]), "close": Cl[i]}
        if not lv_list:
            continue
        price = float(Cl[i])
        if spec.touch_kind == "range":
            if ttf == mk.base:
                recent = _bars_dicts(base, rows[max(0, k - 1):k + 1])
            else:
                fr = mk.frames[ttf]
                j = int(np.searchsorted(mk.ends[ttf], np.datetime64(form_bin), side="right")) - 1
                prev = _bars_dicts(fr, [j]) if j >= 0 and pd.Timestamp(fr["day"].iat[j]) == day else []
                recent = prev + [dict(form)]
        closes_cache, rsi_cache = {}, {}
        for order, (suf, lv) in enumerate(lv_list):
            if spec.touch_kind == "price":
                hit = abs(price - lv) <= lv * spec.touch_tol_pct / 100.0
            else:
                hit = spec.touch_fn(lv, recent, tolerance_pct=spec.touch_tol_pct)[0]
            if not hit:
                continue
            hm = spec.hyst_tf or TF_MIN[suf]
            hm = hm if hm in mk.frames else mk.base
            if hm not in closes_cache:
                if hm == mk.base:
                    closes_cache[hm] = list(Cl[rows[:k + 1]])
                else:
                    fr = mk.frames[hm]
                    j = int(np.searchsorted(mk.ends[hm], np.datetime64(c_t), side="right"))
                    today = [x for x in mk.day_rows[hm].get(day, []) if x < j]
                    cl = list(fr["close"].to_numpy(float)[today])
                    if not today or pd.Timestamp(fr["end"].iat[today[-1]]) < c_t:
                        cl.append(price)                               # चालू (forming) candle चा भाव
                    closes_cache[hm] = cl
            direction = spec.dir_fn(lv, closes_cache[hm], buffer_pct=spec.hyst_pct)
            rm = spec.rsi_tf or TF_MIN[suf]
            rm = rm if rm in mk.frames else mk.base
            if rm not in rsi_cache:
                j = i if rm == mk.base else int(np.searchsorted(mk.ends[rm], np.datetime64(c_t), side="right")) - 1
                v = mk.rsi[rm][j] if j >= 0 else np.nan
                rsi_cache[rm] = round(float(v), 2) if np.isfinite(v) else None
            rsi = rsi_cache[rm]
            if rsi is None or not (rsi < spec.rsi_bull_max if direction == LR.BULL else rsi > spec.rsi_bear_min):
                continue
            sl, tg = legacy_stops(spec, price, direction)
            cands.append({"time": c_t, "order": order, "level": lv, "tf": suf, "direction": direction, "entry": price, "sl": sl, "target": tg,
                          "touch_bar": int(i)})
    day_bars = base.iloc[rows].reset_index(drop=True)
    touch = take_trades(cands, day_bars, spec, mk.symbol, cost)

    # ---------------- confirmation (gate) signals
    cm = confirm_tf(mk, spec)
    cf = mk.frames[cm]
    today_rows = mk.day_rows[cm].get(day)
    conf, sigs = [], []
    if today_rows is not None and len(today_rows):
        prev_days = [d for d in mk.days if d < day][-int(s["ctx_days"]):]
        first = min([mk.day_rows[cm][d][0] for d in prev_days if d in mk.day_rows[cm]] + [today_rows[0]])
        B = cf.iloc[first:today_rows[-1] + 1][["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)
        k0 = int(today_rows[0] - first)
        BH, BL, BC = (B[k].to_numpy(float) for k in ("high", "low", "close"))
        BE = (B["timestamp"] + pd.Timedelta(minutes=cm)).tolist()
        M = int(gate_s["max_armed_bars"])
        cache = {}

        def ev(j, a, t):
            key = (j, a, t)
            if key not in cache:
                others = [x for x in areas[j] if (round(min(x), 4), round(max(x), 4)) != (round(a[0], 4), round(a[1], 4))]
                cache[key] = LR.safe_evaluate(B.iloc[:t + 1], a, ctx, others, k0, s=gate_s)
            return cache[key]

        if ctx.get("ok"):
            for t in range(k0, len(B)):
                c_t = pd.Timestamp(BE[t])
                if (c_t.hour * 60 + c_t.minute) >= _hm(spec.last_entry):
                    break
                j = epoch_of(c_t)
                for order, a in enumerate(areas[j]):
                    if not (BC[t] > a[1] or BC[t] < a[0]):
                        continue
                    w0 = max(k0, t - M - 2)
                    if not ((BL[w0:t + 1] <= a[1]) & (BH[w0:t + 1] >= a[0])).any():
                        continue
                    r = ev(j, a, t)
                    if r.get("entry"):
                        lv = epochs[j][order][1]
                        sigs.append({"time": c_t, "order": order, "level": lv, "tf": epochs[j][order][0], "direction": r["side"],
                                     "entry": float(r["entry_price"]), "sl": float(r["sl"]), "target": float(r["target"]),
                                     "grade": r.get("grade"), "form": r.get("form"), "rr": r.get("rr"), "bar": t, "area": a})
        conf = take_trades(sigs, day_bars, spec, mk.symbol, cost)

        # ---------------- legacy trades चा gate निकाल
        BT = B["timestamp"].to_numpy("datetime64[ns]")
        for tr in touch:
            ts_i = np.datetime64(pd.Timestamp(TS.iat[tr["touch_bar"]]))
            t0 = max(k0, int(np.searchsorted(BT, ts_i, side="right")) - 1)
            w = min(len(B) - 1, t0 + M)
            a = gate_area(tr["level"])
            j = epoch_of(tr["time"])                                   # touch त्याच epoch च्या level वर ⇒ a हा areas[j] मध्येच
            kept_sig = [g for g in sigs if g["area"] == a and g["direction"] == tr["direction"] and t0 - M <= g["bar"] <= w]
            r = ev(j, a, w)
            code, reason, detail = verdict(r, t0 - M, w, bool(kept_sig), ctx, tr["direction"], a)
            sig_times = {pd.Timestamp(g["time"]) for g in kept_sig}
            taken = any(c["level"] == tr["level"] and c["direction"] == tr["direction"] and pd.Timestamp(c["time"]) in sig_times for c in conf)
            tr.update(gate_code=code, gate_reason=reason, gate_detail=detail, gate_kept_taken=bool(taken))
    else:
        for tr in touch:
            tr.update(gate_code="SKIPPED_GATE_ERROR", gate_reason=f"{LR.R_ERROR}: no {cm}m candles", gate_detail="", gate_kept_taken=False)
    return {"touch": touch, "conf": conf, "ctx": ctx, "n_levels": len(epochs[0]) if epochs else 0}


# ------------------------------------------------------------------------------------------------ run + tables
TRADE_COLS = ["bot", "symbol", "mode", "day", "period", "trend", "time", "level", "tf", "direction", "entry", "sl", "target", "exit_time",
              "exit", "exit_reason", "gross_pts", "cost_pts", "net_pts", "risk_pts", "r_net", "grade", "form", "rr", "gate_code", "gate_reason",
              "gate_detail", "gate_kept_taken"]


def replay(mk, spec, days, gate_s=None, s=None, cost=None, progress=None):
    """दिवसांची यादी ⇒ trades DataFrame (दोन्ही modes)."""
    rows = []
    for n, d in enumerate(days):
        out = replay_day(mk, spec, d, gate_s, s, cost)
        meta = {"bot": spec.name, "symbol": mk.symbol, "day": pd.Timestamp(d).normalize(), "period": period_of(mk.symbol, d),
                "trend": trend_bucket(out["ctx"])}
        rows += [{**meta, "mode": TOUCH, **t} for t in out["touch"]]
        rows += [{**meta, "mode": CONF, **t} for t in out["conf"]]
        if progress:
            progress(spec.name, mk.symbol, n + 1, len(days), d)
    df = pd.DataFrame(rows)
    for c in TRADE_COLS:
        if c not in df.columns:
            df[c] = None
    return df[TRADE_COLS]


def summary(trades):
    """bot × symbol × period × trend (+ "all") × mode ⇒ metrics (कालक्रमाने)."""
    out = []
    if trades is None or len(trades) == 0:
        return pd.DataFrame(columns=["bot", "symbol", "period", "trend", "mode", "n", "win_rate", "expectancy", "total", "max_dd", "profit_factor"])
    t = trades.sort_values(["time", "exit_time"])
    for (b, sym, per), g in t.groupby(["bot", "symbol", "period"], sort=False):
        for tr in ("all", "bull", "bear", "range", "no trend"):
            gg = g if tr == "all" else g[g["trend"] == tr]
            for mode in (TOUCH, CONF):
                out.append({"bot": b, "symbol": sym, "period": per, "trend": tr, "mode": mode, **metrics(gg[gg["mode"] == mode]["net_pts"])})
    return pd.DataFrame(out)


def rejection_summary(trades):
    """legacy trades: gate निकालानुसार गट ⇒ n, wins, net total, expectancy. 'saved' = −total (धन ⇒ ते trades टाळल्याने फायदा)."""
    t = trades[trades["mode"] == TOUCH] if trades is not None and len(trades) else pd.DataFrame(columns=TRADE_COLS)
    out = []
    for (b, sym, per, code), g in t.groupby(["bot", "symbol", "period", "gate_code"]):
        m = metrics(g.sort_values("time")["net_pts"])
        out.append({"bot": b, "symbol": sym, "period": per, "gate_code": code, "label": CATEGORY_LABEL.get(code, code), "n": m["n"],
                    "wins": int((g["net_pts"] > 0).sum()), "net_total": m["total"], "expectancy": m["expectancy"],
                    "saved": None if code == "KEPT" else -m["total"]})                     # kept ⇒ टाळलेला नाही
    return pd.DataFrame(out, columns=["bot", "symbol", "period", "gate_code", "label", "n", "wins", "net_total", "expectancy", "saved"])


# ------------------------------------------------------------------------------------------------ markdown
def _f(x, nd=1, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if isinstance(x, float) and np.isinf(x):
        return "∞"
    return f"{x * 100:.0f}%" if pct else f"{x:,.{nd}f}"


def cell_note(n_touch, n_conf, min_n=MIN_N):
    return "" if min(n_touch, n_conf) >= min_n else f"n < {min_n} — no conclusion"


def conclusion_lines(summ, min_n=MIN_N):
    """फक्त दोन्ही modes n ≥ min_n असलेल्या cells वर तथ्यात्मक तुलना (बाकी "no conclusion")."""
    out = []
    if summ is None or len(summ) == 0:
        return out
    for (b, sym, per, tr), g in summ.groupby(["bot", "symbol", "period", "trend"], sort=False):
        a = g[g["mode"] == TOUCH].iloc[0]
        c = g[g["mode"] == CONF].iloc[0]
        if min(a["n"], c["n"]) < min_n:
            continue
        d = c["expectancy"] - a["expectancy"]
        out.append(f"- {b} · {sym} · {per} · {tr}: net expectancy {_f(c['expectancy'], 2)} (confirmation, n {c['n']}) vs "
                   f"{_f(a['expectancy'], 2)} (touch, n {a['n']}) ⇒ {'+' if d >= 0 else ''}{d:,.2f} pts/trade; max DD {_f(c['max_dd'])} vs "
                   f"{_f(a['max_dd'])}; PF {_f(c['profit_factor'], 2)} vs {_f(a['profit_factor'], 2)}.")
    return out


def render_report(trades, meta, sample=True, min_n=MIN_N, per_reason=None):
    """docs/reports/level_bots_confirmation.md चा मजकूर (English)."""
    per_reason = int(per_reason or DEFAULTS["list_per_reason"])
    summ, rej = summary(trades), rejection_summary(trades)
    L = ["# Level bots — touch vs confirmation replay (L6)", ""]
    if sample:
        L += ["> **SAMPLE — full run pending.** Small slice only, to review the template. Every cell here is n < 30 ⇒ no conclusion.", ""]
    L += [f"Generated {meta.get('generated', '')} by `{meta.get('command', '')}`.", "",
          f"Data: {meta.get('data', '')}", "", "## How this replay works", ""]
    L += [f"- {x}" for x in meta.get("assumptions", [])]
    L += ["", f"Cells with n < {min_n} carry **no conclusion** (numbers shown for reference only).", ""]
    L += ["## Conclusions (cells with n ≥ %d in both modes)" % min_n, ""]
    cl = conclusion_lines(summ, min_n)
    L += cl if cl else ["- None — no cell reaches n ≥ %d in both modes." % min_n]
    L += [""]
    if trades is None or len(trades) == 0:
        return "\n".join(L + ["(no trades)"]) + "\n"
    for (b, sym), _g in trades.groupby(["bot", "symbol"], sort=False):
        L += [f"## {b} — {sym}", "", "### Results by Daily trend context (net of costs, points)", "",
              "| period | trend | mode | n | win rate | net expectancy | net total | max DD | profit factor | note |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
        sb = summ[(summ["bot"] == b) & (summ["symbol"] == sym)]
        for (per, tr), g in sb.groupby(["period", "trend"], sort=False):
            nt, nc = int(g[g["mode"] == TOUCH]["n"].iloc[0]), int(g[g["mode"] == CONF]["n"].iloc[0])
            if nt == 0 and nc == 0 and tr != "all":
                continue
            note = cell_note(nt, nc, min_n)
            for _, r in g.iterrows():
                L.append(f"| {per} | {tr} | {r['mode']} | {r['n']} | {_f(r['win_rate'], pct=True)} | {_f(r['expectancy'], 2)} | {_f(r['total'])} | "
                         f"{_f(r['max_dd'])} | {_f(r['profit_factor'], 2)} | {note} |")
        tb = trades[(trades["bot"] == b) & (trades["symbol"] == sym) & (trades["mode"] == TOUCH)]
        kept = tb[tb["gate_code"] == "KEPT"]
        n_taken = int(kept["gate_kept_taken"].fillna(False).astype(bool).sum())
        L += ["", "### Legacy (touch) trades the gate rejects — grouped by reason", "",
              f"Legacy trades: {len(tb)} · kept by the gate: {len(kept)} (taken by the confirmation arm: {n_taken}) · rejected: {len(tb) - len(kept)}.",
              "", "`saved` = −(net total of those legacy trades): positive ⇒ skipping them saved points, negative ⇒ skipping them cost points.", "",
              "| period | gate verdict | n | wins | net total | net expectancy | saved | note |", "|---|---|---:|---:|---:|---:|---:|---|"]
        rb = rej[(rej["bot"] == b) & (rej["symbol"] == sym)]
        for _, r in rb.sort_values(["period", "n"], ascending=[True, False]).iterrows():
            L.append(f"| {r['period']} | {r['label']} | {r['n']} | {r['wins']} | {_f(r['net_total'])} | {_f(r['expectancy'], 2)} | "
                     f"{_f(r['saved'])} | {'' if r['n'] >= min_n else f'n < {min_n}'} |")
        tt = trades[(trades["bot"] == b) & (trades["symbol"] == sym) & (trades["mode"] == TOUCH) & (trades["gate_code"] != "KEPT")]
        L += ["", f"### Rejected legacy trades (first {per_reason} per reason; full list in `{meta.get('csv', 'trades CSV')}`)", ""]
        for code, g in tt.sort_values("time").groupby("gate_code", sort=False):
            L += [f"**{CATEGORY_LABEL.get(code, code)}** ({len(g)})", "", "| day | time | level | side | trend | exit | net pts | detail |",
                  "|---|---|---:|---|---|---|---:|---|"]
            for _, r in g.head(per_reason).iterrows():
                det = r["gate_detail"] or (r["gate_reason"] if code not in ("SKIPPED_GATE_NOT_AT_AREA", "GATE_OTHER_SIDE") else "")
                L.append(f"| {pd.Timestamp(r['day']).date()} | {pd.Timestamp(r['time']):%H:%M} | {r['level']:,.2f} | "
                         f"{'long' if r['direction'] == LR.BULL else 'short'} | {r['trend']} | {r['exit_reason']} | {r['net_pts']:,.1f} | {det} |")
            L.append("")
    return "\n".join(L) + "\n"
