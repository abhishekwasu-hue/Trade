"""
mcx_trade_replay.py
---------------------
🎓 वापरकर्त्याची मागणी (MCX trend filter / cooldown — आधी replay, मग कोड): MCX Futures Trader चे झालेले trades पुन्हा तपासणे —
प्रत्येक trade साठी त्या entry वेळेपर्यंत **पूर्ण झालेल्या** 30M / 1H / 4H / Daily bars वरून (no-lookahead) नवीन filters ने तो trade
अडला असता का. **Read-only** — कुठलाही order, DB-लेखन, setting बदल नाही (SQLite read-only connection).

  (a) सध्याचा Supertrend filter "both_against" (1H आणि 4H दोन्ही विरुद्ध ⇒ block)
  (b) "htf_against" (4H Supertrend विरुद्ध ⇒ block)
  (c) broken-support cascade (30M close ने तुटलेला support + CHoCH नाही ⇒ block) — mcx_filters.cascade_block
  (d) SL cooldown (60 मि.) + त्याच level/दिशेवर आजचा SL — mcx_filters (आधीच्या trades वरून)
Filters चं तर्क mcx_filters.py मध्ये — टप्पा 1 मध्ये bot हेच functions वापरेल.

अतिरिक्त:
  --trade-id ID  : त्या trade ची forensics — exit_reason_detail (Monitor lag / Price source), peak, trailing level, आणि exit भोवतीचे 1-मिनिट
                   candles (level प्रत्यक्ष कधी ओलांडला आणि exit कधी झाला).
  --margin       : सध्याचा front contract वि. पुढचा — Upstox Margin API (1 lot, BUY/SELL) + contract value, delivery-period margin तपासणीसाठी.

    python3 mcx_trade_replay.py --symbol GOLD --from 2026-09-22 --to 2026-10-01 --out /root/mcx_replay
    python3 mcx_trade_replay.py --symbol GOLD --trade-id <ID> --margin
"""
import argparse
import json
import os
import re
import sqlite3
import sys

import pandas as pd

import mcx_filters as F

MCX_SOURCES = ("mcx_futures", "mcx_futures_srv3_shadow")
TRADE_COLS = ("trade_id", "symbol", "mode", "source", "strategy", "legs_json", "lots", "lot_size", "net_credit", "entry_time", "exit_time",
              "exit_reason", "exit_reason_detail", "realized_pnl", "entry_level_price", "entry_timeframe", "peak_pnl", "sl_pnl_level",
              "target_pnl_level", "entry_margin_required", "pnl_multiplier", "status", "entry_spot_price")


# ---------------------------------------------------------------------------------------------------------------------
# DB (read-only)
# ---------------------------------------------------------------------------------------------------------------------
def load_trades(db_path, symbol, date_from=None, date_to=None, trade_ids=None):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        have = {r[1] for r in conn.execute("PRAGMA table_info(live_trades)").fetchall()}
        cols = [c for c in TRADE_COLS if c in have]
        q = f"SELECT {', '.join(cols)} FROM live_trades WHERE source IN ({','.join('?' * len(MCX_SOURCES))}) AND symbol=?"
        params = [*MCX_SOURCES, symbol]
        if trade_ids:
            q += f" AND trade_id IN ({','.join('?' * len(trade_ids))})"
            params += list(trade_ids)
        else:
            if date_from:
                q += " AND substr(entry_time,1,10) >= ?"
                params.append(str(date_from))
            if date_to:
                q += " AND substr(entry_time,1,10) <= ?"
                params.append(str(date_to))
        rows = [dict(zip(cols, r)) for r in conn.execute(q + " ORDER BY entry_time", params).fetchall()]
    finally:
        conn.close()
    for r in rows:
        try:
            legs = json.loads(r.get("legs_json") or "[]")
        except ValueError:
            legs = []
        r["instrument_key"] = (legs[0] if legs else {}).get("instrument_key")
        r["expiry"] = (legs[0] if legs else {}).get("expiry")
        r["direction"] = "BULLISH" if "LONG" in str(r.get("strategy") or "").upper() else "BEARISH"
        for col in ("entry_time", "exit_time"):                  # तुलनेसाठी सर्व वेळा tz-शिवाय IST
            if r.get(col):
                r[col] = str(naive(pd.Timestamp(r[col])))
    return rows


# ---------------------------------------------------------------------------------------------------------------------
# Bars (no-lookahead)
# ---------------------------------------------------------------------------------------------------------------------
def naive(ts):
    t = pd.to_datetime(ts)
    if isinstance(t, pd.Series):
        return t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None) if getattr(t.dt, "tz", None) is not None else t
    return t.tz_convert("Asia/Kolkata").tz_localize(None) if t.tzinfo is not None else t


