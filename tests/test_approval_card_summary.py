"""Abhi (simple approval card): setting `approval_card_layout` — "classic" (default) = today's Vision / approval card byte-for-byte;
"summary" = five short lines on top (side + label · area + last price · the reader's ✓ / ✗ from the engine's layer 6a evidence list ·
Vision in one line · what you do + deadline), today's details unchanged below "── details ──". Fake rows only (no real data, no
network, no AI). Every summary value comes from the row / gate tags / engine reader facts; a missing value is left out."""
import json
import re

import pytest

from bots_common import plain_text as PT
from decision3 import settings as S3
from vision import approval as AP
from vision import card_summary as CS
from vision import config as VCF
from vision import decide as VD
from vision import worker as VW

CLASSIC_MAIN = {  # captured from origin/main (16203b2) for the fake rows below — classic must stay byte-identical
    # (T-1, DECISIONS 29: only the deadline / no-buttons / rejected lines changed to Abhi's plain words; the longer rejected line
    #  trims one detail line of own_rejected under the 1024 limit)
    'engine_a_pending': (
        'NIFTY: a bear call (bearish) trade at supply area 22,544–22,622 (78 pts) (15M chart). Look at the area and the last candle: did sellers really take over there?\n'
        '<b>Decision needed: approve / reject</b> by 09:55\n'
        '── details ──\n'
        '👁 <b>NIFTY</b> · <b>Vision V1 — veto_then_confirm</b> · <i>Price-action engine (PAPER)</i>\n'  # addition D: engine signal
        '⏱ <b>Decide by 09:55</b>. ✅ take · ❌ skip. No reply ⇒ taken (full size).\n'
        '🎯 Confirmation: supply 22,544–22,622 · grade A · trend: DOWN\n'
        'NIFTY · Bearish · Reversal (touch)\n'
        'engine: NA (ताजा engine निर्णय नाही)\n'
        'Area 22,544–22,622 (78 pts) (Resistance, 15M) · signal 09:45\n'
        'मत: ✅ <b>सहमत</b> (confidence 0.80)\n'
        '<b>कारण:</b> Sellers took over inside the 1H supply: a strong red commitment candle closed back below the area after a fast two-candle turn. RSI shows a lower high.\n'
        'Trend: HTF up · setup unclear (against)\n'
        'Level: reference · real yes · confluence yes\n'
        'Wave: unclear · correction पूर्ण no\n'
        'Reversal: touch ✗ reclaim ✗ strength ✗ close ✗ ⇒ no\n'
        'SL / target / exits: bot चे नेहमीचे नियम (automatic).'
    ),
    'engine_b_pending': (
        'NIFTY: a bear call (bearish) trade at supply area 22,544–22,622 (78 pts) (15M chart). Look at the area and the last candle: did sellers really take over there?\n'
        '<b>Decision needed: approve / reject</b> by 09:55\n'
        '── details ──\n'
        '👁 <b>NIFTY</b> · <b>Vision V1 — veto_then_confirm</b> · <i>Price-action engine (PAPER)</i>\n'  # addition D: engine signal
        '⏱ <b>Decide by 09:55</b>. ✅ take · ❌ skip. No reply ⇒ taken (full size).\n'
        '🎯 Confirmation: supply 22,544–22,622 · grade B · trend: DOWN\n'
        'NIFTY · Bearish · Reversal (touch)\n'
        'engine: NA (ताजा engine निर्णय नाही)\n'
        'Area 22,544–22,622 (78 pts) (Resistance, 15M) · signal 09:45\n'
        'मत: ✅ <b>सहमत</b> (confidence 0.80)\n'
        '<b>कारण:</b> Sellers took over inside the 1H supply: a strong red commitment candle closed back below the area after a fast two-candle turn. RSI shows a lower high.\n'
        'Trend: HTF up · setup unclear (against)\n'
        'Level: reference · real yes · confluence yes\n'
        'Wave: unclear · correction पूर्ण no\n'
        'Reversal: touch ✗ reclaim ✗ strength ✗ close ✗ ⇒ no\n'
        'SL / target / exits: bot चे नेहमीचे नियम (automatic).'
    ),
    'own_rejected': (
        'NIFTY: a bear call (bearish) trade at resistance 23,175 (5M chart). Look at the area and the last candle: did sellers really take over there?\n'
        'Decision needed: none — information (entry rejected automatically)\n'
        '── details ──\n'
        '👁 <b>Vision V1 — veto_then_confirm</b> · NIFTY 5-Min Instant\n'
        '<b>❌ ENTRY नाकारली</b> — veto_then_confirm: vision disagree ⇒ आपोआप skip. Trade NOT taken; a comparison-only shadow trade may follow (not counted in results).\n'
        'NIFTY · Bearish · Reversal (touch)\n'
        'engine: NA (ताजा engine निर्णय नाही)\n'
        'Level 23,175 (Resistance, 5M) · signal 11:30\n'
        'मत: ❌ <b>असहमत</b> (confidence 0.90)\n'
        '<b>कारण:</b> Price is far below the marked resistance and the last candle shows no seller takeover at the level. The structure is still an up-move on the higher timeframe, so a bear call here is against it.\n'
        'Trend: HTF up · setup unclear (against)\n'
        'Level: reference · real yes · confluence yes\n'
        'Wave: unclear · correction पूर्ण no\n'
        'SL / target / exits: bot चे नेहमीचे नियम (automatic).'
    ),
    'test_rejected': (
        '🧪 TEST — not a trade · NIFTY: a bear call (bearish) trade at resistance 23,175 (15M chart). Look at the area and the last candle: did sellers really take over there?\n'
        'Decision needed: none — information (entry rejected automatically)\n'
        '── details ──\n'
        '👁 <b>Vision V1 — veto_then_confirm</b> · NIFTY 15M Dynamic SR\n'
        '<b>❌ ENTRY नाकारली</b> — veto_then_confirm: vision disagree ⇒ आपोआप skip. Trade NOT taken; a comparison-only shadow trade may follow (not counted in results).\n'
        'NIFTY · Bearish · Reversal (touch)\n'
        'engine: NA (ताजा engine निर्णय नाही)\n'
        'Level 23,175 (Resistance, 15M) · signal 00:09\n'
        'मत: ❌ <b>असहमत</b> (confidence 0.90)\n'
        '<b>कारण:</b> Price is far below the marked resistance and the last candle shows no seller takeover at the level. The structure is still an up-move on the higher timeframe, so a bear call here is against it.\n'
        'Trend: HTF up · setup unclear (against)\n'
        'Level: reference · real yes · confluence yes\n'
        'Wave: unclear · correction पूर्ण no\n'
        'SL / target / exits: bot चे नेहमीचे नियम (automatic).'
    ),
    'level_bot_pending_nobuttons': (
        'NIFTY: a bear call (bearish) trade at supply area 22,715–22,776 (61 pts) (15M chart). Look at the area and the last candle: did sellers really take over there?\n'
        '<b>Decision needed: approve / reject</b> by 09:55\n'
        '── details ──\n'
        '👁 <b>Vision V1 — veto_then_confirm</b> · NIFTY Classic SR\n'
        '⏱ <b>Decide by 09:55</b>. ✅ take · ❌ skip. No reply ⇒ taken (full size).\n'
        '⚠️ Buttons unavailable: no approver; the no-reply rule decides this signal.\n'
        'Vision: NA (budget संपलं) — बटणं तरीही चालतात\n'
        '🎯 Confirmation: supply 22,715–22,776 · grade B · trend: Daily DOWN\n'
        'inside supply: sellers growing\n'
        'commitment: two_candle · volume above the opposite side\n'
        'Entry 22677.0 · engine reference (info): SL 22790.0 · target 22300.0\n'
        'Trade SL / target: dashboard settings\n'
        'NIFTY · Bearish · Reversal (touch)\n'
        'engine: NA (ताजा engine निर्णय नाही)\n'
        'Area 22,715–22,776 (61 pts) (Resistance, 15M) · signal 09:45\n'
        'मत: ⚪ <b>उपलब्ध नाही</b>\n'
        'कारण: budget संपलं\n'
        'SL / target / exits: bot चे नेहमीचे नियम (automatic).'
    ),
    'manual_approved': (
        'NIFTY: your manual bear call (bearish) trade at resistance 22,583 (15M chart). Look at the area and the last candle: did sellers really take over there?\n'
        'Decision needed: none — information (entry approved automatically)\n'
        '── details ──\n'
        '👁 <b>Vision V1 — veto_then_confirm</b> · ✋ Manual\n'
        '<b>✅ ENTRY मंजूर</b> (पूर्ण size) — auto_veto: agree. Bot पुढच्या मिनिटाला drift guard नंतर entry घेईल (त्याचा trade संदेश येईल).\n'
        '✋ MANUAL bear call 22700/22900 · SL 22790 · T 22300\n'
        'NIFTY · Bearish · Reversal (touch)\n'
        'engine: NA (ताजा engine निर्णय नाही)\n'
        'Level 22,583 (Resistance, 15M) · signal 09:45\n'
        'मत: ✅ <b>सहमत</b> (confidence 0.80)\n'
        '<b>कारण:</b> Sellers took over inside the 1H supply: a strong red commitment candle closed back below the area after a fast two-candle turn. RSI shows a lower high.\n'
        'Trend: HTF up · setup unclear (against)\n'
        'Level: reference · real yes · confluence yes\n'
        'Wave: unclear · correction पूर्ण no\n'
        'SL / T: तुमचे spot SL / T (paper watcher) + backstop generic नियम.'
    ),
    'v0_notify': (
        'NIFTY: a bear call (bearish) trade at resistance 23,175 (5M chart). Look at the area and the last candle: did sellers really take over there?\n'
        'Decision needed: none — information (Vision opinion only; the bot decided as usual)\n'
        '── details ──\n'
        '👁 <b>Vision V0 — फक्त माहिती</b> · NIFTY 5-Min Instant\n'
        'NIFTY · Bearish · Reversal (touch)\n'
        'Level 23,175 (Resistance, 5M) · signal 11:30\n'
        'मत: ❌ <b>असहमत</b> (confidence 0.90)\n'
        '<b>कारण:</b> Price is far below the marked resistance and the last candle shows no seller takeover at the level. The structure is still an up-move on the higher timeframe, so a bear call here is against it.\n'
        'Trend: HTF up · setup unclear (against)\n'
        'Level: reference · real yes · confluence yes\n'
        'Wave: unclear · correction पूर्ण no\n'
        'Reversal: touch ✗ reclaim ✗ strength ✗ close ✗ ⇒ no\n'
        'Room ok · false-break risk high · time low\n'
        'Bot ने नेहमीप्रमाणे निर्णय घेतला — vision चा trade वर परिणाम नाही (V0).\n'
        'खर्च $0.0123 · 8.2s'
    ),
    'ticket': (
        'NIFTY: your changed entry 22600 (engine reference stop 22790, target 22300). Check the new numbers, then approve again.\n'
        '<b>Decision needed: approve / reject</b> by 10:05\n'
        '── details ──\n'
        '✏️ <b>सुधारित ticket</b> · NIFTY BEARISH · 15M\n'
        'Entry (limit, spot) <b>22600</b> (engine: 22677) · engine reference (info): SL 22790 · target 22300 · area 22,715–22,776 (61 pts)\n'
        '⚠️ entry area 22,715–22,776 बाहेर\n'
        'फक्त entry बदलली — trade चे SL / target / lots / strikes / hedge / expiry / risk: dashboard चेच.\n'
        '⏱ <b>10:05 पर्यंत</b> पुन्हा ✅ हवं. ✅ नंतर spot 22600 ला पोहोचला तरच PAPER entry; 5 मिनिटांत नाही ⇒ position नाही (would-have नोंद).'
    ),
}


