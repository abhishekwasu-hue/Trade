"""chart_reader/elliott_ctx.py — Elliott ची शक्यता (evidence EW), निर्णायक नाही (golden 0/5 ⇒ Elliott एकट्याने entry देत नाही).

  "end"            trade degree वर preferred count चा setup (wave 2 / 4 / ABC C-end / triangle E-end) trade बाजूने
  "a_end_or_in_b"  preferred count = zigzag / flat, impulse विरुद्ध, चालू wave A किंवा B ⇒ correction अपूर्ण. `clear` = त्या degree ची count
                   gray नाही ⇒ A3 व्हेटो (KB); gray ⇒ फक्त EW −15 (शक्यता)
  "gray"           count gray / कमी confidence ⇒ neutral
  "none"           काही नाही
S6a / S13 (B-end → C) setups `c_wave_setups_enabled` (default OFF) — grade.py मध्ये.
फक्त asof पर्यंतचे 1m (Elliott engine स्वतः causal: confirmed pivots known_at ≤ t).
"""
from elliott import settings as ES


def read(df1m, asof, side, degrees=(1, 2), es=None):
    es = es or dict(ES.DEFAULTS)
    out = {"state": "none", "clear": False, "setup": None, "tier": None, "hard_inv": None, "zone": None, "degree": None, "line": "Elliott: —"}
    try:
        from elliott import swings as W
        from elliott.counts import CountEngine
        from elliott.setups import Setup, degree_setup
        md = W.multi_degree(df1m, es, now=asof)
        eng = CountEngine(md, es)
        snap = eng.snapshot(asof)
        grays = []
        for d in degrees:
            st = degree_setup(eng, snap, d, asof)
            if isinstance(st, Setup):
                if st.trade_dir == side:
                    lv = [float(x) for x in st.levels] if st.levels else []
                    out.update(state="end", setup=st.code, tier=st.tier, hard_inv=float(st.hard_inv), degree=d,
                               zone=(min(lv), max(lv)) if lv else None,
                               line=f"Elliott D{d}: {st.code} (Tier {st.tier}) — {st.node.pattern} {st.node.current_wave} चा शेवट, "
                                    f"invalidation {st.hard_inv:,.1f}")
                    return out
                continue
            if st == "gray":
                grays.append(d)
            v = snap.degrees.get(d)
            pref = v.preferred if v is not None else None
            if pref is not None and pref.pattern in ("zigzag", "flat") and pref.direction == -side and pref.current_wave in ("A", "B"):
                out.update(state="a_end_or_in_b", degree=d, clear=st != "gray",
                           line=f"Elliott D{d}: {pref.pattern} wave {pref.current_wave} चालू ⇒ correction अपूर्ण (A-end / B च्या आत entry नाही)")
                return out
        if grays:
            out.update(state="gray", line=f"Elliott: count gray (D{', D'.join(map(str, grays))}) ⇒ neutral")
    except Exception as exc:                                             # Elliott अपयश ⇒ gray (neutral), निर्णय अडत नाही
        out.update(state="gray", line=f"Elliott: गणना अपयशी ({type(exc).__name__}) ⇒ gray")
    return out
