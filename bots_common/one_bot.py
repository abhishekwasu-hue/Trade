"""bots_common/one_bot.py — Abhi (one bot): फक्त 15M SRv2 (`15m_dynamic_sr`) ON, signal_source = engine (decision3), NIFTY / BANKNIFTY /
SENSEX, PAPER. बाकी प्रत्येक entry-capable bot OFF — तेच field जे bot स्वतः तपासतो (`symbol_enabled` …); काहीही delete नाही; strikes /
ITM depth / hedge / lots / SL / TSL / target / exits ला हात नाही; LIVE / LIVE_PAPER combo ला हात नाही (फक्त इशारा).

  plan(io)          ⇒ बदलांची यादी (before / after), LIVE combos skip.
  apply(io, ...)    ⇒ before-state JSON (revert साठी) + लिहिणं.  revert(io, before) ⇒ तंतोतंत आधीचं (आधी नसलेले keys काढले).
  one_bot_status()  ⇒ प्रत्येक entry-capable bot चा प्रत्यक्ष (effective) on/off + engine schedule ⇒ pre-open ओळ (`preopen_line`).

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
SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
ON_KEY = "15m_dynamic_sr"
VISION_BOT = "srv2_momentum_reversal"
ABSENT = "__ABSENT__"
AUTO_TRADERS = ("oi_signal_auto_trader.py", "credit_spread_auto_trader.py", "oi_greeks_vix_strategy.py")
ENGINE_CRON_TAG = "scripts/engine_signal_run.py"
OFF_TAG = "#one-bot-off# "


def mcx_symbols():
    try:
        from bots_common.level_visibility import MCX_SYMBOLS
        return tuple(MCX_SYMBOLS)
    except Exception:                                                    # noqa: BLE001
        return ("CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER")


def targets():
    """(label, strategy, symbol, {key: value}) — लिहायचे settings (bot जे field तपासतो तेच)."""
    out = [("15M SRv2", ON_KEY, s, {"symbol_enabled": True, "signal_source": "engine", "trading_mode": "PAPER"}) for s in SYMBOLS]
    out += [("5M Instant", "1m_instant", s, {"symbol_enabled": False}) for s in SYMBOLS]
    out += [("SR V3 PAPER shadow", "1m_instant", s, {"srv3_shadow_enabled": False}) for s in SYMBOLS]
    out += [("Classic SR reversal", "classic_sr_reversal", s, {"symbol_enabled": False}) for s in SYMBOLS]
    out += [("MCX futures", "mcx_futures", s, {"symbol_enabled": False}) for s in mcx_symbols()]
    return out


# ------------------------------------------------------------------------------------------------ IO (dashboard चीच storage)
class IO:
    """Strategy settings = cloud_db (Supabase strategy_settings; dashboard तेच वाचतं), Vision = vision.config (dashboard चं Vision पान),
    PAPER instruments = paper/config local override. Tests: हे methods बदलतात."""

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
        return VC.save(bot, changes, by="set_one_bot_mode")

    def paper_local_path(self):
        from paper import config as PC
        return PC.local_path()

    def paper_cfg(self):
        from paper import config as PC
        return PC.load()

    def crontab(self):
        return read_crontab()


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
def plan(io):
    """रिटर्न (changes, warnings). change = dict(label, strategy, symbol, key, before_raw, before, after, skip)."""
    changes, warns = [], []
    for label, strat, sym, kv in targets():
        eff = io.effective(strat, sym)
        raw = io.raw(strat, sym)
        live = _mode(eff) != "PAPER"
        if live:
            warns.append(f"⚠️ {label} {sym}: trading_mode {_mode(eff)} ⇒ हात लावला नाही (LIVE untouched) — फक्त नोंद")
        for k, v in kv.items():
            changes.append({"label": label, "strategy": strat, "symbol": sym, "key": k, "before_raw": raw.get(k, ABSENT),
                            "before": eff.get(k), "after": eff.get(k) if live else v, "skip": "LIVE" if live else None})
    vs = io.vision_load(VISION_BOT)
    syms = list(dict.fromkeys([*(x.upper() for x in vs.get("symbols") or []), *SYMBOLS]))
    for k, v in (("symbols", syms), ("approval_required", True)):
        changes.append({"label": "Vision (15M SRv2 approval)", "strategy": "vision", "symbol": VISION_BOT, "key": k, "before_raw": vs.get(k),
                        "before": vs.get(k), "after": v, "skip": None})
    cfg = io.paper_cfg()
    for sym in SYMBOLS:
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


def apply(io, changes):
    """फक्त बदल (skip नसलेले) लिहितो. रिटर्न लिहिलेल्या (strategy, symbol) ची संख्या."""
    by = {}
    for c in changes:
        if c["strategy"] in ("vision", "paper") or c["skip"]:
            continue
        by.setdefault((c["strategy"], c["symbol"]), {})[c["key"]] = c["after"]
    for (strat, sym), kv in by.items():
        if _mode(io.effective(strat, sym)) != "PAPER":                    # लिहिण्याआधी पुन्हा (race) — LIVE ⇒ नाही
            continue
        io.save(strat, sym, kv)
    io.vision_save(VISION_BOT, {c["key"]: c["after"] for c in changes if c["strategy"] == "vision"})
    write_paper_local(io.paper_local_path(), {c["symbol"]: c["after"] for c in changes if c["strategy"] == "paper"})
    return len(by)


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
        live = [x for x in act if re.search(r"--mode\s+LIVE", x)]
        out[s] = "LIVE" if live else ("on" if act else ("off" if any(s in x for x in lines) else "absent"))
    return out


def one_bot_status(io=None, crontab_text=False):
    """प्रत्येक entry-capable bot × symbol चा प्रत्यक्ष on/off (bot जे field तपासतो तेच + PAPER instruments + Vision approval), auto
    traders चा cron, engine schedule. रिटर्न dict: bots (list), auto_traders, engine_cron, vision, ok (फक्त 15M SRv2 engine), line."""
    io = io or IO()
    rows = []
    try:
        cfg = io.paper_cfg()
    except Exception:                                                    # noqa: BLE001
        cfg = {}
    pin = {s: bool(((cfg.get("instruments") or {}).get(s) or {}).get("enabled", False)) for s in SYMBOLS}
    for label, strat, sym, kv in targets():
        try:
            eff = io.effective(strat, sym)
        except Exception as exc:                                         # noqa: BLE001
            rows.append({"bot": label, "strategy": strat, "symbol": sym, "on": None, "why": f"settings वाचता आले नाहीत: {exc}"})
            continue
        flag = next(iter(kv))
        if label == "SR V3 PAPER shadow":
            on = bool(eff.get("srv3_shadow_enabled")) and bool(eff.get("symbol_enabled"))
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
    cron = cron_state(io.crontab() if crontab_text is False else crontab_text)
    srv2 = [r for r in rows if r["strategy"] == ON_KEY]
    others_on = [r for r in rows if r["strategy"] != ON_KEY and r.get("on") and r.get("trading_mode") == "PAPER"]
    live = [f"{r['bot']} {r['symbol']} {r['trading_mode']}" for r in rows if r.get("on") and r.get("trading_mode") not in ("PAPER", None)
            and r["strategy"] != ON_KEY]
    auto_on = [s for s in AUTO_TRADERS if cron.get(s) in ("on", "LIVE")]
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
    missing_v = [s for s in SYMBOLS if s not in [x.upper() for x in (vision.get("symbols") or [])]]
    if missing_v:
        problems.append(f"Vision symbols missing {'/'.join(missing_v)} (no approval request)")
    problems += [f"{r['bot']} {r['symbol']} ON" for r in others_on]
    problems += [f"{s} cron {cron[s]}" for s in auto_on]
    if cron.get(ENGINE_CRON_TAG) not in ("on", "unknown"):
        problems.append(f"engine schedule {cron.get(ENGINE_CRON_TAG)}")
    if cron.get("srv2_momentum_reversal_strategy.py") not in ("on", "unknown"):
        problems.append(f"15M SRv2 cron {cron.get('srv2_momentum_reversal_strategy.py')}")
    st = {"bots": rows, "vision": vision, "auto_traders": {s: cron.get(s) for s in AUTO_TRADERS}, "engine_cron": cron.get(ENGINE_CRON_TAG),
          "srv2_cron": cron.get("srv2_momentum_reversal_strategy.py"), "problems": problems, "live_untouched": live, "ok": not problems}
    st["line"] = preopen_line(st)
    return st


def preopen_line(st):
    live = f" · ⚠️ LIVE (untouched): {', '.join(st['live_untouched'])}" if st.get("live_untouched") else ""
    if st.get("ok"):
        return "Only 15M SRv2 active · signal source: engine · symbols NIFTY / BANKNIFTY / SENSEX · mode PAPER" + live
    return "❌ One-bot mode NOT clean: " + "; ".join(st.get("problems") or ["unknown"]) + live


def table(changes):
    w = [("bot", 22), ("symbol", 22), ("key", 18), ("before", 30), ("after", 30), ("note", 6)]
    out = ["  ".join(n.ljust(k) for n, k in w)]
    for c in changes:
        vals = [c["label"], c["symbol"], c["key"], json.dumps(c["before"], ensure_ascii=False, default=str),
                json.dumps(c["after"], ensure_ascii=False, default=str), c["skip"] or ("" if c["before"] == c["after"] else "change")]
        out.append("  ".join(str(v)[:k].ljust(k) for v, (_, k) in zip(vals, w)))
    return "\n".join(out)
