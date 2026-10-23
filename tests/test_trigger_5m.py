"""Abhi (DECISIONS 37, owner rule): the entry trigger on 5M for every model — `trigger_tf = 5M` (default), `15M` = the earlier behaviour
(what-if, byte-identical). docs/reports/trigger_5m_report.md §2–§10. Synthetic only (CI-safe), both mirrors where a side matters:

  • the setting + switch are registered / validated; the 15M path (V22.decide) is byte-identical to the code before this build (pinned
    digests on the CI fixtures, model C off and on) for trigger_tf 15M AND 5M (decide never reads the setting);
  • trigger_frame: k(j) = the last CLOSED 15M bar, b(j) / the bar in progress, the FUT 5M join (exact bar start, NaN never 0, reason);
  • handover5 (resumable) == method.handover_episode on every prefix;
  • E1 = the first 5M candle trading into the refined base (not the 15M bar); a 5M candle that never trades into the base never fires;
    nothing fires on a 5M candle closing beyond the invalidation side; each model at most once per visit across the 5M steps;
  • E3 = the 5M candle whose close makes the CHoCH, and it must trade into the refined base (Q6, not relaxed);
  • E4 (a) on 5M: the sweep and the failed 5M push; E4 (b) on 5M: rejection at the broken object from the break side (DECISIONS 38);
  • a visit may start on a 5M candle inside the 15M bar in progress (visit id = area @ that 15M bin);
  • no look-ahead: the 5M reader on full data = on data cut at the 5M close (every 5M candle);
  • the decide5 row / entry payload (trigger_tf, 5M trigger ts / OHLC, context_bar_ts, entry_ref = the 5M close) and model C wiring."""
import hashlib
import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import entry_models5 as EM5
from decision3 import levels as LV
from decision3 import method as M
from decision3 import settings as S3
from decision3 import trigger_frame as TF
from tests.test_decision3_entry_models import BEAR, MID, SWINGS, _bare, _ltf_from, _mirror_rows
from tests.test_entry_models_inside_area import REF, REF_SW
from tests.test_entry_models_sweep_fakeout import SWEEP, SWEEP_EVENT, SWEEP_SW

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
REFINE = {"entry_area_refine": "setup_tf"}


def _v5(rows, sw, band, mirror, s=None, events=(), fut=None, ltf_rows=None):
    """A bare V22 with its 5M trigger frame from the 15M rows (each 15M bar = 3 5M candles: open → extremes → close)."""
    rr = _mirror_rows(rows) if mirror else rows
    V, lvl, d = _bare(rows, sw, band=band, mirror=mirror, s=s, events=events, ltf=_ltf_from(rr))
    if fut is not None:
        F = TF.of(V)
        F.has_fut = True
        F.A["volume"][:] = F.A["volume_raw"][:] = fut(F)
    return V, lvl, d


def _scan(V, lvl, d, js=None):
    F = TF.of(V)
    out = {}
    for j in (range(F.n) if js is None else js):
        out[j] = EM5.Reader5(V, j).area5(lvl, d)
    return out


def _fired(st):
    return [(j, f["model"]) for j, (_a, fs) in st.items() for f in fs]


