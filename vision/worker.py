"""vision/worker.py — QUEUED signals → chart render → vision audit → नोंद → (notify mode) Telegram. V0: trading वर परिणाम नाही.

    python3 -m vision.worker --loop-seconds 55        # cron दर मिनिटाला (ProcessLock — एका वेळी एकच worker)
    python3 -m vision.worker --usage [YYYY-MM-DD]     # त्या दिवसाचा token / $ वापर (G-COST मोजमाप)

🎓 क्रम (प्रत्येक signal):
  1. 15 मिनिटांपेक्षा जुना QUEUED/RUNNING ⇒ EXPIRED (restart / उशीर — जुनं मत उपयोगाचं नाही).
  2. तोच symbol/दिशा/TF/level `reuse_window_min` (15) मिनिटांत आधी तपासलेला ⇒ तेच मत (API call नाही, खर्च 0).
  3. 1m candles (Upstox) → signal पर्यंत कापून 2-panel chart (`vision/chart.py`).
  4. Budget: आजचा / महिन्याचा खर्च + या audit चा अंदाज > मर्यादा ⇒ vision नाही (verdict unavailable, `vision_fail_action`), Telegram इशारा दिवसातून एकदा.
  5. Model / API key नाही ⇒ unavailable (खर्च नाही).
  6. Audit (1, गरज असल्यास 2) → `vision_signals` row DONE (verdict, JSON, latency, cost) + `vision_usage`.
  7. mode = notify ⇒ Telegram वर chart + मत (बटणं नाहीत). shadow ⇒ फक्त नोंद.
"""
import argparse
import html
import re
import sys
import time

import pandas as pd

from . import chart as CH
from . import config as VC
from . import decide as VD
from . import images as IM
from . import signal_audit as SA
from . import store as VS

STALE_MIN = 15
VERDICT_MR = {"agree": ("✅", "सहमत"), "gray": ("🟡", "संदिग्ध"), "disagree": ("❌", "असहमत"), "unavailable": ("⚪", "उपलब्ध नाही")}
DIR_MR = {"BULLISH": "Bullish", "BEARISH": "Bearish"}


def setup_kind(row):
    t = row.get("tags") or {}
    if t.get("breakout_entry"):
        return "Breakout entry"
    if t.get("directional"):
        return "Directional (IV breakout)"
    return "Reversal (touch)"


def default_fetch(symbol, need_daily=False):
    """(1m frame, daily frame|None) — Upstox. Token Supabase / .env मधून (कधीच print नाही)."""
    import cloud_db
    from upstox_api import fetch_candles
    token = cloud_db.get_effective_upstox_token(None)
    if not token:
        raise RuntimeError("Upstox token नाही")
    m1 = fetch_candles(token, symbol, 0, interval="1minute", lookback_days=21)          # v2: major levels (~3 आठवडे) + PWH / PWL
    d1 = fetch_candles(token, symbol, 0, interval="day", lookback_days=120) if need_daily else None
    return m1, d1


def fetch_expiries(symbol):
    """Weekly expiry dates (contract master) — v2 signal text साठी. अपयश ⇒ [] (कधीच raise नाही)."""
    try:
        import cloud_db
        from upstox_api import fetch_option_expiries
        token = cloud_db.get_effective_upstox_token(None)
        return list(fetch_option_expiries(token, symbol) or []) if token else []
    except Exception:
        return []


YES = {"yes": "✓", "no": "✗", "good": "✓", "middle": "~", "bad": "✗"}


