"""Vision v2.1 (signal_check_v2_1): gap संदर्भ (G0–G5, acceptance / rejection, fill, जुने gaps), line panel, today_role, L ची ओळ, room फक्त न
तुटलेले, derived invalidation, gap नियम, आणि तुम्हाला दाखवलेले 3 नमुने (2021 IS, repo मधला parquet)."""
import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

from tests.test_vision_v0 import GOOD
from vision import chart as CH
from vision import config as VC
from vision import context as CX
from vision import gap_context as GC
from vision import signal_audit as SA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def day_bars(day, o, path, n=375):
    """एका दिवसाचे 1m bars: path = [(minute index, price)] मधून linear."""
    idx = np.arange(n)
    xs, ys = zip(*path)
    c = np.interp(idx, xs, ys)
    op = np.r_[o, c[:-1]]
    t0 = pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=15)
    return pd.DataFrame({"timestamp": [t0 + pd.Timedelta(minutes=int(k)) for k in idx], "open": op,
                         "high": np.maximum(op, c) + 1, "low": np.minimum(op, c) - 1, "close": c})


def history(trend=+20.0, days=16, base=25000.0, start="2026-09-14"):
    out, p = [], base
    for d in pd.bdate_range(start, periods=days):
        out.append(day_bars(d, p, [(0, p), (374, p + trend)]))
        p += trend
    return pd.concat(out, ignore_index=True), p


# ------------------------------------------------------------------------------------------------ gap वर्ग / वर्तन
def test_gap_classes_synthetic():
    s = GC.DEFAULTS
    assert GC.classify(0.4, "inside", False, 0, s, "range") == "GX-inside"               # trend range / unclear ⇒ GX
    assert GC.classify(-0.9, "beyond", False, 0, s, "unclear") == "GX-beyond"
    assert GC.classify(0.1, "inside", True, 0, s) == "G0"
    assert GC.classify(0.4, "inside", False, 0, s) == "G1"
    assert GC.classify(0.4, "inside", True, 0, s) == "G2"
    assert GC.classify(0.4, "beyond", True, 0, s) == "G3"
    assert GC.classify(-0.4, "beyond", False, 0, s) == "G4"
    assert GC.classify(0.9, "beyond", True, 3.5, s) == "G5"
    assert GC.classify(0.9, "beyond", True, 1.0, s) == "G3"                       # leg ताणलेला नाही


def test_gap_up_with_trend_acceptance_and_fill_is_causal():
    h, p = history(+20.0)
    sig_day = pd.Timestamp("2026-10-06")
    today = day_bars(sig_day, p + 120, [(0, p + 120), (60, p + 160), (374, p + 200)])
    df = pd.concat([h, today], ignore_index=True)
    ts = sig_day + pd.Timedelta(hours=10, minutes=31)
    cut = CH.cut_1m(df, ts)
    g = GC.build(cut, ts, 10.0)
    assert g["class"] in ("G3", "G5") and g["direction"] == "up" and g["with_trend"] and g["location"] == "beyond"
    assert g["behaviour"] == "acceptance" and g["fill_pct"] < 5 and not g["pdc_acceptance"]
    fut = df.copy()
    fut.loc[fut.timestamp >= ts, "low"] -= 500                                 # भविष्यात gap पूर्ण भरला
    assert GC.build(CH.cut_1m(fut, ts), ts, 10.0) == g
    assert g["pdc"] == pytest.approx(float(h.close.iloc[-1]))                   # आधीचा पूर्ण दिवस
    early = sig_day + pd.Timedelta(hours=9, minutes=16)                         # 09:15 bar पूर्ण ⇒ open ठरला (पुढे बदलत नाही)
    g2 = GC.build(CH.cut_1m(df, early), early, 10.0)
    assert g2["open"] == g["open"] and g2["gap"] == g["gap"] and g2["behaviour"] == "undecided" and g2["bars_15m_done"] == 0
    mid = sig_day + pd.Timedelta(hours=9, minutes=15, seconds=30)               # opening bar चालू ⇒ आज अजून पूर्ण bar नाही ⇒ gap नाही
    assert GC.build(CH.cut_1m(df, mid), mid, 10.0)["has_gap"] is False


