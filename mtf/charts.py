"""mtf/charts.py — W / D / 1H / 15M: प्रत्येक TF च्या स्वतःच्या candles वरचे थर, दोन images प्रति TF.

(अ) रचना: degree-निहाय swings + H / L / HH / HL / LH / LL, संरक्षित, trend, range कडा, I, A-B-C (प्रकार + गुण), K टोक / आधार-रेघ /
K-reset, zones (★, प्रकार, self, अवस्था; मेलेले + कारण), trendlines, sweep / false-break, वरच्या TF चे zones / संरक्षित (फिके).
(आ) entry: तेच संदर्भ + area-touch box, correction संपतेय ✔ (shrink / overlap / counter-wick), momentum checklist, RSI divergence,
commitment candle G1–G8, engine निर्णय + अडलेला gate, B1 बाण (✅ / 🟡, एका चाचणीला एक), B2 योजना.
सगळं t पर्यंत माहीत असलेलं (known_at ≤ t). फक्त दाखवणं — नियम / निर्णय / order बदलत नाही. Legend: प्रत्येक संकल्पना ✓ (किती) /
"NA (अजून नाही)" / बंद. Labels उजव्या स्तंभात एकमेकांवर न येता.
"""
import numpy as np
import pandas as pd

import instruments as INS
from decision2 import charts7 as D7
from decision2 import engine as DE
from legs2 import features as LF
from legs2 import ik2 as IK
from patterns2 import charts as PCH
from patterns2 import fold2 as F2
from patterns2 import momentum as MO
from review7 import method as RM
from review7 import settings as RS

from . import adapter as MA
from . import concepts as CC

ARROW = {"UP": "↑", "DOWN": "↓", "RANGE": "↔", "unknown": "?"}
TREND_MR = {"UP": "वर", "DOWN": "खाली", "RANGE": "range", "unknown": "अज्ञात"}
DEG_COL = {1: "#b0bec5", 2: "#ffd54f", 3: "#ff8a65"}
FMT = {"W": "%d %b %y", "D": "%d %b %y", "1H": "%d %b %H:%M", "15M": "%d %b %H:%M"}
UPPER = {"D": "W", "1H": "D", "15M": "1H"}
ROLE_MR = {"seller": "विक्रेते", "buyer": "खरेदीदार"}
IMG_MR = {"अ": "रचना", "आ": "entry"}
WIDTH, HEIGHT = 1600, 1000


# ------------------------------------------------------------------------------------------------------------- वाचन (≤ t)
def trend_rows(C, t):
    """degree-निहाय trend: D1 / D2 (structure) + D3 (pivots). रिटर्न [(deg, trend)]."""
    out = []
    for d in (1, 2, 3):
        if d == 3:
            out.append((3, DE.d3_trend(C, t)))
        elif d in C.st:
            out.append((d, C.st[d]["states"][t]["trend"]))
    return out


def trend_since(C, t, d):
    """D{d} trend आत्ताचा कधीपासून (पहिला bar जिथून सलग तोच)."""
    if d not in C.st:
        return None
    sts = C.st[d]["states"]
    cur = sts[t]["trend"]
    b = t
    while b - 1 >= 0 and sts[b - 1]["trend"] == cur:
        b -= 1
    return b


def zone_kind(z):
    """zone चा प्रकार (थर 4 च्या खुणांवरून): flip / breaker, origin, sweep, liquidity, range कड, k."""
    k = []
    if z.get("flip_bar") is not None:
        k.append("breaker" if z.get("breaker") else "flip")
    fl = z.get("flags") or {}
    if fl.get("c"):
        k.append("origin")
    if z.get("sweeps"):
        k.append("sweep")
    if fl.get("e"):
        k.append("liquidity")
    if fl.get("d"):
        k.append("range कड")
    if z.get("k"):
        k.append("/".join(z["k"]))
    return " · ".join(k) or "swing"


def zone_state(C, z, t):
    """जिवंत / test (भेट चालू किंवा pending) / मेला."""
    if z["status"] == "dead":
        return "मेला"
    inside = C.A["l"][t] <= z["top"] and C.A["h"][t] >= z["bottom"]
    return "test" if (z.get("pending") or inside) else "जिवंत"


def dead_zones(C, b0, t):
    """window मध्ये मेलेले zones: (id, band, मृत्यू bar, कारण). कारण = flip नंतर पुन्हा real break (थर 4 §4)."""
    out = []
    for e in getattr(C.Z, "events", []) or []:
        if e.get("type") != "मेला" or not (b0 <= e["bar"] <= t):
            continue
        prev = next((z for z in (C.Z.snap.get(e["bar"] - 1) or []) if z["id"] == e["id"]), None)
        if prev is not None:
            out.append({"id": e["id"], "top": prev["top"], "bottom": prev["bottom"], "role": prev["role"], "bar": e["bar"],
                        "why": "flip नंतर पुन्हा तुटला"})
    return out


