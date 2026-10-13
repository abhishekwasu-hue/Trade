"""Vision V4 (R0, design §12.2–§12.4): checklist schema / validator / prices-in-facts / Telegram, V4 request (cached Method Pack prefix),
worker wiring (default off, audit-only, pack_version नोंद). सगळे fakes — API call नाही."""
import json
import types

import pandas as pd
import pytest

from vision import checklist as CK
from vision import config as VC
from vision import method_pack as MP
from vision import store as VS
from vision import v4 as V4

PV = "0123456789ab"


def good(**kw):
    d = {"pack_version": PV, "verdict": "partly", "items": [
        {"n": 1, "status": "pass", "evidence": "Daily LH/LL from the protected origin 22,809.10; trade on the trend side"},
        {"n": 2, "status": "pass", "evidence": "3rd touch of the supply band 22,640.00-22,667.35"},
        {"n": 3, "status": "pass", "evidence": "falling line, 2 wick touches, projected 3rd touch at the band"},
        {"n": 4, "status": "pass", "evidence": "a-b-c rally, C near 1.0 × A"},
        {"n": 5, "status": "NA", "evidence": "futures volume not provided"},
        {"n": 6, "status": "fail", "evidence": "no 5M CHoCH by close yet at 09:45"},
        {"n": 7, "status": "pass", "evidence": "no breakout: entry at the area, 0.5 MR from the line, 61.8% retrace"},
    ]}
    d.update(kw)
    return d


KNOWN = CK.facts_prices({"a": 22809.10, "b": [22640.0, 22667.35]})


# ----------------------------------------------------------------------------------------------------------- validator
def test_valid_output_passes_with_prices_in_facts():
    out, err = CK.validate(good(), pack_version=PV, known_prices=KNOWN)
    assert err is None and [i["n"] for i in out["items"]] == list(range(1, 8))
    assert out["items"][4]["status"] == "NA"


@pytest.mark.parametrize("mut, why", [
    (lambda d: d["items"].pop(), "items must be"),
    (lambda d: d["items"][1].update(n=1), "duplicate"),
    (lambda d: d["items"][0].update(status="maybe"), "invalid status"),
    (lambda d: d["items"][0].update(evidence="  "), "empty evidence"),
    (lambda d: d.update(verdict="agree"), "agree with a failed"),
    (lambda d: d.update(verdict="yes"), "invalid verdict"),
    (lambda d: d.update(pack_version="ffffffffffff"), "pack_version"),
    (lambda d: d.update(extra=1), "unexpected fields"),
    (lambda d: d["items"][0].update(note="x"), "item shape"),
    (lambda d: d["items"][0].update(n=True), "invalid / duplicate"),
])
def test_malformed_output_rejected(mut, why):
    d = good()
    mut(d)
    out, err = CK.validate(d, pack_version=PV, known_prices=KNOWN)
    assert out is None and why in err


def test_status_case_and_whitespace_normalised():
    d = good()
    d["items"][4]["status"] = "na"
    d["items"][0]["evidence"] = "line one\n line two"
    out, err = CK.validate(d, pack_version=PV)
    assert err is None and out["items"][4]["status"] == "NA" and out["items"][0]["evidence"] == "line one line two"


def test_price_not_in_facts_rejects_whole_output(caplog):
    d = good()
    d["items"][1]["evidence"] = "3rd touch of the supply band at 22,690"
    with caplog.at_level("WARNING", logger="vision.checklist"):
        out, err = CK.validate(d, pack_version=PV, known_prices=KNOWN)
    assert out is None and "22,690" in err
    assert any("rejected" in r.message for r in caplog.records)


def test_price_tolerance_is_tick_plus_written_precision():
    k = CK.facts_prices([22667.35])
    assert CK.unknown_prices(["band 22,667.35"], k) == []
    assert CK.unknown_prices(["band 22,667.40"], k) == []               # 1 tick
    assert CK.unknown_prices(["band 22,667.50"], k) == ["22,667.50"]
    assert CK.unknown_prices(["band 22,667"], k) == []                   # rounded to the point it was written at
    assert CK.unknown_prices(["band 22,668"], k) == ["22,668"]
    assert CK.unknown_prices(["band 22667.3"], k) == []


