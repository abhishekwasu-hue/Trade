"""Chart labels (Abhi 2026-10-09): खऱ्या भावावर क्रमांक-खूण + legend box (किंमतीसह), range बाहेरचे ⇒ कडेवर बाण; entry-area ठळक फक्त
trade दिशेचे (bear ⇒ seller आणि entry च्या वर; bull ⇒ buyer आणि entry च्या खाली); chart वर फक्त चालू SL / target."""
import plotly.graph_objects as go

from backtest_review import charts as BC


def _anns(fig):
    return list(fig.layout.annotations)


def test_marks_stay_on_true_price_and_legend_lists_prices():
    fig = go.Figure()
    items = [{"y": 100.0 + i * 0.5, "text": f"S{i} liquidity {100 + i * 0.5:,.1f}", "bold": False} for i in range(8)]
    n = BC.level_marks(fig, 10, items, 0.0, 400.0)
    marks = [a for a in _anns(fig) if a.xref != "paper"]
    assert n == 8 and len(marks) == 8
    assert sorted(a.y for a in marks) == sorted(it["y"] for it in items)              # कुठलीही खूण भावापासून हललेली नाही
    assert all(not a.showarrow for a in marks)
    legend = [a for a in _anns(fig) if a.xref == "paper" and "①" in a.text]
    assert len(legend) == 1 and "① S7 liquidity 103.5" in legend[0].text              # सर्वात वरचा = ①, किंमतीसह


def test_out_of_range_levels_go_to_edge_with_arrow_not_axis():
    fig = go.Figure()
    BC.level_marks(fig, 0, [{"y": 500.0, "text": "wave1_origin 500"}, {"y": -5.0, "text": "impulse_end -5"},
                            {"y": 50.0, "text": "S1 50"}], 0.0, 100.0)
    texts = [a.text for a in _anns(fig)]
    assert "↑ wave1_origin 500" in texts and "↓ impulse_end -5" in texts
    legend = next(a.text for a in _anns(fig) if a.xref == "paper" and "①" in a.text)
    assert "wave1_origin" not in legend and "S1 50" in legend


def test_only_bold_items_bold():
    fig = go.Figure()
    BC.level_marks(fig, 5, [{"y": 10.0, "text": "S1 10", "bold": True}, {"y": 50.0, "text": "S2 50"}, {"y": None, "text": "x"}], 0.0, 100.0)
    legend = next(a.text for a in _anns(fig) if a.xref == "paper")
    assert "<b>② S1 10</b>" in legend and "<b>① S2 50</b>" not in legend
    marks = {a.text for a in _anns(fig) if a.xref != "paper"}
    assert marks == {"<b>②</b>", "①"}


def test_entry_area_bold_only_trade_side_and_beyond_entry():
    """7 Oct 12:15 bear (entry 22,649, area 22,682–22,740): चढती support B1 (buy, ~22,707) ठळक नाही; S zone entry वर ⇒ ठळक."""
    a = {"low": 22682.07, "high": 22740.23, "side": "sell", "entry": 22648.9}
    assert not BC.is_entry_area(22707.0, 22707.0, "buy", a)                          # B1 trendline — विरुद्ध बाजू
    assert BC.is_entry_area(22720.0, 22745.0, "sell", a)                             # S5 PDH
    assert not BC.is_entry_area(22600.0, 22640.0, "sell", a)                         # seller पण entry च्या खाली
    b = {"low": 100.0, "high": 110.0, "side": "buy", "entry": 112.0}
    assert BC.is_entry_area(101.0, 105.0, "buy", b) and not BC.is_entry_area(113.0, 115.0, "buy", b)


def test_sl_target_shows_only_current_modes():
    sg = {"ref_levels": {"structural_invalidation": 22740.2, "next_opposite_area": 22626.6, "impulse_end": 22217.3}}
    ex = {"sl_mode": "structural_invalidation", "target_mode": "impulse_end"}
    (sl, sl_lab), (tg, tg_lab) = BC.sl_target({"signal": sg, "plan": {"settings": ex, "sl": 22748.6, "target": 22217.3}})
    assert (sl, tg) == (22748.6, 22217.3) and "impulse_end" in tg_lab
    (sl, _), (tg, _) = BC.sl_target({"signal": sg, "plan": {"settings": ex}})           # plan ने भाव काढला नाही (उदा. G9 tier) ⇒ ref
    assert (sl, tg) == (22740.2, 22217.3)
    (sl, _), (tg, _) = BC.sl_target({"signal": sg, "plan": {"settings": {**ex, "target_mode": "next_opposite_area"}}})
    assert tg == 22626.6
    assert BC.sl_target({"signal": sg})[1][0] is None                                    # settings नाहीत ⇒ target नाही


def test_legend_corner_avoids_candles_marks_and_blocked():
    import pandas as pd
    d = pd.DataFrame({"high": [99.0] * 10 + [30.0] * 10, "low": [90.0] * 10 + [10.0] * 10, "close": [95.0] * 10 + [20.0] * 10})
    # डावे candles वर, उजवे खाली ⇒ top-right रिकामा; पण तिथे खुणा असतील तर bottom-left
    assert BC.legend_corner(d, 0.0, 100.0, items_y=[], n_rows=4) == "top-right"
    assert BC.legend_corner(d, 0.0, 100.0, items_y=[95.0, 90.0], n_rows=4) == "bottom-left"
    assert BC.legend_corner(d, 0.0, 100.0, items_y=[95.0, 90.0], n_rows=4, blocked=("bottom-left",)) != "bottom-left"
