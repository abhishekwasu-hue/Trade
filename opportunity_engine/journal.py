"""opportunity_engine/journal.py — in-memory Structure Journal (PR-1a). Live आणि backtest साठी एकच code path: `on_bar_close(tf, bar)`.

🎓 Journal bar फक्त `bar_end ≤ t` झाल्यावर (closed) घेतो — कॉलर ही अट पाळतो (`run()` सर्व bars आधीच बंद असलेल्या frames वर चालवतो).
Supabase लिहिणं PR-1b मध्ये; इथे फक्त मेमरीत states, events आणि state-बदलांचा इतिहास.
"""
import bisect

import numpy as np
import pandas as pd

from .config import EngineConfig, TF_ORDER
from .structure import StructureTracker

REPORT_EVENTS = ("INIT_TREND", "INIT_RANGE", "CHOCH", "BOS", "SWEEP", "RECOVERY", "REVERSAL_CONFIRMED", "RANGE_START", "RANGE_EXIT_UP",
                 "RANGE_EXIT_DOWN", "PULLBACK_START", "PULLBACK_END")


class Journal:
    def __init__(self, cfg=None, tfs=TF_ORDER):
        self.cfg = cfg or EngineConfig()
        self.trackers = {tf: StructureTracker(tf, self.cfg) for tf in tfs}
        self._times = {tf: [] for tf in tfs}

    # ---- incremental (live) ----
    def on_bar_close(self, tf, bar_end, o, h, l, c, full=True):
        events = self.trackers[tf].on_bar(bar_end, o, h, l, c, full)
        return events

    # ---- batch (backtest/refresh) ----
    def run(self, frames):
        """frames = {tf: engine frame (bar_end, open, high, low, close, bar_is_full)}. प्रत्येक TF चे bars क्रमाने."""
        for tf, df in frames.items():
            if tf not in self.trackers or df is None or df.empty:
                continue
            tr = self.trackers[tf]
            be = df["bar_end"].tolist()
            ov, hv, lv, cv = (df[x].to_numpy(dtype="float64") for x in ("open", "high", "low", "close"))
            fv = df["bar_is_full"].to_numpy(dtype=bool) if "bar_is_full" in df.columns else np.ones(len(df), dtype=bool)
            for i in range(len(df)):
                tr.on_bar(be[i], ov[i], hv[i], lv[i], cv[i], fv[i])
        return self

    # ---- queries ----
    def state(self, tf):
        return self.trackers[tf].state

    def snapshot(self, tf):
        return self.trackers[tf].snapshot()

    def state_at(self, tf, t):
        """t पर्यंत (bar_end ≤ t) प्रक्रिया झालेल्या bars नंतरचा state (state-बदलांच्या इतिहासावरून). t आधी काहीच बदल नसेल तर 'INIT'."""
        changes = self.trackers[tf].changes
        times = [ch["time"] for ch in changes]
        i = bisect.bisect_right(times, pd.Timestamp(t))
        return changes[i - 1]["state"] if i else "INIT"

    def events(self, tf=None, types=None):
        tfs = [tf] if tf else list(self.trackers)
        out = []
        for name in tfs:
            out += [e for e in self.trackers[name].events if types is None or e["type"] in types]
        return sorted(out, key=lambda e: (e["time"], e["tf"]))

    def structure_table(self, tfs=("1d", "4h", "1h")):
        """Structure accuracy CSV: प्रत्येक state-बदल/event — तारीख(bar_end), tf, event, नवीन state, किंमत, trigger_bar, protected."""
        rows = []
        for tf in tfs:
            tr = self.trackers.get(tf)
            if tr is None:
                continue
            for e in tr.events:
                if e["type"] not in REPORT_EVENTS or e["type"] in ("PULLBACK_START", "PULLBACK_END"):
                    continue
                rows.append({"time": e["time"], "tf": tf, "event": e["type"], "from_state": e.get("from_state"), "state": e.get("to_state", e["state"]),
                             "price": e["price"], "trigger_bar": e.get("trigger_bar", e["time"]),
                             "detail": e.get("side") or (f"LH {e['lh_price']:.2f}" if e.get("lh_price") is not None else "")})
        cols = ["time", "tf", "event", "from_state", "state", "price", "trigger_bar", "detail"]
        if not rows:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame(rows, columns=cols).sort_values(["time", "tf"]).reset_index(drop=True)
