"""vision/story.py — Chart Story reader (design docs/design/CHART_READER_AGENT.md §5, §7, §8, §9, §12; build step R3, first slice).

🎓 काय: chart AI ला दिला की तो काळजीपूर्वक trader सारखा chart समजावून सांगतो (KB भाग B टप्पा 8a, Method Pack 0b) — सात भाग + ≤ 15 ओळींचा
मराठी मजकूर. नियम KB / Method Pack मध्ये मजकूर म्हणून; **code फक्त facts मोजतो**, model charts + facts वाचून गोष्ट लिहितो.

Request (एकच call, repair नाही):
  • system = Method Pack + story schema मजकूर, शेवटी prompt-caching breakpoint (`vision.v4.system_blocks` — V4 चाच मार्ग).
  • images = 15M spot candles + FUT volume pane + RSI(14) pane व divergences (rsi2.charts सारखे), 1H, Daily (vision_led.blind_test
    renderer). English मजकूर फक्त.
  • FACTS = `facts.dossier.build_dossier` चे sections (compact) + zone states (decision3 Abhi flip facts main वर असतील तर; नाहीतर NA +
    कारण) + `rsi2.engine.Divergence` (K-RSI) + a-b-c pivots (patterns2 + swings2 pivots वरून `patterns2.fold2.c_equals_a`) + OHLC
    तक्ते. Anonymise (golden): `scripts/golden_vision_check.anonymise` जसंच्या तसं — symbol लपवलेला, तारखा पूर्ण आठवड्यांनी मागे, किंमत
    × scale; facts anonymised frames वरूनच बनतात ⇒ facts, images आणि price check एकाच किंमत-जगात.
  • No look-ahead: प्रत्येक frame `facts.dossier._closed` ने (close ≤ as_of) कापला; FUT तसंच.
Reply: JSON schema check + "प्रत्येक किंमत facts मध्ये" (`vision.checklist.unknown_prices`, V4 चाच validator; देवनागरी अंक सुद्धा
तपासले) + प्रत्येक भाग facts cite करतो (cite चा पहिला key FACTS मध्ये हवा) ⇒ नाहीतर संपूर्ण उत्तर नाकारलं + log (कधीच शांत accept नाही).

Model (कोडमध्ये नाव नाही): role "deep" (pre-open / EOD) = `_global` setting `story_model_deep` ⇒ env `VISION_STORY_DEEP_MODEL`;
role "light" (intraday) = `story_model_light` ⇒ env `VISION_STORY_LIGHT_MODEL` ⇒ env `VISION_SIGNAL_MODEL`. Effort / thinking (ऐच्छिक):
env `VISION_STORY_EFFORT` / `VISION_STORY_THINKING`; max tokens env `VISION_STORY_MAX_TOKENS`.
Budget: खर्च `vision_usage` मध्ये task "chart_story" (cached / uncached tokens सह, pack_version); उप-मर्यादा `_global` setting
`story_daily_cap` (default $1.00 / दिवस), Vision च्या एकूण दैनिक / मासिक budget च्या आत (`vision.v4.budget_ok`, signals राखीव सोडून).
🎓 SHADOW: AI कधीच order देत नाही; setup_read नेहमी "SHADOW — no trade; Abhi decides". हे module order / broker ला हात लावत नाही.
"""
import base64
import json
import logging
import os
import re
import time

import numpy as np
import pandas as pd

from . import checklist as CK
from . import method_pack as MP
from . import v4 as V4

log = logging.getLogger("vision.story")

TASK = "chart_story"
PROMPT_VERSION = "story_v1"
SHADOW = "SHADOW — no trade; Abhi decides"
MARATHI_MAX_LINES = 15
MAX_TOKENS = 12000                                                         # सात भाग + मराठी + thinking (thinking output मध्ये मोजलं जातं; env ने बदलता येतो)
READS = ("pre_open", "intraday", "eod")
READ_ROLE = {"pre_open": "deep", "eod": "deep", "intraday": "light"}       # design §7 + Abhi (13 Oct): deep = pre-open / EOD
ROLE_SETTING = {"deep": "story_model_deep", "light": "story_model_light"}
ROLE_ENV = {"deep": ("VISION_STORY_DEEP_MODEL",), "light": ("VISION_STORY_LIGHT_MODEL", "VISION_SIGNAL_MODEL")}
PARTS = ("daily_trend", "zones", "structure", "in_zone_study", "rsi_divergence", "watch_next", "setup_read")
ZONE_STATES = ("ACTIVE", "sweep", "BROKEN", "FLIPPED", "DEAD", "NA")
VOL_STATES = ("expanding", "contracting", "flat", "NA")
M15_SESSIONS, H1_SESSIONS, DAILY_BARS = 8, 15, 120                         # design §5: 15M ≈ 8 दिवस, 1H ≈ 15 दिवस, Daily ≈ 6 महिने
TABLE_15M_SESSIONS, TABLE_1H_SESSIONS, TABLE_DAILY_BARS = 3, 5, 60         # facts मधले OHLC तक्ते (images पेक्षा लहान — tokens)
PIVOTS_PER_DEGREE = 4
LIQ_NEAR_MR = 4.0                                                          # liquidity pools: close पासून इतक्या MR आतले (display cap)
FALLBACK_RVOL_MIN = 5                                                      # owner (legs2) ला 10 sessions; FUT इतिहास कमी ⇒ हे "short" लेबलसह

# ----------------------------------------------------------------------------------------------------------- schema
_S = {"type": "string"}


def _enum(*v):
    return {"type": "string", "enum": list(v)}


def _part(**extra):
    props = {**extra, "read": _S, "facts": {"type": "array", "items": _S}}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


ZONE_ITEM = {"type": "object", "additionalProperties": False, "required": ["zone", "role", "state", "far_side_swing"],
             "properties": {"zone": _S, "role": _enum("supply", "demand"), "state": _enum(*ZONE_STATES), "far_side_swing": _S}}
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["pack_version", *PARTS, "marathi"],
    "properties": {
        "pack_version": _S,
        "daily_trend": _part(trend=_enum("UP", "DOWN", "RANGE", "unclear"), move=_enum("impulse", "correction", "unclear")),
        "zones": _part(items={"type": "array", "items": ZONE_ITEM}),
        "structure": _part(),
        "in_zone_study": _part(selling_volume=_enum(*VOL_STATES), buying_volume=_enum(*VOL_STATES),
                               growing_side=_enum("sellers", "buyers", "neither", "NA")),
        "rsi_divergence": _part(present=_enum("yes", "no", "NA")),
        "watch_next": _part(watch=_S, invalidation=_S),
        "setup_read": _part(decision=_enum("setup", "wait", "none"), side=_enum("bear", "bull", "none"), label=_S),
        "marathi": _S,
    },
}

