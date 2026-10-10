"""थर 4 (zones2) — synthetic data फक्त, कुठलीही तारीख नाही (थर 4 §11)."""
import ast
import json
import os
from types import SimpleNamespace

import numpy as np
import pytest

from legs2 import ik2 as LI
from patterns2 import fold2 as F2
from patterns2 import momentum as MO
from tests.test_legs2 import DATE_RX_I
from tests.test_legs2_v2 import built
from zones2 import engine as ZE
from zones2 import layer as ZL
from zones2 import settings as ZS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S = ZS.load()


def _A(o, h, l, c):
    return {"o": np.array(o, float), "h": np.array(h, float), "l": np.array(l, float), "c": np.array(c, float)}


def test_band_direction_and_width_limits():
    A = _A([100, 105], [110, 106], [95, 104], [108, 105.5])
    p = SimpleNamespace(bar=0, kind="H", price=110.0)
    top, bot = ZE._band(A, p, 10.0, S)
    assert top == 110 and bot == pytest.approx(108)                             # [max(O, C), high], रुंदी 2 = 0.2 σ
    p2 = SimpleNamespace(bar=1, kind="L", price=104.0)
    top, bot = ZE._band(A, p2, 10.0, S)
    assert bot == 104 and top == pytest.approx(106)                             # 1 < 0.2 σ ⇒ 2 पर्यंत वाढ
    A3 = _A([100], [130], [95], [101])
    top, bot = ZE._band(A3, SimpleNamespace(bar=0, kind="H", price=130.0), 10.0, S)
    assert top - bot == pytest.approx(10.0)                                     # > 1 σ ⇒ कापा


def _z(top, bot, i, born=0, src="a"):
    return {"id": i, "top": top, "bottom": bot, "born": born, "src": src}


def test_linkage_order_independent_and_split_recursion():
    Z = object.__new__(ZE.Zones)
    Z.s = S
    atoms = [_z(101, 100, "a"), _z(101.4, 100.6, "b"), _z(106, 105.5, "c"), _z(103.5, 103, "d")]
    g1 = Z.cluster(atoms, 1.0)
    g2 = Z.cluster(list(reversed(atoms)), 1.0)
    norm = lambda gs: sorted(sorted(a["id"] for a in g) for g in gs)       # noqa: E731
    assert norm(g1) == norm(g2)
    chain = [_z(100 + 0.4 * k + 0.2, 100 + 0.4 * k, f"x{k}") for k in range(10)]   # सलग overlap ⇒ एक union 3.8 σ
    for g in Z.cluster(chain, 1.0):
        assert max(a["top"] for a in g) - min(a["bottom"] for a in g) <= 1.5 + 1e-9


def test_group_id_oldest_pivot_k_never_sets_id():
    g = [_z(1, 0, "kPDH5", born=1, src="k"), _z(1, 0, "p9H", born=9), _z(1, 0, "p4L", born=4)]
    assert ZE.Zones.gid(g) == "p4L"
    assert ZE.Zones.gid([_z(1, 0, "kPDH5", born=5, src="k"), _z(1, 0, "kPDL3", born=3, src="k")]) == "kPDL3"


@pytest.fixture(scope="module")
def world():
    m15, res, st, lg = built(11, trend=0.6)
    trk = {d: LI.Tracker(lg, st, d) for d in (1, 2)}
    f2 = F2.Fold(lg, trk[2])
    f2.run()
    f1 = F2.Fold(lg, trk[1], parent=f2)
    f1.run()
    Z = ZE.Zones(lg, st, trk).run(snap_bars=range(len(m15)))
    L = ZL.run(Z, f1, f2)
    return m15, res, st, lg, trk, f1, f2, Z, L


def test_births_d1_plus_only_and_known_at(world):
    m15, res, st, lg, trk, f1, f2, Z, L = world
    d1 = {(p.bar, p.kind): p for p in res["pivots"][1]}
    for a in Z.atoms:
        if a["src"] == "a":
            p = a["pivot"]
            assert (p.bar, p.kind) in d1 and a["born"] == p.confirm_bar
    for t, zs in Z.snap.items():
        for z in zs:
            for mid in z["members"]:
                at = next(a for a in Z.atoms if a["id"] == mid)
                assert at["born"] <= t


