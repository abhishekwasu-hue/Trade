"""bots_common/chart_reading_text.py — Message 2 of the daily Chart Reading Report (Abhi's order, owner-orders DECISIONS 35): the READING
in plain words, one section per concept of the closed list (Price Action Standard §1 MTF, §2 A–L, §3 models), Marathi by default
(dashboard setting `chart_reading_language` mr / en).

Rules (the order + CLAUDE.md):
  • every line comes from a fact of `decision3.chart_reading.collect` (each line keeps its fact's `src`); no new rule, score or number;
  • a concept with nothing to say is left out (no empty heading);
  • no buy / sell / target / stop words; areas as ranges (lo–hi); no day / date / session / clock framing in the reading — the header's
    "for the next session" is only the operational send time;
  • it fits one Telegram message (TELEGRAM_LIMIT, the platform's limit): `detail = short` keeps the main line of each section, `full`
    every line; when it is still too long, the lowest sections' extra lines go first, then whole sections from the bottom (the plan and
    the link always stay), and the last line points to the dashboard page with the full detail;
  • execution stays the dashboard settings (said in the plan section).
Display only — never an order, a gate or a reading."""
import re

TELEGRAM_LIMIT = 4096                                                      # Telegram's own message limit (platform, not a reading number)
LANGS = ("mr", "en")
DETAILS = ("short", "full")
RULE = "━━━━━━━━━━━━━━━━"

# words that must never appear in the reading (the order's rule) — EN and the Marathi forms
FORBIDDEN = re.compile(r"\b(buy|buying|sell|selling|target|targets|stop|stops|stop-loss|sl)\b|खरेदी|विक्री|टार्गेट|स्टॉप", re.I)
# day / date / clock framing in the reading (the header line is exempt)
DATE_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\b|\b\d{1,2} (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
                     r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|yesterday|tomorrow|session|intraday)\b|"
                     r"आज|काल|उद्या|सोमवार|मंगळवार|बुधवार|गुरुवार|शुक्रवार", re.I)


def n(x):
    return "NA" if x is None else f"{float(x):,.0f}"


def rng(lo, hi):
    if lo is None or hi is None:
        return "NA"
    return n(lo) if round(float(lo)) == round(float(hi)) else f"{n(lo)}–{n(hi)}"


T = {
    "head": {"en": "📘 {sym} — chart reading (for the next session)", "mr": "📘 {sym} — chart वाचन (पुढच्या session साठी)"},
    "last": {"en": "Last close {x}", "mr": "शेवटचा close {x}"},
    "s_big": {"en": "🧭 Big picture", "mr": "🧭 मोठं चित्र"},
    "s_struct": {"en": "🏗 Structure (A, B)", "mr": "🏗 रचना (A, B)"},
    "s_areas": {"en": "🧱 Areas (C) — what the engine watches", "mr": "🧱 Areas (C) — engine काय पाहतो"},
    "s_liq": {"en": "💧 Liquidity (D)", "mr": "💧 Liquidity (D)"},
    "s_lines": {"en": "📐 Lines · patterns (E, H) · confluence (F)", "mr": "📐 रेषा · patterns (E, H) · confluence (F)"},
    "s_vol": {"en": "📊 Volume (I) · RSI (J)", "mr": "📊 Volume (I) · RSI (J)"},
    "s_brk": {"en": "🔀 Breakout / range (K, L)", "mr": "🔀 Breakout / range (K, L)"},
    "s_wave": {"en": "🌊 Wave context", "mr": "🌊 Wave context"},
    "s_plan": {"en": "🎯 What the engine waits for (a plan, not a signal)", "mr": "🎯 Engine कशाची वाट पाहतो (plan, signal नाही)"},
    "s_vision": {"en": "👁 Vision second opinion (info only)", "mr": "👁 Vision चं दुसरं मत (फक्त माहिती)"},
    "link": {"en": "Full report → {link}", "mr": "पूर्ण report → {link}"},
    "more": {"en": "… more on the dashboard page", "mr": "… बाकी dashboard पानावर"},
}
STATE = {   # mtf_state vocabulary × the timeframe's trend
    ("correction in progress", "UP"): {"en": "correction inside an up-trend", "mr": "up-trend मधलं correction"},
    ("correction in progress", "DOWN"): {"en": "correction inside a down-trend", "mr": "down-trend मधलं correction"},
    ("trending up", None): {"en": "trending up", "mr": "trend वर (up)"},
    ("trending down", None): {"en": "trending down", "mr": "trend खाली (down)"},
    ("range", None): {"en": "range", "mr": "range"},
    ("unclear", None): {"en": "unclear (the swings give no state yet)", "mr": "अस्पष्ट (swings अजून state देत नाहीत)"},
}
DIRW = {"up": {"en": "↑", "mr": "↑"}, "down": {"en": "↓", "mr": "↓"}}
AREA_STATE = {"ACTIVE": "FRESH", "TESTED": "TESTED", "FLIPPED": "FLIPPED", "BROKEN": "BROKEN", "DEAD": "DEAD"}
ROLE_WORD = {"support": {"en": "support", "mr": "support"}, "resistance": {"en": "resistance", "mr": "resistance"}}
MODEL_STATUS = {"passed": {"en": "passed", "mr": "गेला"}, "waiting": {"en": "waiting", "mr": "वाट"}, "fired": {"en": "FIRED", "mr": "FIRED"},
                "fired_earlier": {"en": "fired earlier in this visit", "mr": "या visit मध्ये आधीच fired"},
                "disarmed": {"en": "disarmed", "mr": "disarmed"}, "off": {"en": "off", "mr": "बंद"},
                "cluster_consumed": {"en": "used at this place", "mr": "या जागी वापरला"},
                "blocked_data_problem": {"en": "data problem (no entry)", "mr": "data problem (entry नाही)"},
                "fired_outside_hours": {"en": "outside the entry hours (no entry)", "mr": "entry hours बाहेर (entry नाही)"}}


