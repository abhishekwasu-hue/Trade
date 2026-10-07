"""
elliott/strikes.py — E3: expiry + strike + credit guard + sizing (spec §8 strike सूत्र, §9 Sizing, §14 Q5)
-------------------------------------------------------------------------------------------------------
🎓 Signal (E2) आणि fill वेळ (पुढच्या TTF bar चा open) वरून:
  expiry    contracts.ExpiryBook.choose (fill दिवस; आज expiry ⇒ पुढची)
  inv_far   same-direction counts (≥ alt_weight_min) पैकी सर्वात दूरचा hard inv (bull put ⇒ सर्वात खालचा)
  dist_inv  |spot − inv_far| + inv_buffer_mr × MR(TTF)        (short strike count मरण्याआधी गाठला जाऊ नये)
  dist_vol  k_sd × spot × IV × √(dte_frac / 252)
  dist      max(dist_inv, dist_vol, min_dist_pts)
  short     bull put PE floor(spot − dist) · bear call CE ceil(spot + dist)  (50-grid);  long = short ∓ width
  guard     credit/width ≥ c_min(dte_days) · credit ≥ min_credit_pts · |delta short| ≤ max_short_delta
            fail ⇒ credit_fail_action: skip | widen_width (50 ने, 200 पर्यंत) | try_next_weekly (एकदा)
  lots      sizing_mode = tier_of_A (default, F1): A = max(1, floor(capital × risk% / ((width − credit) × lot))), B/C =
            round(A × tier गुणक [× leading_diag_mult S10]) पण किमान tierB/C_min_lots (≤ A); risk_budget: floor(tier budget /
            प्रति-lot तोटा). 0 ⇒ skip. min_one_lot (shadow) ⇒ किमान 1. plan मध्ये over_budget + size_floor (कारण).
price_fn(opt, strike, expiry) ⇒ premium (mid) किंवा None (data नाही ⇒ skip "no_price"); delta_fn(opt, strike, expiry) ⇒ delta.
"""
import math

from . import contracts as CT
from . import pricing as PR

TIER_IDX = {"A": 0, "B": 1, "C": 2}


def inv_far(sig):
    lv = [sig.hard_inv] + list(sig.alt_invs or [])
    return min(lv) if sig.trade_dir > 0 else max(lv)


def strikes_for(sig, spot, dist, width, step=CT.STRIKE_STEP):
    if sig.trade_dir > 0:
        k = CT.floor_grid(spot - dist, step)
        return "PE", k, k - width
    k = CT.ceil_grid(spot + dist, step)
    return "CE", k, k + width


def size_lots(tier, mult, base_budget, per_lot, s):
    return size_lots_detail(tier, mult, base_budget, per_lot, s)[0]