def v2_lines(a, hits=None):
    """signal_check_v2 audit ⇒ caption च्या ओळी (trend, level, wave, reversal 4 टप्पे, room, false-break risk, नियम)."""
    s = [f"Trend: HTF {a.get('htf_trend')} · setup {a.get('setup_structure')} ({a.get('trend_context')})",
         f"Level: {a.get('level_kind')} · real {a.get('level_real')} · confluence {a.get('confluence')}",
         f"Wave: {a.get('wave_position')} · correction पूर्ण {a.get('correction_complete')}"
         + (f" · {html.escape(a['elliott_note'])}" if a.get("elliott_note") else ""),
         "Reversal: " + " ".join(f"{k} {YES.get(a.get('reversal_' + k), '?')}" for k in ("touch", "reclaim", "strength"))
         + f" close {YES.get(a.get('reversal_close_location'), '?')} ⇒ {a.get('reversal_valid')}"
         + (" · false-break reclaim ✓" if a.get("false_break_reclaim") == "yes" else ""),
         f"Room {a.get('room_to_next_level')} · false-break risk {a.get('false_break_risk')} · time {a.get('time_risk')}"
         + (" · <b>BREAKOUT</b>" if a.get("is_breakout_entry") == "yes" else "")]
    if a.get("gap_behaviour"):                                          # v2.1
        s.append(f"Gap: {a.get('gap_behaviour')} · setup {a.get('gap_setup')} · वर्ग पटतो {a.get('gap_class_agrees')} · line {a.get('line_structure')} "
                 f"({a.get('line_vs_candles')})")
    if a.get("code_overrides"):
        s.append("Code तथ्यं: " + html.escape("; ".join(a["code_overrides"])))
    if hits and (hits.get("disagree") or hits.get("gray")):
        s.append("नियम: " + ", ".join([f"❌ {x}" for x in hits.get("disagree") or []] + [f"🟡 {x}" for x in hits.get("gray") or []]))
    return s


def caption(row, res, mode, reused=False):
    e, mr = VERDICT_MR.get(res.get("verdict") or "unavailable", ("⚪", res.get("verdict")))
    ts = pd.Timestamp(row["signal_ts"])
    s = [f"👁 <b>Vision V0 — फक्त माहिती</b> · {html.escape(str(row.get('bot_label') or row['bot']))}",
         f"{row['symbol']} · {DIR_MR.get(str(row.get('direction')).upper(), row.get('direction'))} · {setup_kind(row)}",
         f"Level {float(row['level']):,.0f} ({row.get('role')}, {row.get('setup_tf')}) · signal {ts:%H:%M}" if row.get("level") is not None
         else f"signal {ts:%H:%M}",
         f"मत: {e} <b>{mr}</b>" + (f" (confidence {res['confidence']:.2f})" if res.get("confidence") is not None else "")
         + (" · 15 मिनिटांतलं आधीचं मत" if reused else "")]
    a = (res.get("audits") or [None])[0]
    if a:
        if a.get("reason"):
            s.append("<b>कारण:</b> " + html.escape(a["reason"]))
        if "level_kind" in a:                                           # signal_check_v2
            s += v2_lines(a, (res.get("rule_hits") or [None])[0])
        else:
            s.append(f"level {a.get('level_real')} · trend {a.get('trend_context')} · reversal {a.get('reversal_valid')} · "
                     f"breakout {a.get('is_breakout_entry')} · false-break {a.get('false_break_risk')}")
        if a.get("elliott_note") and "level_kind" not in a:
            s.append("Elliott: " + html.escape(a["elliott_note"]))
        if len(res.get("audits") or []) > 1:
            s.append("दुसरा audit: " + " / ".join(res.get("verdicts") or []))
    elif res.get("error"):
        s.append("कारण: " + html.escape(str(res["error"])[:160]))
    s.append("Bot ने नेहमीप्रमाणे निर्णय घेतला — vision चा trade वर परिणाम नाही (V0).")
    if res.get("cost_usd"):
        s.append(f"खर्च ${res['cost_usd']:.4f} · {res.get('latency_ms', 0) / 1000:.1f}s")
    return "\n".join(s)[:1024]


def _budget_ok(g, model, path=None):
    day, month = VS.spent(path)
    est = SA.estimate_usd(model)
    return day + est <= float(g["vision_daily_budget_usd"]) and month + est <= float(g["vision_monthly_budget_usd"]), day, month


def _warn_budget_once(day, month, g, send_text, path=None):
    k = "budget_warned_" + VS.now_ist().strftime("%Y-%m-%d")
    if VS.kv_get(k, path):
        return
    VS.kv_set(k, "1", path)
    send_text(f"⚠️ <b>Vision budget</b>: आज ${day:.3f} / ${g['vision_daily_budget_usd']}, महिना ${month:.2f} / ${g['vision_monthly_budget_usd']} — "
              "पुढचे signals vision शिवाय (algorithm चा निर्णय).")


