"""
elliott/invalidation.py — E2: invalidation hierarchy (spec §7) — signal नंतर कुठला level खरा तुटला
-------------------------------------------------------------------------------------------------
🎓 तीन स्तर, सगळे **real break** ने (breaks.py — buffer + displacement / acceptance / failed retest; wick किंवा reclaim ⇒ false
break ⇒ काहीच नाही), signal च्या TTF वर, signal bar नंतरपासून:
  hard    trade degree चा hard_inv          ⇒ लगेच exit, त्या setup ला re-entry नाही
  parent  D+1 चे invs (cascade)             ⇒ exit (D+1 count मेला ⇒ त्याखालचे सगळे trades)
  soft    reversal composite चं टोक ± buffer ⇒ soft_stop_action (default exit); hard टिकला असेल तर re-entry (E3: max_reentries)
Lower degree (D−1) चा break फक्त warning (lower_inv_action, E3).
Exit निर्णय (क्रम, premium stop, target …) E3 चा — इथे फक्त "कुठला level, कधी तुटला".
"""


def level_events(scanner, sig, t, hard_inv=None):
    """t पर्यंत तुटलेले levels: [(kind, level, confirm_index)] — confirm क्रमाने. Causal: BreakCache फक्त t पर्यंत.
    hard_inv = progressive inv नंतरचा चालू level (TradeState.hard_inv); नसेल ⇒ signal चा."""
    from .breaks import frame_index_at
    fr = scanner.frames[sig.ttf]
    j = frame_index_at(fr, t)
    if j <= sig.ttf_idx:
        return []
    cache = scanner.cache[sig.ttf]
    side = "below" if sig.trade_dir > 0 else "above"
    out = []
    checks = [("hard", sig.hard_inv if hard_inv is None else hard_inv)] + [("soft", sig.soft_stop)] + \
        [("parent", lvl) for lvl, sd, _ in sig.parent_invs if sd == side]
    for kind, lvl in checks:
        c = cache.confirm_index(sig.ttf_idx + 1, lvl, side, j)
        if c is not None:
            out.append((kind, float(lvl), int(c)))
    return sorted(out, key=lambda x: (x[2], ("hard", "parent", "soft").index(x[0])))
