"""Layer 6b (Abhi's method, docs/knowledge/CHART_READER_METHOD.md §5 / P8): the OUTPUT reads the same method as the decision.

Every change to what the LIVE Vision card / Telegram / pre-open text shows sits behind a display setting whose default = today's output
(decision3/settings.py OUTPUT); the live-switch track wires them to the dashboard. Synthetic data only, no network, no AI."""
import json

import pytest

from decision3 import settings as S3
from paper import engine_entry as EE


def test_output_settings_registered_with_todays_default():
    from bots_common import plain_text as PT
    from vision import config as VCF
    assert set(S3.OUTPUT) == {"approval_band_warn_rule", "vision_chart_band_finder", "vision_volume_words"}
    for k, (default, options, where) in S3.OUTPUT.items():
        assert S3.REGISTER[k][0] == default and S3.REGISTER[k][2] == "setting" and default == options[0] and where, k
        assert S3.REGISTER[k][1] == " / ".join(options), k
    assert PT.band_warn_rule(None) == S3.OUTPUT["approval_band_warn_rule"][0]
    for k in ("vision_chart_band_finder", "vision_volume_words"):
        assert VCF.BOT_DEFAULTS[k] == S3.OUTPUT[k][0] and tuple(VCF.ENUMS[k]) == S3.OUTPUT[k][1] and k in VCF.CTX_KEYS
        with pytest.raises(ValueError):
            VCF.validate("srv2_momentum_reversal", {k: "sigma"})
    assert not set(S3.OUTPUT) & set(S3.DEFAULTS)                                 # display only: never a reading setting


def _payload():
    return {"engine": "decision3", "trend_used": "DOWN",
            "level": {"id": 7, "tf": "1H", "role": "resistance", "lo": 22600.0, "hi": 22650.0, "state": "FLIPPED",
                      "confluence_label": "confluence: line (touch 3)", "births": ["a:D2"]},
            "watch_list": [{"id": 7, "tf": "1H", "role": "resistance", "lo": 22600.0, "hi": 22650.0, "state": "FLIPPED"},
                           {"id": 9, "tf": "D", "role": "resistance", "lo": 22800.0, "hi": 22870.0, "state": "ACTIVE",
                            "confluence_label": None}]}


def test_engine_gate_tags_carry_the_decisions_areas():
    r = {"level_lo": 22600.0, "level_hi": 22650.0, "grade": "A", "payload": json.dumps(_payload())}
    g = EE.engine_gate_tags(r, "BEARISH")
    assert [a["id"] for a in g["areas"]] == [7, 9] and g["areas"][0]["state"] == "FLIPPED"
    assert g["areas"][0]["confluence_label"] == "confluence: line (touch 3)"
    assert EE.engine_gate_tags({"level_lo": 1.0, "level_hi": 2.0}, "BEARISH")["areas"] is None   # no payload ⇒ NA, never invented


def test_vision_method_bands_only_with_both_settings(monkeypatch):
    """Default (vision_chart_bands OFF, finder validity) ⇒ today's image path; finder "method" ⇒ the engine's own areas from the gate
    tags (no display finder called), drawn with their state; the signal text says they are the engine's areas, one base each."""
    from tests import test_vision_v2 as TV
    from vision import chart as VCH
    from vision import config as VCF
    from vision import signal_audit as SA
    df = TV.bars()
    cs = {**{k: VCF.BOT_DEFAULTS[k] for k in VCF.CTX_KEYS}, "events": {}}
    gate = EE.engine_gate_tags({"level_lo": 22600.0, "level_hi": 22650.0, "payload": json.dumps(_payload())}, "BEARISH")
    monkeypatch.setattr(VCH, "chart_bands", lambda *a, **k: (_ for _ in ()).throw(AssertionError("display finder called")))
    s = TV.sig(ctx_settings={**cs, "vision_chart_bands": True, "vision_chart_band_finder": "method"}, tags={"gate": gate})
    png, meta = VCH.render(df, s)
    if meta["error"] and "aleido" in meta["error"]:
        pytest.skip("kaleido / Chrome missing (BROWSER_PATH)")
    assert meta["error"] is None and meta["ctx"]["bands_finder"] == "method"
    rows = meta["ctx"]["bands"]
    assert [(b["lo"], b["hi"]) for b in rows] == [(22600.0, 22650.0), (22800.0, 22870.0)]
    assert rows[0]["state"] == "flipped (confluence: line (touch 3))" and rows[0]["touches"] is None
    txt = SA.signal_text({**s, "ctx": meta["ctx"]})
    assert "the engine's own areas" in txt and "2+ real reaction touches" not in txt and "22,600.00 - 22,650.00 | flipped" in txt
    s2 = TV.sig(ctx_settings={**cs, "vision_chart_bands": True, "vision_chart_band_finder": "method"})   # no engine areas
    png, meta = VCH.render(df, s2)
    assert meta["ctx"]["bands"] == [] and "the engine row carries no areas" in SA.signal_text({**s2, "ctx": meta["ctx"]})


