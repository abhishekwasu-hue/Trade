"""Abhi 21 Oct — BANKNIFTY 07–21 Oct review, root causes (decision3/entry_models.py). Synthetic only (CI-safe), both mirrors.

  RC1  the overlapping cluster only COUNTS one signal per model per place: the trigger check and the invalidation come from the area
       price is actually visiting, never the union; no union field reaches an entry, the live payload or the card (Z-1u);
  RC2  research default `entry_area_refine = setup_tf`: the 1H / Daily area is the context; the refined 15M base inside it (the newest
       15M turn of the area's side inside the band, wick to body) gives the trigger proximity, the E1 entry and the invalidation; no
       refined base yet ⇒ the models wait;
  RC3  `entry_trigger_rule = inside`: a model fires only while price is inside its area and not beyond its invalidation — a bar that
       gaps through or a large candle that closes through / out of the area never fires (E1 / E2 / E3 / E4 a), and E4 (b)'s rejection
       form must be AT the retested object;
  RC4  E4 (b): a broken line is "being revisited" only while price is actually back at it, and the revisit ends when price leaves it
       by structure (a new swing that does not reach it).
"""
import json

import numpy as np
import pytest

from decision3 import entry_models as EM
from decision3 import method as M
from decision3 import settings as S3
from decision3 import trendline as TL
from tests.test_decision3_entry_models import BEAR, MID, SWINGS, _bare, _ltf_from, _mirror_rows

AREA = {"entry_area_refine": "area"}                      # RC3 alone (the context area = the trade area)
LEGACY = {**AREA, "entry_trigger_rule": "legacy"}         # the da7cbbc trigger (control)
MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])


def _fired(V, lvl, d, bars):
    return {t: [f["model"] for f in EM.Reader(V).area(t, lvl, d)[1]] for t in bars}


def _rows(changes):
    rows = list(BEAR)
    for i, r in changes.items():
        rows[i] = r
    return rows


# ------------------------------------------------------------------------------------------------ settings
def test_rc2_rc3_settings_registered_with_the_new_defaults():
    assert S3.DEFAULTS["entry_trigger_rule"] == "inside" and S3.REGISTER["entry_trigger_rule"][1] == "inside / legacy"
    assert S3.DEFAULTS["entry_area_refine"] == "setup_tf" and S3.REGISTER["entry_area_refine"][1] == "setup_tf / area"
    assert "RESEARCH DEFAULT" in S3.REGISTER["entry_area_refine"][3] and "review after" in S3.REGISTER["entry_area_refine"][3]
    from decision3 import engine as E3
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    for k in ("entry_trigger_rule", "entry_area_refine"):
        with pytest.raises(ValueError, match=k):
            E3.V22(m15, s={k: "x"}, ltf=ltf, futures=fut)


# ------------------------------------------------------------------------------------------------ RC3: inside the area at the trigger
@MIRRORS
def test_e1_wick_into_the_area_closing_outside_never_fires(mirror):
    rows = _rows({3: (99.3, 100.6, 99.2, 99.8, 1.0)})                      # first bar of the visit: a wick in, closes below the area
    V, lvl, d = _bare(rows, SWINGS, mirror=mirror, s=AREA)
    a, f = EM.Reader(V).area(3, lvl, d)
    assert f == [] and "price has left the area" in a["models"]["E1"]["waiting"]
    V0, lvl0, d0 = _bare(rows, SWINGS, mirror=mirror, s=LEGACY)
    assert [x["model"] for x in EM.Reader(V0).area(3, lvl0, d0)[1]] == ["E1"]   # the da7cbbc trigger fired there


@MIRRORS
def test_gap_through_and_large_candle_through_the_far_edge_never_fire(mirror):
    gap = _rows({3: (102.4, 102.9, 102.2, 102.6, 1.0)})                    # opens beyond the far edge (gap through)
    big = _rows({3: (99.3, 103.0, 99.2, 102.7, 1.0)})                      # one large candle through the whole area
    for rows in (gap, big):
        V, lvl, d = _bare(rows, SWINGS, mirror=mirror, s=AREA)
        assert "E1" not in sum(_fired(V, lvl, d, range(3, len(rows))).values(), [])
    # inside a visit: the commitment bar gaps beyond the far edge, or one large candle closes through it ⇒ no E2 there
    for bar6 in ((102.3, 102.9, 99.9, 100.1, 5.0), (101.6, 103.4, 101.5, 103.2, 5.0)):
        V, lvl, d = _bare(_rows({6: bar6}), SWINGS, mirror=mirror, s=AREA)
        assert "E2" not in _fired(V, lvl, d, [6])[6]