def test_states_and_events_order(world):
    *_, Z, L = world
    by = {}
    for e in Z.events:
        by.setdefault(e["id"], []).append(e)
    for i, evs in by.items():
        kinds = [e["type"] for e in evs]
        if "मेला" in kinds:
            assert "flip" in kinds and kinds.index("flip") < kinds.index("मेला")      # real break शिवाय भूमिका बदलत नाही


def test_truncation_zones_same(world):
    m15, res, st, lg, trk, f1, f2, Z, L = world
    from legs2 import measure2 as M2
    from swings2 import engine as SE
    from swings2 import structure as SST
    cut = len(m15) - 50
    r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
    st2, rr2 = SST.all_structure(r2)
    lg2 = M2.build(r2, None, rr=rr2)
    t2 = {d: LI.Tracker(lg2, st2, d) for d in (1, 2)}
    g2 = F2.Fold(lg2, t2[2])
    g2.run()
    g1 = F2.Fold(lg2, t2[1], parent=g2)
    g1.run()
    Z2 = ZE.Zones(lg2, st2, t2).run(snap_bars=range(cut + 1))
    L2 = ZL.run(Z2, g1, g2)
    for t in (cut - 40, cut - 11, cut):
        a = json.dumps([ZL.zone_json(z) for z in Z.snap[t]], default=str, sort_keys=True)
        b = json.dumps([ZL.zone_json(z) for z in Z2.snap[t]], default=str, sort_keys=True)
        assert a == b
        assert json.dumps(L[t], default=str, sort_keys=True) == json.dumps(L2[t], default=str, sort_keys=True)


def test_score_na_normalised_and_stars(world):
    *_, Z, L = world
    for zs in list(Z.snap.values())[-50:]:
        for z in zs:
            assert 0.0 <= z["score"] <= 1.0
            assert z["stars"] == (1 if z["score"] < S["star2"] else (2 if z["score"] < S["star3"] else 3))
            assert "touches" not in z["parts"]                                   # raw touches गुणात नाहीत


def test_k_area_rules(world):
    m15, res, st, lg, trk, f1, f2, Z, L = world
    for t, r in L.items():
        ka = r["k_area"]
        if ka["ans"] == "NA":
            continue
        I = trk[1].I_at(t)
        if ka.get("zone"):
            z = next(x for x in Z.snap[t] if x["id"] == ka["zone"])
            assert not (z["pivot_bar"] is not None and z["pivot_bar"] > I["end"].bar)       # self नाही
            if z["accept"]:
                assert ka["ans"] == "नाही"
            assert z["role"] == (ZE.SELLER if I["dir"] < 0 else ZE.BUYER)


def test_momentum_reemit_single_verdict(world):
    *_, Z, L = world
    got = [r["momentum"] for r in L.values() if r["momentum"]]
    assert got
    for m in got:
        assert m["item9_zone"] and len(m["items"]) == 12 and m["verdict"] in (MO.WEAK, MO.NOT, MO.UNCLEAR, MO.EARLY, MO.NA_V)


def test_profile_grid_and_poc():
    A = _A([0, 0, 0], [101, 101, 105], [100, 100, 104], [0, 0, 0])
    vol = np.array([10.0, 10.0, 1.0])
    poc, val, vah = ZE.profile(A, vol, [0, 1, 2], 10.0, S)
    assert 100 <= poc <= 101 and val <= poc <= vah
    assert ZE.profile(A, np.full(3, np.nan), [0, 1, 2], 10.0, S) is None


def test_confluence_round_and_extras():
    out = ZE.confluence(22500.4, 10.0, S, [("C = A", 22501.0), ("Fib 61.8", 22600.0)])
    assert "round 22500" in out and "C = A" in out and "Fib 61.8" not in out


