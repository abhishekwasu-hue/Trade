"""tests/test_vision_story.py — R3 Chart Story (vision/story.py, scripts/golden_story_check.py). No network, no API, no key.

Synthetic 12-Oct-shaped fixture (tests/oct12_fixture.py, dates far from the holdout; anonymised with a short shift so the shifted dates
stay outside the sealed holdout too). The private golden data is used only by the last test (skipped cleanly when absent).
"""
import json
import os
import re
from types import SimpleNamespace

import pandas as pd
import pytest

from tests import oct12_fixture as F
from tests.ltf_fixtures import split_bars
from vision import config as VC
from vision import method_pack as MP
from vision import story as ST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANON = {"shift_weeks": 52, "scale": 0.731, "tick": 0.05}


def _bars():
    m15, fut, ltf = F.build()
    return {"15M": m15, "5M": ltf, "1m": split_bars(m15, 15, 15)}, fut


def _asof(m15, k=1):
    """Close of the k-th 15M bar of the last session (k = 1 ⇒ the 09:30 bar closes at 09:45)."""
    ts = pd.to_datetime(m15["timestamp"])
    last = ts.dt.normalize().iloc[-1]
    return pd.Timestamp(m15[ts.dt.normalize() == last]["bar_end"].iloc[k])


@pytest.fixture(scope="module")
def world():
    bars, fut = _bars()
    as_of = _asof(bars["15M"])
    prep = ST.prepare(bars, fut, as_of, "intraday", anon=ANON, render=True, hide=("NIFTY",))
    return bars, fut, as_of, prep


# ----------------------------------------------------------------------------------------------------------- a valid story
def _story(**over):
    pv = MP.load()[1]

    def part(**x):
        return {**x, "read": "Daily lower highs; the move into the zone is a correction.", "facts": ["trend.D2"]}
    d = {"pack_version": pv,
         "daily_trend": part(trend="DOWN", move="correction"),
         "zones": {"items": [{"zone": "16,457.00-16,500.00", "role": "supply", "state": "FLIPPED", "far_side_swing": "NA"}],
                   "read": "Z1 is a flipped supply zone.", "facts": ["zones.Z1"]},
         "structure": part(),
         "in_zone_study": part(selling_volume="expanding", buying_volume="contracting", growing_side="sellers"),
         "rsi_divergence": part(present="no"),
         "watch_next": part(watch="a close back above Z1", invalidation="close above 16,500.00"),
         "setup_read": part(decision="setup", side="bear", label=ST.SHADOW),
         "marathi": "Daily trend खाली.\nZ1 seller zone.\n" + ST.SHADOW}
    for k, v in over.items():
        d[k] = v
    return d


KNOWN = [16400.0, 16457.0, 16500.0, 16600.0]


def test_schema_accepts_a_valid_story_and_canonical_label():
    out, err = ST.validate(_story(), pack_version=MP.load()[1], known_prices=KNOWN, fact_keys={"trend", "zones"})
    assert err is None and out["setup_read"]["label"] == ST.SHADOW and out["marathi"].count("\n") == 2
    assert set(ST.SCHEMA["required"]) == {"pack_version", *ST.PARTS, "marathi"} and len(ST.PARTS) == 7
    assert "SHADOW — no trade; Abhi decides" in ST.SCHEMA_TEXT


@pytest.mark.parametrize("mut, why", [
    (lambda d: d.pop("structure"), "fields"),
    (lambda d: d.update(extra=1), "fields"),
    (lambda d: d["daily_trend"].update(trend="SIDEWAYS"), "invalid value"),
    (lambda d: d["zones"]["items"][0].update(state="DEAD-ish"), "invalid role / state"),
    (lambda d: d["rsi_divergence"].update(facts=[]), "cites no facts"),
    (lambda d: d["structure"].update(facts=["made_up.key"]), "unknown facts"),
    (lambda d: d["setup_read"].update(label="trade now"), "SHADOW"),
    (lambda d: d["setup_read"].update(side="none"), "without a side"),
    (lambda d: d.update(marathi="\n".join(f"ओळ {i}" for i in range(16))), "lines"),
    (lambda d: d.update(pack_version="abc"), "pack_version"),
])
def test_schema_rejects_bad_shapes(mut, why):
    d = _story()
    mut(d)
    out, err = ST.validate(d, pack_version=MP.load()[1], known_prices=None, fact_keys={"trend", "zones"})
    assert out is None and why in err


