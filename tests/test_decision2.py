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
    C.ext = {"vix": {t: 25.0}}                                                     # Abhi उत्तर 14: VIX gate नाही ⇒ फक्त size
    d = DE.decide(C, t)
    assert d["decision"] == DE.SETUP and d["size_weight"] == pytest.approx(S["size_floor"])
    C.ext = {"vix": {t: 20.0}}
    assert DE.decide(C, t)["size_weight"] == pytest.approx(0.75)
    C.ext = {"vix": {t: 15.0}, "event_bars": {t: "RBI policy"}}                   # event ⇒ size कमी, gate नाही
    d = DE.decide(C, t)
    assert d["decision"] == DE.SETUP and d["size_weight"] == pytest.approx(S["reduce_size"])
    assert d["points"]["11_context"]["event"] == "RBI policy"


def test_grade_determinism_and_macro_only_size(patched):
    C, t = fake_ctx()
    a, b = DE.decide(C, t), DE.decide(C, t)
    assert a["grade_score"] == b["grade_score"]
    C.ext = {"macro": {t: -0.8}}                                                   # macro_source = none (Abhi निर्णय 4) ⇒ परिणाम नाही
    n = DE.decide(C, t)
    assert n["size_weight"] == a["size_weight"] and n["grade_score"] == a["grade_score"] and "macro_source = none" in n["flags"]
    C, t = fake_ctx(overrides={"macro_source": "macro_daily"})
    a = DE.decide(C, t)
    C.ext = {"macro": {t: 1.0}}                                                    # trade-बाजूचा macro ⇒ काहीच बदल नाही
    c = DE.decide(C, t)
    assert c["decision"] == a["decision"] and c["grade_score"] == a["grade_score"] and c["size_weight"] == a["size_weight"]
    C.ext = {"macro": {t: -0.8}}                                                   # trade-विरुद्ध ⇒ फक्त size (gate / grade नाही)
    e = DE.decide(C, t)
    assert e["decision"] == a["decision"] and e["grade_score"] == a["grade_score"]
    assert e["size_weight"] == pytest.approx(max(a["size_weight"] * S["macro_size"], S["size_floor"]))


def test_tier2_needs_next_candle_confirm():
    C = mini([105, 104, 99.5, 103.0], [106, 105, 103.5, 106.0], [103, 101, 98.0, 102.5], [104, 102, 103.2, 105.0])
    area = {"band": (98.0, 100.0)}
    assert DE.commit_tier(C, 2, 1, area)["pass"]                                  # tier 1 (default): commitment candle
    C.s["tier"] = 2
    C.day = pd.Series([C.day[0]] * 4)
    r = DE.commit_tier(C, 3, 1, area)                                             # t−1 commitment + t close 105 > 103.5
    assert r["pass"] and r["tier2_confirm"] and r["entry"] == 105.0
    C.A["c"][3] = 103.0
    assert not DE.commit_tier(C, 3, 1, area)["pass"]
    C.A["c"][3] = 105.0
    C.day = pd.Series([C.day[0]] * 3 + [C.day[0] + pd.Timedelta(days=1)])
    assert DE.commit_tier(C, 3, 1, area) is None                                   # आदल्या session ची candle + आजची ⇒ नाही


def test_trendline_break_flavour_needs_area_within_n(patched):
    C, t = fake_ctx()
    C.L5[t] = {"k_base": {"bar": t}}
    C.L4[t]["k_area"]["band"] = (117.0, 119.0)                                     # break आधीच्या ≤ 6 candles मध्ये area स्पर्श
    d = DE.decide(C, t)
    assert "trendline-break" in d["points"]["9_price_failure"]["flavours"]
    C.L4[t]["k_area"]["band"] = (120.5, 121.0)                                     # फक्त break candle स्वतः स्पर्श करते ⇒ "आधी" नाही
    assert "trendline-break" not in DE.decide(C, t)["points"]["9_price_failure"]["flavours"]
    C.L4[t]["k_area"]["band"] = (117.0, 119.0)
    C.L4[t]["k_area"]["band"] = (60.0, 61.0)                                       # area ≤ 6 candles आधी नाही
    assert "trendline-break" not in DE.decide(C, t)["points"]["9_price_failure"]["flavours"]


def test_steep_line_lowers_grade(patched):
    C, t = fake_ctx()
    C.L4[t]["k_area"] = {"ans": "नाही"}
    C.res["sigma"] = {C.day[t]: 10.0}
    C.L5[t] = {"k_area_line": {"ans": "हो", "value": 100.0, "line": "H1-2"}}
    a = DE.decide(C, t)
    C.L5[t]["k_area_line"]["steep"] = True
    b = DE.decide(C, t)
    assert b["decision"] == a["decision"] == DE.SETUP and b["grade_score"] == pytest.approx(a["grade_score"] + S["w_steep"])


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


