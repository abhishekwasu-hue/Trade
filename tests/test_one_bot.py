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
    assert "Only 15M SRv2 active · signal source: engine · symbols NIFTY / BANKNIFTY / SENSEX · mode PAPER" in out
    for sym in ("NIFTY", "BANKNIFTY", "SENSEX"):                     # dashboard चा getter (page_bot_dynamic_sr_algo) तेच वाचतो
        s = cloud_db.get_strategy_settings("15m_dynamic_sr", sym)
        assert s["symbol_enabled"] is True and s["signal_source"] == "engine" and s["trading_mode"] == "PAPER"
        assert cloud_db.get_strategy_settings("1m_instant", sym)["symbol_enabled"] is False
        assert cloud_db.get_strategy_settings("1m_instant", sym)["srv3_shadow_enabled"] is False
        assert cloud_db.get_strategy_settings("classic_sr_reversal", sym)["symbol_enabled"] is False
        assert PC.enabled(sym)
    s = cloud_db.get_strategy_settings("15m_dynamic_sr", "NIFTY")
    assert all(s[k] == v for k, v in abhi.items())                    # Abhi चे strikes / lots / SL / entry_mode तसेच
    assert cloud_db.get_strategy_settings("1m_instant", "NIFTY")["lots"] == 2
    gold = db.rows[("mcx_futures", "GOLD")]
    assert gold == {"symbol_enabled": True, "trading_mode": "LIVE", "lots": 1}                     # LIVE ला हात नाही
    assert cloud_db.get_strategy_settings("mcx_futures", "CRUDEOIL")["symbol_enabled"] is False
    from vision import config as VC
    v = VC.load(OB.VISION_BOT)
    assert set(v["symbols"]) >= {"NIFTY", "BANKNIFTY", "SENSEX"} and v["approval_required"] is True
    assert SOB.main(["--revert", "--state", st]) == 0
    assert {k: v for k, v in db.rows.items() if v} == {k: v for k, v in before.items() if v}       # नवे keys काढले, जुने परत
    assert not os.path.exists(os.environ["PAPER_LOCAL_CONFIG"]) and not PC.enabled("BANKNIFTY")
    assert VC.load(OB.VISION_BOT)["symbols"] == ["NIFTY"]


