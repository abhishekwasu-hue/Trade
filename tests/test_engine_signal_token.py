"""🔴 Upstox token rejected (Abhi): दुसऱ्या system साठी नवा token ⇒ bot चा token रद्द ⇒ FUT resolve HTTP 401 UDAPI100050 पण spot candles
200 ⇒ bot आंधळा आणि alert "FUT volume missing" सांगत होता. आता: run सुरुवातीची profile तपासणी ⇒ error row + 🔴 ओळ दर 15M bar; पास ⇒ ✅
एकदा; network चूक ⇒ जुना data-problem मार्ग; valid token ⇒ main सारखंच. Code मध्ये तारीख नाही (tests मधील तारखा फक्त fixture)."""
import json

import pandas as pd
import pytest

import engine3_live as L
import engine_signal as ES
import verify_opportunity_data_availability as V
from scripts import engine_signal_run as ESR

BODY_401 = {"status": "error", "errors": [{"errorCode": "UDAPI100050", "message": "Invalid token used to access API",
                                           "propertyPath": None, "invalidValue": None, "error_code": "UDAPI100050"}]}
TEXT_401 = json.dumps(BODY_401)
RED = "🔴 Upstox token rejected — bot is blind (no engine reading, no entries); log in again (bot token). Exits unaffected."
GREEN = "✅ Upstox data restored — engine reading again"
SECRET = "sekret-token-value"


@pytest.fixture
def env(tmp_path, monkeypatch):
    p = str(tmp_path / "es.db")
    monkeypatch.setenv("ENGINE_SIGNAL_DB", p)
    monkeypatch.delenv("ENGINE_TOKEN_CHECK", raising=False)
    return p, str(tmp_path / "al.json")


def _main(al, t, check, run_fn, sent, argv=None):
    return ESR.main(argv or [], token_fn=lambda: SECRET, run_fn=run_fn, market_fn=lambda: True, send=sent.append, alert_path=al,
                    now=pd.Timestamp(t), check_fn=check)


def wait(sym, tok):
    return {"bar_ts": "2030-01-07 10:15:00", "decision": "wait", "skipped": "x"}


def fut_missing(sym, tok):
    raise L.FutVolumeMissing(f"{L.DATA_PROBLEM_FUT} ({sym}: FUT volume नाही (EngineDataError: FUT resolve HTTP None))")


def test_alert_texts_exact():
    assert ES.TOKEN_REJECTED_LINE == RED and ES.TOKEN_RESTORED_LINE == GREEN


def test_rejected_at_start_error_rows_alert_every_bar_then_restored_once(env, capsys):
    p, al = env
    sent, calls = [], []
    rejected = lambda tok: calls.append(tok) or "rejected (HTTP 401 UDAPI100050)"   # noqa: E731
    never = lambda sym, tok: pytest.fail("engine must not run on a rejected token")  # noqa: E731
    assert _main(al, "2030-01-07 12:16", rejected, never, sent) == 2
    assert sent == [RED] and calls == [SECRET]                            # one check per run (not per symbol), alert at once
    for sym in ("NIFTY", "BANKNIFTY"):
        row = ES.latest(sym, "2030-01-07 12:17", path=p)
        assert row["decision"] == ES.ERROR and "Upstox token rejected (HTTP 401 UDAPI100050)" in row["reason"]
        assert ES.pending_entry("srv2_momentum_reversal", sym, {"signal_source": "engine", "trading_mode": "PAPER"},
                                "2030-01-07 12:17", p) is None           # fail closed: no new entry
    assert _main(al, "2030-01-07 12:20", rejected, never, sent) == 2 and sent == [RED]   # same bar twice ⇒ once
    assert _main(al, "2030-01-07 12:31", rejected, never, sent) == 2 and sent == [RED, RED]          # next bar ⇒ again (no 60-min
    assert _main(al, "2030-01-07 12:46", rejected, never, sent) == 2 and sent == [RED, RED, RED]     # throttle)
    out = capsys.readouterr().out
    assert SECRET not in out and SECRET not in json.dumps(sent) and SECRET not in open(al, encoding="utf-8").read()
    assert _main(al, "2030-01-07 13:01", lambda tok: "ok", wait, sent) == 0 and sent[3:] == [GREEN]
    assert _main(al, "2030-01-07 13:16", lambda tok: "ok", wait, sent) == 0 and sent[3:] == [GREEN]  # restored only once
    assert _main(al, "2030-01-07 13:31", rejected, never, sent) == 2 and sent[4:] == [RED]           # rejected again ⇒ again


