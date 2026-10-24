"""decision3/reading_gallery.py — "Today's reading gallery" (owner-orders DECISIONS 49, the daily loop; drawn in the DECISIONS 46 style).

Display / review only: it never reads a rule, a gate or a number of its own. Everything comes from
  • the engine store rows of the session (engine_signals: `entries` + `armed` with visit ids and each model's status, the row's
    reason) and the per-bot consumed records (engine_entry_consumed) — read, never written;
  • the session's V22 (built ONCE by scripts/reading_gallery_today.py from the live engine's inputs) for the geometry: the object's
    lifecycle events known at the decision (Levels events / trendline break, broken back), the next area (Levels.snapshot at the
    closed 15M bar), the refined base the reader itself reports.
Look-ahead: on every panel only the bars CLOSED at the decision (bar end ≤ the decision) are drawn as known; the 15M / 1H bar in
progress and every later bar are drawn faded under "after the decision"; no lifecycle event after the decision is drawn.
Chart text is English; the one reader line per case is plain Marathi built from the row's own reason / status (marathi_line) —
known reader phrases are mapped to Marathi words, internal codes (status names, rule tags, model codes) never appear.

Public: collect(rows, consumed, day) · marathi_line(case) · plan(cases, settings) · render_all(V, sym, cases, out_dir, settings) ·
write_html(out_dir, day, groups, settings) · summary(groups) · panel_bars(...) (the known / after split, tested for look-ahead).
"""
import html as _html
import json
import os
import re
import textwrap

import numpy as np
import pandas as pd

MODELS = ("E1", "E2", "E3", "E4")
NAME_EN = {"E1": "Aggressive", "E2": "Confirmation", "E3": "Structure", "E4": "Sweep-retest"}
DEFAULT_MAX_VISIT_CHARTS = 40                                              # display (dashboard `reading_gallery_max_visit_charts`)


