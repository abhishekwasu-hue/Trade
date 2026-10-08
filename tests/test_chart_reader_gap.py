"""chart_reader/gap.py — K13 gap नियम (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §4, §4A, §8.1): synthetic, सर्वसाधारण (7 Oct वर tune नाही)."""
import pandas as pd

from chart_reader import gap as GP

MR = 2.0


def bars(rows, day="2026-03-10", start="09:15"):
    ts = pd.date_range(f"{day} {start}", periods=len(rows), freq="15min")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", ts)
    df["bar_end"] = ts + pd.Timedelta(minutes=15)
    return df


GAP_DOWN = {"has_gap": True, "direction": "down", "class": "G2", "open": 100.0, "pdc": 106.0, "gap_atr": -0.4, "location": "inside",
            "behaviour": "acceptance", "fill_pct": 0.0}


# ------------------------------------------------------------------ §8.1 gap chase: पहिला pullback नाही ⇒ entry नाही
def test_with_trade_gap_without_pullback_blocks_entry():
    t = bars([(100, 100.4, 98, 98.2), (98.2, 98.5, 96, 96.3), (96.3, 96.6, 94, 94.2)])       # सरळ घसरण
    r = GP.read(t, GAP_DOWN, -1, [], None, {}, MR)
    assert r["relation"] == "with" and r["block"] == "GAP_NO_PULLBACK" and r["gp"] == "neutral" and not r["pullback"]["seen"]


def test_g2_gap_is_included_not_only_g3_g5():
    t = bars([(100, 100.4, 98, 98.2), (98.2, 98.5, 96, 96.3)])
    for cls in ("G2", "G3", "G5", "GX-inside"):
        assert GP.read(t, {**GAP_DOWN, "class": cls}, -1, [], None, {}, MR)["block"] == "GAP_NO_PULLBACK"


def test_gap_fill_rally_to_open_is_first_pullback_setup_b():
    t = bars([(100, 100.4, 98, 98.2), (98.2, 98.5, 96, 96.3), (96.3, 99.9, 96.2, 99.5), (99.5, 99.8, 98.4, 98.6)])
    r = GP.read(t, GAP_DOWN, -1, [], None, {}, MR)
    assert r["block"] is None and r["setup"] == "B" and r["gp"] == "confirms"
    assert r["pullback"]["to"] == "gap edge (open)" and r["pullback"]["at"].endswith("09:45:00")


def test_pullback_to_selling_zone_below_open_counts():
    zone = {"id": "S1", "kind": "solid", "role": "RESISTANCE", "state": "ACTIVE", "low": 97.5, "high": 98.0}
    t = bars([(100, 100.2, 97, 97.2), (97.2, 97.3, 95, 95.2), (95.2, 97.4, 95.1, 97.1)])
    r = GP.read(t, GAP_DOWN, -1, [zone], None, {}, MR)
    assert r["pullback"]["seen"] and r["pullback"]["to"] == "S1"
    assert GP.read(t, GAP_DOWN, -1, [], None, {}, MR)["block"] == "GAP_NO_PULLBACK"     # zone नसेल ⇒ open पर्यंत आला नाही


def test_extreme_bar_itself_is_not_a_pullback():
    t = bars([(100, 100.1, 99, 99.2), (99.2, 101, 95, 95.5)])                           # एकाच bar मध्ये high आणि low — क्रम माहीत नाही
    assert not GP.read(t, GAP_DOWN, -1, [], None, {}, MR)["pullback"]["seen"]


def test_against_gap_rejection_is_setup_a_and_acceptance_opposes():
    t = bars([(100, 101, 99, 100.5)])
    a = GP.read(t, {**GAP_DOWN, "behaviour": "rejection"}, 1, [], None, {}, MR)
    assert a["relation"] == "against" and a["setup"] == "A" and a["gp"] == "confirms" and a["block"] is None
    assert GP.read(t, GAP_DOWN, 1, [], None, {}, MR)["gp"] == "opposes"


