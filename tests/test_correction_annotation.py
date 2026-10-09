"""Correction Reader annotation (Abhi, annotation prompt §6): synthetic data फक्त, तारीख नाही. Pattern स्थिती (§4), रेघा, checklist box,
no-lookahead, खिडकी (impulse origin / शेवट), zones (≤ 4 / बाजू), caption मर्यादा, shadow (live signals तसेच), code मध्ये तारीख नाही."""
import json
import os
import re
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from correction import annotate as AN
from correction import reader as CR
from correction import settings as CRS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _base_day():
    """Synthetic data ची सुरुवात: आजपासून मागे, सोमवारी (कोणतीही ठरलेली तारीख नाही)."""
    b = pd.Timestamp.now().normalize() - pd.Timedelta(days=140)
    return b - pd.Timedelta(days=b.dayofweek)


def _m1(days=45, seed=3):
    """Trend खाली (मोठे displacement legs) + मधे corrections — 1m bars 09:15–15:29."""
    rng = np.random.default_rng(seed)
    rows, px = [], 24000.0
    drift = np.concatenate([np.full(8, -0.25), np.full(5, 0.12), np.full(6, -0.3), np.full(6, 0.15), np.full(8, -0.28), np.full(12, 0.10)])
    for k, d in enumerate(pd.bdate_range(_base_day(), periods=days)):
        mu = drift[min(k, len(drift) - 1)]
        for t in pd.date_range(d + pd.Timedelta(hours=9, minutes=15), d + pd.Timedelta(hours=15, minutes=29), freq="1min"):
            o = px
            px += mu + rng.normal(0, 2.2)
            rows.append((t, o, max(o, px) + abs(rng.normal(0, 0.8)), min(o, px) - abs(rng.normal(0, 0.8)), px))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).assign(volume=0.0)


@pytest.fixture(scope="module")
def m1():
    return _m1()


@pytest.fixture(scope="module")
def asof(m1):
    days = sorted(pd.to_datetime(m1["timestamp"]).dt.normalize().unique())
    return pd.Timestamp(days[-10]) + pd.Timedelta(hours=13, minutes=15)          # synthetic मध्ये इथे impulse + K hypotheses


@pytest.fixture(scope="module")
def R(m1, asof):
    return CR.read(m1, asof)


# ---------------------------------------------------------------------------------------------------------------- §4 स्थिती
def _node(pattern, wave, pts, tent=None, subtype=None):
    P = [NS(ts=pd.Timestamp(_base_day()) + pd.Timedelta(hours=10 + i), price=p, kind="H") for i, p in enumerate(pts)]
    T = None if tent is None else NS(ts=P[-1].ts + pd.Timedelta(hours=1), price=tent, kind="H")
    return NS(pattern=pattern, current_wave=wave, points=P, tentative=T, subtype=subtype or pattern, joint_score=0.5, invs=[])


@pytest.mark.parametrize("pattern,wave,pts,tent,fail,against,want", [
    ("zigzag", "C", [100, 140, 120], 150, False, None, "final_leg_present"),          # C ने A चं टोक ओलांडलं
    ("zigzag", "C", [100, 140, 120], 135, False, None, "final_leg_in_progress"),      # A चं टोक नाही, price failure नाही ⇒ थांबा
    ("zigzag", "C", [100, 140, 120], 135, True, None, "final_leg_short"),             # A चं टोक नाही, area वर failure ⇒ Gray-2
    ("zigzag", "C", [100, 140, 120], 150, False, True, "final_leg_in_progress"),      # lower degree: C चे 3 sub-legs, आता चौथा
    ("zigzag", "C", [100, 140, 120], 150, False, None, "final_leg_present"),          # lower degree अज्ञात ⇒ gate नाही
    ("flat", "B", [100, 140], 110, False, None, "forming_B"),
    ("zigzag", "A", [100], 130, False, None, "forming_A"),
    ("wxy", "X", [100, 140], 125, False, None, "in_X"),
    ("wxy", "Y", [100, 140, 120], 155, False, None, "final_leg_present"),
    ("triangle", "C", [100, 140, 110], 130, False, None, "in_triangle"),
    ("triangle", "E", [100, 140, 110, 132, 116], 125, False, None, "final_leg_present"),
    ("impulse", "5", [100, 120, 110, 140, 130], 150, False, None, "k_is_five"),
    ("impulse", "3", [100, 120, 110], 140, False, None, "forming_A"),
    ("lead_diag", "5", [100, 120, 110, 130, 125], 135, False, None, "forming_A"),
])
def test_pattern_state_order(pattern, wave, pts, tent, fail, against, want):
    n = _node(pattern, wave, pts, tent)
    labels = CR._labels(n)
    assert labels[-1]["tentative"] == (tent is not None) and labels[-1]["label"] == wave
    assert CR.hypothesis_state(n, labels, k_dir=1, area_failure=fail, against=against) == want


