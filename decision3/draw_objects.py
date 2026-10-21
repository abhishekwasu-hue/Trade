"""decision3/draw_objects.py — PA standard §4 OUTPUT (track T8): ONE list of drawn objects, the same list on the Telegram (Vision) chart
and on the verification charts. Display / evidence only: nothing here decides, blocks or triggers an entry, and no order is placed.

🎓 The schema (every object is a plain dict, JSON-safe, so it can travel inside a signal's tags to the Vision worker):

    {kind, tf, t0, t1, p0, p1, label, state, style_key, evidence}   + optional {degree, base_type, lines, points, id, src}

  kind       one of KINDS (below).
  tf         the timeframe the object was READ on ("W" / "D" / "1H" / "15M" / "5M") — not the chart it is drawn on.
  t0, t1     timestamps ("YYYY-MM-DD HH:MM:SS", naive IST, the bar START as in the engine frames); t1 may equal t0 (a point).
  p0, p1     prices at t0 / t1. A horizontal object has p0 = p1 (a level, a pool); a band has p0 = low, p1 = high (an area, a FVG).
  label      the short English chart text (Abhi: no Marathi on charts).
  state      the object's state word in the method's vocabulary (see KIND_SPEC), or None.
  style_key  "<kind>[.<variant>]" — decision3/draw_render.STYLE picks colour / line style from it (unknown ⇒ the kind's default).
  evidence   list of short strings: the evidence wording that goes with the object (T9 wires these into the evidence list).
  degree     swings2 degree (swing, line, divergence) — D1 = internal / pullback, D2 = the 1H-area structure.
  base_type  area only: "RBD" / "DBR" / "RBR" / "DBD" (C.1, from the area track) or None until that track lands.
  lines      channel / pattern: extra straight lines [{role, t0, p0, t1, p1}] (the parallel, the neckline, the boundaries).
  points     pattern / line touches: [[t, price], …] (the swings that make it).

Geometry is in TIME and PRICE (never a bar index of one chart), so the same object lands at the same place on a 15M, a 1H or a
Vision chart whose bars are cut differently. Renderers: decision3/draw_render.py (matplotlib + plotly, one geometry).

API
  obj(kind, tf, t0, p0, …)          build + validate one object (ValueError on a bad one).
  clean(objects)                     the valid ones (+ the reasons the others were dropped) — never raises (live display path).
  collect(V, t, extras=None, …)      what EXISTS today at bar t (no look-ahead): swings (D1 / D2, HH / HL / LH / LL), the decision's
                                     areas with their K4 state + confluence label, the trade-side line (+ touch N), equal highs / lows,
                                     sweeps / trapped (failed breakout), regular RSI divergence, the Daily protected swing; plus the
                                     plain-dict lists the other tracks return (T1–T7, `extras`), validated the same way.
  tf_story(V, t, objects, …)         per-timeframe reader story (W / D / 1H / 15M / 5M): market state + the objects of that timeframe.
                                     Display only.
Method-pure: every reading comes from the existing modules (swings2, levels, trendline, liquidity, rsi2, daily); this module only
gathers and words them. Display numbers only (how many sessions a default window shows) — no threshold reads price.
"""
import math

import pandas as pd

KINDS = ("swing", "area", "line", "channel", "level", "fvg", "fib", "pattern", "liquidity", "sweep", "divergence", "entry")
FIELDS = ("kind", "tf", "t0", "t1", "p0", "p1", "label", "state", "style_key", "evidence")
OPTIONAL = ("degree", "base_type", "lines", "points", "id", "src")
TFS = ("W", "D", "1H", "15M", "5M")
TF_ORDER = {tf: i for i, tf in enumerate(TFS)}
BASE_TYPES = ("RBD", "DBR", "RBR", "DBD")

