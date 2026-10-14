"""One bot (Abhi): set_one_bot_mode (before / after / revert / dry-run / LIVE नकार, dashboard getter तेच दाखवतो), one_bot_status,
install_engine_schedule.sh (idempotent, revert तंतोतंत, LIVE ओळ untouched), decision3 live engine ⇒ store ⇒ adapter, fail-closed. Network नाही."""
import json
import os
import re
import subprocess

import pandas as pd
import pytest

import cloud_db
import engine3_live as L
import engine_signal as ES
from bots_common import one_bot as OB
from paper import config as PC
from scripts import engine_signal_run as ESR
from scripts import set_one_bot_mode as SOB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------------------ fake Supabase (cloud_db चा SQL मार्ग)
class FakeDB:
    def __init__(self, rows=None):
        self.rows = {k: dict(v) for k, v in (rows or {}).items()}

    def conn(self):
        db = self

        class Cur:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=()):
                s = " ".join(sql.split())
                self.res = None
                if s.startswith("SELECT settings FROM strategy_settings"):
                    r = db.rows.get(tuple(params))
                    self.res = [(dict(r),)] if r is not None else []
                elif s.startswith("INSERT INTO strategy_settings"):
                    k = (params[0], params[1])
                    db.rows[k] = {**db.rows.get(k, {}), **json.loads(params[2])}
                elif s.startswith("UPDATE strategy_settings SET settings = settings -"):
                    keys, k = params[0], (params[1], params[2])
                    if k in db.rows:
                        db.rows[k] = {a: b for a, b in db.rows[k].items() if a not in keys}
                elif s.startswith("SELECT strategy_name, symbol, settings"):
                    self.res = [(a, b, dict(v)) for (a, b), v in db.rows.items()]
                else:
                    raise AssertionError(s)

            def fetchone(self):
                return self.res[0] if self.res else None

            def fetchall(self):
                return list(self.res or [])

        class Conn:
            def cursor(self):
                return Cur()

            def commit(self):
                pass

            def close(self):
                pass
        return Conn()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_DB_PATH", str(tmp_path / "vision.db"))
    monkeypatch.setenv("PAPER_LOCAL_CONFIG", str(tmp_path / "paper_local.yaml"))
    cron = tmp_path / "cron"
    cron.write_text("* 4-10 * * 1-5 cd /root/Trade && sleep 30 && python3 srv2_momentum_reversal_strategy.py >> s.log 2>&1\n"
                    "1,16,31,46 4-9 * * 1-5 cd /root/Trade && python3 scripts/engine_signal_run.py >> e.log 2>&1 # one-bot-engine\n")
    monkeypatch.setenv("CRONTAB_FILE", str(cron))
    abhi = {"lots": 3, "itm_depth_points": 250, "hedge_width_points": 400, "spread_sl_spot_pct": 0.2, "entry_mode": "confirmation"}
    db = FakeDB({("15m_dynamic_sr", "NIFTY"): dict(abhi, signal_source="own"),
                 ("1m_instant", "NIFTY"): {"symbol_enabled": True, "srv3_shadow_enabled": True, "lots": 2},
                 ("classic_sr_reversal", "BANKNIFTY"): {"symbol_enabled": True},
                 ("mcx_futures", "GOLD"): {"symbol_enabled": True, "trading_mode": "LIVE", "lots": 1}})
    monkeypatch.setattr(cloud_db, "get_connection", db.conn)
    cloud_db._LAST_GOOD_STRATEGY_SETTINGS.clear()
    return db, abhi, tmp_path


def test_dry_run_writes_nothing(env, capsys):
    db, _, tmp = env
    before = repr(sorted(db.rows.items()))
    assert SOB.main(["--dry-run", "--state", str(tmp / "st.json")]) == 0
    out = capsys.readouterr().out
    assert repr(sorted(db.rows.items())) == before and not (tmp / "st.json").exists()
    assert "signal_source" in out and "LIVE" in out and "dry-run" in out


def test_apply_then_dashboard_getter_shows_one_bot_and_revert_is_exact(env, capsys):
    db, abhi, tmp = env
    before = {k: dict(v) for k, v in db.rows.items()}
    st = str(tmp / "st.json")
    assert SOB.main(["--state", st]) == 0
    out = capsys.readouterr().out
    assert "Only 15M SRv2 active · signal source: engine · symbols NIFTY / BANKNIFTY · mode PAPER" in out   # signal_symbols default
    assert "SENSEX" not in out.split("Only 15M SRv2 active")[1].split("\n")[0]
    for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):                     # dashboard चा getter (page_bot_dynamic_sr_algo) तेच वाचतो
        s = cloud_db.get_strategy_settings("15m_dynamic_sr", sym)
        if sym == "SENSEX":                                          # signal symbol नाही ⇒ 15M SRv2 सुद्धा OFF (data फक्त)
            assert s["symbol_enabled"] is False and s.get("signal_source", "own") == "own"
        else:
            assert s["symbol_enabled"] is True and s["signal_source"] == "engine" and s["trading_mode"] == "PAPER"
            assert PC.enabled(sym)
        assert cloud_db.get_strategy_settings("1m_instant", sym)["symbol_enabled"] is False
        assert cloud_db.get_strategy_settings("1m_instant", sym)["srv3_shadow_enabled"] is False
        assert cloud_db.get_strategy_settings("classic_sr_reversal", sym)["symbol_enabled"] is False
    s = cloud_db.get_strategy_settings("15m_dynamic_sr", "NIFTY")
    assert all(s[k] == v for k, v in abhi.items())                    # Abhi चे strikes / lots / SL / entry_mode तसेच
    assert cloud_db.get_strategy_settings("1m_instant", "NIFTY")["lots"] == 2
    gold = db.rows[("mcx_futures", "GOLD")]
    assert gold == {"symbol_enabled": True, "trading_mode": "LIVE", "lots": 1}                     # LIVE ला हात नाही
    assert cloud_db.get_strategy_settings("mcx_futures", "CRUDEOIL")["symbol_enabled"] is False
    from vision import config as VC
    v = VC.load(OB.VISION_BOT)
    assert v["symbols"] == ["NIFTY", "BANKNIFTY"] and v["approval_required"] is True          # SENSEX ⇒ approval मार्ग नाही
    st_ = OB.one_bot_status()
    sx = next(r for r in st_["bots"] if r["strategy"] == OB.ON_KEY and r["symbol"] == "SENSEX")
    assert st_["signal_symbols"] == ["NIFTY", "BANKNIFTY"] and sx["on"] is False and sx["signal_symbol"] is False
    assert SOB.main(["--revert", "--state", st]) == 0
    assert {k: v for k, v in db.rows.items() if v} == {k: v for k, v in before.items() if v}       # नवे keys काढले, जुने परत
    assert not os.path.exists(os.environ["PAPER_LOCAL_CONFIG"]) and not PC.enabled("BANKNIFTY")
    assert VC.load(OB.VISION_BOT)["symbols"] == ["NIFTY"]