def test_pattern_lines_zigzag_triangle_flat():
    e = {"ts": str(_base_day() + pd.Timedelta(hours=9)), "price": 100.0}
    z = _node("zigzag", "C", [100, 140, 120], 150)
    names = [x["name"] for x in CR.pattern_lines(z, CR._labels(z), e)]
    assert any("A सुरुवात" in x for x in names) and any("समांतर" in x for x in names)
    t = _node("triangle", "E", [100, 140, 110, 132, 116], 125)
    names = [x["name"] for x in CR.pattern_lines(t, CR._labels(t), e)]
    assert "triangle A–C" in names and "triangle B–D" in names
    f = _node("flat", "C", [100, 140, 102], 145)
    assert sum(1 for x in CR.pattern_lines(f, CR._labels(f), e) if x.get("horizontal")) == 2


def test_lower_degree_against_needs_three_confirmed_sublegs():
    t0 = _base_day() + pd.Timedelta(hours=10)
    mk = lambda i, p, k: NS(ts=t0 + pd.Timedelta(minutes=15 * i), price=p, kind=k, confirmed_at=t0 + pd.Timedelta(minutes=15 * i + 30))  # noqa: E731
    md = {1: {"confirmed": [mk(1, 110, "H"), mk(2, 104, "L"), mk(3, 118, "H")]}, 2: {"confirmed": []}}
    asof = t0 + pd.Timedelta(hours=3)
    assert CR.lower_degree_against(md, 2, t0, 1, asof, price_now=112) is True             # तिसऱ्यानंतर उलट ⇒ C मध्यात
    assert CR.lower_degree_against(md, 2, t0, 1, asof, price_now=121) is False
    md2 = {1: {"confirmed": [mk(1, 110, "H"), mk(2, 104, "L")]}, 2: {"confirmed": []}}
    assert CR.lower_degree_against(md2, 2, t0, 1, asof, price_now=100) is None             # pivots पुरेसे नाहीत ⇒ अज्ञात
    assert CR.lower_degree_against(md, 0, t0, 1, asof, price_now=100) is None              # खालची degree नाही ⇒ अज्ञात


# ---------------------------------------------------------------------------------------------------------------- read()
def test_read_has_all_items_and_decision(R):
    assert set(R["items"]) == set(range(1, 13))
    assert R["decision"]["outcome"] in ("setup", "wait", "no_trade")
    for n, it in R["items"].items():
        assert it["status"] in ("✔", "✘", "–") and it["name"] == CR.ITEMS[n]
    g = R["decision"]["gate"]
    if R["decision"]["outcome"] == "no_trade" and g is not None:
        assert R["items"][g]["status"] == "✘" and R["items"][g]["gate"]
    if R["decision"]["outcome"] == "setup":
        assert all(R["items"][n]["status"] == "✔" for n in (5, 6, 7, 9, 10))


def test_prices_come_from_ohlc(m1, asof, R):
    _, fr = CR.frames(m1, asof)
    t15 = fr["15M"]
    assert R["risk"]["entry"] == round(float(t15["close"].iloc[-1]), 2) if R.get("risk") else True
    if R.get("K"):
        seg = t15[pd.to_datetime(t15["timestamp"]) > pd.Timestamp(R["impulse"]["I"]["to_ts"])]
        want = seg["high"].max() if R["K"]["dir"] > 0 else seg["low"].min()
        assert R["K"]["extreme"] == round(float(want), 2)


