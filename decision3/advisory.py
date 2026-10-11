"""decision3/advisory.py — Q15 (5): elliott count engine (elliott.counts.CountEngine, simple_core.count_source मार्फत) चा preferred count
— फक्त **सल्ला** (Telegram caption च्या ① ओळीत Dow state सोबत). Gate / conviction नाही. 1m data लागतो (NIFTY); नसेल ⇒ "count NA" कारणासह.
Count engine फक्त asof पर्यंतचा data पाहतो (count_source.engine cut). Order / broker / AI call नाही."""
import pandas as pd


def count_line(df1m, asof, cache=None):
    """'Count D3: impulse/5/-1 (alt zigzag/C/+1)' — सर्वात मोठी non-gray degree. cache = dict (asof दिवस ⇒ line)."""
    if df1m is None:
        return "count NA (1m data नाही)"
    key = str(pd.Timestamp(asof))
    if cache is not None and key in cache:
        return cache[key]
    from simple_core import count_source as CS
    md, snap = CS.engine(df1m, asof)
    if md is None:
        line = f"count NA ({snap})"
    else:
        br = CS.degrees_brief(snap)
        pick = [(k, v) for k, v in sorted(br.items(), key=lambda kv: -int(kv[0][1:])) if v["preferred"] and not v["gray"]]
        if not pick:
            pick = [(k, v) for k, v in sorted(br.items(), key=lambda kv: -int(kv[0][1:])) if v["preferred"]]
        if not pick:
            line = "count gray (सगळ्या degrees)"
        else:
            k, v = pick[0]
            line = f"Count {k}: {v['preferred']}" + (f" (alt {v['alternate']})" if v["alternate"] else "") + (" · gray" if v["gray"] else "")
    if cache is not None:
        cache[key] = line
    return line
