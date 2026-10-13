"""Method Pack (R0, design §12.1): stale-pack CI check + content rules. API call नाही."""
import re

import pytest

from vision import method_pack as MP


def test_committed_pack_equals_regenerated_from_kb():
    text, ver = MP.build_from_repo()
    with open(MP.PACK_PATH, encoding="utf-8") as fh:
        committed = fh.read()
    assert committed == text, "docs/knowledge/method_pack.md stale — run `python3 scripts/build_method_pack.py` and commit"
    assert MP.load() == (text, ver)


def test_version_header_is_body_hash():
    with open(MP.PACK_PATH, encoding="utf-8") as fh:
        text = fh.read()
    ver, body = MP.split(text)
    assert re.fullmatch(r"[0-9a-f]{12}", ver)
    assert ver == MP.version_of(body)


def test_no_rr_sl_lot_rules_and_size_in_bounds():
    text, _ = MP.build_from_repo()
    assert MP.banned_hits(text) == []
    for bad in ("R:R", "risk-reward", "risk reward", "reward-to-risk"):
        assert bad.lower() not in text.lower()
    assert not re.search(r"\blots?\b", text, re.I)
    assert MP.TOKENS_MIN <= MP.tokens_estimate(text) <= MP.TOKENS_MAX


def test_sections_in_abhi_order_and_kb_sources():
    text, _ = MP.build_from_repo()
    heads = re.findall(r"^## (\d)\. ", text, re.M)
    assert heads == [str(n) for n in range(9)]
    for must in ("2 touches", "3rd touch", "role flip", "confluence", "zigzag", "expanded", "running flat", "triangle",
                 "W-X-Y", "handover", "sweep", "CHoCH by close", "dominant commitment", "KP1", "Never a breakout"):
        assert must.lower() in text.lower(), must
    assert "KB source:" in text


def test_banned_hits_detects_words():
    assert MP.banned_hits("keep R:R ≥ 3") and MP.banned_hits("2 lots") and MP.banned_hits("Risk-Reward 1:3")
    assert MP.banned_hits("time slot, pilot, allotted") == []


def _kb(extra=""):
    blocks = []
    for n in range(8):
        key = MP.SECTIONS[n][0]
        blocks.append(f"<!-- pack:{n} {key} -->\n<details><summary>Method Pack (English) — {n}. T{n} (source: K{n})</summary>\n\n"
                      f"- text {n}\n\n</details>\n<!-- /pack -->")
    return "मराठी मजकूर\n\n" + "\n\nमधला मजकूर\n\n".join(blocks) + extra


def test_build_is_deterministic_and_includes_notes_entries():
    t1, v1 = MP.build(_kb(), "# x\n\n## Entries\n")
    t2, v2 = MP.build(_kb(), "# x\n\n## Entries\n")
    assert (t1, v1) == (t2, v2)
    assert MP.NONE_YET in t1
    t3, v3 = MP.build(_kb(), "# x\n\n## Entries\n- [2026-10-14, approved by Abhi] lesson one.\n")
    assert "lesson one." in t3 and v3 != v1
    assert "*0. T0 — KB source: K0*" in t1 and "मराठी" not in t1


def test_malformed_markers_fail_closed():
    with pytest.raises(MP.PackError):
        MP.build(_kb("\n<!-- pack:3 trendlines -->\nno details\n<!-- /pack -->"), "")
    with pytest.raises(MP.PackError):
        MP.build(_kb("\n<!-- pack:2 wrongkey -->\n<details><summary>Method Pack (English) — x (source: y)</summary>\n</details>\n"
                     "<!-- /pack -->"), "")
    with pytest.raises(MP.PackError):                                      # उघडा marker
        MP.build(_kb("\n<!-- pack:1 topdown -->\n"), "")
    with pytest.raises(MP.PackError):                                      # section गहाळ
        MP.build(_kb().replace("<!-- pack:6 trigger -->", "<!-- x -->").replace("(source: K6)</summary>\n\n- text 6\n\n</details>\n"
                                                                                 "<!-- /pack -->", ""), "")


def test_load_rejects_tampered_pack(tmp_path):
    text, _ = MP.build(_kb(), "")
    p = tmp_path / "pack.md"
    p.write_text(text.replace("text 3", "text 33"), encoding="utf-8")
    with pytest.raises(MP.PackError):
        MP.load(str(p))


def test_generator_check_mode(tmp_path, capsys):
    import scripts.build_method_pack as G
    assert G.main(["--check"]) == 0
    out = tmp_path / "pack.md"
    assert G.main(["--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == MP.build_from_repo()[0]
    out.write_text("stale", encoding="utf-8")
    assert G.main(["--check", "--out", str(out)]) == 1
    assert "tokens" in capsys.readouterr().out



def test_pack_has_two_touch_rule_and_no_three_touch_minimum():
    """TA3 / TA3b (Abhi): line आणि horizontal band 2 touches वरून काढले जातात; 3रा touch = trade location; ≥ 3 = established."""
    text, _ = MP.build_from_repo()
    low = text.lower()
    assert "a trendline is drawn from 2 touches" in low and "horizontal s/r band — drawn from 2 touches" in low
    assert "3rd touch is the trade location" in low and "established" in low
    assert "never a minimum" in low
    for bad in ("≥ 3 touches", ">= 3 touches", "at least 3 touches", "at least three touches", "minimum of 3 touches",
                "need 3 touches", "needs 3 touches", "requires 3 touches"):
        assert bad not in low, bad


def test_pending_abhi_text_is_excluded_from_pack():
    text, _ = MP.build_from_repo()
    assert "pending" not in text.lower()
    flat = text.replace("\n  ", " ")                                               # Abhi: "zone dead" नाही — तुटलेला zone flip होतो
    assert "dead only beyond the far swing" not in flat and "A broken zone flips [Abhi]" in flat
    assert "reaches the next swing" in flat and "strong move" in flat
    assert "not by a single wick" not in flat                                  # "strong move" चं वाचन अजून pending
    assert "22,720" not in flat                                                # golden दिवसाचा निकाल pack मध्ये नाही (leak)
    pend = "\n<!-- pending:abhi -->\n- secret pending rule\n<!-- /pending -->"
    t1, _ = MP.build(_kb().replace("- text 2", "- text 2" + pend), "")
    assert "secret pending rule" not in t1 and "text 2" in t1
    with pytest.raises(MP.PackError):                                      # उघडा pending marker
        MP.build(_kb().replace("- text 2", "- text 2\n<!-- pending:abhi -->\n- x"), "")
