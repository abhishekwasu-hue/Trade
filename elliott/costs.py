"""
elliott/costs.py — E3: options trade खर्च, **तारीखनिहाय** दरांसह (spec §8 India facts, §11 cost_model)
----------------------------------------------------------------------------------------------------
🎓 प्रत्येक leg (buy/sell × premium × qty) साठी त्या **दिवशीचे** दर:
  STT (फक्त sell premium):  ≤ 31 May 2016 0.017% · 1 Jun 2016 0.05% · 1 Apr 2023 0.0625% · 1 Oct 2024 0.1% · 1 Apr 2026 0.15% (spec)
  NSE exchange txn (दोन्ही बाजू): ≈0.05% · 1 Apr 2023 0.053% · 1 Jan 2024 0.0495% · 1 Oct 2024 0.03503%  [अनुमान — पडताळा]
  SEBI fee 0.0001% (₹10/crore), दोन्ही बाजू · Stamp (फक्त buy): 1 Jul 2020 पासून 0.003%, आधी ≈0.002% [अनुमान]
  GST 18% (brokerage + exchange + SEBI); आधी service tax 12.36% → 14% (Jun 2015) → 14.5% (Nov 2015) → 15% (Jun 2016)
  Brokerage = brokerage_per_order प्रति executed order
  Slippage = slippage_ticks × ₹0.05 प्रति leg प्रति बाजू (प्रतिकूल दिशेने) — किंमतीत, खर्चात नाही.
Expiry ला ITM leg exercise ⇒ settlement value वर STT — exits (क्रम 7) ITM leg कधीच expire होऊ देत नाहीत; तरी settle_cost देतो.
"""
import datetime as dt

import pandas as pd

TICK = 0.05
_STT = [(dt.date(2000, 1, 1), 0.00017), (dt.date(2016, 6, 1), 0.0005), (dt.date(2023, 4, 1), 0.000625),
        (dt.date(2024, 10, 1), 0.001), (dt.date(2026, 4, 1), 0.0015)]
_EXCH = [(dt.date(2000, 1, 1), 0.0005), (dt.date(2023, 4, 1), 0.00053), (dt.date(2024, 1, 1), 0.000495),
         (dt.date(2024, 10, 1), 0.0003503)]                                    # [अनुमान — NSE circulars; IPFT वगळला]
_STAMP = [(dt.date(2000, 1, 1), 0.00002), (dt.date(2020, 7, 1), 0.00003)]
_TAX = [(dt.date(2000, 1, 1), 0.1236), (dt.date(2015, 6, 1), 0.14), (dt.date(2015, 11, 15), 0.145), (dt.date(2016, 6, 1), 0.15),
        (dt.date(2017, 7, 1), 0.18)]                                           # service tax (+cess) → GST
SEBI = 0.000001
STT_EXERCISE = [(dt.date(2000, 1, 1), 0.00125), (dt.date(2026, 4, 1), 0.0015)]   # [अनुमान] exercise करणाऱ्या (long ITM) leg वर


def _at(table, day):
    day = pd.Timestamp(day).date()
    v = table[0][1]
    for since, x in table:
        if day >= since:
            v = x
    return v


def rates(day):
    return {"stt": _at(_STT, day), "exch": _at(_EXCH, day), "stamp": _at(_STAMP, day), "tax": _at(_TAX, day), "sebi": SEBI}


def slip(px, side, s):
    """side "buy"/"sell": प्रतिकूल slippage — buy महाग, sell स्वस्त (किमान 0)."""
    t = s["slippage_ticks"] * TICK
    return px + t if side == "buy" else max(0.0, px - t)


def leg_cost(day, side, premium, qty, s):
    """एका executed leg चा एकूण खर्च (₹) — slippage वगळून (तो fill किंमतीत)."""
    r = rates(day)
    turnover = premium * qty
    stt = r["stt"] * turnover if side == "sell" else 0.0
    exch = r["exch"] * turnover
    sebi = r["sebi"] * turnover
    stamp = r["stamp"] * turnover if side == "buy" else 0.0
    brok = s["brokerage_per_order"]
    tax = r["tax"] * (brok + exch + sebi)
    return {"stt": stt, "exch": exch, "sebi": sebi, "stamp": stamp, "brokerage": brok, "tax": tax,
            "total": stt + exch + sebi + stamp + brok + tax}


def spread_cost(day, short_px, long_px, qty, s, opening=True):
    """Spread उघडणं (short sell + long buy) किंवा बंद करणं (short buy + long sell) — दोन orders (freeze qty slicing E6)."""
    if opening:
        a, b = leg_cost(day, "sell", short_px, qty, s), leg_cost(day, "buy", long_px, qty, s)
    else:
        a, b = leg_cost(day, "buy", short_px, qty, s), leg_cost(day, "sell", long_px, qty, s)
    return {k: a[k] + b[k] for k in a}


def settle_cost(day, intrinsic_long, settle_price, qty):
    """Long leg ITM expire ⇒ exercise: STT **holder** (long) वर — 1 Jun 2016 पासून intrinsic (settlement value), आधी
    settlement price × qty (notional) [अनुमान]. Exits ITM leg expire होऊ देत नाहीत; हे फक्त अपवादासाठी."""
    if intrinsic_long <= 0:
        return 0.0
    base = intrinsic_long if pd.Timestamp(day).date() >= dt.date(2016, 6, 1) else settle_price
    return _at(STT_EXERCISE, day) * base * qty
