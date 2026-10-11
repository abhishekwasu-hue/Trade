"""decision3/vision_audit.py — v2.2 charts चा Vision audit, Telegram आधी (Abhi: chart → Vision audit → Telegram; सगळ्या v2.2 charts ना).

Vision फक्त **placement** तपासतो (pivots / tags / protected / Dow पट्टा / wave labels / zones / pullback-trigger / entry-SL-target जागा).
आकडे कधीच image मधून नाहीत — engine JSON मधले facts text मध्ये दिले जातात. Vision कधीच level बदलत नाही, निर्णय बदलत नाही, order देत /
अडवत नाही (PAPER / shadow फक्त): `audit_chart` ला decision object मिळतच नाही; मिळाला तरी तो deep-copy वर वाचतो (test).
Provider / खर्च / budget: vision.signal_audit (client, cost_usd, usage_of) + vision.store (add_usage, spent) + vision.config
(`vision_daily_budget_usd`, hard stop). Budget संपला / अपयश ⇒ chart तरीही जातो, caption मध्ये तसं ("never block silently")."""
import base64
import copy
import json
import os
import time

PROMPT_VERSION = "v22_chart_audit_v2"
TASK = "v22_chart_audit"
SECTIONS = ("zones", "structure", "pullback_trigger", "entry_sl_target")
SECTION_NAMES = {"zones": "Zones", "structure": "Structure", "pullback_trigger": "Pullback & trigger", "entry_sl_target": "Entry/SL/Target"}
STATUS_ICON = {"ok": "✅", "warn": "⚠️", "fail": "❌", "na": "—"}
VERDICTS = ("agree", "partly_agree", "disagree")
FOOTER = "Engine numbers from data; Vision judges placement only — no order"

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["verdict", "sections", "issues", "missing_or_clutter"],
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "sections": {"type": "object", "additionalProperties": False, "required": list(SECTIONS),
                     "properties": {k: {"type": "object", "additionalProperties": False, "required": ["status", "reason"],
                                        "properties": {"status": {"type": "string", "enum": list(STATUS_ICON)},
                                                       "reason": {"type": "string"}}} for k in SECTIONS}},
        "issues": {"type": "array", "items": {"type": "string"}},
        "missing_or_clutter": {"type": "string"},
    },
}

SYSTEM_PROMPT = """ROLE
You audit a chart produced by a rule-based trading engine (NSE index, PAPER/shadow review only). You judge whether what is DRAWN is
placed where the candles say it should be. You never trade, never change levels, never change the engine's decision.

RULES
- Numbers come only from the FACTS text (engine data). Never read prices from the image; judge placement only.
- Check, where the chart shows them:
  Zones/levels: each zone at a real prior buyer/seller area (visible reaction/rejection), sensible width, only significant levels
  (no clutter), state (fresh/tested/flipped/invalidated) consistent with candles, any obvious significant level missing.
  Structure: the protected swing / origin line at the right swing and the Dow state in the title consistent with the candles
  (default charts draw no minor pivots or HH/HL/LH/LL tags — never ask for them).
  Pullback & trigger: price really pulled back into the level; commitment (reversal) candle at the level and of a recognisable form;
  trendline/channel drawn where claimed.
  Entry/SL/Target: entry at the marked trigger; stop beyond the structural swing/zone (not inside); target at the next opposing level;
  drawn R:R consistent with the engine R:R from FACTS; for no-trade charts the "blocked at step N" reason is visible.
- A section the chart does not show ⇒ status "na".
- status: ok / warn / fail / na; reason ≤ 15 words, English. issues: ≤ 5 short items, most important first.
- verdict: agree (no fail, ≤ 1 warn) / partly_agree / disagree (any fail on structure or entry_sl_target).
Return only the JSON object."""


