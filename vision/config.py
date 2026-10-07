"""vision/config.py — bot-निहाय Vision settings (defaults, validation, बदल-इतिहास) + env (model, key).

🎓 Modes: off / shadow / notify / auto_veto / human_confirm / veto_then_confirm. **V0 मध्ये फक्त off / shadow / notify लागू** — बाकीचे V1 मध्ये
(निवडले तर ValueError: "V1 मध्ये"). LIVE bot ⇒ नेहमी off (`effective_mode`) — LIVE ला हात नाही.
V0 defaults (WORK_LOG मध्ये कारण): NIFTY 5-Min Instant आणि 15M = notify (G-V0 साठी पहिल्या दिवसाचा Telegram हवा); बाकी सगळे off.
Pullback Credit Spread सध्या फक्त preview पान (PAPER bot म्हणून चालत नाही) ⇒ यादीत off.

Settings बदल: `python3 -m vision.config set <bot> <key> <value> --by <नाव>` (इतिहासासह); `python3 -m vision.config show`.
"""
import argparse
import copy
import json
import os
import sys

from . import store as VS

MODES = ("off", "shadow", "notify", "auto_veto", "human_confirm", "veto_then_confirm")
V0_MODES = ("off", "shadow", "notify")
LIVE_FORBIDDEN = ("auto_veto", "human_confirm", "veto_then_confirm")

BOTS = {
    # bot key            : (dashboard नाव, symbols, V0 default mode)
    "dynamic_sr_instant": ("NIFTY 5-Min Instant", ("NIFTY",), "notify"),
    "srv2_momentum_reversal": ("NIFTY 15M Dynamic SR", ("NIFTY",), "notify"),
    "pullback_credit_spread": ("Pullback Credit Spread", ("NIFTY",), "off"),
    "mcx_futures": ("MCX Futures", (), "off"),
    "elliott": ("Elliott (E6 नंतर)", ("NIFTY",), "off"),
}

BOT_DEFAULTS = {
    "vision_mode": "off",
    "symbols": ["NIFTY"],
    "vision_gray_action": "half",          # half / skip / ignore           (V1)
    "vision_disagree_action": "skip",      # skip / half / ignore           (V1)
    "vision_fail_action": "ignore",        # ignore / skip — ignore = algorithm चा निर्णय
    "timeout_action": "auto_veto",         # auto_veto / skip               (V1: veto_then_confirm मध्ये उत्तर न आल्यास)
    "approve_window_min": 10,
    "max_drift_mr": 0.5,
    "exit_advice": False,
    "vision_timeout_sec": 20,
    "second_audit_below_conf": 0.6,        # पहिल्या audit ची confidence याखाली ⇒ दुसरा audit
    "reuse_window_min": 15,                # तोच level/setup 15 मिनिटांत ⇒ आधीचं मत पुन्हा
    "level_gate": "off",                   # off / skip_mid_range           (V2)
}
GLOBAL_DEFAULTS = {
    "vision_daily_budget_usd": 0.30,
    "vision_monthly_budget_usd": 5.0,
    "morning_audit_time": "08:00",
}
ENUMS = {
    "vision_mode": MODES, "vision_gray_action": ("half", "skip", "ignore"), "vision_disagree_action": ("skip", "half", "ignore"),
    "vision_fail_action": ("ignore", "skip"), "timeout_action": ("auto_veto", "skip"), "level_gate": ("off", "skip_mid_range"),
}
RANGES = {"approve_window_min": (1, 60), "max_drift_mr": (0.05, 5.0), "vision_timeout_sec": (5, 120), "second_audit_below_conf": (0.0, 1.0),
          "reuse_window_min": (0, 120), "vision_daily_budget_usd": (0.0, 5.0), "vision_monthly_budget_usd": (0.0, 50.0)}


def defaults(bot):
    d = copy.deepcopy(BOT_DEFAULTS)
    if bot in BOTS:
        d["vision_mode"] = BOTS[bot][2]
        d["symbols"] = list(BOTS[bot][1])
    return d