SCHEMA_TEXT = (
    "OUTPUT — the Chart Story (fixed schema; SHADOW: your answer never places, sizes or approves a trade)\n"
    "Write the Chart Story of the chart in the user message with the Method Pack above (section 0b lists the seven parts). Return one "
    "JSON object:\n"
    '{"pack_version": "<the 12-hex version from the Method Pack header>",\n'
    ' "daily_trend": {"trend": "UP"|"DOWN"|"RANGE"|"unclear", "move": "impulse"|"correction"|"unclear", "read": "...", "facts": [...]},\n'
    ' "zones": {"items": [{"zone": "<low-high copied from the FACTS>", "role": "supply"|"demand", '
    '"state": "ACTIVE"|"sweep"|"BROKEN"|"FLIPPED"|"DEAD"|"NA", "far_side_swing": "<price copied from the FACTS, or NA>"}], '
    '"read": "...", "facts": [...]},\n'
    ' "structure": {"read": "...", "facts": [...]},\n'
    ' "in_zone_study": {"selling_volume": "expanding"|"contracting"|"flat"|"NA", "buying_volume": "expanding"|"contracting"|"flat"|"NA", '
    '"growing_side": "sellers"|"buyers"|"neither"|"NA", "read": "...", "facts": [...]},\n'
    ' "rsi_divergence": {"present": "yes"|"no"|"NA", "read": "...", "facts": [...]},\n'
    ' "watch_next": {"watch": "...", "invalidation": "...", "read": "...", "facts": [...]},\n'
    ' "setup_read": {"decision": "setup"|"wait"|"none", "side": "bear"|"bull"|"none", "label": "' + SHADOW + '", '
    '"read": "<the reason>", "facts": [...]},\n'
    ' "marathi": "<the Telegram text>"}\n'
    "Rules:\n"
    "- read: English, at most 4 sentences per part (setup_read: 1–2), following the Method Pack section 0b for that part.\n"
    "- facts: the FACTS the part relies on, as paths that start with a top-level FACTS key (for example \"zones.Z2\", "
    "\"in_zone.studies\", \"divergence.latest\", \"ohlc.15M\"). Every part cites at least one.\n"
    "- Prices: every price you write, in any field and in marathi, is copied exactly from the FACTS (JSON or OHLC tables) — never read "
    "from an image, never rounded, never computed by you. Prefer naming the zone id or the pivot over writing a price.\n"
    "- A fact given as NA stays NA (zone state NA, volume NA, divergence NA): say what is missing; never fill it from the image.\n"
    "- zones.items: the zones that matter for this read (most relevant first, at most 4).\n"
    f"- setup_read.label is exactly \"{SHADOW}\". decision \"setup\" needs side bear or bull; \"wait\" names what is missing.\n"
    f"- marathi: simple Marathi (Devanagari) for Telegram, at most {MARATHI_MAX_LINES} lines, Western digits (0-9), the same content as "
    "the seven parts and nothing new; its last line is the SHADOW label.\n"
    "- Do not judge stop, target, position size, reward-to-risk or exits — they are not part of the story.\n"
    "Reply with the JSON object only.")

FACTS_HEAD = ("FACTS (computed by code from closed bars only; nothing after the as-of time exists; the only source of prices). JSON "
              "first, then the OHLC tables (FACTS key \"ohlc\"):\n")


def task_text(read):
    return (f"Read type: {read}. Write the Chart Story (Method Pack section 0b) for the as-of time in FACTS.meta and return the JSON. "
            f"SHADOW — the story never places an order.")


# ----------------------------------------------------------------------------------------------------------- model / settings
def model_for(role, g=None):
    """role deep / light ⇒ (model, स्रोत). स्रोत क्रम: `_global` setting (story_model_deep / story_model_light) ⇒ env (ROLE_ENV).
    Model नाव कधीच कोडमध्ये नाही. सापडलं नाही ⇒ (None, कारण)."""
    if role not in ROLE_SETTING:
        raise ValueError(f"role {role!r} — {sorted(ROLE_SETTING)} पैकी")
    key = ROLE_SETTING[role]
    v = str((g or {}).get(key) or "").strip()
    if v:
        return v, f"setting _global.{key}"
    for env in ROLE_ENV[role]:
        v = (os.environ.get(env) or "").strip()
        if v:
            return v, f"env {env}"
    return None, f"not set (setting _global.{key} or env {' / '.join(ROLE_ENV[role])})"


def role_of(read, role=None):
    if role:
        if role not in ROLE_SETTING:
            raise ValueError(f"role {role!r}")
        return role
    if read not in READ_ROLE:
        raise ValueError(f"read {read!r} — {READS} पैकी")
    return READ_ROLE[read]


def max_tokens():
    return int(os.environ.get("VISION_STORY_MAX_TOKENS", MAX_TOKENS))


def budget_ok(est, g, by_task, today):
    """V4 चाच budget नियम (signals राखीव सोडून दैनिक / मासिक Vision budget) + story उप-मर्यादा `story_daily_cap`."""
    cap = float((g or {}).get("story_daily_cap", 1.0))
    return V4.budget_ok(est, g, by_task, today, task=TASK, sub_cap=cap, label="Chart Story")


# ----------------------------------------------------------------------------------------------------------- frames
def _cut_frames(bars_by_tf, fut5, as_of):
    """Real / anonymised frames ⇒ बंद bars फक्त (close ≤ as_of): 15M (हवाच), 5M, 1m, 1H (15M वरून), D (15M वरून दिवस). FUT तसंच."""
    from facts import dossier as D
    m15 = D._closed(bars_by_tf.get("15M"), 15, as_of)
    if m15 is None:
        raise ValueError("story: no closed 15M bar at or before as_of")
    out = {"15M": m15, "5M": D._closed(bars_by_tf.get("5M"), 5, as_of), "1m": D._closed(bars_by_tf.get("1m"), 1, as_of)}
    out["1H"] = D._hours_from_15m(m15)
    out["D"] = D._closed_daily(daily_from_15m(m15), as_of)
    fut = D._closed(fut5, 5, as_of, keys=D._fut_keys(fut5)) if fut5 is not None else None
    return out, fut