# --------------------------------------------------------------------------------------------------------- V1
FACTOR_MR = {1.0: "पूर्ण size", 0.5: "अर्धा size", 0.0: "skip"}


def _fmr(f):
    return FACTOR_MR.get(round(float(f or 0), 2), f"×{f}")


def v1_status(row, verdict, s, meta):
    """(status, finish fields, Decision|None). V0 mode ⇒ ("DONE", {}, None)."""
    if row.get("mode") not in VC.V1_MODES:
        return "DONE", {}, None
    d = VD.decide(row["mode"], verdict, s)
    now = VS.now_ist()
    extra = {"factor": d.factor, "decision_reason": d.reason, "timeout_status": d.timeout_status, "timeout_factor": d.timeout_factor,
             "median_range": (meta or {}).get("median_range")}
    if d.ask_human:
        extra["deadline"] = VS._iso(now + pd.Timedelta(minutes=int(s["approve_window_min"])))
        extra["final"] = "PENDING"
    else:
        extra.update(decided_at=VS._iso(now), decided_by="vision", final="ENTER" if d.status == "APPROVED" else "SKIP")
    return d.status, extra, d


def v1_caption(row, res, d, deadline=None, buttons=True, why=""):
    s = caption(row, res, row["mode"]).replace("👁 <b>Vision V0 — फक्त माहिती</b>", f"👁 <b>Vision V1 — {row['mode']}</b>")
    s = s.replace("Bot ने नेहमीप्रमाणे निर्णय घेतला — vision चा trade वर परिणाम नाही (V0).", "")
    lines = [x for x in s.split("\n") if x]
    s = ""
    if d.status == "PENDING_HUMAN":
        to = "skip" if d.timeout_status == "REJECTED" else _fmr(d.timeout_factor)
        dl = pd.Timestamp(deadline).strftime("%H:%M") if deadline else "?"
        s += f"\n⏱ <b>{dl} पर्यंत</b> निर्णय: ✅ ⇒ {_fmr(d.factor)} · ❌ ⇒ skip (shadow). उत्तर नाही ⇒ {to}."
        if not buttons:
            s += f"\n⚠️ बटणं नाहीत ({html.escape(why or 'VISION_CALLBACK_SECRET / TELEGRAM_APPROVER_IDS नाही')}) ⇒ timeout नियम लागू."
    elif d.status == "APPROVED":
        s += f"\n<b>✅ ENTRY मंजूर</b> ({_fmr(d.factor)}) — {html.escape(d.reason)}. Bot पुढच्या मिनिटाला drift guard नंतर entry घेईल (त्याचा trade संदेश येईल)."
    else:
        s += f"\n<b>❌ ENTRY नाकारली</b> — {html.escape(d.reason)}. खरा trade नाही; तुलनेसाठी PAPER shadow trade."
    lines = lines[:1] + [x for x in s.split("\n") if x] + lines[1:] + ["SL / target / exits: bot चे नेहमीचे नियम (automatic)."]
    return _fit(lines)


def _fit(lines, limit=1024):
    """Telegram caption मर्यादा: शेवटच्या ओळी पूर्ण गाळतो (HTML tag मध्येच कापला जाऊ नये; निर्णयाची ओळ वर असल्याने टिकते)."""
    while len(lines) > 2 and len("\n".join(lines)) > limit:
        lines.pop(-2 if len(lines) > 3 else -1)
    s = "\n".join(lines)
    return s if len(s) <= limit else re.sub(r"<[^>]+>", "", s)[:limit]


def v1_notify(row, res, d, png, path, reused=False):
    from . import tg as TG
    sid = row["signal_id"]
    r = VS.get_signal(sid, path) or {}
    can, why = TG.can_ask()
    btn = [("✅ Approve", VD.callback_data(sid, "A")), ("❌ Reject", VD.callback_data(sid, "R"))] if d.ask_human and can else None
    mid = TG.send_photo(png, v1_caption({**row, **r}, res, d, r.get("deadline"), buttons=bool(btn) or not d.ask_human, why=why), btn)
    VS.update(sid, path, tg_message_id=mid, notified=1 if mid else 0)
    return mid


