"""tests/test_level_bots_visibility.py — L5 (Abhi §5): level bots चे आजचे areas (dashboard table) + bot-निहाय दैनिक सारांश. DB / network नाही.
hit_type खऱ्या bots प्रमाणे: 5M Instant / MCX "CONFIRMED", 15M SRv2 / Classic "CONFIRMATION"."""
import json

import pandas as pd
import pytest

from bots_common import level_gate_bot as LGB
from bots_common import level_reaction as LR
from bots_common import level_visibility as LV

DAY = "2026-10-12"
W = "[GATE] Watching supply 22,570–22,640 · price arrived · waiting for a bearish commitment · 1/8 bars"
INSTANT_HIT, SRV2_HIT, CLASSIC_HIT, MCX_HIT = "CONFIRMED", "CONFIRMATION", "CONFIRMATION", "CONFIRMED"


def row(t, lt, px, status, hit="NO_HIT", reason="", symbol=None):
    r = {"signal_time": f"{DAY} {t}:00", "level_type": lt, "level_price": px, "hit_type": hit, "direction": "NONE",
         "ltp_at_signal": None, "trade_status": status, "reason": reason}
    if symbol:
        r["symbol"] = symbol
    return r


R1, S1 = "DYNAMIC_SR_RESISTANCE_1M", "DYNAMIC_SR_SUPPORT_1M"


def instant_rows():
    """5M Instant चे 1M levels (hit_type "CONFIRMED")."""
    return [
        # A: armed → absorption → waiting → CONFIRMED (OPENED) ⇒ confirmed; मधलं absorption ignored मध्ये नाही. मग area सोडली → against trend
        row("09:20", R1, 22600.0, "SKIPPED_GATE_NOT_AT_AREA"), row("09:30", R1, 22600.0, "SKIPPED_GATE_WAITING_COMMITMENT", reason=W),
        row("09:40", R1, 22600.0, "SKIPPED_GATE_ABSORPTION"), row("09:50", R1, 22600.0, "SKIPPED_GATE_WAITING_COMMITMENT"),
        row("10:00", R1, 22600.0, "OPENED (trade_id=T1)", hit=INSTANT_HIT), row("10:05", R1, 22600.0, "SKIPPED_GATE_ALREADY_CONFIRMED"),
        row("10:30", R1, 22600.0, "SKIPPED_GATE_NOT_AT_AREA"), row("11:00", R1, 22600.0, "SKIPPED_GATE_AGAINST_TREND"),
        # B: भेट 1 = waiting ×2 → timeout; भेट 2 = commitment शिवाय area सोडली ⇒ no commitment
        row("09:30", S1, 22400.0, "SKIPPED_GATE_WAITING_COMMITMENT"), row("09:35", S1, 22400.0, "SKIPPED_GATE_WAITING_COMMITMENT"),
        row("10:10", S1, 22400.0, "SKIPPED_GATE_TIMEOUT"), row("10:30", S1, 22400.0, "SKIPPED_GATE_NOT_AT_AREA"),
        row("11:00", S1, 22400.0, "SKIPPED_GATE_WAITING_COMMITMENT"), row("11:20", S1, 22400.0, "SKIPPED_GATE_NOT_AT_AREA"),
        # C: area मध्ये hysteresis ने role उलटला (SUPPORT → RESISTANCE) — तीच भेट; दिवस संपताना अजून वाट ⇒ no commitment (एकदाच)
        row("14:00", S1, 22300.0, "SKIPPED_GATE_WAITING_COMMITMENT"), row("14:05", R1, 22300.0, "SKIPPED_GATE_WAITING_COMMITMENT"),
        # D: impulsive → broken (शेवटचं कारण broken); मग उलट भूमिकेत (flip) retest ⇒ नवी भेट, confirmed पण max hits
        row("12:00", R1, 22800.0, "SKIPPED_GATE_IMPULSIVE"), row("12:30", R1, 22800.0, "SKIPPED_GATE_BROKEN"),
        row("13:00", S1, 22800.0, "SKIPPED_GATE_WAITING_COMMITMENT"), row("13:15", S1, 22800.0, "SKIPPED_MAX_2_HITS_REACHED", hit=INSTANT_HIT),
        # E: absorption चालू असतानाच area सोडली ⇒ शेवटचं कारण absorption
        row("12:00", S1, 22200.0, "SKIPPED_GATE_WAITING_COMMITMENT"), row("12:10", S1, 22200.0, "SKIPPED_GATE_ABSORPTION"),
        row("12:20", S1, 22200.0, "SKIPPED_GATE_NOT_AT_AREA"),
        # gate ची नसलेली row (touch mode) ⇒ दुर्लक्ष
        row("09:15", S1, 22100.0, None),
    ]