def test_old_gap_edge_active_area_is_setup_c():
    act = {"area": {"id": "GAP1", "tool": "l", "old": True}}
    assert GP.read(bars([(100, 101, 99, 100.5)]), {"has_gap": False}, -1, [], act, {}, MR)["setup"] == "C"


def test_story_weak_rally_then_gap_down_confirms_weakness():
    cl = [100 + 0.6 * i + (1.5 if i % 2 else -1.5) for i in range(8)]                    # चढती पण दोलायमान (overlapping) तेजी
    op = [100.0] + cl[:-1]
    prev = bars([(o, max(o, c) + 0.3, min(o, c) - 0.3, c) for o, c in zip(op, cl)], day="2026-03-09", start="13:30")
    st = GP.story(prev, GAP_DOWN, {}, MR)
    assert st["relation"] == "confirms" and "कमजोरीची पुष्टी" in st["line"]
    strong = bars([(100 + i, 101 + i, 99.9 + i, 101 + i) for i in range(8)], day="2026-03-09", start="13:30")
    assert GP.story(strong, GAP_DOWN, {}, MR)["relation"] == "opposes"


# ------------------------------------------------------------------ §4A G7 exhaustion gap reversal
G7GAP = {"has_gap": True, "direction": "down", "class": "G5", "open": 100.0, "pdc": 130.0, "gap_atr": -1.2, "location": "beyond",
         "behaviour": "undecided", "fill_pct": 0.0}
DEMAND = [{"id": "D3-S", "low": 96.0, "high": 99.0, "degree": 3, "state": "ACTIVE", "role": "SUPPORT", "tf": "1d"}]
G7_DAY = [(100, 100.5, 96.5, 99.5),       # zone मध्ये लांब lower wick
          (99.5, 101, 99, 100.8),         # नवा low नाही + open reclaim ⇒ rejection
          (100.8, 102, 100.5, 101.8),     # पहिली recovery candle — entry नाही
          (101.8, 102, 100.6, 100.9),     # पहिला pullback
          (100.9, 102.5, 100.7, 102.3)]   # reversal candle ⇒ entry


def test_g7_a_exhaustion_gap_rejection_pullback_entry():
    r = GP.g7(bars(G7_DAY), G7GAP, DEMAND, -1, {}, MR)
    assert r["state"] == "entry" and r["side"] == 1 and r["zone"]["id"] == "D3-S"
    assert r["inv"] == 96.0 and r["target"] == 130.0 and r["rr"] >= 3
    assert GP.g7(bars(G7_DAY[:3]), G7GAP, DEMAND, -1, {}, MR)["state"] == "rejected"         # पहिली recovery candle वर entry नाही


def test_g7_b_gap_accepted_no_entry():
    falling = [(100 - i, 100.2 - i, 98.6 - i, 98.8 - i) for i in range(6)]
    assert GP.g7(bars(falling), G7GAP, [{**DEMAND[0], "low": 90.0}], -1, {}, MR)["state"] == "watch"


def test_g7_c_no_major_zone_no_g7():
    assert GP.g7(bars(G7_DAY), G7GAP, [], -1, {}, MR)["state"] == "none"
    minor = [{**DEMAND[0], "degree": 1}]
    assert GP.g7(bars(G7_DAY), G7GAP, minor, -1, {}, MR)["state"] == "none"
    assert GP.g7(bars(G7_DAY), {**G7GAP, "class": "G2"}, DEMAND, -1, {}, MR)["state"] == "none"   # मोठा gap नाही


def test_g7_d_opening_window_no_entry_and_setting_off():
    r = GP.g7(bars(G7_DAY), G7GAP, DEMAND, -1, {}, MR, opening_end=pd.Timestamp("2026-03-10 10:30"))
    assert r["state"] != "entry"
    assert GP.g7(bars(G7_DAY), G7GAP, DEMAND, -1, {"gap_setup_g7": False}, MR)["state"] == "none"


def test_g7_day_extreme_broken_kills_setup():
    day = G7_DAY[:4] + [(100.9, 101, 95, 95.5)]
    assert GP.g7(bars(day), G7GAP, DEMAND, -1, {}, MR)["state"] == "none"
