"""opportunity_engine/visual_audit/evaluate.py — visual audit उपयोगी आहे का हे डेटाने तपासणे (spec §17.7). सिद्ध झाल्याशिवाय score/gate मध्ये नाही.

  • Agreement matrix: engine grade × model verdict, model verdict × user verdict.
  • Outcome: प्रत्येक audited level ची पुढच्या 10 sessions मधली प्रत्यक्ष reaction — पहिल्या स्पर्शानंतर किंमत zone पासून किती दूर गेली (ADR च्या पटीत) आणि zone
    टिकला का (दूरच्या कडेपलीकडे close नाही). Verdict/consensus वर्गानुसार सरासरी. त्या levels वरच्या trades चा R (trade row मधला `zone_id`).
  • Tuning अहवाल: model (आणि वापरकर्ता) दोघांनी SPURIOUS/WRONG ठरवलेल्या levels चे §2.6 components वि. VALID — फक्त अहवाल, threshold आपोआप बदलत नाही.
  • तयारी: किमान 4 आठवडे आणि 200+ audited levels नंतरच निष्कर्ष.
"""
import numpy as np
import pandas as pd

SUPPORT_KINDS = ("DEMAND", "SUPPORT")


def agreement_matrix(audit_df, feedback=None):
    """रिटर्न {"grade_vs_model": DataFrame, "model_vs_user": DataFrame|None}."""
    if audit_df is None or not len(audit_df):
        return {"grade_vs_model": pd.DataFrame(), "model_vs_user": None}
    a = audit_df.copy()
    a["model_verdict"] = a["model_verdict"].fillna("FAILED")
    out = {"grade_vs_model": pd.crosstab(a["engine_grade"].fillna("?"), a["model_verdict"], margins=True, margins_name="एकूण"), "model_vs_user": None}
    if feedback:
        a["user_verdict"] = a["level_id"].map(feedback)
        b = a.dropna(subset=["user_verdict"])
        if len(b):
            out["model_vs_user"] = pd.crosstab(b["model_verdict"], b["user_verdict"], margins=True, margins_name="एकूण")
    return out


def level_reaction(row, bars, adr=None, sessions=10, follow=10):
    """एका audited level ची reaction. bars = engine frame (bar_end, high, low, close) — audit_date नंतरचे पुढचे `sessions` दिवस वापरले जातात.
    रिटर्न dict: touched, touch_time, reaction_pts, reaction_adr, held."""
    d0 = pd.Timestamp(row["audit_date"]).normalize()
    be = pd.to_datetime(bars["bar_end"])
    days = sorted(set(be[be >= d0].dt.normalize()))[:sessions]
    if not days:
        return {"touched": False, "touch_time": None, "reaction_pts": np.nan, "reaction_adr": np.nan, "held": None}
    m = (be >= d0) & (be.dt.normalize() <= days[-1])
    seg = bars[m.values].reset_index(drop=True)
    lo, hi = float(row["zone_low"]), float(row["zone_high"])
    support = row.get("kind") in SUPPORT_KINDS
    touch = np.nonzero(((seg["low"] <= hi) & (seg["high"] >= lo)).to_numpy())[0]
    if not len(touch):
        return {"touched": False, "touch_time": None, "reaction_pts": np.nan, "reaction_adr": np.nan, "held": None}
    j = int(touch[0])
    after = seg.iloc[j:j + follow + 1]
    if support:
        reaction = float(after["high"].max()) - hi
        held = bool((after["close"] >= lo).all())
    else:
        reaction = lo - float(after["low"].min())
        held = bool((after["close"] <= hi).all())
    reaction = max(reaction, 0.0)
    return {"touched": True, "touch_time": seg["bar_end"].iloc[j], "reaction_pts": reaction,
            "reaction_adr": reaction / adr if adr and np.isfinite(adr) and adr > 0 else np.nan, "held": held}


