"""chart_reader/rules.py — पक्के नियम (Abhi §0; हेच फक्त, बाकी सगळं पुरावा). कुठलाही मोडला ⇒ entry नाही, कारणासह.

1. Breakout / chase entry नाही: support वर bear call / resistance वर bull put नाही; किंमत योग्य बाजूने area कडे आलेली हवी;
   gap-and-go / ORB / पहिल्या 15m चा break नाही; 09:15–09:30 मध्ये entry नाही.
2. फक्त बंद candle वर.
3. स्पष्ट invalidation (योग्य बाजूला, finite).
4. Spot R:R ≥ min_rr (1:3).
5. Risk मर्यादा (bot चे dashboard settings — caller `risk_ok` देतो).
"""
import pandas as pd


def check(ctx, s):
    """ctx: side, bar_closed, bar_end, approach_ok, area_role, invalidation, entry, rr, gap_chase, risk_ok. रिटर्न मोडलेल्या नियमांची यादी."""
    out = []
    side = ctx["side"]
    if not ctx.get("bar_closed"):
        out.append("बंद candle नाही — फक्त बंद candle वर entry")
    role = ctx.get("area_role")
    if not ctx.get("approach_ok") or (side < 0 and role == "SUPPORT") or (side > 0 and role == "RESISTANCE") or ctx.get("gap_chase"):
        out.append("breakout / chase entry (चुकीची बाजू, support वर bear call / resistance वर bull put, किंवा gap-and-go / ORB)")
    be = pd.Timestamp(ctx["bar_end"]) if ctx.get("bar_end") is not None else None
    if be is not None:
        open_end = be.normalize() + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=int(s["opening_block_min"]))
        if be <= open_end:
            out.append(f"09:15–{open_end:%H:%M} opening window — entry नाही")
    inv, entry = ctx.get("invalidation"), ctx.get("entry")
    if inv is None or entry is None or (side > 0 and not inv < entry) or (side < 0 and not inv > entry):
        out.append("स्पष्ट invalidation नाही (किंवा चुकीच्या बाजूला)")
    rr = ctx.get("rr")
    if rr is None or rr < float(s["min_rr"]):
        out.append(f"spot R:R {'—' if rr is None else f'1:{rr:.1f}'} < 1:{s['min_rr']:g}")
    if not ctx.get("risk_ok", True):
        out.append("risk मर्यादा (bot settings: daily loss / max open / kill switch)")
    return out