def k_resets(C, b0, t):
    """K-reset: K चालू असताना I चं टोक पुढे गेलं (नवं टोक) ⇒ K पुन्हा शून्यापासून. रिटर्न [(bar, नवं टोक)]."""
    out = []
    trk = C.trk[1]
    prev_I, prev_st = None, None
    for b in range(max(b0, 1), t + 1):
        I = trk.I_at(b)
        st = trk.state(b).get("state")
        if (I is not None and prev_I is not None and prev_st in (IK.ST_K, IK.ST_KSTART) and I["origin"].bar == prev_I["origin"].bar
                and I["end"].bar != prev_I["end"].bar):
            out.append((b, float(I["end"].price)))
        prev_I, prev_st = I, st
    return out


def sweeps(C, b0, t):
    """structure sweep / failed gap break (D1 / D2) + zone sweep — known bar window मध्ये."""
    out = []
    for d in (1, 2):
        for e in (C.st.get(d) or {}).get("events", []):
            if e["type"] in ("sweep", "failed_gap_break") and b0 <= e["bar"] <= t:
                out.append((e["bar"], e.get("level"), f"D{d} {'sweep' if e['type'] == 'sweep' else 'false-break'}",
                            "seller" if e.get("dir", 0) > 0 else "buyer"))
    seen = set()
    for z in (C.Z.snap.get(t) or []):                                         # zone sweep: close परत आत आल्यावरच कळतो (seen ≤ t)
        for x in z.get("sweeps_all") or []:
            if b0 <= x["bar"] <= t and x.get("seen") is not None and x["seen"] <= t and (x["bar"], z["id"]) not in seen:
                seen.add((x["bar"], z["id"]))
                out.append((x["bar"], None, ("zone deep sweep" if x.get("deep") else "zone sweep"), z["role"]))
    return out


def corr_marks(C, t, d, s):
    """correction संपतेय ✔ (त्या bar ला, trade दिशा d): shrink (review7), overlap (overlap3 ≥ g6), counter-wick (wick ≥ g4)."""
    A = C.A
    out = []
    if RM._shrink(C, t, s):
        out.append("shrink")
    o3 = LF.overlap3(A, t)
    if o3 is not None and o3 >= float(C.s["g6_overlap3"]):
        out.append("overlap")
    rng = A["h"][t] - A["l"][t]
    if rng > 0:
        wick = (min(A["o"][t], A["c"][t]) - A["l"][t]) / rng if d > 0 else (A["h"][t] - max(A["o"][t], A["c"][t])) / rng
        if wick >= float(C.s["g4_wick"]):
            out.append("counter-wick")
    return out


def momentum_line(C, t):
    rec = C.f1.out.get(t) or {}
    m = (C.L4.get(t) or {}).get("momentum") or rec.get("momentum")
    if not m:
        return None
    marks = " ".join(f"{i + 1}{x}" for i, x in enumerate(m["items"]))
    return f"momentum: {m['verdict']} ({sum(x == MO.YES for x in m['items'])}/{m['non_na']}) · {marks}"


# ------------------------------------------------------------------------------------------------------------- top-down
def topdown(Cs, asof):
    """Cs = {tf: C | None}. रिटर्न {"rows": [{tf, deg, trend, dir, state, t}], "strip", "warn": [कारण]}."""
    rows = []
    for tf in ("W", "D", "1H", "15M"):
        C = Cs.get(tf)
        if C is None:
            rows.append({"tf": tf, "na": "display-only (holdout)" if (tf in ("W", "D") and INS.holdout()) else "data नाही"})
            continue
        t = _bar_at(C, asof)
        if t is None:
            rows.append({"tf": tf, "na": "बंद candle नाही"})
            continue
        deg, tr, d = RM.trend(C, t)
        st = C.trk[1].state(t).get("state")
        rows.append({"tf": tf, "t": t, "deg": deg, "trend": tr, "dir": d, "state": st})
    warn = []
    live = [r for r in rows if "na" not in r]
    for a, b in zip(live, live[1:]):
        if a["dir"] and b["dir"] and a["dir"] != b["dir"]:
            k = " (वरच्या TF चा K चालू ⇒ हा pullback असू शकतो)" if a["state"] in (IK.ST_K, IK.ST_KSTART) else ""
            warn.append(f"⚠ {b['tf']} {ARROW[b['trend']]} पण {a['tf']} {ARROW[a['trend']]}{k}")
    parts = []
    for r in rows:
        if "na" in r:
            parts.append(f"{r['tf']} — ({r['na']})")
            continue
        bad = any(w.startswith(f"⚠ {r['tf']} ") for w in warn)
        parts.append(f"{r['tf']} {ARROW.get(r['trend'], '?')}" + (f" D{r['deg']}" if r["deg"] else "") + f" ({r['state']})" + (" ⚠" if bad else ""))
    return {"rows": rows, "strip": " · ".join(parts), "warn": warn}


def _bar_at(C, asof):
    return MA.bar_at(C, asof)


def upper_ctx(Cu, asof, cfg):
    """वरच्या TF चे जिवंत zones + D1 / D2 संरक्षित (asof पर्यंत बंद candle)."""
    if Cu is None:
        return None
    tu = _bar_at(Cu, asof)
    if tu is None:
        return None
    zs = [z for z in (Cu.Z.snap.get(tu) or []) if z["status"] != "dead"]
    prot = [(d, Cu.st[d]["states"][tu].get("protected")) for d in (1, 2) if d in Cu.st and Cu.st[d]["states"][tu].get("protected") is not None]
    return {"tf": Cu.tf, "zones": zs, "protected": prot}


