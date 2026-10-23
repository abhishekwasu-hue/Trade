"""Abhi (live): approval संदेश, pre-open आणि 15:45 सारांशात पट्ट्याची रुंदी (pts); रुंदी `approval_band_warn_pts` (default 150) पेक्षा
जास्त ⇒ "⚠️ merged band — check". फक्त दाखवणं — निर्णय / gate / order बदलत नाही. पट्टा नाही ⇒ काहीच जास्त नाही, crash नाही. Network नाही."""
import html
import importlib.util
import json
import os

import pandas as pd

import cloud_db
from bots_common import level_reaction as LR
from bots_common import plain_text as PT
from paper import engine_entry as EE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = "merged band — check"
WIDTH = {"approval_band_warn_rule": "width"}           # DECISIONS 53: the 150-pt line on engine areas = the what-if `width` only


def _load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_bandw", os.path.join(ROOT, "scripts", f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------ helpers
def test_setting_default_and_helpers():
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]["approval_band_warn_pts"] == PT.BAND_WARN_PTS_DEFAULT == 150
    assert PT.band_warn_pts(None) == 150 and PT.band_warn_pts({}) == 150 and PT.band_warn_pts("x") == 150 and PT.band_warn_pts(-5) == 150
    assert PT.band_warn_pts({"approval_band_warn_pts": 300}) == 300 and PT.band_warn_pts("80") == 80
    assert PT.band_range(22622.0, 22544.0) == "22,544–22,622 (78 pts)"
    assert PT.band_flag(22544.0, 22622.0) == ""
    assert PT.band_flag(22300.0, 22750.0) == "⚠️ merged band — check (width 450 pts > 150)"
    assert PT.band_flag(22300.0, 22450.0) == ""                              # = 150 ⇒ जास्त नाही
    assert PT.band_flag(22544.0, 22622.0, 50) == "⚠️ merged band — check (width 78 pts > 50)"   # setting override
    assert PT.band_flag(22300.0, 22750.0, {"approval_band_warn_pts": 500}) == ""
    for missing in ((None, None), (None, 22600.0), ("?", 1.0)):
        assert PT.band_range(*missing) == "" and PT.band_flag(*missing) == "" and PT.band_wide_words(*missing) == ""
    assert PT.band_wide_words(22715.0, 22776.0) == "61 pts wide"
    assert PT.band_wide_words(22300.0, 22750.0) == "450 pts wide ⚠️ merged band — check (over 150 pts)"


def test_engine_gate_tags_carry_setting_display_only():
    r = {"level_lo": 22544.0, "level_hi": 22622.0, "grade": "B"}
    g = EE.engine_gate_tags(r, "BULLISH")
    assert g["band_warn_pts"] == 150 and g["area"] == [22544.0, 22622.0]
    g2 = EE.engine_gate_tags(r, "BULLISH", {"approval_band_warn_pts": 60, "signal_source": "engine"})
    assert g2["band_warn_pts"] == 60
    assert {k: v for k, v in g2.items() if k != "band_warn_pts"} == {k: v for k, v in g.items() if k != "band_warn_pts"}   # फक्त दाखवणं
    assert EE.engine_gate_tags({"level_lo": None, "level_hi": None}, "BEARISH")["area"] is None


# ------------------------------------------------------------------------------------------------ approval caption
def _row(lo, hi, settings=None, direction="BULLISH"):
    gate = EE.engine_gate_tags({"level_lo": lo, "level_hi": hi, "grade": "B"}, direction, settings)
    return {"signal_id": "s1", "bot": "srv2_momentum_reversal", "bot_label": "15M SRv2", "symbol": "NIFTY", "direction": direction,
            "level": 22580.0, "role": "SUPPORT", "setup_tf": "15M", "signal_ts": "2026-10-14T10:15:00", "mode": "human_confirm",
            "setup_json": json.dumps({"tags": {"engine": True, "gate": gate}})}


def _v1(row, monkeypatch):
    from vision import decide as VD
    from vision import worker as VW
    monkeypatch.setattr(VW, "engine_line", lambda r: "engine: NA")
    d = VD.Decision("PENDING_HUMAN", 1.0, "human", "REJECTED", 0.0)
    return VW.v1_caption(row, {"verdict": "agree", "audits": [], "confidence": 0.8}, d, "2026-10-14T10:25:00")


