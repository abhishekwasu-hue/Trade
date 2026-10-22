"""Chart Reading Report (Abhi's order, owner-orders DECISIONS 35): the message maps every section to a reader fact (a fixture per
concept), an empty concept is omitted, ≤ 4096 Telegram units with the overflow line + link, the "not visible" Vision rule, the language
setting, no look-ahead (the report at a close uses bars ≤ that close), golden-format snapshots in English and Marathi, no buy / sell /
target / stop words and no date / clock framing in the reading, the old level-count message off by default, the dashboard settings.
Synthetic facts + a synthetic V22 only; no network, no model call (Vision = a fake client)."""
import copy
import json
import pathlib
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from bots_common import chart_reading_text as CT

GOLDEN = pathlib.Path(__file__).parent / "golden"


def area(i, tf="1H", role="resistance", lo=100.0, hi=110.0, state="ACTIVE", dist=5.0, **kw):
    a = {"id": i, "tf": tf, "role": role, "kind": "supply" if role == "resistance" else "demand", "lo": lo, "hi": hi, "state": state,
         "tests": 0, "sweeps": 0, "flips": 0, "was": None, "dist": dist, "above": role == "resistance", "below": role == "support",
         "trade_location": True, "born_bar": 0, "confluence_label": None, "src": "levels.snapshot (K4 lifecycle)"}
    a.update(kw)
    return a


A1 = area(11, lo=22760, hi=22820, state="FLIPPED", was="support", tests=1, dist=40, confluence=[{"what": "line"}])
A2 = area(12, lo=22900, hi=22950, dist=120)
OPP = area(21, role="support", lo=22560, hi=22610, dist=110)
DLY = area(31, tf="D", lo=23050, hi=23200, state="TESTED", tests=2, dist=270)

