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

PROMPT_VERSION = "v22_chart_audit_v1"
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
  Structure: pivots at visible swing extremes, HH/HL/LH/LL tags consistent with drawn swings, protected swing at the right swing,
  Dow state band matches structure, impulse vs correction legs, wave labels plausible.
  Pullback & trigger: price really pulled back into the level; commitment (reversal) candle at the level and of a recognisable form;
  trendline/channel drawn where claimed.
  Entry/SL/Target: entry at the marked trigger; stop beyond the structural swing/zone (not inside); target at the next opposing level;
  drawn R:R consistent with the engine R:R from FACTS; for no-trade charts the "blocked at step N" reason is visible.
- A section the chart does not show ⇒ status "na".
- status: ok / warn / fail / na; reason ≤ 15 words, English. issues: ≤ 5 short items, most important first.
- verdict: agree (no fail, ≤ 1 warn) / partly_agree / disagree (any fail on structure or entry_sl_target).
Return only the JSON object."""


def facts_text(kind, js):
    """Engine JSON ⇒ छोटा facts मजकूर (आकडे फक्त इथून)."""
    if kind == "v22_daily_swings":
        piv = js.get("pivots") or []
        prot = [p for p in piv if p.get("protected_minor") or p.get("protected_q15")]
        q, m = js.get("q15") or {}, js.get("minor") or {}
        lines = [f"Chart: {js.get('symbol')} daily swings, window {js.get('window', {}).get('from')} .. {js.get('window', {}).get('to')}.",
                 f"Engine pivots in window: {len(piv)} (tags {sum(1 for p in piv if p['tag'] in ('HH', 'HL'))} HH/HL, "
                 f"{sum(1 for p in piv if p['tag'] in ('LH', 'LL'))} LH/LL); protected swings {len(prot)}.",
                 f"Dow minor state now {m.get('trend')} since {m.get('since')}; protected {m.get('protected_now')}.",
                 f"Q15 degree-aware now {q.get('trend')} {q.get('phase')} {q.get('wave')}; origin {q.get('protected_now')}; mature {q.get('mature')}.",
                 f"Elliott advisory degree {js.get('elliott_degree')} (not used in decisions).",
                 "No zones, no entry/SL/target on this chart (structure review only)."]
        return "\n".join(lines)
    return json.dumps({k: js.get(k) for k in ("symbol", "decision", "checklist", "risk", "level", "conviction", "why") if k in js},
                      ensure_ascii=False, default=str)[:3000]


def build_request(png, facts, model, max_tokens=900):
    if not model:
        raise ValueError("VISION_SIGNAL_MODEL env सेट नाही")
    return {"model": model, "max_tokens": int(max_tokens),
            "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode()}},
                {"type": "text", "text": "FACTS (engine data):\n" + facts}]}],
            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}


def validate(raw):
    if not isinstance(raw, dict) or raw.get("verdict") not in VERDICTS:
        return None, "verdict अवैध"
    secs = raw.get("sections") or {}
    out = {"verdict": raw["verdict"], "sections": {}, "issues": [str(x)[:120] for x in (raw.get("issues") or [])][:5],
           "missing_or_clutter": str(raw.get("missing_or_clutter") or "")[:160]}
    for k in SECTIONS:
        s = secs.get(k) or {}
        st = s.get("status") if s.get("status") in STATUS_ICON else None
        if st is None:
            return None, f"{k} status अवैध"
        out["sections"][k] = {"status": st, "reason": str(s.get("reason") or "")[:120]}
    return out, None


def _budget(model, g=None, spent_fn=None, estimate_fn=None):
    """(ok, day, cap). Hard stop: आजचा खर्च + अंदाज > vision_daily_budget_usd ⇒ नाही."""
    from vision import config as VC
    from vision import signal_audit as SA
    from vision import store as VS
    g = g or VC.load("_global")
    day, month = (spent_fn or VS.spent)()
    est = (estimate_fn or SA.estimate_usd)(model)
    cap = float(g["vision_daily_budget_usd"])
    if day + est > cap:
        return False, day, cap, "daily budget reached"
    if month + est > float(g["vision_monthly_budget_usd"]):
        return False, day, cap, "monthly budget reached"
    return True, day, cap, ""


def audit_chart(png, facts, model=None, client=None, budget=None, on_usage=None, decision=None):
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
    try:
        client = client or SA.make_client(30)
        msg = client.messages.create(**build_request(png, facts, model))
    except Exception as exc:                                               # noqa: BLE001 — chart तरीही जातो; कारण caption मध्ये
        out.update(status="failed", why=f"API: {type(exc).__name__}")
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
    text = next((b.text for b in (getattr(msg, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    try:
        data, err = validate(json.loads(text or ""))
    except ValueError as exc:
        data, err = None, f"JSON: {exc}"
    if err:
        out.update(status="failed", why=err)
        return out
    out.update(status="done", **data)
    return out


def caption_line(a):
    if a["status"] == "done":
        bad = sum(1 for s in a["sections"].values() if s["status"] in ("warn", "fail"))
        return "Vision audit: pass" if a["verdict"] == "agree" and bad == 0 else \
            f"Vision audit: {a['verdict'].replace('_', ' ')} — {bad} issue{'s' if bad != 1 else ''}, see report"
    if a["why"] in ("daily budget reached", "monthly budget reached"):
        return f"Vision audit skipped: {a['why']}"
    return f"Vision audit {'failed' if a['status'] == 'failed' else 'skipped'}: {a['why'][:40]}"


def report_text(a, title):
    """Vision report (English, ≤ 12 ओळी): verdict, चार sections ✅/⚠️/❌, footer."""
    lines = [f"Vision report — {title}"[:120]]
    if a["status"] != "done":
        lines.append(caption_line(a))
    else:
        lines.append(f"Verdict: {a['verdict'].replace('_', ' ')}")
        for k in SECTIONS:
            s = a["sections"][k]
            lines.append(f"{SECTION_NAMES[k]}: {STATUS_ICON[s['status']]} {s['reason']}"[:160])
        for x in a["issues"][:4]:
            lines.append(f"• {x}"[:140])
        if a.get("cost_usd"):
            lines.append(f"Cost ${a['cost_usd']:.4f} · today ${a.get('spent_today', 0) + a['cost_usd']:.3f} / ${a.get('cap', 0):.2f}")
    lines.append(FOOTER)
    return "\n".join(lines[:11] + [lines[-1]] if len(lines) > 12 else lines)


def with_audit_line(caption, line):
    """Caption मधली "Vision audit…" ओळ बदला (नसेल तर शेवटच्या ओळीआधी जोडा); ≤ 1024."""
    ls = caption.splitlines()
    idx = next((i for i, x in enumerate(ls) if x.startswith("Vision audit")), None)
    if idx is None:
        ls.insert(max(0, len(ls) - 1), line)
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
            if old.get("sha") == sha and old.get("status") == "done":
                return {**old, "reused": True}
        except (OSError, ValueError):
            pass
        jp = os.path.join(run_dir, it["json"]) if it.get("json") else None
        try:
            js = json.load(open(jp, encoding="utf-8")) if jp and os.path.exists(jp) else {}
        except ValueError:
            js = {}
        a = audit_chart(png, facts_text(it.get("kind"), js), model=model, client=client, budget=budget, on_usage=on_usage)
        a["item"], a["chart"], a["sha"] = it["item"], png_rel, sha
        try:
            with open(out_p, "w", encoding="utf-8") as fh:
                json.dump(a, fh, ensure_ascii=False, indent=1)
        except OSError as exc:
            a["save_error"] = type(exc).__name__
        return a
    return run
