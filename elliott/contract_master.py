"""
elliott/contract_master.py — Live / PAPER साठी contract master (review F7, Master rule 5)
-----------------------------------------------------------------------------------
🎓 Live आणि PAPER मध्ये expiry, lot आणि strike step **Upstox instruments (contract master) वरून** — weekday नियम आणि holiday
table (contracts.py) फक्त backtest fallback. Lot बदल (उदा. 20 Nov 2024) contract-wise: प्रत्येक contract चा स्वतःचा lot_size.

Upstox `/v2/option/contract?instrument_key=NSE_INDEX|Nifty 50` चे rows (expiry, strike_price, lot_size, instrument_type, …) →
`ContractMaster`. Network call `fetch_upstox_contracts` फक्त live/PAPER loop मध्ये (tests offline).
v1 = NIFTY फक्त; SENSEX (Thursday expiry, BSE) नाही — dashboard वर स्पष्ट, नंतरचं काम.
"""
import collections

import pandas as pd

from . import contracts as CT

NIFTY_KEY = "NSE_INDEX|Nifty 50"


class ContractMasterMissing(RuntimeError):
    """Live / PAPER मध्ये contract master शिवाय expiry / lot ठरवायचा प्रयत्न."""


class ContractMaster:
    def __init__(self, rows, underlying="NIFTY"):
        df = pd.DataFrame(rows)
        need = {"expiry", "strike_price", "lot_size", "instrument_type"}
        missing = need - set(df.columns)
        if missing:
            raise ValueError(f"contract master: columns नाहीत {sorted(missing)}")
        df = df[df["instrument_type"].isin(["CE", "PE"])].copy()
        df["expiry"] = pd.to_datetime(df["expiry"]).dt.date
        df["strike_price"] = df["strike_price"].astype(float)
        df["lot_size"] = df["lot_size"].astype(int)
        self.underlying = underlying
        self.df = df.sort_values(["expiry", "strike_price"]).reset_index(drop=True)

    def expiries(self):
        return sorted(self.df["expiry"].unique())

    def lots(self):
        """{expiry: lot} — त्या expiry च्या contracts चा lot (contract-wise; एका expiry मध्ये वेगवेगळे असतील तर ValueError)."""
        out = {}
        for e, g in self.df.groupby("expiry"):
            vals = set(g["lot_size"])
            if len(vals) != 1:
                raise ValueError(f"contract master: {e} ला अनेक lot sizes {sorted(vals)}")
            out[e] = vals.pop()
        return out

    def strike_step(self, expiry=None):
        """त्या expiry (नाहीतर सर्वात जवळची) च्या strikes मधलं सर्वात सामान्य अंतर."""
        e = expiry or self.expiries()[0]
        k = sorted(set(self.df.loc[self.df["expiry"] == e, "strike_price"]))
        diffs = collections.Counter(round(b - a, 6) for a, b in zip(k, k[1:]) if b > a)
        if not diffs:
            raise ValueError(f"contract master: {e} चे strikes अपुरे")
        return int(diffs.most_common(1)[0][0])

    def expiry_frame(self, listed_on):
        """ExpiryBook साठी (expiry, kind, first_seen) — Upstox `weekly` flag असेल तर तो; नाहीतर महिन्याची शेवटची expiry = monthly."""
        ex = self.expiries()
        if "weekly" in self.df.columns:
            wk = self.df.groupby("expiry")["weekly"].first()
            return pd.DataFrame({"expiry": ex, "kind": ["weekly" if bool(wk[e]) else "monthly" for e in ex],
                                 "first_seen": [pd.Timestamp(listed_on).date()] * len(ex)})
        last_in_month = {}
        for e in ex:
            last_in_month[(e.year, e.month)] = max(e, last_in_month.get((e.year, e.month), e))
        return pd.DataFrame({"expiry": ex, "kind": ["monthly" if last_in_month[(e.year, e.month)] == e else "weekly" for e in ex],
                             "first_seen": [pd.Timestamp(listed_on).date()] * len(ex)})


def expiry_book_for(mode, cal, master=None, listed_on=None, **kw):
    """mode = backtest ⇒ (bhav/नियम) ExpiryBook; paper / live ⇒ contract master अनिवार्य (नियम-fallback नाही)."""
    m = str(mode).lower()
    if m not in ("backtest", "paper", "live"):
        raise ValueError(f"mode {mode!r} — backtest / paper / live")
    if m in ("paper", "live"):
        if master is None:
            raise ContractMasterMissing("PAPER/LIVE मध्ये expiry contract master वरूनच (weekday नियम फक्त backtest साठी)")
        book = CT.ExpiryBook(cal, master.expiry_frame(listed_on or pd.Timestamp.now(tz="Asia/Kolkata").date()))
        book.source = "contract_master"
        return book
    return CT.ExpiryBook(cal, kw.get("bhav"), kw.get("start"), kw.get("end"))


def lot_for(master, expiry):
    """PAPER/LIVE: त्या expiry चा lot contract master मधूनच — नसेल तर error (table fallback नाही)."""
    lots = master.lots()
    day = pd.Timestamp(expiry).date()
    if day not in lots:
        raise ContractMasterMissing(f"{day} चा contract master मध्ये lot नाही")
    return lots[day]


def fetch_upstox_contracts(access_token, instrument_key=NIFTY_KEY, timeout=10):
    """Upstox option contracts (network). Live/PAPER loop मधूनच; token कधीच log/print नाही."""
    import requests
    r = requests.get("https://api.upstox.com/v2/option/contract", params={"instrument_key": instrument_key},
                     headers={"Accept": "application/json", "Authorization": f"Bearer {access_token}"}, timeout=timeout)
    r.raise_for_status()
    return ContractMaster(r.json().get("data") or [])