READER_A = {"evidence_list": {"required": "present", "entry_hours": "inside",
                              "confirming": {"volume_growing": "NA", "rsi_divergence": "present", "confluence": "present",
                                             "correction_line_closed_through": "absent"},
                              "context": {"trap_sweep": "absent"}},
            "trend": True, "area": True, "handover_form": "sharp_reversal", "ltf": "5M"}
READER_B = {"evidence_list": {"required": "present", "entry_hours": "inside",
                              "confirming": {"volume_growing": "absent", "rsi_divergence": "NA", "confluence": "absent",
                                             "correction_line_closed_through": "NA"},
                              "context": {}},
            "trend": True, "area": True, "handover_form": "study", "ltf": "5M"}


def engine_gate(grade, reader):
    return {"mode": "engine", "side": "BEARISH", "area": [22543.75, 22621.8], "grade": grade, "tf": "15M", "trend": "DOWN",
            "form": "two_candle", "band_warn_pts": 150.0, "band_warn_rule": "points",
            "areas": [{"id": 7, "role": "resistance", "lo": 22543.75, "hi": 22621.8, "tf": "1H", "state": "TESTED",
                       "confluence_label": "confluence: line (touch 3)"}],
            "reader": reader}


def row(tags, **kw):
    r = {"signal_id": "s1", "bot": "srv2_momentum_reversal", "bot_label": "NIFTY 15M Dynamic SR", "symbol": "NIFTY",
         "direction": "BEARISH", "level": 22582.78, "role": "Resistance", "setup_tf": "15M", "signal_ts": "2026-10-12T09:45:00",
         "mode": "veto_then_confirm", "spot": 22470.0, "setup_json": json.dumps({"tags": tags}, ensure_ascii=False)}
    r.update(kw)
    return r


