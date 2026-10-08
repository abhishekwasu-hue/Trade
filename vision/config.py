"""vision/config.py — bot-निहाय Vision settings (defaults, validation, बदल-इतिहास) + env (model, key).

🎓 Modes: off / shadow / notify (V0 — trading वर परिणाम नाही) आणि auto_veto / human_confirm / veto_then_confirm (V1 — reduce-only gate:
skip किंवा अर्धा size, कधीच वाढ नाही). LIVE bot ⇒ नेहमी off (`effective_mode`), आणि V1 modes LIVE bot साठी save करता येत नाहीत
(`save` मध्ये bot चा trading_mode तपासतो) — LIVE ला हात नाही. V1 default अजून notify — dry-run (G-V1) नंतर तुम्ही निवडलेल्या bots वर.
V0 defaults (WORK_LOG मध्ये कारण): NIFTY 5-Min Instant आणि 15M = notify (G-V0 साठी पहिल्या दिवसाचा Telegram हवा); बाकी सगळे off.
Pullback Credit Spread सध्या फक्त preview पान (PAPER bot म्हणून चालत नाही) ⇒ यादीत off.

Settings बदल: `python3 -m vision.config set <bot> <key> <value> --by <नाव>` (इतिहासासह); `python3 -m vision.config show`.
"""
import argparse
import datetime as dt
import copy
import json
import os
import sys

from . import store as VS

MODES = ("off", "shadow", "notify", "auto_veto", "human_confirm", "veto_then_confirm")
V0_MODES = ("off", "shadow", "notify")
V1_MODES = ("auto_veto", "human_confirm", "veto_then_confirm")
LIVE_FORBIDDEN = V1_MODES
BOT_STRATEGY_KEY = {"dynamic_sr_instant": "1m_instant", "srv2_momentum_reversal": "15m_dynamic_sr"}   # cloud_db strategy settings

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
    "shadow_cooldown_min": 30,             # (V1) नाकारलेल्या level वर इतक्या मिनिटांत पुन्हा विचारणा / shadow नाही (bot च्या 30-मिनिट cooldown सारखं)
    "exec_window_min": 5,                  # (V1) approve / reject नंतर इतक्या मिनिटांत bot ने entry / shadow घ्यावा, नाहीतर EXPIRED
    "level_gate": "off",                   # off / skip_mid_range           (V2)
    # signal_check_v2 चे verdict नियम (code मध्ये; vision चं मत यांपेक्षा positive कधीच नाही) — चालू नियमांची यादी, dashboard वरून on/off
    "v2_disagree_rules": ["breakout", "reversal_invalid", "weak_level", "bad_wave", "bad_close", "opening", "gap_disallowed", "gap_chase",
                          "gap_b_pdc_accept", "wrong_approach", "role_conflict"],
    "v2_gray_rules": ["unclear", "correction_incomplete", "tight_room", "middle_close", "impulse_running", "gap_undecided_early",
                      "line_conflict", "event_day", "gap_c_alone"],
    # v2.1 chart / gap संदर्भ
    "vision_wait_for_bar_close": True,     # (v2.1) signal चा setup bar बंद झाल्यावरच vision call (Instant bot चा signal bar च्या मधे येतो)
    "line_lookback_sessions": 5,           # line panel: किती sessions चे 15m closes
    "inv_buffer_mr": 0.5,                  # bot ने invalidation न दिल्यास L ∓ हे × median range (chart / text)
    "gap_g0_atr": 0.25,                    # |gap_atr| याखाली ⇒ G0 (noise). IS 2015–2021 p50 = 0.247
    "gap_large_atr": 0.63,                 # G5 साठी "मोठा" gap. IS p90 = 0.628
    "gap_stretch_atr": 3.0,                # G5: आधीचा 5-session leg ≥ हे × ATR
    "gap_max_age_sessions": 10,            # जुने unfilled gaps किती sessions पर्यंत
}
RULE_IDS = {"v2_disagree_rules": ("breakout", "reversal_invalid", "weak_level", "bad_wave", "bad_close", "opening", "gap_disallowed",
                                  "gap_chase", "gap_b_pdc_accept", "wrong_approach", "role_conflict"),
            "v2_gray_rules": ("unclear", "correction_incomplete", "tight_room", "middle_close", "impulse_running", "gap_undecided_early",
                              "line_conflict", "event_day", "gap_c_alone")}
