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
