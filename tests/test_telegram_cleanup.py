"""Abhi (TELEGRAM_CLEANUP 1–4): Telegram वर फक्त proposals / pre-open / 15:45 / review charts; debug runs व kinds नकार (--force शिवाय);
प्रत्येक संदेशाची ओळ 1 साधी English, ओळ 2 "Decision needed", engine codes फक्त "── details ──" खाली. Network नाही (Telegram mock)."""
import contextlib
import importlib.util
import json
import os

import pandas as pd
import pytest

from backtest_review import telegram as RT
from bots_common import level_reaction as LR
from bots_common import plain_text as PT
from tests.test_review_telegram import PNG, PNG_15M, FakeTG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = "K leg a:D2+b · sweep ✓ · Q44 target · pb candle · ★★★ · ① Daily DOWN"
creds = lambda: ("T", "C")                                                    # noqa: E731


def _run(tmp_path, kinds, tag=None, raw=RAW):
    d = tmp_path / "review" / "v22" / "r1"
    items = []
    for i, k in enumerate(kinds):
        day = f"2026-10-0{i + 1}"
        (d / day).mkdir(parents=True)
        (d / day / "a.png").write_bytes(PNG)
        (d / day / "b.png").write_bytes(PNG_15M)
        it = {"n": i + 1, "date": day, "item": f"r1|{day}", "reading": "x", "caption": f"V22 · {day}\n{raw}", "files": [f"{day}/a.png",
                                                                                                                       f"{day}/b.png"]}
        if k is not None:
            it["kind"] = k
        items.append(it)
    m = {"run_id": "r1", "title": "v2.2 NIFTY", "items": items}
    if tag is not None:
        m["tag"] = tag
    (d / "manifest.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return str(d)


# ------------------------------------------------------------------------------------------------ 1. debug ⇒ Telegram नाही
def test_debug_tagged_run_refused_without_force(tmp_path):
    d = _run(tmp_path, ["v22_setup", "v22_setup"], tag="debug")
    tg = FakeTG()
    with pytest.raises(RT.DebugRunRefused, match='tagged "debug"'):
        RT.send_run(d, call=tg, creds=creds, sent=str(tmp_path / "s.json"), sleep=lambda s: None)
    assert tg.calls == [] and not os.path.exists(tmp_path / "s.json")
    out = RT.send_run(d, call=tg, creds=creds, sent=str(tmp_path / "s.json"), sleep=lambda s: None, force=True)
    assert out["sent"] == 2 and len(tg.calls) == 2


def test_debug_kinds_refused_allowed_kinds_sent(tmp_path):
    d = _run(tmp_path, ["v22_daymap", "v22_check", "v22_per_bar_strip", None, "reader2_debug", "mystery_kind"])
    tg = FakeTG()
    out = RT.send_run(d, call=tg, creds=creds, sent=str(tmp_path / "s.json"), sleep=lambda s: None)
    assert out["sent"] == 2 and len(tg.calls) == 2                               # v22_check + kind नसलेला जुना review item
    why = dict(out["refused"])
    assert set(why) == {"r1|2026-10-01", "r1|2026-10-03", "r1|2026-10-05", "r1|2026-10-06"}
    assert "debug view" in why["r1|2026-10-01"] and "not in the allowed list" in why["r1|2026-10-06"]
    out2 = RT.send_run(d, call=tg, creds=creds, sent=str(tmp_path / "s.json"), sleep=lambda s: None, force=True)
    assert out2["sent"] == 4 and out2["skipped"] == 2 and out2["refused"] == []


def test_allowed_and_debug_kind_lists_are_documented():
    for k in ("v22_check", "v22_setup", "v22_daily_swings", "vision_test", None):
        assert RT.item_refusal({"kind": k}) is None
    for k in ("v22_daymap", "reader_debug", "v22_commit_diag", "v22_whatif"):
        assert RT.item_refusal({"kind": k})
    assert "v22_daymap" in RT.__doc__ or "day maps" in RT.__doc__
    assert RT.run_refusal({"run_id": "x", "tag": ["review", "DEBUG"]}) and RT.run_refusal({"run_id": "x"}) is None


def test_script_refuses_debug_run_and_force_flag(tmp_path, monkeypatch, capsys):
    import process_lock
    monkeypatch.setattr(process_lock, "ProcessLock", lambda name: contextlib.nullcontext())
    monkeypatch.setenv(RT.SENT_ENV, str(tmp_path / "s.json"))
    _run(tmp_path, ["v22_setup"], tag="debug")
    spec = importlib.util.spec_from_file_location("send_review", os.path.join(ROOT, "scripts", "send_review_to_telegram.py"))
    S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)
    base = ["--run", "review/v22/r1", "--data-dir", str(tmp_path), "--no-pull", "--vision-audit", "off"]
    assert S.main(base) == 6
    out = capsys.readouterr().out
    assert "Not sent" in out and 'tagged "debug"' in out and "--force" in out
    assert S.main(base + ["--dry-run", "--force"]) == 0                       # dry-run: Telegram call नाही
    assert "पाठवले 1" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ 2. caption: साधी ओळ + निर्णय