def tr(key, lang, **kw):
    return T[key][lang].format(**kw)


def L(text, src, main=False):
    return {"text": text, "src": src, "main": bool(main)}


def state_words(st, trend, lang, band=None):
    x = STATE.get((st, trend)) or STATE.get((st, None))
    w = x[lang] if x else (st or "NA")
    if st == "range" and band and band[0] is not None:
        w += f" {rng(band[0], band[1])}"
    return w


def area_words(a, lang, with_id=True):
    """"🔴 1H supply 55,699–55,970 · FLIPPED (was support) · tested 8× · swept" (state words from the K4 lifecycle)."""
    if not a:
        return ""
    em = "🔴" if a["kind"] == "supply" else "🟢" if a["kind"] == "demand" else "▫️"
    tf = {"D": "Daily", "W": "Weekly"}.get(a["tf"], a["tf"])
    st = AREA_STATE.get(a["state"], a["state"])
    plain = a["state"] in ("ACTIVE", "TESTED")
    if plain and a.get("tests"):
        st = f"TESTED {a['tests']}×"
    bits = [f"{em} {tf} {a['kind']} {rng(a['lo'], a['hi'])}", st]
    if a.get("was"):
        bits[-1] += f" ({'was' if lang == 'en' else 'आधी'} {ROLE_WORD[a['was']][lang]})"
    if a.get("tests") and not plain:
        bits.append(f"tested {a['tests']}×" if lang == "en" else f"{a['tests']}× tested")
    if a.get("sweeps"):
        bits.append("swept, back inside" if lang == "en" else "swept, परत आत")
    s = " · ".join(bits)
    return s + (f" [#{a['id']}]" if with_id and a.get("id") is not None else "")


# ------------------------------------------------------------------------------------------------------------------------ sections
def sec_big(f, lang):
    bp = f.get("big_picture") or {}
    tfs, d = bp.get("tfs") or {}, bp.get("daily") or {}
    out = []
    w = tfs.get("W") or {}
    if w.get("state"):
        out.append(L(f"• Weekly: {state_words(w['state'], w.get('trend'), lang, w.get('band'))}", "mtf_state.tfs[W]", True))
    if d.get("trend"):
        bits = [f"• Daily: {d['trend']}"]
        if d.get("phase"):
            bits.append(str(d["phase"]))
        if d.get("protected") is not None:
            k = {"H": "high", "L": "low"}.get(d.get("protected_kind"), "")
            bits.append((f"protected {k} {n(d['protected'])}" if lang == "en" else f"protected {k} {n(d['protected'])}").replace("  ", " "))
        out.append(L(" · ".join(bits), "decision row ① (daily.fold_impulse)", True))
    h, m = tfs.get("1H") or {}, tfs.get("15M") or {}
    if h.get("state") or m.get("state"):
        out.append(L(f"• 1H: {state_words(h.get('state'), h.get('trend'), lang, h.get('band'))} · 15M: "
                     f"{state_words(m.get('state'), m.get('trend'), lang, m.get('band'))}", "mtf_state.tfs[1H / 15M]", True))
    rel = bp.get("agreement") or {}
    if rel and bp.get("side") in ("UP", "DOWN"):
        groups = {}
        for tf, r in rel.items():
            if r != "reference":
                groups.setdefault(r, []).append(tf)
        word = {"agrees": {"en": "agree", "mr": "सहमत"}, "correction": {"en": "in correction", "mr": "correction मध्ये"},
                "against": {"en": "against", "mr": "विरुद्ध"}, "range": {"en": "range", "mr": "range"},
                "unclear": {"en": "unclear", "mr": "अस्पष्ट"}}
        parts = [f"{word.get(k, {}).get(lang, k)}: {', '.join(v)}" for k, v in groups.items()]
        out.append(L(("• With the Daily side " if lang == "en" else "• Daily बाजूशी ") + f"{bp['side']}: " + " · ".join(parts),
                     "mtf_state.agreement"))
    return out


def _event_words(e, lang):
    dirn = DIRW.get(e.get("dir"), {}).get(lang, "")
    side = ("above" if e.get("dir") == "up" else "below") if lang == "en" else ("वर" if e.get("dir") == "up" else "खाली")
    if lang == "en":
        return f"• Last {e['tf']} event: {e['type']} {dirn} (close {side} {n(e['level'])})"
    return f"• {e['tf']} वरचा शेवटचा event: {e['type']} {dirn} ({n(e['level'])} च्या {side} close)"


LEG_MEASURE = {
    "body": {"impulse": {"en": "larger bodies", "mr": "मोठे bodies"}, "correction": {"en": "smaller bodies", "mr": "लहान bodies"}},
    "overlap": {"impulse": {"en": "little overlap", "mr": "कमी overlap"}, "correction": {"en": "overlapping", "mr": "overlapping candles"}},
    "volume": {"impulse": {"en": "more FUT volume per bar", "mr": "प्रति bar जास्त FUT volume"},
               "correction": {"en": "less FUT volume per bar", "mr": "प्रति bar कमी FUT volume"}},
}
LEG_VERDICT = {"impulse": {"en": "impulsive", "mr": "impulsive"}, "correction": {"en": "corrective", "mr": "corrective"},
               "mixed": {"en": "mixed", "mr": "mixed"}}


