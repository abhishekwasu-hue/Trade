"""DECISIONS 52 / 53 (Abhi, layer 6 gallery answers L6-O4, O10, O11, O13): the ENGINE-ENTRY Vision card (signal_source = engine: tags
engine + entry_model).

  O-4  the caption is short bullets (the key fields, never cut by the 1024 limit); the full details (5M trigger, evidence, invalidation)
       go as a reply threaded under the card's message id; the ✅ / ❌ buttons stay on the card; the reply works with Vision NA.
  O-13 the 5M trigger is its own panel beside the 15M panel on the engine card (no inset over the 15M chart).
  BW-1 no "merged band — check" line for engine areas (`approval_band_warn_rule = method`, default); `width` = the earlier line.
  VP3  no "grade cap B": missing FUT volume is "FUT volume missing — E2 cannot be read".
Every other card (level bots, own / manual / TEST, an engine row without an entry model) stays byte-identical (pinned below and in
tests/test_approval_card_summary.py). Fakes only: no Telegram, no network, no AI."""
import json

import pandas as pd
import pytest

from bots_common import plain_text as PT
from decision3 import volume_pane as VP
from vision import card_summary as CS
from vision import decide as VD
from vision import worker as VW

LONG_RULE = ("price closes above the visit's extreme 56,065.50 (refined base 2026-09-25 14:00) and forms a swing high beyond it — the "
             "structural invalidation of the refined 15M base, read at the trigger as the current state of the area, never the 5M "
             "candle's own extreme")
PA = [{"track": f"T{i}", "tf": "1H", "text": f"PA fact {i} " + "x" * 160 + f" (detail {i})"} for i in range(1, 8)]
EVID = [["required set (handover + commitment + volume + LTF CHoCH)", "✓"], ["volume growing inside", "✓"], ["RSI divergence", "✗"],
        ["confluence", "✓"], ["correction line closed through", "NA"],
        ["counter channel broken in the trade direction (handover evidence; context)", "✗"]]
TRIG = {"tf": "5M", "ts": "2026-10-16 09:15:00", "bar_end": "2026-10-16 09:20:00",
        "ohlc": {"open": 55927.15, "high": 55989.55, "low": 55656.7, "close": 55663.55}, "volume": 32940.0,
        "context_bar_ts": "2026-10-15 15:15:00", "bar15_ts": "2026-10-16 09:15:00", "visit_start5": "2026-10-15 10:10:00",
        "facts": {"form": "strong_close"}}


def tags(**kw):
    t = {"engine": True, "engine_bar": "2026-10-16 09:20:00", "entry_model": "E2", "entry_name": "Confirmation",
         "entry_label": "E2 — Confirmation", "entry_visit": "280@2026-10-15 10:00:00", "entry_area_id": 280, "entry_object": "area",
         "entry_trigger_ts": "2026-10-16 09:15:00", "entry_ref": 55663.55, "entry_invalidation": {"price": 56065.5, "rule": LONG_RULE},
         "entry_evidence": EVID, "entry_pa_evidence": PA, "entry_trigger_tf": "5M", "entry_trigger": TRIG,
         "gate": {"mode": "engine", "side": "BEARISH", "area": [55699.45, 55970.15], "grade": "A", "tf": "15M", "trend": "DOWN",
                  "band_warn_pts": 150.0, "band_warn_rule": "method", "htf": {"weekly": "UP", "daily": "DOWN", "daily_phase": "impulse"},
                  "refined": {"lo": 55699.45, "hi": 55762.6, "ts": "2026-09-25 14:00:00"},
                  "areas": [{"id": "280", "tf": "1H", "role": "resistance", "lo": 55699.45, "hi": 55970.15, "state": "FLIPPED"}],
                  "next_area": {"id": "297", "tf": "1H", "role": "support", "lo": 55284.15, "hi": 55340.7, "state": "FLIPPED"}}}
    t.update(kw)
    return t