def _shape(text, decision_prefix):
    top = PT.first_part(text)
    lines = top.strip("\n").splitlines()
    assert lines[0] and not lines[0].startswith(("🔎", "V22", "🧭 v2.2", "👁"))      # ओळ 1 = साधी English, engine शीर्षक नाही
    assert lines[1].replace("<b>", "").startswith(decision_prefix)
    assert not PT.has_raw_codes(top), top
    return top


def test_review_caption_plain_headline_then_details(tmp_path):
    d = _run(tmp_path, ["v22_check", "v22_daily_swings", None])
    m = RT.load_manifest(d)
    for it in m["items"]:
        cap = RT.caption(m, it)
        _shape(cap, "Decision needed:")
        assert PT.SEP in cap and "Q44" in cap.split(PT.SEP)[1] and len(cap) <= 1024
    it = {**m["items"][0], "headline": "Look at the 10:45 candle.", "decision": PT.DECISION_NONE, "caption": "x" * 3000}
    cap = RT.caption(m, it)
    assert cap.startswith("Look at the 10:45 candle.\n" + PT.DECISION_NONE) and len(cap) <= 1024 and cap.endswith("…")


def _gate_row(status_tags=None):
    tags = {"gate": {"mode": "confirmation", "side": LR.BEAR, "area": [22715.0, 22776.0], "grade": "B", "trend": "Daily DOWN",
                     "study": "inside supply: K leg a:D2+b, sweep ✓", "commit_line": "c0 dominance · pb candle 12:00 · Q44",
                     "entry": 22677.0, "sl": 22790.0, "target": 22300.0, "rr": 3.3}}
    tags.update(status_tags or {})
    return {"signal_id": "s1", "bot": "srv2_momentum_reversal", "bot_label": "15M SRv2", "symbol": "NIFTY", "direction": "BEARISH",
            "level": 22745.0, "role": "RESISTANCE", "setup_tf": "15M", "signal_ts": "2026-10-09T12:15:00", "mode": "human_confirm",
            "setup_json": json.dumps({"tags": tags})}


def test_proposal_caption_asks_for_decision_codes_below(monkeypatch):
    from vision import decide as VD
    from vision import worker as VW
    monkeypatch.setattr(VW, "engine_line", lambda row: "engine: NA")
    row = _gate_row()
    res = {"verdict": "agree", "audits": [], "confidence": 0.8}
    d = VD.Decision("PENDING_HUMAN", 1.0, "human", "REJECTED", 0.0)
    cap = VW.v1_caption(row, res, d, "2026-10-09T12:25:00")
    top = _shape(cap, "Decision needed: approve / reject")
    assert "by 12:25" in top and "NIFTY" in top and "supply area 22,715–22,776" in top and "bear call" in top
    assert "K leg" in cap.split(PT.SEP)[1] and len(cap) <= 1024
    auto = VW.v1_caption(row, res, VD.Decision("APPROVED", 1.0, "agree"), None)
    _shape(auto, "Decision needed: none — information")
    v0 = VW.caption({**row, "tags": {}}, res, "notify")
    _shape(v0, "Decision needed: none — information")
    dry = VW.v1_caption({**row, "setup_json": json.dumps({"tags": {"dry_run": True}})}, res, d, "2026-10-09T12:25:00")
    assert dry.startswith("🧪 [DRY-RUN] NIFTY:")


