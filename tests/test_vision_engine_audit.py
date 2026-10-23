"""T-5 (owner-orders DECISIONS 31, PROVISIONAL): an ENGINE signal is audited against the engine's own reading — the engine card and the
method's concept checklist; the old level-bot session / gap / opening / L-line rules are context lines only and never floor the verdict.
Level-bot signals (signal_source = own) stay byte-identical (pinned). Verdict × outcome table. No real model API call (fake client)."""
import hashlib
import json
import re

import pandas as pd
import pytest

from reader_report import standard as RS
from tests.test_vision_v0 import GOOD, msg
from tests.test_vision_v2 import bars
from vision import chart as CH
from vision import config as VC
from vision import engine_audit as EA
from vision import engine_measure as EM
from vision import signal_audit as SA
from vision import store as VS
from vision import worker as VW

TS = pd.Timestamp("2026-10-06 11:15")


class Fake:
    def __init__(self, replies):
        self.replies, self.calls, self.messages = list(replies), [], self

    def create(self, **params):
        self.calls.append(params)
        return self.replies.pop(0)


def ok_reply(verdict="agree", **status):
    ck = {k: {"status": status.get(k, "pass"), "note": f"{k} read on the chart"} for k in EA.KEYS}
    return {"checklist": ck, "verdict": verdict, "reason": "engine चं वाचन chart वर दिसतं", "confidence": 0.8}


def engine_sig(df=None, **k):
    df = bars() if df is None else df
    last = float(df[df.timestamp < TS].close.iloc[-1])
    tags = {"engine": True, "engine_bar": str(TS), "entry_model": "E4", "entry_name": "Sweep-retest (b)",
            "entry_label": "E4 (b) — Sweep-retest", "entry_object": "broken_area", "entry_visit": "287@x", "entry_area_id": "287",
            "entry_trigger_ts": "2026-10-06 11:00:00", "entry_ref": last,
            "entry_invalidation": {"price": last + 30, "rule": f"price above the retest extreme {last + 30:,.2f}"},
            "entry_evidence": [["required set (handover + commitment + volume + LTF CHoCH)", "✗"], ["RSI divergence", "✓"]],
            "gate": {"mode": "engine", "side": "BEARISH", "area": [last - 5, last + 15], "tf": "15M", "trend": "DOWN",
                     "htf": {"weekly": "DOWN", "daily": "DOWN", "daily_phase": "correction"},
                     "refined": {"lo": last - 2, "hi": last + 6, "ts": "2026-10-06 10:00:00"},
                     "areas": [{"id": "287", "role": "resistance", "lo": last - 5, "hi": last + 15, "tf": "1H", "state": "BROKEN"},
                               {"id": "201", "role": "support", "lo": last - 80, "hi": last - 60, "tf": "1H", "state": "TESTED"},
                               {"id": "202", "role": "support", "lo": last - 40, "hi": last - 30, "tf": "1H", "state": "DEAD"}]}}
    return {"bot": "srv2_momentum_reversal", "symbol": "NIFTY", "direction": "BEARISH", "role": "RESISTANCE", "level": last + 5,
            "setup_tf": "15M", "signal_ts": TS, "spot": last, "tags": tags, **k}


OLD_CTX = {   # the old level-bot facts that floored the 22 Oct card: opening, an event day, a with-gap chase, the L line role conflict
    "time_flag": "opening", "median_range": 10.0, "level": 24990.0, "room": {"next_mr": 3.0},
    "gap_ctx": {"event": "policy", "has_gap": True, "direction": "down", "class": "G3", "fill_pct": 5, "pdc_acceptance": True,
                "behaviour": "undecided", "bars_15m_done": 2, "pdc": None, "error": None, "reason": "test"},
    "l_line": {"approach": "from above", "opening_side": "below", "earlier_role": "held_as_support", "broken": False, "reclaimed": False,
               "broken_at": None, "spot_side": "below", "bot_role": "RESISTANCE", "today_role": "held_as_support"},
}


