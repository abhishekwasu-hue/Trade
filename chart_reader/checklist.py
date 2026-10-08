"""chart_reader/checklist.py — trade ठरवण्याआधी प्रत्येक candidate वर 23 बाबींचा checklist, क्रमाने (KB भाग B चे 8 टप्पे + भाग H;
TRADE_KB_FULL_IMPLEMENTATION_PROMPT §5A).

प्रत्येक बाब: {n, name, value (मूल्य / निष्कर्ष, किंवा "लागू नाही: कारण"), mark ("✅" बाजूने / pass, "❌" विरुद्ध / fail, "—" तटस्थ /
लागू नाही)}. एकही बाब रिकामी (value None / "") ⇒ `CHECKLIST_INCOMPLETE` — candidate evaluate होत नाही (bug म्हणून alert).
Chart वर नाही: trade card / dashboard / अहवालात बाजूला तक्ता; Telegram वर `summary()` ("23/23 ✓ · fail: R:R").
"""
ITEMS = [
    (1, "HTF trend + protected"), (2, "Elliott position"), (3, "Impulse"), (4, "Correction / reversal"), (5, "Correction प्रकार, टप्पा"),
    (6, "Retrace खोली"), (7, "Zones (selling / buying)"), (8, "Active zone"), (9, "Confluence"), (10, "Liquidity / sweep"),
    (11, "Candle मालिका"), (12, "Futures volume"), (13, "RSI divergence"), (14, "Chart pattern"), (15, "Gap गोष्ट (+ G7)"),
    (16, "वेळ / expiry / event / VIX"), (17, "Reversal composite"), (18, "Zone जवळ entry"), (19, "Invalidation + target"), (20, "R:R"),
    (21, "पक्के नियम + A3 व्हेटो"), (22, "Setup प्रकार (G1–G7)"), (23, "Evidence + grade"),
]
OK, BAD, NA = "✅", "❌", "—"


def _pts(kb, k):
    return float(((kb or {}).get(k) or {}).get("pts") or 0.0)


def _line(kb, k):
    return ((kb or {}).get(k) or {}).get("line") or ""


def _mark_pts(p):
    return OK if p > 0 else BAD if p < 0 else NA


def _i1(r):
    ms = r.get("market_state") or {}
    t = ms.get("trend") or {}
    d = t.get("dir")
    if d is None:
        return None
    pr = t.get("protected") or {}
    val = (f"{'up' if d > 0 else 'down' if d < 0 else 'range'} ({t.get('state', '—')})"
           + (f" · protected {pr.get('kind', '')} {float(pr['price']):,.1f}" if pr.get("price") is not None else " · protected नाही"))
    side = r.get("side") or 0
    return val, (OK if d and d == side else BAD if d and side and d != side else NA)


def _i2(r):
    el = r.get("elliott") or {}
    st = el.get("state")
    if not st:
        return None
    return f"{st}" + (" (स्पष्ट count)" if el.get("clear") else "") + (f" · {el.get('line')}" if el.get("line") else ""), NA


def _i3(r):
    imp = (r.get("market_state") or {}).get("impulse")
    if not imp:
        return "लागू नाही: trade-degree impulse नाही", BAD
    return f"{float(imp['from']):,.1f} → {float(imp['to']):,.1f} ({imp.get('size_mr', '—')}× MR)", OK


def _i4(r):
    pb = (r.get("structure") or {}).get("pullback")
    if not pb:
        return "लागू नाही: structure नाही", NA
    return pb, OK if pb == "pullback" else BAD if pb == "reversal" else NA


def _i5(r):
    st = r.get("structure") or {}
    if not st.get("impulse"):
        return "लागू नाही: impulse नाही", NA
    return f"{st.get('correction_type') or 'अनिश्चित'} · टप्पा {st.get('entry_point') or 'चालू'}", OK if st.get("entry_point") else NA


def _i6(r):
    rt = (r.get("structure") or {}).get("retrace")
    if rt is None:
        return "लागू नाही: correction नाही", NA
    return f"{float(rt):.0%}", OK if 0.382 <= float(rt) <= 0.80 else BAD


def _i7(r):
    zs = r.get("zones")
    if zs is None:
        return None
    sell = [z["zid"] for z in zs if z.get("side") == "sell" and z.get("zid")][:4]
    buy = [z["zid"] for z in zs if z.get("side") == "buy" and z.get("zid")][:4]
    want = sell if (r.get("side") or 0) < 0 else buy
    return f"selling {len([z for z in zs if z.get('side') == 'sell'])} ({', '.join(sell) or '—'}) · buying " \
           f"{len([z for z in zs if z.get('side') == 'buy'])} ({', '.join(buy) or '—'})", OK if want else BAD


def _i8(r):
    a = (r.get("active") or {}).get("area")
    if not a:
        return "नाही: ताज्या bars नी trade बाजूचा zone शिवलेला नाही", BAD
    return f"{a.get('zid') or a.get('id')} · {a.get('type') or a.get('tool')} · {float(a['low']):,.1f}–{float(a['high']):,.1f}", OK


