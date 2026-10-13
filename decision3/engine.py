"""decision3/engine.py — थर v2.2 "method-first" (docs/prompts_v2/08_थर_v22_METHOD_FIRST.md). Gates = Abhi च्या 6 पायऱ्या; दुसरं gate नाही.

पायरी B: ① Daily trend (Dow) + ② 1H levels (जीवनक्रम). पायरी C: ③ K, ④ power shift, ⑥ commitment, ⑦ risk (R:R ≥ 3), §5–§7 पुरावे ⇒
conviction (A ✅ / B 🟡 / weak ⇒ वाट / against ⇒ नाही). Abhi 13 Oct: ⑦ (SL / target / R:R) engine मधून काढला — default
`rr_step` = False ⇒ checklist मध्ये ⑦ नाही, risk नाही; setup निर्णय ⑥ (commitment + c1) वर संपतो (SL / target dashboard चे, R:R Abhi चा
approval वेळचा निर्णय). rr_step = True = जुना ⑦ फक्त जुने reports / golden tests reproduce. कठोर नियम फक्त H1 (①), H2 (②③, breakout नाही), H3 (⑦); ⑥ = entry trigger;
§5.3 range अवस्था = gate. ⑤ K ची आतली रेघ close ने तुटली = पुरावा (grade +), gate नाही (`trendline.py`).
जुना decision2 (v2.1) तसाच — `engine_version` setting ने shadow तुलना. हा module order / broker call करत नाही; AI order देत नाही.
Known_at: प्रत्येक bar चा निर्णय फक्त त्या bar च्या close पर्यंतच्या माहितीवर (Daily state known_at ≤ bar_end; levels त्यांच्या जन्म-bar पासून).
"""
import numpy as np
import pandas as pd

from . import daily as DD
from . import flip as FL
from . import levels as LV
from . import liquidity as LQ
from . import method as M
from . import settings as S3
from . import trendline as TL

SETUP, WAIT, NO_TRADE = "setup", "wait", "no_trade"
M_SETUP, M_WAIT, M_NO = "s", "w", "n"


STEPS = ("③", "④", "⑤", "⑥", "⑦")


def level_eval_brief(dd, part, extra, lvl):
    """अहवालासाठी: एका active level चा निकाल (decide फक्त सर्वोत्तम level दाखवतो — R:R ने अडलेले levels इथे दिसतात)."""
    gates = ("③", "⑥", "⑦")
    reached = [k for k in gates if (part.get(k) or [None])[0]]
    rk = extra.get("risk")
    out = {"id": lvl["id"], "role": lvl["role"], "lo": lvl["lo"], "hi": lvl["hi"],
           "decision": {M_SETUP: SETUP, M_WAIT: WAIT, M_NO: NO_TRADE}[dd], "reached": reached[-1] if reached else "②",
           "n_ok": sum(1 for k in STEPS if (part.get(k) or [None])[0]),
           "checklist": {k: [v[0], str(v[1])[:90]] for k, v in part.items()}, "conviction": extra.get("conviction"),
           "form": (extra.get("commit") or {}).get("form")}
    if rk:                                                                 # legacy rr_step = True फक्त (default: engine R:R / SL / target नाही)
        out.update(rr=rk.get("rr"), entry=rk.get("entry"), sl=rk.get("sl"), target=rk.get("target"))
    out["why"] = (extra.get("why") or "")[:120]
    return out


def mature_intact(st):
    """Abhi (12 Oct, owner rule): maturity = पुरावा फक्त. Trend रचना अखंड ⇔ protected close ने तुटलेला नाही (phase ≠ origin_broken) आणि
    उलट same-degree impulse / correction नक्की नाही (counter ≠ correction). अखंड ⇒ mature फक्त grade एक पायरी खाली; नाहीतर जुना cap (weak)."""
    return st.phase in ("impulse", "correction") and st.counter != "correction"