def sec_struct(f, lang):
    st = f.get("structure") or {}
    out = []
    for i, e in enumerate(st.get("events") or ()):
        if e["tf"] == "D":
            continue
        out.append(L(_event_words(e, lang), e["src"], i == 0))
    legs = []
    for lg in st.get("legs") or ():
        ms = [LEG_MEASURE[k][v][lang] for k, v in (lg.get("measures") or {}).items() if k in LEG_MEASURE and v in LEG_MEASURE[k]]
        dirw = {"up": {"en": "the up-leg", "mr": "वरचा leg"}, "down": {"en": "the down-leg", "mr": "खालचा leg"}}.get(lg["dir"], {})
        so_far = "" if lg.get("complete") else (" (so far)" if lang == "en" else " (आतापर्यंत)")
        legs.append(f"{dirw.get(lang, lg['dir'])}{so_far} {LEG_VERDICT.get(lg['verdict'], {}).get(lang, lg['verdict'])}"
                    + (f" ({', '.join(ms)})" if ms else ""))
    if legs:
        out.append(L(("• Legs (1H): " if lang == "en" else "• Legs (1H): ") + "; ".join(legs), "legs_compare.tfs[1H].legs", True))
    return out


def said_ids(f):
    """The areas this message names: the nearest + the next trade-side area, the next opposite area, the Daily / Weekly ones."""
    A = f.get("areas") or {}
    watch = sorted(A.get("watch") or (), key=lambda a: a["dist"])
    o = A.get("next_opposite")
    return {a["id"] for a in watch[:2]} | ({o["id"]} if o else set()) | {a["id"] for a in A.get("htf") or ()}


def sec_areas(f, lang, detail):
    A = f.get("areas") or {}
    watch = sorted(A.get("watch") or (), key=lambda a: a["dist"])
    out = []
    if watch:
        out.append(L("• " + area_words(watch[0], lang), "levels.snapshot (K4) · decision row watch_list", True))
        if len(watch) > 1:
            nx = ("next" if lang == "en" else "पुढचा")
            out.append(L(f"• {nx}: " + area_words(watch[1], lang), "levels.snapshot (K4) · decision row watch_list"))
        if len(watch) > 2:
            rest = len(watch) - 2
            out.append(L((f"• +{rest} more trade-side areas ahead (dashboard page)" if lang == "en"
                          else f"• पुढे आणखी {rest} trade-बाजूचे areas (dashboard पान)"), "decision row watch_list"))
    o = A.get("next_opposite")
    if o:
        out.append(L(("• next opposite area: " if lang == "en" else "• विरुद्ध बाजूचा पुढचा area: ") + area_words(o, lang),
                     "levels.snapshot (K4) · next opposite role", True))
    for i, a in enumerate(A.get("htf") or ()):
        out.append(L("• " + area_words(a, lang), "levels.snapshot (Daily / Weekly)", i == 0))
    said = said_ids(f)
    dups = [g for g in A.get("duplicates") or () if set(g["ids"]) & said]          # only at the places this message names
    if dups:
        for g in dups:
            ids = ", ".join(f"#{i}" for i in g["ids"])
            out.append(L((f"• Reading check: {len(g['ids'])} overlapping {g['tf']} {g['kind']} areas {rng(g['lo'], g['hi'])} ({ids}) = one "
                          f"place (counted once, never merged — Z-1u)") if lang == "en" else
                         (f"• वाचन तपासणी: {g['tf']} {g['kind']} चे {len(g['ids'])} एकमेकांवर येणारे areas {rng(g['lo'], g['hi'])} ({ids}) = "
                          f"एकच जागा (एकदाच मोजली, कधीच merge नाही — Z-1u)"), g["src"], g is dups[0]))
    elif watch or o:
        out.append(L("• Reading check: no duplicate area at the shown places" if lang == "en"
                     else "• वाचन तपासणी: दाखवलेल्या जागी duplicate area नाही", "levels.snapshot (Z-1u counter)", True))
    return out


def sec_liq(f, lang):
    q = f.get("liquidity") or {}
    out, parts = [], []
    for side in ("above", "below"):
        x = q.get(side)
        if not x:
            continue
        what = (("equal highs" if side == "above" else "equal lows") if x.get("equal") else
                ("swing high" if side == "above" else "swing low"))
        head = ({"above": "Above", "below": "Below"}[side] if lang == "en" else {"above": "वर", "below": "खाली"}[side])
        parts.append(f"{head}: {what} {'≈ ' if x.get('equal') else ''}{n(x['price'])} ({'resting' if lang == 'en' else 'अजून घेतलेली नाही'})")
    if parts:
        out.append(L("• " + " · ".join(parts), "liquidity_pa.obvious", True))
    s = q.get("sweep")
    if s:
        if lang == "en":
            how = "and closed back inside" if s["state"] == "swept" else "— a failed breakout, closed back (trapped)"
            out.append(L(f"• Last sweep: price went {s['beyond']} {n(s['pool'])} to {n(s['extreme'])} {how}", s["src"], True))
        else:
            how = "आणि परत आत close" if s["state"] == "swept" else "— अयशस्वी breakout, परत आत close (trapped)"
            side = "वर" if s["beyond"] == "above" else "खाली"
            out.append(L(f"• शेवटचा sweep: किंमत {n(s['pool'])} च्या {side} {n(s['extreme'])} पर्यंत गेली {how}", s["src"], True))
    return out