# ------------------------------------------------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, C, t, tf, cfg, image, title, extra_right=0):
        import plotly.graph_objects as go
        self.go = go
        self.C, self.t, self.tf, self.cfg, self.image = C, t, tf, cfg, image
        n_win = int(cfg["window"].get(tf, CC.WINDOW[tf]))
        self.b0 = max(0, t - n_win + 1)
        A = C.A
        idx = np.arange(self.b0, t + 1)
        self.n = len(idx)
        self.xr = self.n - 1 + extra_right
        self.lo, self.hi = float(np.min(A["l"][idx])), float(np.max(A["h"][idx]))
        self.span = (self.hi - self.lo) or 1.0
        self.fig = go.Figure(go.Candlestick(x=np.arange(self.n), open=A["o"][idx], high=A["h"][idx], low=A["l"][idx], close=A["c"][idx],
                                            showlegend=False, increasing_line_color="#26a69a", decreasing_line_color="#ef5350"))
        self.fig.update_layout(template="plotly_dark", width=WIDTH, height=HEIGHT, paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                               title=dict(text=title, font=dict(size=17)), showlegend=False, font=dict(size=12))
        self.right, self.inner, self.far = [], [], []
        self.used = {k: 0 for k in CC.keys_for(image)}
        self.tsi = {str(x): i for i, x in enumerate(C.ts)}

    def on(self, key):
        return CC.on(self.cfg, key, self.image)

    def hit(self, key, n=1):
        self.used[key] = self.used.get(key, 0) + n

    def X(self, b):
        return None if b is None or b < self.b0 or b > self.t else int(b - self.b0)

    def vis(self, y):
        return self.lo - 0.06 * self.span <= y <= self.hi + 0.30 * self.span

    def seg(self, b1, p1, b2, p2):
        """bar निर्देशांकातील सरळ भाग window ला कापून ⇒ (x1, y1, x2, y2, कापला?) | None."""
        if b2 < self.b0 or b1 > self.t or b2 == b1 and b1 < self.b0:
            return None
        cut = b1 < self.b0
        y1 = p1 + (p2 - p1) * (self.b0 - b1) / (b2 - b1) if cut and b2 != b1 else p1
        y2 = p2 if b2 <= self.t else p1 + (p2 - p1) * (self.t - b1) / (b2 - b1)
        return self.X(max(b1, self.b0)), y1, self.X(min(b2, self.t)), y2, cut

    def rlabel(self, y, txt, col):
        """उजव्या स्तंभातलं लेबल (finish मध्ये एकमेकांवर न येता मांडतो). दिसणाऱ्या भागाबाहेर ⇒ legend मध्ये."""
        txt = txt if len(txt) <= 64 else txt[:63] + "…"
        if self.vis(y):
            self.right.append([float(y), float(y), txt, col])
        else:
            self.far.append(f"{txt} ({y:,.0f})")

    def label(self, x, y, txt, col, up=True, size=11):
        """chart आतलं लेबल: जवळच्या लेबलशी टक्कर ⇒ थोडं पुढे सरकवतो."""
        frac = (y - self.lo) / self.span
        sh = 14
        while any(abs(x - a) <= 2 and abs(frac + (sh if up else -sh) / 700 - b) < 0.028 for a, b in self.inner) and sh < 120:
            sh += 14
        self.inner.append((x, frac + (sh if up else -sh) / 700))
        self.fig.add_annotation(x=x, y=y, text=txt, showarrow=False, yshift=sh if up else -sh, font=dict(size=size, color=col))

    def hline(self, y, col, txt, dash="dash", w=1.2, x0=0):
        if not self.vis(y):
            self.far.append(f"{txt} ({y:,.0f})")
            return
        self.fig.add_shape(type="line", x0=x0, x1=self.xr, y0=y, y1=y, line=dict(color=col, width=w, dash=dash))
        self.rlabel(y, txt, col)

    def band(self, bot, top, fill, line=None, x0=0, x1=None, dash="solid"):
        self.fig.add_shape(type="rect", x0=x0, x1=self.xr if x1 is None else x1, y0=bot, y1=top, fillcolor=fill, layer="below",
                           line=dict(color=line or "rgba(0,0,0,0)", width=1 if line else 0, dash=dash))

    def box(self, text, x=0.005, y=0.995, xanchor="left"):
        self.fig.add_annotation(x=x, y=y, xref="paper", yref="paper", xanchor=xanchor, yanchor="top", align="left", showarrow=False,
                                text=text, font=dict(size=11), bgcolor="rgba(14,17,23,0.88)", bordercolor="#455a64", borderwidth=1)

    def finish(self, legend_keys=""):
        y0 = self.lo - 0.06 * self.span
        y1 = self.hi + 0.30 * self.span
        nleg = 6
        plot_px = HEIGHT - 70 - (40 + 16 * (nleg + 1))
        gap = 15.0 * (y1 - y0) / max(plot_px, 100)                              # एका ओळीची उंची (price एककात)
        self.right.sort(key=lambda r: r[0])
        keep = int((y1 - y0) / gap)
        if len(self.right) > keep:                                             # जागा नाही ⇒ जास्तीचे legend मध्ये
            for r in self.right[keep:]:
                self.far.append(f"{r[2]} ({r[1]:,.0f})")
            self.right = self.right[:keep]
        for i in range(len(self.right)):
            lo_ok = y0 + gap * i if i == 0 else self.right[i - 1][0] + gap
            self.right[i][0] = max(self.right[i][0], lo_ok)
        over = (self.right[-1][0] - (y1 - gap / 2)) if self.right else 0
        if over > 0:                                                           # वर ओसंडलं ⇒ खाली सरकवा (क्रम आणि gap तसाच)
            for i in range(len(self.right) - 1, -1, -1):
                lim = (y1 - gap / 2) if i == len(self.right) - 1 else self.right[i + 1][0] - gap
                self.right[i][0] = min(self.right[i][0], lim)
        px = max(plot_px, 100) / (y1 - y0)
        for y, y_true, txt, col in self.right:
            dy = (y - y_true) * px
            moved = abs(dy) > 3
            self.fig.add_annotation(x=self.xr, y=y_true, text=txt, showarrow=moved, arrowhead=0, arrowwidth=0.6, arrowcolor=col,
                                    ax=14, ay=-dy if moved else 0, xanchor="left", font=dict(size=10, color=col), yshift=0 if moved else 0)
        top = y1
        rows = []
        for k in CC.keys_for(self.image):
            nm = CC.CONCEPTS[k][0]
            if not self.on(k):
                rows.append(f"<span style='color:#546e7a'>✕ {nm} (बंद)</span>")
            elif self.used.get(k):
                rows.append(f"✓ {nm}" + (f" ({self.used[k]})" if self.used[k] > 1 else ""))
            else:
                rows.append(f"<span style='color:#90a4ae'>NA (अजून नाही) {nm}</span>")
        lines, cur = [], ""
        for r in rows:
            if len(cur) + len(r) > 200:
                lines.append(cur)
                cur = ""
            cur += ("" if not cur else " · ") + r
        lines.append(cur)
        if self.far:
            lines.append("chart बाहेर: " + " · ".join(self.far[:8]))
        if legend_keys:
            lines.append(legend_keys)
        lines.append("Volume: NA (index) · सगळं t पर्यंत माहीत (known_at ≤ t) · फक्त दाखवणं, order नाही"
                     + (" · W / D / 1H: एक candle = एक session ⇒ engine चे वेळ-gates (entry वेळ) इथे अर्थहीन" if self.C.synthetic else ""))
        self.fig.add_annotation(x=0.0, y=-0.06, xref="paper", yref="paper", xanchor="left", yanchor="top", align="left", showarrow=False,
                                text="<br>".join(lines), font=dict(size=10, color="#b0bec5"))
        self.fig.update_layout(margin=dict(l=75, r=400, t=70, b=40 + 16 * (max(len(lines), nleg) + 1)))
        ts = self.C.real_ts.iloc[self.b0:self.t + 1].reset_index(drop=True)
        k = max(1, self.n // 10)
        ticks = list(range(0, self.n, k))
        self.fig.update_xaxes(tickvals=ticks, ticktext=[pd.Timestamp(ts[i]).strftime(FMT[self.tf]) for i in ticks], rangeslider_visible=False,
                              showgrid=False, range=[-1, self.xr + 1])
        self.fig.update_yaxes(side="left", tickformat=",.0f", gridcolor="#263238",          # उजवा स्तंभ labels साठी
                              range=[y0, y1])
        self.fig._mtf_used = dict(self.used)                                   # tests / summary: कोणती संकल्पना किती वेळा काढली
        return self.fig


# ------------------------------------------------------------------------------------------------------------- थर काढणं
def draw_swings(cv):
    C, t = cv.C, cv.t
    piv = C.res["pivots"]
    higher = {}
    for d in (2, 3):
        for p in piv.get(d, []):
            if p.confirm_bar <= t and not p.warmup:
                higher[p.bar] = max(higher.get(p.bar, 0), d)
    for d in (1, 2, 3):
        ps = [p for p in piv.get(d, []) if p.confirm_bar <= t and not p.warmup]
        vis = [p for p in ps if cv.X(p.bar) is not None]
        chain = [p for p in ps if p.bar < cv.b0][-1:] + vis
        xs, ys = [], []
        for a, b in zip(chain, chain[1:]):
            sg = cv.seg(a.bar, a.price, b.bar, b.price)
            if sg is not None:
                xs += [sg[0], sg[2], None]
                ys += [sg[1], sg[3], None]
        if xs:
            cv.fig.add_trace(cv.go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=DEG_COL[d], width=0.8 + 0.7 * d), opacity=0.6,
                                           showlegend=False, hoverinfo="skip"))
        for p in vis:
            if higher.get(p.bar, 0) > d:
                continue                                                        # त्याच टोकावर वरच्या degree ची खूण
            cv.label(cv.X(p.bar), p.price, f"D{d} " + D7._lbl(ps, p), DEG_COL[d], p.kind == "H", 10 + d)
            cv.hit("swings")


