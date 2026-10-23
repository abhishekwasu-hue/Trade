"""decision3/pa_evidence.py — T9 (PA standard evidence wiring): every PA track's facts listed on each entry. EVIDENCE ONLY.

CLAUDE.md: "Evidence is listed and never blocks." Nothing here enters, blocks, grades or changes an entry: `entry_models.read` adds the
list as the entry's `pa_evidence` after every decision field is set (the 6a `evidence` marks, the label, the trigger and the invalidation
are untouched — pinned by tests/test_pa_evidence.py). No new reading rule, no score, no number, no setting: each row copies the words the
track's own reader writes (its `evidence` / `statements` / `label`), read with bars ≤ t only.

Rows: {"track", "concept", "tf", "text", "src"} in the standard's order (§1 / §2 A–L):
  T1  market state per timeframe + agreement with the trade direction (mtf_state), the leg nature per timeframe (legs_compare);
  T2  the entry area's base type and departure (area_types), its confluence pieces (confluence_pa), the inducement before it and the
      reader's nearest resting liquidity on each side (liquidity_pa);
  T3  channels per timeframe (trendline.channels_by_tf): the channel price is in, a retest of a broken channel line, a counter channel
      broken in the trade direction (handover evidence);
  T4  named chart patterns on 1H / 15M (patterns_pa — named only after confirmation);
  T5  candle forms at a location on the trigger candle (candle_forms), the volume reads (volume_read) — "FUT volume missing" when the
      near-month FUT volume is missing (never spot volume);
  T6  hidden RSI divergence (rsi_hidden), classic reading + the inside-the-move read;
  T7  the structural range per timeframe and a range edge the entry band lies on (range_edges.range_state).
Selection is identity / comparison only: the entry's own area id, a band overlapping the entry band, the reader's own "nearest" flag, the
channel state word. One track failing gives one NA row for it and never stops the others.
"""
from . import trendline as TL

TRACK_ORDER = ("T1", "T2", "T3", "T4", "T5", "T6", "T7")


def _row(track, concept, text, src, tf=None):
    return {"track": track, "concept": concept, "tf": tf, "text": " ".join(str(text).split()), "src": src}


def _overlap(lo, hi, a_lo, a_hi):
    return lo is not None and hi is not None and not (float(hi) < float(a_lo) or float(lo) > float(a_hi))


def _memo(V, key, fn):
    """One read per (bar, direction, reader) — several entries at one bar share it; kept for the current bar only (key[0] = t). The
    readers are bars-≤-t functions."""
    box = V.__dict__.setdefault("_pa_ev_memo", {"t": None, "m": {}})
    if box["t"] != key[0]:
        box["t"], box["m"] = key[0], {}
    if key not in box["m"]:
        box["m"][key] = fn()
    return box["m"][key]


# ------------------------------------------------------------------------------------------------ one builder per track
def t1(V, t, d, area, ctx):
    from . import legs_compare as LC
    from . import mtf_state as MS
    st = _memo(V, (t, d, "mtf"), lambda: MS.read_mtf_state(V, t, d, with_structure=False))
    rows = [_row("T1", "market state", f"{tf} {st['tfs'][tf]['state']}"
                 + (f" ({st['tfs'][tf]['detail']})" if st["tfs"][tf].get("detail") else ""), "mtf_state.read_mtf_state", tf)
            for tf in MS.TFS if tf in st["tfs"]]
    rows.append(_row("T1", "agreement", st["agreement"]["line"], "mtf_state.agreement"))
    lc = _memo(V, (t, d, "legs"), lambda: LC.read_legs_compare(V, t, d))
    rows += [_row("T1", "leg nature", x, "legs_compare.read_legs_compare", x.split(" ", 1)[0]) for x in LC.evidence(lc)]
    return rows


def t2(V, t, d, area, ctx):
    from . import area_types as AT
    from . import confluence_pa as CP
    from . import liquidity_pa as LP
    rows = []
    aid = area.get("id")
    if area.get("object", "area") in ("area", "broken_area"):              # an area of the Levels (a broken line has no base)
        ty =_memo(V, (t, d, "types"), lambda: AT.read_area_types(V, t, d))
        rows += [_row("T2", "area base / departure", x["evidence"], "area_types.read_area_types", x.get("tf"))
                 for x in ty if x.get("id") == aid and x.get("evidence")]
        cf = _memo(V, (t, d, "conf"), lambda: CP.read_confluence(V, t, d))
        rows += [_row("T2", "confluence", x["label"], "confluence_pa.read_confluence", x.get("tf"))
                 for x in cf.get("areas") or () if x.get("id") == aid and x.get("label")]
    lq = _memo(V, (t, d, "liq"), lambda: LP.read_liquidity(V, t, d))
    rows += [_row("T2", "inducement", x["evidence"], "liquidity_pa.inducement", x.get("tf"))
             for x in lq.get("inducement") or () if x.get("area_id") == aid and x.get("evidence")]
    rows += [_row("T2", "liquidity", x["evidence"], "liquidity_pa.obvious_extremes", x.get("tf"))
             for x in lq.get("obvious") or () if x.get("nearest") and x.get("evidence")]
    return rows


