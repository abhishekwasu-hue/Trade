"""
research/elliott_candle_merge_report.py — Elliott + candle merge C2/C3 (addendum §4, §7) → docs/reports/elliott_candle_merge.md
---------------------------------------------------------------------------------------------------------------------------
🎓 फक्त IS weekly काळ (11 Feb 2019 → 31 Dec 2021); VAL / holdout उघडत नाही. **Model premium** (E4 सारखं) ⇒ ₹ अंदाज.
Trading settings सगळ्या variants ना सारखे: credit guard बंद (E4 variant B — model premium वर guard ~90% signals अडवतो) + पूर्ण exits.
Variants (signal settings): (a) generic · (b) +wave-profile · c1–c8 §3 सुधारणा एकेक · c_all · (d) b + c_all.
(r) random baseline: (a) चे ARMED episodes (re-arm सह) — त्या episode चा trigger TF, 09:30–14:45 मधले bars, त्या वेळचा setup
    (strike/inv), structure-free exits. Elliott ने trade केलेल्या (TRIGGERED) episodes वर तुलना: Elliott व random दोन्ही
    resample करून फरकाचा bootstrap CI (दोन्ही बाजूंचा sampling noise).
सांख्यिकी (scipy नाही ⇒ numpy): day-block bootstrap (1,000), PBO (CSCV, S = 16), White Reality Check (variants वि. (a)),
score quintile monotonicity, bull put वि. bear call. KEEP नियम: (a) पेक्षा (PBO ≤ 0.05, RC p < 0.05) **आणि** random पेक्षा
(फरकाचा CI > 0) चांगला, **आणि** VAL मध्ये टिकला (VAL अजून चालवला नाही ⇒ इथे कुठलाही KEEP अंतिम नाही).
C2 (report-only): preferred counts चे completed legs (leg चं शेवटचं label) — impulsive वि. corrective: body %, overlap, CLV,
efficiency, displacement / bar (Mann-Whitney U, ties सह normal approx; legs स्वतंत्र नाहीत ⇒ p अंदाजे).

    python3 research/elliott_candle_merge_report.py [--workers 4] [--quick]
"""
import argparse
import collections
import itertools
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import backtest as BT  # noqa: E402
from elliott import data_policy as DP  # noqa: E402
from elliott import golden as GD  # noqa: E402
from elliott import settings as S  # noqa: E402
from elliott import trigger as TR  # noqa: E402
import hashlib  # noqa: E402
from elliott.patterns import LABELS  # noqa: E402

OUT = os.path.join(ROOT, "docs", "reports", "elliott_candle_merge.md")
START, WARM, END = "2019-02-11", "2018-10-01", "2021-12-31 23:59:59"
TRADE = {"c_min_by_dte": [0.0] * 5, "min_credit_pts": 0.0}
C = {
    "c1_time_slot": {"strength_ref": "time_slot"},
    "c2_cap_logic": {"strength_cap_mode": "logic"},
    "c3_reclaim_depth": {"w_reclaim_depth": 0.10},
    "c4_overlap": {"w_overlap": 0.10},
    "c5_path_n3": {"path_checks": True, "n3_penalty": 0.05},
    "c6_body_fix": {"body_term_mode": "body_or_reclaim", "min_body_or_reclaim": True},
    "c7_followthrough": {"followthrough_mode": "addendum"},
    "c8_c_leg_exhaustion": {"c_leg_exhaustion_required": True},
}
C_ALL = {k: v for d in C.values() for k, v in d.items() if k != "c_leg_exhaustion_required"}
VARIANTS = {"a_generic": {}, "b_profile": {"candle_profile_mode": "on"}, **C, "c_all": C_ALL,
            "d_profile_c_all": {"candle_profile_mode": "on", **C_ALL}}


LEG_KIND = {"impulse": {("impulse", w): ("impulsive" if w in "135" else "corrective") for w in "12345"},
            "zigzag": {("zigzag", w): ("impulsive" if w in "AC" else "corrective") for w in "ABC"},
            "flat": {("flat", w): ("impulsive" if w == "C" else "corrective") for w in "BC"}}   # flat A 3-wave ⇒ वगळला


