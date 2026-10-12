"""decision3/accepted_legs.py — Abhi ने स्वीकारलेली trend-degree वाचनं (CD14): "हा leg impulse आहे" — default / Telegram chart वर घन
impulse, "not verified" मजकूर नाही; structure / anatomy votes फक्त debug view + JSON मध्ये.

नोंदी `decision3/data/accepted_legs.json` मध्ये (env `DECISION3_ACCEPTED_LEGS` ⇒ दुसरी file, उदा. private trade-data): symbol, timeframe
("1D"), from / to (leg च्या टोकांच्या तारखा), reading ("impulse"), direction ("up" / "down"), source. Code मध्ये तारीख / symbol नाही —
जुळवणं फक्त नोंदींवरून.

जुळवणं (match): chart वर काढलेल्या trend leg ची स्वतःची pivot टोकं (from / to bar) ⇔ नोंदीच्या तारखा, प्रत्येक टोक ± `daily_pivot_n`
sessions आत, आणि दिशा तीच. का ± daily_pivot_n: pivot म्हणजे दोन्ही बाजूंच्या n bars पेक्षा टोकाचा bar (`daily.pivots_pivot`: डावीकडे strict,
उजवीकडे ≥) ⇒ n sessions च्या आत त्याच प्रकारचा दुसरा pivot असू शकत नाही — जुळणं एकाच pivot शी, आणि vendor च्या तारखेतला / सुट्टीचा
फरक सामावतो. किंमत कधीच वापरत नाही (tuning नाही). Engine (trend / phase / protected) बदलत नाही — फक्त दाखवणं."""
import json
import os

import pandas as pd

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "accepted_legs.json")
ENV = "DECISION3_ACCEPTED_LEGS"
READINGS = ("impulse",)
DIRECTIONS = {"up": 1, "down": -1}
TIMEFRAMES = ("1D",)
KEYS = ("symbol", "timeframe", "from", "to", "reading", "direction", "source")


def validate(rec):
    """एक नोंद ⇒ साफ dict (from / to = pd.Timestamp); चूक ⇒ ValueError (कारणासह)."""
    if not isinstance(rec, dict):
        raise ValueError(f"accepted leg: not an object: {rec!r}")
    miss = [k for k in KEYS if k not in rec]
    if miss:
        raise ValueError(f"accepted leg: missing {miss}: {rec!r}")
    sym = str(rec["symbol"]).strip().upper()
    if not sym:
        raise ValueError(f"accepted leg: empty symbol: {rec!r}")
    if rec["timeframe"] not in TIMEFRAMES:
        raise ValueError(f"accepted leg: timeframe must be one of {TIMEFRAMES}: {rec!r}")
    if rec["reading"] not in READINGS:
        raise ValueError(f"accepted leg: reading must be one of {READINGS}: {rec!r}")
    if rec["direction"] not in DIRECTIONS:
        raise ValueError(f"accepted leg: direction must be up / down: {rec!r}")
    if not str(rec["source"]).strip():
        raise ValueError(f"accepted leg: empty source: {rec!r}")
    try:
        a, b = pd.Timestamp(rec["from"]).normalize(), pd.Timestamp(rec["to"]).normalize()
    except (TypeError, ValueError) as e:
        raise ValueError(f"accepted leg: bad date: {rec!r}") from e
    if not a < b:
        raise ValueError(f"accepted leg: from must be before to: {rec!r}")
    return {"symbol": sym, "timeframe": rec["timeframe"], "from": a, "to": b, "reading": rec["reading"],
            "direction": rec["direction"], "dir": DIRECTIONS[rec["direction"]], "source": str(rec["source"]).strip()}


def load(path=None, symbol=None, timeframe="1D"):
    """File ⇒ तपासलेल्या नोंदी (symbol / timeframe ने गाळलेल्या). File नाही ⇒ [] (नोंदी नसणं ही चूक नाही); चुकीची file ⇒ ValueError.
    त्याच symbol / timeframe च्या दोन नोंदी एकमेकांवर येत असतील (overlap) ⇒ ValueError — एका leg ला एकच वाचन."""
    p = path or os.environ.get(ENV) or DEFAULT_PATH
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        raw = json.load(fh)
    recs = raw.get("legs") if isinstance(raw, dict) else raw
    if not isinstance(recs, list):
        raise ValueError(f"accepted legs file {p}: expected a list under 'legs'")
    out = [validate(r) for r in recs]
    for i, x in enumerate(out):
        for y in out[i + 1:]:
            if (x["symbol"], x["timeframe"]) == (y["symbol"], y["timeframe"]) and x["from"] < y["to"] and y["from"] < x["to"]:
                raise ValueError(f"accepted legs file {p}: overlapping records {x['from'].date()}..{x['to'].date()} and "
                                 f"{y['from'].date()}..{y['to'].date()} ({x['symbol']})")
    sym = None if symbol is None else str(symbol).upper()
    return [x for x in out if (sym is None or x["symbol"] == sym) and x["timeframe"] == timeframe]


def session_of(ts, day):
    """तारीख ⇒ त्या session चा bar (तो दिवस session नसेल ⇒ पुढचा session); frame च्या बाहेर ⇒ None."""
    ts = pd.DatetimeIndex(pd.to_datetime(ts)).normalize()
    if not len(ts) or day < ts[0] or day > ts[-1]:
        return None
    return int(ts.searchsorted(day, side="left"))


def match(leg, rec, ts, slack):
    """Leg (bars) ⇔ नोंद (तारखा): दिशा तीच, from आणि to दोन्ही ± slack sessions आत."""
    if int(leg["dir"]) != rec["dir"]:
        return False
    a, b = session_of(ts, rec["from"]), session_of(ts, rec["to"])
    if a is None or b is None:
        return False
    return abs(int(leg["from"]) - a) <= slack and abs(int(leg["to"]) - b) <= slack


def annotate(impulses, records, ts, slack):
    """प्रत्येक trend-degree leg वर "accepted" (जुळलेली नोंद: reading, direction, source, from / to तारखा) किंवा None. एक नोंद ⇒ कमाल एक
    leg (सर्वात जवळचा). impulses जागीच बदलतो आणि परत देतो."""
    ts = pd.DatetimeIndex(pd.to_datetime(ts)).normalize()
    for lg in impulses:
        lg["accepted"] = None
    for rec in records:
        hits = [lg for lg in impulses if match(lg, rec, ts, slack)]
        if not hits:
            continue
        a, b = session_of(ts, rec["from"]), session_of(ts, rec["to"])
        best = min(hits, key=lambda lg: abs(int(lg["from"]) - a) + abs(int(lg["to"]) - b))
        best["accepted"] = {"reading": rec["reading"], "direction": rec["direction"], "source": rec["source"],
                            "from": str(rec["from"].date()), "to": str(rec["to"].date())}
    return impulses