def test_approval_caption_shows_width_no_flag_when_narrow(monkeypatch):
    cap = _v1(_row(22544.0, 22622.0), monkeypatch)
    top, det = cap.split(PT.SEP)
    lines = top.strip("\n").splitlines()
    assert "demand area 22,544–22,622 (78 pts)" in lines[0]
    assert lines[1].replace("<b>", "").startswith(PT.DECISION_APPROVE) and len(lines) == 2
    assert "Area 22,544–22,622 (78 pts)" in det
    assert FLAG not in cap and len(cap) <= 1024


def test_approval_caption_flags_wide_band_after_decision_line(monkeypatch):
    assert FLAG not in _v1(_row(22300.0, 22750.0, direction="BEARISH"), monkeypatch)      # DECISIONS 53: default method
    cap = _v1(_row(22300.0, 22750.0, WIDTH, direction="BEARISH"), monkeypatch)
    lines = PT.first_part(cap).strip("\n").splitlines()
    assert "supply area 22,300–22,750 (450 pts)" in lines[0]
    assert lines[1].replace("<b>", "").startswith(PT.DECISION_APPROVE)          # ओळ 2 = निर्णय (TELEGRAM_CLEANUP आकार तसाच)
    assert html.unescape(lines[2]) == "⚠️ merged band — check (width 450 pts > 150)"
    assert "&gt;" in lines[2] and ">" not in lines[2].replace("&gt;", "")        # Telegram HTML सुरक्षित
    assert len(cap) <= 1024


def test_approval_caption_setting_override(monkeypatch):
    wide_ok = _v1(_row(22300.0, 22750.0, {"approval_band_warn_pts": 500}), monkeypatch)
    assert FLAG not in wide_ok and "(450 pts)" in wide_ok
    narrow_flag = _v1(_row(22544.0, 22622.0, {"approval_band_warn_pts": 50, **WIDTH}), monkeypatch)
    assert "⚠️ merged band — check (width 78 pts &gt; 50)" in PT.first_part(narrow_flag)


def test_v0_caption_flag_and_missing_band(monkeypatch):
    from vision import worker as VW
    res = {"verdict": "agree", "audits": []}
    v0 = VW.caption(_row(22300.0, 22750.0, WIDTH), res, "notify")
    assert FLAG in PT.first_part(v0) and "(450 pts)" in v0
    # पट्टा नाही (engine band NA / gate नाही / अर्धवट) ⇒ जुना "Level" मजकूर, width / flag नाही, crash नाही
    for tags in ({"engine": True, "gate": EE.engine_gate_tags({"level_lo": None, "level_hi": None}, "BULLISH")}, {},
                 {"gate": {"area": [22544.0, None]}}, {"gate": {"area": None, "band_warn_pts": "junk"}}):
        row = {**_row(1.0, 2.0), "setup_json": json.dumps({"tags": tags})}
        for cap in (VW.caption(row, res, "notify"), _v1(row, monkeypatch)):
            assert " pts)" not in cap.split("·")[0] and FLAG not in cap and "Level 22,580" in cap
        assert VW.band_flag_line(row) == ""


