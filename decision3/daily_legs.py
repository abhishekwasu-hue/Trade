"""decision3/daily_legs.py — Q32 (Abhi): Daily swings साठी legs2 / patterns2 adapter — leg impulse आहे की corrective.

legs2 / patterns2 intraday swings2 (15M degrees, sessions, futures volume) वर चालतात; इथे त्यांचेच नियम Daily pivots वर:
  • स्वभाव C (legs2 थर 2 §3, `legs2.measure.candle_metrics` + `legs2.measure2.c_score` सारखं): leg च्या Daily candles चे ER,
    (1 − overlap), body, दिशेच्या candles — त्याच Daily मालिकेतल्या आधीच्या ≤ `baseline_legs` confirmed legs शी percentile; ≥ c_hi ⇒
    IMP, ≤ c_lo ⇒ COR. Daily ला futures volume नाही ⇒ V नाही (C एकटाच). Daily gap हा leg चाच भाग (overnight वजा नाही).
    Baseline < `baseline_min` ⇒ NA (warm-up). Thresholds legs2 settings2 मधूनच — नवीन संख्या नाहीत.
  • रचना (patterns2 नियम): leg च्या आतले confirmed pivots (टोक ते टोक) सर्वात लहान आतल्या जोडीपासून क्रमाने गाळून 5 / 3 waves.
    5-wave वाचन `patterns2.rules.impulse` (पक्के नियम) पार ⇒ "impulse"; नाहीतर 3-wave (zigzag / flat, `patterns2.rules2`) ⇒
    "corrective"; आतले pivots नाहीत ⇒ "single".
  • kind: "impulse" = रचना impulse किंवा C = IMP; "corrective" = (रचना corrective आणि C ≠ IMP) किंवा C = COR; बाकी "unclear".
Shadow / पुरावा: ही फाइल order देत नाही; daily.fold_impulse Q28 (trend सुरुवात) साठी वापरतो.
"""
import numpy as np

from legs2 import measure as LM
from legs2 import settings2 as LS2
from patterns2 import rules as PR
from patterns2 import rules2 as PR2
from patterns2 import settings2 as PS2

IMP, NEU, COR = LM.IMP, LM.NEU, LM.COR
METRICS = ("er", "overlap", "body", "dirc")
CODE = {IMP: "IMP", NEU: "NEU", COR: "COR"}                               # English codes (caption / JSON)


def arrays(d):
    """Daily OHLC ⇒ legs2 candle_metrics चा A; first = False सगळीकडे (Daily gap leg चाच भाग)."""
    return {"o": d["open"].to_numpy(float), "h": d["high"].to_numpy(float), "l": d["low"].to_numpy(float),
            "c": d["close"].to_numpy(float), "first": np.zeros(len(d), bool)}


def metrics(A, i0, i1, dirn):
    """Leg bars (i0, i1] वरची legs2 candle मापं; < 1 bar ⇒ None."""
    if i1 <= i0:
        return None
    return LM.candle_metrics(A, int(i0), int(i1), int(dirn))[0]


def c_class(raw, base_raws, s=None):
    """legs2 C: percentile ची सरासरी (overlap उलट) ⇒ (C, cls). base < baseline_min ⇒ (None, NA)."""
    s = s or LS2.DEFAULTS
    base = [b for b in base_raws if b is not None][-int(s["baseline_legs"]):]
    if raw is None or len(base) < int(s["baseline_min"]):
        return None, "NA"
    pct = []
    for m in METRICS:
        x = raw.get(m)
        vals = [b[m] for b in base if b.get(m) is not None]
        if x is None or not vals:
            continue
        p = LM.pct_rank(x, vals)
        pct.append(1.0 - p if m == "overlap" else p)
    if not pct:
        return None, "NA"
    C = float(np.mean(pct))
    return C, LM.classify(C, s["c_hi"], s["c_lo"])


def reduce_waves(x):
    """टोक ते टोक आलटून पालटून किंमती x[0..n] ⇒ {n: x_n} (5 / 3 / 1 waves): दर वेळी सर्वात लहान **आतली** जोडी (दोन्ही टोकं
    सोडून) गाळतो — जोडी गाळल्यावरही बाकीची टोकं टोकच राहतील तेव्हाच (उदा. up leg: गाळलेला H पुढच्या H पेक्षा उंच नाही, गाळलेला L
    मागच्या L पेक्षा खाली नाही)."""
    x = list(map(float, x))
    out = {len(x) - 1: list(x)}
    d = 1 if x[-1] > x[0] else -1
    while len(x) - 1 > 1:
        best = None
        for i in range(1, len(x) - 2):
            a, b = x[i], x[i + 1]
            # x[i] हा leg-दिशेचा टोक असेल (i विषम ⇒ d दिशा) तर पुढच्या त्याच प्रकारच्या टोकापलीकडे नसावा; उलट टोक मागच्याच्या आत
            sgn = d if i % 2 == 1 else -d
            ok = (x[i + 2] - a) * sgn >= 0 and (b - x[i - 1]) * sgn >= 0
            size = abs(b - a)
            if ok and (best is None or size < best[0]):
                best = (size, i)
        if best is None:
            break
        i = best[1]
        x = x[:i] + x[i + 2:]
        out.setdefault(len(x) - 1, list(x))
    return out