FACTS = {
    "symbol": "NIFTY", "t": 999, "as_of": "2030-01-01 15:30:00", "bar": "2030-01-01 15:15:00", "last_close": 22720.0, "fut_volume": True,
    "errors": {},
    "big_picture": {"tfs": {"W": {"state": "correction in progress", "trend": "UP", "protected": 21000.0, "band": None, "src": "mtf_state.tfs[W]"},
                            "D": {"state": "trending down", "trend": "DOWN", "protected": 23180.0, "band": None, "src": "mtf_state.tfs[D]"},
                            "1H": {"state": "range", "trend": "RANGE", "protected": None, "band": [22600.0, 22950.0], "src": "mtf_state.tfs[1H]"},
                            "15M": {"state": "correction in progress", "trend": "DOWN", "protected": None, "band": None, "src": "x"},
                            "5M": {"state": "unclear", "trend": None, "protected": None, "band": None, "src": "x"}},
                    "daily": {"trend": "DOWN", "trend_used": "DOWN", "phase": "correction", "protected": 23180.0, "protected_kind": "H",
                              "weekly": "UP", "src": "decision row ① (daily.fold_impulse)"},
                    "agreement": {"W": "against", "D": "reference", "1H": "range", "15M": "correction", "5M": "unclear"}, "side": "DOWN"},
    "structure": {"events": [{"tf": "1H", "type": "CHoCH", "dir": "down", "level": 22790.0, "src": "mtf_state.1H.external.events"}],
                  "legs": [{"tf": "1H", "dir": "down", "verdict": "impulse", "complete": True,
                            "measures": {"body": "impulse", "overlap": "impulse", "volume": "impulse"}, "p0": 22950, "p1": 22600,
                            "src": "legs_compare.tfs[1H].legs"},
                           {"tf": "1H", "dir": "up", "verdict": "correction", "complete": False,
                            "measures": {"body": "correction", "overlap": "correction", "volume": "correction"}, "p0": 22600, "p1": 22720,
                            "src": "legs_compare.tfs[1H].legs"}], "legs_htf": []},
    "areas": {"watch": [A1, A2], "next_opposite": OPP, "htf": [DLY], "broken": [], "alive": [A1, A2, OPP, DLY],
              "duplicates": [], "shown_ids": [11, 12, 21, 31]},
    "liquidity": {"above": {"price": 22950.0, "equal": True, "state": "resting", "src": "liquidity_pa.obvious"},
                  "below": {"price": 22600.0, "equal": False, "state": "resting", "src": "liquidity_pa.obvious"},
                  "sweep": {"state": "swept", "pool": 22600.0, "extreme": 22580.0, "beyond": "below", "src": "liquidity.sweeps_and_traps"},
                  "inducement": None},
    "lines": {"channels": [{"tf": "1H", "degree": 2, "slope": "falling", "upper": 22830.0, "lower": 22590.0, "touches": 3, "id": "c1",
                            "geom": [], "src": "decision row channels (trendline.channels)"}], "above": None, "below": None},
    "patterns": [{"name": "double bottom", "family": "double_bottom", "state": "forming", "named": False,
                  "boundaries": {"neckline": "inside"}, "lines": [{"name": "neckline", "value": 22950.0}], "tf": "1H", "end_bar": 990,
                  "src": "patterns_pa.read_patterns"}],
    "confluence": [{"id": 11, "tf": "1H", "kind": "supply", "lo": 22760, "hi": 22820, "pieces": [{"what": "line"}],
                    "src": "confluence_pa.read_confluence areas"}],
    "volume": {"missing": False, "pullback": {"state": "lower", "impulse_dir": -1, "pullback_avg": 900.0, "impulse_avg": 1500.0},
               "effort_result": "in harmony", "climax": "none", "src": "volume_read.read_volume"},
    "rsi": {"regular": [{"side": "bull", "degree": 2, "p0": 22650.0, "p1": 22600.0, "state": "confirmed", "t0": "2030-01-01 10:00:00",
                         "t1": "2030-01-01 14:00:00", "src": "rsi2 regular divergence (draw_objects.divergences)"}],
            "hidden": {"side": "bear", "found": False, "src": "rsi_hidden.read_hidden_divergence"}},
    "breakout_range": {"in_range": True, "tfs": ["1H"], "edges": [
        {"tf": "1H", "edge": "lower", "lo": 22600.0, "hi": 22610.0, "lifecycle": "tested", "src": "range_edges.range_state"},
        {"tf": "1H", "edge": "upper", "lo": 22940.0, "hi": 22950.0, "lifecycle": "fresh", "src": "range_edges.range_state"}],
        "breakouts": [], "sweeps": []},
    "wave": {"weekly_detail": "same-degree correction candidate (leg b)", "daily_leg": "L4", "corr_label": "b", "daily_phase": "correction",
             "weekly_state": "correction in progress", "weekly_counter": "candidate", "src": "decision row wave_context (daily)",
             "model_c": "off"},
    "plan": {"trend": "DOWN", "sides": ["bear_call"], "nearest": A1, "next_same_side": A2, "models": {}, "refined": {
        "lo": 22790.0, "hi": 22815.0, "far": 22815.0, "ts": "x", "src": "entry_models.Reader.refined (RC2)"}, "entries": [],
        "models_on": ["E1", "E2", "E3", "E4"], "src": "entry_models.read (decision row armed)", "far_edge": 22820.0, "d": -1},
}

SECTION_OF = {"big_picture": "big", "structure": "struct", "areas": "areas", "liquidity": "liq", "lines": "lines", "patterns": "lines",
              "confluence": "lines", "volume": "vol", "rsi": "vol", "breakout_range": "brk", "wave": "wave", "plan": "plan"}
EMPTY = {"big_picture": {}, "structure": {"events": [], "legs": []}, "areas": {}, "liquidity": {}, "lines": {}, "patterns": [],
         "confluence": [], "volume": {}, "rsi": {}, "breakout_range": {}, "wave": {}}