def _safe_notify(row, res, d, png, path, reused=False):
    """Telegram / DB चूक निर्णयावर परिणाम करत नाही (निर्णय आधीच नोंदला आहे; बटणं नसतील तर timeout नियम)."""
    try:
        return v1_notify(row, res, d, png, path, reused=reused)
    except Exception as exc:
        print(f"⚠️ vision V1 Telegram त्रुटी (निर्णय नोंदलेला आहे): {type(exc).__name__}: {exc}")
        return None


def v1_housekeeping(path=None, now=None):
    """Timeouts (PENDING_HUMAN; worker उशीर ⇒ जुने QUEUED / RUNNING), न वापरलेले निर्णय (exec_window नंतर) ⇒ EXPIRED, drift / expiry ची माहिती.
    नियम `gate.resolve_due` चेच (bot सुद्धा तेच लावतो — worker बंद असला तरी). रिटर्न बदललेल्या rows."""
    from . import gate as VG
    from . import tg as TG
    now = pd.Timestamp(now or VS.now_ist())
    changed = []
    today = now.strftime("%Y-%m-%d")
    for r in VS.rows_with_status(("PENDING_HUMAN", "QUEUED", "RUNNING"), path):
        if r.get("mode") not in VC.V1_MODES:
            continue
        if str(r["signal_ts"])[:10] < today:                          # मागच्या दिवसाचे (worker बंद होता) ⇒ शांतपणे EXPIRED, entry / संदेश नाही
            if VS.transition(r["signal_id"], r["status"], "EXPIRED", path, exec_note="मागच्या दिवसाचा न ठरलेला signal", transition_notified=1):
                changed.append((r["signal_id"], "EXPIRED"))
            continue
        r2, to = VG.resolve_due(r, VC.load(r["bot"], path), now, path)
        if to:
            changed.append((r["signal_id"], to))
            if r["status"] == "PENDING_HUMAN":
                f = float(r2.get("factor") or 0.0)
                TG.edit_any(r.get("tg_message_id"), f"⏱ उत्तर आलं नाही ⇒ <b>{'skip (shadow)' if to == 'REJECTED' else _fmr(f)}</b> "
                            f"· {r['symbol']} {r['direction']} L{float(r['level'] or 0):,.0f}")
    for r in VS.rows_with_status(("APPROVED", "REJECTED"), path):
        s = VC.load(r["bot"], path)
        if r.get("decided_at") and pd.Timestamp(r["decided_at"]) + pd.Timedelta(minutes=int(s["exec_window_min"])) <= now:
            if VS.transition(r["signal_id"], r["status"], "EXPIRED", path,
                             exec_note=f"{r['status']} नंतर {s['exec_window_min']} मिनिटांत bot पोहोचला नाही (gates बदलले)",
                             transition_notified=0 if str(r["signal_ts"])[:10] >= today else 1):
                changed.append((r["signal_id"], "EXPIRED"))
    for r in VS.rows_with_status(("DRIFT_REJECTED", "EXPIRED"), path):
        if not r.get("transition_notified") and r.get("mode") in VC.V1_MODES and r.get("decided_at"):
            msg = (f"❌ <b>ENTRY नाकारली (drift guard)</b>: {r['symbol']} {r['direction']} L{float(r['level'] or 0):,.0f} — {r.get('drift_result')} ⇒ PAPER shadow"
                   if r["status"] == "DRIFT_REJECTED" else
                   f"⌛ {r['symbol']} {r['direction']} L{float(r['level'] or 0):,.0f}: {r.get('exec_note') or 'expired'}")
            TG.send_text(msg)
            VS.update(r["signal_id"], path, transition_notified=1)
    return changed


BAR_WAIT = True                                                          # tests / scripts साठी master switch (setting सोबत)