def daily_from_15m(m15):
    """15M bars ⇒ दिवसाचे OHLC (timestamp = दिवस). दिवस पूर्ण झाला का ते `_closed_daily` (session close ≤ as_of) ठरवतो."""
    d = m15.assign(_d=pd.to_datetime(m15["timestamp"]).dt.normalize())
    g = d.groupby("_d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).reset_index()
    return g.rename(columns={"_d": "timestamp"})


def _fut_near_month(fut5):
    """Real FUT ⇒ near-month rows (owner: opportunity_engine.volume.near_month_rows) + `expiry` column (legs2.volume.expiry_of);
    contract नाव काढलं (त्यात symbol + खरी तारीख ⇒ anonymise मध्ये गळती). expiry नंतर anonymise सोबत तितकीच shift होते."""
    if fut5 is None or not len(fut5):
        return None
    from legs2 import volume as LV
    from opportunity_engine import volume as OV
    f = OV.near_month_rows(fut5).copy()
    if "contract" in f.columns or "expiry" in f.columns:
        f["expiry"] = LV.expiry_of(f)
    return f.drop(columns=[c for c in ("contract", "oi") if c in f.columns]).reset_index(drop=True)


def anonymise_all(frames, fut, as_of, anon):
    """`scripts/golden_vision_check.anonymise` (एकच अंमलबजावणी) frames + FUT वर; FUT expiry सुद्धा तितक्याच आठवड्यांनी मागे."""
    from scripts import golden_vision_check as GV
    sw, sc, tk = int(anon["shift_weeks"]), float(anon["scale"]), float(anon["tick"])
    fr = {k: v for k, v in frames.items() if v is not None}
    if fut is not None:
        fr["FUT"] = fut
    afr, aasof = GV.anonymise(fr, as_of, sw, sc, tk)
    afut = afr.pop("FUT", None)
    if afut is not None and "expiry" in afut.columns:
        afut["expiry"] = pd.to_datetime(afut["expiry"]) - pd.Timedelta(days=7 * sw)
    return afr, afut, aasof


# ----------------------------------------------------------------------------------------------------------- facts helpers
def _r(x, nd=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), nd)


def _pt(p):
    return {k: p.get(k) for k in ("ts", "price") if k in p}


def _ohlc_table(df, tf, vol=None, rv=None):
    fmt = "%Y-%m-%d" if tf == "D" else "%Y-%m-%d %H:%M"
    head = "time,open,high,low,close" + (",fut_volume,rel_vol" if vol is not None else "")
    rows = []
    for i, r in enumerate(df.itertuples()):
        row = f"{pd.Timestamp(r.timestamp):{fmt}},{r.open:.2f},{r.high:.2f},{r.low:.2f},{r.close:.2f}"
        if vol is not None:
            v, q = vol[i], rv[i]
            row += "," + ("NA" if not np.isfinite(v) else f"{int(round(v))}") + "," + ("NA" if not np.isfinite(q) else f"{q:.2f}x")
        rows.append(row)
    return head + "\n" + "\n".join(rows)


def _sessions_tail(df, n):
    days = pd.to_datetime(df["timestamp"]).dt.normalize()
    keep = sorted(days.unique())[-n:]
    return df[days.isin(keep).to_numpy()].reset_index(drop=True)


def fut_15m(m15, fut):
    """15M spot bars शी जुळणारा near-month FUT volume (legs2.volume.bar_volume) आणि वेळ-slot normalised RVOL (legs2.volume.rvol, owner
    default: मागचे 20 पात्र sessions, किमान 10). FUT इतिहास कमी ⇒ owner चं RVOL NA ⇒ त्याच owner ने किमान FALLBACK_RVOL_MIN sessions वर
    'short' RVOL (स्पष्ट लेबल). रिटर्न (vol, rv, label)."""
    n = len(m15)
    if fut is None or not len(fut):
        return np.full(n, np.nan), np.full(n, np.nan), "NA (no FUT 5M bars at or before as_of)"
    from legs2 import settings as LS
    from legs2 import volume as LV
    vol = LV.bar_volume(m15, fut)
    s = LS.load()
    rv, _ = LV.rvol(m15, fut, s)
    label = (f"rel_vol = FUT volume / median of the same 15M time-of-day slot over up to {s['rvol_sessions']} previous sessions "
             f"(owner legs2.volume.rvol; min {s['rvol_min_sessions']})")
    if np.isfinite(vol[-1]) and not np.isfinite(rv[-1]):
        rv2, _ = LV.rvol(m15, fut, {**s, "rvol_min_sessions": FALLBACK_RVOL_MIN})
        if np.isfinite(rv2[-1]):
            rv = rv2
            label = (f"rel_vol on a SHORT baseline: FUT history has fewer than {s['rvol_min_sessions']} sessions, so the same-slot median "
                     f"uses {FALLBACK_RVOL_MIN}–{s['rvol_min_sessions'] - 1} previous sessions (owner legs2.volume.rvol) — weaker evidence")
    return vol, rv, label


# ----------------------------------------------------------------------------------------------------------- facts sections
def _trend(S, gaps):
    st = S.get("structure") or {}
    if st.get("status") != "OK":
        return {"status": "NA", "reason": st.get("reason")}
    out = {"source": "swings2 degrees on 15M (D1 smallest … D4 largest); daily SMA trend from the gap owner",
           "daily_sma_trend": (gaps or {}).get("trend") if (gaps or {}).get("status") == "OK" else "NA"}
    for k, v in (st.get("degrees") or {}).items():
        if k == "D0":
            continue
        x = {"pivot_trend": v.get("pivot_trend"),
             "last_pivots": [{"ts": p["ts"], "kind": p["kind"], "label": p.get("label"), "price": p["price"]}
                             for p in (v.get("pivots") or [])[-PIVOTS_PER_DEGREE:]]}
        if v.get("state"):
            x["state"] = {kk: v["state"].get(kk) for kk in ("trend", "range", "lastH", "lastL", "protected", "weak", "reversal")}
        if v.get("events"):
            x["last_events"] = [{kk: e.get(kk) for kk in ("type", "ts", "level", "dir")} for e in v["events"][-3:]]
        out[k] = x
    return out


FLIP_KEYS = ("flip_state", "broken_at", "far_swing", "flipped_at")


def zone_flip_facts(band, df, t, tf="15M"):
    """Abhi चा flip नियम (KB K4: zone पलीकडे AND far-side swing पार ⇒ FLIPPED; नाहीतर BROKEN) — decision3 owner चे facts:
    (1) band वरच `flip_state` (#325 नंतर `decision3.levels.find_bands` स्वतः `band_flip_facts` जोडतो) ⇒ तेच; (2) नाहीतर
    `decision3.levels.band_flip_facts` असेल तर त्याच band वर (त्या TF चा lookback); (3) नाहीतर NA + कारण. नियम इथे लिहिलेला नाही."""
    if band.get("flip_state") is not None:
        return {"status": "OK", "owner": "decision3.levels.find_bands (band_flip_facts)", **{k: band.get(k) for k in FLIP_KEYS}}
    from decision3 import levels as LV
    fn = getattr(LV, "band_flip_facts", None)
    if fn is None:
        return {"status": "NA", "reason": "Abhi's flip rule (KB K4: beyond the zone AND past the far-side swing ⇒ FLIPPED, else BROKEN) "
                                          "is not in the decision3 code on this branch; judge it from the zone's breaks and the pivots"}
    if df is None or not len(df):
        return {"status": "NA", "reason": f"{tf} frame missing"}
    from facts import validity as FV
    try:
        x = fn(df, t, band, FV.lookback(tf))
    except Exception as exc:                                               # noqa: BLE001 — NA with the reason
        return {"status": "NA", "reason": f"decision3.levels.band_flip_facts failed: {type(exc).__name__}"}
    return {"status": "OK", "owner": "decision3.levels.band_flip_facts", **{k: x.get(k) for k in FLIP_KEYS}}