# ------------------------------------------------------------------------------------------------ the engine card + checklist
def test_engine_signal_is_audited_with_the_engine_card_and_checklist(monkeypatch):
    df = bars()
    s = engine_sig(df)
    monkeypatch.setattr("plotly.graph_objects.Figure.to_image", lambda self, **k: b"\x89PNG-engine")
    png, meta = CH.render(df, s)
    assert png == b"\x89PNG-engine" and meta["card"] == "engine" and meta["error"] is None
    ctx = meta["ctx"]
    assert ctx["signal_source"] == "engine" and ctx["engine"]["model"] == "E4" and ctx["engine"]["object"] == "broken_area"
    assert ctx["engine"]["next_area"]["lo"] == s["tags"]["gate"]["areas"][1]["lo"]          # the engine's own opposite area (DEAD skipped)
    # the card: the engine's objects, never the L line / reference levels / opening band
    setup, higher, tfs, cut = CH.panels(df, TS, "15M", return_cut=True)
    fig = CH.engine_figure(cut, setup, higher, tfs, s, {}, None, {})
    texts = [a.text for a in fig.layout.annotations]
    for want in ("BASE 15M", "BROKEN 1H AREA (retest from below)", "T ▼"):
        assert want in texts, texts
    assert any(t.startswith("INV ") for t in texts) and any(t.startswith("NEXT demand") for t in texts)
    assert not any("L RESISTANCE" in t or "PDH" in t or "ORH" in t or "OPEN" in t for t in texts)
    assert "HTF: W DOWN · D DOWN (correction) · trend used DOWN" in fig.layout.title.text
    # the audit: the engine prompt / schema / facts, the method's checklist
    fake = Fake([msg(ok_reply())])
    res = SA.audit(fake, png, {**s, "ctx": ctx}, "test-sonnet-model")
    p = fake.calls[0]
    assert p["system"][0]["text"] == EA.SYSTEM_PROMPT and p["output_config"]["format"]["schema"] == EA.SCHEMA
    text = p["messages"][0]["content"][1]["text"]
    assert "Entry model: E4 Sweep-retest (b)" in text and "Retested object" in text and "Invalidation:" in text
    assert "Traded level L" not in text and "Gap" not in text and "PDH" not in text
    assert res["verdict"] == "agree" and res["prompt_version"] == EA.PROMPT_VERSION
    assert set(res["audits"][0]["checklist"]) == set(EA.KEYS) and res["rule_hits"][0]["disagree"] == []


def test_engine_checklist_fail_floors_and_evidence_never_decides():
    s = {**engine_sig(), "ctx": {"signal_source": "engine"}}
    r = SA.audit(Fake([msg(ok_reply(trigger_in_base="fail"))]), b"png", s, "test-sonnet-model")
    assert r["verdict"] == "disagree" and r["rule_hits"][0]["disagree"] == ["trigger_in_base"]      # Vision's own concept, named
    r = SA.audit(Fake([msg(ok_reply(evidence="fail"))]), b"png", s, "test-sonnet-model")
    assert r["verdict"] == "agree"                                                                 # evidence is listed, never blocks
    r = SA.audit(Fake([msg(ok_reply(visit="unclear"))]), b"png", s, "test-sonnet-model")
    assert r["verdict"] == "gray" and r["rule_hits"][0]["gray"] == ["visit"]
    bad = ok_reply()
    del bad["checklist"]["visit"]
    assert SA.audit(Fake([msg(bad)]), b"png", s, "test-sonnet-model")["verdict"] == "unavailable"


