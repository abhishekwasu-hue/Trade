"""Abhi deploy fixes (pre-open): (1) signal_symbols dashboard setting (default NIFTY / BANKNIFTY) — SENSEX ला signal / approval /
pre-open ओळ नाही; (2) प्रत्येक area पट्टा (low < high, TA4) — decision3 levels (σ_1H नसताना रुंदी 0 होती), engine ⇒ Vision tags, pre-open;
(3) pre-open फक्त चालू bot(s) आणि त्यांचे पट्टे. Network नाही."""
import importlib.util
import os
import re
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

import cloud_db
import engine_signal as ES
from bots_common import level_reaction as LR
from bots_common import plain_text as PT
from decision3 import levels as LV
from paper import engine_entry as EE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANGE_RE = re.compile(r"(\d[\d,]*)–(\d[\d,]*)")


def _preopen():
    spec = importlib.util.spec_from_file_location("level_gate_preopen_t2", os.path.join(ROOT, "scripts", "level_gate_preopen.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    return P


def _no_zero_width(text):
    """प्रत्येक "low–high" मध्ये low < high (एकच किंमत नाही)."""
    pairs = [(float(a.replace(",", "")), float(b.replace(",", ""))) for a, b in RANGE_RE.findall(text)]
    assert pairs, text
    assert all(lo < hi for lo, hi in pairs), pairs


# ------------------------------------------------------------------------------------------------ 2. decision3 levels: पट्टा, एकच किंमत नाही
def _m15(closes, per_day=25):
    rows, prev = [], closes[0]
    days = pd.bdate_range("2030-01-07", periods=(len(closes) + per_day - 1) // per_day)
    for i, c in enumerate(closes):
        ts = days[i // per_day] + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * (i % per_day))
        rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": prev, "close": c, "high": max(prev, c),
                     "low": min(prev, c)})
        prev = c
    return pd.DataFrame(rows)


def _res(m15, piv, sig_day2=10.0):
    """σ_1H: पहिला दिवस NaN (window सुरुवात — sigma_sessions अजून नाहीत), दुसरा दिवस sig_day2."""
    days = pd.to_datetime(m15["timestamp"]).dt.normalize().unique()
    return {"m15": m15, "pivots": {0: [], 1: [], 2: piv}, "sigma_1h": {pd.Timestamp(d): (np.nan if i == 0 else sig_day2)
                                                                         for i, d in enumerate(days)}}


# 1H candle 09:15 close = high (वरची wick नाही) ⇒ wick-to-body पट्टा = एकच किंमत 103; σ_1H NaN ⇒ आधी किमान रुंदी 0 ⇒ "103–103"
CLOSES = [100, 101, 102, 103, 102, 101, 100] + [100.5, 99.5] * 9 + [100] * 25


def test_level_band_never_zero_width_when_sigma_missing():
    m = _m15(CLOSES)
    lv = LV.Levels(_res(m, [NS(kind="H", price=103.0, bar=3, confirm_bar=5)]))
    L = [x for x in lv.L if x.role0 == LV.RES][0]
    lo0, hi0 = L.band_at(5)
    assert hi0 == 103.0 and lo0 < hi0                                         # जन्म: तात्पुरती रुंदी (bars ≤ t चे 1H ranges)
    lo1, hi1 = L.band_at(len(m) - 1)
    assert hi1 == 103.0 and hi1 - lo1 >= 0.15 * 10.0 - 1e-9                   # σ_1H माहीत झाल्यावर spec ची किमान रुंदी (टोकापासून आत)
    assert all(x["hi"] > x["lo"] for t in range(5, len(m)) for x in lv.snapshot(t))


def test_level_band_fix_has_no_lookahead():
    m = _m15(CLOSES)
    piv = [NS(kind="H", price=103.0, bar=3, confirm_bar=5)]
    full = LV.Levels(_res(m, piv))
    for k in (8, 20, 27, 40):                                                 # truncated run ⇒ तेच पट्टे (t < k)
        part = LV.Levels(_res(m.iloc[:k].reset_index(drop=True), piv))
        for t in range(5, k):
            assert [(x["lo"], x["hi"]) for x in part.snapshot(t)] == [(x["lo"], x["hi"]) for x in full.snapshot(t)], (k, t)


def test_level_band_unchanged_when_sigma_known():
    m = _m15(CLOSES)
    days = pd.to_datetime(m["timestamp"]).dt.normalize().unique()
    res = {"m15": m, "pivots": {0: [], 1: [], 2: [NS(kind="H", price=103.0, bar=3, confirm_bar=5)]},
           "sigma_1h": {pd.Timestamp(d): 10.0 for d in days}}
    L = LV.Levels(res).L[0]
    assert L.bands == [(5, 101.5, 103.0)]                                     # σ असताना आधीसारखंच (एकच band, बदल नाही)


# ------------------------------------------------------------------------------------------------ 2. engine ⇒ Vision / Telegram: पट्टा
def _put(p, sym="NIFTY", lo=25000.0, hi=25020.0, d=1):
    ES.save({"symbol": sym, "bar_ts": "2026-10-12 10:00:00", "computed_at": "2026-10-12 10:00:00", "decision": "setup", "gate": None,
             "direction": d, "level_lo": lo, "level_hi": hi, "entry": 25030.0, "invalidation": 24980.0, "target": 25200.0,
             "grade": "B", "reason": "x", "payload": '{"trend_used": "UP", "commitment_form": "engulf"}'}, p)


ST = {"signal_source": "engine", "trading_mode": "PAPER", "lots": 1, "naked_lots": 0, "naked_enabled": False, "itm_depth_points": 100,
      "hedge_width_points": 150}


def test_engine_entry_sends_band_to_vision_and_skips_non_signal_symbol(tmp_path):
    p = str(tmp_path / "es.db")
    _put(p)
    _put(p, "SENSEX", 82000.0, 82040.0)
    seen = []
    hold = NS(action="HOLD", note="wait", final=False)

    def gate(*a, **k):
        seen.append((a, k))
        return hold
    kw = dict(now="2026-10-12 10:05", has_open=lambda s, src: False, gate_fn=gate, chain=[{"underlying_spot_price": 25010.0}], path=p)
    EE.process("srv2_momentum_reversal", "t", "NIFTY", ST, 65, "srv2", **kw)
    g = seen[0][1]["tags"]["gate"]
    assert g["area"] == [25000.0, 25020.0] and g["side"] == "BULLISH" and g["trend"] == "UP" and g["form"] == "engulf"
    assert "sl" not in g and "entry" not in g                                 # ✏️ Modify / R:R वर्तन आधीसारखंच
    m = EE.process("srv2_momentum_reversal", "t", "SENSEX", ST, 65, "srv2", **kw)   # default signal_symbols ⇒ SENSEX नाही
    assert "signal_symbols" in m and len(seen) == 1                            # approval विचारली नाही
    EE.process("srv2_momentum_reversal", "t", "SENSEX", ST, 65, "srv2", symbols_fn=lambda: ["NIFTY", "SENSEX"], **kw)
    assert len(seen) == 2                                                      # dashboard ने SENSEX चालू केला ⇒ approval मार्ग
    assert EE.engine_gate_tags({"level_lo": None, "level_hi": None}, "BEARISH")["area"] is None   # band नाही ⇒ NA (एकच किंमत नाही)


def test_vision_caption_shows_engine_band_not_single_price():
    from vision import worker as VW
    row = {"symbol": "NIFTY", "direction": "BEARISH", "level": 22781.0, "role": "Resistance", "setup_tf": "15M",
           "signal_ts": "2026-10-12T10:00:00", "bot": "srv2_momentum_reversal",
           "tags": {"engine": True, "gate": EE.engine_gate_tags({"level_lo": 22761.0, "level_hi": 22801.0, "grade": "B"}, "BEARISH")}}
    head = VW.plain_head(row)
    assert "supply area 22,761–22,801" in head and "resistance 22,781" not in head
    body = VW._body(row, {"verdict": "agree", "audits": []}, "notify")
    assert "Area 22,761–22,801" in body and "Level 22,781" not in body
    _no_zero_width(head + body)


# ------------------------------------------------------------------------------------------------ 1 + 3. pre-open
NIFTY = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN", "protected": 24774.0}
BANK = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP", "protected": 49000.0}
SENSEX = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP", "protected": 70000.0}
CTX = {"NIFTY": NIFTY, "BANKNIFTY": BANK, "SENSEX": SENSEX}
LAST = {"NIFTY": 22565.0, "BANKNIFTY": 51250.0, "SENSEX": 74000.0}
# market_zones DYNAMIC_SR rows = एकच किंमत (zone_low = zone_high) — Abhi ने पाहिलेलं "supply 22,781–22,781"
SINGLE = pd.DataFrame([{"zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": 22781.0, "zone_high": 22781.0, "status": "ACTIVE"},
                       {"zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 22700.0, "zone_high": 22700.0, "status": "ACTIVE"}])
ENGINE = {"NIFTY": [{"role": "resistance", "lo": 22715.0, "hi": 22776.0}, {"role": "support", "lo": 22400.0, "hi": 22430.0}],
          "BANKNIFTY": [{"role": "support", "lo": 50800.0, "hi": 50900.0}]}


def _settings(on):
    def get(key, sym):
        return {"symbol_enabled": False, "trading_mode": "PAPER", **on.get((key, sym), {})}
    return get


ONE_BOT = {("15m_dynamic_sr", s): {"symbol_enabled": True, "signal_source": "engine"} for s in ("NIFTY", "BANKNIFTY")}


def _report(P, symbols, active, engine_areas_fn=lambda s: ENGINE.get(s, [])):
    return P.build_report(symbols, "tok", lambda s: SINGLE if s == "NIFTY" else None, lambda s: LAST[s], trend_fn=lambda s: CTX[s],
                          weekly_fn=lambda s: "UP", day="2026-10-13", active=active, engine_fn=lambda s: pd.Timestamp("2026-10-12 15:16"),
                          now=pd.Timestamp("2026-10-13 09:00"), engine_cron=True, engine_areas_fn=engine_areas_fn)


def test_preopen_one_bot_mode_mentions_only_active_bot_and_engine_bands(capsys):
    P = _preopen()
    syms = cloud_db.SIGNAL_SYMBOLS_DEFAULT                                    # default signal_symbols
    msg = _report(P, list(syms), P.bot_status(list(syms), _settings(ONE_BOT)))
    first = msg.splitlines()[0]
    assert first == "Only 15M SRv2 active · signal source: engine · symbols NIFTY / BANKNIFTY · mode PAPER"
    for gone in ("SENSEX", "5M Instant", "Classic", "SR V3", "MCX"):           # बंद bots / non-signal index नाहीत
        assert gone not in msg, gone
    top, det = msg.split(PT.SEP)
    assert "supply 22,715–22,776 (1H, ≈150 pts above)" in top and "22,781" not in msg   # engine चा पट्टा, market_zones चा एकच-किंमत level नाही
    assert "demand 50,800–50,900 (1H, ≈350 pts below)" in top
    assert "• 15M SRv2 (engine areas): watching supply 22,715–22,776" in det
    assert "engine areas" not in capsys.readouterr().out                      # त्रुटी नाही
    _no_zero_width(msg)


def test_preopen_engine_areas_missing_is_na_with_reason_debug_in_log(capsys):
    P = _preopen()
    active = P.bot_status(["NIFTY"], _settings(ONE_BOT))

    def boom(sym):
        raise RuntimeError("Traceback-ish detail 15minute HTTP 500")
    msg = _report(P, ["NIFTY"], active, boom)
    nifty = next(ln for ln in msg.splitlines() if "<b>NIFTY</b>" in ln)
    assert nifty.startswith("❌ ") and "Watched areas NA — engine areas not available (see the pre-open log)" in nifty
    assert "HTTP 500" not in msg and "HTTP 500" in capsys.readouterr().out    # debug तपशील फक्त log मध्ये


def test_preopen_own_source_single_price_level_shown_as_bots_gate_band():
    """own source bot (उदा. 15M SRv2 own): DB चा एकच-किंमत level ⇒ bot चाच gate पट्टा (level ± gate_area_pad_pct) — "X–X" नाही."""
    P = _preopen()
    own = {("15m_dynamic_sr", "NIFTY"): {"symbol_enabled": True, "signal_source": "own", "gate_area_pad_pct": 0.1}}
    msg = _report(P, ["NIFTY"], P.bot_status(["NIFTY"], _settings(own)))
    assert "supply 22,770–22,792 (15-min" in msg and "22,781–22,781" not in msg and "22,700" not in msg   # 5M = 5M Instant चा TF (बंद)
    assert "5M Instant" not in msg
    _no_zero_width(msg)
    from bots_common import level_gate_bot as LGB
    lo, hi = P.trade_side_areas(SINGLE, ("15M",), 22565.0, NIFTY, pad_pct=LGB.AREA_PAD_PCT)[0][1:3]
    assert (lo, hi) == pytest.approx(LGB.areas_from_rows([{"zone_low": 22781.0, "zone_high": None}], 22781.0 * LGB.AREA_PAD_PCT / 100)[0])


def test_preopen_main_default_has_no_sensex_line(monkeypatch, capsys):
    import notifications
    P = _preopen()
    monkeypatch.setattr(notifications, "send_telegram_message", lambda m: None)
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda x: None)
    monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
    monkeypatch.setattr(cloud_db, "get_strategy_settings", _settings({**ONE_BOT, ("15m_dynamic_sr", "SENSEX"): {"symbol_enabled": True}}))
    monkeypatch.setattr(cloud_db, "get_market_zones", lambda s: None)
    monkeypatch.setattr(LR, "daily_trend", lambda s, tok, fetch=None: {"ok": False, "trend": "UNKNOWN", "sides": set(), "reason": "x"})
    monkeypatch.setattr(P, "engine_last_run", lambda s, path=None: None)
    monkeypatch.setattr(P, "one_bot_problems", lambda status_fn=None: [])
    from bots_common import level_visibility as LV_
    monkeypatch.setattr(LV_, "mcx_symbols", lambda get_settings=None: ())
    assert P.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "symbols NIFTY / BANKNIFTY · mode PAPER" in out and "<b>NIFTY</b>" in out and "<b>BANKNIFTY</b>" in out
    assert "SENSEX" not in out
    assert P.main(["--dry-run", "--symbols", "NIFTY,SENSEX"]) == 0               # हाताने दिलं तरी signal_symbols बाहेरचं ⇒ ओळ नाही
    out = capsys.readouterr().out
    assert "⏭️ SENSEX: signal_symbols" in out and "<b>SENSEX</b>" not in out


def test_dashboard_has_signal_symbols_control():
    src = open(os.path.join(ROOT, "page_bot_dynamic_sr_algo.py"), encoding="utf-8").read()
    assert "_render_signal_symbols_panel()" in src and "cloud_db.save_signal_symbols(pick)" in src
    assert cloud_db.SIGNAL_SYMBOLS_DEFAULT == ("NIFTY", "BANKNIFTY")


def test_watched_levels_show_only_tradeable_states(monkeypatch):
    """#325: snapshot मध्ये BROKEN zones सुद्धा (state field) ⇒ pre-open फक्त ACTIVE / TESTED / FLIPPED; state नसेल (main) ⇒ सगळे."""
    import engine3_live as L3
    lv = [{"role": "resistance", "lo": 22715.0, "hi": 22776.0, "state": "ACTIVE"},
          {"role": "resistance", "lo": 22600.0, "hi": 22640.0, "state": "BROKEN"},
          {"role": "resistance", "lo": 22650.0, "hi": 22690.0, "state": "dead"},
          {"role": "resistance", "lo": 22800.0, "hi": 22840.0, "state": "TESTED"},
          {"role": "resistance", "lo": 22900.0, "hi": 22950.0, "state": "Flipped"}]
    assert [x["lo"] for x in L3.tradeable_levels(lv)] == [22715.0, 22800.0, 22900.0]
    plain = [{k: v for k, v in x.items() if k != "state"} for x in lv]
    assert L3.tradeable_levels(plain) == plain                                 # main: state field नाही ⇒ सगळे (snapshot = जिवंत)
    m15 = _m15([100.0] * 250)                                                  # watched_levels स्वतः filter करतो (V22 snapshot stub)
    monkeypatch.setattr(L3, "build_inputs", lambda *a, **k: (m15, pd.DataFrame(), None, None, None))
    import decision3.engine as E3
    monkeypatch.setattr(E3, "V22", lambda *a, **k: NS(m15=m15, levels=NS(snapshot=lambda t: lv)))
    got = L3.watched_levels("BANKNIFTY", None, pd.Timestamp("2030-01-07 09:00"))
    assert [x["state"] for x in got] == ["ACTIVE", "TESTED", "Flipped"]
    P = _preopen()                                                             # pre-open: BROKEN पट्टा किंमतीजवळ असला तरी नाही
    msg = _report(P, ["NIFTY"], P.bot_status(["NIFTY"], _settings(ONE_BOT)), engine_areas_fn=lambda s: lv)
    assert "22,600" not in msg and "22,650" not in msg and "supply 22,715–22,776" in msg


# ------------------------------------------------------------------------------------------------ 15:45 सारांश (review #326)
def _ctx_down():
    return {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "mature": False}


def test_summary_default_symbols_follow_signal_symbols_no_sensex(monkeypatch):
    from scripts import paper_daily_summary as S
    monkeypatch.setattr(cloud_db, "get_signal_symbols", lambda: ["NIFTY", "BANKNIFTY"])
    txt = S.symbols_section("2026-10-09", ctx_fn=lambda s, d: None, rows_fn=lambda s, d: (None, "db"),
                            zones_fn=lambda s: None, range_fn=lambda s, d: None)
    assert "NIFTY" in txt and "BANKNIFTY" in txt and "SENSEX" not in txt


def test_summary_own_source_single_price_zone_printed_as_bots_gate_band(monkeypatch):
    from scripts import paper_daily_summary as S
    monkeypatch.setattr(cloud_db, "get_strategy_settings", lambda k, s: {"signal_source": "own", "gate_area_pad_pct": 0.1})
    monkeypatch.setattr(cloud_db, "get_market_zones", lambda s: pd.DataFrame([
        {"zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": 22781.0, "zone_high": 22781.0, "status": "ACTIVE"},
        {"zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 22710.0, "zone_high": 22710.0, "status": "ACTIVE"}]))   # 5M: SRv2 पाहत नाही
    z = S.default_zones("NIFTY")
    assert list(z["zone_type"]) == ["DYNAMIC_SR_RESISTANCE_15M"]
    assert z["zone_high"].iloc[0] - z["zone_low"].iloc[0] == pytest.approx(22781.0 * 0.1 / 100)
    txt = S.symbols_section("2026-10-09", symbols=("NIFTY",), ctx_fn=lambda s, d: _ctx_down(), rows_fn=lambda s, d: ([], None),
                            range_fn=lambda s, d: {"high": 22700.0, "low": 22600.0})
    assert "(15-min, " in txt                                              # 5M level (जवळचा) SRv2 पाहत नाही ⇒ दाखवत नाही
    near = re.search(r"Nearest supply ([\d,]+)–([\d,]+)", txt)
    assert near and near.group(1) != near.group(2) and near.group(1).startswith("22,77")   # 15M पट्टा, एकच किंमत नाही


def test_summary_engine_source_uses_engine_bands_without_broken(monkeypatch):
    from scripts import paper_daily_summary as S
    import engine3_live as L3
    monkeypatch.setattr(cloud_db, "get_strategy_settings", lambda k, s: {"signal_source": "engine"})
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda x: "t")
    monkeypatch.setattr(cloud_db, "get_market_zones", lambda s: pytest.fail("engine source must not read market_zones"))
    monkeypatch.setattr(L3, "UpstoxFeed", lambda tok, today=None: object())
    monkeypatch.setattr(L3, "watched_levels", lambda sym, feed, now, s=None: L3.tradeable_levels([
        {"role": "supply", "lo": 22763.0, "hi": 22809.0, "state": "ACTIVE"},
        {"role": "supply", "lo": 22715.0, "hi": 22732.0, "state": "BROKEN"}]))
    txt = S.symbols_section("2026-10-09", symbols=("NIFTY",), ctx_fn=lambda s, d: _ctx_down(), rows_fn=lambda s, d: ([], None),
                            range_fn=lambda s, d: {"high": 22700.0, "low": 22600.0})
    assert "Nearest supply 22,763–22,809 (1H" in txt and "22,715" not in txt


def test_summary_engine_areas_missing_says_not_available(monkeypatch, capsys):
    from scripts import paper_daily_summary as S
    monkeypatch.setattr(cloud_db, "get_strategy_settings", lambda k, s: {"signal_source": "engine"})
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda x: None)
    txt = S.symbols_section("2026-10-09", symbols=("NIFTY",), ctx_fn=lambda s, d: _ctx_down(), rows_fn=lambda s, d: ([], None),
                            range_fn=lambda s, d: {"high": 22700.0, "low": 22600.0})
    assert "Bot areas not available today (Upstox login missing)." in txt and "Nearest" not in txt
    assert "EngineDataError" in capsys.readouterr().out                    # पूर्ण तपशील log मध्ये
