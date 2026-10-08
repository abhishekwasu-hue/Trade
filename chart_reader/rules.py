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
    if not ctx.get("approach_ok") or (side < 0 and role == "SUPPORT") or (side > 0 and role == "RESISTANCE"):
        out.append("breakout / chase entry (चुकीची बाजू, support वर bear call / resistance वर bull put, किंवा ORB)")
    if ctx.get("gap_chase"):
        out.append("GAP_NO_PULLBACK — trade दिशेचा gap, पहिला pullback अजून नाही (gap-and-go / chase) [K13]")
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


def zone_entry(side, area, comp, entry, mr, s):
    """§3 (A3 व्याख्यात्मक व्हेटो — pullback खऱ्या zone मध्ये संपला): bear call ⇒ selling zone, bull put ⇒ buying zone.
    reversal composite (o, h, l, c) चं trade-विरुद्ध टोक (bear high / bull low) zone च्या आत किंवा ≤ zone_entry_tol_mr × MR अंतरात.
    Close चं अंतर नियम नाही (Abhi 2026-10-08: R:R ≥ 3 आणि strength_max cap पुरेसे) — फक्त नोंद (dist_mr).
    रिटर्न {code: None / "NO_ZONE" / "FAR_FROM_ZONE", line, touch_mr, dist_mr}."""
    if not side or not mr:
        return {"code": None, "line": "—", "touch_mr": None, "dist_mr": None}
    want = "RESISTANCE" if side < 0 else "SUPPORT"
    if area is None or area.get("kind") != "solid" or area.get("role") != want:
        return {"code": "NO_ZONE", "line": f"NO_ZONE — trade बाजूचा {'selling' if side < 0 else 'buying'} zone नाही ⇒ entry नाही",
                "touch_mr": None, "dist_mr": None}
    lo_, hi_ = float(area["low"]), float(area["high"])
    tip = (float(comp[1]) if side < 0 else float(comp[2])) if comp else None
    touch = None if tip is None else max(0.0, (lo_ - tip) if side < 0 else (tip - hi_)) / mr
    dist = max(0.0, (lo_ - entry) if side < 0 else (entry - hi_)) / mr
    if side < 0 and entry > hi_ or side > 0 and entry < lo_:
        dist = 0.0                                                          # zone पलीकडे close — इतर नियम (invalidation / chase) पाहतात
    zid = area.get("id")
    if touch is None or touch > float(s["zone_entry_tol_mr"]):
        return {"code": "FAR_FROM_ZONE", "touch_mr": touch, "dist_mr": round(dist, 2),
                "line": f"FAR_FROM_ZONE — reversal zone {zid} पर्यंत पोहोचला नाही ({'—' if touch is None else f'{touch:.2f}'} MR > "
                        f"{s['zone_entry_tol_mr']:g})"}
    return {"code": None, "touch_mr": round(touch, 2), "dist_mr": round(dist, 2),
            "line": f"zone {zid} ({lo_:,.1f}–{hi_:,.1f}) वर entry: reversal {touch:.2f} MR, entry अंतर {dist:.2f} MR"}