def test_no_lookahead_truncation(m1, asof, R):
    cut = m1[pd.to_datetime(m1["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
    R2 = CR.read(cut, asof)
    assert json.dumps(R, default=str, sort_keys=True) == json.dumps(R2, default=str, sort_keys=True)
    _, fr = CR.frames(m1, asof)
    for tf, f in fr.items():
        assert not len(f) or pd.Timestamp(f["bar_end"].max()) <= asof


def test_window_shows_impulse_origin_and_end(m1, asof, R):
    if not (R.get("impulse") or {}).get("I"):
        pytest.skip("synthetic data मध्ये impulse नाही")
    I = R["impulse"]["I"]
    _, fr = CR.frames(m1, asof)
    st = AN.window_start(R, R["ms_swings"])
    assert st <= pd.Timestamp(I["from_ts"])
    for tf in ("1H", "15M"):
        w = AN.window(fr[tf], tf, st)
        ts = pd.to_datetime(w["timestamp"])
        assert ts.iloc[0] <= pd.Timestamp(I["from_ts"]) and ts.iloc[-1] >= pd.Timestamp(I["to_ts"])


def test_zones_at_most_four_per_side_and_existing_at_decision(R):
    z = R["area"]["chart_zones"] if R.get("area") else []
    for side in ("sell", "buy"):
        assert sum(1 for x in z if x["side"] == side) <= CRS.DEFAULTS["annot_zones_per_side"]
    assert all(x["tool"] != "f" for x in z)                              # trendlines रेघ म्हणून वेगळ्या
    big = [{"id": str(i), "tool": "a", "side": "sell", "low": 100.0 + i, "high": 101.0 + i, "state": "ACTIVE", "quality": 0.5}
           for i in range(9)]
    assert len(CR.pick_zones(big, 100.0, 5.0, 4)) == 4


def test_caption_limits_and_no_code_keys(R):
    cap = AN.caption(3, 40, R)
    assert len(cap.encode("utf-16-le")) // 2 <= 1024 and len(cap.splitlines()) <= 8
    assert cap.startswith("🧭 ANNOTATION CHECK 3/40") and cap.endswith("Reply: ✔ बरोबर · ✘ कारण")
    for key in ("_", "{", "}", "no_trade", "final_leg", "outcome"):
        assert key not in cap


def test_checklist_box_and_charts_render(m1, asof, R):
    box = AN.checklist_box(R)
    for n in range(1, 13):
        assert f" {n}" in box
    assert "🎯" in box
    _, fr = CR.frames(m1, asof)
    p = AN.charts(fr, R, R["ms_swings"])
    assert set(p) == {"15M", "1H", "D", "W"} or set(p) >= {"15M", "1H"}
    assert all(b[:4] == b"\x89PNG" for b in p.values())
    assert AN.pdf_page(p, "t") is not None


def test_shadow_does_not_change_live_signal(m1, asof):
    from simple_core import engine as SE
    a = SE.signal_at(m1, asof)
    CR.read(m1, asof)
    b = SE.signal_at(m1, asof)
    keys = ("signal", "why", "pause_bars")
    assert json.dumps({k: a.get(k) for k in keys}, default=str, sort_keys=True) == json.dumps({k: b.get(k) for k in keys}, default=str,
                                                                                              sort_keys=True)
    for root, _, files in [w for pkg in ("simple_core", "market_state", "chart_reader", "vision", "elliott")
                           for w in os.walk(os.path.join(ROOT, pkg))]:
        for f in files:
            if f.endswith(".py"):
                assert "correction" not in re.findall(r"^\s*(?:from|import)\s+(\w+)", open(os.path.join(root, f), encoding="utf-8").read(), re.M)


def test_review_kind_annotation_check_is_not_measured():
    from backtest_review import store as BS
    assert "annotation_check" in BS.KINDS and "annotation_check" in BS.NOT_MEASURED


# ---------------------------------------------------------------------------------------------------------------- तारीख नाही
DATE_RX = [re.compile(r"\b(?:19|20)\d\d[-/.](?:0[1-9]|1[0-2])\b"),                     # वर्ष-महिना (पूर्ण तारीखही)
           re.compile(r"\b(?:19|20)\d\d(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\b"),      # 8 अंकी
           re.compile(r"\bdate(?:time)?\(\s*(?:19|20)\d\d\s*,"),                          # date(वर्ष, …)
           re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d\d\b"),
           re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b"),
           re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:0?[1-9]|[12]\d|3[01])\b")]


def test_no_date_literals_in_new_code():
    paths = [os.path.join(ROOT, "correction", f) for f in os.listdir(os.path.join(ROOT, "correction")) if f.endswith(".py")]
    paths += [os.path.join(ROOT, "scripts", "annotation_check.py"), os.path.abspath(__file__)]
    hits = []
    for p in paths:
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if any(rx.search(line) for rx in DATE_RX):
                hits.append(f"{os.path.basename(p)}:{i}: {line.strip()[:80]}")
    assert not hits, hits


def test_time_evidence_is_score_only():
    """§5 #1: t(C) > t(A) आणि t(C) ≤ t(A)+t(B) — पुरावा; स्थिती (gate) बदलत नाही."""
    t0 = _base_day() + pd.Timedelta(hours=9, minutes=15)
    fr = pd.DataFrame({"timestamp": pd.date_range(t0, periods=40, freq="15min")})
    ts = lambda k: str(fr["timestamp"].iloc[k])  # noqa: E731
    labels = [{"label": "A", "ts": ts(5), "price": 140}, {"label": "B", "ts": ts(12), "price": 120},
              {"label": "C", "ts": ts(30), "price": 150, "tentative": True}]
    tm = CR.time_evidence(fr, ts(0), labels, ts(30))
    assert (tm["t_A"], tm["t_B"], tm["t_C"]) == (5, 7, 18) and tm["C_gt_A"] and not tm["C_le_A_plus_B"] and tm["B_ge_A"]
    n = _node("zigzag", "C", [100, 140, 120], 150)
    assert CR.hypothesis_state(n, CR._labels(n), 1) == "final_leg_present"


def test_pdf_document_sent_once_and_not_a_review(tmp_path):
    from backtest_review import telegram as RT
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    sent = str(tmp_path / "sent.json")
    calls = []

    def call(method, data=None, files=None, timeout=60):
        calls.append(method)
        return {"ok": True, "result": {"message_id": 77}}
    creds = lambda: ("t", "c")  # noqa: E731
    assert RT.send_document(str(pdf), "cap", "annotation/x", call=call, creds=creds, sent=sent) == "sent"
    assert RT.send_document(str(pdf), "cap", "annotation/x", call=call, creds=creds, sent=sent) == "skipped"
    assert calls == ["sendDocument"]
    msg = {"reply_to_message": {"message_id": 77}, "text": "✔", "from": {"id": 1}, "chat": {"id": 1}}
    assert RT.handle_reply(msg, lambda f, c: True, save=lambda *a: True, sent=sent) == (False, "not_review")


# ---------------------------------------------------------------------------------------------------------------- futures volume (Abhi नियम 1, 2, 4)
def _fut(m1, roll_day_idx=None, price_shift=0.0):
    """Synthetic futures 5M: spot पेक्षा वेगळे भाव (premium), volume वेळेनुसार; roll_day_idx ⇒ त्या दिवसापासून नवा contract (जास्त volume)."""
    f = m1.set_index("timestamp").resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min",
                                                                                        "close": "last"}).dropna().reset_index()
    f[["open", "high", "low", "close"]] += 150.0 + price_shift
    days = sorted(f["timestamp"].dt.normalize().unique())
    rng = np.random.default_rng(1)
    f["volume"] = rng.integers(1000, 5000, len(f)).astype(float)
    f["contract"] = "NEAR"
    if roll_day_idx is not None:
        nxt = f.copy()
        nxt["contract"] = "NEXT"
        nxt["volume"] = np.where(nxt["timestamp"].dt.normalize() >= days[roll_day_idx - 1], nxt["volume"] * 3, nxt["volume"] * 0.1)
        f = pd.concat([f, nxt], ignore_index=True)
    return f


def test_futures_volume_joined_by_time_never_by_price(m1, asof):
    _, fr = CR.frames(m1, asof)
    a = CR.futures_volume(fr["15M"], _fut(m1), asof)
    b = CR.futures_volume(fr["15M"], _fut(m1, price_shift=900.0), asof)            # futures भाव बदलले तरी volume join तेच
    assert np.array_equal(np.nan_to_num(a[0]), np.nan_to_num(b[0]))
    t = pd.to_datetime(fr["15M"]["timestamp"]).iloc[-1]
    f = _fut(m1)
    want = f[(f["timestamp"] >= t) & (f["timestamp"] < t + pd.Timedelta(minutes=15))]["volume"].sum()
    assert a[0][-1] == want                                                          # spot bar च्या वेळेचे तीन 5M bars
    late = CR.futures_volume(fr["15M"], _fut(m1), asof - pd.Timedelta(minutes=15))
    assert not np.isfinite(late[0][-1])                                              # decision bar नंतरचा volume नाही


def test_rollover_day_marked_and_excluded(m1, asof, R):
    days = sorted(pd.to_datetime(m1["timestamp"]).dt.normalize().unique())
    k = [i for i, d in enumerate(days) if d <= pd.Timestamp(asof).normalize()][-1] - 2
    _, fr = CR.frames(m1, asof)
    fv = CR.futures_volume(fr["15M"], _fut(m1, roll_day_idx=k), asof)
    assert fv[2].any()                                                                # rollover दिवस खूण
    I = R["impulse"]["I"]
    vs = CR.volume_summary(fr["15M"], fv, I, None)
    vol, rel, roll = fv
    vol2 = vol.copy()
    vol2[roll] = 1e12                                                                 # rollover bars कितीही मोठे ⇒ सरासरी तीच
    assert CR.volume_summary(fr["15M"], (vol2, rel, roll), I, None)["correction_avg"] == vs["correction_avg"]
    assert vs["excluded_roll_bars"] >= 0


def test_noise_breaks_are_notes_only(m1, asof, R, monkeypatch):
    monkeypatch.setattr(CR, "noise_notes", lambda *a, **k: ["correction ची रेघ तुटली", "छोटा swing तुटला"])
    R2 = CR.read(m1, asof)
    assert R2["noise"] and R2["decision"] == R["decision"] and R2.get("grade") == R.get("grade")
    assert [it["status"] for it in R2["items"].values()] == [it["status"] for it in R["items"].values()]
    assert "noise" in AN.checklist_box(R2)


def test_volume_panel_and_box_line(m1, asof):
    R3 = CR.read(m1, asof, fut5=_fut(m1))
    assert R3["volume"]["available"] and R3["volume_series"]
    _, fr = CR.frames(m1, asof)
    f = AN.window(fr["15M"], "15M", AN.window_start(R3, R3["ms_swings"]))
    fig = AN.figure(f, "15M", R3, "t", m15_ts=pd.to_datetime(fr["15M"]["timestamp"]).to_numpy(dtype="datetime64[ns]"))
    assert any(getattr(t, "yaxis", None) == "y2" and t.type == "bar" for t in fig.data)
    assert "impulse" in AN.volume_line(R3) and "correction" in AN.volume_line(R3)
    assert "data नाही" in AN.volume_line(CR.read(m1, asof))


def test_pdf_network_error_is_not_resent(tmp_path):
    from backtest_review import telegram as RT
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    sent, calls = str(tmp_path / "sent.json"), []

    def call(method, data=None, files=None, timeout=60):
        calls.append(method)
        return None
    assert RT.send_document(str(pdf), "c", "annotation/x", call=call, creds=lambda: ("t", "c"), sent=sent).startswith("network")
    assert RT.send_document(str(pdf), "c", "annotation/x", call=call, creds=lambda: ("t", "c"), sent=sent) == "skipped"
    assert calls == ["sendDocument"]


def test_caption_has_no_code_pattern_names_and_short_data_is_safe(R):
    import copy
    for pat in ("end_diag", "lead_diag", "wxy", "impulse"):
        R2 = copy.deepcopy(R)
        R2.setdefault("pattern", {})["hypotheses"] = [{"pattern": pat, "labels": [{"label": "1", "price": 1.0, "ts": R["decision_bar"]}]}]
        cap = AN.caption(1, 2, R2)
        assert "_" not in cap and pat not in cap.replace("impulse (5)", "")
    short = {"decision_bar": None, "items": {}, "decision": {"outcome": "no_trade"}, "asof": R["asof"]}
    assert AN.charts({}, short) == {} and "data अपुरा" in AN.caption(1, 1, short)


def test_valid_trigger_not_blocked_by_earlier_too_early_composite(m1, asof, monkeypatch):
    """Review: एका zone चा composite entry_start आधी सुरू झाला, पण दुसरा trigger (sweep + reclaim) बरोबर ⇒ entry वेळ ✔."""
    from chart_reader import reversal as CRV
    from elliott import settings as ES
    _, fr = CR.frames(m1, asof)
    t = fr["15M"].copy()
    j = len(t) - 1
    k915 = max(i for i in range(j) if pd.Timestamp(t["timestamp"].iloc[i]).strftime("%H:%M") == "09:15")
    monkeypatch.setattr(CRV, "evaluate", lambda *a, **k: {"status": "ok", "n": j - k915 + 1, "label": "x"})   # 09:15 पासून ⇒ खूप लवकर
    lvl = float(t["high"].iloc[j]) - 0.5
    t.loc[t.index[j], "close"] = lvl - 5.0                                         # sweep: high पलीकडे, close परत खाली (bear)
    z = {"id": "SWH", "low": lvl - 1, "high": lvl + 1, "level": lvl}
    pf = CR.price_failure(t, -1, [z], [z], 5.0, dict(ES.DEFAULTS), 0.5, CRS.load(), "09:30")
    assert pf["ok"] and pf["type"] == "sweep + reclaim" and pf["start_ok"]


def test_beyond_origin_real_break_gates_item_4(m1, asof, monkeypatch):
    import market_state.core as MC
    monkeypatch.setattr(MC, "_real_break", lambda *a, **k: 3)
    R2 = CR.read(m1, asof, s={"depth_sweep_hi": -1.0})                           # "100% पलीकडे" कृत्रिम
    assert R2["items"][4]["status"] == "✘" and "real break" in R2["items"][4]["evidence"]
    assert R2["decision"]["outcome"] == "no_trade"