def row(t=None, **kw):
    t = tags() if t is None else t
    r = {"signal_id": "s6", "bot": "srv2_momentum_reversal", "bot_label": "Price-action engine (PAPER)", "symbol": "BANKNIFTY",
         "direction": "BEARISH", "level": 55834.8, "role": "Resistance", "setup_tf": "15M", "signal_ts": "2026-10-16T09:20:00",
         "mode": "human_confirm", "spot": 55663.55, "setup_json": json.dumps({"tags": t}, ensure_ascii=False), "tags": t,
         "volume_line": "volume: NA (grade cap B)"}
    r.update(kw)
    return r


LONG_REASON = ("Sellers took over inside the 1H supply after a sharp two-candle turn and the 5M commitment candle closed back below "
               "the refined base on rising FUT volume. " + "The structure below is clean. " * 40)
RES_AGREE = {"verdict": "agree", "confidence": 0.82, "verdicts": ["agree"], "audits": [{"reason": LONG_REASON}]}
RES_NA = {"verdict": "unavailable", "error": "budget संपलं"}
PEND = VD.Decision("PENDING_HUMAN", 1.0, "human_confirm: your ✅ decides", "REJECTED", 0.0, True)
DL = "2026-10-16T09:31:00"


@pytest.fixture(autouse=True)
def _engine_line(monkeypatch):
    monkeypatch.setattr(VW, "engine_line", lambda r: "engine: NA (shadow)")   # the engine store is not read here


def plain(s):
    import html
    import re
    return html.unescape(re.sub(r"<[^>]+>", "", s))


# ------------------------------------------------------------------------------------------------ O-4 the short caption
@pytest.mark.parametrize("res", [RES_AGREE, RES_NA])
def test_caption_is_short_and_keeps_every_key_field(res):
    cap = VW.v1_caption(row(), res, PEND, DL, approval=True)
    p = plain(cap)
    lines = p.split("\n")
    assert PT.tg_len(cap) <= 1024 - PT.MARGIN                                     # never cut: no key field dropped or shortened
    assert not any("…" in x for x in lines if not x.startswith("• Vision"))       # (Vision's reason: its first sentence; full in the reply)
    assert lines[0] == "🎯 BANKNIFTY · bear call · E2 — Confirmation · label A — decide now"   # line 1: what + the action
    assert lines[1] == "⏱ Decide by 09:31. ✅ take · ❌ skip. No reply ⇒ skipped."
    for want in ("• Trend: DOWN (Daily DOWN, impulse · Weekly UP)",
                 "• Area: supply 55,699–55,970 (1H, flipped) · refined base 55,699–55,763",
                 "• Trigger 5M: E2 candle 09:15–09:20, traded into the refined base ✓, close 55,663.55",
                 "• Invalidation (info): 56,065.5 · trade SL / target = dashboard",
                 "• Next area: demand 55,284–55,341 (1H)",
                 "• Evidence ✓: required set · volume growing inside · confluence",
                 "• FUT volume missing — E2 cannot be read",
                 VW.DETAILS_POINTER):
        assert any(x.startswith(want) for x in lines), want
    assert ("• Vision: ✅ सहमत (0.82) — \"Sellers took over" in p) if res is RES_AGREE else ("• Vision: NA (budget संपलं)" in p)
    assert "merged band" not in p and "grade cap" not in p and PT.SEP not in p    # DECISIONS 53 (BW-1, VP3)
    assert LONG_RULE[:60] not in p and "PA fact" not in p                          # the details are the reply's


