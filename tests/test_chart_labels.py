"""उजवीकडचे chart labels: stagger (एकमेकांवर येऊ नयेत) + फक्त entry-area / ENTRY ठळक (Abhi Sep–Oct review)."""
import plotly.graph_objects as go

from backtest_review import charts as BC


def _labels(fig):
    return [(a.text, a.ay if a.showarrow else a.y, a.y) for a in fig.layout.annotations]


def test_close_labels_are_staggered_with_min_gap():
    fig = go.Figure()
    items = [{"y": 100.0, "text": "ENTRY", "color": "#fff", "bold": True}, {"y": 101.0, "text": "next_opp", "color": "#aaa", "bold": False},
             {"y": 200.0, "text": "far", "color": "#aaa", "bold": False}]
    BC.place_right_labels(fig, 10, items, 0.0, 400.0)
    pos = sorted(p for _, p, _ in _labels(fig))
    gaps = [b - a for a, b in zip(pos, pos[1:])]
    assert min(gaps) >= 0.045 * 400 - 1e-9
    moved = [a for a in fig.layout.annotations if a.showarrow]
    assert len(moved) == 1 and moved[0].y == 101.0                          # बाण खऱ्या भावाकडे


def test_only_bold_items_are_bold_and_none_skipped():
    fig = go.Figure()
    BC.place_right_labels(fig, 5, [{"y": 10.0, "text": "S1", "bold": True}, {"y": 50.0, "text": "S2"}, {"y": None, "text": "x"}], 0.0, 100.0)
    texts = [a.text for a in fig.layout.annotations]
    assert texts == ["<b>S1</b>", "S2"]


def test_labels_kept_inside_top():
    fig = go.Figure()
    BC.place_right_labels(fig, 0, [{"y": 99.0 + i * 0.1, "text": str(i)} for i in range(5)], 0.0, 100.0)
    assert max(p for _, p, _ in _labels(fig)) <= 100.0 + 0.04 * 100 + 1e-9