def _pieces_words(c, lang):
    out = []
    for p in c.get("pieces") or ():
        w = p.get("what")
        if w == "htf_band":
            out.append(f"{ {'D': 'Daily', 'W': 'Weekly'}.get(p.get('tf'), p.get('tf'))} {rng(p.get('lo'), p.get('hi'))}")
        elif w == "fib":
            out.append(f"Fib {round(float(p['ratio']) * 100, 1):g}% {n(p.get('price'))}" if p.get("ratio") is not None else "Fib")
        elif w == "imbalance":
            out.append(f"imbalance {p.get('tf')} {rng(p.get('lo'), p.get('hi'))}")
        elif w == "line":
            out.append("a line (touch point)" if lang == "en" else "रेषा (touch point)")
        elif w == "liquidity":
            out.append(f"liquidity {n(p.get('price'))}")
    return list(dict.fromkeys(out))


def shown_patterns(f, detail):
    """The latest pattern (short); full: + the patterns whose boundary is the next one in price's path above / below (comparison)."""
    pats = f.get("patterns") or []
    if not pats:
        return []
    out = [pats[0]]
    if detail == "full":
        c = float(f.get("last_close") or 0)
        for side in (1, -1):
            best = None
            for p in pats:
                for ln in p.get("lines") or ():
                    v = ln.get("value")
                    if v is not None and (v - c) * side > 0 and (best is None or abs(v - c) < best[0]):
                        best = (abs(v - c), p)
            if best and best[1] not in out:
                out.append(best[1])
    return out


PAT_STATE = {"forming": {"en": "forming", "mr": "बनतोय"}, "broken": {"en": "broken (close beyond + swing beyond)", "mr": "तुटला (पलीकडे close + swing)"},
             "failed": {"en": "failed", "mr": "अयशस्वी"}, "retest": {"en": "retest", "mr": "retest"}}


def sec_lines(f, lang, detail):
    li = f.get("lines") or {}
    out = []
    chans = sorted(li.get("channels") or (), key=lambda c: 0 if c.get("tf") == "1H" else 1)
    for i, c in enumerate(chans):
        sl = {"falling": {"en": "falling", "mr": "खाली जाणारा"}, "rising": {"en": "rising", "mr": "वर जाणारा"}}.get(c.get("slope"), {})
        if lang == "en":
            txt = (f"• {c['tf']} {sl.get('en', c.get('slope'))} channel (price inside): upper {n(c['upper'])} · lower {n(c['lower'])}"
                   + (f" · main line touched {c['touches']}×" if c.get("touches") else ""))
        else:
            txt = (f"• {c['tf']} {sl.get('mr', c.get('slope'))} channel (किंमत आत): वरची रेषा {n(c['upper'])} · खालची {n(c['lower'])}"
                   + (f" · मुख्य रेषेला {c['touches']}× touch" if c.get("touches") else ""))
        out.append(L(txt, c["src"], i == 0))
    for side in ("above", "below"):
        x = li.get(side)
        if not x:
            continue
        if lang == "en":
            txt = f"• Next line {side}: {x['tf']} {x.get('family')} ≈ {n(x['value'])} ({x['touches']} touches)"
        else:
            txt = f"• {'वरची' if side == 'above' else 'खालची'} पुढची रेषा: {x['tf']} {x.get('family')} ≈ {n(x['value'])} ({x['touches']} touches)"
        out.append(L(txt, x["src"], not out))
    pats = shown_patterns(f, detail)
    for i, p in enumerate(pats):
        bd = ", ".join(f"{k} {v}" for k, v in (p.get("boundaries") or {}).items())
        nm = p["name"] + ("" if p.get("named") else (" (candidate)" if lang == "en" else " (candidate)"))
        st = PAT_STATE.get(p.get("state"), {}).get(lang, p.get("state"))
        out.append(L((f"• Pattern {p.get('tf')}: {nm} — {st}" if lang == "en" else f"• Pattern {p.get('tf')}: {nm} — {st}")
                     + (f" ({bd})" if bd else ""), p["src"], not out and i == 0))
    said = said_ids(f)
    for c in f.get("confluence") or ():
        if c.get("id") not in said:
            continue
        pw = _pieces_words(c, lang)
        if not pw:
            continue
        if lang == "en":
            txt = f"• Confluence: the {c['kind']} {rng(c['lo'], c['hi'])} lies on " + " · ".join(pw)
        else:
            txt = f"• Confluence: {c['kind']} {rng(c['lo'], c['hi'])} वर " + " · ".join(pw)
        out.append(L(txt, c["src"], True))
        if detail == "short":
            break
    return out


PULLBACK = {"lower": {"en": "lower", "mr": "कमी"}, "higher": {"en": "higher", "mr": "जास्त"}, "equal": {"en": "the same", "mr": "तेवढाच"}}
EFFORT = {"in harmony": {"en": "effort and result in harmony", "mr": "effort आणि result जुळतात"},
          "effort without result": {"en": "effort without result (more volume, less progress)", "mr": "effort without result (जास्त volume, कमी प्रगती)"},
          "result with ease": {"en": "result with ease (less volume, more progress)", "mr": "result with ease (कमी volume, जास्त प्रगती)"},
          "effort without result (candle)": {"en": "a candle of effort without result", "mr": "effort without result ची candle"}}


