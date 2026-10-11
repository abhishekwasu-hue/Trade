"""patterns2/charts2.py — 🧭 PATTERN CHECK v2.1 (थर 3 §9): 15M (D1 pattern) + 1H (D2 pattern). v1 chart (labels, alternate फिके,
pattern रेघा, D0 ठिपके) + box: momentum निकाल + 12 ✓✗NA ओळ + अवस्था + गुण; final_flag / partial / position_ban खुणा."""
import pandas as pd

import instruments as INS
from pivots import charts as PC
from swings2 import engine as SE

from . import charts as CH1
from . import fold2 as F2
from . import momentum as MO


def item_json(f1, f2, t):
    j1, j2 = F2.rec_json(f1.out[t], f1.ts), F2.rec_json(f2.out[t], f2.ts)
    for j, f in ((j1, f1), (j2, f2)):
        I = f.trk.I_at(t)
        if I is not None:
            j["I_full"] = {"origin": I["origin"].price, "origin_ts": str(I["origin"].ts), "end": I["end"].price, "end_ts": str(I["end"].ts)}
    return j1, j2


def mline(m):
    if not m:
        return "momentum: —"
    marks = " ".join(f"{i + 1}{x}" for i, x in enumerate(m["items"]))
    dz = f" · danger: {', '.join(m['danger'])}" if m["danger"] else ""
    return f"momentum: <b>{m['verdict']}</b> ({m['ratio'] if m['ratio'] is not None else '—'}, {m['non_na']} non-NA){dz}<br>&nbsp;&nbsp;{marks}"


def box_text(j1, j2):
    rows = []
    for j, nm in ((j1, "15M (D1)"), (j2, "1H (D2)")):
        p = j.get("pref")
        head = (f"<b>{nm}</b>: {CH1._name(p)} · {F2.STATE_MR.get(p['state'], p['state'])} · गुण {p['score']:.2f}" if p
                else f"<b>{nm}</b>: {j['agg_mr']}")
        flags = []
        if p and p.get("flags"):
            flags += p["flags"]
        if j.get("final_flag_risk"):
            flags.append("final_flag_risk")
        if j.get("partial_rise"):
            flags.append("partial_rise")
        if (j.get("position") or {}).get("ban"):
            flags.append(f"position_ban (D2: {j['position'].get('where')})")
        if j.get("c_eq_a") is not None:
            flags.append(f"C=A {j['c_eq_a']:,.0f}")
        rows.append(head + ("<br>&nbsp;&nbsp;" + " · ".join(flags) if flags else ""))
        rows.append("&nbsp;&nbsp;" + mline(j.get("momentum")))
    return "<br>".join(rows)


def charts(res, f1, f2, t, j1, j2):
    m15 = res["m15"]
    m = m15.iloc[:t + 1]
    asof = pd.Timestamp(m["bar_end"].iloc[-1])
    title = "🧭 PATTERN CHECK v2 · " + INS.label() + " {tf} · {d:%d %b %Y %H:%M} · {deg}"
    d0 = SE.known(res, 0, asof)
    d1 = SE.known(res, 1, asof)
    return {"15M": PC.png(CH1.figure(PC.window(m, "15M", asof), "15M", j1, d0, title.format(tf="15M", d=asof, deg="D1 pattern"),
                                     box=box_text(j1, j2))),
            "1H": PC.png(CH1.figure(PC.window(PC.agg_1h(m), "1H", asof), "1H", j2, d1, title.format(tf="1H", d=asof, deg="D2 pattern")))}