def other_rows():
    return [
        # 15M SRv2 (साधा SUPPORT / RESISTANCE, index): low volume → R:R (शेवटचं R:R) ; दुसरा area CONFIRMATION (OPENED)
        row("10:00", "SUPPORT", 22200.0, "SKIPPED_GATE_LOW_VOLUME"), row("10:15", "SUPPORT", 22200.0, "SKIPPED_GATE_RR"),
        row("10:00", "RESISTANCE", 22900.0, "SKIPPED_GATE_WAITING_COMMITMENT"), row("10:15", "RESISTANCE", 22900.0, "OPENED", hit=SRV2_HIT),
        # 5M (Instant + Classic एकत्र) : error ; 15M Classic : trend unclear, आणि एक CONFIRMATION
        row("09:16", "DYNAMIC_SR_SUPPORT_5M", 22450.0, "SKIPPED_GATE_ERROR"),
        row("09:16", "DYNAMIC_SR_SUPPORT_15M", 22350.0, "SKIPPED_GATE_NO_TREND"),
        row("11:00", "DYNAMIC_SR_RESISTANCE_15M", 22950.0, "OPENED", hit=CLASSIC_HIT),
    ]


def mcx_rows():
    """MCX (CRUDEOIL) — साधा SUPPORT / RESISTANCE पण symbol MCX ⇒ SRv2 मध्ये नाही."""
    return [
        row("15:00", "SUPPORT", 995.0, "SKIPPED_GATE_WAITING_COMMITMENT", symbol="CRUDEOIL"),
        row("15:15", "SUPPORT", 995.0, "SKIPPED_GATE_SL_TOO_WIDE", hit=MCX_HIT, symbol="CRUDEOIL"),
        row("16:00", "RESISTANCE", 1095.0, "OPENED (trade_id=M1)", hit=MCX_HIT, symbol="CRUDEOIL"),
        row("16:01", "RESISTANCE", 1095.0, "SKIPPED_GATE_CONFIRM_USED", hit=MCX_HIT, symbol="CRUDEOIL"),
    ]


def _nosym(rows):
    return [{k: v for k, v in r.items() if k != "symbol"} for r in rows]


def all_rows():
    return instant_rows() + other_rows() + mcx_rows()


def test_summarize_counts_final_reason_per_visit():
    s = LV.summarize(LV.group_rows(all_rows(), ("1M",)))
    assert (s["armed"], s["confirmed"]) == (7, 2)                          # A, B×2, C (role flip ⇒ एकच), D×2, E
    assert s["entry_statuses"] == {"OPENED (trade_id=T1)": 1, "SKIPPED_MAX_2_HITS_REACHED": 1}
    assert dict(s["ignored"]) == {"against_trend": 1, "timeout": 1, "no_commitment": 2, "broken": 1, "absorption": 1}
    v2 = LV.summarize(LV.group_rows(all_rows(), None))
    assert (v2["armed"], v2["confirmed"], dict(v2["ignored"])) == (2, 1, {"rr": 1})        # low volume शेवटचं नाही ⇒ मोजत नाही
    assert dict(LV.summarize(LV.group_rows(all_rows(), ("5M",)))["ignored"]) == {"error": 1}
    c15 = LV.summarize(LV.group_rows(all_rows(), ("15M",)))
    assert (c15["confirmed"], dict(c15["ignored"])) == (1, {"trend_unclear": 1})
    m = LV.summarize(LV.group_rows(all_rows(), None, "mcx"))
    assert (m["armed"], m["confirmed"]) == (2, 2)
    assert m["entry_statuses"] == {"SKIPPED_GATE_SL_TOO_WIDE": 1, "OPENED (trade_id=M1)": 1}
    assert dict(m["ignored"]) == {"sl_too_wide": 1}                       # confirmed पण gate ने entry थांबवली


