"""research/map_a1_register.py — नकाशा A1 (I5, P8): entry engine मधल्या प्रत्येक आकड्याचा register. **फक्त अहवाल; code बदलत नाही.**

स्रोत: settings dicts (AST ने key, value, file:line, comment) + entry-मार्गातल्या files मधले inline आकडे (0 / 1 / −1 / 2 वगळून).
प्रत्येक key साठी "used_by" = entry मार्गातल्या कोणत्या files मध्ये ती वापरली जाते (नसेल ⇒ shadow / context, entry नाही).
वर्ग (व्याख्या / Abhi / research / NIFTY / अंदाज) आणि कारण: CLASS मधून (हाताने, स्रोतासह); नोंद नसलेले ⇒ "अंदाज (वर्ग तपासायचा)".

    python3 research/map_a1_register.py --out docs/reports/situation_map
"""
import argparse
import ast
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DICTS = [("simple_core/settings.py", "ENGINE_DEFAULTS"), ("market_state/core.py", "DEFAULTS"), ("chart_reader/zones.py", "DEFAULTS"),
         ("chart_reader/gap.py", "DEFAULTS"), ("chart_reader/candles.py", "DEFAULTS"), ("price_action/levels_v2.py", "DEFAULTS"),
         ("vision/gap_context.py", "DEFAULTS"), ("chart_reader/settings.py", "DEFAULTS")]
ELLIOTT = "elliott/settings.py"
ELLIOTT_SECTIONS = ("breaks", "swings", "degrees", "count", "invalidation")
ENTRY_FILES = ["simple_core/engine.py", "simple_core/waves.py", "simple_core/flags.py", "simple_core/settings.py", "market_state/core.py",
               "chart_reader/areas.py", "chart_reader/zones.py", "chart_reader/gap.py", "chart_reader/candles.py", "chart_reader/measures.py",
               "price_action/levels_v2.py", "elliott/breaks.py", "elliott/swings.py", "vision/gap_context.py"]
INLINE_FILES = ["simple_core/engine.py", "simple_core/waves.py", "simple_core/flags.py", "market_state/core.py", "chart_reader/zones.py",
                "chart_reader/areas.py", "elliott/breaks.py", "price_action/levels_v2.py"]

