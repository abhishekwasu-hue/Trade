"""Abhi (track F): pre-open संदेशाच्या वर CRUX (प्रत्येक symbol ≤ 5 ओळी) + Daily / 1H / 15M charts. Network / Telegram / DB नाही.

  • crux = fake reader state वरून: जवळचा area (kind, पट्टा, अंतर, state, confluence), method चा क्रम, invalidation, target — प्रत्येक
    आकडा input मधूनच (नवा आकडा नाही);
  • setting `preopen_charts` बंद ⇒ आजचाच संदेश अक्षरशः; चालू ⇒ फक्त crux block जोडलेला;
  • chart अयशस्वी (render / send) ⇒ संदेश तसाच जातो, "(chart unavailable)";
  • synthetic data वर प्रत्येक tf चा PNG, वेळ / memory मर्यादेत.
"""
import importlib.util
import os
import re
import time
import tracemalloc

import pandas as pd
import pytest

from bots_common import level_reaction as LR
from bots_common import plain_text as PT
from bots_common import preopen_crux as PC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _preopen():
    spec = importlib.util.spec_from_file_location("level_gate_preopen_f", os.path.join(ROOT, "scripts", "level_gate_preopen.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    return P


# Abhi च्या आजच्या संदेशासारखी अवस्था (आकडे त्या संदेशातले; state / tests / protected = fake reader facts)
NIFTY = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN", "protected": 23456.0}
BANK = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN", "protected": None}
CTX = {"NIFTY": NIFTY, "BANKNIFTY": BANK}
LAST = {"NIFTY": 22889.0, "BANKNIFTY": 55488.0}
LEVELS = {
    "NIFTY": [
        {"id": 1, "tf": "D", "role": "resistance", "lo": 23039.0, "hi": 23111.0, "state": "ACTIVE", "tests": 0, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None},
        {"id": 2, "tf": "1H", "role": "resistance", "lo": 23119.0, "hi": 23172.0, "state": "TESTED", "tests": 2, "flips": 0,
         "trade_location": True, "confluence": [{"tf": "W", "id": 9, "lo": 21281.0, "hi": 23290.0}, {"tf": "D", "id": 8, "lo": 23116.0,
                                                                                                       "hi": 23202.0}],
         "confluence_label": "confluence: Weekly 21,281–23,290; Daily 23,116–23,202"},
        {"id": 3, "tf": "1H", "role": "support", "lo": 22610.0, "hi": 22655.0, "state": "ACTIVE", "tests": 1, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None},
        {"id": 4, "tf": "1H", "role": "support", "lo": 22400.0, "hi": 22430.0, "state": "BROKEN", "tests": 1, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None}],
    "BANKNIFTY": [
        {"id": 5, "tf": "1H", "role": "resistance", "lo": 55699.0, "hi": 55970.0, "state": "FLIPPED", "tests": 1, "flips": 1,
         "trade_location": True, "confluence": [{"tf": "D", "id": 7, "lo": 55800.0, "hi": 56100.0}],
         "confluence_label": "confluence: Daily 55,800–56,100"},
        {"id": 6, "tf": "1H", "role": "resistance", "lo": 55947.0, "hi": 56066.0, "state": "ACTIVE", "tests": 0, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None}]}
ONE_BOT = {("15m_dynamic_sr", s): {"symbol_enabled": True, "signal_source": "engine"} for s in ("NIFTY", "BANKNIFTY")}
NOW = pd.Timestamp("2026-10-13 09:00")


def _settings(on, extra=None):
    def get(key, sym):
        return {"symbol_enabled": False, "trading_mode": "PAPER", **on.get((key, sym), {}), **((extra or {}) if (key, sym) in on else {})}
    return get


def _report(P, active, **kw):
    return P.build_report(["NIFTY", "BANKNIFTY"], "tok", lambda s: None, lambda s: LAST[s], trend_fn=lambda s: CTX[s],
                          weekly_fn=lambda s: "UP", day="2026-10-13", active=active, engine_fn=lambda s: pd.Timestamp("2026-10-12 15:16"),
                          now=NOW, engine_cron=True, engine_areas_fn=lambda s: LEVELS[s], **kw)


def _crux(msg):
    """Decision needed नंतरचा crux block (पहिल्या रिकाम्या ओळीनंतर, symbol ओळींच्या आधी)."""
    body = msg.split(PT.DECISION_NONE + "\n\n", 1)[1]
    return body[:body.index("<b>NIFTY</b>")].rstrip("\n").split("\n")


def _nums(text):
    return {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", re.sub(r"<[^>]+>", "", text))}


def test_crux_from_fake_reader_state_nearest_sequence_invalidation_target():
    P = _preopen()
    msg = _report(P, P.bot_status(["NIFTY", "BANKNIFTY"], _settings(ONE_BOT)))
    crux = _crux(msg)
    nifty = crux[:crux.index("")]
    bank = crux[crux.index("") + 1:]
    assert len(nifty) <= 5 and len(bank) <= 5
    assert nifty[0] == "<b>🎯 NIFTY</b> — Daily DOWN, Weekly UP ⇒ sell side only: supply above price."
    assert nifty[1] == ("Nearest: supply 23,039–23,111 (Daily, ≈150 pts above last close 22,889) · fresh (not tested yet) · "
                        "confluence: none")
    assert nifty[2].startswith("Entry only if: price visits it → handover → commitment candle with volume → 5-min change of character.")
    assert "Label A needs one more piece (RSI divergence" in nifty[2] and "without it B" in nifty[2]   # confluence नाही ⇒ B, A ला piece हवा
    assert nifty[3] == ("Invalid: a 15M close above 23,111 (beyond the area); Daily DOWN ends on a daily close above 23,456 "
                        "(protected).")
    # target = विरुद्ध बाजूचा सर्वात जवळचा जिवंत support (BROKEN 22,400 tradeable_levels ने वगळला); पुढचा supply = 1H 23,119
    assert nifty[4] == ("Target: next demand 22,610–22,655 (1H, ≈234 pts below) · if it breaks, next: supply 23,119–23,172 (1H).")
    assert bank[1] == ("Nearest: supply 55,699–55,970 (1H, ≈211 pts above last close 55,488) · flipped (reader role now supply, was demand), "
                       "tested 1× · "
                       "confluence: Daily")
    assert "Confluence is already there ⇒ label A if all of this happens." in bank[2]          # method §5: confluence = confirming piece
    assert bank[3] == "Invalid: a 15M close above 55,970 (beyond the area)."                   # protected नाही ⇒ ती अट नाही
    assert bank[4].startswith("Target: no demand area in the engine's list") and "next: supply 55,947–56,066" in bank[4]
    # नवा आकडा नाही: crux मधला प्रत्येक आकडा = input (पट्टे, last close, protected) किंवा त्यांचं अंतर, किंवा tf / touch / tests
    allowed = {float(v) for s in LEVELS for x in LEVELS[s] for v in (x["lo"], x["hi"])} | set(LAST.values()) | {23456.0}
    allowed |= {round(23039 - 22889), round(22889 - 22655), round(55699 - 55488)} | {1.0, 5.0, 15.0}
    assert _nums("\n".join(crux)) <= allowed, _nums("\n".join(crux)) - allowed
    assert not PT.has_raw_codes(PT.first_part(msg))                                             # वरचा भाग साध्या शब्दांत
    top = PT.first_part(msg)
    assert top.index("🎯 NIFTY") < top.index("<b>NIFTY</b>: Daily DOWN")                        # crux वर, जुनी ओळ खाली तशीच


def test_setting_off_is_todays_message_exactly_and_on_only_adds_the_crux():
    P = _preopen()
    syms = ["NIFTY", "BANKNIFTY"]
    off = _report(P, P.bot_status(syms, _settings(ONE_BOT, {"preopen_charts": False})))
    assert off == _report(P, P.bot_status(syms, _settings(ONE_BOT)), crux_on=False)            # बंद ⇒ crux_on False सारखंच
    assert "🎯" not in off and PC.CHART_NA not in off
    for v in ("false", "0", "off", "no"):                                                       # dashboard मधून "false" साठवलं तरी बंद
        assert _report(P, P.bot_status(syms, _settings(ONE_BOT, {"preopen_charts": v}))) == off
    on = _report(P, P.bot_status(syms, _settings(ONE_BOT)))                                     # key नाही ⇒ default ON
    crux = "\n".join(_crux(on)) + "\n\n"
    assert crux in on and on.replace(crux, "", 1) == off                                        # फक्त crux block जोडलेला
    # जुने callers (active False) / settings वाचता नाहीत (None) ⇒ crux नाही
    assert "🎯" not in _report(P, False) and "🎯" not in _report(P, None)
    # default ON: cloud_db defaults + parser
    import cloud_db
    assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]["preopen_charts"] is True
    assert PC.charts_on(None) and PC.charts_on("") and PC.charts_on("true") and not PC.charts_on(False)


def test_chart_failure_never_blocks_the_text():
    P = _preopen()
    active = P.bot_status(["NIFTY", "BANKNIFTY"], _settings(ONE_BOT))
    ok = _report(P, active, chart_fn=lambda *a: True)

    def boom(sym, f, wk, line):
        raise MemoryError("render")
    bad = _report(P, active, chart_fn=boom)
    assert bad.count(PC.CHART_NA) == 2 and PC.CHART_NA not in ok
    assert bad.replace(" " + PC.CHART_NA, "") == ok                                             # बाकी संदेश तसाच
    half = _report(P, active, chart_fn=lambda sym, *a: sym == "NIFTY")
    assert half.count(PC.CHART_NA) == 1 and "🎯 BANKNIFTY</b> — Daily DOWN, Weekly UP ⇒ sell side only: supply above price. (chart" in half
    seen = []
    _report(P, active, chart_fn=lambda sym, f, wk, line: seen.append((sym, f["nearest"]["lo"], f["target"])) or True)
    assert seen[0][:2] == ("NIFTY", 23039.0) and seen[0][2]["lo"] == 22610.0                     # chart ला crux चीच तथ्यं


def test_send_charts_failure_is_logged_only(capsys):
    P = _preopen()
    png = {"NIFTY": [("Daily", b"\x89PNG..", "c1"), ("1H", b"\x89PNG..", "c2"), ("15M", b"\x89PNG..", "c3")]}
    got = []
    assert P.send_charts(png, lambda items: got.append(items) or True) == {"NIFTY": True}
    assert [c for _, c in got[0]] == ["c1", "c2", "c3"]

    def boom(items):
        raise ConnectionError("telegram down")
    assert P.send_charts(png, boom) == {"NIFTY": False}
    assert P.send_charts(png, lambda items: False) == {"NIFTY": False}
    out = capsys.readouterr().out
    assert "ConnectionError" in out and "NOT sent (text message already sent)" in out
    assert P.send_charts({}, boom) == {}


def test_main_sends_text_first_then_one_album_per_symbol_and_survives_chart_errors(monkeypatch, capsys):
    """main(): engine areas ⇒ तोच V22 (keep) ⇒ charts; संदेश आधी, मग album. Render / album त्रुटी ⇒ संदेश तरी गेला, exit 0."""
    import cloud_db
    import engine3_live as L3
    import notifications
    import upstox_api
    from decision3 import preopen_chart as PCH
    P = _preopen()
    sent = []
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda x: "tok")
    monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
    monkeypatch.setattr(cloud_db, "get_signal_symbols", lambda: ["NIFTY", "BANKNIFTY"])
    monkeypatch.setattr(cloud_db, "get_strategy_settings", _settings(ONE_BOT))
    monkeypatch.setattr(cloud_db, "get_market_zones", lambda s: None)
    monkeypatch.setattr(LR, "daily_trend", lambda s, tok, fetch=None: CTX[s])
    daily = {s: pd.DataFrame({"timestamp": [NOW], "open": [v], "high": [v], "low": [v], "close": [v]}) for s, v in LAST.items()}
    monkeypatch.setattr(upstox_api, "fetch_candles", lambda tok, sym, **k: daily[sym])
    monkeypatch.setattr(P, "engine_last_run", lambda s, path=None: None)
    monkeypatch.setattr(P, "one_bot_problems", lambda: [])
    from bots_common import level_visibility as LV
    monkeypatch.setattr(LV, "mcx_symbols", lambda get_settings=None: ())
    monkeypatch.setattr(L3, "UpstoxFeed", lambda tok, today=None: object())

    def watched(sym, feed, now, s=None, keep=None):
        if keep is not None:
            keep["V"] = f"V-{sym}"
        return L3.tradeable_levels(LEVELS[sym])
    monkeypatch.setattr(L3, "watched_levels", watched)
    monkeypatch.setattr(PCH, "line_facts", lambda V, trend: {"line": None, "tags": {}})
    monkeypatch.setattr(PCH, "render", lambda V, sym, f, wk, line: ([(tf, b"\x89PNG" + V.encode(), f"{sym} {tf}") for tf in PCH.TFS], []))
    monkeypatch.setattr(notifications, "send_telegram_message", lambda m: sent.append(("text", m)) or True)
    monkeypatch.setattr(notifications, "send_telegram_media_group", lambda items: sent.append(("album", items)) or True)
    assert P.main([]) == 0
    assert [k for k, _ in sent] == ["text", "album", "album"]                                   # संदेश आधी, मग प्रत्येक symbol चा album
    assert [c for _, c in sent[1][1]] == ["NIFTY Daily", "NIFTY 1H", "NIFTY 15M"] and sent[1][1][0][0] == b"\x89PNGV-NIFTY"
    assert "🎯 NIFTY" in sent[0][1] and PC.CHART_NA not in sent[0][1]
    # album त्रुटी ⇒ संदेश गेला, exit 0
    sent.clear()
    monkeypatch.setattr(notifications, "send_telegram_media_group", lambda items: (_ for _ in ()).throw(ConnectionError("x")))
    assert P.main([]) == 0 and [k for k, _ in sent] == ["text"]
    # render त्रुटी ⇒ "(chart unavailable)", album नाही, संदेश गेला
    sent.clear()
    monkeypatch.setattr(PCH, "render", lambda *a: (_ for _ in ()).throw(MemoryError("x")))
    assert P.main([]) == 0 and [k for k, _ in sent] == ["text"] and sent[0][1].count(PC.CHART_NA) == 2
    # setting बंद ⇒ V ठेवत नाही, charts नाहीत, crux नाही
    sent.clear()
    monkeypatch.setattr(cloud_db, "get_strategy_settings", _settings(ONE_BOT, {"preopen_charts": False}))
    monkeypatch.setattr(PCH, "render", lambda *a: pytest.fail("charts must not render when the setting is off"))
    assert P.main([]) == 0 and [k for k, _ in sent] == ["text"] and "🎯" not in sent[0][1]
    # --dry-run ⇒ काहीच पाठवत नाही
    sent.clear()
    assert P.main(["--dry-run", "--no-charts"]) == 0 and sent == []


def test_media_group_helper_never_raises_and_falls_back(monkeypatch):
    import notifications as N
    calls = []

    class R:
        def __init__(self, code):
            self.status_code = code
    monkeypatch.setattr(N, "_load_telegram_credentials", lambda: ("T", "C"))
    monkeypatch.setattr(N, "_log_locally", lambda m: None)
    monkeypatch.setattr(N.requests, "post", lambda url, **k: calls.append((url.rsplit("/", 1)[1], k)) or R(200))
    assert N.send_telegram_media_group([(b"a", "x"), (b"b", "y"), (b"c", "z")]) is True
    assert calls[0][0] == "sendMediaGroup" and len(calls[0][1]["files"]) == 3 and '"attach://p2"' in calls[0][1]["data"]["media"]
    assert "T" not in calls[0][1]["data"]["media"]
    calls.clear()
    monkeypatch.setattr(N.requests, "post", lambda url, **k: calls.append(url.rsplit("/", 1)[1]) or R(400 if "Group" in url else 200))
    assert N.send_telegram_media_group([(b"a", "x"), (b"b", "y")]) is True and calls == ["sendMediaGroup", "sendPhoto", "sendPhoto"]

    def down(url, **k):
        raise N.requests.ConnectionError("x")
    monkeypatch.setattr(N.requests, "post", down)
    assert N.send_telegram_media_group([(b"a", "x"), (b"b", "y")]) is False
    monkeypatch.setattr(N, "_load_telegram_credentials", lambda: (None, None))
    assert N.send_telegram_media_group([(b"a", "x"), (b"b", "y")]) is False and N.send_telegram_media_group([]) is False


@pytest.fixture(scope="module")
def synth_v():
    from decision3 import engine as E3
    from tests import oct12_fixture as F
    m15, _fut, _ltf = F.build()
    return E3.V22(m15, None, None)


def test_charts_render_png_per_timeframe_on_synthetic_data_within_budget(synth_v):
    from decision3 import preopen_chart as PCH
    V = synth_v
    t = len(V.m15) - 1
    last = float(V.m15["close"].iloc[t])
    from engine3_live import tradeable_levels
    lv = tradeable_levels(V.levels.snapshot(t))
    st = V.daily[-1]
    ctx = {"ok": True, "trend": st.trend if st.trend in ("UP", "DOWN") else "DOWN", "sides": {LR.BEAR}, "band": None,
           "protected": st.protected.price if st.protected is not None else None}
    sides = [(LR.BEAR, x["lo"], x["hi"], "ENGINE_LEVEL_1H") for x in lv if x["lo"] > last] or \
        [(LR.BEAR, last + 10.0, last + 20.0, "ENGINE_LEVEL_1H")]
    line = PCH.line_facts(V, ctx["trend"])
    f = PC.facts(ctx, last, sides[:3], lv, line["tags"])
    tracemalloc.start()
    t0 = time.time()
    items, errs = PCH.render(V, "BANKNIFTY", f, "UP", line)
    took = time.time() - t0
    peak = tracemalloc.get_traced_memory()[1] / 2 ** 20
    tracemalloc.stop()
    assert errs == [] and [tf for tf, _, _ in items] == ["Daily", "1H", "15M"]
    for tf, png, cap in items:
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and 5_000 < len(png) < 600_000, (tf, len(png))
        assert cap.startswith(f"BANKNIFTY · {tf} · Daily ")
    assert took < 30 and peak < 150, (took, peak)                                              # 1 vCPU / 1 GB VPS: हलकं
    import matplotlib.pyplot as plt
    assert plt.get_fignums() == []                                                              # प्रत्येक figure बंद
    # एक tf अयशस्वी ⇒ बाकीचे तरी, कारण errors मध्ये
    items2, errs2 = PCH.render(V, "BANKNIFTY", {**f, "nearest": {"bad": 1}, "watched": [{"bad": 1}]}, "UP", line, tfs=("15M",))
    assert items2 == [] and errs2 and errs2[0].startswith("15M: KeyError")


def test_crux_edge_cases_no_area_na_unclear():
    assert PC.lines("NIFTY", {"ok": False, "trend": "UNKNOWN", "sides": set(), "reason": "x"}, None, 1.0)[0].startswith(
        "<b>🎯 NIFTY</b> — no new entries today")
    f = PC.facts(NIFTY, 22889.0, [], None)
    out = PC.lines("NIFTY", NIFTY, "UP", 22889.0, f)
    assert out[1] == "Last close 22,889: no supply area near price yet — nothing to enter."
    assert PC.lines("NIFTY", NIFTY, "UP", 22889.0, f, na="engine areas not available")[1] == "Watched areas NA — engine areas not available."
    assert PC.lines("NIFTY", NIFTY, "UP", None, PC.facts(NIFTY, None, [], None))[1].startswith("Price data missing")
    # own source (engine levels नाहीत): state / target NA, कुठलाही नवा आकडा नाही
    f = PC.facts(NIFTY, 22889.0, [(LR.BEAR, 23000.0, 23050.0, "DYNAMIC_SR_RESISTANCE_15M")], None)
    out = PC.lines("NIFTY", NIFTY, "UP", 22889.0, f)
    assert out[1] == "Nearest: supply 23,000–23,050 (15-min, ≈111 pts above last close 22,889) · confluence: none"
    assert out[4] == "Target: no demand area in the engine's list — use your dashboard target."
    # line touch N (reader चं confluence_areas) ⇒ confluence शब्द
    f = PC.facts(NIFTY, 22889.0, [(LR.BEAR, 23039.0, 23111.0, "ENGINE_LEVEL_1D")], LEVELS["NIFTY"], {1: "line (touch 3)"})
    assert f["nearest"]["conf"] == "line (touch 3)"


def test_nearest_is_by_edge_distance_not_midpoint_order():
    """12 Oct-like: the message lists 22,570–22,579 first (midpoint ≈211 pts) but price reaches 22,544–22,622 first (edge ≈181 pts)."""
    P = _preopen()
    last = 22363.0
    levels = [{"id": 1, "tf": "1H", "role": "resistance", "lo": 22570.0, "hi": 22579.0, "state": "ACTIVE", "tests": 0},
              {"id": 2, "tf": "1H", "role": "resistance", "lo": 22544.0, "hi": 22622.0, "state": "TESTED", "tests": 5},
              {"id": 3, "tf": "1H", "role": "resistance", "lo": 22723.0, "hi": 22732.0, "state": "ACTIVE", "tests": 0}]
    areas = [(LR.BEAR, x["lo"], x["hi"], "ENGINE_LEVEL_1H") for x in levels]
    ordered = P.nearest(areas, last, 3)
    assert (ordered[0][1], ordered[0][2]) == (22570.0, 22579.0)                                # the message's own order: midpoint
    f = PC.facts(NIFTY, last, ordered, levels)
    assert (f["nearest"]["lo"], f["nearest"]["hi"], f["nearest"]["dist"]) == (22544.0, 22622.0, 181.0)
    assert (f["next"]["lo"], f["next"]["hi"]) == (22570.0, 22579.0)
    out = PC.lines("NIFTY", NIFTY, "UP", last, f)
    assert out[1] == "Nearest: supply 22,544–22,622 (1H, ≈181 pts above last close 22,363) · tested 5× · confluence: none"
    assert out[3].startswith("Invalid: a 15M close above 22,622 (beyond the area)")
    assert out[4].endswith("if it breaks, next: supply 22,570–22,579 (1H).")
    assert [(a["lo"], a["hi"]) for a in f["watched"]] == [(x[1], x[2]) for x in ordered]       # everything else unchanged