def size_lots_detail(tier, mult, base_budget, per_lot, s):
    """(lots, floor कारण) — F1. tier_of_A: Tier A lots = budget ÷ प्रति-lot तोटा (किमान 1 — "a_min_one"); बाकी tiers = round(A × गुणक),
    किमान tierB_min_lots / tierC_min_lots पण A पेक्षा जास्त नाही ("tier_floor"); गुणक 0 ⇒ 0. risk_budget: tier budget ÷ प्रति-lot
    तोटा (जुनं). दोन्हीत `min_one_lot` (shadow trades) ⇒ गुणक > 0 असताना किमान 1 ("min_one_lot")."""
    if per_lot <= 0 or mult <= 0:
        return 0, ""
    why = ""
    if s.get("sizing_mode", "tier_of_A") == "risk_budget":
        lots = int(base_budget * mult // per_lot)
    else:
        raw_a = int(base_budget // per_lot)
        lots_a = max(1, raw_a)
        if tier == "A":
            lots, why = lots_a, ("a_min_one" if raw_a < 1 else "")
        else:
            lots = int(math.floor(lots_a * mult + 0.5 + 1e-9))                         # सामान्य rounding (0.5 ⇒ वर)
            floor_ = min({"B": s["tierB_min_lots"], "C": s["tierC_min_lots"]}.get(tier, 0), lots_a)
            if lots < floor_:
                lots, why = floor_, "tier_floor"
    if lots < 1 and s["min_one_lot"]:
        lots, why = 1, "min_one_lot"                                                # budget ओलांडतो — report मध्ये वेगळं
    return lots, why


def plan_spread(sig, spot, fill_ts, iv, mr, cal, book, s, price_fn, delta_fn=None, bhav_lots=None, slip_pts=0.0):
    """dict (trade plan) किंवा कारण (str). iv = float किंवा callable(expiry) (§11: निवडलेल्या expiry चा ATM IV).
    delta_fn नसेल ⇒ BS delta (risk_free_rate, त्या expiry चा IV) — max_short_delta guard कधीच गुपचूप बंद नाही.
    slip_pts = प्रति leg slippage (points) — guard आणि sizing **fill नंतरच्या** credit वर (short − slip, long + slip)."""
    tries = [0, 1] if s["credit_fail_action"] == "try_next_weekly" else [0]
    last = "no_expiry"
    for skip in tries:
        ex = book.choose(fill_ts, s, skip=skip)
        if ex is None:
            return last if skip else "no_expiry"                                    # पुढची listed नाही ⇒ आधीचं खरं कारण
        expiry, kind = ex
        vol = iv(expiry) if callable(iv) else iv
        if not vol or vol <= 0:
            last = "no_iv"
            continue
        dd = CT.dte_days(cal, fill_ts, expiry)
        df_ = CT.dte_frac(cal, fill_ts, expiry, s["dte_mode"])
        far = inv_far(sig)
        d_inv = abs(spot - far) + s["inv_buffer_mr"] * mr
        d_vol = s["k_sd"] * spot * vol * math.sqrt(max(df_, 0.0) / 252.0)
        dist = max(d_inv, d_vol, s["min_dist_pts"])
        widths = [s["width_pts"]]
        if s["credit_fail_action"] == "widen_width":                                # फक्त min_credit साठी उपयोगी (credit/width घटतो)
            widths += [w for w in s.get("widen_widths", (100, 150, 200)) if w > s["width_pts"]]
        for width in widths:
            opt, sk, lk = strikes_for(sig, spot, dist, width, s["strike_step"])
            ps, pl = price_fn(opt, sk, expiry), price_fn(opt, lk, expiry)
            if ps is None or pl is None:
                last = "no_price"
                break
            credit = ps - pl - 2.0 * slip_pts
            cmin = s["c_min_by_dte"][min(max(dd, 1), 5) - 1]
            if delta_fn is not None:
                dl = abs(delta_fn(opt, sk, expiry))
            else:
                dl = abs(PR.delta(spot, sk, max(df_, 0.0) / 252.0, s["risk_free_rate"], vol, opt))
            if credit / width < cmin:
                last = "guard_credit_width"
                continue
            if credit < s["min_credit_pts"]:
                last = "guard_min_credit"
                continue
            if dl > s["max_short_delta"]:
                last = "guard_delta"
                continue
            lot = CT.lot_size(expiry, bhav_lots)
            mult = s["tier_mult"][TIER_IDX[sig.tier]] * (s["leading_diag_mult"] if sig.setup == "S10" else 1.0)
            per_lot = (width - credit) * lot
            base = s["capital"] * s["risk_per_trade_pct"] / 100.0
            budget = base * mult
            lots, floor_why = size_lots_detail(sig.tier, mult, base, per_lot, s)
            if lots < 1:
                return "size_zero"
            return {"expiry": expiry, "expiry_kind": kind, "dte_days": dd, "dte_frac": df_, "opt": opt, "short_k": sk,
                    "long_k": lk, "width": width, "credit": credit, "short_px": ps, "long_px": pl, "lots": lots, "lot": lot,
                    "qty": lots * lot, "max_loss": per_lot * lots, "risk_budget": budget, "over_budget": per_lot * lots > budget, "size_floor": floor_why,
                    "dist_inv": d_inv, "dist_vol": d_vol, "dist": dist, "inv_far": far, "iv": vol, "short_delta": dl,
                    "next_weekly": skip > 0, "premium_stop_reachable": s["hard_stop_mult"] * credit < width}
    return last
