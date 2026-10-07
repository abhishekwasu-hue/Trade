"""
elliott/confirm.py — real-break confirmation TF (spec §7 / §11 `break_confirm_tf`, review F4)
------------------------------------------------------------------------------------------
🎓 Count engine (count मेला का?) आणि trade exit (hard inv तुटला का?) **एकाच TF वर, एकाच नियमाने** तपासले पाहिजेत. नाहीतर
15m trade उघडा असताना 5m वरच्या दोन कमकुवत closes ने count मरतो (spec §7 नुसार निषिद्ध).

`break_confirm_tf`:
  level_tf (default) — त्या wave चा TF: trigger_tf_mode fixed ⇒ trigger_tf_fixed; fixed degree mode ⇒ degree_tf[d];
                       auto ⇒ auto_tf(wave start → t) (8–40 bars नियम, trigger TF सारखाच; wave लांब होते तसा TF मोठा).
  5m / 15m           — ठराविक TF.

**Sticky (review H1):** auto mode मध्ये TF वेळेनुसार बदलतो. प्रत्येक TF फक्त त्याच्या "सक्रिय" काळातच (त्या bar च्या close ला
tf_for = तो TF) break confirm करू शकतो; सगळ्या काळांपैकी सर्वात आधीचा confirm. TF निवड wave start आणि bar grids वरूनच ठरते ⇒
एकदा confirm झालेला break नंतर TF बदलला तरी जात नाही, आणि मागच्या काळातला नवा break अचानक उगवत नाही. Causal: t नंतरचा bar नाही.
"""
import numpy as np
import pandas as pd

from . import swings as W
from .breaks import BreakCache


class ConfirmTF:
    def __init__(self, frames, s, caches=None):
        self.frames, self.s = frames, s
        self._cache = dict(caches or {})
        self._ts = {tf: fr["timestamp"].to_numpy("datetime64[ns]") for tf, fr in frames.items()}
        self._end = {tf: fr["bar_end"].to_numpy("datetime64[ns]") for tf, fr in frames.items()}
        self._spans = {}

    def cache(self, tf):
        if tf not in self._cache:
            self._cache[tf] = BreakCache(self.frames[tf], self.s)
        return self._cache[tf]

    @staticmethod
    def _ns(x):
        return np.datetime64(pd.Timestamp(x), "ns")

    def _auto_pick(self, start, t):
        s = self.s
        counts = {}
        for tf in s["auto_tfs"]:
            e = self._end[tf]
            counts[tf] = int(np.searchsorted(e, t, "right")) - int(np.searchsorted(e, start, "right"))
        order = sorted(counts, key=W.TF_MIN.get)
        for tf in order:                                                 # swings.auto_tf चाच नियम
            if s["tf_bars_min"] <= counts[tf] <= s["tf_bars_max"]:
                return tf
        enough = [x for x in order if counts[x] >= s["tf_bars_min"]]
        return enough[-1] if enough else order[0]

    def spans(self, degree, start_ts):
        """[(tf, from_ns, to_ns)] — त्या wave साठी प्रत्येक confirmation TF चा सक्रिय काळ (from < bar_end ≤ to). Wave start वरूनच."""
        s = self.s
        mode = s["break_confirm_tf"]
        inf = np.datetime64("2262-01-01", "ns")
        start = self._ns(start_ts)
        if mode != "level_tf":
            return [(mode, start, inf)]
        if s["trigger_tf_mode"] == "fixed":
            return [(s["trigger_tf_fixed"], start, inf)]
        if s["degree_tf_mode"] == "fixed":
            return [(s["degree_tf"][degree], start, inf)]
        key = start
        if key not in self._spans:
            cand = set()                                                 # TF निवड फक्त count thresholds ओलांडताना बदलू शकते
            for tf in s["auto_tfs"]:
                e = self._end[tf]
                a = int(np.searchsorted(e, start, "right"))
                for k in (a + s["tf_bars_min"] - 1, a + s["tf_bars_max"]):
                    if 0 <= k < len(e):
                        cand.add(e[k])
            out, cur_tf, cur_from = [], self._auto_pick(start, start), start
            for x in sorted(cand):
                tf = self._auto_pick(start, x)
                if tf != cur_tf:
                    out.append((cur_tf, cur_from, x - np.timedelta64(1, "ns")))
                    cur_tf, cur_from = tf, x - np.timedelta64(1, "ns")
            out.append((cur_tf, cur_from, inf))
            self._spans[key] = out
        return self._spans[key]

    def tf_for(self, degree, start_ts, t):
        tn = self._ns(t)
        for tf, a, b in self.spans(degree, start_ts):
            if tn <= b:
                return tf
        return self.spans(degree, start_ts)[-1][0]

    def confirm(self, degree, start_ts, level, side, t, tf=None, since=None):
        """start_ts (pivot / wave start) नंतरच्या bars मध्ये `level` चा खरा break t पर्यंत confirm ⇒ (tf, confirm bar_end); नाहीतर None.
        प्रत्येक TF फक्त त्याच्या सक्रिय काळात; सर्वात आधीचा confirm. `tf` दिला ⇒ फक्त तो TF (पूर्ण काळ). `since` ⇒ त्या क्षणापासून
        सुरू होणारे bars च (progressive inv — TF निवड मात्र मूळ wave start वरूनच)."""
        tn, start = self._ns(t), self._ns(start_ts)
        spans = [(tf, start, np.datetime64("2262-01-01", "ns"))] if tf else self.spans(degree, start_ts)
        for k, a_ns, b_ns in spans:
            if a_ns > tn:
                break
            ts, end = self._ts[k], self._end[k]
            a0 = int(np.searchsorted(ts, start, "right"))                # wave start चा bar वगळून
            a = max(a0, int(np.searchsorted(end, a_ns, "right")))        # या TF चा सक्रिय काळ सुरू झाल्यानंतर बंद होणारे bars
            if since is not None:
                a = max(a, int(np.searchsorted(ts, self._ns(since), "left")))
            j = int(np.searchsorted(end, min(tn, b_ns), "right")) - 1
            if j < a:
                continue
            c = self.cache(k).confirm_index(a, level, side, j)
            if c is not None:
                return k, pd.Timestamp(end[c])
        return None

    def broken(self, degree, start_ts, level, side, t, tf=None, since=None):
        return self.confirm(degree, start_ts, level, side, t, tf, since) is not None