def bar_wait(row, s, now=None):
    """`vision_wait_for_bar_close`: signal चा setup bar अजून बंद नसेल तर (मूल्यमापन नंतर) ⇒ (थांबायचं?, bar माहिती)."""
    from . import context as CX
    s_tf = CH.TF_MAP.get(str(row.get("setup_tf")).upper(), (5, 15))[0]
    sb = CX.signal_bar(pd.Timestamp(row["signal_ts"]), s_tf, now or VS.now_ist())
    return bool(BAR_WAIT and s.get("vision_wait_for_bar_close", True) and not sb["closed"]), sb


def process_row(row, fetch_fn=default_fetch, client_factory=SA.make_client, send_photo=None, send_text=None, path=None, data_cache=None,
                wait_for_bar=True):
    """एक RUNNING row पूर्ण करणे. रिटर्न अंतिम result dict. कधीच raise नाही (चूक ⇒ FAILED row).
    `vision_wait_for_bar_close` (default on): signal चा setup bar बंद होईपर्यंत row परत QUEUED (data fetch / खर्च नाही); बंद झाल्यावर chart आणि
    संदर्भ त्या bar च्या close पर्यंत (asof) — मग निर्णय, आणि entry च्या क्षणी drift guard."""
    from notifications import send_telegram_message, send_telegram_photo
    send_photo = send_photo or send_telegram_photo
    send_text = send_text or send_telegram_message
    sid = row["signal_id"]
    img_path = img_sha = None
    try:
        import json
        setup = json.loads(row.get("setup_json") or "{}")
        row = {**row, "bot_label": setup.get("bot_label"), "tags": setup.get("tags") or {}, "invalidation": setup.get("invalidation"),
               "last_bar": setup.get("last_bar")}
        s, g = VC.load(row["bot"], path), VC.load("_global", path)
        model = VC.env_model("signal")
        wait, sb = bar_wait(row, s)
        if wait and wait_for_bar:
            VS.transition(sid, "RUNNING", "QUEUED", path)                 # bar बंद झाल्यावर पुन्हा (worker चा 5 s loop)
            return {"verdict": None, "deferred": True, "bar_end": sb["end"]}
        if wait_for_bar and s.get("vision_wait_for_bar_close", True) and BAR_WAIT and pd.Timestamp(sb["end_ts"]) > pd.Timestamp(row["signal_ts"]):
            row["asof"] = sb["end_ts"]                                    # bar बंद झाला ⇒ तिथपर्यंतचा chart (signal नंतरचा, पण निर्णयाच्या आधीचा)

        # 3. chart (reuse असला तरी Telegram साठी ताजा chart)
        need_daily = True                                               # v2.1: daily candles ⇒ ATR14 / trend / leg (gap वर्ग); 60M ⇒ daily panel
        key = (row["symbol"], need_daily)
        if data_cache is not None and key in data_cache:
            m1, d1 = data_cache[key]
        else:
            m1, d1 = fetch_fn(row["symbol"], need_daily)
            if data_cache is not None:
                data_cache[key] = (m1, d1)
        ek = ("expiries", row["symbol"])
        if data_cache is not None and ek in data_cache:
            row["expiries"] = data_cache[ek]
        else:
            row["expiries"] = fetch_expiries(row["symbol"]) if fetch_fn is default_fetch else []
            if data_cache is not None:
                data_cache[ek] = row["expiries"]
        row["ctx_settings"] = VC.ctx_settings(row["bot"], path)
        png, meta = CH.render(m1, row, d1) if m1 is not None and len(m1) else (None, {"error": "1m candles नाहीत"})
        row["ctx"] = meta.get("ctx")                                      # v2 signal text (अचूक किंमती OHLC वरून)
        if png:
            # §11: `_sent.png` आधी disk वर (overwrite नाही), मग तीच फाईल परत वाचून (sha256 तपासून) vision आणि Telegram ला — तेच bytes.
            img_path, img_sha = IM.save_exclusive(IM.signal_path(row, IM.SENT), png)
            png = IM.read_verified(img_path, img_sha)
        final = row.get("algo_decision") or "ENTER"                     # V0: vision फक्त माहिती ⇒ अंतिम निर्णय = algorithm चा

        # 2. reuse
        prev = (VS.find_reusable(row, int(s["reuse_window_min"]), path=path, prompt_version=SA.PROMPT_VERSION)
                if int(s["reuse_window_min"]) > 0 else None)
        if prev is not None:
            pj = json.loads(prev.get("vision_json") or "{}")
            res = {**pj, "verdict": prev["verdict"], "confidence": prev.get("confidence"), "cost_usd": 0.0, "latency_ms": 0, "error": None}
            pa = (pj.get("audits") or [None])[0]
            if pa:                                                      # code तथ्यं वेळेनुसार बदलतात (L break, PDC acceptance) — नव्या ctx वर पुन्हा (review S6)
                fa, _ = SA.apply_facts(SA.validate(pa)[0] or pa, meta.get("ctx"), row.get("direction"))
                cv = SA.code_verdict(fa, s.get("v2_disagree_rules"), s.get("v2_gray_rules"), meta.get("ctx"), row.get("direction"))
                if cv in SA.SEVERITY and SA.SEVERITY[cv] > SA.SEVERITY.get(res["verdict"], 1):
                    res["verdict"] = cv
            elif res["verdict"] == "agree":
                res["verdict"] = "gray"                                 # जुनं मत तपासता येत नाही ⇒ entry नाही
            pj = {**pj, "reused_image_sha256": prev.get("image_sha256"),          # vision ने पाहिलेली image = आधीच्या signal ची
                  "context": meta.get("ctx"), "reused_context": True}             # संदर्भ या signal चा; मत आधीचं
            st, extra, d = v1_status(row, res["verdict"], s, meta)
            ok = VS.finish(sid, st, path, only_from="RUNNING", verdict=res["verdict"], vision_json=pj, audits=0, confidence=prev.get("confidence"), latency_ms=0,
                      cost_usd=0.0, model=prev.get("model"), reused_from=prev["signal_id"], image_path=img_path, image_sha256=img_sha,
                      prompt_version=prev.get("prompt_version"), final_decision=extra.pop("final", final), **extra)
            if not ok:                                                  # bot / service ने आधीच ठरवलं (उदा. उशीर ⇒ timeout) — overwrite नाही
                return res
            if d is not None:
                _safe_notify(row, res, d, png, path, reused=True)
            elif row["mode"] == "notify":
                VS.set_notified(sid, send_photo(png, caption(row, res, row["mode"], reused=True)), path)
            return res

        # 4–5. render / model / key / budget
        res = {"verdict": "unavailable", "audits": [], "verdicts": [], "confidence": None, "cost_usd": 0.0, "latency_ms": 0, "model": model}
        if png is None:
            res["error"] = f"chart नाही: {meta.get('error')}"
        elif not model:
            res["error"] = "VISION_SIGNAL_MODEL env नाही"
        elif not VC.api_key_present():
            res["error"] = "ANTHROPIC_API_KEY नाही"
        else:
            ok, day, month = _budget_ok(g, model, path)
            if not ok:
                res["error"] = "budget संपलं"
                _warn_budget_once(day, month, g, send_text, path)
            else:
                client = client_factory(int(s["vision_timeout_sec"]))
                res = SA.audit(client, png, row, model, second_below=float(s["second_audit_below_conf"]), effort=VC.env_effort("signal"),
                               thinking=VC.env_thinking("signal"),
                               on_usage=lambda u, c: VS.add_usage("signal", model, u, c, sid, path),
                               budget_ok=lambda: _budget_ok(g, model, path)[0],
                               disagree_rules=s.get("v2_disagree_rules"), gray_rules=s.get("v2_gray_rules"))
        res["fail_action"] = s["vision_fail_action"] if res["verdict"] == "unavailable" else None
        st, extra, d = v1_status(row, res["verdict"], s, meta)
        ok = VS.finish(sid, st, path, only_from="RUNNING", verdict=res["verdict"], vision_json={**{k: res.get(k) for k in ("audits", "verdicts", "error", "prompt_version", "usage",
                                                                                                    "fail_action", "rule_hits")},
                                                                               "context": meta.get("ctx")},
                  audits=len(res.get("audits") or []), confidence=res.get("confidence"), latency_ms=res.get("latency_ms"),
                  cost_usd=res.get("cost_usd") or 0.0, model=model, image_path=img_path, image_sha256=img_sha, error=res.get("error"),
                  prompt_version=SA.PROMPT_VERSION if res.get("audits") or res.get("verdicts") else None,
                  final_decision=extra.pop("final", final), **extra)
        if not ok:
            return res
        if d is not None:
            _safe_notify(row, res, d, png, path)
        elif row["mode"] == "notify":
            VS.set_notified(sid, send_photo(png, caption(row, res, row["mode"])), path)
        return res
    except Exception as exc:
        err = f"{type(exc).__name__}: {str(exc)[:200]}"
        if row.get("mode") in VC.V1_MODES:                              # V1: worker अपयश ⇒ vision unavailable म्हणून निर्णय (bot अडकू नये)
            try:
                st, extra, d = v1_status(row, "unavailable", VC.load(row["bot"], path), {})
                if VS.finish(sid, st, path, only_from="RUNNING", verdict="unavailable", error=err, image_path=img_path, image_sha256=img_sha,
                             final_decision=extra.pop("final", "ENTER"), **extra):
                    _safe_notify(row, {"verdict": "unavailable", "error": err}, d, None, path)
                return {"verdict": "unavailable", "error": str(exc)}
            except Exception:
                pass
        VS.finish(sid, "FAILED", path, only_from="RUNNING", verdict="unavailable", error=err, image_path=img_path,
                  image_sha256=img_sha, final_decision=row.get("algo_decision") or "ENTER")
        return {"verdict": "unavailable", "error": str(exc)}


