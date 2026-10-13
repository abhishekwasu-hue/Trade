"""trendlines2/two_touch.py — the trendline owner's line finder on the shared K6 check (facts/validity.py; Abhi TA1–TA3, design §10).

A line is drawn from 2 wick-anchored touches (confirmed pivots); the projected 3rd touch is the trade location (candidate area). Every
returned line carries its evidence (anchors, touches, break, reasons) and its projected next-touch zone; nothing here is a score.
Uses only bars ≤ t (truncation-safe). Not wired into any decision: charts call it through `display_lines`.
"""
from facts import validity as V


def find_lines(df, t, s=None, start=None, sides=(V.RES, V.SUP)):
    """All 2-touch candidate lines at decision bar t (one per distinct line; valid ones first, ranked by V.rank_line)."""
    s = V.load(s)
    B = V.bars_of(df)
    cands = [x for side in sides for x in V.candidate_lines(B, t, side, s, start=start)]
    valid = V.dedupe_lines([x for x in cands if x["valid"]], s)
    invalid = [x for x in cands if not x["valid"]]
    return valid + invalid


def display_lines(df, t, s=None, start=None, debug=False):
    """TA1: the lines a chart draws at t — at most 2 valid (V.select_lines), each with touch count and projected 3rd-touch zone."""
    return V.select_lines(find_lines(df, t, s, start), s, debug=debug)


def line_label(x):
    """Chart label (English): touch count, established flag and the projected next touch."""
    z = x.get("projected_zone") or {}
    nxt = z.get("next") or {}
    lab = f"{x['side']} line, {x['touch_count']} touches" + (" (established)" if x.get("established") else "")
    if nxt:
        lab += f", touch {z.get('touch_number')} zone {nxt['lo']:,.0f}-{nxt['hi']:,.0f}"
    if not x["valid"]:
        lab += " [invalid: " + ", ".join(x["reasons"]) + "]"
    return lab