def _zones(S, frames):
    ar = S.get("areas") or {}
    if ar.get("status") != "OK":
        return {"status": "NA", "reason": ar.get("reason")}, {}
    out, raw = {}, {}
    k = 0
    for tf in ("1H", "15M"):
        x = (ar.get("by_tf") or {}).get(tf)
        if not x:
            continue
        df = frames.get(tf)
        for b in sorted(x.get("bands") or [], key=lambda b: -b["hi"]):
            k += 1
            zid = f"Z{k}"
            raw[zid] = (tf, b)
            out[zid] = {"tf": tf, "lo": b["lo"], "hi": b["hi"], "role": b["role"],
                        "kind": "supply" if b["role"] == "resistance" else "demand",
                        "valid": b.get("valid"), "reasons": b.get("reasons"), "touch_count": b.get("touch_count"),
                        "established": b.get("established"), "touches": [_pt(p) for p in b.get("touches") or []],
                        "breaks": [{"ts": z.get("ts"), "dir": z.get("dir"), "close": z.get("price")} for z in (b.get("breaks") or [])[-3:]],
                        "shared_check": {"flipped_by_acceptance": b.get("flipped"), "broken": b.get("broken")},
                        "price_side_now": b.get("price_side"),
                        "abhi_flip_rule": zone_flip_facts(b, df, len(df) - 1 if df is not None else -1, tf)}
    out["_note"] = ("bands from the shared K4 band check (decision3.levels.display_bands): up to 3 above and 3 below the close per "
                    "timeframe + the latest broken one; 'shared_check' flips by acceptance (K5 real break), which is NOT Abhi's "
                    "far-side-swing flip rule — see 'abhi_flip_rule'")
    return out, raw


def _lines(S):
    ln = S.get("lines") or {}
    if ln.get("status") != "OK":
        return {"status": "NA", "reason": ln.get("reason")}
    out = []
    for tf, x in (ln.get("by_tf") or {}).items():
        for l in x.get("lines") or []:
            pz = (l.get("projected_zone") or {}).get("next") or {}
            out.append({"tf": tf, "side": l.get("side"), "anchor1": _pt(l.get("anchor1") or {}), "anchor2": _pt(l.get("anchor2") or {}),
                        "touch_count": l.get("touch_count"), "established": l.get("established"), "valid": l.get("valid"),
                        "broken": l.get("broken"), "value_now": l.get("value_at_t"),
                        "next_touch_zone": [pz.get("lo"), pz.get("hi")] if pz else None})
    conf = S.get("confluence") or {}
    items = [{"band_tf": c.get("band_tf"), "line_tf": c.get("line_tf"), "role": c.get("role"), "band": c.get("band"),
              "line_value": c.get("line_value"), "distance_mr": c.get("distance_mr")} for c in conf.get("items") or []]
    return {"lines": out, "confluence": items}


def _abc(S, zones, mr):
    """a-b-c facts: patterns2 (owner, K11 correction family) + c = a projections from the last three confirmed swings2 pivots of each
    degree (patterns2.fold2.c_equals_a — the same formula) + nearest prior swings / zones to each projection (distance in MR;
    within K4 confluence_mr ⇒ flagged). Facts only — which count is right is the reader's call."""
    from facts import validity as FV
    from patterns2 import fold2 as F2
    pat = S.get("patterns") or {}
    out = {"patterns2": {"status": pat.get("status"), "reason": pat.get("reason")} if pat.get("status") != "OK" else
           {k: _pat(pat.get(k)) for k in ("D2", "D1")}}
    st = (S.get("structure") or {}).get("degrees") or {}
    allp = [p for k in ("D1", "D2", "D3") for p in (st.get(k) or {}).get("pivots") or []]
    cmr = float(FV.DEFAULTS["confluence_mr"])
    proj = {}
    for k in ("D1", "D2"):
        ps = (st.get(k) or {}).get("pivots") or []
        if len(ps) < 3:
            proj[k] = {"status": "NA", "reason": "fewer than 3 confirmed pivots"}
            continue
        p0, p1, p2 = ps[-3:]
        cea = F2.c_equals_a({"family": "zigzag", "x": [p0["price"], p1["price"], p2["price"]]}, None)
        up = p1["price"] > p0["price"]
        kind = "H" if up else "L"
        near = sorted(({"ts": p["ts"], "kind": p["kind"], "degree": p.get("degree"), "price": p["price"],
                        "distance_mr": _r(abs(p["price"] - cea) / mr, 2) if mr else None}
                       for p in allp if p["kind"] == kind and p["ts"] < p2["ts"]), key=lambda x: x["distance_mr"] or 1e9)
        dz = []
        for zid, z in zones.items():
            if zid.startswith("_"):
                continue
            d = 0.0 if z["lo"] <= cea <= z["hi"] else min(abs(cea - z["lo"]), abs(cea - z["hi"]))
            dz.append({"zone": zid, "distance_mr": _r(d / mr, 2) if mr else None})
        dz.sort(key=lambda x: x["distance_mr"] if x["distance_mr"] is not None else 1e9)
        uniq = list({(x["ts"], x["price"]): x for x in near}.values())[:3]
        proj[k] = {"a_start": {"ts": p0["ts"], "price": p0["price"]}, "a_end": {"ts": p1["ts"], "price": p1["price"]},
                   "b_end": {"ts": p2["ts"], "price": p2["price"]}, "a_direction": "up" if up else "down",
                   "c_equals_a": cea, "nearest_prior_swings": uniq, "nearest_zones": dz[:3],
                   "confluence_within_mr": cmr}
    out["projections"] = proj
    out["note"] = ("projections use the last three confirmed swings2 pivots of the degree as a-start, a-end, b-end; c = a = b-end + "
                   "(a-end − a-start). A projection is a measuring tool: it counts only together with a real zone or swing (K4 / K7)")
    return out


def _pat(rec):
    if not rec:
        return None
    out = {k: rec.get(k) for k in ("ts", "phase", "state", "c_eq_a")}
    for k in ("pref", "alt"):
        h = rec.get(k)
        out[k] = None if not h else {kk: h.get(kk) for kk in ("family", "kind", "sub", "waves", "points", "state", "c_eq_a")}
    return out


