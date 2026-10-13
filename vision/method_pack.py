"""vision/method_pack.py — Method Pack (design `docs/design/CHART_READER_AGENT.md` §12): KB मधून बनलेला स्थिर English method मजकूर.

🎓 एकच स्रोत: `docs/knowledge/KNOWLEDGE_BASE.md`. KB मधले `<!-- pack:N key -->` … `<!-- /pack -->` blocks (Abhi च्या क्रमाने N = 0–7; आतले `<!-- pending:abhi -->` …
`<!-- /pending -->` भाग = Abhi ची मंजुरी बाकी ⇒ pack मध्ये येत नाहीत)
आणि `docs/knowledge/ABHI_METHOD_NOTES.md` चे "## Entries" (section 8) ⇒ `docs/knowledge/method_pack.md` (`scripts/build_method_pack.py`).
Pack version = pack body चा sha256 (पहिले 12 hex) — header मध्ये; प्रत्येक Vision / reader नोंदीत तोच version (§12.4).
Pack मध्ये R:R / SL / target / size / exits नाहीत (dashboard settings, Abhi चा निर्णय) — `banned_hits` + stale-pack test.
हे module API call करत नाही; फक्त मजकूर बनवतो / वाचतो.
"""
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(ROOT, "docs", "knowledge", "KNOWLEDGE_BASE.md")
NOTES_PATH = os.path.join(ROOT, "docs", "knowledge", "ABHI_METHOD_NOTES.md")
PACK_PATH = os.path.join(ROOT, "docs", "knowledge", "method_pack.md")

SECTIONS = {                                                              # Abhi चा क्रम (§12.1 items 1–8; 0 = conventions)
    0: ("conventions", "Conventions"),
    1: ("topdown", "Top-down reading"),
    2: ("areas", "Areas (demand / supply)"),
    3: ("trendlines", "Trendlines and channels"),
    4: ("corrections", "Corrections: impulse vs correction, correction types"),
    5: ("zone_study", "Zone study: liquidity, volume, handover, patterns inside the area"),
    6: ("trigger", "Trigger"),
    7: ("never", "Never"),
    8: ("abhi_notes", "Abhi method notes"),
}
TOKENS_MIN, TOKENS_MAX = 6000, 10000                                       # §12.1 target ≈ 6–10k tokens (chars / 4)
BANNED = (                                                                 # §12.1 "Not in the pack"
    (r"R\s*:\s*R", "R:R"),
    (r"risk[\s-]*(?:to[\s-]*)?reward", "risk-reward"),
    (r"reward[\s-]*(?:to[\s-]*)?risk", "reward-to-risk"),
    (r"\blots?\b", "lot"),
)
_BLOCK = re.compile(r"<!-- pack:(\d) ([a-z_]+) -->\n(.*?)\n<!-- /pack -->", re.S)
_SUMMARY = re.compile(r"^<summary>Method Pack \(English\) — ([^<]*?)\(source: (.*)\)</summary>$")
_PENDING = re.compile(r"\n?<!-- pending:[a-z_]+ -->\n.*?\n<!-- /pending -->", re.S)    # Abhi च्या मंजुरीची वाट ⇒ pack मध्ये नाही
_HEAD = re.compile(r"\A# Method Pack — version ([0-9a-f]{12})\n<!--[^\n]*-->\n\n")
NONE_YET = "(none yet — entries are added only after Abhi approves them)"


class PackError(ValueError):
    """KB markers / notes / pack file चुकीचे (generator आणि loader fail-closed)."""


