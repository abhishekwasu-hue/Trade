"""bots_common/one_bot.py — Abhi (one bot): फक्त 15M SRv2 (`15m_dynamic_sr`) ON, signal_source = engine (decision3), PAPER, फक्त
dashboard setting `signal_symbols` चे symbols (default NIFTY / BANKNIFTY; `cloud_db.get_signal_symbols`) — बाकी index (SENSEX) वर 15M SRv2
सुद्धा OFF (data / context म्हणून राहतो). बाकी प्रत्येक entry-capable bot OFF — तेच field जे bot स्वतः तपासतो (`symbol_enabled` …);
काहीही delete नाही; strikes / ITM depth / hedge / lots / SL / TSL / target / exits ला हात नाही; LIVE / LIVE_PAPER combo ला हात नाही (फक्त इशारा).

  plan(io)          ⇒ बदलांची यादी (before / after), LIVE combos skip.
  apply(io, ...)    ⇒ before-state JSON (revert साठी) + लिहिणं.  revert(io, before) ⇒ तंतोतंत आधीचं (आधी नसलेले keys काढले).
  one_bot_status()  ⇒ प्रत्येक entry-capable bot चा प्रत्यक्ष (effective) on/off + engine schedule ⇒ pre-open ओळ (`preopen_line`).
  apply_signal_symbols(...) ⇒ Abhi 9a (PF-3): dashboard वर `signal_symbols` सेव्ह ⇒ plan चा signal-symbols भाग (15M SRv2 per symbol
                    on/off, Vision srv2 symbols, PAPER instruments) लगेच लावतो — तेच plan / apply, LIVE नकार तसाच; टप्पेवार निकाल + log.

Entry-capable bots (code inventory; exits वेगळे — trade_monitor / MCX exit monitor — त्यांना symbol_enabled लागत नाही):
  15m_dynamic_sr (srv2_momentum_reversal_strategy.py)   symbol_enabled  ⇒ ON (engine मार्ग: paper/bot_hooks.pre_cycle → engine_entry)
  1m_instant (dynamic_sr_instant_trader.py)             symbol_enabled  ⇒ OFF (त्यातले otm / min-hold / vision shadows सुद्धा बंद)
  SR V3 PAPER shadow (srv3_instant_shadow.py)           1m_instant.srv3_shadow_enabled ⇒ OFF
  classic_sr_reversal (classic_sr_reversal_trader.py)   symbol_enabled  ⇒ OFF
  mcx_futures (mcx_futures_trader.py --mode entry)      symbol_enabled  ⇒ OFF (MCX exits चालूच)
  Vision shadow (<bot>_vision_shadow PAPER trades)      vision approval_required = True ⇒ shadow position नाही (srv2 साठी तपासून)
  oi_signal_auto_trader / credit_spread_auto_trader / oi_greeks_vix_strategy — settings flag नाही, फक्त cron ⇒
      scripts/install_engine_schedule.sh PAPER ओळी comment करतो (LIVE ओळ नाही).
  ✋ /paper (manual, Abhi स्वतः), pullback_credit_spread (फक्त preview पान), elliott / simple_core (execution नाही) ⇒ बदल नाही.
"""
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")                                  # index universe (बाकी bots सगळ्यांवर OFF)
ON_KEY = "15m_dynamic_sr"
VISION_BOT = "srv2_momentum_reversal"
ABSENT = "__ABSENT__"
AUTO_TRADERS = ("oi_signal_auto_trader.py", "credit_spread_auto_trader.py", "oi_greeks_vix_strategy.py")
ENGINE_CRON_TAG = "scripts/engine_signal_run.py"
LIVE_RE = re.compile(r"""--mode[=\s]+['"]?LIVE\b""")                          # --mode LIVE / --mode=LIVE / --mode "LIVE" / --mode='LIVE'
OFF_TAG = "#one-bot-off# "
# plan चे जे भाग `signal_symbols` वर अवलंबून आहेत (dashboard save वर हेच लागतात; बाकी bots — 5M / Classic / MCX / auto — ला हात नाही)
SIGNAL_SYMBOL_PARTS = (ON_KEY, "vision", "paper")