def _in_zone(S, m15, vol, rv, rv_label, mr):
    c = S.get("candles") or {}
    if c.get("status") != "OK":
        return {"status": "NA", "reason": c.get("reason")}
    ts = pd.to_datetime(m15["timestamp"]).astype(str).tolist()
    studies = []
    for a in c.get("area_studies") or []:
        i0 = ts.index(str(pd.Timestamp(a["arrival"]["ts"]))) if str(pd.Timestamp(a["arrival"]["ts"])) in ts else None
        bars = []
        if i0 is not None:
            for i in range(i0, len(m15)):
                o, h, l, cl = (float(m15[k].iloc[i]) for k in ("open", "high", "low", "close"))
                bars.append({"ts": ts[i], "side": "up" if cl > o else ("down" if cl < o else "flat"),
                             "range_mr": _r((h - l) / mr, 2) if mr else None, "body_mr": _r(abs(cl - o) / mr, 2) if mr else None,
                             "fut_volume": None if not np.isfinite(vol[i]) else int(round(vol[i])),
                             "rel_vol": None if not np.isfinite(rv[i]) else _r(rv[i], 2)})

        def side(sd):
            x = [b for b in bars if b["side"] == sd]
            m = [b["rel_vol"] for b in x if b["rel_vol"] is not None]
            r = [b["range_mr"] for b in x if b["range_mr"] is not None]
            return {"bars": len(x), "mean_range_mr": _r(np.mean(r), 2) if r else None, "mean_rel_vol": _r(np.mean(m), 2) if m else None}
        studies.append({"band_tf": a.get("band_tf"), "band": a.get("band"), "role": a.get("role"), "reaction_side": a.get("reaction_side"),
                        "arrival": a.get("arrival", {}).get("ts"), "bars_in_study": a.get("bars_in_study"),
                        "zone_study": a.get("zone_study"), "commitment": a.get("commitment"),
                        "bars": bars, "by_side": {"down": side("down"), "up": side("up")}})
    lb = c.get("last_bar") or {}
    return {"studies": studies, "volume_source": c.get("volume_source"), "rel_vol_definition": rv_label,
            "last_bar": {k: lb.get(k) for k in ("ts", "open", "high", "low", "close", "read")},
            "reversal_form_at_last_bar": c.get("reversal_form_at_last_bar"),
            "note": "studied only at valid zones touched within decision3 touch_window_bars of as_of (owner decision3.method); the "
                    "approach into the zone is context only (KB K4)"}


def divergence_facts(m15, t=None, df1m=None, s=None):
    """rsi2.engine.Divergence (K-RSI facts on the 15M spot frame): latest pair per degree / side with the absence statement, the
    divergences known now (pivots, RSI, bars, status, area). df1m = intrabar order rows (1m; dossier सारखेच) ⇒ swings2 ला candle मधल्या
    high / low चा क्रम कळतो (नाहीतर उदा. 09:15 spike D0 pivot होत नाही). s = rsi2 settings overrides. Owner failure ⇒ NA + कारण.
    Returns (facts, Divergence | None)."""
    from rsi2 import engine as RE
    try:
        Dv = RE.Divergence(m15, "15M", s=s, df1m=_order_rows(df1m))
        r = Dv.read(t)
    except Exception as exc:                                               # noqa: BLE001 — NA with the reason (evidence only)
        return {"status": "NA", "reason": f"rsi2.engine.Divergence failed: {type(exc).__name__}: {str(exc)[:120]}"}, None

    def slim(x):
        return {"degree": x.get("degree"), "side": x.get("side"), "type": x.get("type"), "status": x.get("status"),
                "pivot1": {k: x["L1"].get(k) for k in ("time", "price", "rsi")}, "pivot2": {k: x["L2"].get(k) for k in ("time", "price", "rsi")},
                "bars_apart": x.get("bars"), "price_rel": x.get("price_rel"), "rsi_diff": x.get("rsi_diff"), "count": x.get("count"),
                "area": x.get("area")}
    return {"rsi14_now": r.get("rsi"), "rsi_warmup": r.get("rsi_warmup"), "bar_window": r.get("bar_window"),
            "latest": [x["statement"] for x in r.get("latest") or []],
            "divergences_now": [slim(x) for x in r.get("divergences") or []],
            "note": "K-RSI facts (rsi2.engine.Divergence, KB K10.4): evidence inside the zone study only — never a trigger alone"}, Dv


def _liquidity(S, close, mr):
    q = S.get("liquidity") or {}
    if q.get("status") != "OK":
        return {"status": "NA", "reason": q.get("reason")}
    near = [p for p in q.get("pools") or [] if mr and abs(float(p.get("price", 0)) - close) <= LIQ_NEAR_MR * mr]
    return {"pools_near": near[:8], "sweeps": (q.get("sweeps") or [])[-4:], "traps": (q.get("traps") or [])[-4:],
            "note": f"pools within {LIQ_NEAR_MR:g} MR of the close"}


def _ltf(S):
    x = S.get("ltf_choch") or {}
    if x.get("status") != "OK":
        return {"status": "NA", "reason": x.get("reason")}
    keep = ("band_tf", "band", "role", "reaction_side", "study_from", "study_to", "done", "at", "close", "line", "sweep")
    return {"visits": [{k: v.get(k) for k in keep} for v in x.get("visits") or []]}


def _plain(sec, drop=("owner",)):
    if not sec:
        return {"status": "NA", "reason": "missing"}
    if sec.get("status") != "OK":
        return {"status": "NA", "reason": sec.get("reason")}
    return {k: v for k, v in sec.items() if k not in drop and k != "status"}


def _order_rows(df1m):
    """Intrabar order rows for swings2 (timestamp + OHLC) or None."""
    if df1m is None or not len(df1m):
        return None
    return df1m[["timestamp", "open", "high", "low", "close"]].reset_index(drop=True)


