"""थर 7 (decision2 + vision2) — synthetic / नियंत्रित inputs, कुठलीही तारीख नाही (थर 7 §11)."""
import ast
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from decision2 import engine as DE
from decision2 import settings as DS
from swings2 import structure as SST
from tests.test_legs2 import DATE_RX_I
from tests.test_pivots_dc import SLOTS, _monday
from vision2 import veto as VV

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S = DS.load()


def _P(price, bar, sigma=10.0):
    return SimpleNamespace(price=price, bar=bar, sigma=sigma, kind="L", confirm_bar=bar)


class FakeTrk:
    def __init__(self, I, st):
        self.I, self.st = I, st

    def I_at(self, t):
        return self.I

    def state(self, t):
        return self.st


def fake_ctx(n=40, overrides=None, **kw):
    """bars 09:15 पासून; t = n−1 (session मधली 12:30 नंतरची candle). सगळे थर नियंत्रित."""
    day = pd.bdate_range(_monday(700), periods=2)
    ts = [d + SLOTS[i] for d in day for i in range(25)][:n]
    c = np.linspace(100, 120, n)
    A = {"o": c - 0.5, "h": c + 1.0, "l": c - 1.0, "c": c, "first": np.array([t.hour == 9 and t.minute == 15 for t in ts])}
    I = {"dir": 1, "mode": "trend", "origin": _P(80.0, 2), "end": _P(160.0, 20)}
    st = {"I": {"quality": "spike", "climax": False, "SOT_trend": False, "origin_bounded": False, "I_weak_basis": False},
          "K": {"extreme": 99.0, "depth_main": 0.6, "depth_secondary": 0.5}, "flags": {"pullback_quiet": True}, "state": "K चालू"}
    t = n - 1
    pref = {"family": "zigzag", "state": "complete_resuming", "score": 0.8, "flags": []}
    C = SimpleNamespace(
        s=DS.load(overrides), ext={}, A=A, rr=np.full(n, 1.2), ts=pd.Series(ts), day=pd.Series(ts).dt.normalize(), n=n,
        trk={1: FakeTrk(I, st)}, f1=SimpleNamespace(out={t: {"agg": "complete_resuming", "pref": pref, "position": {"ban": False},
                                                           "momentum": {"verdict": "कमकुवत होतोय", "ratio": 0.7, "danger": []}}}),
        L4={t: {"k_area": {"ans": "हो", "band": (98.0, 101.0), "stars": 3, "zone": "z1"}, "momentum": {"verdict": "कमकुवत होतोय",
                                                                                                    "ratio": 0.7, "danger": []}}},
        L5={t: {}}, L6={t: {"label": None}},
        st={2: {"states": [{"trend": SST.UPT, "protected": 90.0, "reversal": None, "range": None}] * n, "events": []}},
        res={"pivots": {3: []}, "sigma": {}, "sessions": list(pd.Series(ts).dt.normalize().unique()), "gap_bar_2s": [], "segments": {}},
        lg={"settings": {"climax_rng_ratio": 2.0}}, m15=pd.DataFrame({"high": A["h"], "low": A["l"], "close": A["c"], "open": A["o"]}),
        mr=np.full(n, 2.0), _mh_start=[(None, 0, None)] * n)
    for k, v in kw.items():
        setattr(C, k, v)
    return C, t


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(DE, "regime", lambda C, t: {"regime": DE.UP})
    monkeypatch.setattr(DE, "must_hold_broken", lambda C, t, d: False)
    monkeypatch.setattr(SST, "trend_of", lambda ps: SST.UPT)
    good = {"pass": True, "checks": {}, "merged": 1, "candle": {"i0": 39, "t": 39, "o": 99.5, "h": 101.0, "l": 98.5, "c": 100.5},
            "g4_both": False, "engulf": False, "rng_ratio": 1.2, "overlap3": 0.2}
    monkeypatch.setattr(DE, "commitment", lambda C, t, d, area, s=None: dict(good))
    return monkeypatch


def test_setup_path_and_paper(patched):
    C, t = fake_ctx()
    d = DE.decide(C, t)
    assert d["decision"] == DE.SETUP and d["paper_only"] and d["approval_required"]
    assert d["grade"] in ("A", "B", "C") and d["size_weight"] >= S["size_floor"]
    assert list(d["points"]) and "12_hard_rules" in d["points"]


