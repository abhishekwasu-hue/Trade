"""engine_signal.py — common analysis engine चा signal bots ना एकाच interface ने (Abhi, Monday PAPER). **Order कधीच नाही.**

Engine (`engine_name`, default decision3 — Abhi, one bot): decision3 = थर v2.2 method engine (trend → area → pullback → commitment + c1; R:R नाही — Abhi 13 Oct;
live feed `engine3_live.py`, NIFTY / BANKNIFTY / SENSEX); decision2 = जुना मार्ग (NIFTY 1m ⇒ थर 1–7) तसाच उपलब्ध (`--engine decision2`).

रचना:
  • Service (`scripts/engine_signal_run.py`, cron, प्रत्येक बंद 15M candle नंतर): NIFTY 1m (Upstox, holdout वगळून) ⇒ थर 1–7 ⇒ शेवटच्या बंद
    15M candle चा decision2 निर्णय ⇒ इथल्या store मध्ये (VPS local SQLite, `ENGINE_SIGNAL_DB`, default data/engine_signals.db).
  • Adapter (bots, vision caption): `latest`, `opinion`, `own_allowed`, `pending_entry`, `mark_consumed`.
  • Bot setting `signal_source` (dashboard): own (default) / engine / both.
      own    ⇒ bot चा स्वतःचा signal; engine फक्त shadow मत (caption).
      engine ⇒ फक्त engine चा setup (bot चे spread selection / strikes / execution / settings तसेच) — `engine_entry.py`.
      both   ⇒ bot चा signal फक्त engine च्या ताज्या setup शी दिशा जुळली तरच.
  Engine चं मत निर्णयात फक्त `engine` / `both` निवडल्यावर; ते सुद्धा Vision + Abhi ✅ नंतरच entry (vision/gate.py).
"""
import json
import os
import sqlite3

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES = ("own", "engine", "both")
DEFAULTS = {"signal_source": "own", "engine_max_age_min": 30, "engine_lookback_days": 100, "engine_name": "decision3",
            "engine_first_bar_end": "09:30", "engine_last_bar_end": "15:00"}       # decision3: फक्त या वेळांत बंद होणारे 15M bars
