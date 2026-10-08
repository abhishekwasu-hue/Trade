"""scripts/vision_dryrun.py — Vision V1 चा end-to-end dry-run (G-V1). **खोटा signal, कोणताही order नाही, bot ला हात नाही.**

    python3 scripts/vision_dryrun.py                          # veto_then_confirm, vision सह (≈ $0.01), 3 मिनिटांची मुदत
    python3 scripts/vision_dryrun.py --no-vision              # vision शिवाय ("unavailable" ⇒ तुम्हाला विचारतो), खर्च 0
    python3 scripts/vision_dryrun.py --drift                  # approve नंतर drift guard चा नकार दाखवायला (spot मुद्दाम दूर)
    python3 scripts/vision_dryrun.py --mode auto_veto         # बटणांशिवाय (vision चा निर्णय)

🎓 पायऱ्या:
  1. शेवटच्या 1m candle वर TEST signal (bot = vision_dryrun) ⇒ chart (`_sent.png`) ⇒ vision ⇒ निर्णय.
  2. PENDING_HUMAN ⇒ Telegram वर ✅ / ❌ बटणं. Telegram service (`vision.telegram_bot`) चालू नसेल तर हा script स्वतः getUpdates वाचतो.
  3. उत्तर / timeout ⇒ APPROVED / REJECTED ⇒ drift guard (ताजा spot; `--drift` ⇒ मुद्दाम दूर) ⇒ EXECUTED (dry) / DRIFT_REJECTED / SHADOWED (dry).
  4. Telegram वर "🧪 DRY-RUN निकाल — order नाही". तिन्ही मार्ग (approve, reject, timeout) दाखवायला तीनदा चालवा.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from vision import chart as CH  # noqa: E402
from vision import decide as VD  # noqa: E402
from vision import store as VS  # noqa: E402
from vision import tg as TG  # noqa: E402
from vision import worker as VW  # noqa: E402

BOT = "vision_dryrun"


def make_signal(m1, mode, symbol="NIFTY"):
    d = CH.norm_1m(m1)
    last = d["timestamp"].iloc[-1]
    tail = d.tail(30)
    close = float(tail["close"].iloc[-1])
    lo, hi = float(tail["low"].min()), float(tail["high"].max())
    bull = close - lo <= hi - close
    return VS.insert_signal({"bot": BOT, "symbol": symbol, "trading_mode": "PAPER", "mode": mode, "signal_ts": last + pd.Timedelta(minutes=1),
                             "direction": "BULLISH" if bull else "BEARISH", "level": round(lo if bull else hi, 1),
                             "role": "SUPPORT" if bull else "RESISTANCE", "setup_tf": "5M", "spot": close, "algo_decision": "TEST",
                             "setup": {"bot_label": "🧪 DRY-RUN (order नाही)", "tags": {"test": True}}})


def finish_dry(sid, spot, drift_mr=0.5):
    """निर्णयानंतर bot जे करेल ते (order शिवाय): drift guard ⇒ EXECUTED / DRIFT_REJECTED / SHADOWED. रिटर्न (status, तपशील)."""
    r = VS.get_signal(sid)
    if r["status"] == "APPROVED":
        drift = VD.drift_guard(r, spot, r["direction"], drift_mr)
        if drift:
            VS.transition(sid, "APPROVED", "DRIFT_REJECTED", executed_at=VS._iso(VS.now_ist()), drift_result="; ".join(drift),
                          exec_note="dry-run: order नाही")
            return "DRIFT_REJECTED", "; ".join(drift)
        VS.transition(sid, "APPROVED", "EXECUTED", executed_at=VS._iso(VS.now_ist()), drift_result="ok",
                      exec_note=f"dry-run: order नाही (lots × {r['factor']})")
        return "EXECUTED", f"drift guard ठीक · size × {r['factor']}"
    if r["status"] == "REJECTED":
        VS.transition(sid, "REJECTED", "SHADOWED", executed_at=VS._iso(VS.now_ist()), exec_note="dry-run: shadow order नाही")
        return "SHADOWED", r.get("decision_reason") or "rejected"
    return r["status"], r.get("decision_reason") or ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="veto_then_confirm", choices=("veto_then_confirm", "human_confirm", "auto_veto"))
    ap.add_argument("--no-vision", action="store_true")
    ap.add_argument("--window", type=float, default=3.0, help="Approve मुदत (मिनिटं)")
    ap.add_argument("--drift", action="store_true", help="approve नंतर spot मुद्दाम दूर ⇒ drift guard नकार")
    ap.add_argument("--symbol", default="NIFTY")
    a = ap.parse_args(argv)
    if a.no_vision:
        os.environ.pop("VISION_SIGNAL_MODEL", None)
    m1, _ = VW.default_fetch(a.symbol, False)
    if m1 is None or len(m1) == 0:
        print("❌ 1m candles मिळाले नाहीत (Upstox token?)")
        return 1
    sid = make_signal(m1, a.mode, a.symbol)
    row = VS.claim_one(sid)
    if row is not None:
        VW.process_row(row, data_cache={(a.symbol, False): (m1, None)})
    else:                                                                # चालू worker ने आधीच उचलला — तोच chart / बटणं पाठवेल
        print("ℹ️ vision worker ने हा TEST signal उचलला — त्याची वाट …")
        for _ in range(60):
            if VS.get_signal(sid)["status"] not in ("QUEUED", "RUNNING"):
                break
            time.sleep(2)
    r = VS.get_signal(sid)
    print(f"TEST {sid}: verdict {r['verdict']} ⇒ {r['status']} ({r.get('decision_reason')})")
    if r["status"] == "PENDING_HUMAN":
        VS.update(sid, deadline=VS._iso(VS.now_ist() + pd.Timedelta(minutes=a.window)))
        print(f"⏱ Telegram वर {a.window:g} मिनिटांत ✅ / ❌ दाबा (किंवा थांबा ⇒ timeout).")
        from process_lock import ProcessLock, ProcessLockHeld
        from vision import telegram_bot as TB
        try:
            lock = ProcessLock("vision_telegram").__enter__()                      # service चालू नाही ⇒ इथेच getUpdates
            own = True
        except ProcessLockHeld:
            lock, own = None, False
            print("ℹ️ Telegram service चालू आहे — तिच्याकडून बटण वाचलं जाईल.")
        try:
            offset = int(VS.kv_get("tg_offset") or 0)
            while VS.get_signal(sid)["status"] == "PENDING_HUMAN":
                if own:
                    offset = TB.poll_once(offset, timeout=5)
                else:
                    time.sleep(3)
                VW.v1_housekeeping()
        finally:
            if own:
                lock.__exit__(None, None, None)
    m1b, _ = VW.default_fetch(a.symbol, False)
    spot = float(CH.norm_1m(m1b)["close"].iloc[-1]) if m1b is not None and len(m1b) else float(r["spot"])
    if a.drift:
        mr = float(VS.get_signal(sid).get("median_range") or 10.0)
        spot = float(r["spot"]) + 3 * mr * (1 if r["direction"] == "BULLISH" else -1)
    st, why = finish_dry(sid, spot)
    r = VS.get_signal(sid)
    msg = (f"🧪 <b>DRY-RUN निकाल — कोणताही order नाही</b>\n{r['symbol']} {r['direction']} L{float(r['level']):,.0f} · mode {a.mode}\n"
           f"vision: {r['verdict']} · निर्णय: {r.get('decided_by') or '—'} ({r.get('human_decision') or '—'})\n"
           f"⇒ <b>{st}</b> — {why}")
    TG.send_text(msg)
    print(msg.replace("<b>", "").replace("</b>", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