def _data():
    d = pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    d = d[(d["timestamp"] >= WARM) & (d["timestamp"] <= END)]
    return DP.filter_allowed(d, "research").reset_index(drop=True)


class ArmScanner(TR.Scanner):
    """(a) साठी: ARMED episodes (re-arm सह) + setup इतिहास (random baseline), आणि preferred counts चे completed legs (C2)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.episodes, self.hist, self.legs = [], collections.defaultdict(list), {}
        snap_fn = self.eng.snapshot

        def snapshot(t):
            snap = snap_fn(t)
            for d, v in snap.degrees.items():
                n = v.preferred
                if n is not None and n.pattern in LEG_KIND:
                    for i in range(min(len(n.points) - 1, len(LABELS[n.pattern]))):
                        self.legs[(d, n.points[i].ts, n.points[i + 1].ts)] = (n.pattern, LABELS[n.pattern][i], n.points[i],
                                                                              n.points[i + 1], t)     # शेवटचं label
            return snap
        self.eng.snapshot = snapshot

    def _arm(self, st, t):
        key = (st.degree, st.code, st.trade_dir, st.wave_start.ts)
        h = self.hist[key]
        sig = (st.extreme.price, st.hard_inv, tuple(st.alt_invs), tuple(st.levels))
        if not h or h[-1][2] != sig:
            h.append((pd.Timestamp(t), st, sig))                                 # त्या वेळचा setup (strike/inv साठी)
        super()._arm(st, t)

    def _transition(self, st, t, to, why):
        key = (st.degree, st.code, st.trade_dir, st.wave_start.ts)
        if self.state.get(key, "IDLE") in ("IDLE", "EXPIRED"):
            self.episodes.append((key, pd.Timestamp(t)))
        super()._transition(st, t, to, why)

    def setup_at(self, key, t):
        h = self.hist.get(key, [])
        i = int(np.searchsorted(np.array([x[0].value for x in h]), pd.Timestamp(t).value, "right")) - 1
        return h[i][1] if i >= 0 else None


SCRIPT_VERSION = 2


def _src_hash():
    h = hashlib.sha1()
    files = [os.path.abspath(__file__), os.path.join(ROOT, "price_action", "legs.py")]
    files += sorted(os.path.join(ROOT, "elliott", f) for f in os.listdir(os.path.join(ROOT, "elliott")) if f.endswith(".py"))
    for f in files:
        with open(f, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:10]


CACHE = os.environ.get("CM_CACHE", os.path.expanduser("~/.cache/trade_candle_merge"))


def run_variant(args):
    """एक variant — निकाल CACHE मध्ये (container restart झाला तरी पूर्ण झालेले variants पुन्हा चालवत नाही)."""
    import pickle
    name, ov = args
    tag = hashlib.sha1(repr((S.snapshot(S.validate(dict(ov))[0])["hash"], sorted(TRADE.items()), WARM, START, END, PER_EP,
                             SCRIPT_VERSION, _src_hash())).encode()).hexdigest()[:12]
    key = os.path.join(CACHE, f"{name}_{tag}.pkl")
    if os.path.exists(key):
        with open(key, "rb") as f:
            return dict(pickle.load(f), cached=True)
    out = _run_variant(name, ov)
    os.makedirs(CACHE, exist_ok=True)
    with open(key + ".tmp", "wb") as f:
        pickle.dump(out, f)
    os.replace(key + ".tmp", key)
    return out


def _run_variant(name, ov):
    assert pd.Timestamp(END) <= DP.IS_END and pd.Timestamp(START) >= pd.Timestamp("2019-02-11"), "फक्त IS"
    d = _data()
    s, e = S.validate({**ov})
    assert not e, e
    sc = ArmScanner(d, s) if name == "a_generic" else TR.Scanner(d, s)
    times = sc.times()
    sigs = BT.collect_signals(sc, times)
    sigs_is = {t: v for t, v in sigs.items() if t >= pd.Timestamp(START)}
    st = {**s, **TRADE}
    common = dict(scanner=sc, trade_from=START, entry_until=pd.Timestamp(END) - pd.Timedelta(days=7))
    full = BT.Backtest(d, st, replay=sigs, **common)
    full.run(times)
    sfe = BT.Backtest(d, st, replay=sigs, structure_free_exits=True, entry_filters=False, pricer=full.pricer, cal=full.cal,
                      book=full.book, **common)
    sfe.run(times)
    out = {"name": name, "n_sig": sum(len(v) for v in sigs_is.values()), "full": full.results(), "sfe": sfe.results(),
           "scores": [(x.t, x.score, x.direction, x.candle_ctx.get("label"), (x.candle_ctx.get("profile") or {}).get("admitted"))
                      for v in sigs_is.values() for x in v]}
    if name == "a_generic":
        out["random"] = random_pool(d, sc, st, times, full)
        out["legs"] = leg_study(sc)
    return out


PER_EP = 12


def random_pool(d, sc, st, times, ref_bt, per_ep=PER_EP):
    """प्रत्येक ARMED episode (ARMED → पुढचा TRIGGERED/EXPIRED, कमाल 3 दिवस): त्या setup चा trigger TF (arm वेळी), 09:30–14:45 मधले
    त्या TF चे bars (समान अंतराने कमाल `per_ep`); प्रत्येक bar वर त्या वेळचा setup (extreme / inv / alt invs) ⇒ entry,
    structure-free exits, filters बंद. Rows: (episode, R, triggered?)."""
    out_end = {}
    trans = collections.defaultdict(list)
    for t, key, _, b, _ in sc.transitions:
        if b in ("TRIGGERED", "EXPIRED"):
            trans[key].append((pd.Timestamp(t), b))
    replay, ep_of = collections.defaultdict(list), {}
    n = 0
    lo, hi = pd.Timestamp("09:30").time(), pd.Timestamp("14:45").time()
    for e, (key, t0) in enumerate(sc.episodes):
        if t0 < pd.Timestamp(START):
            continue
        nxt = next(((t, b) for t, b in trans[key] if t >= t0), None)
        t1 = min(nxt[0], t0 + pd.Timedelta(days=3)) if nxt else t0 + pd.Timedelta(days=3)
        out_end[e] = bool(nxt and nxt[1] == "TRIGGERED" and nxt[0] <= t0 + pd.Timedelta(days=3))
        st0 = sc.setup_at(key, t0)
        if st0 is None:
            continue
        tf = sc._tf_for(st0, t0)[0] or "5m"
        fr = sc.frames[tf]
        be = fr["bar_end"].to_numpy("datetime64[ns]")
        i0 = int(np.searchsorted(be, np.datetime64(t0, "ns"), "left"))
        i1 = int(np.searchsorted(be, np.datetime64(t1, "ns"), "right"))
        cand = [j for j in range(i0, i1) if lo <= pd.Timestamp(be[j]).time() <= hi]
        if len(cand) > per_ep:
            cand = [cand[int(i)] for i in np.linspace(0, len(cand) - 1, per_ep)]
        for j in cand:
            tj = pd.Timestamp(be[j])
            stp = sc.setup_at(key, tj) or st0
            n += 1
            o, h, l, c = (float(fr[k].iloc[j]) for k in ("open", "high", "low", "close"))
            buf = st["soft_buffer_pts"]
            sig = TR.Signal(t=tj, degree=stp.degree, setup=stp.code, tier=stp.tier, direction=stp.direction,
                            trade_dir=stp.trade_dir, ttf=tf, ttf_idx=j, levels=list(stp.levels), touched=c,
                            hard_inv=stp.hard_inv, inv_rule=stp.inv_rule, soft_stop=l - buf if stp.trade_dir > 0 else h + buf,
                            sub_origin=stp.extreme.price, bars_last_subleg=1, extreme=stp.extreme.price,
                            extreme_ts=stp.extreme.ts, wave_start_ts=stp.wave_start.ts + pd.Timedelta(microseconds=n),
                            comp=(o, h, l, c), n=1, score=0.0, vote=stp.vote, opp_max=stp.opp_max, alt_invs=list(stp.alt_invs),
                            pattern=stp.node.pattern, current_wave=stp.node.current_wave,
                            inv_degree=getattr(stp, "inv_degree", None), inv_start_ts=getattr(stp, "inv_start_ts", None),
                            parent_start_ts=getattr(stp, "parent_start_ts", None))
            replay[tj].append(sig)
            ep_of[sig.wave_start_ts] = e
    bt = BT.Backtest(d, st, scanner=sc, replay=dict(replay), structure_free_exits=True, entry_filters=False, pricer=ref_bt.pricer,
                     cal=ref_bt.cal, book=ref_bt.book, trade_from=START, entry_until=pd.Timestamp(END) - pd.Timedelta(days=7))
    bt.run(times)
    res = bt.results()
    rows = [(ep_of[tr.sig.wave_start_ts], r, out_end[ep_of[tr.sig.wave_start_ts]]) for tr, r in zip(bt.closed, res["R"])] \
        if len(res) else []
    return {"pool": rows, "n_candidates": n, "episodes": len(sc.episodes), "episodes_is": len(out_end)}


def random_compare(ew, pool, reps=1000, seed=17):
    """Elliott mean R − random mean R (random = प्रत्येक episode मधून एक random entry). दोन्ही resample (bootstrap) ⇒ फरकाचा
    95% CI आणि P(फरक ≤ 0). ew: R array; pool: DataFrame(ep, R)."""
    ew = np.asarray(ew, float)
    ew = ew[np.isfinite(ew)]
    if len(ew) < 5 or pool.empty:
        return {"diff": np.nan, "lo": np.nan, "hi": np.nan, "p": np.nan, "rnd": np.nan}
    eps = [v for v in pool.groupby("ep")["R"].apply(np.array).values if len(v)]
    rnd_mean = float(np.mean([v.mean() for v in eps]))
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(reps):
        e = ew[rng.integers(len(ew), size=len(ew))].mean()
        pick = rng.integers(len(eps), size=len(eps))
        r = np.mean([eps[i][rng.integers(len(eps[i]))] for i in pick])
        diffs.append(e - r)
    diffs = np.array(diffs)
    return {"diff": float(ew.mean() - rnd_mean), "lo": float(np.percentile(diffs, 2.5)), "hi": float(np.percentile(diffs, 97.5)),
            "p": float(np.mean(diffs <= 0)), "rnd": rnd_mean}


def leg_study(sc):
    """C2: preferred counts चे completed legs (दोन्ही टोक confirmed) — impulsive वि. corrective features."""
    from price_action.legs import leg_features
    rows = []
    for (d, _, _), (pat, lab, p0, p1, t) in sc.legs.items():
        if t < pd.Timestamp(START) or (pat, lab) not in LEG_KIND[pat]:
            continue
        fr = sc.md[d]["frame"]
        f = leg_features(fr, p0.bar_idx, p1.bar_idx, 1 if p1.price > p0.price else -1, p0.price, p1.price,
                         sc.eng.cache[d].mr[p1.bar_idx])
        rows.append({"degree": d, "kind": LEG_KIND[pat][(pat, lab)], "wave": f"{pat}/{lab}", "body_pct": f["body_pct"],
                     "overlap": f["overlap"], "clv": f["clv"], "eff_range": f["eff_range"], "disp_n": f["disp_n"], "bars": f["bars"],
                     "disp_per_bar": f["disp_n"] / max(f["bars"], 1)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ statistics (numpy)
def mann_whitney(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    n1, n2 = len(x), len(y)
    if n1 < 3 or n2 < 3:
        return np.nan, np.nan
    allv = np.r_[x, y]
    r = pd.Series(allv).rank().to_numpy()
    u = r[:n1].sum() - n1 * (n1 + 1) / 2
    N = n1 + n2
    _, cnt = np.unique(allv, return_counts=True)
    tie = (cnt ** 3 - cnt).sum() / (N * (N - 1))                                    # ties correction
    mu, sd = n1 * n2 / 2, math.sqrt(max(n1 * n2 / 12 * ((N + 1) - tie), 0.0))
    z = (u - mu) / sd if sd > 0 else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    return p, 2 * u / (n1 * n2) - 1                                                  # p, rank-biserial effect


def day_block_ci(df, reps=1000, seed=11):
    if df.empty:
        return (np.nan, np.nan)
    g = df.assign(day=pd.to_datetime(df["fill"]).dt.date).groupby("day")["R"].apply(list)
    days = list(g.values)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(reps):
        pick = rng.integers(len(days), size=len(days))
        vals = [v for i in pick for v in days[i]]
        means.append(np.mean(vals) if vals else 0.0)
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


def pbo_cscv(perf, S=16, max_combos=3000, seed=5):
    """perf: DataFrame (rows = variants, cols = S time blocks) mean R. PBO = P(IS-best चा OOS rank logit ≤ 0)."""
    if perf.shape[0] < 2:
        return np.nan
    blocks = list(range(S))
    combos = list(itertools.combinations(blocks, S // 2))
    rng = np.random.default_rng(seed)
    if len(combos) > max_combos:
        combos = [combos[i] for i in rng.choice(len(combos), max_combos, replace=False)]
    lam = []
    for cmb in combos:
        is_, oos = list(cmb), [b for b in blocks if b not in cmb]
        best = perf[is_].mean(axis=1).idxmax()
        oos_perf = perf[oos].mean(axis=1)
        w = (oos_perf.rank()[best] - 0.5) / len(oos_perf)
        lam.append(math.log(w / (1 - w)))
    return float(np.mean(np.array(lam) <= 0))


def reality_check(trades, bench, reps=1000, seed=3):
    """White Reality Check, **प्रति-trade सरासरी R** वर (day-block bootstrap). H0: कुठलाही variant (a) पेक्षा चांगला नाही.
    trades: {variant: DataFrame(fill, R)}. दिवस नसलेल्या variant ला 0 R भरत नाही (कमी trades = आपोआप 'चांगला' टाळतो)."""
    def per_day(df):
        g = df.assign(day=pd.to_datetime(df["fill"]).dt.date).groupby("day")["R"]
        return g.sum(), g.count()
    days = sorted(set().union(*[set(pd.to_datetime(d["fill"]).dt.date) for d in list(trades.values()) + [bench]]))
    pos = {d: i for i, d in enumerate(days)}

    def arrays(df):
        sm, ct = per_day(df)
        S, N = np.zeros(len(days)), np.zeros(len(days))
        S[[pos[d] for d in sm.index]] = sm.to_numpy()
        N[[pos[d] for d in ct.index]] = ct.to_numpy()
        return S, N
    bS, bN = arrays(bench)
    VS = [arrays(df) for df in trades.values()]
    if not VS:
        return np.nan
    obs = np.array([S.sum() / max(N.sum(), 1) - bS.sum() / max(bN.sum(), 1) for S, N in VS])
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(reps):
        idx = rng.integers(len(days), size=len(days))
        b = bS[idx].sum() / max(bN[idx].sum(), 1)
        d = np.array([S[idx].sum() / max(N[idx].sum(), 1) - b for S, N in VS]) - obs   # H0 वर केंद्रित
        cnt += d.max() >= obs.max()
    return cnt / reps


def summarize(df):
    if df is None or df.empty:
        return {"n": 0}
    r = df["R"].dropna()
    k = max(1, int(np.ceil(len(r) * 0.05)))
    return {"n": len(df), "win%": f"{(df['pnl'] > 0).mean() * 100:.1f}", "R सरासरी": r.mean(), "CVaR5% R": r.nsmallest(k).mean(),
            "max-loss%": df["max_loss_hit"].mean() * 100, "breach%": df["breach"].mean() * 100}


def fmt(v):
    if isinstance(v, (float, np.floating)):
        return "—" if not np.isfinite(v) else (f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}")
    return str(v)


def table(rows, cols):
    L = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    L += ["| " + " | ".join(fmt(r.get(c, "")) for c in cols) + " |" for r in rows]
    return L


G2_NOTE = ("> **G2 निर्णय (7 Oct 2026):** हा अहवाल entry quality मधला फरक **मोजू शकत नाही**. याची दोन कारणं आहेत: progress-time exit "
           "बहुतेक trades 20–30 मिनिटांत बंद करतो, आणि model premium (IV = realized vol) मध्ये खरी skew/IV माहिती नाही. त्यामुळे निष्कर्ष "
           "\"Elliott/candle मध्ये edge नाही\" असा **नाही**, तर **\"अजून मोजता आलं नाही\"** असा आहे. सगळे candle settings off/shadow; VAL नंतर "
           "(खरे premiums + E4 review fixes).")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--quick", action="store_true", help="फक्त a, b, c_all (चाचणी)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    vs = {k: v for k, v in VARIANTS.items() if not a.quick or k in ("a_generic", "b_profile", "c_all")}
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers) as pool:
        res = {r["name"]: r for r in pool.map(run_variant, list(vs.items()))}
    base = res["a_generic"]
    L = ["# Elliott + candle merge — C2/C3 अहवाल (NIFTY, IS 11 Feb 2019 – 31 Dec 2021)", "", G2_NOTE, "",
         "> ⚠️ **Model premium** (BS, IV = 20 दिवस realized vol) — options data अजून नाही. ₹/R अंदाज; निर्णय खऱ्या premium वर पुन्हा "
         "चालवल्यानंतरच. Trading settings सगळ्या variants ना सारखे: credit guard बंद (E4 variant B) + पूर्ण exits. VAL / holdout उघडले नाहीत.",
         "", f"Variants: {len(res)} ({sum(1 for r in res.values() if r.get('cached'))} cache मधून; cache key = settings + trading "
         f"settings + काळ + code hash) · वेळ {(time.time() - t0) / 60:.1f} मि. · `c_all` = c1–c7 (c8 C-leg wait वेगळा).", "",
         "## 1. Variants — signals आणि trades (पूर्ण exits)", ""]
    rows, block_perf = [], {}
    edges = pd.date_range(START, END, periods=17)
    for name, r in res.items():
        df = r["full"]
        lo, hi = day_block_ci(df)
        row = {"variant": name, "signals": r["n_sig"], **summarize(df), "R 95% CI (day-block)": f"{fmt(lo)} … {fmt(hi)}"}
        for side in ("bull_put", "bear_call"):
            row[f"R {side}"] = df[df["dir"] == side]["R"].mean() if len(df) else np.nan
        row["admitted"] = sum(1 for x in r["scores"] if x[4])
        row["R (structure-free exits)"] = r["sfe"]["R"].mean() if len(r["sfe"]) else np.nan
        for tier in ("A", "B", "C"):
            k = int((df["tier"] == tier).sum()) if len(df) else 0
            row[f"R tier {tier}"] = f"{df[df['tier'] == tier]['R'].mean():.3f} ({k})" if k else "—"
        rows.append(row)
        if len(df):
            blk = pd.cut(pd.to_datetime(df["fill"]), edges, labels=False, include_lowest=True)
            block_perf[name] = df.groupby(blk)["R"].mean().reindex(range(16)).fillna(0.0)
    L += table(rows, ["variant", "signals", "n", "win%", "R सरासरी", "R 95% CI (day-block)", "CVaR5% R", "R bull_put", "R bear_call",
                      "max-loss%", "admitted"])
    L += ["", "Tier नुसार (पूर्ण exits, कंसात n):", ""]
    L += table(rows, ["variant", "R tier A", "R tier B", "R tier C", "R (structure-free exits)"])
    L += ["", "Setup नुसार R (पूर्ण exits; n ≥ 5 असलेले cells):", ""]
    setups = sorted({x for r in res.values() for x in r["full"].get("setup", pd.Series(dtype=str)).unique()})
    srows = []
    for name, r in res.items():
        df = r["full"]
        row = {"variant": name}
        for su in setups:
            g = df[df["setup"] == su]["R"] if len(df) else pd.Series(dtype=float)
            row[su] = f"{g.mean():.3f} ({len(g)})" if len(g) >= 5 else (f"({len(g)})" if len(g) else "—")
        srows.append(row)
    L += table(srows, ["variant"] + setups)
    L += ["", "`admitted` = profile मुळे (own_correction) generic पेक्षा जास्तीचे signals — reduce-only अपवाद, वेगळे मोजले."]
    perf = pd.DataFrame(block_perf).T
    pbo = pbo_cscv(perf) if len(perf) > 1 else np.nan
    rc = reality_check({k: r["full"] for k, r in res.items() if k != "a_generic" and len(r["full"])}, base["full"]) \
        if len(res) > 1 and len(base["full"]) else np.nan
    L += ["", f"**PBO (CSCV, S = 16):** {fmt(pbo)} (> 0.05 ⇒ reject) · **White Reality Check p** (प्रति-trade R वर; कुठलाही variant (a) पेक्षा खरंच चांगला?): "
              f"{fmt(rc)}", ""]
    # random baseline
    rp = base.get("random", {})
    pool = pd.DataFrame(rp.get("pool", []), columns=["ep", "R", "triggered"])
    L += ["## 2. Random entry baseline (r) — त्याच ARMED zones मध्ये", ""]
    trig = pool[pool["triggered"]] if len(pool) else pool
    cmp_a = random_compare(base["sfe"]["R"] if len(base["sfe"]) else [], trig[["ep", "R"]])
    if pool.empty:
        L += ["Random pool रिकामा."]
    else:
        by = pool.groupby("triggered")
        L += [f"ARMED episodes {rp.get('episodes')} (IS मध्ये सुरू {rp.get('episodes_is')}; random trade झालेले {pool['ep'].nunique()}: "
              f"Elliott ने trigger केलेले {trig['ep'].nunique()}, trigger न होता EXPIRED {pool[~pool['triggered']]['ep'].nunique()}). "
              f"Candidate entries {rp.get('n_candidates')} (episode ला कमाल {PER_EP}, त्या setup च्या trigger TF वर, त्या वेळचा "
              "setup). Exits: structure-free (emergency, premium stop, profit %, expiry) — Elliott बाजूलाही तेच.", "",
              "| random episodes | n trades | episode-सरासरी R |", "|---|---|---|"]
        for k, g in by:
            L.append(f"| {'Elliott ने trigger केलेले' if k else 'trigger न झालेले (EXPIRED)'} | {len(g)} | "
                     f"{fmt(float(g.groupby('ep')['R'].mean().mean()))} |")
        L += ["", f"**तुलना (फक्त trigger झालेले episodes):** Elliott (a) mean R {fmt(float(base['sfe']['R'].mean()))} "
                  f"(n {len(base['sfe'])}) वि. random {fmt(cmp_a['rnd'])} ⇒ फरक **{cmp_a['diff']:+.4f}** "
                  f"(95% CI {cmp_a['lo']:+.4f} … {cmp_a['hi']:+.4f}; P(फरक ≤ 0) = {fmt(cmp_a['p'])}; Elliott व random दोन्ही resample).",
              f"- निष्कर्ष: {'Elliott entry random पेक्षा चांगली (CI > 0)' if cmp_a['lo'] > 0 else ('Elliott entry random पेक्षा **वाईट** (CI < 0)' if cmp_a['hi'] < 0 else 'Elliott entry आणि random मध्ये फरक दिसत नाही (CI 0 ओलांडतो)')}."]
    L += ["", "## 3. KEEP / REJECT (addendum §7)", ""]
    a_mean = summarize(base["full"]).get("R सरासरी", np.nan)
    multi_ok = np.isfinite(pbo) and pbo <= 0.05 and np.isfinite(rc) and rc < 0.05
    L += [f"(a) पेक्षा चांगला मानायला: फरक > 0 **आणि** PBO ≤ 0.05 **आणि** RC p < 0.05 (सध्या PBO {fmt(pbo)}, RC p {fmt(rc)} ⇒ "
          f"{'अट पूर्ण' if multi_ok else 'अट पूर्ण नाही'}). Random पेक्षा चांगला मानायला: फरकाचा CI > 0 (trigger झालेले episodes, "
          "structure-free exits).", ""]
    for r in rows:
        if r["variant"] == "a_generic":
            continue
        diff = r.get("R सरासरी", np.nan) - a_mean
        better_a = diff > 0 and multi_ok
        cr = random_compare(res[r["variant"]]["sfe"]["R"] if len(res[r["variant"]]["sfe"]) else [], trig[["ep", "R"]])
        better_r = cr["lo"] > 0
        verdict = "VAL साठी उमेदवार (VAL अजून नाही)" if better_a and better_r else "REJECT (setting off)"
        L.append(f"- **{r['variant']}**: (a) शी R फरक {diff:+.4f} ⇒ {'चांगला' if better_a else 'चांगला नाही'}; random शी फरक "
                 f"{cr['diff']:+.4f} (CI {cr['lo']:+.4f} … {cr['hi']:+.4f}) ⇒ {'चांगला' if better_r else 'चांगला नाही'} ⇒ {verdict}")
    L += ["", "(a) शी फरक ±0.002 R च्या आत = व्यवहारात काहीच नाही. PBO > 0.05 / RC p ≥ 0.05 ⇒ variants मधले फरक योगायोगापेक्षा वेगळे "
              "मानता येत नाहीत."]
    # monotonicity
    L += ["", "## 4. Score monotonicity — (a) signal score quintiles वि. trade R", ""]
    sc = pd.DataFrame(base["scores"], columns=["t", "score", "dir", "label", "adm"])
    tr = base["full"]
    if len(tr) >= 10:
        m = tr.merge(sc.drop_duplicates(["t", "dir"])[["t", "dir", "score", "label"]], on=["t", "dir"], how="left").dropna(subset=["score"])
        m["q"] = pd.qcut(m["score"].rank(method="first"), 5, labels=False) + 1
        L += table([{"quintile": int(q), "n": len(g), "score सरासरी": g["score"].mean(), "R सरासरी": g["R"].mean(),
                     "win%": f"{(g['pnl'] > 0).mean() * 100:.1f}"} for q, g in m.groupby("q")], ["quintile", "n", "score सरासरी", "R सरासरी", "win%"])
        L += ["", "Blended label नुसार (फक्त log): " + ", ".join(f"{k} n={len(g)} R={g['R'].mean():.3f}" for k, g in m.groupby("label"))]
    else:
        L += ["Trades कमी — quintiles नाहीत."]
    # C2 legs
    L += ["", "## 5. C2 — leg features: impulsive वि. corrective (report-only)", ""]
    lg = base.get("legs")
    if lg is not None and len(lg):
        rows2 = []
        L += ["Legs (wave नुसार): " + ", ".join(f"{k} {v}" for k, v in lg["wave"].value_counts().sort_index().items()) +
              ". Preferred count मध्ये शेवटची wave (5 / C) पूर्ण झालेली क्वचितच दिसते ⇒ impulsive ≈ 1, 3, A; corrective ≈ 2, 4, B.", ""]
        for feat in ("bars", "body_pct", "overlap", "clv", "eff_range", "disp_n", "disp_per_bar"):
            for d in sorted(lg["degree"].unique()):
                x = lg[(lg["degree"] == d) & (lg["kind"] == "impulsive")][feat]
                y = lg[(lg["degree"] == d) & (lg["kind"] == "corrective")][feat]
                p, eff = mann_whitney(x, y)
                rows2.append({"feature": feat, "degree": f"D{d}", "impulsive median": x.median(), "corrective median": y.median(),
                              "n imp/cor": f"{len(x)}/{len(y)}", "rank-biserial": eff, "p": p})
        L += table(rows2, ["feature", "degree", "impulsive median", "corrective median", "n imp/cor", "rank-biserial", "p"])
        L += ["", "अर्थ: |rank-biserial| ≥ 0.3 आणि p < 0.01 (अनेक चाचण्या ⇒ कडक) असेल तरच 'वेगळे दिसतात'. `disp_n` व `eff_range` "
              "leg च्या लांबीवर अवलंबून (impulsive legs लांब) ⇒ `disp_per_bar` पहा. Legs एकमेकांत गुंतलेले (degrees, counts) ⇒ स्वतंत्र "
              "नाहीत, p खरे पेक्षा लहान दिसतात. तसं असलं तरी "
              "`gray_resolve_mode = legs` फक्त पुढच्या टप्प्यात, default off; R1–R11 कधीच override नाही."]
    L += ["", "## 6. Golden regression (सगळ्या variants मध्ये)", "",
          "Golden 1m data (`trade-data`) अजून नाही ⇒ चालवता आलं नाही (checker तयार; data आल्यावर)." if GD.golden_csv() is None else
          "Golden data उपलब्ध — `tests/test_elliott_e4.py::test_golden_regression_on_real_data` पहा."]
    L += ["", "## 7. वाचताना", "", "- Model premium ⇒ निष्कर्ष तात्पुरते. - n < 30 cells वर निष्कर्ष नाही. - कुठलाही variant on करायचा निर्णय "
          "तुमचा (G2); सगळे settings default off."]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