ENGINE_A = row({"engine": True, "engine_bar": "2026-10-12 09:45:00", "engine_grade": "A", "gate": engine_gate("A", READER_A)},
               ctx={"spot": 22488.6})
ENGINE_B = row({"engine": True, "engine_bar": "2026-10-12 09:45:00", "engine_grade": "B", "gate": engine_gate("B", READER_B)})
ENGINE_OLD = row({"engine": True, "engine_grade": "A", "gate": {**engine_gate("A", None)}})          # an older row: no reader
OWN = row({}, level=23175.0, spot=22889.0, signal_ts="2026-10-20T11:30:00", bot="dynamic_sr_instant", bot_label="NIFTY 5-Min Instant",
          setup_tf="5M")
TEST = row({"test_only": True, "dry_run": True}, level=23175.0, spot=22889.0, signal_ts="2026-10-21T00:09:00")
LEVEL_BOT = row({"gate": {"mode": "confirmation", "side": "BEARISH", "area": [22715.0, 22776.0], "grade": "B", "trend": "Daily DOWN",
                          "study": "inside supply: sellers growing", "commit_line": "commitment: two_candle · volume above the opposite side",
                          "entry": 22677.0, "sl": 22790.0, "target": 22300.0, "rr": None}},
                bot="classic_sr", bot_label="NIFTY Classic SR", spot=22690.0)