def sec_vol(f, lang):
    v = f.get("volume") or {}
    out = []
    if v.get("missing"):
        out.append(L("• FUT volume missing — a data problem (no entry); never spot volume" if lang == "en"
                     else "• FUT volume नाही — data problem (entry नाही); spot volume कधीच नाही", v.get("src", "volume_read"), True))
    else:
        pb = v.get("pullback") or {}
        dirw = {1: ("up", "वर जाणाऱ्या"), -1: ("down", "खाली जाणाऱ्या")}.get(pb.get("impulse_dir"), ("", ""))
        if pb.get("state") in PULLBACK:
            if lang == "en":
                txt = (f"• The pullback came on {PULLBACK[pb['state']]['en']} FUT volume than the impulse {dirw[0]} "
                       f"(per bar {n(pb.get('pullback_avg'))} vs {n(pb.get('impulse_avg'))})")
            else:
                txt = (f"• Pullback {dirw[1]} impulse पेक्षा {PULLBACK[pb['state']]['mr']} FUT volume वर आला "
                       f"(प्रति bar {n(pb.get('pullback_avg'))} विरुद्ध {n(pb.get('impulse_avg'))})")
            out.append(L(txt, v["src"], True))
        elif pb.get("state") == "beyond":
            out.append(L("• Price went beyond the last impulse's start — not a pullback of that leg (volume compared leg by leg)"
                         if lang == "en" else "• किंमत शेवटच्या impulse च्या सुरुवातीपलीकडे गेली — त्या leg चा pullback नाही", v["src"], True))
        if v.get("effort_result") in EFFORT:
            out.append(L(f"• {EFFORT[v['effort_result']][lang]}", v["src"], not out))
        if v.get("climax") in ("found", "forming"):
            out.append(L("• Volume climax " + ({"found": "found", "forming": "forming"}[v["climax"]] if lang == "en" else
                                               {"found": "दिसला", "forming": "बनतोय"}[v["climax"]]), v["src"]))
    r = f.get("rsi") or {}
    regs = {}
    for x in r.get("regular") or ():                                       # the latest pair per side (D1 / D2 duplicates once)
        if x["side"] not in regs or str(x["t1"]) > str(regs[x["side"]]["t1"]):
            regs[x["side"]] = x
    for j, (side, x) in enumerate(sorted(regs.items(), key=lambda kv: str(kv[1]["t1"]), reverse=True)):
        if lang == "en":
            txt = (f"• RSI: regular {'bearish' if side == 'bear' else 'bullish'} divergence {n(x['p0'])} → {n(x['p1'])} "
                   f"({x.get('state')}, evidence only)")
        else:
            txt = (f"• RSI: regular {'bearish' if side == 'bear' else 'bullish'} divergence {n(x['p0'])} → {n(x['p1'])} "
                   f"({x.get('state')}, फक्त पुरावा)")
        out.append(L(txt, x["src"], j == 0))
    h = r.get("hidden")
    if h and h.get("found") is not None:
        if h["found"]:
            out.append(L((f"• RSI: hidden {'bearish' if h['side'] == 'bear' else 'bullish'} divergence (continuation evidence)"
                          if lang == "en" else f"• RSI: hidden {'bearish' if h['side'] == 'bear' else 'bullish'} divergence (continuation पुरावा)"),
                         h["src"]))
        elif not regs:
            out.append(L("• RSI: no divergence pair (regular or hidden)" if lang == "en" else "• RSI: divergence pair नाही (regular / hidden)",
                         h["src"]))
    return out


def sec_brk(f, lang, detail):
    b = f.get("breakout_range") or {}
    out = []
    if b.get("in_range") and b.get("edges"):
        es = {e["edge"]: e for e in b["edges"]}
        lo, up = es.get("lower"), es.get("upper")
        tf = (lo or up)["tf"]
        txt = (f"• Range ({tf}, from structure): edges {rng(lo['lo'], lo['hi']) if lo else 'NA'} / {rng(up['lo'], up['hi']) if up else 'NA'}"
               if lang == "en" else
               f"• Range ({tf}, रचनेवरून): कडा {rng(lo['lo'], lo['hi']) if lo else 'NA'} / {rng(up['lo'], up['hi']) if up else 'NA'}")
        out.append(L(txt, "range_edges.range_state", True))
    pats = f.get("patterns") or []
    latest = pats[0] if pats else None
    brk = [x for x in b.get("breakouts") or () if latest and x["pattern"] == latest["name"]]
    acc = [x for x in brk if x["state"] == "accepted"]
    if acc:
        x = acc[0]
        out.append(L((f"• Accepted break: {x['pattern']} {x['boundary']} (close beyond + swing beyond) — context, never an entry"
                      if lang == "en" else f"• स्वीकारलेला break: {x['pattern']} {x['boundary']} (पलीकडे close + swing) — फक्त context, entry नाही"),
                     x["src"], True))
    elif latest:
        out.append(L("• No accepted breakout at the current pattern" if lang == "en" else "• चालू pattern वर स्वीकारलेला breakout नाही",
                     "patterns_pa boundaries", True))
    said = said_ids(f)
    for s in [x for x in b.get("sweeps") or () if x.get("id") in said][: (1 if detail == "short" else None)]:
        out.append(L((f"• Fakeout / sweep: the {s['kind']} {rng(s['lo'], s['hi'])} was swept {s['sweeps']}× and price came back inside "
                      f"(the area stays alive — K4)") if lang == "en" else
                     (f"• Fakeout / sweep: {s['kind']} {rng(s['lo'], s['hi'])} {s['sweeps']}× swept, किंमत परत आत (area जिवंत — K4)"),
                     s["src"]))
    return out