@pytest.mark.parametrize("hit", ["CONFIRMED", "CONFIRMATION"])
def test_both_confirmed_hit_types_count_as_confirmed(hit):
    rows = [row("10:00", S1, 22400.0, "SKIPPED_GATE_WAITING_COMMITMENT"), row("10:05", S1, 22400.0, "OPENED", hit=hit),
            row("10:30", S1, 22400.0, "SKIPPED_GATE_NOT_AT_AREA")]
    s = LV.summarize(rows)
    assert (s["armed"], s["confirmed"], sum(s["ignored"].values())) == (1, 1, 0)
    assert LV.area_table(rows[:2], "1m_instant")[0]["State"] == "✅ confirmed"


@pytest.mark.parametrize("lt", [S1, R1])
def test_absorption_then_confirmed_is_not_ignored_mirror(lt):
    """a2 absorption / low volume मधे आले पण भेट CONFIRMED ⇒ ignored नाही (दोन्ही roles)."""
    rows = [row("10:00", lt, 1000.0, "SKIPPED_GATE_ABSORPTION"), row("10:05", lt, 1000.0, "SKIPPED_GATE_LOW_VOLUME"),
            row("10:10", lt, 1000.0, "OPENED", hit=INSTANT_HIT)]
    s = LV.summarize(rows)
    assert (s["armed"], s["confirmed"], dict(s["ignored"])) == (1, 1, {})


def _getlog(rows_by_sym):
    def get(sym, day):
        assert day == DAY
        return pd.DataFrame(rows_by_sym.get(sym, []), columns=list(row("09:15", R1, 1.0, None)))
    return get


def test_summary_text_per_bot_with_touch_legacy_and_mcx():
    wh = [{"bot": "dynamic_sr_instant_touch_legacy", "ts": f"{DAY} 10:00:00"},
          {"bot": "dynamic_sr_instant_touch_legacy", "ts": f"{DAY} 10:05:00"},
          {"bot": "srv2_momentum_reversal_touch_legacy", "ts": f"{DAY} 11:00:00"},
          {"bot": "mcx_futures_touch_legacy", "ts": f"{DAY} 16:00:00"},
          {"bot": "classic_sr_reversal_touch_legacy", "ts": "2026-10-09 11:00:00"},              # दुसरा दिवस
          {"bot": "classic_sr_reversal_touch_legacy", "ts": f"{DAY} 11:00:00", "dry_run": 1},    # dry-run
          {"bot": "dynamic_sr_instant", "ts": f"{DAY} 11:00:00"}]                                 # touch-legacy नाही
    txt = LV.summary_text(DAY, get_log=_getlog({"NIFTY": instant_rows() + other_rows(), "CRUDEOIL": _nosym(mcx_rows())}), wh_rows=wh,
                          mcx=("CRUDEOIL",))
    lines = txt.splitlines()
    assert "NIFTY/BANKNIFTY/SENSEX/CRUDEOIL" in lines[0]
    inst = next(x for x in lines if x.startswith("• 5M Instant"))
    assert "armed 7" in inst and "confirmed 2 (" in inst and "ignored 6" in inst
    assert "no commitment 2" in inst and "against trend 1" in inst and "absorption 1" in inst and "timeout 1" in inst
    assert "armed 2 · confirmed 1 (OPENED 1) · ignored 1: R:R &lt; min 1" in next(x for x in lines if x.startswith("• 15M SRv2"))
    m = next(x for x in lines if x.startswith("• MCX Futures"))
    assert "armed 2 · confirmed 2" in m and "SL too wide 1" in m
    assert "error 1" in txt and "trend unclear 1" in txt
    assert "👻 touch-legacy would-have: Instant 2 · Classic 0 · SRv2 1 · MCX 1" in txt


