"""chart_reader/risk.py — active area वरून invalidation, target areas आणि spot R:R (पक्का नियम R:R ≥ 1:3).

invalidation (bull put) = min(area low, reversal composite low, correction चं टोक) − inv_buffer_mr × MR — सगळ्यात दूरचं (idea खरंच
चुकली तिथे).
Bear call आरसा. targets = पुढचे 1–2 opposite areas (entry च्या पलीकडे, जवळचा आधी). R:R = (entry → पहिला target) ÷ (entry → invalidation).
किंमती फक्त OHLC / code areas मधून — vision च्या image वरून कधीच नाही.
"""


def compute(side, entry, area, rev_comp, targets, mr, s, extreme=None):
    """extreme = correction चं टोक (structure) — invalidation त्याच्याही पलीकडे (idea तिथेच चुकते)."""
    buf = float(s["inv_buffer_mr"]) * float(mr or 0.0)
    if side > 0:
        ref = min(float(area["low"]), float(rev_comp[2])) if rev_comp else float(area["low"])
        if extreme is not None:
            ref = min(ref, float(extreme))
        inv = ref - buf
        tg = sorted([(p, i) for p, i in targets if p > entry], key=lambda x: x[0])
    else:
        ref = max(float(area["high"]), float(rev_comp[1])) if rev_comp else float(area["high"])
        if extreme is not None:
            ref = max(ref, float(extreme))
        inv = ref + buf
        tg = sorted([(p, i) for p, i in targets if p < entry], key=lambda x: -x[0])
    tg = [{"price": float(p), "id": i} for p, i in tg[: int(s["max_targets"])]]
    risk = abs(entry - inv)
    rr = (abs(tg[0]["price"] - entry) / risk) if tg and risk > 0 else None
    return {"entry": float(entry), "invalidation": float(inv), "risk_pts": round(risk, 2), "targets": tg,
            "rr": rr, "line": (f"invalidation {inv:,.1f} · target {tg[0]['price']:,.1f} ({tg[0]['id']}) · spot R:R 1:{rr:.1f}" if tg and rr
                                else f"invalidation {inv:,.1f} · target area नाही ⇒ R:R नाही")}
