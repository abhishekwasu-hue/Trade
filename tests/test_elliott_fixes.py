"""tests/test_elliott_fixes.py — E4 review fixes: F3 (H fallback नाही ⇒ skip), F4 (count आणि trade exit एकाच confirmation TF वर)."""
import types

import numpy as np
import pandas as pd

from elliott import backtest as BT
from elliott import settings as S
from elliott import swings as W
from elliott import trigger as TR
from elliott.confirm import ConfirmTF

T0 = pd.Timestamp("2021-03-01 09:15")


def _cfg(**k):
    c, e = S.validate(k)
    assert not e, e
    return c


def _frame5(rows):
    ts = [T0 + pd.Timedelta(minutes=5 * i) for i in range(len(rows))]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df.insert(0, "timestamp", ts)
    df.insert(1, "bar_end", [t + pd.Timedelta(minutes=5) for t in ts])
    return df


def test_f3_no_fractal_origin_means_skip_not_extreme_bar_high():
    down = _frame5([(110 - i, 111 - i, 108 - i, 109 - i) for i in range(12)])      # प्रत्येक bar lower high ⇒ sub-leg origin नाही
    fake = types.SimpleNamespace(frames={"5m": down})
    st = types.SimpleNamespace(degree=0, trade_dir=1)
    legs, H, hi = TR.Scanner._sub_structure(fake, st, None, "5m", 0, 11)
    assert H is None and hi is None                                                  # आधी: H = extreme bar चा high, bls = 1
    rows = [(110 - i, 111 - i, 108 - i, 109 - i) for i in range(6)] + [(104, 109, 103, 108), (108, 108.5, 102, 103)] + \
           [(103 - i, 104 - i, 100 - i, 101 - i) for i in range(4)]
    bounce = _frame5(rows)
    legs, H, hi = TR.Scanner._sub_structure(types.SimpleNamespace(frames={"5m": bounce}), st, None, "5m", 0, len(rows) - 1)
    assert H == 109.0 and hi == 6


def _one_min(closes_5m):
    """प्रत्येक 5m bar साठी 5 सारखे 1m bars (o=h=l=c नाही — थोडी range)."""
    rows = []
    t = T0
    for o, h, l, c in closes_5m:
        for k in range(5):
            rows.append((t, o if k == 0 else c, h, l, c))
            t += pd.Timedelta(minutes=1)
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def _shake_frames(tail=6, shake=None):
    base = [(100, 101, 99, 100)] * 30
    shake = shake or [(99, 99.5, 96.8, 97.0), (97.0, 97.6, 96.5, 97.2), (97.2, 100.5, 97.0, 100.2)]
    d1 = _one_min(base + shake + [(100, 101, 99, 100)] * tail)
    return {"5m": W.build_frame(d1, "5m"), "15m": W.build_frame(d1, "15m")}


def test_f4_displacement_on_5m_false_break_on_15m():
    frames = _shake_frames()
    t = frames["5m"]["bar_end"].iloc[-1]
    pivot = frames["5m"]["timestamp"].iloc[5]
    on5 = ConfirmTF(frames, _cfg(break_confirm_tf="5m", break_retest_confirm=False))
    on15 = ConfirmTF(frames, _cfg(break_confirm_tf="15m", break_retest_confirm=False))
    assert on5.broken(0, pivot, 98.0, "below", t)                                    # 5m: ताकदीचा (displacement) break
    assert not on15.broken(0, pivot, 98.0, "below", t)                               # 15m: close level वर ⇒ false break


def test_f4_acceptance_path_two_weak_closes():
    weak = [(98.5, 98.6, 97.0, 97.3), (97.3, 97.6, 96.9, 97.2), (97.2, 100.6, 97.1, 100.4)]    # range < 1.2 × MR ⇒ कमकुवत
    frames = _shake_frames(shake=weak)
    pivot, t = frames["5m"]["timestamp"].iloc[5], frames["5m"]["bar_end"].iloc[-1]
    c = ConfirmTF(frames, _cfg(break_confirm_tf="5m", break_retest_confirm=False)).confirm(0, pivot, 98.0, "below", t)
    assert c is not None and c[1] == frames["5m"]["bar_end"].iloc[31]               # दुसऱ्या कमकुवत close वर (acceptance)


def test_f4_level_tf_verdict_is_sticky_across_tf_switch():
    frames = _shake_frames(tail=30)
    s = _cfg(auto_tfs=["5m", "15m"], break_retest_confirm=False)
    cf = ConfirmTF(frames, s)
    pivot = frames["5m"]["timestamp"].iloc[5]
    seen = []
    for i in range(33, len(frames["5m"])):
        t = frames["5m"]["bar_end"].iloc[i]
        seen.append((cf.tf_for(0, pivot, t), cf.broken(0, pivot, 98.0, "below", t)))
    assert ("5m", True) in seen and any(tf == "15m" for tf, _ in seen)               # TF 5m → 15m बदलला
    assert all(b for _, b in seen)                                                   # एकदा मेलेला count पुन्हा जिवंत नाही
    late = _shake_frames(tail=30)                                                    # उलट: 15m चा break 5m सक्रिय काळात नाही
    cf2 = ConfirmTF(late, _cfg(auto_tfs=["5m", "15m"], tf_bars_max=12, break_retest_confirm=False))
    t0 = late["5m"]["bar_end"].iloc[-1]
    assert cf2.tf_for(0, pivot, t0) == "15m"
    assert cf2.confirm(0, pivot, 98.0, "below", t0) is None or cf2.confirm(0, pivot, 98.0, "below", t0)[0] == "15m"