def jsafe(o):
    return json.loads(json.dumps(o, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


def _payload(r):
    try:
        p = json.loads((r or {}).get("payload") or "{}")
    except (TypeError, ValueError):
        return {}
    return p if isinstance(p, dict) else {}


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def px(x):
    v = _f(x)
    return "?" if v is None else f"{v:,.2f}"


# ================================================================================================================ cases from the store
def collect(rows, consumed=None, day=None):
    """The session's cases from the engine store rows of ONE symbol (any order) ⇒ {"entries": [...], "visits": [...], "errors": [...],
    "rows": n}.
      entry  = every (visit_id, model) entry of the session's rows (the first row that carries it = the decision), with the per-bot
               consumed status (engine_entry_consumed: EXECUTED / SKIPPED_* / …; none ⇒ pending);
      visit  = every armed area / broken object visit (visit_id) seen in the rows' `armed` list that got NO entry this session (not an
               entry's visit, not a member of an entry's cluster in the same direction while the visit was seen); its decision bar =
               the LAST row it was seen in (the reader's final status of the visit that session).
    Rows of another day (when `day` is given) and error rows are left out (errors listed)."""
    day = None if day is None else pd.Timestamp(day).normalize()
    rows = sorted([dict(r) for r in rows or []], key=lambda r: str(r.get("bar_ts")))
    entries, seen, visits, errors = [], set(), {}, []
    for r in rows:
        bts = pd.Timestamp(r.get("bar_ts"))
        if day is not None and bts.normalize() != day:
            continue
        if str(r.get("decision") or "").lower() == "error":
            errors.append({"bar_ts": str(bts), "reason": str(r.get("reason") or "")[:200]})
            continue
        p = _payload(r)
        for e in p.get("entries") or []:
            if not isinstance(e, dict) or str(e.get("model") or "").upper() not in MODELS or not e.get("visit_id"):
                continue
            k = (str(e["visit_id"]), str(e["model"]).upper())
            if k in seen:
                continue
            seen.add(k)
            used = [{"bot": c.get("bot"), "status": c.get("status")} for c in consumed or []
                    if str(c.get("visit_id")) == k[0] and str(c.get("model") or "").upper() == k[1]]
            entries.append({"kind": "entry", "bar_ts": str(bts), "entry": e, "reason": str(r.get("reason") or ""), "used": used,
                            "direction": int(e.get("direction") or 0), "visit_id": k[0], "model": k[1]})
        for a in p.get("armed") or []:
            if not isinstance(a, dict) or not a.get("visit_id"):
                continue
            key = str(a["visit_id"])
            v = visits.get(key)
            if v is None:
                v = visits[key] = {"kind": "visit", "visit_id": key, "first_ts": str(bts), "n_rows": 0, "direction": int(a.get("direction") or 0)}
            v.update(bar_ts=str(bts), armed=a, n_rows=v["n_rows"] + 1)
    evid = {e["visit_id"] for e in entries}
    members = [(str(m.get("area_uid") or m.get("area_id")), e["direction"], pd.Timestamp(e["bar_ts"])) for e in entries
               for m in ((e["entry"].get("cluster") or {}).get("members") or []) if isinstance(m, dict)]
    out = []
    for key, v in visits.items():
        a = v["armed"]
        if key in evid:
            continue
        aid, d = str(a.get("area_uid") or a.get("area_id")), int(a.get("direction") or 0)
        if any(aid == m and d == dd and pd.Timestamp(v["first_ts"]) <= t <= pd.Timestamp(v["bar_ts"]) for m, dd, t in members):
            continue
        out.append(v)
    return {"entries": entries, "visits": sorted(out, key=lambda v: (v["first_ts"], v["visit_id"])), "errors": errors,
            "rows": sum(1 for r in rows if day is None or pd.Timestamp(r.get("bar_ts")).normalize() == day)}


def _setting_int(settings, key, dflt):
    try:
        v = int((settings or {}).get(key, dflt))
    except (TypeError, ValueError):
        return dflt
    return max(0, v)


def is_disarmed(c):
    return c["kind"] == "visit" and bool((c.get("armed") or {}).get("disarmed"))


def plan(cases, settings=None):
    """Numbering + the display cap (never a reading rule): every case gets its number #1 … in decision order (entries and visits
    together); entries are always drawn; visits are drawn up to `reading_gallery_max_visit_charts` (in decision order) and, when
    `reading_gallery_disarmed_charts` = off, a disarmed visit (the reader said the visit does not apply) is listed without a chart.
    A case not drawn is still listed with its number and its Marathi line. ⇒ the ordered list (each with "n", "draw")."""
    mx = _setting_int(settings, "reading_gallery_max_visit_charts", DEFAULT_MAX_VISIT_CHARTS)
    dis = str((settings or {}).get("reading_gallery_disarmed_charts", "on")) == "on"
    allc = sorted(list(cases.get("entries") or []) + list(cases.get("visits") or []),
                  key=lambda c: (str(c["bar_ts"]) if c["kind"] == "entry" else str(c["first_ts"]), c["kind"] != "entry", c["visit_id"]))
    drawn = 0
    for i, c in enumerate(allc, 1):
        c["n"] = i
        if c["kind"] == "entry":
            c["draw"], c["why_not_drawn"] = True, None
        elif not dis and is_disarmed(c):
            c["draw"], c["why_not_drawn"] = False, "display: disarmed visits listed without a chart (reading_gallery_disarmed_charts = off)"
        elif drawn >= mx:
            c["draw"], c["why_not_drawn"] = False, f"display cap: {mx} visit charts (reading_gallery_max_visit_charts)"
        else:
            c["draw"], c["why_not_drawn"] = True, None
            drawn += 1
    return allc


# ================================================================================================================ the Marathi line
SIDE_MR = {-1: "bear call", 1: "bull put"}
ROLE_MR = {"resistance": "पुरवठा (resistance)", "support": "मागणी (support)"}
MODEL_MR = {"E1": "पहिला स्पर्श", "E2": "पुष्टी (commitment)", "E3": "रचना (5M CHoCH)", "E4": "sweep / retest",
            "E4a": "sweep नंतरचा retest", "E4b": "तुटलेल्या object चा retest"}
STATUS_MR = {"fired": "entry झाली", "fired_earlier": "या visit मध्ये आधीच entry झाली{at}", "passed": "पहिल्या स्पर्शाची संधी गेली",
             "waiting": "वाट", "off": "dashboard वर बंद", "disarmed": "हा visit लागू नाही",
             "blocked_data_problem": "data problem (FUT volume नाही) ⇒ entry नाही", "fired_outside_hours": "entry वेळेबाहेर ⇒ entry नाही",
             "cluster_consumed": "याच ठिकाणी (cluster) आधीच मोजलं"}
USED_MR = [("EXECUTED", "PAPER position उघडली"), ("ENTERING", "position उघडत होती"), ("OPEN_FAILED", "PAPER position उघडता आली नाही"),
           ("SKIPPED_MODEL_C_OFF", "हे model dashboard वर बंद ⇒ घेतली नाही"), ("SKIPPED_MODEL_OFF", "हे model dashboard वर बंद ⇒ घेतली नाही"),
           ("SKIPPED_CUTOFF", "entry वेळ संपल्यावर ⇒ घेतली नाही"), ("SKIPPED_DIRECTION_OFF", "ही बाजू dashboard वर बंद ⇒ घेतली नाही"),
           ("SKIPPED_MAX_HITS_PER_ZONE", "या क्षेत्रावरच्या entries ची dashboard मर्यादा भरली ⇒ घेतली नाही"),
           ("NOT_ENTERED", "✅ मिळाला नाही / नाकारली ⇒ entry नाही"), ("SKIPPED", "घेतली नाही")]

_N = r"([\d,]+(?:\.\d+)?)"
_TS = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?::\d{2})?"
_B = rf"the refined 15M base {_N}–{_N}(?: \({_TS}\))?"
# (regex, Marathi template) — the reader's own phrases (decision3/entry_models*.py, method.py); groups keep the numbers / times.
PHRASES = [
    (r"price came into the area from the trade side", "किंमत trade च्या बाजूनेच क्षेत्रात आली (pullback नाही)"),
    (rf"the area broke inside this visit at {_TS}", "या visit मध्येच क्षेत्र तुटलं ({0}: close + swing पलीकडे)"),
    (rf"the broken area changed state inside the revisit at {_TS}", "retest दरम्यान तुटलेल्या क्षेत्राची अवस्था बदलली ({0})"),
    (rf"the trend side changed inside this visit \({_TS}", "या visit मध्ये trend ची बाजू बदलली ({0}); पहिला स्पर्श पुढच्या visit ला"),
    (r"no refined base yet", "क्षेत्रात अजून 15M refined base तयार नाही ⇒ models थांबले"),
    (rf"{_B} was closed through in this visit at (?:the 5M candle )?{_TS}",
     "refined base {0}–{1} या visit मध्ये close ने तुटला ({3}) ⇒ तिथे entry नाही"),
    (rf"(?:waiting for price to reach|waiting for a 5M candle to reach) {_B}", "किंमत अजून refined base {0}–{1} पर्यंत आली नाही"),
    (rf"price has not reached the refined 15M base {_N}–{_N}", "किंमत अजून refined base {0}–{1} पर्यंत आली नाही"),
    (rf"{_B} is a newer turn formed inside this visit",
     "refined base {0}–{1} या visit मध्येच नव्याने बनला; पहिला स्पर्श फक्त आधी माहीत base वर"),
    (rf"E1 fires only on the visit's first (?:5M candle|bar) at {_B}; that (?:candle|bar) \({_TS}\) did not",
     "base {0}–{1} वरचा पहिला स्पर्श ({3}) पात्र नव्हता"),
    (rf"E1 fires only on a new visit's first (?:5M candle|bar) \(this visit began {_TS}",
     "पहिला स्पर्श फक्त नव्या visit च्या पहिल्या candle वर (हा visit {0} ला सुरू)"),
    (r"gap through the far side of the area", "क्षेत्राच्या पलीकडच्या कडेतून gap (breakout)"),
    (r"close through the far side of the area", "क्षेत्राच्या पलीकडच्या कडेबाहेर close (breakout)"),
    (r"close beyond the area's far edge", "क्षेत्राच्या पलीकडच्या कडेबाहेर close ⇒ क्षेत्र तुटत आहे, entry नाही"),
    (r"the (?:5M )?candle did not trade inside the area", "candle क्षेत्रात आलीच नाही ⇒ किंमत trade बाजूने क्षेत्र सोडून गेली"),
    (r"close outside the area on the trade side", "trade बाजूला क्षेत्राबाहेर close ⇒ किंमत क्षेत्र सोडून गेली"),
    (rf"the (?:5M )?candle did not trade into the refined 15M base {_N}–{_N}",
     "candle refined base {0}–{1} मध्ये आली नाही (फक्त मोठ्या क्षेत्रात)"),
    (rf"close beyond the invalidation {_N}", "invalidation {0} पलीकडे close"),
    (r"commitment candle not dominant", "commitment candle मोठी नाही (या visit मध्ये तितकी / मोठी candle आधी आहे)"),
    (r"commitment candle: nothing to compare", "commitment candle: तुलना करायला या visit मध्ये अजून काही नाही"),
    (r"commitment volume: nothing to compare", "commitment volume: तुलना करायला काही नाही"),
    (r"commitment on low volume", "commitment candle चा volume कमी"),
    (r"absorption without a handover", "absorption चालू, handover नाही"),
    (r"no commitment", "commitment candle नाही"),
    (r"(?:no 5M CHoCH yet|no LTF CHoCH yet)", "अजून 5M CHoCH नाही"),
    (rf"the 5M CHoCH candle \({_TS}\) did not qualify", "5M CHoCH candle ({0}) trigger म्हणून पात्र नव्हती (refined base मध्ये नव्हती)"),
    (rf"5M: .*?no close (above|below) (?:the )?(?:lower high|higher low|LH|HL)? ?{_N} yet", "5M CHoCH बाकी: अजून {1} च्या {0} close नाही"),
    (r"still making .*?LTF still trending against", "5M अजून विरुद्ध दिशेने चालू (CHoCH नाही)"),
    (r"LTF data missing", "5M data नाही"),
    (r"no (?:5M )?sweep yet", "अजून sweep नाही (पलीकडे जाऊन परत आत close नाही)"),
    (r"(?:5M )?sweep seen; waiting for the next", "sweep झाला; पुढचा push sweep टोकाच्या आत अपयशी होण्याची वाट"),
    (r"revisit in progress; waiting for a (?:5M )?rejection", "तुटलेल्या object चा retest चालू; दूर close करणाऱ्या rejection candle ची वाट"),
    (r"the revisit came from (?:above|below) the broken object", "किंमत तुटलेल्या object कडे मूळ बाजूने आली (break च्या बाजूने retest नाही)"),
    (r"the rejection candle came from (?:above|below) the broken object", "rejection candle मूळ बाजूने येऊन object पार केली (breakout candle, retest नाही)"),
    (r"the rejection candle is not at the retested object", "rejection candle retest object वर नव्हती (किंमत आधीच दूर)"),
    (r"data problem", "data problem: FUT volume नाही / अपुरा"),
    (r"outside the entry hours", "entry वेळेबाहेर"),
    (r"doji level वर", "level वर doji ⇒ पुढच्या candle ची वाट"),
    (r"inside bar", "inside bar ⇒ पुढच्या candle ची वाट"),
    (r"candle अजून pullback-दिशेची", "candle अजून pullback च्या दिशेची ⇒ वाट"),
    (r"commitment candle नाही", "commitment candle नाही"),
]
CODES = re.compile(r"\b(E[1-4][ab]?|RC\d|K\d(?:\.\d)?|H\d|TA\d|Z-1\w*|C-\d+|DECISIONS|SKIPPED_\w*|NOT_ENTERED\w*|fired_earlier|"
                   r"fired_outside_hours|blocked_data_problem|cluster_consumed|disarmed|armed|ignored|touch-legacy|legacy_k_gate|"
                   r"c0|c1|a2|vol_gap_max_frac|entry_trigger_rule|traded_inside|bear_call|bull_put)\b")


SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")                           # setting / status names in snake_case


def code_free(s):
    """True when a text carries none of the internal codes (status names, rule tags, model codes, snake_case setting names, a bare
    "(a)" / "(b)" variant tag)."""
    s = str(s or "")
    return CODES.search(s) is None and SNAKE.search(s) is None and re.search(r"\(\s*[ab]\s*\)", s) is None


def to_mr(text):
    """One reader phrase (English, as the reader wrote it) ⇒ plain Marathi. Known phrases ⇒ their Marathi words (numbers kept); an
    unknown phrase ⇒ the reader's words quoted with every internal code removed (never invented)."""
    t = str(text or "").strip()
    if not t:
        return ""
    for rx, mr in PHRASES:
        m = re.search(rx, t)
        if m:
            return mr.format(*[g or "" for g in m.groups()])
    t = re.sub(r"\s*\((?:RC\d|H\d|K\d|TA\d|Z-1\w*|DECISIONS[^)]*|Abhi[^)]*|[^)]*_[a-z]+[^)]*)\)", "", t)
    t = re.sub(r"\bE4\s*\(([ab])\)", lambda m: MODEL_MR["E4" + m.group(1)], t)          # model codes ⇒ the model in words
    t = re.sub(r"\bE([1-4])\b", lambda m: MODEL_MR["E" + m.group(1)], t)
    t = SNAKE.sub("", t)                                                     # setting names (snake_case) never shown
    t = CODES.sub("", t)
    t = re.sub(r"\(\s*[ab]?\s*\)", "", t)                                   # a bare "(b)" / "()" left behind
    t = re.sub(r"\s*=\s*(?=[\s;,.]|$)", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ;,—-=")
    return f"वाचक: “{t}”" if t else ""


def object_mr(a, e=None):
    a = a or {}
    obj = str(a.get("object") or (e or {}).get("object") or "area")
    if obj == "broken_line" or str(a.get("area_id") or a.get("id") or "").startswith("line:"):
        return "तुटलेली रेषा" + (f" (आता {px(a.get('lo'))})" if _f(a.get("lo")) is not None else "")
    role = ROLE_MR.get(str(a.get("role")), str(a.get("role") or ""))
    pre = "तुटलेलं " if obj == "broken_area" else ""
    return f"{pre}{a.get('tf') or ''} {role} क्षेत्र {px(a.get('lo'))}–{px(a.get('hi'))}".strip()


def model_key(e):
    m = str(e.get("model") or "").upper()
    if m == "E4":
        return "E4b" if str(e.get("object") or "").startswith("broken") or "(b)" in str(e.get("name") or "") else "E4a"
    return m


WHY_MR = {"E1": "visit मधला refined base {rb} चा पहिला स्पर्श, base च्या पलीकडच्या कडेबाहेर close नाही",
          "E2": "refined base {rb} वर commitment candle (पुष्टी) बंद झाली",
          "E3": "5M CHoCH candle (pullback विरुद्धच्या शेवटच्या 5M swing पलीकडे close) refined base {rb} मध्ये आली",
          "E4a": "क्षेत्राबाहेर sweep (swing न बनता परत आत close) आणि पुढचा 5M push sweep टोकाच्या आत अपयशी",
          "E4b": "किंमत break च्या बाजूने {obj} कडे परत आली आणि 5M rejection candle तिथून दूर close झाली"}
INV_WHAT_MR = [("refined 15M base's far edge", "refined base ची पलीकडची कड"), ("visit's extreme", "visit चं टोक"),
               ("sweep extreme", "sweep टोक"), ("retest extreme", "retest टोक"), ("area's far edge", "क्षेत्राची पलीकडची कड")]


def inv_mr(inv):
    inv = inv if isinstance(inv, dict) else {"price": inv}
    rule = str(inv.get("rule") or "")
    word = "वर" if " above " in f" {rule} " else ("खाली" if " below " in f" {rule} " else "पलीकडे")
    what = next((mr for en, mr in INV_WHAT_MR if en in rule), "invalidation")
    return f"{what} {px(inv.get('price'))} च्या {word} close"


def used_mr(used):
    if not used:
        return "कोणत्याही bot ने अजून घेतली नाही (pending)"
    out = []
    for u in used:
        st = str(u.get("status") or "")
        w = next((mr for code, mr in USED_MR if st.startswith(code)), "नोंद आहे")
        out.append(f"{u.get('bot')}: {w}")
    return "; ".join(dict.fromkeys(out))


def marathi_line(c):
    """ONE plain Marathi line of the reader's own reason for a case (an entry: the model in words, the object, the side, the model's
    definition, the invalidation; a visit: what each model's status says, grouped). Built only from the row's entry / armed record."""
    if c["kind"] == "entry":
        e = c["entry"]
        mk = model_key(e)
        rb = e.get("refined_base") or {}
        rbt = f"{px(rb.get('lo'))}–{px(rb.get('hi'))}" if rb else "(नाही)"
        obj = object_mr(e.get("area") or {}, e)
        why = WHY_MR.get(mk, "").format(rb=rbt, obj=obj)
        return (f"{obj} वर {SIDE_MR.get(int(e.get('direction') or 0), '')} entry — {MODEL_MR.get(mk, '')} model, {px(e.get('entry_ref'))} "
                f"ला: {why}; invalidation: {inv_mr(e.get('invalidation'))}.")
    a = c.get("armed") or {}
    head = f"{object_mr(a)} वर {SIDE_MR.get(int(a.get('direction') or 0), '')} visit — entry नाही: "
    if a.get("disarmed"):
        return head + to_mr(a["disarmed"]) + "."
    groups = {}
    for m, st in (a.get("models") or {}).items():
        st = st or {}
        s = str(st.get("status") or "")
        word = STATUS_MR.get(s, "")
        if s == "fired_earlier":
            word = word.format(at=f" ({str(st.get('at'))[:16]})" if st.get("at") else "")
        reason = to_mr(st.get("waiting") or st.get("note") or "")
        if s == "waiting":
            phrase = reason or "वाट"
        elif s == "off":
            phrase = word
        else:
            phrase = word + (f" — {reason}" if reason and s not in ("fired_earlier",) else "")
        mk = "E4b" if m == "E4" and str(a.get("object") or "").startswith("broken") else m
        groups.setdefault(phrase, []).append(MODEL_MR.get(mk, mk))
    if not groups:
        return head + "models ची नोंद नाही."
    return head + "; ".join(f"{', '.join(ms)}: {ph}" for ph, ms in groups.items()) + "."


# ================================================================================================================ geometry (from V)
def _ts15(V):
    return pd.to_datetime(V.m15["timestamp"]).reset_index(drop=True)


def ctx_bar(V, dec):
    """The last 15M bar CLOSED at the decision (bar_end ≤ dec) — everything above the trigger is read there."""
    be = pd.to_datetime(V.bar_end).to_numpy("datetime64[ns]")
    return int(np.searchsorted(be, np.datetime64(pd.Timestamp(dec)), side="right")) - 1


def find_line(V, lid, k):
    """The line as listed AT the decision's closed 15M bar k only (never a later bar: a line can be redrawn later ⇒ look-ahead).
    Not listed at k ⇒ None (the chart says "line not known at the decision")."""
    from . import trendline as TL
    try:
        cands = list(TL.channel_lines(V, k)) + [ch["parallel"] for ch in TL.channels(V, k)]
    except Exception:                                                      # noqa: BLE001 — display
        return None
    return next((x for x in cands if str(x.get("id")) == str(lid)), None)


def geometry(V, c):
    """The case's object as known at its decision: {dec, k, d, kind (area | line), lo, hi, tf, role, state, label, events [(ts, kind,
    word)], line (dict), rb (refined base), inv {price, rule}, next {…}, approach {ts, from, y}, trigger (ts, end), entry_ref}."""
    from . import trendline as TL
    dec = pd.Timestamp(c["bar_ts"])
    k = ctx_bar(V, dec)
    ts = _ts15(V)
    e = c.get("entry") if c["kind"] == "entry" else None
    a = (e.get("area") if e else c.get("armed")) or {}
    d = int((e or c.get("armed") or {}).get("direction") or c.get("direction") or 0)
    aid = a.get("id", a.get("area_id"))
    obj = str((e or {}).get("object") or a.get("object") or "area")
    g = {"dec": dec, "k": k, "d": d, "obj": obj, "lo": _f(a.get("lo")), "hi": _f(a.get("hi")), "tf": a.get("tf"), "role": a.get("role"),
         "state": a.get("state"), "aid": aid, "uid": a.get("uid") or a.get("area_uid"), "events": [], "line": None, "rb": None, "inv": None, "next": None, "approach": None}
    T = lambda b: ts[int(b)] if 0 <= int(b) < len(ts) else None             # noqa: E731
    if str(aid).startswith("line:"):
        g["kind"] = "line"
        ln = find_line(V, str(aid)[5:], k)
        g["line"] = ln
        if ln is not None:
            b2 = int((ln.get("p2") or ln["p1"])[0])
            if b2 <= k:
                g["events"].append((T(b2), "born", "line drawn (2nd swing)"))
            if ln.get("broken") and ln.get("break_bar") is not None and int(ln["break_bar"]) <= k:
                g["events"].append((T(ln["break_bar"]), "broken", f"broken {ln.get('break_side') or ''}: close beyond"))
                try:
                    kb = TL.break_known_at(V, ln)
                    if kb is not None and int(kb) <= k:
                        g["events"].append((T(kb), "known", "break known (swing beyond)"))
                    bb = TL.broken_back_at(V, ln, k)
                    if bb is not None and int(bb) <= k:
                        g["events"].append((T(bb), "reclaim", "broken back ⇒ dead"))
                except Exception:                                          # noqa: BLE001 — display
                    pass
        g["label"] = (f"broken {ln.get('tf', '')} line {ln.get('family', '')}".replace("  ", " ") if ln else
                      "broken line (line not known at the decision — not drawn)")
    else:
        g["kind"] = "area"
        L = None
        uid = a.get("uid") or a.get("area_uid")                            # A5: the place's stable id first (the list index of
        if uid and hasattr(V.levels, "by_uid"):                            # another build may name a different level)
            L = V.levels.by_uid(uid)
        if L is None and not uid:
            try:
                L = V.levels.L[int(aid)]
            except (TypeError, ValueError, IndexError):
                L = None
        if L is not None:
            if L.born_bar <= k:
                g["events"].append((T(L.born_bar), "born", f"born ({L.tf} {L.role0})"))
            for b, kind, _w in L.events:
                if int(b) <= k and kind != "test":
                    g["events"].append((T(b), kind, {"broken": "broken (close + swing beyond)", "flip": "flipped (role changed)",
                                                      "reclaim": "reclaimed (broken back)", "dead": "dead", "sweep": "sweep"}.get(kind, kind)))
            if L.dead_bar is not None and L.dead_bar <= k and not any(x[1] == "dead" for x in g["events"]):
                g["events"].append((T(L.dead_bar), "dead", "dead"))
            g["tests"] = sum(1 for b, kind, _ in L.events if kind == "test" and int(b) <= k)
        role = {"resistance": "supply", "support": "demand"}.get(str(g["role"]), str(g["role"]))
        g["label"] = (f"{'broken ' if obj == 'broken_area' else ''}{g['tf']} {role} area {px(g['lo'])}–{px(g['hi'])} "
                      f"({str(g['state'] or '').lower()})")
    g["events"] = [x for x in g["events"] if x[0] is not None and pd.Timestamp(x[0]) <= ts[k]]
    if e:
        rb = e.get("refined_base")
        g["rb"] = rb if isinstance(rb, dict) and rb.get("lo") is not None else None
        g["inv"] = e.get("invalidation") if isinstance(e.get("invalidation"), dict) else {"price": e.get("invalidation")}
        g["entry_ref"] = _f(e.get("entry_ref"))
        g["trigger"] = (pd.Timestamp(e.get("trigger_ts")) if e.get("trigger_ts") else dec - pd.Timedelta(minutes=5), dec)
        tr = e.get("trigger") or {}
        g["line_values5"] = tr.get("line_values")
    else:
        g["trigger"] = (dec - pd.Timedelta(minutes=5), dec)
        g["rb"] = refined_for_visit(V, c, g)
    # the next area: Levels.snapshot at k, the opposite role beyond the price at the decision (target side)
    ref = last_close(V, dec)
    g["price"] = ref
    try:
        opp = []
        for x in V.levels.snapshot(k):
            if str(x.get("state") or "").upper() in ("BROKEN", "DEAD") or not x.get("trade_location", True) or ref is None:
                continue
            if (d < 0 and x.get("role") == "support" and float(x["hi"]) < ref) or (d > 0 and x.get("role") == "resistance" and float(x["lo"]) > ref):
                opp.append(x)
        if opp:
            n = min(opp, key=lambda x: (float(x["lo"]) - ref) if d > 0 else (ref - float(x["hi"])))
            g["next"] = {kk: n.get(kk) for kk in ("id", "tf", "role", "lo", "hi", "state")}
    except Exception:                                                      # noqa: BLE001 — display
        pass
    g["approach"] = approach_of(V, c, g)
    return g


def last_close(V, dec):
    A = V.ltf if isinstance(getattr(V, "ltf", None), dict) else None
    if A is not None and len(A.get("end", [])):
        i = int(np.searchsorted(np.asarray(A["end"], "datetime64[ns]"), np.datetime64(pd.Timestamp(dec)), side="right")) - 1
        if i >= 0:
            return float(A["close"][i])
    k = ctx_bar(V, dec)
    return float(V.m15["close"].iloc[k]) if k >= 0 else None


def refined_for_visit(V, c, g):
    """The refined 15M base the reader reports for this area at the decision (entry_models5.Reader5.refined) — display only."""
    if g["kind"] != "area" or g["lo"] is None or c["kind"] != "visit":
        return None
    try:
        from . import entry_models5 as EM5
        F = V.trigger_frame()
        j = int(np.searchsorted(np.asarray(F.end, "datetime64[ns]"), np.datetime64(g["dec"]), side="right")) - 1
        R = EM5.Reader5(V, j)
        Lu = V.levels.by_uid(g["uid"]) if g.get("uid") and hasattr(V.levels, "by_uid") else None   # A5: this build's level of the place
        aid = Lu.id if Lu is not None else g["aid"]
        lvl = {"id": aid, "lo": g["lo"], "hi": g["hi"], "tf": g["tf"], "role": g["role"]}
        try:
            lvl.update({kk: v for kk, v in next(x for x in V.levels.snapshot(g["k"]) if x["id"] == int(aid)).items()
                        if kk not in ("lo", "hi")})
        except (StopIteration, TypeError, ValueError):
            pass
        rb = R.refined(g["k"], lvl, g["d"])
        return {"lo": float(rb["lo"]), "hi": float(rb["hi"]), "ts": str(rb.get("ts"))} if rb else None
    except Exception:                                                      # noqa: BLE001 — display only
        return None


def approach_of(V, c, g):
    """The side price approached the object from: the close of the 15M bar before the visit's first 15M bar vs the object (the area's
    band / the line's value there). ⇒ {ts, from: above | below | inside, y}."""
    vs = (c.get("entry") or {}).get("visit_start") if c["kind"] == "entry" else (c.get("armed") or {}).get("visit_start")
    if not vs:
        return None
    ts = _ts15(V)
    i = int(np.searchsorted(ts.to_numpy("datetime64[ns]"), np.datetime64(pd.Timestamp(vs))))
    if i <= 0 or i >= len(ts):
        return None
    pc = float(V.m15["close"].iloc[i - 1])
    if g["kind"] == "line":
        if not g.get("line"):
            return None
        from . import trendline as TL
        lo = hi = TL.line_value(g["line"], i - 1)
        y = TL.line_value(g["line"], i)
    else:
        lo, hi = g["lo"], g["hi"]
        y = None
    if lo is None:
        return None
    side = "above" if pc > hi else ("below" if pc < lo else "inside")
    return {"ts": str(ts[i]), "from": side, "y": y if y is not None else (hi if side == "above" else lo), "prev_close": pc}


# ================================================================================================================ panels (no look-ahead)
def _bucket_1h(t):
    t = pd.to_datetime(pd.Series(t))
    day = t.dt.normalize()
    return day + pd.Timedelta(hours=9, minutes=15) + ((t - day - pd.Timedelta(hours=9, minutes=15)) // pd.Timedelta(hours=1)) * pd.Timedelta(hours=1)


def panel_bars(V, dec, back15=90, ahead15=26, backh=70, aheadh=8, back5=54, ahead5=24, since=None, since15=None):
    """The three panels' candles around the decision: {"1H" | "15M" | "5M": DataFrame[timestamp, end, open, high, low, close, known]}.
    known = the bar closed at the decision (end ≤ dec); the 15M / 1H bar in progress and every later bar are known = False (drawn
    faded "after the decision"). 1H = the 15M bars grouped per hour (09:15 anchored); a 1H bar is known only when all its 15M bars are.
    `since` (a timestamp) widens the 1H window back to it (the object's lifecycle), `since15` the 15M window (the visit); capped."""
    dec = pd.Timestamp(dec)
    m = V.m15[["timestamp", "open", "high", "low", "close"]].copy().reset_index(drop=True)
    m["timestamp"] = pd.to_datetime(m["timestamp"])
    m["end"] = pd.to_datetime(V.bar_end).to_numpy()
    nb = int((m["end"] <= dec).sum())
    pos = lambda t: int(np.searchsorted(m["timestamp"].to_numpy("datetime64[ns]"), np.datetime64(pd.Timestamp(t))))   # noqa: E731
    if since is not None:
        backh = min(max(backh, (nb - pos(since)) // 4 + 6), 170)
    if since15 is not None:
        back15 = min(max(back15, nb - pos(since15) + 12), 200)
    w15 = m.iloc[max(0, nb - back15): nb + ahead15].copy()
    w15["known"] = w15["end"] <= dec
    hb = m.iloc[max(0, nb - backh * 4): nb + aheadh * 4].copy()
    hb["b"] = _bucket_1h(hb["timestamp"]).to_numpy()
    h = hb.groupby("b").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                            end=("end", "max"), n=("close", "size")).reset_index().rename(columns={"b": "timestamp"})
    h["known"] = h["end"] <= dec
    first_full = h.index[0] if len(h) else None                                     # the window's first hour may be cut: drop it
    if first_full is not None and len(h) > 1 and h["n"].iloc[0] < h["n"].max():
        h = h.iloc[1:]
    h = h.drop(columns="n")
    A = V.ltf
    f5 = pd.DataFrame({"timestamp": pd.to_datetime(A["start"]), "end": pd.to_datetime(A["end"]), "open": A["open"], "high": A["high"],
                       "low": A["low"], "close": A["close"]})
    n5 = int((f5["end"] <= dec).sum())
    w5 = f5.iloc[max(0, n5 - back5): n5 + ahead5].copy()
    w5["known"] = w5["end"] <= dec
    w5 = w5[w5["timestamp"].dt.normalize() >= w5["timestamp"].dt.normalize().max() - pd.Timedelta(days=4)]
    return {"1H": h.reset_index(drop=True), "15M": w15.reset_index(drop=True), "5M": w5.reset_index(drop=True)}


# ================================================================================================================ drawing
UP, DN = "#2f9e44", "#e03131"
SUPC, RESC = "#2b8a3e", "#c92a2a"
NEXTC, INVC, DECC, APPC, TRGC = "#1c7ed6", "#c92a2a", "#343a40", "#7048e8", "#f08c00"
EVC = {"born": "#1864ab", "broken": "#e8590c", "known": "#e8590c", "flip": "#9c36b5", "reclaim": "#2b8a3e", "dead": "#212529",
       "sweep": "#868e96"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


class Labels:
    """Collision-reduced text on one axis (the axis limits must be set first): each new label is moved up / down in steps of its own
    height until its box does not overlap an earlier label; after `tries` it stays where it was placed."""

    def __init__(self, ax):
        self.ax, self.boxes = ax, []
        self.r = ax.figure.canvas.get_renderer()

    def text(self, x, y, s, tries=8, prefer=1, **kw):
        kw.setdefault("fontsize", 7.5)
        kw.setdefault("zorder", 8)
        t = self.ax.text(x, y, s, **kw)
        bb = t.get_window_extent(self.r)
        inv = self.ax.transData.inverted()
        y_px = self.ax.transData.transform((x, y))[1]
        for k in range(1, tries + 1):
            if not any(bb.overlaps(o) for o in self.boxes):
                break
            off = bb.height * 1.08 * ((k + 1) // 2) * (prefer if k % 2 else -prefer)
            t.set_position((x, inv.transform((0, y_px + off))[1]))
            bb = t.get_window_extent(self.r)
        self.boxes.append(bb)
        return t


class Panel:
    def __init__(self, ax, bars, title):
        self.ax, self.b, self.title = ax, bars.reset_index(drop=True), title
        self.n = len(self.b)
        self.nb = int(self.b["known"].sum())
        self.ts = self.b["timestamp"].to_numpy("datetime64[ns]")
        self.L = Labels(ax)

    def x(self, t):
        i = int(np.searchsorted(self.ts, np.datetime64(pd.Timestamp(t)), side="right")) - 1
        return float(min(max(i, 0), max(self.n - 1, 0)))

    def limits(self, ylim):
        self.ax.set_ylim(*ylim)
        self.ax.set_xlim(-1, self.n + 0.5)

    def candles(self):
        for i, r in self.b.iterrows():
            a = 1.0 if r.known else 0.2
            col = UP if r.close >= r.open else DN
            self.ax.plot([i, i], [r.low, r.high], color=col, lw=0.8, alpha=a, zorder=3)
            self.ax.add_patch(_plt().Rectangle((i - 0.32, min(r.open, r.close)), 0.64, max(abs(r.close - r.open), 0.5), color=col,
                                               alpha=a, zorder=3))

    def finish(self, ylim, fmt):
        ax = self.ax
        if self.nb < self.n:
            ax.axvspan(self.nb - 0.5, self.n + 0.5, color="#dee2e6", alpha=0.45, zorder=0, lw=0)
            ax.text(self.nb + 0.2, ylim[1], " after the decision", fontsize=8, color="#495057", va="top", style="italic", zorder=9,
                    bbox=dict(fc="white", ec="#ced4da", alpha=0.9, pad=1.5))
        ax.axvline(self.nb - 0.5, color=DECC, lw=1.5, zorder=6)
        ax.text(self.nb - 0.7, ylim[1], "decision ", fontsize=8, color=DECC, va="top", ha="right", weight="bold", zorder=9)
        step = max(1, self.n // 7)
        idx = list(range(0, self.n, step))
        ax.set_xticks(idx)
        ax.set_xticklabels([pd.Timestamp(self.ts[i]).strftime(fmt) for i in idx], fontsize=6.5)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.14)
        ax.set_title(self.title, fontsize=9.3, loc="left")


def _ylim(b, keys, frac=0.07):
    lo, hi = float(b["low"].min()), float(b["high"].max())
    rng = max(hi - lo, 1.0)
    for y in keys:
        y = _f(y)
        if y is not None and lo - 1.0 * rng <= y <= hi + 1.0 * rng:
            lo, hi = min(lo, y), max(hi, y)
    p = (hi - lo) * frac
    return lo - p, hi + p * 1.8


def _band(P, lo, hi, x0, color, alpha, label=None, label_at="hi"):
    plt = _plt()
    x0 = max(-0.5, x0)
    if x0 < P.nb - 0.5:
        P.ax.add_patch(plt.Rectangle((x0, lo), P.nb - 0.5 - x0, max(hi - lo, 0.5), color=color, alpha=alpha, zorder=1, lw=0))
    if P.nb < P.n:
        P.ax.add_patch(plt.Rectangle((max(P.nb - 0.5, x0), lo), P.n + 1 - max(P.nb - 0.5, x0), max(hi - lo, 0.5), color=color,
                                     alpha=alpha * 0.35, zorder=1, lw=0))
    if label:
        P.L.text(max(x0, 0), lo if label_at == "lo" else hi, " " + label, color=color, va="top" if label_at == "lo" else "bottom",
                 bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.6))


def _offchart(P, ylim, y, color, label):
    y = _f(y)
    if y is None or ylim[0] <= y <= ylim[1]:
        return False
    up = y > ylim[1]
    yy = ylim[1] - (ylim[1] - ylim[0]) * 0.07 if up else ylim[0] + (ylim[1] - ylim[0]) * 0.03
    P.L.text(max(P.nb * 0.04, 0), yy, f"{'↑' if up else '↓'} {label} {y:,.0f} ({'above' if up else 'below'} the view)", color=color,
             fontsize=7.5, va="center")
    return True


def _hline(P, y, color, label, below=False):
    P.ax.plot([-0.5, P.nb - 0.5], [y, y], color=color, ls="--", lw=1.3, zorder=5)
    if P.nb < P.n:
        P.ax.plot([P.nb - 0.5, P.n], [y, y], color=color, ls="--", lw=0.9, alpha=0.35, zorder=5)
    P.L.text(P.nb - 1.2, y, f"{label} ", color=color, ha="right", va="top" if below else "bottom",
             bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.6))


def _line_y(g, V, P, tf):
    """The broken line's value at each panel bar (the reader's own 5M values where the entry carries them)."""
    ln = g.get("line")
    if not ln:
        return None
    ts15 = _ts15(V).to_numpy("datetime64[ns]")
    b1 = int(ln["p1"][0])
    v5 = {pd.Timestamp(a): float(b) for a, b in (g.get("line_values5") or [])} if tf == "5M" else {}
    ys = []
    for i in range(P.n):
        t0 = pd.Timestamp(P.ts[i])
        if t0 in v5:
            ys.append(v5[t0])
            continue
        pos = float(np.searchsorted(ts15, np.datetime64(t0), side="right") - 1)
        if tf == "5M":
            pos += ((t0 - pd.Timestamp(ts15[int(max(pos, 0))])) / pd.Timedelta(minutes=15))
        elif tf == "1H":
            pos += 1.5
        ys.append(float(ln["p1"][1]) + float(ln["slope"]) * (pos - b1) if pos >= b1 else None)
    return ys


def render_case(V, sym, c, out_png, g=None):
    """One case ⇒ PNG (1H on top, 15M + 5M below, a text strip). ⇒ meta {png, panels {tf: {known, n, last_known_end}}, …}."""
    plt = _plt()
    g = g or geometry(V, c)
    d = g["d"]
    marks = [pd.Timestamp(x[0]) for x in g["events"] if x[1] != "sweep"]   # the 1H window reaches back to the lifecycle (capped)
    vs = (c.get("entry") or {}).get("visit_start") if c["kind"] == "entry" else (c.get("armed") or {}).get("visit_start")
    B = panel_bars(V, g["dec"], since=min(marks) if marks else None, since15=vs)
    fig = plt.figure(figsize=(17, 12.4))
    gs = fig.add_gridspec(3, 2, height_ratios=[5.0, 5.4, 1.25], width_ratios=[1.45, 1], hspace=0.30, wspace=0.08)
    axes = {"1H": fig.add_subplot(gs[0, :]), "15M": fig.add_subplot(gs[1, 0]), "5M": fig.add_subplot(gs[1, 1])}
    axt = fig.add_subplot(gs[2, :])
    side = "bull put" if d > 0 else "bear call"
    e = c.get("entry")
    titles = {"1H": f"1H — {g['label']} · {side} · object with its lifecycle (events known at the decision)",
              "15M": "15M — the visit, the refined base, the invalidation, the next area (15M bar in progress = after the decision)",
              "5M": "5M trigger panel — " + ("T = the trigger candle" if e else "D = the decision candle (no trigger)")}
    P = {tf: Panel(axes[tf], B[tf], titles[tf]) for tf in ("1H", "15M", "5M")}
    obj_col = RESC if str(g.get("role")) == "resistance" else SUPC
    side_col = UP if d > 0 else DN
    inv = _f((g.get("inv") or {}).get("price"))
    nxt = g.get("next")
    rb = g.get("rb")
    meta = {"panels": {}}
    for tf, p in P.items():
        if not p.n:
            axes[tf].text(0.5, 0.5, f"no {tf} bars", transform=axes[tf].transAxes, ha="center")
            continue
        p.candles()
        keys = [g["lo"], g["hi"], inv] + ([rb["lo"], rb["hi"]] if rb else []) + ([nxt["lo"], nxt["hi"]] if nxt and tf != "5M" else [])
        ylim = _ylim(p.b, keys)
        p.limits(ylim)
        # the object
        if g["kind"] == "line":
            ys = _line_y(g, V, p, tf)
            if ys:
                xs = [i for i, y in enumerate(ys) if y is not None]
                yy = [ys[i] for i in xs]
                kn = [(x, y) for x, y in zip(xs, yy) if x < p.nb]
                af = [(x, y) for x, y in zip(xs, yy) if x >= p.nb - 1]
                if kn:
                    p.ax.plot(*zip(*kn), color=obj_col, lw=2.0, zorder=4)
                    p.L.text(kn[0][0], kn[0][1], f" {g['label']}", color=obj_col, va="bottom")
                if af:
                    p.ax.plot(*zip(*af), color=obj_col, lw=1.2, alpha=0.3, zorder=4)
        elif g["lo"] is not None:
            born = next((x[0] for x in g["events"] if x[1] == "born"), None)
            x0 = p.x(born) if born is not None and pd.Timestamp(born) >= pd.Timestamp(p.ts[0]) else -0.5
            _band(p, g["lo"], g["hi"], x0, obj_col, 0.10 if rb else 0.2, f"{g['label']}" + (" — context" if rb else ""),
                  label_at="lo" if d < 0 else "hi")
        if rb:
            x0 = p.x(rb.get("ts")) if rb.get("ts") and pd.Timestamp(rb["ts"]) >= pd.Timestamp(p.ts[0]) else -0.5
            _band(p, float(rb["lo"]), float(rb["hi"]), x0, side_col, 0.34, f"refined 15M base {px(rb['lo'])}–{px(rb['hi'])}",
                  label_at="hi" if d < 0 else "lo")
        if nxt and tf != "5M" and not _offchart(p, ylim, nxt["hi"] if d < 0 else nxt["lo"], NEXTC, "next area"):
            _band(p, float(nxt["lo"]), float(nxt["hi"]), -0.5, NEXTC, 0.16,
                  f"next area {nxt.get('tf')} {nxt.get('role')} {px(nxt['lo'])}–{px(nxt['hi'])}", label_at="lo" if d < 0 else "hi")
        if inv is not None and not _offchart(p, ylim, inv, INVC, "invalidation"):
            _hline(p, inv, INVC, f"invalidation {inv:,.2f}", below=d > 0)
        # lifecycle events known at the decision (15M / 1H only)
        if tf != "5M":
            for ts_e, kind, word in sorted(g["events"], key=lambda x: pd.Timestamp(x[0])):
                if pd.Timestamp(ts_e) < pd.Timestamp(p.ts[0]):
                    continue
                xe = p.x(ts_e)
                if xe >= p.nb:
                    continue
                col = EVC.get(kind, "#495057")
                p.ax.axvline(xe, color=col, lw=0.9, ls=(0, (3, 2)), alpha=0.8, zorder=2)
                if kind == "sweep":
                    continue
                p.L.text(xe, ylim[0] + (ylim[1] - ylim[0]) * 0.04, f" {word}\n {pd.Timestamp(ts_e):%d %b %H:%M}", color=col, fontsize=7,
                         prefer=1, bbox=dict(fc="white", ec=col, alpha=0.88, lw=0.6, pad=1.2))
            nsw = sum(1 for x in g["events"] if x[1] == "sweep")
            if nsw and tf == "1H":
                p.L.text(0, ylim[0] + (ylim[1] - ylim[0]) * 0.16, f" sweeps of the area known at the decision: {nsw} (grey dotted)",
                         color=EVC["sweep"], fontsize=7)
        # the approach side
        ap = g.get("approach")
        if ap and ap["from"] in ("above", "below") and tf != "1H":
            ta = pd.Timestamp(ap["ts"])
            if ta >= pd.Timestamp(p.ts[0]):
                xa = p.x(ta)
                if xa < p.nb:
                    dy = (ylim[1] - ylim[0]) * (0.16 if tf == "15M" else 0.12)
                    y0 = ap["y"] + dy if ap["from"] == "above" else ap["y"] - dy
                    p.ax.annotate("", (xa, ap["y"]), xytext=(xa - 1.5, y0),
                                  arrowprops=dict(arrowstyle="-|>,head_width=0.45,head_length=0.8", color=APPC, lw=2.4), zorder=10)
                    p.L.text(xa - 1.5, y0, f"approached from {ap['from']}", color=APPC, fontsize=8, weight="bold", ha="center",
                             va="bottom" if ap["from"] == "above" else "top")
        # the trigger / decision candle
        if tf == "5M":
            tr0, tr1 = g["trigger"]
            hit = [i for i in range(p.n) if pd.Timestamp(p.b["timestamp"].iloc[i]) >= tr0 and pd.Timestamp(p.b["end"].iloc[i]) <= tr1]
            if hit:
                i0, i1 = hit[0], hit[-1]
                lo_, hi_ = float(p.b["low"].iloc[i0:i1 + 1].min()), float(p.b["high"].iloc[i0:i1 + 1].max())
                p.ax.add_patch(plt.Rectangle((i0 - 0.5, lo_), i1 - i0 + 1, hi_ - lo_, fill=False, ec=TRGC if e else "#495057", lw=2.0, zorder=11))
                p.ax.text((i0 + i1) / 2, hi_, "T" if e else "D", color=TRGC if e else "#495057", fontsize=11, ha="center", va="bottom",
                          weight="bold", zorder=11)
            if e and g.get("entry_ref") is not None and hit:
                p.ax.annotate(f"{'▲' if d > 0 else '▼'} entry {g['entry_ref']:,.2f}", (hit[-1], g["entry_ref"]), textcoords="offset points",
                              xytext=(-95, 30 if d < 0 else -36), fontsize=9, color="#1864ab", weight="bold",
                              arrowprops=dict(arrowstyle="->", color="#1864ab"), zorder=12)
        elif tf == "15M" and p.nb < p.n:
            p.ax.axvspan(p.nb - 0.5, p.nb + 0.5, color="#fab005", alpha=0.22, zorder=0, lw=0)   # the 15M bar holding the 5M decision
        p.finish(ylim, "%d %b %H:%M" if tf != "5M" else "%d %H:%M")
        meta["panels"][tf] = {"n": p.n, "known": p.nb, "last_known_end": str(p.b["end"][p.b["known"]].max()) if p.nb else None,
                              "first_after_ts": str(p.b["timestamp"].iloc[p.nb]) if p.nb < p.n else None}
    # text strip (English)
    axt.axis("off")
    lc = "; ".join(f"{w} {pd.Timestamp(t):%d %b %H:%M}" for t, k_, w in sorted(g["events"], key=lambda x: pd.Timestamp(x[0])) if k_ != "sweep") or "none"
    nsw = sum(1 for x in g["events"] if x[1] == "sweep")
    lines = [f"{sym} #{c['n']} · decision = 5M close {g['dec']:%Y-%m-%d %H:%M} (the 15M context bar closed {pd.Timestamp(V.bar_end.iloc[g['k']]):%d %b %H:%M})"
             + (f" · approached from {g['approach']['from']}" if g.get("approach") else ""),
             f"Object: {g['label']} · lifecycle known at the decision: {lc}" + (f"; sweeps {nsw}" if nsw else "")
             + (f"; tests {g.get('tests')}" if g.get("tests") else "")]
    if e:
        lines.append(f"Entry: {e.get('model')} {e.get('name')} {side} at {px(e.get('entry_ref'))} · invalidation "
                     f"{px((g.get('inv') or {}).get('price'))} ({(g.get('inv') or {}).get('rule') or ''}) · next area "
                     + (f"{nxt.get('tf')} {nxt.get('role')} {px(nxt['lo'])}–{px(nxt['hi'])}" if nxt else "none known"))
    else:
        a = c.get("armed") or {}
        mods = " | ".join(f"{m}: {(s or {}).get('status')}" for m, s in (a.get("models") or {}).items())
        lines.append(f"Visit {c['first_ts'][5:16]} → last seen {c['bar_ts'][5:16]} ({c['n_rows']} rows) · models: {mods}"
                     + (f" · disarmed: {a.get('disarmed')}" if a.get("disarmed") else ""))
    axt.text(0, 1, "\n".join("\n".join(textwrap.wrap(x, 210)) for x in lines), fontsize=8.6, va="top", family="DejaVu Sans Mono")
    head = (f"#{c['n']} {sym} — " + (f"ENTRY {e.get('model')} {e.get('name')} {side}" if e else f"VISIT, no entry ({side})")
            + f" — {g['label']}")
    fig.suptitle(head, fontsize=12.5, x=0.07, ha="left", y=0.935, weight="bold")
    fig.savefig(out_png, dpi=78, bbox_inches="tight")
    plt.close(fig)
    meta.update(png=os.path.basename(out_png), dec=str(g["dec"]), label=g["label"], approach=g.get("approach"), rb=rb,
                inv=g.get("inv"), next=nxt, events=[(str(a_), b_, c_) for a_, b_, c_ in g["events"]])
    return meta


def render_all(V, sym, cases, out_dir, settings=None, errors=None, log=print):
    """Number + cap (plan), the Marathi line of every case, the PNG of every drawn case. Mutates `cases` (adds "list")."""
    lst = plan(cases, settings)
    for c in lst:
        c["mr"] = marathi_line(c)
        if not c.get("draw"):
            continue
        fn = os.path.join(out_dir, f"{sym}_{c['n']:02d}_{c['kind']}.png")
        try:
            c["chart"] = render_case(V, sym, c, fn)
        except Exception as exc:                                           # noqa: BLE001 — one chart never stops the gallery
            c["chart_error"] = f"{type(exc).__name__}: {exc}"
            (errors if errors is not None else []).append(f"#{c['n']}: {c['chart_error']}")
            log(f"⚠️ {sym} #{c['n']}: chart failed: {c['chart_error']}")
    cases["list"] = lst
    return lst


def plan_only(sym, cases, settings=None):
    """Without V (no charts): numbering + Marathi lines (a symbol whose V22 failed is still listed)."""
    lst = plan(cases, settings)
    for c in lst:
        c["mr"] = marathi_line(c)
        c["draw"] = False
        c.setdefault("why_not_drawn", "no chart (V22 not built)")
    cases["list"] = lst
    return lst


# ================================================================================================================ HTML
def summary(groups):
    ne = sum(len(g["cases"].get("entries") or []) for g in groups)
    nv = sum(len(g["cases"].get("visits") or []) for g in groups)
    syms = [g["symbol"] for g in groups]
    return {"symbols": syms, "entries": ne, "visits": nv,
            "line_en": f"{ne} entries · {nv} visits without an entry · {', '.join(syms) or 'no symbol'}",
            "line_mr": f"entries {ne} · entry नसलेले visits {nv} · {', '.join(syms) or 'symbol नाही'}"}


CSS = """:root{--bg:#f8f9fa;--fg:#212529;--card:#fff;--mut:#6c757d;--line:#dee2e6;--acc:#1864ab}
@media (prefers-color-scheme:dark){:root{--bg:#1b1e21;--fg:#e9ecef;--card:#25292d;--mut:#adb5bd;--line:#3a3f44;--acc:#74c0fc}}
body{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,"Noto Sans Devanagari",sans-serif;margin:0;padding:16px}
main{max-width:1240px;margin:0 auto}h1{font-size:1.5em;margin:.2em 0}h2{margin-top:1.6em;border-bottom:1px solid var(--line)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:14px 0}
.mr{font-size:1.05em;margin:.4em 0}.mut{color:var(--mut);font-size:.9em}img{max-width:100%;height:auto;border-radius:4px}
table{border-collapse:collapse;width:100%;font-size:.92em}td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
.tag{display:inline-block;padding:0 6px;border-radius:4px;font-size:.85em;background:#e7f5ff;color:#1864ab}.tag.v{background:#fff4e6;color:#d9480f}
a{color:var(--acc)}"""


def write_html(out_dir, day, groups, settings=None):
    day = str(pd.Timestamp(day).date())
    sm = summary(groups)
    esc = lambda s: _html.escape(str(s), quote=True)                      # noqa: E731
    h = [f"<!doctype html><html lang='mr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Reading gallery {day}</title><style>{CSS}</style></head><body><main>",
         f"<h1>Today's reading gallery — {day}</h1>",
         f"<p class='mr'>आजची reading gallery: {esc(sm['line_mr'])}. प्रत्येक case ला क्रमांक आहे — दुरुस्ती अशी पाठवा: "
         f"<b>“#3: …”</b>.</p>",
         "<p class='mut'>Charts: 1H (top, the object and its lifecycle known at the decision) · 15M (the visit, refined base, invalidation, "
         "next area) · 5M (the trigger / decision candle). Bars after the decision are faded under “after the decision” — nothing "
         "drawn as known comes from after it. Chart text English; the line under each chart = the reader's own reason in Marathi.</p>"]
    for g in groups:
        lst = g["cases"].get("list") or []
        ne, nv = len(g["cases"].get("entries") or []), len(g["cases"].get("visits") or [])
        h.append(f"<h2>{esc(g['symbol'])} — entries {ne} · visits without an entry {nv} · engine rows {g['cases'].get('rows', 0)}</h2>")
        if g.get("note"):
            h.append(f"<p class='mut'>{esc(g['note'])}</p>")
        if g["cases"].get("errors"):
            h.append(f"<p class='mut'>engine error rows this session: {len(g['cases']['errors'])} (first: "
                     f"{esc(g['cases']['errors'][0]['bar_ts'][11:16])} {esc(g['cases']['errors'][0]['reason'][:120])})</p>")
        for x in g.get("errors") or []:
            h.append(f"<p class='mut'>⚠️ {esc(x)}</p>")
        if not lst:
            h.append("<p class='mr'>या session मध्ये entry किंवा armed क्षेत्राचा visit नाही.</p>")
            continue
        h.append("<table><tr><th>#</th><th>kind</th><th>decision</th><th>reader (मराठी)</th></tr>")
        for c in lst:
            kind = (f"<span class='tag'>entry {esc(c['entry'].get('model'))}</span>" if c["kind"] == "entry" else "<span class='tag v'>visit</span>")
            h.append(f"<tr><td><a href='#{esc(g['symbol'])}-{c['n']}'>#{c['n']}</a></td><td>{kind}</td><td>{esc(str(c['bar_ts'])[11:16])}</td>"
                     f"<td>{esc(c['mr'])}</td></tr>")
        h.append("</table>")
        for c in lst:
            h.append(f"<div class='card' id='{esc(g['symbol'])}-{c['n']}'><b>#{c['n']}</b> · {esc(g['symbol'])} · "
                     + (f"ENTRY {esc(c['entry'].get('model'))} {esc(c['entry'].get('name'))}" if c["kind"] == "entry" else "VISIT (no entry)")
                     + f" · decision {esc(str(c['bar_ts'])[:16])}")
            if c.get("chart"):
                h.append(f"<div><img loading='lazy' src='{esc(c['chart']['png'])}' alt='#{c['n']} 1H + 15M + 5M'></div>")
            elif c.get("chart_error"):
                h.append(f"<p class='mut'>chart failed: {esc(c['chart_error'])}</p>")
            elif c.get("why_not_drawn"):
                h.append(f"<p class='mut'>{esc(c['why_not_drawn'])}</p>")
            h.append(f"<p class='mr'>{esc(c['mr'])}</p>")
            if c["kind"] == "entry":
                h.append(f"<p class='mut'>bots: {esc(used_mr(c.get('used')))}</p>")
            h.append("</div>")
    h.append("</main></body></html>")
    p = os.path.join(out_dir, "index.html")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h))
    return p
