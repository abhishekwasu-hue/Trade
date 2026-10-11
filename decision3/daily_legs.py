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


def reduce_counted(x):
    """reduce_waves सारखंच, पण प्रत्येक उरलेल्या wave मध्ये मूळ किती पाय (subdivision) — {n: (prices, counts)}."""
    x = list(map(float, x))
    cnt = [1] * (len(x) - 1)
    out = {len(x) - 1: (list(x), list(cnt))}
    d = 1 if x[-1] > x[0] else -1
    while len(x) - 1 > 1:
        best = None
        for i in range(1, len(x) - 2):
            a, b = x[i], x[i + 1]
            sgn = d if i % 2 == 1 else -d
            ok = (x[i + 2] - a) * sgn >= 0 and (b - x[i - 1]) * sgn >= 0
            if ok and (best is None or abs(b - a) < best[0]):
                best = (abs(b - a), i)
        if best is None:
            break
        i = best[1]
        merged = cnt[i - 1] + cnt[i] + cnt[i + 1]
        x = x[:i] + x[i + 2:]
        cnt = cnt[:i - 1] + [merged] + cnt[i + 2:]
        out.setdefault(len(x) - 1, (list(x), list(cnt)))
    return out


MOTIVE = ("impulse", "diagonal")
CORRECTIVE = ("zigzag", "flat", "triangle", "combination", "3-wave")
COMPLETE = ("zigzag", "flat", "triangle", "combination")                  # Abhi item 4: combination = दोन पूर्ण corrective patterns
                                                                       # (W, Y [, Z]) X ने जोडलेले — न ओळखलेला "3-wave" W / Y नाही
_READ_CACHE = {}


def _segments(prices, counts):
    """reduced waves ⇒ प्रत्येक wave चे मूळ बिंदू (subdivision)."""
    out, k = [], 0
    for c in counts:
        out.append(list(prices[k:k + c + 1]))
        k += c
    return out


def _is_motive(seg):
    return len(seg) - 1 == 1 or read_counter(seg)["family"] in MOTIVE


def _is_corrective(seg):
    return len(seg) - 1 == 1 or read_counter(seg)["family"] in CORRECTIVE


