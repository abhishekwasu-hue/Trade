#!/usr/bin/env python3
"""scripts/reader_export_manifest.py — Abhi (Trade sunset, §4): what ATP must receive, with size and checksum, and what does NOT move.

Reads a local checkout of the PRIVATE trade-data repo (and this repo's own data / KB files) and writes docs/reader/EXPORT_MANIFEST.md:
one row per item = path · files · size · sha256 (of the sorted "path<TAB>sha256(file)" lines, so a moved copy can be checked) · moves?
Every top-level trade-data folder and every review/ folder must be classified below, else the run fails (nothing lost by mistake).
Writes nothing into trade-data; prints no data; no network. Re-run right before the move:
    python3 scripts/reader_export_manifest.py --trade-data ../trade-data
"""
import argparse
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs", "reader", "EXPORT_MANIFEST.md")

# (root, path, group, moves, what) — root "data" = trade-data, "repo" = this repo
ITEMS = [
    ("repo", "data/nifty50_1min.parquet", "Candle history", True, "NIFTY spot 1m (the reader's base series; all timeframes are built from it)"),
    ("repo", "data/nifty50_daily_extension.parquet", "Candle history", True, "NIFTY spot daily extension"),
    ("data", "upstox", "Candle history", True, "NIFTY spot 1m, golden window"),
    ("data", "banknifty", "Candle history", True, "BANKNIFTY D / 1H / 15M / W + manifest"),
    ("data", "live_export", "Candle history", True, "Spot + FUT exports from the VPS (NIFTY / BANKNIFTY / SENSEX, all timeframes)"),
    ("data", "major_levels_candles", "Candle history", True, "NIFTY 15m + MCX 30m candles (major-level agreement test)"),
    ("data", "futures", "FUT exports", True, "NIFTY FUT + index 5m (volume source)"),
    ("data", "futures_volume", "FUT exports", True, "NIFTY / BANKNIFTY FUT + index 5m"),
    ("data", "nse_fo_bhavcopy", "FUT exports", True, "NSE F&O bhavcopy, NIFTY options + futures (IS / VAL) and the golden window"),
    ("data", "fixtures", "Golden cases", True, "golden_cases.md (the golden set, private)"),
    ("data", "golden_story", "Golden cases", True, "golden story cases"),
    ("data", "golden_v4", "Golden cases", True, "golden v4 cases"),
    ("data", "reports/r1_lines_bands", "Golden cases", True, "R1 golden lines / bands reference charts"),
    ("data", "review/swings2", "Abhi's approved charts and marks", True, "Abhi's approved swings (SWING CHECK, D1 / D2 stream) — layer 1's reference"),
    ("data", "review/abhi_charts", "Abhi's approved charts and marks", True, "Abhi's own marked charts"),
    ("data", "review/abhi_marked_08sep", "Abhi's approved charts and marks", True, "Abhi's marked decisions (8 Sep)"),
    ("data", "review/oct12_zone", "Abhi's approved charts and marks", True, "12 Oct area case (golden area reference)"),
    ("data", "review/sep29_zone", "Abhi's approved charts and marks", True, "29 Sep area case (golden area reference)"),
    ("data", "review/method_layer1", "Reader layer reports", True, "Layer 1 question pack (Abhi's A / B picks become the definition)"),
    ("data", "review/method_layer2", "Reader layer reports", True, "Layer 2 report charts"),
    ("data", "review/method_layer3", "Reader layer reports", True, "Layer 3 report charts"),
    ("data", "reader2_gallery", "Abhi's approved charts and marks", True, "Gallery seeds (labelled cases)"),
    ("data", "visual_audit", "Vision logs", True, "Vision visual-audit charts + records worth keeping"),
    ("repo", "docs/knowledge/KNOWLEDGE_BASE.md", "KB and Method Pack", True, "The KB (owned here until the switch-over)"),
    ("repo", "docs/knowledge/method_pack.md", "KB and Method Pack", True, "Method Pack (generated from the KB)"),
    ("repo", "docs/knowledge/CHART_READER_METHOD.md", "KB and Method Pack", True, "The governing method spec"),
    ("repo", "docs/knowledge/ABHI_METHOD_NOTES.md", "KB and Method Pack", True, "Abhi's approved method notes"),
    ("data", "research", "Not moving", False, "Research outputs (situation map) — reproducible from code"),
    ("data", "reports/trendline_audit", "Not moving", False, "Trendline / area audit run (research)"),
    ("data", "probes", "Not moving", False, "API probe result"),
    ("data", "wip", "Not moving", False, "Work-in-progress research files"),
    ("data", "chart_reader/no_touch", "Not moving", False, "Debug charts"),
] + [("data", f"review/{d}", "Not moving", False, "Debug / research review run (charts re-renderable from code + candles)")
     for d in ("all7", "banknifty_abc_candidates", "diag_window", "engine3_1m", "golden_story", "k10", "legs", "map", "mtf",
               "patterns", "rsi_divergence", "sept2026", "structure_timeline_22d", "swings", "v22", "vision_test")]

