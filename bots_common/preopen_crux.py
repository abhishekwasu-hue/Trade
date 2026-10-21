"""bots_common/preopen_crux.py — pre-open संदेशाच्या वर लहान CRUX (Abhi, track F): प्रत्येक symbol ≤ 5 ओळी — Daily (+ Weekly) trend, engine
पाहत असलेला सर्वात जवळचा trade-बाजूचा area (kind, पट्टा, last close पासून अंतर, state, confluence एका शब्दात), entry आधी काय हवं (method
चा क्रम: visit → handover → commitment with volume → 5-min CHoCH; A = एक confirming piece, नाहीतर B), invalidation (engine चा नियम: area पलीकडे
close + पलीकडे swing ⇒ BROKEN; protected Daily level) आणि विरुद्ध बाजूचा जवळचा area (engine; SL / target = dashboard).

"High-probability" = फक्त reader जे आधीच सांगतो (engine चे watched areas, त्यांची state, confluence, line touch N, method चा A / B नियम) —
नवा score / नियम / आकडा नाही: प्रत्येक आकडा area च्या lo / hi, last close किंवा protected मधूनच. फक्त दाखवणं — gate / order / निर्णय बदलत
नाही. Setting `preopen_charts` (15M SRv2 पान, default ON — Abhi ने मागितलं) बंद ⇒ हा block नाही, charts नाहीत (आजचाच संदेश).
"""
import html

from bots_common import level_reaction as LR
from bots_common import plain_text as PT

SETTING_KEY = "preopen_charts"
MARK = "🎯"                                                                # crux ओळीची सुरुवात (symbol ओळ "<b>SYM</b>" ने सुरू — वेगळी)
CHART_NA = "(chart unavailable)"
TF_WORD = {"1H": "1H", "D": "Daily", "1D": "Daily", "W": "Weekly"}
SEQUENCE = "price visits it → handover → commitment candle with volume → 5-min change of character"
CONFIRMING_WORDS = "RSI divergence / volume growing / correction line closed through"