# What each field means per kind, and the state words (the method's vocabulary). None in STATES = any word (the owning track decides).
KIND_SPEC = {
    "swing": ("a confirmed swing: t0 = t1 = the swing bar, p0 = p1 = its price; label HH / HL / LH / LL / EQH / EQL / H / L; degree",
              ("confirmed",)),
    "area": ("supply / demand area: t0 = its base (birth), t1 = now (or when it died), p0 = low, p1 = high; base_type; tf = 1H / D / W",
             ("active", "tested", "broken", "flipped", "dead")),
    "line": (("a straight line through two reactions: (t0, p0) the first anchor, (t1, p1) the line's value at the last bar it is drawn "
              "to; points = the touches"), ("respected", "broken", "retest")),
    "channel": ("two lines of one move: (t0, p0)-(t1, p1) the main line, lines = [the parallel through the opposite extreme]",
                ("inside", "broken", "retest")),
    "level": ("a horizontal higher-timeframe level (earlier swing extreme, protected swing): p0 = p1; t0 = where it comes from", None),
    "fvg": ("a fair value gap left by an impulse: t0 = the gap candle, t1 = now / filled, p0 = low, p1 = high",
            ("open", "partly filled", "filled")),
    "fib": ("a Fibonacci retracement price — ONLY when it lands on an area / liquidity (Abhi): p0 = p1; evidence names what it meets",
            ("confluent",)),
    "pattern": ("a chart pattern from the swings: lines = boundary / neckline, points = its swings, (t0, p0)-(t1, p1) the key line",
                ("forming", "broken", "retest", "failed")),
    "liquidity": ("resting liquidity: equal highs / lows (p0 = p1) or a pool along a line ((t0, p0)-(t1, p1))", ("resting", "taken")),
    "sweep": ("a stop run: t0 = the bar that went beyond, p0 = the pool, p1 = the extreme, t1 = the close back inside",
              ("swept", "trapped")),
    "divergence": ("RSI divergence between two swings: (t0, p0) the first, (t1, p1) the second; label regular / hidden, bull / bear",
                   ("confirmed", "forming")),
    "entry": ("an entry model mark (E1–E4): t0 = the signal bar, p0 = the entry reference, p1 = the invalidation price", None),
}
assert set(KIND_SPEC) == set(KINDS)

DEFAULT_SESSIONS = 8                      # display window of collect() when `since` is not given — the same as charts.h1_png (display)


# ------------------------------------------------------------------------------------------------------------------------- schema
def ts_str(x):
    """Any timestamp-like ⇒ "YYYY-MM-DD HH:MM:SS" (naive; a tz-aware one is first put in IST)."""
    t = pd.Timestamp(x)
    if t.tzinfo is not None:
        t = t.tz_convert("Asia/Kolkata").tz_localize(None)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _num(x, name):
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{name} is not a number: {x!r}")
    if not math.isfinite(v):
        raise ValueError(f"{name} is not finite: {x!r}")
    return round(v, 2)


def _line(d, where):
    if not isinstance(d, dict):
        raise ValueError(f"{where}: a line is a dict {{role, t0, p0, t1, p1}}")
    return {"role": str(d.get("role") or ""), "t0": ts_str(d["t0"]), "p0": _num(d["p0"], f"{where}.p0"),
            "t1": ts_str(d["t1"]), "p1": _num(d["p1"], f"{where}.p1")}