def sec_wave(f, lang):
    w = f.get("wave") or {}
    out = []
    bits = []
    if w.get("weekly_detail") and not DATE_RX.search(str(w["weekly_detail"])):   # reader prose: never with a date / clock word
        bits.append(f"Weekly: {w['weekly_detail']}")
    if w.get("daily_leg") or w.get("daily_phase"):
        bits.append(f"Daily leg {w.get('daily_leg') or 'NA'} · {w.get('daily_phase') or ''}".strip(" ·"))
    if w.get("corr_label"):
        bits.append(f"correction {w['corr_label']}")
    if bits:
        out.append(L("• " + " · ".join(bits), w.get("src", "wave_context"), True))
    mc = w.get("model_c")
    if mc:
        out.append(L((f"• Counter-trend C leg entries: model C {mc.upper()}" if lang == "en"
                      else f"• Counter-trend C leg entries: model C {mc.upper()}"), "model_c.is_on", not out))
    return out


SIDE_WORD = {"bear_call": {"en": "Bear-call side", "mr": "Bear-call बाजू"}, "bull_put": {"en": "Bull-put side", "mr": "Bull-put बाजू"}}
SEQ = {"en": "visit {r} → handover → commitment with FUT volume → 5-min CHoCH ⇒ E1–E4",
       "mr": "{r} ला visit → handover → FUT volume सह commitment → 5-min CHoCH ⇒ E1–E4"}


def sec_plan(f, lang):
    p = f.get("plan") or {}
    out = []
    n0 = p.get("nearest")
    sides = p.get("sides") or []
    if not n0:
        if sides:
            out.append(L(("• No trade-side area ahead of price — nothing to wait for" if lang == "en"
                          else "• किंमतीपुढे trade-बाजूचा area नाही — वाट पाहण्यासारखं काही नाही"), p.get("src", "entry_models"), True))
        else:
            out.append(L("• No trade side (the Daily state gives none)" if lang == "en" else "• Trade side नाही (Daily state देत नाही)",
                         p.get("src", "entry_models"), True))
    else:
        side = "bear_call" if n0["role"] == "resistance" else "bull_put"
        out.append(L(f"• {SIDE_WORD[side][lang]}: " + SEQ[lang].format(r=rng(n0["lo"], n0["hi"])), p["src"], True))
        rb = p.get("refined")
        if rb:
            if lang == "en":
                out.append(L(f"• Refined 15M base {rng(rb['lo'], rb['hi'])}: the trigger candle must trade into it; E1 invalidation beyond "
                             f"{n(rb['far'])}", rb["src"], True))
            else:
                out.append(L(f"• Refined 15M base {rng(rb['lo'], rb['hi'])}: trigger candle त्यात trade झाली पाहिजे; E1 invalidation "
                             f"{n(rb['far'])} च्या पलीकडे", rb["src"], True))
        else:
            out.append(L("• No refined 15M base inside the area yet — the models wait (RC2)" if lang == "en"
                         else "• Area मध्ये अजून refined 15M base नाही — models वाट पाहतात (RC2)", "entry_models.Reader.refined (RC2)"))
        ms = p.get("models") or {}
        if ms:
            st = " · ".join(f"{m} {MODEL_STATUS.get(x.get('status'), {}).get(lang, x.get('status'))}" for m, x in sorted(ms.items()))
            why = {"trade_side": {"en": " (price came in from the trade side — not a pullback, H2)",
                                  "mr": " (किंमत trade बाजूने आली — pullback नाही, H2)"},
                   "broken": {"en": " (the area broke in this visit)", "mr": " (या visit मध्ये area तुटला)"}}.get(p.get("disarmed") or "", {})
            out.append(L((f"• Entry models in the current visit: {st}" if lang == "en" else f"• चालू visit मधले entry models: {st}")
                         + why.get(lang, ""), p["src"]))
        else:
            out.append(L("• Price has not visited this area yet — the models are armed when it does" if lang == "en"
                         else "• किंमत अजून या area ला आली नाही — आली की models armed होतात", p["src"]))
        far = "above" if n0["role"] == "resistance" else "below"
        nx = p.get("next_same_side")
        if lang == "en":
            txt = f"• Idea cancelled if: a close {far} {n(p.get('far_edge'))} + a swing {far} (the area BROKEN)"
            txt += f" → next: {rng(nx['lo'], nx['hi'])}" if nx else ""
        else:
            fw = "वर" if far == "above" else "खाली"
            txt = f"• Idea रद्द जर: {n(p.get('far_edge'))} च्या {fw} close + {fw} swing (area BROKEN)"
            txt += f" → पुढचा: {rng(nx['lo'], nx['hi'])}" if nx else ""
        out.append(L(txt, "levels K4 (break_rule = structure)", True))
        other = "bull_put" if side == "bear_call" else "bear_call"
        mc = (f.get("wave") or {}).get("model_c") or "off"
        if p.get("trend") in ("UP", "DOWN"):
            out.append(L((f"• {SIDE_WORD[other]['en']}: only via model C ({mc.upper()})" if lang == "en"
                          else f"• {SIDE_WORD[other]['mr']}: फक्त model C मधून ({mc.upper()})"), "model_c.is_on", True))
    for e in p.get("entries") or ():
        out.append(L((f"• {e['model']} fired at area #{e['area']} on the last bar (see its PAPER card)" if lang == "en"
                      else f"• शेवटच्या bar ला area #{e['area']} वर {e['model']} fired (PAPER card पाहा)"), "decision row entries", True))
    out.append(L("• Execution = your dashboard settings" if lang == "en" else "• Execution = तुमची dashboard settings",
                 "dashboard settings", True))
    return out