def build_facts(dossier, frames, fut, as_of, read, meta_extra=None, div=None):
    """Dossier (anonymised frames वरून) + frames ⇒ FACTS dict (JSON-safe, compact). Keys = cite targets for the story.
    div = divergence_facts(...)[0] (आधीच बनवलेलं असल्यास; नाहीतर इथे)."""
    S = dossier["sections"]
    m15 = frames["15M"]
    from facts import validity as FV
    mr = float(FV.mr_at(FV.bars_of(m15), len(m15) - 1))
    vol, rv, rv_label = fut_15m(m15, fut)
    zones, _ = _zones(S, frames)
    if div is None:
        div, _ = divergence_facts(m15, df1m=frames.get("1m"))
    close = float(m15["close"].iloc[-1])
    vs = S.get("volume") or {}
    t15 = _sessions_tail(m15, TABLE_15M_SESSIONS)
    k0 = len(m15) - len(t15)
    facts = {
        "meta": {"index": "hidden (anonymised: dates shifted, prices rescaled — use only these numbers)", "read": read,
                 "as_of": str(pd.Timestamp(as_of)), "last_closed_15m_bar": str(m15["timestamp"].iloc[-1]), "close_now": close,
                 "mr_15m": _r(mr, 2), "price": "spot index", "volume": "near-month index futures (FUT) volume, matched to spot bars",
                 **(meta_extra or {})},
        "trend": _trend(S, S.get("gaps")),
        "zones": zones,
        "lines": _lines(S),
        "abc": _abc(S, zones, mr),
        "in_zone": _in_zone(S, m15, vol, rv, rv_label, mr),
        "volume": _plain(vs) if vs.get("status") != "OK" else {"session": {k: vs["session"].get(k) for k in ("up_bars", "down_bars")},
                                                                 "lookback": vs.get("lookback"), "coverage": vs.get("coverage")},
        "divergence": div,
        "ltf_choch": _ltf(S),
        "liquidity": _liquidity(S, close, mr),
        "context": _plain(S.get("context"), drop=("owner", "missing")),
        "gaps": _plain(S.get("gaps")),
        "ohlc": {"D": _ohlc_table(frames["D"].tail(TABLE_DAILY_BARS), "D") if frames.get("D") is not None else "NA",
                 "1H": _ohlc_table(_sessions_tail(frames["1H"], TABLE_1H_SESSIONS), "1H") if frames.get("1H") is not None else "NA",
                 "15M": _ohlc_table(t15, "15M", vol[k0:], rv[k0:])},
    }
    return facts


def facts_text(facts):
    """FACTS ⇒ prompt मजकूर: JSON (ohlc शिवाय) + OHLC तक्ते (headings = cite paths)."""
    body = {k: v for k, v in facts.items() if k != "ohlc"}
    out = [FACTS_HEAD + json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=str)]
    for tf, tab in (facts.get("ohlc") or {}).items():
        out.append(f"ohlc.{tf} — {tf} spot OHLC (closed bars; last row = last closed bar):\n{tab}")
    return "\n\n".join(out)


