"""थर 5 (trendlines2) — synthetic data फक्त, कुठलीही तारीख नाही (थर 5 §8)."""
import ast
import json
import os

import numpy as np
import pandas as pd
import pytest

from elliott import breaks as BR
from legs2 import ik2 as LI
from patterns2 import fold2 as F2
from tests.test_legs2 import DATE_RX_I
from tests.test_legs2_v2 import built
from trendlines2 import engine as TE
from trendlines2 import layer as TL
from trendlines2 import settings as TS
from zones2 import engine as ZE
from zones2 import layer as ZL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def mini(h, l, c=None, o=None, sigma=10.0):
    """हाताने बनवलेल्या bars वर Engine (σ ठरलेला, θ_D0 = 2 σ)."""
    n = len(h)
    c = list(c) if c is not None else [(a + b) / 2 for a, b in zip(h, l)]
    o = list(o) if o is not None else [c[0]] + c[:-1]
    E = object.__new__(TE.Engine)
    E.A = {"o": np.array(o, float), "h": np.array(h, float), "l": np.array(l, float), "c": np.array(c, float)}
    E.n = n
    E.s = TS.load()
    E.es = dict(TE.LINE_BREAK)
    E.m15 = pd.DataFrame({"open": E.A["o"], "high": E.A["h"], "low": E.A["l"], "close": E.A["c"]})
    E.mr = np.full(n, 4.0)
    E.k0 = 2.0
    E.sig = np.full(n, sigma)
    E.ts = pd.Series(pd.to_datetime(np.arange(n) * 900, unit="s"))
    E.lines = {}
    E.steep = {}
    return E


def test_beyond_equals_breaks():
    for c in (99.0, 100.0, 101.0, 102.5):
        for side in ("above", "below"):
            assert TE.beyond_buf(c, 100.0, 1.0, side) == BR._beyond(c, 100.0, 1.0, side)


def test_validity_close_beyond_wick_ok_slope_spacing():
    h = [200, 150, 150, 150, 150, 150, 150, 190, 150, 150]
    l = [x - 5 for x in h]
    c = [x - 2 for x in h]
    E = mini(h, l, c)
    L = E.make((0, 200.0), (7, 190.0), "H", 7)
    assert L.valid0
    h2 = list(h)
    c2 = list(c)
    h2[4], c2[4] = 205, 200                                                     # close 200 > रेघ (~197) + 3 ⇒ अवैध
    E2 = mini(h2, l, c2)
    assert E2.make((0, 200.0), (7, 190.0), "H", 7).why == "anchors मध्ये close पलीकडे"
    h3 = list(h)
    h3[4] = 205                                                                 # फक्त wick ⇒ वैध
    assert mini(h3, l, c).make((0, 200.0), (7, 190.0), "H", 7).valid0
    assert mini(h, l, c).make((0, 200.0), (3, 190.0), "H", 3).why == "spacing"
    assert mini(h, l, c).make((0, 200.0), (7, 100.0), "H", 7).why == "तीव्र (slope)"


def test_touch_visit_continuity_held_and_flat():
    # रेघ 200 ⇒ 186 (slope −2); तिसरी भेट: अनेक candles चिकटून ⇒ एक touch; held = θ_D0 (20) दूर
    n = 40
    h = [170.0] * n
    l = [150.0] * n
    h[0], h[7] = 200, 186
    for i in range(15, 22):                                                    # रेघेजवळ चिकटून (18 ला थोडं दूर, 19 ला परत)
        h[i] = 200 - 2 * i + (0.5 if i != 18 else -4.0)
        l[i] = h[i] - 6
    l[25] = 150 - 100
    E = mini(h, l, [x - 1 for x in l])
    L = E.make((0, 200.0), (7, 186.0), "H", 7)
    starts = [x["start"] for x in L.held]
    assert starts[:2] == [0, 7]
    assert len([s for s in starts if s >= 15]) <= 1
    flat = mini([100.0] * 20, [90.0] * 20).make((0, 100.0), (10, 99.99), "H", 10)
    assert flat.flat