def draw_protected_range(cv):
    C, t = cv.C, cv.t
    if cv.on("protected"):
        for d, dash in ((1, "dot"), (2, "dash")):
            if d in C.st:
                pr = C.st[d]["states"][t].get("protected")
                if pr is not None:
                    cv.hline(float(pr), "#ff8a65" if d == 2 else "#ffab91", f"D{d} संरक्षित {pr:,.0f}", dash=dash)
                    cv.hit("protected")
    if cv.on("range"):
        b = DE.range_band(C, t)
        if b is not None and C.st[2]["states"][t]["trend"] == "RANGE":
            cv.band(b[1], b[0], "rgba(144,164,174,0.06)", "#90a4ae", dash="dot")
            cv.rlabel(b[0], f"D2 range वरची कड {b[0]:,.0f}", "#90a4ae")
            cv.rlabel(b[1], f"D2 range खालची कड {b[1]:,.0f}", "#90a4ae")
            cv.hit("range")
        r1 = C.st[1]["states"][t].get("range") if 1 in C.st else None
        if r1:
            cv.band(r1["bottom"], r1["top"], "rgba(144,164,174,0.04)", "#78909c", dash="dot")
            cv.rlabel(r1["top"], f"D1 range {r1['bottom']:,.0f}–{r1['top']:,.0f}", "#78909c")
            cv.hit("range")