# ----------------------------------------------------------------------------------------------------------- images
def m15_figure(frame, vol, rsi, divs, title, zones=None):
    """15M chart: candles + FUT volume pane (decision3.volume_pane.add_plotly — एकच volume pane) + RSI(14) pane व divergence रेघा
    (rsi2.charts चाच रंग / label नियम). English मजकूर फक्त; zone पट्टे फक्त ids सह (किंमत मजकूर नाही — किंमती facts मधून)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from decision3 import volume_pane as VP
    from pivots import charts as PC
    from rsi2 import charts as RC
    from rsi2 import engine as RE
    from vision_led import blind_test as BT
    d = frame.reset_index(drop=True)
    n = len(d)
    x = np.arange(n)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.15, 0.25], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"], showlegend=False,
                                 increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=1)
    for zid, z in (zones or {}).items():
        if zid.startswith("_") or z.get("tf") not in ("15M", "1H"):
            continue
        fig.add_shape(type="rect", x0=0, x1=n - 0.5, y0=z["lo"], y1=z["hi"], line_width=0, row=1, col=1,
                      fillcolor="rgba(239,83,80,0.13)" if z["kind"] == "supply" else "rgba(38,166,154,0.13)")
        fig.add_annotation(x=n - 0.5, y=z["hi"], text=f"{zid} {z['tf']}", showarrow=False, xanchor="left", font=dict(size=10, color="#cfd8dc"),
                           row=1, col=1)
    st = VP.plain(VP.study(d, vol=vol))
    st["side"] = [1 if c > o else (-1 if c < o else 0) for o, c in zip(d["open"], d["close"])]
    VP.add_plotly(fig, st, 2, 1, title="FUT volume (near-month) · blue = up candle, orange = down candle")
    fig.add_trace(go.Scatter(x=x, y=rsi, mode="lines", line=dict(color="#ffd54f", width=1.5), showlegend=False, hoverinfo="skip"),
                  row=3, col=1)
    for yv in (30, 70):
        fig.add_shape(type="line", x0=0, x1=n - 1, y0=yv, y1=yv, line=dict(color="#90a4ae", width=1, dash="dot"), row=3, col=1)
    for k, v in enumerate(RC.merge_degrees(divs or [])):
        xa, xb = PC._x_of(d, v["L1"]["time"]), PC._x_of(d, v["L2"]["time"])
        if xa is None or xb is None:
            continue
        col = RC.DIV_COL[(v["side"], v["type"])]
        ln = dict(color=col, width=2, dash="dash" if v["status"] == "forming" else "solid")
        fig.add_trace(go.Scatter(x=[xa, xb], y=[v["L1"]["price"], v["L2"]["price"]], mode="lines+markers", line=ln, showlegend=False,
                                 hoverinfo="skip"), row=1, col=1)
        ra, rb = PC._x_of(d, v["L1"]["rsi_time"]), PC._x_of(d, v["L2"]["rsi_time"])
        if ra is not None and rb is not None:
            fig.add_trace(go.Scatter(x=[ra, rb], y=[v["L1"]["rsi"], v["L2"]["rsi"]], mode="lines+markers", line=ln, showlegend=False,
                                     hoverinfo="skip"), row=3, col=1)
        fig.add_annotation(x=xb, y=v["L2"]["rsi"] if v["L2"]["rsi"] is not None else 50, text=RE.div_label(v), showarrow=False,
                           yshift=12 + 12 * (k % 2), font=dict(size=10, color=col), row=3, col=1)
    if not divs:
        fig.add_annotation(x=0.01, y=0.95, xref="x3 domain", yref="y3 domain", xanchor="left", text="no RSI divergence", showarrow=False,
                           font=dict(size=11, color="#b0bec5"))
    lo, hi = float(d["low"].min()), float(d["high"].max())
    pad = 0.06 * ((hi - lo) or 1.0)
    step = max(1, n // 10)
    fig.update_layout(template="plotly_dark", width=1600, height=1100, margin=dict(l=10, r=90, t=60, b=40), paper_bgcolor="#0e1117",
                      plot_bgcolor="#0e1117", title=dict(text=title, font=dict(size=15)), showlegend=False)
    fig.update_xaxes(tickvals=list(x[::step]), ticktext=[BT.fmt_time(t, "15M") for t in d["timestamp"].iloc[::step]],
                     rangeslider_visible=False, showgrid=False, row=3, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238", range=[lo - pad, hi + pad], row=1, col=1)
    fig.update_yaxes(side="right", range=[0, 100], gridcolor="#263238", tickvals=[30, 50, 70], row=3, col=1)
    BT.tf_badge(fig, "15M")
    return fig


def render_images(frames, fut, as_of, zones=None, Dv=None):
    """[(name, PNG bytes)]: 15M (+ FUT volume + RSI / divergences), 1H, Daily. Only closed bars (frames already cut at as_of)."""
    from vision_led import blind_test as BT
    m15 = frames["15M"]
    w = _sessions_tail(m15, M15_SESSIONS)
    i0 = len(m15) - len(w)
    vol, _, _ = fut_15m(m15, fut)
    rsi = np.full(len(m15), np.nan) if Dv is None else Dv.rsi
    divs = [] if Dv is None else [x for x in Dv.history(len(m15) - 1) if x["L2"]["bar"] >= i0 and x["L1"]["bar"] >= i0]
    cut = f"cut at {pd.Timestamp(as_of):%Y-%m-%d %H:%M} (closed bars only)"
    out = [("15M", BT.png(m15_figure(w, vol[i0:], rsi[i0:], divs, f"INDEX · 15M spot · FUT volume · RSI(14) · {cut}", zones)))]
    h1 = _sessions_tail(frames["1H"], H1_SESSIONS)
    out.append(("1H", BT.png(BT.figure(h1, "1H", f"INDEX · 1H · {cut}"))))
    dd = frames["D"].tail(DAILY_BARS).reset_index(drop=True)
    out.append(("D", BT.png(BT.figure(dd, "D", f"INDEX · DAILY · {cut}"))))
    return out


# ----------------------------------------------------------------------------------------------------------- prepare (no API)
def prepare(bars_by_tf, fut5, as_of, read, anon=None, render=True, cfg=None, meta_extra=None, symbol="INDEX", hide=(),
            rsi_settings=None):
    """एका story request साठी सगळं (API call नाही): holdout guard (खऱ्या तारखांवर) ⇒ frames कापले (close ≤ as_of) ⇒ (anon असेल तर)
    anonymise ⇒ dossier ⇒ FACTS ⇒ images. रिटर्न dict: facts, text (FACTS + task मजकूर), images [(name, png)], known, anchors,
    as_of (anonymised असल्यास तसा), frames, fut. anon = {"shift_weeks", "scale", "tick"} (golden_vision_check चे defaults) किंवा None.
    anon ⇒ prompt मजकुरात खरी तारीख (as_of चं वर्ष) किंवा `hide` मधला शब्द (उदा. symbol) सापडला ⇒ ValueError (गळती नाही)."""
    from facts import dossier as D
    if read not in READS:
        raise ValueError(f"read {read!r} — {READS} पैकी")
    as_of = pd.Timestamp(as_of)
    D.guard_inputs(symbol, bars_by_tf, {"5M": fut5} if fut5 is not None else None)      # खऱ्या तारखांवर, anonymise आधी
    real_year = str(as_of.year)
    frames, fut = _cut_frames(bars_by_tf, _fut_near_month(fut5), as_of)
    if anon:
        frames, fut, as_of = anonymise_all(frames, fut, as_of, anon)
    dossier = D.build_dossier("INDEX" if anon else symbol, {k: frames.get(k) for k in ("15M", "5M", "1m", "D")},
                              {"5M": fut} if fut is not None else None, as_of=as_of, cfg=cfg)
    div, Dv = divergence_facts(frames["15M"], df1m=frames.get("1m"), s=rsi_settings)
    facts = build_facts(dossier, frames, fut, as_of, read, meta_extra, div=div)
    text = facts_text(facts) + "\n\n" + task_text(read)
    if anon:
        leak = [w for w in (real_year, *hide) if w and re.search(rf"(?<![\w.,]){re.escape(str(w))}(?![\w.,])", text, re.I)]
        if leak:
            raise ValueError(f"story: anonymised prompt leaks {leak}")
    images = render_images(frames, fut, as_of, facts["zones"] if isinstance(facts["zones"], dict) else None, Dv) if render else []
    anchors = CK.facts_prices({tf: frames[tf] for tf in ("15M", "1H", "D") if frames.get(tf) is not None})
    known = CK.facts_prices(anchors, facts)
    return {"facts": facts, "text": text, "images": images, "known": known, "anchors": anchors, "as_of": as_of, "frames": frames,
            "fut": fut, "dossier_inputs": dossier.get("inputs")}


# ----------------------------------------------------------------------------------------------------------- request / estimate
def build_request(images, text, model, pack=None, max_tokens_=None, effort=None, thinking=None, ttl=None):
    if not model:
        raise ValueError("story model not set (setting story_model_deep / story_model_light or env)")
    ptext, _ = pack or MP.load()
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.standard_b64encode(p).decode("utf-8")}} for p in images if p]
    content.append({"type": "text", "text": text})
    params = {"model": model, "max_tokens": int(max_tokens_ or max_tokens()),
              "system": V4.system_blocks(ptext, ttl, schema_text=SCHEMA_TEXT),
              "messages": [{"role": "user", "content": content}],
              "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}
    if effort:
        params["output_config"]["effort"] = effort
    if thinking:
        params["thinking"] = {"type": thinking}
    return params


def estimate(n_images, text, pack_text, model, max_tokens_=None):
    """Dry-run अंदाज (V4.estimate — chars / 4, image ≈ 1,600; story schema + story मजकूर)."""
    return V4.estimate(n_images, None, pack_text, model, max_tokens_ or max_tokens(), schema_text=SCHEMA_TEXT, user_text=text)


# ----------------------------------------------------------------------------------------------------------- validate
_DEV = str.maketrans("०१२३४५६७८९", "0123456789")


def _texts(d):
    """Price check साठी सगळे मुक्त मजकूर (read, zones, watch, invalidation, marathi) — enum / cite / label नाहीत."""
    out = []
    for p in PARTS:
        x = d[p]
        out.append(x["read"])
        if p == "zones":
            for z in x["items"]:
                out += [z["zone"], z["far_side_swing"]]
        if p == "watch_next":
            out += [x["watch"], x["invalidation"]]
    out.append(d["marathi"])
    return [str(t).translate(_DEV) for t in out]


def _cite_ok(c, keys):
    head = re.split(r"[.\[\s/:(]", str(c).strip(), maxsplit=1)[0]
    return head in keys


def validate(raw, pack_version=None, known_prices=None, tick=CK.DEFAULT_TICK, anchors=None, fact_keys=None):
    """Model JSON ⇒ (स्वच्छ dict, None) किंवा (None, English कारण). Fail-closed + log warning. known_prices None ⇒ price check नाही
    (फक्त आकार तपासणी, tests)."""
    out = _validate(raw, pack_version, fact_keys)
    if isinstance(out, str):
        log.warning("Chart Story rejected: %s", out)
        return None, out
    if known_prices is not None:
        bad = CK.unknown_prices(_texts(out), known_prices, tick, anchors)
        if bad:
            why = "prices not in facts: " + ", ".join(dict.fromkeys(bad))
            log.warning("Chart Story rejected: %s", why)
            return None, why
    return out, None


def _validate(raw, pack_version, fact_keys):
    if not isinstance(raw, dict):
        return "not a JSON object"
    want = {"pack_version", *PARTS, "marathi"}
    if set(raw) != want:
        return f"fields {sorted(set(raw) ^ want)} wrong"
    pv = raw.get("pack_version")
    if not isinstance(pv, str) or not re.fullmatch(r"[0-9a-f]{12}", pv.strip()):
        return "invalid pack_version"
    if pack_version and pv.strip() != pack_version:
        return f"pack_version {pv.strip()} != {pack_version}"
    out = {"pack_version": pv.strip()}
    for p in PARTS:
        x = raw.get(p)
        spec = SCHEMA["properties"][p]
        if not isinstance(x, dict) or set(x) != set(spec["required"]):
            return f"{p}: wrong shape"
        y = {}
        for k, ks in spec["properties"].items():
            v = x[k]
            if "enum" in ks:
                if v not in ks["enum"]:
                    return f"{p}.{k}: invalid value {v!r}"
                y[k] = v
            elif ks.get("type") == "string":
                if not isinstance(v, str) or (k in ("read", "label") and not v.strip()):
                    return f"{p}.{k}: empty / not text"
                y[k] = " ".join(v.split())
            elif k == "facts":
                if not isinstance(v, list) or not v or not all(isinstance(c, str) and c.strip() for c in v):
                    return f"{p}: cites no facts"
                if fact_keys is not None:
                    badc = [c for c in v if not _cite_ok(c, fact_keys)]
                    if badc:
                        return f"{p}: cites unknown facts {badc[:3]}"
                y[k] = [c.strip() for c in v]
            elif k == "items":
                if not isinstance(v, list):
                    return "zones.items: not a list"
                items = []
                for z in v:
                    if not isinstance(z, dict) or set(z) != set(ZONE_ITEM["required"]):
                        return "zones.items: wrong shape"
                    if z["role"] not in ("supply", "demand") or z["state"] not in ZONE_STATES:
                        return f"zones.items: invalid role / state {z.get('role')!r} / {z.get('state')!r}"
                    if not all(isinstance(z[q], str) and z[q].strip() for q in ("zone", "far_side_swing")):
                        return "zones.items: empty zone / far_side_swing"
                    items.append({q: " ".join(str(z[q]).split()) for q in ZONE_ITEM["required"]})
                y[k] = items
        out[p] = y
    sr = out["setup_read"]
    if "SHADOW" not in sr["label"] or "no trade" not in sr["label"].lower():
        return "setup_read.label is not the SHADOW label"
    sr["label"] = SHADOW
    if sr["decision"] == "setup" and sr["side"] == "none":
        return "setup_read: decision setup without a side"
    mr = raw.get("marathi")
    if not isinstance(mr, str) or not mr.strip():
        return "marathi: empty"
    lines = [ln.rstrip() for ln in mr.strip().splitlines() if ln.strip()]
    if len(lines) > MARATHI_MAX_LINES:
        return f"marathi: {len(lines)} lines > {MARATHI_MAX_LINES}"
    out["marathi"] = "\n".join(lines)
    return out


def telegram_text(data, title=None):
    """Telegram मजकूर: (title) + मराठी story (≤ 15 ओळी) + SHADOW ओळ (आधीच नसेल तर). पाठवत नाही — फक्त मजकूर."""
    lines = ([f"📖 Chart Story · {title}"] if title else []) + data["marathi"].splitlines()
    if SHADOW not in data["marathi"]:
        lines.append(SHADOW)
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------------- call
def run(client, prep, model, pack=None, on_usage=None, effort=None, thinking=None, ttl=None, max_tokens_=None):
    """एक story call (repair / दुसरा call नाही). रिटर्न dict: status done / rejected / failed, data, error, raw_text, usage (cached /
    uncached tokens), cost_usd, latency_ms, pack_version, prompt_version, model. AI कधीच order देत नाही."""
    from . import signal_audit as SA
    ptext, ver = pack or MP.load()
    imgs = [p for _, p in prep["images"]]
    params = build_request(imgs, prep["text"], model, pack=(ptext, ver), max_tokens_=max_tokens_, effort=effort, thinking=thinking, ttl=ttl)
    out = {"status": "failed", "data": None, "error": None, "raw_text": None, "usage": {}, "cost_usd": 0.0, "latency_ms": 0,
           "pack_version": ver, "prompt_version": PROMPT_VERSION, "model": model, "task": TASK}
    t0 = time.monotonic()
    try:
        msg = client.messages.create(**params)
    except Exception as exc:                                               # noqa: BLE001 — billed असू शकतो ⇒ सावध अंदाज नोंद
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        out["error"] = f"API: {type(exc).__name__}"
        est = estimate(len(imgs), prep["text"], ptext, model, max_tokens_)
        usage = {"input_tokens": est["system_tokens"] + est["fresh_input_tokens"], "output_tokens": est["max_output_tokens"],
                 "estimated": 1}
        out.update(usage=usage, cost_usd=round(SA.cost_usd(model, usage), 6), cost_estimated=True)
        V4._usage_cb(on_usage, usage, out)
        log.warning("Chart Story call failed: %s", out["error"])
        return out
    out["latency_ms"] = int((time.monotonic() - t0) * 1000)
    usage = SA.usage_of(msg)
    out.update(usage=usage, cost_usd=round(SA.cost_usd(model, usage), 6))
    V4._usage_cb(on_usage, usage, out)
    out["raw_text"] = next((b.text for b in (getattr(msg, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    keys = set(prep["facts"])

    def validator(raw, **kw):
        return validate(raw, fact_keys=keys, **kw)
    data, err = V4.read_message(msg, ver, prep["known"], anchors=prep["anchors"], validator=validator)
    if err:
        out.update(status="rejected", error=err)
        log.warning("Chart Story rejected (%s): %s", model, err)
        return out
    out.update(status="done", data=data)
    return out


def cost_line(res):
    """एक ओळ: $ + tokens (uncached input / cache read / cache write / output)."""
    u = res.get("usage") or {}
    return (f"cost ${res.get('cost_usd', 0.0):.4f}{' (estimated)' if res.get('cost_estimated') else ''} · input {u.get('input_tokens', 0):,} "
            f"uncached · cache read {u.get('cache_read', 0):,} · cache write {u.get('cache_write', 0):,} · output {u.get('output_tokens', 0):,}"
            f" · model {res.get('model')} · pack {res.get('pack_version')}")