# (वर्ग, कारण) — हाताने; स्रोत KB / Abhi निर्णय / research notes. नोंद नसलेले ⇒ अंदाज.
CLASS = {
    "accept_closes": ("Abhi", "K-10 निर्णय B2 (16 Feb PDL): सलग 3 closes ⇒ acceptance; elliott/breaks.time_accepted हीच व्याख्या"),
    "break_accept_closes": ("Abhi", "K-10 B2; breaks.py (KB G ची एकच real-break व्याख्या) चा भाग"),
    "break_buffer_mr": ("research", "KB G: break buffer × MR (Osler stop clusters / spec §7); आकडा 0.25 अंदाज-समान"),
    "break_no_reclaim_bars": ("व्याख्या", "KB G: कमकुवत close नंतर reclaim नाही ⇒ acceptance"),
    "break_displacement_confirm": ("व्याख्या", "KB G: displacement close वर लगेच break"),
    "median_range_n": ("अंदाज", "MR lookback (20); sensitivity हवी"),
    "strength_min": ("अंदाज", "displacement / commitment ताकद × MR (1.2); sensitivity हवी"),
    "strength_max": ("अंदाज", "news spike मर्यादा × MR (2.5)"),
    "break_close_loc": ("अंदाज", "displacement close location (0.3)"),
    "area_tol_mr": ("अंदाज", "touch सहनशीलता 0.3 MR (Abhi: contaminated वर tune नाही; IS sensitivity हवी)"),
    "area_merge_mr": ("अंदाज", "zones एकत्र करण्याचं अंतर"),
    "pause_body_max": ("अंदाज", "indecision body ≤ 0.5 range"),
    "pause_range_max_mr": ("अंदाज", "indecision range ≤ 1 MR"),
    "pause_wick_min": ("अंदाज", "दोन्ही wicks ≥ 0.2"),
    "pause_min_bars": ("Abhi", "Simple Core: area वर किमान एक pause (थेट entry नाही)"),
    "pause_lookback": ("अंदाज", "pause शोध खिडकी"),
    "commit_strength_min_mr": ("अंदाज", "commitment range ≥ 1.2 MR (elliott strength_min सारखं)"),
    "commit_strength_max_mr": ("अंदाज", "commitment ≤ 2.5 MR (news spike नाही)"),
    "commit_body_min": ("अंदाज", "commitment body ≥ 0.5"),
    "commit_close_max": ("अंदाज", "close टोकाजवळ (0.3)"),
    "commitment_vs_pause": ("अंदाज", "Evening plan §5 [अनुमान] 1.5; Abhi: 1.3 / 1.5 / 2.0 sensitivity"),
    "accept_bars": ("अंदाज", "engine area acceptance: buffer पलीकडे सलग 2 closes (breaks.py बाहेरची दुसरी व्याख्या — B2 नुसार विलीन करायची)"),
    "accept_buf_mr": ("अंदाज", "engine acceptance buffer"),
    "opening_block_min": ("Abhi", "opening window (A3 / KB K14: पहिली candle नाही)"),
    "g8_retrace_max": ("Abhi", "KB H G8: उथळ 23.6–38.2%"),
    "g8_max_bars": ("Abhi", "KB H G8: 2–6 candles"),
    "g8_retrace_tol": ("अंदाज", "G8 retrace सहनशीलता"),
    "w3_proj": ("research", "Elliott guideline 1.618 (K7: Fibonacci ला सांख्यिकीय आधार नाही ⇒ फक्त माहिती)"),
    "w5_proj_w1": ("research", "Elliott guideline wave 5 = wave 1"),
    "w5_proj_w13": ("research", "Elliott guideline 0.618 × (1 start → 3 end)"),
    "flag_retrace_max": ("अंदाज", "flag ≤ 50% (research notes 'codable rule' ⇒ अंदाज वर्ग, नकाशा I5)"),
    "flag_min_bars": ("अंदाज", "flag किमान bars (नकाशा S5: G8 2–6 candles शी जुळवायचं)"),
    "flag_overlap_min": ("research", "KB K10.1 correction overlap > 0.6"),
    "flag_min_touches": ("व्याख्या", "channel = प्रत्येक रेषेला ≥ 2 touches"),
    "flag_slope_tol_mr": ("अंदाज", "flag slope सहनशीलता"),
    "trend_swing_atr_mult": ("research", "KB K1: HTF swing ≥ 1.5–2 MR"),
    "trade_swing_atr_mult": ("अंदाज", "trade-degree swings ATR × 3 (Elliott D1)"),
    "impulse_min_mr": ("research", "KB भाग B टप्पा 2: impulse ≥ 4 MR"),
    "impulse_er_min": ("अंदाज", "market_state: ER ≥ 0.45 [अनुमान, Abhi मंजुरी] — 7 Oct impulse overlap 0.62"),
    "impulse_overlap_max": ("research", "KB K2: overlap < 0.4"),
    "correction_overlap_min": ("research", "KB K10.1: correction overlap > 0.6"),
    "retrace_lo": ("Abhi", "valid खोली 38.2% पासून (नकाशा P4)"),
    "retrace_hi": ("व्याख्या", "100% = origin"),
    "reversal_retrace_min": ("रद्द (टप्पा B)", "POSSIBLE_REVERSAL — नकाशा: S3 + Gray-1 + reaction test ने बदलणार"),
    "reversal_min_criteria": ("रद्द (टप्पा B)", "POSSIBLE_REVERSAL — नकाशा: बदलणार"),
    "reversal_internal_atr": ("रद्द (टप्पा B)", "POSSIBLE_REVERSAL — नकाशा: बदलणार"),
    "disp_body_mr": ("अंदाज", "displacement body ≥ 1.5 MR"),
    "disp_body_frac": ("अंदाज", "displacement body ÷ range ≥ 0.6"),
    "htf_days": ("अंदाज", "HTF lookback दिवस"),
    "trade_days": ("अंदाज", "trade TF lookback दिवस"),
    "chop_max_crossings": ("अंदाज", "MAGNET: chop window मध्ये > 4 crossings"),
    "chop_window": ("अंदाज", "MAGNET खिडकी 20 bars"),
    "zone_pad_mr": ("अंदाज", "zone पट्टा pad"),
    "zone_min_mr": ("अंदाज", "zone किमान रुंदी"),
    "cluster_tol_mr": ("अंदाज", "pivot clustering सहनशीलता"),
    "min_rr": ("Abhi", "A3: R:R ≥ 3"),
    "g7_min_rr": ("Abhi", "A3: R:R ≥ 3 (G7)"),
    "atr_len": ("research", "standard ATR14"),
    "fib_min_impulse_mr": ("research", "KB भाग B: impulse ≥ 4 MR"),
    "impulse_disp_min": ("व्याख्या", "impulse मध्ये किमान एक displacement candle (F3)"),
    "zone_break_buffer_mr": ("अंदाज", "zone lifecycle buffer (breaks.py break_buffer_mr सारखाच 0.25 — एकच स्रोत करायचा)"),
    "g8_max_bars_note": ("Abhi", ""),
}
CONFIG = {"structure_tf", "swing_mode", "degree_tf_mode", "degree_tf", "auto_tfs", "trend_tf", "trade_tf", "pivot_source", "trade_degrees_enabled",
          "break_confirm_tf", "break_retest_confirm", "gap_setup_g7", "g7_classes", "elliott_degrees", "degrees"}


def _comment(lines, ln):
    m = re.search(r"#\s*(.*)$", lines[ln - 1])
    return m.group(1).strip() if m else ""


def dict_keys(path, name):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    lines = src.splitlines()
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets) and isinstance(node.value, ast.Dict):
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant):
                    try:
                        val = ast.literal_eval(v)
                    except ValueError:
                        val = ast.unparse(v)
                    out.append({"key": k.value, "value": val, "file": path, "line": k.lineno, "comment": _comment(lines, k.lineno)})
    return out