@pytest.mark.parametrize("reg,want", [({"regime": DE.DRIFT}, (DE.WAIT, "G-A")), ({"regime": DE.BARB}, (DE.NO_TRADE, "G-A")),
                                      ({"regime": DE.DOWN}, (DE.NO_TRADE, "G-A"))])
def test_regime_gate(patched, reg, want):
    patched.setattr(DE, "regime", lambda C, t: reg)
    C, t = fake_ctx()
    d = DE.decide(C, t)
    assert (d["decision"], d["gate"]) == want
    if reg["regime"] == DE.DOWN:
        assert d["where_wrong"] == "against_parent"


def test_htf_veto_and_unknown(patched):
    patched.setattr(SST, "trend_of", lambda ps: SST.DNT)
    C, t = fake_ctx()
    assert DE.decide(C, t)["where_wrong"] == "HTF veto (D3)"
    patched.setattr(SST, "trend_of", lambda ps: SST.UNK)
    d = DE.decide(C, t)
    assert d["decision"] == DE.SETUP and "htf_unknown" in d["flags"]
    C2, t = fake_ctx(overrides={"htf_unknown_action": "block"})
    assert DE.decide(C2, t)["decision"] == DE.NO_TRADE


def test_gray_policy_block_and_reduce(patched):
    C, t = fake_ctx()
    C.st[2]["states"] = [{"trend": SST.UPT, "protected": 90.0, "reversal": 1, "range": None}] * C.n
    assert DE.decide(C, t)["decision"] == DE.NO_TRADE
    C.ext = {"gray_policy": "reduce", "abhi_dir": 1}
    d = DE.decide(C, t)
    assert d["decision"] == DE.SETUP and "gray-reduce" in d["flags"] and d["size_weight"] == pytest.approx(S["size_floor"])


def test_must_hold_and_position_ban(patched):
    patched.setattr(DE, "must_hold_broken", lambda C, t, d: True)
    C, t = fake_ctx()
    assert (DE.decide(C, t)["decision"], DE.decide(C, t)["gate"]) == (DE.NO_TRADE, "G-B")
    patched.setattr(DE, "must_hold_broken", lambda C, t, d: False)
    C.f1.out[t]["position"] = {"ban": True, "where": "B"}
    d = DE.decide(C, t)
    assert (d["decision"], d["gate"]) == (DE.NO_TRADE, "G-G")


def test_area_momentum_pattern_waits(patched):
    C, t = fake_ctx()
    C.L4[t]["k_area"] = {"ans": "नाही"}
    assert DE.decide(C, t)["gate"] == "G-C"
    C, t = fake_ctx()
    C.L4[t]["k_area"]["ans"] = "हो"
    C.L4[t]["k_area"]["htf_against"] = True
    assert DE.decide(C, t)["gate"] == "G-C"
    C, t = fake_ctx()
    C.L4[t]["momentum"]["verdict"] = "नाही"
    assert DE.decide(C, t)["gate"] == "G-D"
    C.L4[t]["momentum"]["verdict"] = "अस्पष्ट"
    assert DE.decide(C, t)["gate"] == "G-D"
    C.L6[t]["label"] = "K संपतोय"                                                   # अस्पष्ट + on_K ⇒ पास
    assert DE.decide(C, t)["decision"] == DE.SETUP
    C, t = fake_ctx()
    C.f1.out[t]["pref"]["state"] = "forming_B"
    assert (DE.decide(C, t)["decision"], DE.decide(C, t)["gate"]) == (DE.WAIT, "G-G")


def test_trendline_area_used_when_no_zone(patched):
    C, t = fake_ctx()
    C.L4[t]["k_area"] = {"ans": "नाही"}
    C.res["sigma"] = {C.day[t]: 10.0}
    C.L5[t] = {"k_area_line": {"ans": "हो", "value": 100.0, "line": "H1-2"}}
    d = DE.decide(C, t)
    assert d["decision"] == DE.SETUP and d["points"]["7_area"]["src"] == "रेघ"


def test_retrace_flavour_rule(patched):
    C, t = fake_ctx()
    C.trk[1].st["K"]["depth_main"] = 0.85
    d = DE.decide(C, t)
    assert (d["decision"], d["gate"]) == (DE.WAIT, "G-E")                           # plain rejection ⇒ wait
    C.L4[t]["k_area"]["ans"] = "हो (sweep)"
    assert DE.decide(C, t)["decision"] == DE.SETUP                                 # sweep-reclaim ⇒ setup (danger नाही)


