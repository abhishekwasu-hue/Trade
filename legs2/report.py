"""legs2/report.py — थर 2 §5 मोजमाप (वर्णन, backtest नाही; PDF चं पहिलं पान)."""
import numpy as np
import pandas as pd

from . import measure as LM
from . import settings as LS


def _q(x):
    return "—" if not x else f"{np.percentile(x, 25):.2f} / {np.median(x):.2f} / {np.percentile(x, 75):.2f}"


def _relabel(L, s, c=None, v=None):
    c_hi, c_lo = c or (s["c_hi"], s["c_lo"])
    v_hi, v_lo = v or (s["v_hi"], s["v_lo"])
    nat, weak = LM.nature(LM.classify(L.get("C"), c_hi, c_lo), LM.classify(L.get("V"), v_hi, v_lo))
    if L.get("short"):
        nat, weak = LM.NEU, False
    return LM.label(L["role"], nat, weak)


def rows(lg, start, end, logs):
    """प्रत्येक degree: labels चं वाटप, भूमिकेनुसार C, रचना-नोंद, gap / C_na / volume-विना, sensitivity, I बदल / रद्द."""
    s = lg["settings"]
    out = []
    for d in s["degrees"]:
        ls = [L for L in lg["legs"][d] if pd.Timestamp(start) <= L["known_at"] <= pd.Timestamp(end)]
        lab = pd.Series([L["label"] for L in ls]).value_counts().to_dict() if ls else {}
        cd = [L["C"] for L in ls if L["role"] == LM.ROLE_DOM and L.get("C") is not None]
        cr = [L["C"] for L in ls if L["role"] == LM.ROLE_RET and L.get("C") is not None]
        st = {}
        for L in ls:
            if L.get("structure") and L["structure"].get("note"):
                k = f"{L['role']}: {L['structure']['note']}"
                st[k] = st.get(k, 0) + 1
        sens = 0
        for L in ls:
            alts = {_relabel(L, s, c=c) for c in LS.SENSITIVITY["c"]} | {_relabel(L, s, v=v) for v in LS.SENSITIVITY["v"]}
            sens += any(a != L["label"] for a in alts)
        lg_d = logs.get(d, [])
        out.append({"Degree": f"D{d}", "Legs": len(ls),
                    "Labels": "<br>".join(f"{k} {v}" for k, v in sorted(lab.items(), key=lambda x: -x[1])) or "—",
                    "C प्रबळ (q1/med/q3)": _q(cd), "C परतावा (q1/med/q3)": _q(cr),
                    "रचना (भूमिकेनुसार)": "<br>".join(f"{k} {v}" for k, v in sorted(st.items())) or "—",
                    "gap legs": sum(1 for L in ls if L["gap"]), "C_na": sum(1 for L in ls if L.get("C_na")),
                    "volume-विना / rollover": sum(1 for L in ls if L.get("v_why") == "volume नाही / rollover"),
                    "उंबरठा ±1 ⇒ label बदल": sens,
                    "I बदल / रद्द": (f"{sum(1 for x in lg_d if 'सरकला' in x['event'] or x['event'] == 'नवा I')} / "
                                    f"{sum(1 for x in lg_d if 'रद्द' in x['event'])}") if d in logs else "—"})
    return out