def test_caption_and_script(world, tmp_path):
    from zones2 import charts as ZC
    m15, res, st, lg, trk, f1, f2, Z, L = world
    t = len(m15) - 1
    zmap = {z["id"]: z for z in Z.snap[t]}
    cap = ZC.caption(1, 5, m15["bar_end"].iloc[t], L[t], zmap)
    assert len(cap.splitlines()) <= 8 and len(cap.encode("utf-16-le")) // 2 <= 1024 and "_" not in cap
    assert "बाजू" in ZC.box_text(L[t], zmap)
    rows = ZC.rows(Z, L, t - 200, t)
    assert rows and "K area हो %" in rows[0]


def test_script_rerun_identical(tmp_path):
    import importlib.util

    import pandas as pd

    from tests.test_pivots_dc import SLOTS, _monday
    spec = importlib.util.spec_from_file_location("zc", os.path.join(ROOT, "scripts", "zone_check.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    rng = np.random.default_rng(8)
    rows, px = [], 20000.0
    for d in pd.bdate_range(_monday(900), periods=25):
        for t in pd.date_range(d + SLOTS[0], d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += rng.normal(0.05, 2.0)
            rows.append((t, o, max(o, px) + 0.5, min(o, px) - 0.5, px))
    data = tmp_path / "in.csv"
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(data, index=False)
    outs = []
    for k in ("a", "b"):
        od = tmp_path / k
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "zones2/t", "--days", "1",
                       "--futures-dir", str(tmp_path / "nofut")]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert outs[0] == outs[1] and outs[0]


def test_register_numbers_dates_shadow():
    reg = " ".join(ZS.REGISTER)
    for k in ZS.DEFAULTS:
        assert k in reg, k
    allowed = {0, 1, -1, 2, 3, 6, 9, 12, 15, 0.5, 1.0, 0.0, 0.33, 0.67, 0.7, 1000, 10}   # 6 = round अंक; 10 ** 12 = "कधीच नाही"
    for f in ("engine.py", "layer.py"):
        tree = ast.parse(open(os.path.join(ROOT, "zones2", f), encoding="utf-8").read())
        nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)}
        assert nums <= allowed, (f, nums - allowed)
    paths = [os.path.join(ROOT, "zones2", f) for f in os.listdir(os.path.join(ROOT, "zones2")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "zone_check.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits
    for p in paths[:-2]:
        src = open(p, encoding="utf-8").read()
        for bad in ("broker", "place_order", "market_state", "chart_reader", "levels_v2", "areas"):
            assert f"import {bad}" not in src and f"from {bad}" not in src


def _bare():
    Z = object.__new__(ZE.Zones)
    Z.s, Z.state, Z.owner, Z.events = S, {}, {}, []
    return Z


def _round(Z, groups, t):
    ids = Z.assign_ids(groups, t)
    for g, i in zip(groups, ids):
        if i not in Z.state:
            Z.state[i] = {"born": t, "id": i}
        for a in g:
            Z.owner[a["id"]] = i
    return ids


def test_zone_id_lineage_prune_merge_split():
    """Abhi निर्णय (04 §3): id बदलत नाही; merge ⇒ जुना id; split ⇒ मूळ pivot चा भाग; pruning ⇒ तोच id."""
    Z = _bare()
    a, b, c = _z(101, 100, "p1H", born=1), _z(101, 100.2, "p5H", born=5), _z(110, 109, "p7H", born=7)
    assert _round(Z, [[a, b], [c]], 10) == ["p1H", "p7H"]
    assert _round(Z, [[b]], 11) == ["p1H"]                                     # मूळ p1H pruning ⇒ तोच id (वंश)
    assert any(x["what"].startswith("वारसा") for x in Z.state["p1H"]["lineage"])
    _round(Z, [[b]], 11)
    assert sum(x["what"].startswith("वारसा") for x in Z.state["p1H"]["lineage"]) == 1     # एकदाच नोंद
    assert _round(Z, [[b, c]], 12) == ["p1H"]                                  # merge ⇒ जुना id
    assert any(e["type"] == "merge" and e["from"] == "p7H" for e in Z.events)
    Z2 = _bare()
    _round(Z2, [[a, b, c]], 10)
    ids = _round(Z2, [[c], [a, b]], 11)                                        # split ⇒ मूळ pivot (p1H) चा भाग id ठेवतो
    assert ids[1] == "p1H" and ids[0] != "p1H"
    assert any(e["type"] == "split" and e["id"] == "p1H" for e in Z2.events)


def test_real_zone_ids_never_reused_for_two_groups(world):
    m15, res, st, lg, trk, f1, f2, Z, L = world
    for t, zs in Z.snap.items():
        ids = [z["id"] for z in zs]
        assert len(ids) == len(set(ids))


def test_sessions_profile_needs_full_sessions_and_volume():
    A = _A([0] * 6, [101, 102, 103, 104, 105, 106], [100, 101, 102, 103, 104, 105], [0] * 6)
    import pandas as pd
    day = pd.Timestamp(0) + pd.to_timedelta(np.arange(6), unit="D")
    sess = {pd.Timestamp(d): [j] for j, d in enumerate(day)}
    vol = np.full(6, 10.0)
    s5 = dict(S, profile_sessions=5)
    assert ZE.sessions_profile(A, vol, day, sess, 5, 10.0, s5) is not None   # 5 आधीच्या पूर्ण sessions
    assert ZE.sessions_profile(A, vol, day, sess, 4, 10.0, s5) is None       # फक्त 4 ⇒ NA
    v2 = vol.copy()
    v2[2] = np.nan
    assert ZE.sessions_profile(A, v2, day, sess, 5, 10.0, s5) is None        # एका session मध्ये volume नाही ⇒ NA


def test_audit30_dead_and_flipped_groups_do_not_swallow_new_atoms():
    """Audit #30 (🔴): मेलेला / flip झालेला group नवा pivot / PDL गिळायचा ⇒ नवा zone जन्मताच dead. आता dead atoms clustering बाहेर,
    flipped group नव्या atoms शी जोडत नाही."""
    Z = _bare()
    old, new = _z(101, 100, "p1H", born=1), _z(101.2, 100.1, "p9H", born=9)
    _round(Z, [[old]], 5)
    Z.state["p1H"]["status"] = "flipped"
    g = Z.cluster([old, new], 1.0)
    assert sorted(sorted(a["id"] for a in x) for x in g) == [["p1H"], ["p9H"]]      # flipped ⇒ वेगळे
    Z.state["p1H"]["status"] = "dead"
    assert Z.owner_status(old) == "dead" and Z.owner_status(new) is None
    Z.state["p1H"]["status"] = "active"
    assert len(Z.cluster([old, new], 1.0)) == 1                                    # जिवंत ⇒ नेहमीसारखं merge


def test_audit31_deep_sweep_is_note_only_not_zone_sweep():
    """Audit #31 (🔴): > sweep_hi σ wick = deep_sweep (फक्त नोंद); `sweeps` (k_area "हो (sweep)" / score) मध्ये जात नाही."""
    Z = object.__new__(ZE.Zones)
    Z.s, Z.events = S, []
    Z.A = _A([100] * 4, [100, 103, 100.5, 100], [99] * 4, [100] * 4)
    Z.lg = {"vol": np.ones(4)}
    z = {"id": "z", "role": ZE.SELLER, "sweeps": [], "deep": []}
    Z._sweep(z, 1, 3.0, 1.0, 1)                                                     # 3σ wick ⇒ deep
    Z._sweep(z, 2, 0.5, 1.0, 2)                                                     # 0.5σ ⇒ zone_sweep
    assert [x["bar"] for x in z["deep"]] == [1] and [x["bar"] for x in z["sweeps"]] == [2]
    assert [e["type"] for e in Z.events] == ["deep_sweep", "zone_sweep"]