@MIRRORS
def test_e2_commitment_candle_closing_outside_the_area_never_fires(mirror):
    rows = _rows({6: (101.6, 101.7, 99.0, 99.2, 5.0)})                     # the dominant red closes BELOW the area (07 Oct 09:15 E2)
    V, lvl, d = _bare(rows, SWINGS, mirror=mirror, s=AREA)
    fired = _fired(V, lvl, d, range(3, len(rows)))
    assert "E2" not in fired[6]
    a6 = EM.Reader(V).area(6, lvl, d)[0]
    assert a6["models"]["E2"]["status"] == "waiting" and "price has left the area" in a6["models"]["E2"]["waiting"]
    V0, lvl0, d0 = _bare(rows, SWINGS, mirror=mirror, s=LEGACY)
    assert "E2" in _fired(V0, lvl0, d0, [6])[6]                           # the da7cbbc trigger fired on it


@MIRRORS
def test_e3_waits_while_the_choch_bar_is_outside_and_fires_back_inside(mirror, monkeypatch):
    rows = _rows({6: (101.6, 101.7, 99.0, 99.2, 1.0), 7: (99.2, 100.6, 99.1, 100.4, 1.0)})   # 6 closes below, 7 back inside
    V, lvl, d = _bare(rows, SWINGS, mirror=mirror, s=AREA)
    monkeypatch.setattr(EM.Reader, "c1", lambda self, u, l, dd, st: {"done": u >= 6, "line": "LTF CHoCH (test)"})
    monkeypatch.setattr(EM.Reader, "c0", lambda self, *a: (False, "no commitment", {}))
    fired = _fired(V, lvl, d, range(3, 9))
    assert "E3" not in fired[6] and "E3" in fired[7]


@MIRRORS
def test_e4a_confirmation_bar_closing_outside_never_fires(mirror):
    rows = _rows({9: (100.9, 101.0, 99.5, 99.6, 1.0)})                     # the push failed, but the bar already left the area
    V, lvl, d = _bare(rows, SWINGS, mirror=mirror, s=AREA)
    assert "E4" not in _fired(V, lvl, d, [9])[9]
    V0, lvl0, d0 = _bare(rows, SWINGS, mirror=mirror, s=LEGACY)
    assert "E4" in _fired(V0, lvl0, d0, [9])[9]


def _neck(mirror):
    rows = [(96.0, 96.4, 95.2, 96.2, 1.0), (96.2, 96.4, 95.6, 96.1, 1.0), (96.1, 96.2, 94.0, 94.2, 1.0),
            (94.2, 94.3, 93.0, 93.2, 1.0), (93.2, 94.6, 93.1, 94.5, 1.0), (94.5, 96.1, 94.4, 96.0, 1.0),
            (96.0, 97.3, 95.9, 97.2, 1.0), (97.2, 98.6, 97.1, 98.4, 1.0), (98.4, 98.5, 96.6, 96.7, 1.0)]
    neck = {"kind": "L", "p1": [0, 95.0], "slope": 0.5, "broken": True, "break_bar": 2, "break_side": "down", "id": "pat:neck",
            "family": "pattern neckline"}
    if mirror:
        rows = _mirror_rows(rows)
        neck = {**neck, "kind": "H", "p1": [0, 2 * MID - 95.0], "slope": -0.5, "break_side": "up"}
    return rows, neck


@MIRRORS
def test_e4b_rejection_form_must_be_at_the_retested_line(mirror, monkeypatch):
    rows, neck = _neck(mirror)
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 4)
    monkeypatch.setattr(EM, "PATTERN_HOOK", lambda V, t, d: [neck])
    d = M.UP if mirror else M.DOWN
    V, _l, _d = _bare(rows, [], trend_at=lambda u: "UP" if mirror else "DOWN")
    for form, fires in ((("engulf", 1), True), (("strong_close", 1), False)):   # bar 8 does not reach the line; bar 7 did
        monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None, form=form: form if t == 8 else None)
        fired = [t for t in range(4, len(rows)) for _f in EM.Reader(V).broken(t, d)[1]]
        assert (fired == [8]) is fires, (form, fired)