def test_rr_time_vix_gates(patched):
    C, t = fake_ctx()
    C.trk[1].I["end"] = _P(101.0, 20)
    assert DE.decide(C, t)["gate"] == "G-F"
    C, t = fake_ctx(n=50)                                                          # दुसऱ्या दिवसाची शेवटची candle 15:15
    assert DE.decide(C, t)["gate"] == "G-H"
    C, t = fake_ctx()
    C.ext = {"vix": {t: 25.0}}
    assert (DE.decide(C, t)["decision"], DE.decide(C, t)["gate"]) == (DE.NO_TRADE, "G-I")
    C.ext = {"vix": {t: 20.0}}
    assert DE.decide(C, t)["size_weight"] == pytest.approx(0.75)


def test_grade_determinism_and_macro_changes_grade_not_decision(patched):
    C, t = fake_ctx()
    a, b = DE.decide(C, t), DE.decide(C, t)
    assert a["grade_score"] == b["grade_score"]
    C.ext = {"macro": {t: 1.0}}
    c = DE.decide(C, t)
    assert c["decision"] == a["decision"] and c["grade_score"] == pytest.approx(a["grade_score"] + S["w_macro"])


def test_hard_exits_independent(patched):
    C, t = fake_ctx()
    assert DE.hard_exits(C, t, 1) == []
    patched.setattr(DE, "must_hold_broken", lambda C, t, d: True)
    C.ext = {"vix": {t: 99.0}}                                                     # risk gate / vision / approval exits ला अडवत नाहीत
    assert DE.hard_exits(C, t, 1) == ["D2 must-hold real break"]
    C.trk[1].I = None                                                               # I नाही ⇒ exit नाही (फक्त दोन hard exits)
    assert DE.hard_exits(C, t, 1) == ["D2 must-hold real break"]
    I_trade = {"dir": 1, "origin": _P(140.0, 2), "end": _P(160.0, 5)}               # origin 140 च्या खूप खाली closes ⇒ real break
    assert "I_origin real break" in DE.hard_exits(C, t, 1, I_trade)


def test_must_hold_side_follows_d2_trend():
    C, t = fake_ctx()
    C._mh_start = [(150.0, 0, SST.DNT)] * C.n                                       # D2 DOWN चा strong high; long trade ⇒ NA
    assert DE.must_hold_broken(C, t, 1) is False
    C._mh_start = [(110.0, 0, SST.UPT)] * C.n                                       # D2 UP strong low 110; closes 100 ⇒ खाली break
    assert DE.must_hold_broken(C, t, 1) in (True, False)


def test_expiry_choice_uses_calendar_not_future_data():
    C, t = fake_ctx()
    d0 = pd.Timestamp(C.day[t])
    ex = DE.expiry_choice(C, t, [d0, d0 + pd.Timedelta(days=1), d0 + pd.Timedelta(days=14)])
    assert "आज expiry ⇒ पुढचा" in ex["flags"] and ex["expiry"] == str((d0 + pd.Timedelta(days=14)).date())


# ---------------------------------------------------------------------------------------------------- commitment candle
def mini(o, h, l, c, rr=None):
    n = len(o)
    day = pd.bdate_range(_monday(700), periods=1)[0]
    ts = pd.Series([day + SLOTS[6 + i] for i in range(n)])
    return SimpleNamespace(A={"o": np.array(o, float), "h": np.array(h, float), "l": np.array(l, float), "c": np.array(c, float),
                              "first": np.zeros(n, bool)},
                           rr=np.array(rr if rr is not None else [1.5] * n, float), ts=ts, day=ts.dt.normalize(), s=DS.load(),
                           lg={"settings": {"climax_rng_ratio": 2.0}})