def test_gap_against_trend_rejection_and_pdc_acceptance():
    h, p = history(+20.0)
    sig_day = pd.Timestamp("2026-10-06")
    today = day_bars(sig_day, p - 120, [(0, p - 120), (20, p - 60), (45, p + 30), (374, p + 40)])
    df = pd.concat([h, today], ignore_index=True)
    ts = sig_day + pd.Timedelta(hours=11)
    g = GC.build(CH.cut_1m(df, ts), ts, 10.0)
    assert g["direction"] == "down" and not g["with_trend"] and g["class"] in ("G1", "G4")
    assert g["behaviour"] == "rejection" and g["fill_pct"] == 100 and g["pdc_touched"] and g["pdc_acceptance"]


def test_special_short_sessions_skipped_for_pdc():
    h, p = history(+20.0)
    muhurat = day_bars("2026-10-06", p + 500, [(0, p + 500), (59, p + 520)], n=60)        # signal दिवसाच्या आदल्या दिवशी लहान session
    df = pd.concat([h, muhurat, day_bars("2026-10-07", p, [(0, p), (374, p)])], ignore_index=True)
    ts = pd.Timestamp("2026-10-07 11:00")
    g = GC.build(CH.cut_1m(df, ts), ts, 10.0)
    assert g["pdc"] == pytest.approx(float(h.close.iloc[-1])) and abs(g["pdc"] - (p + 520)) > 100   # muhurat चा close नाही
    assert CX.prev_day(CH.cut_1m(df, ts), ts.normalize())["day"] == "2026-10-05"


def test_old_unfilled_gap_remaining_part():
    h, p = history(+20.0, days=8)
    d1 = day_bars("2026-09-24", p + 100, [(0, p + 100), (374, p + 130)])             # gap up 100, भरला नाही
    d2 = day_bars("2026-09-25", p + 130, [(0, p + 130), (200, p + 60), (374, p + 120)])  # अर्धवट भरला (खाली p+60 पर्यंत)
    df = pd.concat([h, d1, d2], ignore_index=True)
    ts = pd.Timestamp("2026-09-25 15:00")
    g = GC.build(CH.cut_1m(df, ts), ts, 10.0)
    ug = [u for u in g["old_gaps"] if u["day"] == "2026-09-24"]
    assert ug and ug[0]["low"] == pytest.approx(p, abs=1) and ug[0]["high"] == pytest.approx(p + 59, abs=2)


# ------------------------------------------------------------------------------------------------ today_role / L / room
def bars5(rows):
    t0 = pd.Timestamp("2026-10-06 09:15")
    return pd.DataFrame([{"start": t0 + pd.Timedelta(minutes=5 * k), "open": o, "high": hi, "low": lo, "close": c}
                         for k, (o, hi, lo, c) in enumerate(rows)])


def test_today_role_rules():
    up = bars5([(110, 112, 105, 108), (108, 109, 99, 103), (103, 106, 101, 105)])
    assert CX.today_role(up, 100, 1.0) == ("held_as_support", None)                    # वरून touch, close वर
    brk = bars5([(110, 112, 105, 108), (108, 109, 96, 97), (97, 99, 95, 96)])
    assert CX.today_role(brk, 100, 1.0)[0] == "broken_down"
    recl = bars5([(110, 112, 105, 108), (108, 109, 96, 97), (97, 99, 95, 96), (96, 104, 95, 103), (103, 106, 102, 105)])
    assert CX.today_role(recl, 100, 1.0)[0] == "reclaimed"                              # break नंतर पूर्ण bar परत उघडण्याच्या बाजूला
    already = bars5([(110, 112, 108, 111), (111, 115, 109, 114)])
    assert CX.today_role(already, 100, 1.0)[0] == "untested"                          # आधीपासून वर ⇒ "broken_up" नाही
    probe = bars5([(110, 112, 105, 108), (108, 109, 99.5, 99.6), (99.6, 103, 99, 102)])
    assert CX.today_role(probe, 100, 1.0)[0] == "held_as_support"                      # buffer पेक्षा कमी ⇒ break नाही