def test_caption_layouts_and_decisions():
    assert VW.v1_caption(row(), RES_AGREE, PEND, DL, layout="summary") == VW.v1_caption(row(), RES_AGREE, PEND, DL)
    app = VW.v1_caption(row(), RES_AGREE, VD.Decision("APPROVED", 1.0, "auto_veto: agree"), None)
    assert plain(app).split("\n")[0].endswith("— entry approved automatically") and "ENTRY मंजूर" in app
    rej = VW.v1_caption(row(), RES_AGREE, VD.Decision("REJECTED", 0.0, "vision disagree"), None)
    assert plain(rej).split("\n")[0].endswith("— entry rejected automatically") and "ENTRY नाकारली" in rej
    nob = VW.v1_caption(row(), RES_NA, PEND, DL, buttons=False, why="no approver", approval=True)
    assert "Buttons unavailable: no approver" in nob and PT.tg_len(nob) <= 1024
    test = VW.v1_caption(row(tags(test_only=True)), RES_AGREE, PEND, DL)
    assert test.startswith("🧪 TEST — not a trade · 🎯")
    nolab = tags()
    nolab["gate"] = {**nolab["gate"], "grade": None}                               # the label as the tags carry it (none ⇒ none)
    assert plain(VW.v1_caption(row(nolab), RES_AGREE, PEND, DL)).split("\n")[0] == \
        "🎯 BANKNIFTY · bear call · E2 — Confirmation — decide now"
    old = tags()
    old["gate"] = {k: v for k, v in old["gate"].items() if k != "next_area"}       # an older row without the engine's next area
    assert "Next area" not in VW.v1_caption(row(old), RES_AGREE, PEND, DL)
    none = tags()
    none["gate"] = {**none["gate"], "next_area": None}
    assert "• Next area: none known" in VW.v1_caption(row(none), RES_AGREE, PEND, DL)
    full = VW.v1_caption(row(volume_line="volume: counter-side candles 0.7× → trend-side 1.4× · commitment 1.6× avg"), RES_AGREE, PEND, DL)
    assert "FUT volume missing" not in full


def test_caption_of_a_line_object_says_line():
    t = tags(entry_model="E4", entry_name="Sweep-retest (b)", entry_label="E4 (b) — Sweep-retest", entry_object="broken_line",
             entry_line={"tf": "1H", "family": "rising line of lows", "break_side": "down", "value": 55710.0})
    t["gate"] = {**t["gate"], "area": [55710.0, 55710.0], "refined": None}
    p = plain(VW.v1_caption(row(t), RES_AGREE, PEND, DL))
    assert "• Object: broken 1H line at 55,710 (rising line of lows, broken down), retest from below" in p
    assert "at the retested object ✓" in p and "Supply" not in p and "supply 55,710" not in p


# ------------------------------------------------------------------------------------------------ O-4 the details reply
def test_details_hold_trigger_evidence_invalidation_in_full():
    det = VW.engine_details(row(), RES_NA, PEND)
    p = plain(det)
    assert p.split("\n")[0] == "📎 Details · BANKNIFTY · E2 — Confirmation · bear call (the card above)"
    assert "Trigger 5M: E2 candle 09:15–09:20, traded into the refined base ✓, close 55,663.55; context = last closed 15M bar 15:15" in p
    assert "5M candle: O 55,927.15 H 55,989.55 L 55,656.7 C 55,663.55 · FUT volume 32,940 · inside the 15M bar 09:15" in p
    assert "Visit's first 5M candle: 2026-10-15 10:10" in p and "Model's 5M facts: form strong close" in p
    assert f"invalidation (info): 56,065.5 — {LONG_RULE} · trade SL / target = dashboard" in p          # the rule never shortened
    assert ("📋 E2 — Confirmation evidence (label A): " + CS.evidence_text(EVID, limit=10 ** 6)) in p
    assert all(f"• {r['track']} 1H: {r['text']}" in p for r in PA)                                     # every PA fact, in full
    assert "Area 55,699–55,970 (271 pts) (Resistance, 1H) · signal 09:20" in p and "उपलब्ध नाही" in p and "budget संपलं" in p
    assert "volume: FUT volume missing — E2 cannot be read" in p and "grade cap" not in p and "merged band" not in p
    assert PT.tg_len(det) > 1024                                                   # it would never have fitted in a caption
    parts = VW.details_parts(det)
    assert len(parts) == 1 and parts[0] == det


def test_details_parts_split_at_line_ends():
    text = "\n".join(f"line {i} " + "y" * 300 for i in range(40))
    parts = VW.details_parts(text)
    assert len(parts) > 1 and all(PT.tg_len(x) <= 4096 for x in parts) and "\n".join(parts) == text