def mcx_symbols():
    try:
        from bots_common.level_visibility import MCX_SYMBOLS
        return tuple(MCX_SYMBOLS)
    except Exception:                                                    # noqa: BLE001
        return ("CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER")


def targets(signal=SYMBOLS):
    """(label, strategy, symbol, {key: value}) — लिहायचे settings (bot जे field तपासतो तेच). 15M SRv2: signal symbols ⇒ ON (engine, PAPER),
    बाकी index ⇒ OFF (`symbol_enabled` = false)."""
    out = [("15M SRv2", ON_KEY, s, {"symbol_enabled": True, "signal_source": "engine", "trading_mode": "PAPER"} if s in signal
            else {"symbol_enabled": False}) for s in SYMBOLS]
    out += [("5M Instant", "1m_instant", s, {"symbol_enabled": False}) for s in SYMBOLS]
    out += [("SR V3 PAPER shadow", "1m_instant", s, {"srv3_shadow_enabled": False}) for s in SYMBOLS]
    out += [("Classic SR reversal", "classic_sr_reversal", s, {"symbol_enabled": False}) for s in SYMBOLS]
    out += [("MCX futures", "mcx_futures", s, {"symbol_enabled": False}) for s in mcx_symbols()]
    out += [(f"Auto: {k}", k, s, {"symbol_enabled": False}) for k in AUTO_KEYS for s in SYMBOLS]
    return out


# ------------------------------------------------------------------------------------------------ IO (dashboard चीच storage)
class IO:
    """Strategy settings = cloud_db (Supabase strategy_settings; dashboard तेच वाचतं), Vision = vision.config (dashboard चं Vision पान),
    PAPER instruments = paper/config local override. Tests: हे methods बदलतात. `by` = Vision settings इतिहासात कोणी बदल केला."""

    def __init__(self, by="set_one_bot_mode"):
        self.by = by

    def raw(self, strategy, symbol):
        import cloud_db
        return cloud_db.get_strategy_settings_raw(strategy, symbol)

    def effective(self, strategy, symbol):
        import cloud_db
        return cloud_db.get_strategy_settings(strategy, symbol)

    def save(self, strategy, symbol, changes):
        import cloud_db
        if not cloud_db.save_strategy_settings(strategy, symbol, changes):
            raise RuntimeError(f"save अयशस्वी: {strategy} {symbol}")

    def remove(self, strategy, symbol, keys):
        import cloud_db
        if not cloud_db.remove_strategy_settings_keys(strategy, symbol, keys):
            raise RuntimeError(f"keys काढता आले नाहीत: {strategy} {symbol} {keys}")

    def vision_load(self, bot):
        from vision import config as VC
        return VC.load(bot)

    def vision_save(self, bot, changes):
        from vision import config as VC
        return VC.save(bot, changes, by=getattr(self, "by", "set_one_bot_mode"))

    def paper_local_path(self):
        from paper import config as PC
        return PC.local_path()

    def paper_cfg(self):
        from paper import config as PC
        return PC.load()

    def crontab(self):
        return read_crontab()

    def signal_symbols(self):
        import cloud_db
        return cloud_db.get_signal_symbols()


def signal_symbols(io):
    """io चे signal symbols (dashboard setting); जुनं IO (method नाही) / त्रुटी ⇒ default NIFTY / BANKNIFTY."""
    try:
        return [x.upper() for x in io.signal_symbols()]
    except Exception:                                                    # noqa: BLE001
        import cloud_db
        return list(cloud_db.SIGNAL_SYMBOLS_DEFAULT)


AUTO_KEYS = {"credit_spread_auto_trader": "credit_spread_auto_trader.py", "oi_signal_auto_trader": "oi_signal_auto_trader.py",
             "oi_greeks_vix_strategy": "oi_greeks_vix_strategy.py"}