def test_f4_count_and_trade_same_verdict_with_real_confirm():
    frames = _shake_frames(tail=30)
    cf = ConfirmTF(frames, _cfg(auto_tfs=["5m", "15m"], break_retest_confirm=False))
    from elliott.counts import CountEngine
    eng = CountEngine.__new__(CountEngine)
    eng.confirm = cf
    pivot = frames["5m"]["timestamp"].iloc[5]
    node = types.SimpleNamespace(points=[types.SimpleNamespace(ts=pivot, bar_idx=5)], invs=[(98.0, "below", "R1")])
    sig = types.SimpleNamespace(degree=0, wave_start_ts=pivot, inv_degree=0, inv_start_ts=pivot, trade_dir=1)
    tr = types.SimpleNamespace(sig=sig, tf="5m", inv_from=20, entry_idx=20, st=types.SimpleNamespace(hard_inv=98.0))
    bt = types.SimpleNamespace(sc=types.SimpleNamespace(confirm=cf, frames=frames))
    for i in range(20, len(frames["5m"])):
        t = frames["5m"]["bar_end"].iloc[i]
        assert (not CountEngine._valid(eng, 0, node, i, t)) == BT.Backtest._hard_broken(bt, tr, t, i, "below")


def test_f4_trigger_fixed_mode_uses_trigger_tf():
    frames = _shake_frames()
    cf = ConfirmTF(frames, _cfg(trigger_tf_mode="fixed", trigger_tf_fixed="15m"))
    assert cf.tf_for(2, frames["5m"]["timestamp"].iloc[5], frames["5m"]["bar_end"].iloc[-1]) == "15m"


def test_f4_count_engine_and_trade_exit_use_the_same_confirm():
    calls = []

    class Spy:
        def tf_for(self, d, st, t):
            return "15m"

        def broken(self, d, st, lvl, side, t, tf=None, since=None):
            calls.append(("broken", d, st))
            return True

        def confirm(self, d, st, lvl, side, t, tf=None):
            return None

    sig = types.SimpleNamespace(degree=0, wave_start_ts=T0 - pd.Timedelta(hours=1), inv_degree=1, inv_start_ts=T0, trade_dir=1)
    tr = types.SimpleNamespace(sig=sig, tf="5m", inv_from=3, entry_idx=3, st=types.SimpleNamespace(hard_inv=98.0))
    bt = types.SimpleNamespace(sc=types.SimpleNamespace(confirm=Spy(), frames={"5m": _frame5([(1, 1, 1, 1)] * 5)}))
    assert BT.Backtest._hard_broken(bt, tr, T0 + pd.Timedelta(hours=1), 4, "below")
    assert calls == [("broken", 1, T0)]                                              # trade exit: तोच ConfirmTF, inv मालकाची degree/start
    from elliott.counts import CountEngine
    eng = CountEngine.__new__(CountEngine)
    eng.confirm = Spy()
    node = types.SimpleNamespace(points=[types.SimpleNamespace(ts=T0, bar_idx=0)], invs=[(98.0, "below", "R1")])
    assert not CountEngine._valid(eng, 1, node, 10, T0 + pd.Timedelta(hours=1))      # count तोच निर्णय (broken ⇒ invalid)
    assert calls[-1] == ("broken", 1, T0)


def test_f5_completed_wave_rules_use_count_inv_basis():
    import importlib.util, os
    spec = importlib.util.spec_from_file_location("tc", os.path.join(os.path.dirname(__file__), "test_elliott_counts.py"))
    TC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(TC)
    from elliott import patterns as P
    s0 = _cfg()
    pts = TC.piv([100, 120, 99.5])                                                   # wave 2 चा wick origin खाली 0.5
    no_break = lambda lvl, side, a, b: False                                         # noqa: E731 — close आत
    real = lambda lvl, side, a, b: True                                              # noqa: E731
    assert P.build(1, "impulse", pts, TC.tent(130, 30), s0, broke=no_break) is not None   # real_break: wick ⇒ count जिवंत
    why = []
    assert P.build(1, "impulse", pts, TC.tent(130, 30), s0, broke=real, why=why) is None and why == ["R1"]
    assert P.build(1, "impulse", pts, TC.tent(130, 30), _cfg(count_inv_basis="wick"), broke=no_break) is None
    assert P.build(1, "impulse", TC.piv([100, 120, 100]), TC.tent(130, 30), _cfg(count_inv_basis="wick")) is not None  # double bottom
    zz = TC.piv([200, 170, 200.4])                                                   # zigzag B चा wick A origin पलीकडे
    assert P.build(1, "zigzag", zz, TC.tent(160, 30), s0, broke=no_break) is not None
    assert P.build(1, "zigzag", zz, TC.tent(160, 30), s0, broke=real) is None