def test_detrended_break_flip_and_demark():
    n = 60
    v = lambda i: 200 - 1.0 * i                                                 # noqa: E731
    h = [v(i) - 3 for i in range(n)]
    l = [v(i) - 25 for i in range(n)]
    c = [v(i) - 10 for i in range(n)]
    o = [v(i) - 12 for i in range(n)]
    h[0], h[10] = 200, 190
    for i in range(30, n):                                                      # break: रेघेपलीकडे सलग closes
        h[i], c[i], o[i], l[i] = v(i) + 30, v(i) + 25, v(i) + 22, v(i) + 15
    o[30], c[29], o[29] = v(30) - 5, v(29) - 15, v(29) - 10                     # Q1: आधीची candle लाल
    E = mini(h, l, c, o)
    L = E.make((0, 200.0), (10, 190.0), "H", 10)
    assert L.valid0 and L.cb is not None and L.cb >= 30
    F = E.detrended(L)
    assert BR.first_real_break(F, 11, 0.0, "above", E.es, mr=E.mr, end=L.cb, retest_fn=None) == L.cb       # end = decision bar
    assert BR.first_real_break(F, 11, 0.0, "above", E.es, mr=E.mr, end=L.cb - 1, retest_fn=None) is None
    assert E.status(L, L.cb) == "flip" and E.status(L, L.cb - 1) in ("pending", "अखंड")
    assert L.q["Q1"] is True


def test_structural_top_needs_close_not_wick():
    class P:
        def __init__(self, kind, price, bar, cb):
            self.kind, self.price, self.bar, self.confirm_bar, self.warmup = kind, price, bar, cb, False
    A = {"h": np.array([100, 110, 105, 104, 103, 102.0]), "l": np.array([90, 100, 95, 89, 92, 93.0]),
         "c": np.array([95, 105, 100, 92, 96, 97.0])}
    res = {"pivots": {1: [P("L", 90, 0, 1), P("H", 110, 1, 3)]}}
    assert TE.structural_tops(res, A, 1, "H") == []                            # low 89 फक्त wick ⇒ top नाही
    A["c"][3] = 89.5
    tops = TE.structural_tops(res, A, 1, "H")
    assert len(tops) == 1 and tops[0][1] == 3                                   # top_known_at = close चा bar


@pytest.fixture(scope="module")
def world():
    m15, res, st, lg = built(11, trend=0.6)
    trk = {d: LI.Tracker(lg, st, d) for d in (1, 2)}
    f2 = F2.Fold(lg, trk[2])
    f2.run()
    f1 = F2.Fold(lg, trk[1], parent=f2)
    f1.run()
    Z = ZE.Zones(lg, st, trk).run(snap_bars=range(len(m15)))
    L4 = ZL.run(Z, f1, f2)
    E = TE.Engine(lg, st)
    L5 = TL.run(E, trk, f1, Z, L4)
    return m15, res, st, lg, trk, f1, f2, Z, L4, E, L5


def test_lines_born_after_known_at_and_provisional_only_with_k_break(world):
    *_, E, L5 = world
    for t, r in L5.items():
        for x in r["lines"]:
            L = next(v for v in E.lines.values() if v.id == x["id"])
            assert L.birth <= t
            if x["class"] == "trade-योग्य":
                assert not L.flat
                if L.provisional:                                              # उत्तर 10-ब: K आधार-रेघ break + 3रा touch
                    assert r["k_base"] is not None and TE.prov_ok(E, L, t, r["k_base"]) is not None
        ka = r["k_area_line"]
        if ka.get("line"):
            L = next(v for v in E.lines.values() if v.id == ka["line"])
            assert not L.k_line


def test_line_class_steep_and_provisional_rules():
    lc = TE.line_class
    assert lc(False, True, True, 2, True, False, False) == "trade-योग्य"
    assert lc(False, True, True, 2, True, True, False) == "तीव्र"               # तीव्र + 2 touches ⇒ trade-योग्य नाही
    assert lc(False, True, True, 3, True, True, False) == "trade-योग्य"        # तीव्र + ≥ 3 held ⇒ trade-योग्य (grade कमी)
    assert lc(False, True, False, 2, True, False, False) == "लागू नाही"        # provisional (before_k नाही), prov नाही
    assert lc(False, True, False, 2, True, False, True) == "trade-योग्य"       # provisional + prov अट
    assert lc(False, True, False, 2, True, True, True) == "तीव्र"              # तीव्र + provisional + 2 held ⇒ नाही
    assert lc(False, True, False, 3, True, True, True) == "trade-योग्य"
    assert lc(True, True, True, 5, True, False, False) == "सपाट"


def test_prov_ok_third_touch_close_inside_then_k_break_within_n():
    n = 40
    h, l = [150.0] * n, [130.0] * n
    h[0], h[10] = 200, 190                                                     # A1, A2 (slope −1)
    l[3], l[14] = 100, 100                                                     # θ_D0 दूर ⇒ दोन्ही held
    h[25] = 175.5                                                              # 3रा touch (रेघ 175), close आत
    c = [x - 5 for x in h]
    E = mini(h, l, c)
    L = E.make((0, 200.0), (10, 190.0), "H", 10, provisional=True)
    assert len([x for x in L.held if x["held"] < 25]) >= 2
    assert TE.prov_ok(E, L, 28, {"bar": 28}) == 25                             # break 3 candles नंतर ⇒ ✓
    assert TE.prov_ok(E, L, 27, {"bar": 28}) is None                           # break अजून झाला नाही
    assert TE.prov_ok(E, L, 33, {"bar": 33}) is None                           # 8 candles नंतर > N (6)
    assert TE.prov_ok(E, L, 31, {"bar": 31}) == 25                             # नेमके N (6) candles नंतर ⇒ ✓
    c2 = list(c)
    c2[25] = 180.0                                                             # close रेघेपलीकडे ⇒ commitment नाही
    E2 = mini(h, l, c2)
    L2 = E2.make((0, 200.0), (10, 190.0), "H", 10, provisional=True)
    assert TE.prov_ok(E2, L2, 28, {"bar": 28}) is None


