"""
order_execution.py
------------------
🎓 T5 — Order type पर्याय (SEBI retail-algo framework / exchange नियम: API मधून शुद्ध MARKET orders वर निर्बंध).
**हा module अजून कुठल्याही LIVE/PAPER मार्गाशी जोडलेला नाही** (G3: LIVE वर परिणाम करणारा कोणताही बदल वापरकर्त्याच्या मंजुरीनंतरच).
सध्याचं वर्तन (trading_engine → upstox_api.execute_order_leg_set, order_type "MARKET") जसंच्या तसं.

तीन शैली (`order_style` setting — डीफॉल्ट "MARKET" ⇒ काहीच बदल नाही):
  • "MARKET"            — जुनं वर्तन.
  • "MARKET_PROTECTION" — MARKET / SL-M orders मध्ये Upstox चा `market_protection` (1–25 %) स्पष्टपणे भरतो (न भरल्यास Upstox चा डीफॉल्ट −1 = auto).
  • "MARKETABLE_LIMIT"  — **फक्त entries साठी** (G3 निर्णय; exit साठी ValueError). setting `entry_order_style` डीफॉल्ट "MARKET", कुठेही जोडलेला नाही.
                          LIMIT order @ LTP ± buffer (tick ला गोल); ठराविक वेळेत पूर्ण न भरल्यास उरलेल्या quantity साठी cancel → नवीन LTP ± वाढीव
                          buffer ने पुन्हा (कमाल `retries`); शेवटी उरलेलं unfilled ⇒ स्पष्ट निकाल (caller ठरवेल — उदा. exit साठी अलर्ट).

सर्व broker कॉल्स injectable functions (place/status/cancel/ltp) — म्हणजे tests मध्ये network शिवाय तपासता येतं.
"""
import math
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

ORDER_STYLES = ("MARKET", "MARKET_PROTECTION", "MARKETABLE_LIMIT")
DEFAULT_ORDER_STYLE = "MARKET"
TERMINAL_OK = ("complete",)
TERMINAL_BAD = ("rejected", "cancelled")


@dataclass
class LimitConfig:
    buffer_pct: float = 0.5          # LTP पासून किती % पलीकडे limit (BUY ⇒ वर, SELL ⇒ खाली) — marketable
    buffer_step_pct: float = 0.5     # प्रत्येक retry ला buffer किती वाढवायचा
    max_buffer_pct: float = 3.0
    retries: int = 3
    wait_sec: float = 2.0            # प्रत्येक प्रयत्नानंतर fill साठी किती थांबायचं
    poll_sec: float = 0.5            # किमान 0.2s (rate-limit संरक्षण)
    tick: float = 0.05
    market_protection_pct: int = 2   # MARKET_PROTECTION शैलीसाठी (1–25)


SIDES = ("BUY", "SELL")


def _check_side(side):
    if side not in SIDES:
        raise ValueError(f"transaction_type BUY/SELL हवा, मिळाला {side!r}")


def _decimals(tick):
    s = f"{tick:.10f}".rstrip("0")
    return max(len(s.split(".")[1]) if "." in s else 0, 2)


def round_to_tick(price, tick, side):
    """BUY ⇒ वर गोल (marketable राहावं), SELL ⇒ खाली गोल. किमान एक tick."""
    _check_side(side)
    if tick <= 0:
        return round(price, 2)
    n = price / tick
    n = math.ceil(n - 1e-9) if side == "BUY" else math.floor(n + 1e-9)
    return round(max(n, 1) * tick, _decimals(tick))


def marketable_limit_price(ltp, side, buffer_pct, tick=0.05):
    """LTP ± buffer% (BUY वर, SELL खाली), tick ला गोल. ltp ≤ 0 ⇒ ValueError."""
    _check_side(side)
    if ltp is None or not (ltp > 0):
        raise ValueError("LTP उपलब्ध नाही — marketable limit किंमत ठरवता येत नाही")
    sign = 1 if side == "BUY" else -1
    return round_to_tick(ltp * (1 + sign * buffer_pct / 100.0), tick, side)


def with_market_protection(orders, pct):
    """MARKET / SL-M orders च्या प्रतीत `market_protection` = pct (1–25). इतर orders तसेच. मूळ list बदलत नाही."""
    pct = int(pct)
    if not 1 <= pct <= 25:
        raise ValueError("market_protection 1–25 % असावा")
    out = []
    for o in orders:
        p = dict(o)
        if str(p.get("order_type", "")).upper() in ("MARKET", "SL-M"):
            p["market_protection"] = pct
        out.append(p)
    return out