def paper_entry_blocked(strategy, symbol, trading_mode, raw_fn=None):
    """Auto traders (settings flag नव्हता): **साठवलेला** `symbol_enabled` = false आणि PAPER ⇒ कारण (नवा entry नाही); नाहीतर None.
    Default (नोंद नाही) = आधीसारखं चालू. LIVE ⇒ कधीच अडवत नाही. Settings वाचता नाही ⇒ None (जुनं वर्तन; installer cron ओळ बंद करतो)."""
    if str(trading_mode or "").upper() != "PAPER":
        return None
    try:
        if raw_fn is None:
            import cloud_db
            raw_fn = cloud_db.get_strategy_settings_raw
        raw = raw_fn(strategy, symbol) or {}
    except Exception:                                                    # noqa: BLE001
        return None
    if raw.get("symbol_enabled") is False:
        return f"{symbol}: {strategy} PAPER entries off (symbol_enabled = false, one-bot mode) — open positions still managed"
    return None


def open_auto_sources(symbols=SYMBOLS, has_open=None):
    """कोणत्या auto traders च्या OPEN positions आहेत (installer: त्यांची cron ओळ exits साठी चालू ठेवतो)."""
    if has_open is None:
        from database import has_open_trade_from_source as has_open
    return sorted({src for src in AUTO_KEYS for sym in symbols if has_open(sym, src)})


def read_crontab():
    """crontab मजकूर (env CRONTAB_FILE ⇒ ती file; tests). वाचता आलं नाही ⇒ None."""
    p = os.environ.get("CRONTAB_FILE")
    try:
        if p:
            return open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        return r.stdout if r.returncode == 0 else ""
    except Exception:                                                    # noqa: BLE001
        return None


def _mode(eff):
    return str((eff or {}).get("trading_mode", "PAPER") or "PAPER").upper()


# ------------------------------------------------------------------------------------------------ plan / apply / revert
def plan(io, parts=None):
    """रिटर्न (changes, warnings). change = dict(label, strategy, symbol, key, before_raw, before, after, skip).
    `parts` (उदा. SIGNAL_SYMBOL_PARTS) ⇒ फक्त त्या strategies / "vision" / "paper" चे बदल; None ⇒ सगळं (script)."""
    changes, warns = [], []
    want = (lambda k: True) if parts is None else (lambda k: k in parts)
    ctext = io.crontab() if any(want(k) for k in AUTO_KEYS) else None
    sig = signal_symbols(io)
    for label, strat, sym, kv in targets(sig):
        if not want(strat):
            continue
        eff = io.effective(strat, sym)
        raw = io.raw(strat, sym)
        if strat in AUTO_KEYS and cron_runs(ctext, AUTO_KEYS[strat]).get(sym) == "LIVE":
            eff = {**eff, "trading_mode": "LIVE"}                        # auto trader चा mode = cron `--mode` (settings मध्ये नाही)
        live = _mode(eff) != "PAPER"
        if live:
            warns.append(f"⚠️ {label} {sym}: trading_mode {_mode(eff)} ⇒ हात लावला नाही (LIVE untouched) — फक्त नोंद")
        for k, v in kv.items():
            changes.append({"label": label, "strategy": strat, "symbol": sym, "key": k, "before_raw": raw.get(k, ABSENT),
                            "before": eff.get(k), "after": eff.get(k) if live else v, "skip": "LIVE" if live else None})
    if want("vision"):
        vs = io.vision_load(VISION_BOT)                                 # Vision srv2 symbols = signal symbols (बाकी index ⇒ approval मार्ग नाही)
        syms = list(dict.fromkeys([*(x.upper() for x in vs.get("symbols") or [] if x.upper() not in SYMBOLS), *sig]))
        for k, v in (("symbols", syms), ("approval_required", True)):
            changes.append({"label": "Vision (15M SRv2 approval)", "strategy": "vision", "symbol": VISION_BOT, "key": k,
                            "before_raw": vs.get(k), "before": vs.get(k), "after": v, "skip": None})
    if want("paper"):
        cfg = io.paper_cfg()
        for sym in sig:                                                  # PAPER instrument: फक्त signal symbols ON (बाकी तसेच)
            cur = bool(((cfg.get("instruments") or {}).get(sym) or {}).get("enabled", False))
            changes.append({"label": "PAPER instrument", "strategy": "paper", "symbol": sym, "key": "enabled", "before_raw": cur,
                            "before": cur, "after": True, "skip": None})
    return changes, warns