# ------------------------------------------------------------------------------------------------ RC4: the broken-line revisit
@MIRRORS
def test_e4b_line_far_away_is_never_a_revisit_and_a_revisit_ends_by_structure(mirror, monkeypatch):
    up = [(100.0 + k, 100.6 + k, 99.6 + k, 100.4 + k, 1.0) for k in range(10)]   # price far beyond a flat broken line at 95
    rows = [(96.0, 96.4, 95.2, 96.2, 1.0), (96.2, 96.4, 94.0, 94.2, 1.0)] + up
    neck = {"kind": "L", "p1": [0, 95.0], "slope": 0.0, "broken": True, "break_bar": 1, "break_side": "down", "id": "pat:far",
            "family": "pattern neckline"}
    if mirror:
        rows = _mirror_rows(rows)
        neck = {**neck, "kind": "H", "p1": [0, 2 * MID - 95.0], "break_side": "up"}
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 1)
    monkeypatch.setattr(EM, "PATTERN_HOOK", lambda V, t, d: [neck])
    monkeypatch.setattr(M, "reversal_form", lambda A, t, dd, s, tss=None: ("engulf", 1))
    d = M.UP if mirror else M.DOWN
    V, _l, _d = _bare(rows, [], trend_at=lambda u: "UP" if mirror else "DOWN")
    for t in range(2, len(rows)):
        armed, fired = EM.Reader(V).broken(t, d)
        assert armed == [] and fired == [], t                              # 04 Aug: never "revisit in progress" from far away
    # a revisit that ends by structure: touch at bar 2, then a swing away that does not reach the line
    R = EM.Reader(V)
    touch = lambda b, u: np.array([i for i in range(b, u + 1) if i == 2])  # noqa: E731
    from types import SimpleNamespace as NS
    kind = "L" if not mirror else "H"
    V.levels._known0 = [NS(kind=kind, price=float(rows[5][2] if not mirror else rows[5][1]), bar=5, confirm_bar=6)]
    aw = lambda p: True  # noqa: E731
    assert R.touch_visit(4, "x", 2, touch, aw, d) == 2 and EM.Reader(V).touch_visit(6, "x", 2, touch, aw, d) is None


# ------------------------------------------------------------------------------------------------ RC2: the refined 15M base
# A supply 100–104 (the context). Bar 1 = a 15M swing high at 103.5 inside it (confirmed at 2): sellers acted there ⇒ the refined base
# = that candle's wick to body (103.0–103.5). Price later enters the context area at bar 6 (low part) — not yet at the refined base —
# and reaches it at bar 8 (E1 there); invalidation = the base's far edge 103.5 (not the context's 104).
REF = [(101.0, 102.0, 100.8, 101.8, 1.0),     # 0
       (101.8, 103.5, 101.7, 103.0, 1.0),     # 1  swing high 103.5 inside the context (body top 103.0)
       (103.0, 103.1, 100.5, 100.6, 1.0),     # 2
       (100.6, 100.7, 98.0, 98.2, 1.0),       # 3
       (98.2, 98.4, 97.0, 97.1, 1.0),         # 4  swing low away (confirmed at 5) ⇒ the earlier visit ended
       (97.1, 99.2, 97.0, 99.0, 1.0),         # 5
       (99.0, 100.9, 98.9, 100.7, 1.0),       # 6  enters the context area (low part)
       (100.7, 102.2, 100.6, 102.0, 1.0),     # 7
       (102.0, 103.2, 101.9, 103.1, 1.0),     # 8  reaches the refined base, closes inside it ⇒ E1
       (103.1, 103.3, 102.0, 102.1, 1.0)]     # 9
REF_SW = [("H", 103.5, 1, 2), ("L", 97.0, 4, 5)]


def _ref(mirror, s=None):
    return _bare(REF, REF_SW, band=(100.0, 104.0), mirror=mirror, s={"entry_area_refine": "setup_tf", **(s or {})})


@MIRRORS
def test_refined_base_is_the_15m_turn_inside_the_context_area(mirror):
    V, lvl, d = _ref(mirror)
    rb = EM.Reader(V).refined(8, lvl, d)
    want = (2 * MID - 103.5, 2 * MID - 103.0) if mirror else (103.0, 103.5)
    assert (rb["lo"], rb["hi"]) == pytest.approx(want) and rb["bar"] == 1 and rb["tf"] == "15M"
    assert EM.Reader(V).refined(1, lvl, d) is None                         # not confirmed yet at its own bar


@MIRRORS
def test_e1_fires_at_the_refined_base_not_at_the_context_edge_with_the_bases_invalidation(mirror):
    V, lvl, d = _ref(mirror)
    fired = _fired(V, lvl, d, range(6, len(REF)))
    assert fired[6] == [] and fired[7] == [] and fired[8] == ["E1"]
    e1 = next(f for f in EM.Reader(V).area(8, lvl, d)[1] if f["model"] == "E1")
    far = 2 * MID - 103.5 if mirror else 103.5
    assert e1["invalidation"] == pytest.approx(far) and "refined 15M base" in e1["invalidation_rule"]
    assert e1["refined"]["bar"] == 1
    a7 = EM.Reader(V).area(7, lvl, d)[0]
    assert "refined 15M base" in a7["models"]["E1"]["waiting"] and "reach" in a7["models"]["E1"]["waiting"]
    Va, lvla, da = _ref(mirror, AREA)                                      # the context area alone: E1 on entering it (bar 6)
    assert _fired(Va, lvla, da, [6])[6] == ["E1"]