def test_summary_text_empty_data():
    txt = LV.summary_text(DAY, get_log=_getlog({}), wh_rows=[], mcx=("CRUDEOIL",))
    assert txt.count("armed 0 · confirmed 0 · ignored 0: —") == len(LV.GROUPS)
    assert "Instant 0 · Classic 0 · SRv2 0 · MCX 0" in txt and "NA" not in txt
    assert "कुठलाही commodity सक्रिय नाही" in LV.summary_text(DAY, get_log=_getlog({}), wh_rows=[], mcx=())


def test_summary_text_db_error_says_na_and_rest_still_sends():
    txt = LV.summary_text(DAY, get_log=lambda s, d: None, wh_rows=[{"bot": "classic_sr_reversal_touch_legacy", "ts": f"{DAY} 10:00"}],
                          mcx=("GOLD",))
    assert "gate आकडे: NA (signal log NIFTY वाचता आला नाही" in txt and "MCX gate आकडे: NA (signal log GOLD" in txt and "Classic 1" in txt

    def boom(sym, day):
        raise RuntimeError("db down")

    class BadRows:
        def __iter__(self):
            raise OSError("journal locked")
    txt = LV.summary_text(DAY, get_log=boom, wh_rows=BadRows(), mcx=())
    assert "gate आकडे: NA (RuntimeError: db down)" in txt and "touch-legacy would-have: NA (OSError: journal locked)" in txt


def test_mcx_symbols_from_settings_only():
    on = {"CRUDEOIL", "GOLD"}
    assert LV.mcx_symbols(lambda key, s: {"symbol_enabled": s in on}) == ("CRUDEOIL", "GOLD")

    def bad(key, s):
        raise RuntimeError("db")
    assert LV.mcx_symbols(bad) == ()


def test_daily_summary_script_one_message_carries_both(monkeypatch):
    from scripts import paper_daily_summary as S
    from vision import approval as AP
    monkeypatch.setattr(AP, "daily_summary_text", lambda day=None, *a, **k: f"🗓 PAPER {day}")
    sent = []
    assert S.main(["--day", DAY], send=sent.append, level=lambda d: f"🎯 LEVEL {d}") == 0
    assert len(sent) == 1 and f"🗓 PAPER {DAY}" in sent[0] and f"🎯 LEVEL {DAY}" in sent[0]
    from bots_common import level_visibility

    def bad(day):
        raise ValueError("<x>")
    monkeypatch.setattr(level_visibility, "summary_text", bad)
    sent.clear()
    assert S.main(["--day", DAY], send=sent.append) == 0
    assert "🗓 PAPER" in sent[0] and "Level bots — confirmation gate: NA (ValueError: &lt;x&gt;)" in sent[0]   # HTML escape


def test_daily_summary_send_false_is_nonzero(monkeypatch):
    from scripts import paper_daily_summary as S
    from vision import approval as AP
    monkeypatch.setattr(AP, "daily_summary_text", lambda day=None, *a, **k: "🗓 PAPER")
    assert S.main(["--day", DAY], send=lambda t: False, level=lambda d: "🎯") == 1
    assert S.main(["--day", DAY], send=lambda t: True, level=lambda d: "🎯") == 0


def test_daily_summary_capped_at_4096_never_drops_approvals(monkeypatch):
    from scripts import paper_daily_summary as S
    from vision import approval as AP
    appr = "🗓 PAPER\n" + "a" * 1000
    monkeypatch.setattr(AP, "daily_summary_text", lambda day=None, *a, **k: appr)
    gate = "🎯 <b>Level bots</b>\n" + "\n".join(f"• line {i} <b>x</b> " + "g" * 80 for i in range(100))
    sent = []
    assert S.main(["--day", DAY], send=sent.append, level=lambda d: gate) == 0
    assert len(sent[0]) <= 4096 and sent[0].startswith(appr) and sent[0].endswith("\n…")
    assert sent[0].count("<b>") == sent[0].count("</b>")                    # ओळी-निहाय ⇒ अर्धवट tag नाही
    assert S.combine("x", "short") == "x\n\nshort"


