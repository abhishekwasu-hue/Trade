"""simple_core/count_source.py — एकच count स्रोत (Phase B §2.5; Abhi 2026-10-09): G9 / G1 label, S11, पालक दिशा (`preferred_count`) आणि
"दोन counts" नोंद — सगळं elliott count engine (elliott.counts.CountEngine, market_state.elliott_vote वापरतो तोच) च्या **preferred**
count (आणि alternate) मधून. `waves.py` चा स्वतंत्र count निर्णयात नाही (फक्त तुलना अहवाल).

Degree (निर्णय 9 / §2.4): reading layer चा correction origin E (trade-degree confirmed pivot) ज्या count-degree वर confirmed pivot म्हणून
आहे, त्यापैकी सगळ्यात मोठी degree (D3 → D0 शोध) — ती "correction ची degree". त्या degree चा preferred node:
  • चालू wave E पासून सुरू (node चा शेवटचा point = E) ⇒ हाच node trade होणाऱ्या correction चं वर्णन करतो;
  • motive (impulse / diagonal) + चालू wave 2 ⇒ G1, 4 ⇒ G9 (G9 फक्त preferred wave 4 म्हणतो तेव्हा; alternate ⇒ फक्त grade वाढ);
  • corrective + चालू wave B ⇒ S11 (B च्या आत; B-end → C विरुद्ध ⇒ default OFF);
  • sequence दिशा (पालक, `preferred_count`): motive node ⇒ node.direction; corrective node मधे B / X / D ⇒ node.direction; नाहीतर
    वरच्या degree चा preferred motive node ⇒ त्याची direction; काहीच नाही ⇒ PARENT_UNKNOWN.
Count नाही / degree जुळत नाही ⇒ labels नाहीत ("count gray at trade degree") — engine चा निर्णय बदलत नाही (G-labels नाहीत एवढंच).
"""
import pandas as pd

MOTIVE = ("impulse", "lead_diag", "end_diag")
TIE_EPS = 1e-9                                                             # व्याख्या: score बरोबरी (floating सहनशीलता)


def _parent_of(n, snap, deg):
    """Sequence दिशा (पालक, §2.3): motive node ⇒ node.direction; corrective मधे B / X / D ⇒ node.direction; नाहीतर वरच्या degree चा
    preferred motive node ⇒ त्याची direction; काहीच नाही ⇒ 0."""
    if n.pattern in MOTIVE or n.current_wave in ("B", "X", "D"):
        return int(n.direction)
    up = snap.degrees.get(deg + 1)
    upn = (up.preferred or (up.nodes[0] if up.nodes else None)) if up is not None else None
    return int(upn.direction) if upn is not None and upn.pattern in MOTIVE else 0


def _node(n):
    if n is None:
        return None
    return {"pattern": n.pattern, "wave": n.current_wave, "dir": int(n.direction), "current_dir": int(n.current_dir),
            "next_motive_dir": int(n.next_motive_dir or 0), "start_ts": str(pd.Timestamp(n.points[-1].ts)),
            "points": [(str(pd.Timestamp(p.ts)), round(float(p.price), 2)) for p in n.points],
            "invs": [(round(float(l), 2), sd) for l, sd, _ in (n.invs or [])][:3]}