@MIRRORS
def test_no_refined_base_yet_the_models_wait(mirror):
    V, lvl, d = _bare(REF, [("L", 97.0, 4, 5)], band=(100.0, 104.0), mirror=mirror, s={"entry_area_refine": "setup_tf"})
    for t in range(6, len(REF)):
        a, f = EM.Reader(V).area(t, lvl, d)
        assert f == [] and all("no refined base yet" in (st.get("waiting") or "") for st in a["models"].values()), t


# ------------------------------------------------------------------------------------------------ RC1: the cluster only counts
def _two(mirror):
    from types import SimpleNamespace as NS
    L1 = NS(id=1, born_bar=0, state_at=lambda u: "ACTIVE", events=[], dead_bar=None)
    V, lvl0, d = _bare(BEAR, SWINGS, mirror=mirror, extra_L=(L1,), s=AREA)
    b1 = (2 * MID - 103.0, 2 * MID - 101.0) if mirror else (101.0, 103.0)
    return V, lvl0, {**lvl0, "id": 1, "lo": b1[0], "hi": b1[1]}, d


@MIRRORS
def test_no_union_field_reaches_an_entry_the_payload_or_the_card(mirror):
    import engine3_live as L
    from paper import engine_entry as EE
    V, lvl0, lvl1, d = _two(mirror)
    union = {round(min(lvl0["lo"], lvl1["lo"]), 2), round(max(lvl0["hi"], lvl1["hi"]), 2)}
    for t in range(3, len(BEAR)):
        R = EM.Reader(V)
        armed, ents = [], []
        for lv in (lvl0, lvl1):
            a, f = R.area(t, lv, d)
            if a is not None:
                armed.append(a)
                ents += [(x, lv, d, a) for x in f]
        for f, lv, _d, a in EM.clusters(armed, ents, [(lvl0, d), (lvl1, d)]):
            own = {round(lv["lo"], 2), round(lv["hi"], 2)}
            cl = f["cluster"]
            assert not {"lo", "hi", "far_edge", "visit_extreme"} & set(cl) and "count only" in cl["use"]
            assert "cluster" not in f["invalidation_rule"]
            if f["model"] == "E1":                                         # E1: its OWN area's far edge
                assert f["invalidation"] == pytest.approx(lv["hi"] if d < 0 else lv["lo"])
            if round(float(f["invalidation"]), 2) in union - own:
                pytest.fail(f"{f['model']} invalidation from the union {f['invalidation']}")
            e = {"model": f["model"], "name": "x", "direction": d, "side": "s", "object": "area",
                 "area": {k: lv[k] for k in ("id", "tf", "role", "lo", "hi", "state")}, "visit_id": cl["visit_id"], "key": "k",
                 "trigger_ts": "2030-01-07 10:00:00", "invalidation": f["invalidation"], "invalidation_rule": f["invalidation_rule"],
                 "cluster": cl, "evidence": [], "evidence_list": {}, "label": None}
            x = L.compact_entries([e])[0]
            assert "lo" not in x["cluster"] and "hi" not in x["cluster"]
            assert EE.entry_zone(x) == (d, *sorted((lv["lo"], lv["hi"])))   # max_hits_per_zone counts the visited area
            g = EE.entry_gate_tags({"bar_ts": "2030-01-07 10:00:00", "payload": json.dumps({})}, x,
                                   "BEARISH" if d < 0 else "BULLISH")["gate"]
            assert g["area"] == sorted([lv["lo"], lv["hi"]]) and "lo" not in (g.get("cluster") or {})


# ------------------------------------------------------------------------------------------------ review #364: E1 on a broken base
@MIRRORS
def test_e1_never_fires_on_a_refined_base_already_closed_through_in_the_visit(mirror):
    """Bar 6 gaps into the top of the context area ABOVE the refined base and closes beyond its far edge (103.9 > 103.5); bar 7 comes
    back into the base. E1 must not fire there: its invalidation (the base's far edge) would sit inside price already traded — the
    base is being broken (lifecycle), not entered."""
    rows = REF[:6] + [(103.8, 103.95, 103.6, 103.9, 1.0), (103.9, 103.95, 103.2, 103.3, 1.0), (103.3, 103.4, 102.0, 102.1, 1.0)]
    V, lvl, d = _ref_rows(rows, mirror)
    fired = _fired(V, lvl, d, range(6, len(rows)))
    assert "E1" not in sum(fired.values(), [])
    a7 = EM.Reader(V).area(7, lvl, d)[0]
    assert "closed through in this visit" in a7["models"]["E1"]["waiting"]
    ok = REF[:6] + [(103.0, 103.45, 102.9, 103.2, 1.0)]                    # control: the first touch closes inside ⇒ E1
    V2, lvl2, d2 = _ref_rows(ok, mirror)
    assert _fired(V2, lvl2, d2, [6])[6] == ["E1"]