def blocks(kb_text):
    """KB ⇒ [(n, key, title, source, body)] KB क्रमाने. Marker चुकीचा (key ≠ SECTIONS, summary नाही, उघडा marker) ⇒ PackError."""
    out = []
    for m in _BLOCK.finditer(kb_text):
        n, key, raw = int(m.group(1)), m.group(2), m.group(3)
        if n not in SECTIONS or n == 8 or SECTIONS[n][0] != key:
            raise PackError(f"pack:{n} {key} — अज्ञात section (SECTIONS 0–7)")
        lines = raw.strip("\n").split("\n")
        if len(lines) < 3 or not lines[0].startswith("<details><summary>"):
            raise PackError(f"pack:{n} {key} — <details><summary>Method Pack (English) — …</summary> हवं")
        sm = _SUMMARY.match(lines[0][len("<details>"):])
        if not sm or lines[-1] != "</details>":
            raise PackError(f"pack:{n} {key} — summary / </details> ओळ चुकीची: {lines[0][:80]!r}")
        body = "\n".join(lines[1:-1]).strip("\n")
        body = _PENDING.sub("", body)
        if "<!-- pending" in body or "<!-- /pending" in body:
            raise PackError(f"pack:{n} {key} — pending marker उघडा / बंद जुळत नाही")
        out.append((n, key, sm.group(1).strip(), sm.group(2).strip(), body))
    opened, closed = kb_text.count("<!-- pack:"), kb_text.count("<!-- /pack -->")
    if opened != len(out) or closed != len(out):
        raise PackError(f"pack markers जुळत नाहीत: उघडे {opened}, बंद {closed}, वाचलेले {len(out)}")
    missing = [SECTIONS[n][0] for n in range(8) if not any(b[0] == n for b in out)]
    if missing:
        raise PackError(f"KB मध्ये pack sections नाहीत: {missing}")
    return out


def notes_entries(notes_text):
    """ABHI_METHOD_NOTES.md चा "## Entries" खालचा मजकूर (रिकामा ⇒ "")."""
    m = re.search(r"^## Entries[ \t]*\n(.*)\Z", notes_text or "", re.S | re.M)
    return (m.group(1) if m else "").strip()


def build_body(kb_text, notes_text):
    """Pack body (header शिवाय) — deterministic: फक्त KB + notes मजकुरावर अवलंबून (वेळ / path नाही)."""
    bl = blocks(kb_text)
    parts = ["You read NIFTY / BANKNIFTY charts with the owner's method below. It is generated from the owner's knowledge base and is the "
             "only method text you use. Not in this pack: trade-management numbers (stop, target, position size, exits) — they are "
             "dashboard settings and the owner's decision at approval; never judge or mention them."]
    for n in range(8):
        parts.append(f"## {n}. {SECTIONS[n][1]}")
        for _, _, title, src, body in (b for b in bl if b[0] == n):
            parts.append(f"*{title} — KB source: {src}*\n\n{body}")
    ent = notes_entries(notes_text)
    parts.append(f"## 8. {SECTIONS[8][1]}\n\n{ent or NONE_YET}")
    return "\n\n".join(parts).rstrip() + "\n"


def version_of(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def header(ver):
    return (f"# Method Pack — version {ver}\n"
            "<!-- generated by scripts/build_method_pack.py from docs/knowledge/KNOWLEDGE_BASE.md + ABHI_METHOD_NOTES.md — "
            "do not edit by hand -->\n\n")


def build(kb_text, notes_text):
    """(pack file मजकूर, version)."""
    body = build_body(kb_text, notes_text)
    ver = version_of(body)
    return header(ver) + body, ver


def build_from_repo(kb_path=KB_PATH, notes_path=NOTES_PATH):
    kb = open(kb_path, encoding="utf-8").read()
    notes = open(notes_path, encoding="utf-8").read() if os.path.exists(notes_path) else ""
    return build(kb, notes)


def split(pack_text):
    """Pack file ⇒ (header मधला version, body). Header चुकीचा ⇒ PackError."""
    m = _HEAD.match(pack_text or "")
    if not m:
        raise PackError("method_pack.md header चुकीचा (# Method Pack — version <12 hex>)")
    return m.group(1), pack_text[m.end():]


def tokens_estimate(text):
    return len(text) // 4                                                   # §12.1: chars / 4


def banned_hits(text):
    """Pack मध्ये नसावेत असे शब्द (R:R / risk-reward / lot) ⇒ [(label, सापडलेला मजकूर)]."""
    out = []
    for rx, label in BANNED:
        out += [(label, m.group(0)) for m in re.finditer(rx, text, re.I)]
    return out


def load(path=PACK_PATH):
    """Commit केलेला pack ⇒ (पूर्ण मजकूर, version). Header चा version body च्या hash शी जुळत नाही ⇒ PackError (fail-closed)."""
    text = open(path, encoding="utf-8").read()
    ver, body = split(text)
    if version_of(body) != ver:
        raise PackError(f"method_pack.md version {ver} ≠ body hash {version_of(body)} — scripts/build_method_pack.py पुन्हा चालवा")
    return text, ver