def reactions(audit_df, bars, adr_lookup=None, sessions=10):
    """audit rows (audit_date, zone_low, zone_high, kind, …) + reaction columns. adr_lookup(date) -> ADR (ऐच्छिक)."""
    if audit_df is None or not len(audit_df):
        return pd.DataFrame()
    rows = []
    for _, r in audit_df.iterrows():
        adr = adr_lookup(r["audit_date"]) if adr_lookup else None
        rows.append({**r.to_dict(), **level_reaction(r, bars, adr, sessions)})
    return pd.DataFrame(rows)


def reaction_table(rx, by="model_verdict"):
    """by (verdict / consensus_class) नुसार: levels, स्पर्श %, सरासरी reaction (ADR), टिकले %."""
    if rx is None or not len(rx):
        return pd.DataFrame()
    out = []
    for key, g in rx.groupby(rx[by].fillna("—")):
        t = g[g["touched"]]
        out.append({by: key, "levels": len(g), "स्पर्श_%": round(100.0 * len(t) / len(g), 1),
                    "avg_reaction_adr": round(float(t["reaction_adr"].mean()), 3) if len(t) and t["reaction_adr"].notna().any() else None,
                    "avg_reaction_pts": round(float(t["reaction_pts"].mean()), 1) if len(t) else None,
                    "टिकले_%": round(100.0 * t["held"].astype(bool).mean(), 1) if len(t) else None})
    return pd.DataFrame(out)


def trades_by_class(trades, audit_df, by="consensus_class", col="r"):
    """trades चा `zone_id` audit rows च्या level_id शी जोडून वर्गनिहाय R."""
    if trades is None or not len(trades) or audit_df is None or not len(audit_df) or "zone_id" not in trades.columns:
        return pd.DataFrame()
    m = audit_df.drop_duplicates("level_id", keep="last").set_index("level_id")[by]
    t = trades.assign(_cls=trades["zone_id"].map(m)).dropna(subset=["_cls"])
    if not len(t):
        return pd.DataFrame()
    return t.groupby("_cls")[col].agg(trades="count", expectancy_r="mean", total_r="sum").round(3).reset_index().rename(columns={"_cls": by})


def tuning_report(records, feedback=None):
    """records (JSONL/audit) मधले `components` + verdicts: SPURIOUS (model) / WRONG (user) वि. VALID — §2.6 components ची सरासरी. फक्त अहवाल."""
    feedback = feedback or {}
    rows = []
    for rec in records or []:
        comps = rec.get("components") or {}
        verdicts = {v["label"]: v["verdict"] for v in (((rec.get("overlay") or {}).get("data") or {}).get("verdicts") or [])}
        for lab in rec.get("labels") or []:
            c = comps.get(lab["level_id"])
            v = verdicts.get(lab["label"])
            if not c or v is None:
                continue
            user = feedback.get(lab["level_id"])
            group = "दोघांनी SPURIOUS/WRONG" if v == "SPURIOUS" and user == "WRONG" else "model SPURIOUS" if v == "SPURIOUS" else "VALID" if v == "VALID" else "SHIFT"
            rows.append({"गट": group, **c})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.groupby("गट").agg(["mean", "count"]).round(3)


def readiness(audit_df, min_weeks=4, min_levels=200):
    """निष्कर्ष काढण्याइतका डेटा आहे का — (ok, संदेश)."""
    if audit_df is None or not len(audit_df):
        return False, "अजून कुठलाही audit नाही."
    days = pd.to_datetime(audit_df["audit_date"])
    weeks = (days.max() - days.min()).days / 7.0
    n = int(audit_df["model_verdict"].notna().sum())
    ok = weeks >= min_weeks and n >= min_levels
    return ok, f"{weeks:.1f} आठवडे, {n} audited levels — " + ("अहवाल ग्राह्य." if ok else f"किमान {min_weeks} आठवडे आणि {min_levels}+ levels नंतरच निष्कर्ष.")