def draw_I_K(cv, image):
    C, t = cv.C, cv.t
    I = C.trk[1].I_at(t)
    st = C.trk[1].state(t)
    if I is not None and cv.on("impulse") and image == "अ":
        o, e = I["origin"], I["end"]
        sg = cv.seg(o.bar, o.price, e.bar, e.price)
        if sg is not None:
            cv.fig.add_trace(cv.go.Scatter(x=[sg[0], sg[2]], y=[sg[1], sg[3]], mode="lines", line=dict(color="#fff176", width=4), opacity=0.55,
                                           showlegend=False, hoverinfo="skip"))
            cv.label(sg[2], e.price, f"I {'↑' if I['dir'] > 0 else '↓'} {o.price:,.0f} ⇒ {e.price:,.0f}", "#fff176", I["dir"] > 0, 12)
        else:
            cv.hline(float(e.price), "#fff176", f"I टोक {e.price:,.0f} (chart आधी)", w=1)
        cv.hit("impulse")
    kx = (st.get("K") or {}).get("extreme")
    if kx is not None and cv.on("k_extreme"):
        cv.hline(float(kx), "#ce93d8", f"K टोक {kx:,.0f}", dash="dot", w=1)
        cv.hit("k_extreme")
    kb = ((C.L5.get(t) or {}).get("k_lines") or {}).get("base")
    if kb and cv.on("k_base"):
        if draw_line(cv, kb, "#42a5f5", 1.8, "dash", "K आधार-रेघ"):
            cv.hit("k_base")
    if image == "अ" and cv.on("k_reset"):
        for b, px in k_resets(C, cv.b0, t):
            cv.label(cv.X(b), px, "K reset", "#ce93d8", I is not None and I["dir"] > 0, 10)
            cv.hit("k_reset")


def draw_line(cv, x, col, w, dash, txt):
    b1, b2 = cv.tsi.get(x["a1"]["ts"]), cv.tsi.get(x["a2"]["ts"])
    if b1 is None or b2 is None or b1 == b2:
        return False
    sl = (x["a2"]["price"] - x["a1"]["price"]) / (b2 - b1)
    sg = cv.seg(b1, x["a1"]["price"], cv.t, x["a1"]["price"] + sl * (cv.t - b1))
    if sg is None:
        return False
    cv.fig.add_trace(cv.go.Scatter(x=[sg[0], cv.n - 1], y=[sg[1], sg[3]], mode="lines", line=dict(color=col, width=w, dash=dash),
                                   showlegend=False, hoverinfo="skip"))
    cv.rlabel(sg[3], txt, col if "rgba" not in col else "#b0bec5")
    return True


def draw_lines(cv):
    if not cv.on("lines"):
        return
    for x in ((cv.C.L5.get(cv.t) or {}).get("lines") or []):
        cls = x.get("class")
        if cls == "तुटलेली" and (x.get("name") or "").startswith("fan"):
            continue
        strong = cls == "trade-योग्य" and not x.get("provisional")
        col = ("#ef5350" if x["kind"] == "H" else "#26a69a") if strong else "rgba(176,190,197,0.5)"
        tc = x.get("touches") or {}
        fb = f" · false-break {tc['false_break']}" if tc.get("false_break") else ""
        txt = f"{x.get('name') or 'रेघ'} · {cls}" + (" · provisional" if x.get("provisional") else "") + f" · {tc.get('held', 0)} स्पर्श{fb}"
        if draw_line(cv, x, col, 2.4 if strong else 1.0, "solid" if strong else "dot", txt):
            cv.hit("lines")
            if tc.get("false_break") and cv.on("sweep"):
                cv.hit("sweep")