def test_price_validator_rejects_an_invented_price_anywhere_incl_devanagari_digits(caplog):
    out, err = ST.validate(_story(watch_next={"watch": "a retest of 16,480.00", "invalidation": "NA", "read": "x",
                                              "facts": ["zones.Z1"]}), known_prices=KNOWN, fact_keys={"trend", "zones"})
    assert out is None and "16,480.00" in err and "Chart Story rejected" in caplog.text
    out, err = ST.validate(_story(marathi="Z1 वर १६४८० ला विक्री.\n" + ST.SHADOW), known_prices=KNOWN, fact_keys={"trend", "zones"})
    assert out is None and "prices not in facts" in err
    ok, err = ST.validate(_story(marathi="Z1 वर १६४५७ ला विक्री.\n" + ST.SHADOW), known_prices=KNOWN, fact_keys={"trend", "zones"})
    assert err is None                                                         # देवनागरी अंक facts मध्ये असलेली किंमत ⇒ चालतो


def test_telegram_text_is_marathi_plus_shadow_line():
    out, _ = ST.validate(_story(marathi="एक ओळ"), fact_keys={"trend", "zones"})
    t = ST.telegram_text(out, title="x")
    assert t.splitlines()[-1] == ST.SHADOW and len(t.splitlines()) <= ST.MARATHI_MAX_LINES + 2


# ----------------------------------------------------------------------------------------------------------- prepare (facts / images)
def test_prepare_builds_facts_images_and_cited_keys(world):
    *_, prep = world
    f = prep["facts"]
    for k in ("meta", "trend", "zones", "abc", "in_zone", "divergence", "ohlc"):
        assert k in f, k
    assert [n for n, _ in prep["images"]] == ["15M", "1H", "D"] and all(p[:8] == b"\x89PNG\r\n\x1a\n" for _, p in prep["images"])
    assert "Read type: intraday" in prep["text"] and "ohlc.15M" in prep["text"]
    assert prep["known"] and prep["anchors"]
    json.dumps(f, allow_nan=False, default=str)
    flip = [z["abhi_flip_rule"] for k, z in f["zones"].items() if not k.startswith("_")]
    from decision3 import levels as LV
    if not hasattr(LV, "band_flip_facts"):                                     # main: Abhi's flip rule not in code ⇒ NA + reason
        assert flip and all(x["status"] == "NA" and x["reason"] for x in flip)


def test_anonymisation_hides_real_prices_dates_and_symbol(world):
    bars, _, as_of, prep = world
    assert prep["as_of"] == as_of - pd.Timedelta(days=7 * ANON["shift_weeks"])
    txt = prep["text"]
    assert str(as_of.date()) not in txt and "NIFTY" not in txt.upper()
    real = bars["15M"][pd.to_datetime(bars["15M"]["bar_end"]) <= as_of]
    hits = [x for x in real["close"].tail(40) if re.search(rf"(?<![\d.]){x:.2f}(?!\d)", txt)]
    assert not hits                                                            # real closes never appear (only scaled ones)
    sc = [round(round(x * ANON["scale"] / 0.05) * 0.05, 2) for x in real["close"].tail(5)]
    assert all(f"{x:.2f}" in txt for x in sc)


def test_leak_guard_refuses_a_prompt_with_the_symbol():
    bars, fut = _bars()
    with pytest.raises(ValueError, match="leaks"):
        ST.prepare(bars, fut, _asof(bars["15M"]), "intraday", anon=ANON, render=False, hide=("intraday",))


def test_no_lookahead_future_bars_do_not_change_facts(world):
    bars, fut, as_of, prep = world
    cut = {k: v[pd.to_datetime(v["bar_end"] if "bar_end" in v.columns else v["timestamp"]) <= as_of].reset_index(drop=True)
           if k != "1m" else v[pd.to_datetime(v["timestamp"]) + pd.Timedelta(minutes=1) <= as_of].reset_index(drop=True)
           for k, v in bars.items()}
    fcut = fut[pd.to_datetime(fut["timestamp"]) + pd.Timedelta(minutes=5) <= as_of]
    p2 = ST.prepare(cut, fcut, as_of, "intraday", anon=ANON, render=False)
    assert p2["text"] == prep["text"]
    a_asof = prep["as_of"]
    for tf, fr in prep["frames"].items():
        if fr is not None and len(fr):
            assert pd.to_datetime(fr["bar_end"]).max() <= a_asof, tf
    assert (pd.to_datetime(prep["fut"]["timestamp"]) + pd.Timedelta(minutes=5)).max() <= a_asof