def test_context_rows_known_at(tmp_path):
    from decision2 import context as DX
    day = pd.bdate_range(_monday(700), periods=2)
    ts = pd.Series([d + SLOTS[i] for d in day for i in range(25)])
    be = ts + pd.Timedelta(minutes=15)
    vix = pd.DataFrame({"timestamp": [ts[0], ts[1], ts[30]], "close": [14.0, 15.0, 16.5]})
    v, j = DX.vix_map(vix, be)
    assert 0 in v and v[0] == 14.0 and v[1] == 15.0 and v[24] == 15.0 and v[30] == 16.5   # known_at = candle close
    assert 29 not in v                                                             # आदल्या session चा VIX ⇒ stale ⇒ NA
    assert j[30] == pytest.approx(16.5 / 15.0 - 1.0)
    vz = vix.assign(timestamp=pd.to_datetime(vix["timestamp"]).dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC"))
    assert DX.vix_map(vz, be)[0] == v                                              # tz-aware (UTC) ⇒ IST naive, तसंच
    p = tmp_path / "ev.yaml"
    d0, d1 = (str(x.date()) for x in day)
    p.write_text(f"events:\n  - {{date: {d1}, name: X, kind: rbi, added_on: {d0}}}\n  - {{date: {d0}, name: Y, kind: fomc, added_on: {d1}}}\n"
                 f"  - {{date: {d1}, name: Z, kind: expiry, added_on: {d0}}}\n",
                 encoding="utf-8")
    ev = DX.event_bars(DX.load_events(str(p)), ts)
    assert set(ev) == set(range(0, 50)) and ev[25] == "X" and ev[0] == "X"       # event दिवस + आधीचा session; Y: added_on नंतर; Z expiry ⇒ size नाही
    real = DX.load_events(DX.EVENTS_PATH)
    kinds = {e["kind"] for e in real}
    assert {"holiday", "expiry", "fomc", "rbi", "budget"} <= kinds
    assert all(e["verify"] for e in real if e["kind"] in ("fomc", "rbi"))
    assert DX.MacroDailyProvider().rows().empty and DX.MacroDailyProvider.source == "none"
    m = DX.macro_map(pd.DataFrame({"fetched_at": [be[3]], "value": [0.4]}), be)
    assert 2 not in m and m[3] == 0.4
    m2 = DX.macro_map(pd.DataFrame({"fetched_at": [be[3]], "value": [0.4]}), be, max_age_h=1)
    assert 3 in m2 and 10 not in m2                                                # 1 तासापेक्षा जुनी ⇒ NA


def test_vision_run_budget_uses_existing_caps():
    g = {"visual_audit_daily_cap": 0.10, "vision_daily_budget_usd": 0.30}
    assert VV.run_budget(g) == pytest.approx(0.10) and VV.run_budget(None) is None
    assert VV.MODEL_TASK == "veto"


def test_range_mode_area_options(monkeypatch):
    """Abhi batch 2 निर्णय 2: range mode area = (a) कडेचा zone (+1) / (b) ★ ≥ 2 zone बाहेरच्या तृतीयांशात / (c) trade-योग्य रेघ त्याच
    तृतीयांशात; मधला तृतीयांश ⇒ नाही."""
    C, t = fake_ctx()
    C.res["sigma"] = {C.day[t]: 10.0}
    band = (130.0, 100.0)                                                         # top, bot; d > 0 ⇒ खालचा तृतीयांश 100–110
    l4 = {"range_zone_bands": [(118.0, 122.0, "buyer")], "k_area": {"ans": "हो", "band": (104.0, 106.0), "stars": 2, "zone": "z"}}
    a = DE.range_area(C, t, 1, band, l4, {})
    assert a["src"] == "range-कड zone" and a.get("range_edge")                     # (a) प्राधान्य
    l4["range_zone_bands"] = []
    assert DE.range_area(C, t, 1, band, l4, {})["src"] == "zone (बाहेरचा तृतीयांश)"  # (b)
    l4["k_area"]["stars"] = 1
    assert DE.range_area(C, t, 1, band, l4, {}) is None                           # ★ 1 ⇒ नाही
    l4["k_area"] = {"ans": "हो", "band": (114.0, 116.0), "stars": 3}
    assert DE.range_area(C, t, 1, band, l4, {}) is None                           # मधला तृतीयांश ⇒ नाही
    l5 = {"k_area_line": {"ans": "हो (sweep)", "value": 107.0, "line": "L1-2"}}
    assert DE.range_area(C, t, 1, band, l4, l5)["src"] == "रेघ (बाहेरचा तृतीयांश)"   # (c)
    l5["k_area_line"]["value"] = 125.0
    assert DE.range_area(C, t, 1, band, l4, l5) is None
    g0 = DE.grade(C, t, 1, {"stars": 1}, {"g4_both": False}, [], {}, {}, {}, {}, False)
    g1 = DE.grade(C, t, 1, {"stars": 1, "range_edge": True}, {"g4_both": False}, [], {}, {}, {}, {}, False)
    assert g1 == pytest.approx(g0 + S["w_range_edge"])