def _read(p):
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return None


def before_state(io, changes):
    st = {"kind": "one_bot_before", "strategy": [], "vision": {}, "paper_local": _read(io.paper_local_path())}
    for c in changes:
        if c["strategy"] in ("vision", "paper") or c["skip"]:
            continue
        st["strategy"].append({"strategy": c["strategy"], "symbol": c["symbol"], "key": c["key"], "raw": c["before_raw"]})
    st["vision"] = {c["key"]: c["before_raw"] for c in changes if c["strategy"] == "vision"}
    return st


def _steps(io, changes):
    """apply चे टप्पे, क्रमाने: [(नाव, fn)] — fn() ⇒ "written" / "skipped (LIVE)". रिटर्न (steps, strategy-combos संख्या).
    Vision / PAPER टप्पे फक्त changes मध्ये ते भाग असतील तर."""
    by = {}
    for c in changes:
        if c["strategy"] in ("vision", "paper") or c["skip"]:
            continue
        by.setdefault((c["strategy"], c["symbol"]), {})[c["key"]] = c["after"]
    steps = []
    for (strat, sym), kv in by.items():
        def _write(strat=strat, sym=sym, kv=kv):
            if _mode(io.effective(strat, sym)) != "PAPER":                # लिहिण्याआधी पुन्हा (race) — LIVE ⇒ नाही
                return "skipped (LIVE)"
            io.save(strat, sym, kv)
            return "written"
        steps.append((f"{strat} {sym}", _write))
    vis = {c["key"]: c["after"] for c in changes if c["strategy"] == "vision"}
    pap = {c["symbol"]: c["after"] for c in changes if c["strategy"] == "paper"}

    def _vision():
        io.vision_save(VISION_BOT, vis)
        return "written"

    def _paper():
        write_paper_local(io.paper_local_path(), pap)
        return "written"
    if any(c["strategy"] == "vision" for c in changes):
        steps.append(("Vision srv2 symbols", _vision))
    if any(c["strategy"] == "paper" for c in changes):
        steps.append(("PAPER instruments", _paper))
    return steps, len(by)


def apply(io, changes):
    """फक्त बदल (skip नसलेले) लिहितो. रिटर्न लिहिलेल्या (strategy, symbol) ची संख्या. त्रुटी ⇒ exception (script)."""
    steps, n = _steps(io, changes)
    for _name, fn in steps:
        fn()
    return n


def apply_reported(io, changes):
    """apply सारखंच, पण टप्पेवार निकाल: पहिल्या त्रुटीवर थांबतो (बाकी "not run") — अर्धवट स्थिती लपत नाही.
    रिटर्न dict(applied=[नाव], skipped_live=[नाव], failed=None | {part, error}, not_run=[नाव], ok)."""
    steps, _ = _steps(io, changes)
    out = {"applied": [], "skipped_live": [], "failed": None, "not_run": []}
    for i, (name, fn) in enumerate(steps):
        try:
            r = fn()
        except Exception as exc:                                         # noqa: BLE001
            out["failed"] = {"part": name, "error": f"{type(exc).__name__}: {exc}"}
            out["not_run"] = [n for n, _f in steps[i + 1:]]
            break
        (out["skipped_live"] if r == "skipped (LIVE)" else out["applied"]).append(name)
    out["ok"] = out["failed"] is None
    return out