def test_non_prices_are_ignored():
    k = CK.facts_prices([25010.0])
    txt = ["2026-10-12 09:30 close, 12 Oct, 0.5 MR, 61.8%, 3 bars, 1.618 × A, 2 touches, 15M, 5M, wave 3, 2,026 points"]
    assert CK.unknown_prices(txt, k) == []
    assert CK.unknown_prices(["sweep of 24,992 then reclaim 25,018"], k) == ["24,992", "25,018"]


def test_no_known_prices_is_fail_closed():
    assert CK.unknown_prices(["level 22,600"], []) == ["22,600"]
    assert CK.unknown_prices(["3 legs, 0.5 MR"], []) == []


def test_facts_prices_reads_frames_and_text():
    df = pd.DataFrame({"timestamp": pd.to_datetime(["2020-01-01 09:15"]), "open": [1.5], "high": [2.25], "low": [1.0], "close": [2.0]})
    got = CK.facts_prices({"15M": df}, "Level L: 22,640.50 as resistance", None, True)
    assert {1.5, 2.25, 1.0, 2.0, 22640.5} <= set(got)


def test_parse_json_tolerates_fences():
    assert CK.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert CK.parse_json('note {"a": 2} end') == {"a": 2}
    with pytest.raises(ValueError):
        CK.parse_json("no json")


# ----------------------------------------------------------------------------------------------------------- Telegram
def test_telegram_failed_and_na_first_max_12_lines_audit_only():
    out, _ = CK.validate(good(), pack_version=PV)
    lines = CK.telegram_lines({"data": out}, title="NIFTY <bear>")
    assert len(lines) <= CK.TELEGRAM_MAX_LINES
    assert "audit only" in lines[0].lower() and "&lt;bear&gt;" in lines[0]
    assert lines[2].startswith("❌ 6.") and lines[3].startswith("— 5.") and lines[4].startswith("✅ 1.")
    assert lines[-1] == CK.FOOTER and "never blocks" in lines[-1]
    na = CK.telegram_lines({"error": "prices not in facts: 22,690"})
    assert "22,690" in na[1] and na[-1] == CK.FOOTER


def test_schema_text_and_schema_shape():
    assert all(f"{n}. " in CK.SCHEMA_TEXT for n in range(1, 8))
    assert "never read a price from an image" in CK.SCHEMA_TEXT
    assert set(CK.SCHEMA["required"]) == {"pack_version", "items", "verdict"}
    assert CK.SCHEMA["properties"]["verdict"]["enum"] == ["agree", "partly", "disagree"]


# ----------------------------------------------------------------------------------------------------------- V4 request
def test_v4_request_caches_pack_prefix_and_puts_images_and_facts_after():
    text, ver = MP.load()
    p = V4.build_request([b"png1", b"png2"], "FACTS here", "m", pack=(text, ver))
    sysb = p["system"]
    assert sysb[0]["text"].startswith("# Method Pack — version " + ver) and "cache_control" not in sysb[0]
    assert sysb[-1]["text"] == CK.SCHEMA_TEXT and sysb[-1]["cache_control"] == {"type": "ephemeral"}
    c = p["messages"][0]["content"]
    assert [b["type"] for b in c] == ["image", "image", "text"] and "FACTS here" in c[-1]["text"]
    assert p["output_config"]["format"]["schema"] is CK.SCHEMA
    assert V4.build_request([b"x"], "f", "m", pack=(text, ver), ttl="1h")["system"][-1]["cache_control"]["ttl"] == "1h"
    with pytest.raises(ValueError):
        V4.build_request([b"x"], "f", None, pack=(text, ver))


def test_v4_prefix_is_identical_across_calls():
    pack = MP.load()
    a = V4.build_request([b"a"], "facts one", "m", pack=pack)["system"]
    b = V4.build_request([b"b", b"c"], "facts two", "m", pack=pack)["system"]
    assert a == b