def test_area_table_newest_per_area_armed_first_and_bars_estimate():
    rows = all_rows() + [row("13:00", "DYNAMIC_SR_RESISTANCE_5M", 22610.0, "SKIPPED_GATE_WAITING_COMMITMENT", reason=W)]
    t = LV.area_table(pd.DataFrame(rows), "1m_instant", now=f"{DAY} 13:12:00", tf_minutes=5)
    levels = [x["Level"] for x in t]
    assert "15M SUPPORT 22,350.00" not in levels and "SUPPORT 22,200.00" not in levels and "SUPPORT 995.00" not in levels
    assert t[0]["State"].startswith("🟡") and t[0]["Level"] in ("5M RESISTANCE 22,610.00", "1M RESISTANCE 22,300.00")
    w5 = next(x for x in t if x["Level"] == "5M RESISTANCE 22,610.00")
    assert w5["Gate"].startswith("Watching supply 22,570–22,640") and "~3/8 bars" in w5["Gate"] and w5["Since"] == "13:00"
    assert next(x for x in t if x["Level"] == "1M RESISTANCE 22,600.00")["Status"] == "SKIPPED_GATE_AGAINST_TREND"   # सर्वात नवी नोंद
    assert [x["Level"] for x in t if "22,300" in x["Level"]] == ["1M RESISTANCE 22,300.00"]   # role उलटला ⇒ एकच ओळ (जुनी "armed" नाही)
    assert next(x for x in t if "22,800" in x["Level"])["State"] == "✅ confirmed"
    assert all(x["Status"] != "SKIPPED_GATE_NOT_AT_AREA" for x in LV.area_table(rows, "1m_instant", include_idle=False))
    srv2 = LV.area_table(rows, "15m_dynamic_sr")
    assert [x["Level"] for x in srv2] == ["RESISTANCE 22,900.00", "SUPPORT 22,200.00"] and srv2[1]["State"] == "⛔ R:R < min"
    assert [x["Level"] for x in LV.area_table(rows, "classic_sr_reversal")] == [
        "5M RESISTANCE 22,610.00", "15M RESISTANCE 22,950.00", "15M SUPPORT 22,350.00", "5M SUPPORT 22,450.00"]
    mcx = LV.area_table(_nosym(mcx_rows()), "mcx_futures", symbol="CRUDEOIL")
    assert [(x["Level"], x["Status"]) for x in mcx] == [("RESISTANCE 1,095.00", "SKIPPED_GATE_CONFIRM_USED"),
                                                        ("SUPPORT 995.00", "SKIPPED_GATE_SL_TOO_WIDE")]
    assert LV.area_table(mcx_rows(), "15m_dynamic_sr") == []                 # MCX rows SRv2 मध्ये नाहीत
    assert LV.area_table(_nosym(other_rows()), "mcx_futures", symbol="CRUDEOIL") != [] and \
        LV.area_table(_nosym(other_rows()), "mcx_futures", symbol="NIFTY") == []


@pytest.mark.parametrize("empty", [None, [], pd.DataFrame()])
def test_area_table_handles_empty(empty):
    assert LV.area_table(empty, "1m_instant", now=f"{DAY} 10:00:00") == []


def test_armed_absorption_and_low_volume_get_own_status_and_line():
    base = {"state": LR.ARMED, "side": LR.BEAR, "area": (22570.0, 22640.0), "bars_armed": 3, "max_armed_bars": 8, "reason": LR.R_NO_COMMIT}
    assert LGB.status_of(base) == "SKIPPED_GATE_WAITING_COMMITMENT"
    assert LGB.status_of({**base, "absorbing": True, "low_volume": True}) == "SKIPPED_GATE_ABSORPTION"
    lv = LGB.skip_fields({**base, "low_volume": True})
    assert lv["trade_status"] == "SKIPPED_GATE_LOW_VOLUME" and lv["reason"].endswith("3/8 bars · commitment on low volume")
    assert LR.describe(base) == "Watching supply 22,570–22,640 · price arrived · waiting for a bearish commitment · 3/8 bars"
    assert LV.category({"trade_status": LGB.status_of({**base, "absorbing": True})}) == "absorption"


