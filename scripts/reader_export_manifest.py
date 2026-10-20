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
    ("repo", "data/nifty50_1min.parquet", "Candle history", True,
     "NIFTY spot 1m up to 2024-03-27; later bars are in Supabase `nifty_1min_ohlc` (see the external section)"),
    ("repo", "data/nifty50_daily_extension.parquet", "Candle history", True, "NIFTY spot daily extension"),
    ("data", "upstox", "Candle history", True, "NIFTY spot 1m, golden window"),
    ("data", "banknifty", "Candle history", True, "BANKNIFTY D / 1H / 15M / W + manifest"),
    ("data", "live_export", "Candle history", True, "Spot + FUT exports from the VPS (NIFTY / BANKNIFTY / SENSEX, all timeframes)"),
    ("data", "major_levels_candles", "Candle history", True, "NIFTY 15m + MCX 30m candles (major-level agreement test)"),
    ("data", "futures", "FUT exports", True, "NIFTY FUT + index 5m snapshot (the full history is on the VPS — external section)"),
    ("data", "futures_volume", "FUT exports", True, "NIFTY / BANKNIFTY FUT + index 5m snapshot"),
    ("data", "nse_fo_bhavcopy", "FUT exports", True, "NSE F&O bhavcopy, NIFTY options + futures (IS / VAL) and the golden window"),
    ("data", "fixtures", "Golden cases", True, "golden_cases.md (the golden set, private)"),
    ("data", "golden_story", "Golden cases", True, "golden story cases"),
    ("data", "golden_v4", "Golden cases", True, "golden v4 cases"),
    ("data", "reports/r1_lines_bands", "Golden cases", True, "R1 golden lines / bands reference charts"),
    ("repo", "tests/golden_chart_cases", "Golden cases", True, "Charts Abhi read, turned into expectations"),
    ("repo", "tests/fixtures/golden_vision_v4_cases.json", "Golden cases", True, "Vision v4 golden cases"),
    ("repo", "docs/reports/elliott_golden_expectations.json", "Golden cases", True, "Elliott golden expectations"),
    ("data", "review/swings2", "Abhi's approved charts and marks", True, "Abhi's approved swings (SWING CHECK, D1 / D2 stream) — layer 1's reference"),
    ("data", "review/abhi_charts", "Abhi's approved charts and marks", True, "Abhi's own marked charts"),
    ("data", "review/abhi_marked_08sep", "Abhi's approved charts and marks", True, "Abhi's marked decisions (8 Sep)"),
    ("data", "review/oct12_zone", "Abhi's approved charts and marks", True, "12 Oct area case (golden area reference)"),
    ("data", "review/sep29_zone", "Abhi's approved charts and marks", True, "29 Sep area case (golden area reference)"),
    ("repo", "docs/reports/ground_truth_levels.csv", "Abhi's approved charts and marks", True, "Abhi's hand-drawn levels (ground truth)"),
    ("repo", "gallery2/data", "Abhi's approved charts and marks", True, "Gallery cases Abhi labelled (abhi_cases.json + manifest)"),
    ("data", "reader2_gallery", "Abhi's approved charts and marks", True, "Gallery seeds (the labels are on the VPS — external section)"),
] + [("data", f"review/{d}", "Abhi's approved charts and marks", True,
      "Review run Abhi gave ✔ / ✘ on — kept exactly as he saw it (a re-render with later code would differ)")
     for d in ("swings", "legs", "patterns", "k10", "v22")] + [
    ("data", "review/method_layer1", "Reader layer reports", True, "Layer 1 question pack (Abhi's A / B picks become the definition)"),
    ("data", "review/method_layer2", "Reader layer reports", True, "Layer 2 report charts"),
    ("data", "review/method_layer3", "Reader layer reports", True, "Layer 3 report charts"),
    ("data", "review/method_layer4", "Reader layer reports", True, "Layer 4 question (12 Oct line vs area)"),
    ("data", "visual_audit", "Vision logs", True, "Vision visual-audit charts + records (pushed by scripts/vision_archive.py)"),
    ("data", "review/vision_test", "Vision logs", True, "Vision test runs (input / marked charts)"),
    ("repo", "docs/knowledge/KNOWLEDGE_BASE.md", "KB and Method Pack", True, "The KB (owned here until the switch-over)"),
    ("repo", "docs/knowledge/method_pack.md", "KB and Method Pack", True, "Method Pack (generated from the KB)"),
    ("repo", "docs/knowledge/CHART_READER_METHOD.md", "KB and Method Pack", True, "The governing method spec"),
    ("repo", "docs/knowledge/ABHI_METHOD_NOTES.md", "KB and Method Pack", True, "Abhi's approved method notes"),
    ("data", "README.md", "KB and Method Pack", True, "trade-data README (data-use rules)"),
    ("data", "research", "Not moving", False, "Research outputs (situation map) — reproducible from code"),
    ("data", "reports/trendline_audit", "Not moving", False, "Trendline / area audit run (research)"),
    ("data", "probes", "Not moving", False, "API probe result"),
    ("data", "wip", "Not moving", False, "Work-in-progress research files"),
    ("data", "chart_reader/no_touch", "Not moving", False, "Debug charts"),
] + [("data", f"review/{d}", "Not moving", False, "Debug / research run (charts re-renderable from code + candles)")
     for d in ("all7", "banknifty_abc_candidates", "diag_window", "engine3_1m", "golden_story", "map", "mtf", "rsi_divergence",
               "sept2026", "structure_timeline_22d")]