def test_v4_estimate_cached_cheaper_than_uncached():
    text, _ = MP.load()
    e = V4.estimate(1, "x" * 4000, text, "m")
    assert e["system_tokens"] > 6000 and e["fresh_input_tokens"] >= V4.IMAGE_TOKENS + 1000
    assert e["usd_cached"] < e["usd_uncached"] < e["usd_cache_write"]


class FakeClient:
    def __init__(self, reply=None, exc=None, stop="end_turn"):
        self.reply, self.exc, self.stop, self.calls = reply, exc, stop, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc
        usage = types.SimpleNamespace(input_tokens=1200, output_tokens=400, cache_read_input_tokens=8000, cache_creation_input_tokens=0)
        return types.SimpleNamespace(stop_reason=self.stop, usage=usage,
                                     content=[types.SimpleNamespace(type="text", text=json.dumps(self.reply))])


def test_v4_audit_done_rejected_failed():
    text, ver = MP.load()
    pack = (text, ver)
    seen = []
    r = V4.audit(FakeClient(good(pack_version=ver)), [b"p"], "facts", "m", KNOWN, pack=pack, on_usage=lambda u, c: seen.append((u, c)))
    assert r["status"] == "done" and r["pack_version"] == ver and r["usage"]["cache_read"] == 8000 and seen
    bad = good(pack_version=ver)
    bad["items"][1]["evidence"] = "band 23,000"
    r = V4.audit(FakeClient(bad), [b"p"], "facts", "m", KNOWN, pack=pack)
    assert r["status"] == "rejected" and "23,000" in r["error"] and r["data"] is None
    r = V4.audit(FakeClient(good(pack_version=ver), stop="refusal"), [b"p"], "facts", "m", KNOWN, pack=pack)
    assert r["status"] == "rejected" and "refusal" in r["error"]
    seen.clear()
    r = V4.audit(FakeClient(exc=TimeoutError("t")), [b"p"], "facts", "m", KNOWN, pack=pack, on_usage=lambda u, c: seen.append(c))
    assert r["status"] == "failed" and r["cost_estimated"] and seen and seen[0] > 0


# ----------------------------------------------------------------------------------------------------------- config / store / worker
def test_config_v4_default_off_and_validated():
    assert VC.GLOBAL_DEFAULTS["vision_v4_audit"] == "off"
    assert VC.GLOBAL_DEFAULTS["vision_daily_budget_usd"] == 2.0
    assert VC.validate("_global", {"vision_v4_audit": "v4"})["vision_v4_audit"] == "v4"
    with pytest.raises(ValueError):
        VC.validate("_global", {"vision_v4_audit": "v5"})


def test_usage_pack_version_and_migration_of_old_db(tmp_path):
    import sqlite3
    p = str(tmp_path / "old.db")
    con = sqlite3.connect(p)                                               # जुना DB: pack_version कॉलम नाहीत
    con.execute("CREATE TABLE vision_usage (ts TEXT NOT NULL, day TEXT NOT NULL, month TEXT NOT NULL, task TEXT, model TEXT, "
                "signal_id TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read INTEGER, cache_write INTEGER, cost_usd REAL)")
    con.commit()
    con.close()
    VS._MIGRATED.clear()
    VS.add_usage("signal_v4", "m", {"input_tokens": 5}, 0.01, "sid", p, pack_version=PV)
    VS.add_usage("signal", "m", {"input_tokens": 5}, 0.02, "sid", p)
    with VS.connect(p) as c:
        rows = c.execute("SELECT task, pack_version FROM vision_usage ORDER BY task").fetchall()
        cols = {r[1] for r in c.execute("PRAGMA table_info(vision_signals)")}
    assert [tuple(r) for r in rows] == [("signal", None), ("signal_v4", PV)]
    assert {"pack_version", "v4_json"} <= cols
    assert VS.spent(p)[0] == pytest.approx(0.03)                           # budget तीच table (V4 खर्च सुद्धा $2 / दिवस मध्ये)