def sec_vision(vision, lang):
    """Vision's part (info only). vision None ⇒ "not run"; else the adapter's summary (decision3.chart_reading_vision.summarise)."""
    if vision is None:
        return [L("• Not run (dashboard chart_reading_vision = off) — the engine reading above stands alone" if lang == "en"
                  else "• चालवलं नाही (dashboard chart_reading_vision = off) — वरचं engine वाचनच", "vision: not run", True)]
    if vision.get("status") != "ok":
        why = vision.get("why") or ""
        return [L((f"• Not run: {why}" if lang == "en" else f"• चालवलं नाही: {why}"), "vision: not run", True)]
    out = []
    c = vision.get("counts") or {}
    tot = c.get("audited", 0)
    parts = [f"{c.get('VALID', 0)} of {tot} agree" if lang == "en" else f"{tot} पैकी {c.get('VALID', 0)} सहमत"]
    if c.get("SPURIOUS"):
        parts.append(f"{c['SPURIOUS']} SPURIOUS")
    if c.get("SHIFT"):
        parts.append(f"{c['SHIFT']} shift suggested" if lang == "en" else f"{c['SHIFT']} shift सुचवला")
    out.append(L("• Areas: " + " · ".join(parts), "vision: per area verdicts", True))
    for a in vision.get("disagree") or ():
        out.append(L(f"• #{a['id']} {a['tf']} {rng(a['lo'], a['hi'])}: {a['verdict']}" + (f" — {a['reason']}" if a.get("reason") else ""),
                     "vision: per area verdicts"))
    nv = vision.get("not_visible") or []
    if nv:
        out.append(L(("• Not visible on this chart: " if lang == "en" else "• या chart वर दिसत नाही: ") + ", ".join(f"#{i}" for i in nv),
                     "vision: not visible rule"))
    for z in vision.get("missing") or ():
        out.append(L((f"• A zone it sees that the engine does not: {rng(z['lo'], z['hi'])} ({z['tf']})" if lang == "en"
                      else f"• Engine ला नसलेला, Vision ला दिसणारा zone: {rng(z['lo'], z['hi'])} ({z['tf']})"), "vision: missing zones"))
    for g in vision.get("duplicates") or ():
        out.append(L((f"• Duplicate check: {', '.join('#' + str(i) for i in g['ids'])} overlap = one place (Z-1u)" if lang == "en"
                      else f"• Duplicate तपासणी: {', '.join('#' + str(i) for i in g['ids'])} एकमेकांवर = एकच जागा (Z-1u)"),
                     "vision: duplicates"))
    for k, word in (("trend", {"en": "Trend reading", "mr": "Trend वाचन"}), ("structure", {"en": "Structure reading", "mr": "Structure वाचन"})):
        x = (vision.get("agreement") or {}).get(k)
        if x is not None:
            w = ({"en": "agrees", "mr": "सहमत"} if x.get("agrees") else {"en": "differs", "mr": "वेगळं"})[lang]
            out.append(L(f"• {word[lang]}: {w}" + (f" ({x.get('vision')})" if x.get("vision") else ""), f"vision: {k} agreement"))
    return out


# ------------------------------------------------------------------------------------------------------------------------ render
def sections(f, lang="mr", detail="short", vision=None, vision_on=True):
    """[(key, heading, [lines])] — empty sections dropped. vision_on False ⇒ no Vision section at all."""
    if lang not in LANGS:
        raise ValueError(f"language {lang!r} — {LANGS}")
    if detail not in DETAILS:
        raise ValueError(f"detail {detail!r} — {DETAILS}")
    out = [("big", "s_big", sec_big(f, lang)), ("struct", "s_struct", sec_struct(f, lang)), ("areas", "s_areas", sec_areas(f, lang, detail)),
           ("liq", "s_liq", sec_liq(f, lang)), ("lines", "s_lines", sec_lines(f, lang, detail)), ("vol", "s_vol", sec_vol(f, lang)),
           ("brk", "s_brk", sec_brk(f, lang, detail)), ("wave", "s_wave", sec_wave(f, lang)), ("plan", "s_plan", sec_plan(f, lang))]
    if vision_on:
        out.append(("vision", "s_vision", sec_vision(vision, lang)))
    res = []
    for key, h, lines in out:
        if detail == "short":
            keep = [x for x in lines if x["main"]] or lines[:1]
            lines = keep
        if lines:
            res.append((key, tr(h, lang), lines))
    return res


DROP_ORDER = ("vision", "wave", "brk", "vol", "lines", "liq", "struct", "areas", "big")   # extra lines first, bottom-up; plan never


def _join(head, secs, tail):
    parts = list(head)
    for _, h, lines in secs:
        parts += ["", h] + [x["text"] for x in lines]
    return "\n".join(parts + [""] + tail)


def tg_len(text):
    """Telegram counts a message in UTF-16 code units (an emoji = 2) — the length this module keeps ≤ the limit."""
    return len(text.encode("utf-16-le")) // 2