def test_user_rules_2a_2b_2c():
    """तुमचे deterministic नियम: 2a approach बाजू, 2b signal bar / मागच्या 3 bars मध्ये trade दिशेने real break ⇒ breakout, 2c bot-role वि. today_role."""
    a = SA.validate(GOOD)[0]
    base = {"time_flag": "none", "room": {"next_mr": 3.0}, "recent_breaks": []}
    ll = {"approach": "from above", "today_role": "held_as_support", "bot_role": "RESISTANCE"}
    ctx = {**base, "l_line": ll}
    d, _ = SA.rule_hits(a, ctx=ctx, direction="BEARISH")
    assert "wrong_approach" in d and "role_conflict" in d                                 # नमुना 2 सारखं
    ok = {**base, "l_line": {"approach": "from below", "today_role": "held_as_resistance", "bot_role": "RESISTANCE"}}
    assert SA.code_verdict(a, ctx=ok, direction="BEARISH") == "agree"
    bull_ok = {**base, "l_line": {"approach": "from above", "today_role": "held_as_support", "bot_role": "SUPPORT"}}
    assert SA.code_verdict(a, ctx=bull_ok, direction="BULLISH") == "agree"
    assert "wrong_approach" in SA.rule_hits(a, ctx={**base, "l_line": {**bull_ok["l_line"], "approach": "from below"}}, direction="BULLISH")[0]
    assert "role_conflict" in SA.rule_hits(a, ctx={**base, "l_line": {**bull_ok["l_line"], "today_role": "held_as_resistance"}},
                                           direction="BULLISH")[0]
    broke = {**ok, "recent_breaks": [{"name": "ORL", "at": "13:10"}]}
    b, ch = SA.apply_facts(a, broke, "BEARISH")
    assert b["is_breakout_entry"] == "yes" and "ORL 13:10" in ch[0] and SA.code_verdict(b, ctx=broke, direction="BEARISH") == "disagree"


def test_recent_breaks_ignore_reclaims_and_magnets():
    down = bars5([(110, 112, 105, 108), (108, 109, 104, 106), (106, 107, 97, 97.5), (97.5, 98, 96, 96.5)])
    assert CX.recent_breaks(down, 100, 1.0) == ("down", "09:25")                         # उघडण्याच्या बाजूपासून दूर
    recl = bars5([(95, 96, 93, 94), (94, 99, 93, 98), (98, 103, 97, 102.5), (102.5, 104, 101, 103)])
    assert CX.recent_breaks(recl, 100, 1.0)[0] == "up"                                   # खाली उघडला ⇒ वर break = दूर
    spring = bars5([(105, 106, 103, 104), (104, 104, 96, 97), (97, 103, 96, 102.5), (102.5, 104, 101, 103)])
    assert CX.recent_breaks(spring, 100, 1.0) == (None, None)                            # वर उघडला, खाली गेला, परत वर = reclaim
    chop = bars5([(101, 102, 98, 99), (99, 102, 98, 101), (101, 102, 98, 99), (99, 102, 98, 101), (101, 102, 98, 99)])
    assert CX.crossings(chop, 100) >= CX.MAGNET_CROSSES


# ------------------------------------------------------------------------------------------------ gap नियम
def gctx(**k):
    g = {"has_gap": True, "class": "G3", "direction": "up", "fill_pct": 5.0, "pdc": 25000.0, "edge": 25050.0, "pdc_acceptance": False,
         "behaviour": "acceptance", "bars_15m_done": 8, "event": None}
    g.update(k)
    return {"gap_ctx": g, "median_range": 10.0, "level": 25150.0, "time_flag": "none", "room": {"next_mr": 3.0}}