def read_counter(prices):
    """ABC_FIX / fixture library: एक संपूर्ण चाल (टोक ते टोक, एक degree खालचे pivots) Elliott नियमांनी वाचा (Frost & Prechter —
    docs/research/elliott_rules.md). प्रत्येक wave ची subdivision recursive वाचली: impulse 5-3-5-3-5 (1/3/5 motive, 2/4 corrective),
    diagonal (wedge, 3-3-3-3-3), triangle (sideways, 3-3-3-3-3), combination (W आणि Y स्वतः corrective), zigzag 5-3-5 (a, c motive),
    flat 3-3-5 (a corrective, c motive). एक-पायी wave ⇒ दोन्ही चालतो (तपशील दिसत नाही). Ratios नाहीत — फक्त नियम + patterns2 settings.
    रिटर्न {"family", "n"}: impulse / diagonal / triangle / combination / zigzag / flat / 3-wave / single."""
    key = tuple(round(float(v), 6) for v in prices)
    if key in _READ_CACHE:
        return _READ_CACHE[key]
    if len(_READ_CACHE) > 20000:
        _READ_CACHE.clear()
    n = len(prices) - 1
    if n <= 1:
        return {"family": "single", "n": max(n, 0)}
    _READ_CACHE[key] = {"family": "3-wave", "n": n}                       # recursion guard
    red = reduce_counted(prices)
    s2 = PS2.DEFAULTS
    fam = None
    p5 = red.get(5)
    if p5 is not None and n >= 5:
        x5, c5 = p5
        seg5 = _segments(prices, c5)
        corr_all = all(_is_corrective(g) for g in seg5)
        if PR.impulse(x5, done=True) and all(_is_motive(seg5[k]) for k in (0, 2, 4)) and all(_is_corrective(seg5[k]) for k in (1, 3)):
            fam = "impulse"
        elif (corr_all or (all(_is_motive(seg5[k]) for k in (0, 2, 4)) and all(_is_corrective(seg5[k]) for k in (1, 3)))) and \
                (PR.wedge(x5, done=True, kind="contracting") or PR.wedge(x5, done=True, kind="expanding")):
            fam = "diagonal"                                               # ending 3-3-3-3-3 / leading 5-3-5-3-5 (4 overlaps 1)
        elif corr_all and any(PR.triangle(x5, done=True, kind=k)[0] for k in ("contracting", "expanding")) and not PR.impulse(x5, True):
            fam = "triangle"
        elif all(len(seg5[k]) > 2 and read_counter(seg5[k])["family"] in COMPLETE for k in (0, 2, 4)) and \
                all(_is_corrective(seg5[k]) for k in (1, 3)):
            fam = "combination"                                            # triple three W-X-Y-X-Z (W, Y, Z स्वतः corrective)
    p9 = red.get(9)
    if fam is None and p9 is not None and n >= 9:                          # extended wave: 9 waves (विस्तारलेल्या wave चे 5 उप-waves
        x9, c9 = p9                                                        # इतर waves इतकेच मोठे — Frost & Prechter "extensions")
        seg9 = _segments(prices, c9)
        for ext in (0, 2, 4):                                              # 1st / 3rd / 5th extended
            grp = [[k] for k in range(9)]
            j = ext
            waves = grp[:j] + [list(range(j, j + 5))] + grp[j + 5:]
            if len(waves) != 5:
                continue
            x5e = [x9[0]] + [x9[w[-1] + 1] for w in waves]
            segs = [sum((seg9[k][1:] if t else seg9[k] for t, k in enumerate(w)), []) for w in waves]
            if PR.impulse(x5e, done=True) and all(_is_motive(segs[k]) for k in (0, 2, 4)) and \
                    all(_is_corrective(segs[k]) for k in (1, 3)):
                fam = "impulse"
                break
    p3 = red.get(3)
    if fam is None and p3 is not None:
        x3, c3 = p3
        a_seg, _, c_seg = _segments(prices, c3)
        if len(a_seg) > 2 and len(c_seg) > 2 and read_counter(a_seg)["family"] in COMPLETE and \
                read_counter(c_seg)["family"] in COMPLETE:
            fam = "combination"                                            # W आणि Y स्वतः corrective (double / triple three, double zigzag)
        elif PR2.zigzag(x3, True, s2)[0] and _is_motive(a_seg) and _is_motive(c_seg):
            fam = "zigzag"
        elif PR2.flat(x3, True, s2)[0] and _is_corrective(a_seg) and _is_motive(c_seg):
            fam = "flat"
        if fam is None:                                                    # B सर्वात टोकाच्या बिंदूवर संपत नाही (उदा. triangle B चा e)
            ia = c3[0]
            for ib in range(ia + 1, n, 2):
                xb = [prices[0], prices[ia], prices[ib], prices[n]]
                b_seg, c2 = list(prices[ia:ib + 1]), list(prices[ib:])
                if (prices[ib] - prices[0]) * (prices[n] - prices[0]) < 0 or len(c2) < 2:
                    continue
                if not (_is_corrective(b_seg) and _is_motive(c2)):
                    continue
                if PR2.zigzag(xb, True, s2)[0] and _is_motive(a_seg):
                    fam = "zigzag"
                    break
                if PR2.flat(xb, True, s2)[0] and _is_corrective(a_seg):
                    fam = "flat"
                    break
    out = {"family": fam or "3-wave", "n": n}
    _READ_CACHE[key] = out
    return out