MANUAL = row({"manual": True, "manual_id": "m1", "manual_text": "✋ MANUAL bear call 22700/22900 · SL 22790 · T 22300"},
             bot="manual", bot_label="✋ Manual")

REASON = ("Price is far below the marked resistance and the last candle shows no seller takeover at the level. "
          "The structure is still an up-move on the higher timeframe, so a bear call here is against it.")
AUDIT = {"reason": REASON, "level_kind": "reference", "level_real": "yes", "confluence": "yes", "htf_trend": "up",
         "setup_structure": "unclear", "trend_context": "against", "wave_position": "unclear", "correction_complete": "no",
         "reversal_touch": "no", "reversal_reclaim": "no", "reversal_strength": "bad", "reversal_close_location": "bad",
         "reversal_valid": "no", "room_to_next_level": "ok", "false_break_risk": "high", "time_risk": "low"}
RES_DISAGREE = {"verdict": "disagree", "confidence": 0.9, "audits": [AUDIT], "verdicts": ["disagree"], "cost_usd": 0.0123,
                "latency_ms": 8200}
RES_AGREE = {"verdict": "agree", "confidence": 0.8, "verdicts": ["agree"],
             "audits": [{**AUDIT, "reason": "Sellers took over inside the 1H supply: a strong red commitment candle closed back below "
                                              "the area after a fast two-candle turn. RSI shows a lower high."}]}
RES_NA = {"verdict": "unavailable", "error": "budget संपलं"}


ENGINE_LINE = "engine: NA (ताजा engine निर्णय नाही)"
PEND = VD.Decision("PENDING_HUMAN", 1.0, "veto_then_confirm: agree", "APPROVED", 1.0, True)
REJ = VD.Decision("REJECTED", 0.0, "veto_then_confirm: vision disagree ⇒ आपोआप skip")
APP = VD.Decision("APPROVED", 1.0, "auto_veto: agree")
DL = "2026-10-12T09:55:00"
TICKET = {"side": "BEARISH", "entry": 22600.0, "sl": 22790.0, "target": 22300.0, "rr": None, "area": [22715.0, 22776.0],
          "engine_entry": 22677.0, "src": "engine", "warnings": ["⚠️ entry area 22,715–22,776 बाहेर"], "show_rr": False}


@pytest.fixture(autouse=True)
def _engine_line(monkeypatch):
    monkeypatch.setattr(VW, "engine_line", lambda row: ENGINE_LINE)        # the engine store is not read in these tests


def cards(layout=None, **kw):
    """The same eight cards as CLASSIC_MAIN; layout None ⇒ the callers' default (no argument at all)."""
    lk = {} if layout is None else {"layout": layout, **kw}
    tk = {} if layout is None else {"layout": layout, "window_min": kw.get("window_min")}
    return {
        "engine_a_pending": VW.v1_caption(ENGINE_A, RES_AGREE, PEND, DL, **lk),
        "engine_b_pending": VW.v1_caption(ENGINE_B, RES_AGREE, PEND, DL, **lk),
        "own_rejected": VW.v1_caption(OWN, RES_DISAGREE, REJ, None, **lk),
        "test_rejected": VW.v1_caption(TEST, RES_DISAGREE, REJ, None, **lk),
        "level_bot_pending_nobuttons": VW.v1_caption(LEVEL_BOT, RES_NA, PEND, DL, buttons=False, why="no approver", **lk),
        "manual_approved": VW.v1_caption(MANUAL, RES_AGREE, APP, None, **lk),
        "v0_notify": VW.caption({**OWN, "mode": "notify"}, RES_DISAGREE, "notify", **({} if layout is None else {"layout": layout})),
        "ticket": AP.ticket_text(LEVEL_BOT, TICKET, "2026-10-12T10:05:00", 5, **tk),
    }


def top5(cap):
    head, _sep, _rest = cap.partition("\n" + PT.SEP + "\n")
    return head.split("\n")