def test_confirm_tf_setting_falls_back_to_bot_default():
    assert LGB.confirm_tf("mcx", {}) == 15 and LGB.confirm_tf("mcx", {"confirm_tf_minutes": 10}) == 15
    assert LGB.confirm_tf("classic_sr", {"confirm_tf_minutes": "15"}) == 15 and LGB.confirm_tf("classic_sr", {"confirm_tf_minutes": 7}) == 5
    assert LGB.confirm_tf("srv2", {"confirm_tf_minutes": "abc"}) == 15


def test_trend_from_cache_reads_files_only(tmp_path):
    assert LV.trend_from_cache("NIFTY", DAY, cache_dir=str(tmp_path)) is None
    ctx = {"ok": True, "trend": "DOWN", "sides": [LR.BEAR], "reason": "Daily DOWN", "protected": 23010.5, "asof": "2026-10-09"}
    open(LR._cache_path("NIFTY", DAY, str(tmp_path)), "w", encoding="utf-8").write(json.dumps(ctx))
    got = LV.trend_from_cache("NIFTY", DAY, cache_dir=str(tmp_path))
    assert got["trend"] == "DOWN"
    assert LV.trend_text(got) == "Daily DOWN · as of 2026-10-09 · protected 23,010 · entries: bearish (supply)"
    assert LV.trend_from_cache("NIFTY", DAY, cache_dir=str(tmp_path), allow_parent=True) is None             # _a1 वेगळी file
    assert "NO NEW ENTRIES" in LV.trend_text({"ok": False, "reason": "no entry: trend unclear (Daily NEUTRAL)", "sides": []})
    # negative cache ("_fail") ⇒ ok False; MCX ⇒ contract च्या नावाची file
    fail = {"at": 1.0, "ctx": {"ok": False, "trend": "UNKNOWN", "sides": [], "reason": "gate error (fail-closed): trend — Timeout"}}
    open(LR._cache_path("CRUDEOIL FUT 19 NOV 26", DAY + "_fail", str(tmp_path)), "w", encoding="utf-8").write(json.dumps(fail))
    assert LV.trend_from_cache("CRUDEOIL", DAY, cache_dir=str(tmp_path)) is None
    got = LV.trend_from_cache("CRUDEOIL", DAY, cache_dir=str(tmp_path), contract=True)
    assert got["ok"] is False and "Timeout" in got["reason"] and "NO NEW ENTRIES" in LV.trend_text(got)


def _page_app():
    from unittest.mock import patch
    import builtins
    import streamlit as st
    import cloud_db
    page = __import__(builtins._L5_PAGE)
    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("token_input", "")
    st.session_state.setdefault("product_type", "D")
    with patch.object(cloud_db, "get_signal_log", side_effect=lambda sym, day: builtins._L5_LOG):
        page.render()


def _today(rows):
    now = pd.Timestamp.now().strftime("%Y-%m-%d")
    return pd.DataFrame([{**r, "signal_time": r["signal_time"].replace(DAY, now)} for r in _nosym(rows)])


@pytest.mark.parametrize("log", ["rows", "empty", "none"])
def test_page_renders_areas_tab_without_exception(log):
    import builtins
    from streamlit.testing.v1 import AppTest
    builtins._L5_PAGE = "page_bot_dynamic_sr_algo"
    builtins._L5_LOG = {"rows": _today(instant_rows()), "empty": pd.DataFrame(), "none": None}[log]
    at = AppTest.from_function(_page_app, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    if log == "rows":
        df = at.dataframe[-1].value
        assert "Gate" in df.columns and any("against trend" in s or "armed" in s for s in df["State"])
    if log == "none":
        assert any("Signal log वाचता आला नाही" in w.value for w in at.warning)


def test_mcx_page_renders_areas_tab_without_exception():
    import builtins
    from streamlit.testing.v1 import AppTest
    builtins._L5_PAGE = "page_mcx_futures"
    builtins._L5_LOG = _today(mcx_rows())
    at = AppTest.from_function(_page_app, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    frames = [d.value for d in at.dataframe if isinstance(d.value, pd.DataFrame) and "Gate" in d.value.columns]
    assert frames and "SKIPPED_GATE_CONFIRM_USED" in set(frames[-1]["Status"])
