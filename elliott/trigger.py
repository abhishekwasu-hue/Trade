"""
elliott/trigger.py — E2: entry trigger (spec §6 C0–C4, T1–T7; §14 Q2/Q3) आणि signal scanner
------------------------------------------------------------------------------------------
🎓 दर बंद structure bar (t) ला: count snapshot → प्रत्येक trade degree वर setup (setups.py) → setup च्या **trigger TF** (TTF)
चा bar नेमका t ला बंद झाला असेल तर trigger तपासणी:
  TTF   level_tf: ज्या corrective wave च्या शेवटी entry, ती tf_bars_min–tf_bars_max बंद candles मध्ये दिसेल असा सर्वात लहान TF
        (swings.auto_tf). min पेक्षा कमी ⇒ आतली रचना दिसत नाही ⇒ entry नाही.
  C2    hard_inv वर TTF वर real break नाही (wave सुरू झाल्यापासून).
  R4    correction च्या आत किमान min_corrective_legs lower-degree legs (A-end ban). D ≥ 1: D−1 चे confirmed pivots;
        D0: TTF चे 1-bar fractals (सर्वात लहान दिसणारी रचना) [अनुमान, WORK_LOG].
  T7    no-breakout: reclaim close शेवटच्या sub-leg च्या origin H च्या आतच (bull put: close < H). H = extreme आधीचा शेवटचा
        D−1 उलट pivot (नसल्यास TTF 1-bar fractal swing).
  T1–T4 reversal.evaluate (composite 1–3 candles; touch/reclaim/strength/score).
  T5    entry_start ≤ bar_end ≤ entry_end; composite चे सगळे candles त्याच session चे आणि entry_start नंतर सुरू झालेले
        (opening gap candle composite मध्ये नाही — golden "gap वर entry नाही").
  T6    vote ≥ vote_min आणि उलट count < alt_block_weight (setups.py).
Signal knowable_at = TTF bar चा bar_end (= t). Fill पुढच्या TTF bar च्या open वर (E3/E4). एकाच setup-instance वर नवीन signal
फक्त नवीन composite (आधीच्या signal नंतर सुरू होणारा); त्या setup चा hard inv खरा तुटला असेल तर पुन्हा कधीच नाही (§7).
बाकी re-entry (soft stop नंतर) चा निर्णय E3 चा.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import reversal as RV
from . import swings as W
from .breaks import BreakCache, frame_index_at
from .counts import CountEngine
from .settings import snapshot as settings_snapshot
from .setups import Setup, degree_setup


@dataclass
class Signal:
    t: pd.Timestamp                    # knowable_at (TTF reclaim bar चा bar_end)
    degree: int
    setup: str
    tier: str
    direction: str                     # bull_put / bear_call
    trade_dir: int
    ttf: str
    ttf_idx: int
    levels: list
    touched: float
    hard_inv: float
    inv_rule: str
    soft_stop: float
    sub_origin: float                  # T7 चा H
    bars_last_subleg: int
    extreme: float
    extreme_ts: pd.Timestamp
    wave_start_ts: pd.Timestamp
    comp: tuple                        # composite (o, h, l, c)
    n: int
    score: float
    vote: float
    opp_max: float
    alt_invs: list = field(default_factory=list)
    parent_invs: list = field(default_factory=list)
    recount: bool = False
    pattern: str = ""
    current_wave: str = ""
    settings_hash: str = ""
    points: list = field(default_factory=list)         # count चे completed pivots (किंमत) — targets (E3)
    parent_pattern: str = ""
    parent_wave: str = ""
    parent_points: list = field(default_factory=list)

    @property
    def key(self):
        return (self.degree, self.setup, self.trade_dir, self.wave_start_ts)


def _rsi(close, n):
    d = np.diff(close, prepend=close[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)


def _hm(x):
    h, m = str(x).split(":")
    return int(h) * 60 + int(m)


class Scanner:
    """df1m = NIFTY spot 1m (पूर्ण उपलब्ध डेटा); step(t) फक्त t पर्यंत माहीत असलेलं वापरतो (engine + bar_end ≤ t)."""

    def __init__(self, df1m, s, md=None):
        self.s = s
        self.md = md if md is not None else W.multi_degree(df1m, s)
        self.eng = CountEngine(self.md, s)
        tfs = set(s["auto_tfs"]) | {s["trigger_tf_fixed"]} | set(s["degree_tf"])
        self.frames = {tf: W.build_frame(df1m, tf) for tf in tfs}
        self.bars, self.atr, self.cache = {}, {}, {}
        for tf, fr in self.frames.items():
            self.cache[tf] = BreakCache(fr, s)
            self.bars[tf] = RV.Bars(fr, self.cache[tf].mr)
            self.atr[tf] = W.atr(fr, s["atr_len"])
        self._ts = {tf: fr["timestamp"].to_numpy("datetime64[ns]") for tf, fr in self.frames.items()}
        self._end = {tf: fr["bar_end"].to_numpy("datetime64[ns]") for tf, fr in self.frames.items()}
        self._rsi = {}
        self.hash = settings_snapshot(s)["hash"]
        self.last_window = {}           # setup key → आधीच्या signal च्या composite चा शेवट (bar_end — TF-निरपेक्ष)
        self.fired = {}                 # setup key → (tf, idx, hard_inv, side) — आधीच्या signal चा hard inv (re-entry बंदी)
        self.signals = []
        self.reasons = []               # (t, degree, setup|None, reason) — report साठी

    # ------------------------------------------------------------------------------------------------------------
    def _tf_for(self, st, t):
        s = self.s
        if s["trigger_tf_mode"] == "fixed":
            return s["trigger_tf_fixed"], None
        if s["degree_tf_mode"] == "fixed":
            return s["degree_tf"][st.degree], None
        tf, counts, _ = W.auto_tf({k: self.frames[k] for k in s["auto_tfs"]}, st.wave_start.ts, t, s)
        if counts[tf] < s["tf_bars_min"]:
            return None, "tf_bars_min"
        return tf, None

    def _idx_of(self, tf, ts):
        """ts असलेला TTF bar (timestamp ≤ ts) चा index."""
        return int(np.searchsorted(self._ts[tf], np.datetime64(pd.Timestamp(ts), "ns"), "right")) - 1

    def _sub_structure(self, st, t, tf, ws_idx, ext_idx):
        """(legs, H, H_idx) — corrective wave च्या आतली रचना. D ≥ 1 ⇒ D−1 confirmed pivots (t ला माहीत); नाहीतर/अपुरे ⇒ TTF fractals."""
        nm = st.trade_dir
        want = "H" if nm > 0 else "L"                                    # bull put: correction खाली ⇒ sub-leg origin = high
        if st.degree >= 1:
            lower, _ = self.eng.known(st.degree - 1, t)
            inside = [p for p in lower if st.wave_start.ts < p.ts < st.extreme.ts]
            opp = [p for p in inside if p.kind == want]
            if opp:
                hi = max(self._idx_of(tf, opp[-1].ts), ws_idx)
                return len(inside) + 1, opp[-1].price, hi
        b = self.bars[tf]
        seg = self.frames[tf].iloc[ws_idx:ext_idx + 1]
        piv = [p for p in W._alternating_fractals(seg, 1) if 0 < p[1] < len(seg) - 1] if len(seg) >= 3 else []
        legs = len(piv) + 1
        k = ext_idx
        if nm > 0:
            while k - 1 >= ws_idx and b.h[k - 1] >= b.h[k]:
                k -= 1
            return legs, float(b.h[k]), k
        while k - 1 >= ws_idx and b.l[k - 1] <= b.l[k]:
            k -= 1
        return legs, float(b.l[k]), k

    def _div_ok(self, st, tf, ext_idx, t):
        if self.s["rejection_weights"][4] <= 0 or st.degree < 1:
            return None
        lower, _ = self.eng.known(st.degree - 1, t)
        kind = "L" if st.trade_dir > 0 else "H"
        prev = [p for p in lower if p.kind == kind and st.wave_start.ts < p.ts < st.extreme.ts]
        if not prev:
            return None
        key = (tf, self.s["rsi_len"])
        if key not in self._rsi:
            self._rsi[key] = _rsi(self.bars[tf].c, self.s["rsi_len"])
        r = self._rsi[key]
        pi = self._idx_of(tf, prev[-1].ts)
        beyond = (st.extreme.price < prev[-1].price) if st.trade_dir > 0 else (st.extreme.price > prev[-1].price)
        better = (r[ext_idx] > r[pi]) if st.trade_dir > 0 else (r[ext_idx] < r[pi])
        return bool(beyond and better)

    def trigger(self, st: Setup, t):
        """Signal किंवा कारण (str)."""
        s = self.s
        tf, why = self._tf_for(st, t)
        if tf is None:
            return why
        j = frame_index_at(self.frames[tf], t)
        if j < 0 or self._end[tf][j] != np.datetime64(pd.Timestamp(t), "ns"):
            return "not_ttf_close"
        prev = self.fired.get((st.degree, st.code, st.trade_dir, st.wave_start.ts))
        if prev is not None and self.cache[prev[0]].broken_by(prev[1] + 1, prev[2], prev[3], frame_index_at(self.frames[prev[0]], t)):
            return "hard_broken_no_reentry"                                       # §7: hard inv तुटल्यावर त्या setup ला re-entry नाही
        end = pd.Timestamp(self._end[tf][j])
        mins = end.hour * 60 + end.minute
        if not _hm(s["entry_start"]) <= mins <= _hm(s["entry_end"]):
            return "T5_time"
        day_open = end.normalize() + pd.Timedelta(minutes=_hm(s["entry_start"]))
        a0 = int(np.searchsorted(self._ts[tf], np.datetime64(day_open, "ns"), "left"))
        ws_idx = max(self._idx_of(tf, st.wave_start.ts), 0)
        ext_idx = self._idx_of(tf, st.extreme.ts)
        if ext_idx < ws_idx or ext_idx > j:
            return "extreme_outside"
        side = st.inv_side
        if self.cache[tf].broken_by(ws_idx + 1, st.hard_inv, side, j):
            return "C2_inv_broken"
        legs, H, h_idx = self._sub_structure(st, t, tf, ws_idx, ext_idx)
        if legs < s["min_corrective_legs"]:
            return "R4_legs"
        b = self.bars[tf]
        if not (b.c[j] < H if st.trade_dir > 0 else b.c[j] > H):
            return "T7_breakout"
        atr = self.atr[tf][j]
        tol = s["zone_tol_atr"] * (atr if np.isfinite(atr) else 0.0)
        bls = max(ext_idx - h_idx, 1)
        r = RV.evaluate(b, j, st.trade_dir, st.levels, tol, s, inv=st.hard_inv, min_start=max(a0, ws_idx + 1),
                        extreme_idx=ext_idx, bars_last_subleg=bls, div_ok=self._div_ok(st, tf, ext_idx, t),
                        reclaim_ref=s["reclaim_ref"])
        if not r["ok"]:
            return f"T_{r['reason']}"
        o, h, l, c = r["comp"]
        soft = l - s["soft_buffer_pts"] if st.trade_dir > 0 else h + s["soft_buffer_pts"]
        sig = Signal(pd.Timestamp(t), st.degree, st.code, st.tier, st.direction, st.trade_dir, tf, j, list(st.levels), r["touched"],
                     st.hard_inv, st.inv_rule, soft, H, bls, st.extreme.price, st.extreme.ts, st.wave_start.ts, r["comp"], r["n"],
                     r["score"], st.vote, st.opp_max, list(st.alt_invs), list(st.parent_invs), st.recount, st.node.pattern,
                     st.node.current_wave, self.hash, [p.price for p in st.node.points],
                     st.parent.pattern if st.parent is not None else "", st.parent.current_wave if st.parent is not None else "",
                     [p.price for p in st.parent.points] if st.parent is not None else [])
        win_start = pd.Timestamp(self._ts[tf][j - r["n"] + 1])
        last = self.last_window.get(sig.key)
        if last is not None and win_start < last:
            return "dup_same_rejection"                                          # तोच नकार (TF बदलला तरी वेळेवरून)
        self.last_window[sig.key] = end
        self.fired[sig.key] = (tf, j, st.hard_inv, side)
        return sig

    def step(self, t):
        snap = self.eng.snapshot(t)
        out = []
        for d in self.s["trade_degrees_enabled"]:
            st = degree_setup(self.eng, snap, d, t)
            if isinstance(st, str):
                self.reasons.append((t, d, None, st))
                continue
            res = self.trigger(st, t)
            if isinstance(res, str):
                self.reasons.append((t, d, st.code, res))
                continue
            out.append(res)
        self.signals.extend(out)
        return out

    def times(self, skip=300):
        """Scan वेळा: structure TF आणि सगळ्या trigger TFs च्या bar_end चा union (structure TF trigger TF पेक्षा मोठा असला तरी
        प्रत्येक TTF close तपासला जातो). पहिले `skip` structure bars warm-up."""
        st = self.md[0]["frame"]["bar_end"]
        t0 = st.iloc[min(skip, len(st) - 1)] if len(st) else None
        allt = np.unique(np.concatenate([self._end[tf] for tf in self.frames] + [st.to_numpy("datetime64[ns]")]))
        return [pd.Timestamp(x) for x in allt if t0 is not None and x >= np.datetime64(t0, "ns")]

    def run(self, times=None):
        for t in (self.times() if times is None else times):
            self.step(t)
        return self.signals