# ------------------------------------------------------------------------------------------------ setting
def test_setting_registered_default_classic():
    assert S3.OUTPUT["approval_card_layout"][:2] == ("classic", ("classic", "summary"))
    assert S3.REGISTER["approval_card_layout"][:3] == ("classic", "classic / summary", "setting")
    assert VCF.BOT_DEFAULTS["approval_card_layout"] == "classic" and tuple(VCF.ENUMS["approval_card_layout"]) == ("classic", "summary")
    assert VCF.validate("srv2_momentum_reversal", {"approval_card_layout": "summary"})["approval_card_layout"] == "summary"
    with pytest.raises(ValueError):
        VCF.validate("srv2_momentum_reversal", {"approval_card_layout": "fancy"})
    assert CS.layout(None) == CS.layout("") == CS.layout("weird") == CS.layout({}) == "classic"
    assert CS.layout({"approval_card_layout": "SUMMARY"}) == "summary"
    assert "approval_card_layout" not in S3.DEFAULTS                             # display only: never a reading setting


# ------------------------------------------------------------------------------------------------ classic = today, byte for byte
@pytest.mark.parametrize("layout", [None, "classic", "nonsense"])
def test_classic_is_byte_identical_to_main(layout):
    got = cards(layout, window_min=10)
    for k, want in CLASSIC_MAIN.items():
        assert got[k] == want, k


# ------------------------------------------------------------------------------------------------ summary: the five lines
def test_summary_engine_label_a():
    cap = VW.v1_caption(ENGINE_A, RES_AGREE, PEND, DL, layout="summary", window_min=10, modify=False)
    assert top5(cap) == [
        "🟡 NIFTY · bear call · Label A — घ्यायचा?",
        "📍 Supply 22,544–22,622 (1H) · आत्ता 22,489 (≈55 pts खाली)",
        "📋 Reader: ✓ trend ✓ area ✓ handover(fast) ✓ commitment+volume ✓ 5M CHoCH · + RSI div, confluence",
        '👁 Vision: ✅ सहमत — "Sellers took over inside the 1H supply: a strong red commitment candle closed back below…"',
        "👉 ✅ घ्या · ❌ नको (कारण)   ⏱ 10 मिनिटं (09:55 पर्यंत)"]                    # engine: no ✏️ button ⇒ not offered


def test_summary_engine_label_b_lists_no_confirming_piece():
    cap = VW.v1_caption(ENGINE_B, RES_AGREE, PEND, DL, layout="summary", window_min=10, modify=True)
    t = top5(cap)
    assert t[0] == "🟡 NIFTY · bear call · Label B — घ्यायचा?"
    assert t[1] == "📍 Supply 22,544–22,622 (1H) · आत्ता 22,470 (≈74 pts खाली)"      # no ctx ⇒ the row's own spot
    assert t[2] == "📋 Reader: ✓ trend ✓ area ✓ handover ✓ commitment+volume ✓ 5M CHoCH"   # slow handover ⇒ no "(fast)"; B ⇒ no "+"
    assert t[4] == "👉 ✅ घ्या · ✏️ फक्त entry बदला · ❌ नको (कारण)   ⏱ 10 मिनिटं (09:55 पर्यंत)"


def test_summary_vision_disagree_auto_skip_bots_own_signal():
    cap = VW.v1_caption(OWN, RES_DISAGREE, REJ, None, layout="summary")
    assert top5(cap) == [
        "❌ NIFTY · bear call · entry नाही (Vision असहमत)",
        "📍 Resistance 23,175 (5M) · आत्ता 22,889 (≈286 pts खाली)",
        "📋 Reader: — (bot's own signal)",
        '👁 Vision: "Price is far below the marked resistance and the last candle shows no seller takeover at…"',
        "👉 तुमच्याकडून: काही नाही"]


def test_summary_test_card():
    cap = VW.v1_caption(TEST, RES_DISAGREE, REJ, None, layout="summary")
    t = top5(cap)
    assert t[0] == "❌ NIFTY · bear call · entry नाही (Vision असहमत)   🧪 TEST"
    assert t[2] == "📋 Reader: — (TEST signal, no engine reading)" and t[4] == "👉 तुमच्याकडून: काही नाही"
    dry = VW.v1_caption({**OWN, "setup_json": json.dumps({"tags": {"dry_run": True}})}, RES_DISAGREE, REJ, None, layout="summary")
    assert top5(dry)[0].endswith("   🧪 DRY-RUN")