def run_once(path=None, **kw):
    VS.expire_stale(STALE_MIN, path)
    try:
        v1_housekeeping(path)
    except Exception as exc:                                            # housekeeping ची चूक नवे signals थांबवत नाही
        print(f"⚠️ vision housekeeping त्रुटी: {type(exc).__name__}: {exc}")
    cache = {}
    done = []
    for row in VS.claim_queued(path=path):
        done.append((row["signal_id"], process_row(row, path=path, data_cache=cache, **kw)))
    return done


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--loop-seconds", type=int, default=0, help="इतके सेकंद दर --poll ने तपासत राहा (cron दर मिनिटाला ⇒ 55)")
    p.add_argument("--poll", type=int, default=5)
    p.add_argument("--usage", nargs="?", const="today", default=None, help="त्या दिवसाचा token / $ वापर")
    a = p.parse_args(argv)
    if a.usage:
        day = VS.now_ist().strftime("%Y-%m-%d") if a.usage == "today" else a.usage
        u = VS.usage_summary(day)
        rows = VS.list_signals(day)
        print(f"{day}: signals {len(rows)} (DONE {sum(r['status'] == 'DONE' for r in rows)}, reuse {sum(bool(r['reused_from']) for r in rows)}), "
              f"API calls {u['calls']}, input {u['input_tokens']:,} + cache-read {u['cache_read']:,} + cache-write {u['cache_write']:,}, "
              f"output {u['output_tokens']:,} tokens, खर्च ${u['cost_usd']:.4f}")
        for r in rows:
            print(f"  {r['signal_ts'][11:16]} {r['bot']} {r['symbol']} {r['direction']} L{r['level']} {r['setup_tf']} → {r['verdict']} "
                  f"({r['confidence']}) ${r['cost_usd'] or 0:.4f} {r['latency_ms'] or 0}ms {r['error'] or ''}")
        return 0
    from process_lock import ProcessLock, ProcessLockHeld
    try:
        with ProcessLock("vision_worker"):
            t_end = time.monotonic() + max(0, a.loop_seconds)
            while True:
                for sid, res in run_once():
                    print(f"{VS.now_ist():%H:%M:%S} {sid} → {res.get('verdict')} {res.get('error') or ''}")
                if time.monotonic() + a.poll >= t_end:
                    break
                time.sleep(a.poll)
    except ProcessLockHeld:
        print("⏭️ vision worker आधीच चालू आहे")
    return 0


if __name__ == "__main__":
    sys.exit(main())