def test_live_srv2_is_refused(env, capsys):
    db, _, tmp = env
    db.rows[("15m_dynamic_sr", "SENSEX")] = {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    SOB.main(["--state", str(tmp / "st.json")])
    out = capsys.readouterr().out
    assert "15M SRv2 SENSEX: trading_mode LIVE" in out
    assert db.rows[("15m_dynamic_sr", "SENSEX")] == {"trading_mode": "LIVE", "symbol_enabled": True, "signal_source": "own"}
    st = OB.one_bot_status()
    assert not st["ok"] and st["line"].startswith("❌")


def test_status_flags_auto_trader_cron_and_missing_engine(env, monkeypatch):
    _, _, tmp = env
    SOB.main(["--state", str(tmp / "st.json")])
    (tmp / "cron").write_text("* 4-10 * * 1-5 python3 srv2_momentum_reversal_strategy.py\n*/5 4-9 * * 1-5 python3 oi_signal_auto_trader.py\n")
    st = OB.one_bot_status()
    assert st["auto_traders"]["oi_signal_auto_trader.py"] == "on" and st["engine_cron"] == "absent" and not st["ok"]


# ------------------------------------------------------------------------------------------------ install_engine_schedule.sh
def _install(cron, *args):
    return subprocess.run(["bash", os.path.join(ROOT, "scripts", "install_engine_schedule.sh"), *args], capture_output=True, text=True,
                          env={**os.environ, "CRONTAB_FILE": str(cron)}, check=True).stdout


def test_schedule_installer_idempotent_and_revert_exact(tmp_path):
    cron = tmp_path / "cron"
    orig = ("* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py >> m.log 2>&1\n"
            "1,16,31,46 3-10 * * 1-5 cd /root/Trade && set -a && . ./.env && set +a && python3 scripts/engine_signal_run.py >> engine_signal.log 2>&1\n"
            "*/5 4-9 * * 1-5 cd /root/Trade && python3 oi_signal_auto_trader.py >> o.log 2>&1\n"
            "*/5 4-9 * * 1-5 cd /root/Trade && python3 credit_spread_auto_trader.py --mode LIVE >> c.log 2>&1\n"
            "* 4-10 * * 1-5 cd /root/Trade && sleep 30 && python3 srv2_momentum_reversal_strategy.py >> s.log 2>&1\n")
    cron.write_text(orig)
    out = _install(cron)
    once = cron.read_text()
    _install(cron)
    assert cron.read_text() == once                                   # idempotent
    act = [x for x in once.splitlines() if not x.startswith("#")]
    assert sum("scripts/engine_signal_run.py --engine decision3" in x and "--dry-run" not in x for x in act) == 1
    assert "1,16,31,46 4-9 * * 1-5" in once and "--symbols NIFTY,BANKNIFTY,SENSEX" in once
    assert "#one-bot-off# 1,16,31,46 3-10" in once and "#one-bot-off# */5 4-9 * * 1-5 cd /root/Trade && python3 oi_signal" in once
    assert any("credit_spread_auto_trader.py --mode LIVE" in x for x in act) and "LIVE" in out    # LIVE ओळ untouched
    assert "trade_monitor.py" in once and "# one-bot-srv2" not in once
    _install(cron, "--revert")
    assert cron.read_text() == orig


def test_schedule_installer_adds_srv2_when_missing_and_dry_run(tmp_path):
    cron = tmp_path / "cron"
    cron.write_text("* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py\n")
    out = _install(cron, "--dry-run")
    assert "# one-bot-srv2" in out and cron.read_text() == "* 4-10 * * 1-5 cd /root/Trade && python3 trade_monitor.py\n"


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


def test_fail_closed_error_row_and_one_telegram_line_per_symbol_per_day(tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    monkeypatch.setenv("ENGINE_SIGNAL_DB", p)
    monkeypatch.setattr(L, "compute", lambda s, feed, n, st=None: v22_setup(s, "2030-01-07 10:00"))
    ES.run3("SENSEX", "tok", feed=object(), path=p, now=pd.Timestamp("2030-01-07 10:01"))
    sent = []

    def boom(sym, tok):
        raise L.EngineDataError(f"{sym}: BSE front-month FUT सापडला नाही")
    for k in range(2):
        rc = ESR.main(["--symbols", "SENSEX,BANKNIFTY"], token_fn=lambda: "tok", run_fn=boom, market_fn=lambda: True, send=sent.append,
                      alert_path=str(tmp_path / "al.json"), now=pd.Timestamp("2030-01-07 10:16"))
        assert rc == 1
    assert len(sent) == 2 and all(x.startswith("❌ Engine") for x in sent)          # symbol मागे एकदाच (2 runs × 2 symbols ⇒ 2 ओळी)
    st = {"signal_source": "engine", "trading_mode": "PAPER"}
    assert ES.pending_entry("srv2_momentum_reversal", "SENSEX", st, "2030-01-07 10:17", p) is None        # आधीचा setup सुद्धा नाही
    assert ES.latest("SENSEX", "2030-01-07 10:17", path=p)["decision"] == ES.ERROR


def test_token_missing_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []
    assert ESR.main([], token_fn=lambda: None, market_fn=lambda: True, send=sent.append, alert_path=str(tmp_path / "a.json"),
                    now=pd.Timestamp("2030-01-07 10:16")) == 2
    assert len(sent) == 3


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


def test_build_inputs_fail_closed_on_missing_ltf_or_fut():
    now = pd.Timestamp("2030-03-25 15:31")
    m15, daily, ltf, fut = L.build_inputs(Feed(), "BANKNIFTY", now)
    assert len(m15) and (m15["bar_end"] <= now).all() and daily["timestamp"].max() < now.normalize() and fut["volume"].sum() > 0
    with pytest.raises(L.EngineDataError, match="LTF"):
        L.build_inputs(Feed(ltf=False), "BANKNIFTY", now)
    with pytest.raises(L.EngineDataError, match="FUT"):
        L.build_inputs(Feed(fut=False), "SENSEX", now)
    with pytest.raises(L.EngineDataError, match="अजून Upstox"):
        L.build_inputs(Feed(), "BANKNIFTY", pd.Timestamp("2030-03-26 10:01"))      # आजचा बंद bar नाही
    assert L.index_key("SENSEX") == "BSE_INDEX|SENSEX"
    with pytest.raises(L.EngineDataError):
        L.index_key("FOOBAR")


def test_fut_volume_aligned_to_15m_bins():
    m15 = pd.DataFrame({"timestamp": pd.to_datetime(["2030-01-07 09:15", "2030-01-07 09:30"])})
    f = pd.DataFrame({"timestamp": pd.to_datetime(["2030-01-07 09:15", "2030-01-07 09:20", "2030-01-07 09:25", "2030-01-07 09:30"]),
                      "volume": [1.0, 2.0, 3.0, 7.0]})
    assert list(L.fut_volume_15m(m15, f)) == [6.0, 7.0]


def test_sources_no_dates_no_live_orders():
    for f in ("engine3_live.py", "bots_common/one_bot.py", "scripts/set_one_bot_mode.py", "scripts/engine_signal_run.py", "engine_signal.py",
              "scripts/diag_today.py", "scripts/install_engine_schedule.sh"):
        s = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert not re.search(r"20\d\d-\d\d-\d\d", s), f
        assert "place_order" not in s and 'trading_mode="LIVE"' not in s