# ------------------------------------------------------------------------------------------------ setting, switch, 15M parity
def test_trigger_tf_setting_registered_and_validated():
    assert S3.DEFAULTS["trigger_tf"] == "5M"
    v, allowed, kind, why = S3.REGISTER["trigger_tf"]
    assert v == "5M" and allowed == "5M / 15M (what-if)" and kind == "Abhi नियम" and "DECISIONS 37" in why and "byte-identical" in why
    import engine3_live as L
    assert L.METHOD_SWITCHES["engine3_trigger_tf"][:2] == ("trigger_tf", ("5m", "15m"))
    assert L.method_switches({"engine3_trigger_tf": "15M"}) == {"trigger_tf": "15m"}
    assert L.method_switches({"engine3_trigger_tf": "5m"}) == {} and L.method_switches({}) == {}
    with pytest.raises(ValueError):
        L.method_switches({"engine3_trigger_tf": "1m"})
    assert L.trigger_tf_of({}) == "5M" and L.trigger_tf_of({"engine3_trigger_tf": "15m"}) == "15M"
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    with pytest.raises(ValueError, match="trigger_tf"):
        E3.V22(m15, s={"trigger_tf": "1M"}, ltf=ltf, futures=fut)
    assert E3.V22(m15, s={"trigger_tf": "15m"}, ltf=ltf, futures=fut).trigger_tf == "15M"


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _rows15(name, extra):
    if name == "abc":
        from tests.test_decision3_method import _abc_m15
        s = {"maturity_sigma_d": -1e6, "ltf_choch": False, "c0_volume_required": False, **extra}
        return E3.V22(_abc_m15(), s=s).run()
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=name == "oct12_bull")
    V = E3.V22(m15, s={"level_death_side": "role", **extra}, ltf=ltf, futures=fut)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    return [V.decide(t) for t in range(len(ts)) if ts.dt.normalize().iloc[t] == last]


# V22.decide rows of the code BEFORE the 5M build (git 8ff504e), every key, computed on these fixtures
PIN15 = {"abc": "b629eeb2aac645b48d4b478206070385ca39d06feec79c3c94fee7a2d2e462de",
         "oct12_bear": "b958c1981998c89a5cc706c5544e45be41eb2e9ac02265b572a80e82f69a002b",
         "oct12_bull": "cccbc4d26c792f72dcfc755c643d81dd008d41cd0fa567e535af1f1927a50602"}
PIN15_C = {"abc": "fc218b0817b2648dd4177cf8d414da4660dee55db7928f9eae7448565a741f2e",
           "oct12_bear": "20d14e2757185d322c0013f76147183f2b1e30cf493d1250925cc0f7f856ecd7",
           "oct12_bull": "c596545e7de3a9b357808ee2ae7d111aa1a92e155f2541084a73c94e5c6d8823"}


@pytest.mark.parametrize("name", sorted(PIN15))
def test_15m_path_is_byte_identical_to_the_code_before_the_5m_build(name):
    """trigger_tf = 15M (what-if) = today's decide(t), byte for byte; decide(t) never reads trigger_tf (the 5M default changes only
    decide5, the live loop and the card)."""
    for tf in ({"trigger_tf": "15M"}, {}, {"trigger_tf": "5M"}):
        assert _digest(_rows15(name, tf)) == PIN15[name]
    assert _digest(_rows15(name, {"trigger_tf": "15M", "model_c": "on"})) == PIN15_C[name]


# ------------------------------------------------------------------------------------------------ the trigger frame
def test_trigger_frame_maps_each_5m_candle_to_the_closed_15m_bar_and_its_own_bin():
    V, _lvl, _d = _v5(BEAR, SWINGS, (100.0, 102.0), False)
    F = TF.of(V)
    assert F.n == 3 * len(BEAR)
    assert list(F.k_of[:6]) == [-1, -1, 0, 0, 0, 1]                        # a 15M bar is known only at its own close
    assert list(F.b_of[:6]) == [0, 0, 0, 1, 1, 1] and not F.virtual.any()
    assert F.pos[3] == pytest.approx(1 - 1 / 3) and F.pos[4] == pytest.approx(1.0) and F.pos[5] == pytest.approx(1 + 1 / 3)
    assert F.last_child_closing(V.bar_end[2]) == 8 and F.first_at_or_after(V.bar_end[2]) == 9
    # the bar in progress: a V22 with one 15M bar fewer (the live cut) ⇒ its 5M children map to k + 1 (a position, not an index)
    Vc, _l, _dd = _bare(BEAR[:5], SWINGS[:1], ltf=_ltf_from(BEAR[:6]))
    Fc = TF.of(Vc)
    assert list(Fc.k_of[-3:]) == [4, 4, 4] and list(Fc.b_of[-3:]) == [5, 5, 5] and Fc.virtual[-3:].all()
    assert Fc.bin_T(Fc.n - 1) == str(pd.Timestamp("2030-01-07 09:15") + pd.Timedelta(minutes=75))


