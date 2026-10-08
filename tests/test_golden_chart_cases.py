"""V2 golden chart cases: tests/golden_chart_cases/*.json (अपेक्षा) × trade-data candles. Data नसेल ⇒ skip (CI).

प्रत्येक window bar वर market_state.read (trend / impulse / correction / side); active_area आणि checkpoints साठी chart_reader.evaluate.
"""
import glob
import json
import os

import pandas as pd
import pytest

import market_state as MS

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = sorted(glob.glob(os.path.join(HERE, "golden_chart_cases", "*.json")))
TRADE_DATA = os.environ.get("TRADE_DATA", "/home/user/trade-data")
DIR = {"up": 1, "down": -1}
_CACHE = {}


def _data(rel):
    p = os.path.join(TRADE_DATA, rel)
    if not os.path.exists(p):
        pytest.skip(f"trade-data नाही: {rel}")
    if p not in _CACHE:
        _CACHE[p] = pd.read_csv(p, parse_dates=["timestamp"])
    return _CACHE[p]


def _near(a, b, tol):
    return a is not None and abs(float(a) - float(b)) <= tol


def _times(case):
    w = case["window"]
    return list(pd.date_range(w["from"], w["to"], freq=f"{int(w.get('step_min', 15))}min"))


def _check_ms(ms, ex, tol, t):
    errs = []
    tr = ex.get("trend")
    if tr:
        if ms["trend"]["dir"] != DIR[tr["dir"]]:
            errs.append(f"{t}: trend {ms['trend']['dir']} ≠ {tr['dir']}")
        if "protected" in tr and not _near((ms["trend"].get("protected") or {}).get("price"), tr["protected"], tol):
            errs.append(f"{t}: protected {ms['trend'].get('protected')} ≠ ~{tr['protected']}")
    im = ex.get("impulse")
    if im:
        i = ms.get("impulse")
        if not i:
            errs.append(f"{t}: impulse नाही")
        else:
            if i["dir"] != DIR[im["dir"]]:
                errs.append(f"{t}: impulse dir {i['dir']}")
            if not _near(i["from"], im["from"], tol) or not _near(i["to"], im["to"], tol):
                errs.append(f"{t}: impulse {i['from']}→{i['to']} ≠ ~{im['from']}→{im['to']}")
    co = ex.get("correction")
    if co:
        c = ms.get("correction") or {}
        labels = [x["label"] for x in c.get("labels") or []]
        if "labels" in co and labels[:len(co["labels"])] != co["labels"]:
            errs.append(f"{t}: correction labels {labels} ≠ {co['labels']}")
        if "c_top_range" in co:
            ctop = next((x["to"] for x in c.get("labels") or [] if x["label"] == "C"), None)
            lo, hi = co["c_top_range"]
            if ctop is None or not lo - tol <= ctop <= hi + tol:
                errs.append(f"{t}: C top {ctop} ∉ {co['c_top_range']}")
        if "status_in" in co and c.get("status") not in co["status_in"]:
            errs.append(f"{t}: correction status {c.get('status')} ∉ {co['status_in']}")
    if "side_in" in ex and ms["side"] not in ex["side_in"]:
        errs.append(f"{t}: side {ms['side']} ∉ {ex['side_in']} ({'; '.join(ms['side_reasons'])})")
    if "side" in ex and ms["side"] != ex["side"]:
        errs.append(f"{t}: side {ms['side']} ≠ {ex['side']} ({'; '.join(ms['side_reasons'])})")
    return errs


def _check_area(r, aa, tol, t):
    errs = []
    a = (r.get("active") or {}).get("area")
    if not a:
        return [f"{t}: active area नाही"]
    cands = {z["id"]: z for z in r["areas"]["candidates"]}
    tl = cands.get(a["id"], a)
    if aa.get("tool") and a.get("tool") != aa["tool"]:
        errs.append(f"{t}: active area tool {a.get('tool')} ({a['id']}) ≠ {aa['tool']}")
        return errs
    if aa.get("slope") == "down" and not (tl.get("slope", 0) < 0):
        errs.append(f"{t}: trendline slope {tl.get('slope')} उतरती नाही")
    if "value_range" in aa:
        lo, hi = aa["value_range"]
        v = tl.get("value", (a["low"] + a["high"]) / 2)
        if not lo - tol <= v <= hi + tol:
            errs.append(f"{t}: area value {v:.1f} ∉ {aa['value_range']}")
    for day, px in aa.get("anchors_near") or []:
        if not any(str(an[0]).startswith(day) and abs(an[1] - px) <= 2 * tol for an in tl.get("anchors") or []):
            errs.append(f"{t}: anchor {day} ~{px} नाही ({tl.get('anchors')})")
    return errs


