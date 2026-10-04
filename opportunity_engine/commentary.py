"""opportunity_engine/commentary.py — मराठी "ट्रेडर commentary" (spec §9): प्रत्येक निर्णयासाठी (घेतलेला, नाकारलेला, gate-rejected, pullback). फक्त मजकूर बनवतं."""
from .config import TF_LABEL
from .context import trend_sign

STATE_MR = {
    "UPTREND": "UPTREND", "UPTREND_PULLBACK": "UPTREND (pullback)", "UPTREND_WEAK": "UPTREND कमजोर (CHoCH)",
    "DOWNTREND": "DOWNTREND", "DOWNTREND_PULLBACK": "DOWNTREND (pullback)", "DOWNTREND_WEAK": "DOWNTREND कमजोर (CHoCH)",
    "RANGE": "RANGE", "INIT": "अजून ठरलेला नाही", None: "—",
}
DIR_MR = {"LONG": "Long", "SHORT": "Short"}
SETUP_MR = {"D1": "Gap-Go", "D2": "Gap-Fade", "D3": "Gap-Retest Reversal", "D4": "Trendline 3री touch", "D5": "Trendline Break-Retest",
            "D6": "HTF Zone Pullback Reversal", "D7": "Range-Box Breakout", "D8": "Triangle Breakout", "D9": "Chart Pattern Breakout", "D10": "Failed-Breakout Trap"}


def _px(x):
    return "—" if x is None else f"{x:,.0f}" if abs(x) >= 1000 else f"{x:,.2f}"


def states_line(ctx):
    parts = []
    for tf in ("1d", "4h", "1h"):
        st = ctx.get(tf)
        if st is None:
            continue
        prot = f" (protected {_px(st.protected)})" if st.protected is not None else ""
        parts.append(f"{TF_LABEL[tf]} {STATE_MR.get(st.state, st.state)}{prot}")
    return ", ".join(parts)


def bias_line(bias):
    return f"Bias: {bias.label} — " + "; ".join(bias.reasons)


def gate_rejected(cand, gate, bias, ctx):
    name = SETUP_MR.get(cand.setup_id, cand.setup_id)
    txt = f"{name} ({DIR_MR[cand.direction]}) नाकारला [{', '.join(gate.codes)}]: " + "; ".join(gate.reasons) + f". {states_line(ctx)}."
    if gate.pullback_in_progress:
        txt += " हा pullback मानला, trade नाही."
        if gate.watch:
            txt += f" Watch zone: {_px(gate.watch['zone_low'])}–{_px(gate.watch['zone_high'])} ({gate.watch['reason']})."
    return txt


def rejected(cand, status, reasons, ctx):
    name = SETUP_MR.get(cand.setup_id, cand.setup_id)
    return f"{name} ({DIR_MR[cand.direction]}) — {status}: " + "; ".join(reasons) + f". {states_line(ctx)}."


def taken(cand, plan, score, validation, ctx, bias):
    name = SETUP_MR.get(cand.setup_id, cand.setup_id)
    z = cand.zone
    zone_txt = ""
    if z:
        zone_txt = f" {TF_LABEL.get(z.get('tf'), z.get('tf'))} {z.get('freshness', '')} {z.get('kind', '')} zone ({_px(z.get('low'))}–{_px(z.get('high'))}, grade {z.get('quality_grade', '?')}) मध्ये."
    if validation.kind == "REVERSAL":
        ok = [name for name, ch in validation.checks.items() if ch.get("pass")]
        trig = f"reversal ({', '.join(ok) or '—'}) score {validation.score:.0f}"
    else:
        vol = "Volume N/A" if validation.volume_na else f"volume {validation.checks['volume']['value']}×"
        body = validation.checks.get("body", {}).get("value")
        trig = f"body {body}, {vol}" if body is not None else vol
    rr = "" if plan.rr_to_opposing is None else f" पुढचा HTF अडथळा {plan.rr_to_opposing:.1f}R वर."
    size = "पूर्ण साइज" if score.decision == "FULL" else "अर्धी साइज"
    return (f"{states_line(ctx)}.{zone_txt} {name} {DIR_MR[cand.direction]} — entry {_px(plan.entry)}, SL {_px(plan.sl)}, T1 {_px(plan.t1)}, T2 {_px(plan.t2)}. "
            f"Trigger: {trig}.{rr} Score {score.total:.0f} → {size}.")


def summary(result):
    """EvalResult चा एका ओळीचा सारांश (page/Telegram साठी)."""
    n = len(result.decisions)
    chosen = result.selection.chosen
    head = bias_line(result.bias)
    if chosen is not None:
        return f"{head} | निवडलेला: {chosen.candidate.setup_id} {chosen.candidate.direction} (score {chosen.score.total:.0f})"
    return f"{head} | candidates: {n}, निवडलेला: नाही" + (f" ({result.selection.day_block})" if result.selection.day_block else "")