@pytest.mark.parametrize("ctx,direction,kind,rule", [
    (gctx(), "BULLISH", 0, "gap_chase"),
    (gctx(class_="G5"), "BULLISH", 0, "gap_chase"),
    (gctx(pdc_acceptance=True, fill_pct=100.0), "BULLISH", 0, "gap_b_pdc_accept"),
    (gctx(behaviour="undecided", bars_15m_done=3), "BEARISH", 1, "gap_undecided_early"),
    (gctx(event="RBI policy", class_="G0", has_gap=False), "BULLISH", 1, "event_day"),
])
def test_gap_code_rules(ctx, direction, kind, rule):
    if "class_" in ctx["gap_ctx"]:
        ctx["gap_ctx"]["class"] = ctx["gap_ctx"].pop("class_")
    a = SA.validate(GOOD)[0]
    hits = SA.rule_hits(a, ctx=ctx, direction=direction)
    assert rule in hits[kind]
    assert SA.code_verdict(a, ctx=ctx, direction=direction) == ("disagree" if kind == 0 else "gray")
    off = [r for r in VC.RULE_IDS["v2_disagree_rules" if kind == 0 else "v2_gray_rules"] if r != rule]
    kw = {"disagree_rules": off} if kind == 0 else {"gray_rules": off}
    assert rule not in SA.rule_hits(a, ctx=ctx, direction=direction, **kw)[kind]


def test_gap_pullback_to_edge_is_not_chase_and_model_gap_rules():
    a = SA.validate(GOOD)[0]
    near = gctx()
    near["level"] = 25052.0                                                              # gap edge जवळ (pullback)
    assert "gap_chase" not in SA.rule_hits(a, ctx=near, direction="BULLISH")[0]
    assert "gap_chase" not in SA.rule_hits(a, ctx=gctx(), direction="BEARISH")[0]        # gap विरुद्ध दिशा
    assert SA.code_verdict(SA.validate({**GOOD, "gap_setup": "disallowed"})[0]) == "disagree"
    assert SA.code_verdict(SA.validate({**GOOD, "line_vs_candles": "conflict"})[0]) == "gray"
    assert SA.code_verdict(SA.validate({**GOOD, "gap_setup": "C", "confluence": "no"})[0]) == "gray"
    assert SA.code_verdict(SA.validate({**GOOD, "gap_setup": "C", "confluence": "yes"})[0]) == "agree"


def test_event_days_setting():
    s = VC.validate("_global", {"event_days": "2026-10-09:RBI policy;2027-02-01:Budget"})
    assert s["event_days"] == ["2026-10-09:RBI policy", "2027-02-01:Budget"]
    with pytest.raises(ValueError):
        VC.validate("_global", {"event_days": ["9 Oct:RBI"]})