def closed_bars_at(df30, df_day, t):
    """entry वेळ t ला पूर्ण झालेले: 30M (timestamp+30मि ≤ t), 1H/4H (bar_end ≤ t, MCX 09:00 ग्रिड), Daily (t च्या आधीचे दिवस)."""
    from signals import resample_to_1h, resample_to_4h
    t = pd.Timestamp(t)
    d30 = df30.copy()
    d30["timestamp"] = naive(d30["timestamp"])
    for col in ("volume", "oi"):
        if col not in d30.columns:
            d30[col] = 0
    d30 = d30[d30["timestamp"] + pd.Timedelta(minutes=30) <= t].reset_index(drop=True)
    h1 = resample_to_1h(d30) if len(d30) else d30
    h4 = resample_to_4h(d30) if len(d30) else d30
    if len(h1) and "bar_end" in h1.columns:
        h1 = h1[naive(h1["bar_end"]) <= t]
    if len(h4) and "bar_end" in h4.columns:
        h4 = h4[naive(h4["bar_end"]) <= t]
    dd = None
    if df_day is not None and len(df_day):
        dd = df_day.copy()
        dd["timestamp"] = naive(dd["timestamp"])
        dd = dd[dd["timestamp"].dt.normalize() < t.normalize()]
    return d30, h1, h4, dd


def _st_dir(df, period=10, mult=3.0):
    from dynamic_sr_instant_trader import get_supertrend_direction
    if df is None or len(df) < period + 2:
        return None
    try:
        return get_supertrend_direction(df, period, mult)
    except Exception:
        return None


def evaluate_trade(trade, df30, df_day, prior, settings=None):
    """एका trade साठी (a)–(d). prior = त्याआधी बंद झालेले त्याच symbol चे trades."""
    s = settings or {}
    t = naive(pd.Timestamp(trade["entry_time"]))
    d30, h1, h4, dd = closed_bars_at(df30, df_day, t)
    dir_1h = _st_dir(h1, s.get("supertrend_1h_period", 10), s.get("supertrend_1h_multiplier", 3.0))
    dir_4h = _st_dir(h4, s.get("supertrend_4h_period", 10), s.get("supertrend_4h_multiplier", 3.0))
    direction, level = trade["direction"], float(trade.get("entry_level_price") or trade.get("entry_spot_price") or 0)
    a, a_why = F.supertrend_block("both_against", direction, dir_1h, dir_4h)
    b, b_why = F.supertrend_block("htf_against", direction, dir_1h, dir_4h)
    c, c_why, c_info = F.cascade_block(d30, direction, level)
    d1, d1_why = F.sl_cooldown_block(prior, t, 60)
    d2, d2_why = F.sl_level_direction_block(prior, t, level, direction)
    daily_trend = None
    if dd is not None and len(dd) >= 6:
        last5 = dd.tail(6)["close"].to_numpy(float)
        daily_trend = "UP" if last5[-1] > last5[0] else "DOWN"
    return {
        "trade_id": trade["trade_id"], "entry_time": str(t), "side": "LONG" if direction == "BULLISH" else "SHORT", "level": level,
        "exit_reason": trade.get("exit_reason"), "pnl": trade.get("realized_pnl"), "bars_30m": len(d30),
        "st_1h": dir_1h, "st_4h": dir_4h, "daily_5d": daily_trend,
        "a_both_against": a, "b_htf_against": b, "c_cascade": c, "d_cooldown": d1 or d2,
        "c_broken_level": c_info.get("broken_level"), "c_choch_level": c_info.get("choch_level"),
        "reasons": " | ".join(x for x in (a_why, b_why if b and not a else None, c_why, d1_why, d2_why) if x),
    }


