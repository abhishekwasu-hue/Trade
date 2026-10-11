#!/usr/bin/env python3
"""scripts/level_bots_replay.py — L6: level bots replay, legacy "touch" वि. "confirmation" gate (level_bots_replay.py चा docstring बघा).

फक्त local data (network / DB / order नाही):
  • NIFTY 1-मिनिट  data/nifty50_1min.parquet — elliott.data_policy.load_parquet (IS / VAL फक्त; HOLDOUT कधीच load नाही)
  • BANKNIFTY      <trade-data>/banknifty/BANKNIFTY_15M.csv.gz (+ Daily CSVs trend साठी) — फक्त 15M SRv2 (5M bots ना 5M data नाही)
  • MCX            <trade-data>/major_levels_candles/{GOLD,SILVER,COPPER}_30m.csv — फक्त MCX bot (30M levels, confirm 30m: 15m data नाही)
निकाल: <out>/trades.csv, summary.csv, rejections.csv आणि markdown अहवाल (--report).

    python3 scripts/level_bots_replay.py                                   # पूर्ण run (सगळे symbols / bots, क्रमाने)
    python3 scripts/level_bots_replay.py --symbols NIFTY --start 2021-12-15 --max-days 20 --sample      # छोटा नमुना
"""
import argparse
import datetime as dt
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import level_bots_replay as RP  # noqa: E402
from elliott import data_policy as DP  # noqa: E402

MCX_SYMBOLS = ("GOLD", "SILVER", "COPPER")


def default_trade_data():
    return os.environ.get("TRADE_DATA_DIR") or os.path.join(os.path.dirname(ROOT), "trade-data")


def load_nifty(path):
    """IS / VAL फक्त (data_policy filter + guard)."""
    df = DP.load_parquet(path, purpose="research")
    RP.assert_research_only(df, "NIFTY")
    return RP.prepare_market("NIFTY", df, 1, "09:15")


def load_banknifty(base_dir):
    d = os.path.join(base_dir, "banknifty")
    m15 = pd.read_csv(os.path.join(d, "BANKNIFTY_15M.csv.gz"))
    parts = []
    p_old = os.path.join(d, "BANKNIFTY_daily_2015_2024-03.csv")
    if os.path.exists(p_old):
        parts.append(pd.read_csv(p_old).rename(columns={"date": "timestamp"}))
    p_new = os.path.join(d, "BANKNIFTY_D.csv.gz")
    if os.path.exists(p_new):
        parts.append(pd.read_csv(p_new))
    for x in parts:                                                       # दोन files, दोन तारीख-स्वरूपे ⇒ वेगवेगळे parse
        x["timestamp"] = pd.to_datetime(x["timestamp"], format="mixed").dt.normalize()
    daily = pd.concat(parts, ignore_index=True)[["timestamp", "open", "high", "low", "close"]] if parts else None
    return RP.prepare_market("BANKNIFTY", m15, 15, "09:15", daily_df=daily)


def load_mcx(base_dir, symbol):
    df = pd.read_csv(os.path.join(base_dir, "major_levels_candles", f"{symbol}_30m.csv"))
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return RP.prepare_market(symbol, df, 30, "09:00", exchange="MCX")


def per_symbol(arg):
    """"2021-12-17" (सगळ्या symbols ना) किंवा "NIFTY=2021-12-17,GOLD=2026-09-01" ⇒ (default, {SYM: date})."""
    if not arg:
        return None, {}
    default, out = None, {}
    for part in str(arg).split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().upper()] = v.strip()
        elif part.strip():
            default = part.strip()
    return default, out