# ------------------------------------------------------------------------------------------------ old rules = context only
def test_session_and_gap_rules_never_floor_an_engine_verdict():
    own = {"bot": "srv2_momentum_reversal", "symbol": "NIFTY", "direction": "BEARISH", "role": "RESISTANCE", "level": 24990.0,
           "setup_tf": "15M", "signal_ts": TS, "spot": 24985.0, "tags": {}, "ctx": dict(OLD_CTX)}
    r_own = SA.audit(Fake([msg(GOOD)]), b"png", own, "test-sonnet-model")
    assert r_own["verdict"] == "disagree"                                                           # the old rulebook floors it
    assert {"opening", "role_conflict"} <= set(r_own["rule_hits"][0]["disagree"])
    eng = {**engine_sig(), "ctx": {**OLD_CTX, "signal_source": "engine"}}
    r = SA.audit(Fake([msg(ok_reply())]), b"png", eng, "test-sonnet-model")
    assert r["verdict"] == "agree" and r["rule_hits"][0]["disagree"] == [] and r["rule_hits"][0]["gray"] == []
    ctxo = r["rule_hits"][0]["context_only"]                                                        # shown as context lines only
    assert {"opening", "role_conflict", "gap_b_pdc_accept"} <= set(ctxo["disagree"]) and "event_day" in ctxo["gray"]
    lines = EA.caption_lines(r["audits"][0], r["rule_hits"][0])
    assert any(x.startswith("Context only (old level-bot rules, not in the verdict): ") and "opening" in x for x in lines)
    # the worker's reuse path re-applies the facts on the marked context: still the engine rules
    a, _ = SA.apply_facts(r["audits"][0], eng["ctx"], "BEARISH")
    assert SA.code_verdict(a, None, None, eng["ctx"], "BEARISH") == "agree"
    assert "time_risk" not in a                                                                       # no session fact written in
    # the what-if switch: `legacy` keeps the old audit for engine signals
    leg = {**engine_sig(), "ctx": dict(OLD_CTX), "ctx_settings": {"vision_engine_audit": "legacy"}}
    assert not EA.use_engine(leg) and SA.audit(Fake([msg(GOOD)]), b"png", leg, "test-sonnet-model")["verdict"] == "disagree"


# ------------------------------------------------------------------------------------------------ level bots byte-identical
def _own_fingerprint(sa):
    sig = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "direction": "BULLISH", "role": "SUPPORT", "level": 24990.0, "setup_tf": "5M",
           "signal_ts": "2026-10-06 11:01:00", "spot": 25000.0, "tags": {"gate": {"area": [24980.0, 24995.0], "side": "BULLISH"}},
           "ctx": dict(OLD_CTX)}
    req = sa.build_request(b"png", sig, "test-sonnet-model", effort="low")
    res = sa.audit(Fake([msg({**GOOD, "confidence": 0.4}), msg({**GOOD, "verdict": "gray"})]), b"png", sig, "test-sonnet-model",
                   disagree_rules=VC.BOT_DEFAULTS["v2_disagree_rules"], gray_rules=VC.BOT_DEFAULTS["v2_gray_rules"])
    res = {k: v for k, v in res.items() if k != "latency_ms"}                                    # wall-clock, not behaviour
    a = sa.validate(GOOD)[0]
    extra = [sa.apply_facts(a, OLD_CTX, "BEARISH"), sa.rule_hits(a, None, None, OLD_CTX, "BEARISH"),
             sa.code_verdict(a, None, None, OLD_CTX, "BULLISH"), sa.pre_verdict(OLD_CTX, "BEARISH"), sa.code_facts(OLD_CTX, "BEARISH")]
    blob = json.dumps([req, res, extra, sa.PROMPT_VERSION], sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


OWN_PIN = "52d72cd870350f2dce3fca5adf7d36014ad28bde2f62803ae7c512933ff86654"   # the pre-T-5 code (git show HEAD~ version); a deliberate
                                                                                      # level-bot prompt change updates it


def test_level_bot_audit_is_byte_identical():
    """signal_source = own: the request (prompt, schema, signal text), the audit result, the code facts / rule hits / floor — pinned
    to the values of the code before T-5 (computed from that version)."""
    assert _own_fingerprint(SA) == OWN_PIN


def test_level_bot_card_and_reuse_unchanged(monkeypatch):
    df = bars()
    own = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "direction": "BULLISH", "role": "SUPPORT", "level": 24990.0,
           "setup_tf": "5M", "signal_ts": pd.Timestamp("2026-10-06 11:01"), "spot": 25000.0, "tags": {}}
    monkeypatch.setattr("plotly.graph_objects.Figure.to_image", lambda self, **k: b"\x89PNG-own")
    png, meta = CH.render(df, own)
    assert png == b"\x89PNG-own" and "card" not in meta and "signal_source" not in meta["ctx"] and "engine" not in meta["ctx"]
    assert not EA.is_engine(own) and not EA.is_engine({**own, "tags": {"gate": {"mode": "confirmation"}}})
    j = lambda t: json.dumps({"tags": t})  # noqa: E731
    assert VS._engine_tag(j({})) is False and VS._engine_tag(j({"engine": True})) is True