def test_f11_holdout_extension_file_is_refused():
    import os
    import pytest
    from elliott import data_policy as DP
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with pytest.raises(DP.HoldoutError):
        DP.load_parquet(os.path.join(root, "data", "nifty50_daily_extension.parquet"))
    with pytest.raises(DP.HoldoutError):
        DP.check_range("2024-03-28", "2026-08-20")
    for folder in ("elliott", "research"):                                           # elliott/research loaders हा file वाचत नाहीत
        for f in os.listdir(os.path.join(root, folder)):
            if f.endswith(".py") and (folder == "elliott" or f.startswith("elliott_")):
                src = open(os.path.join(root, folder, f), encoding="utf-8").read()
                assert "daily_extension" not in src or f == "data_policy.py", f


def test_f7_contract_master_lot_step_and_paper_requires_master():
    import pytest
    from elliott import contract_master as CM
    from elliott import contracts as CT
    rows = [{"expiry": e, "strike_price": k, "lot_size": lot, "instrument_type": t}
            for e, lot in (("2024-11-14", 25), ("2024-11-21", 75), ("2024-11-28", 75)) for k in range(23000, 23300, 50) for t in ("CE", "PE")]
    cm = CM.ContractMaster(rows)
    assert cm.lots()[pd.Timestamp("2024-11-14").date()] == 25 and cm.lots()[pd.Timestamp("2024-11-21").date()] == 75   # contract-wise
    assert cm.strike_step() == 50
    fr = cm.expiry_frame("2024-11-10")
    assert list(fr["kind"]) == ["weekly", "weekly", "monthly"]
    cal = CT.TradingCalendar(pd.bdate_range("2024-11-01", "2024-12-31"))
    with pytest.raises(CM.ContractMasterMissing):
        CM.expiry_book_for("paper", cal)
    book = CM.expiry_book_for("paper", cal, cm, listed_on="2024-11-10")
    assert book.source == "contract_master" and book.choose("2024-11-12", _cfg())[0] == pd.Timestamp("2024-11-14").date()
    assert CM.lot_for(cm, "2024-11-21") == 75
    with pytest.raises(CM.ContractMasterMissing):
        CM.lot_for(cm, "2024-12-05")                                                  # table fallback नाही
    with pytest.raises(CM.ContractMasterMissing):
        CM.expiry_book_for("PAPER", cal)                                              # case-insensitive
    with pytest.raises(ValueError):
        CM.expiry_book_for("papr", cal)
    assert CM.expiry_book_for("backtest", cal).source == "rule"
    with pytest.raises(ValueError):
        CM.ContractMaster([{"expiry": "2024-11-14", "strike_price": 1, "lot_size": 25, "instrument_type": "CE"},
                           {"expiry": "2024-11-14", "strike_price": 2, "lot_size": 75, "instrument_type": "PE"}]).lots()


def test_f10_followthrough_score_gate_option():
    import importlib.util, os
    spec = importlib.util.spec_from_file_location("c1", os.path.join(os.path.dirname(__file__), "test_elliott_c1.py"))
    C1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C1)
    from elliott import reversal as RV
    rows = [(100, 101, 88, 95), (95, 97, 93, 94), (94, 98, 93, 95.5), (95.5, 104, 95, 103)]
    b = C1.bars_of(C1.frame(rows))
    assert RV.evaluate(b, 33, 1, [94.0], 0.0, _cfg(followthrough_mode="addendum"))["ok"]
    strict = _cfg(followthrough_mode="addendum", followthrough_score_gate=True, followthrough_score_relax=0.0, rejection_min=0.95)
    assert not RV.evaluate(b, 33, 1, [94.0], 0.0, strict).get("followthrough")


def test_f5_completed_check_uses_violating_wave_start_and_keeps_origin_inv():
    import importlib.util, os
    spec = importlib.util.spec_from_file_location("tc2", os.path.join(os.path.dirname(__file__), "test_elliott_counts.py"))
    TC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(TC)
    from elliott import patterns as P
    from elliott.counts import CountEngine
    pts = TC.piv([100, 120, 99.5])
    seen = []

    class Spy:
        def broken(self, d, st, lvl, side, t, tf=None, since=None):
            seen.append(st)
            return False
    eng = CountEngine.__new__(CountEngine)
    eng.confirm = Spy()
    fr = pd.DataFrame({"bar_end": [T0 + pd.Timedelta(minutes=5 * (i + 1)) for i in range(200)]})
    eng._completed_break(1, pts, fr)(100.0, "below", 0, 2)
    assert seen == [pts[1].ts]                                                       # wave 2 ची सुरुवात — _valid सारखीच (review H1)
    n = P.build(1, "impulse", pts, TC.tent(130, 30), _cfg(), broke=lambda *a: False)
    assert (100.0, "below", "R1") in n.invs                                          # M1: wick-only R1 ⇒ origin inv कायम