# ----------------------------------------------------------------------------------------------------------- estimate / budget / models
def test_dry_run_estimate_counts_pack_schema_images_and_output():
    text, _ = MP.load()
    e = ST.estimate(3, "x" * 4000, text, None, 6000)
    assert e["system_tokens"] == MP.tokens_estimate(text) + MP.tokens_estimate(ST.SCHEMA_TEXT)
    assert e["fresh_input_tokens"] == 3 * 1600 + 1000 and e["max_output_tokens"] == 6000
    assert e["usd_cached"] < e["usd_uncached"] < e["usd_cache_write"]


def test_budget_sub_cap_refuses_and_allows():
    g = dict(VC.GLOBAL_DEFAULTS)
    assert g["story_daily_cap"] == 1.0
    today = pd.Timestamp("2030-03-04 09:00")
    ok, why = ST.budget_ok(0.10, g, {ST.TASK: (0.95, 0.95, 4)}, today)
    assert not ok and "Chart Story daily cap" in why
    ok, why = ST.budget_ok(0.10, g, {ST.TASK: (0.50, 0.50, 2)}, today)
    assert ok, why
    ok, why = ST.budget_ok(0.10, g, {ST.TASK: (0.0, 0.0, 0), "signal": (1.75, 1.75, 9)}, today)
    assert not ok and "Vision daily budget" in why                          # within the Vision total (signals reserve kept)
    with pytest.raises(ValueError):
        VC.validate("_global", {"story_daily_cap": 5.0})