CTX_KEYS = ("line_lookback_sessions", "inv_buffer_mr", "gap_g0_atr", "gap_large_atr", "gap_stretch_atr", "gap_max_age_sessions")
GLOBAL_DEFAULTS = {
    "vision_daily_budget_usd": 0.30,
    "vision_monthly_budget_usd": 5.0,
    "morning_audit_time": "08:00",
    "event_days": [],                      # ["YYYY-MM-DD:नाव", …] — event दिवस (policy / budget / मोठा data), dashboard वरून
    "visual_audit_symbols": ["NIFTY"],     # EOD visual audit (run_visual_audit.py) — Abhi 2026-10-08: फक्त NIFTY (खर्च कमी); खर्च याच budget मध्ये
    "visual_audit_daily_cap": 0.10,        # visual audit ची दैनिक उप-मर्यादा ($) — signals ला प्राधान्य (Abhi 2026-10-08)
    "signals_daily_reserve_usd": 0.20,     # signals साठी राखीव ($/दिवस): audit कधीच (दैनिक budget − हे) पलीकडे जात नाही
}
VISUAL_AUDIT_SYMBOLS = ("NIFTY", "BANKNIFTY")
ENUMS = {
    "vision_mode": MODES, "vision_gray_action": ("half", "skip", "ignore"), "vision_disagree_action": ("skip", "half", "ignore"),
    "vision_fail_action": ("ignore", "skip"), "timeout_action": ("auto_veto", "skip"), "level_gate": ("off", "skip_mid_range"),
}
RANGES = {"approve_window_min": (1, 60), "max_drift_mr": (0.05, 5.0), "vision_timeout_sec": (5, 120), "second_audit_below_conf": (0.0, 1.0),
          "reuse_window_min": (0, 120), "exec_window_min": (1, 30), "shadow_cooldown_min": (0, 240),
          "line_lookback_sessions": (2, 15), "inv_buffer_mr": (0.1, 3.0), "gap_g0_atr": (0.0, 3.0), "gap_large_atr": (0.1, 5.0), "gap_stretch_atr": (0.5, 20.0),
          "gap_max_age_sessions": (0, 30), "vision_daily_budget_usd": (0.0, 5.0), "vision_monthly_budget_usd": (0.0, 50.0),
          "visual_audit_daily_cap": (0.0, 2.0), "signals_daily_reserve_usd": (0.0, 5.0)}


def defaults(bot):
    d = copy.deepcopy(BOT_DEFAULTS)
    if bot in BOTS:
        d["vision_mode"] = BOTS[bot][2]
        d["symbols"] = list(BOTS[bot][1])
    return d


def validate(bot, s):
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
        if k in ("exit_advice", "vision_wait_for_bar_close"):
            v = bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes", "on")
        if k == "visual_audit_symbols":
            v = [x.strip().upper() for x in (v.split(",") if isinstance(v, str) else v) if str(x).strip()]
            bad = [x for x in v if x not in VISUAL_AUDIT_SYMBOLS]
            if bad:
                raise ValueError(f"visual_audit_symbols: {bad} — {VISUAL_AUDIT_SYMBOLS} पैकी")
        if k == "symbols":
            v = [x.strip().upper() for x in (v.split(",") if isinstance(v, str) else v) if x.strip()]
        if k == "event_days":
            v = [str(x).strip() for x in (v.split(";") if isinstance(v, str) else v) if str(x).strip()]
            for x in v:
                try:
                    dt.date.fromisoformat(x.split(":", 1)[0])
                except ValueError:
                    raise ValueError(f"event_days: {x!r} — 'YYYY-MM-DD:नाव' हवं")
        if k in RULE_IDS:
            v = [x.strip() for x in (v.split(",") if isinstance(v, str) else v) if str(x).strip()]
            bad = [x for x in v if x not in RULE_IDS[k]]
            if bad:
                raise ValueError(f"{k}: अज्ञात नियम {bad} — {RULE_IDS[k]} पैकी")
        out[k] = v
    return out


def effective_mode(settings, trading_mode):
    """LIVE (किंवा अज्ञात) ⇒ off. PAPER ⇒ settings चा mode (V0 मध्ये फक्त off/shadow/notify)."""
    if str(trading_mode or "").upper() != "PAPER":
        return "off"
    m = settings.get("vision_mode", "off")
    return m if m in MODES else "off"


def bot_trading_mode(bot, symbol="NIFTY"):
    """Bot चा trading_mode (cloud_db strategy settings). वाचता आला नाही / अज्ञात bot ⇒ "UNKNOWN" (V1 modes नाकारायला)."""
    key = BOT_STRATEGY_KEY.get(bot)
    if not key:
        return "UNKNOWN"
    try:
        import cloud_db
        return str(cloud_db.get_strategy_settings(key, symbol).get("trading_mode", "PAPER")).upper()
    except Exception:
        return "UNKNOWN"


def load(bot, path=None, timeout=10):
    with VS.connect(path, timeout) as c:
        r = c.execute("SELECT json FROM vision_settings WHERE bot=?", (bot,)).fetchone()
    stored = json.loads(r[0]) if r else {}
    try:
        return validate(bot, stored)
    except Exception:                                                    # हाताने बिघडलेली row ⇒ defaults (gate चूक ⇒ पूर्ण size नको)
        return defaults(bot) if bot != "_global" else copy.deepcopy(GLOBAL_DEFAULTS)


def save(bot, changes, by, path=None, trading_mode_fn=None):
    """changes merge + validate + इतिहास. रिटर्न नवीन settings."""
    if bot != "_global" and bot not in BOTS:
        raise ValueError(f"अज्ञात bot: {bot} — {sorted(BOTS)}")
    old = load(bot, path)
    new = validate(bot, {**old, **changes})
    if bot != "_global" and new["vision_mode"] in LIVE_FORBIDDEN and new["vision_mode"] != old["vision_mode"]:
        modes = {sym: (trading_mode_fn or bot_trading_mode)(bot, sym) for sym in new["symbols"] or ["NIFTY"]}
        bad = {k: v for k, v in modes.items() if v != "PAPER"}
        if bad:
            raise ValueError(f"{new['vision_mode']} फक्त PAPER bot वर — {bot}: {bad} (LIVE ला हात नाही)")
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


def ctx_settings(bot, path=None):
    """Chart / gap संदर्भासाठी settings (+ event दिवस {YYYY-MM-DD: नाव})."""
    s, g = load(bot, path), load("_global", path)
    ev = {}
    for x in g.get("event_days") or []:
        d, _, name = str(x).partition(":")
        ev[d.strip()] = name.strip() or "event"
    return {**{k: s[k] for k in CTX_KEYS}, "events": ev}


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

