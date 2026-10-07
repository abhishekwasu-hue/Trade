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
    wave_ctx: dict = field(default_factory=dict)        # addendum §6
    candle_ctx: dict = field(default_factory=dict)

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
        self.state, self.transitions = {}, []          # ARMED state machine (log)
        self._slot = {}
        self._gen_last, self._gen_fired = {}, {}      # generic (profile off) निर्णयाचं bookkeeping — reduce-only (profile on)
        self.profile_log = []                         # (t, key, generic ok, generic reason, profile dict) — shadow/on

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
        key = (st.degree, st.code, st.trade_dir, st.wave_start.ts)
        for fired in (self.fired, self._gen_fired):                               # profile on: generic ने fire केलं असतं तरी
            prev = fired.get(key)
            if prev is not None and self.cache[prev[0]].broken_by(prev[1] + 1, prev[2], prev[3], frame_index_at(self.frames[prev[0]], t)):
                return "hard_broken_no_reentry"                                   # §7: hard inv तुटल्यावर त्या setup ला re-entry नाही
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
        if s["c_leg_exhaustion_required"] and j - ext_idx <= 1 and self._c_leg_displacing(st, tf, ext_idx):
            return "C_leg_displacement"
        kw = dict(inv=st.hard_inv, min_start=max(a0, ws_idx + 1), extreme_idx=ext_idx, bars_last_subleg=bls,
                  div_ok=self._div_ok(st, tf, ext_idx, t), reclaim_ref=s["reclaim_ref"])
        gen_mr = self._strength_mr(tf, s["strength_ref"], ws_idx, ext_idx)
        r = RV.evaluate(b, j, st.trade_dir, st.levels, tol, s, mr_override=gen_mr, **kw)
        gen_ok, gen_dup = r["ok"], False
        if gen_ok:                                                                # generic निर्णयाचं dedup / re-entry bookkeeping
            last = self._gen_last.get(key)
            gen_dup = last is not None and pd.Timestamp(self._ts[tf][j - r["n"] + 1]) < last
            if not gen_dup:
                self._gen_last[key] = end
                self._gen_fired[key] = (tf, j, st.hard_inv, side)
        prof = None
        if s["candle_profile_mode"] != "off":
            fam, ref, rmin = self._profile(st)
            pr = RV.evaluate(b, j, st.trade_dir, st.levels, tol, s, mr_override=self._strength_mr(tf, ref, ws_idx, ext_idx), rmin=rmin, **kw)
            may_admit = fam in ("w4", "tri_e") and ref == "own_correction"        # §2: अपवाद फक्त wave 4 / triangle E
            prof = {"name": fam, "ref": ref, "ok": pr["ok"], "reason": pr["reason"], "score": round(pr["score"], 4),
                    "admitted": bool(pr["ok"] and not gen_ok and may_admit)}
            self.profile_log.append((pd.Timestamp(t), key, gen_ok, r["reason"], prof))
            if s["candle_profile_mode"] == "on":
                if pr["ok"] and not gen_ok and not may_admit:
                    pr = dict(pr, ok=False, reason="profile_not_reduce_only")      # reduce-only
                r = pr
        if not r["ok"]:
            ft = s["followthrough_mode"] == "addendum" or r["n"] == s["touch_reclaim_window"]
            if r["reason"] == RV.INDECISIVE and ft:
                self._transition(st, t, "WAIT_FOLLOWTHROUGH", "indecision")
            elif self.state.get(key) == "WAIT_FOLLOWTHROUGH" and r["reason"] != RV.INDECISIVE:
                self._transition(st, t, "ARMED", "follow-through नाही")
            return f"T_{r['reason']}"
        if gen_ok and gen_dup:
            return "dup_same_rejection"                                          # generic ने हाच नकार आधी वापरला
        o, h, l, c = r["comp"]
        soft = l - s["soft_buffer_pts"] if st.trade_dir > 0 else h + s["soft_buffer_pts"]
        sig = Signal(pd.Timestamp(t), st.degree, st.code, st.tier, st.direction, st.trade_dir, tf, j, list(st.levels), r["touched"],
                     st.hard_inv, st.inv_rule, soft, H, bls, st.extreme.price, st.extreme.ts, st.wave_start.ts, r["comp"], r["n"],
                     r["score"], st.vote, st.opp_max, list(st.alt_invs), list(st.parent_invs), st.recount, st.node.pattern,
                     st.node.current_wave, self.hash, [p.price for p in st.node.points],
                     st.parent.pattern if st.parent is not None else "", st.parent.current_wave if st.parent is not None else "",
                     [p.price for p in st.parent.points] if st.parent is not None else [])
        sig.wave_ctx = {"setup": st.code, "degree": st.degree, "tier": st.tier, "vote": round(st.vote, 4),
                        "opp_max": round(st.opp_max, 4), "n_alt_invs": len(st.alt_invs), "zone": [min(st.levels), max(st.levels)],
                        "hard_inv": st.hard_inv, "pattern": st.node.pattern, "wave": st.node.current_wave, "recount": st.recount,
                        "zone_known_at": max((p.confirmed_at for p in st.node.points), default=None)}
        sig.candle_ctx = {"n": r["n"], "comp": r["comp"], "touched": r["touched"], "strength": round(r["rng_ratio"], 4),
                          "close_loc": round(r["close_loc"], 4), "parts": r.get("parts", {}), "label": r.get("label"),
                          "followthrough": bool(r.get("followthrough")), "profile": prof, "strength_ref": s["strength_ref"]}
        win_start = pd.Timestamp(self._ts[tf][j - r["n"] + 1])
        last = self.last_window.get(key)
        if last is not None and win_start < last:
            return "dup_same_rejection"                                          # तोच नकार (TF बदलला तरी वेळेवरून)
        self.last_window[key] = end
        self.fired[key] = (tf, j, st.hard_inv, side)
        self._transition(st, t, "TRIGGERED", f"{sig.setup} n={r['n']} score={r['score']:.2f}")
        return sig

    # ------------------------------------------------------------------------------------------------ C1 helpers
    PROFILE = {"S3": "w4", "S4": "w4", "S5": "w4", "S14": "w4", "S6c": "tri_e", "S9": "tri_e", "S6a": "counter", "S6b": "counter",
               "S12": "counter"}

    def _profile(self, st):
        """(profile नाव, strength_ref, rejection_min) — addendum §2 तक्ता."""
        s = self.s
        fam = self.PROFILE.get(st.code, "default")
        if st.code == "S7" and st.node.pattern == "flat" and getattr(st.node, "subtype", "") == "flat_exp":
            fam = "flat_c"
        ref = {"w4": s["profile_ref_w4"], "tri_e": s["profile_ref_tri_e"], "flat_c": s["profile_ref_flat_c"]}.get(fam, s["profile_ref_default"])
        if ref == "last_20":
            ref = s["strength_ref"]                                              # profile चा last_20 = generic संदर्भ (time_slot असेल तर तो)
        rmin = s["rejection_min"] + (s["profile_counter_extra"] if fam == "counter" else 0.0)
        return fam, ref, rmin

    def _strength_mr(self, tf, ref, ws_idx, ext_idx):
        """None ⇒ सध्याचं (window आधीचा median20). own_correction ⇒ correction च्या bars चा median range (ws..ext, causal);
        time_slot ⇒ window-start a ला max(median20[a], त्याच 15m slot चा मागच्या sessions चा median) — callable(a)."""
        if ref == "last_20":
            return None
        b = self.bars[tf]
        if ref == "own_correction":
            seg = (b.h[ws_idx:ext_idx + 1] - b.l[ws_idx:ext_idx + 1])
            return float(np.median(seg)) if len(seg) >= 3 else None
        slot = self._slot_median(tf)

        def at(a):
            v, m20 = slot[a], b.mr[a]
            if not np.isfinite(v):
                return None                                                      # slot इतिहास अपुरा ⇒ median20
            return float(max(v, m20)) if np.isfinite(m20) else float(v)
        return at

    def _slot_median(self, tf):
        """प्रत्येक bar साठी: त्याच 15m slot ची मागच्या `slot_median_sessions` sessions मधली (प्रत्येक session चा त्या slot मधला
        median bar range) median — चालू session वगळून (shift 1 session) ⇒ भविष्यातली/आजची candle नाही."""
        key = (tf, self.s["slot_median_sessions"])
        if key not in self._slot:
            fr = self.frames[tf]
            rng = (fr["high"] - fr["low"]).astype(float)
            ts = pd.to_datetime(fr["timestamp"])
            d = pd.DataFrame({"day": ts.dt.normalize(), "slot": ts.dt.floor("15min").dt.strftime("%H:%M"), "rng": rng})
            per = d.groupby(["slot", "day"])["rng"].median().reset_index().sort_values(["slot", "day"])
            per["ref"] = per.groupby("slot")["rng"].transform(
                lambda x: x.shift(1).rolling(self.s["slot_median_sessions"], min_periods=5).median())
            self._slot[key] = d.merge(per[["slot", "day", "ref"]], on=["slot", "day"], how="left")["ref"].to_numpy(float)
        return self._slot[key]

    def _c_leg_displacing(self, st, tf, ext_idx):
        """C-leg अजून displacement candles ने: extreme पर्यंतच्या शेवटच्या 2 bars पैकी एक pullback दिशेने displacement."""
        b, s, d = self.bars[tf], self.s, st.trade_dir
        for k in (ext_idx, ext_idx - 1):
            if k < 1 or not np.isfinite(b.mr[k]):
                continue
            rng = b.h[k] - b.l[k]
            if rng <= 0 or rng < s["strength_min"] * b.mr[k]:
                continue
            loc = (b.c[k] - b.l[k]) / rng if d > 0 else (b.h[k] - b.c[k]) / rng      # pullback दिशेच्या टोकापासून
            if loc <= s["break_close_loc"]:
                return True
        return False

    def _arm(self, st, t):
        """Correction चं टोक zone मध्ये पोचलं ⇒ ARMED. त्याआधी candle evaluation चा अर्थ नाही (log)."""
        key = (st.degree, st.code, st.trade_dir, st.wave_start.ts)
        if self.state.get(key, "IDLE") not in ("IDLE", "EXPIRED"):
            return
        x = st.extreme.price                                                     # correction चं टोक (t पर्यंत) zone मध्ये पोचलं
        if (x <= max(st.levels)) if st.trade_dir > 0 else (x >= min(st.levels)):
            self._transition(st, t, "ARMED", "price in zone")

    def _expire(self, d, t, st):
        """त्या degree वर आधीचा ARMED/WAIT setup आता नाही (count बदलला / inv तुटला / gray) ⇒ EXPIRED."""
        cur = None if st is None else (st.degree, st.code, st.trade_dir, st.wave_start.ts)
        for key, state in list(self.state.items()):
            if key[0] == d and key != cur and state in ("ARMED", "WAIT_FOLLOWTHROUGH"):
                self.state[key] = "EXPIRED"
                self.transitions.append((pd.Timestamp(t), key, state, "EXPIRED", "setup गेला"))

    def _transition(self, st, t, to, why):
        """ARMED state machine (addendum §1): IDLE → ARMED → (WAIT_FOLLOWTHROUGH) → TRIGGERED; ARMED → EXPIRED. Log फक्त."""
        key = (st.degree, st.code, st.trade_dir, st.wave_start.ts)
        prev = self.state.get(key, "IDLE")
        if prev == "TRIGGERED" and to in ("ARMED", "WAIT_FOLLOWTHROUGH"):
            return                                                               # signal झाल्यावर (re-entry सह) फक्त EXPIRED
        if prev in ("IDLE", "EXPIRED") and to != "ARMED":                                     # zone tolerance मध्ये touch ⇒ आधी ARMED
            self.transitions.append((pd.Timestamp(t), key, prev, "ARMED", "zone tolerance मध्ये touch"))
            prev = "ARMED"
        if prev != to:
            self.state[key] = to
            self.transitions.append((pd.Timestamp(t), key, prev, to, why))

    def step(self, t):
        snap = self.eng.snapshot(t)
        out = []
        for d in self.s["trade_degrees_enabled"]:
            st = degree_setup(self.eng, snap, d, t)
            self._expire(d, t, None if isinstance(st, str) else st)
            if isinstance(st, str):
                self.reasons.append((t, d, None, st))
                continue
            self._arm(st, t)
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