def wave_ends(prices):
    """Chart (§5 / Abhi review): read_counter ने जे family वाचलं त्याच्या waves चे टोक — prices मधले index (0 = सुरुवात सोडून).
    read_counter चाच शाखा-क्रम (त्याचं वर्तन बदलत नाही, फक्त टोकं दाखवतो): zigzag / flat / 3-wave ⇒ a b c, triangle ⇒ a–e,
    combination ⇒ W X Y (X Z). impulse / diagonal / single ⇒ टोकं नाहीत. रिटर्न (family, [(index, letter)])."""
    fam = read_counter(prices)["family"]
    n = len(prices) - 1
    red = reduce_counted(prices)
    cum = lambda c: [sum(c[:k + 1]) for k in range(len(c))]              # noqa: E731
    if fam == "triangle" and red.get(5):
        return fam, list(zip(cum(red[5][1]), "abcde"))
    if fam == "combination":
        p5 = red.get(5)
        if p5 is not None and n >= 5:
            seg5 = _segments(prices, p5[1])
            if all(len(seg5[k]) > 2 and read_counter(seg5[k])["family"] in COMPLETE for k in (0, 2, 4)) and \
                    all(_is_corrective(seg5[k]) for k in (1, 3)):
                return fam, list(zip(cum(p5[1]), ("W", "X", "Y", "X", "Z")))
        if red.get(3):
            return fam, list(zip(cum(red[3][1]), ("W", "X", "Y")))
        return fam, []
    if fam not in ("zigzag", "flat", "3-wave") or not red.get(3):
        return fam, []
    x3, c3 = red[3]
    ends = cum(c3)
    if fam == "3-wave":
        return fam, list(zip(ends, "abc"))
    s2 = PS2.DEFAULTS
    a_seg, _, c_seg = _segments(prices, c3)
    main = (PR2.zigzag(x3, True, s2)[0] and _is_motive(a_seg) and _is_motive(c_seg)) if fam == "zigzag" else \
        (PR2.flat(x3, True, s2)[0] and _is_corrective(a_seg) and _is_motive(c_seg))
    if not main:                                                           # read_counter ची B-शोध शाखा (B सर्वात टोकाला नाही)
        ia = c3[0]
        for ib in range(ia + 1, n, 2):
            xb = [prices[0], prices[ia], prices[ib], prices[n]]
            b_seg, c2 = list(prices[ia:ib + 1]), list(prices[ib:])
            if (prices[ib] - prices[0]) * (prices[n] - prices[0]) < 0 or len(c2) < 2:
                continue
            if not (_is_corrective(b_seg) and _is_motive(c2)):
                continue
            if fam == "zigzag" and PR2.zigzag(xb, True, s2)[0] and _is_motive(a_seg):
                ends = [ia, ib, n]
                break
            if fam == "flat" and PR2.flat(xb, True, s2)[0] and _is_corrective(a_seg):
                ends = [ia, ib, n]
                break
    return fam, list(zip(ends, "abc"))


def structure(prices, elliott=False):
    """रिटर्न {"structure": impulse / corrective / single, "n": मूळ waves, "form": ...}. Default (Q28 / Q36 nature gates): 5-wave
    reduction वर impulse नियम, नाहीतर zigzag / flat / 3-wave. elliott=True (ABC_FIX — संपूर्ण counter-move, correction शेवट, box family):
    read_counter चं subdivision वाचन (impulse / diagonal ⇒ "impulse"; zigzag / flat / triangle / combination / 3-wave ⇒ "corrective")."""
    n = len(prices) - 1
    if n <= 1:
        return {"structure": "single", "n": max(n, 0), "form": None}
    if elliott:
        fam = read_counter(prices)["family"]
        if fam in ("impulse", "diagonal"):
            return {"structure": "impulse", "n": n, "form": fam}
        return {"structure": "corrective", "n": n, "form": fam}
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


def classify(A, seq, a_bar, a_price, b_bar, b_price, upto_confirm, s=None, cache=None, inner_seq=None, elliott=False):
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
    st = structure(prices, elliott)
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