def test_rejected_dry_run_prints_only(env, capsys):
    p, al = env
    sent = []
    assert ESR.main(["--dry-run"], token_fn=lambda: SECRET, run_fn=wait, market_fn=lambda: True, send=sent.append, alert_path=al,
                    now=pd.Timestamp("2030-01-07 12:16"), check_fn=lambda tok: "rejected (HTTP 401)") == 2
    assert sent == [] and ES.latest("NIFTY", "2030-01-07 12:17", path=p) is None
    assert "Upstox token rejected (HTTP 401)" in capsys.readouterr().out


def test_network_error_on_check_keeps_todays_data_problem_path(env):
    p, al = env
    sent = []
    assert _main(al, "2030-01-07 12:16", lambda tok: "unknown (network)", fut_missing, sent) == 1
    assert len(sent) == 2 and all(x.startswith("⚠️ Engine") and "FUT volume missing" in x for x in sent) and RED not in sent
    boom = lambda tok: (_ for _ in ()).throw(RuntimeError("down"))          # noqa: E731 — the check itself crashes ⇒ unknown
    assert _main(al, "2030-01-07 12:31", boom, fut_missing, sent) == 1 and len(sent) == 2   # once a day (today's throttle)
    assert ES.latest("NIFTY", "2030-01-07 12:32", path=p)["decision"] == ES.ERROR


def test_token_rejected_mid_run_uses_the_red_line_once_per_bar(env):
    p, al = env
    sent = []

    def rej(sym, tok):
        raise L.TokenRejected(f"{sym}: FUT resolve: Upstox token rejected (HTTP 401 UDAPI100050)")
    assert _main(al, "2030-01-07 12:16", lambda tok: "unknown (network)", rej, sent) == 1
    assert sent == [RED]                                                  # two symbols, one token ⇒ one line per bar
    assert "Upstox token rejected" in ES.latest("BANKNIFTY", "2030-01-07 12:17", path=p)["reason"]
    assert _main(al, "2030-01-07 12:31", lambda tok: "unknown (network)", rej, sent) == 1 and sent == [RED, RED]


def test_valid_token_is_byte_identical_to_main(env, monkeypatch, capsys):
    """Valid token ⇒ फक्त एक जास्तीचा GET (mock); output / Telegram / rows तसेच (check बंद = main चा मार्ग)."""
    p, al = env
    runs = {}
    for mode in ("off", "on"):
        if mode == "off":
            monkeypatch.setenv("ENGINE_TOKEN_CHECK", "0")
        else:
            monkeypatch.delenv("ENGINE_TOKEN_CHECK")
        sent, calls = [], []
        rc = [_main(al + mode, t, lambda tok: calls.append(1) or "ok", f, sent)
              for t, f in (("2030-01-07 10:16", wait), ("2030-01-07 10:31", fut_missing), ("2030-01-07 10:46", wait))]
        runs[mode] = (rc, sent, capsys.readouterr().out, len(calls))
    assert runs["on"][:3] == runs["off"][:3] and runs["off"][3] == 0 and runs["on"][3] == 3


def test_check_only_for_decision3(env):
    p, al = env
    sent = []
    assert ESR.main(["--engine", "decision2"], token_fn=lambda: SECRET, run_fn=wait, market_fn=lambda: True, send=sent.append,
                    alert_path=al, now=pd.Timestamp("2030-01-07 10:16"),
                    check_fn=lambda tok: pytest.fail("decision2 untouched")) == 0


# ------------------------------------------------------------------------------------------------ detector / engine3_live
@pytest.mark.parametrize("status,body,error,want", [
    (401, BODY_401, TEXT_401, True), (401, None, "", True), (403, None, "forbidden", True),
    (400, BODY_401, TEXT_401, True), (500, None, "Invalid token used to access API", True),
    (200, {"data": []}, None, False), (None, None, "ConnectionError: boom", False), (500, None, "server", False),
    (429, None, "rate", False), (404, {"errors": [{"errorCode": "UDAPI100011"}]}, "", False)])
def test_token_rejected_detector(status, body, error, want):
    assert L.token_rejected(status, body, error) is want


