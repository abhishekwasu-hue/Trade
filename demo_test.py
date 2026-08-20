"""
demo_test.py
--------------
Synthetic data वापरून संपूर्ण pipeline (4 strategies + orchestrator) end-to-end
चालतंय का हे तपासणारी script. Real Upstox data आल्यावर snapshot builder फक्त
बदलायचा — बाकी सगळं तसंच राहील.

Run: python demo_test.py
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pytz

from loader import build_orchestrator
from strategies.base import MarketSnapshot

IST = pytz.timezone("Asia/Kolkata")


def make_synthetic_futures_ohlcv(n=90, seed=42):
    rng = np.random.default_rng(seed)
    base = 24500
    closes = base + np.cumsum(rng.normal(0, 8, n))
    df = pd.DataFrame({
        "open": closes + rng.normal(0, 2, n),
        "high": closes + abs(rng.normal(3, 2, n)),
        "low": closes - abs(rng.normal(3, 2, n)),
        "close": closes,
        "volume": rng.integers(50000, 150000, n).astype(float),
    })
    # force a volume spike + breakout on the last candle (BB squeeze test साठी)
    df.loc[n - 1, "volume"] = df["volume"].iloc[:-1].mean() * 2.2
    df.loc[n - 1, "close"] = df["close"].iloc[-2] + 40  # sharp breakout up

    # simple BB (20-period)
    period = 20
    df["bb_middle"] = df["close"].rolling(period).mean()
    df["bb_std"] = df["close"].rolling(period).std()
    df["bb_upper"] = df["bb_middle"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_middle"] - 2 * df["bb_std"]
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

    # simple ATR (14-period, approx using high-low)
    df["atr"] = (df["high"] - df["low"]).rolling(14).mean()

    # simple VWAP proxy (cumulative for demo)
    df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vwap_std"] = (df["close"] - df["vwap"]).rolling(20).std().fillna(5)

    return df.dropna().reset_index(drop=True)


def make_synthetic_options_chain():
    strikes = [24400, 24450, 24500, 24550, 24600]
    rows = []
    for k in strikes:
        rows.append({"strike": k, "option_type": "CE", "oi": 120000, "oi_prev": 150000, "ltp": 80})  # call unwinding
        rows.append({"strike": k, "option_type": "PE", "oi": 180000, "oi_prev": 140000, "ltp": 60})  # put buildup
    return pd.DataFrame(rows)


def make_synthetic_structure_data():
    return {
        "swept_high": False,
        "swept_low": True,
        "bos_confirmed": True,
        "choch_confirmed": False,
        "bos_direction": "LONG",
        "fvg_zones": [
            {"start": 24510, "end": 24525, "direction": "LONG", "candle_idx": 55},
        ],
    }


def main():
    orch = build_orchestrator("config.yaml")
    print("Loaded strategies:", [s.strategy_id for s in orch.strategies])

    snapshot = MarketSnapshot(
        timestamp=datetime.now(IST),
        futures_ohlcv=make_synthetic_futures_ohlcv(),
        options_chain=make_synthetic_options_chain(),
        structure_data=make_synthetic_structure_data(),
    )

    signals = orch.run_cycle(snapshot)

    print("\n=== RAW per-strategy check (debug) ===")
    for strat in orch.strategies:
        r = strat.check_gates(snapshot)
        print(f"[{r.strategy_id}] dir={r.direction.value} conf={r.confidence:.2f} | {r.reason}")

    print("\n=== FINAL APPROVED SIGNALS (after orchestrator gates) ===")
    if not signals:
        print("No approved signals this cycle.")
    for s in signals:
        print(f"[{s.strategy_id}] {s.direction.value} conf={s.confidence:.2f} "
              f"entry={s.entry_price} sl={s.stop_loss} target={s.target}")
        print(f"   reason: {s.reason}")


if __name__ == "__main__":
    main()