def test_fut_5m_volume_joins_on_the_exact_bar_start_never_zero_never_filled():
    V, _lvl, _d = _v5(BEAR[:3], SWINGS[:1], (100.0, 102.0), False)
    ts = pd.Series(pd.to_datetime(TF.of(V).ts))
    fut = pd.DataFrame({"timestamp": ts.drop(index=[4]).reset_index(drop=True), "volume": 100.0, "contract": "BANKNIFTY30JANFUT"})
    fut["expiry"] = pd.Timestamp("2030-01-31")
    from legs2 import volume as LVOL
    fut = fut.assign(expiry=LVOL.expiry_of(fut)) if fut["expiry"].isna().all() else fut
    V._futures = fut
    V._tf5 = None
    F = TF.TriggerFrame(V, fut)
    assert F.has_fut and np.isnan(F.A["volume_raw"][4]) and F.vol_reason[4] == "no FUT bar"
    assert np.nansum(F.A["volume_raw"]) == 100.0 * (F.n - 1) and (F.A["volume_raw"][np.isfinite(F.A["volume_raw"])] > 0).all()
    assert "FUT 5M volume missing" in F.vol_na_reason(4) and F.vol_na_reason(3) is None
    g = F.vol_gaps(3, 5, 0.5)
    assert g["n"] == 1 and g["m"] == 3 and not g["over"]
    assert TF.TriggerFrame(V, None).vol_gaps(0, 5, 0.5) is None              # FUT not given ⇒ c0's own data-problem rule (no gap count)


def test_handover5_resumable_equals_method_handover_episode_on_every_prefix():
    rng = np.random.default_rng(3)
    n = 40
    c = 100 + np.cumsum(rng.normal(0, 0.6, n))
    o = np.r_[c[0], c[:-1]]
    A = {"open": o, "close": c, "high": np.maximum(o, c) + rng.random(n) * 0.5, "low": np.minimum(o, c) - rng.random(n) * 0.5,
         "volume": rng.random(n) * 1000 + 10}
    s = S3.load({})
    for d in (-1, 1):
        broken = lambda e: e == 27                                        # noqa: E731
        sharp = lambda i, a0: M.sharp_reversal(A, i, d, 99.0, 101.0, s, a0=a0)   # noqa: E731
        memo = {}
        for t in range(3, n):
            want = M.handover_episode(A, 3, t, d, s, broken=broken, sharp=sharp)
            got = TF.handover5(A, 3, t, d, s, broken=broken, sharp=sharp, memo=memo, key="k")
            assert got == want, (d, t)
        assert TF.handover5(A, 3, 10, d, s, broken=broken, sharp=sharp, memo=memo, key="k") == \
            M.handover_episode(A, 3, 10, d, s, broken=broken, sharp=sharp)   # an earlier t after a later one: still exact


# ------------------------------------------------------------------------------------------------ the models on 5M
@MIRRORS
def test_e1_is_the_first_5m_candle_trading_into_the_refined_base(mirror):
    """REF: the 15M bar 8 reaches the refined base 103.0–103.5; on 5M its FIRST child stays below the base and the second one trades into
    it ⇒ E1 at that 5M candle (the 15M E1 read at bar 8's close); invalidation = the base's far edge; once per visit."""
    V, lvl, d = _v5(REF, REF_SW, (100.0, 104.0), mirror, s=REFINE)
    st = _scan(V, lvl, d)
    e1 = [j for j, m in _fired(st) if m == "E1"]
    assert e1 == [25]
    f = next(f for f in st[25][1] if f["model"] == "E1")
    rb = f["refined"]
    assert f["invalidation"] == pytest.approx(2 * MID - 103.5 if mirror else 103.5)
    A5 = TF.of(V).A
    assert float(A5["low"][25]) <= rb["hi"] and float(A5["high"][25]) >= rb["lo"]
    assert not (float(A5["low"][24]) <= rb["hi"] and float(A5["high"][24]) >= rb["lo"])     # the earlier child never touched it
    assert all(st[j][0]["models"]["E1"]["status"] == "fired_earlier" for j in range(26, TF.of(V).n))
    assert st[25][0]["visit_id"] == "0@" + str(V.levels.ts[6]) and st[25][0]["trigger_tf"] == "5M"


