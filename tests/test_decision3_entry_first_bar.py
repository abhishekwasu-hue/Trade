"""Abhi (13 Oct) — decision3 V22:
  • R:R engine मधून काढला (`rr_step` default False): checklist मध्ये ⑦ नाही, engine SL / target / R:R output मध्ये नाहीत; setup निर्णय
    ⑥ (commitment + c1) वर संपतो. rr_step = True = जुना ⑦ (फक्त जुने reports / goldens).
  • `entry_first_bar` (default True): सत्राची पहिली 15M candle (09:15) स्वतः commitment / entry candle असू शकते (निर्णय bar_end 09:30 ला).
  • c1 (5M CHoCH by close) फक्त 09:30 पर्यंत बंद 5M bars + आदल्या दिवसाची 5M रचना वापरून 09:15 candle मध्येच पूर्ण होऊ शकतो.
  • Live: 09:15 candle चा setup (bar_end 09:30) engine_signal entry window मध्ये येतो.
आरसा (bull put / bear call) सगळीकडे.
"""
import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import method as M
from decision3 import settings as S3
from tests import oct12_fixture as F
from tests.ltf_fixtures import split_bars
from tests.test_decision3_method import NO_MATURE, _abc_m15

S_ROLE = {"level_death_side": "role"}
S_OLD = {**S_ROLE, "rr_step": True, "entry_first_bar": False}


def test_defaults():
    S = S3.load()
    assert S["rr_step"] is False and S["entry_first_bar"] is True


# ------------------------------------------------------------------------------------------------ R:R removed
@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put_mirror"])
def test_default_run_has_no_rr_step_and_no_engine_sl_target(mirror):
    m15, fut, ltf = F.build(mirror=mirror)
    V = E3.V22(m15, s=S_ROLE, ltf=ltf, futures=fut)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == last][:6]
    rows = [V.decide(t) for t in bars]
    st = [r for r in rows if r["decision"] == "setup"]
    assert st and st[0]["level"]["role"] == ("support" if mirror else "resistance")
    for r in rows:
        assert "⑦" not in r["checklist"] and r["risk"] is None
        assert "R:R" not in str(r.get("why") or "")
        for e in r["level_evals"]:
            assert not {"rr", "sl", "target", "entry"} & set(e)
    old = E3.V22(m15, s=S_OLD, ltf=ltf, futures=fut).decide(st[0]["bar"])
    assert old["decision"] == "setup" and old["risk"]["rr"] >= 3 and "⑦" in old["checklist"]   # legacy ⑦ अजून reproduce होतो


def test_removing_rr_step_only_adds_setups():
    """⑦ काढल्याने (09:15 नियम बंद ठेवून) जुना प्रत्येक setup setup च राहतो; फरक फक्त R:R ने अडलेले bars."""
    m15 = _abc_m15()
    old = E3.V22(m15, s={**NO_MATURE, "rr_step": True, "entry_first_bar": False}).run()
    new = E3.V22(m15, s={**NO_MATURE, "entry_first_bar": False}).run()
    so = {r["bar"] for r in old if r["decision"] == "setup"}
    sn = {r["bar"] for r in new if r["decision"] == "setup"}
    assert so and so <= sn
    assert all(r["decision"] != "no_trade" or "R:R" not in str(r.get("why") or "") for r in new)