def apply_signal_symbols(before=None, after=None, io=None, by="dashboard", now_fn=None, logger=None):
    """Abhi 9a (PF-3): dashboard वर `signal_symbols` सेव्ह झाल्यावर — `scripts/set_one_bot_mode.py` चा signal-symbols भाग
    (SIGNAL_SYMBOL_PARTS: 15M SRv2 per symbol on/off + engine + PAPER, Vision srv2 symbols / approval, PAPER instruments) लगेच लावतो.
    तेच plan / apply (LIVE / LIVE_PAPER combo ⇒ skip, लिहिण्याआधी पुन्हा तपास). बाकी bots ला हात नाही; before-state file लिहीत नाही
    (script चा revert तसाच) — त्याऐवजी log (before / after, कोण / कुठून, वेळ). कधीच raise करत नाही.
    रिटर्न dict: ok, at, by, signal_symbols {before, after}, changes [label symbol key before after skip], warnings, applied,
    skipped_live, failed, not_run."""
    if logger is None:
        from log_setup import get_logger
        logger = get_logger("one_bot")
    if now_fn is None:
        from config import get_ist_now as now_fn
    try:
        at = now_fn().isoformat(timespec="seconds")
    except Exception:                                                    # noqa: BLE001
        at = None
    res = {"ok": False, "at": at, "by": by, "signal_symbols": {"before": list(before or []), "after": list(after or [])},
           "changes": [], "warnings": [], "applied": [], "skipped_live": [], "failed": None, "not_run": []}
    try:
        io = io or IO(by=by)
        changes, warns = plan(io, parts=SIGNAL_SYMBOL_PARTS)
    except Exception as exc:                                             # noqa: BLE001
        res["failed"] = {"part": "plan (settings वाचन)", "error": f"{type(exc).__name__}: {exc}"}
        logger.error("signal_symbols apply FAILED by=%s before=%s after=%s: %s", by, res["signal_symbols"]["before"],
                     res["signal_symbols"]["after"], res["failed"])
        return res
    res["warnings"] = warns
    res["changes"] = [{k: c[k] for k in ("label", "symbol", "key", "before", "after", "skip")} for c in changes]
    res.update(apply_reported(io, changes))
    payload = json.dumps({k: res[k] for k in ("by", "signal_symbols", "changes", "applied", "skipped_live", "failed", "not_run")},
                         ensure_ascii=False, default=str)
    (logger.info if res["ok"] else logger.error)("signal_symbols apply %s at=%s %s", "OK" if res["ok"] else "FAILED", at, payload)
    return res


def write_paper_local(path, enabled):
    import yaml
    loc = {}
    try:
        loc = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except (OSError, ValueError):
        loc = {}
    ins = loc.get("instruments") or {}
    for sym, on in enabled.items():
        ins[sym] = {**(ins.get(sym) or {}), "enabled": bool(on)}
    loc["instruments"] = ins
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# VPS local — scripts/set_one_bot_mode.py (git मध्ये नाही). --revert ने आधीसारखं.\n")
        yaml.safe_dump(loc, f, allow_unicode=True, sort_keys=True)


def revert(io, st):
    """before-state ⇒ तंतोतंत आधीचं. LIVE झालेला combo ⇒ skip + इशारा. रिटर्न warnings."""
    warns, by_set, by_del = [], {}, {}
    for e in st.get("strategy") or []:
        k = (e["strategy"], e["symbol"])
        (by_del.setdefault(k, []).append(e["key"]) if e["raw"] == ABSENT else by_set.setdefault(k, {}).__setitem__(e["key"], e["raw"]))
    for k in sorted(set(by_set) | set(by_del)):
        if _mode(io.effective(*k)) != "PAPER":
            warns.append(f"⚠️ {k[0]} {k[1]}: आता {_mode(io.effective(*k))} ⇒ revert केला नाही (LIVE untouched)")
            continue
        if by_set.get(k):
            io.save(k[0], k[1], by_set[k])
        if by_del.get(k):
            io.remove(k[0], k[1], by_del[k])
    if st.get("vision"):
        io.vision_save(VISION_BOT, st["vision"])
    p = io.paper_local_path()
    if st.get("paper_local") is None:
        if os.path.exists(p):
            os.remove(p)
    else:
        with open(p, "w", encoding="utf-8") as f:
            f.write(st["paper_local"])
    return warns


