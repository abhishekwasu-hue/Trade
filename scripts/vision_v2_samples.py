"""scripts/vision_v2_samples.py — signal_check_v2 चे नमुने: शेवटचे N खरे signals (vision.db) पुन्हा chart v2 + v2 prompt ने तपासणे.
**फक्त पाहणी — trade नाही, vision_signals ला हात नाही** (नवीन row / status बदल नाही; खर्च `vision_usage` मध्ये task "sample" म्हणून नोंद).

    python3 scripts/vision_v2_samples.py               # 3 नमुने (≈ $0.01 / नमुना), JSON + code verdict छापतो, chart Telegram वर
    python3 scripts/vision_v2_samples.py --n 3 --no-telegram
    python3 scripts/vision_v2_samples.py --no-vision   # फक्त chart v2 + signal text (खर्च 0)
    python3 scripts/vision_v2_samples.py --historical  # तुम्ही पाहिलेले तेच 3 नमुने (2021 IS, data/nifty50_1min.parquet) — त्यांचं JSON
Exit code 2 ⇒ model असूनही एकही वैध JSON नाही (deploy block auto_veto चालू करत नाही).

🎓 Signals कमी असतील तर बाकीचे शेवटच्या 1m candle वर TEST signal (dry-run सारखे). Chart signal च्या क्षणापर्यंतच कापलेला (no-lookahead).
Daily / monthly budget तपासणी तीच (`_budget_ok`).
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from vision import chart as CH  # noqa: E402
from vision import config as VC  # noqa: E402
from vision import images as IM  # noqa: E402
from vision import signal_audit as SA  # noqa: E402
from vision import store as VS  # noqa: E402
from vision import worker as VW  # noqa: E402


# तुम्हाला दाखवलेले 3 नमुने (2021 IS data): (signal वेळ, दिशा, role, level, spot)
HISTORICAL = [("2021-07-20 10:31:00", "BULLISH", "SUPPORT", 15636.3, 15640.85),
              ("2021-07-12 13:11:00", "BEARISH", "RESISTANCE", 15730.55, 15729.3),
              ("2021-07-02 10:01:00", "BULLISH", "SUPPORT", 15667.65, 15670.7)]
HIST_EXPIRIES = ["2021-07-01", "2021-07-08", "2021-07-15", "2021-07-22", "2021-07-29"]


def historical():
    """[(sig, 1m frame)] — signal पर्यंतचाच data render मध्ये कापला जातो (cut_1m)."""
    df = CH.norm_1m(pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet")))
    dd = df.groupby(df.timestamp.dt.normalize()).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                                     n=("close", "size"))
    dd = dd[dd.n >= 200].reset_index().rename(columns={"index": "timestamp"})
    dd = dd.rename(columns={dd.columns[0]: "timestamp"})
    out = []
    for k, (ts, d, role, lv, spot) in enumerate(HISTORICAL, 1):
        t = pd.Timestamp(ts)
        hist = df[(df.timestamp >= t - pd.Timedelta(days=21)) & (df.timestamp < t + pd.Timedelta(days=1))]
        daily = dd[(dd.timestamp >= t - pd.Timedelta(days=180)) & (dd.timestamp < t.normalize())]   # आधीचे पूर्ण दिवस
        out.append(({"signal_id": f"hist{k}", "bot": "dynamic_sr_instant", "bot_label": f"🧪 नमुना {k} (2021 IS, trade नाही)", "symbol": "NIFTY",
                     "direction": d, "role": role, "level": lv, "setup_tf": "5M", "signal_ts": t, "spot": spot, "tags": {"breakout_entry": False},
                     "expiries": HIST_EXPIRIES}, hist, daily))
    return out


def candidates(n, m1, symbol="NIFTY"):
    rows = [r for r in reversed(VS.list_signals()) if r["symbol"] == symbol and r["bot"] in VC.BOTS and r["level"] is not None][:n]
    out = []
    for r in rows:
        setup = json.loads(r.get("setup_json") or "{}")
        out.append({**r, "bot_label": setup.get("bot_label"), "tags": setup.get("tags") or {}, "invalidation": setup.get("invalidation"),
                    "last_bar": setup.get("last_bar"), "signal_ts": pd.Timestamp(r["signal_ts"])})
    d = CH.norm_1m(m1)
    k = 0
    while len(out) < n and len(d) > 40:                                  # कमी असतील तर TEST signals (शेवटच्या candles वर)
        cut = d.iloc[: len(d) - 15 * k]
        tail = cut.tail(30)
        close = float(tail["close"].iloc[-1])
        lo, hi = float(tail["low"].min()), float(tail["high"].max())
        bull = close - lo <= hi - close
        out.append({"signal_id": f"sample{k}", "bot": "sample", "bot_label": "🧪 V2 sample (TEST, trade नाही)", "symbol": symbol,
                    "direction": "BULLISH" if bull else "BEARISH", "level": round(lo if bull else hi, 1), "role": "SUPPORT" if bull else "RESISTANCE",
                    "setup_tf": "5M", "spot": close, "tags": {"test": True}, "signal_ts": cut["timestamp"].iloc[-1] + pd.Timedelta(minutes=1)})
        k += 1
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--no-vision", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--historical", action="store_true", help="तुम्हाला दाखवलेले तेच 3 नमुने (2021 IS)")
    a = ap.parse_args(argv)
    if a.historical:
        pairs = historical()
    else:
        m1, d1 = VW.default_fetch(a.symbol, True)
        if m1 is None or len(m1) == 0:
            print("❌ 1m candles मिळाले नाहीत (Upstox token?)")
            return 1
        exp = VW.fetch_expiries(a.symbol)
        pairs = [({**s_, "expiries": exp}, m1, d1) for s_ in candidates(a.n, m1, a.symbol)]
    s, g = VC.load("dynamic_sr_instant"), VC.load("_global")
    model = None if a.no_vision else VC.env_model("signal")
    out_dir = os.path.join(IM.base_dir(), "samples_v2")
    os.makedirs(out_dir, exist_ok=True)
    valid, total, summary = 0, 0.0, []
    expect = {1: "disagree", 2: "disagree", 3: "gray"} if a.historical else {}
    for i, (sig, frame, daily) in enumerate(pairs, 1):
        sig["ctx_settings"] = VC.ctx_settings("dynamic_sr_instant")
        png, meta = CH.render(frame, sig, daily)
        sig["ctx"] = meta.get("ctx")
        print(f"\n===== नमुना {i}: {sig['bot']} {sig['symbol']} {sig['direction']} L{sig['level']} @ {sig['signal_ts']} =====")
        if png is None:
            print(f"chart नाही: {meta.get('error')}")
            continue
        path = os.path.join(out_dir, f"sample_{i}_{pd.Timestamp(sig['signal_ts']):%Y%m%d_%H%M}.png")
        with open(path, "wb") as f:
            f.write(png)
        print(f"chart: {path}\n--- signal text ---\n{SA.signal_text(sig)}")
        res = None
        if model and VC.api_key_present() and VW._budget_ok(g, model)[0]:
            client = SA.make_client(int(s["vision_timeout_sec"]))
            res = SA.audit(client, png, sig, model, second_below=0.0, effort=VC.env_effort("signal"), thinking=VC.env_thinking("signal"),
                           on_usage=lambda u, c: VS.add_usage("sample", model, u, c, None),
                           disagree_rules=s["v2_disagree_rules"], gray_rules=s["v2_gray_rules"])
            valid += 1 if res.get("audits") else 0
            print("--- vision JSON (v2) ---")
            print(json.dumps((res.get("audits") or [None])[0], ensure_ascii=False, indent=1))
            print(f"code verdict: {res['verdict']} · नियम: {(res.get('rule_hits') or [None])[0]} · code तथ्यं: "
                  f"{((res.get('audits') or [{}])[0] or {}).get('code_overrides')} · error: {res.get('error')} · "
                  f"${res.get('cost_usd', 0):.4f} · tokens {res.get('usage')}")
            total += float(res.get("cost_usd") or 0)
            own = ((res.get("audits") or [{}])[0] or {}).get("verdict")
            summary.append(f"नमुना {i}: vision {own} ⇒ अंतिम {res['verdict']}" + (f" (तुमचं अपेक्षित {expect[i]})" if i in expect else ""))
        else:
            print("(vision call नाही — --no-vision / model / key / budget)")
        if not a.no_telegram:
            cap = VW.caption({**sig, "signal_ts": str(sig["signal_ts"])}, res or {"verdict": "unavailable", "error": "sample — vision नाही"},
                             "auto_veto").replace("Vision V0 — फक्त माहिती", "🧪 Vision V2 नमुना — trade नाही")
            cap = cap.replace("Bot ने नेहमीप्रमाणे निर्णय घेतला — vision चा trade वर परिणाम नाही (V0).", "")
            from vision import tg as TG
            TG.send_photo(png, cap)
    if summary:
        print("\n===== सारांश =====\n" + "\n".join(summary) + f"\nएकूण खर्च ${total:.4f}")
    if not a.no_vision and not valid:                                    # model / key नसले तरी exit 2 (review S7)                                              # vision चालत नाही ⇒ auto_veto चालू करू नये (सगळे signals skip होतील)
        print("❌ एकाही नमुन्याला वैध v2 JSON मिळाला नाही — key / model / आजचं budget संपलं / network / max_tokens (VISION_SIGNAL_THINKING?) तपासा")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