WINDOW_CASES = [c for c in CASES if "window" in json.load(open(c, encoding="utf-8"))]


@pytest.mark.parametrize("path", WINDOW_CASES, ids=[os.path.basename(p) for p in WINDOW_CASES])
def test_golden_chart_case(path):
    case = json.load(open(path, encoding="utf-8"))
    df = _data(case["data"])
    tol = float(case.get("tolerance_pts", 15))
    ex = case.get("expect", {})
    errs = []
    from chart_reader import evaluate as EV
    from chart_reader import settings as CS
    s = CS.load()
    for t in _times(case):
        ms = MS.read(df, t)
        errs += _check_ms(ms, ex, tol, t)
        if ex.get("active_area"):
            r = EV.evaluate(df[df["timestamp"] >= t - pd.Timedelta(days=90)], "srv2", t, s=s)
            errs += _check_area(r, ex["active_area"], tol, t)
            if "side" in ex and r["side"] != DIR["down" if ex["side"] == "bear_call" else "up"]:
                errs.append(f"{t}: chart_reader side {r['side']}")
    for cp in case.get("checkpoints") or []:
        t = pd.Timestamp(cp["at"])
        ms = MS.read(df, t)
        labels = [x["label"] for x in (ms.get("correction") or {}).get("labels") or []]
        if "correction_labels" in cp and labels != cp["correction_labels"]:
            errs.append(f"{cp['id']} {t}: labels {labels} ≠ {cp['correction_labels']}")
        if cp.get("no_entry_side"):
            r = EV.evaluate(df[df["timestamp"] >= t - pd.Timedelta(days=90)], "srv2", t, s=s)
            bad = DIR["down" if cp["no_entry_side"] == "bear_call" else "up"]
            if r["entry"] and r["side"] == bad:
                errs.append(f"{cp['id']} {t}: {cp['no_entry_side']} entry झाली ({cp['why']})")
    assert not errs, "\n".join(errs)


DAY_CASES = [c for c in CASES if "simple_core_day" in json.load(open(c, encoding="utf-8"))]


@pytest.mark.parametrize("path", DAY_CASES, ids=[os.path.basename(c)[:-5] for c in DAY_CASES])
def test_golden_simple_core_day(path):
    """Simple Core (Abhi 2026-10-08): दिवसभर प्रत्येक बंद 15M bar वर signal_at (trendline memory + एक setup = एक entry) ⇒ signals फक्त
    अपेक्षित वेळांवर; pause अपेक्षित वेळेपासून; area अपेक्षित पट्टा सामावतो; trendline ओळख स्थिर."""
    from chart_reader import setups as SU
    from simple_core import engine as EN
    case = json.load(open(path, encoding="utf-8"))
    de = case["simple_core_day"]
    m1 = _data(case["data"])
    day = pd.Timestamp(de["date"])
    m1 = m1[pd.to_datetime(m1["timestamp"]) >= day - pd.Timedelta(days=110)]
    mem, tr = SU.LineMemory(), EN.Tracker()
    got, tl = {}, {}
    for t in pd.date_range(f"{de['date']} {de['from']}", f"{de['date']} {de['to']}", freq="15min"):
        r = EN.signal_at(m1, t + pd.Timedelta(minutes=15), memory=mem, tracker=tr)
        hm = f"{t:%H:%M}"
        tl[hm] = next((z for z in r.get("zones") or [] if z.get("tool") == "f" and z.get("role") == "RESISTANCE" and z.get("tl_reason")), None)
        if r["signal"]:
            got[hm] = r["signal"]
    assert {k: v["side"] for k, v in got.items()} == de["signals"], f"signals {list(got)}"
    assert not set(de["no_signal"]) & set(got)
    for hm in de["signals"]:
        sg = got[hm]
        if de.get("pause_from_max"):
            assert sg["pause_from"][11:16] <= de["pause_from_max"], sg["pause_from"]
        if de.get("area_contains"):
            lo, hi = de["area_contains"]
            assert sg["area"]["low"] <= lo and sg["area"]["high"] >= hi, sg["area"]
        if (de.get("setups") or {}).get(hm):
            assert sg.get("setup") == de["setups"][hm], f"{hm}: setup {sg.get('setup')}"
    st = de.get("same_trendline") or {"at": []}
    for hm in st["at"]:
        z = tl.get(hm) or {}
        assert z.get("id") == st["id"], f"{hm}: trendline {z.get('id')} ≠ {st['id']}"
        for (day_, px), (ts, v) in zip(st["anchors_near"], z["anchors"]):
            assert str(ts).startswith(day_) and abs(float(v) - px) <= 15, f"{hm}: anchor {ts} {v}"