def t3(V, t, d, area, ctx):
    want, against = ("down", "rising") if d < 0 else ("up", "falling")
    by = _memo(V, (t, "chan_tf"), lambda: TL.channels_by_tf(V, t))
    rows = []
    for tf in TL.CHANNEL_TFS:
        x = by.get(tf) or {}
        if x.get("na"):
            rows.append(_row("T3", "channel", f"{tf} channels: NA ({x['na']})", "trendline.channels_by_tf", tf))
            continue
        for c in x.get("channels") or ():
            st = str(c.get("state"))
            name = f"{tf} {c['slope_dir']} channel"
            band = f"upper {c['upper_t']:,.2f}, lower {c['lower_t']:,.2f}"
            if c.get("slope_dir") == against and c.get("broken_side") == want:
                rows.append(_row("T3", "channel", f"{name}: {st} — a counter channel broken in the trade direction (handover evidence; "
                                                  f"{band})", "trendline.channels_by_tf", tf))
            elif st == "inside" or st.startswith("retest"):
                rows.append(_row("T3", "channel", f"{name}: {'price inside' if st == 'inside' else st} ({band})",
                                 "trendline.channels_by_tf", tf))
    return rows


def t4(V, t, d, area, ctx):
    from . import patterns_pa as PP
    rows = []
    for tf in PP.TFS:
        p = _memo(V, (t, d, "pat", tf), lambda tf=tf: PP.read_patterns(V, t, d, tf))
        rows += [_row("T4", "chart pattern", x, "patterns_pa.read_patterns", tf) for x in p.get("evidence") or () if x]
    return rows


def t5(V, t, d, area, ctx):
    from . import candle_forms as CF
    from . import volume_read as VR
    f = _memo(V, (t, d, "cf"), lambda: CF.read_candle_forms(V, t, d))
    rows = [_row("T5", "candle form", x, "candle_forms.read_candle_forms", "15M") for x in f.get("evidence") or ()]
    lvl = ctx.get("lvl") if area.get("object", "area") == "area" else None
    v = _memo(V, (t, d, "vol", str(area.get("id"))), lambda: VR.read_volume(V, t, d, area=lvl))
    if v.get("volume") is None:
        rows.append(_row("T5", "volume", "FUT volume missing (never spot volume)", "volume_read.read_volume", "15M"))
    else:
        rows += [_row("T5", "volume", x, "volume_read.read_volume", "15M") for x in v.get("evidence") or () if x]
    return rows


def t6(V, t, d, area, ctx):
    from . import rsi_hidden as RH
    lvl = ctx.get("lvl") if area.get("object", "area") == "area" else None
    h = RH.read_hidden_divergence(V, t, d, move_from=ctx.get("move_from"), arm=ctx.get("arm"), lvl=lvl)
    return [_row("T6", "hidden divergence", x, "rsi_hidden.read_hidden_divergence") for x in h.get("statements") or () if x]


def t7(V, t, d, area, ctx):
    from . import range_edges as RE
    rs = _memo(V, (t, "range"), lambda: RE.range_state(V, t))
    rows = []
    for tf, x in (rs.get("by_tf") or {}).items():
        if x.get("state") == "range" and x.get("band"):
            lo, hi = x["band"]
            rows.append(_row("T7", "range", f"{tf} range {float(lo):,.2f}–{float(hi):,.2f} (structure)", "range_edges.range_state", tf))
            for e in x.get("edges") or ():
                if _overlap(e.get("lo"), e.get("hi"), area["lo"], area["hi"]):
                    rows.append(_row("T7", "range edge", f"the entry band lies on the {tf} {e.get('range_edge')} range edge "
                                                         f"{float(e['lo']):,.2f}–{float(e['hi']):,.2f} ({e.get('lifecycle')})",
                                     "range_edges.range_state", tf))
    return rows


TRACKS = (("T1", t1), ("T2", t2), ("T3", t3), ("T4", t4), ("T5", t5), ("T6", t6), ("T7", t7))


def for_entry(V, t, d, area, lvl=None, arm=None, move_from=None):
    """The PA evidence rows for one entry at bar t, trade direction d (±1); area = the entry's area dict (id, lo, hi, object; a broken
    line: lo = hi = its value at t); lvl = the area as the reader holds it (watch-list / snapshot dict) for the volume / divergence reads;
    arm / move_from = the visit's start and the move into the area (as the 6a evidence reads them). Never raises."""
    t, d = int(t), int(d)
    ctx = {"lvl": lvl, "arm": arm, "move_from": move_from}
    out = []
    for track, fn in TRACKS:
        try:
            out += fn(V, t, d, area, ctx)
        except Exception as exc:                                           # noqa: BLE001 — one track never stops the rest; said, not hidden
            out.append(_row(track, "NA", f"{track} not read ({type(exc).__name__})", fn.__module__ + "." + fn.__name__))
    return out


def brief(rows, limit=None):
    """One plain line of the rows for a card (display only): "T1 1H trending up · T3 …"; NA rows kept (said, never hidden)."""
    parts = [r["text"] for r in rows or () if isinstance(r, dict) and r.get("text")]
    s = " · ".join(parts)
    return s if limit is None or len(s) <= limit else s[:limit - 1].rstrip() + "…"