def structure(prices):
    """रिटर्न {"structure": impulse / corrective / single, "n": मूळ waves, "form": zigzag / flat / None}."""
    n = len(prices) - 1
    if n <= 1:
        return {"structure": "single", "n": max(n, 0), "form": None}
    red = reduce_waves(prices)
    x5 = red.get(5)
    if x5 is not None and PR.impulse(x5, done=True):
        return {"structure": "impulse", "n": n, "form": "impulse"}
    x3 = red.get(3)
    form = None
    if x3 is not None:
        s = PS2.DEFAULTS
        form = "zigzag" if PR2.zigzag(x3, True, s)[0] else ("flat" if PR2.flat(x3, True, s)[0] else None)
    return {"structure": "corrective", "n": n, "form": form or "3-wave"}


def _m(A, i0, i1, dirn, cache):
    if cache is None:
        return metrics(A, i0, i1, dirn)
    k = (int(i0), int(i1), int(dirn))
    if k not in cache:
        cache[k] = metrics(A, i0, i1, dirn)
    return cache[k]


def classify(A, seq, a_bar, a_price, b_bar, b_price, upto_confirm, s=None, cache=None, inner_seq=None):
    """एक leg (a ⇒ b, b चालू टोक असू शकतो): seq = त्याच degree चे confirmed pivots (DPivot) — आधी पूर्ण झालेले legs C baseline साठी;
    inner_seq = एक degree खालचे pivots (आतली रचना; seq आलटून पालटून असल्याने त्याच degree चे आतले pivots नसतात). confirm_bar ≤
    upto_confirm. legs2 नियम: ≤ short_leg_bars bars चा leg ⇒ C तटस्थ, baseline बाहेर. रिटर्न dict kind / structure / form / C / c_cls / n."""
    s = s or LS2.DEFAULTS
    dirn = 1 if b_price > a_price else -1
    conf = [p for p in seq if p.confirm_bar <= upto_confirm]
    inner_src = conf if inner_seq is None else [p for p in inner_seq if p.confirm_bar <= upto_confirm]
    inner = sorted((p for p in inner_src if a_bar < p.bar < b_bar), key=lambda p: p.bar)
    prices, kinds = [a_price], ["L" if dirn > 0 else "H"]
    for p in inner:                                                       # आलटून पालटून; सलग तोच प्रकार ⇒ जास्त टोकाचा
        if p.kind != kinds[-1]:
            prices.append(p.price)
            kinds.append(p.kind)
        elif len(prices) > 1 and (p.price - prices[-1]) * (1 if p.kind == "H" else -1) > 0:
            prices[-1] = p.price
    if len(prices) > 1 and kinds[-1] == ("H" if dirn > 0 else "L"):     # शेवटचा आतला pivot leg-दिशेचा ⇒ b शी merge
        prices, kinds = prices[:-1], kinds[:-1]
    prices.append(b_price)
    st = structure(prices)
    short = int(s["short_leg_bars"])
    done = sorted((p for p in conf if p.bar <= a_bar), key=lambda p: p.bar)   # a पर्यंत पूर्ण झालेले Daily legs (C baseline)
    pairs = [(p, q) for p, q in zip(done, done[1:]) if p.kind != q.kind and q.bar - p.bar > short][-int(s["baseline_legs"]):]
    base = [_m(A, p.bar, q.bar, 1 if q.price > p.price else -1, cache) for p, q in pairs]
    if b_bar - a_bar <= short:
        C, cls = None, NEU                                                 # legs2 §3: 1–2 bars ⇒ तटस्थ
    else:
        C, cls = c_class(_m(A, a_bar, b_bar, dirn, cache), base, s)
    cls = CODE.get(cls, cls)
    if st["structure"] == "impulse" or cls == "IMP":
        kind = "impulse"
    elif cls == "COR" or st["structure"] == "corrective":
        kind = "corrective"
    else:
        kind = "unclear"
    return {"kind": kind, "structure": st["structure"], "form": st["form"], "n": st["n"], "C": C, "c_cls": cls}


def tag(c):
    """छोटी English नोंद (caption / why): उदा. "impulse (5-wave, C IMP)"."""
    if not c:
        return "—"
    return f"{c['kind']} ({c['form'] or c['structure']}, C {c['c_cls']})"
