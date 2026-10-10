"""paper/manual.py — ✋ Manual trigger (Abhi, Monday PAPER — P0): Telegram `/paper` ⇒ bot signal सारखाच मार्ग:
pending signal (source MANUAL) ⇒ Vision (अयशस्वी ⇒ "Vision: NA", बटणं तरीही) ⇒ ✅ / ❌ ⇒ PAPER entry ⇒ updates ⇒ exit ⇒ journal.

  /paper NIFTY bullput SL 24750 [T 25300]               ⇒ strikes / spread width / lots: `manual_profile` bot च्या existing settings
  /paper NIFTY bullput 24900/24800 SL 24750 [T 25300]   ⇒ Abhi चे strikes (short/hedge)

Validation (सगळं order च्या आधी): instrument enabled (config.yaml paper), बाजार वेळ, token, pause / kill-switch / उघडी manual position /
आधीचा pending manual, option chain (आज expiry ⇒ पुढची weekly — bots चाच नियम), बाजू (bull put: short > hedge, SL spot खाली, T वर;
bear call उलट), strikes chain मध्ये, net credit > 0. R:R = |T − spot| / |spot − SL| (spot वरून) — < 3 ⇒ इशारा (तरी घेता येतो).

🎓 Vision bot key "manual" वेगळा (bots च्या forced levels मध्ये manual signal मिसळू नये ⇒ दुहेरी entry नाही); profile फक्त strikes / lots साठी.
Exit: तुमचा spot SL / T (`spot_exit`, paper watcher — trade_monitor च्या प्रत्येक cycle ला) + backstop म्हणून generic exit नियम
(SL = credit च्या 100% तोटा, 3:10 carry-forward नियम). Kill-switch / pause / VIX नियम entry वेळी पुन्हा `open_multi_leg_trade` मध्ये लागतात.
AI कधीच order देत नाही; किंमती फक्त Upstox option chain / LTP मधून. **फक्त PAPER**.
"""
import json
import os
import sqlite3
import uuid

import pandas as pd

from . import config as PC
from . import journal as PJ
from . import lots as PL

BOT = "manual"                                                          # vision bot key
SOURCE = "manual_paper"                                                 # live_trades.source
KINDS = {"bullput": ("BULLISH", "PE", "Support"), "bearcall": ("BEARISH", "CE", "Resistance")}
PROFILES = {"srv3_instant": "1m_instant", "dynamic_sr_instant": "1m_instant", "srv2_momentum_reversal": "15m_dynamic_sr"}
PROFILE_LABEL = {"srv3_instant": "SR V3", "dynamic_sr_instant": "5-Min Instant", "srv2_momentum_reversal": "15M Dynamic SR"}
RR_WARN = 3.0
OPEN = ("QUEUED",)                                                      # approval / Vision ची वाट
HELP = ("✋ <b>Manual PAPER trigger</b> (फक्त approver):\n"
        "• <code>/paper NIFTY bullput SL 24750 T 25300</code> — strikes / width / lots: manual_profile bot च्या settings ने\n"
        "• <code>/paper NIFTY bearcall 25100/25200 SL 25250 T 24800</code> — तुमचे strikes (short/hedge)\n"
        "SL / T = spot. T ऐच्छिक. पुढे: Vision ⇒ ✅ / ❌ ⇒ PAPER entry. R:R &lt; 3 ⇒ इशारा.\n"
        "इतर: /status · /positions · /pause · /resume · /pending · /today")

SCHEMA = """
CREATE TABLE IF NOT EXISTS manual_setups (
  id TEXT PRIMARY KEY, created_at TEXT, by_ TEXT, command TEXT, symbol TEXT, kind TEXT, direction TEXT, short_strike REAL, hedge_strike REAL,
  strikes_from TEXT, sl REAL, target REAL, spot REAL, rr REAL, lots INTEGER, lot_size INTEGER, expiry TEXT, expiry_index INTEGER,
  profile TEXT, status TEXT, vision_signal_id TEXT, trade_id TEXT, note TEXT, dry_run INTEGER DEFAULT 0, updated_at TEXT);
"""


