"""
elliott/contracts.py — E3: NIFTY options contract facts — expiry calendar, expiry निवड, DTE, lot size, strike grid (spec §8)
------------------------------------------------------------------------------------------------------------------------
🎓 Expiry कधीच "पुढचा Tuesday" असा काढायचा नाही (holiday ⇒ आधीचा trading day). स्रोतांचा क्रम:
  1. **bhavcopy calendar** (elliott.bhavcopy.expiry_calendar — त्या दिवशी प्रत्यक्ष listed contracts, first_seen ≤ fill दिवस ⇒
     causal; सुट्टीमुळे सरकलेली प्रत्यक्ष expiry).
  2. **नियम-calendar** (bhavcopy नसताना — E3 tests / live fallback): weekly weekday तारखेनुसार (Thursday; 1 Sep 2025 पासून
     Tuesday), monthly = महिन्याचा शेवटचा तो weekday, holiday ⇒ आधीचा trading day. Weekly options 11 Feb 2019 पासून;
     त्याआधी फक्त monthly ⇒ "current weekly" = सर्वात जवळची listed expiry (WORK_LOG E3).
Trading days = NIFTY spot data मधले दिवस (+ भविष्यासाठी config.NSE_HOLIDAYS_2026 वगळून weekdays).
Lot size: bhavcopy (UDiFF, 8 Jul 2024 पासून) असेल तर तोच; नाहीतर खालचा **expiry**-निहाय table [अनुमान — पडताळणी आवश्यक; ₹
निकालांवरच परिणाम, R-multiples वर नाही]. Trading days फक्त पूर्ण sessions (मुहूर्त/DR sessions वगळून).
"""
import bisect
import datetime as dt

import numpy as np
import pandas as pd

SESSION_MIN = 375                                   # NSE 09:15–15:30
OPEN = dt.time(9, 15)
CLOSE = dt.time(15, 30)
WEEKLY_START = dt.date(2019, 2, 11)                 # NIFTY weekly options listing [पुरावा: NSE circular; bhavcopy first_weekly_listing ने पडताळा]
TUESDAY_FROM = dt.date(2025, 9, 1)                  # NIFTY expiry Thursday → Tuesday (spec §8 table)
STRIKE_STEP = 50

# (पासून, lot) — [अनुमान, secondary स्रोत; bhavcopy UDiFF NewBrdLotQty / contract master ने पडताळा]
# Lot बदल contract series नुसार लागू होतात ⇒ table चा key = **expiry** (त्या तारखेला/नंतर expire होणारे contracts).
NIFTY_LOTS = [(dt.date(2000, 1, 1), 25), (dt.date(2015, 10, 30), 75), (dt.date(2021, 7, 30), 50),
              (dt.date(2024, 4, 26), 25), (dt.date(2024, 11, 20), 75), (dt.date(2026, 1, 6), 65)]
FULL_SESSION_MIN_BARS = 300                         # मुहूर्त / DR / अर्धे sessions (≈ 60–120 bars) trading day नाहीत


def lot_size(expiry, bhav_lots=None):
    """त्या expiry च्या contract चा NIFTY lot. bhav_lots = {expiry date: lot} (UDiFF वरून) असेल तर तो प्राधान्याने."""
    day = pd.Timestamp(expiry).date()
    if bhav_lots and day in bhav_lots and np.isfinite(bhav_lots[day]):
        return int(bhav_lots[day])
    lot = NIFTY_LOTS[0][1]
    for since, n in NIFTY_LOTS:
        if day >= since:
            lot = n
    return lot


def _weekday_for(day):
    return 1 if day >= TUESDAY_FROM else 3                      # Tuesday = 1, Thursday = 3


class TradingCalendar:
    """Trading days (sorted dates). `days` = पूर्ण sessions चे दिवस; त्यापुढे weekdays − holidays (config)."""

    @classmethod
    def from_spot(cls, df1m, min_bars=FULL_SESSION_MIN_BARS):
        """Spot 1m data वरून: फक्त weekday आणि ≥ min_bars bars असलेले दिवस (मुहूर्त / weekend DR / अर्धे sessions वगळून —
        review H1: नाहीतर 2021-11-04 (दिवाळी) expiry आणि DTE चुकतो). Data नंतरचे दिवस: weekdays − config.NSE_HOLIDAYS_2026."""
        ts = pd.to_datetime(df1m["timestamp"])
        n = ts.dt.normalize().value_counts()
        days = [d.date() for d, c in n.items() if c >= min_bars and d.weekday() < 5]
        try:
            import config
            hol = getattr(config, "NSE_HOLIDAYS_2026", set())
        except Exception:                                               # noqa: BLE001 — config नसल्यास सुट्ट्या नाहीत
            hol = set()
        return cls(days, hol)

    def __init__(self, days, extra_holidays=()):
        self.days = sorted({pd.Timestamp(d).date() for d in days})
        self.holidays = {pd.Timestamp(h).date() for h in extra_holidays}
        self._set = set(self.days)

    def is_trading(self, day):
        if self.days and self.days[0] <= day <= self.days[-1]:
            return day in self._set
        return day.weekday() < 5 and day not in self.holidays

    def prev_or_same(self, day):
        while not self.is_trading(day):
            day -= dt.timedelta(days=1)
        return day

    def sessions_between(self, a, b):
        """a नंतर b पर्यंतचे trading sessions (b धरून, a वगळून)."""
        n, d = 0, a + dt.timedelta(days=1)
        while d <= b:
            n += self.is_trading(d)
            d += dt.timedelta(days=1)
        return n


