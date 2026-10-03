"""tests/test_dashboard_sr_v3_view.py -- Dashboard चार्टच्या "Bot view" dropdown मधला "SR Levels V3 (नवीन)" पर्याय.
निवडल्यावर आधीची सगळी drawings (जुना S/R तक्ता+रेषा, Supertrend, Hammer/Star मार्कर्स, bot ओळी) निघून फक्त V3 रेषा दिसाव्यात.
page_dashboard.py चा चार्ट-ब्लॉक (symbol/timeframe/Bot-view निवडीपासून tv_html पर्यंत) कृत्रिम candles सह AppTest मध्ये चालवतो."""
import json
import os
import re

from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = '''
import os, sys, textwrap
sys.path.insert(0, __ROOT__)
import numpy as np, pandas as pd
import streamlit as st
import page_dashboard as pdash

src = open(os.path.join(__ROOT__, "page_dashboard.py"), encoding="utf-8").read()
a = src.index("            # 🎓 \\"Timeframe + symbol switcher चार्टवर\\"")
b = src.index("            # 🎓 Live updates -- दर 3 सेकंदांनी शेवटची candle")
block = textwrap.dedent(src[a:b])

def market(days=10, seed=3):
    rng = np.random.default_rng(seed)
    stamps = []
    for d in pd.bdate_range("2026-09-01", periods=days):
        stamps += list(pd.date_range(d + pd.Timedelta(hours=9, minutes=15), periods=75, freq="5min"))
    n = len(stamps)
    close = 24100 + 100 * np.sin(np.arange(n) * 2 * np.pi / 150) + rng.normal(0, 3, n)
    open_ = np.concatenate([[close[0]], close[:-1]])
    f5 = pd.DataFrame({"timestamp": stamps, "open": open_, "high": np.maximum(open_, close) + 2,
                       "low": np.minimum(open_, close) - 2, "close": close, "volume": 1000, "oi": 0})
    def rs(rule):
        return f5.set_index("timestamp").resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "oi": "last"}).dropna(subset=["open"]).reset_index()
    daily = f5.assign(date=f5["timestamp"].dt.normalize()).groupby("date").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum"),
        oi=("oi", "last")).reset_index().rename(columns={"date": "timestamp"})
    return {"1minute": f5, "5minute": f5, "15minute": rs("15min"), "30minute": rs("30min"), "1hour": rs("1h"), "day": daily}

FRAMES = market()
_m = FRAMES["15minute"]
_i = len(_m) - 30
_c = float(_m.loc[_i, "close"])
_m.loc[_i, ["open", "high", "low", "close"]] = [_c - 0.5, _c + 1.0, _c - 60.0, _c + 0.8]      # मोठी खालची सावली = Hammer
calls = []
def fake_fetch(token, sym, spot, interval="30minute", lookback_days=None):
    calls.append(interval)
    if st.session_state.get("_fail_v3") and interval == "day":
        raise RuntimeError("boom")
    return FRAMES.get(interval, FRAMES["15minute"]).copy()

g = dict(vars(pdash))
g.update(st=st, pd=pd, symbol="NIFTY", timeframe_option="15minute", underlying_price=24100.0, token_input="tok",
         fetch_candles=fake_fetch, _CHART_LOOKBACK_DAYS={"15minute": 180})
g["df_candles"] = fake_fetch("tok", "NIFTY", 24100.0, "15minute"); calls.clear()
exec(block, g)
html = g["tv_html"]
st.session_state["html"] = html
st.session_state["note"] = g.get("bot_note")
st.session_state["fetches"] = list(calls)
'''


def _trade_lines(html):
    m = re.search(r"const tradeLines = (\[.*?\]);", html)
    return json.loads(m.group(1)) if m else []


def _segments(html):
    return [json.loads(m) for m in re.findall(r"addSupertrendSegments\((\[.*?\]), \d\);", html)]


def _run():
    at = AppTest.from_string(SCRIPT.replace("__ROOT__", repr(ROOT)), default_timeout=120)
    at.run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    return at


def _bot_view_box(at):
    return next(s for s in at.selectbox if s.label == "Bot view:")


def test_v3_is_in_the_dropdown_after_the_bots():
    at = _run()
    options = list(_bot_view_box(at).options)
    assert options[0] == "—" and options[-1].startswith("SR Levels V3") and "5M Instant" in options


def test_selecting_v3_removes_old_drawings_and_shows_only_v3_levels():
    at = _run()
    plain = at.session_state["html"]
    assert "Support / Resistance Levels" in plain, "डीफॉल्ट चार्टवर जुना S/R तक्ता असतो"
    assert "markerData = [];" not in plain and any(_segments(plain)), "डीफॉल्ट चार्टवर मार्कर्स आणि Supertrend असतात (तुलनेसाठी)"
    assert _trade_lines(plain) == []

    _bot_view_box(at).select(next(o for o in _bot_view_box(at).options if o.startswith("SR Levels V3"))).run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    html = at.session_state["html"]
    lines = _trade_lines(html)
    assert lines, at.session_state["note"]
    assert all(re.match(r"^[SRZ] [ABC]\d+", ln["title"]) for ln in lines), [ln["title"] for ln in lines]
    assert "Support / Resistance Levels" not in html, "जुना S/R तक्ता/रेषा निघाल्या पाहिजेत"
    assert "markerData = [];" in html and not any(_segments(html)), "Supertrend रेषा आणि Hammer/Star मार्कर्स निघाले पाहिजेत"
    note = at.session_state["note"]
    assert "फक्त" in note and "SR Levels V3" in note and "लोड करता आला नाही" not in note


def test_switching_back_to_none_restores_the_normal_chart():
    at = _run()
    box = _bot_view_box(at)
    box.select(next(o for o in box.options if o.startswith("SR Levels V3"))).run()
    assert _trade_lines(at.session_state["html"])
    _bot_view_box(at).select("—").run()
    html = at.session_state["html"]
    assert _trade_lines(html) == [] and "Support / Resistance Levels" in html


def test_v3_failure_shows_a_clear_note_and_a_clean_chart_instead_of_crashing():
    at = _run()
    at.session_state["_fail_v3"] = True
    box = _bot_view_box(at)
    box.select(next(o for o in box.options if o.startswith("SR Levels V3"))).run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    assert _trade_lines(at.session_state["html"]) == []
    assert "लोड करता आला नाही" in at.session_state["note"]


def test_other_bot_views_still_dispatch_to_the_bot_branch_not_v3():
    """V3 शाखा 'elif' ने वेगळी आहे -- जुन्या bot view ला (5M Instant) V3 रेषा/नोट येऊ नये (तिथे cloud_db नसल्याने साधा संदेश येतो)."""
    at = _run()
    _bot_view_box(at).select("5M Instant").run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    assert "SR Levels V3 निवडला आहे" not in (at.session_state["note"] or "")