def test_summary_level_bot_and_manual_and_v0_and_ticket():
    c = cards("summary", window_min=10)
    lb = top5(c["level_bot_pending_nobuttons"])
    assert lb == ["🟡 NIFTY · bear call — घ्यायचा?",
                  "📍 Supply 22,715–22,776 (15M) · entry 22,677 · SL 22,790 · target 22,300 (ref) · आत्ता 22,690 (≈25 pts खाली)",
                  "📋 Reader: — (bot's own signal)", "👁 Vision: ⚪ उपलब्ध नाही", "👉 बटणं नाहीत ⇒ 09:55 ला timeout नियम"]
    mn = top5(c["manual_approved"])
    assert mn[0] == "✅ NIFTY · bear call · entry मंजूर (Vision सहमत) · ✋ manual" and mn[2] == "📋 Reader: — (your manual signal)"
    assert top5(c["v0_notify"])[0] == "ℹ️ NIFTY · bear call · फक्त माहिती (Vision असहमत; bot ने नेहमीप्रमाणे ठरवलं)"
    tk = top5(c["ticket"])
    assert tk[0] == "✏️ NIFTY · bear call · नवी entry 22,600 — पुन्हा घ्यायचा?"
    assert tk[1] == "📍 Supply 22,715–22,776 (15M) · entry 22,600 · SL 22,790 · target 22,300 (ref) · signal वेळी 22,690 (≈25 pts खाली)"
    assert "आत्ता" not in tk[1]                                                 # the ticket's spot is the signal-time spot
    assert tk[4] == "👉 ✅ घ्या · ✏️ entry पुन्हा बदला · ❌ नको (कारण)   ⏱ 10 मिनिटं (10:05 पर्यंत)"


def test_summary_details_are_todays_lines(monkeypatch):
    """Below the SEP: today's detail lines, same text and order (fewer only when the 1024 caption limit needs it — the summary is
    longer than today's two plain lines); Vision's full reason is the last detail line to go."""
    summ = cards("summary", window_min=10)
    monkeypatch.setattr(VW, "_fit", lambda lines, limit=1024, keep=2, protect=None: "\n".join(lines))
    untrimmed = cards(None)                                              # today's card with nothing trimmed
    sep = "\n" + PT.SEP + "\n"
    for k, cap in summ.items():
        det = cap.split(sep, 1)[1].split("\n")
        full = untrimmed[k].split(sep, 1)[1].split("\n")
        if k == "ticket":                                               # a text message: nothing is cut
            assert det == full == CLASSIC_MAIN[k].split(sep, 1)[1].split("\n")
            continue
        assert det[0] == full[0] and det[-1] == full[-1], k              # header and the SL / exits tail kept
        it = iter(full)
        assert all(x in it for x in det), k                              # a subsequence: same lines, same order
        if any(x.startswith("<b>कारण:</b> ") for x in full):
            assert any(x.startswith("<b>कारण:</b> ") for x in det), k  # the full reason survives in the details


def test_summary_fits_telegram_and_never_cuts_the_summary():
    long_reason = {**RES_AGREE, "audits": [{**AUDIT, "reason": "📈 " * 400}]}
    tags = json.loads(LEVEL_BOT["setup_json"])["tags"]
    tags["gate"].update(study="🟡 " * 300, commit_line="✅ " * 300)
    tags.update(manual=True, manual_text="✋ MANUAL " + "🧪" * 200)
    worst = {**LEVEL_BOT, "bot_label": "B" * 200, "setup_json": json.dumps({"tags": tags})}
    for row in (ENGINE_A, ENGINE_B, OWN, TEST, worst):
        for res, d, dl in ((long_reason, PEND, DL), (RES_DISAGREE, REJ, None), (RES_NA, APP, None)):
            cap = VW.v1_caption(row, res, d, dl, layout="summary", window_min=10)
            assert PT.tg_len(cap) <= 1024 - PT.MARGIN and cap.count("<b>") == cap.count("</b>")
            t = top5(cap)
            assert t == CS.lines(row, res, d.status, dl, 10, True, True), (row["signal_id"], d.status)
            assert len(t) == 5 and all(PT.tg_len(x) <= 200 for x in t)
    v0 = VW.caption({**worst, "mode": "notify", "tags": {}}, long_reason, "notify", layout="summary")
    assert PT.tg_len(v0) <= 1024 - PT.MARGIN and len(top5(v0)) == 5
    tk = AP.ticket_text(worst, TICKET, "2026-10-12T10:05:00", 5, layout="summary", window_min=10)
    assert PT.tg_len(tk) <= 4096 and len(top5(tk)) == 5


def test_short_reason_one_line():
    assert CS.short_reason("Sellers took over. RSI lower high.") == "Sellers took over."
    s = CS.short_reason("word " * 60)
    assert len(s) <= CS.REASON_MAX and s.endswith("…") and "\n" not in s
    assert CS.short_reason("  a\nb  ") == "a b" and CS.short_reason(None) == "" and CS.short_reason("") == ""
    assert CS.short_reason("Close 22,544.5 held. Next.") == "Close 22,544.5 held."


# ------------------------------------------------------------------------------------------------ never invented
def _nums(s):
    return set(re.findall(r"\d[\d,]*(?:\.\d+)?", s))


