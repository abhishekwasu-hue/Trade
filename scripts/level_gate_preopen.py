"""scripts/level_gate_preopen.py — 09:15 आधी एकदा: आजची Daily trend अवस्था + bots कोणते areas पाहणार (trade-बाजूचे), Telegram ला.

Abhi (TRADE_SESSION_LEVEL_BOTS_CONFIRMATION §8): pre-open check. Trend (decision3 Daily, कालच्या close पर्यंत) दिवसासाठी cache होतो —
bots तोच वापरतात. Trend काढता आला नाही ⇒ "NO NEW ENTRIES (fail-closed)" स्पष्ट. हा script order देत नाही.

    python3 scripts/level_gate_preopen.py [--symbols NIFTY,BANKNIFTY,SENSEX] [--no-telegram]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots_common import level_reaction as LR  # noqa: E402

BOT_TFS = {"5M Instant": ("1M", "5M"), "Classic": ("5M", "15M"), "15M SRv2": ("15M", "30M", "60M")}


def trade_side_areas(zones, tfs, last, ctx, n=3):
    """त्या bot च्या timeframes चे ACTIVE areas ⇒ trend ने परवानगी दिलेल्या बाजूचे, किंमतीच्या सर्वात जवळचे n."""
    if zones is None or len(zones) == 0 or last is None:
        return []
    out = []
    for _, z in zones.iterrows():
        if z.get("status") != "ACTIVE" or not any(str(z.get("zone_type", "")).endswith(f"_{tf}") for tf in tfs):
            continue
        lo = float(z["zone_low"])
        hi = float(z["zone_high"]) if z.get("zone_high") is not None else lo
        lo, hi = min(lo, hi), max(lo, hi)
        side = LR.BULL if hi < last else (LR.BEAR if lo > last else None)
        if side and LR.side_allowed(ctx, side, (lo, hi)):
            out.append((abs((lo + hi) / 2 - last), side, lo, hi, str(z.get("zone_type"))))
    out.sort()
    seen, res = set(), []
    for _, side, lo, hi, zt in out:
        k = (round(lo), round(hi))
        if k not in seen:
            seen.add(k)
            res.append((side, lo, hi, zt))
        if len(res) >= n:
            break
    return res


def build_report(symbols, token, get_zones, last_close, trend_fn=None):
    trend_fn = trend_fn or (lambda sym: LR.daily_trend(sym, token))
    lines = ["🧭 Level bots — pre-open check (confirmation mode)"]
    for sym in symbols:
        ctx = trend_fn(sym)
        last = last_close(sym)
        head = f"\n<b>{sym}</b> · {ctx.get('reason')}"
        if ctx.get("protected") is not None:
            head += f" · protected {ctx['protected']:,.0f}"
        if not ctx.get("ok"):
            lines.append(head + "\n⛔ NO NEW ENTRIES today (fail-closed) — exits run as usual")
            continue
        lines.append(head + (f" · last close {last:,.0f}" if last else ""))
        zones = get_zones(sym)
        for bot, tfs in BOT_TFS.items():
            ar = trade_side_areas(zones, tfs, last, ctx)
            if not ar:
                lines.append(f"• {bot}: no trade-side area near price")
                continue
            txt = "; ".join(f"{'demand' if s == LR.BULL else 'supply'} {lo:,.0f}–{hi:,.0f}" for s, lo, hi, _ in ar)
            lines.append(f"• {bot}: watching {txt}")
    lines.append("\nMCX: PAPER new entries paused until its confirmation gate (L4) is ready; exits run as usual.")
    lines.append("Entry only after a closed-candle commitment → Vision → your ✅. PAPER only.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NIFTY,BANKNIFTY,SENSEX")
    ap.add_argument("--no-telegram", action="store_true")
    a = ap.parse_args(argv)
    import cloud_db
    token = cloud_db.get_effective_upstox_token(None)
    if not token:
        print("❌ Upstox token नाही — आधी daily login करा. Trend काढता येत नाही ⇒ bots नवे entries घेणार नाहीत (fail-closed).")
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]

    def last_close(sym):
        try:
            from upstox_api import fetch_candles
            df = fetch_candles(token, sym, current_spot=0, interval="day", lookback_days=10)
            return float(df["close"].iloc[-1]) if df is not None and len(df) else None
        except Exception:
            return None

    msg = build_report(syms, token, lambda s: cloud_db.get_market_zones(s), last_close)
    print(msg)
    if not a.no_telegram:
        try:
            from notifications import send_telegram_message
            send_telegram_message(msg)
        except Exception as exc:
            print(f"⚠️ Telegram त्रुटी: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