def test_resolve_future_401_raises_token_rejected(monkeypatch):
    import datetime as dt
    monkeypatch.setattr(V, "_get", lambda url, tok, params=None, **k: (401, BODY_401, TEXT_401))
    with pytest.raises(L.TokenRejected) as ei:
        L.resolve_future(SECRET, "NIFTY", dt.date(2030, 1, 7))
    assert isinstance(ei.value, L.EngineDataError) and "HTTP 401 UDAPI100050" in str(ei.value) and SECRET not in str(ei.value)
    monkeypatch.setattr(V, "_get", lambda url, tok, params=None, **k: (None, None, "ConnectionError: x"))
    with pytest.raises(L.EngineDataError) as ei:                          # network ⇒ today's EngineDataError, not TokenRejected
        L.resolve_future(SECRET, "NIFTY", dt.date(2030, 1, 7))
    assert not isinstance(ei.value, L.TokenRejected) and "FUT resolve HTTP None" in str(ei.value)


def test_feed_401_raises_token_rejected(monkeypatch):
    import datetime as dt
    f = L.UpstoxFeed(SECRET, dt.date(2030, 1, 7))
    monkeypatch.setattr(V, "_get", lambda url, tok, params=None, **k: (401, BODY_401, TEXT_401))
    with pytest.raises(L.TokenRejected):
        f._intraday("NSE_INDEX|Nifty 50", "15minute")
    monkeypatch.setattr(V, "fetch_candles_window", lambda *a, **k: {"status": 401, "candles": [], "error": TEXT_401})
    with pytest.raises(L.TokenRejected):
        f._history("NSE_INDEX|Nifty 50", "15minute", 30)
    monkeypatch.setattr(V, "fetch_candles_window", lambda *a, **k: {"status": 500, "candles": [], "error": "x"})
    with pytest.raises(L.EngineDataError) as ei:
        f._history("NSE_INDEX|Nifty 50", "15minute", 30)
    assert not isinstance(ei.value, L.TokenRejected)


def test_build_inputs_token_rejected_on_fut_is_not_fut_volume_missing():
    from tests.test_one_bot import Feed

    class RejFeed(Feed):
        def futures(self, sym, interval, days):
            raise L.TokenRejected(f"{sym}: FUT resolve: Upstox token rejected (HTTP 401 UDAPI100050)")
    with pytest.raises(L.TokenRejected):
        L.build_inputs(RejFeed(), "NIFTY", pd.Timestamp("2030-03-25 15:31"))
    with pytest.raises(L.FutVolumeMissing):                               # any other FUT failure ⇒ today's path
        L.build_inputs(Feed(fut=False), "NIFTY", pd.Timestamp("2030-03-25 15:31"))


@pytest.mark.parametrize("ret,want", [((200, {"data": {}}, None), "ok"), ((401, BODY_401, TEXT_401), "rejected (HTTP 401 UDAPI100050)"),
                                      ((403, None, "x"), "rejected (HTTP 403)"), ((503, None, "x"), "unknown (HTTP 503)"),
                                      ((None, None, "ConnectionError"), "unknown (network)")])
def test_profile_check_uses_paper_status_profile_url(ret, want):
    from scripts import paper_status as PS
    seen = []
    got = L.profile_check(SECRET, get=lambda url, tok: seen.append((url, tok)) or ret)
    assert got == want and seen == [(PS.PROFILE_URL, SECRET)] and SECRET not in got


def test_profile_check_never_raises():
    def boom(url, tok):
        raise RuntimeError(f"failed for {tok}")
    got = L.profile_check(SECRET, get=boom)
    assert got == "unknown (RuntimeError)" and SECRET not in got


def test_paper_status_401_udapi100050_is_rejected(monkeypatch):
    """#348: paper_status (profile call) — 401 + UDAPI100050 body ⇒ "rejected (HTTP 401)", token never printed."""
    import cloud_db
    import requests
    from types import SimpleNamespace as NS
    from scripts import paper_status as PS
    monkeypatch.setattr(cloud_db, "get_effective_upstox_token", lambda acc=None: SECRET)
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: NS(status_code=401, text=TEXT_401,
                                                                                   json=lambda: BODY_401))
    got = PS.IO().token()
    assert got == "rejected (HTTP 401)" and SECRET not in got