# Not in any repo today. Abhi exports each into trade-data at the named folder (on his word); a re-run then sums them like the rest.
# (what, source — setting / table names only, never values, destination folder in trade-data)
EXTERNAL = [
    ("NIFTY spot 1m from 2024-03-28 (the live history)", "Supabase table `nifty_1min_ohlc` (filled by the `nifty_1min_daily_update` workflow)",
     "vps_export/supabase/nifty_1min_ohlc"),
    ("Other candle history", "Supabase table `historical_candles`", "vps_export/supabase/historical_candles"),
    ("FUT + index 5m history (the reader's volume source)", "VPS `data/oe_futures_5min_*.parquet`, `data/oe_index_5min_*.parquet` (git-ignored)",
     "vps_export/futures_history"),
    ("Abhi's ✔ / ✘ verdicts (swing / leg / pattern / v22 / annotation checks)", "Supabase table `backtest_review`", "vps_export/supabase/backtest_review"),
    ("Abhi's gallery labels", "Supabase table `reader2_gallery`", "vps_export/supabase/reader2_gallery"),
    ("Review packs written on the VPS clone of trade-data", "VPS `/root/trade-data/backtest_review`, `golden_gallery`, `reader2_gallery/labels`",
     "backtest_review, golden_gallery, reader2_gallery/labels (push the VPS clone)"),
    ("Paper trade journal", "`PAPER_JOURNAL_DB` + the Supabase trade tables (`SUPABASE_DB_URL`)", "vps_export/paper_journal"),
    ("Vision logs", "`VISION_DB_PATH` (signals, verdicts, approvals) + `VISION_IMAGE_DIR` (charts)", "vps_export/vision"),
    ("Engine signal store", "`ENGINE_SIGNAL_DB` (decision3 setups as sent)", "vps_export/engine_signal"),
    ("VPS state files", "`data/one_bot_before.json` (one-bot revert state), `data/review_tg_sent.json`", "vps_export/state"),
]
OPTIONAL = ("vps_export", "backtest_review", "golden_gallery")             # exist only after Abhi's export ⇒ summed when present


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
    lines = "".join(sorted(f"{os.path.relpath(p, base)}\t{_sha(p)}\n" for p in fs))   # documented: sorted, paths from the root
    return len(fs), sum(os.path.getsize(p) for p in fs), hashlib.sha256(lines.encode()).hexdigest()


def unclassified(data):
    """Every top-level entry (folder or loose file) and, under a partly classified folder, every entry must be classified."""
    known = {p for r, p, *_ in ITEMS if r == "data"}
    miss = []

    def walk(rel):
        full = os.path.join(data, rel) if rel else data
        for e in sorted(os.listdir(full)):
            r = f"{rel}/{e}" if rel else e
            if e == ".git" or r in known or r.split("/")[0] in OPTIONAL:
                continue
            if os.path.isdir(os.path.join(data, r)) and any(k.startswith(r + "/") for k in known):
                walk(r)
            else:
                miss.append(r)
    walk("")
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
    extra = [("data", d, "Exported from the VPS / Supabase", True, "present — summed")
             for d in OPTIONAL if os.path.isdir(os.path.join(data, d))]
    for root, rel, group, moves, what in ITEMS + extra:
        m = measure(HERE if root == "repo" else data, rel)
        if m is None and moves:
            sys.exit(f"moving item not found: {rel} ({root}) — fix ITEMS or the checkout")
        if group not in groups:
            groups.append(group)
        rows.append((group, root, rel, moves, what, m))
    o = ["# Export manifest — what ATP receives (Abhi, Trade sunset §4)", "",
         "Generated by `scripts/reader_export_manifest.py` — do not edit by hand; re-run right before the move.",
         f"trade-data checkout: `{head(data)}` · this repo: `{head(HERE)}`.", "",
         "Checksum = sha256 of the item's lines `path<TAB>sha256(file)\\n`, sorted, with each path relative to the root it lives in "
         "(the trade-data root, or this repo's root), so a copied item can be verified.",
         "`trade-data` items stay in the PRIVATE trade-data repo; nothing here copies data into this public repo.", ""]
    for g in groups:
        o += [f"## {g}", "", "| Item | Where | Files | Size | Checksum (sha256) | Moves | What |", "|---|---|---|---|---|---|---|"]
        for group, root, rel, moves, what, m in rows:
            if group != g:
                continue
            where = "trade-data" if root == "data" else "this repo"
            n, size, ck = m if m else (0, 0, "— missing")
            o.append(f"| `{rel}` | {where} | {n} | {human(size)} | `{ck}` | {'✅' if moves else '— no'} | {what} |"
                     if m else f"| `{rel}` | {where} | — | — | missing | {'✅' if moves else '— no'} | {what} |")
        o.append("")
    o += ["## Not in any repo yet — exported by Abhi into trade-data (on his word)", "",
          "Setting / table names only, never values. Once a destination folder exists, a re-run of this script sums it with the rest.", "",
          "| Item | Source | Destination in trade-data |", "|---|---|---|"]
    o += [f"| {a} | {b} | `{c}` |" for a, b, c in EXTERNAL]
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
