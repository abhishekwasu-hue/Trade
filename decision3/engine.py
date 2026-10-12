"""decision3/engine.py — थर v2.2 "method-first" (docs/prompts_v2/08_थर_v22_METHOD_FIRST.md). Gates = Abhi च्या 6 पायऱ्या; दुसरं gate नाही.

पायरी B: ① Daily trend (Dow) + ② 1H levels (जीवनक्रम). पायरी C: ③ K, ④ power shift, ⑥ commitment, ⑦ risk (R:R ≥ 3), §5–§7 पुरावे ⇒
conviction (A ✅ / B 🟡 / weak ⇒ वाट / against ⇒ नाही). कठोर नियम फक्त H1 (①), H2 (②③, breakout नाही), H3 (⑦); ⑥ = entry trigger;
§5.3 range अवस्था = gate. ⑤ K ची आतली रेघ close ने तुटली = पुरावा (grade +), gate नाही (`trendline.py`).
जुना decision2 (v2.1) तसाच — `engine_version` setting ने shadow तुलना. हा module order / broker call करत नाही; AI order देत नाही.
Known_at: प्रत्येक bar चा निर्णय फक्त त्या bar च्या close पर्यंतच्या माहितीवर (Daily state known_at ≤ bar_end; levels त्यांच्या जन्म-bar पासून).
"""
import pandas as pd

from . import daily as DD
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
    rk = extra.get("risk") or {}
    return {"id": lvl["id"], "role": lvl["role"], "lo": lvl["lo"], "hi": lvl["hi"],
            "decision": {M_SETUP: SETUP, M_WAIT: WAIT, M_NO: NO_TRADE}[dd], "reached": reached[-1] if reached else "②",
            "n_ok": sum(1 for k in STEPS if (part.get(k) or [None])[0]),
            "checklist": {k: [v[0], str(v[1])[:90]] for k, v in part.items()}, "conviction": extra.get("conviction"),
            "form": (extra.get("commit") or {}).get("form"), "rr": rk.get("rr"), "entry": rk.get("entry"), "sl": rk.get("sl"),
            "target": rk.get("target"), "why": (extra.get("why") or "")[:120]}