# ------------------------------------------------------------------------------------------------ status (dashboard / pre-open)
def cron_state(text):
    """{script: "on" / "off" / "LIVE" / "absent" / "unknown"} — auto traders + engine schedule."""
    out = {}
    if text is None:
        return {s: "unknown" for s in (*AUTO_TRADERS, ENGINE_CRON_TAG, "srv2_momentum_reversal_strategy.py")}
    lines = text.splitlines()
    for s in (*AUTO_TRADERS, ENGINE_CRON_TAG, "srv2_momentum_reversal_strategy.py"):
        act = [x for x in lines if s in x and not x.lstrip().startswith("#")]
        live = [x for x in act if LIVE_RE.search(x)]
        out[s] = "LIVE" if live else ("on" if act else ("off" if any(s in x for x in lines) else "absent"))
    return out


SYM_RE = re.compile(r"""--symbol[=\s]+['"]?([A-Z]+)""")


def cron_runs(text, script):
    """{symbol: "LIVE" / "PAPER"} — त्या script च्या चालू (comment नसलेल्या) cron ओळी (`--symbol` नसेल ⇒ NIFTY, script चा default)."""
    out = {}
    for x in (text or "").splitlines():
        if script in x and not x.lstrip().startswith("#"):
            m = SYM_RE.search(x)
            sym = m.group(1) if m else "NIFTY"
            out[sym] = "LIVE" if LIVE_RE.search(x) or out.get(sym) == "LIVE" else "PAPER"
    return out


