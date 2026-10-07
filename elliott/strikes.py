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
  lots      floor(capital × risk% × tier गुणक [× leading_diag_mult S10] / ((width − credit) × lot)); 0 ⇒ skip
            (min_one_lot = true ⇒ 1 lot, risk budget ओलांडून — default बंद; plan मध्ये over_budget)
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


def plan_spread(sig, spot, fill_ts, iv, mr, cal, book, s, price_fn, delta_fn=None, bhav_lots=None):
    """dict (trade plan) किंवा कारण (str). iv = float किंवा callable(expiry) (§11: निवडलेल्या expiry चा ATM IV).
    delta_fn नसेल ⇒ BS delta (risk_free_rate, त्या expiry चा IV) — max_short_delta guard कधीच गुपचूप बंद नाही."""
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
            widths += [w for w in (100, 150, 200) if w > s["width_pts"]]
        for width in widths:
            opt, sk, lk = strikes_for(sig, spot, dist, width, s["strike_step"])
            ps, pl = price_fn(opt, sk, expiry), price_fn(opt, lk, expiry)
            if ps is None or pl is None:
                last = "no_price"
                break
            credit = ps - pl
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
            budget = s["capital"] * s["risk_per_trade_pct"] / 100.0 * mult
            lots = int(budget // per_lot) if per_lot > 0 else 0
            if lots < 1 and s["min_one_lot"] and mult > 0:
                lots = 1                                                            # budget ओलांडतो — report मध्ये वेगळं
            if lots < 1:
                return "size_zero"
            return {"expiry": expiry, "expiry_kind": kind, "dte_days": dd, "dte_frac": df_, "opt": opt, "short_k": sk,
                    "long_k": lk, "width": width, "credit": credit, "short_px": ps, "long_px": pl, "lots": lots, "lot": lot,
                    "qty": lots * lot, "max_loss": per_lot * lots, "risk_budget": budget, "over_budget": per_lot * lots > budget,
                    "dist_inv": d_inv, "dist_vol": d_vol, "dist": dist, "inv_far": far, "iv": vol, "short_delta": dl,
                    "next_weekly": skip > 0, "premium_stop_reachable": s["hard_stop_mult"] * credit < width}
    return last