def _i9(r):
    cf = (r.get("active") or {}).get("confluence") or []
    return (", ".join(cf) if cf else "नाही"), OK if cf else NA


def _i10(r):
    return _line(r.get("kb"), "LQ") or None, _mark_pts(_pts(r.get("kb"), "LQ"))


def _i11(r):
    c = (r.get("candles") or {}).get("legs")
    if not c:
        return None
    return c.get("line"), OK if c.get("tired") else NA


def _i12(r):
    return _line(r.get("kb"), "VL") or None, _mark_pts(_pts(r.get("kb"), "VL"))


def _i13(r):
    return _line(r.get("kb"), "DV") or None, _mark_pts(_pts(r.get("kb"), "DV"))


def _i14(r):
    return _line(r.get("kb"), "PT") or None, _mark_pts(_pts(r.get("kb"), "PT"))


def _i15(r):
    g = r.get("gap_rule")
    if not g:
        return None
    g7 = (r.get("g7") or {}).get("line") or "G7: —"
    story = (g.get("story") or {}).get("line") or ""
    mark = BAD if g.get("block") else OK if g.get("gp") == "confirms" else BAD if g.get("gp") == "opposes" else NA
    return f"{g.get('line')} · {story} · {g7}", mark


def _i16(r):
    kb = r.get("kb") or {}
    ev = (r.get("evidence") or {}).get("event_day")
    tm, vx = _line(kb, "TM"), _line(kb, "VX")
    if not tm:
        return None
    p = _pts(kb, "TM") + _pts(kb, "VX") + (-1 if ev else 0)
    return f"{tm} · {vx or 'VX —'} · event {'हो' if ev else 'नाही'}", _mark_pts(p)


def _i17(r):
    rv = r.get("reversal") or {}
    if rv.get("status") == "ok":
        return f"s {rv.get('s')} · {rv.get('label')}", OK
    return f"नाही ({rv.get('status') or '—'})", BAD


def _i18(r):
    ze = r.get("zone_entry")
    if not ze:
        return None
    return ze.get("line"), OK if not ze.get("code") else BAD


def _i19(r):
    rk = r.get("risk")
    if not rk:
        return "लागू नाही: active zone नाही ⇒ invalidation / target नाही", BAD
    tg = (rk.get("targets") or [{}])[0]
    sl2 = rk.get("sl_defs") or {}
    extra = " · ".join(f"{k} {v['price']:,.1f}" for k, v in sl2.items() if v.get("price") is not None)
    return (f"SL {float(rk['invalidation']):,.1f} · target {float(tg['price']):,.1f} ({tg.get('id')})" if tg.get("price") is not None
            else f"SL {float(rk['invalidation']):,.1f} · target नाही") + (f" · [{extra}]" if extra else ""), OK if tg.get("price") else BAD


def _i20(r):
    rr = (r.get("risk") or {}).get("rr")
    if rr is None:
        return "लागू नाही: target / invalidation नाही", BAD
    return f"1:{float(rr):.1f}", OK if float(rr) >= 3.0 else BAD


def _i21(r):
    bad = list(r.get("hard_rules") or []) + list(r.get("vetoes") or [])
    return ("pass" if not bad else "fail: " + " | ".join(str(x)[:60] for x in bad)), OK if not bad else BAD


def _i22(r):
    st = r.get("setups")
    if st is None:
        return None
    return (", ".join(st) if st else "none"), NA


def _i23(r):
    if r.get("total") is None:
        return None
    return f"{float(r['total']):.1f} · grade {r.get('grade')}", OK if r.get("grade") in ("A", "B") else BAD


BUILDERS = [_i1, _i2, _i3, _i4, _i5, _i6, _i7, _i8, _i9, _i10, _i11, _i12, _i13, _i14, _i15, _i16, _i17, _i18, _i19, _i20, _i21, _i22,
            _i23]


def build(r, builders=None):
    """रिटर्न (rows, missing). missing = रिकाम्या बाबींचे क्रमांक."""
    rows, missing = [], []
    for (n, name), fn in zip(ITEMS, builders or BUILDERS):
        try:
            got = fn(r)
        except Exception as exc:                                            # noqa: BLE001 — bug ⇒ रिकामी बाब ⇒ CHECKLIST_INCOMPLETE
            got = None
            name = f"{name} (error {type(exc).__name__})"
        if not got or got[0] in (None, ""):
            missing.append(n)
            rows.append({"n": n, "name": name, "value": None, "mark": BAD})
        else:
            rows.append({"n": n, "name": name, "value": str(got[0]), "mark": got[1]})
    if len(rows) != len(ITEMS):
        missing += [n for n, _ in ITEMS[len(rows):]]
    return rows, missing


def summary(rows):
    """Telegram साठी: "23/23 ✓ · fail: R:R, Zone जवळ entry"."""
    filled = sum(1 for x in rows if x["value"] is not None)
    fails = [x["name"] for x in rows if x["mark"] == BAD]
    return f"{filled}/{len(ITEMS)} ✓" + (f" · fail: {', '.join(fails)}" if fails else "")