# ------------------------------------------------------------------------------------------------ O-4 the reply is threaded, buttons stay
def _notify(monkeypatch, r, res, mid=42):
    from vision import approval as AP
    from vision import store as VS
    from vision import tg as TG
    sent, replies = [], []
    monkeypatch.setattr(TG, "can_ask", lambda: (True, ""))
    monkeypatch.setattr(TG, "send_photo", lambda png, cap, buttons=None, chat_id=None: (sent.append((cap, buttons)), mid)[1])
    monkeypatch.setattr(TG, "reply", lambda message_id, text, chat_id=None: (replies.append((message_id, text)), 77)[1])
    monkeypatch.setattr(VS, "get_signal", lambda sid, path=None: {"deadline": DL})
    monkeypatch.setattr(VS, "update", lambda *a, **k: None)
    monkeypatch.setattr(AP, "base_levels", lambda row: None)
    monkeypatch.setattr(VW.VC, "load", lambda bot, path=None: {**VW.VC.BOT_DEFAULTS})
    out = VW.v1_notify(r, res, PEND, b"png", None)
    return out, sent, replies


@pytest.mark.parametrize("res", [RES_AGREE, RES_NA])
def test_details_reply_threads_under_the_card_and_buttons_stay_on_the_card(monkeypatch, res):
    out, sent, replies = _notify(monkeypatch, row(), res)
    assert out == 42 and len(sent) == 1
    cap, buttons = sent[0]
    from vision import approval as AP
    assert buttons == AP.buttons("s6", False) and any("✅" in b[0] for b in buttons) and any("❌" in b[0] for b in buttons)
    assert PT.tg_len(cap) <= 1024 and VW.DETAILS_POINTER in cap
    assert replies and {m for m, _ in replies} == {42}                            # threaded under the card's message id
    assert all(PT.tg_len(t) <= 4096 for _, t in replies) and (len(replies) > 1) is (res is RES_AGREE)   # the long reason: 2 parts
    assert "Trigger 5M" in replies[0][1] and "evidence (label A)" in replies[0][1] and "invalidation (info)" in replies[0][1]


def test_no_card_no_details_and_never_a_reply_for_other_cards(monkeypatch):
    _out, _sent, replies = _notify(monkeypatch, row(), RES_AGREE, mid=None)        # the card failed ⇒ no orphan details message
    assert replies == []
    lvl = {**row(), "tags": {"gate": {"mode": "confirmation", "area": [22715.0, 22776.0]}},
           "setup_json": json.dumps({"tags": {"gate": {"mode": "confirmation", "area": [22715.0, 22776.0]}}})}
    _out, sent, replies = _notify(monkeypatch, lvl, RES_AGREE)
    assert replies == [] and PT.SEP in sent[0][0]                                  # a level-bot card: today's card, no reply
    eng = {**row(), "tags": {"engine": True, "gate": tags()["gate"]}, "setup_json": json.dumps({"tags": {"engine": True, "gate": tags()["gate"]}})}
    _out, sent, replies = _notify(monkeypatch, eng, RES_AGREE)
    assert replies == [] and PT.SEP in sent[0][0]                                  # an engine row without an entry model: today's card


def test_send_details_never_raises():
    assert VW.send_details(5, row(), RES_NA, reply_fn=lambda m, t: (_ for _ in ()).throw(OSError("tg"))) == []
    assert VW.send_details(None, row(), RES_NA, reply_fn=lambda m, t: 1) == []


# ------------------------------------------------------------------------------------------------ BW-1 the merged-band line
def test_no_merged_band_line_for_engine_areas_under_method():
    p = plain(VW.v1_caption(row(), RES_AGREE, PEND, DL))
    assert "merged band" not in p and VW.band_flag_line(row()) == ""               # 271 pts wide, one base (Z-1u)
    w = tags()
    w["gate"] = {**w["gate"], "band_warn_rule": "width"}                           # the what-if = the earlier line
    pw = plain(VW.v1_caption(row(w), RES_AGREE, PEND, DL))
    assert pw.split("\n")[1] == "⚠️ merged band — check (width 271 pts > 150)" and PT.tg_len(VW.v1_caption(row(w), RES_AGREE, PEND, DL)) <= 1024