DAILY_SYSTEM_PROMPT = """ROLE
You audit a DAILY structure chart produced by a rule-based trading engine (NSE index, PAPER/shadow review only). You judge whether what is
DRAWN is placed where the candles say it should be. You never trade, never change levels, never change the engine's decision.

The chart shows only trend-degree structure: impulse legs (one line each), corrections as labelled brackets/boxes, the protected origin
line, and at most six horizontal level bands. Minor pivots and tags are intentionally NOT drawn — never ask for them.

Answer exactly these questions (numbers only from FACTS; judge placement only):
- zones: are the level bands at real prior buyer/seller areas (visible reaction/rejection)?
- structure: are the corrections bracketed correctly (start, end, in progress), and is the origin/protected line at the right swing?
- missing_or_clutter: is anything important missing (a major swing level, a correction not bracketed)?
- pullback_trigger and entry_sl_target: always "na" on this chart.
status: ok / warn / fail / na; reason ≤ 15 words, English. issues: ≤ 5 short items, most important first.
verdict: agree (no fail, ≤ 1 warn) / partly_agree / disagree (any fail on structure).
Return only the JSON object."""
REPAIR = "Your previous reply was not a valid JSON object for the required schema. Reply again with only that JSON object — no prose, no code fences."


def facts_text(kind, js):
    """Engine JSON ⇒ छोटा facts मजकूर (आकडे फक्त इथून)."""
    if kind == "v22_daily_swings":
        piv = js.get("pivots") or []
        prot = [p for p in piv if p.get("protected_minor") or p.get("protected_q15")]
        q, m = js.get("q15") or {}, js.get("minor") or {}
        if js.get("objects") is not None:                                 # C1: trend-degree chart (corrections + bands)
            ob = js["objects"]
            lines = [f"Chart: {js.get('symbol')} daily structure, window {js.get('window', {}).get('from')} .. {js.get('window', {}).get('to')}.",
                     f"Trend now: {js.get('trend_line')}.",
                     f"Impulse legs drawn: {len(ob.get('legs', []))}; corrections bracketed: {len(ob.get('corrections', []))}; "
                     f"level bands: {len(js.get('bands') or [])}.",
                     "Bands: " + "; ".join(f"{b['label']} {b['lo']:,.0f}-{b['hi']:,.0f} ({b['state']})" for b in (js.get("bands") or [])) + "."]
            return "\n".join(lines)
        lines = [f"Chart: {js.get('symbol')} daily swings, window {js.get('window', {}).get('from')} .. {js.get('window', {}).get('to')}.",
                 f"Engine pivots in window: {len(piv)} (tags {sum(1 for p in piv if p['tag'] in ('HH', 'HL'))} HH/HL, "
                 f"{sum(1 for p in piv if p['tag'] in ('LH', 'LL'))} LH/LL); protected swings {len(prot)}.",
                 f"Dow minor state now {m.get('trend')} since {m.get('since')}; protected {m.get('protected_now')}.",
                 f"Q15 degree-aware now {q.get('trend')} {q.get('phase')}; origin {q.get('protected_now')}; mature {q.get('mature')}. "
                 "Wave labels (1)-(5)/(A)(B)(C) on the chart are the Elliott advisory count only.",
                 f"Elliott advisory degree {js.get('elliott_degree')} (not used in decisions).",
                 "No zones, no entry/SL/target on this chart (structure review only)."]
        return "\n".join(lines)
    return json.dumps({k: js.get(k) for k in ("symbol", "decision", "checklist", "risk", "level", "conviction", "why") if k in js},
                      ensure_ascii=False, default=str)[:3000]


def build_request(png, facts, model, max_tokens=900, system=None):
    if not model:
        raise ValueError("VISION_SIGNAL_MODEL env सेट नाही")
    return {"model": model, "max_tokens": int(max_tokens),
            "system": [{"type": "text", "text": system or SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode()}},
                {"type": "text", "text": "FACTS (engine data):\n" + facts}]}],
            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}


def validate(raw):
    """Vision JSON ⇒ (data, None) किंवा (None, English कारण) — caption / report English राहतात; कोणताही आकार raise करत नाही."""
    if not isinstance(raw, dict) or raw.get("verdict") not in VERDICTS:
        return None, "invalid verdict"
    secs = raw.get("sections")
    if not isinstance(secs, dict):
        return None, "invalid sections"
    iss = raw.get("issues") or []
    iss = iss if isinstance(iss, list) else [iss]
    out = {"verdict": raw["verdict"], "sections": {}, "issues": [_one_line(x)[:120] for x in iss][:5],
           "missing_or_clutter": _one_line(raw.get("missing_or_clutter") or "")[:160]}
    for k in SECTIONS:
        s = secs.get(k)
        s = s if isinstance(s, dict) else {}
        st = s.get("status") if s.get("status") in STATUS_ICON else None
        if st is None:
            return None, f"invalid {k} status"
        out["sections"][k] = {"status": st, "reason": _one_line(s.get("reason") or "")[:120]}
    return out, None