KEEP = {"confluence": ("areas",)}                                         # confluence labels land ON the areas (concept F)
ALSO = {"patterns": {"brk"}, "confluence": {"areas"}}                      # a pattern's boundary state is concept K too


def only(concept):
    f = {k: copy.deepcopy(v) for k, v in FACTS.items()}
    for k, v in EMPTY.items():
        if k != concept and k not in KEEP.get(concept, ()):
            f[k] = copy.deepcopy(v)
    return f


# ------------------------------------------------------------------------------------------------------------------- sections ↔ facts
@pytest.mark.parametrize("concept", sorted(SECTION_OF))
def test_every_section_maps_to_its_reader_fact(concept):
    """A fixture per concept: only that concept's facts ⇒ its section appears and every line of it names that reader fact."""
    f = only(concept)
    secs = {k: lines for k, _, lines in CT.sections(f, "en", "full", vision=None)}
    key = SECTION_OF[concept]
    assert key in secs, concept
    for k, lines in secs.items():
        if k in ("plan", "vision"):
            continue
        assert k == key or k in ALSO.get(concept, set()), (concept, k)
        for x in lines:
            assert x["src"] and not x["src"].startswith("?"), x


def test_lines_carry_their_source_everywhere():
    text, meta = CT.render(FACTS, "en", "full")
    assert meta["lines"] and all(x["src"] for x in meta["lines"])
    srcs = " ".join(x["src"] for x in meta["lines"])
    for s in ("mtf_state", "legs_compare", "levels.snapshot", "liquidity_pa", "trendline", "patterns_pa", "confluence_pa", "volume_read",
              "rsi2", "range_edges", "wave_context", "entry_models", "RC2", "model_c"):
        assert s in srcs, s


def test_empty_concept_is_omitted():
    f = copy.deepcopy(FACTS)
    f["liquidity"] = {"above": None, "below": None, "sweep": None}
    f["structure"] = {"events": [], "legs": []}
    text, meta = CT.render(f, "en", "full")
    assert "💧 Liquidity" not in text and "🏗 Structure" not in text and "liq" not in meta["sections"]
    assert "🧭 Big picture" in text and "🎯 What the engine waits for" in text


# ------------------------------------------------------------------------------------------------------------------- length
def big_facts():
    f = copy.deepcopy(FACTS)
    f["areas"]["watch"] = [area(100 + i, lo=22760 + 10 * i, hi=22800 + 10 * i, dist=40 + i) for i in range(60)]
    f["areas"]["htf"] = [area(300 + i, tf="D", lo=23000 + 50 * i, hi=23040 + 50 * i, dist=300 + i) for i in range(40)]
    f["areas"]["duplicates"] = [{"tf": "1H", "kind": "supply", "ids": [100 + i, 300 + i], "lo": 1, "hi": 2, "src": "levels.snapshot"}
                                for i in range(40)]
    f["lines"]["channels"] = [dict(FACTS["lines"]["channels"][0], id=f"c{i}") for i in range(40)]
    f["confluence"] = [dict(FACTS["confluence"][0], id=300 + i) for i in range(40)]
    return f


@pytest.mark.parametrize("lang", ["en", "mr"])
@pytest.mark.parametrize("detail", ["short", "full"])
def test_length_fits_one_telegram_message_with_overflow_link(lang, detail):
    text, meta = CT.render(big_facts(), lang, detail, link="https://dash.example/chart-reading")
    assert CT.tg_len(text) <= CT.TELEGRAM_LIMIT and meta["length"] <= CT.TELEGRAM_LIMIT
    assert text.splitlines()[-1].endswith("https://dash.example/chart-reading")
    if detail == "full":
        assert meta["cut"] and (CT.T["more"][lang] in text)
    assert "plan" in meta["sections"]                                     # the plan is never dropped


def test_tiny_limit_still_ends_with_the_link():
    text, meta = CT.render(FACTS, "en", "full", link="L", limit=300)
    assert CT.tg_len(text) <= 300 and text.endswith("Full report → L") and meta["cut"]