def _row(path, mode="notify"):
    sid = VS.insert_signal({"bot": "srv2_momentum_reversal", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": mode,
                            "signal_ts": "2026-10-12 09:45:00", "direction": "BEARISH", "level": 22640.0, "role": "RESISTANCE",
                            "setup_tf": "15M", "spot": 22610.5, "setup": {}}, path)
    row = VS.get_signal(sid, path)
    row.update(level=22640.0, spot=22610.5, invalidation=22700.0, tags={}, ctx={})
    return row


def test_worker_v4_off_by_default_no_call(tmp_path, monkeypatch):
    from vision import worker as W
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    p = str(tmp_path / "v.db")
    row = _row(p)
    called = []
    g = VC.load("_global", p)
    assert W.maybe_v4(row, b"png", {}, None, g, "m", path=p, send_text=called.append,
                      client_factory=lambda t: called.append("client")) is None
    assert called == [] and VS.get_signal(row["signal_id"], p)["v4_json"] is None


@pytest.mark.parametrize("mode, sent", [("notify", 1), ("shadow", 0), ("human_confirm", 1)])
def test_worker_v4_on_records_pack_version_and_never_touches_decision(tmp_path, monkeypatch, mode, sent):
    from vision import worker as W
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    p = str(tmp_path / "v.db")
    row = _row(p, mode)
    before = VS.get_signal(row["signal_id"], p)
    _, ver = MP.load()
    reply = good(pack_version=ver)
    reply["items"][0]["evidence"] = "level 22,640.00 held as resistance; spot 22,610.50"
    reply["items"][1]["evidence"] = "invalidation 22,700 above the band"
    texts = []
    fc = FakeClient(reply)
    g = {**VC.load("_global", p), "vision_v4_audit": "v4"}
    res = W.maybe_v4(row, b"png", {"ctx": {"levels": [{"price": 22640.0}]}}, None, g, "m", path=p, send_text=texts.append,
                     client_factory=lambda t: fc)
    assert res["status"] == "done", res
    after = VS.get_signal(row["signal_id"], p)
    assert after["pack_version"] == ver and json.loads(after["v4_json"])["data"]["verdict"] == "partly"
    for k in ("status", "verdict", "final_decision", "human_decision", "factor"):
        assert after[k] == before[k]                                        # audit-only: निर्णय / gate fields तसेच
    with VS.connect(p) as c:
        u = c.execute("SELECT task, pack_version FROM vision_usage").fetchall()
    assert [tuple(x) for x in u] == [("signal_v4", ver)]
    assert len(texts) == sent
    if sent:
        assert "audit only" in texts[0].lower() and len(texts[0].split("\n")) <= 12
    assert "cache_control" in fc.calls[0]["system"][-1]


def test_worker_v4_budget_and_errors_never_raise(tmp_path, monkeypatch):
    from vision import worker as W
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    p = str(tmp_path / "v.db")
    row = _row(p)
    g = {**VC.load("_global", p), "vision_v4_audit": "v4", "vision_daily_budget_usd": 0.0}
    calls = []
    r = W.maybe_v4(row, b"png", {}, None, g, "m", path=p, send_text=lambda t: None, client_factory=lambda t: calls.append(1))
    assert r["status"] == "skipped" and calls == []
    g["vision_daily_budget_usd"] = 2.0

    def boom(t):
        raise RuntimeError("x")
    assert W.maybe_v4(row, b"png", {}, None, g, "m", path=p, send_text=lambda t: None, client_factory=boom) is None


def test_worker_known_prices_cut_at_signal():
    from vision import worker as W
    m1 = pd.DataFrame({"timestamp": pd.to_datetime(["2026-10-12 09:15", "2026-10-12 09:16", "2026-10-12 10:30"]),
                       "open": [1.0, 2.0, 99.0], "high": [1.5, 2.5, 99.5], "low": [0.5, 1.5, 98.5], "close": [1.25, 2.25, 99.25]})
    row = {"signal_ts": "2026-10-12 09:45:00", "level": 22640.0, "spot": None, "invalidation": None}
    k = W.v4_known_prices(row, {"ctx": {"levels": [{"price": 22650.0}]}}, m1)
    assert 22640.0 in k and 22650.0 in k and 2.5 in k and 99.5 not in k