@MIRRORS
def test_every_5m_trigger_traded_into_the_base_and_never_beyond_its_invalidation(mirror, monkeypatch):
    """The common trigger rules on the 5M candle (traded_inside on the refined base, H2, beyond) on the sweep fixture with FUT 5M
    volume; each model at most once per visit."""
    monkeypatch.setattr(EM5.Reader5, "c1", lambda self, u, l, dd, st: {"done": False, "line": "test"})
    V, lvl, d = _v5(SWEEP, SWEEP_SW, (100.0, 104.0), mirror, s=REFINE, events=SWEEP_EVENT,
                    fut=lambda F: np.where(np.arange(F.n) // 3 == 14, 5000.0, 100.0))
    st = _scan(V, lvl, d)
    F = TF.of(V)
    fired = _fired(st)
    assert fired, "the sweep fixture fires on 5M"
    seen = {}
    for j, (a, fs) in st.items():
        for f in fs:
            key = (a["visit_id"], f["model"])
            assert key not in seen, key                                    # once per visit per model
            seen[key] = j
            rb = f.get("refined") or (f.get("facts") or {}).get("refined")
            if rb:
                assert float(F.A["low"][j]) <= rb["hi"] and float(F.A["high"][j]) >= rb["lo"]   # traded into the refined base
            c = float(F.A["close"][j])
            assert (c - float(f["invalidation"])) * d >= 0                   # never a close beyond the invalidation side
            far = float(lvl["hi"]) if d < 0 else float(lvl["lo"])
            assert (c - far) * d >= 0 and (float(F.A["open"][j]) - far) * d >= 0   # H2 on the 5M candle
    assert "E1" in {m for _j, m in fired} and "E4" in {m for _j, m in fired}


@MIRRORS
def test_e3_trigger_is_the_5m_choch_candle_and_it_must_trade_into_the_base(mirror, monkeypatch):
    V, lvl, d = _v5(REF + [(102.1, 103.4, 101.0, 101.2, 1.0), (101.2, 101.4, 100.9, 101.0, 1.0)], REF_SW, (100.0, 104.0), mirror,
                    s=REFINE)
    F = TF.of(V)
    at = {"j": None}

    def c1(self, u, l, dd, st):                                           # the CHoCH closes at 5M candle at["j"] (and stays done)
        done = at["j"] is not None and u >= at["j"]
        return {"done": done, "at": F.E(at["j"]) if done else None, "line": "5M CHoCH (test)"}
    monkeypatch.setattr(EM5.Reader5, "c1", c1)
    monkeypatch.setattr(EM5.Reader5, "absorbing", lambda *a, **k: None)
    rb_touch = [j for j in range(18, F.n) if float(F.A["low"][j]) <= (103.5 if not mirror else 2 * MID - 103.0)
                and float(F.A["high"][j]) >= (103.0 if not mirror else 2 * MID - 103.5)]
    off = [j for j in range(26, F.n) if j not in rb_touch]
    at["j"] = off[0]                                                       # the CHoCH candle does not trade into the base ⇒ no E3
    V._em5_memo = {}
    assert not [j for j, m in _fired(_scan(V, lvl, d)) if m == "E3"]
    on = [j for j in rb_touch if j > 25]
    at["j"] = on[0]                                                        # the CHoCH candle trades into the base ⇒ E3 at that candle
    V._em5_memo = {}
    assert [j for j, m in _fired(_scan(V, lvl, d)) if m == "E3"] == [on[0]]


@MIRRORS
def test_e4a_on_5m_sweep_and_the_failed_5m_push(mirror):
    V, lvl, d = _v5(SWEEP, SWEEP_SW, (100.0, 104.0), mirror, s=REFINE, events=SWEEP_EVENT)
    st = _scan(V, lvl, d)
    e4 = [(j, f) for j, (_a, fs) in st.items() for f in fs if f["model"] == "E4"]
    assert len(e4) == 1
    j, f = e4[0]
    fa = f["facts"]
    assert fa["tf"] == "5M" and fa["sweep_bar"] < fa["push_bar"] < j and fa["push_known_bar"] == fa["push_bar"] + 1 <= j
    F = TF.of(V)
    ext = max(float(F.A["high"][i]) for i in range(fa["sweep_bar"] + 1)) if not mirror else \
        min(float(F.A["low"][i]) for i in range(fa["sweep_bar"] + 1))
    assert f["invalidation"] == pytest.approx(round(ext, 2)) and "sweep extreme" in f["invalidation_rule"]


@MIRRORS
def test_e4b_on_5m_rejection_at_the_broken_area_from_the_break_side(mirror):
    rows = [(103.0, 103.2, 101.8, 102.0, 1.0), (102.0, 102.1, 99.0, 99.2, 1.0), (99.2, 99.3, 97.0, 97.2, 1.0),
            (97.2, 98.6, 97.1, 98.5, 1.0), (98.5, 99.6, 98.4, 99.5, 1.0), (99.5, 100.6, 99.4, 100.3, 1.0),
            (100.3, 100.4, 98.9, 99.0, 1.0), (99.0, 99.1, 98.0, 98.1, 1.0)]
    sw = [("L", 97.0, 2, 3)]
    br = {"id": 1, "lo": 100.0, "hi": 102.0, "role": LV.SUP, "state": "BROKEN", "break_dir": -1, "broken_at": 2,
          "trade_location": True, "tf": "1H", "sweeps": 0, "births": ["a:D2"], "fresh": False, "confluence": []}
    if mirror:
        br = {**br, "lo": 2 * MID - 102.0, "hi": 2 * MID - 100.0, "role": LV.RES, "break_dir": 1}
    L1 = NS(id=1, born_bar=0, state_at=lambda u: "BROKEN", events=[], dead_bar=None)
    rr = _mirror_rows(rows) if mirror else rows
    V, _lvl, d = _bare(rows, sw, mirror=mirror, snapshot=lambda t: [br], extra_L=[L1], ltf=_ltf_from(rr))
    F = TF.of(V)
    got = {j: EM5.Reader5(V, j).broken5(d) for j in range(9, F.n)}
    fired = [(j, f) for j, (_a, fs) in got.items() for f in fs]
    assert len(fired) == 1
    j, f = fired[0]
    assert f["variant"] == "b" and f["facts"]["trigger_tf"] == "5M" and f["obj"]["visit_id"].startswith("1@")
    assert 15 <= j <= 20                                                   # inside the 15M bars 5–6 (the revisit and its rejection)
    lo, hi = float(br["lo"]), float(br["hi"])
    touch = lambda i: float(F.A["low"][i]) <= hi and float(F.A["high"][i]) >= lo   # noqa: E731
    assert touch(j) or touch(j - 1)
    assert (float(F.A["close"][j]) < lo) if not mirror else (float(F.A["close"][j]) > hi)   # closes away, on the trade side
    ext = max(float(F.A["high"][i]) for i in range(f["start"], j + 1)) if not mirror else \
        min(float(F.A["low"][i]) for i in range(f["start"], j + 1))
    assert f["invalidation"] == pytest.approx(round(ext, 2))
    # DECISIONS 38 on 5M: the same object revisited from its ORIGINAL side (price above the broken support, coming down) is no E4 (b)
    down = [(104.0, 104.2, 102.9, 103.0, 1.0)] * 3 + [(103.0, 103.1, 101.0, 101.2, 1.0), (101.2, 101.3, 99.0, 99.1, 1.0),
                                                       (99.1, 99.2, 98.0, 98.1, 1.0)]
    rr2 = _mirror_rows(down) if mirror else down
    V2, _l2, d2 = _bare(down, [], mirror=mirror, snapshot=lambda t: [br], extra_L=[L1], ltf=_ltf_from(rr2))
    F2 = TF.of(V2)
    assert not [f for j in range(9, F2.n) for f in EM5.Reader5(V2, j).broken5(d2)[1]]


@MIRRORS
def test_a_visit_may_start_on_a_5m_candle_inside_the_15m_bar_in_progress(mirror):
    """The live cut: 15M bars closed up to bar 7, the 5M children of bar 8 (in progress) known; the second child trades into the refined
    base ⇒ E1 on that 5M candle, before the 15M bar closes; the visit id = area @ the visit's 15M bin (the same id the 15M bar gets later)."""
    rows = REF[:5] + [(97.1, 99.2, 97.0, 99.0, 1.0), (99.0, 99.6, 98.9, 99.5, 1.0), (99.5, 99.8, 99.4, 99.7, 1.0),
                      (99.7, 103.2, 99.6, 103.1, 1.0)]                    # bar 8: first touch of the area AND the base
    rr = _mirror_rows(rows) if mirror else rows
    V, lvl, d = _bare(rows[:8], REF_SW, band=(100.0, 104.0), mirror=mirror, s=REFINE, ltf=_ltf_from(rr))
    F = TF.of(V)
    assert F.virtual[-3:].all()
    st = {j: EM5.Reader5(V, j).area5(lvl, d) for j in range(F.n)}
    e1 = [j for j, m in _fired(st) if m == "E1"]
    assert e1 == [25]                                                      # 8 × 3 + 1: before the 15M bar 8 is closed
    a = st[25][0]
    assert a["visit_id"] == "0@" + F.bin_T(25) and a["visit_start"] == str(pd.Timestamp("2030-01-07 09:15") + pd.Timedelta(minutes=120))
    Vf, lvlf, df_ = _bare(rows, REF_SW, band=(100.0, 104.0), mirror=mirror, s=REFINE, ltf=_ltf_from(rr))
    assert EM5.Reader5(Vf, 26).area5(lvlf, df_)[0]["visit_id"] == a["visit_id"]   # the same visit id once the bar is closed


# ------------------------------------------------------------------------------------------------ no look-ahead
def _cut_bare(rows, sw, events, mirror, s, j):
    """The bare V22 as the live loop would build it at the 5M close of candle j: 15M bars closed by then, swings / K4 events known by
    then, 5M candles ≤ j."""
    rr = _mirror_rows(rows) if mirror else rows
    full5 = _ltf_from(rr)
    end = full5["end"][j]
    k = int(np.searchsorted((pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min") + pd.Timedelta(minutes=15)).to_numpy(),
                            end, side="right")) - 1
    cut5 = {**{kk: v[:j + 1] for kk, v in full5.items() if isinstance(v, np.ndarray)}, "minutes": 5, "label": "5M"}
    return _bare(rows[:k + 1], [x for x in sw if x[3] <= k], band=(100.0, 104.0), mirror=mirror, s=s,
                 events=[e for e in events if e[0] <= k], ltf=cut5)


@MIRRORS
def test_no_look_ahead_full_data_equals_data_cut_at_the_5m_close(mirror):
    rows, sw, ev = SWEEP, SWEEP_SW, SWEEP_EVENT
    V, lvl, d = _v5(rows, sw, (100.0, 104.0), mirror, s=REFINE, events=ev)
    F = TF.of(V)
    for j in range(F.n):
        full = EM5.Reader5(V, j).area5(lvl, d)
        Vc, lc, dc = _cut_bare(rows, sw, ev, mirror, REFINE, j)
        cut = EM5.Reader5(Vc, TF.of(Vc).n - 1).area5(lc, dc)
        assert json.dumps(full, default=str, sort_keys=True) == json.dumps(cut, default=str, sort_keys=True), j


# ------------------------------------------------------------------------------------------------ decide5 row, payload, model C
@pytest.fixture(scope="module")
def oct12_5m():
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    return E3.V22(m15, s={"level_death_side": "role"}, ltf=ltf, futures=fut)


def test_decide5_row_reads_the_closed_15m_bar_and_carries_the_5m_trigger(oct12_5m):
    V = oct12_5m
    F = V.trigger_frame()
    j = F.n - 2
    r = V.decide5(j)
    k = int(F.k_of[j])
    assert r["trigger_tf"] == "5M" and r["bar5"] == j and r["context_bar"] == k and r["bar_end"] == F.E(j)
    assert pd.Timestamp(r["context_bar_end"]) <= pd.Timestamp(F.end[j]) and r["context_ts"] == str(pd.Timestamp(V._ts[k]))
    r15 = V.decide(k)
    for key in ("daily_trend", "trend_used", "watch_list", "active_levels"):
        assert json.dumps(r[key], default=str) == json.dumps(r15[key], default=str)   # the structure = the closed 15M bar's
    assert all(a.get("trigger_tf") == "5M" for a in r["armed"])


def test_5m_entry_payload_fields_and_live_row(oct12_5m, monkeypatch):
    V = oct12_5m
    F = V.trigger_frame()
    js = [j for j in range(F.n - 60, F.n)]
    got = None
    for j in js:                                                           # force an E1 on the first armed visit (payload shape only)
        r = V.decide5(j)
        if r.get("armed"):
            got = (j, r)
            break
    if got is None:
        pytest.skip("no armed visit in the fixture tail")
    import engine3_live as L
    e = {"model": "E1", "name": "Aggressive", "direction": -1, "side": "bear_call", "object": "area", "visit_id": "8@x",
         "visit_start": "x", "key": "8|x|E1", "trigger_tf": "5M", "trigger_ts": F.T(got[0]), "trigger_bar_end": F.E(got[0]),
         "trigger_ohlc": {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}, "context_bar_ts": "2030-02-27 12:00:00",
         "trigger_bar15_ts": "2030-02-27 12:15:00", "visit_start5": "2030-02-27 12:20:00", "entry_ref": 1.5, "invalidation": 2.5,
         "invalidation_rule": "rule", "area": {"id": 8, "tf": "1H", "lo": 1.0, "hi": 2.0, "state": "TESTED"},
         "facts": {"trigger_tf": "5M", "line": "5M CHoCH", "choch_level": 1.7}}
    c = L.compact_entries([e])[0]
    assert c["trigger_tf"] == "5M" and c["trigger"]["ohlc"]["close"] == 1.5 and c["trigger"]["context_bar_ts"] == "2030-02-27 12:00:00"
    assert c["entry_ref"] == 1.5 and c["trigger"]["bar15_ts"] == "2030-02-27 12:15:00"
    assert "trigger_tf" not in L.compact_entries([{**e, "trigger_tf": None}])[0]   # a 15M entry: the payload as before


def test_read5_entries_carry_trigger_tf_ohlc_context_and_entry_ref_the_5m_close():
    V, lvl, d = _v5(REF, REF_SW, (100.0, 104.0), False, s=REFINE)
    V.step2 = None
    V.rsi_divergence = lambda *a, **k: {"found": None, "na": "test"}
    V.range_structure = lambda t: None
    out = EM5.read5(V, 25, "DOWN", [lvl])
    e = next(x for x in out["entries"] if x["model"] == "E1")
    F = TF.of(V)
    assert e["trigger_tf"] == "5M" and e["trigger_bar"] == 25 and e["trigger_ts"] == F.T(25) and e["trigger_bar_end"] == F.E(25)
    assert e["entry_ref"] == round(float(F.A["close"][25]), 2) and e["trigger_ohlc"]["close"] == e["entry_ref"]
    assert e["context_bar"] == int(F.k_of[25]) == 7 and e["context_bar_ts"] == str(V.levels.ts[7])
    assert e["trigger_bar15_ts"] == str(V.levels.ts[8]) and e["visit_id"] == "0@" + str(V.levels.ts[6])
    assert e["invalidation"] == pytest.approx(103.5)                       # structural: the base's far edge, never the 5M candle's high


def test_model_c_follows_trigger_tf_and_stays_off_by_default(oct12_5m, monkeypatch):
    from decision3 import model_c as MDC
    V = oct12_5m
    assert not MDC.is_on(V)
    seen = []
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    Vc = E3.V22(m15, s={"level_death_side": "role", "model_c": "on"}, ltf=ltf, futures=fut)
    real = MDC.entries_at

    def spy(V_, t, cyc, read=None):
        seen.append(read)
        return real(V_, t, cyc, read)
    monkeypatch.setattr(MDC, "entries_at", spy)
    Fc = Vc.trigger_frame()
    for j in range(Fc.n - 75, Fc.n):
        r = Vc.decide5(j)
        assert "model_c" in r and not (r["model_c"] or {}).get("error")
    assert all(x is not None for x in seen)                                 # every model C read went through the 5M reader


# ------------------------------------------------------------------------------------------------ no look-ahead on real data (private)
def test_no_look_ahead_real_banknifty_decide5_full_equals_cut_at_the_5m_close():
    """The mandatory full-vs-cut test (report §3) on the private BANKNIFTY export (skips cleanly without it; nothing stored here): one
    session built as engine3_live builds it at the close vs built with the data cut at a 5M close T (15M bars closed by T, 5M / FUT ≤ T,
    1m ≤ the last closed 15M end) — decide5 gives the same entries / armed / decision at T (the session's 5M trigger candles + the
    candle after each + the first and the last)."""
    import engine3_live as L
    import instruments as INS
    from bots_common import level_reaction as LR
    from decision3 import history as HI
    from tests.test_entry_models_real_bn_oct07 import _inputs
    m15_all, m5_all, m1_all, fut_all, daily_all = _inputs()
    D = pd.Timestamp("2026-10-15")
    S = L.DEFAULTS
    prev = INS.current()
    INS.set_current("BANKNIFTY")

    def build(now):
        def cut(df, days, minutes):
            x = df[(df["timestamp"] >= D - pd.Timedelta(days=days)) & (df["timestamp"] < D + pd.Timedelta(days=1))]
            return L.closed_session_bars(x, minutes, now)
        m15 = cut(m15_all, S["engine3_m15_days"], 15)
        dd = daily_all[daily_all["timestamp"] <= D]
        daily = LR.prepare_daily(L._naive(dd)[["timestamp", "open", "high", "low", "close"]], D)
        m1 = m1_all[(m1_all["timestamp"] >= m15["timestamp"].iloc[0]) & (m1_all["timestamp"] + pd.Timedelta(minutes=1) <= m15["bar_end"].iloc[-1])]
        return E3.V22(m15.drop(columns=["volume"], errors="ignore"), m1.reset_index(drop=True), daily, sealed=HI.sealed_fn("BANKNIFTY"),
                      ltf=cut(m5_all, S["engine3_ltf_days"], 5), futures=cut(fut_all, S["engine3_fut_days"], 5))

    def clean(r):
        return json.loads(json.dumps({"entries": [{k: v for k, v in e.items() if not k.startswith("_") and k != "pa_evidence"}
                                                  for e in r.get("entries") or []], "armed": r.get("armed"),
                                      "decision": r.get("decision")}, default=str))
    try:
        full = build(D + pd.Timedelta(hours=15, minutes=31))
        F = full.trigger_frame()
        js = [j for j in range(F.n) if pd.Timestamp(F.ts[j]).normalize() == D]
        ent = [j for j in js if full.decide5(j).get("entries")]
        assert ent, "the 15 Oct session has 5M entries"
        for j in sorted({js[0], js[-1], *ent, *[x + 1 for x in ent if x + 1 <= js[-1]]}):
            Vc = build(pd.Timestamp(F.end[j]))
            Fc = Vc.trigger_frame()
            assert pd.Timestamp(Fc.end[Fc.n - 1]) == pd.Timestamp(F.end[j])
            assert clean(full.decide5(j)) == clean(Vc.decide5(Fc.n - 1)), F.T(j)
    finally:
        INS.set_current(prev)