def test_prov_break_n_matches_layer7():
    from decision2 import settings as DS
    assert TS.DEFAULTS["prov_break_n"] == DS.DEFAULTS["tl_break_n"]


def test_k_base_break_once_and_mirror(world):
    *_, E, L5 = world
    seen = {}
    for t, r in L5.items():
        kb = r.get("k_base")
        if kb:
            base = r["k_lines"]["base"]["id"]
            seen.setdefault(base, set()).add(kb["bar"])
            assert kb["dir"] == (-1 if r["side"] == "seller" else 1)
    for v in seen.values():
        assert len(v) == 1


def test_truncation_same_output(world):
    m15, res, st, lg, trk, f1, f2, Z, L4, E, L5 = world
    from legs2 import measure2 as M2
    from swings2 import engine as SE
    from swings2 import structure as SST
    cut = len(m15) - 30
    r2 = SE.build(m15.iloc[:cut + 1].reset_index(drop=True))
    st2, rr2 = SST.all_structure(r2)
    lg2 = M2.build(r2, None, rr=rr2)
    t2 = {d: LI.Tracker(lg2, st2, d) for d in (1, 2)}
    g2 = F2.Fold(lg2, t2[2])
    g2.run()
    g1 = F2.Fold(lg2, t2[1], parent=g2)
    g1.run()
    Z2 = ZE.Zones(lg2, st2, t2).run(snap_bars=range(cut + 1))
    L42 = ZL.run(Z2, g1, g2)
    E2 = TE.Engine(lg2, st2)
    L52 = TL.run(E2, t2, g1, Z2, L42)
    for t in (cut - 25, cut - 6, cut):
        assert json.dumps(L5[t], default=str, sort_keys=True) == json.dumps(L52[t], default=str, sort_keys=True)


def test_caption_and_rows(world):
    from trendlines2 import charts as TC
    m15, *_, L5 = world
    t = len(m15) - 1
    cap = TC.caption(1, 3, m15["bar_end"].iloc[t], L5[t])
    assert len(cap.splitlines()) <= 8 and len(cap.encode("utf-16-le")) // 2 <= 1024 and "_" not in cap
    assert TC.rows(L5, t - 300, t)


def test_script_rerun_identical(tmp_path):
    import importlib.util

    from tests.test_pivots_dc import SLOTS, _monday
    spec = importlib.util.spec_from_file_location("tlc", os.path.join(ROOT, "scripts", "trendline_check.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    rng = np.random.default_rng(9)
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
        assert M.main(["--data", str(data), "--out-dir", str(od), "--run-id", "tl/t", "--days", "1",
                       "--futures-dir", str(tmp_path / "nofut")]) == 0
        outs.append({f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(od) for f in fs if f.endswith(".json")})
    assert outs[0] == outs[1] and outs[0]


def test_register_numbers_dates_shadow():
    reg = " ".join(TS.REGISTER)
    for k in TS.DEFAULTS:
        assert k in reg, k
    allowed = {0, 1, -1, 2, 3, 4, 0.0, 1e-9}
    for f in ("engine.py", "layer.py"):
        tree = ast.parse(open(os.path.join(ROOT, "trendlines2", f), encoding="utf-8").read())
        nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)}
        assert nums <= allowed, (f, nums - allowed)
    paths = [os.path.join(ROOT, "trendlines2", f) for f in os.listdir(os.path.join(ROOT, "trendlines2")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "trendline_check.py"), os.path.abspath(__file__)]
    hits = [f"{os.path.basename(p)}:{i}" for p in paths for i, line in enumerate(open(p, encoding="utf-8"), 1)
            if any(rx.search(line) for rx in DATE_RX_I)]
    assert not hits, hits
    for p in paths[:-2]:
        src = open(p, encoding="utf-8").read()
        for bad in ("broker", "place_order", "market_state", "chart_reader", "levels_v2", "areas"):
            assert f"import {bad}" not in src and f"from {bad}" not in src
        assert "BreakCache" not in src.replace("BreakCache नाही", "").replace("BreakCache वापरायचा", "")