def test_modified_ticket_headline():
    from vision import approval as AP
    t = {"side": "BEARISH", "entry": 22700.0, "sl": 22790.0, "target": 22400.0, "rr": 3.33, "area": [22715.0, 22776.0],
         "engine_entry": 22677.0, "src": "engine", "warnings": []}
    txt = AP.ticket_text(_gate_row(), t, "2026-10-09T12:40:00", 10)
    top = _shape(txt, "Decision needed: approve / reject")
    assert "22700" in top and "by 12:40" in top and "सुधारित ticket" in txt.split(PT.SEP)[1]


# ------------------------------------------------------------------------------------------------ 3. pre-open: एक संदेश
def _preopen():
    spec = importlib.util.spec_from_file_location("level_gate_preopen_t", os.path.join(ROOT, "scripts", "level_gate_preopen.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    return P


ZONES = pd.DataFrame([
    {"zone_type": "DYNAMIC_SR_RESISTANCE_60M", "zone_low": 22715.0, "zone_high": 22776.0, "status": "ACTIVE"},
    {"zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": 22900.0, "zone_high": 22950.0, "status": "ACTIVE"},
    {"zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": 22400.0, "zone_high": 22430.0, "status": "ACTIVE"},
    {"zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 22600.0, "zone_high": 22610.0, "status": "BROKEN"}])
NIFTY = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN", "protected": 24774.0, "mature": True,
         "targets": [22183.0], "phase": "impulse"}
BANK = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP", "protected": 49000.0}
SENSEX = {"ok": False, "trend": "DOWN", "sides": set(), "phase": "origin_broken", "reason": "no entry: trend unclear (Q47 …)"}


def test_preopen_one_message_per_symbol_line_with_distances():
    P = _preopen()
    ctx = {"NIFTY": NIFTY, "BANKNIFTY": BANK, "SENSEX": SENSEX}
    zz = {"NIFTY": ZONES, "BANKNIFTY": pd.DataFrame([{"zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": 50800.0, "zone_high": 50900.0,
                                                      "status": "ACTIVE"}]), "SENSEX": None}
    last = {"NIFTY": 22565.0, "BANKNIFTY": 51250.0, "SENSEX": 74000.0}
    msg = P.build_report(list(ctx), "tok", lambda s: zz[s], lambda s: last[s], trend_fn=lambda s: ctx[s],
                         weekly_fn=lambda s: {"NIFTY": "UP", "BANKNIFTY": "UP"}.get(s), day="2026-10-09")
    top = _shape(msg, PT.DECISION_NONE)
    lines = {ln.split(":")[0].replace("<b>", "").replace("</b>", ""): ln for ln in top.splitlines() if ln.startswith("<b>")}
    assert set(lines) == {"NIFTY", "BANKNIFTY", "SENSEX"}                          # प्रत्येक symbol ची एकच ओळ
    assert lines["NIFTY"].startswith("<b>NIFTY</b>: Daily DOWN, Weekly UP")
    assert "supply 22,715–22,776 (1H, ≈150 pts above)" in lines["NIFTY"] and "22,400" not in lines["NIFTY"]   # DOWN ⇒ फक्त supply
    assert "22,600" not in lines["NIFTY"]                                             # BROKEN area नाही
    assert "demand 50,800–50,900 (15-min, ≈350 pts below)" in lines["BANKNIFTY"]
    assert "NO NEW ENTRIES" in lines["SENSEX"] and "Weekly n/a" in lines["SENSEX"] and "starting point broke" in lines["SENSEX"]
    assert "15M SRv2: watching supply 22,715–22,776" in msg.split(PT.SEP)[1]        # bot-निहाय तपशील details मध्ये


def _settings(on):
    """on = {(key, sym): extra settings}; बाकी सगळे bots बंद (symbol_enabled False)."""
    def get(key, sym):
        return {"symbol_enabled": False, "trading_mode": "PAPER", **on.get((key, sym), {})}
    return get


ONE_BOT = {("15m_dynamic_sr", s): {"symbol_enabled": True, "signal_source": "engine"} for s in ("NIFTY", "BANKNIFTY", "SENSEX")}
NOW = pd.Timestamp("2026-10-13 09:00")


# engine (decision3 ② Levels) चे पट्टे — signal_source = engine ⇒ pre-open हेच दाखवतो (market_zones नाही)
ENGINE_LEVELS = {"NIFTY": [{"role": "resistance", "lo": 22715.0, "hi": 22776.0}, {"role": "support", "lo": 22400.0, "hi": 22430.0},
                           {"role": "resistance", "lo": 22900.0, "hi": 22950.0}]}


def _one_bot_report(P, active, engine_fn, **kw):
    ctx = {"NIFTY": NIFTY, "BANKNIFTY": BANK, "SENSEX": SENSEX}
    zz = {"NIFTY": ZONES, "BANKNIFTY": None, "SENSEX": None}
    kw.setdefault("engine_areas_fn", lambda s: ENGINE_LEVELS.get(s, []))
    return P.build_report(list(ctx), "tok", lambda s: zz[s], lambda s: {"NIFTY": 22565.0}.get(s),
                          trend_fn=lambda s: ctx[s], weekly_fn=lambda s: "UP", day="2026-10-13", active=active, engine_fn=engine_fn,
                          now=NOW, **kw)


def test_preopen_starts_with_active_bot_from_settings_and_engine_checks():
    P = _preopen()
    syms = ["NIFTY", "BANKNIFTY", "SENSEX"]
    active = P.bot_status(syms, _settings(ONE_BOT))
    eng = {"NIFTY": pd.Timestamp("2026-10-12 15:15"), "BANKNIFTY": pd.Timestamp("2026-10-01 15:15"), "SENSEX": None}
    msg = _one_bot_report(P, active, lambda s: eng[s])
    lines = msg.splitlines()
    assert lines[0] == "Only 15M SRv2 active · signal source: engine · symbols NIFTY / BANKNIFTY / SENSEX · mode PAPER"
    assert lines[2] == PT.DECISION_NONE and not PT.has_raw_codes(PT.first_part(msg))
    top = PT.first_part(msg)
    assert "❌ BANKNIFTY: the engine last ran 01 Oct 15:15" in top and "❌ SENSEX: the engine has no records" in top
    assert "❌ NIFTY: the engine" not in top and "NIFTY engine: last run 12 Oct 15:15" in msg.split(PT.SEP)[1]
    nifty = next(ln for ln in lines if ln.startswith("<b>NIFTY</b>"))
    assert "supply 22,715–22,776 (1H" in nifty and "22,600" not in nifty            # SRv2 फक्त 15M / 30M / 60M areas
    assert any(ln.startswith("❌ <b>BANKNIFTY</b>") and "Price data missing" in ln for ln in lines)


def test_preopen_status_line_says_what_is_really_active():
    P = _preopen()
    syms = ["NIFTY", "BANKNIFTY", "SENSEX"]
    two = {**ONE_BOT, ("1m_instant", "NIFTY"): {"symbol_enabled": True}}
    two.pop(("15m_dynamic_sr", "SENSEX"))
    line = P.status_line(P.bot_status(syms, _settings(two)), syms)
    assert line.startswith("⚠️ 2 bots active: 15M SRv2 (NIFTY / BANKNIFTY; engine; PAPER) · 5M Instant (NIFTY; own; PAPER)")
    part = {k: v for k, v in ONE_BOT.items() if k[1] != "SENSEX"}
    assert P.status_line(P.bot_status(syms, _settings(part)), syms).endswith("mode PAPER · not active for SENSEX")
    assert P.status_line([], syms).startswith("❌ No bot is active")
    assert P.status_line(None, syms).startswith("❌ Bot settings could not be read")
    msg = _one_bot_report(P, None, lambda s: None, problems=["❌ Upstox login missing — no price data."])
    assert msg.startswith("❌ Bot settings could not be read") and "❌ Upstox login missing" in PT.first_part(msg)


def test_preopen_engine_store_last_run(tmp_path):
    import engine_signal as ES
    P = _preopen()
    p = str(tmp_path / "e.db")
    assert P.engine_last_run("NIFTY", p) is None
    with ES.connect(p) as c:
        c.execute("INSERT INTO engine_signals (symbol, bar_ts, computed_at) VALUES (?, ?, ?)", ("NIFTY", "2026-10-12 15:15:00",
                                                                                              "2026-10-12 15:16:02"))
    assert P.engine_last_run("nifty", p) == pd.Timestamp("2026-10-12 15:16:02")
    assert P.engine_problem("NIFTY", lambda s: (_ for _ in ()).throw(OSError("x")), NOW)[0].startswith("❌ NIFTY: engine status not")


def test_preopen_engine_not_yet_started_is_info_when_cron_installed():
    """पहिल्या engine run आधी (09:45 पर्यंत, आज row नाही): cron ओळ आहे + मागच्या trading session चा row ⇒ ℹ️ "engine starts at 09:31
    (cron installed)"; cron आहे पण मागच्या session चा row नाही ⇒ ❌ "did not run in the last session". Cron ओळ नाही (comment / फक्त warm)
    ⇒ जुने ❌; 09:45 नंतरही row नाही ⇒ ❌."""
    P = _preopen()
    cron = ("1,16,31,46 4-9 * * 1-5 cd /root/Trade && python3 scripts/engine_signal_run.py --engine decision3 >> e.log 2>&1 # one-bot-engine\n")
    warm_only = "20 3 * * 1-5 cd /root/Trade && python3 scripts/engine_signal_run.py --dry-run --force >> e.log 2>&1 # one-bot-engine-warm\n"
    assert P.engine_cron_installed(cron) and not P.engine_cron_installed(warm_only)
    assert not P.engine_cron_installed("#one-bot-off# " + cron) and not P.engine_cron_installed(None)
    prev_row = lambda s: pd.Timestamp("2026-10-12 15:16")                  # noqa: E731 — सोम 12 Oct (मागचा session)
    info, t = P.engine_problem("NIFTY", prev_row, NOW, cron_installed=True)
    assert info.startswith("ℹ️ NIFTY: engine starts at 09:31 (cron installed)") and "❌" not in info and t == pd.Timestamp("2026-10-12 15:16")
    assert P.engine_problem("NIFTY", prev_row, pd.Timestamp("2026-10-13 09:40"), cron_installed=True)[0].startswith("ℹ️")
    # cron आहे, पण मागच्या session चा row नाही (store रिकामा / जुना row) ⇒ ❌
    for fn in (lambda s: None, lambda s: pd.Timestamp("2026-10-09 15:16")):
        bad = P.engine_problem("NIFTY", fn, NOW, cron_installed=True)[0]
        assert bad == "❌ NIFTY: engine did not run in the last session (12 Oct) — check engine_signal.log."
    # weekend + सुट्टी: सोम 5 Oct चा मागचा session = गुरु 1 Oct (2 Oct गांधी जयंती)
    assert P.previous_session(pd.Timestamp("2026-10-05")) == pd.Timestamp("2026-10-01").date()
    assert P.engine_problem("NIFTY", lambda s: pd.Timestamp("2026-10-01 15:16"), pd.Timestamp("2026-10-05 09:00"),
                            cron_installed=True)[0].startswith("ℹ️")
    late = P.engine_problem("NIFTY", lambda s: None, pd.Timestamp("2026-10-13 09:46"), cron_installed=True)[0]
    assert late.startswith("❌ NIFTY: the engine has no records")
    assert P.engine_problem("NIFTY", lambda s: None, NOW, cron_installed=False)[0].startswith("❌ NIFTY: the engine has no records")
    assert P.engine_problem("NIFTY", lambda s: pd.Timestamp("2026-10-13 09:31"), pd.Timestamp("2026-10-13 09:40"), cron_installed=True)[0] is None
    active = P.bot_status(["NIFTY", "BANKNIFTY", "SENSEX"], _settings(ONE_BOT))
    msg = _one_bot_report(P, active, prev_row, engine_cron=True)
    top = PT.first_part(msg)
    assert "❌" not in "".join(ln for ln in top.splitlines() if "engine" in ln) and top.count("engine starts at 09:31 (cron installed)") == 3
    assert "NIFTY engine: last run 12 Oct 15:16" in msg.split(PT.SEP)[1]
    top = PT.first_part(_one_bot_report(P, active, lambda s: None, engine_cron=True))
    assert top.count("engine did not run in the last session") == 3 and "engine starts at" not in top
    top = PT.first_part(_one_bot_report(P, active, lambda s: None, engine_cron=False))
    assert "❌ NIFTY: the engine has no records" in top and "engine starts at" not in top


def test_preopen_dry_run_does_not_send(monkeypatch, capsys):
    import cloud_db
    import notifications
    P = _preopen()
    sent = []
    monkeypatch.setattr(notifications, "send_telegram_message", lambda m: sent.append(m))
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda x: None)
    monkeypatch.setattr(cloud_db, "get_connection", lambda: None)
    monkeypatch.setattr(cloud_db, "get_strategy_settings", _settings(ONE_BOT))
    monkeypatch.setattr(cloud_db, "get_market_zones", lambda s: None)
    monkeypatch.setattr(LR, "daily_trend", lambda s, tok, fetch=None: {"ok": False, "trend": "UNKNOWN", "sides": set(), "reason": "x"})
    monkeypatch.setattr(P, "engine_last_run", lambda s, path=None: None)
    from bots_common import level_visibility as LV
    monkeypatch.setattr(LV, "mcx_symbols", lambda get_settings=None: ())
    assert P.main(["--dry-run"]) == 0 and sent == []
    out = capsys.readouterr().out
    assert out.startswith("❌ Upstox token") and "Only 15M SRv2 active · signal source: engine" in out
    assert "❌ Upstox login missing" in out and "❌ Settings database not reachable" in out and "❌ <b>NIFTY</b>: NO NEW ENTRIES" in out


# ------------------------------------------------------------------------------------------------ 4. 15:45 सारांश
def _summary():
    from scripts import paper_daily_summary as S
    return S


GATE_ROWS = {"NIFTY": [], "BANKNIFTY": [
    {"symbol": "BANKNIFTY", "level_type": "DYNAMIC_SR_SUPPORT_15M", "level_price": 50850.0, "trade_status": "SKIPPED_GATE_WAITING_COMMITMENT",
     "signal_time": "2026-10-09 10:00"},
    {"symbol": "BANKNIFTY", "level_type": "DYNAMIC_SR_SUPPORT_15M", "level_price": 50850.0, "trade_status": "SKIPPED_GATE_RR",
     "signal_time": "2026-10-09 10:30"}]}


def _section(S, **kw):
    ctx = {"NIFTY": NIFTY, "BANKNIFTY": BANK}
    zz = {"NIFTY": ZONES, "BANKNIFTY": pd.DataFrame([{"zone_type": "DYNAMIC_SR_SUPPORT_15M", "zone_low": 50800.0, "zone_high": 50900.0,
                                                      "status": "ACTIVE"}])}
    rng = {"NIFTY": {"high": 22625.0, "low": 22480.0}, "BANKNIFTY": {"high": 51300.0, "low": 50830.0}}
    args = dict(symbols=("NIFTY", "BANKNIFTY"),                            # = default signal_symbols (DB ला हात नाही; default path: test_preopen_symbols_bands)
                ctx_fn=lambda s, d: ctx.get(s), rows_fn=lambda s, d: (GATE_ROWS[s], None) if s in GATE_ROWS else (None, "db"),
                zones_fn=lambda s: zz[s], range_fn=lambda s, d: rng.get(s))
    args.update(kw)
    return S.symbols_section("2026-10-09", **args)


def test_summary_symbol_lines_plain_words_like_abhis_example():
    S = _summary()
    txt = _section(S)
    lines = txt.splitlines()
    assert lines[0] == ("<b>NIFTY</b>: no setup today. Trend DOWN (daily), but price never reached a supply area. Nearest supply "
                        "22,715–22,776 (1H, ≈90 pts above the high), 61 pts wide. Daily move: mature (context only), near target 22,183.")
    # ↑ ", 61 pts wide" = Abhi (merged band — check): पट्ट्याची रुंदी दाखवणं (हेतुपूर्वक wording बदल, निर्णय नाही)
    assert lines[1].startswith("<b>BANKNIFTY</b>: no setup today. Trend UP (daily). Price reached a demand area 1 time; no entry because "
                               "the reward was too small for the risk.") and "Price traded into demand 50,800–50,900" in lines[1]
    assert len(lines) == 2 and "SENSEX" not in txt                       # default = signal_symbols (NIFTY, BANKNIFTY) — SENSEX ची ओळ नाही
    three = _section(S, symbols=("NIFTY", "BANKNIFTY", "SENSEX")).splitlines()
    assert three[2] == "<b>SENSEX</b>: no data today (no trend file, bot records and day high / low not available)."
    assert not PT.has_raw_codes(txt)


def test_maturity_is_one_context_line_and_never_a_grade_cap():
    """Abhi B1 (trader's patience, 13 Oct final): maturity = context only — no grade cap anywhere (level gate, engine, texts). Pre-open
    and the 15:45 summary print one context line "daily move: mature (context only)", whatever the structure."""
    P, S = _preopen(), _summary()
    weak = {**NIFTY, "counter": "correction"}
    for c in (NIFTY, weak):
        assert LR.mature_cap(c) is None
        line = P.symbol_line("NIFTY", c, "UP", 22565.0, ZONES)
        assert "(daily move: mature (context only))" in line and "grade at most" not in line
    assert LR.mature_cap({**NIFTY, "mature": False}) is None and LR.mature_words({**NIFTY, "mature": False}) is None
    txt = _section(S, ctx_fn=lambda s, d: {"NIFTY": weak, "BANKNIFTY": BANK}.get(s))
    assert "Daily move: mature (context only), near target 22,183." in txt.splitlines()[0] and "grade at most" not in txt


def test_summary_partial_data_says_so():
    S = _summary()
    txt = _section(S, range_fn=lambda s, d: None, rows_fn=lambda s, d: (_ for _ in ()).throw(RuntimeError("db down")))
    nifty = txt.splitlines()[0]
    assert "bot records not available" in nifty and "Day high / low not available" in nifty and "Daily move: mature (context only)" in nifty


def test_summary_one_message_headline_decisions_pnl_details(monkeypatch):
    S = _summary()
    from vision import approval as AP
    monkeypatch.setattr(AP, "daily_summary", lambda day=None, *a, **k: {
        "day": day, "approvals": 1, "modifications": 1, "modified_approved": 1, "limit_expired": 0, "rejections": {"wrong zone": 2},
        "timeouts": 1, "corrections": 0, "pnl": -850.0, "trades_closed": 1, "trades_open": 0, "would_have": 2})
    sent = []
    assert S.main(["--day", "2026-10-09"], send=sent.append, plain=lambda d: _section(S), level=lambda d: "🎯 Level bots — gate a:D2+b") == 0
    assert len(sent) == 1 and len(sent[0]) <= S.TG_MAX
    msg = sent[0]
    top = _shape(msg, PT.DECISION_NONE)
    assert top.startswith("🗓 Day summary 2026-10-09 (15:45, PAPER)")
    assert "<b>NIFTY</b>: no setup today." in top and "SENSEX" not in top   # default signal_symbols ⇒ SENSEX ची ओळ नाही
    assert "approved 1 (1 with a changed entry), rejected 2 (wrong zone 2), changed entry 1, no answer 1." in top
    assert "net P&L <b>₹-850</b>" in top and "Skipped trades tracked for comparison: 2" in top
    assert "a:D2+b" in msg.split(PT.SEP)[1]                                            # gate तपशील details मध्येच


# ------------------------------------------------------------------------------------------------ PR #307 review fixes
def test_caption_limit_counts_utf16_units_with_emoji(tmp_path):
    d = _run(tmp_path, ["v22_check"], raw="🧭📈🟡✅ " * 400)
    m = RT.load_manifest(d)
    cap = RT.caption(m, {**m["items"][0], "headline": "📈" * 50 + " look at the area"})
    assert PT.tg_len(cap) <= 1024 - PT.MARGIN and len(cap) < PT.tg_len(cap) and cap.endswith("…")
    assert PT.tg_cut("a📈b", 2) == "a" and PT.tg_len("📈") == 2


def test_v1_caption_worst_case_keeps_deadline_and_no_buttons_warning(monkeypatch):
    from vision import decide as VD
    from vision import worker as VW
    monkeypatch.setattr(VW, "engine_line", lambda row: "engine: " + "📈" * 200)
    row = _gate_row()
    tags = json.loads(row["setup_json"])["tags"]
    tags["gate"]["study"] = "🟡 " * 300
    tags["gate"]["commit_line"] = "✅ " * 300
    tags.update(manual=True, manual_text="✋ MANUAL " + "🧪" * 200)
    row = {**row, "bot_label": "B" * 200, "setup_json": json.dumps({"tags": tags})}
    res = {"verdict": "unavailable", "error": "x" * 200}
    d = VD.Decision("PENDING_HUMAN", 1.0, "human", "REJECTED", 0.0)
    cap = VW.v1_caption(row, res, d, "2026-10-09T12:25:00", buttons=False, why="no approver")
    assert PT.tg_len(cap) <= 1024 and cap.count("<b>") == cap.count("</b>")
    det = cap.split(PT.SEP + "\n", 1)[1].splitlines()
    assert det[1].startswith("⏱") and det[2].startswith("⚠️ बटणं नाहीत")
    v0 = VW.caption({**row, "tags": {}}, {"verdict": "agree", "audits": [], "error": "📈" * 600}, "notify")
    assert PT.tg_len(v0) <= 1024 and v0.count("<b>") == v0.count("</b>")


def test_preopen_escapes_html_and_retries_plain_text(capsys):
    P = _preopen()
    bad = {**SENSEX, "reason": "trend <unclear> & x", "trend": "<NEUTRAL>", "phase": None}
    msg = P.build_report(["SENSEX"], "tok", lambda s: None, lambda s: None, trend_fn=lambda s: bad, day="2026-10-13",
                         active=[{"label": "15M SRv2", "symbol": "SENSEX", "source": "<engine>", "mode": "PAPER"}],
                         engine_fn=lambda s: NOW, now=NOW)
    assert "<unclear>" not in msg and "&lt;unclear&gt;" in msg and "&lt;engine&gt;" in msg and "<NEUTRAL>" not in msg
    sent = []
    assert P.send_checked("<b>x</b> &lt;y&gt;", lambda t: sent.append(t) or len(sent) > 1) is True
    assert sent == ["<b>x</b> &lt;y&gt;", "x &lt;y&gt;"] and "retrying as plain text" in capsys.readouterr().out
    assert P.send_checked("m", lambda t: (_ for _ in ()).throw(OSError("net"))) is False
    assert "NOT sent" in capsys.readouterr().out


def test_kindless_item_in_debug_named_run_refused():
    assert RT.item_refusal({"kind": None}, {"run_id": "review/v22/diag_q1516", "title": "x"})
    assert RT.item_refusal({"kind": None}, {"run_id": "k10/run1", "title": "K-10"}) is None