# ------------------------------------------------------------------------------------------------ chart v2.1 / तुमचे 3 नमुने
def _samples():
    spec = importlib.util.spec_from_file_location("vsamp21", os.path.join(ROOT, "scripts", "vision_v2_samples.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.historical()


@pytest.fixture(scope="module")
def samples():
    if not os.path.exists(os.path.join(ROOT, "data", "nifty50_1min.parquet")):
        pytest.skip("parquet नाही")
    out = []
    for sig, fr, daily in _samples():
        sig["ctx_settings"] = {**{k: VC.BOT_DEFAULTS[k] for k in VC.CTX_KEYS}, "events": {}}
        setup, higher, tfs, cut = CH.panels(fr, sig["signal_ts"], "5M", return_cut=True)
        out.append((sig, CX.build(cut, setup, sig, None, daily), cut, fr, daily))
    return out


def test_user_samples_code_facts(samples):
    """तुमचं वाचन: नमुना 2 = disagree (ORL तोडून breakdown विक्री, PDH वरून touch) — vision काहीही म्हणो, code ने. 1 आणि 3 vision वर (code
    त्यांना जबरदस्ती disagree करत नाही — नमुना 3 मध्ये PDL चा reclaim = spring, breakout नाही)."""
    good = SA.validate(GOOD)[0]
    got = []
    for sig, ctx, _, _, _ in samples:
        b, ch = SA.apply_facts(good, ctx, sig["direction"])
        got.append(SA.code_verdict(b, ctx=ctx, direction=sig["direction"]))
    assert got[1] == "disagree"
    assert samples[1][1]["l_line"]["approach"] == "from above" and samples[1][1]["gap_ctx"]["direction"] == "up"
    ll3 = samples[2][1]["l_line"]                                                          # 10:01: 10:00 चा reclaim bar अपूर्ण ⇒ break पूर्ण bars वरच
    assert ll3["today_role"] == "reclaimed" and ll3["broken_at"] == "09:55" and got[2] == "gray"   # नमुना 3: PDL reclaimed; bar बंद नाही ⇒ gray
    assert got[0] == "gray" and samples[0][1]["room"]["next_name"] == "PWL"                  # नमुना 1: PWL 0.30× वर ⇒ room tight (किमान gray)
    assert samples[1][1]["recent_breaks"] == [{"name": "ORL", "at": "13:10"}]                 # नमुना 2: ORL broken_down at 13:10 ⇒ breakout
    g2 = samples[1][1]["gap_ctx"]
    assert g2["behaviour"] == "acceptance" and any("acceptance" in h for h in g2["behaviour_history"])   # तुमचं अपेक्षित: acceptance
    assert samples[0][1]["gap_ctx"]["direction"] == "down"
    txt = SA.signal_text({**samples[1][0], "ctx": samples[1][1]})
    assert "L+PDH" in txt and "approached L from above" in txt and "today_role" in txt and "Gap today" in txt


def test_room_includes_flips_expected_values_and_invalidation_derived(samples):
    """तुमची अपेक्षा: नमुना 1 room = PWL 0.30x (tight), नमुना 3 room = PDC 1.89x (आज तुटलेला = flip, तरी room मध्ये)."""
    sig, ctx, _, _, _ = samples[0]
    assert ctx["room"]["next_name"] == "PWL" and ctx["room"]["next_mr"] == pytest.approx(0.30, abs=0.01)
    c3 = samples[2][1]
    assert c3["room"]["next_name"] == "PDC" and c3["room"]["next_mr"] == pytest.approx(1.89, abs=0.01) and c3["room"]["next_flip"]
    assert ctx["invalidation"] == pytest.approx(sig["level"] - 0.5 * ctx["median_range"]) and "derived" in ctx["invalidation_source"]


def test_line_panel_and_gap_context_truncated_at_signal(samples):
    sig, ctx, cut, fr, daily = samples[1]
    line = CH.line_frame(cut, 5)
    assert pd.to_datetime(line["start"]).max() < pd.Timestamp(sig["signal_ts"])
    assert pd.to_datetime(line["start"]).dt.normalize().nunique() == 5
    fut = fr.copy()
    fut.loc[fut.timestamp >= sig["signal_ts"], ["high", "low", "close"]] += 400
    s2, h2, t2, cut2 = CH.panels(fut, sig["signal_ts"], "5M", return_cut=True)
    assert CX.build(cut2, s2, sig, None, daily) == ctx
    assert CH.line_frame(cut2, 5).equals(line)


def test_v21_image_size_and_token_estimate(samples):
    sig, ctx, cut, fr, daily = samples[2]
    png, meta = CH.render(fr, sig, daily)
    if png is None:
        pytest.skip(f"kaleido नाही: {meta.get('error')}")
    from PIL import Image
    import io
    w, h = Image.open(io.BytesIO(png)).size
    assert (w, h) == (1000, 900) and w * h / 750 <= 1500                                  # image tokens ≈ w × h / 750
    setup, higher, tfs, cut2 = CH.panels(fr, sig["signal_ts"], "5M", return_cut=True)
    texts = [a.text for a in CH.build_figure(setup, higher, sig, tfs, meta["ctx"], CH.line_frame(cut2)).layout.annotations]
    assert any("reclaimed" in t for t in texts if t.startswith("<b>L"))                   # "PDL · reclaimed"
    assert any(t in ("sH", "sL") for t in texts) and "INV" in texts and not any(t in ("H", "L") for t in texts)


def test_gap_setup_letters_are_valid_not_unavailable():
    for x in ("A", "B", "C", "a", "none", "disallowed"):
        a, err = SA.validate({**GOOD, "gap_setup": x})
        assert err is None and a["gap_setup"] in ("A", "B", "C", "none", "disallowed")
    assert SA.validate({**GOOD, "gap_setup": "D"})[1]


def test_opening_behaviour_rejection_open_test_drive_and_history():
    o, pdc, pdh, pdl, buf = 25100.0, 25000.0, 25060.0, 24900.0, 2.0
    t0 = pd.Timestamp("2026-10-06 09:15")
    def m(rows):
        return pd.DataFrame([{"start": t0 + pd.Timedelta(minutes=15 * k), "open": a, "high": b, "low": c, "close": d} for k, (a, b, c, d) in enumerate(rows)])
    rej = m([(25100, 25110, 25080, 25090), (25090, 25095, 25050, 25060)])                 # नवीन high नाही, open खाली ⇒ rejection
    assert GC.opening_behaviour(rej, o, pdc, pdh, pdl, True, "beyond", buf)[0] == "rejection"
    otd = m([(25100, 25110, 25085, 25105), (25105, 25108, 25099, 25104), (25104, 25150, 25103, 25145)])   # open test, मग नवीन high + PDH वर
    st, at, hist = GC.opening_behaviour(otd, o, pdc, pdh, pdl, True, "beyond", buf)
    assert st == "acceptance" and at == "09:45" and hist[0] == "09:15 test" and "open-test-drive" in hist[-1]
    fail = m([(25100, 25110, 25085, 25105), (25104, 25150, 25103, 25145), (25145, 25146, 25080, 25085)])  # drive नंतर परत open खाली
    st, _, hist = GC.opening_behaviour(fail, o, pdc, pdh, pdl, True, "beyond", buf)
    assert st == "undecided" and "failed drive" in hist[-1]                                  # पहिल्या घटनेवर lock नाही


# ------------------------------------------------------------------------------------------------ round 3: bar close / reclaimed / pre-verdict
def test_signal_bar_open_vs_closed_and_text():
    sb = CX.signal_bar(pd.Timestamp("2021-07-12 13:11"), 5)
    assert (sb["start"], sb["closed"], sb["elapsed"]) == ("13:10", False, 1)
    assert CX.signal_bar(pd.Timestamp("2021-07-12 13:15"), 5)["closed"]                   # 13:14 minute पूर्ण ⇒ 13:10 चा bar बंद
    assert CX.signal_bar(pd.Timestamp("2021-07-12 13:11"), 5, pd.Timestamp("2021-07-12 13:15"))["closed"]


def test_open_bar_breaking_is_reported_not_counted_as_role(samples):
    """नमुना 2: ORL तक्त्यात held ... until 13:05; current open bar breaking it down — breakout ओळीशी विरोध नाही."""
    sig, ctx, _, _, _ = samples[1]
    orl = [r for r in ctx["levels"] if r["name"] == "ORL"][0]
    assert orl["open_bar_breaking"] == "down" and orl["held_until"] == "13:05" and not orl["today_role"].startswith("broken")
    txt = SA.signal_text({**sig, "ctx": ctx})
    assert "the current OPEN (unfinished) bar is breaking it down" in txt and "ORL at 13:10" in txt and "NOT CLOSED yet (1/5 min" in txt


def test_reclaimed_turns_off_role_conflict():
    a = SA.validate(GOOD)[0]
    ctx = {"time_flag": "none", "room": {"next_mr": 3.0}, "recent_breaks": [],
           "l_line": {"approach": "from above", "today_role": "reclaimed", "bot_role": "SUPPORT"}}
    assert "role_conflict" not in SA.rule_hits(a, ctx=ctx, direction="BULLISH")[0]
    held_r = {**ctx, "l_line": {**ctx["l_line"], "today_role": "held_as_resistance"}}
    assert "role_conflict" in SA.rule_hits(a, ctx=held_r, direction="BULLISH")[0]


def test_code_pre_verdicts_for_user_samples(samples):
    """तुमची अपेक्षा: 1 = gray (room tight / bar बंद नाही), 2 = disagree (breakout), 3 = vision ठरवेल — code floor gray (bar बंद नाही)."""
    out = [SA.pre_verdict(ctx, sig["direction"]) for sig, ctx, _, _, _ in samples]
    assert out[0][0] == "gray" and {"tight_room", "unclear"} <= set(out[0][1]["gray"])
    assert out[1][0] == "disagree" and {"breakout", "wrong_approach", "role_conflict"} <= set(out[1][1]["disagree"])
    assert out[2][0] == "gray" and out[2][1] == {"disagree": [], "gray": ["unclear"]}


def test_worker_waits_for_bar_close_then_cuts_chart_at_close(tmp_path, monkeypatch):
    """vision_wait_for_bar_close: bar बंद नसेल ⇒ row परत QUEUED (fetch / खर्च नाही); बंद झाल्यावर asof = bar close."""
    from vision import store as VS
    from vision import worker as VW
    monkeypatch.setattr(VW, "BAR_WAIT", True)
    row = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "notify", "signal_ts": pd.Timestamp("2026-10-06 10:31"),
           "direction": "BULLISH", "level": 25000.0, "role": "SUPPORT", "setup_tf": "5M", "spot": 25010.0, "algo_decision": "ENTER"}
    sid = VS.insert_signal(row)
    r = VS.claim_one(sid)
    monkeypatch.setattr(VS, "now_ist", lambda: pd.Timestamp("2026-10-06 10:33").to_pydatetime())
    fetched = []
    out = VW.process_row(r, fetch_fn=lambda s, d: fetched.append(1) or (None, None))
    assert out["deferred"] and VS.get_signal(sid)["status"] == "QUEUED" and not fetched
    seen = {}
    monkeypatch.setattr(VS, "now_ist", lambda: pd.Timestamp("2026-10-06 10:35:20").to_pydatetime())
    monkeypatch.setattr(CH, "render", lambda m1, s, d=None: (seen.update(asof=s.get("asof")), (None, {"error": "x"}))[1])
    VW.process_row(VS.claim_one(sid), fetch_fn=lambda s, d: (pd.DataFrame({"timestamp": [pd.Timestamp("2026-10-06 10:30")], "open": [1.0],
                                                                        "high": [1.0], "low": [1.0], "close": [1.0]}), None))
    assert str(seen["asof"]).startswith("2026-10-06 10:35")


def test_samples_bar_close_flow(capsys, tmp_path, monkeypatch):
    """तुमचे 3 नमुने live प्रमाणे (bar close नंतर + drift guard), vision शिवाय: 1 gray (room tight), 2 disagree (breakout, drift), 3 agree ⇒ vision ठरवेल."""
    if not os.path.exists(os.path.join(ROOT, "data", "nifty50_1min.parquet")):
        pytest.skip("parquet नाही")
    spec = importlib.util.spec_from_file_location("vsmoke21", os.path.join(ROOT, "scripts", "vision_v0_smoke.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--sample", "--bar-close", "--no-vision", "--no-telegram"]) == 0
    out = capsys.readouterr().out
    for hm in ("10:35", "13:15", "10:05"):
        assert f"evaluated at bar close {hm}" in out and f"drift guard @ {hm}" in out
    pv = [ln for ln in out.splitlines() if ln.startswith("--- code-only pre-verdict")]
    assert pv[0].split(": ")[1].startswith("gray") and "tight_room" in pv[0]
    assert pv[1].split(": ")[1].startswith("disagree") and "breakout" in pv[1]
    assert pv[2].split(": ")[1].startswith("agree")
    assert "drift guard @ 13:15" in out and "❌ drift" in out