def charts_on(value):
    """Setting ची किंमत ⇒ bool. None / "" ⇒ True (default ON); "false" / "0" / "no" / "off" ⇒ False."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "0", "no", "off")
    return bool(value)


def setting_for(active, sym=None):
    """चालू bots (`bot_status`) पैकी त्या symbol चा पहिला स्पष्ट `preopen_charts` ⇒ bool; कुठेच नाही ⇒ True (default ON).
    active None / False (settings वाचता नाहीत / जुने callers) ⇒ False (जुनाच संदेश)."""
    if not active:
        return False
    for a in active:
        if (sym is None or a.get("symbol") == sym) and a.get(SETTING_KEY) is not None:
            return charts_on(a[SETTING_KEY])
    return True


def _esc(x):
    return html.escape(str(x), quote=False)


def _rng(lo, hi):
    return f"{float(lo):,.0f}" if round(lo) == round(hi) else f"{float(lo):,.0f}–{float(hi):,.0f}"


def _kind(side):
    return "demand" if side == LR.BULL else "supply"


def _conf_word(label, line_tag=None):
    """Confluence एका शब्दात: "Daily" / "Weekly" / "Daily+Weekly" / "line (touch 3)" … नाही ⇒ "none"."""
    lab = str(label or "")
    parts = [w for w in ("Daily", "Weekly") if w in lab]
    if line_tag:
        parts.append(str(line_tag))
    elif "line" in lab:
        i = lab.find("line")
        tail = lab[i:].split(";", 1)[0].strip()
        parts.append(tail)
    return "+".join(parts) if parts else "none"


def _state_words(lv):
    """engine level dict (`Levels.snapshot`) ⇒ "fresh (not tested yet)" / "tested 2×" / "flipped (was demand), tested 1×"; नाही ⇒ None."""
    if not lv:
        return None
    st = str(lv.get("state") or "").upper()
    tests = lv.get("tests")
    out = []
    if st == "FLIPPED" or (lv.get("flips") or 0) > 0:
        role = str(lv.get("role") or "").lower()                           # reader ची आताची भूमिका (kind = किंमतीच्या कोणत्या बाजूला)
        now, was = {"support": ("demand", "supply"), "resistance": ("supply", "demand")}.get(role, (None, None))
        out.append(f"flipped (reader role now {now}, was {was})" if now else "flipped")
    if tests is not None:
        out.append("fresh (not tested yet)" if int(tests) == 0 else f"tested {int(tests)}×")
    elif st:
        out.append(st.lower())
    return ", ".join(out) or None


def _match(levels, lo, hi):
    for x in levels or ():
        if round(float(x["lo"])) == round(lo) and round(float(x["hi"])) == round(hi):
            return x
    return None


def _tf_of(lv, zt):
    if lv and lv.get("tf"):
        return TF_WORD.get(str(lv["tf"]), str(lv["tf"]))
    return PT.tf_word(zt)


def _dist(side, lo, hi, last):
    """last close पासून area च्या जवळच्या कडेपर्यंत (area_words सारखंच)."""
    return (last - hi) if side == LR.BULL else (lo - last)


def facts(ctx, last, areas, levels=None, line_tags=None):
    """Crux / chart साठी तथ्यं (नवा आकडा नाही). areas = संदेशातलाच watched list (`nearest()`: (side, lo, hi, zone_type), मध्य-क्रम);
    nearest = किंमत ज्या पट्ट्याच्या कडेला आधी पोहोचेल तो (last close पासून कडेपर्यंतचं अंतर सर्वात कमी), next = त्याच बाजूचा पुढचा;
    levels = engine चे tradeable पट्टे (`watched_levels`, state / tf / confluence सह) किंवा None (own source); line_tags = {level id:
    "line (touch N)"} (reader चं `trendline.confluence_areas`) किंवा None.
    target = विरुद्ध बाजूचा (bear ⇒ किंमतीखालचा support, bull ⇒ वरचा resistance) सर्वात जवळचा जिवंत पट्टा — reader चा `method.risk`
    target सारखाच (विरुद्ध बाजूचा जवळचा जिवंत level). रिटर्न dict (nearest None ⇒ area नाही)."""
    out = {"ctx": ctx, "last": last, "nearest": None, "next": None, "target": None, "watched": [],
           "protected": (ctx or {}).get("protected")}
    if last is None:
        return out
    for i, (side, lo, hi, zt) in enumerate(areas or ()):
        lv = _match(levels, lo, hi)
        tag = (line_tags or {}).get(lv.get("id")) if lv else None
        a = {"side": side, "lo": float(lo), "hi": float(hi), "tf": _tf_of(lv, zt), "state": _state_words(lv),
             "conf": _conf_word((lv or {}).get("confluence_label") or PT.zone_note(zt), tag), "dist": _dist(side, lo, hi, last),
             "id": (lv or {}).get("id"), "confluence": list((lv or {}).get("confluence") or ())}
        out["watched"].append(a)
    if out["watched"]:
        # nearest = the band edge price reaches first (edge distance from the last close), not the midpoint order of the list
        by_edge = sorted(out["watched"], key=lambda a: (a["dist"], a["lo"] if a["side"] == LR.BEAR else -a["hi"]))
        out["nearest"] = by_edge[0]
        side = out["nearest"]["side"]
        same = [a for a in by_edge[1:] if a["side"] == side]
        out["next"] = same[0] if same else None
        opp_role = "support" if side == LR.BEAR else "resistance"
        cands = []
        for x in levels or ():
            lo, hi = float(x["lo"]), float(x["hi"])
            role = str(x.get("role") or "").lower()
            if side == LR.BEAR and hi < last and (not role or role == opp_role):
                cands.append((last - hi, LR.BULL, lo, hi, x))
            elif side == LR.BULL and lo > last and (not role or role == opp_role):
                cands.append((lo - last, LR.BEAR, lo, hi, x))
        if cands:
            d, s2, lo, hi, x = min(cands, key=lambda c: c[0])
            out["target"] = {"side": s2, "lo": lo, "hi": hi, "tf": _tf_of(x, ""), "dist": d, "id": x.get("id")}
    return out


def _side_words(ctx):
    sides = set((ctx or {}).get("sides") or ())
    if sides == {LR.BEAR}:
        return "sell side only: supply above price"
    if sides == {LR.BULL}:
        return "buy side only: demand below price"
    if sides:
        return "range: each edge"
    return "no trade side"


def lines(sym, ctx, weekly, last, f=None, na=None, chart_ok=True):
    """Crux ओळी (HTML, ≤ 5). f = `facts()`; na = watched areas NA कारण; chart_ok False ⇒ पहिल्या ओळीला "(chart unavailable)"."""
    wk = f"Weekly {_esc(weekly)}" if weekly else "Weekly n/a"
    tail = "" if chart_ok else f" {CHART_NA}"
    ctx = ctx or {}
    if not ctx.get("ok"):
        return [f"<b>{MARK} {sym}</b> — no new entries today ({_esc(PT.unclear_words(ctx))}), {wk}.{tail}"]
    head = f"<b>{MARK} {sym}</b> — {_esc(PT.trend_words(ctx))}, {wk} ⇒ {_side_words(ctx)}.{tail}"
    if last is None:
        return [head, "Price data missing (no last close) — no area distances."]
    n = (f or {}).get("nearest")
    if n is None:
        if na:
            return [head, f"Watched areas NA — {_esc(na)}."]
        want = " or ".join(_kind(s) for s in sorted(ctx.get("sides") or ())) or "trade-side"
        return [head, f"Last close {last:,.0f}: no {want} area near price yet — nothing to enter."]
    bull = n["side"] == LR.BULL
    where = "below" if bull else "above"
    st = f" · {n['state']}" if n.get("state") else ""
    out = [head,
           f"Nearest: {_kind(n['side'])} {_rng(n['lo'], n['hi'])} ({_esc(n['tf']) + ', ' if n['tf'] else ''}{PT.pts(n['dist'])} {where} "
           f"last close {last:,.0f}){st} · confluence: {_esc(n['conf'])}"]
    if n["conf"] != "none":
        ab = "Confluence is already there ⇒ label A if all of this happens."
    else:
        ab = f"Label A needs one more piece ({CONFIRMING_WORDS}); without it B."
    out.append(f"Entry only if: {SEQUENCE}. {ab}")
    edge = n["lo"] if bull else n["hi"]
    # engine (KB K4, decision3/levels.py): BROKEN = a close beyond AND a swing formed beyond; a close beyond alone = sweep
    inv = f"Invalid: close {'below' if bull else 'above'} {edge:,.0f} + a swing beyond it (area broken)"
    p, tr = f["protected"], str(ctx.get("trend") or "")
    if p is not None and tr in ("UP", "DOWN"):
        inv += f"; Daily {tr} ends on a daily close {'below' if tr == 'UP' else 'above'} {float(p):,.0f} (protected)"
    out.append(inv + ".")
    t = f.get("target")
    opp = "supply" if bull else "demand"
    if t:
        tgt = (f"Next opposite area (engine): {opp} {_rng(t['lo'], t['hi'])} ({_esc(t['tf']) + ', ' if t['tf'] else ''}"
               f"{PT.pts(t['dist'])} {'above' if bull else 'below'})")
    else:
        tgt = f"Next opposite area (engine): no {opp} area in the list"
    tgt += " · SL / target = dashboard"
    nx = f.get("next")
    if nx:
        tgt += f" · if it breaks, next: {_kind(nx['side'])} {_rng(nx['lo'], nx['hi'])}" + (f" ({_esc(nx['tf'])})" if nx["tf"] else "")
    out.append(tgt + ".")
    return out[:5]