def draw_zones(cv, image):
    C, t = cv.C, cv.t
    if cv.on("zones"):
        I = C.trk[1].I_at(t)
        ie = None if I is None else I["end"].bar
        for z in (C.Z.snap.get(t) or []):
            if z["status"] == "dead":
                continue
            sell = z["role"] == "seller"
            x0 = cv.X(z.get("pivot_bar"))
            cv.band(z["bottom"], z["top"], "rgba(239,83,80,0.13)" if sell else "rgba(38,166,154,0.13)", x0=x0 if x0 is not None else 0)
            self_ = ie is not None and z.get("pivot_bar") is not None and z["pivot_bar"] > ie
            tag = " · self" if (self_ and cv.on("zone_self")) else ""
            if tag:
                cv.hit("zone_self")
            cv.rlabel((z["top"] + z["bottom"]) / 2, f"{ROLE_MR[z['role']]} {'★' * int(z.get('stars', 1))} {zone_kind(z)} · {zone_state(C, z, t)}{tag}",
                      "#ef9a9a" if sell else "#80cbc4")
            cv.hit("zones")
    if image == "अ" and cv.on("zone_dead"):
        for z in dead_zones(C, cv.b0, t):
            x1 = cv.X(z["bar"])
            cv.band(z["bottom"], z["top"], "rgba(120,144,156,0.08)", "#78909c", x0=max(0, (x1 or 0) - 6), x1=x1, dash="dot")
            cv.label(x1, z["top"], f"मेला ✕ {z['why']}", "#90a4ae", True, 9)
            cv.hit("zone_dead")


def draw_sweeps(cv):
    if not cv.on("sweep"):
        return
    A = cv.C.A
    for b, lvl, txt, role in sweeps(cv.C, cv.b0, cv.t):
        up = role == "seller"                                                  # वरच्या टोकाचा sweep ⇒ high वर
        cv.label(cv.X(b), A["h"][b] if up else A["l"][b], f"⚡{txt}", "#ffcc80", up, 9)
        cv.hit("sweep")


def draw_upper(cv, up):
    if not up or not cv.on("upper_tf"):
        return
    for z in up["zones"]:
        if not cv.vis(z["top"]) and not cv.vis(z["bottom"]):
            continue
        cv.band(z["bottom"], z["top"], "rgba(255,255,255,0.035)", "rgba(255,255,255,0.18)", dash="dash")
        cv.rlabel(z["top"], f"{up['tf']} {ROLE_MR[z['role']]} zone {'★' * int(z.get('stars', 1))} (फिका)", "#78909c")
        cv.hit("upper_tf")
    for d, p in up["protected"]:
        cv.hline(float(p), "rgba(255,171,145,0.45)", f"{up['tf']} D{d} संरक्षित {p:,.0f} (फिका)", dash="dashdot", w=1)
        cv.hit("upper_tf")


def draw_abc(cv):
    if not cv.on("abc"):
        return None
    rec = cv.C.f1.out.get(cv.t) or {}
    if not rec.get("pref"):
        return None
    hj = F2.hyp_json(rec["pref"], cv.C.ts)
    xs, ys = [], []
    for p in hj.get("points") or []:
        b = cv.tsi.get(str(p["ts"]))
        x = cv.X(b)
        if x is None:
            continue
        xs.append(x)
        ys.append(p["price"])
        if p.get("label"):
            cv.label(x, p["price"], p["label"], "#80deea", True, 13)
    if xs:
        cv.fig.add_trace(cv.go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#80deea", width=1.6, dash="dot"), showlegend=False,
                                       hoverinfo="skip"))
    cv.hit("abc")
    return f"{PCH._name(hj)} · {F2.STATE_MR.get(hj['state'], hj['state'])} · गुण {hj['score']:.2f}"


def info_box(cv, td, extra=()):
    C, t = cv.C, cv.t
    rows = []
    if cv.on("topdown") and td:
        rows.append("<b>top-down</b>: " + td["strip"])
        cv.hit("topdown")
        rows += td["warn"][:2]
    if cv.on("trend"):
        tr = []
        for d, x in trend_rows(C, t):
            b = trend_since(C, t, d)
            since = f" ({pd.Timestamp(C.real_ts[b]).strftime(FMT[cv.tf])} पासून)" if b is not None else ""
            tr.append(f"D{d} {ARROW.get(x, '?')} {TREND_MR.get(x, x)}{since}")
        rows.append("<b>trend</b>: " + " · ".join(tr))
        cv.hit("trend")
    st = C.trk[1].state(t)
    I = C.trk[1].I_at(t)
    if cv.on("impulse") or cv.on("k_extreme"):
        rows.append(f"<b>I / K</b>: {st.get('state')}" + ("" if I is None else f" · I {'↑' if I['dir'] > 0 else '↓'} {I['origin'].price:,.0f} ⇒ "
                                                           f"{I['end'].price:,.0f}"))
    rows += [r for r in extra if r]
    cv.box("<br>".join(rows))