def render(f, lang="mr", detail="short", link=None, vision=None, vision_on=True, limit=TELEGRAM_LIMIT):
    """Message 2 text (plain, Telegram-safe) ≤ limit (UTF-16 units). Returns (text, meta {sections, lines [{text, src}], cut, length}).
    Too long ⇒ 1) the extra (non-main) lines go one by one, bottom-up in DROP_ORDER; 2) whole sections, bottom-up (the plan stays);
    3) a hard cut — the "more on the dashboard page" line and the link line always end the message."""
    if lang not in LANGS:
        raise ValueError(f"language {lang!r} — {LANGS}")
    head = [tr("head", lang, sym=f.get("symbol") or ""), RULE, tr("last", lang, x=n(f.get("last_close")))]
    tail = [tr("link", lang, link=link or ("dashboard → Chart Reading" if lang == "en" else "dashboard → Chart Reading पान"))]
    secs = [(k, h, list(ls)) for k, h, ls in sections(f, lang, detail, vision, vision_on)]
    cut = []
    text = _join(head, secs, tail)
    more = [tr("more", lang)] + tail
    if tg_len(text) > limit:                                               # 1) extra lines, one at a time, bottom-up
        for key in DROP_ORDER:
            for i, (k, h, lines) in enumerate(secs):
                if k != key:
                    continue
                while tg_len(text) > limit:
                    extra = [j for j, x in enumerate(lines) if not x["main"]]
                    if not extra:
                        break
                    lines.pop(extra[-1])
                    cut.append(f"{k}: 1 line")
                    text = _join(head, secs, more)
            if tg_len(text) <= limit:
                break
    if tg_len(text) > limit:                                               # 2) whole sections from the bottom (the plan stays)
        for key in DROP_ORDER:
            if tg_len(text) <= limit:
                break
            if any(k == key for k, _, _ in secs):
                secs = [x for x in secs if x[0] != key]
                cut.append(f"{key}: section")
                text = _join(head, secs, more)
    if tg_len(text) > limit:                                               # 3) last resort: hard cut, the link kept
        keep = "\n".join(more)
        body = text
        while tg_len(body) + tg_len(keep) + 1 > limit and "\n" in body:
            body = body.rsplit("\n", 1)[0]
        text = body + "\n" + keep
        cut.append("hard cut")
    meta = {"sections": [k for k, _, _ in secs], "lines": [{"text": x["text"], "src": x["src"]} for _, _, ls in secs for x in ls],
            "cut": cut, "length": tg_len(text)}
    return text, meta


def reading_lines(text):
    """The reading lines (everything but the header line and the link line) — for the no-date / forbidden-word checks."""
    lines = text.splitlines()
    return [x for i, x in enumerate(lines) if i != 0 and not x.startswith(("Full report →", "पूर्ण report →"))]


def check(text):
    """[problems]: forbidden words, date / clock framing in the reading, length."""
    out = []
    body = "\n".join(reading_lines(text))
    for m in FORBIDDEN.finditer(body):
        out.append(f"forbidden word: {m.group(0)!r}")
    for m in DATE_RX.finditer(body):
        out.append(f"date / time framing: {m.group(0)!r}")
    if tg_len(text) > TELEGRAM_LIMIT:
        out.append(f"length {tg_len(text)} > {TELEGRAM_LIMIT}")
    return out


# ------------------------------------------------------------------------------------------------------------------------ refresh
def refresh(prev, f, lang="mr", link=None):
    """The short pre-open refresh: what changed since the close reading (`prev` facts) — trend / state per timeframe, the nearest
    trade-side area and its state, areas that appeared / left the trade-side list, the last close. Nothing changed ⇒ one line."""
    head = [("🔁 {sym} — before the open: what changed" if lang == "en" else "🔁 {sym} — open आधी: काय बदललं").format(sym=f.get("symbol")),
            RULE]
    ch = []
    if prev:
        for tf in ("W", "D", "1H", "15M"):
            a = (((prev.get("big_picture") or {}).get("tfs") or {}).get(tf) or {})
            b = (((f.get("big_picture") or {}).get("tfs") or {}).get(tf) or {})
            if (a.get("state"), a.get("trend")) != (b.get("state"), b.get("trend")):
                ch.append(f"• {tf}: {state_words(a.get('state'), a.get('trend'), lang)} → {state_words(b.get('state'), b.get('trend'), lang)}")
        pa = {x["id"]: x for x in ((prev.get("areas") or {}).get("watch") or ())}
        fa = {x["id"]: x for x in ((f.get("areas") or {}).get("watch") or ())}
        for i, x in fa.items():
            if i in pa and pa[i]["state"] != x["state"]:
                ch.append(f"• #{i} {rng(x['lo'], x['hi'])}: {AREA_STATE.get(pa[i]['state'])} → {AREA_STATE.get(x['state'])}")
        new = [x for i, x in fa.items() if i not in pa]
        gone = [x for i, x in pa.items() if i not in fa]
        for x in sorted(new, key=lambda a: a["dist"])[:1]:
            ch.append(("• new on the trade side: " if lang == "en" else "• trade बाजूला नवा: ") + area_words(x, lang))
        for x in sorted(gone, key=lambda a: a["dist"])[:1]:
            ch.append(("• left the trade side: " if lang == "en" else "• trade बाजूतून गेला: ") + area_words(x, lang))
        if prev.get("last_close") != f.get("last_close"):
            ch.append(("• Last close " if lang == "en" else "• शेवटचा close ") + f"{n(prev.get('last_close'))} → {n(f.get('last_close'))}")
    else:
        ch.append("• No close reading stored — the full reading follows at the next close" if lang == "en"
                  else "• Close चं वाचन साठवलेलं नाही — पूर्ण वाचन पुढच्या close नंतर")
    if not ch:
        ch.append("• No change since the close reading" if lang == "en" else "• Close च्या वाचनानंतर बदल नाही")
    p = (f.get("plan") or {}).get("nearest")
    if p:
        ch.append(("• Nearest trade-side area: " if lang == "en" else "• सर्वात जवळचा trade-बाजूचा area: ") + area_words(p, lang))
    tail = [tr("link", lang, link=link or ("dashboard → Chart Reading" if lang == "en" else "dashboard → Chart Reading पान"))]
    return "\n".join(head + ch + [""] + tail)[:TELEGRAM_LIMIT]