def test_telegram_length_counts_utf16_units():
    assert CT.tg_len("🔴") == 2 and CT.tg_len("मराठी") == 5 and CT.tg_len("abc") == 3


# ------------------------------------------------------------------------------------------------------------------- language
def test_language_setting_changes_the_words_not_the_facts():
    en, _ = CT.render(FACTS, "en", "short")
    mr, _ = CT.render(FACTS, "mr", "short")
    assert en != mr
    assert re.search(r"[ऀ-ॿ]", mr) and not re.search(r"[ऀ-ॿ]", en)
    nums = lambda s: re.findall(r"\d[\d,]*", s)                            # noqa: E731 — the same numbers in both languages
    assert sorted(set(nums(en))) == sorted(set(nums(mr)))
    with pytest.raises(ValueError):
        CT.render(FACTS, "fr")


def test_dashboard_settings_defaults_and_validation():
    import cloud_db
    s = cloud_db.get_chart_reading_settings(raw_fn=lambda *a: {})
    assert s["chart_reading_report"] == "off" and s["chart_reading_language"] == "mr" and s["chart_reading_detail"] == "short"
    assert s["chart_reading_vision"] == "off" and s["visual_audit_level_message"] == "off" and s["chart_reading_symbols"] == []
    s2 = cloud_db.get_chart_reading_settings(raw_fn=lambda *a: {"chart_reading_language": "en", "chart_reading_detail": "bogus"})
    assert s2["chart_reading_language"] == "en" and s2["chart_reading_detail"] == "short"      # a bad stored value ⇒ that default
    assert cloud_db.clean_chart_reading_settings({"chart_reading_symbols": "nifty, BANKNIFTY"}) == {
        "chart_reading_symbols": ["NIFTY", "BANKNIFTY"]}
    for bad in ({"chart_reading_language": "fr"}, {"chart_reading_symbols": ["MCX"]}, {"nope": 1}, {"chart_reading_page_url": "x"}):
        with pytest.raises(ValueError):
            cloud_db.clean_chart_reading_settings(bad)


def test_old_level_count_message_is_off_by_default():
    import run_visual_audit as RVA
    assert RVA.level_message_on(lambda: {}) is False
    assert RVA.level_message_on(lambda: {"visual_audit_level_message": "on"}) is True
    assert RVA.level_message_on(lambda: (_ for _ in ()).throw(RuntimeError("db"))) is False


# ------------------------------------------------------------------------------------------------------------------- words
@pytest.mark.parametrize("lang", ["en", "mr"])
def test_no_forbidden_words_and_no_date_framing(lang):
    for f in (FACTS, big_facts()):
        for detail in ("short", "full"):
            text, _ = CT.render(f, lang, detail)
            assert CT.check(text) == [], CT.check(text)
            assert "22,760–22,820" in text                                # areas as ranges


def test_check_catches_the_forbidden_and_the_dates():
    bad = "📘 X — header\n• sell at the target 22,700 on 2030-01-01 10:15 session"
    probs = " ".join(CT.check(bad))
    for w in ("sell", "target", "2030-01-01", "10:15", "session"):
        assert w in probs


# ------------------------------------------------------------------------------------------------------------------- golden format
@pytest.mark.parametrize("lang", ["en", "mr"])
def test_golden_format_snapshot(lang):
    text, _ = CT.render(FACTS, lang, "short", link="https://dash.example/chart-reading")
    want = (GOLDEN / f"chart_reading_{lang}.txt").read_text(encoding="utf-8").rstrip("\n")
    assert text == want


