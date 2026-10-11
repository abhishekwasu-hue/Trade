"""reader2/selfcheck.py — "trader chart पुन्हा तपासतो" (spec §3): marking नंतर invariants 1–7; प्रत्येक उल्लंघनाचा भाग पुन्हा वाचा;
कमाल `max_passes` (3) passes; उरलेलं ⇒ "uncertain". प्रत्येक बदल log: "relabelled X → Y because …" + known_at (वाचनाची वेळ T —
backtest causal: T ला माहीत असलेला label साठवला जातो) + at (बदललेल्या leg / bar ची वेळ).

  1. impulse label पण corrective anatomy (किंवा उलट) ⇒ पर्यायी खालच्या pivots ने re-read (fusion).
  2. Trend flip फक्त impulse counter-move वर (impulse structure + impulsive anatomy + prior swing break); नाहीतर counter-move =
     correction (anatomy आवेगी असेल तर uncertain), trend तसाच.
  3. Correction (c > a सकट) वर flip कधीच नाही.
  4. Protected origin पलीकडे close ⇒ trend पुन्हा वाचा (ठेवू नका).
  5. त्याच degree चे लागोपाठचे दोन उलट "impulse" (दुसरा पहिल्याची सुरुवात तोडत नाही) ⇒ re-read.
  6. वरचा TF: trend साठी वरची degree जिंकते, चालू pullback अवस्थेसाठी खालची (`run(R, higher)`).
  7. नवीन bars ⇒ पुन्हा check (`history`): label बदल कधीच गुपचूप नाही, known_at सह.
"""
import pandas as pd

from . import fusion as RF
from . import trend as RT
from .frame import Chart

TREND_INV = ("2", "3", "4")


def _entry(R, pas, inv, target, frm, to, because, at):
    e = {"pass": pas, "invariant": inv, "target": target, "from": frm, "to": to, "because": because, "known_at": R.known_at,
         "at": at, "text": f"relabelled {target}: {frm} → {to} because {because}"}
    R.log.append(e)
    return e


def relabel(R, leg, to, conf, because, pas, inv):
    if leg.label == to:
        return False
    _entry(R, pas, inv, leg.name(), leg.label, to, because, leg.known_at)
    leg.history.append({"known_at": R.known_at, "from": leg.label, "to": to, "because": because})
    leg.label, leg.confidence, leg.reason = to, conf, because
    return True


def _refuse(R, leg):
    """Leg पुन्हा वाचा: (effective structure, anatomy) ⇒ fusion; विरोध ⇒ पर्यायी pivots (re-read)."""
    sv, av = RT.eff_structure(leg), leg.anatomy
    lab, conf, why = RF.fuse(sv, av)
    if lab is None:
        lab, conf, why, sv2 = RF.reread(R.ch, leg, sv, av)
        if sv2 is not sv:
            leg.structure = dict(leg.structure, reread=sv2)
    return lab, conf, why


def _opposite(label, cls):
    return (label == RF.IMPULSE and cls == "corrective") or (label == RF.CORRECTION and cls == "impulsive")


def _flip_leg(R, ev, new_dir):
    legs = R.legs.get(R.trend_degree, [])
    if ev.get("leg") is not None:
        return R.find(*ev["leg"])
    cand = [lg for lg in legs if lg.dirn == new_dir and lg.i0 < ev["bar"]]
    return max(cand, key=lambda lg: lg.i0) if cand else None