def engine(df1m, asof, es=None):
    """CountEngine + snapshot(asof) (auto_by_bars — market_state.elliott_vote सारखं). अपयश ⇒ (None, कारण)."""
    from elliott import settings as ES
    from elliott import swings as W
    from elliott.counts import CountEngine
    es = es or dict(ES.DEFAULTS)
    asof = pd.Timestamp(asof)
    try:
        cut = df1m[pd.to_datetime(df1m["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
        md = W.multi_degree(cut, es, now=asof)
        return md, CountEngine(md, es).snapshot(asof)
    except Exception as exc:                                               # noqa: BLE001 — गुपचूप नाही: कारण नोंदीत
        return None, f"{type(exc).__name__}: {str(exc)[:80]}"


def degrees_brief(snap):
    """B4 (P7) नोंद: प्रत्येक degree चे preferred / alternate (pattern / चालू wave / दिशा) + gray."""
    out = {}
    for d, v in sorted(snap.degrees.items()):
        pref = v.preferred or (v.nodes[0] if v.nodes else None)
        alt = next((n for n in v.nodes if n is not pref), None)
        out[f"D{d}"] = {"preferred": None if pref is None else f"{pref.pattern}/{pref.current_wave}/{int(pref.direction):+d}",
                        "alternate": None if alt is None else f"{alt.pattern}/{alt.current_wave}/{int(alt.direction):+d}",
                        "gray": bool(v.gray)}
    return out


def read(df1m, asof, e_ts, side, es=None, md_snap=None):
    """E (correction origin, trade-degree pivot) च्या degree चा preferred / alternate count. रिटर्न dict (नोंद + निर्णयासाठी)."""
    asof = pd.Timestamp(asof)
    md, snap = md_snap if md_snap is not None else engine(df1m, asof, es)
    out = {"degree": None, "preferred": None, "alternate": None, "setup": None, "S11": False, "parent_dir": 0,
           "parent_code": "PARENT_UNKNOWN", "why": ""}
    if md is None:
        out["why"] = f"count engine अपयश: {snap}"
        return out
    out["degrees"] = degrees_brief(snap)                                   # B4 नोंद: प्रत्येक degree चे दोन counts
    if e_ts is None:
        out["why"] = "correction origin नाही"
        return out
    e_ts = pd.Timestamp(e_ts)
    ekind = "L" if side < 0 else "H"
    deg = None
    for d in sorted(md, reverse=True):                                     # सगळ्यात मोठी degree जिथे E confirmed pivot आहे
        tf = md[d]["tf"]
        tol = pd.Timedelta(minutes=30 if tf in ("5m", "15m") else 120)
        if any(p.kind == ekind and abs(pd.Timestamp(p.ts) - e_ts) <= tol and p.confirmed_at is not None and p.confirmed_at <= asof
               for p in md[d]["confirmed"]):
            deg = d
            break
    if deg is None:
        out["why"] = "E कोणत्याही count degree वर confirmed pivot नाही"
        return out
    out["degree"] = int(deg)
    v = snap.degrees.get(deg)
    if v is None or not v.nodes:
        out["why"] = f"D{deg}: valid count नाही"
        return out
    pref = v.preferred or v.nodes[0]
    alt = next((n for n in v.nodes if n is not pref), None)
    out.update(preferred=_node(pref), alternate=_node(alt))
    tol = pd.Timedelta(minutes=30 if md[deg]["tf"] in ("5m", "15m") else 120)
    # I6 (7 Oct, Abhi 2026-10-09 "12:15 ला C संपला"): beam मध्ये score बरोबरीत ⇒ "preferred" फक्त pattern नावाच्या क्रमाने निवडलेला
    # (counts.py sort tie-break) — तो पसंती नाही. Tie ⇒ count-आधारित labels / S11 नाहीत ("count tie" नोंद); पालक फक्त सगळे सहमत असतील तर.
    top = float(getattr(pref, "joint_score", 0.0) or 0.0)
    tie = [n for n in v.nodes if abs(float(getattr(n, "joint_score", 0.0) or 0.0) - top) <= TIE_EPS]
    if len(tie) > 1:
        out["count_tie"] = [f"{n.pattern}/{n.current_wave}" for n in tie]
    here = abs(pd.Timestamp(pref.points[-1].ts) - e_ts) <= tol            # चालू wave E पासून ⇒ हाच node correction चं वर्णन
    # I6.4 तुलना (अहवालासाठी): tie नियमाआधीचं उत्तर (नावाच्या क्रमाचा preferred) — निर्णयात वापर नाही
    out["S11_alpha"] = bool(here and pref.pattern not in MOTIVE and pref.current_wave == "B")
    out["setup_alpha"] = ({"2": "G1", "4": "G9"}.get(pref.current_wave)
                          if here and pref.pattern in MOTIVE and int(pref.direction) == side else None)
    if len(tie) == 1 and here and pref.pattern in MOTIVE and int(pref.direction) == side:
        out["setup"] = {"2": "G1", "4": "G9"}.get(pref.current_wave)
    if len(tie) == 1 and here and pref.pattern not in MOTIVE and pref.current_wave == "B":
        out["S11"] = True
    pdirs = {_parent_of(n, snap, deg) for n in tie}
    if len(pdirs) == 1 and next(iter(pdirs)):
        out.update(parent_dir=next(iter(pdirs)), parent_code=None)
    if alt is not None and int(alt.next_motive_dir or 0) == side:
        out["alt_same_side"] = True                                         # P2 grade वाढ (alternate नुसार सुद्धा त्याच दिशेने)
    return out


def wave_refs(pref, setup, s, ext=None):
    """एकाच preferred count मधून wave refs (फक्त माहिती; target / SL dashboard ठरवतं). Gray / label नाही ⇒ सगळे None.
    G1 (चालू wave 2): wave1_origin = O, wave1_extreme = W1, wave3_projection = wave 2 टोक (ext) + w3_proj × wave 1.
    G9 (चालू wave 4): wave1_origin = O, wave1_extreme = W1, wave5_projection = wave 4 टोक (ext) + w5_proj_w1 × wave 1.
    Projection प्रमाणं = settings (KB H guideline, K7: फक्त माहिती)."""
    out = {"wave3_projection": None, "wave5_projection": None, "wave1_origin": None, "wave1_extreme": None, "subwave_origin": None}
    pts = [p for _, p in (pref or {}).get("points") or []]
    if setup not in ("G1", "G9") or len(pts) < 2:
        return out
    o, w1 = float(pts[0]), float(pts[1])
    d = 1.0 if w1 > o else -1.0
    out.update(wave1_origin=round(o, 2), wave1_extreme=round(w1, 2))
    if ext is not None:
        if setup == "G1":
            out["wave3_projection"] = round(float(ext) + d * float(s["w3_proj"]) * abs(w1 - o), 2)
        else:
            out["wave5_projection"] = round(float(ext) + d * float(s["w5_proj_w1"]) * abs(w1 - o), 2)
    return out