ENGINES = ("decision3", "decision2")
ERROR = "error"                                                                     # fail-closed row (data / exception) ⇒ entry नाही
DIR_TXT = {1: "BULLISH", -1: "BEARISH"}
SIDE_TXT = {1: "bull put", -1: "bear call"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS engine_signals (
  symbol TEXT NOT NULL, bar_ts TEXT NOT NULL, computed_at TEXT, decision TEXT, gate TEXT, direction INTEGER,
  level_lo REAL, level_hi REAL, entry REAL, invalidation REAL, target REAL, grade TEXT, reason TEXT, payload TEXT,
  PRIMARY KEY (symbol, bar_ts));
CREATE TABLE IF NOT EXISTS engine_consumed (
  bot TEXT NOT NULL, symbol TEXT NOT NULL, bar_ts TEXT NOT NULL, status TEXT, at TEXT, PRIMARY KEY (bot, symbol, bar_ts));
"""


def db_path(path=None):
    return path or os.environ.get("ENGINE_SIGNAL_DB") or os.path.join(ROOT, "data", "engine_signals.db")


def connect(path=None, timeout=5):
    p = db_path(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    c = sqlite3.connect(p, timeout=timeout)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def now_ist():
    return (pd.Timestamp.now("UTC").tz_localize(None) + pd.Timedelta(hours=5, minutes=30)).floor("s")


def _naive(t):
    """IST naive Timestamp (tz-aware ⇒ IST मध्ये नेऊन tz काढा)."""
    t = pd.Timestamp(t)
    return t.tz_convert("Asia/Kolkata").tz_localize(None) if t.tzinfo is not None else t


def source_of(settings, key="signal_source"):
    v = str((settings or {}).get(key, DEFAULTS["signal_source"]) or "own").lower()
    return v if v in SOURCES else "own"


# ---------------------------------------------------------------------------------------------------------------- service
def row_from_decision(symbol, dec, bar_end):
    """decision2 चा dict ⇒ store row. दिशा: risk point (entry vs invalidation) नाहीतर I दिशा."""
    p = dec.get("points") or {}
    risk = p.get("10_risk") or {}
    area = p.get("7_area") or {}
    band = area.get("band") or [None, None]
    d = None
    if risk.get("entry") is not None and risk.get("invalidation") is not None:
        d = 1 if risk["entry"] > risk["invalidation"] else -1
    elif ((p.get("2_parent") or {}).get("I") or {}).get("dir") in (1, -1):
        d = int(p["2_parent"]["I"]["dir"])
    return {"symbol": str(symbol).upper(), "bar_ts": str(pd.Timestamp(bar_end)), "computed_at": str(now_ist()), "decision": dec.get("decision"),
            "gate": dec.get("gate"), "direction": d, "level_lo": band[0], "level_hi": band[1], "entry": risk.get("entry"),
            "invalidation": risk.get("invalidation"), "target": risk.get("target"), "grade": dec.get("grade"),
            "reason": dec.get("where_wrong"), "payload": json.dumps(dec, ensure_ascii=False, default=str)[:20000]}


def save(row, path=None):
    with connect(path) as c:
        cols = list(row)
        c.execute(f"INSERT OR REPLACE INTO engine_signals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [row[k] for k in cols])


def compute(m1, fut=None):
    """1m frame (holdout आधीच वगळलेला) ⇒ शेवटच्या **बंद** 15M candle चा (decision, bar_end). सगळं ≤ त्या candle."""
    from decision2 import engine as DE
    from pivots import engine as PE
    from scripts import decision_check as DCK
    m15 = PE.bars_15m(m1)
    if not len(m15):
        raise ValueError("15M candles नाहीत")
    t = len(m15) - 1
    C = DCK.build_ctx(m15, m1, fut, max(0, t - 2))
    return DE.decide(C, t), m15["bar_end"].iloc[t]


def run(symbol, access_token, fetch=None, path=None, lookback_days=None, now=None):
    """एक service cycle. रिटर्न saved row. Token नाही ⇒ स्पष्ट ValueError."""
    if not access_token:
        raise ValueError("Upstox token नाही — engine signal मोजता येत नाही (आधी daily login)")
    from elliott import data_policy as DP
    if fetch is None:
        from upstox_api import fetch_candles as fetch
    m1 = fetch(access_token, symbol, 0, interval="1minute", lookback_days=int(lookback_days or DEFAULTS["engine_lookback_days"]))
    if m1 is None or not len(m1):
        raise ValueError("1m candles मिळाले नाहीत")
    m1 = m1.copy()
    m1["timestamp"] = pd.to_datetime(m1["timestamp"])
    if getattr(m1["timestamp"].dt, "tz", None) is not None:
        m1["timestamp"] = m1["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    now = _naive(now or now_ist())
    m1 = m1[m1["timestamp"] + pd.Timedelta(minutes=1) <= now]                       # फक्त बंद 1m candles
    m1 = DP.filter_allowed(m1[["timestamp", "open", "high", "low", "close"]].sort_values("timestamp").reset_index(drop=True), "annotation")
    dec, bar_end = compute(m1)
    if pd.Timestamp(bar_end) > now:                                                 # शेवटचा 15M अजून बंद नाही ⇒ आधीचा हवा
        raise ValueError("शेवटचा 15M candle अजून बंद नाही")
    row = row_from_decision(symbol, dec, bar_end)
    save(row, path)
    return row


def engine_name(value=None):
    """decision3 (default) / decision2 — CLI `--engine` नाहीतर env `ENGINE_SIGNAL_ENGINE`. अज्ञात ⇒ ValueError (अंदाज नाही)."""
    v = str(value or os.environ.get("ENGINE_SIGNAL_ENGINE") or DEFAULTS["engine_name"]).strip().lower()
    if v not in ENGINES:
        raise ValueError(f"engine {v!r} — {ENGINES} पैकी हवा")
    return v


def _hm(s):
    h, m = (int(x) for x in str(s).split(":"))
    return h, m


def in_window(bar_end, s=None):
    """bar_end (IST) `engine_first_bar_end` … `engine_last_bar_end` मध्ये? (09:30 = 09:15 चा opening candle सुद्धा मोजला जातो.)"""
    s = {**DEFAULTS, **(s or {})}
    b = pd.Timestamp(bar_end)
    return _hm(s["engine_first_bar_end"]) <= (b.hour, b.minute) <= _hm(s["engine_last_bar_end"])


def expected_bar_end(now):
    """आत्ता (IST) शेवटचा बंद व्हायला हवा तो 15M bar_end."""
    return _naive(now).floor("15min")


def save_error(symbol, bar_ts, msg, path=None, engine="decision3"):
    """Fail-closed नोंद: त्या bar साठी "error" row ⇒ `pending_entry` नवा entry देत नाही (✅ च्या वाटेतला आधीचा setup मात्र तसाच — gate ठरवतो)."""
    save({"symbol": str(symbol).upper(), "bar_ts": str(pd.Timestamp(bar_ts)), "computed_at": str(now_ist()), "decision": ERROR,
          "gate": "data", "direction": None, "level_lo": None, "level_hi": None, "entry": None, "invalidation": None, "target": None,
          "grade": None, "reason": str(msg)[:300], "payload": json.dumps({"engine": engine, "error": str(msg)[:500]}, ensure_ascii=False)},
         path)


ALERT_REPEAT_MIN = 60                                                       # अजून अपयश ⇒ इतक्या मिनिटांनी पुन्हा एक ओळ


def _alert_state(p):
    try:
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    except (OSError, ValueError):
        return {}


def _alert_send(line, send):
    try:
        if send is None:
            from notifications import send_telegram_message as send
        send(line)
    except Exception:                                                    # noqa: BLE001
        print(line)


def _alert_path(state_path):
    return state_path or os.path.join(ROOT, "data", "engine_signal_alerts.json")


def alert_error(symbol, msg, send=None, state_path=None, now=None):
    """Engine error ⇒ Telegram: पहिल्या अपयशाला एक ओळ; अजून अपयशी असेल तर `ALERT_REPEAT_MIN` नंतरच पुन्हा. रिटर्न पाठवलं का. raise नाही."""
    p, sym = _alert_path(state_path), str(symbol).upper()
    now = _naive(now or now_ist())
    st = _alert_state(p)
    cur = st.get(sym) or {}
    last = pd.Timestamp(cur["last_sent"]) if cur.get("last_sent") else None
    if cur.get("failing") and last is not None and now - last < pd.Timedelta(minutes=ALERT_REPEAT_MIN):
        return False
    again = " (still failing)" if cur.get("failing") else ""
    _alert_send(f"❌ Engine {sym}{again}: {str(msg)[:160]} ⇒ no new engine entry for {sym} until the data is back (exits unaffected)", send)
    st[sym] = {"failing": True, "since": cur.get("since") or str(now), "last_sent": str(now)}
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return True


def alert_data_problem(symbol, msg="data problem: FUT volume missing", send=None, state_path=None, now=None):
    """Abhi Z-1c: data problem (NIFTY / BANKNIFTY FUT volume missing) ⇒ एक Telegram ओळ, symbol प्रमाणे दिवसातून जास्तीत जास्त एकदा
    (त्याच alert state file मध्ये). Entry आधीच नाही (caller). रिटर्न पाठवलं का. raise नाही."""
    p, sym = _alert_path(state_path), str(symbol).upper()
    day = str(_naive(now or now_ist()).date())
    st = _alert_state(p)
    seen = st.setdefault("_data_problem", {})
    if seen.get(sym) == day:
        return False
    _alert_send(f"⚠️ Engine {sym}: {str(msg)[:160]} ⇒ no engine entry for {sym} (exits unaffected)", send)
    seen[sym] = day
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return True


def alert_recovered(symbol, send=None, state_path=None, now=None):
    """आधी अपयशी होता आणि आता चालला ⇒ एक "recovered" ओळ (एकदाच). रिटर्न पाठवलं का."""
    p, sym = _alert_path(state_path), str(symbol).upper()
    st = _alert_state(p)
    cur = st.get(sym) or {}
    if not cur.get("failing"):
        return False
    _alert_send(f"✅ Engine {sym} recovered (failing since {pd.Timestamp(cur.get('since')):%H:%M}) — engine setups resume", send)
    st[sym] = {"failing": False}
    try:
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return True


def run3(symbol, access_token, feed=None, path=None, now=None, s=None, dry_run=False):
    """decision3 (V22) चा एक service cycle: शेवटच्या **बंद** 15M bar चा निर्णय ⇒ store. रिटर्न row (+ "skipped" कारण, असल्यास).
    Data नाही / अपूर्ण / exception ⇒ raise (caller: error row + Telegram ओळ). dry_run ⇒ store मध्ये लिहीत नाही."""
    import engine3_live as L
    now = _naive(now or now_ist())
    if feed is None:
        feed = L.UpstoxFeed(access_token, now.date())
    r = L.compute(str(symbol).upper(), feed, now, s)
    row = L.row_from_v22(symbol, r, now_ist)
    if pd.Timestamp(row["bar_ts"]) > now:
        raise ValueError("शेवटचा 15M candle अजून बंद नाही")
    if not in_window(row["bar_ts"], s) or pd.Timestamp(row["bar_ts"]).normalize() != now.normalize():
        row["skipped"] = f"bar {pd.Timestamp(row['bar_ts']):%Y%m%d %H:%M} entry window ({DEFAULTS['engine_first_bar_end']}–" \
                         f"{DEFAULTS['engine_last_bar_end']}, आजचा) बाहेर ⇒ store मध्ये नाही"
        return row
    if not dry_run:
        save(row, path)
    return row


# ---------------------------------------------------------------------------------------------------------------- adapter
def latest(symbol, now=None, max_age_min=None, path=None):
    """सर्वात ताजा engine निर्णय (bar_end ≤ now, वय ≤ max_age_min). नाही ⇒ None. कधीच raise नाही."""
    try:
        now = _naive(now or now_ist())
        age = int(max_age_min if max_age_min is not None else DEFAULTS["engine_max_age_min"])
        with connect(path) as c:
            r = c.execute("SELECT * FROM engine_signals WHERE symbol=? AND bar_ts<=? ORDER BY bar_ts DESC LIMIT 1",
                          (str(symbol).upper(), str(now))).fetchone()
        if r is None:
            return None
        r = dict(r)
        if pd.Timestamp(r["bar_ts"]) < now - pd.Timedelta(minutes=age):
            return None
        return r
    except Exception as exc:
        print(f"⚠️ engine_signal.latest: {type(exc).__name__}: {exc}")
        return None


def opinion(symbol, now=None, path=None, max_age_min=None):
    """Caption साठी shadow मत: "engine: setup ↑ bull put (grade B) · …" / "engine: wait — G-A: I नाही" / "engine: NA (…)"."""
    r = latest(symbol, now, max_age_min, path)
    if r is None:
        return "engine: NA (ताजा engine निर्णय नाही)"
    hm = pd.Timestamp(r["bar_ts"]).strftime("%H:%M")
    if r["decision"] == "setup" and r["direction"] in (1, -1):
        arrow = "↑" if r["direction"] > 0 else "↓"
        lv = f" · area {r['level_lo']:,.0f}–{r['level_hi']:,.0f}" if r.get("level_lo") is not None else ""
        return f"engine ({hm}): setup {arrow} {SIDE_TXT[r['direction']]} · grade {r.get('grade') or '—'}{lv}"
    return f"engine ({hm}): {r.get('decision') or 'wait'} — {r.get('gate') or ''}: {r.get('reason') or ''}".strip()


def own_allowed(symbol, direction, settings, now=None, path=None, key="signal_source"):
    """bot चा स्वतःचा signal वापरायचा का (signal_source नुसार). रिटर्न (ok, कारण)."""
    src = source_of(settings, key)
    if src == "own":
        return True, "signal_source = own"
    if src == "engine":
        return False, "signal_source = engine ⇒ bot चा स्वतःचा signal वापरत नाही"
    r = latest(symbol, now, (settings or {}).get("engine_max_age_min"), path)
    want = 1 if str(direction).upper() == "BULLISH" else -1
    if r is None or r["decision"] != "setup":
        return False, f"signal_source = both ⇒ engine setup नाही ({'NA' if r is None else (r.get('gate') or r.get('decision'))})"
    if r["direction"] != want:
        return False, f"signal_source = both ⇒ engine दिशा {DIR_TXT.get(r['direction'], '?')} ≠ {direction}"
    return True, "signal_source = both ⇒ engine सहमत"


def pending_entry(bot, symbol, settings, now=None, path=None):
    """signal_source = engine: या bot ने अजून न वापरलेला ताजा engine setup. नाही ⇒ None.
    ताजा = bar_ts ≥ now − engine_max_age_min. सर्वात नवा setup (त्यानंतरचा "wait" / "error" bar तो रद्द करत नाही — Abhi च्या ✅ ची वाट
    चालू असताना पुढचा 15M bar आला / data त्रुटी आली तरी तोच setup; Vision gate / ✅ हाच अंतिम तपास). "error" row कधीच setup नाही ⇒
    नवा entry नाही (fail-closed). नवा setup ⇒ जुना बाद. सर्वात नवा setup आधीच वापरला ⇒ None."""
    if source_of(settings) != "engine":
        return None
    try:
        now = _naive(now or now_ist())
        age = int((settings or {}).get("engine_max_age_min") or DEFAULTS["engine_max_age_min"])
        with connect(path) as c:
            rows = [dict(x) for x in c.execute("SELECT * FROM engine_signals WHERE symbol=? AND bar_ts<=? AND bar_ts>=? ORDER BY bar_ts DESC",
                                                (str(symbol).upper(), str(now), str(now - pd.Timedelta(minutes=age)))).fetchall()]
            r = next((x for x in rows if x["decision"] == "setup"), None)
            if r is None or r["direction"] not in (1, -1):
                return None
            done = c.execute("SELECT status FROM engine_consumed WHERE bot=? AND symbol=? AND bar_ts=?",
                             (bot, str(symbol).upper(), r["bar_ts"])).fetchone()
    except Exception:
        return None
    return None if done else r


def mark_consumed(bot, symbol, bar_ts, status, path=None):
    try:
        with connect(path) as c:
            c.execute("INSERT OR REPLACE INTO engine_consumed (bot, symbol, bar_ts, status, at) VALUES (?,?,?,?,?)",
                      (bot, str(symbol).upper(), str(bar_ts), str(status), str(now_ist())))
    except Exception as exc:
        print(f"⚠️ engine_signal.mark_consumed: {exc}")