def summarize(rows):
    """प्रत्येक नियम: किती तोट्यातले अडले आणि किती फायद्याचे चुकून अडले."""
    out = []
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()
    loss = df["pnl"].astype(float) < 0
    for col, name in (("a_both_against", "(a) Supertrend both_against"), ("b_htf_against", "(b) 4H htf_against"),
                      ("c_cascade", "(c) cascade"), ("d_cooldown", "(d) cooldown")):
        blk = df[col].astype(bool)
        out.append({"नियम": name, "अडलेले": int(blk.sum()), "तोट्यातले अडले": int((blk & loss).sum()), "एकूण तोट्यातले": int(loss.sum()),
                    "फायद्याचे चुकून अडले": int((blk & ~loss).sum()), "वाचलेला तोटा ₹": round(float(-df.loc[blk & loss, "pnl"].astype(float).sum()), 0),
                    "गमावलेला नफा ₹": round(float(df.loc[blk & ~loss, "pnl"].astype(float).sum()), 0)})
    blk = df[["b_htf_against", "c_cascade", "d_cooldown"]].astype(bool).any(axis=1)
    out.append({"नियम": "(b)+(c)+(d) पैकी कुठलाही", "अडलेले": int(blk.sum()), "तोट्यातले अडले": int((blk & loss).sum()),
                "एकूण तोट्यातले": int(loss.sum()), "फायद्याचे चुकून अडले": int((blk & ~loss).sum()),
                "वाचलेला तोटा ₹": round(float(-df.loc[blk & loss, "pnl"].astype(float).sum()), 0),
                "गमावलेला नफा ₹": round(float(df.loc[blk & ~loss, "pnl"].astype(float).sum()), 0)})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------------------------------------------------
# Forensics + margin
# ---------------------------------------------------------------------------------------------------------------------
_RS = re.compile(r"Rs\s*([\d,]+(?:\.\d+)?)")


def parse_exit_prices(detail):
    """'futures price Rs X hit/crossed … price Rs Y' ⇒ (X = exit-वेळचा भाव, Y = SL/trailing level). नसेल तर (None, None)."""
    nums = [float(x.replace(",", "")) for x in _RS.findall(str(detail or ""))]
    return (nums[0], nums[1]) if len(nums) >= 2 else (None, None)


def forensics(trade, df1m, level=None):
    """exit भोवतीचे 1-मिनिट candles: level प्रत्यक्ष पहिल्यांदा कधी ओलांडला (SHORT: high ≥ level; LONG: low ≤ level) वि. exit_time.
    Trailing SL चा level entry पासून नसतो — तो peak नंतरच तयार होतो. म्हणून TRAILING exit साठी शोध peak (SHORT: सर्वात कमी low,
    LONG: सर्वात जास्त high) च्या minute पासून. `gap_points` = ओलांडण्याआधीचा शेवटचा close ते ओलांडणाऱ्या minute चा open — मोठा gap ⇒
    भावच उडी मारून level च्या पलीकडे गेला (monitor उशीर नव्हे)."""
    exit_px, lvl = parse_exit_prices(trade.get("exit_reason_detail"))
    lvl = level if level is not None else lvl
    out = {"trade_id": trade["trade_id"], "exit_reason": trade.get("exit_reason"), "exit_time": trade.get("exit_time"),
           "detail": trade.get("exit_reason_detail"), "peak_pnl": trade.get("peak_pnl"), "exit_price_in_detail": exit_px, "level": lvl,
           "peak_time": None, "peak_price": None, "first_cross_time": None, "minutes_cross_to_exit": None,
           "price_before_cross": None, "cross_open": None, "gap_points": None, "candles": None}
    if df1m is None or not len(df1m) or lvl is None or trade.get("exit_time") is None:
        return out
    d = df1m.copy()
    d["timestamp"] = naive(d["timestamp"])
    d = d.sort_values("timestamp").reset_index(drop=True)
    ex = pd.Timestamp(trade["exit_time"])
    ent = pd.Timestamp(trade["entry_time"])
    short = trade["direction"] == "BEARISH"
    win = d[(d["timestamp"] >= ent.floor("min")) & (d["timestamp"] <= ex)]
    if "TRAILING" in str(trade.get("exit_reason") or "").upper() and len(win):
        pk = win["low"].idxmin() if short else win["high"].idxmax()
        out["peak_time"] = str(d.loc[pk, "timestamp"])
        out["peak_price"] = float(d.loc[pk, "low"] if short else d.loc[pk, "high"])
        win = d[(d.index >= pk) & (d["timestamp"] <= ex + pd.Timedelta(minutes=2))]
    else:
        win = d[(d["timestamp"] >= ent.floor("min")) & (d["timestamp"] <= ex + pd.Timedelta(minutes=2))]
    crossed = win[win["high"] >= lvl] if short else win[win["low"] <= lvl]
    if len(crossed):
        i = crossed.index[0]
        first = d.loc[i, "timestamp"]
        out["first_cross_time"] = str(first)
        out["minutes_cross_to_exit"] = round((ex - first).total_seconds() / 60, 1)
        out["cross_open"] = float(d.loc[i, "open"])
        if i > 0:
            out["price_before_cross"] = float(d.loc[i - 1, "close"])
            out["gap_points"] = round(abs(out["cross_open"] - out["price_before_cross"]), 2)
    out["candles"] = d[(d["timestamp"] >= ex - pd.Timedelta(minutes=12)) & (d["timestamp"] <= ex + pd.Timedelta(minutes=2))][
        ["timestamp", "open", "high", "low", "close"]]
    return out