def validate(bot, s, allow_future_modes=False):
    """रिटर्न स्वच्छ dict; चुकीचं ⇒ ValueError (कारणासह)."""
    out = defaults(bot) if bot != "_global" else copy.deepcopy(GLOBAL_DEFAULTS)
    for k, v in (s or {}).items():
        if k not in out:
            raise ValueError(f"अज्ञात setting: {k}")
        if k in ENUMS and v not in ENUMS[k]:
            raise ValueError(f"{k} = {v!r} — {ENUMS[k]} पैकी हवं")
        if k in RANGES:
            lo, hi = RANGES[k]
            v = float(v) if isinstance(out[k], float) else int(v)
            if not lo <= v <= hi:
                raise ValueError(f"{k} = {v} — [{lo}, {hi}] मध्ये हवं")
        if k == "exit_advice":
            v = bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes", "on")
        if k == "symbols":
            v = [x.strip().upper() for x in (v.split(",") if isinstance(v, str) else v) if x.strip()]
        out[k] = v
    if bot != "_global" and not allow_future_modes and out["vision_mode"] not in V0_MODES:
        raise ValueError(f"vision_mode {out['vision_mode']} V1 मध्ये येईल — V0 मध्ये फक्त {V0_MODES}")
    return out


def effective_mode(settings, trading_mode):
    """LIVE (किंवा अज्ञात) ⇒ off. PAPER ⇒ settings चा mode (V0 मध्ये फक्त off/shadow/notify)."""
    if str(trading_mode or "").upper() != "PAPER":
        return "off"
    m = settings.get("vision_mode", "off")
    return m if m in V0_MODES else "off"


def load(bot, path=None, timeout=10):
    with VS.connect(path, timeout) as c:
        r = c.execute("SELECT json FROM vision_settings WHERE bot=?", (bot,)).fetchone()
    stored = json.loads(r[0]) if r else {}
    try:
        return validate(bot, stored)
    except ValueError:
        return defaults(bot) if bot != "_global" else copy.deepcopy(GLOBAL_DEFAULTS)


def save(bot, changes, by, path=None):
    """changes merge + validate + इतिहास. रिटर्न नवीन settings."""
    if bot != "_global" and bot not in BOTS:
        raise ValueError(f"अज्ञात bot: {bot} — {sorted(BOTS)}")
    old = load(bot, path)
    new = validate(bot, {**old, **changes})
    stored = {k: v for k, v in new.items()}
    with VS.connect(path) as c:
        ts = VS._iso(VS.now_ist())
        c.execute("INSERT INTO vision_settings (bot, json, updated_at, updated_by) VALUES (?,?,?,?) ON CONFLICT(bot) DO UPDATE SET "
                  "json=excluded.json, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                  (bot, json.dumps(stored, ensure_ascii=False), ts, by))
        c.execute("INSERT INTO vision_settings_history VALUES (?,?,?,?,?)", (ts, bot, by, json.dumps(old, ensure_ascii=False),
                                                                            json.dumps(stored, ensure_ascii=False)))
    return new


def history(bot=None, path=None):
    with VS.connect(path) as c:
        q = "SELECT * FROM vision_settings_history" + (" WHERE bot=?" if bot else "") + " ORDER BY ts"
        return [dict(r) for r in c.execute(q, (bot,) if bot else ())]


# --------------------------------------------------------------------------------------------------------- env
def env_model(task):
    """task = signal | level. Model नाव फक्त env मधून (कोडमध्ये नाही): VISION_SIGNAL_MODEL / VISION_LEVEL_MODEL."""
    return (os.environ.get(f"VISION_{task.upper()}_MODEL") or "").strip() or None


def env_effort(task):
    return (os.environ.get(f"VISION_{task.upper()}_EFFORT") or "").strip() or None


def env_thinking(task):
    """ऐच्छिक thinking type (उदा. model ला thinking बंद करायचं असेल तर त्या model चा प्रकार) — रिकामा ⇒ field पाठवत नाही."""
    return (os.environ.get(f"VISION_{task.upper()}_THINKING") or "").strip() or None


def api_key_present():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def main(argv=None):
    p = argparse.ArgumentParser(description="Vision settings (बदल-इतिहासासह)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    st = sub.add_parser("set")
    st.add_argument("bot")
    st.add_argument("key")
    st.add_argument("value")
    st.add_argument("--by", default=os.environ.get("USER", "cli"))
    sub.add_parser("history")
    a = p.parse_args(argv)
    if a.cmd == "show":
        for b in ["_global", *BOTS]:
            print(b, json.dumps(load(b), ensure_ascii=False))
    elif a.cmd == "set":
        v = a.value
        try:
            v = json.loads(v)
        except ValueError:
            pass
        print(json.dumps(save(a.bot, {a.key: v}, a.by), ensure_ascii=False))
    else:
        for h in history():
            print(h["ts"], h["bot"], h["by"], h["new_json"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