def apply_order_style(orders, style=DEFAULT_ORDER_STYLE, cfg=None, ltp_map=None, purpose="entry"):
    """orders (trading_engine चे dicts) -> नवीन शैलीतले orders. "MARKET" ⇒ अगदी तेच (प्रत) — डीफॉल्ट वर्तन बदलत नाही.
    "MARKETABLE_LIMIT" साठी `ltp_map` {instrument_token: ltp} लागतो; पहिल्या प्रयत्नाची limit किंमत भरतो."""
    cfg = cfg or LimitConfig()
    if style not in ORDER_STYLES:
        raise ValueError(f"अज्ञात order_style: {style!r}")
    if style == "MARKETABLE_LIMIT" and purpose != "entry":
        raise ValueError("MARKETABLE_LIMIT फक्त entries साठी — exits (SL/Target/TSL) साठी नाही (वापरकर्त्याचा G3 निर्णय)")
    if style == "MARKET":
        return [dict(o) for o in orders]
    if style == "MARKET_PROTECTION":
        return with_market_protection(orders, cfg.market_protection_pct)
    out = []
    for o in orders:
        p = dict(o)
        if str(p.get("order_type", "")).upper() == "MARKET":
            ltp = (ltp_map or {}).get(p.get("instrument_token"))
            p["order_type"] = "LIMIT"
            p["price"] = marketable_limit_price(ltp, p.get("transaction_type"), cfg.buffer_pct, cfg.tick)
        out.append(p)
    return out


@dataclass
class LimitResult:
    filled_qty: int = 0
    remaining_qty: int = 0
    attempts: int = 0
    avg_price: Optional[float] = None
    order_ids: List[str] = field(default_factory=list)
    log: List[str] = field(default_factory=list)
    unresolved_order_id: Optional[str] = None   # cancel निश्चित झाला नाही ⇒ broker वर अजून live असू शकतो (caller ने तपासावं)
    overfill_qty: int = 0                       # broker ने उरलेल्यापेक्षा जास्त भरलं असं सांगितलं तर

    @property
    def complete(self):
        return self.remaining_qty == 0 and self.filled_qty > 0


def run_marketable_limit(order, place: Callable, status: Callable, cancel: Callable, ltp: Callable, cfg=None,
                         sleep: Callable = time.sleep, clock: Callable = time.monotonic):
    """एका leg साठी marketable-LIMIT अंमलबजावणी. Partial fills सांभाळतो.
    place(order_dict) -> order_id | None · status(order_id) -> {"status", "filled_quantity", "average_price"} ·
    cancel(order_id) -> bool · ltp(instrument_token) -> float | None.
    रिटर्न LimitResult (filled / remaining / attempts / सरासरी किंमत / log). Network नाही — सर्व functions caller चे."""
    cfg = cfg or LimitConfig()
    side = order.get("transaction_type")
    _check_side(side)
    total = int(order.get("quantity") or 0)
    res = LimitResult(remaining_qty=total)
    notional, priced_qty = 0.0, 0
    poll = max(cfg.poll_sec, 0.2)
    buffer = cfg.buffer_pct
    for attempt in range(cfg.retries + 1):
        if res.remaining_qty <= 0:
            break
        price_now = ltp(order.get("instrument_token"))
        try:
            limit = marketable_limit_price(price_now, side, buffer, cfg.tick)
        except ValueError as e:
            res.log.append(f"प्रयत्न {attempt + 1}: {e}")
            break
        o = {**order, "order_type": "LIMIT", "price": limit, "quantity": res.remaining_qty}
        oid = place(o)
        res.attempts += 1
        if not oid:
            res.log.append(f"प्रयत्न {attempt + 1}: order नाकारला/पाठवता आला नाही @ {limit}")
            buffer = min(buffer + cfg.buffer_step_pct, cfg.max_buffer_pct)
            continue
        res.order_ids.append(oid)
        t0 = clock()
        st = {}
        while True:
            st = status(oid) or {}
            s = str(st.get("status", "")).lower()
            if s in TERMINAL_OK or s in TERMINAL_BAD or clock() - t0 >= cfg.wait_sec:
                break
            sleep(poll)
        s = str(st.get("status", "")).lower()
        if s not in TERMINAL_OK and s not in TERMINAL_BAD:
            ok = cancel(oid)                                      # उरलेलं रद्द करून नवीन किंमतीने पुन्हा
            st = status(oid) or st                                # cancel नंतरचा अंतिम filled आकडा
            s = str(st.get("status", "")).lower()
            if not ok or (s not in TERMINAL_OK and s not in TERMINAL_BAD):
                res.unresolved_order_id = oid                     # order अजून live असू शकतो ⇒ पुढे retry नाही (दुहेरी position टाळण्यासाठी)
        raw = int(st.get("filled_quantity") or 0)
        if raw > res.remaining_qty:
            res.overfill_qty += raw - res.remaining_qty
        filled = max(0, min(raw, res.remaining_qty))
        if filled and st.get("average_price") is not None:
            notional += filled * float(st["average_price"])
            priced_qty += filled
        res.filled_qty += filled
        res.remaining_qty -= filled
        res.log.append(f"प्रयत्न {attempt + 1}: LIMIT {limit} ⇒ {s or 'unknown'}, भरले {filled}, उरले {res.remaining_qty}")
        if res.unresolved_order_id:
            res.log.append(f"⚠️ order {oid} चा cancel निश्चित झाला नाही — थांबलो; broker वर तपासा")
            break
        buffer = min(buffer + cfg.buffer_step_pct, cfg.max_buffer_pct)
    if priced_qty:
        res.avg_price = round(notional / priced_qty, 4)                 # फक्त किंमत माहीत असलेल्या fills वर
    return res