def assumptions(level_refresh):
    from bots_common import level_gate_bot as LGB
    from bots_common import level_reaction as LR
    g = LR.DEFAULTS
    costs = {s: round(RP.cost_points(s, 0.0 if RP.COST_DEFAULTS[s]["kind"] == "option" else p), 2)
             for s, p in (("NIFTY", 0), ("BANKNIFTY", 0), ("GOLD", 150000.0), ("SILVER", 230000.0), ("COPPER", 1400.0))}
    return [
        "Same days, same levels, same cost model for both modes. Levels = the bots' Dynamic S/R (`sr_dynamic.compute_dynamic_sr`, refresh "
        f"parameters and lookbacks), recomputed at the session open and every {level_refresh} min from closed bars only (no lookahead). "
        "Level memory is not replayed.",
        "**Touch (legacy)** = the bots' own functions imported from the bot files (`check_level_crossed`, `determine_direction_with_hysteresis`), "
        "default settings (RSI thresholds, max hits per level and role, cooldowns, one position at a time, no new entry from 14:45, EOD). "
        "PCR gate skipped (no PCR history). Exits = the bots' naked spot-% SL / target (MCX: settings points).",
        "**Confirmation** = `level_reaction.evaluate` on closed confirmation-TF candles, exactly as the live cycle: an entry only on the commitment "
        f"candle itself. Trend = one `decision3.daily.fold` per symbol + `state_at` per day (yesterday's close). Gate defaults: min R:R {g['min_rr']:g}, "
        f"max armed bars {g['max_armed_bars']}, area = level ± {LGB.AREA_PAD_PCT:g}% / 2. RSI / PCR gates off, no breakout. "
        "Exits = the gate's structural SL (beyond the area's far edge + buffer) / target (next opposite area).",
        "Exit simulation on the next base bars: SL before target when both are inside one bar (pessimistic); a gap beyond SL fills at the open; "
        "EOD closes at the bar close. Index futures volume is not available for IS / VAL ⇒ volume NA ⇒ grade ≤ B (as live with volume NA).",
        "P&L is in **index / futures points** — intraday option premium history is not available. Cost per round trip (points) from "
        f"`charges.py` (Upstox rates): 1 lot naked ITM option buy (premium / lot / delta / slippage in `COST_DEFAULTS`) ⇒ {costs}.",
        "NIFTY: IS / VAL per `elliott.data_policy`; the HOLDOUT is never loaded (guard raises). BANKNIFTY: only 15M candles exist (≈ 3 months, "
        "not sealed, but the calendar overlaps the gate's NIFTY design window ⇒ illustration, not validation); touch and exits on 15M bars; "
        "only 15M SRv2. MCX: 30m candles only (≈ 4 months, no volume); confirmation on 30m (live: 15m); Daily trend from ≤ 4 months of Daily bars "
        "(live: ~10 years) ⇒ trend often UNKNOWN; MCX extra filters (cascade, supertrend, structure SL, min-hold) not replayed.",
        "Trend split = the gate's Daily trend that day (UP ⇒ bull, DOWN ⇒ bear, RANGE ⇒ range, NEUTRAL / UNKNOWN ⇒ no trend). A day whose trend "
        "is UP / DOWN but where the gate blocks new entries (origin broken / at risk, parent correction A1) stays in bull / bear; its legacy "
        "trades show the verdict \"Daily trend unclear / entries blocked\".",
        "Rejected legacy trades: for each legacy trade, the gate's verdict on the same area in the window max armed bars before → after the touch "
        "(the same visit); the Daily trend check comes first, as in the gate. "
        "\"Kept\" = the gate confirmed the same area and side in that window (whether or not the confirmation arm could take it).",
    ]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NIFTY,BANKNIFTY," + ",".join(MCX_SYMBOLS))
    ap.add_argument("--bots", default="instant,srv2,classic,mcx")
    ap.add_argument("--start", default=None, help='"YYYY-MM-DD" किंवा "NIFTY=YYYY-MM-DD,GOLD=YYYY-MM-DD"')
    ap.add_argument("--end", default=None, help="--start सारखेच")
    ap.add_argument("--max-days", type=int, default=None, help="प्रत्येक symbol चे पहिले इतके दिवस (नमुना)")
    ap.add_argument("--nifty-path", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--trade-data", default=default_trade_data())
    ap.add_argument("--level-refresh-min", type=int, default=RP.DEFAULTS["level_refresh_min"])
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "research", "level_bots_replay"))
    ap.add_argument("--report", default=os.path.join(ROOT, "docs", "reports", "level_bots_confirmation.md"))
    ap.add_argument("--sample", action="store_true", help='अहवालावर "SAMPLE — full run pending"')
    a = ap.parse_args(argv)
    t0 = time.time()
    specs = RP.bot_specs()
    bots = [b.strip() for b in a.bots.split(",") if b.strip() in specs]
    s = {"level_refresh_min": a.level_refresh_min}
    frames, data_lines = [], []
    (s0, s_map), (e0, e_map) = per_symbol(a.start), per_symbol(a.end)
    for sym in [x.strip().upper() for x in a.symbols.split(",") if x.strip()]:
        start, end = s_map.get(sym, s0), e_map.get(sym, e0)
        if sym in RP.SEALED and (start or end):
            DP.check_range(start or DP.IS_START, end or DP.VAL_END, purpose="research")      # HOLDOUT ला छेदणारी श्रेणी ⇒ HoldoutError
        try:
            mk = (load_nifty(a.nifty_path) if sym == "NIFTY" else load_banknifty(a.trade_data) if sym == "BANKNIFTY"
                  else load_mcx(a.trade_data, sym) if sym in MCX_SYMBOLS else None)
        except (OSError, ValueError, KeyError) as exc:
            print(f"⚠️ {sym}: data नाही ({type(exc).__name__}: {exc}) — वगळले", flush=True)
            continue
        if mk is None:
            print(f"⚠️ {sym}: loader नाही — वगळले", flush=True)
            continue
        days = [d for d in mk.days if (start is None or d >= pd.Timestamp(start)) and (end is None or d <= pd.Timestamp(end))]
        if sym in RP.SEALED:
            days = [d for d in days if DP.allowed(d, "research")]
        if a.max_days:
            days = days[:a.max_days]
        if not days:
            continue
        data_lines.append(f"{sym} {mk.base}m bars, replay {days[0].date()} → {days[-1].date()} ({len(days)} days)")
        print(f"{sym}: {len(days)} दिवस ({time.time() - t0:.0f}s)", flush=True)
        for b in bots:
            spec = specs[b]
            if not RP.supported(mk, spec):
                continue
            df = RP.replay(mk, spec, days, s=s, progress=lambda n_, sy, i, k, d: (i % 100 == 0 or i == k) and print(
                f"  {n_}/{sy}: {i}/{k} {pd.Timestamp(d):%Y-%m-%d} ({time.time() - t0:.0f}s)", flush=True))
            frames.append(df)
    trades = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) else pd.DataFrame(columns=RP.TRADE_COLS)
    os.makedirs(a.out, exist_ok=True)
    trades.to_csv(os.path.join(a.out, "trades.csv"), index=False)
    RP.summary(trades).to_csv(os.path.join(a.out, "summary.csv"), index=False)
    RP.rejection_summary(trades).to_csv(os.path.join(a.out, "rejections.csv"), index=False)
    cmd = "python3 scripts/level_bots_replay.py " + " ".join(argv if argv is not None else sys.argv[1:])
    meta = {"generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "command": cmd.strip(), "data": "; ".join(data_lines),
            "assumptions": assumptions(a.level_refresh_min), "csv": os.path.relpath(os.path.join(a.out, "trades.csv"), ROOT)}
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    with open(a.report, "w", encoding="utf-8") as f:
        f.write(RP.render_report(trades, meta, sample=a.sample))
    print(f"trades {len(trades)} · CSV {a.out} · अहवाल {a.report} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