def test_live_srv2_is_refused(env, capsys):
    db, _, tmp = env
    db.rows[("15m_dynamic_sr", "BANKNIFTY")] = {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    db.rows[("15m_dynamic_sr", "SENSEX")] = {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    SOB.main(["--state", str(tmp / "st.json")])
    out = capsys.readouterr().out
    assert "15M SRv2 BANKNIFTY: trading_mode LIVE" in out and "15M SRv2 SENSEX: trading_mode LIVE" in out
    for sym in ("BANKNIFTY", "SENSEX"):                              # LIVE ⇒ हात नाही (signal symbol असो वा नसो)
        assert db.rows[("15m_dynamic_sr", sym)] == {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    st = OB.one_bot_status()
    assert not st["ok"] and st["line"].startswith("❌") and "15M SRv2 BANKNIFTY LIVE" in st["line"]
    assert "15M SRv2 SENSEX LIVE" in st["line"]                      # non-signal LIVE ⇒ ⚠️ LIVE (untouched) नोंद


def test_signal_symbols_setting_drives_one_bot(env, capsys):
    """Dashboard setting signal_symbols (default NIFTY / BANKNIFTY): SENSEX ⇒ 15M SRv2 OFF, Vision approval नाही, status ओळीत नाही;
    setting बदलला ⇒ तोच (hard-coded यादी नाही)."""
    db, _, tmp = env
    assert cloud_db.get_signal_symbols() == ["NIFTY", "BANKNIFTY"]                              # नोंद नाही ⇒ default
    with pytest.raises(ValueError):
        cloud_db.clean_signal_symbols(["NIFTY", "CRUDEOIL"])
    with pytest.raises(ValueError):
        cloud_db.clean_signal_symbols([])
    db.rows[("15m_dynamic_sr", "SENSEX")] = {"symbol_enabled": True, "signal_source": "engine", "trading_mode": "PAPER"}
    from vision import config as VC
    VC.save(OB.VISION_BOT, {"symbols": ["NIFTY", "BANKNIFTY", "SENSEX"]}, by="test")              # मागच्या deploy सारखं
    SOB.main(["--state", str(tmp / "st.json")])
    assert db.rows[("15m_dynamic_sr", "SENSEX")]["symbol_enabled"] is False
    assert VC.load(OB.VISION_BOT)["symbols"] == ["NIFTY", "BANKNIFTY"]
    st = OB.one_bot_status()
    assert "SENSEX" not in st["line"] and st["signal_symbols"] == ["NIFTY", "BANKNIFTY"]
    db.rows[("15m_dynamic_sr", "SENSEX")]["symbol_enabled"] = True                               # कुणी हाताने चालू केलं ⇒ ❌
    OB.write_paper_local(os.environ["PAPER_LOCAL_CONFIG"], {"SENSEX": True})
    VC.save(OB.VISION_BOT, {"symbols": ["NIFTY", "BANKNIFTY", "SENSEX"]}, by="test")
    cloud_db._LAST_GOOD_STRATEGY_SETTINGS.clear()
    st = OB.one_bot_status()
    assert not st["ok"] and "15M SRv2 SENSEX ON (not a signal symbol)" in st["problems"]
    assert "Vision symbols include SENSEX (not a signal symbol)" in st["problems"]
    assert cloud_db.save_signal_symbols("nifty") is True and cloud_db.get_signal_symbols() == ["NIFTY"]
    SOB.main(["--state", str(tmp / "st.json")])
    assert db.rows[("15m_dynamic_sr", "BANKNIFTY")]["symbol_enabled"] is False and VC.load(OB.VISION_BOT)["symbols"] == ["NIFTY"]
    assert "symbols NIFTY · mode PAPER" in OB.one_bot_status()["line"]


class _Log:
    """log_setup logger ऐवजी — (level, formatted message) नोंदी."""
    def __init__(self):
        self.lines = []

    def info(self, msg, *a):
        self.lines.append(("INFO", msg % a))

    def error(self, msg, *a):
        self.lines.append(("ERROR", msg % a))


def _now():
    return pd.Timestamp("2030-01-07 10:05:00")


def test_dashboard_signal_symbols_save_applies_one_bot_part(env):
    """Abhi 9a (PF-3): dashboard save ⇒ script चाच plan (signal-symbols भाग) लगेच: 15M SRv2 per symbol, Vision srv2 symbols, PAPER instruments.
    बाकी bots (5M / Classic / MCX) ला हात नाही; before-state file नाही; log मध्ये before / after + by dashboard + वेळ."""
    db, abhi, tmp = env
    from vision import config as VC
    assert cloud_db.save_signal_symbols(["NIFTY"]) is True
    log = _Log()
    res = OB.apply_signal_symbols(before=["NIFTY", "BANKNIFTY"], after=["NIFTY"], now_fn=_now, logger=log)
    assert res["ok"] and res["failed"] is None and res["not_run"] == [] and res["at"] == "2030-01-07T10:05:00"
    assert res["applied"] == ["15m_dynamic_sr NIFTY", "15m_dynamic_sr BANKNIFTY", "15m_dynamic_sr SENSEX", "Vision srv2 symbols",
                              "PAPER instruments"]
    n = cloud_db.get_strategy_settings("15m_dynamic_sr", "NIFTY")
    assert n["symbol_enabled"] is True and n["signal_source"] == "engine" and n["trading_mode"] == "PAPER" and n["lots"] == abhi["lots"]
    assert db.rows[("15m_dynamic_sr", "BANKNIFTY")] == {"symbol_enabled": False}
    assert db.rows[("15m_dynamic_sr", "SENSEX")] == {"symbol_enabled": False}
    assert VC.load(OB.VISION_BOT)["symbols"] == ["NIFTY"] and VC.load(OB.VISION_BOT)["approval_required"] is True
    assert VC.history(OB.VISION_BOT)[-1]["by"] == "dashboard"
    assert PC.enabled("NIFTY")
    assert db.rows[("1m_instant", "NIFTY")]["symbol_enabled"] is True                      # signal-symbols भाग नाही ⇒ हात नाही
    assert db.rows[("classic_sr_reversal", "BANKNIFTY")] == {"symbol_enabled": True}
    assert not any(p.name.endswith(".json") for p in tmp.iterdir())                         # before-state file नाही (script चाच)
    (lvl, msg), = log.lines
    assert lvl == "INFO" and "signal_symbols apply OK at=2030-01-07T10:05:00" in msg and '"by": "dashboard"' in msg
    assert '"before": ["NIFTY", "BANKNIFTY"], "after": ["NIFTY"]' in msg and '"key": "symbol_enabled"' in msg
    again = OB.apply_signal_symbols(before=["NIFTY"], after=["NIFTY"], now_fn=_now, logger=log)    # दुसऱ्यांदा ⇒ बदल नाहीत (idempotent)
    assert again["ok"] and all(c["before"] == c["after"] for c in again["changes"])


def test_dashboard_signal_symbols_save_still_refuses_live(env):
    db, _, tmp = env
    db.rows[("15m_dynamic_sr", "BANKNIFTY")] = {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    assert cloud_db.save_signal_symbols(["NIFTY"]) is True
    log = _Log()
    res = OB.apply_signal_symbols(before=["NIFTY", "BANKNIFTY"], after=["NIFTY"], now_fn=_now, logger=log)
    assert res["ok"] and "15m_dynamic_sr BANKNIFTY" not in res["applied"]
    assert any("15M SRv2 BANKNIFTY: trading_mode LIVE" in w for w in res["warnings"])
    assert db.rows[("15m_dynamic_sr", "BANKNIFTY")] == {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    assert any(c["symbol"] == "BANKNIFTY" and c["skip"] == "LIVE" for c in res["changes"])
    # plan नंतर कुणी LIVE केलं (race) ⇒ लिहिण्याआधीचा तपास ⇒ skipped_live, लिहिलं नाही
    db.rows[("15m_dynamic_sr", "NIFTY")] = {"symbol_enabled": False, "signal_source": "own"}
    cloud_db._LAST_GOOD_STRATEGY_SETTINGS.clear()
    io = OB.IO(by="dashboard")
    changes, _ = OB.plan(io, parts=OB.SIGNAL_SYMBOL_PARTS)
    assert any(c["symbol"] == "NIFTY" and c["key"] == "symbol_enabled" and c["after"] is True and not c["skip"] for c in changes)
    db.rows[("15m_dynamic_sr", "NIFTY")]["trading_mode"] = "LIVE"
    cloud_db._LAST_GOOD_STRATEGY_SETTINGS.clear()
    rep = OB.apply_reported(io, changes)
    assert rep["ok"] and "15m_dynamic_sr NIFTY" in rep["skipped_live"]
    assert db.rows[("15m_dynamic_sr", "NIFTY")] == {"symbol_enabled": False, "signal_source": "own", "trading_mode": "LIVE"}


def test_dashboard_signal_symbols_apply_failure_reports_parts(env):
    """एखादा भाग अयशस्वी ⇒ पुढचे थांबतात, कोणते लागले / कोणते नाही ते निकालात + ERROR log; raise नाही. Plan च अयशस्वी ⇒ काहीच लिहिलं नाही."""
    db, _, tmp = env

    class BadVision(OB.IO):
        def vision_save(self, bot, changes):
            raise RuntimeError("vision db locked")
    assert cloud_db.save_signal_symbols(["NIFTY"]) is True
    log = _Log()
    res = OB.apply_signal_symbols(before=["NIFTY", "BANKNIFTY"], after=["NIFTY"], io=BadVision(by="dashboard"), now_fn=_now, logger=log)
    assert not res["ok"] and res["failed"] == {"part": "Vision srv2 symbols", "error": "RuntimeError: vision db locked"}
    assert res["applied"] == ["15m_dynamic_sr NIFTY", "15m_dynamic_sr BANKNIFTY", "15m_dynamic_sr SENSEX"] and res["not_run"] == ["PAPER instruments"]
    assert db.rows[("15m_dynamic_sr", "BANKNIFTY")] == {"symbol_enabled": False}               # लागलेला भाग खरंच लिहिला
    assert not os.path.exists(os.environ["PAPER_LOCAL_CONFIG"])                               # न चाललेला भाग लिहिला नाही
    assert log.lines[-1][0] == "ERROR" and "FAILED" in log.lines[-1][1] and "vision db locked" in log.lines[-1][1]

    class BadRead(OB.IO):
        def effective(self, strategy, symbol):
            raise RuntimeError("supabase down")
    before = repr(sorted(db.rows.items()))
    res = OB.apply_signal_symbols(before=["NIFTY", "BANKNIFTY"], after=["NIFTY"], io=BadRead(), now_fn=_now, logger=log)
    assert not res["ok"] and res["failed"]["part"].startswith("plan") and res["applied"] == []
    assert repr(sorted(db.rows.items())) == before and log.lines[-1][0] == "ERROR"


def test_dashboard_apply_uses_saved_symbols_and_refuses_stale_read(env, monkeypatch):
    """Review #328 blocker: सेव्ह नंतरचं वाचन अयशस्वी ⇒ get_signal_symbols जुनी / default यादी देतो ⇒ काहीच लावायचं नाही, failed
    "signal_symbols read" (✅ नाही). plan ला `after` हीच यादी (override) जाते."""
    db, _, tmp = env
    from vision import config as VC
    db.rows[("15m_dynamic_sr", "BANKNIFTY")] = {"symbol_enabled": True, "signal_source": "engine", "trading_mode": "PAPER"}
    before = repr(sorted(db.rows.items()))
    monkeypatch.setattr(cloud_db, "get_signal_symbols", lambda: ["NIFTY", "BANKNIFTY"])          # read fail ⇒ जुनी यादी
    log = _Log()
    res = OB.apply_signal_symbols(before=["NIFTY", "BANKNIFTY"], after=["nifty"], now_fn=_now, logger=log)
    assert not res["ok"] and res["failed"]["part"] == "signal_symbols read" and res["applied"] == [] and res["changes"] == []
    assert "NIFTY', 'BANKNIFTY'] ≠ saved ['NIFTY']" in res["failed"]["error"]
    assert repr(sorted(db.rows.items())) == before and db.rows[("15m_dynamic_sr", "BANKNIFTY")]["symbol_enabled"] is True
    assert log.lines[-1][0] == "ERROR"

    class BoomRead(OB.IO):
        def signal_symbols(self):
            raise RuntimeError("db down")
    res = OB.apply_signal_symbols(after=["NIFTY"], io=BoomRead(), now_fn=_now, logger=log)
    assert res["failed"]["part"] == "signal_symbols read" and "db down" in res["failed"]["error"]
    res = OB.apply_signal_symbols(after=["NIFTY", "CRUDEOIL"], now_fn=_now, logger=log)          # अवैध ⇒ काहीच नाही
    assert res["failed"]["part"] == "signal_symbols (after)" and repr(sorted(db.rows.items())) == before
    # override: io काहीही म्हणो, plan ला दिलेली यादीच
    changes, _ = OB.plan(OB.IO(), parts=OB.SIGNAL_SYMBOL_PARTS, symbols=["NIFTY"])
    bn = next(c for c in changes if c["strategy"] == OB.ON_KEY and c["symbol"] == "BANKNIFTY")
    assert bn["after"] is False and next(c for c in changes if c["key"] == "symbols")["after"] == ["NIFTY"]
    assert VC.load(OB.VISION_BOT)["symbols"] == ["NIFTY"]                                       # (default; अजून काही लिहिलं नाही)


def test_live_check_uses_raw_row_when_settings_read_falls_back(env):
    """Review #328: get_strategy_settings read अयशस्वी ⇒ defaults (PAPER) दिसतात; raw row LIVE ⇒ combo skip, लिहिलं नाही — plan मध्ये आणि
    लिहिण्याआधीच्या तपासात. Raw read अयशस्वी (लिहिण्याआधी) ⇒ तो टप्पा failed, लिहिलं नाही."""
    db, _, tmp = env
    db.rows[("15m_dynamic_sr", "BANKNIFTY")] = {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}

    class FallbackEff(OB.IO):                                         # read fail ⇒ cloud_db fallback = defaults (PAPER)
        def effective(self, strategy, symbol):
            return dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS.get(strategy, {}))
    io = FallbackEff(by="dashboard")
    changes, warns = OB.plan(io, parts=OB.SIGNAL_SYMBOL_PARTS, symbols=["NIFTY"])
    assert any(c["symbol"] == "BANKNIFTY" and c["strategy"] == OB.ON_KEY and c["skip"] == "LIVE" for c in changes)
    assert any("15M SRv2 BANKNIFTY: trading_mode LIVE" in w for w in warns)
    rep = OB.apply_reported(io, changes)
    assert rep["ok"] and "15m_dynamic_sr BANKNIFTY" not in rep["applied"]
    assert db.rows[("15m_dynamic_sr", "BANKNIFTY")] == {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    # plan PAPER पाहून झाल्यावर raw मध्ये LIVE (race) — effective अजूनही PAPER fallback ⇒ लिहिण्याआधीचा तपास raw पाहतो
    db.rows[("15m_dynamic_sr", "SENSEX")] = {"symbol_enabled": True}
    changes, _ = OB.plan(io, parts=(OB.ON_KEY,), symbols=["NIFTY"])
    db.rows[("15m_dynamic_sr", "SENSEX")]["trading_mode"] = "LIVE_PAPER"
    rep = OB.apply_reported(io, changes)
    assert "15m_dynamic_sr SENSEX" in rep["skipped_live"]
    assert db.rows[("15m_dynamic_sr", "SENSEX")] == {"symbol_enabled": True, "trading_mode": "LIVE_PAPER"}

    class RawFails(FallbackEff):
        def raw(self, strategy, symbol):
            raise RuntimeError("Supabase connection नाही")
    db.rows[("15m_dynamic_sr", "SENSEX")] = {"symbol_enabled": True}
    changes, _ = OB.plan(io, parts=(OB.ON_KEY,), symbols=["NIFTY"])
    rep = OB.apply_reported(RawFails(), changes)
    assert not rep["ok"] and "Supabase connection" in rep["failed"]["error"] and rep["applied"] == []
    assert db.rows[("15m_dynamic_sr", "SENSEX")] == {"symbol_enabled": True}


def test_apply_signal_symbols_never_raises_when_logger_or_clock_break(env, monkeypatch):
    import log_setup

    def boom(*a, **k):
        raise RuntimeError("no log dir")
    monkeypatch.setattr(log_setup, "get_logger", boom)
    assert cloud_db.save_signal_symbols(["NIFTY"]) is True
    res = OB.apply_signal_symbols(before=["NIFTY", "BANKNIFTY"], after=["NIFTY"], now_fn=boom)
    assert res["ok"] and res["at"] is None and "15m_dynamic_sr BANKNIFTY" in res["applied"]


def _signal_symbols_panel_app():
    import page_bot_dynamic_sr_algo as P
    P._render_signal_symbols_panel()


def test_dashboard_panel_save_button_applies_and_shows_result(env):
    """Dashboard 🎯 panel: सेव्ह ⇒ signal_symbols साठवले + one-bot भाग लागला + छोटा निकाल (mocked cloud_db = FakeDB)."""
    from streamlit.testing.v1 import AppTest
    db, _, tmp = env
    at = AppTest.from_function(_signal_symbols_panel_app, default_timeout=60)
    at.run()
    assert not at.exception
    at.multiselect(key="bdsr_signal_symbols").set_value(["NIFTY"])
    at.button(key="bdsr_signal_symbols_save").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert cloud_db.get_signal_symbols() == ["NIFTY"]
    assert any("One-bot mode लागू" in x.value for x in at.success)
    assert any("`signal_source` = engine" in x.value and "'own' किंवा 'both'" in x.value for x in at.caption)
    assert db.rows[("15m_dynamic_sr", "BANKNIFTY")] == {"symbol_enabled": False}


def test_dashboard_panel_stale_read_shows_error_not_success(env, monkeypatch):
    from streamlit.testing.v1 import AppTest
    db, _, tmp = env
    monkeypatch.setattr(OB.IO, "signal_symbols", lambda self: ["NIFTY", "BANKNIFTY"])            # सेव्ह नंतरचं वाचन जुनं
    at = AppTest.from_function(_signal_symbols_panel_app, default_timeout=60)
    at.run()
    at.multiselect(key="bdsr_signal_symbols").set_value(["NIFTY"])
    at.button(key="bdsr_signal_symbols_save").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not any("One-bot mode लागू" in x.value for x in at.success)
    assert any("signal_symbols read" in x.value and "set_one_bot_mode.py" in x.value for x in at.error)
    assert ("15m_dynamic_sr", "BANKNIFTY") not in db.rows


def test_dashboard_panel_shows_error_and_keeps_symbols_when_apply_fails(env, monkeypatch):
    from streamlit.testing.v1 import AppTest
    db, _, tmp = env
    monkeypatch.setattr(OB.IO, "vision_save", lambda self, bot, changes: (_ for _ in ()).throw(RuntimeError("vision db locked")))
    at = AppTest.from_function(_signal_symbols_panel_app, default_timeout=60)
    at.run()
    at.multiselect(key="bdsr_signal_symbols").set_value(["NIFTY"])
    at.button(key="bdsr_signal_symbols_save").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert cloud_db.get_signal_symbols() == ["NIFTY"]                                          # symbols सेव्ह राहिले
    err = " ".join(x.value for x in at.error)
    assert "vision db locked" in err and "set_one_bot_mode.py" in err and "15m_dynamic_sr BANKNIFTY" in err


def test_status_flags_auto_trader_cron_and_missing_engine(env, monkeypatch):
    db, _, tmp = env
    (tmp / "cron").write_text("* 4-10 * * 1-5 python3 srv2_momentum_reversal_strategy.py\n*/5 4-9 * * 1-5 python3 oi_signal_auto_trader.py\n")
    st = OB.one_bot_status()
    assert st["auto_traders"]["oi_signal_auto_trader.py"] == "on" and st["engine_cron"] == "absent" and not st["ok"]
    assert any("oi_signal_auto_trader NIFTY ON" in p for p in st["problems"])
    SOB.main(["--state", str(tmp / "st.json")])                         # PAPER entries settings ने बंद (cron ओळ exits साठी राहू शकते)
    assert db.rows[("oi_signal_auto_trader", "NIFTY")]["symbol_enabled"] is False
    st = OB.one_bot_status()
    assert not any("oi_signal_auto_trader" in p for p in st["problems"]) and not st["ok"]          # engine cron अजून नाही
    assert OB.paper_entry_blocked("oi_signal_auto_trader", "NIFTY", "PAPER")
    assert OB.paper_entry_blocked("oi_signal_auto_trader", "NIFTY", "LIVE") is None              # LIVE ला कधीच नाही
    assert OB.paper_entry_blocked("oi_signal_auto_trader", "BANKNIFTY", "PAPER") is not None
    assert OB.paper_entry_blocked("credit_spread_auto_trader", "NIFTY", "PAPER", raw_fn=lambda *a: {}) is None   # नोंद नाही ⇒ जुनं वर्तन


@pytest.mark.parametrize("line", ["python3 credit_spread_auto_trader.py --mode LIVE", "python3 credit_spread_auto_trader.py --mode=LIVE",
                                  "python3 credit_spread_auto_trader.py --mode \"LIVE\"", "python3 credit_spread_auto_trader.py --mode='LIVE'"])
def test_live_auto_trader_cron_forms_are_live(env, line):
    db, _, tmp = env
    (tmp / "cron").write_text(f"*/5 4-9 * * 1-5 cd /root/Trade && {line}\n")
    assert OB.cron_state((tmp / "cron").read_text())["credit_spread_auto_trader.py"] == "LIVE"
    SOB.main(["--state", str(tmp / "st.json")])
    assert ("credit_spread_auto_trader", "NIFTY") not in db.rows                                  # LIVE ⇒ settings ला हात नाही
    assert any("credit_spread_auto_trader NIFTY LIVE" in x for x in OB.one_bot_status()["live_untouched"])


def test_preopen_message_carries_one_bot_line():
    from scripts import level_gate_preopen as PRE
    assert PRE.one_bot_problems(lambda: {"ok": True, "line": "Only 15M SRv2 active"}) == []
    bad = PRE.one_bot_problems(lambda: {"ok": False, "line": "❌ One-bot mode NOT clean: 5M Instant NIFTY ON <x>"})
    assert bad == ["❌ One-bot mode NOT clean: 5M Instant NIFTY ON &lt;x&gt;"]

    def boom():
        raise RuntimeError("db")
    assert PRE.one_bot_problems(boom)[0].startswith("❌ One-bot status not readable")
    msg = PRE.build_report(["NIFTY"], "t", lambda s: None, lambda s: 22500.0,
                           trend_fn=lambda s: {"ok": False, "trend": "UNKNOWN", "reason": "x", "sides": set()}, problems=bad,
                           active=[{"label": "15M SRv2", "symbol": "NIFTY", "source": "engine", "mode": "PAPER"}],
                           engine_fn=lambda s: None)
    assert msg.startswith("Only 15M SRv2 active · signal source: engine") and "❌ One-bot mode NOT clean" in msg
    assert "❌ NIFTY: the engine has no records" in msg


# ------------------------------------------------------------------------------------------------ install_engine_schedule.sh
def _install(cron, *args, open_src="", check=True):
    return subprocess.run(["bash", os.path.join(ROOT, "scripts", "install_engine_schedule.sh"), *args], capture_output=True, text=True,
                          env={**os.environ, "CRONTAB_FILE": str(cron), "ONE_BOT_OPEN_SOURCES": open_src}, check=check)


ORIG = ("* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> m.log 2>&1\n"
        "\n"
        "1,16,31,46 3-10 * * 1-5 cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/engine_signal_run.py >> engine_signal.log 2>&1\n"
        "*/5 4-9 * * 1-5 cd /root/Trade && python3 oi_signal_auto_trader.py >> o.log 2>&1\n"
        "*/5 4-9 * * 1-5 cd /root/Trade && python3 credit_spread_auto_trader.py --mode LIVE >> c.log 2>&1\n"
        "*/5 4-9 * * 1-5 cd /root/Trade && python3 oi_greeks_vix_strategy.py --mode=LIVE >> g.log 2>&1\n"
        "*/5 4-9 * * 1-5 cd /root/Trade && python3 credit_spread_auto_trader.py --symbol BANKNIFTY --mode 'LIVE' >> c2.log 2>&1\n"
        "\n"
        "* 4-10 * * 1-5 cd /root/Trade && sleep 30 && python3 srv2_momentum_reversal_strategy.py >> s.log 2>&1\n")


def test_schedule_installer_idempotent_and_revert_exact(tmp_path):
    cron = tmp_path / "cron"
    cron.write_text(ORIG)
    out = _install(cron).stdout
    once = cron.read_text()
    _install(cron)
    assert cron.read_text() == once                                   # idempotent
    act = [x for x in once.splitlines() if x and not x.startswith("#")]
    assert sum("scripts/engine_signal_run.py --engine decision3" in x and "--dry-run" not in x for x in act) == 1
    assert "1,16,31,46 4-9 * * 1-5" in once and "engine_signal_run.py --engine decision3 >>" in once   # symbols = dashboard setting
    assert "SENSEX" not in "".join(x for x in once.splitlines() if "engine_signal_run.py" in x and not x.startswith("#"))
    assert sum(x.startswith("30 3 * * 1-5 ") and "scripts/level_gate_preopen.py" in x for x in act) == 1   # 09:00 IST pre-open, एकदाच
    assert "#one-bot-off# 1,16,31,46 3-10" in once and "#one-bot-off# */5 4-9 * * 1-5 cd /root/Trade && python3 oi_signal" in once
    for live in ("credit_spread_auto_trader.py --mode LIVE", "oi_greeks_vix_strategy.py --mode=LIVE", "--mode 'LIVE'"):
        assert any(live in x for x in act), live                      # LIVE ओळी (सगळे प्रकार) untouched
    assert out.count("LIVE auto-trader") == 3
    assert "trade_monitor.py" in once and "# one-bot-srv2" not in once and "\n\n" in once
    _install(cron, "--revert")
    assert cron.read_text() == ORIG                                   # रिकाम्या ओळींसकट तंतोतंत


def test_schedule_installer_keeps_auto_trader_line_with_open_position(tmp_path):
    cron = tmp_path / "cron"
    cron.write_text(ORIG)
    r = _install(cron, open_src="oi_signal_auto_trader")
    once = cron.read_text()
    assert "\n*/5 4-9 * * 1-5 cd /root/Trade && python3 oi_signal_auto_trader.py" in once and "#one-bot-off# */5 4-9 * * 1-5 cd /root/Trade && python3 oi_signal" not in once
    assert "oi_signal_auto_trader: open position" in r.stderr
    _install(cron, open_src="UNKNOWN")                                # तपासता आलं नाही ⇒ सुरक्षित: ओळ चालू
    assert "#one-bot-off# */5 4-9 * * 1-5 cd /root/Trade && python3 oi_signal" not in cron.read_text()


def test_schedule_installer_aborts_without_trade_monitor_or_crontab(tmp_path):
    cron = tmp_path / "cron"
    cron.write_text("1,16,31,46 3-10 * * 1-5 python3 scripts/engine_signal_run.py\n# * * * * * python3 trade_monitor.py\n")
    r = _install(cron, check=False)
    assert r.returncode == 1 and "❌" in r.stdout
    assert cron.read_text() == "1,16,31,46 3-10 * * 1-5 python3 scripts/engine_signal_run.py\n# * * * * * python3 trade_monitor.py\n"
    r = _install(tmp_path / "missing", check=False)
    assert r.returncode == 1 and not (tmp_path / "missing").exists()


def test_schedule_installer_adds_srv2_when_missing_and_dry_run(tmp_path):
    cron = tmp_path / "cron"
    cron.write_text("* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py\n")
    out = _install(cron, "--dry-run").stdout
    assert "# one-bot-srv2" in out and cron.read_text() == "* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py\n"


def test_deploy_script_syntax_and_live_readonly():
    p = os.path.join(ROOT, "scripts", "deploy_one_bot.sh")
    subprocess.run(["bash", "-n", p], check=True)
    s = open(p, encoding="utf-8").read()
    body = s[s.index('echo "== 1/7'):]
    assert body.index("bash scripts/install_engine_schedule.sh\n") < body.index("python3 scripts/set_one_bot_mode.py; RC")   # status तपासणीला engine cron आधी हवा
    assert "list-units --type=service" in s and ". ./.env" in s and "--revert" in s and '"$RC" = 3' in s and "LIVE" not in s.replace("LIVE ला हात नाही", "").replace(
        "LIVE combos", "").replace("LIVE cron", "").replace("LIVE setting", "")


# ------------------------------------------------------------------------------------------------ live decision3 ⇒ store ⇒ adapter
def v22_setup(symbol, bar_end, role="resistance"):
    return {"bar": 10, "ts": str(pd.Timestamp(bar_end) - pd.Timedelta(minutes=15)), "bar_end": str(bar_end), "daily_trend": "DOWN",
            "trend_used": "DOWN", "decision": "setup", "mark": "🟡", "conviction": "B",
            "checklist": {"①": [True, "Daily DOWN"], "②": [True, "resistance"], "③": [True, "at"], "④": [True, "ps"], "⑤": [None, "—"],
                          "⑥": [True, "commit"], "⑦": [True, "R:R 3.4"]},
            "level": {"id": 1, "role": role, "lo": 22600.0, "hi": 22670.0, "births": ["b"], "sweeps": 1, "dist": 10.0},
            "risk": {"entry": 22580.0, "sl": 22690.0, "target": 22200.0, "rr": 3.4}, "why": None}


@pytest.mark.parametrize("sym", ["NIFTY", "BANKNIFTY", "SENSEX"])
def test_engine_run_per_symbol_writes_setup_readable_by_adapter(sym, tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    now = pd.Timestamp("2030-01-07 10:01")
    monkeypatch.setattr(L, "compute", lambda s, feed, n, st=None: v22_setup(s, "2030-01-07 10:00"))
    r = ES.run3(sym, "tok", feed=object(), path=p, now=now)
    assert r["decision"] == "setup" and r["direction"] == -1 and r["level_lo"] == 22600.0 and r["grade"] == "B"
    st = {"signal_source": "engine", "trading_mode": "PAPER"}
    pe = ES.pending_entry("srv2_momentum_reversal", sym, st, now, p)
    assert pe is not None and pe["bar_ts"] == "2030-01-07 10:00:00" and json.loads(pe["payload"])["engine"] == "decision3"
    # पुढचा bar "wait" ⇒ setup ✅ ची वाट पाहत तसाच (max age मध्ये)
    w = dict(v22_setup(sym, "2030-01-07 10:15"), decision="wait")
    monkeypatch.setattr(L, "compute", lambda s, feed, n, st=None: w)
    ES.run3(sym, "tok", feed=object(), path=p, now=pd.Timestamp("2030-01-07 10:16"))
    assert ES.pending_entry("srv2_momentum_reversal", sym, st, "2030-01-07 10:17", p)["bar_ts"] == "2030-01-07 10:00:00"
    assert ES.pending_entry("srv2_momentum_reversal", sym, st, "2030-01-07 10:45", p) is None            # max age नंतर नाही
    ES.mark_consumed("srv2_momentum_reversal", sym, "2030-01-07 10:00:00", "EXECUTED", p)
    assert ES.pending_entry("srv2_momentum_reversal", sym, st, "2030-01-07 10:17", p) is None


def test_engine_window_skips_bars_outside_0930_1500(tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    monkeypatch.setattr(L, "compute", lambda s, feed, n, st=None: v22_setup(s, "2030-01-07 15:15"))
    r = ES.run3("NIFTY", "tok", feed=object(), path=p, now=pd.Timestamp("2030-01-07 15:16"))
    assert r.get("skipped") and ES.latest("NIFTY", "2030-01-07 15:16", path=p) is None
    assert ES.in_window("2030-01-07 09:30") and ES.in_window("2030-01-07 15:00") and not ES.in_window("2030-01-07 09:15")



def test_fail_closed_error_row_alerts_first_repeat_60min_and_recovered(tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    monkeypatch.setenv("ENGINE_SIGNAL_DB", p)
    monkeypatch.setattr(L, "compute", lambda s, feed, n, st=None: v22_setup(s, "2030-01-07 10:00"))
    ES.run3("SENSEX", "tok", feed=object(), path=p, now=pd.Timestamp("2030-01-07 10:01"))
    sent, al = [], str(tmp_path / "al.json")

    def boom(sym, tok):
        raise L.EngineDataError(f"{sym}: 5M spot (LTF) data नाही")

    def run(t, fn=boom):
        return ESR.main(["--symbols", "SENSEX,BANKNIFTY"], token_fn=lambda: "tok", run_fn=fn, market_fn=lambda: True, send=sent.append,
                        alert_path=al, now=pd.Timestamp(t), symbols_fn=lambda: ["NIFTY", "BANKNIFTY", "SENSEX"])   # dashboard: SENSEX ON
    assert run("2030-01-07 10:16") == 1 and len(sent) == 2 and all(x.startswith("❌ Engine") for x in sent)
    assert run("2030-01-07 10:31") == 1 and len(sent) == 2                       # 60 मिनिटांच्या आत पुन्हा नाही
    st = {"signal_source": "engine", "trading_mode": "PAPER"}
    assert ES.latest("SENSEX", "2030-01-07 10:17", path=p)["decision"] == ES.ERROR
    pe = ES.pending_entry("srv2_momentum_reversal", "SENSEX", st, "2030-01-07 10:17", p)
    assert pe is not None and pe["bar_ts"] == "2030-01-07 10:00:00"             # error row ✅ च्या वाटेतला setup रद्द करत नाही
    assert ES.pending_entry("srv2_momentum_reversal", "BANKNIFTY", st, "2030-01-07 10:17", p) is None   # नवा entry नाही
    assert run("2030-01-07 11:17") == 1 and len(sent) == 4 and "still failing" in sent[-1]
    ok = lambda sym, tok: {"bar_ts": "2030-01-07 11:30:00", "decision": "wait", "skipped": "x"}       # noqa: E731
    assert run("2030-01-07 11:31", ok) == 0 and len(sent) == 6 and all("recovered" in x for x in sent[-2:])
    assert run("2030-01-07 11:46", ok) == 0 and len(sent) == 6                    # recovered एकदाच


def test_token_missing_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []
    assert ESR.main([], token_fn=lambda: None, market_fn=lambda: True, send=sent.append, alert_path=str(tmp_path / "a.json"),
                    now=pd.Timestamp("2030-01-07 10:16")) == 2
    assert len(sent) == 2 and not any("SENSEX" in x for x in sent)           # default signal_symbols = NIFTY / BANKNIFTY


def test_engine_run_reads_signal_symbols(tmp_path, monkeypatch, capsys):
    """Engine run: symbols = dashboard signal_symbols; --symbols मधले बाहेरचे (SENSEX) ⇒ skip (row / alert नाही)."""
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    seen = []
    ok = lambda sym, tok: seen.append(sym) or {"bar_ts": "2030-01-07 10:15:00", "decision": "wait", "skipped": "x"}   # noqa: E731
    kw = dict(token_fn=lambda: "tok", run_fn=ok, market_fn=lambda: True, send=[].append, alert_path=str(tmp_path / "a.json"),
              now=pd.Timestamp("2030-01-07 10:16"))
    assert ESR.main([], **kw) == 0 and seen == ["NIFTY", "BANKNIFTY"]
    seen.clear()
    assert ESR.main(["--symbols", "NIFTY,BANKNIFTY,SENSEX"], **kw) == 0 and seen == ["NIFTY", "BANKNIFTY"]
    assert "⏭️ SENSEX: signal_symbols (NIFTY / BANKNIFTY)" in capsys.readouterr().out
    seen.clear()
    assert ESR.main([], symbols_fn=lambda: ["BANKNIFTY"], **kw) == 0 and seen == ["BANKNIFTY"]

class Feed:
    def __init__(self, fut=True, ltf=True):
        days = pd.bdate_range("2030-01-01", periods=60)
        ts = [d + pd.Timedelta(minutes=555 + 15 * k) for d in days for k in range(25)]
        self.m15 = pd.DataFrame({"timestamp": ts, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5})
        self.d = pd.DataFrame({"timestamp": pd.bdate_range("2029-01-01", periods=300), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
        self.fut, self.ltf = fut, ltf

    def five(self):
        f = pd.concat([self.m15.assign(timestamp=self.m15["timestamp"] + pd.Timedelta(minutes=5 * k)) for k in range(3)])
        return f.sort_values("timestamp").reset_index(drop=True)

    def index(self, sym, interval, days):
        if interval == "5minute":
            return self.five() if self.ltf else self.five().iloc[:0]
        return {"15minute": self.m15, "day": self.d}[interval]

    def futures(self, sym, interval, days):
        if not self.fut:
            raise L.EngineDataError(f"{sym}: BSE front-month FUT सापडला नाही ⇒ FUT volume नाही")
        return self.five().assign(volume=10.0)




def test_build_inputs_ltf_fail_closed_fut_missing_is_volume_na():
    now = pd.Timestamp("2030-03-25 15:31")
    m15, daily, ltf, fut, note = L.build_inputs(Feed(), "BANKNIFTY", now)
    assert len(m15) and (m15["bar_end"] <= now).all() and daily["timestamp"].max() < now.normalize() and fut["volume"].sum() > 0
    assert note is None and len(ltf) and (ltf["bar_end"] <= now).all()
    with pytest.raises(L.EngineDataError, match="LTF"):
        L.build_inputs(Feed(ltf=False), "BANKNIFTY", now)
    m15, daily, ltf, fut, note = L.build_inputs(Feed(fut=False), "SENSEX", now)                  # FUT नाही ⇒ fail-closed नाही
    assert fut is None and "volume NA" in note
    with pytest.raises(L.EngineDataError, match="अजून Upstox"):
        L.build_inputs(Feed(), "BANKNIFTY", pd.Timestamp("2030-03-26 10:01"))      # आजचा बंद bar नाही
    assert L.index_key("SENSEX") == "BSE_INDEX|SENSEX"
    with pytest.raises(L.EngineDataError):
        L.index_key("FOOBAR")


def test_evaluate_passes_real_ltf_and_futures_to_v22(monkeypatch):
    from decision3 import engine as E3
    seen = {}

    class FakeV22:
        def __init__(self, m15, df1m=None, daily_df=None, s=None, res=None, sealed=None, ltf=None, futures=None):
            seen.update(m15=m15, ltf=ltf, futures=futures)
            self.m15 = m15

        def decide(self, t):
            return {"bar_end": str(self.m15["bar_end"].iloc[t]), "decision": "wait"}
    monkeypatch.setattr(E3, "V22", FakeV22)
    m15, daily, ltf, fut, _ = L.build_inputs(Feed(), "BANKNIFTY", pd.Timestamp("2030-03-25 15:31"))
    L.evaluate("BANKNIFTY", m15, daily, ltf, fut)
    assert seen["ltf"] is ltf and seen["futures"] is fut and "volume" not in seen["m15"].columns   # index volume 0 ⇒ NA, खोटा 0 नाही
    L.evaluate("BANKNIFTY", m15, daily, ltf, None)
    assert seen["futures"] is None and "volume" not in seen["m15"].columns


def test_fut_volume_aligned_to_15m_bins():
    m15 = pd.DataFrame({"timestamp": pd.to_datetime(["2030-01-07 09:15", "2030-01-07 09:30"])})
    f = pd.DataFrame({"timestamp": pd.to_datetime(["2030-01-07 09:15", "2030-01-07 09:20", "2030-01-07 09:25", "2030-01-07 09:30"]),
                      "volume": [1.0, 2.0, 3.0, 7.0]})
    assert list(L.fut_volume_15m(m15, f)) == [6.0, 7.0]


def test_sources_no_dates_no_live_orders():
    for f in ("engine3_live.py", "bots_common/one_bot.py", "scripts/set_one_bot_mode.py", "scripts/engine_signal_run.py", "engine_signal.py",
              "scripts/diag_today.py", "scripts/install_engine_schedule.sh", "scripts/deploy_one_bot.sh"):
        s = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert not re.search(r"20\d\d-\d\d-\d\d", s), f
        assert "place_order" not in s and 'trading_mode="LIVE"' not in s