# ------------------------------------------------------------------------------------------------------------- दोन images
def structure_fig(C, t, cfg, td=None, up=None, title=""):
    cv = Canvas(C, t, C.tf, cfg, "अ", title)
    draw_upper(cv, up)
    draw_zones(cv, "अ")
    if cv.on("swings"):
        draw_swings(cv)
    draw_protected_range(cv)
    draw_lines(cv)
    draw_I_K(cv, "अ")
    abc = draw_abc(cv)
    draw_sweeps(cv)
    info_box(cv, td, [None if abc is None else f"<b>A-B-C</b>: {abc}"])
    return cv.finish("रंग: राखाडी D1 · सोनेरी D2 · नारिंगी D3 · पिवळी जाड I · जांभळी तुटक K टोक · निळी तुटक K आधार · लाल / हिरवे पट्टे "
                     "विक्रेते / खरेदीदार zones · फिकट तुटक पट्टे = वरच्या TF चे · ⚡ sweep / false-break")


def tf_review(C, t, cfg, s=None, cache=None):
    """B1 (window + आधीचे 15 candles lead-in, बाण फक्त window मधले) + B2 (t ला)."""
    s = s or RS.load()
    n_win = int(cfg["window"].get(C.tf, CC.WINDOW[C.tf]))
    b0 = max(0, t - n_win + 1)
    lead = max(0, b0 - 15)
    cache = {} if cache is None else cache
    marks = [m for m in RM.scan(C, list(range(lead, t + 1)), C.D, s, cache) if m["bar"] >= b0]
    return marks, RM.plan(C, t, s), cache


