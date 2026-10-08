"""Chart Reader G-E1a — evidence score ⇒ A/B/C (Abhi ने मंजूर केलेले weights, 2026-10-08). Tuning नाही; फक्त settings."""
import pytest

from chart_reader import grade as G
from chart_reader import settings as CS

S = dict(CS.DEFAULTS)


def ev(**kw):
    base = {"side": 1, "htf": "up", "trend_strength": "strong", "at_range_edge": False, "elliott": "gray", "elliott_setup": None,
            "tier": None, "correction_weakening": 0.0, "area_quality": 0.0, "confluence_extra": 0, "reversal_s": 0.30, "gap": "neutral",
            "rr": 3.0, "event_day": False}
    base.update(kw)
    return base


def test_reversal_points_mapping():
    assert [G.rv_points(s) for s in (0.10, 0.20, 0.30, 0.45, 0.55, 0.60, 0.66, 0.80, 1.0)] == [-10, -5, 0, 7.5, 12.5, 15, 18, 25, 25]
    assert G.rv_points(None) == -10                                                       # reversal नाही ⇒ किमान
    assert G.reversal_label(0.62) == "strong" and G.reversal_label(0.5) == "medium" and G.reversal_label(0.4) == "weak"


def test_all_evidence_max_is_a_and_thresholds():
    r = G.score(ev(correction_weakening=1, area_quality=1, confluence_extra=3, reversal_s=0.9, gap="confirms", elliott="end",
                   rr=6), S)
    assert r["points"] == {"T": 15, "PB": 0, "CW": 15, "AQ": 20, "CF": 10, "LQ": 0, "RV": 25, "VL": 0, "DV": 0, "PT": 0, "GP": 10,
                           "EW": 10, "RM": 5, "TM": 0, "VX": 0, "EV": 0}
    assert r["total"] == 100 and r["grade"] == "A"                                        # 110 ⇒ 100 वर clip
    assert G.grade_of(60, S) == "A" and G.grade_of(59.9, S) == "B" and G.grade_of(45, S) == "B" and G.grade_of(44.9, S) == "C"
    assert all(line for line in r["lines"])                                               # प्रत्येक पुराव्याची ओळ


def test_counter_htf_without_elliott_takes_minus_20_but_is_not_a_gate():
    r = G.score(ev(side=-1, htf="up", correction_weakening=1, area_quality=1, confluence_extra=2, reversal_s=0.9, gap="confirms"), S)
    assert r["points"]["T"] == -20 and r["grade"] in ("A", "B", "C") and "counter" in r["lines"][0]


def test_c_wave_setups_off_by_default_and_exemption_only_when_on():
    """Abhi 2026-10-08 (दुसरी दुरुस्ती): मुख्य setup = pullback end. S6a / S13 (B-end → C) setting, default OFF ⇒ C."""
    assert S["c_wave_setups_enabled"] is False
    for code in ("S6a", "S13"):
        r = G.score(ev(side=1, htf="down", elliott="end", elliott_setup=code, tier="B", correction_weakening=1, area_quality=1,
                       confluence_extra=2, reversal_s=0.9), S)
        assert r["grade"] == "C" and r["size_mult"] == 0.0 and any("बंद" in x for x in r["lines"])
        on = {**S, "c_wave_setups_enabled": True}
        r = G.score(ev(side=1, htf="down", elliott="end", elliott_setup=code, tier="B", correction_weakening=0.5, area_quality=0.8,
                       reversal_s=0.7), on)
        assert r["points"]["T"] == 0 and r["size_mult"] == on["tier_mult"]["B"] == 0.5


def test_a3_vetoes_force_c_whatever_the_points():
    """KB A3: व्याख्यात्मक व्हेटो (count स्पष्ट A-end / B, origin acceptance, MAGNET, gap B pullback नाही) ⇒ C, गुण कितीही असोत."""
    best = dict(correction_weakening=1, area_quality=1, confluence_extra=2, reversal_s=0.9, elliott="end", gap="confirms")
    assert G.score(ev(**best), S)["grade"] == "A"
    r = G.score(ev(**best, vetoes=["⛔ [K5] MAGNET level X"]), S)
    assert r["grade"] == "C" and r["size_mult"] == 0.0 and r["total"] >= 60 and any("MAGNET" in x for x in r["lines"])


def test_counter_impulsive_is_pb_minus_10_evidence_not_a_forced_c():
    """KB भाग D: counter displacement / 5-wave counter-move ⇒ PB −10 (पुरावा). Entry point structure देत नाही (evaluate मध्ये)."""
    best = dict(correction_weakening=1, area_quality=1, confluence_extra=2, reversal_s=0.9, elliott="end", gap="confirms")
    r = G.score(ev(**best, pullback="reversal", reversal_reasons=["counter_move_impulsive"],
                   kb={"PB": {"pts": -10, "line": "PB -10 [K2]: धोक्याची चिन्हं"}}), S)
    assert r["points"]["PB"] == -10 and r["grade"] == "A" and not r["vetoes"]


def test_kb_points_are_clipped_to_part_d_ranges_and_lines_carry_chapter_tags():
    kb = {"PB": {"pts": 30}, "LQ": {"pts": 12}, "VL": {"pts": -9}, "DV": {"pts": 9}, "PT": {"pts": -20}, "TM": {"pts": 4}, "VX": {"pts": 7}}
    r = G.score(ev(kb=kb), S)
    assert {k: r["points"][k] for k in kb} == {"PB": 10, "LQ": 8, "VL": -5, "DV": 5, "PT": -10, "TM": 0, "VX": 2}
    assert [x.split()[0] for x in r["lines"][:16]] == list(G.KEYS)
    assert all("[K" in x or "[A3]" in x for x in r["lines"][:16])


def test_elliott_gray_a_end_is_points_only():
    r = G.score(ev(elliott="a_end_or_in_b", elliott_clear=False), S)
    assert r["points"]["EW"] == -15 and "gray" in r["lines"][11] and not r["vetoes"]


def test_elliott_a_end_or_inside_b_minus_15():
    assert G.score(ev(elliott="a_end_or_in_b"), S)["points"]["EW"] == -15
    assert G.score(ev(elliott="gray"), S)["points"]["EW"] == 0


def test_trend_weakening_range_edge_gap_event_rr():
    assert G.score(ev(trend_strength="weakening"), S)["points"]["T"] == 8
    assert G.score(ev(htf="range", at_range_edge=True), S)["points"]["T"] == 5
    assert G.score(ev(htf="range"), S)["points"]["T"] == 0
    assert G.score(ev(gap="opposes"), S)["points"]["GP"] == -10
    assert G.score(ev(event_day=True), S)["points"]["EV"] == -5
    assert G.score(ev(rr=5.0), S)["points"]["RM"] == 5 and G.score(ev(rr=4.9), S)["points"]["RM"] == 0


def test_size_full_for_with_trend_and_c_grade_none():
    r = G.score(ev(correction_weakening=1, area_quality=1, confluence_extra=2, reversal_s=0.8, elliott="end"), S)
    assert r["grade"] == "A" and r["size_mult"] == 1.0
    r = G.score(ev(reversal_s=0.2), S)
    assert r["grade"] == "C" and r["size_mult"] == 0.0


def test_settings_validation_rejects_bad_values():
    with pytest.raises(ValueError):
        CS.validate({**S, "grade_a_min": 40, "grade_b_min": 45})
    with pytest.raises(ValueError):
        CS.validate({**S, "tier_mult": {"A": 1.0, "B": 1.5, "C": 0.25}})                  # reduce-only: ≤ 1
    assert CS.validate(dict(S)) == S