def test_no_invented_numbers():
    """Every number on the summary is an input value (area, level, last price, entry / SL / target, deadline, window, the LTF / TF
    labels) or the distance between the last price and the area — nothing else."""
    for row, res, d, dl in ((ENGINE_A, RES_AGREE, PEND, DL), (ENGINE_B, RES_AGREE, PEND, DL), (OWN, RES_DISAGREE, REJ, None),
                            (TEST, RES_DISAGREE, REJ, None), (LEVEL_BOT, RES_NA, PEND, DL)):
        t = top5(VW.v1_caption(row, {**res, "audits": []}, d, dl, layout="summary", window_min=10))   # Vision's own text aside
        g = (json.loads(row["setup_json"])["tags"].get("gate") or {})
        spot = (row.get("ctx") or {}).get("spot", row.get("spot"))
        vals = [x for x in (g.get("area") or [])] + [row["level"], spot] + [g.get(k) for k in ("entry", "sl", "target")]
        allowed = {f"{float(v):,.0f}" for v in vals if v is not None} | {f"{float(v):,.2f}".rstrip("0").rstrip(".") for v in vals if v is not None}
        lo = min(g["area"]) if g.get("area") else row["level"]
        hi = max(g["area"]) if g.get("area") else row["level"]
        allowed |= {f"{lo - spot:,.0f}", f"{spot - hi:,.0f}", "09", "55", "10", "5", "1", "15"}   # distance · 09:55 · 10 min · 5M / 1H / 15M
        assert _nums("\n".join(t)) <= allowed, (row["signal_id"], _nums("\n".join(t)) - allowed)


def test_missing_values_are_omitted_not_guessed():
    old = top5(VW.v1_caption(ENGINE_OLD, RES_AGREE, PEND, DL, layout="summary"))
    assert old[2] == "📋 Reader: NA (the engine's evidence list is not on this signal)" and "आत्ता" in old[1]
    nospot = top5(VW.v1_caption({**OWN, "spot": None}, RES_DISAGREE, REJ, None, layout="summary"))
    assert nospot[1] == "📍 Resistance 23,175 (5M)"
    nolevel = top5(VW.v1_caption({**OWN, "level": None}, RES_DISAGREE, REJ, None, layout="summary"))
    assert nolevel[1] == "📍 level: NA"
    part = {"evidence_list": {"required": "present", "confirming": {"confluence": "present"}}}             # no ① / ③ / form / ltf
    row = {**ENGINE_B, "setup_json": json.dumps({"tags": {"engine": True, "gate": engine_gate("A", part)}})}
    assert top5(VW.v1_caption(row, RES_AGREE, PEND, DL, layout="summary"))[2] == \
        "📋 Reader: ✓ handover ✓ commitment+volume ✓ LTF CHoCH · + confluence"
    absent = {"trend": True, "area": True, "evidence_list": {"required": "absent", "confirming": {}}, "ltf": "5M"}
    row = {**ENGINE_B, "setup_json": json.dumps({"tags": {"engine": True, "gate": engine_gate("B", absent)}})}
    assert top5(VW.v1_caption(row, RES_AGREE, PEND, DL, layout="summary"))[2] == \
        "📋 Reader: ✓ trend ✓ area ✗ required set (handover / commitment+volume / 5M CHoCH)"
    nod = top5(VW.v1_caption(ENGINE_A, RES_AGREE, PEND, None, layout="summary"))
    assert nod[4] == "👉 ✅ घ्या · ✏️ फक्त entry बदला · ❌ नको (कारण)"                  # no deadline, no window ⇒ no ⏱
    inside = top5(VW.v1_caption({**ENGINE_B, "spot": 22600.0}, RES_AGREE, PEND, DL, layout="summary"))
    assert inside[1].endswith("आत्ता 22,600 (area मध्ये)")


