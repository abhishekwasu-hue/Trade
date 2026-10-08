"""chart_reader/narrative.py — code ची गोष्ट (deterministic), KB भाग B च्या 8 टप्प्यांच्या क्रमाने, प्रत्येक ओळीवर chapter tag ([K#]).

8–12 ओळी: trend → impulse → correction प्रकार → area (confluence) → area वरचं वर्तन → context → पुष्टी → risk → grade, आणि
"मी कुठे चुकीचा ठरेन" एका ओळीत. Vision ला input आणि Telegram / dashboard वर. किंमती फक्त code कडून.
"""


def _kb(r, k):
    return ((r.get("kb") or {}).get(k) or {}).get("line", "").split(": ", 1)[-1]


def build(r):
    L = []
    st = r.get("structure") or {}
    el = r.get("elliott") or {}
    # टप्पा 1: मोठं चित्र
    L.append(f"[K1] {r['trend']['line']} · [K3] {el.get('line', 'Elliott: —')}")
    # टप्पा 2: impulse / correction
    facts = st.get("facts") or []
    if facts:
        L.append(f"[K2] {facts[0]}")
    if len(facts) > 1:
        L.append(f"[K2] {' · '.join(facts[1:3])}")
    # टप्पा 3: areas
    a = r.get("active") or {}
    bt = (r.get("areas") or {}).get("by_tool") or {}
    tools = ", ".join(f"{k}{n}" for k, n in bt.items() if n)
    if a.get("area"):
        z = a["area"]
        L.append(f"[K4/K6/K8] active area {z['id']} (साधन {z.get('tool')}, {z.get('state')}) {z['low']:,.1f}–{z['high']:,.1f} · गुणवत्ता "
                 f"{a['quality']:.2f}" + (" · horizontal ∩ sloping" if a.get("intersection") else "")
                 + (f" · [K7] confluence: {', '.join(a['confluence'])}" if a.get("confluence") else "") + f" · तपासलेली साधनं: {tools or '—'}")
    else:
        L.append(f"[K4/K6] ताज्या bars नी trade बाजूचा ठोस area शिवलेला नाही · तपासलेली साधनं: {tools or '—'}")
    # टप्पा 4: area वरचं वर्तन
    beh = []
    if r.get("last_candle"):
        beh.append(f"[K9] {r['last_candle']['line']}")
    if st.get("cw_parts"):
        beh.append(f"[K10] correction कमकुवत {st.get('correction_weakening', 0):.2f}")
    if beh:
        L.append(" · ".join(beh))
    L.append(f"[K5] {_kb(r, 'LQ')} · [K10.3] {_kb(r, 'VL')} · [K10.2] {_kb(r, 'DV')} · [K11] {_kb(r, 'PT')}")
    # टप्पा 5: context
    g = r.get("gap") or {}
    L.append(f"[K13] gap: {g.get('line') or '—'} · [K14] {_kb(r, 'TM')} · {_kb(r, 'VX')}")
    # टप्पा 6: पुष्टी
    rv = r.get("reversal") or {}
    if rv.get("status") == "ok":
        cb = (rv.get("candles") or {}).get("components") or {}
        L.append(f"[K9] reversal: N={rv['n']} s={rv['s']:.2f} ({rv['label']})" + (f" · mods {', '.join(rv['mods'])}" if rv.get("mods") else "")
                 + (f" · candles 0–100: {' / '.join(f'{k} {v:g}' for k, v in cb.items())}" if cb else ""))
    else:
        L.append(f"[K9] reversal: {rv.get('status') or '—'}")
    # टप्पा 7: risk
    if r.get("risk"):
        L.append(f"[A3] risk: {r['risk']['line']}")
    # टप्पा 8: grade + कुठे चुकीचा
    vet = r.get("vetoes") or []
    L.append(f"[भाग D] grade {r.get('grade')} ({r.get('total')})" + (f" · {vet[0]}" if vet else "")
             + (f" · मी चुकीचा ठरेन: {r['invalidation']:,.1f} च्या पलीकडे close" if r.get("invalidation") is not None else ""))
    return L[:12]