def test_refresh_lists_changes_or_says_none():
    f2 = copy.deepcopy(FACTS)
    assert "No change since the close reading" in CT.refresh(FACTS, f2, "en")
    f2["areas"]["watch"][0]["state"] = "BROKEN"
    f2["big_picture"]["tfs"]["1H"]["state"] = "trending down"
    f2["big_picture"]["tfs"]["1H"]["trend"] = "DOWN"
    r = CT.refresh(FACTS, f2, "en")
    assert "#11 22,760–22,820: FLIPPED → BROKEN" in r and "1H: range → trending down" in r
    assert "Close चं वाचन साठवलेलं नाही" in CT.refresh(None, f2, "mr")


# ------------------------------------------------------------------------------------------------------------------- Vision
class FakeClient:
    """A fake Messages client: the overlay call answers SPURIOUS for every label it is given; the independent call one zone."""
    def __init__(self):
        self.calls = []
        self.messages = self

    def create(self, **params):
        self.calls.append(params)
        text = params["messages"][-1]["content"][1]["text"]
        if "Labelled zones" in text:
            labels = json.loads(text.split("\n")[1])
            data = {"verdicts": [{"label": x["label"], "verdict": "SPURIOUS", "reason": "single spike"} for x in labels],
                    "missing": [{"approx_low": 120.0, "approx_high": 125.0, "kind": "SUPPLY", "reason": "clear turn"}],
                    "trend_state": "DOWNTREND", "agrees_with_engine_state": False}
        else:
            data = {"zones": [{"approx_low": 101.0, "approx_high": 104.0, "kind": "SUPPLY", "reason": "overlaps an alive area"}],
                    "trend_state": "DOWNTREND"}
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(data))], stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))


def test_vision_not_visible_rule_and_info_only(monkeypatch):
    from decision3 import chart_reading_vision as CRV
    from opportunity_engine.visual_audit import auditor as AU
    df = pd.DataFrame({"timestamp": pd.date_range("2030-01-01 09:15", periods=30, freq="h"), "open": 100.0, "high": 130.0, "low": 90.0,
                       "close": 110.0})
    df["bar_end"] = df["timestamp"] + pd.Timedelta(hours=1)
    monkeypatch.setattr(CRV, "frame", lambda V, sym, tf, t: df)
    facts = {"t": 5, "big_picture": {"tfs": {"1H": {"state": "trending down", "trend": "DOWN"}}},
             "areas": {"alive": [area(1, lo=100, hi=106), area(2, lo=103, hi=108), area(3, lo=500, hi=520),     # #3 outside the window
                                 area(4, role="support", lo=91, hi=95)]}}
    used = []
    client = FakeClient()
    res = CRV.audit(client, AU.VisualAuditConfig(model="fake-model"), None, "NIFTY", facts, tfs=("1h",),
                    render_fn=lambda *a, **k: b"png", allow=lambda tf: (True, ""), on_usage=used.append)
    r = res[0]
    assert r["status"] == "ok" and r["not_visible"] == [3]
    assert {a["id"] for a in r["areas"]} == {1, 2, 4} and all(a["verdict"] == "SPURIOUS" for a in r["areas"])
    assert 3 not in {a["id"] for a in r["areas"]}                          # outside the window: never SPURIOUS
    sent = json.loads(client.calls[0]["messages"][-1]["content"][1]["text"].split("\n")[1])
    assert "A3" not in {x["label"] for x in sent}
    assert r["missing"] == [{"lo": 120.0, "hi": 125.0, "kind": "SUPPLY", "tf": "1h", "src": "overlay", "reason": "clear turn"}]
    assert r["duplicates"] == [{"tf": "1H", "kind": "supply", "ids": [1, 2]}]
    assert r["trend"]["agrees"] is False and r["structure"]["agrees"] is True and used
    s = CRV.summarise(res)
    assert s["counts"]["SPURIOUS"] == 3 and s["not_visible"] == [3]
    text, _ = CT.render(FACTS, "en", "full", vision=s)
    assert "Not visible on this chart: #3" in text and "Trend reading: differs" in text
    checks = CRV.reading_checks("NIFTY", res)
    assert any("concept C" in c for c in checks) and any("§1 MTF" in c for c in checks)