def caption(n, total, asof, j1, j2, why=None):
    """≤ 8 ओळी, ≤ 1024 (UTF-16), code keys नाहीत: pattern · अवस्था · momentum · कारण."""
    def one(j):
        p = j.get("pref")
        return (f"{CH1._name(p)} · {F2.STATE_MR.get(p['state'], p['state'])}" if p else j["agg_mr"])

    def mom(j):
        m = j.get("momentum")
        if not m:
            return "—"
        y = sum(x == MO.YES for x in m["items"])
        return f"{m['verdict']} ({y}/{m['non_na']} लक्षणं)" + (" · धोका: " + ", ".join(m["danger"]) if m["danger"] else "")
    lines = [f"🧭 PATTERN CHECK {n}/{total} · {pd.Timestamp(asof):%d %b %Y · %H:%M}" + (f" · {why}" if why else " · दिवस-अखेर"),
             f"15M pattern: {one(j1)}", f"15M momentum: {mom(j1)}", f"1H pattern: {one(j2)}", f"1H momentum: {mom(j2)}"]
    if (j1.get("position") or {}).get("ban"):
        lines.append("जागा: मोठ्या pattern च्या आत (entry बंदी नोंद)")
    lines.append("Reply: ✔ बरोबर · ✘ कोणता pattern / label / momentum चुकला")
    while len("\n".join(lines).encode("utf-16-le")) // 2 > 1024 and len(lines) > 2:
        lines[-2] = lines[-2][:max(0, len(lines[-2]) - 20)]
    return "\n".join(lines)


KEY_STATES = ("final_leg_present", "complete_resuming")


def moments(f, bars, k):
    """महत्त्वाचे क्षण: final_leg_present, complete_resuming, preferred बदल, momentum ⇒ कमकुवत. (दिवस-अखेरची candle वगळून.)"""
    out = []
    prev = f.out.get(bars[0] - 1, {}) if bars else {}
    for t in bars[:-1]:
        r = f.out[t]
        p, pp = r.get("pref"), prev.get("pref")
        why = None
        if r.get("change") and r["change"].get("why") in ("challenger", "preferred invalid"):
            why = "preferred बदल"
        elif p and p["state"] in KEY_STATES and (not pp or pp["state"] != p["state"]):
            why = F2.STATE_MR[p["state"]]
        elif (r.get("momentum") or {}).get("verdict") == MO.WEAK and (prev.get("momentum") or {}).get("verdict") != MO.WEAK:
            why = "momentum कमकुवत"
        if why:
            out.append((t, why))
        prev = r
        if len(out) >= k:
            break
    return out


def rows(folds, t0, t1):
    """मोजमाप (वर्णन; थर 3 §10)."""
    out = []
    for d, f in folds.items():
        rs = [f.out[t] for t in range(t0, t1 + 1) if t in f.out]
        fam, stt, ver, items = {}, {}, {}, {}
        flips, last = 0, None
        for r in rs:
            p = r.get("pref")
            if p:
                fam[p["family"]] = fam.get(p["family"], 0) + 1
            stt[r["agg"]] = stt.get(r["agg"], 0) + 1
            m = r.get("momentum")
            if m:
                ver[m["verdict"]] = ver.get(m["verdict"], 0) + 1
                if last is not None and m["verdict"] != last:
                    flips += 1
                last = m["verdict"]
                for i, x in enumerate(m["items"]):
                    items.setdefault(i + 1, {MO.YES: 0, MO.NO: 0, MO.NA: 0})[x] += 1
        n = max(len(rs), 1)
        out.append({"degree": f"D{d}", "patterns": ", ".join(f"{k}:{v}" for k, v in sorted(fam.items())),
                    "अवस्था %": ", ".join(f"{F2.STATE_MR.get(k, k)}:{round(100 * v / n)}" for k, v in sorted(stt.items())),
                    "ओळखता येत नाही %": round(100 * stt.get("none", 0) / n),
                    "preferred बदल": sum(1 for e in f.log if t0 <= e["bar"] <= t1 and "बदल" in e["event"]),
                    "momentum": ", ".join(f"{k}:{v}" for k, v in sorted(ver.items())), "verdict flips": flips,
                    "लक्षणं ✓/✗/NA": " ".join(f"{i}:{c[MO.YES]}/{c[MO.NO]}/{c[MO.NA]}" for i, c in sorted(items.items()))})
    return out


def register_rows():
    from . import settings2 as PS
    return [{"आकडा": k, "default": str(v[0]), "पर्याय": str(v[1]), "वर्ग": v[2], "स्रोत": v[3]} for k, v in PS.REGISTER.items()]