def violations(R):
    """रिटर्न [{"inv", "leg" | None, "bar" | None, "why"}]."""
    out = []
    for lg in R.all_legs():                                                       # 1
        av = lg.anatomy or {}
        if _opposite(lg.label, av.get("cls")):
            out.append({"inv": "1", "leg": lg, "bar": None,
                        "why": f"labelled {lg.label} but anatomy is {av['cls']} ({av['score']:+.2f})"})
    for D, legs in R.legs.items():                                                # 5
        for a, b in zip(legs, legs[1:]):
            if a.label == b.label == RF.IMPULSE and a.dirn != b.dirn and (b.p1 - a.p0) * b.dirn <= 0:
                out.append({"inv": "5", "leg": b, "bar": None, "pair": a,
                            "why": f"two consecutive opposite impulses at degree {D} ({a.name()}, {b.name()}) and the second "
                                   f"does not break the start of the first"})
    last_dec = None                                                               # 2 / 3
    for ev in R.events or []:
        to = ev["to"]
        if to in ("UP", "DOWN"):
            nd = 1 if to == "UP" else -1
            if last_dec is not None and last_dec != nd:
                lg = _flip_leg(R, ev, nd)
                if lg is None:
                    out.append({"inv": "2", "leg": None, "bar": ev["bar"], "why": f"trend flip to {to} with no counter-move leg"})
                elif lg.label == RF.CORRECTION:
                    out.append({"inv": "3", "leg": lg, "bar": ev["bar"],
                                "why": f"flip to {to} rests on {lg.name()}, a correction (a correction beyond its a-wave is "
                                       f"not a flip)"})
                else:
                    ok, why = RT.flip_test(lg, R.prev_of(lg))
                    if not ok:
                        out.append({"inv": "2", "leg": lg, "bar": ev["bar"],
                                    "why": f"flip to {to} rests on {lg.name()}, not an impulse counter-move: {why}"})
            last_dec = nd
    for st in R.states or []:                                                     # 4
        if st["trend"] not in ("UP", "DOWN"):
            continue
        org = st.get("origin")
        if org is None and st.get("leg") is not None:
            lg = R.find(*st["leg"])
            org = lg.p0 if lg else None
        d = 1 if st["trend"] == "UP" else -1
        if org is not None and (R.ch.A["c"][st["bar"]] - org) * d < 0:
            out.append({"inv": "4", "leg": None, "bar": st["bar"],
                        "why": f"trend kept {st['trend']} after a close beyond the protected origin {org:g}"})
            break
    return out


def _fix_counter_move(R, lg, why, pas, inv):
    """2 / 5: counter-move impulse नाही ⇒ correction; anatomy आवेगी (पण structure / break नाही) ⇒ uncertain."""
    sv, av = RT.eff_structure(lg), lg.anatomy or {}
    if av.get("cls") == "impulsive":
        relabel(R, lg, RF.UNCERTAIN, None, why + " (impulsive candles: wave 1 or wave A?)", pas, inv)
    else:
        relabel(R, lg, RF.CORRECTION, "medium" if sv.get("cls") != "impulse" else "low", why, pas, inv)


def _rederive(R, reasons, pas, inv):
    """Trend reader2 नियमांनी पुन्हा (बाहेरची marking असेल तर तिच्या जागी); बदललेल्या प्रत्येक run च्या पहिल्या bar ची नोंद."""
    old = R.states or []
    R.states, R.events = RT.derive(R.ch, R.legs.get(R.trend_degree, []))
    R.trend_source = "reader2"
    prev_same = True
    for o, n in zip(old, R.states):
        same = o["trend"] == n["trend"]
        if not same and prev_same:
            why = reasons.get(n["bar"]) or "; ".join(sorted(set(reasons.values()))) or "trend-degree legs relabelled"
            _entry(R, pas, inv, f"trend at bar {n['bar']}", o["trend"], n["trend"], f"{why} (re-read: {n['why'] or 'no impulse yet'})",
                   n["known_at"])
        prev_same = same


def fix(R, viol, pas):
    trend_reasons, invs, touched_trend = {}, set(), False
    for v in viol:
        lg = v["leg"]
        if v["inv"] == "1":
            lab, conf, why = _refuse(R, lg)
            relabel(R, lg, lab, conf, f"{v['why']}; re-read: {why}", pas, "1")
            touched_trend |= lg.degree == R.trend_degree
        elif v["inv"] == "5":
            a = v["pair"]
            for x in (a, lg):
                if x.history:                                                 # self-check ने आधीच पुन्हा वाचलेला ⇒ परत उलटवू नका
                    continue
                lab, conf, why = _refuse(R, x)
                relabel(R, x, lab, conf, f"{v['why']}; re-read: {why}", pas, "5")
            if a.label == lg.label == RF.IMPULSE:
                _fix_counter_move(R, lg, v["why"], pas, "5")
            touched_trend |= lg.degree == R.trend_degree
        elif v["inv"] == "2" and lg is not None:
            _fix_counter_move(R, lg, v["why"], pas, "2")
            touched_trend = True
        if v["inv"] in TREND_INV:
            trend_reasons.setdefault(v["bar"], v["why"])
            touched_trend = True
        invs.add(v["inv"])
    if touched_trend or R.trend_source != "reader2":
        _rederive(R, trend_reasons, pas, "/".join(sorted(invs)))