# ------------------------------------------------------------------------------------------------ 09:15 = entry candle
def _A(rows):
    a = np.array(rows, float)
    return {"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}


@pytest.mark.parametrize("d", [M.DOWN, M.UP])
def test_first_bar_can_be_commitment_old_setting_keeps_window(d):
    """09:15 pin (level मध्ये spike, लांब wick, close आदल्या दिवसाच्या close पलीकडे परत) ⇒ default commitment; entry_first_bar False ⇒ जुनं."""
    base = [(100, 101, 99, 100.5), (100.5, 101.5, 100, 101), (101, 101.4, 100.6, 101.2)]          # आदला दिवस (close 101.2)
    if d == M.DOWN:
        first = (101.6, 104.5, 100.7, 100.9)                                     # gap-up spike, वरचा wick, close 101.2 खाली
        lvl = {"lo": 102.0, "hi": 105.0}
    else:
        first = (100.8, 101.7, 97.9, 101.5)                                      # gap-down spike, खालचा wick, close 101.2 वर
        lvl = {"lo": 97.5, "hi": 100.4}
    A = _A(base + [first])
    tss = np.array([pd.Timestamp("2030-01-07 14:45"), pd.Timestamp("2030-01-07 15:00"), pd.Timestamp("2030-01-07 15:15"),
                    pd.Timestamp("2030-01-08 09:15")], dtype="datetime64[ns]")
    S = S3.load()
    ok, why, cm = M.commitment(A, 3, d, lvl, S, tss)
    assert ok and cm["form"] == "pin", why
    assert M.commitment(A, 3, d, lvl, {**S, "entry_first_bar": False}, tss)[1] == "entry वेळ-खिडकीबाहेर"
    assert M.entry_open(S) == "09:15" and M.entry_open({**S, "entry_first_bar": False}) == "09:30"


def _variant(mirror, close_off):
    """oct12 fixture, शेवटच्या दिवसाचा 09:15 bar: spike +170, close = आदल्या close + close_off (आरसा ⇒ उलट)."""
    m15, fut, _ = F.build(mirror=mirror)
    ts = pd.to_datetime(m15["timestamp"])
    i0 = int(np.flatnonzero((ts.dt.normalize() == ts.dt.normalize().iloc[-1]).to_numpy())[0])
    c0 = float(m15["close"].iloc[i0 - 1])
    sg = -1.0 if mirror else 1.0
    o, ext, opp, c = c0 + sg * 40, c0 + sg * 170, c0 + sg * (min(close_off, 20) - 5), c0 + sg * close_off
    m15 = m15.copy()
    m15.loc[i0, ["open", "high", "low", "close"]] = [o, max(ext, opp), min(ext, opp), c]
    return m15, fut, split_bars(m15, 15, 3), i0


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put_mirror"])
def test_c1_can_complete_inside_the_0915_candle_with_5m_bars_closed_by_0930(mirror):
    d = M.UP if mirror else M.DOWN
    for close_off, done in ((-40, True), (20, False)):
        m15, fut, ltf, i0 = _variant(mirror, close_off)
        V = E3.V22(m15, s=S_ROLE, ltf=ltf, futures=fut)
        k = V.pb.at(i0, d)
        lvl = V.levels.active(i0, "UP" if mirror else "DOWN")[0]
        c0 = k["i_end_bar"] if k.get("i_end_bar") is not None else k["k_open_bar"]
        end = pd.Timestamp(V.bar_end[i0])
        assert end.strftime("%H:%M") == "09:30"
        ch = M.ltf_choch(V.ltf, d, pd.Timestamp(V._ts[int(c0)]), pd.Timestamp(V._ts[i0]), end, lvl=lvl)
        assert ch["done"] is done, ch["line"]
        if done:
            assert pd.Timestamp(ch["at"]) <= end and "CHoCH" in ch["line"]


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put_mirror"])
def test_0915_arrival_candle_reaches_c0_under_default(mirror):
    """09:15 = entry खिडकीत (default) ⇒ ⑥ commitment तपासला जातो; जुना नियम ⇒ "वेळ-खिडकी". नोंद (OPEN_QUESTIONS): 09:15 candle हीच area
    मधली पहिली (arrival) candle असेल तर c0 चा study window = ती candle स्वतः ⇒ body 1.0× ⇒ "dominant नाही" (c0 बदललेला नाही)."""
    m15, fut, ltf, i0 = _variant(mirror, -40)
    r = E3.V22(m15, s=S_ROLE, ltf=ltf, futures=fut).decide(i0)
    assert r["checklist"]["③"][0] is True
    assert "वेळ-खिडकी" not in r["checklist"]["⑥"][1] and "dominant नाही" in r["checklist"]["⑥"][1]
    r0 = E3.V22(m15, s=S_OLD, ltf=ltf, futures=fut).decide(i0)
    assert "वेळ-खिडकी" in r0["checklist"]["⑥"][1]


def test_live_window_accepts_the_0915_bar():
    """engine_signal store row चा bar_ts = bar_end (engine3_live.row_from_v22) ⇒ 09:15 candle = 09:30 ⇒ entry window मध्ये."""
    import engine3_live as L
    import engine_signal as ES
    assert ES.in_window("2030-03-04 09:30") and not ES.in_window("2030-03-04 09:15")
    r = {"bar_end": "2030-03-04 09:30:00", "decision": "setup", "level": {"role": "resistance", "lo": 1.0, "hi": 2.0},
         "checklist": {"①": [True, ""]}, "conviction": "B", "risk": None}
    row = L.row_from_v22("NIFTY", r, lambda: "2030-03-04 09:30:05")
    assert row["bar_ts"] == "2030-03-04 09:30:00" and ES.in_window(row["bar_ts"])
    assert row["entry"] is None and row["invalidation"] is None and row["target"] is None   # engine SL / target नाहीत


def test_replay_day_default_output_has_no_engine_rr_sl_target(tmp_path):
    """replay / approval संदेश (dry run, synthetic): default ⇒ engine R:R / SL / target नाहीत; --legacy-rr ⇒ जुनी ओळ परत."""
    import json
    from scripts import replay_day as RD
    out = tmp_path / "new.json"
    assert RD.main(["--date", "2030-03-04", "--synthetic", "--dry-run", "--json", str(out), "--out-dir", str(tmp_path)]) == 0
    j = json.loads(out.read_text(encoding="utf-8"))
    assert j["setup"]["side"] == "bear call" and not {"rr", "sl", "target", "entry"} & set(j["setup"])
    msg = j["approval"]["message"]
    assert "R:R" not in msg and "reward" not in msg.lower() and "Entry " not in msg      # engine SL / target / R:R ओळ नाही
    assert "SL / target / exits: bot चे नेहमीचे नियम" in msg                              # dashboard चे SL / target (आजसारखेच)
    assert all("⑦" not in b["checklist"] for b in j["bars"])
    old = tmp_path / "old.json"
    assert RD.main(["--date", "2030-03-04", "--synthetic", "--dry-run", "--json", str(old), "--out-dir", str(tmp_path),
                    "--legacy-rr", "--no-first-bar-entry"]) == 0
    jo = json.loads(old.read_text(encoding="utf-8"))
    assert jo["setup"]["rr"] >= 3 and "R:R" in jo["approval"]["message"]
