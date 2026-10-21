"""Parity fixtures for a STABLE reader layer (docs/reader/STABLE.md) ⇒ the private trade-data repo, `parity/layer<N>/<tag>/`.

ATP ports each stable layer and must reproduce this repo's output exactly. For the tagged commit this writes, per layer:
  • inputs/   — the bars the engine read: NIFTY (spot 15M, 1m, 5M, near-month FUT 5M, Daily history) and BANKNIFTY (spot 15M, Daily),
                each also MIRRORED (price p ⇒ 2·pivot − p, high ⇔ low, open / close mirrored; volume unchanged);
  • outputs/  — the layer's exact output on every bar of every input (JSON lines, one record per bar or per swing);
  • golden.json — the golden cases (12 Oct, 13 Oct, 29 Sep NIFTY) and what the engine reads there;
  • kb/       — the KB, the Method Pack and the method spec at this commit (ATP copies the same text);
  • MANIFEST.json — tag, commit, KB / Pack version, every file with its sha256.
Never into this public repo: an output root inside this checkout or any worktree of the repo is refused (realpath). No VPS, no broker,
no network. Holdout (checked before anything is written): no 15M / LTF / FUT / 1m bar on a sealed (HOLDOUT) date. The NIFTY Daily
history is the golden tests' own (Abhi Z-1t): sealed-date Daily bars only as LEVEL HISTORY before the 15M window — the role live's
Upstox Daily plays; without them the golden reading cannot be reproduced. Their count per case is in the manifest.
An engine exception on any bar stops the export (never an "error" fixture). Everything is written in a temp folder next to the target
and renamed only when every layer is complete, so a failed run leaves nothing behind.

    python3 scripts/reader_parity_export.py --layer 2=reader-layer2-stable-v1 --layer 3=reader-layer3-stable-v1 --trade-data ../trade-data

(Several layers in one run share one engine build per case.) The NIFTY inputs are the golden tests' own (`tests/test_decision3_flip`
`real_inputs`, trade-data at /home/user/trade-data).
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

LAYERS = {1: "swings / structure", 2: "areas + lifecycle", 3: "visit, zone study, commitment, LTF", 4: "lines + confluence"}
GOLDEN = {"2026-10-12": "bear call at the 1H supply (fast-form handover, 5M CHoCH, commitment volume above the approach-leg average; "
                        "the 09:15 turn at the descending line ⇒ \"confluence: line\")",
          "2026-10-13": "no bear call (no handover)",
          "2026-09-29": "no entry (FUT volume missing)"}
KB_FILES = ("docs/knowledge/KNOWLEDGE_BASE.md", "docs/knowledge/method_pack.md", "docs/knowledge/CHART_READER_METHOD.md")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(x))
    if isinstance(x, (str, int, bool)) or x is None:
        return x
    if hasattr(x, "__dataclass_fields__"):
        return _jsonable({k: getattr(x, k) for k in x.__dataclass_fields__})
    return str(x)


# ------------------------------------------------------------------------------------------------ inputs
def mirror(df, pivot):
    """Price mirror around `pivot`: p ⇒ 2·pivot − p; high ⇔ low; volume unchanged. Every reading rule is symmetric, so the mirrored
    input must read as the mirror image (bull ⇔ bear, demand ⇔ supply)."""
    if df is None:
        return None
    m = df.copy()
    for c in ("open", "close"):
        if c in m:
            m[c] = 2.0 * pivot - df[c]
    if "high" in m and "low" in m:
        m["high"], m["low"] = 2.0 * pivot - df["low"], 2.0 * pivot - df["high"]
    return m


def nifty_inputs(td):
    """The golden window's inputs, exactly the golden tests' (tests/test_decision3_flip.real_inputs; Daily = Abhi Z-1t history), read
    from the same trade-data `td` as BANKNIFTY."""
    from tests import test_decision3_flip as T
    missing = [p for p in T.files(td).values() if not os.path.exists(p)]
    if missing:
        raise SystemExit(f"NIFTY golden inputs missing under {td}: {missing}")
    m15, ltf, fut, m1, daily = T.real_inputs(td)
    return {"m15": m15, "m1": m1, "ltf": ltf, "fut": fut, "daily": daily}


INTRADAY = ("m15", "ltf", "fut", "m1")


def check_holdout(symbol, inp):
    """Abhi holdout (NIFTY only — `history.sealed_fn`): no intraday bar (15M / LTF / FUT / 1m) on a sealed date, and sealed Daily bars
    only as level history BEFORE the 15M window (Z-1t). Refuses otherwise; returns the number of sealed Daily bars (the MANIFEST
    states it)."""
    from decision3 import history as HI
    from elliott import data_policy as DP
    if not HI.is_nifty(symbol):
        return 0
    for k in INTRADAY:
        df = inp.get(k)
        if df is not None and len(df):
            n = int(DP.final_holdout_mask(pd.to_datetime(df["timestamp"])).sum())
            if n:
                raise SystemExit(f"{symbol} {k}: {n} rows on sealed (HOLDOUT) dates — never in a parity fixture")
    daily = inp.get("daily")
    if daily is None or not len(daily):
        return 0
    ts = pd.to_datetime(daily["timestamp"])
    sealed = DP.final_holdout_mask(ts)
    late = int((sealed & (ts >= pd.to_datetime(inp["m15"]["timestamp"]).min()).to_numpy()).sum())
    if late:
        raise SystemExit(f"{symbol} daily: {late} sealed (HOLDOUT) Daily bars at / after the 15M window start — Z-1t allows them only "
                         "as level history before the window")
    return int(sealed.sum())


def banknifty_inputs(td):
    from decision3 import history as HI
    m15 = pd.read_csv(os.path.join(td, "banknifty", "BANKNIFTY_15M.csv.gz"), parse_dates=["timestamp"])
    m15 = m15[["timestamp", "open", "high", "low", "close"]].sort_values("timestamp").reset_index(drop=True)
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    hist, _n = HI.repo_level_history("BANKNIFTY", m15["timestamp"].min(), root=HERE, trade_data=td)
    return {"m15": m15, "m1": None, "ltf": None, "fut": None, "daily": HI.daily_warmup("BANKNIFTY", m15, hist)}


def mirrored(inp):
    piv = float(inp["m15"]["close"].iloc[0])
    out = {k: mirror(v, piv) if k != "fut" else v for k, v in inp.items()}
    if inp["fut"] is not None:                                              # FUT price mirrored too (volume unchanged)
        out["fut"] = mirror(inp["fut"], piv)
    return out


def build(symbol, inp):
    import instruments as INS
    from decision3 import engine as E3
    from decision3 import history as HI
    INS.set_current(symbol)
    kw = {"sealed": HI.sealed_fn(symbol)}
    if inp["ltf"] is not None:
        kw["ltf"] = inp["ltf"]
    if inp["fut"] is not None:
        kw["futures"] = inp["fut"]
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        return E3.V22(inp["m15"], inp["m1"], inp["daily"], **kw)


# ------------------------------------------------------------------------------------------------ per-layer outputs
def out_layer1(V):
    for d, ps in sorted(V.res["pivots"].items()):
        for p in sorted(ps, key=lambda p: (p.bar, p.kind)):
            yield {"degree": int(d), "kind": p.kind, "bar": int(p.bar), "ts": str(p.ts), "price": float(p.price),
                   "confirm_bar": int(p.confirm_bar), "known_at": str(p.known_at), "eq": bool(p.eq), "warmup": bool(p.warmup)}


def _bars(V):
    return range(len(V.m15))


def out_layer2(V):
    for t in _bars(V):
        yield {"bar": t, "ts": str(V.m15["timestamp"].iloc[t]), "levels": V.levels.snapshot(t)}


class EngineError(RuntimeError):
    """The engine raised on a bar: the export stops (no fixture ever records an error as the layer's output)."""


def _at(layer, V, t, fn, *a):
    try:
        return fn(*a)
    except Exception as exc:                                                # noqa: BLE001 — re-raised with the bar named
        raise EngineError(f"layer {layer}: the engine raised on bar {t} ({V.m15['timestamp'].iloc[t]}): "
                          f"{type(exc).__name__}: {exc}") from exc


def out_layer3(V):
    for t in _bars(V):
        yield {"bar": t, "ts": str(V.m15["timestamp"].iloc[t]), "decide": _at(3, V, t, V.decide, t)}


def out_layer4(V):
    from decision3 import trendline as TL
    for t in _bars(V):
        rec = {"bar": t, "ts": str(V.m15["timestamp"].iloc[t])}
        for name, d in (("down", TL.DOWN), ("up", TL.UP)):
            ln = _at(4, V, t, TL.swing_line, V, t, d)
            rt = _at(4, V, t, TL.reaction_touch, V, t, d, ln) if ln is not None else None
            trend = "DOWN" if d == TL.DOWN else "UP"
            _, _, act = _at(4, V, t, V.step2, t, trend)
            lab = [{"id": x["id"], "lo": x["lo"], "hi": x["hi"], "confluence_label": x.get("confluence_label"),
                    "line_touch": x.get("line_touch")} for x in act if x.get("confluence_line")]
            rec[name] = {"line": ln, "reaction_touch": rt, "confluence": lab}
        yield rec


OUTPUTS = {1: out_layer1, 2: out_layer2, 3: out_layer3, 4: out_layer4}


def golden(V):
    out = {}
    ts = pd.to_datetime(V.m15["timestamp"])
    for day, what in GOLDEN.items():
        ix = [int(i) for i in np.flatnonzero((ts.dt.normalize() == pd.Timestamp(day)).to_numpy())]
        rows = []
        for t in ix:
            r = _at("golden", V, t, V.decide, t)
            rows.append({"bar": t, "ts": str(ts.iloc[t]), "decision": r.get("decision"), "why": r.get("why"),
                         "conviction": r.get("conviction")})
        out[day] = {"expected (Abhi)": what, "bars": rows}
    return out


# ------------------------------------------------------------------------------------------------ write
def write_frame(df, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, compression="gzip")


def write_jsonl(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    import gzip
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(_jsonable(r), ensure_ascii=False, sort_keys=True) + "\n")


def git(*a):
    return subprocess.check_output(["git", "-C", HERE, *a], text=True).strip()


def _real(p):
    return os.path.realpath(os.path.abspath(p))


def _under(p, root):
    p, root = _real(p), _real(root)
    return os.path.commonpath([p, root]) == root


def repo_roots():
    """This checkout, its top level and every worktree of this repo (incl. the main checkout): no fixture is ever written inside."""
    roots = {HERE, git("rev-parse", "--show-toplevel")}
    roots |= {ln.split(" ", 1)[1] for ln in git("worktree", "list", "--porcelain").splitlines() if ln.startswith("worktree ")}
    return sorted(_real(r) for r in roots if r)


def main_checkout():
    """The repo's main checkout (first `git worktree list` entry) — the default trade-data sits next to it, never inside."""
    for ln in git("worktree", "list", "--porcelain").splitlines():
        if ln.startswith("worktree "):
            return ln.split(" ", 1)[1]
    return HERE


def guard_out_root(out_root):
    """The fixtures are private (STABLE.md): refuse an output root inside this public repo or any of its worktrees."""
    for r in repo_roots():
        if _under(out_root, r):
            raise SystemExit(f"{_real(out_root)} is inside this public repo ({r}) — parity fixtures go to the private trade-data only")
    return _real(out_root)


def pack_version():
    out = subprocess.check_output([sys.executable, os.path.join(HERE, "scripts", "build_method_pack.py"), "--check"], text=True, cwd=HERE)
    return out.split("Method Pack version ")[1].split()[0] if "Method Pack version " in out else None


def export(layers, td, out_root=None, log=print):
    """layers = {layer: tag}. One engine build per case; each layer gets its own folder parity/layer<N>/<tag>/."""
    bad = [n for n in layers if n not in LAYERS]
    if bad:
        raise SystemExit(f"layer(s) {bad}: only {sorted(LAYERS)}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("the working tree has changes — export only from the clean tagged commit")
    commit = git("rev-parse", "HEAD")
    tagged = git("tag", "--points-at", "HEAD").split()
    parity = guard_out_root(out_root or os.path.join(td, "parity"))
    finals = {}
    for n, tag in layers.items():
        if tag not in tagged:
            raise SystemExit(f"{tag} does not point at HEAD ({commit[:7]}) — check out the tag first")
        finals[n] = os.path.join(parity, f"layer{n}", tag)
        if os.path.exists(finals[n]) and os.listdir(finals[n]):
            raise SystemExit(f"{finals[n]} exists — a stable tag's fixtures are never overwritten (a fix = a new tag)")
    roots = {}                                                              # written in a temp folder, renamed only when all is done
    try:
        for n, final in finals.items():
            os.makedirs(os.path.dirname(final), exist_ok=True)
            roots[n] = tempfile.mkdtemp(prefix=f".{os.path.basename(final)}.partial-", dir=os.path.dirname(final))
        cases, held = _write_all(roots, td, log)
        pv = pack_version()
        for n, root in roots.items():
            _finish(n, layers[n], root, commit, pv, cases, held, log)
        for n, root in roots.items():
            if os.path.isdir(finals[n]):
                os.rmdir(finals[n])                                         # an empty leftover only (checked above)
            os.rename(root, finals[n])
            log(f"written: {finals[n]}")
    finally:
        for root in roots.values():
            if os.path.isdir(root):
                shutil.rmtree(root)
    return finals


def _write_all(roots, td, log):
    cases, held = [], {}
    for symbol, fn in (("NIFTY", nifty_inputs), ("BANKNIFTY", banknifty_inputs)):
        base = fn(td)
        for kind, inp in (("real", base), ("mirror", mirrored(base))):
            name = f"{symbol}_{kind}"
            held[name] = check_holdout(symbol, inp)                         # mirror: same timestamps ⇒ the same count, checked again
            log(f"{name}: building V22 on {len(inp['m15'])} bars")
            V = build(symbol, inp)
            for n, root in roots.items():
                for k, df in inp.items():
                    if df is not None:
                        write_frame(df, os.path.join(root, "inputs", name, f"{k}.csv.gz"))
                log(f"  layer {n} output")
                write_jsonl(OUTPUTS[n](V), os.path.join(root, "outputs", f"{name}.jsonl.gz"))
                if symbol == "NIFTY" and kind == "real":
                    with open(os.path.join(root, "golden.json"), "w", encoding="utf-8") as f:
                        json.dump(_jsonable(golden(V)), f, ensure_ascii=False, indent=1, sort_keys=True)
            cases.append(name)
    return cases, held


def _finish(n, tag, root, commit, pv, cases, held, log):
    for p in KB_FILES:
        dst = os.path.join(root, "kb", os.path.basename(p))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(os.path.join(HERE, p), "rb") as a, open(dst, "wb") as b:
            b.write(a.read())
    files = sorted(os.path.relpath(os.path.join(dp, f), root) for dp, _, fs in os.walk(root) for f in fs)
    manifest = {"layer": n, "covers": LAYERS[n], "tag": tag, "commit": commit, "method_pack_version": pv,
                "cases": cases, "mirror": "price p ⇒ 2·(first 15M close) − p, high ⇔ low; volume unchanged",
                "holdout": "checked before writing: no 15M / LTF / FUT / 1m bar on a sealed date; the NIFTY Daily history carries "
                           "sealed-date Daily bars only as level history before the 15M window (Abhi Z-1t, as live's Upstox Daily): "
                           + ", ".join(f"{c} {held[c]} bars" for c in cases),
                "holdout_daily_bars": {c: held[c] for c in cases},
                "files": {f: _sha(os.path.join(root, f)) for f in files}}
    with open(os.path.join(root, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
    log(f"layer {n}: {len(files) + 1} files")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", action="append", required=True, help="N=tag (repeatable)")
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA_DIR") or os.path.join(os.path.dirname(main_checkout()), "trade-data"),
                    help="the private trade-data repo (default: next to the main checkout; never inside this repo)")
    ap.add_argument("--out", default=None, help="parity root (default <trade-data>/parity)")
    a = ap.parse_args(argv)
    export({int(x.split("=", 1)[0]): x.split("=", 1)[1] for x in a.layer}, a.trade_data, a.out)


if __name__ == "__main__":
    main()