def mature_intact(st):
    """Abhi (12 Oct, owner rule): maturity = पुरावा फक्त. Trend रचना अखंड ⇔ protected close ने तुटलेला नाही (phase ≠ origin_broken) आणि
    उलट same-degree impulse / correction नक्की नाही (counter ≠ correction). अखंड ⇒ mature फक्त grade एक पायरी खाली; नाहीतर जुना cap (weak)."""
    return st.phase in ("impulse", "correction") and st.counter != "correction"


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
        if futures is not None:
            from legs2 import volume as LVOL
            self.levels.A["volume"] = LVOL.bar_volume(self.m15, futures)
        elif "volume" in self.m15.columns:
            self.levels.A["volume"] = pd.to_numeric(self.m15["volume"], errors="coerce").to_numpy(float)

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
        cf = M.confirm(A, arm, t, d, lvl, self.s, self._ts, ltf=self.ltf, ltf_times=times)
        cm = dict(cf["commit"] or {})
        cm.update(study_from=str(pd.Timestamp(self._ts[arm])), confirm_wait=cf["wait"], confirm_lines=cf["lines"],
                  ltf_line=(cf["choch"] or {}).get("line"), handover=(cf["study"] or {}).get("handover"),
                  absorption=cf["absorption"])
        return cf["ok"], cf["why"], cm

    def step1(self, t):
        """① Q15: Daily impulse-degree Dow + Weekly पालक. रिटर्न (ok, why, st, ctx); ctx = {trend (वापरलेला), resolution, cap, notes,
        weekly}. Weekly विरुद्ध ⇒ कमाल B; Daily वाचता येत नाही (NEUTRAL / UNKNOWN) + Weekly trend ⇒ Weekly fallback, कमाल B;
        impulse mature / origin धोक्यात (B1) ⇒ कमाल weak; origin close ने तुटला, उलट impulse नाही ⇒ कमाल B (Q23); A1: impulse origin
        तुटला पण parent टिकला ⇒ same-degree correction (protected = parent; कमाल B — आधीच्या origin_broken सारखाच, loosen नाही).
        RANGE (Q27: origin तुटल्यानंतर दोन समान H / L सुद्धा) ⇒ पट्टा ctx["band"] — ② कडांजवळची levels."""
        st = DD.state_at(self.daily, self.bar_end[t])
        wk = DD.state_at(self.weekly, self.bar_end[t])
        ctx = {"trend": st.trend, "resolution": "daily impulse" if st.trend in ("UP", "DOWN") else ("daily range" if st.trend == "RANGE"
               else None), "cap": None, "notes": [], "weekly": wk.trend, "band": st.band if st.trend == "RANGE" else None}
        why = {"UP": "Daily UP", "DOWN": "Daily DOWN", "RANGE": "Daily RANGE ⇒ कडेनुसार", "NEUTRAL": "Daily NEUTRAL",
               "UNKNOWN": "Daily data अपुरा"}[st.trend]
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
            if st.origin_risk:                                              # B1 (Abhi): correction origin जवळ ⇒ conviction weak
                ctx["cap"] = M.cap_min(ctx["cap"], "weak")
                ctx["notes"].append("correction protected origin जवळ (origin धोक्यात) ⇒ नवे entries weak")
            if getattr(st, "corr_zone", None) is not None and st.phase == "impulse" and st.counter in (None, "pullback"):                  # ABC_FIX rule 3: correction sharp zone मध्ये संपली + trend
                ctx["evidence"] = list(st.evidence)                         # दिशेने close ⇒ continuation पुरावा (cap नाही; नोंद — Q51)
                ctx["notes"].append("continuation evidence: " + st.evidence[-1] if st.evidence else "continuation evidence")
            if st.mature and mature_intact(st):                             # Abhi (12 Oct): maturity = पुरावा फक्त — रचना अखंड ⇒ gate नाही,
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
        tl = TL.k_line(self, t, d, k)
        chk["⑤"] = [None, "K ची आतली रेघ नाही (< 2 स्पर्श)"] if tl is None else \
            [tl["broken"], f"K रेघ ({tl['touches']} स्पर्श) {'close ने तुटली ⇒ grade +' if tl['broken'] else 'अजून अखंड'}"]
        ok4, n4, items = M.power_shift(A, t, d, k, self.s)
        chk["④"] = [ok4, f"power shift {n4}/4 ({', '.join(x for x in ('a_shrinking', 'b_overlap', 'c_no_new_extreme_or_sweep', 'd_rejection_wick') if items[x]) or '—'})"]
        rng = M.range_state(A, t, self.s) and not M.range_broken_by(A, t, d, self.s)   # Q24: पट्ट्याबाहेर close ⇒ range संपली
        ok6, why6, cm = self._confirm(t, d, lvl, k)                         # ⑥ a2 + c0 + c1 (shared, method.confirm)
        chk["⑥"] = [ok6, why6]
        last3 = range(max(0, t - 2), t + 1)
        ev = {"level_star": lvl["sweeps"] >= 1 or any(b in lvl["births"] for b in ("b", "c", "d", "a:D")), "fresh": lvl["fresh"],
              "power_shift": ok4, "trap_sweep": bool(items.get("sweep")) or lvl["sweeps"] >= 1, "second_attempt": k["legs"] >= 2,
              "commit_strong": bool(cm.get("big_body") and cm.get("big_range")) if cm else False,   # signal-bar ताकद (आकार); grade वेगळी
              "engulf": bool(cm.get("engulf")) if cm else False,
              "rsi_div": None, "volume_low": None, "pattern": None,
              "against_bodies": any((A["close"][i] - A["open"][i]) * d < 0 and M.candle_read(A, i, self.s)["big_body"] for i in last3),
              "fourth_attempt": k["legs"] > int(self.s["max_attempts"]),
              "tl_break": True if (tl and tl["broken"]) else None,           # ⑤ "(असल्यास) तुटली ⇒ grade +": अखंड / नाही ⇒ NA (वजा नाही)
              "tl_confluence": True if "tl" in lvl["births"] else None}      # फक्त नोंद (वजन नाही ⇒ grade वाढत नाही; D12-6)
        sw, tr = LQ.sweeps_and_traps(self, t, int(self.s["liquidity_lookback"]))                           # §7: pullback ने pool (bear call ⇒ buy-side वर, bull put ⇒ खाली) sweep?
        side = "buy" if d == M.DOWN else "sell"
        mine = [x for x in sw if x["side"] == side]
        ev["trap_sweep"] = bool(ev["trap_sweep"] or mine or [x for x in tr if x["side"] == side])
        conv, score, missing = M.conviction(ev, self.s)
        extra = {"K": k, "evidence": ev, "trendline": tl, "conviction": conv, "conv_score": score, "missing": missing, "commit": cm,
                 "liquidity": {"sweeps": mine[:3], "trapped": [x for x in tr if x["side"] == side][:2]}}
        if rng:
            chk["⑥"] = [False, "§5.3 range अवस्था (overlap + doji) ⇒ entry नाही"]
            return M_WAIT, chk, extra
        if k["legs"] > int(self.s["max_attempts"]):
            return M_NO, chk, {**extra, "why": "चौथा+ प्रयत्न ⇒ reversal शक्यता (§5.1)"}
        if not ok6:
            return M_WAIT, chk, {**extra, "why": f"commitment ची वाट ({why6})"}
        ok7, rk = M.risk(self, t, d, lvl, k, self.s)
        chk["⑦"] = [ok7, f"R:R {rk['rr']}" if rk["rr"] is not None else "target नाही"]
        extra["risk"] = rk
        if not ok7:
            return M_NO, chk, {**extra, "why": "R:R < 3 ⇒ trade नाही"}
        conv1 = M.first_leg_cap(conv, k["legs"], lvl["sweeps"], ev["commit_strong"])
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
        for k in ("③", "④", "⑤", "⑥", "⑦"):
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
                "mature_step_down": bool(ctx.get("step_down")),
                "trade_side": list(DD.trade_side(trend)),
                "protected": None if st.protected is None else {"kind": st.protected.kind, "price": st.protected.price,
                                                                  "day": ("before window" if self.sealed and self.sealed(st.protected.day)
                                                                          else str(st.protected.day.date()))},
                "range_band": st.band, "active_levels": act, "checklist": chk, "decision": dec, "mark": mark,
                "K": best.get("K"), "risk": best.get("risk"), "conviction": best.get("conviction"), "conv_score": best.get("conv_score"),
                "missing": best.get("missing"), "evidence": best.get("evidence"), "why": best.get("why"),
                "level": best.get("level"), "liquidity": best.get("liquidity"), "trendline": best.get("trendline"),
                "commit": best.get("commit"), "commitment_form": (best.get("commit") or {}).get("form"),
                "level_evals": evals}

    def run(self, bars=None):
        bars = range(len(self.m15)) if bars is None else bars
        return [self.decide(t) for t in bars]