# ------------------------------------------------------------------------------------------------ prompt: no time framing, no numbers
FORBIDDEN = re.compile(r"\b(today|yesterday|session|opening|open range|PDH|PDL|PDC|ORH|ORL|PWH|PWL|minutes?|IST|morning|afternoon|"
                       r"last hour|event day|weekday|G[0-5])\b", re.I)
CLOCK = re.compile(r"\b\d{1,2}:\d{2}\b|\b\d{4}-\d{2}-\d{2}\b")


def test_engine_prompt_has_no_time_framing_and_no_numbers_in_rules():
    for text in (EA.SYSTEM_PROMPT, EA.facts_text(engine_sig()), json.dumps(EA.SCHEMA)):
        assert not RS._DAY_RE.search(text.lower()), RS._DAY_RE.search(text.lower())
        assert not FORBIDDEN.search(text), FORBIDDEN.search(text)
        assert not CLOCK.search(text), CLOCK.search(text)
    rules = re.sub(r"\bE[1-4]\b|\b(15M|1H|5M)\b", "", EA.SYSTEM_PROMPT)       # model ids and timeframe labels are names, not numbers
    assert not re.search(r"\d", rules), re.search(r"\d", rules)


# ------------------------------------------------------------------------------------------------ worker end to end
@pytest.fixture
def vdb(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_DB_PATH", str(tmp_path / "v.db"))
    return str(tmp_path / "v.db")


def test_worker_records_the_engine_audit(vdb, monkeypatch):
    df = bars()
    s = engine_sig(df)
    VC.save("srv2_momentum_reversal", {"vision_mode": "auto_veto", "vision_gray_action": "skip", "vision_fail_action": "skip"}, "t",
            trading_mode_fn=lambda b, s_: "PAPER")
    row = {"bot": s["bot"], "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "auto_veto", "signal_ts": TS, "direction": "BEARISH",
           "level": s["level"], "role": "RESISTANCE", "setup_tf": "15M", "spot": s["spot"], "algo_decision": "ENTER",
           "setup": {"tags": s["tags"]}}
    sid = VS.insert_signal(row)
    r = VS.claim_one(sid)
    monkeypatch.setenv("VISION_SIGNAL_MODEL", "test-sonnet-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr("plotly.graph_objects.Figure.to_image", lambda self, **k: b"\x89PNG-engine")
    from vision import images as IM
    from vision import tg as TG
    monkeypatch.setattr(IM, "save_exclusive", lambda p, png: ("/tmp/x_sent.png", "sha"))
    monkeypatch.setattr(IM, "read_verified", lambda p, sha: b"\x89PNG-engine")
    monkeypatch.setattr(TG, "send_photo", lambda *a, **k: 1)
    fake = Fake([msg(ok_reply())])
    out = VW.process_row(r, fetch_fn=lambda sym, daily: (df[df.timestamp < TS + pd.Timedelta(minutes=15)], None),
                         client_factory=lambda t: fake, wait_for_bar=False)
    got = VS.get_signal(sid)
    assert out["verdict"] == "agree" and got["verdict"] == "agree" and got["prompt_version"] == EA.PROMPT_VERSION, got["error"]
    vj = json.loads(got["vision_json"])
    assert vj["context"]["signal_source"] == "engine" and "context_only" in vj["rule_hits"][0]
    assert fake.calls[0]["system"][0]["text"] == EA.SYSTEM_PROMPT
    body = VW._body({**row, "signal_ts": TS, "tags": s["tags"]}, out, "auto_veto")
    assert "✓ Trend side" in body and "level None" not in body


# ------------------------------------------------------------------------------------------------ verdict × outcome
def _m1(path):
    """1m bars from (minute offset, high, low, close) points, the rest flat."""
    t0 = pd.Timestamp("2026-10-06 11:15")
    rows = []
    for k in range(240):
        t = t0 + pd.Timedelta(minutes=k)
        if t.hour >= 15 and t.minute >= 30 or t.hour > 15:
            continue
        o = c = 25000.0
        h, lo = 25001.0, 24999.0
        for m, hh, ll, cc in path:
            if k == m:
                h, lo, c = hh, ll, cc
        rows.append((t, o, h, lo, c))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def _row(ctx_engine, **k):
    return {"signal_id": "s1", "signal_ts": "2026-10-06 11:15:00", "direction": "BEARISH", "symbol": "NIFTY", "spot": 25000.0,
            "setup_json": json.dumps({"tags": {"engine": True, "entry_label": "E4 (b) — Sweep-retest"}}),
            "vision_json": json.dumps({"context": {"engine": ctx_engine}}), **k}


def test_structure_outcome_next_area_first_or_invalidation_first():
    rd = {"next_area": {"role": "support", "lo": 24900.0, "hi": 24920.0}, "invalidation": 25030.0}
    down = _m1([(20, 25001.0, 24918.0, 24930.0)])                                        # trades into the next area first
    assert EM.structure_outcome(down, _row(rd))["result"] == "next_area_first"
    up = _m1([(14, 25040.0, 24999.0, 25035.0), (40, 25001.0, 24910.0, 24930.0)])        # a 15M close above the invalidation first
    assert EM.structure_outcome(up, _row(rd))["result"] == "invalidation_first"
    assert EM.structure_outcome(_m1([]), _row(rd))["result"] == "open_at_data_end"
    wick = _m1([(14, 25040.0, 24999.0, 25000.0), (40, 25001.0, 24910.0, 24930.0)])      # only a wick beyond: not a close beyond
    assert EM.structure_outcome(wick, _row(rd))["result"] == "next_area_first"


def test_verdict_vs_outcome_table():
    def r(sid, verdict, abhi, pnl, st, engine=True):
        tags = {"engine": True, "entry_model": "E4"} if engine else {}
        return {"signal_id": sid, "signal_ts": "2026-10-22 10:15:00", "symbol": "NIFTY", "direction": "BEARISH", "level": 22747.0,
                "verdict": verdict, "human_decision": abhi, "final_decision": "ENTER", "status": "EXECUTED",
                "setup_json": json.dumps({"tags": tags}),
                "outcome_json": json.dumps({"trade_id": "t" + sid, "realized_pnl": pnl, "result": "win" if pnl > 0 else "loss",
                                            "structure": {"result": st}})}
    rows = [r("a", "disagree", "approve", 1200.0, "next_area_first"), r("b", "agree", "approve", -800.0, "invalidation_first"),
            r("c", "disagree", "reject", -300.0, "invalidation_first"), r("d", "gray", "approve", 50.0, "open_at_data_end"),
            r("e", "agree", "approve", 999.0, "next_area_first", engine=False),                                # a level-bot trade
            {**r("f", "agree", "approve", 1.0, "x"), "outcome_json": None}]                                   # no closed trade
    rec = EM.closed_rows(rows)
    assert [x["signal_id"] for x in rec] == ["a", "b", "c", "d"]
    t = EM.table(rec).set_index("verdict")
    assert list(t.index) == ["agree", "gray", "disagree"]
    assert t.loc["disagree", "trades"] == 2 and t.loc["disagree", "next_area_first"] == 1 and t.loc["disagree", "invalidation_first"] == 1
    assert t.loc["disagree", "abhi_approve"] == 1 and t.loc["disagree", "abhi_reject"] == 1 and t.loc["disagree", "pnl"] == 900.0
    assert t.loc["agree", "loss"] == 1 and t.loc["gray", "open_at_data_end"] == 1
    assert EM.table([]).empty