def test_vision_budget_refusal_skips_without_a_call(monkeypatch):
    from decision3 import chart_reading_vision as CRV
    from opportunity_engine.visual_audit import auditor as AU
    df = pd.DataFrame({"timestamp": pd.date_range("2030-01-01", periods=10, freq="h"), "open": 1.0, "high": 2.0, "low": 0.5,
                       "close": 1.5})
    monkeypatch.setattr(CRV, "frame", lambda *a: df)
    client = FakeClient()
    res = CRV.audit(client, AU.VisualAuditConfig(model="m"), None, "NIFTY", {"t": 1, "areas": {"alive": []}}, tfs=("1d", "1h"),
                    render_fn=lambda *a, **k: b"png", allow=lambda tf: (False, "cap"))
    assert not client.calls and all(r["status"] == "skipped" and r["why"] == "cap" for r in res)
    assert CRV.summarise(res)["status"] == "not_run"


def test_vision_off_by_setting_means_no_client():
    import importlib
    S = importlib.import_module("scripts.chart_reading_report")
    made = []
    out = S.vision_part(None, "NIFTY", {}, {"chart_reading_vision": "off"}, client_factory=lambda: made.append(1))
    assert out == (None, []) and not made


# ------------------------------------------------------------------------------------------------------------------- synthetic V22
def _m15(closes, start="2030-01-07", per_day=25, wick=1.0):
    rows, prev = [], closes[0]
    days = pd.bdate_range(start, periods=(len(closes) + per_day - 1) // per_day)
    for i, c in enumerate(closes):
        d = days[i // per_day]
        ts = d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * (i % per_day))
        rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": prev, "close": c,
                     "high": max(prev, c) + wick, "low": min(prev, c) - wick})
        prev = c
    return pd.DataFrame(rows)


def _ltf(m15):
    rows = []
    for r in m15.itertuples():
        mids = [r.open + k * (r.close - r.open) / 3 for k in range(4)]
        for k in range(3):
            ts = r.timestamp + pd.Timedelta(minutes=5 * k)
            a, b = mids[k], mids[k + 1]
            rows.append({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=5), "open": a, "close": b, "high": max(a, b) + 0.5,
                         "low": min(a, b) - 0.5})
    return pd.DataFrame(rows)


def _closes(n_legs=60):
    rng = np.random.default_rng(7)
    pts, x = [1000.0], 1000.0
    for k in range(n_legs):
        x += 120 if k % 2 == 0 else -70
        pts.append(x)
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        out += list(np.linspace(a, b, (8 if b > a else 24) + 1)[1:])
    return list(np.r_[pts[0], np.array(out)] + rng.normal(0, 0.6, len(out) + 1))


@pytest.fixture(scope="module")
def V():
    from decision3 import engine as E3
    m = _m15(_closes())
    return E3.V22(m, ltf=_ltf(m))


def test_collect_on_a_real_reader_and_render(V):
    from decision3 import chart_reading as CR
    f = CR.collect(V, symbol="TEST")
    for k in ("big_picture", "structure", "areas", "liquidity", "lines", "patterns", "volume", "rsi", "breakout_range", "wave", "plan"):
        assert k in f
    json.dumps(f)                                                          # JSON-safe (stored for the dashboard page)
    assert f["volume"]["missing"] is True                                  # no FUT bars given ⇒ said, never spot volume
    for lang in ("en", "mr"):
        text, meta = CT.render(f, lang, "full")
        assert CT.check(text) == [] and meta["length"] <= CT.TELEGRAM_LIMIT
    assert "FUT volume missing" in CT.render(f, "en", "full")[0]


