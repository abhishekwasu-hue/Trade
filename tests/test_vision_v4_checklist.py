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


PROBES = ["wave 5 of C", "Wave (4) low", "item 3 NA", "section 6 trigger", "2nd leg of 3", "touches on 12/10", "spring at 9:30am",
          "fell 1.5 percent", "volume 1.8 lakh", "12-Oct sweep", "(iv) of 3 ended", "volume 1,80,000 on the commitment candle",
          "wave (5) at 10am", "0.5 MR, 61.8%, 3 bars, 2 touches"]


@pytest.mark.parametrize("probe", PROBES)
def test_reviewer_probes_are_not_prices(probe):
    anchors = [22610.5, 22640.0, 22700.0]
    assert CK.unknown_prices([probe], anchors, anchors=anchors) == []
    assert CK.unknown_prices([probe], [], anchors=[]) == []                # anchors नसतानाही (fail-closed मोड) हे prices नाहीत
    out, err = CK.validate(dict(good(), items=[dict(i, evidence=probe if i["n"] == 3 else "ok") for i in good()["items"]]),
                           pack_version=PV, known_prices=anchors, anchors=anchors)
    assert err is None, (probe, err)


def test_invented_and_other_instrument_prices_rejected():
    anchors = [22610.5, 22640.0, 22700.0]
    known = anchors + [5.0, 420.0, 12.0]                                    # facts मधले bar counts / MR range वाढवत नाहीत
    assert CK.unknown_prices(["rejected at 22,655"], known, anchors=anchors) == ["22,655"]          # invented
    assert CK.unknown_prices(["like BANKNIFTY 55,120"], known, anchors=anchors) == ["55,120"]       # > 1.5 × max ⇒ नाकार
    assert CK.unknown_prices(["5 legs, 420 bars ago, 9,000 contracts"], known, anchors=anchors) == []
    assert CK.price_range([12.0, 22610.5]) == (6.0, 22610.5 * 1.5)
    assert CK.price_range([]) == (100.0, float("inf"))


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
    assert W.maybe_v4(row, b"png", {}, g, "m", path=p, send_text=called.append,
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
    res = W.maybe_v4(row, b"png", {"ctx": {"levels": [{"price": 22640.0}]}}, g, "m", path=p, send_text=texts.append,
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


def test_worker_v4_errors_never_raise(tmp_path, monkeypatch):
    from vision import worker as W
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    p = str(tmp_path / "v.db")
    row = _row(p)
    g = {**VC.load("_global", p), "vision_v4_audit": "v4"}

    def boom(t):
        raise RuntimeError("x")
    assert W.maybe_v4(row, b"png", {}, g, "m", path=p, send_text=lambda t: None, client_factory=boom) is None
    assert W.run_v4_jobs([{"row": row}]) == [(row["signal_id"], None)]          # चुकीचा job ⇒ raise नाही


# ----------------------------------------------------------------------------------------------------------- budget (🔴1)
G0 = {"vision_daily_budget_usd": 2.0, "vision_monthly_budget_usd": 60.0, "signals_daily_reserve_usd": 0.20}
TODAY = pd.Timestamp("2026-10-29 11:00")                                    # गुरुवार: महिन्यात 1 weekday उरलेला (fixture तारीख)


def test_v4_budget_sub_cap_reserve_and_month():
    assert V4.budget_ok(0.05, G0, {}, TODAY, sub_cap=0.30)[0]
    ok, why = V4.budget_ok(0.05, G0, {"signal_v4": (0.27, 0.27, 6)}, TODAY, sub_cap=0.30)
    assert not ok and "V4 daily cap" in why
    ok, why = V4.budget_ok(0.05, G0, {"signal": (1.76, 10.0, 40)}, TODAY, sub_cap=2.0)
    assert not ok and "reserve" in why                                     # 1.76 + 0.05 > 2.0 − 0.20
    assert V4.budget_ok(0.04, G0, {"signal": (1.76, 10.0, 40)}, TODAY, sub_cap=2.0)[0]
    ok, why = V4.budget_ok(0.05, G0, {"signal": (0.0, 59.78, 0)}, TODAY, sub_cap=2.0)
    assert not ok and "monthly" in why                                     # 59.78 + 0.05 > 60 − 0.20 × 1
    assert V4.weekdays_left(TODAY) == 1


def test_v4_can_never_make_a_later_v2_audit_unavailable(tmp_path, monkeypatch):
    """V4 जास्तीत जास्त (दैनिक − राखीव) पर्यंतच; मग V2 चा budget check (worker._budget_ok) अजून पास होतो."""
    from vision import signal_audit as SA
    from vision import worker as W
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    p = str(tmp_path / "v.db")
    g = {**VC.load("_global", p), "vision_v4_audit": "v4", "vision_v4_daily_cap": 2.0}
    VS.add_usage("signal", "m", {}, 1.60, "x", p)                            # आज signals चा खर्च
    assert SA.estimate_usd("m") <= g["signals_daily_reserve_usd"]            # राखीव एका V2 audit ला पुरतो
    texts = []
    for i in range(20):                                                     # V4 कडून शक्य तितका खर्च (प्रत्येक call = पूर्ण अंदाज)
        row = _row(p)
        monkeypatch.setattr(V4, "audit", lambda *a, **k: (k["on_usage"]({"input_tokens": 1}, 0.12), {
            "status": "done", "data": None, "pack_version": "x", "cost_usd": 0.12})[1])
        monkeypatch.setattr(V4, "estimate", lambda *a, **k: {"usd_uncached": 0.12})
        W.maybe_v4(row, b"png", {}, g, "m", path=p, send_text=texts.append, client_factory=lambda t: object())
    day, _ = VS.spent(p)
    assert day <= g["vision_daily_budget_usd"] - g["signals_daily_reserve_usd"] + 1e-9
    assert W._budget_ok(g, "m", p)[0]                                       # V2 audit अजून चालतो (unavailable नाही)
    warn = [t for t in texts if "paused for today" in t]
    assert len(warn) == 1                                                   # 🟡c: budget इशारा दिवसातून एकदाच
    skipped = [json.loads(r["v4_json"])["status"] for r in VS.list_signals(path=p) if r["v4_json"]]
    assert "skipped" in skipped and "done" in skipped


# ----------------------------------------------------------------------------------------------------------- second pass (🔴2)
def test_run_once_finishes_all_v2_rows_before_any_v4_call(monkeypatch, tmp_path):
    import datetime as dt
    from tests import test_vision_v0 as T0
    from vision import chart as CH
    from vision import worker as W
    p = str(tmp_path / "vision.db")
    monkeypatch.setenv("VISION_DB_PATH", p)
    monkeypatch.setenv("VISION_IMAGE_DIR", str(tmp_path / "img"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-real")
    monkeypatch.setenv("VISION_SIGNAL_MODEL", "test-model")
    monkeypatch.setattr(VS, "now_ist", lambda: dt.datetime(2026, 10, 6, 10, 43))
    monkeypatch.setattr(CH, "render", lambda df, s, daily=None, **k: (b"\x89PNGfake", {"error": None, "ctx": T0.CTX_OK}))
    VC.save("_global", {"vision_v4_audit": "v4"}, "t")
    T0.queue(p)
    T0.queue(p, level=25200.0)
    order = []
    real_finish = VS.finish
    monkeypatch.setattr(VS, "finish", lambda sid, st, *a, **k: order.append(("finish", sid)) or real_finish(sid, st, *a, **k))
    monkeypatch.setattr(W, "maybe_v4", lambda row, *a, **k: order.append(("v4", row["signal_id"])))
    sent = T0.Sent()
    out = W.run_once(fetch_fn=lambda sym, daily: (T0.m1_frame(), None), client_factory=lambda t: T0.FakeClient([T0.msg(T0.GOOD)] * 4),
                     send_photo=sent.photo, send_text=sent.text)
    assert len(out) == 2
    kinds = [k for k, _ in order]
    assert kinds == ["finish", "finish", "v4", "v4"], order                 # row B चा V2 finish row A च्या V4 आधी
    assert {s for k, s in order if k == "v4"} == {s for k, s in order if k == "finish"}


def test_v4_price_facts_use_facts_and_levels_not_1m_history():
    from vision import worker as W
    row = {"level": 22640.0, "spot": 22610.5, "invalidation": None}
    meta = {"ctx": {"levels": [{"price": 22650.0}], "room": {"next_price": 22500.25}, "median_range": 12.0}}
    known, anchors = W.v4_price_facts(row, meta, "Level L: 22,640.00 as resistance. PDH 22,701.40. 420 bars, 1.2 x median range")
    assert {22640.0, 22610.5, 22650.0, 22500.25, 22701.4} <= set(known)
    assert anchors == [22500.25, 22610.5, 22640.0, 22650.0]                 # anchors फक्त किंमती (12.0 median range / 420 bars नाहीत)
    assert CK.unknown_prices(["PDH 22,701.40 swept"], known, anchors=anchors) == []
    assert CK.unknown_prices(["swept 22,702"], known, anchors=anchors) == ["22,702"]


def test_config_v4_cap_and_unset_for_rollback(tmp_path):
    p = str(tmp_path / "v.db")
    assert VC.GLOBAL_DEFAULTS["vision_v4_daily_cap"] == 0.30
    with pytest.raises(ValueError):
        VC.validate("_global", {"vision_v4_daily_cap": 5})
    VC.save("_global", {"vision_v4_audit": "v4", "vision_v4_daily_cap": 0.5, "vision_daily_budget_usd": 1.5}, "t", path=p)
    assert VC.unset("_global", ["vision_v4_audit", "vision_v4_daily_cap", "nope"], "t", path=p) == ["vision_v4_audit",
                                                                                                    "vision_v4_daily_cap"]
    with VS.connect(p) as c:
        stored = json.loads(c.execute("SELECT json FROM vision_settings WHERE bot='_global'").fetchone()[0])
    assert "vision_v4_audit" not in stored and "vision_v4_daily_cap" not in stored and stored["vision_daily_budget_usd"] == 1.5
    assert VC.history("_global", p)[-1]["by"] == "t"


# ----------------------------------------------------------------------------------------------------------- re-review #318 (2)
@pytest.mark.parametrize("probe", ["Market 25,555", "Decline 25,555", "Mayday 25,555", "leg 25,555", "no 25,555", "n 25,555",
                                   "Octave 25,555", "item 25,555"])
def test_words_before_invented_prices_do_not_hide_them(probe):
    anchors = [22610.5, 22640.0, 22700.0]
    assert CK.unknown_prices([probe], anchors, anchors=anchors) == ["25,555"]


def test_known_check_runs_before_above_range_rejection():
    anchors = [22610.5, 22640.0, 22700.0]
    known = CK.facts_prices(anchors, "Bot tags: oi=180000, OI 1,20,000 at the strike, avg 1,30,000")
    ev = ["OI 1,20,000 on the call side", "avg 1,30,000", "oi 180000 per bot tag"]
    assert CK.unknown_prices(ev, known, anchors=anchors) == []
    assert CK.unknown_prices(["OI 1,25,000"], known, anchors=anchors) == ["1,25,000"]


def test_monthly_reserve_counts_today_on_a_weekday():
    fri = pd.Timestamp("2026-10-30 11:00")                                  # महिन्याचा शेवटचा weekday (fixture तारीख)
    assert V4.weekdays_left(fri) == 0
    assert V4.budget_ok(0.05, G0, {"signal": (0.0, 59.74, 0)}, fri, sub_cap=2.0)[0]          # 59.79 ≤ 60 − 0.20 × 1
    ok, why = V4.budget_ok(0.05, G0, {"signal": (0.0, 59.76, 0)}, fri, sub_cap=2.0)
    assert not ok and "monthly" in why
    sat = pd.Timestamp("2026-10-31 11:00")
    assert V4.budget_ok(0.05, G0, {"signal": (0.0, 59.90, 0)}, sat, sub_cap=2.0)[0]          # शनिवार: आजचा राखीव नाही


def test_budget_reason_text_when_reserve_exceeds_daily():
    ok, why = V4.budget_ok(0.05, {**G0, "vision_daily_budget_usd": 0.10, "signals_daily_reserve_usd": 0.20}, {}, TODAY, sub_cap=0.3)
    assert not ok and "$-" not in why and "reserve $0.20" in why


def test_v4_pass_cap_and_skip_when_new_rows_queued(tmp_path, monkeypatch):
    import datetime as dt
    from vision import worker as W
    p = str(tmp_path / "v.db")
    monkeypatch.setattr(VS, "now_ist", lambda: dt.datetime(2026, 10, 12, 12, 0))
    calls = []
    monkeypatch.setattr(W, "maybe_v4", lambda row, *a, **k: calls.append(row["signal_id"]))
    rows = [_row(p) for _ in range(3)]
    for r in rows:
        VS.finish(r["signal_id"], "DONE", p)
    jobs = [{"row": r, "png": b"p", "meta": {}, "g": {}, "model": "m", "path": p} for r in rows]
    W.run_v4_jobs(jobs, path=p, limit=2, check_queue=True)
    assert calls == [rows[0]["signal_id"], rows[1]["signal_id"]]           # कमाल 2; तिसरा सोडला (audit-only) + नोंद
    with VS.connect(p) as c:
        ev = [tuple(x) for x in c.execute("SELECT signal_id, event FROM vision_events WHERE event='v4_dropped'")]
    assert ev == [(rows[2]["signal_id"], "v4_dropped")]
    calls.clear()
    _row(p)                                                                 # नवा QUEUED row (bar बंद) ⇒ V4 पास वगळतो
    assert W.ready_queued(p) == 1
    W.run_v4_jobs(jobs[:1], path=p, limit=2, check_queue=True)
    assert calls == []


def test_v4_budget_warning_not_sent_for_shadow_rows(tmp_path, monkeypatch):
    from vision import worker as W
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    p = str(tmp_path / "v.db")
    g = {**VC.load("_global", p), "vision_v4_audit": "v4", "vision_v4_daily_cap": 0.0}
    texts = []
    r = W.maybe_v4(_row(p, "shadow"), b"png", {}, g, "m", path=p, send_text=texts.append, client_factory=lambda t: object())
    assert r["status"] == "skipped" and texts == []
    W.maybe_v4(_row(p, "notify"), b"png", {}, g, "m", path=p, send_text=texts.append, client_factory=lambda t: object())
    assert len(texts) == 1 and "paused for today" in texts[0]