VPS_ONLY = [  # not in any repo: exported from the VPS by Abhi at the switch-over (names of settings only, never values)
    ("Paper trade journal", "PAPER_JOURNAL_DB / the Supabase trade tables (SUPABASE_DB_URL)", "export to trade-data at switch-over"),
    ("Vision logs", "VISION_DB_PATH (signals, verdicts, approvals) + VISION_IMAGE_DIR (charts)", "export the rows / charts worth keeping"),
    ("Engine signal store", "ENGINE_SIGNAL_DB (decision3 setups as sent)", "export with the journal"),
]


def _files(path):
    if os.path.isfile(path):
        return [path]
    out = []
    for d, sub, fs in os.walk(path):
        sub[:] = sorted(x for x in sub if x != ".git")
        out += [os.path.join(d, f) for f in sorted(fs)]
    return out


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def measure(base, rel):
    full = os.path.join(base, rel)
    if not os.path.exists(full):
        return None
    fs = _files(full)
    lines = "".join(f"{os.path.relpath(p, base)}\t{_sha(p)}\n" for p in fs)
    return len(fs), sum(os.path.getsize(p) for p in fs), hashlib.sha256(lines.encode()).hexdigest()


def unclassified(data):
    known = {p for r, p, *_ in ITEMS if r == "data"}
    tops = [d for d in sorted(os.listdir(data)) if os.path.isdir(os.path.join(data, d)) and d != ".git"]
    miss = []
    for d in tops:
        subs = [f"{d}/{s}" for s in sorted(os.listdir(os.path.join(data, d))) if os.path.isdir(os.path.join(data, d, s))]
        if d in known:
            continue
        if not any(k.startswith(d + "/") for k in known):
            miss.append(d)
        else:
            miss += [s for s in subs if s not in known]
    return miss


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:,.0f} {u}" if u == "B" else f"{n:,.1f} {u}"
        n /= 1024


def head(path):
    try:
        return subprocess.check_output(["git", "-C", path, "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:                                                      # noqa: BLE001 — a plain copy (no git) is fine
        return "not a git checkout"


def build(data):
    miss = unclassified(data)
    if miss:
        sys.exit("unclassified trade-data folders (add them to ITEMS): " + ", ".join(miss))
    rows, groups = [], []
    for root, rel, group, moves, what in ITEMS:
        m = measure(HERE if root == "repo" else data, rel)
        if m is None and moves:
            sys.exit(f"moving item not found: {rel} ({root}) — fix ITEMS or the checkout")
        if group not in groups:
            groups.append(group)
        rows.append((group, root, rel, moves, what, m))
    o = ["# Export manifest — what ATP receives (Abhi, Trade sunset §4)", "",
         "Generated by `scripts/reader_export_manifest.py` — do not edit by hand; re-run right before the move.",
         f"trade-data checkout: `{head(data)}` · this repo: `{head(HERE)}`.", "",
         "Checksum = sha256 of the sorted `path<TAB>sha256(file)` lines of the item, so a copied item can be verified.",
         "`trade-data` items stay in the PRIVATE trade-data repo; nothing here copies data into this public repo.", ""]
    for g in groups:
        o += [f"## {g}", "", "| Item | Where | Files | Size | Checksum (sha256) | Moves | What |", "|---|---|---|---|---|---|---|"]
        for group, root, rel, moves, what, m in rows:
            if group != g:
                continue
            where = "trade-data" if root == "data" else "this repo"
            n, size, ck = m if m else (0, 0, "— missing")
            o.append(f"| `{rel}` | {where} | {n} | {human(size)} | `{ck[:16]}…` | {'✅' if moves else '— no'} | {what} |"
                     if m else f"| `{rel}` | {where} | — | — | missing | {'✅' if moves else '— no'} | {what} |")
        o.append("")
    o += ["## On the VPS only (exported by Abhi at the switch-over)", "",
          "Not in any repo. Setting names only (never values); the export runs on the VPS on Abhi's word (SUNSET.md).", "",
          "| Item | Source on the VPS | Step |", "|---|---|---|"]
    o += [f"| {a} | {b} | {c} |" for a, b, c in VPS_ONLY]
    mv = [r for r in rows if r[3] and r[5]]
    nm = [r for r in rows if not r[3] and r[5]]
    o += ["", f"Totals — moving: {len(mv)} items, {sum(r[5][0] for r in mv):,} files, {human(sum(r[5][1] for r in mv))}; "
          f"not moving: {len(nm)} items, {sum(r[5][0] for r in nm):,} files, {human(sum(r[5][1] for r in nm))}.", ""]
    return "\n".join(o)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade-data", default=os.environ.get("TRADE_DATA_DIR", os.path.join(os.path.dirname(HERE), "trade-data")))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if not os.path.isdir(a.trade_data):
        sys.exit(f"trade-data checkout not found: {a.trade_data}")
    text = build(a.trade_data)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"written: {os.path.relpath(a.out, HERE)}")


if __name__ == "__main__":
    main()