def test_no_look_ahead_report_at_a_close_uses_bars_up_to_it(V):
    """The facts at a session's close on the full data = the facts on data cut at that close (and the cut drops later bars)."""
    import importlib
    from decision3 import chart_reading as CR
    from decision3 import engine as E3
    S = importlib.import_module("scripts.chart_reading_report")
    ts = pd.to_datetime(V.m15["timestamp"])
    fri = [i for i in range(len(ts) - 1) if ts.iloc[i].dayofweek == 4 and ts.iloc[i + 1].normalize() != ts.iloc[i].normalize()]
    t = fri[-2]
    close_at = pd.Timestamp(V.m15["bar_end"].iloc[t])
    m15_full = V.m15[["timestamp", "bar_end", "open", "high", "low", "close"]]
    ltf_full = _ltf(m15_full)
    m15c, m1c, dc, ltfc, futc = S.cut_inputs(m15_full, None, None, ltf_full, None, close_at)
    assert len(m15c) == t + 1 and (m15c["bar_end"] <= close_at).all() and (ltfc["bar_end"] <= close_at).all()
    V2 = E3.V22(m15c.reset_index(drop=True), ltf=ltfc)
    a, b = CR.collect(V, t, "TEST"), CR.collect(V2, None, "TEST")
    assert a["as_of"] == b["as_of"] == str(close_at)
    for k in ("big_picture", "structure", "liquidity", "patterns", "breakout_range", "wave"):
        assert a[k] == b[k], k
    assert [x["id"] for x in a["areas"]["alive"]] == [x["id"] for x in b["areas"]["alive"]]
    assert CT.render(a, "en", "full")[0] == CT.render(b, "en", "full")[0]


def test_charts_render_three_pngs_clean(V):
    from decision3 import chart_reading as CR
    from decision3 import chart_reading_charts as CC
    f = CR.collect(V, symbol="TEST")
    items, errs = CC.render(V, "TEST", f, cap=2)
    assert errs == [] and [n for n, *_ in items] == ["W+D", "1H", "15M"]
    for name, png, cap, meta in items:
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and "TEST" in cap and len(cap) <= 1024
        lv = meta["lines_view"]
        if lv["max_lines"] is not None:                                    # P8: the legend ≤ chart_max_lines, only shown lines
            assert len(lv["legend"]) <= lv["max_lines"] == 2 and set(lv["legend"]) <= set(lv["shown"])


def test_store_and_send_never_raise(tmp_path):
    import importlib
    S = importlib.import_module("scripts.chart_reading_report")
    rec = {"symbol": "TEST", "send": "a < b & c", "text": {}, "facts": {}}
    S.save("TEST", "close", rec, [("W+D", b"\x89PNG", "cap", {})], root=str(tmp_path))
    assert S.load_latest("TEST", "close", str(tmp_path))["send"] == "a < b & c"
    got = []
    assert S.send(rec, [("1H", b"png", "c", {})], send_text=lambda m: got.append(m) or True,
                  send_album=lambda items: got.append(items) or True)
    assert got[1] == "a &lt; b &amp; c"                                    # HTML-escaped for the Telegram parse mode
    assert S.send(rec, [], send_text=lambda m: (_ for _ in ()).throw(RuntimeError("net")), log=lambda *a: None) is False


def test_cron_installer_is_idempotent_and_reverts(tmp_path):
    import subprocess
    cron = tmp_path / "cron"
    cron.write_text("* * * * * python3 trade_monitor.py # exits\n")
    sh = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "install_chart_reading_schedule.sh"
    env = {"CRONTAB_FILE": str(cron), "REPO_DIR": "/root/Trade", "PATH": "/usr/bin:/bin"}
    for _ in range(2):
        subprocess.run(["bash", str(sh)], env=env, check=True, capture_output=True)
    txt = cron.read_text()
    assert txt.count("# chart-reading-close") == 1 and txt.count("# chart-reading-preopen") == 1 and "trade_monitor.py" in txt
    subprocess.run(["bash", str(sh), "--revert"], env=env, check=True, capture_output=True)
    assert "chart-reading" not in cron.read_text() and "trade_monitor.py" in cron.read_text()
