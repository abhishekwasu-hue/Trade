"""P8 clean charts (Abhi 21 Oct, decision3/chart_lines.py + decision3/draw_render.py): DISPLAY ONLY — which lines a chart shows.
Synthetic objects / bars only (no real data, no image written to the repo).

  • an evidence line is always shown; a dead line is hidden; a lower-degree line nearly parallel and close to a higher-degree one is
    dropped for the higher degree; a line outside the trade's path is hidden;
  • the cap follows the display setting `chart_max_lines` (decision3/settings.py OUTPUT, vision/config.py);
  • CI check: sample charts are rendered (matplotlib verification panel + the plotly Vision panel) and their legends never list more
    lines than the setting; the renderer itself asserts it.
"""
import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from decision3 import chart_lines as CL  # noqa: E402
from decision3 import draw_objects as DO  # noqa: E402
from decision3 import draw_render as DR  # noqa: E402
from decision3 import settings as S3  # noqa: E402

N = 40
TS = pd.date_range("2030-01-07 09:15", periods=N, freq="15min")
CLOSE = 95 + np.arange(N) * 0.2
BARS = pd.DataFrame({"timestamp": TS, "high": CLOSE + 1.0, "low": CLOSE - 1.0, "close": CLOSE})
CTX = {"t": str(TS[-1]), "d": -1, "area": (102.0, 104.0), "invalidation": 104.5, "target": (93.0, 94.0), "visit_start": str(TS[35]),
       "bars": BARS, "setup_tf": "15M", "entry_ref": float(CLOSE[-1])}


def flat(v, tf="15M", state="respected", label=None, lid=None):
    return DO.obj("line", tf, TS[0], v, TS[-1], v, label=label or f"{tf} line {v}", state=state, style_key="line", id=lid or f"{tf}@{v}")


def objects(extra=()):
    return [flat(102.5, label="evidence line", lid="ev"),                  # touched in the visit, inside the entry area
            flat(97.0, state="broken", label="dead line", lid="dead"),     # closed through, not retested in the visit
            flat(106.0, tf="1H", label="beyond the invalidation", lid="far"),
            flat(99.0, label="15M near the 1H", lid="dup15"), flat(99.3, tf="1H", label="1H line", lid="h1"),
            DO.obj("area", "1H", TS[0], 102.0, TS[-1], 104.0, label="supply", state="tested", style_key="area.supply"),
            DO.obj("area", "1H", TS[0], 93.0, TS[-1], 94.0, label="demand", state="active", style_key="area.demand"),
            DO.obj("area", "1H", TS[0], 90.0, TS[-1], 91.0, label="old", state="dead", style_key="area.demand"), *extra]


def why(sel, key):
    return next((h["reason"] for h in sel["hidden"] if h["key"] == key), None)


def test_setting_registered_as_a_display_setting():
    from vision import config as VCF
    assert S3.OUTPUT["chart_max_lines"][:2] == (6, (1, 20)) and S3.REGISTER["chart_max_lines"][2] == "setting"
    assert VCF.BOT_DEFAULTS["chart_max_lines"] == 6 and "chart_max_lines" in VCF.CTX_KEYS and VCF.RANGES["chart_max_lines"] == (1, 20)
    assert "chart_max_lines" not in S3.DEFAULTS and CL.max_lines_default() == 6          # display only, never a reading setting
    with pytest.raises(ValueError):
        VCF.validate("srv2_momentum_reversal", {"chart_max_lines": 50})


def test_evidence_shown_dead_hidden_parallel_duplicate_dropped_out_of_path_hidden():
    sel = CL.select(objects(), CTX, max_lines=6)
    shown = [x["key"] for x in sel["lines"]]
    assert "ev" in shown and sel["evidence"] == ["ev"] and sel["lines"][0]["category"] == "evidence line"
    assert "dead" not in shown and why(sel, "dead").startswith("dead")
    assert "far" not in shown and "outside the trade's path" in why(sel, "far")
    assert "h1" in shown and "dup15" not in shown and "nearly parallel and close to the higher-degree line" in why(sel, "dup15")
    labels = {o["label"]: o["style_key"] for o in sel["shown"] if o["kind"] == "area"}
    assert labels["supply"] == "area.supply.context" and labels["demand"] == "area.supply.target" or \
        labels["demand"].endswith(".target")
    assert "old" not in labels                                             # dead area hidden


def test_evidence_line_is_always_shown_even_at_the_smallest_cap():
    extra = [flat(96.0 + k * 0.5, tf="1H", lid=f"h{k}") for k in range(10)]
    sel = CL.select(objects(extra), CTX, max_lines=1)
    assert [x["key"] for x in sel["lines"]] == ["ev"]
    sel = CL.select(objects(extra), {**CTX, "evidence_ids": ["far"]}, max_lines=2)   # an E4 (b) line id: shown even off the path
    assert {x["key"] for x in sel["lines"]} == {"ev", "far"}