def validate(o):
    """One object ⇒ the normalised dict (timestamps as strings, prices rounded, evidence a list); ValueError with the reason."""
    if not isinstance(o, dict):
        raise ValueError("an object is a dict")
    kind = o.get("kind")
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r} (allowed: {', '.join(KINDS)})")
    tf = o.get("tf")
    if tf not in TFS:
        raise ValueError(f"{kind}: unknown tf {tf!r} (allowed: {', '.join(TFS)})")
    try:
        t0 = ts_str(o["t0"])
        t1 = ts_str(o["t1"] if o.get("t1") is not None else o["t0"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{kind}: bad t0 / t1 ({exc})")
    if t1 < t0:
        raise ValueError(f"{kind}: t1 {t1} before t0 {t0}")
    p0 = _num(o.get("p0"), f"{kind}.p0")
    p1 = _num(o["p1"] if o.get("p1") is not None else o.get("p0"), f"{kind}.p1")
    if kind in ("area", "fvg") and p1 < p0:
        raise ValueError(f"{kind}: a band is p0 = low, p1 = high")
    state = o.get("state")
    allowed = KIND_SPEC[kind][1]
    if state is not None:
        state = str(state)
        if allowed is not None and state not in allowed:
            raise ValueError(f"{kind}: state {state!r} not in {allowed}")
    ev = o.get("evidence")
    ev = [] if ev is None else [ev] if isinstance(ev, str) else [str(x) for x in ev]
    sk = str(o.get("style_key") or kind)
    if sk.split(".")[0] != kind:
        raise ValueError(f"{kind}: style_key {sk!r} must start with the kind")
    out = {"kind": kind, "tf": tf, "t0": t0, "t1": t1, "p0": p0, "p1": p1, "label": str(o.get("label") or ""), "state": state,
           "style_key": sk, "evidence": ev}
    if o.get("degree") is not None:
        out["degree"] = int(o["degree"])
    if o.get("base_type") is not None:
        if kind != "area" or o["base_type"] not in BASE_TYPES:
            raise ValueError(f"{kind}: base_type {o['base_type']!r} (area only, one of {BASE_TYPES})")
        out["base_type"] = o["base_type"]
    if o.get("lines"):
        out["lines"] = [_line(d, f"{kind}.lines[{i}]") for i, d in enumerate(o["lines"])]
    if o.get("points"):
        out["points"] = [[ts_str(a), _num(b, f"{kind}.points")] for a, b in o["points"]]
    for k in ("id", "src"):
        if o.get(k) is not None:
            out[k] = o[k] if isinstance(o[k], (int, str)) else str(o[k])
    if kind == "fib" and not ev:                                          # Abhi: Fibonacci only as confluence, never on its own
        raise ValueError("fib: only when it lands on an area / liquidity — evidence must name what it meets")
    return out


def obj(kind, tf, t0, p0, t1=None, p1=None, label="", state=None, style_key=None, evidence=None, **opt):
    """Build + validate one object (see the module doc). Extra keys: OPTIONAL only."""
    bad = set(opt) - set(OPTIONAL)
    if bad:
        raise ValueError(f"unknown field(s) {sorted(bad)} (optional: {', '.join(OPTIONAL)})")
    return validate({"kind": kind, "tf": tf, "t0": t0, "t1": t1, "p0": p0, "p1": p1, "label": label, "state": state,
                     "style_key": style_key, "evidence": evidence, **opt})


def clean(objects):
    """(valid objects, [reason, …]) — never raises (the live display path: a bad object from another track is dropped, not fatal)."""
    out, why = [], []
    for i, o in enumerate(objects or ()):
        try:
            out.append(validate(o))
        except (ValueError, KeyError, TypeError) as exc:
            why.append(f"#{i} {(o or {}).get('kind') if isinstance(o, dict) else type(o).__name__}: {exc}")
    return out, why


def of_kind(objects, *kinds):
    return [o for o in objects if o["kind"] in kinds]


def in_window(objects, start, end):
    """Objects that touch the time window [start, end] (a horizontal object that began before start is kept)."""
    a, b = ts_str(start), ts_str(end)
    return [o for o in objects if o["t0"] <= b and o["t1"] >= a]


# ------------------------------------------------------------------------------------------------------------------------- collect
def _lv(V):
    return V.levels if hasattr(V, "levels") else V


def _settings(V):
    s = getattr(V, "s", None)
    if s is None:
        s = getattr(_lv(V), "s", None)
    if s is None:
        from . import settings as S3
        s = S3.load()
    return s


def _ns(V):
    """The engine object the trendline / liquidity readers need (V22, or a namespace around a Levels — as charts._trend_line)."""
    if hasattr(V, "levels"):
        return V
    from types import SimpleNamespace
    return SimpleNamespace(levels=V, s=V.s, res=V.res, m15=V.m15)


def window_start(V, t, sessions=DEFAULT_SESSIONS):
    """The first 15M bar of the last `sessions` sessions up to t (the display window; charts.h1_png uses the same)."""
    ts = _lv(V).ts
    days = ts.dt.normalize()
    keep = sorted(days.iloc[:t + 1].unique())[-int(sessions):]
    return int(days.isin(keep).to_numpy().argmax())


def trend_at(V, t):
    """The trade-side trend at t: the engine's own step ① when V is a V22 (read-only call), else the Daily state at the bar's end."""
    if hasattr(V, "step1"):
        return V.step1(t)[3]["trend"]
    from . import daily as DD
    lv = _lv(V)
    return DD.state_at(lv.daily_states, lv.bar_end[t]).trend if lv.daily_states else "UNKNOWN"


def collect(V, t, extras=None, r=None, since=None, trend=None, areas="view", why=None):
    """Every object that exists today at 15M bar t (bars ≤ t, confirmed swings only). V = a decision3 V22 (or its Levels).
    r = the decision row of bar t (optional: its trend, watch list and level are used so the chart shows what the decision used).
    since = first bar index of the window (default: the last DEFAULT_SESSIONS sessions). areas "view" = the 1H chart's selection
    (charts.method_band_view: armed + ≤ 3 per side + inside + latest broken), "all" = every alive area. extras = lists of plain dicts
    from the other tracks (T1–T7) in the same schema. why (list) collects the reasons an object was skipped. Returns [object]."""
    why = [] if why is None else why
    lv = _lv(V)
    t = int(t)
    since = window_start(V, t) if since is None else max(0, int(since))
    trend = (r or {}).get("trend_used") or trend or trend_at(V, t)
    out = []
    for name, fn in (("swings", lambda: swings(V, t, since)), ("areas", lambda: area_objects(V, t, trend, r, areas)),
                     ("line", lambda: trade_line(V, t, trend)), ("liquidity", lambda: equal_pools(V, t, since)),
                     ("sweeps", lambda: sweeps(V, t, since)), ("divergence", lambda: divergences(V, t, since)),
                     ("level", lambda: protected_level(V, t))):
        try:
            out += fn()
        except Exception as exc:                                           # noqa: BLE001 — display only: one reader failing never
            why.append(f"{name}: {type(exc).__name__}: {str(exc)[:120]}")   # stops the rest (the reason is kept)
    got, bad = clean(list(extras or ()))
    why += [f"extras {x}" for x in bad]
    now = ts_str(lv.ts[t])
    late = [o for o in got if o["t0"] > now]                               # no look-ahead: another track's object after t is dropped
    why += [f"extras {o['kind']}: t0 {o['t0']} after the bar {now}" for o in late]
    return out + [o for o in got if o["t0"] <= now]


def swings(V, t, since=0):
    """Confirmed swings (known by t) at the line degree (D1, `tl_degree`) and the area degree (D2, `level_degree`) from swing bar `since`;
    label HH / HL / LH / LL / EQH / EQL by the same degree's previous same-kind swing (swings2.engine.labels)."""
    from swings2 import engine as SE
    lv, s = _lv(V), _settings(V)
    out = []
    for deg in sorted({int(s.get("tl_degree", 1)), int(s.get("level_degree", 2))}):
        ps = [p for p in lv.res["pivots"].get(deg, []) if p.confirm_bar <= t]
        lab = SE.labels(ps)
        for p in ps:
            if p.bar < since:
                continue
            tag = lab.get(id(p), p.kind)
            out.append(obj("swing", "15M", p.ts, p.price, label=tag, state="confirmed", style_key=f"swing.D{deg}", degree=deg, src=p.kind,
                           evidence=[f"{tag} (D{deg}) {p.price:,.0f}"]))
    return out


def _area_state(x):
    st = str(x.get("state") or "ACTIVE").lower()
    return st if st in KIND_SPEC["area"][1] else "active"


def area_objects(V, t, trend, r=None, mode="view"):
    """The decision's own areas (`Levels.snapshot`: one base, K4 state, confluence label) — for the trade side labelled with the line
    confluence exactly as engine.step2 does (`trendline.confluence_areas`). mode "view" = the 1H chart's selection
    (charts.method_band_view) on the areas inside the view distance plus the decision's next armed area (the engine arms every area
    ahead — drawing all of them would hide the candles)."""
    from . import charts as CH
    from . import method as M
    from . import trendline as TL
    lv, s = _lv(V), _settings(V)
    snap = lv.snapshot(t)
    band = (r or {}).get("range_band")
    act = lv.active(t, trend, band) if trend in ("UP", "DOWN", "RANGE") else []
    if trend in ("UP", "DOWN") and s.get("line_rule", "logic") == "logic":
        lab = {x["id"]: x for x in TL.confluence_areas(_ns(V), t, M._dir(trend), act)}
        act = [lab.get(x["id"], x) for x in act]
    if r and r.get("active_levels"):
        act = list(r["active_levels"])
    by_id = {x["id"]: x for x in act}
    snap = [by_id.get(x["id"], x) for x in snap]
    if mode == "all":
        view = [(x, "armed" if x["id"] in by_id else "area") for x in snap]
    else:
        sg = lv.sig1h[t]
        lim = float(s["show_distance_sigma"]) * (sg if math.isfinite(sg) else math.inf)
        near = [x for x in snap if x["dist"] <= lim]                       # the view distance (`show_distance_sigma`, display)
        nxt = sorted((x for x in snap if x["id"] in by_id), key=lambda x: x["dist"])[:1]   # + the decision's next area, always
        shown = near + [x for x in nxt if x["id"] not in {y["id"] for y in near}]
        view = CH.method_band_view(lv, t, shown, {x["id"] for x in shown if x["id"] in by_id})
    out = []
    for x, style in view:
        b = x.get("born_bar")
        t0 = lv.ts[int(b)] if b is not None and 0 <= int(b) <= t else lv.ts[0]
        role = {"resistance": "supply", "support": "demand"}.get(x.get("role"), "area")
        ev = [("fresh" if x.get("fresh") else f"tested {x.get('tests')}")]
        if x.get("sweeps"):
            ev.append("swept (reclaimed)")
        if x.get("confluence_label"):
            ev.append(x["confluence_label"])
        if style == "armed":
            ev.append("armed (on the decision's watch list)")
        out.append(obj("area", {"1H": "1H", "D": "D", "W": "W"}.get(x.get("tf", "1H"), "1H"), t0, x["lo"], t1=lv.ts[t], p1=x["hi"],
                       label=area_label(x, style == "armed"), state=_area_state(x),
                       style_key=f"area.{role}" + (".armed" if style == "armed" else ".broken" if style == "broken" else ""),
                       evidence=ev, id=x.get("id"), base_type=x.get("base_type") if x.get("base_type") in BASE_TYPES else None,
                       src="+".join(x.get("births") or ())))
    return out


def area_label(x, armed=False):
    """Short chart label of an area (the full confluence wording stays in its evidence): "> 1H supply 23,016-23,121 (active, 2 tests,
    swept, conf. Daily + Weekly, line)"."""
    from . import levels as LV
    role = {"resistance": "supply", "support": "demand"}.get(x.get("role"), "area")
    bits = [_area_state(x)]
    if x.get("tests"):
        bits.append(f"{x['tests']} test" + ("s" if x["tests"] > 1 else ""))
    if x.get("sweeps"):
        bits.append("swept")
    conf = sorted({LV.TF_WORD.get(c.get("tf"), c.get("tf")) for c in x.get("confluence") or ()}, key=lambda w: (w != "Daily", w))
    if conf:
        bits.append("conf. " + " + ".join(conf))
    if x.get("confluence_line") or "line" in str(x.get("confluence_label") or ""):
        bits.append("line" + (f" touch {x['line_touch']['touch_no']}" if (x.get("line_touch") or {}).get("touch_no") else ""))
    return f"{'> ' if armed else ''}{LV.tf_word(x)} {role} {x['lo']:,.0f}-{x['hi']:,.0f} ({', '.join(bits)})"


def trade_line(V, t, trend):
    """The trade-side line (`trendline.swing_line`: two separate reactions of the D2 structure) with its reaction touch (touch N)."""
    from . import method as M
    from . import trendline as TL
    if trend not in ("UP", "DOWN"):
        return []
    lv = _lv(V)
    d = M._dir(trend)
    ln = TL.swing_line(_ns(V), t, d)
    if ln is None:
        return []
    rt = TL.reaction_touch(_ns(V), t, d, ln)
    (b1, y1), sl = ln["p1"], ln["slope"]
    pts = [[lv.ts[g[0]], y1 + sl * (g[0] - b1)] for g in (ln.get("touch_groups") or [[ln["p1"][0]], [ln["p2"][0]]])]
    lab = f"line ({ln['touches']} touches)"
    ev = [f"{'falling' if d < 0 else 'rising'} line through the {'lower highs' if d < 0 else 'higher lows'}, {ln['touches']} touches"]
    if rt is not None:
        lab += f"; touch {rt['touch_no']}" + (" = trade location" if rt["trade_location"] else "")
        ev.append(f"reaction turned at the line: touch {rt['touch_no']}" + (" (trade location)" if rt["trade_location"] else ""))
    return [obj("line", "15M", lv.ts[b1], y1, t1=lv.ts[t], p1=y1 + sl * (t - b1), label=lab, state="respected",
                style_key="line.trade_side", evidence=ev, degree=int(_settings(V).get("level_degree", 2)), points=pts,
                src="trendline.swing_line")]


def _bar_of_pool(lv, t, price, side):
    kind = "H" if side == "buy" else "L"
    ps = [p for p in lv.known_pivots(t) if p.kind == kind and abs(float(p.price) - price) < 1e-6]
    return min((p.bar for p in ps), default=None)


def equal_pools(V, t, since=0):
    """Equal highs / lows (liquidity.pools, method: equal by comparison) known at t — resting, or taken once price traded beyond."""
    from . import liquidity as LQ
    lv = _lv(V)
    out = []
    for q in LQ.pools(_ns(V), t):
        if q["src"] != "equal":
            continue
        b = _bar_of_pool(lv, t, q["price"], q["side"])
        if b is None or b < since:
            continue
        hi = q["side"] == "buy"
        seg = lv.A["high"][b + 1:t + 1] if hi else lv.A["low"][b + 1:t + 1]
        taken = bool((seg > q["price"]).any()) if hi else bool((seg < q["price"]).any())
        tag = "EQH" if hi else "EQL"
        out.append(obj("liquidity", "15M", lv.ts[b], q["price"], t1=lv.ts[t], label=f"{tag} {q['price']:,.0f}",
                       state="taken" if taken else "resting", style_key=f"liquidity.{'buy' if hi else 'sell'}",
                       evidence=[f"equal {'highs' if hi else 'lows'} {q['price']:,.0f}: "
                                 + ("taken" if taken else f"{'buy' if hi else 'sell'}-side liquidity resting")], src="equal"))
    return out


def sweeps(V, t, since=0):
    """Sweeps ⚡ / trapped (failed breakout) in since … t (liquidity.sweeps_and_traps, the decision's own reader) — the pools known at
    the start of each session of the window, so a pool born inside the window is watched from the next session on. One poke = one
    sweep: the outermost pool it took."""
    from . import liquidity as LQ
    lv = _lv(V)
    days = lv.ts.dt.normalize().to_numpy()
    starts = [since] + [i for i in range(since + 1, t + 1) if days[i] != days[i - 1]]
    best, trapped = {}, set()
    for s0 in starts:
        sw, tr = LQ.sweeps_and_traps(_ns(V), t, start=s0)
        trapped |= {(x["side"], int(x["bar"])) for x in tr}
        for x in sw:
            key = (x["side"], int(x["bar"]))
            old = best.get(key)
            if old is None or ((float(x["price"]) > float(old["price"])) if x["side"] == "buy" else (float(x["price"]) < float(old["price"]))):
                best[key] = x
    out = []
    for key in sorted(best, key=lambda k: k[1]):
        x = best[key]
        hi = x["side"] == "buy"
        back = x.get("back_at")
        st = "trapped" if key in trapped else "swept"
        src = {"swing": "swing high" if hi else "swing low", "equal": "EQH" if hi else "EQL"}.get(x["src"], x["src"])
        out.append(obj("sweep", "15M", lv.ts[int(x["bar"])], x["price"], t1=lv.ts[int(back)] if back is not None else lv.ts[int(x["bar"])],
                       p1=x["extreme"], label=("failed breakout " if st == "trapped" else "sweep ") + src, state=st,
                       style_key=f"sweep.{'buy' if hi else 'sell'}",
                       evidence=[f"{'buy' if hi else 'sell'}-side sweep of the {src} {float(x['price']):,.0f} (to {float(x['extreme']):,.0f}, "
                                 "closed back inside)" + ("; closes beyond first = trapped traders" if st == "trapped" else "")],
                       src=x["src"]))
    return out


def _rsi(V):
    """The RSI divergence reader (rsi2.engine.Divergence on the engine's own 15M frame + swings) — the engine's instance when it already
    built one, else one built the same way and kept on V (display cache)."""
    have = getattr(V, "_rsi", None)
    if have is not None and not isinstance(have, str):
        return have
    have = getattr(V, "_draw_rsi", None)
    if have is None:
        from rsi2 import engine as RE
        lv = _lv(V)
        have = RE.Divergence(lv.m15[["timestamp", "open", "high", "low", "close"]], "15M", res=lv.res, areas=False)
        try:
            V._draw_rsi = have
        except AttributeError:
            pass
    return have


def divergences(V, t, since=0, kinds=("regular",)):
    """Regular RSI divergence pairs known by t (rsi2 history: confirmed + forming at t), at the line / area degrees, second swing in the
    window, not overtaken by a later higher high / lower low (engine.rsi_divergence's rule). Hidden divergence = track T6 (extras)."""
    lv, s = _lv(V), _settings(V)
    R = _rsi(V)
    H, L = R.B.H, R.B.L
    degs = {int(s.get("tl_degree", 1)), int(s.get("level_degree", 2))}
    out, seen = [], set()
    for x in R.history(t):
        if x.get("type") not in kinds or int(x.get("degree", -1)) not in degs or not x.get("is_div", True):
            continue
        b1, b2 = int(x["L1"]["bar"]), int(x["L2"]["bar"])
        if b2 < since or b2 > t:
            continue
        p2 = float(x["L2"]["price"])
        bear = x["side"] == "bear"
        if (bear and (H[b2 + 1:t + 1] > p2).any()) or (not bear and (L[b2 + 1:t + 1] < p2).any()):
            continue
        key = (x["side"], x["type"], b1, b2, int(x["degree"]))
        if key in seen:
            continue
        seen.add(key)
        r1, r2 = x["L1"].get("rsi"), x["L2"].get("rsi")
        st = "forming" if x.get("status") == "forming" else "confirmed"
        out.append(obj("divergence", "15M", lv.ts[b1], x["L1"]["price"], t1=lv.ts[b2], p1=p2,
                       label=f"{'bear' if bear else 'bull'} {x['type']} div (D{int(x['degree'])})", state=st,
                       style_key=f"divergence.{x['type']}.{'bear' if bear else 'bull'}", degree=int(x["degree"]),
                       evidence=[f"{x['type']} {'bearish' if bear else 'bullish'} RSI divergence D{int(x['degree'])}: price "
                                 f"{'higher high' if bear else 'lower low'} {float(x['L1']['price']):,.0f} → {p2:,.0f}, RSI "
                                 + (f"{float(r1):.0f} → {float(r2):.0f}" if r1 is not None and r2 is not None else "lower" if bear
                                    else "higher") + (" (forming)" if st == "forming" else "")]))
    return out


def protected_level(V, t):
    """The Daily protected swing (decision3.daily state at the bar's end) as a higher-timeframe level."""
    from . import daily as DD
    lv = _lv(V)
    if not lv.daily_states:
        return []
    st = DD.state_at(lv.daily_states, lv.bar_end[t])
    p = st.protected
    if p is None or st.trend not in ("UP", "DOWN", "NEUTRAL"):
        return []
    tag = "HL" if p.kind == "L" else "LH"
    word = "broken by a Daily close" if st.trend == "NEUTRAL" else "holds"
    return [obj("level", "D", lv.ts[0] if pd.Timestamp(p.day) < lv.ts[0] else pd.Timestamp(p.day), p.price, t1=lv.ts[t],
                label=f"Daily protected {tag} {p.price:,.0f}", state="broken" if st.trend == "NEUTRAL" else "protected",
                style_key="level.protected", evidence=[f"Daily protected {tag} {p.price:,.0f} {word}"], src="daily.protected")]


# ------------------------------------------------------------------------------------------------------------------------- story
TREND_WORD = {"UP": "up", "DOWN": "down", "RANGE": "range", "NEUTRAL": "neutral (no side)", "UNKNOWN": "not readable"}


def _structure_word(ps):
    """Market state of one degree from its last confirmed swings (pivots.engine.trend: HH + HL = up, LH + LL = down, else range) —
    plus "correction in progress" when the last swing is against the structure but the protected swing still holds."""
    from pivots import engine as PE
    if len(ps) < 4:
        return "not enough swings yet"
    tr = PE.trend(ps)
    word = {1: "up", -1: "down"}.get(tr["dir"], "range")
    last = ps[-1]
    if word == "up" and last.kind == "H":
        return "up (pullback from the last high in progress)"
    if word == "down" and last.kind == "L":
        return "down (bounce from the last low in progress)"
    return word


def tf_story(V, t, objects=None, r=None, states=None):
    """Per-timeframe reader story (display only): {"W": line, "D": …, "1H": …, "15M": …, "5M": …} in the method's words — the market
    state of the timeframe and the objects read on it. states = {tf: word} from the multi-timeframe state track (mtf_state), which
    overrides the word here (no second reading). English (chart / caption safe)."""
    from . import daily as DD
    lv = _lv(V)
    t = int(t)
    objects = objects if objects is not None else []
    s = _settings(V)
    states = dict(states or {})
    out = {}
    end = lv.bar_end[t]
    wst = getattr(V, "weekly", None) or getattr(lv, "weekly_states", None)
    wk = DD.state_at(wst, end) if wst else None
    out["W"] = "W: " + states.get("W", TREND_WORD.get(wk.trend, wk.trend) if wk is not None else "not read")
    dst = DD.state_at(lv.daily_states, end) if lv.daily_states else None
    if "D" in states:
        dw = states["D"]
    elif dst is None:
        dw = "not read"
    else:
        dw = TREND_WORD.get(dst.trend, dst.trend) + (f", {dst.phase.replace('_', ' ')}" if dst.trend in ("UP", "DOWN") and dst.phase else "")
    out["D"] = "D: " + dw
    for tf, deg in (("1H", int(s.get("level_degree", 2))), ("15M", int(s.get("tl_degree", 1)))):
        ps = [p for p in lv.res["pivots"].get(deg, []) if p.confirm_bar <= t]
        out[tf] = f"{tf}: " + states.get(tf, _structure_word(ps) + f" (D{deg} swings)")
    cm = (r or {}).get("commit") or {}
    ch = (cm.get("choch") or {}).get("line")
    out["5M"] = "5M: " + states.get("5M", ch or "read only inside an area visit (no visit at this bar)")
    c = float(lv.A["close"][t])
    for tf, objs in _story_objects(objects, c, int(s.get("level_degree", 2))).items():
        if tf in out:
            out[tf] += "".join(" · " + _brief(o) for o in objs)
    return out


def _story_objects(objects, close, area_degree):
    """The objects a timeframe's story names (display only, so the line stays short): areas / levels / resting liquidity — the nearest
    above and below price (and the one price is in); sweeps / divergences / FVGs — the latest; lines, channels, patterns, fib, entry
    marks — all. Swings are the state itself (not repeated)."""
    by_tf = {}
    for o in objects:
        if o["kind"] == "swing":
            continue
        by_tf.setdefault(o["tf"], []).append(o)
    out = {}
    for tf, objs in by_tf.items():
        pick = []
        for k in ("area", "level", "liquidity"):
            xs = [o for o in objs if o["kind"] == k and (k != "liquidity" or o["state"] == "resting")]
            lo_, hi_ = (lambda o: min(o["p0"], o["p1"])), (lambda o: max(o["p0"], o["p1"]))
            pick += [o for o in xs if lo_(o) <= close <= hi_(o)][:1]
            pick += sorted((o for o in xs if lo_(o) > close), key=lo_)[:1]
            pick += sorted((o for o in xs if hi_(o) < close), key=hi_, reverse=True)[:1]
        for k in ("sweep", "divergence", "fvg"):
            xs = [o for o in objs if o["kind"] == k]
            pick += sorted(xs, key=lambda o: o["t1"])[-1:]
        pick += [o for o in objs if o["kind"] in ("line", "channel", "pattern", "fib", "entry")]
        out[tf] = pick
    return out


def _brief(o):
    k = o["kind"]
    if k == "area":
        lab = o["label"].lstrip("> ")
        for w in ("Daily ", "Weekly ", "1H "):
            lab = lab.replace(w, "", 1) if lab.startswith(w) else lab
        lab = lab.split(" (")[0] + f" ({o['state']}" + (", fresh" if "fresh" in o["evidence"] else "") + ")"
        return lab + (" [armed]" if o["style_key"].endswith("armed") else "")
    if k in ("sweep", "liquidity"):
        return f"{o['label']} ({o['state']}, {o['t0'][5:16]})" if k == "sweep" else f"{o['label']} ({o['state']})"
    if k == "divergence":
        return f"{o['label']} ({o['state']}, {o['t1'][5:16]})"
    return f"{o['label']}" + (f" ({o['state']})" if o["state"] and o["state"] not in o["label"] else "")


def story_text(story):
    """tf_story ⇒ the lines W → 5M (one per timeframe)."""
    return "\n".join(story[tf] for tf in TFS if tf in story)