def parse_json(text):
    """C2: Vision text ⇒ dict — code fence / आधी-नंतरचा मजकूर असेल तर पहिला {...} object; जमलं नाही ⇒ ValueError."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t.lower().startswith("json") else t
    try:
        return json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            raise
        return json.loads(t[a:b + 1])


def _one_line(x):
    return " ".join(str(x).split())


def _weekdays_left(today):
    """आजनंतर महिन्यात उरलेले सोम–शुक्र (signals चा मासिक राखीव भाग — run_visual_audit सारखाच नियम)."""
    import pandas as pd
    t = pd.Timestamp(today).normalize()
    end = t + pd.offsets.MonthEnd(0)
    return int(len(pd.bdate_range(t + pd.Timedelta(days=1), end))) if end > t else 0


def _budget(model, g=None, spent_fn=None, estimate_fn=None, today=None):
    """(ok, day, cap, why). Hard stop — signals ला प्राधान्य (run_visual_audit / PR #274 सारखं): chart audit फक्त जर
    आजचा खर्च + अंदाज ≤ दैनिक budget − signals_daily_reserve_usd, आणि महिना + अंदाज ≤ मासिक − राखीव × उरलेले weekdays."""
    from vision import config as VC
    from vision import signal_audit as SA
    from vision import store as VS
    g = g or VC.load("_global")
    day, month = (spent_fn or VS.spent)()
    est = (estimate_fn or SA.estimate_usd)(model)
    cap = float(g["vision_daily_budget_usd"])
    reserve = float(g.get("signals_daily_reserve_usd", 0.0))
    if day + est > cap - reserve + 1e-12:
        return False, day, cap, "daily budget reached"
    if today is None:
        today = VS.now_ist()
        today = today.replace(tzinfo=None) if getattr(today, "tzinfo", None) is not None else today
    if month + est > float(g["vision_monthly_budget_usd"]) - reserve * _weekdays_left(today) + 1e-12:
        return False, day, cap, "monthly budget reached"
    return True, day, cap, ""


def audit_chart(png, facts, model=None, client=None, budget=None, on_usage=None, decision=None, system=None):
    """एका chart चा audit ⇒ dict {status: done/skipped/failed, verdict, sections, issues, cost_usd, spent_today, cap, why, model,
    prompt_version}. decision (असल्यास) फक्त deep-copy म्हणून वाचतो — परत कधीच नाही / बदल नाही."""
    _ = copy.deepcopy(decision) if decision is not None else None
    model = model or os.environ.get("VISION_SIGNAL_MODEL", "")
    out = {"status": "skipped", "verdict": None, "sections": {}, "issues": [], "cost_usd": 0.0, "why": "", "model": model,
           "prompt_version": PROMPT_VERSION, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not model:
        out["why"] = "VISION_SIGNAL_MODEL not set"
        return out
    try:
        b = budget(model) if budget else _budget(model)
    except Exception as exc:                                               # noqa: BLE001 — DB / settings अपयश ⇒ audit नाही, chart जातो
        out.update(status="failed", why=f"budget check {type(exc).__name__}")
        return out
    ok, day, cap = b[:3]
    out.update(spent_today=round(day, 4), cap=cap)
    if not ok:
        out["why"] = b[3] if len(b) > 3 and b[3] else "daily budget reached"
        return out
    from vision import signal_audit as SA
    t0 = time.monotonic()
    req = build_request(png, facts, model, system=system)
    try:
        client = client or SA.make_client(30)
        msg = client.messages.create(**req)
    except Exception as exc:                                               # noqa: BLE001 — chart तरीही जातो; कारण caption मध्ये
        out.update(status="failed", why=f"API: {type(exc).__name__}")
        if on_usage is not None:                                           # timeout / network: request कदाचित billed ⇒ सावध अंदाज
            usage = {"input_tokens": 2050, "output_tokens": SA.max_output_tokens(), "estimated": 1}   # (signal_audit सारखाच)
            out["cost_usd"] = round(SA.cost_usd(model, usage), 6)
            out["cost_estimated"] = True
            try:
                on_usage(usage, out["cost_usd"])
            except Exception as e2:                                        # noqa: BLE001
                out["cost_log_error"] = type(e2).__name__
        return out
    usage = SA.usage_of(msg)
    cost = SA.cost_usd(model, usage)
    out["cost_usd"] = round(cost, 6)
    out["latency_ms"] = int((time.monotonic() - t0) * 1000)
    if on_usage is not None:
        try:
            on_usage(usage, cost)                                          # cost log अपयश ⇒ पैसे गेलेला निकाल टाकत नाही
        except Exception as exc:                                           # noqa: BLE001
            out["cost_log_error"] = type(exc).__name__
    data, err, text = _read(msg)
    if err:                                                                # C2: JSON / schema चुकीचा ⇒ एकदाच repair (budget आत असेल तरच)
        try:
            b2 = budget(model) if budget else _budget(model)
        except Exception as exc:                                           # noqa: BLE001
            b2, out["repair_error"] = (False,), type(exc).__name__
        if b2[0]:
            out["repair"] = True
            req2 = {**req, "messages": req["messages"] + [{"role": "assistant", "content": text or "{}"},
                                                          {"role": "user", "content": REPAIR}]}
            try:
                msg2 = client.messages.create(**req2)
                u2 = SA.usage_of(msg2)
            except Exception as exc:                                       # noqa: BLE001 — timeout: request कदाचित billed ⇒ सावध अंदाज
                out["repair_error"] = type(exc).__name__
                msg2, u2 = None, {"input_tokens": 2050, "output_tokens": SA.max_output_tokens(), "estimated": 1}
                out["cost_estimated"] = True
            c2 = SA.cost_usd(model, u2)
            out["cost_usd"] = round(out["cost_usd"] + c2, 6)
            if on_usage is not None:
                try:
                    on_usage(u2, c2)
                except Exception as exc:                                   # noqa: BLE001
                    out["cost_log_error"] = type(exc).__name__
            if msg2 is not None:
                data, err, _ = _read(msg2)
    if err:                                                                # chart तरीही जातो: "Vision skipped: parse error" (एकटी failed ओळ नाही)
        out.update(status="skipped", why="parse error", detail=err)
        return out
    out.update(status="done", **data)
    return out


def _read(msg):
    """Vision message ⇒ (data, err, text); JSON वाचता आला नाही ⇒ err "parse error"; schema चुकीचा ⇒ validate चं कारण."""
    text = next((b.text for b in (getattr(msg, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    try:
        raw = parse_json(text)
    except ValueError:
        return None, "parse error", text
    data, err = validate(raw)
    return data, err, text


def caption_line(a):
    if a["status"] == "done":
        bad = sum(1 for s in a["sections"].values() if s["status"] in ("warn", "fail"))
        return "Vision audit: pass" if a["verdict"] == "agree" and bad == 0 else \
            f"Vision audit: {a['verdict'].replace('_', ' ')} — {bad} issue{'s' if bad != 1 else ''}, see report"
    if a["why"] in ("daily budget reached", "monthly budget reached"):
        return f"Vision audit skipped: {a['why']}"
    if a["why"] == "parse error":
        return "Vision skipped: parse error"
    return f"Vision audit {'failed' if a['status'] == 'failed' else 'skipped'}: {a['why'][:40]}"


def report_text(a, title):
    """Vision report (English, ≤ 12 ओळी): verdict, चार sections ✅/⚠️/❌, footer."""
    lines = [f"Vision report — {title}"[:120]]
    if a["status"] != "done":
        lines.append(caption_line(a))
        if a.get("cost_usd"):                                              # C4: पैसे गेले असतील तर खर्च ओळ
            lines.append(f"Cost ${a['cost_usd']:.4f}" + (" (estimated)" if a.get("cost_estimated") else ""))
    else:
        lines.append(f"Verdict: {a['verdict'].replace('_', ' ')}")
        for k in SECTIONS:
            s = a["sections"][k]
            if s["status"] == "na":                                        # C3: chart वर नसलेला भाग ⇒ ओळच नाही ("—" नाही)
                continue
            lines.append(f"{SECTION_NAMES[k]}: {STATUS_ICON[s['status']]} {s['reason']}"[:160])
        if a.get("missing_or_clutter"):
            lines.append(f"Missing: {a['missing_or_clutter']}"[:160])
        for x in a["issues"][:4]:
            lines.append(f"• {x}"[:140])
        if a.get("reused"):
            lines.append("Reused earlier audit of the same chart — no new cost")
        elif a.get("cost_usd"):
            lines.append(f"Cost ${a['cost_usd']:.4f} · today ${a.get('spent_today', 0) + a['cost_usd']:.3f} / ${a.get('cap', 0):.2f}")
    lines.append(FOOTER)
    return "\n".join(lines[:11] + [lines[-1]] if len(lines) > 12 else lines)


def with_audit_line(caption, line):
    """Caption मधली "Vision audit…" ओळ बदला (नसेल तर शेवटच्या ओळीआधी जोडा); ≤ 1024."""
    ls = caption.splitlines()
    idx = next((i for i, x in enumerate(ls) if x.startswith("Vision audit")), None)
    if idx is None:
        ls.insert(max(0, len(ls) - 1), line)
        if len(ls) > 7:                                                    # ≤ 7 ओळी: audit + शेवटची ओळ ठेवून मधली गाळतो
            ls = ls[:5] + ls[-2:]
    else:
        ls[idx] = line
    return "\n".join(ls)[:1024]


def append_summary(path, day, rows):
    """docs/reports/v22/VISION_AUDIT.md मध्ये दिवसाचा सारांश: charts, agree / partly / disagree, skipped, top issues, spend."""
    from collections import Counter
    done = [r for r in rows if r["status"] == "done"]
    cnt = Counter(r["verdict"] for r in done)
    iss = Counter(x for r in done for x in r.get("issues", []))
    spend = sum(r.get("cost_usd") or 0 for r in rows)
    block = [f"\n## {day}", f"- charts audited: {len(done)} / {len(rows)} (skipped / failed {len(rows) - len(done)})",
             f"- agree {cnt.get('agree', 0)} · partly agree {cnt.get('partly_agree', 0)} · disagree {cnt.get('disagree', 0)}",
             "- top issues: " + ("; ".join(f"{k} ×{v}" for k, v in iss.most_common(3)) or "—"), f"- spend: ${spend:.4f}"]
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as fh:
        if new:
            fh.write("# v2.2 Vision audit — daily summary\n\nVision judges placement only; disagreements are evidence for Abhi's review, "
                     "never auto-changes. Engine numbers from data — no order.\n")
        fh.write("\n".join(block) + "\n")
    return block


def make_auditor(model=None, client=None, budget=None, on_usage=None):
    """send_run साठी auditor(run_dir, item): पहिला PNG + item["json"] (engine data) ⇒ audit; JSON PNG शेजारी
    (<png>.vision.json) — trade-data मध्ये."""
    import hashlib

    def run(run_dir, it):
        png_rel = it["files"][0]
        png = open(os.path.join(run_dir, png_rel), "rb").read()
        sha = hashlib.sha256(png).hexdigest()[:16]
        out_p = os.path.join(run_dir, os.path.splitext(png_rel)[0] + ".vision.json")
        try:                                                               # त्याच chart चा आधीचा पूर्ण audit ⇒ पुन्हा खर्च नाही
            old = json.load(open(out_p, encoding="utf-8"))
            if old.get("sha") == sha and old.get("status") == "done":   # खर्च आधीच नोंदलेला ⇒ या send चा खर्च 0 (summary दुहेरी नाही)
                return {**old, "reused": True, "cost_usd": 0.0, "first_cost_usd": old.get("cost_usd", 0.0)}
        except (OSError, ValueError):
            pass
        jp = os.path.join(run_dir, it["json"]) if it.get("json") else None
        try:
            js = json.load(open(jp, encoding="utf-8")) if jp and os.path.exists(jp) else {}
        except ValueError:
            js = {}
        system = DAILY_SYSTEM_PROMPT if (it.get("kind") == "v22_daily_swings" and js.get("objects") is not None) else None   # C1
        a = audit_chart(png, facts_text(it.get("kind"), js), model=model, client=client, budget=budget, on_usage=on_usage,
                        system=system)
        a["item"], a["chart"], a["sha"] = it["item"], png_rel, sha
        try:
            with open(out_p, "w", encoding="utf-8") as fh:
                json.dump(a, fh, ensure_ascii=False, indent=1)
        except OSError as exc:
            a["save_error"] = type(exc).__name__
        return a
    return run