def entry_fig(C, t, cfg, marks, pl, cache, td=None, up=None, title="", s=None):
    s = s or RS.load()
    cv = Canvas(C, t, C.tf, cfg, "आ", title, extra_right=max(4, int(cfg["window"].get(C.tf, CC.WINDOW[C.tf])) // 10))
    draw_upper(cv, up)
    draw_zones(cv, "आ")
    if cv.on("swings"):
        draw_swings(cv)
    draw_protected_range(cv)
    draw_lines(cv)
    draw_I_K(cv, "आ")
    A = C.A
    # area-touch + B1 बाण + commitment
    cm_txt = None
    for i, mk in enumerate(marks, 1):
        x = cv.X(mk["bar"])
        a = mk["area"]
        ok = mk["type"] == "✅"
        if cv.on("area_touch") and x is not None:
            cv.band(a["bot"], a["top"], "rgba(255,213,79,0.10)", "#ffd54f", x0=max(0, x - 3), x1=min(cv.n - 1, x + 1))
            cv.hit("area_touch")
        if cv.on("b1") and x is not None:
            y = A["l"][mk["bar"]] if mk["dir"] > 0 else A["h"][mk["bar"]]
            col = "#66bb6a" if ok else "#ffee58"
            txt = f"{mk['type']}{i} {mk['side']}" + ("" if mk["final"] else " (चालू)")
            cv.fig.add_annotation(x=x, y=y, text=txt, showarrow=True, arrowhead=2, arrowcolor=col, ax=0,
                                  ay=(40 + 18 * (i % 3)) * (1 if mk["dir"] > 0 else -1), font=dict(size=11, color=col))
            cv.hit("b1")
        if ok and cv.on("commitment") and x is not None:
            cm = DE.commitment(C, mk["bar"], mk["dir"], {"band": (a["bot"], a["top"])})
            if cm:
                c0 = cv.X(cm["candle"]["i0"])
                cv.band(cm["candle"]["l"], cm["candle"]["h"], "rgba(255,213,79,0.0)", "#ffd54f", x0=(c0 or x) - 0.45, x1=x + 0.45)
                chk = cm["checks"]
                cm_txt = f"⭐ commitment ({mk['type']}{i}): " + " ".join(f"G{k}{'✔' if chk.get(f'G{k}') else ('NA' if f'G{k}' not in chk else '✗')}"
                                                                    for k in range(1, 9))
                cv.hit("commitment")
    if cm_txt is None and cv.on("commitment"):
        cmd = ((C.D.get(t) or {}).get("points") or {}).get("9_price_failure") or {}
        if cmd.get("candle"):
            chk = cmd["candle"].get("checks") or {}
            cm_txt = "⭐ engine commitment: " + " ".join(f"G{k}{'✔' if chk.get(f'G{k}') else ('NA' if f'G{k}' not in chk else '✗')}"
                                                       for k in range(1, 9))
            cv.hit("commitment")
    # correction संपतेय ✔ (K मधल्या bars, trade दिशेने)
    if cv.on("corr_end"):
        sym = {"shrink": "s", "overlap": "o", "counter-wick": "w"}
        for b in range(cv.b0, t + 1):
            ck = cache.get(b)
            if not ck or not (ck.get("c2") and ck.get("c3")):
                continue                                                        # फक्त area ला स्पर्श + pullback चालू असताना
            cm = corr_marks(C, b, ck["dir"], s)
            if cm:
                cv.label(cv.X(b), A["l"][b] if ck["dir"] > 0 else A["h"][b], "✔" + "".join(sym[x] for x in cm), "#a5d6a7", ck["dir"] < 0, 9)
                cv.hit("corr_end")
    mom = momentum_line(C, t)
    if mom and cv.on("corr_end"):
        cv.hit("corr_end")
    # RSI divergence
    l6 = C.L6.get(t) or {}
    last = l6.get("last")
    if last and cv.on("rsi_div"):
        x1, x2 = cv.X(last["L1"]["bar"]), cv.X(last["L2"]["bar"])
        if x1 is not None and x2 is not None:
            cv.fig.add_trace(cv.go.Scatter(x=[x1, x2], y=[last["L1"]["price"], last["L2"]["price"]], mode="lines+markers",
                                           line=dict(color="#b39ddb", width=2, dash="dot"), showlegend=False, hoverinfo="skip"))
            cv.label(x2, last["L2"]["price"], f"RSI {last['type']}", "#b39ddb", False, 10)
            cv.hit("rsi_div")
    # B2 योजना (उजवीकडे, शेवटच्या candle पुढे)
    if cv.on("b2"):
        xs = cv.n - 0.5
        for k, it in enumerate(pl.get("items") or [], 1):
            sell = it["dir"] < 0
            cv.band(it["bot"], it["top"], "rgba(239,83,80,0.22)" if sell else "rgba(38,166,154,0.22)", "#ffd54f", x0=xs, x1=cv.xr)
            tg = "—" if it.get("target") is None else f"{it['target']:,.0f}"
            cv.rlabel(it["top"] if sell else it["bot"], f"B2-{k} {it['side']} {it['bot']:,.0f}–{it['top']:,.0f} · SL {it['sl']:,.0f} · लक्ष्य {tg}"
                      f" · R:R {it.get('rr') or '—'}", "#ffd54f")
            cv.hit("b2")
        if pl.get("invalid"):
            cv.hit("b2")
    dec = C.D.get(t) or {}
    extra = []
    if cv.on("engine"):
        extra.append(f"<b>engine</b>: {dec.get('decision', '—')}" + (f" · अडला: {dec.get('gate')} — {dec.get('where_wrong')}"
                                                                     if dec.get("decision") != "setup" else f" · grade {dec.get('grade')}"))
        cv.hit("engine")
    if cv.on("b1"):
        extra.append(f"<b>B1</b>: ✅ {sum(m['type'] == '✅' for m in marks)} · 🟡 {sum(m['type'] == '🟡' for m in marks)} (एका चाचणीला एक बाण)")
    if cv.on("b2"):
        extra.append(f"<b>B2</b>: {len(pl.get('items') or [])} areas" + (f" · बाद: {pl['invalid']}" if pl.get("invalid") else ""))
    if cm_txt:
        extra.append(cm_txt)
    if mom and cv.on("corr_end"):
        extra.append(mom)
    if last and cv.on("rsi_div"):
        extra.append(f"RSI: {l6.get('label') or '—'} · शेवटची divergence {last['type']}")
    info_box(cv, td, extra)
    return cv.finish("✅ = ①②③④⑥ पूर्ण (त्या bar ला) · 🟡 = चाचणी झाली पण ④ / ⑥ नाही · ✔s shrink · ✔o overlap · ✔w counter-wick · "
                     "पिवळी चौकट = area-touch / commitment candle · उजवीकडे पिवळ्या कडेचे पट्टे = B2 योजना")


def display_fig(df, tf, title, n=80):
    """NIFTY W / D: फक्त राखाडी candles (holdout sealed — थर नाहीत, निर्णय नाही)."""
    import plotly.graph_objects as go
    d = df.tail(n).reset_index(drop=True)
    fig = go.Figure(go.Candlestick(x=np.arange(len(d)), open=d["open"], high=d["high"], low=d["low"], close=d["close"], showlegend=False,
                                   increasing_line_color="#9e9e9e", decreasing_line_color="#616161"))
    fig.update_layout(template="plotly_dark", width=WIDTH, height=HEIGHT, paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                      title=dict(text=title, font=dict(size=17)), showlegend=False, margin=dict(l=10, r=80, t=70, b=80))
    k = max(1, len(d) // 10)
    ticks = list(range(0, len(d), k))
    fig.update_xaxes(tickvals=ticks, ticktext=[pd.Timestamp(d["timestamp"][i]).strftime(FMT[tf]) for i in ticks], rangeslider_visible=False)
    fig.update_yaxes(side="right", tickformat=",.0f", gridcolor="#263238")
    fig.add_annotation(x=0.0, y=-0.08, xref="paper", yref="paper", xanchor="left", showarrow=False, font=dict(size=11, color="#b0bec5"),
                       text=f"display-only: {INS.label()} holdout sealed ⇒ या TF वर थर / B1 / B2 नाहीत (फक्त post-holdout candles, राखाडी)")
    return fig


def title(tf, image, asof, t_real=None):
    return (f"🗺 {INS.label()} {CC_TF.get(tf, tf)} · ({image}) {IMG_MR[image]} · {pd.Timestamp(asof):%d %b %Y %H:%M} पर्यंत"
            + (f" · शेवटची बंद candle {pd.Timestamp(t_real).strftime(FMT[tf])}" if t_real is not None else ""))


CC_TF = {"W": "Weekly", "D": "Daily", "1H": "1H", "15M": "15M"}