def rule_expiries(cal, start, end):
    """नियम-calendar: [(expiry_date, kind)] — weekly (2019-02-11 पासून) + monthly; holiday ⇒ आधीचा trading day."""
    out = {}
    d = pd.Timestamp(start).date() - dt.timedelta(days=7)
    end = pd.Timestamp(end).date() + dt.timedelta(days=40)
    while d <= end:
        wd = _weekday_for(d)
        if d.weekday() == wd:
            nxt_month = (d + dt.timedelta(days=7)).month != d.month
            if nxt_month or d >= WEEKLY_START + dt.timedelta(days=3):         # पहिली weekly 14 Feb 2019
                e = cal.prev_or_same(d)
                out[e] = "monthly" if nxt_month else out.get(e, "weekly")
        d += dt.timedelta(days=1)
    return sorted(out.items())


class ExpiryBook:
    """Expiry निवड. bhav = expiry_calendar(norm) DataFrame (expiry, kind, first_seen) असेल तर तो; नाहीतर नियम-calendar."""

    def __init__(self, cal, bhav=None, start=None, end=None):
        self.cal = cal
        if bhav is not None and len(bhav):
            b = bhav.sort_values("expiry")
            self.items = [(pd.Timestamp(e).date(), k, pd.Timestamp(f).date()) for e, k, f in zip(b["expiry"], b["kind"], b["first_seen"])]
            self.source = "bhavcopy"
        else:
            # नियम-mode: weekly contracts WEEKLY_START पासूनच listed (त्याआधीचा fill weekly निवडत नाही); monthly नेहमी listed
            self.items = [(e, k, WEEKLY_START if k == "weekly" else None)
                          for e, k in rule_expiries(cal, start or cal.days[0], end or cal.days[-1])]
            self.source = "rule"
        self._dates = [x[0] for x in self.items]

    def listed_on(self, day):
        """त्या दिवशी listed (first_seen ≤ day) आणि अजून न संपलेल्या expiries."""
        i = bisect.bisect_left(self._dates, day)
        return [x for x in self.items[i:] if x[2] is None or x[2] <= day]

    def choose(self, fill_day, s, skip=0):
        """spec §8: today = fill दिवस; पहिली expiry ≥ today; today स्वतः expiry ⇒ पुढची. min_dte_override > 0 ⇒ तितके DTE.
        skip = आणखी किती पुढे (try_next_weekly). रिटर्न (expiry date, kind) किंवा None."""
        day = pd.Timestamp(fill_day).date()
        cands = [x for x in self.listed_on(day) if x[0] > day]          # today == expiry ⇒ वगळली (दुरुस्ती 2)
        if s.get("min_dte_override", 0) > 0:
            cands = [x for x in cands if self.cal.sessions_between(day, x[0]) >= s["min_dte_override"]]
        if len(cands) <= skip:
            return None
        e = cands[skip]
        return e[0], e[1]


def dte_days(cal, day, expiry):
    """आजनंतर expiry पर्यंतची sessions (expiry धरून): Monday → Tuesday expiry = 1."""
    return cal.sessions_between(pd.Timestamp(day).date(), pd.Timestamp(expiry).date())


def dte_frac(cal, ts, expiry, mode="session_fraction"):
    """session_fraction: (आजची उरलेली मिनिटं + dte_days × 375) / 375; whole_days: dte_days."""
    ts = pd.Timestamp(ts)
    n = dte_days(cal, ts.date(), expiry)
    if mode == "whole_days":
        return float(n)
    close = pd.Timestamp.combine(ts.date(), CLOSE)
    left = max(0.0, min(SESSION_MIN, (close - ts).total_seconds() / 60.0))
    return (left + n * SESSION_MIN) / SESSION_MIN


def floor_grid(x, step=STRIKE_STEP):  # step = settings strike_step (contract master; NIFTY 50)
    return int(np.floor(x / step) * step)


def ceil_grid(x, step=STRIKE_STEP):
    return int(np.ceil(x / step) * step)