def test_summary_error_falls_back_to_classic(monkeypatch):
    monkeypatch.setattr(CS, "top", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert VW.v1_caption(OWN, RES_DISAGREE, REJ, None, layout="summary") == CLASSIC_MAIN["own_rejected"]
    assert AP.ticket_text(LEVEL_BOT, TICKET, "2026-10-12T10:05:00", 5, layout="summary") == CLASSIC_MAIN["ticket"]


# ------------------------------------------------------------------------------------------------ live wiring: buttons unchanged
@pytest.mark.parametrize("modify", [True, False])
def test_v1_notify_buttons_unchanged_and_layout_from_settings(monkeypatch, modify):
    from vision import store as VS
    from vision import tg as TG
    sent = []
    monkeypatch.setattr(TG, "can_ask", lambda: (True, ""))
    monkeypatch.setattr(TG, "send_photo", lambda png, cap, buttons=None, chat_id=None: (sent.append((cap, buttons)), 5)[1])
    monkeypatch.setattr(VS, "get_signal", lambda sid, path=None: {"deadline": DL})
    monkeypatch.setattr(VS, "update", lambda *a, **k: None)
    monkeypatch.setattr(AP, "base_levels", lambda row: {"sl": 1.0} if modify else None)
    for lay in ("classic", "summary"):
        monkeypatch.setattr(VW.VC, "load", lambda bot, path=None, lay=lay: {**VCF.BOT_DEFAULTS, "approval_card_layout": lay})
        VW.v1_notify(ENGINE_A, RES_AGREE, PEND, b"png", None)
    (c1, b1), (c2, b2) = sent
    assert b1 == b2 and len(b1) == (4 if modify else 3)                          # same buttons, same callbacks
    assert c1 == VW.v1_caption({**ENGINE_A, "deadline": DL}, RES_AGREE, PEND, DL)                  # classic = today
    assert c2.startswith("🟡 NIFTY · bear call · Label A — घ्यायचा?\n")
    assert ("✏️ फक्त entry बदला" in c2) is modify and "⏱ 10 मिनिटं (09:55 पर्यंत)" in c2
    monkeypatch.setattr(VW.VC, "load", lambda bot, path=None: (_ for _ in ()).throw(OSError("db")))
    assert VW.card_settings("x") == ("classic", None)                            # settings unreadable ⇒ today's card


# ------------------------------------------------------------------------------------------------ engine row ⇒ gate tags
def test_engine_reader_facts_are_copied_not_read():
    import engine3_live as EL
    from paper import engine_entry as EE
    r = {"checklist": {"①": [True, "x"], "③": [True, "y"], "⑥": [True, "z"]}, "evidence_list": READER_A["evidence_list"],
         "commit": {"handover_state": {"form": "sharp_reversal", "present": True}, "choch": {"done": True, "label": "5M"}}}
    assert EL.reader_facts(r) == READER_A
    assert EL.reader_facts({}) == {"evidence_list": None, "trend": None, "area": None, "handover_form": None, "ltf": None}
    assert EL.reader_facts(None) is None                                          # never raises
    assert "reader" not in EL._PAYLOAD_DROP                                       # removed silently, never listed as "dropped"
    pay = {"engine": "decision3", "reader": READER_A}
    g = EE.engine_gate_tags({"level_lo": 1.0, "level_hi": 2.0, "grade": "A", "payload": json.dumps(pay)}, "BEARISH")
    assert g["reader"] == READER_A
    g = EE.engine_gate_tags({"level_lo": 1.0, "level_hi": 2.0, "grade": "A", "payload": json.dumps({"reader": "x"})}, "BEARISH")
    assert g["reader"] is None


def _main_fit_payload(payload, limit):
    """origin/main's fit_payload (16203b2), verbatim logic — the reference for 'byte-identical once reader is removed'."""
    import json as _j
    dump = lambda d: _j.dumps(d, ensure_ascii=False, default=str)  # noqa: E731
    out = dump(payload)
    if len(out) <= limit:
        return out
    p, dropped = dict(payload), []
    for k in ("checklist", "zone_read", "watch_list", "flip_context", "trend_notes", "level", "risk"):
        if k in p:
            p.pop(k)
            dropped.append(k)
            out = dump({**p, "dropped": dropped})
            if len(out) <= limit:
                return out
    keep = {k: payload.get(k) for k in ("engine", "ts", "bar_end", "data_problem")}
    keep["volume_measure"] = str(payload.get("volume_measure") or "")[:500]
    return dump({**keep, "dropped": "all context (payload too large)"})


def test_payload_cap_drops_reader_silently_and_keeps_mains_bytes():
    """Near the 20 KB cap: with the reader the payload is too long, without it main's payload fits / is cut exactly as main cuts it —
    the reader goes first and silently (no longer "dropped" list that could push out an extra context key main keeps)."""
    import engine3_live as EL
    base = {"engine": "decision3", "ts": "t", "bar_end": "b", "data_problem": None, "volume_measure": "v",
            "checklist": {"⑥": [True, "x" * 3000]}, "zone_read": {"z": "y" * 4000}, "watch_list": [{"lo": 1.0}],
            "flip_context": None, "trend_notes": ["n"], "level": {"id": 7}, "risk": None}
    main_len = len(json.dumps(base, ensure_ascii=False, default=str))
    reader = {**READER_A, "pad": "r" * 600}
    full = {**base, "reader": reader}
    full_len = len(json.dumps(full, ensure_ascii=False, default=str))
    edges = [full_len, full_len - 1, main_len, main_len - 1, main_len - 3000, main_len - 7000, 50]
    for lim in edges:
        got = EL.fit_payload(full, lim)
        if lim >= full_len:                                                    # fits ⇒ the reader stays
            assert json.loads(got)["reader"] == reader
            continue
        assert got == _main_fit_payload(base, lim), lim                         # byte-identical to main without the reader
        assert "reader" not in got
    with_drop = EL.fit_payload(full, main_len - 1)                              # one char short: main drops only checklist
    assert json.loads(with_drop)["dropped"] == ["checklist"]