def list_contracts(token, symbol):
    """Upstox Search Instruments — त्या नावाचे (exact) सर्व अजून-चालू MCX FUT contracts, expiry नुसार."""
    import requests
    from config import get_ist_today
    res = requests.get("https://api.upstox.com/v2/instruments/search", timeout=10,
                       headers={"Accept": "application/json", "Authorization": f"Bearer {token.strip()}"},
                       params={"query": symbol, "exchanges": "MCX", "instrument_types": "FUT", "page_number": 1, "records": 30})
    if res.status_code != 200:
        return []
    today = get_ist_today().isoformat()
    rows = [r for r in res.json().get("data", []) if (r.get("trading_symbol") or "").upper().split(" FUT")[0].strip() == symbol.upper()
            and (r.get("expiry") or "") >= today]
    return sorted(rows, key=lambda r: r.get("expiry", ""))


def margin_compare(token, symbol, contracts, margin_fn=None, ltp_fn=None, n=2):
    """पहिले n contracts: 1 lot BUY/SELL margin (Upstox Margin API), LTP, contract value, margin % of value."""
    from mcx_contract_specs import get_price_multiplier
    from mcx_margin import _one_order
    if margin_fn is None or ltp_fn is None:
        from upstox_api import fetch_ltp_map, fetch_required_margin
        margin_fn = margin_fn or fetch_required_margin
        ltp_fn = ltp_fn or fetch_ltp_map
    out = []
    for c in contracts[:n]:
        key = c.get("instrument_key")
        ltp = (ltp_fn(token, [key]) or {}).get(key)
        buy = margin_fn(token, _one_order(key, 1, "BUY", "D"))
        sell = margin_fn(token, _one_order(key, 1, "SELL", "D"))
        value = ltp * int(c.get("lot_size") or 1) * get_price_multiplier(symbol) if ltp else None
        out.append({"contract": c.get("trading_symbol"), "expiry": c.get("expiry"), "LTP": ltp, "BUY margin ₹": buy, "SELL margin ₹": sell,
                    "contract value ₹": round(value, 0) if value else None,
                    "margin % of value": round(100 * max(buy or 0, sell or 0) / value, 1) if value and (buy or sell) else None})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------------------------