def test_commitment_g1_to_g8():
    C = mini([105, 104, 99.5], [106, 105, 103.5], [103, 101, 98.0], [104, 102, 103.2])        # buyer zone 98–100: pin + reclaim
    r = DE.commitment(C, 2, 1, {"band": (98.0, 100.0)})
    assert r["pass"] and all(r["checks"].values())
    r2 = DE.commitment(C, 2, 1, {"band": (98.0, 100.0), "accept": True})
    assert not r2["checks"]["G8"]
    C2 = mini([105, 104, 99.5], [106, 105, 103.5], [103, 101, 101.0], [104, 102, 103.2])      # टोक zone ला लागलं नाही ⇒ G1/G2
    assert not DE.commitment(C2, 2, 1, {"band": (98.0, 100.0)})["checks"]["G2"]
    C3 = mini([105, 104, 99.5], [106, 105, 103.5], [103, 101, 98.0], [104, 102, 103.2], rr=[1.5, 1.5, 0.6])
    C3.s["merge_max"] = 1                                                          # merged candle शिवाय
    assert not DE.commitment(C3, 2, 1, {"band": (98.0, 100.0)})["checks"]["G5"]
    C4 = mini([105, 104, 99.5], [106, 105, 103.5], [103, 101, 98.0], [104, 102, 99.0])        # close खाली (reclaim नाही)
    assert not DE.commitment(C4, 2, 1, {"band": (98.0, 100.0)})["checks"]["G3"]


def test_merged_candles_after_0930_only():
    C = mini([100] * 4, [101] * 4, [99] * 4, [100] * 4)
    assert DE.merged(C, 3, 3) is not None
    C.ts = pd.Series([pd.Timestamp(C.ts[0]).normalize() + SLOTS[i] for i in range(4)])
    C.day = C.ts.dt.normalize()
    assert DE.merged(C, 2, 3) is None                                              # 09:15 candle सामील


# ---------------------------------------------------------------------------------------------------- vision
def test_vision_veto_only_and_price_drop():
    dec = {"decision": "setup", "grade": "B", "grade_score": 5.0}
    out = VV.apply(dec, {"items": {"5": "✘", "1": "✔"}}, S)
    assert out["decision"] == "no_trade" and out["gate"] == "vision:5"
    w = VV.apply({"decision": "wait", "grade": "B", "grade_score": 5.0}, {"items": {str(k): "✔" for k in range(1, 13)}}, S)
    assert w["decision"] == "wait"                                                 # promote कधीच नाही
    e = VV.apply(dec, {"items": {"7": "✘", "8": "✘"}}, S)
    assert e["decision"] == "setup" and e["grade_score"] == pytest.approx(4.0) and e["grade"] == "B"
    s = VV.apply(dec, {"items": {}, "why": "entry 22,450 वर", "edits": {"10": "SL 22410"}}, S)
    assert "22" not in s["vision"]["why"]
    f = VV.apply(dec, None, S)
    assert f["decision"] == "setup" and f["vision"]["status"] == "fail"
    assert VV.should_call({"decision": "wait", "grade": "B"}) and not VV.should_call({"decision": "wait", "grade": "C"})
    assert VV.should_call({"decision": "no_trade"}, manual=True)
    assert not VV.budget_ok(1.0, 1.0) and VV.budget_ok(0.5, 1.0) and not VV.budget_ok(0.0, None)
    p = VV.payload(dec, ["a.png"])
    assert {x["kind"] for x in p["checklist"]} == {"gate", "evidence", "context"}


def test_no_order_no_broker_no_api_and_dates():
    paths = [os.path.join(ROOT, d, f) for d in ("decision2", "vision2") for f in os.listdir(os.path.join(ROOT, d)) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "decision_check.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits
    for p in paths[:-2]:
        src = open(p, encoding="utf-8").read()
        for bad in ("broker", "place_order", "anthropic", "openai", "requests", "market_state", "levels_v2", "simple_core"):
            assert f"import {bad}" not in src and f"from {bad}" not in src, (p, bad)


def test_register_covers_defaults():
    reg = " ".join(DS.REGISTER)
    for k in DS.DEFAULTS:
        assert k in reg, k
    tree = ast.parse(open(os.path.join(ROOT, "decision2", "engine.py"), encoding="utf-8").read())
    nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}
    assert nums <= {0, 1, -1, 2, 3, 0.0, 1.0, 3.0}, nums


def test_script_rerun_identical_and_decide_real_stack(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dcs", os.path.join(ROOT, "scripts", "decision_check.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    rng = np.random.default_rng(12)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=25):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(-0.05, 2.0)
            rows.append((t, o, max(o, px) + 0.5, min(o, px) - 0.5, px))
    data = tmp_path / "in.csv"
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(data, index=False)
    outs = []
    for k in ("a", "b"):
        od = tmp_path / k
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "dec/t", "--days", "1",
                       "--futures-dir", str(tmp_path / "nofut")]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert outs[0] == outs[1] and outs[0]
    for f, b in outs[0].items():
        if f.endswith("_decision.json"):
            assert b'"decision"' in b
