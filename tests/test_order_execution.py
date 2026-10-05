"""tests/test_order_execution.py — T5: marketable-LIMIT (tick गोलाई, partial fills, retry/cancel), market_protection, डीफॉल्ट न-बदल; network नाही."""
import pytest

import order_execution as OX


def test_round_and_marketable_price_direction():
    assert OX.marketable_limit_price(100.0, "BUY", 0.5) == 100.5
    assert OX.marketable_limit_price(100.0, "SELL", 0.5) == 99.5
    assert OX.round_to_tick(100.01, 0.05, "BUY") == 100.05 and OX.round_to_tick(100.04, 0.05, "SELL") == 100.0
    assert OX.round_to_tick(0.01, 0.05, "SELL") == 0.05                                  # किमान एक tick
    with pytest.raises(ValueError):
        OX.marketable_limit_price(None, "BUY", 0.5)


ORDERS = [{"instrument_token": "A", "transaction_type": "BUY", "order_type": "MARKET", "price": 0, "quantity": 75},
          {"instrument_token": "B", "transaction_type": "SELL", "order_type": "SL-M", "price": 0, "trigger_price": 50, "quantity": 75},
          {"instrument_token": "C", "transaction_type": "SELL", "order_type": "LIMIT", "price": 12.0, "quantity": 75}]


def test_default_style_leaves_orders_unchanged_and_copies():
    out = OX.apply_order_style(ORDERS)
    assert out == ORDERS and out[0] is not ORDERS[0]
    with pytest.raises(ValueError):
        OX.apply_order_style(ORDERS, "IOC")


def test_market_protection_only_on_market_and_slm():
    out = OX.apply_order_style(ORDERS, "MARKET_PROTECTION", OX.LimitConfig(market_protection_pct=3))
    assert out[0]["market_protection"] == 3 and out[1]["market_protection"] == 3 and "market_protection" not in out[2]
    assert "market_protection" not in ORDERS[0]
    with pytest.raises(ValueError):
        OX.with_market_protection(ORDERS, 0)                                             # 0 ⇒ exchange नाकारतो


def test_marketable_limit_style_converts_market_only():
    out = OX.apply_order_style(ORDERS, "MARKETABLE_LIMIT", OX.LimitConfig(buffer_pct=1.0), {"A": 200.0})
    assert out[0]["order_type"] == "LIMIT" and out[0]["price"] == 202.0
    assert out[1]["order_type"] == "SL-M" and out[2] == ORDERS[2]


class FakeBroker:
    """प्रत्येक प्रयत्नात किती भरायचं ते script नुसार; ltp क्रमाने."""
    def __init__(self, fills, ltps, final="complete"):
        self.fills, self.ltps, self.final = list(fills), list(ltps), final
        self.placed, self.cancelled, self.st = [], [], {}

    def place(self, o):
        oid = f"O{len(self.placed)}"
        self.placed.append(o)
        want = self.fills.pop(0)
        if want is None:
            return None
        full = want >= o["quantity"]
        self.st[oid] = {"status": "complete" if full else "open", "filled_quantity": min(want, o["quantity"]), "average_price": o["price"]}
        return oid

    def status(self, oid):
        return self.st[oid]

    def cancel(self, oid):
        self.cancelled.append(oid)
        self.st[oid] = {**self.st[oid], "status": "cancelled"}
        return True

    def ltp(self, _):
        return self.ltps.pop(0) if len(self.ltps) > 1 else self.ltps[0]


def run(b, qty=100, side="BUY", cfg=None):
    clock = iter(range(0, 10_000))
    return OX.run_marketable_limit({"instrument_token": "X", "transaction_type": side, "quantity": qty}, b.place, b.status, b.cancel, b.ltp,
                                   cfg or OX.LimitConfig(wait_sec=1, poll_sec=0, retries=3), sleep=lambda s: None, clock=lambda: next(clock))


def test_full_fill_first_attempt():
    b = FakeBroker([100], [100.0])
    r = run(b)
    assert r.complete and r.attempts == 1 and r.avg_price == 100.5 and not b.cancelled


def test_partial_fill_then_cancel_and_retry_with_wider_buffer():
    b = FakeBroker([40, 60], [100.0, 101.0])
    r = run(b)
    assert r.complete and r.attempts == 2 and b.cancelled == ["O0"]
    assert b.placed[1]["quantity"] == 60 and b.placed[1]["price"] == OX.marketable_limit_price(101.0, "BUY", 1.0)
    assert r.avg_price == pytest.approx((40 * 100.5 + 60 * b.placed[1]["price"]) / 100)


def test_gives_up_after_retries_and_reports_remaining():
    b = FakeBroker([0, 0, 0, 0], [100.0])
    r = run(b, side="SELL")
    assert not r.complete and r.remaining_qty == 100 and r.attempts == 4 and len(b.cancelled) == 4
    assert b.placed[-1]["price"] < b.placed[0]["price"]                                   # SELL: buffer वाढत खाली


def test_rejected_placement_and_missing_ltp():
    b = FakeBroker([None, 100], [100.0])
    r = run(b)
    assert r.complete and r.attempts == 2 and r.order_ids == ["O1"]
    b2 = FakeBroker([100], [None])
    r2 = run(b2)
    assert r2.attempts == 0 and r2.remaining_qty == 100 and "LTP" in r2.log[0]