# ------------------------------------------------------------------------------------------------ store
def connect(path=None):
    c = sqlite3.connect(PJ.db_path(path), timeout=5)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _put(row, path=None):
    os.makedirs(os.path.dirname(PJ.db_path(path)) or ".", exist_ok=True)
    with connect(path) as c:
        if c.execute("SELECT 1 FROM manual_setups WHERE id=?", (row["id"],)).fetchone():
            ks = [k for k in row if k != "id"]
            c.execute(f"UPDATE manual_setups SET {','.join(f'{k}=?' for k in ks)} WHERE id=?", [row[k] for k in ks] + [row["id"]])
        else:
            c.execute(f"INSERT INTO manual_setups ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))


def _set_status(mid, frm, to, path=None, **kw):
    """Conditional (status = frm असेल तरच) ⇒ दोन process (Telegram callback + sweep / dry-run) एकाच वेळी ⇒ एकच जिंकतो."""
    os.makedirs(os.path.dirname(PJ.db_path(path)) or ".", exist_ok=True)
    kw = {**kw, "status": to, "updated_at": str(_now())}
    with connect(path) as c:
        cur = c.execute(f"UPDATE manual_setups SET {','.join(f'{k}=?' for k in kw)} WHERE id=? AND status=?", [*kw.values(), mid, frm])
        return cur.rowcount == 1


def get(mid, path=None):
    if not os.path.exists(PJ.db_path(path)):
        return None
    with connect(path) as c:
        r = c.execute("SELECT * FROM manual_setups WHERE id=?", (mid,)).fetchone()
    return dict(r) if r else None


def rows(status=None, path=None, symbol=None, trade_id=None):
    if not os.path.exists(PJ.db_path(path)):
        return []
    q, a = "SELECT * FROM manual_setups WHERE 1=1", []
    if status:
        st = (status,) if isinstance(status, str) else tuple(status)
        q += f" AND status IN ({','.join('?' * len(st))})"
        a += list(st)
    if symbol:
        q += " AND symbol=?"
        a.append(symbol)
    if trade_id:
        q += " AND trade_id=?"
        a.append(trade_id)
    with connect(path) as c:
        return [dict(r) for r in c.execute(q + " ORDER BY created_at", a).fetchall()]


# ------------------------------------------------------------------------------------------------ parse / checks
def _now():
    from config import get_ist_now
    t = pd.Timestamp(get_ist_now())
    return t.tz_localize(None) if t.tzinfo else t


def parse(text):
    """रिटर्न (dict, None) किंवा (None, चूक)."""
    t = (text or "").replace(",", " ").split()
    use = "वापर: /paper NIFTY bullput [short/hedge] SL &lt;spot&gt; [T &lt;spot&gt;] — /help पहा"
    if len(t) < 5 or t[0].split("@")[0].lower() != "/paper":
        return None, use
    sym, kind = t[1].upper(), t[2].lower()
    if kind not in KINDS:
        return None, f"बाजू '{kind}' नाही — bullput किंवा bearcall. {use}"
    out = {"symbol": sym, "kind": kind, "short": None, "hedge": None, "sl": None, "target": None}
    i = 3
    try:
        if "/" in t[i]:
            a, b = t[i].split("/", 1)
            out["short"], out["hedge"] = float(a), float(b)
            i += 1
        if i + 1 >= len(t) or t[i].upper() != "SL":
            return None, f"SL हवा. {use}"
        out["sl"] = float(t[i + 1])
        i += 2
        if i < len(t):
            if i + 1 >= len(t) or t[i].upper() != "T":
                return None, f"'{t[i]}' समजलं नाही. {use}"
            out["target"] = float(t[i + 1])
            i += 2
        if i != len(t):
            return None, f"जास्तीचे शब्द. {use}"
    except ValueError:
        return None, f"आकडे समजले नाहीत. {use}"
    return out, None


def side_errors(kind, spot, sl, target=None, short=None, hedge=None):
    """बाजू / स्तर तपासणी. रिटर्न चुकांची यादी."""
    e = []
    if kind == "bullput":
        if short is not None and not short > hedge:
            e.append(f"bull put: short ({short:g}) > hedge ({hedge:g}) हवा")
        if not sl < spot:
            e.append(f"bull put: SL ({sl:g}) spot ({spot:,.1f}) च्या खाली हवा")
        if target is not None and not target > spot:
            e.append(f"bull put: T ({target:g}) spot ({spot:,.1f}) च्या वर हवा")
    else:
        if short is not None and not short < hedge:
            e.append(f"bear call: short ({short:g}) < hedge ({hedge:g}) हवा")
        if not sl > spot:
            e.append(f"bear call: SL ({sl:g}) spot ({spot:,.1f}) च्या वर हवा")
        if target is not None and not target < spot:
            e.append(f"bear call: T ({target:g}) spot ({spot:,.1f}) च्या खाली हवा")
    return e


def rr(spot, sl, target):
    if target is None:
        return None
    risk = abs(float(spot) - float(sl))
    return round(abs(float(target) - float(spot)) / risk, 2) if risk > 0 else None


def _has_strike(chain, strike, opt):
    side = "put_options" if opt == "PE" else "call_options"
    for it in chain or []:
        if it.get("strike_price") is not None and abs(float(it["strike_price"]) - float(strike)) < 1e-6:
            o = it.get(side) or {}
            return bool(o.get("instrument_key")) and ((o.get("market_data") or {}).get("ltp") or 0) > 0
    return False


def build_spread(chain, direction, short, hedge, step):
    """दिलेल्या short / hedge strikes चा spread — bots चंच `select_credit_spread_itm` (ITM depth 0 ⇒ short = दिलेला strike)."""
    from strategy import select_credit_spread_itm
    return select_credit_spread_itm(chain, direction, short, itm_depth_points=0, hedge_width_points=abs(float(short) - float(hedge)), step=step)


def default_chain(token, symbol):
    """(chain, कारण, expiry_index). आज expiry ⇒ पुढची weekly (bots / engine_entry चाच नियम)."""
    from classic_sr_reversal_trader import is_todays_expiry_day
    from upstox_api import fetch_upstox_option_chain
    ei = 1 if is_todays_expiry_day(token, symbol) else 0
    ch, why = fetch_upstox_option_chain(token, symbol, expiry_index=ei)
    return ch, why, ei


def _profile(path=None):
    try:
        from vision import config as VC
        p = VC.load("_global", path).get("manual_profile") or "srv3_instant"
    except Exception:
        p = "srv3_instant"
    return p if p in PROFILES else "srv3_instant"


def _cutoff_txt(cfg=None):
    return str((cfg or PC.load()).get("entry_cutoff") or "14:45")


def _before_cutoff(now=None, cfg=None):
    h, mi = (int(x) for x in _cutoff_txt(cfg).split(":"))
    t = pd.Timestamp(now or _now())
    return (t.hour, t.minute) < (h, mi)


def _token():
    import cloud_db
    return cloud_db.get_effective_upstox_token(None)


def _market_open():
    from config import is_market_open
    return is_market_open()


def _paused():
    import cloud_db
    s = cloud_db.get_trading_pause_settings() or {}
    return bool(s.get("paused")), s.get("reason")


def _kill():
    from trading_engine import check_kill_switch
    return check_kill_switch()


def _has_open(symbol, source):
    from database import has_open_trade_from_source
    return has_open_trade_from_source(symbol, source)


def _settings(profile, symbol):
    import cloud_db
    return cloud_db.get_strategy_settings(PROFILES[profile], symbol)


def summary(m):
    st = f"{m['short_strike']:g}/{m['hedge_strike']:g}" if m.get("short_strike") is not None else "?"
    rtxt = "NA (T नाही)" if m.get("rr") is None else f"{m['rr']:g}" + (" ⚠️ &lt; 3" if m["rr"] < RR_WARN else "")
    return (f"✋ MANUAL · {m['symbol']} {m['kind']} {st} ({m['strikes_from']}) · SL {m['sl']:g}"
            + (f" · T {m['target']:g}" if m.get("target") is not None else "") + f" · spot {m['spot']:,.1f} · R:R {rtxt} · "
            f"{m['lots']} lot × {m['lot_size']}")


# ------------------------------------------------------------------------------------------------ /paper
def handle(text, by, send=None, token_fn=None, market_fn=None, chain_fn=None, gate_fn=None, paused_fn=None, kill_fn=None,
           has_open=None, settings_fn=None, profile=None, lot_fn=None, now=None, path=None, vpath=None, dry_run=False, cfg=None):
    """`/paper …` ⇒ validation ⇒ pending signal (Vision gate, HOLD). रिटर्न (ok, संदेश). Order नाही."""
    send = send or (lambda s: None)

    def no(msg):
        send(f"❌ /paper: {msg}")
        return False, msg

    p, err = parse(text)
    if err:
        return no(err)
    sym, kind = p["symbol"], p["kind"]
    direction, opt, role = KINDS[kind]
    cfg = cfg or PC.load()
    if not PC.enabled(sym, cfg):
        return no(f"{sym}: PAPER साठी config.yaml मध्ये enabled: false")
    if not dry_run and not (market_fn or _market_open)():
        return no("बाजार बंद (09:15–15:30) ⇒ manual entry नाही")
    if not dry_run and not _before_cutoff(now, cfg):
        return no(f"नवीन entry ची वेळ संपली ({_cutoff_txt(cfg)} नंतर नाही — bots सारखंच; EOD square-off जवळ)")
    token = (token_fn or _token)()
    if not token:
        return no("Upstox token नाही — आधी daily login (Upstox app approve); तोपर्यंत manual entry नाही")
    paused, why = (paused_fn or _paused)()
    if paused:
        return no(f"Trading pause चालू ({why or '—'}) ⇒ नवीन entry नाही (/resume)")
    ok, why = (kill_fn or _kill)()
    if not ok:
        return no(f"Kill-switch: {why}")
    source = SOURCE + ("_dryrun_shadow" if dry_run else "")
    if (has_open or _has_open)(sym, source):
        return no(f"{sym}: manual PAPER position आधीच उघडी (एका वेळी एकच)")
    if rows(OPEN, path, symbol=sym):
        return no(f"{sym}: आधीचा manual signal अजून ✅ / ❌ च्या वाटेत (/pending)")
    chain, cwhy, ei = (chain_fn or default_chain)(token, sym)
    if not chain:
        return no(f"option chain नाही ({cwhy})")
    spot = chain[0].get("underlying_spot_price")
    if spot is None:
        return no("option chain मध्ये spot नाही")
    spot = float(spot)
    errs = side_errors(kind, spot, p["sl"], p["target"], p["short"], p["hedge"])
    if errs:
        return no("; ".join(errs))
    import cloud_db
    step = cloud_db.STRIKE_STEP.get(sym, cloud_db.STRIKE_STEP["NIFTY"])
    profile = profile or _profile(vpath)
    st = (settings_fn or _settings)(profile, sym)
    if p["short"] is not None:
        miss = [f"{k:g} {opt}" for k in (p["short"], p["hedge"]) if not _has_strike(chain, k, opt)]
        if miss:
            return no(f"strike chain मध्ये नाही / LTP नाही: {', '.join(miss)} (expiry {chain[0].get('expiry')})")
        sp, src = build_spread(chain, direction, p["short"], p["hedge"], step), "तुमचे strikes"
    else:
        atm = round(spot / step) * step
        from strategy import select_credit_spread_itm
        sp = select_credit_spread_itm(chain, direction, atm, step=step, itm_depth_points=st["itm_depth_points"],
                                      hedge_width_points=st["hedge_width_points"])
        src = f"{PROFILE_LABEL.get(profile, profile)} settings"
    if sp is None:
        return no("spread बनत नाही (strike LTP नाही किंवा net credit ≤ 0)")
    short, hedge = float(sp["short_leg"]["strike"]), float(sp["long_leg"]["strike"])
    errs = side_errors(kind, spot, p["sl"], None, short, hedge)
    if errs:
        return no("; ".join(errs))
    lot_size, lsrc = (lot_fn or (lambda: PL.lot_size(token, sym, cfg=cfg)))()
    if lot_size is None:
        return no(f"lot size नाही ({lsrc})")
    lots = int(st.get("lots") or 1)
    now = pd.Timestamp(now or _now())
    m = {"id": uuid.uuid4().hex[:12], "created_at": str(now), "by_": by, "command": text.strip()[:200], "symbol": sym, "kind": kind,
         "direction": direction, "short_strike": short, "hedge_strike": hedge, "strikes_from": src, "sl": p["sl"], "target": p["target"],
         "spot": spot, "rr": rr(spot, p["sl"], p["target"]), "lots": lots, "lot_size": int(lot_size), "expiry": chain[0].get("expiry"),
         "expiry_index": ei, "profile": profile, "status": "NEW", "dry_run": 1 if dry_run else 0, "updated_at": str(now)}
    _put(m, path)
    tags = {"manual": True, "manual_id": m["id"], "manual_text": summary(m), "breakout_entry": False}
    if dry_run:
        tags["dry_run"] = True
    if gate_fn is None:
        from vision.gate import entry_gate as gate_fn
    try:
        g = gate_fn(BOT, sym, "PAPER", direction, p["sl"], role, "5M", now, spot, lots, 0, tags=tags, path=vpath)
    except Exception as exc:
        _set_status(m["id"], "NEW", "FAILED", path, note=f"gate: {exc}")
        return no(f"Vision gate त्रुटी ⇒ entry नाही ({type(exc).__name__})")
    if g.action != "HOLD" or not g.signal_id:                           # approval मार्ग नसेल तर (approval बंद / symbol यादीत नाही) ⇒ entry नाही
        _set_status(m["id"], "NEW", "FAILED", path, note=f"gate {g.action} {g.status}: {g.note}"[:300])
        return no(f"approval मार्ग उपलब्ध नाही ({g.action} {g.status}: {g.note}) ⇒ entry नाही")
    _set_status(m["id"], "NEW", "QUEUED", path, vision_signal_id=g.signal_id)
    warn = "" if m["rr"] is None or m["rr"] >= RR_WARN else f"\n⚠️ R:R {m['rr']:g} &lt; 3 — तरीही ✅ दाबल्यास entry होईल"
    msg = f"{summary(m)}\n⏳ Vision chart + ✅ / ❌ संदेश येतोय (signal {g.signal_id}){warn}"
    send(msg)
    return True, msg


# ------------------------------------------------------------------------------------------------ approval ⇒ entry
def execute_ready(token=None, now=None, gate_fn=None, open_fn=None, chain_fn=None, send=None, path=None, vpath=None, market_fn=None,
                  only_signal=None):
    """उघडे manual signals: ✅ ⇒ (drift guard, gate) ⇒ PAPER entry; ❌ / timeout / मुदत ⇒ बंद. Idempotent (gate + status conditional).
    Telegram callback (✅ नंतर लगेच), Telegram service चा sweep आणि dry-run — तिघेही हेच. कधीच raise नाही. रिटर्न [(id, निकाल)]."""
    out = []
    send = send or (lambda s: None)
    try:
        from vision import store as VS
        if gate_fn is None:
            from vision.gate import entry_gate as gate_fn
        for m in rows(OPEN, path):
            if only_signal and m.get("vision_signal_id") != only_signal:
                continue
            try:
                out.append((m["id"], _execute_one(m, VS, token, now, gate_fn, open_fn, chain_fn, send, path, vpath, market_fn)))
            except Exception as exc:
                print(f"⚠️ manual execute ({m['id']}): {type(exc).__name__}: {exc}")
    except Exception as exc:
        print(f"⚠️ manual execute: {type(exc).__name__}: {exc}")
    return out


def _execute_one(m, VS, token, now, gate_fn, open_fn, chain_fn, send, path, vpath, market_fn):
    v = VS.get_signal(m["vision_signal_id"], vpath) if m.get("vision_signal_id") else None
    st = (v or {}).get("status")
    direction, opt, role = KINDS[m["kind"]]
    tags = {"manual": True, "manual_id": m["id"], "manual_text": summary(m), "breakout_entry": False}
    if m.get("dry_run"):
        tags["dry_run"] = True
    spot, chain = float(m["spot"]), None
    if st == "APPROVED":
        from vision import config as VC
        from vision import gate as VG
        if VG._exec_expired(v, VC.load(BOT, vpath), pd.Timestamp(now or VS.now_ist())):
            chain = None                                                 # exec window संपली ⇒ gate EXPIRED करतो (खाली), entry नाही
        else:
            if not m.get("dry_run") and not _before_cutoff(now or VS.now_ist()):
                _set_status(m["id"], "QUEUED", "FAILED", path, note="cutoff / बाजार बंद")
                send(f"❌ ✋ MANUAL {m['symbol']}: ✅ मिळालं पण नवीन entry ची वेळ संपली ({_cutoff_txt()}) ⇒ entry नाही")
                return "FAILED cutoff"
            token = token or _token()
            if not token:
                return "APPROVED पण token नाही ⇒ थांबलो (exec window मध्ये पुन्हा)"
            if not m.get("dry_run") and not (market_fn or _market_open)():
                _set_status(m["id"], "QUEUED", "FAILED", path, note="बाजार बंद")
                send(f"❌ ✋ MANUAL {m['symbol']}: ✅ मिळालं पण बाजार बंद ⇒ entry नाही")
                return "FAILED market"
            chain, why, _ = (chain_fn or (lambda t, s: default_chain(t, s)))(token, m["symbol"])
            if not chain:
                return f"option chain नाही ({why}) ⇒ पुन्हा प्रयत्न"
            spot = float(chain[0].get("underlying_spot_price") or spot)
    g = gate_fn(BOT, m["symbol"], "PAPER", direction, m["sl"], role, "5M", pd.Timestamp(m["created_at"]), spot, int(m["lots"]), 0,
                tags=tags, forced=True, path=vpath)
    if g.action == "ENTER" and chain is None:                           # (exec window संपलेली असताना gate ENTER देत नाही — तरी सुरक्षित)
        _set_status(m["id"], "QUEUED", "FAILED", path, note="chain नाही")
        return "FAILED chain"
    if g.action == "ENTER":
        import cloud_db
        step = cloud_db.STRIKE_STEP.get(m["symbol"], cloud_db.STRIKE_STEP["NIFTY"])
        sp = build_spread(chain, direction, m["short_strike"], m["hedge_strike"], step)
        if sp is None:
            _set_status(m["id"], "QUEUED", "FAILED", path, note="strike LTP नाही / credit ≤ 0")
            _note(g.signal_id, "manual: spread बनत नाही ⇒ entry नाही")
            send(f"❌ ✋ MANUAL {m['symbol']}: ✅ नंतर spread बनत नाही (LTP / credit) ⇒ entry नाही")
            return "FAILED spread"
        if open_fn is None:
            from trading_engine import open_multi_leg_trade as open_fn
        source = SOURCE + ("_dryrun_shadow" if m.get("dry_run") else "")
        ok, resp = open_fn(token, m["symbol"], sp, lots=int(g.lots), lot_size=int(m["lot_size"]), sl_pct_of_max_loss=None,
                           target_pct_of_max_profit=100, product_type="D", trading_mode="PAPER", trading_style="INTRADAY", sl_pct_of_credit=100,
                           source=source, entry_level_price=float(m["sl"]), entry_timeframe="MANUAL", entry_spot_price=spot,
                           direction=direction, entry_reason_tag="MANUAL_TRIGGER")
        if ok:
            tid = (resp or {}).get("trade_id")
            for _ in range(5):                                           # journal DB lock ⇒ पुन्हा (trade_id link हरवू नये — SL / T त्यावर)
                try:
                    _set_status(m["id"], "QUEUED", "EXECUTED", path, trade_id=tid, note=f"lots {g.lots}")
                    break
                except sqlite3.Error as exc:
                    print(f"⚠️ manual EXECUTED नोंद (पुन्हा): {exc}")
                    import time
                    time.sleep(0.5)
            _note(g.signal_id, f"manual PAPER OPENED {tid}")
            return f"EXECUTED {tid}"
        why = (resp or {}).get("reason") or (resp or {}).get("message") or resp
        _set_status(m["id"], "QUEUED", "FAILED", path, note=str(why)[:300])
        _note(g.signal_id, f"manual PAPER FAILED: {why}")
        send(f"❌ ✋ MANUAL {m['symbol']}: entry झाली नाही — {why}")
        return f"FAILED {why}"
    if g.action == "SHADOW":                                             # नाकारलं / drift ⇒ manual साठी shadow trade नाही
        _set_status(m["id"], "QUEUED", "REJECTED", path, note=f"{g.status}: {g.note}"[:300])
        send(f"❌ ✋ MANUAL {m['symbol']}: entry नाही — {g.note}")
        return f"REJECTED {g.status}"
    v2 = VS.get_signal(m["vision_signal_id"], vpath) if m.get("vision_signal_id") else None
    st2 = (v2 or {}).get("status")
    if st2 is None or st2 not in VS.OPEN_V1:                            # EXPIRED / FAILED / SHADOWED … ⇒ manual बंद
        _set_status(m["id"], "QUEUED", "EXPIRED", path, note=f"vision {st2}")
        send(f"⌛ ✋ MANUAL {m['symbol']}: {st2 or 'signal नाही'} ⇒ entry नाही")
        return f"EXPIRED {st2}"
    return f"HOLD {st2}"


def _note(sid, text):
    try:
        from vision.gate import note_execution
        note_execution(sid, text)
    except Exception:
        pass


# ------------------------------------------------------------------------------------------------ spot SL / T exit
def spot_exit(t, access_token, spot_fn=None, close_fn=None, path=None, send=None, tag=""):
    """उघडा manual trade: spot ने तुमचा SL / T ओलांडला ⇒ बंद (close_trade_manually). रिटर्न exit कारण / None. कधीच raise नाही."""
    try:
        if not access_token:
            return None
        ms = rows(None, path, trade_id=t["trade_id"])
        if ms:
            m = ms[-1]
        elif t.get("entry_level_price") is not None:                    # journal ची नोंद चुकली तरी: entry_level_price = तुमचा SL (open वेळी)
            m = {"kind": "bullput" if str(t.get("strategy")) == "BULL_PUT_SPREAD" else "bearcall", "sl": float(t["entry_level_price"]),
                 "target": None}
        else:
            return None
        if spot_fn is None:
            def spot_fn(tok, sym):
                from upstox_api import fetch_ltp_map, get_instrument_key
                k = get_instrument_key(sym)
                return (fetch_ltp_map(tok, [k]) or {}).get(k)
        spot = spot_fn(access_token, t["symbol"])
        if spot is None:
            return None
        spot = float(spot)
        bull = m["kind"] == "bullput"
        why = None
        if (bull and spot <= m["sl"]) or (not bull and spot >= m["sl"]):
            why = ("MANUAL_SPOT_SL", f"spot {spot:,.1f} ने तुमचा SL {m['sl']:g} ओलांडला")
        elif m.get("target") is not None and ((bull and spot >= m["target"]) or (not bull and spot <= m["target"])):
            why = ("MANUAL_SPOT_TARGET", f"spot {spot:,.1f} ने तुमचा T {m['target']:g} गाठला")
        if why is None:
            return None
        if close_fn is None:
            from trading_engine import close_trade_manually as close_fn
        ok, res = close_fn(access_token, t["trade_id"], t["symbol"], "D", exit_reason=why[0], exit_reason_detail=why[1])
        if not ok:
            print(f"⚠️ manual spot exit ({t['trade_id']}): {res}")
            return None
        return why[0]
    except Exception as exc:
        print(f"⚠️ manual spot exit: {type(exc).__name__}: {exc}")
        return None


def rr_for_trade(trade_id, path=None):
    ms = rows(None, path, trade_id=trade_id)
    return ms[-1].get("rr") if ms else None


def profile_for_trade(trade_id, path=None):
    ms = rows(None, path, trade_id=trade_id)
    return ms[-1].get("profile") if ms else None


def as_json(m):
    return json.dumps({k: m.get(k) for k in ("symbol", "kind", "short_strike", "hedge_strike", "sl", "target", "spot", "rr")}, ensure_ascii=False)