def run(R, higher=None):
    """Self-check passes (कमाल max_passes); उरलेले ⇒ uncertain. नंतर invariant 6 (higher दिला तर). R mutate करून परत."""
    mx = int(R.ch.s["max_passes"])
    viol = violations(R)
    p = 0
    while viol and p < mx:
        p += 1
        fix(R, viol, p)
        viol = violations(R)
    R.passes = p
    if viol:
        for v in viol:
            if v["leg"] is not None:
                relabel(R, v["leg"], RF.UNCERTAIN, None, f"unresolved after {mx} self-check passes: {v['why']}", p, v["inv"])
        _rederive(R, {v["bar"]: v["why"] for v in viol if v["bar"] is not None}, p, "/".join(sorted({v["inv"] for v in viol})))
    if higher is not None:
        htf_check(R, higher)
    return R


def _state_at(R, t):
    st = [x for x in (R.states or []) if x["known_at"] <= t]
    return st[-1] if st else None


def htf_check(R, higher, pas=None):
    """Invariant 6 (Q48 projection): वरच्या TF चा trend (R च्या शेवटच्या bar ला माहीत) vs R चा. विरोध ⇒ नोंद + resolution: trend =
    वरचा; R चा उलट trend = चालू pullback अवस्था."""
    me = R.trend_now()
    hi = _state_at(higher, R.known_at)
    mine, theirs = (me or {}).get("trend"), (hi or {}).get("trend")
    out = {"trend": theirs if theirs is not None else mine, "lower_trend": mine, "higher_trend": theirs, "pullback": False,
           "contradiction": False}
    if mine in ("UP", "DOWN") and theirs in ("UP", "DOWN") and mine != theirs:
        out.update(pullback=True, contradiction=True)
        _entry(R, pas, "6", "trend vs higher timeframe", mine, f"pullback within higher {theirs}",
               f"the higher degree ({theirs}) wins for trend; the lower degree ({mine}) gives the current pullback state",
               R.known_at)
    elif mine in ("UP", "DOWN") and theirs == "uncertain":
        _entry(R, pas, "6", "trend vs higher timeframe", mine, "uncertain",
               "the higher timeframe trend is uncertain (higher degree wins for trend)", R.known_at)
    R.htf = out
    return out


def history(df, start, step=1, s=None, low=None, read_fn=None):
    """Invariant 7: प्रत्येक T (start…, step) ला `read(df[:T+1])` — label बदल log (known_at = T चा bar end). रिटर्न
    {"labels": {T: {leg key: label}}, "trend": {T: trend}, "log": [...]}."""
    from . import reader as RR                                           # reader → selfcheck (चक्र टाळण्यासाठी इथे)
    fn = read_fn or RR.read
    first = object()
    labels, trend, log, prev, prev_t = {}, {}, [], {}, first
    n = len(df)
    kat = Chart(df, s).kat if low is not None else None                 # bar T चा शेवट (खालच्या TF चे फक्त तोपर्यंत पूर्ण bars)
    for T in range(int(start), n, int(step)):
        lw = None if low is None else low[pd.to_datetime(low["timestamp"]) < kat[T]]
        R = fn(df.iloc[:T + 1], s=s, low=lw)
        cur = {lg.key: lg for lg in R.all_legs()}
        labels[T] = {k: lg.label for k, lg in cur.items()}
        t = R.trend_now()["trend"] if R.states else None
        trend[T] = t
        for k, lg in cur.items():
            if k in prev and prev[k] != lg.label:
                log.append({"known_at": R.known_at, "bar": T, "target": lg.name(), "from": prev[k], "to": lg.label,
                            "because": lg.reason, "text": f"relabelled {lg.name()}: {prev[k]} → {lg.label} because {lg.reason}"})
        if prev_t is not first and t != prev_t:
            why = R.states[-1]["why"]
            log.append({"known_at": R.known_at, "bar": T, "target": "trend", "from": prev_t, "to": t, "because": why,
                        "text": f"relabelled trend: {prev_t} → {t} because {why}"})
        prev, prev_t = {k: lg.label for k, lg in cur.items()}, t
    return {"labels": labels, "trend": trend, "log": log}
