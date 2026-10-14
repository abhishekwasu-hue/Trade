#!/usr/bin/env python3
"""Abhi Z-1o: decision3 V22 **with** vs **without** the 1m order data (swings2 intrabar high / low order), same days, same inputs.
Read-only: local private files only (no API call, no store, no Telegram); writes only --out-dir. No dates in code (days + files = CLI).

Per symbol and day it reports:
  levels_diff.csv     levels / bands that differ (added = only with 1m, removed = only without, changed = same level, other band / role /
                      state), matched by (anchor, born bar) — level ids are sequence numbers and differ between runs;
  pivots_diff.csv     swings2 pivots present in one run only (or with another price / known_at);
  rsi_pairs.csv       rsi2 Divergence latest pair per degree / side at every bar of the day (as V22 reads it), both runs;
  verdicts.csv        decide() per bar, both runs, with `differs`;
  summary.md          short text.

    python3 scripts/engine3_1m_compare.py --out-dir <trade-data>/review/engine3_1m/run1 \
        --symbol NIFTY --m1 <upstox 1m csv.gz> <export>/NIFTY_1minute.parquet --index5 <export>/oe_index_5min_NIFTY.parquet \
        --fut <export>/oe_futures_5min_NIFTY.parquet --day <D1> --day <D2> \
        [--symbol BANKNIFTY --m15 <15M csv> --daily <D csv> --ltf <5m file> …]   (one --symbol block per symbol)

Inputs (as tests/test_decision3_flip.real_inputs and replay_day): 15M = 1m-built bars (market_state.core.frame) where 1m exists, earlier
days from --m15 files, later days from complete 09:15-anchored 15M bins of --index5. LTF 5M = 1m-built + --ltf + --index5. FUT = --fut.
Daily = --daily (+ 15M-derived days after it), else V22's default (from the 15M). Holdout rows never loaded (data_policy "annotation").
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BAR15 = pd.Timedelta(minutes=15)


def read(path):
    from elliott import data_policy as DP
    df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
    ts = pd.to_datetime(df["timestamp"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return DP.filter_allowed(df.assign(timestamp=ts), "annotation")


def cat(paths, cols=("timestamp", "open", "high", "low", "close")):
    fr = [read(p)[list(cols)] for p in paths or []]
    if not fr:
        return None
    return pd.concat(fr, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)


def bins15(df5):
    """Complete 09:15-anchored 15M bins (3 × 5M) only — an unfinished bin is dropped, never filled."""
    d = df5.copy()
    day = d["timestamp"].dt.normalize()
    k = ((d["timestamp"] - day - pd.Timedelta(hours=9, minutes=15)) // BAR15).astype(int)
    d["k"] = day + pd.Timedelta(hours=9, minutes=15) + k * BAR15
    g = d.groupby("k").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), n=("close", "size"))
    return g[g["n"] == 3].reset_index().rename(columns={"k": "timestamp"})[["timestamp", "open", "high", "low", "close"]]


def inputs(a, last_day):
    """(m15, m1, ltf, fut, daily) up to `last_day` close."""
    import market_state.core as MC
    ohlc = ["timestamp", "open", "high", "low", "close"]
    m1 = cat(a.m1)
    m1 = m1[m1["timestamp"].dt.normalize() <= last_day][ohlc].reset_index(drop=True)
    end = m1["timestamp"].max().normalize() + pd.Timedelta(hours=15, minutes=30)
    first1, last1 = m1["timestamp"].min().normalize(), m1["timestamp"].max().normalize()
    parts = [MC.frame(m1, "15m", end)[ohlc]]
    old = cat(a.m15)
    if old is not None:
        parts.append(old[old["timestamp"].dt.normalize() < first1][ohlc])
    i5 = cat(a.index5)
    if i5 is not None:
        i5 = i5[(i5["timestamp"].dt.normalize() > last1) & (i5["timestamp"].dt.normalize() <= last_day)][ohlc]
        parts.append(bins15(i5))
    m15 = pd.concat(parts, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    m15["bar_end"] = m15["timestamp"] + BAR15
    lparts = [MC.frame(m1, "5m", end)[ohlc]]
    lt = cat(a.ltf)
    if lt is not None:
        lparts.append(lt[lt["timestamp"].dt.normalize() < first1][ohlc])
    if i5 is not None:
        lparts.append(i5)
    ltf = pd.concat(lparts, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    ltf["bar_end"] = ltf["timestamp"] + pd.Timedelta(minutes=5)
    fut = None
    if a.fut:
        fr = [read(p) for p in a.fut]
        fut = pd.concat(fr, ignore_index=True)
        fut = fut[fut["timestamp"].dt.normalize() <= last_day]
        fut = fut.drop_duplicates(["timestamp"] + (["contract"] if "contract" in fut.columns else []), keep="first")
        fut = fut.sort_values("timestamp").reset_index(drop=True)
    daily = None
    if a.daily:
        dd = cat(a.daily)
        d15 = m15.assign(_d=m15["timestamp"].dt.normalize()).groupby("_d").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index().rename(
            columns={"_d": "timestamp"})
        daily = pd.concat([dd, d15[d15["timestamp"] > dd["timestamp"].max()]], ignore_index=True)
        daily = daily[daily["timestamp"] <= last_day].reset_index(drop=True)
        daily["bar_end"] = daily["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    return m15, m1, ltf, fut, daily


def build(sym, m15, m1, ltf, fut, daily):
    import instruments as INS
    from decision3 import engine as E3
    from decision3 import history as HI
    INS.set_current(sym)
    kw = {"sealed": HI.sealed_fn(sym), "ltf": ltf, "futures": fut}
    return E3.V22(m15, None, daily, **kw), E3.V22(m15, m1, daily, **kw)


# ------------------------------------------------------------------------------------------------ diffs
def keyed(snap):
    """level ⇒ key = anchor (the same level can be born a bar earlier / later when its pivot's known_at moves); two live levels
    with one anchor ⇒ anchor + born bar."""
    n = {}
    for x in snap:
        a = round(float(x["anchor"]), 2)
        n[a] = n.get(a, 0) + 1
    out = {}
    for x in snap:
        a = round(float(x["anchor"]), 2)
        out[(a,) if n[a] == 1 else (a, int(x["born_bar"]))] = x
    return out


LFIELDS = ("role", "lo", "hi", "state", "born_bar", "births")


def ldesc(x, V=None):
    born = f" born {str(V.m15['timestamp'].iloc[int(x['born_bar'])])[5:16]}" if V is not None else ""
    return f"{x['role']} {x['lo']:.2f}-{x['hi']:.2f} {x.get('state') or ''} births {'+'.join(map(str, x['births']))}{born}".strip()


def level_diffs(sym, day, ix, V0, V1):
    """per bar diffs ⇒ grouped (same diff on consecutive bars ⇒ one row with first / last bar)."""
    rows = {}
    for t in ix:
        a = keyed(V0.levels.snapshot(t))
        b = keyed(V1.levels.snapshot(t))
        ts = str(V0.m15["timestamp"].iloc[t])
        for k in set(a) | set(b):
            x, y = a.get(k), b.get(k)
            if x is None:
                kind, w0, w1 = "added (only with 1m)", "", ldesc(y, V1)
            elif y is None:
                kind, w0, w1 = "removed (only without 1m)", ldesc(x, V0), ""
            elif any(x.get(f) != y.get(f) for f in LFIELDS):
                ch = dict.fromkeys("band" if f in ("lo", "hi") else ("born" if f == "born_bar" else f) for f in LFIELDS
                                   if x.get(f) != y.get(f))
                kind, w0, w1 = "changed (" + ", ".join(ch) + ")", ldesc(x, V0), ldesc(y, V1)
            else:
                continue
            g = rows.setdefault((kind, k, w0, w1), {"symbol": sym, "day": str(day.date()), "kind": kind, "anchor": k[0],
                                                   "without_1m": w0, "with_1m": w1, "first_bar": ts, "last_bar": ts, "n_bars": 0})
            g["last_bar"], g["n_bars"] = ts, g["n_bars"] + 1
    return list(rows.values())


def pivot_set(V):
    out = {}
    for d, ps in V.res["pivots"].items():
        for p in ps:
            out[(int(d), p.kind, str(pd.Timestamp(p.ts)))] = (round(float(p.price), 2), str(pd.Timestamp(p.known_at)))
    return out


def pivot_diffs(sym, V0, V1):
    a, b = pivot_set(V0), pivot_set(V1)
    rows = []
    for k in sorted(set(a) | set(b), key=lambda k: (k[2], k[0], k[1])):
        x, y = a.get(k), b.get(k)
        if x == y:
            continue
        kind = "only with 1m" if x is None else ("only without 1m" if y is None else "changed")
        rows.append({"symbol": sym, "degree": f"D{k[0]}", "kind_hl": k[1], "ts": k[2], "diff": kind,
                     "price_without": x[0] if x else "", "known_without": x[1] if x else "",
                     "price_with": y[0] if y else "", "known_with": y[1] if y else ""})
    return rows


def rsi_rows(sym, day, ix, V, run):
    from rsi2 import engine as RE
    D = RE.Divergence(V.m15[["timestamp", "open", "high", "low", "close"]], "15M", res=V.res, areas=False)
    out = []
    for t in ix:
        r = D.read(t)
        for y in r["latest"]:
            x = y.get("pair") or {}
            out.append({"symbol": sym, "day": str(day.date()), "bar": str(V.m15["timestamp"].iloc[t]), "run": run,
                        "degree": f"D{y['degree']}", "side": y["side"], "status": x.get("status", ""), "is_div": bool(x.get("is_div")),
                        "type": x.get("type", ""), "L1": (x.get("L1") or {}).get("time", ""), "L1_price": (x.get("L1") or {}).get("price", ""),
                        "L1_rsi": (x.get("L1") or {}).get("rsi", ""), "L2": (x.get("L2") or {}).get("time", ""),
                        "L2_price": (x.get("L2") or {}).get("price", ""), "L2_rsi": (x.get("L2") or {}).get("rsi", ""),
                        "bars": x.get("bars", ""), "statement": y["statement"]})
    return out


def vshort(r):
    lv = r.get("level") or {}
    side = ("bull put" if lv.get("role") == "support" else "bear call") if lv else ""
    lvl = f"{lv.get('role', '')} {lv['lo']:.2f}-{lv['hi']:.2f}" if lv else ""
    c = r.get("checklist") or {}
    why = r.get("why") or next((f"{k} {c[k][1]}" for k in ("①", "②", "③", "⑥", "⑦") if k in c and c[k][0] is False), "")
    zr = ((r.get("zone_read") or {}).get("summary") or {})
    rsi = zr.get("rsi_divergence") if isinstance(zr, dict) else None
    rsi = None if rsi is None else (rsi.get("divergences") or rsi.get("na") or "none") if isinstance(rsi, dict) else rsi
    return {"decision": r.get("decision"), "side": side if r.get("decision") == "setup" else "", "conviction": r.get("conviction") or "",
            "level": lvl, "why": str(why)[:160], "rsi_in_zone": "" if rsi is None else str(rsi)[:120]}


def verdict_rows(sym, day, ix, V0, V1):
    out = []
    for t in ix:
        a, b = vshort(V0.decide(t)), vshort(V1.decide(t))
        row = {"symbol": sym, "day": str(day.date()), "bar": str(V0.m15["timestamp"].iloc[t])[11:16]}
        row.update({f"{k}_without": v for k, v in a.items()})
        row.update({f"{k}_with": v for k, v in b.items()})
        diff = [k for k in ("decision", "side", "conviction", "level", "rsi_in_zone", "why") if a[k] != b[k]]
        row["differs"], row["what_differs"] = bool(diff), " ".join(diff)
        out.append(row)
    return out


# ------------------------------------------------------------------------------------------------ main
def parse(argv):
    """`--symbol X` starts a block; the following options belong to it."""
    blocks, cur, top, i = [], None, [], 0
    common = argparse.ArgumentParser()
    common.add_argument("--out-dir", required=True)
    it = list(argv)
    while i < len(it):
        if it[i] == "--symbol":
            cur = [it[i], it[i + 1]]
            blocks.append(cur)
            i += 2
            continue
        (cur if cur is not None else top).append(it[i])
        i += 1
    a = common.parse_args(top)
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    for k in ("--m1", "--m15", "--index5", "--ltf", "--fut", "--daily"):
        ap.add_argument(k, nargs="*", default=[])
    ap.add_argument("--day", action="append", required=True)
    return a, [ap.parse_args(b) for b in blocks]


def write_csv(rows, path):
    pd.DataFrame(rows).to_csv(path, index=False)


def main(argv=None):
    a, blocks = parse(sys.argv[1:] if argv is None else argv)
    os.makedirs(a.out_dir, exist_ok=True)
    L, P, R, Vr, summ = [], [], [], [], []
    for b in blocks:
        sym = b.symbol.upper()
        days = sorted(pd.Timestamp(d).normalize() for d in b.day)
        m15, m1, ltf, fut, daily = inputs(b, days[-1])
        V0, V1 = build(sym, m15, m1, ltf, fut, daily)
        last1 = m1["timestamp"].max()
        pv = pivot_diffs(sym, V0, V1)
        P += pv
        summ.append(f"## {sym}\n\n15M {len(m15)} bars {m15['timestamp'].min():%d %b} – {m15['timestamp'].max():%d %b %H:%M}; 1m "
                    f"{len(m1)} rows {m1['timestamp'].min():%d %b} – {last1:%d %b %H:%M} (later bars: 5M-built, no 1m in either run); "
                    f"FUT {'yes' if fut is not None else 'no'}; Daily {'file + 15M' if daily is not None else 'from the 15M (V22 default)'}.\n\n"
                    f"swings2 pivots differing over the whole window: {len(pv)} "
                    f"({sum(r['diff'] == 'only with 1m' for r in pv)} only with 1m, {sum(r['diff'] == 'only without 1m' for r in pv)} only "
                    f"without, {sum(r['diff'] == 'changed' for r in pv)} changed).\n")
        for day in days:
            ix = [i for i in range(len(V0.m15)) if pd.Timestamp(V0.m15["timestamp"].iloc[i]).normalize() == day]
            if not ix:
                summ.append(f"### {day:%d %b}: no bars in the data\n")
                continue
            lv = level_diffs(sym, day, ix, V0, V1)
            L += lv
            rr = rsi_rows(sym, day, ix, V0, "without_1m") + rsi_rows(sym, day, ix, V1, "with_1m")
            R += rr
            vr = verdict_rows(sym, day, ix, V0, V1)
            Vr += vr
            hasm1 = bool((m1["timestamp"].dt.normalize() == day).any())
            near = [r for r in pv if pd.Timestamp(r["known_with"] or r["known_without"]).normalize() == day]
            summ.append(f"### {sym} {day:%d %b} ({len(ix)} bars; 1m that day: {'yes' if hasm1 else 'no — 5M-built bars'})\n")
            kinds = ", ".join(f"{k} {sum(x['kind'] == k for x in lv)}" for k in sorted({x["kind"] for x in lv})) or "none"
            summ.append(f"- Levels: {len(lv)} differing level rows ({kinds}).")
            for x in lv[:12]:
                summ.append(f"  - {x['kind']}: anchor {x['anchor']} · without: {x['without_1m'] or '—'} · "
                            f"with: {x['with_1m'] or '—'} ({x['first_bar'][11:16]}–{x['last_bar'][11:16]})")
            summ.append(f"- Pivots known that day differing: {len(near)}" + "".join(
                f"\n  - {r['degree']} {r['kind_hl']} {r['ts'][5:16]} {r['diff']} (price {r['price_with'] or r['price_without']})"
                for r in near[:8]))
            divs = {}
            for r in rr:
                if r["is_div"]:
                    divs.setdefault(r["run"], set()).add(f"{r['degree']} {r['side']} {r['type']} {r['L1'][5:16]} ({r['L1_price']}, RSI "
                                                         f"{r['L1_rsi']}) → {r['L2'][5:16]} ({r['L2_price']}, RSI {r['L2_rsi']}), "
                                                         f"{r['bars']} bars")
            for run in ("without_1m", "with_1m"):
                summ.append(f"- RSI divergences {run.replace('_', ' ')}: " + ("; ".join(sorted(divs.get(run, ()))) or "none"))
            dv = [r for r in vr if r["differs"]]
            by = {k: sum(k in r["what_differs"].split() for r in vr) for k in ("decision", "side", "conviction", "level", "rsi_in_zone", "why")}
            dec0 = pd.Series([r["decision_without"] for r in vr]).value_counts().to_dict()
            dec1 = pd.Series([r["decision_with"] for r in vr]).value_counts().to_dict()
            summ.append(f"- decide() verdicts differing: {len(dv)} of {len(vr)} bars — by field: "
                        + ", ".join(f"{k} {n}" for k, n in by.items()) + f"; decisions without 1m {dec0}, with 1m {dec1}")
            for r in [r for r in dv if set(r["what_differs"].split()) - {"why", "level"}][:12]:
                summ.append(f"  - {r['bar']}: without {r['decision_without']} {r['side_without']} {r['conviction_without']} "
                            f"[{r['level_without']}] · with {r['decision_with']} {r['side_with']} {r['conviction_with']} [{r['level_with']}]"
                            f" ({r['what_differs']}) — {r['why_with'][:90]}")
            summ.append("")
    write_csv(L, os.path.join(a.out_dir, "levels_diff.csv"))
    write_csv(P, os.path.join(a.out_dir, "pivots_diff.csv"))
    write_csv(R, os.path.join(a.out_dir, "rsi_pairs.csv"))
    write_csv(Vr, os.path.join(a.out_dir, "verdicts.csv"))
    head = ("# decision3 V22: with vs without 1m order data (Abhi Z-1o = (a))\n\nSame 15M / LTF / FUT / Daily inputs; only `df1m` differs "
            "(swings2 intrabar high / low order ⇒ pivots ⇒ levels and rsi2 Divergence pairs). Engine settings = defaults. Read-only run "
            "(scripts/engine3_1m_compare.py). CSVs: levels_diff, pivots_diff, rsi_pairs, verdicts (`conviction` = the grade V22 reports even "
            "on a wait bar). Local FUT files start late ⇒ the 15M slot volume baseline can be NA (data-problem wait) in BOTH runs; the live "
            "feed has `engine3_fut_days` of FUT.\n")
    open(os.path.join(a.out_dir, "summary.md"), "w", encoding="utf-8").write(head + "\n" + "\n".join(summ) + "\n")
    print("\n".join(summ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