# ------------------------------------------------------------------------------------------------ VP3 + O-13 the engine card image
def _engine_fig(vols=None):
    from tests.test_vision_engine_audit import TS, engine_sig
    from tests.test_vision_v2 import bars
    from paper import engine_entry as EE2
    from vision import chart as CH
    df = bars()
    s = engine_sig(df)
    last = float(df[df.timestamp < TS].close.iloc[-1])
    trig = {"tf": "5M", "ts": str(TS - pd.Timedelta(minutes=5)), "bar_end": str(TS), "context_bar_ts": str(TS - pd.Timedelta(minutes=30)),
            "ohlc": {"open": last, "high": last + 4, "low": last - 3, "close": last}, "bar15_ts": str(TS - pd.Timedelta(minutes=15)),
            "visit_start5": str(TS - pd.Timedelta(minutes=40)), "facts": {"choch_level": last - 1}}
    s5 = {**s, "tags": {**s["tags"], **EE2.trigger_tags({"trigger_tf": "5M", "trigger": trig}), "entry_trigger_ts": trig["ts"],
                        "entry_object": "area", "entry_model": "E3"}}
    setup, higher, tfs, cut = CH.panels(df, TS, "15M", return_cut=True)
    meta = {}
    return CH.engine_figure(cut, setup, higher, tfs, s5, {}, vols, meta), meta, (cut, setup, higher, tfs, s)


def test_engine_card_5m_panel_is_its_own_panel_beside_15m():
    fig, meta, (cut, setup, higher, tfs, s15) = _engine_fig()
    lay = fig.layout
    assert meta["trigger_panel"]["tf"] == "5M" and "xaxis9" not in lay.to_plotly_json()   # no inset axes
    d1, d2, d3 = lay.xaxis.domain, lay.xaxis2.domain, lay.xaxis3.domain
    assert d1[1] < d2[0] and d2[1] < d3[0]                                         # setup 15M | trigger 5M | higher: side by side
    assert tuple(lay.yaxis2.domain) == tuple(lay.yaxis.domain)                     # the same height as the 15M panel
    texts = [str(a.text) for a in lay.annotations]
    assert texts[0].startswith("setup 15") and texts[2] == "higher 1H" and texts[1].startswith("trigger 5M · T")
    cands = [t for t in fig.data if t.type == "candlestick"]
    assert sorted({t.xaxis for t in cands}) == ["x", "x2", "x3"]                  # 5M candles drawn on their own axes
    assert "CHoCH 5M" in texts and VP.ENGINE_NA_LINE in texts                      # 5M facts + its FUT volume pane (missing here)
    from vision import chart as CH
    fig15 = CH.engine_figure(cut, setup, higher, tfs, s15, {}, None, {})          # no 5M trigger ⇒ two panels, as before
    assert round(fig15.layout.xaxis2.domain[1], 6) == 1.0 and len([t for t in fig15.data if t.type == "candlestick"]) == 2
    assert not any(str(a.text).startswith("trigger 5M") for a in fig15.layout.annotations)


def test_engine_card_volume_words_no_grade_cap():
    fig, meta, _ = _engine_fig(vols=None)
    texts = [str(a.text) for a in fig.layout.annotations]
    assert not any("grade cap" in t for t in texts) and any(VP.ENGINE_NA_LINE in t for t in texts)
    assert meta["volume_line"] == VP.ENGINE_NA_LINE == "volume: FUT volume missing — E2 cannot be read"   # no FUT volume at all
    assert VP.engine_text(VP.NA_LINE) == VP.engine_text(VP.METHOD_NA_LINE) == VP.ENGINE_NA_LINE
    assert VP.engine_text(VP.NO_OPP_LINE) == "volume: no opposite-side candle in the visit" and VP.engine_text("x") == "x"


def test_level_bot_volume_words_unchanged():
    """Every other chart keeps its words byte for byte (VP3 is the engine-entry card only)."""
    import numpy as np
    from tests.test_vision_v2 import bars
    from vision import chart as CH
    assert VP.NA_LINE == "volume: NA (grade cap B)" and VP.na_line(None) == VP.NA_LINE
    df = bars()
    setup, higher, tfs, cut = CH.panels(df, pd.Timestamp("2026-10-06 11:15"), "15M", return_cut=True)
    st = VP.study(setup, vol=np.full(len(setup), np.nan), symbol="NIFTY")
    assert st["line"] == VP.NA_LINE and "na_text" not in st
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1, cols=1)
    VP.add_plotly(fig, st, row=1, col=1)
    assert [a.text for a in fig.layout.annotations][0] == VP.NA_LINE and isinstance(fig, go.Figure)