def fut_children(fut_ts):
    """FUT bars ⇒ (children per 15M bin, children a complete bin needs, FUT bar step). Bins are the same 09:15-anchored 15M bins as
    legs2.volume.to_15m (OPEN / BAR — the volume join itself); the step is the FUT data's own bar size (median spacing inside a session),
    never the LTF minutes. A complete bin needs BAR ÷ step distinct FUT bars."""
    from legs2 import volume as LVOL
    ft = pd.to_datetime(pd.Series(fut_ts)).sort_values().reset_index(drop=True)
    day = ft.dt.normalize()
    d = ft.diff()[(day == day.shift()) & (ft.diff() > pd.Timedelta(0))]
    step = d.median() if len(d) else LVOL.BAR
    step = step if pd.notna(step) and step > pd.Timedelta(0) else LVOL.BAR
    b0 = day + LVOL.OPEN + ((ft - day - LVOL.OPEN) // LVOL.BAR) * LVOL.BAR
    return ft.groupby(b0).nunique(), max(1, int(LVOL.BAR // step)), step


class V22:
    def __init__(self, m15, df1m=None, daily_df=None, s=None, res=None, sealed=None, ltf=None, futures=None):
        self.s = S3.load(s)
        self.sealed = sealed                                              # Q33: sealed (NIFTY holdout) तारखा output मध्ये नाहीत
        self.df1m = df1m                                                  # फक्त advisory (elliott count) साठी
        if res is None:
            from swings2 import engine as SE
            res = SE.build(m15, df1m)
        self.res = res
        self.m15 = res["m15"]
        if daily_df is None:
            from pivots import charts as PC
            daily_df = PC.daily_from_15m(self.m15, pd.to_datetime(self.m15["bar_end"]).max())
        self.daily_df = daily_df.reset_index(drop=True)
        self.daily = DD.fold(self.daily_df, self.s)
        self.weekly_df = DD.weekly_from_daily(self.daily_df)
        self.weekly = DD.fold(self.weekly_df, {**self.s, "daily_min_sessions": int(self.s["weekly_min_bars"])})   # Q15 (4) पालक
        self.levels = LV.Levels(res, self.daily, self.daily_df, self.s, weekly_states=self.weekly, weekly_df=self.weekly_df)
        self.bar_end = pd.to_datetime(self.m15["bar_end"]).reset_index(drop=True)
        self._ts = pd.to_datetime(self.m15["timestamp"]).to_numpy()
        self.pb = M.Pullbacks(self)
        self._confirm_inputs(ltf, futures)

    @property
    def rr_step(self):
        """legacy ⑦ (SL / target / R:R ≥ min_rr gate) — default False (Abhi 13 Oct: R:R engine मधून काढला)."""
        return bool(self.s.get("rr_step", False))

    def _confirm_inputs(self, ltf, futures):
        """⑥ c1 / c0 inputs (Abhi, LEVEL_BOTS_CONFIRMATION): LTF = दिलेले bars, नाहीतर त्याच 1m data चे 5M (market_state.core.frame —
        15M ची तीच व्याख्या); दोन्ही नाहीत ⇒ None ⇒ ⑥ "LTF data missing" (fail-closed). Volume = futures (legs2.volume.bar_volume —
        near-month join) किंवा m15 चा स्वतःचा volume column; नाहीतर NA (spot volume 0 ⇒ NA, grade कमाल B)."""
        lm = M.LTF_OF.get(15, 5)
        if ltf is None and self.df1m is not None and len(self.df1m):
            import market_state.core as MC
            ltf = MC.frame(self.df1m, f"{lm}m", pd.to_datetime(self.df1m["timestamp"]).max() + pd.Timedelta(minutes=1))
        self.ltf = M.ltf_frame(ltf, lm, f"{lm}M")
        if self.ltf is None and bool(self.s.get("ltf_choch", True)):
            M.warn_ltf_missing("decision3 V22")                            # fail-closed (⑥ "LTF data missing"), पण शांतपणे नाही
        # Abhi (Z-1 volume): every in-zone comparison (a2, c0, in-zone facts, G4 context) uses the per-bar FUT volume ÷ the median of the
        # same 15M slot over the previous `vol_slot_sessions` sessions (method.slot_rel_volume); averages per bar, never sums. Raw kept.
        raw, self.vol_src, roll = None, None, None
        self.vol_reason = {}                                               # bar ⇒ why its FUT volume is NA (incomplete / missing)
        if futures is not None:
            from legs2 import settings2 as LS2
            from legs2 import volume as LVOL
            raw, self.vol_src = LVOL.bar_volume(self.m15, futures), "near-month FUT 5M ⇒ 15M (legs2.volume.bar_volume)"
            nm = LVOL.near_month(futures)
            st = pd.to_datetime(self.m15["timestamp"]).reset_index(drop=True)
            if len(nm):                                                    # 15M bar with < 3 of 3 FUT 5M children ⇒ NA (never under-counted)
                kids, need, step = fut_children(nm["timestamp"])
                for i, x in enumerate(st):
                    got = int(kids.get(x, 0))
                    if 0 < got < need:
                        raw[i] = np.nan
                        self.vol_reason[i] = f"incomplete 15M FUT bar ({got} of {need} {int(step / pd.Timedelta(minutes=1))}M bars)"
                    elif got == 0:
                        self.vol_reason[i] = "no FUT bar"
                sessions = sorted(st.dt.normalize().unique())
                roll = LVOL.rollover_days(nm["expiry"].unique(), sessions, int(LS2.DEFAULTS["roll_sessions_before"]))
        elif "volume" in self.m15.columns:
            raw = pd.to_numeric(self.m15["volume"], errors="coerce").to_numpy(float)
            raw, self.vol_src = (raw, "m15 volume column (caller-joined)") if M._vol({"volume": raw}) is not None else (None, None)
        self.vol_roll = set(roll or ())
        self.vol_hist = None
        if raw is not None:
            rel, self.vol_hist = M.slot_rel_volume(self.m15["timestamp"], raw, int(self.s["vol_slot_sessions"]),
                                                   int(self.s["vol_slot_min_sessions"]), exclude_days=roll)   # rollover days out
            self.levels.A["volume"] = rel
            self.levels.A["volume_raw"] = np.asarray(raw, float)

    def vol_na_reason(self, t, Av=None):
        """Why the volume used at bar t is NA (None ⇒ it is available). Av = the window's volume view (raw fallback ⇒ only missing FUT)."""
        A = self.levels.A
        if Av is not None and Av is not A and A.get("volume_raw") is not None and np.isfinite(A["volume_raw"][t]) and A["volume_raw"][t] > 0:
            return None
        if A.get("volume_raw") is None:
            return "FUT volume missing (no FUT bars given)"
        if not (np.isfinite(A["volume_raw"][t]) and A["volume_raw"][t] > 0):
            return "FUT volume missing on this bar" + (f" ({self.vol_reason[t]})" if getattr(self, "vol_reason", {}).get(t) else "")
        if np.isfinite(A["volume"][t]):
            return None
        return (f"FUT volume slot baseline NA: {int(self.vol_hist[t])} earlier sessions in this time slot "
                f"(< vol_slot_min_sessions {int(self.s['vol_slot_min_sessions'])})")

    INSUFFICIENT = "volume normalisation: insufficient history — raw per-bar average"

    def vol_view(self, arm, t):
        """Abhi Z-1h: the volume the in-zone comparisons use for the window arm … t. Slot-normalised (20 sessions, min 10) when every bar
        with FUT volume has a baseline; otherwise (fewer than `vol_slot_min_sessions` earlier sessions in a slot) the RAW per-bar FUT
        volume for the whole window (comparisons stay within the same window ⇒ per-bar averages, never sums) — labelled, NOT a data error.
        Returns (A to use, label)."""
        A = self.levels.A
        raw = A.get("volume_raw")
        if raw is None:
            return A, "FUT volume missing"
        w = np.arange(int(arm), int(t) + 1)
        have = np.isfinite(raw[w]) & (raw[w] > 0)
        gaps = [int(i) for i in w[~have]]
        gtxt = ""
        if gaps and have.any():                                            # FUT present but with gaps: count + reason, never silent
            why = sorted({self.vol_reason.get(i, "no FUT volume") for i in gaps})
            gtxt = f" · FUT volume gaps: {len(gaps)}/{len(w)} bars ({'; '.join(why)}) — averages over the bars with volume"
        if self.levels.ts.iloc[int(t)].normalize() in getattr(self, "vol_roll", set()):
            gtxt += " · FUT rollover day (volume less reliable; never used in a baseline)"
        if have.any() and not np.isfinite(A["volume"][w][have]).all():
            return {**A, "volume": raw, "volume_rel": A["volume"]}, self.INSUFFICIENT + gtxt
        return A, f"slot-normalised (÷ median of the same 15M slot, {int(self.s['vol_slot_sessions'])} sessions, min " \
                  f"{int(self.s['vol_slot_min_sessions'])}, FUT rollover days excluded)" + gtxt

    def _confirm(self, t, d, lvl, k):
        """⑥ = एकच shared confirmation (method.confirm: a2 + c0 + c1). Study window = चालू भेट: K मध्ये level ला स्पर्श करणाऱ्या bars चा
        शेवटचा सलग गट (दोन स्पर्शांत ≤ touch_window_bars — ③ चीच "level मध्ये / लगत" व्याख्या) — त्याचा पहिला स्पर्श (arrival) … t;
        LTF संदर्भ = K च्या impulse टोकापासून (pullback चे swings); LTF bars फक्त setup bar च्या close पर्यंत."""
        A = self.levels.A
        k0 = k.get("k_open_bar") if k.get("k_open_bar") is not None else t
        hits = [i for i in range(int(k0), t + 1) if A["low"][i] <= lvl["hi"] and A["high"][i] >= lvl["lo"]]
        arm = hits[-1] if hits else t
        for i in reversed(hits[:-1]):
            if arm - i > int(self.s["touch_window_bars"]):
                break
            arm = i
        c0 = k.get("i_end_bar") if k.get("i_end_bar") is not None else k0
        times = (pd.Timestamp(self._ts[min(int(c0), arm)]), pd.Timestamp(self._ts[arm]), pd.Timestamp(self.bar_end[t]))
        Av, vlabel = self.vol_view(arm, t)                                  # Abhi Z-1h: normalised, or raw per-bar fallback (labelled)
        cf = M.confirm(Av, arm, t, d, lvl, self.s, self._ts, ltf=self.ltf, ltf_times=times)
        cm = dict(cf["commit"] or {})
        cm.update(study_from=str(pd.Timestamp(self._ts[arm])), confirm_wait=cf["wait"], confirm_lines=cf["lines"],
                  ltf_line=(cf["choch"] or {}).get("line"), handover=(cf["study"] or {}).get("handover"),
                  absorption=cf["absorption"], arm_bar=int(arm), choch=cf["choch"], volume_measure=vlabel, handover_present=cf.get("handover"))
        ok, why = cf["ok"], cf["why"]
        if cf["c0"] and cm.get("vol_na") and bool(self.s.get("c0_volume_required", True)):   # Abhi Z-1c: FUT volume नाही ⇒ data problem
            ok, why = False, "data problem: " + (self.vol_na_reason(t, Av) or "FUT volume missing")
            cm.update(confirm_wait="data_problem", data_problem=why)
        return ok, why, cm

    def step1(self, t):
        """① Q15: Daily impulse-degree Dow + Weekly पालक. रिटर्न (ok, why, st, ctx); ctx = {trend (वापरलेला), resolution, cap, notes,
        weekly}. Weekly विरुद्ध ⇒ कमाल B; Daily वाचता येत नाही (NEUTRAL / UNKNOWN) + Weekly trend ⇒ Weekly fallback, कमाल B;
        impulse mature / origin धोक्यात (B1) ⇒ कमाल weak; trend first: impulse टोकानंतर Daily रचना trend विरुद्ध (`st.rev`) ⇒ trade नाही; origin close ने तुटला, उलट impulse नाही ⇒ कमाल B (Q23); A1: impulse origin
        तुटला पण parent टिकला ⇒ same-degree correction (protected = parent; कमाल B — आधीच्या origin_broken सारखाच, loosen नाही).
        RANGE (Q27: origin तुटल्यानंतर दोन समान H / L सुद्धा) ⇒ पट्टा ctx["band"] — ② कडांजवळची levels."""
        st = DD.state_at(self.daily, self.bar_end[t])
        wk = DD.state_at(self.weekly, self.bar_end[t])
        ctx = {"trend": st.trend, "resolution": "daily impulse" if st.trend in ("UP", "DOWN") else ("daily range" if st.trend == "RANGE"
               else None), "cap": None, "notes": [], "weekly": wk.trend, "band": st.band if st.trend == "RANGE" else None}
        why = {"UP": "Daily UP", "DOWN": "Daily DOWN", "RANGE": "Daily RANGE ⇒ कडेनुसार", "NEUTRAL": "Daily NEUTRAL",
               "UNKNOWN": "Daily data अपुरा"}[st.trend]
        if st.trend in ("UP", "DOWN") and st.phase and getattr(st, "rev", None) is not None:
            # Trend first (Abhi, setups audit — docs/reports/setups_prA_v1_audit.md): impulse टोकानंतर Daily रचना trend विरुद्ध पूर्ण (flip चा (अ) नियम —
            # उलट HL / LH + मधल्या swing पलीकडे close + impulse-स्वभावाचा पाय, Q29 / Q36), फक्त origin पलीकडचा close बाकी ⇒ trend-बाजूचा
            # trade नाही (उलट बाजू पण नाही — trend अजून flip झाला नाही, Q15). Cap नाही, gate (H1).
            opp = "UP" if st.trend == "DOWN" else "DOWN"
            why += f" · {DD.describe(st)} ⇒ trade नाही (trend first: Daily रचना {opp}; flip ला origin पलीकडे close हवा)"
            ctx.update(trend="NEUTRAL", resolution="structure against trend", band=None)
            ctx["notes"].append(f"Daily {st.trend} पण impulse टोकानंतरची रचना {opp} ⇒ {'bear call' if st.trend == 'DOWN' else 'bull put'} नाही "
                                f"(trend first)")
            return False, why, st, ctx
        if st.trend in ("UP", "DOWN") and st.phase:
            why += f" · {DD.describe(st)}"
            if wk.trend in ("UP", "DOWN") and wk.trend != st.trend:
                ctx["cap"] = M.cap_min(ctx["cap"], "B")
                ctx["notes"].append(f"Daily {st.trend} = Weekly {wk.trend} विरुद्ध correction ⇒ कमाल B")
            if st.phase == "origin_broken":                                 # Q23 (Abhi): रचना खराब, अजून उलटली नाही ⇒ कमाल B (नोंद तशीच)
                ctx["cap"] = M.cap_min(ctx["cap"], "B")
                ctx["notes"].append("protected origin close ने तुटला — correction चालू, उलट impulse अजून नाही ⇒ कमाल B")
            if st.counter == "correction":                                  # A1: impulse origin तुटला (parent टिकला) ⇒ आधीसारखाच कमाल B (Q23)
                ctx["cap"] = M.cap_min(ctx["cap"], "B")
                ctx["notes"].append("impulse origin close ने तुटला, parent टिकला — same-degree correction चालू ⇒ कमाल B")
            gates = bool(self.s.get("wave_gates", False))                   # Abhi B1 (patience): wave / maturity फक्त context
            ctx["wave_context"] = {"mature": bool(st.mature), "maturity_targets": list(st.targets), "origin_risk": bool(st.origin_risk),
                                   "wave": st.wave, "corr_label": st.corr_label}
            if st.origin_risk and gates:                                    # legacy (wave_gates): correction origin जवळ ⇒ conviction weak
                ctx["cap"] = M.cap_min(ctx["cap"], "weak")
                ctx["notes"].append("correction protected origin जवळ (origin धोक्यात) ⇒ नवे entries weak")
            elif st.origin_risk:
                ctx["notes"].append("context: correction protected origin जवळ (gate नाही — Abhi B1)")
            if getattr(st, "corr_zone", None) is not None and st.phase == "impulse" and st.counter in (None, "pullback"):                  # ABC_FIX rule 3: correction sharp zone मध्ये संपली + trend
                ctx["evidence"] = list(st.evidence)                         # दिशेने close ⇒ continuation पुरावा (cap नाही; नोंद — Q51)
                ctx["notes"].append("continuation evidence: " + st.evidence[-1] if st.evidence else "continuation evidence")
            if st.mature and not gates:                                     # Abhi B1: maturity / projections = context only — no cap, no step-down
                ctx["notes"].append("context: impulse mature — target जवळ (Q44) (gate / downgrade नाही — Abhi B1)")
            elif st.mature and mature_intact(st):                           # legacy (wave_gates): maturity — रचना अखंड ⇒ gate नाही,
                ctx["step_down"] = True                                     # grade फक्त एक पायरी खाली (A ⇒ B; B तसाच) — `step_down_conv`
                ctx["notes"].append("impulse mature — target जवळ (Q44) · पुरावा फक्त: protected अखंड, उलट impulse नाही ⇒ grade एक पायरी खाली")
            elif st.mature:
                ctx["cap"] = M.cap_min(ctx["cap"], "weak")
                ctx["notes"].append("impulse mature — target जवळ (Q44: parent नंतरच्या पहिल्या impulse leg चं टोक); मोठा reversal शक्य ⇒ नवे entries weak")
        elif st.trend in ("NEUTRAL", "UNKNOWN") and wk.trend in ("UP", "DOWN"):
            ctx.update(trend=wk.trend, resolution="weekly fallback", cap=M.cap_min(ctx["cap"], "B"))
            ctx["notes"].append(f"Daily वाचता येत नाही ⇒ Weekly {wk.trend} (कमाल B)")
            why += f" ⇒ Weekly {wk.trend} fallback"
        elif st.why:
            why += f" · {st.why}"
        ok = ctx["trend"] in ("UP", "DOWN", "RANGE")
        why += {"UP": " ⇒ bull put", "DOWN": " ⇒ bear call"}.get(ctx["trend"], "" if ok else " ⇒ trade नाही")
        return ok, why, st, ctx

    def step2(self, t, trend, band=None):
        act = self.levels.active(t, trend, band)
        act = act + self.tl_areas(t, trend, act)
        if not act:
            return False, "trade-बाजूचा जिवंत 1H level नाही", act
        a = act[0]
        star = "★" * a["sweeps"]
        return True, f"{a['role']} {a['lo']:,.0f}–{a['hi']:,.0f} ({'+'.join(a['births'])}){star} · अंतर {a['dist']:,.0f}", act

    def tl_areas(self, t, trend, act=None):
        """② Abhi (12 Oct): तिरकी trendline (trend-degree swings, t ला माहीत) + ② चेच active horizontal levels (जवळचे `active_levels_max`)
        ⇒ confluence area (`trendline.confluence_areas`). DOWN ⇒ उतरती रेघ + resistance; UP ⇒ चढती + support; RANGE / बाकी ⇒ नाही."""
        if trend not in ("UP", "DOWN"):
            return []
        if act is None:
            act = self.levels.active(t, trend)
        return TL.confluence_areas(self, t, M._dir(trend), act)

    def flip_context(self, t, lvl):
        """KB G4 (Abhi Z-1d): how price came back into a FLIPPED area — (a) approach shape, (b) approach volume vs the flip impulse
        (normalised per bar). CONTEXT ONLY: reported in the checklist / payload, never a no_trade or a wait."""
        return FL.approach_context(self.levels.A, self.levels.ts.to_numpy(), t, lvl, self.res["pivots"], self.s, legs_A=self._legs_A())

    def rsi_divergence(self, t, d, arm):
        """RSI divergence (rsi2.engine.Divergence, 15M, `div_bars` minimum 3 — Abhi RSI-2) as ZONE EVIDENCE: a regular divergence on the
        trade side (bear for a bear call) whose second pivot / running extreme is inside the zone visit (bar ≥ arm), known by bar t.
        Never a gate. Returns {found, divergences, statement} or NA with the reason."""
        if getattr(self, "_rsi", None) is None:
            try:
                from rsi2 import engine as RE
                self._rsi = RE.Divergence(self.m15[["timestamp", "open", "high", "low", "close"]], "15M", res=self.res, areas=False)
            except Exception as exc:                                       # noqa: BLE001 — evidence only ⇒ NA with the reason
                self._rsi = f"{type(exc).__name__}: {exc}"
        if isinstance(self._rsi, str):
            return {"found": None, "na": "rsi2 Divergence failed — " + self._rsi}
        side = "bear" if d < 0 else "bull"
        r = self._rsi.read(t)
        divs = [x for x in r["divergences"] if x["side"] == side and x["type"] == "regular" and x["L2"]["bar"] >= int(arm)]
        keep = ("degree", "status", "bars", "price_rel", "count")
        out = [{**{k: x.get(k) for k in keep}, "L1": {k: x["L1"][k] for k in ("time", "price", "rsi")},
                "L2": {k: x["L2"][k] for k in ("time", "price", "rsi")}} for x in divs]
        st = [y["statement"] for y in r["latest"] if y["side"] == side]
        return {"found": bool(out), "divergences": out, "bar_window": r["bar_window"], "statements": st}

    def _legs_A(self):
        if getattr(self, "_legs_arr", None) is None:
            self._legs_arr = FL.legs_arrays(self.levels.A, self.levels.ts.to_numpy())
        return self._legs_arr

    def _level_eval(self, t, trend, lvl, cap=None, notes=None, *, step_down=False):
        """एका active level साठी ③–⑦ + पुरावे ⇒ (decision, checklist part, extra)."""
        A = self.levels.A
        d = M._dir(trend, lvl["role"])
        k = self.pb.at(t, d)
        chk = {}
        if k is None or not k.get("open"):
            chk["③"] = [False, "K (pullback) उघडी नाही" if k is not None else "trend-दिशेचा impulse (BOS) नाही / origin तुटला"]
            return M_WAIT, chk, {"K": k}
        ok3, why3 = M.at_level_or_confirm(A, t, d, lvl, self.s, self._ts)
        chk["③"] = [ok3, f"{why3} · K {k['why_open']}, पाय {k['legs']}"]
        if not ok3:
            return M_WAIT, chk, {"K": k}
        g4 = None
        if lvl.get("state") == FL.FLIPPED and self.s.get("level_flip_rule", "far_swing") == "far_swing":
            g4 = self.flip_context(t, lvl)                                # Abhi Z-1d: context only — never a gate
            chk["G4"] = [None, g4["why"]]
        tl = TL.k_line(self, t, d, k)
        chk["⑤"] = [None, "K ची आतली रेघ नाही (< 2 स्पर्श)"] if tl is None else \
            [tl["broken"], f"K रेघ ({tl['touches']} स्पर्श) {'close ने तुटली ⇒ grade +' if tl['broken'] else 'अजून अखंड'}"]
        ok4, n4, items = M.power_shift(A, t, d, k, self.s)
        chk["④"] = [ok4, f"power shift {n4}/4 ({', '.join(x for x in ('a_shrinking', 'b_overlap', 'c_no_new_extreme_or_sweep', 'd_rejection_wick') if items[x]) or '—'})"]
        rng = M.range_state(A, t, self.s) and not M.range_broken_by(A, t, d, self.s)   # Q24: पट्ट्याबाहेर close ⇒ range संपली
        ok6, why6, cm = self._confirm(t, d, lvl, k)                         # ⑥ a2 + c0 + c1 (shared, method.confirm)
        chk["⑥"] = [ok6, why6]
        arm = int(cm.get("arm_bar", t))
        rsi = self.rsi_divergence(t, d, arm)                               # zone evidence (Abhi): never a gate
        Av, vlabel = self.vol_view(arm, t)
        zr = FL.zone_read(Av, self.levels.ts.to_numpy(), arm, t, d, lvl, self.s, rsi=rsi)  # in-zone study facts (bars arm … t)
        zr["volume_measure"] = vlabel
        last3 = range(max(0, t - 2), t + 1)
        ev = {"level_star": lvl["sweeps"] >= 1 or any(b in lvl["births"] for b in ("b", "c", "d", "a:D")), "fresh": lvl["fresh"],
              "power_shift": ok4, "trap_sweep": bool(items.get("sweep")) or lvl["sweeps"] >= 1,
              "second_attempt": (k["legs"] >= 2) if self.s.get("wave_gates", False) else None,   # Abhi B1: leg count = context (NA)
              "commit_strong": bool(cm.get("big_body") and cm.get("big_range")) if cm else False,   # signal-bar ताकद (आकार); grade वेगळी
              "engulf": bool(cm.get("engulf")) if cm else False,
              "rsi_div": True if rsi.get("found") else None, "volume_low": None, "pattern": None,   # RSI: evidence + only
              "against_bodies": any((A["close"][i] - A["open"][i]) * d < 0 and M.candle_read(A, i, self.s)["big_body"] for i in last3),
              "fourth_attempt": (k["legs"] > int(self.s["max_attempts"])) if self.s.get("wave_gates", False) else None,
              "tl_break": True if (tl and tl["broken"]) else None,           # ⑤ "(असल्यास) तुटली ⇒ grade +": अखंड / नाही ⇒ NA (वजा नाही)
              "tl_confluence": True if "tl" in lvl["births"] else None}      # फक्त नोंद (वजन नाही ⇒ grade वाढत नाही; D12-6)
        sw, tr = LQ.sweeps_and_traps(self, t, int(self.s["liquidity_lookback"]))                           # §7: pullback ने pool (bear call ⇒ buy-side वर, bull put ⇒ खाली) sweep?
        side = "buy" if d == M.DOWN else "sell"
        mine = [x for x in sw if x["side"] == side]
        ev["trap_sweep"] = bool(ev["trap_sweep"] or mine or [x for x in tr if x["side"] == side])
        conv, score, missing = M.conviction(ev, self.s)
        extra = {"K": k, "evidence": ev, "trendline": tl, "conviction": conv, "conv_score": score, "missing": missing, "commit": cm,
                 "liquidity": {"sweeps": mine[:3], "trapped": [x for x in tr if x["side"] == side][:2]}, "flip_retest": g4,
                 "zone_read": zr}
        extra["range_state"] = bool(rng)                                  # Abhi Z-1j: context fact (sideways = the handover study)
        if rng and bool(self.s.get("range_state_gate", False)):            # legacy only
            chk["⑥"] = [False, "§5.3 range अवस्था (overlap + doji) ⇒ entry नाही"]
            return M_WAIT, chk, extra
        gates = bool(self.s.get("wave_gates", False))
        extra["wave_context"] = {"legs": k["legs"], "second_attempt": k["legs"] >= 2, "fourth_attempt": k["legs"] > int(self.s["max_attempts"]),
                                 "note": "context only (Abhi B1)" if not gates else "legacy wave gates on"}
        if k["legs"] > int(self.s["max_attempts"]) and gates:          # legacy only: Abhi B1 — leg / wave count never blocks
            return M_NO, chk, {**extra, "why": "चौथा+ प्रयत्न ⇒ reversal शक्यता (§5.1)"}
        if not ok6:
            return M_WAIT, chk, {**extra, "why": f"commitment ची वाट ({why6})"}
        if self.rr_step:                                                 # legacy फक्त (Abhi 13 Oct: R:R engine मधून काढला; SL / target dashboard चे)
            ok7, rk = M.risk(self, t, d, lvl, k, self.s)
            chk["⑦"] = [ok7, f"R:R {rk['rr']}" if rk["rr"] is not None else "target नाही"]
            extra["risk"] = rk
            if not ok7:
                return M_NO, chk, {**extra, "why": "R:R < 3 ⇒ trade नाही"}
        conv1 = M.first_leg_cap(conv, k["legs"], lvl["sweeps"], ev["commit_strong"]) if gates else conv   # Abhi B1: legacy only
        if conv1 != conv:
            conv = extra["conviction"] = conv1
            if conv == "weak":
                missing.append("§5.1 पहिला पाय: ★ ≥ 2 + मजबूत signal-bar नाही ⇒ दुसऱ्या पायाची वाट")
        if cm and cm.get("grade") == "B" and M.cap_conv(conv, "B") != conv:
            conv = extra["conviction"] = "B"                            # Q16: wick-only नकार (grade B) ⇒ कमाल B
        conv2 = M.cap_conv(conv, cap)                                    # Q15: weekly विरुद्ध / origin तुटला / mature
        if conv2 != conv:
            conv = extra["conviction"] = conv2
            missing.extend(x for x in (notes or []) if "कमाल" in x or "weak" in x)   # फक्त cap लावणाऱ्या नोंदी
        if step_down:                                                    # mature + रचना अखंड ⇒ एक पायरी खाली (A ⇒ B), entry अडवत नाही
            conv3 = M.step_down_conv(conv)
            if conv3 != conv:
                conv = extra["conviction"] = conv3
                missing.append("impulse mature (पुरावा) ⇒ grade एक पायरी खाली")
        if conv in ("A", "B"):
            return M_SETUP, chk, extra
        if conv == "weak":
            return M_WAIT, chk, {**extra, "why": "conviction कमी — गहाळ: " + ", ".join(missing)}
        return M_NO, chk, {**extra, "why": "विरुद्ध पुरावे जास्त"}

    def decide(self, t):
        ok1, why1, st, ctx = self.step1(t)
        trend = ctx["trend"]
        ok2, why2, act = self.step2(t, trend, ctx.get("band")) if ok1 else (False, "① ✘", [])
        chk = {"①": [ok1, why1], "②": [ok2, why2]}
        for k in STEPS if self.rr_step else STEPS[:-1]:                  # default: ⑦ नाही (Abhi 13 Oct)
            chk[k] = [None, "—"]
        dec, best, evals = (NO_TRADE if not ok1 else WAIT), {}, []
        if ok1 and ok2:
            rank = {M_SETUP: 0, M_WAIT: 1, M_NO: 2}
            res = []
            for lvl in act:
                dd, part, extra = self._level_eval(t, trend, lvl, ctx["cap"], ctx["notes"], step_down=bool(ctx.get("step_down")))
                res.append((rank[dd], dd, part, extra, lvl))
            evals = [level_eval_brief(dd_, part_, extra_, lvl_) for _, dd_, part_, extra_, lvl_ in res]
            # bar चा निकाल = किंमत ज्या level वर आहे (③ ✔) त्याचा; स्पर्श नसलेल्या दूरच्या level चा "wait" (③ ✘) पोहोचलेल्या level चा
            # निकाल (उदा. ⑦ R:R ⇒ no_trade) झाकत नाही. ③ ✔ नसेल ⇒ आधीसारखा क्रम (setup < wait < no_trade).
            res.sort(key=lambda x: (0 if (x[2].get("③") or [None])[0] else 1, x[0]))
            _, dd, part, extra, lvl = res[0]
            chk.update(part)
            dec = {M_SETUP: SETUP, M_WAIT: WAIT, M_NO: NO_TRADE}[dd]
            best = {**extra, "level": lvl}
        mark = None
        if dec == SETUP:
            mark = "✅" if best.get("conviction") == "A" else "🟡"
        return {"bar": int(t), "ts": str(pd.Timestamp(self.m15["timestamp"].iloc[t])), "bar_end": str(self.bar_end[t]),
                "engine_version": "v22", "daily_trend": st.trend, "trend_used": trend, "trend_resolution": ctx["resolution"],
                "weekly_trend": ctx["weekly"], "daily_phase": st.phase, "daily_leg": st.wave, "corr_label": st.corr_label,
                "mature": st.mature, "maturity_targets": list(st.targets), "trend_notes": ctx["notes"], "trend_cap": ctx["cap"],
                "mature_step_down": bool(ctx.get("step_down")), "wave_context": {**(ctx.get("wave_context") or {}),
                                                                                 **(best.get("wave_context") or {})},
                "watch_list": [{k: a.get(k) for k in ("id", "role", "lo", "hi", "state", "dist", "births")} for a in act],
                "trade_side": list(DD.trade_side(trend)),
                "protected": None if st.protected is None else {"kind": st.protected.kind, "price": st.protected.price,
                                                                  "day": ("before window" if self.sealed and self.sealed(st.protected.day)
                                                                          else str(st.protected.day.date()))},
                "range_band": st.band, "active_levels": act, "checklist": chk, "decision": dec, "mark": mark,
                "K": best.get("K"), "risk": best.get("risk"), "conviction": best.get("conviction"), "conv_score": best.get("conv_score"),
                "missing": best.get("missing"), "evidence": best.get("evidence"), "why": best.get("why"),
                "level": best.get("level"), "liquidity": best.get("liquidity"), "trendline": best.get("trendline"),
                "commit": best.get("commit"), "commitment_form": (best.get("commit") or {}).get("form"),
                "flip_retest": best.get("flip_retest"), "zone_read": best.get("zone_read"), "range_state": best.get("range_state"),
                "volume_measure": (best.get("commit") or {}).get("volume_measure") or (best.get("zone_read") or {}).get("volume_measure"),
                "flip": None if not best.get("level") else {k: best["level"].get(k) for k in ("state", "broken_ts", "far_swing",
                                                                                              "flipped_ts", "break_dir")},
                "level_evals": evals}

    def run(self, bars=None):
        bars = range(len(self.m15)) if bars is None else bars
        return [self.decide(t) for t in bars]