def elliott_keys():
    src = open(os.path.join(ROOT, ELLIOTT), encoding="utf-8").read()
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_s" and len(node.args) >= 6:
            try:
                key, section, label, help_, kind, default = (ast.literal_eval(a) for a in node.args[:6])
            except ValueError:
                continue
            if section in ELLIOTT_SECTIONS:
                out.append({"key": key, "value": default, "file": ELLIOTT, "line": node.lineno, "comment": f"[{section}] {label} — {help_}"[:160]})
    return out


def used_by(key):
    pat = re.compile(r"[\"']" + re.escape(key) + r"[\"']")
    return [f for f in ENTRY_FILES if os.path.exists(os.path.join(ROOT, f)) and pat.search(open(os.path.join(ROOT, f), encoding="utf-8").read())]


NUM = re.compile(r"(?<![\w.\"'])(\d+\.\d+|\d+e-?\d+|[3-9]|\d{2,})(?![\w.])")


def inline_literals():
    out = []
    for f in INLINE_FILES:
        for i, line in enumerate(open(os.path.join(ROOT, f), encoding="utf-8").read().splitlines(), 1):
            code = line.split("#", 1)[0]
            if not code.strip() or code.strip().startswith(('"', "'")) or re.match(r"\s*[\"']\w+[\"']\s*:", code) or "def " in code:
                continue
            if re.search(r"(range\(|\[\s*-?\d+\s*\]|\[:\d|\d:\]|iloc\[|:\d+\]|strftime|hours=|minutes=|days=|\{0:|fmt|f\")", code) and \
                    not re.search(r"\b0\.\d+\b", code):
                continue
            nums = [n for n in NUM.findall(code) if n not in ("10",)]
            if nums:
                out.append({"file": f, "line": i, "values": nums, "code": code.strip()[:140]})
    return out


def build():
    rows = []
    for path, name in DICTS:
        rows += [dict(r, source=name) for r in dict_keys(path, name)]
    rows += [dict(r, source="elliott SCHEMA") for r in elliott_keys()]
    for r in rows:
        r["used_by"] = used_by(r["key"])
        cls, why = CLASS.get(r["key"], ("config (TF / स्रोत निवड)", r["comment"]) if r["key"] in CONFIG else
                             ("अंदाज", (r["comment"] or "स्रोत नोंद नाही") + " — [स्रोत नाही ⇒ अंदाज]"))
        if not r["used_by"] and r["file"] == "chart_reader/settings.py":
            cls, why = "shadow (entry मार्गात नाही)", r["comment"] or "chart_reader evidence / grade"
        r["class"], r["reason"] = cls, why
    return rows, inline_literals()


def to_md(rows, inl):
    L = ["# नकाशा A1: Constants register (entry engine)", "",
         "फक्त अहवाल — कोणतंही मूल्य बदललं / निवडलं नाही. वर्ग: व्याख्या / Abhi / research / NIFTY / अंदाज. `used_by` रिकामा ⇒ entry मार्गात वापर "
         "नाही (shadow / context).", "",
         "**Real break ची एकच व्याख्या:** `elliott/breaks.py` — `first_real_break` (buffer + displacement / no-reclaim / failed retest) आणि "
         "`time_accepted` (`break_accept_closes` = 3, Abhi). `levels_v2.lifecycle` (`accept_closes`) आणि Simple Core engine ची area "
         "acceptance दोन्ही `breaks.time_accepted` च वापरतात. **उरलेली दुसरी व्याख्या:** engine `accept_bars` (buffer पलीकडे सलग 2 closes) आणि "
         "`levels_v2` चा buffer + पुढचा bar नियम — टप्पा B मध्ये breaks.py मध्ये विलीन करायचे (खाली ⚠).", ""]
    for cls in sorted({r["class"] for r in rows}):
        sub = [r for r in rows if r["class"] == cls]
        L += [f"## {cls} ({len(sub)})", "", "| key | मूल्य | file:line | used_by | कारण |", "|---|---|---|---|---|"]
        for r in sorted(sub, key=lambda r: (r["file"], r["line"])):
            ub = ", ".join(os.path.basename(u) for u in r["used_by"]) or "—"
            L.append(f"| `{r['key']}` | {r['value']} | {r['file']}:{r['line']} | {ub} | {str(r['reason']).replace('|', '/')[:150]} |")
        L.append("")
    L += ["## Inline आकडे (settings बाहेर) — प्रत्येक setting मध्ये न्यायचा का ते टप्पा B मध्ये", "", "| file:line | आकडे | code |", "|---|---|---|"]
    L += [f"| {x['file']}:{x['line']} | {', '.join(x['values'])} | `{x['code'].replace('|', '/')}` |" for x in inl]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    rows, inl = build()
    open(os.path.join(a.out, "A1_constants_register.md"), "w", encoding="utf-8").write(to_md(rows, inl))
    json.dump({"rows": rows, "inline": inl}, open(os.path.join(a.out, "A1_constants_register.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    from collections import Counter
    print(Counter(r["class"] for r in rows), "inline", len(inl))


if __name__ == "__main__":
    main()
