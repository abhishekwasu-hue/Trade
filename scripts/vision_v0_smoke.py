"""scripts/vision_v0_smoke.py — Vision V0 ची end-to-end तपासणी VPS वर (खोटा TEST signal; **कोणताही order नाही**, bot ला हात नाही).

    python3 scripts/vision_v0_smoke.py --no-vision     # chart + Telegram फक्त (API call नाही, खर्च 0)
    python3 scripts/vision_v0_smoke.py                 # + 1 vision call (≈ $0.005–0.01) — token वापर आणि खर्च छापतो

🎓 शेवटच्या उपलब्ध 1m candle वर (सकाळी 08:00–09:00 म्हणजे कालचा 15:2x) एक TEST signal: NIFTY, शेवटच्या 30 bars च्या low/high पैकी
जवळचा level (OHLC वरून, image वरून नाही). Row `bot = vision_smoke` नावाने नोंदवला जातो (खऱ्या bots च्या आकड्यांत मिसळत नाही).
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from vision import chart as CH  # noqa: E402
from vision import store as VS  # noqa: E402
from vision import worker as VW  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--no-vision", action="store_true", help="vision API call नाही (फक्त chart + Telegram)")
    p.add_argument("--symbol", default="NIFTY")
    p.add_argument("--bar-close", action="store_true", help="--sample सोबत: live प्रमाणे signal bar बंद झाल्यावर (+ drift guard)")
    p.add_argument("--no-telegram", action="store_true", help="--sample सोबत: Telegram नाही")
    p.add_argument("--sample", action="store_true",
                   help="तुम्हाला दाखवलेले 3 नमुने (2021 IS) खऱ्या vision call सह: JSON + code verdict + खर्च (trade नाही, vision_signals ला हात नाही)")
    a = p.parse_args(argv)
    if a.sample:
        import importlib.util
        spec = importlib.util.spec_from_file_location("vision_v2_samples", os.path.join(ROOT, "scripts", "vision_v2_samples.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.main(["--historical"] + (["--no-vision"] if a.no_vision else []) + (["--bar-close"] if a.bar_close else [])
                        + (["--no-telegram"] if a.no_telegram else []))
    m1, _ = VW.default_fetch(a.symbol, False)
    if m1 is None or len(m1) == 0:
        print("❌ 1m candles मिळाले नाहीत (Upstox token?)")
        return 1
    d = CH.norm_1m(m1)
    last = d["timestamp"].iloc[-1]
    tail = d.tail(30)
    close = float(tail["close"].iloc[-1])
    lo, hi = float(tail["low"].min()), float(tail["high"].max())
    bull = close - lo <= hi - close
    level = round(lo if bull else hi, 1)
    sig_ts = last + pd.Timedelta(minutes=1)
    if a.no_vision:
        os.environ.pop("VISION_SIGNAL_MODEL", None)
    sid = VS.insert_signal({"bot": "vision_smoke", "symbol": a.symbol, "trading_mode": "PAPER", "mode": "notify", "signal_ts": sig_ts,
                            "direction": "BULLISH" if bull else "BEARISH", "level": level, "role": "SUPPORT" if bull else "RESISTANCE",
                            "setup_tf": "5M", "spot": close, "algo_decision": "TEST",
                            "setup": {"bot_label": "TEST signal (smoke — order नाही)", "tags": {"test": True}}})
    row = VS.claim_one(sid)                                             # फक्त TEST row — खऱ्या bots च्या rows ला हात नाही
    if row is None:
        print("❌ TEST row claim झाली नाही")
        return 1
    res = VW.process_row(row, data_cache={(a.symbol, True): (m1, None)}, wait_for_bar=False)
    r = VS.get_signal(sid)
    print(f"TEST signal {sid}: {r['direction']} level {level} @ {sig_ts:%d %b %H:%M} → verdict {r['verdict']} "
          f"(confidence {r['confidence']}), खर्च ${r['cost_usd'] or 0:.4f}, {r['latency_ms'] or 0} ms, Telegram {'✅' if r['notified'] else '❌'}, "
          f"image {r['image_path']}")
    if res.get("error"):
        print("ℹ️ कारण:", res["error"])
    u = (res.get("usage") or {})
    if u:
        print(f"tokens: input {u.get('input_tokens', 0):,} · cache-read {u.get('cache_read', 0):,} · cache-write {u.get('cache_write', 0):,} · "
              f"output {u.get('output_tokens', 0):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