def _ref_rows(rows, mirror, ltf=False):
    rr = _mirror_rows(rows) if mirror else rows
    return _bare(rows, REF_SW + [("H", 103.6, 13, 14)], band=(100.0, 104.0), mirror=mirror,
                 s={"entry_area_refine": "setup_tf", "entry_trigger_rule": "inside"}, ltf=_ltf_from(rr) if ltf else None)


# ------------------------------------------------------------------------------------------------ the DEFAULT path, every model
FULL = REF[:9] + [(103.1, 103.3, 100.4, 100.6, 5.0),   # 9  dominant red on volume, closes inside the context ⇒ E2 + the 5M CHoCH (E3)
                  (100.6, 101.0, 100.3, 100.9, 1.0),   # 10
                  (100.9, 104.4, 100.8, 103.8, 1.0),   # 11 sweep beyond the context's far edge, closes back inside
                  (103.8, 103.9, 102.9, 103.0, 1.0),   # 12
                  (103.0, 103.6, 102.8, 103.4, 1.0),   # 13 the next push fails inside the sweep extreme (swing high, known at 14)
                  (103.4, 103.45, 102.0, 102.1, 1.0),  # 14 ⇒ E4 (a), closing inside the area
                  (102.1, 102.2, 101.0, 101.1, 1.0)]   # 15


@MIRRORS
def test_default_settings_every_model_fires_end_to_end(mirror):
    """entry_area_refine = setup_tf + entry_trigger_rule = inside (the defaults): E1 at the refined base, E2 on the commitment, E3 on the
    LTF CHoCH, E4 (a) after the sweep — each once, each closing inside the area, each invalidation from the actual area / base."""
    assert S3.DEFAULTS["entry_area_refine"] == "setup_tf" and S3.DEFAULTS["entry_trigger_rule"] == "inside"
    V, lvl, d = _ref_rows(FULL, mirror, ltf=True)
    st = {t: EM.Reader(V).area(t, lvl, d)[1] for t in range(6, len(FULL))}
    fired = {t: [f["model"] for f in fs] for t, fs in st.items()}
    assert fired[8] == ["E1"] and fired[9] == ["E2", "E3"] and fired[14] == ["E4"]
    assert sum(len(v) for v in fired.values()) == 4
    inv = {f["model"]: f["invalidation"] for fs in st.values() for f in fs}
    m = (lambda x: 2 * MID - x) if mirror else (lambda x: x)
    assert inv["E1"] == pytest.approx(m(103.5)) and inv["E2"] == pytest.approx(m(103.5)) and inv["E3"] == pytest.approx(m(103.5))
    assert inv["E4"] == pytest.approx(m(104.4))                            # the sweep extreme
    for t, fs in st.items():
        for f in fs:
            c = float(V.levels.A["close"][t])
            assert float(lvl["lo"]) <= c <= float(lvl["hi"]) and (c - float(f["invalidation"])) * d >= 0, (t, f["model"])


@MIRRORS
def test_default_settings_e4b_fires_end_to_end(mirror, monkeypatch):
    rows, neck = _neck(mirror)
    monkeypatch.setattr(TL, "channel_lines", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "channels", lambda V, t, degree=None: [])
    monkeypatch.setattr(TL, "break_known_at", lambda V, x: 4)
    monkeypatch.setattr(EM, "PATTERN_HOOK", lambda V, t, d: [neck])
    V, _l, _d = _bare(rows, [], trend_at=lambda u: "UP" if mirror else "DOWN",
                      s={"entry_area_refine": "setup_tf", "entry_trigger_rule": "inside"})
    d = M.UP if mirror else M.DOWN
    fired = [(t, f) for t in range(4, len(rows)) for f in EM.Reader(V).broken(t, d)[1]]
    assert [t for t, _ in fired] == [8] and fired[0][1]["variant"] == "b"
    c = float(V.levels.A["close"][8])
    assert (c - fired[0][1]["invalidation"]) * d >= 0                      # not beyond the retest extreme