@pytest.mark.parametrize("cap", [1, 2, 3, 6, 9])
def test_the_cap_follows_the_setting(cap):
    extra = [flat(96.0 + k * 0.5, tf="1H", lid=f"h{k}") for k in range(10)]
    every = CL.select(objects(extra), CTX, max_lines=100)["lines"]          # what qualifies (a – d) without a cap
    sel = CL.select(objects(extra), CTX, max_lines=cap)
    assert len(every) > 9 and len(sel["lines"]) == min(cap, len(every))
    assert sel["max_lines"] == cap and sel["lines"] == every[:cap] and sel["lines"][0]["key"] == "ev"   # evidence first
    over = [h for h in sel["hidden"] if "over the cap" in h["reason"]]
    assert len(over) == len(every) - len(sel["lines"])


def test_the_renderer_asserts_the_legend_cap():
    extra = [flat(96.0 + k * 0.5, tf="1H", lid=f"h{k}") for k in range(10)]
    xm = DR.XMap(TS, 0)
    with pytest.raises(AssertionError, match="chart_max_lines 6"):
        DR.geometry(objects(extra), xm, ylim=(90, 108), max_lines=6)       # all lines, unselected ⇒ too many in the legend
    sel = CL.select(objects(extra), CTX, max_lines=6)
    prims = DR.geometry(sel["shown"], xm, ylim=(90, 108), max_lines=6, hidden_n=len(sel["hidden"]))
    assert CL.legend_count(prims) == len(sel["lines"]) <= 6
    assert any(p["type"] == "note" and p["text"].startswith(f"hidden: {len(sel['hidden'])}") for p in prims)


@pytest.mark.parametrize("cap", [2, 4, 6])
def test_ci_rendered_sample_charts_never_exceed_the_setting(cap):
    """Render sample charts in both backends and count the legend entries that are lines."""
    import matplotlib.pyplot as plt
    extra = [flat(96.0 + k * 0.5, tf="1H", lid=f"h{k}") for k in range(10)] + \
        [DO.obj("channel", "15M", TS[0], 100.0, TS[-1], 103.0, label="rising channel", state="inside", style_key="channel",
                lines=[{"role": "parallel", "t0": TS[0], "p0": 97.0, "t1": TS[-1], "p1": 100.5}], id="ch")]
    sel = CL.select(objects(extra), CTX, max_lines=cap)
    prims = DR.geometry(sel["shown"], DR.XMap(TS, 0), ylim=(90, 108), max_lines=cap, hidden_n=len(sel["hidden"]))
    fig, ax = plt.subplots()
    DR.draw_mpl(ax, prims)
    line_labels = {DR._short(x["label"]) for x in sel["lines"]} | {x["label"] for x in sel["lines"]}
    legend = [t for t in ax.texts if any(t.get_text().startswith(l) for l in line_labels)]
    plt.close(fig)
    assert 0 < len({t.get_text() for t in legend}) <= cap
    from vision import chart as VC
    df = pd.DataFrame({"start": TS, "open": CLOSE, "high": CLOSE + 1.0, "low": CLOSE - 1.0, "close": CLOSE})
    sig = {"direction": "BEARISH", "ctx_settings": {"chart_max_lines": cap},
           "tags": {"gate": {"area": [102.0, 104.0]}, "entry_invalidation": {"price": 104.5}}}
    from plotly.subplots import make_subplots
    f2 = make_subplots(rows=1, cols=1)
    VC._objects(f2, objects(extra), df, 90, 108, 1, sig=sig)
    ann = [a.text for a in f2.layout.annotations]
    names = {DR._short(o["label"]) for o in objects(extra) if o["kind"] in CL.LINE_KINDS}
    assert sum(1 for a in ann if a in names or any(a.startswith(n) for n in names)) <= cap
    assert any(str(a).startswith("hidden:") for a in ann)


def test_vision_objects_failure_gives_the_chart_without_objects(monkeypatch):
    """Display only: a failing line selection never costs the PNG — the panel is drawn without objects and the error is noted."""
    from plotly.subplots import make_subplots
    from vision import chart as VC
    df = pd.DataFrame({"start": TS, "open": CLOSE, "high": CLOSE + 1.0, "low": CLOSE - 1.0, "close": CLOSE})
    monkeypatch.setattr(CL, "select", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    fig, errs = make_subplots(rows=1, cols=1), []
    VC._objects(fig, objects(), df, 90, 108, 1, sig={"direction": "BEARISH"}, errors=errs)
    assert errs and "boom" in errs[0] and len(fig.layout.shapes) == 0