def test_vision_volume_words_setting(monkeypatch):
    from decision3 import volume_pane as VP
    from tests import test_vision_v2 as TV
    from vision import chart as VCH
    from vision import config as VCF
    df = TV.bars()
    cs = {**{k: VCF.BOT_DEFAULTS[k] for k in VCF.CTX_KEYS}, "events": {}}
    _, m0 = VCH.render(df, TV.sig(ctx_settings=cs))
    _, m1 = VCH.render(df, TV.sig(ctx_settings={**cs, "vision_volume_words": "method"}))
    assert m0["volume_line"] == VP.NA_LINE and m1["volume_line"] == VP.METHOD_NA_LINE      # no FUT given in this fixture


def test_setup_chart_footer_is_the_method_story():
    """The review setup chart's footer reads in the method's order with the label and the evidence list (✓ / ✗ / NA), never a score,
    a power-shift count or a grade."""
    from types import SimpleNamespace
    from decision3 import setup_chart as SC
    st = SimpleNamespace(trend="DOWN", phase="impulse", counter=None, protected=SimpleNamespace(price=23450.0), corr_label=None,
                         parent=None)
    r = {"level": {"tf": "1H", "role": "resistance", "lo": 22600.0, "hi": 22650.0, "births": ["a:D2"], "state": "FLIPPED", "tests": 1,
                   "sweeps": 0, "confluence_label": "confluence: line (touch 3)", "fresh": False},
         "K": {"legs": 1, "why_open": "x"}, "weekly_trend": "UP", "trend_notes": [], "verdict_rule": "method", "conviction": "A",
         "confirming": {"volume_growing": None, "rsi_divergence": True, "confluence": True, "correction_line_closed_through": False},
         "evidence_list": {"required": "present", "entry_hours": "inside",
                           "confirming": {"volume_growing": "NA", "rsi_divergence": "present", "confluence": "present",
                                          "correction_line_closed_through": "absent"}},
         "commit": {"form": "engulf", "visit_start": "2030-03-04 09:15:00", "approach_from": "2030-02-28 13:30:00", "handover_present": True,
                    "handover_state": {"form": "sharp_reversal", "seen_ts": "2030-03-04 09:30:00"},
                    "choch": {"line": "5M CHoCH: close below HL at 09:40"}},
         "zone_read": {"summary": {"rsi_divergence": {"found": True, "degree": 0, "pushes": {"0": 2}, "zone_degree": []}}},
         "trendline": {"broken": False, "broken_before": None}}
    lines = SC.footer_lines(r, st, "trend side OK", "volume: commitment 1.8x the average of the approach leg")
    txt = "\n".join(lines)
    order = ["(1) Trend", "(2) Area", "(3) Arrival", "(4) Inside the area", "(5) Commitment", "(6) LTF", "(7) RSI", "(8) Correction line"]
    assert [txt.index(x) for x in order] == sorted(txt.index(x) for x in order)
    assert "flipped" in lines[1] and "visit since 2030-03-04 09:15" in lines[2] and "sharp_reversal" in lines[3]
    assert "bear divergence present" in lines[6] and "D0" in lines[6]
    assert lines[-1].startswith("Label A (confirming: rsi_divergence, confluence)") and "required set ✓" in lines[-1]
    assert "volume growing inside NA" in lines[-1] and "correction line closed through ✗" in lines[-1]
    for bad in ("grade", "score", "power shift", "conviction"):
        assert bad not in txt.lower(), bad
    short, longst = SC.trend_first_status(None, {**r, "trade_side": ["bear_call"], "trend_used": "DOWN", "ts": "2030-03-04 09:30"})
    assert short == "trend side OK" and "%" not in longst
    assert SC.trend_first_status(None, {**r, "trade_side": ["bull_put"], "trend_used": "UP"})[0] == "against the trend side"