def main(argv=None, fetch=None, token=None, db_path=None, settings=None, today=None, contracts_fn=None, margin_fn=None, ltp_fn=None):
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="GOLD")
    p.add_argument("--from", dest="date_from", default=None)
    p.add_argument("--to", dest="date_to", default=None)
    p.add_argument("--trade-id", action="append", default=None)
    p.add_argument("--level", type=float, default=None, help="--trade-id साठी trailing/SL level हाताने (detail मध्ये नसेल तर)")
    p.add_argument("--margin", action="store_true")
    p.add_argument("--token", default=None)
    p.add_argument("--out", default="mcx_replay_out")
    args = p.parse_args(argv)
    sym = args.symbol.upper()
    if fetch is None:
        from upstox_api import fetch_mcx_candles as fetch
    if db_path is None:
        from config import DB_PATH as db_path
    if token is None:
        import cloud_db
        token = cloud_db.get_effective_upstox_token(args.token)
    if settings is None:
        try:
            import cloud_db
            settings = cloud_db.get_strategy_settings("mcx_futures", sym)
        except Exception:
            settings = {}
    if today is None:
        from config import get_ist_today
        today = get_ist_today()
    if not token:
        print("❌ Upstox token नाही — candles मागवता येत नाहीत.")
        return 1
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 160)
    os.makedirs(args.out, exist_ok=True)

    trades = load_trades(db_path, sym, args.date_from, args.date_to, args.trade_id)
    if not trades:
        print(f"ℹ️ {sym}: या कालावधीत/ids साठी MCX trades सापडले नाहीत.")
    # cooldown साठी: निवडलेल्या कालावधीच्या आधीच्या दिवसापासूनचे सर्व trades
    first_day = min((pd.Timestamp(t["entry_time"]).normalize() for t in trades), default=None)
    history = load_trades(db_path, sym, (first_day - pd.Timedelta(days=1)).date() if first_day is not None else None, args.date_to) if trades else []
    rows, cache = [], {}
    for tr in trades:
        key = tr.get("instrument_key")
        if key not in cache:
            back = (pd.Timestamp(today) - pd.Timestamp(tr["entry_time"]).normalize()).days + 25
            cache[key] = (fetch(token, key, interval="30minute", lookback_days=max(back, 30)),
                          fetch(token, key, interval="day", lookback_days=max(back + 30, 60)))
        df30, dday = cache[key]
        if df30 is None or not len(df30):
            rows.append({"trade_id": tr["trade_id"], "entry_time": tr["entry_time"], "reasons": "⚠️ या contract चे 30M candles मिळाले नाहीत "
                         "(expire झालेल्या contract चा इतिहास Upstox कदाचित देत नाही)"})
            continue
        t_entry = pd.Timestamp(tr["entry_time"])
        prior = [h for h in history if h.get("exit_time") and pd.Timestamp(h["exit_time"]) <= t_entry and h["trade_id"] != tr["trade_id"]]
        rows.append(evaluate_trade(tr, df30, dday, prior, settings))
    if rows:
        table = pd.DataFrame(rows)
        table.to_csv(os.path.join(args.out, f"replay_{sym}.csv"), index=False)
        print(f"\n=== {sym} replay — फक्त entry आधी पूर्ण झालेले bars (no-lookahead) ===")
        print(table.drop(columns=["reasons"], errors="ignore").to_string(index=False))
        print("\nकारणं:")
        for r in rows:
            print(f"  {r['trade_id']}: {r.get('reasons') or '— (कुठलाही नियम अडवत नाही)'}")
        summ_rows = [r for r in rows if "a_both_against" in r]
        summ = summarize(summ_rows)
        if len(summ):
            summ.to_csv(os.path.join(args.out, f"replay_{sym}_summary.csv"), index=False)
            print(f"\n=== सारांश ({len(summ_rows)} trades — लहान sample, फक्त दिशादर्शक) ===")
            print(summ.to_string(index=False))

    for tr in (trades if args.trade_id else []):
        back = (pd.Timestamp(today) - pd.Timestamp(tr["exit_time"] or tr["entry_time"]).normalize()).days + 2
        df1m = fetch(token, tr["instrument_key"], interval="1minute", lookback_days=max(back, 2))
        fz = forensics(tr, df1m, args.level)
        print(f"\n=== Forensics: {tr['trade_id']} ({tr.get('exit_reason')}, exit {tr.get('exit_time')}) ===")
        print(f"exit_reason_detail: {fz['detail']}")
        print(f"peak_pnl: {fz['peak_pnl']} | detail मधला exit भाव: {fz['exit_price_in_detail']} | level: {fz['level']}")
        if fz["peak_time"]:
            print(f"peak (सर्वात फायद्याचा भाव): {fz['peak_price']:,.2f} @ {fz['peak_time']} — trailing level यानंतरच तयार झाला")
        if fz["first_cross_time"]:
            print(f"level प्रत्यक्ष पहिल्यांदा ओलांडला: {fz['first_cross_time']} → exit {fz['exit_time']} "
                  f"(अंतर {fz['minutes_cross_to_exit']} मिनिटं)")
            if fz["gap_points"] is not None:
                print(f"ओलांडण्याआधीचा शेवटचा भाव {fz['price_before_cross']:,.2f} → पुढच्या minute चा open {fz['cross_open']:,.2f} "
                      f"(उडी {fz['gap_points']:,.2f} pts). उडी level पलीकडे असेल तर SL-M order लावला असता तरी fill याच भावाजवळ झालं असतं.")
        else:
            print("1-मिनिट candles मध्ये level ओलांडल्याचं दिसलं नाही (किंवा डेटा/level उपलब्ध नाही) — --level देऊन पुन्हा चालवा.")
        if fz["candles"] is not None and len(fz["candles"]):
            print(fz["candles"].to_string(index=False))
            fz["candles"].to_csv(os.path.join(args.out, f"forensics_{tr['trade_id']}.csv"), index=False)

    if args.margin:
        contracts = (contracts_fn or list_contracts)(token, sym)
        mt = margin_compare(token, sym, contracts, margin_fn=margin_fn, ltp_fn=ltp_fn)
        print(f"\n=== {sym}: front वि. पुढचा contract — 1 lot margin (Upstox Margin API, आत्ताचा) ===")
        print(mt.to_string(index=False) if len(mt) else "(contracts/margin मिळाले नाहीत)")
        if len(mt):
            mt.to_csv(os.path.join(args.out, f"margin_{sym}.csv"), index=False)
    print(f"\nCSV: {os.path.abspath(args.out)} — हा script काहीही बदलत नाही.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