def test_model_selection_by_role_from_settings_then_env(monkeypatch):
    for k in ("VISION_STORY_DEEP_MODEL", "VISION_STORY_LIGHT_MODEL", "VISION_SIGNAL_MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert ST.model_for("deep", {})[0] is None
    monkeypatch.setenv("VISION_SIGNAL_MODEL", "m-signal")
    assert ST.model_for("light", {}) == ("m-signal", "env VISION_SIGNAL_MODEL")
    assert ST.model_for("deep", {})[0] is None                                  # deep never falls back to another role's model
    monkeypatch.setenv("VISION_STORY_DEEP_MODEL", "m-deep-env")
    assert ST.model_for("deep", {}) == ("m-deep-env", "env VISION_STORY_DEEP_MODEL")
    g = VC.validate("_global", {"story_model_deep": " m-deep-setting "})
    assert ST.model_for("deep", g) == ("m-deep-setting", "setting _global.story_model_deep")
    assert [ST.role_of(r) for r in ST.READS] == ["deep", "light", "deep"] and ST.role_of("intraday", "deep") == "deep"


def test_no_model_id_literal_in_story_code():
    fam = "|".join(["op" + "us", "son" + "net", "hai" + "ku"])
    rx = re.compile(r"cl" + r"aude-[a-z0-9]|\b(" + fam + r")\b", re.I)
    for rel in ("vision/story.py", "scripts/golden_story_check.py", "docs/knowledge/method_pack.md"):
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert not rx.search(src), rel


def test_pack_has_the_chart_story_format_and_no_golden_expectations():
    text, _ = MP.load()
    assert "0b. Chart Story" in text and "SHADOW — no trade; Abhi decides" in text and "at most 15 lines" in text
    for part in ("Daily trend and degree", "Zones and their state", "Structure / projection", "In-zone study", "RSI divergence",
                 "What to watch next", "Setup read"):
        assert part in text, part
    for leak in ("22,544", "22,622", "22,721", "22,731", "22,760", "22,763", "22,809", "22,667"):
        assert leak not in text and leak not in ST.SCHEMA_TEXT, leak


# ----------------------------------------------------------------------------------------------------------- run (fake client)
class _Msg:
    def __init__(self, text, stop="end_turn"):
        self.stop_reason = stop
        self.content = [SimpleNamespace(type="text", text=text)]
        self.usage = SimpleNamespace(input_tokens=9000, output_tokens=2000, cache_read_input_tokens=9100, cache_creation_input_tokens=0)


class _Client:
    def __init__(self, text):
        self.messages = SimpleNamespace(create=lambda **kw: (self.calls.append(kw), _Msg(text))[1])
        self.calls = []


def _prep():
    return {"images": [("15M", b"png")], "text": "FACTS", "facts": {"trend": {}, "zones": {}}, "known": KNOWN,
            "anchors": [16400.0, 16600.0]}


def test_run_done_logs_cached_and_uncached_usage():
    seen = []
    c = _Client(json.dumps(_story(), ensure_ascii=False))
    res = ST.run(c, _prep(), "m-test", on_usage=lambda u, cost: seen.append((u, cost)))
    assert res["status"] == "done" and res["task"] == ST.TASK and seen and seen[0][0]["cache_read"] == 9100
    kw = c.calls[0]
    assert kw["system"][-1]["cache_control"]["type"] == "ephemeral" and kw["system"][-1]["text"] == ST.SCHEMA_TEXT
    assert kw["output_config"]["format"]["schema"] is ST.SCHEMA
    assert "cache read 9,100" in ST.cost_line(res)


def test_run_rejects_and_keeps_raw_text_never_silently_accepts():
    bad = _story(structure={"read": "c = a at 16,999.00", "facts": ["trend.D1"]})
    res = ST.run(_Client(json.dumps(bad, ensure_ascii=False)), _prep(), "m-test")
    assert res["status"] == "rejected" and "16,999.00" in res["error"] and res["raw_text"] and res["data"] is None


# ----------------------------------------------------------------------------------------------------------- golden runner
def test_golden_runner_dry_run_calls_nothing_and_keeps_expectations_out_of_the_prompt(tmp_path, monkeypatch):
    import scripts.golden_story_check as G
    seen = {}
    case = {"id": "c1", "status": "x", "symbol": "NIFTY", "as_of": "2030-03-04 09:45", "read": "eod", "role": "deep",
            "data": {"spot_1m": ["a"]}, "notes": "SENTINEL_NOTE", "checks": [{"id": "k", "what": "SENTINEL_CHECK", "kind": "manual"}]}
    (tmp_path / "cases.json").write_text(json.dumps({"cases": [case]}), encoding="utf-8")

    def load(c, td):
        seen["case"] = c
        return {}, None, None

    def prepare(bars, fut, as_of, read, **kw):
        seen["prep_kw"] = kw
        return {"images": [("15M", b"\x89PNG")], "text": "FACTS " + json.dumps(seen["case"]), "facts": {"meta": {"last_closed_15m_bar": "t"}},
                "known": [], "anchors": [], "as_of": as_of}

    def boom():
        raise AssertionError("no API call in a dry run")
    lines = []
    rc = G.main(["--dry-run", "--cases", str(tmp_path / "cases.json"), "--out-dir", str(tmp_path / "out")],
                deps={"load": load, "prepare": prepare, "client": boom, "guard": lambda t: None}, out=lines.append)
    assert rc == 0
    assert set(seen["case"]) <= set(G.CASE_KEYS) and "SENTINEL" not in json.dumps(seen["case"])
    prompt = (tmp_path / "out" / "c1" / "prompt_user.txt").read_text(encoding="utf-8")
    assert "SENTINEL" not in prompt
    out = "\n".join(lines)
    assert "DRY_RUN" in out and "PROVISIONAL" in out and "cost est." in out and "REVIEW" in out
    assert (tmp_path / "out" / "c1" / "input_15M.png").exists() and json.load(open(tmp_path / "out" / "summary.json"))[0]["label"] == "PROVISIONAL"


def test_golden_runner_refuses_over_the_sub_cap(tmp_path, monkeypatch):
    import scripts.golden_story_check as G
    a = SimpleNamespace(model="m", max_tokens=6000, out_dir=str(tmp_path), dry_run=False, shift_weeks=52, scale=0.731, tick=0.05)
    case = {"id": "c1", "symbol": "NIFTY", "as_of": "2030-03-04 09:45", "read": "eod", "data": {}}
    deps = {"guard": lambda t: None, "load": lambda c, td: ({}, None, None), "pack": MP.load,
            "prepare": lambda *x, **k: {"images": [("15M", b"p")], "text": "x" * 40000, "facts": {"meta": {"last_closed_15m_bar": "t"}},
                                        "known": [], "anchors": [], "as_of": pd.Timestamp("2030-03-04")},
            "client": lambda: (_ for _ in ()).throw(AssertionError("no call over the cap"))}
    state = {"g": dict(VC.GLOBAL_DEFAULTS), "by_task": {ST.TASK: (0.99, 0.99, 3)}, "today": pd.Timestamp("2030-03-04 10:00")}
    rec = G.run_case(case, a, deps, state, str(tmp_path))
    assert rec["status"] == "NOT_RUN_BUDGET" and "Chart Story daily cap" in rec["why"]


def test_golden_compare_maps_anonymised_prices_back():
    import scripts.golden_story_check as G
    sc = 0.731
    d = _story(zones={"items": [{"zone": f"{22534.4 * sc:,.2f}-{22574.25 * sc:,.2f}", "role": "supply", "state": "BROKEN",
                                 "far_side_swing": f"{22731.85 * sc:,.2f}"}], "read": "x", "facts": ["zones.Z1"]})
    case = {"price_tol": 15.0, "checks": [
        {"id": "z", "kind": "zone", "state": "BROKEN", "role": "supply", "range": [22544.0, 22622.0]},
        {"id": "p", "kind": "price", "values": [22731.8], "where": ["zones"]},
        {"id": "nb", "kind": "not_setup", "side": "bear"},
        {"id": "f", "kind": "field", "path": "daily_trend.trend", "in": ["DOWN"]},
        {"id": "m", "kind": "manual"}]}
    marks = {r["id"]: r["mark"] for r in G.compare(d, case, sc)}
    assert marks == {"z": "✔", "p": "✔", "nb": "✘", "f": "✔", "m": "REVIEW"}
    assert all(r["label"] == "PROVISIONAL" for r in G.compare(None, case, sc))


# ----------------------------------------------------------------------------------------------------------- private golden data (skip in CI)
TD = os.environ.get("TRADE_DATA", "/home/user/trade-data")
CASES = os.path.join(TD, "golden_story", "cases.json")


@pytest.mark.skipif(not os.path.exists(CASES), reason="private trade-data not present")
def test_golden_12_oct_uses_only_data_up_to_0945():
    import scripts.golden_story_check as G
    case = next(c for c in json.load(open(CASES, encoding="utf-8"))["cases"] if c["id"].startswith("nifty_2026-10-12"))
    bars, fut, _ = G.load_case(case, TD)
    as_of = pd.Timestamp(case["as_of"])
    frames, f = ST._cut_frames(bars, ST._fut_near_month(fut), as_of)
    for tf, fr in frames.items():
        if fr is not None and len(fr):
            assert pd.to_datetime(fr["bar_end"]).max() <= as_of, tf
    assert str(frames["15M"]["timestamp"].iloc[-1]) == "2026-10-12 09:30:00"
    assert (pd.to_datetime(f["timestamp"]) + pd.Timedelta(minutes=5)).max() <= as_of


@pytest.mark.skipif(not os.path.exists(CASES), reason="private trade-data not present")
def test_golden_12_oct_rsi_divergence_needs_1m_order_and_3_bar_minimum():
    """#325 / RSI-2: with the 1m intrabar order the 12 Oct 09:15 spike is a D0 pivot; with the 3-bar minimum the pair
    9 Oct 14:15 (22,580.75, RSI 67.09) → 12 Oct 09:15 (22,651.10, RSI 66.41) is a regular bear divergence (confirmed by 09:45)."""
    import scripts.golden_story_check as G
    from rsi2 import settings as RS
    case = next(c for c in json.load(open(CASES, encoding="utf-8"))["cases"] if c["id"].startswith("nifty_2026-10-12"))
    bars, fut, _ = G.load_case(case, TD)
    fr, _ = ST._cut_frames(bars, ST._fut_near_month(fut), pd.Timestamp(case["as_of"]))
    s3 = {"div_bars": {**RS.DEFAULTS["div_bars"], "15M": (3, 50)}}
    d, _ = ST.divergence_facts(fr["15M"], df1m=fr["1m"], s=s3)
    hit = [x for x in d["divergences_now"] if x["side"] == "bear" and x["type"] == "regular" and x["degree"] == 0]
    assert hit and hit[0]["status"] == "confirmed" and hit[0]["bars_apart"] == 4
    assert (hit[0]["pivot1"]["time"], hit[0]["pivot1"]["price"], hit[0]["pivot1"]["rsi"]) == ("2026-10-09 14:15:00", 22580.75, 67.09)
    assert (hit[0]["pivot2"]["time"], hit[0]["pivot2"]["price"], hit[0]["pivot2"]["rsi"]) == ("2026-10-12 09:15:00", 22651.1, 66.41)
    d0, _ = ST.divergence_facts(fr["15M"], df1m=None, s=s3)                   # without the 1m order the spike is no D0 pivot
    assert not [x for x in d0["divergences_now"] if x["side"] == "bear" and x["degree"] == 0]


@pytest.mark.skipif(not os.path.exists(CASES), reason="private trade-data not present")
def test_golden_13_oct_uses_decision3_cas_policy():
    """ST-4: closing-auction bars dropped (decision3 / market_state policy) ⇒ 13 Oct spot high 22,719.25, not the CAS 22,721.95."""
    import scripts.golden_story_check as G
    case = next(c for c in json.load(open(CASES, encoding="utf-8"))["cases"] if c["id"].startswith("nifty_2026-10-13"))
    bars, fut, _ = G.load_case(case, TD)
    fr, _ = ST._cut_frames(bars, ST._fut_near_month(fut), pd.Timestamp(case["as_of"]))
    day = fr["15M"][pd.to_datetime(fr["15M"]["timestamp"]).dt.normalize() == pd.Timestamp("2026-10-13")]
    assert float(day["high"].max()) == 22719.25 and str(day["timestamp"].iloc[-1]) == "2026-10-13 15:00:00"
    assert float(fr["D"]["high"].iloc[-1]) == 22719.25


def test_divergence_gets_the_1m_order_rows(monkeypatch):
    from rsi2 import engine as RE
    seen = {}

    class Fake:
        def __init__(self, df, tf, s=None, df1m=None, **kw):
            seen.update(tf=tf, s=s, n1m=None if df1m is None else len(df1m))

        def read(self, t=None):
            return {"rsi": 50.0, "latest": [], "divergences": []}
    monkeypatch.setattr(RE, "Divergence", Fake)
    bars, _ = _bars()
    d, _ = ST.divergence_facts(bars["15M"], df1m=bars["1m"], s={"div_bars": {"15M": (3, 50)}})
    assert seen == {"tf": "15M", "s": {"div_bars": {"15M": (3, 50)}}, "n1m": len(bars["1m"])} and d["divergences_now"] == []


def test_zone_flip_facts_from_band_owner_function_or_na(monkeypatch):
    from decision3 import levels as LV
    band = {"lo": 1.0, "hi": 2.0, "breaks": [{"bar": 3, "dir": "up"}], "flip_state": "BROKEN", "broken_at": {"bar": 3},
            "far_swing": {"price": 2.5}, "flipped_at": None}
    x = ST.zone_flip_facts(band, None, -1)
    assert x["status"] == "OK" and x["flip_state"] == "BROKEN" and x["far_swing"] == {"price": 2.5}   # #325: find_bands adds it
    plain = {k: v for k, v in band.items() if k not in ST.FLIP_KEYS}
    monkeypatch.delattr(LV, "band_flip_facts", raising=False)
    assert ST.zone_flip_facts(plain, pd.DataFrame({"x": [1]}), 0)["status"] == "NA"
    monkeypatch.setattr(LV, "band_flip_facts", lambda df, t, b, s=None, start=None: {"flip_state": "FLIPPED", "far_swing": {"price": 2.5},
                                                                                    "broken_at": None, "flipped_at": {"bar": 5}}, raising=False)
    y = ST.zone_flip_facts(plain, pd.DataFrame({"x": [1]}), 0, "1H")
    assert y["status"] == "OK" and y["flip_state"] == "FLIPPED" and y["owner"] == "decision3.levels.band_flip_facts"