# ------------------------------------------------------------------------------------------------ pre-open
CTX = {"NIFTY": {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN", "protected": 24774.0},
       "BANKNIFTY": {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP", "protected": 49000.0}}
LAST = {"NIFTY": 22565.0, "BANKNIFTY": 51250.0}
ENGINE = {"NIFTY": [{"role": "resistance", "lo": 22600.0, "hi": 22950.0}], "BANKNIFTY": [{"role": "support", "lo": 50800.0, "hi": 50900.0}]}


def _preopen_msg(P, extra=None):
    on = {("15m_dynamic_sr", s): {"symbol_enabled": True, "signal_source": "engine", **(extra or {})} for s in ("NIFTY", "BANKNIFTY")}
    active = P.bot_status(["NIFTY", "BANKNIFTY"], lambda k, s: {"symbol_enabled": False, "trading_mode": "PAPER", **on.get((k, s), {})})
    return P.build_report(["NIFTY", "BANKNIFTY"], "tok", lambda s: None, lambda s: LAST[s], trend_fn=lambda s: CTX[s],
                          weekly_fn=lambda s: "UP", day="2026-10-14", active=active, engine_fn=lambda s: pd.Timestamp("2026-10-13 15:16"),
                          now=pd.Timestamp("2026-10-14 09:00"), engine_cron=True, engine_areas_fn=lambda s: ENGINE[s])


def test_preopen_lines_show_width_and_flag():
    P = _load("level_gate_preopen")
    top, det = _preopen_msg(P, WIDTH).split(PT.SEP)
    assert "supply 22,600–22,950 (1H, ≈35 pts above), 350 pts wide ⚠️ merged band — check (over 150 pts)" in top
    assert "demand 50,800–50,900 (1H, ≈350 pts below), 100 pts wide." in top
    assert "watching supply 22,600–22,950 (350 pts) ⚠️ merged band — check (width 350 pts &gt; 150)" in det
    assert "watching demand 50,800–50,900 (100 pts)" in det and det.count(FLAG) == 1
    over = _preopen_msg(P, {"approval_band_warn_pts": 400, **WIDTH})                   # setting override ⇒ इशारा नाही
    assert FLAG not in over and "350 pts wide" in over
    assert P.area_words(LR.BEAR, 22781.0, 22781.0, "DYNAMIC_SR_RESISTANCE_15M", 22700.0) == "supply 22,781 (15-min, ≈81 pts above)"


# ------------------------------------------------------------------------------------------------ 15:45 सारांश
def test_summary_lines_show_width_flag_override_and_missing():
    S = _load("paper_daily_summary")
    ctx = CTX["NIFTY"]
    zones = pd.DataFrame([{"zone_type": "ENGINE_LEVEL_1H", "zone_low": 22700.0, "zone_high": 23000.0, "status": "ACTIVE"}])
    gate = {"confirmed": 0, "armed": 0, "ignored": {}}
    away = S.symbol_line("NIFTY", ctx, gate, zones, {"high": 22650.0, "low": 22500.0}, warn_rule="width")
    assert "Nearest supply 22,700–23,000 (1H, ≈50 pts above the high), 300 pts wide ⚠️ merged band — check (over 150 pts)." in away
    inside = S.symbol_line("NIFTY", ctx, gate, zones, {"high": 22750.0, "low": 22500.0}, warn_pts=500)
    assert "Price traded into supply 22,700–23,000 (1H) today, 300 pts wide." in inside and FLAG not in inside
    conf = zones.assign(zone_type="ENGINE_LEVEL_1H|confluence: Daily 22,725–22,810")   # Abhi Z-1u: label "Nearest" ओळीतही
    near = S.symbol_line("NIFTY", ctx, gate, conf, {"high": 22650.0, "low": 22500.0}, warn_rule="width")
    assert "Nearest supply 22,700–23,000 (1H, ≈50 pts above the high; confluence: Daily 22,725–22,810), 300 pts wide" in near
    na = S.symbol_line("NIFTY", ctx, gate, None, {"high": 22650.0, "low": 22500.0}, areas_na="Upstox login missing")
    assert "pts wide" not in na and FLAG not in na
    txt = S.symbols_section("2026-10-14", symbols=("NIFTY",), ctx_fn=lambda s, d: ctx, rows_fn=lambda s, d: ([], None),
                            zones_fn=lambda s: zones, range_fn=lambda s, d: {"high": 22650.0, "low": 22500.0},
                            warn_fn=lambda s: 350)
    assert "300 pts wide." in txt and FLAG not in txt
    bad = S.symbols_section("2026-10-14", symbols=("NIFTY",), ctx_fn=lambda s, d: ctx, rows_fn=lambda s, d: ([], None),
                            zones_fn=lambda s: zones, range_fn=lambda s, d: {"high": 22650.0, "low": 22500.0},
                            warn_fn=lambda s: 1 / 0, rule_fn=lambda s: "width")   # setting वाचता नाही ⇒ default 150
    assert FLAG in bad


def test_modify_ticket_shows_band_width_and_flag_after_decision_line():
    """Abhi: पट्ट्याची रुंदी प्रत्येक approval संदेशात — ✏️ सुधारित ticket (पुन्हा approve) सुद्धा."""
    import json
    from bots_common import plain_text as PT
    from vision import approval as AP
    base = {"side": "BEARISH", "entry": 22700.0, "sl": 22790.0, "target": 22400.0, "rr": 3.33, "engine_entry": 22677.0,
            "src": "engine", "warnings": []}
    row = {"signal_id": "s1", "symbol": "NIFTY", "setup_tf": "15M", "setup_json": json.dumps({"tags": {"gate": {"area": [22300.0, 22750.0]}}})}
    wide = AP.ticket_text(row, {**base, "area": [22300.0, 22750.0]}, "2026-10-09T12:40:00", 10)
    lines = wide.split("\n")
    assert lines[1].startswith(f"<b>{PT.DECISION_APPROVE}</b>")
    assert lines[2].startswith("⚠️ merged band — check (width 450 pts &gt; 150)")
    assert "area 22,300–22,750 (450 pts)" in wide
    narrow = AP.ticket_text(row, {**base, "area": [22544.0, 22622.0]}, "2026-10-09T12:40:00", 10)
    assert "area 22,544–22,622 (78 pts)" in narrow and "merged band" not in narrow
    row_w = {**row, "setup_json": json.dumps({"tags": {"gate": {"area": [22300.0, 22750.0], "band_warn_pts": 500}}})}
    assert "merged band" not in AP.ticket_text(row_w, {**base, "area": [22300.0, 22750.0]}, "2026-10-09T12:40:00", 10)
    none = AP.ticket_text(row, {**base, "area": None}, "2026-10-09T12:40:00", 10)
    assert "merged band" not in none and "pts)" not in none


# ------------------------------------------------------------------------------------------------ layer 6b: the method statement (setting)
def test_band_warn_rule_setting_default_is_method():
    """Layer 6b (C-18) + DECISIONS 53 (BW-1, Abhi): `approval_band_warn_rule` — default "method" = an engine area is one base, never
    merged (#329, Abhi Z-1u) ⇒ the width stays as a fact, no "merged band" line; any other source keeps the width line. "width" = the
    earlier output (what-if); "points" (the earlier name) reads as "width"."""
    from decision3 import settings as S3
    assert S3.OUTPUT["approval_band_warn_rule"][:2] == ("method", ("method", "width"))
    assert S3.OUTPUT["approval_band_warn_rule"][0] == PT.band_warn_rule(None) == PT.band_warn_rule({}) == "method"
    assert S3.REGISTER["approval_band_warn_rule"][:3] == ("method", "method / width", "setting") and PT.band_warn_rule("junk") == "method"
    assert PT.band_warn_rule({"approval_band_warn_rule": " Width "}) == "width" == PT.band_warn_rule("points")
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]["approval_band_warn_rule"] == "method"
    assert "approval_band_warn_rule" not in S3.DEFAULTS                                         # display only, never a reading setting
    wide = (22300.0, 22750.0)
    assert PT.band_flag(*wide, None, "width", engine_area=True) == PT.band_flag(*wide) != ""   # not an engine area ⇒ the line
    assert PT.band_flag(*wide, None, "points", engine_area=True) == PT.band_flag(*wide)        # old rows' tags read the same
    assert PT.band_flag(*wide, None, "method", engine_area=True) == "" == PT.band_flag(*wide, engine_area=True)
    assert PT.band_flag(*wide, None, "method", engine_area=False) == PT.band_flag(*wide)        # not an engine area ⇒ width
    assert PT.band_wide_words(*wide, None, "method", engine_area=True) == "450 pts wide"
    r = {"level_lo": 22300.0, "level_hi": 22750.0, "grade": "B"}
    assert EE.engine_gate_tags(r, "BEARISH")["band_warn_rule"] == "method"
    assert EE.engine_gate_tags(r, "BEARISH", WIDTH)["band_warn_rule"] == "width"


def test_dashboard_offers_the_band_rule():
    """The setting is on the 15M SRv2 dashboard page (🧭 Signal source) and saved with the page's settings (display only)."""
    src = open(os.path.join(ROOT, "page_bot_dynamic_sr_algo.py"), encoding="utf-8").read()
    assert "_PT.BAND_WARN_RULES" in src and "new_settings[_PT.BAND_WARN_RULE_KEY] = _PT.band_warn_rule(approval_band_warn_rule)" in src


def test_band_warn_rule_method_in_captions_and_preopen(monkeypatch):
    from vision import worker as VW
    row = _row(22300.0, 22750.0, {"approval_band_warn_rule": "method"}, direction="BEARISH")
    cap = _v1(row, monkeypatch)
    assert FLAG not in cap and "(450 pts)" in cap and VW.band_flag_line(row) == ""
    assert FLAG not in VW.caption(row, {"verdict": "agree", "audits": []}, "notify")
    P = _load("level_gate_preopen")
    msg = _preopen_msg(P, {"approval_band_warn_rule": "method"})
    assert FLAG not in msg and "350 pts wide" in msg and "22,600–22,950 (350 pts)" in msg
    assert FLAG not in _preopen_msg(P) and FLAG in _preopen_msg(P, WIDTH)                         # default = method (DECISIONS 53)