def one_bot_status(io=None, crontab_text=False):
    """प्रत्येक entry-capable bot × symbol चा प्रत्यक्ष on/off (bot जे field तपासतो तेच + PAPER instruments + Vision approval), auto
    traders चा cron, engine schedule. रिटर्न dict: bots (list), auto_traders, engine_cron, vision, ok (फक्त 15M SRv2 engine), line."""
    io = io or IO()
    rows = []
    sig = signal_symbols(io)
    try:
        cfg = io.paper_cfg()
    except Exception:                                                    # noqa: BLE001
        cfg = {}
    pin = {s: bool(((cfg.get("instruments") or {}).get(s) or {}).get("enabled", False)) for s in SYMBOLS}
    ctext = io.crontab() if crontab_text is False else crontab_text
    cron = cron_state(ctext)
    for label, strat, sym, kv in targets(sig):
        try:
            eff = io.effective(strat, sym)
        except Exception as exc:                                         # noqa: BLE001
            rows.append({"bot": label, "strategy": strat, "symbol": sym, "on": None, "why": f"settings वाचता आले नाहीत: {exc}"})
            continue
        flag = next(iter(kv))
        if label == "SR V3 PAPER shadow":
            on = bool(eff.get("srv3_shadow_enabled")) and bool(eff.get("symbol_enabled"))
        elif strat in AUTO_KEYS:                                         # cron वर चालतो (त्या symbol साठी) आणि PAPER entries बंद नाहीत
            run = cron_runs(ctext, AUTO_KEYS[strat]).get(sym) if ctext is not None else "unknown"
            if run == "LIVE":
                eff = {**eff, "trading_mode": "LIVE"}
            try:
                blocked = run == "PAPER" and (io.raw(strat, sym) or {}).get("symbol_enabled") is False
            except Exception:                                            # noqa: BLE001
                blocked = False
            on = run is not None and run != "unknown" and not blocked
        else:
            on = bool(eff.get("symbol_enabled"))
        if strat == ON_KEY and _mode(eff) == "PAPER":
            on = on and pin.get(sym, False)
        rows.append({"bot": label, "strategy": strat, "symbol": sym, "on": on, "flag": flag, "trading_mode": _mode(eff),
                     "signal_source": eff.get("signal_source"), "entry_mode": eff.get("entry_mode"),
                     "paper_instrument": pin.get(sym) if sym in SYMBOLS else None})
    try:
        vs = io.vision_load(VISION_BOT)
        vision = {"symbols": vs.get("symbols"), "approval_required": vs.get("approval_required"), "vision_mode": vs.get("vision_mode")}
    except Exception as exc:                                             # noqa: BLE001
        vision = {"error": str(exc)}
    for r in rows:
        r["signal_symbol"] = r["symbol"] in sig if r["symbol"] in SYMBOLS else None
    srv2 = [r for r in rows if r["strategy"] == ON_KEY and r["symbol"] in sig]
    others_on = [r for r in rows if (r["strategy"] != ON_KEY or r["symbol"] not in sig) and r.get("on") and r.get("trading_mode") == "PAPER"]
    live = [f"{r['bot']} {r['symbol']} {r['trading_mode']}" for r in rows if r.get("on") and r.get("trading_mode") not in ("PAPER", None)
            and (r["strategy"] != ON_KEY or r["symbol"] not in sig)]
    problems = []
    for r in srv2:
        if not r.get("on"):
            problems.append(f"15M SRv2 {r['symbol']} OFF")
        elif r.get("signal_source") != "engine":
            problems.append(f"15M SRv2 {r['symbol']} signal_source {r.get('signal_source')}")
        if r.get("trading_mode") != "PAPER":
            problems.append(f"15M SRv2 {r['symbol']} {r.get('trading_mode')}")
    if not vision.get("approval_required", False):
        problems.append("Vision approval_required OFF (shadow trades possible)")
    vsyms = [x.upper() for x in (vision.get("symbols") or [])]
    missing_v = [s for s in sig if s not in vsyms]
    if missing_v:
        problems.append(f"Vision symbols missing {'/'.join(missing_v)} (no approval request)")
    extra_v = [s for s in SYMBOLS if s in vsyms and s not in sig]
    if extra_v and "error" not in vision:
        problems.append(f"Vision symbols include {'/'.join(extra_v)} (not a signal symbol)")
    problems += [f"{r['bot']} {r['symbol']} ON" + ("" if r["strategy"] != ON_KEY else " (not a signal symbol)") for r in others_on]
    if cron.get(ENGINE_CRON_TAG) not in ("on", "unknown"):
        problems.append(f"engine schedule {cron.get(ENGINE_CRON_TAG)}")
    if cron.get("srv2_momentum_reversal_strategy.py") not in ("on", "unknown"):
        problems.append(f"15M SRv2 cron {cron.get('srv2_momentum_reversal_strategy.py')}")
    st = {"bots": rows, "signal_symbols": sig, "vision": vision, "auto_traders": {s: cron.get(s) for s in AUTO_TRADERS},
          "engine_cron": cron.get(ENGINE_CRON_TAG), "srv2_cron": cron.get("srv2_momentum_reversal_strategy.py"), "problems": problems, "live_untouched": live, "ok": not problems}
    st["line"] = preopen_line(st)
    return st


def preopen_line(st):
    live = f" · ⚠️ LIVE (untouched): {', '.join(st['live_untouched'])}" if st.get("live_untouched") else ""
    if st.get("ok"):
        syms = " / ".join(st.get("signal_symbols") or SYMBOLS)
        return f"Only 15M SRv2 active · signal source: engine · symbols {syms} · mode PAPER" + live
    return "❌ One-bot mode NOT clean: " + "; ".join(st.get("problems") or ["unknown"]) + live


def table(changes):
    w = [("bot", 22), ("symbol", 22), ("key", 18), ("before", 30), ("after", 30), ("note", 6)]
    out = ["  ".join(n.ljust(k) for n, k in w)]
    for c in changes:
        vals = [c["label"], c["symbol"], c["key"], json.dumps(c["before"], ensure_ascii=False, default=str),
                json.dumps(c["after"], ensure_ascii=False, default=str), c["skip"] or ("" if c["before"] == c["after"] else "change")]
        out.append("  ".join(str(v)[:k].ljust(k) for v, (_, k) in zip(vals, w)))
    return "\n".join(out)
