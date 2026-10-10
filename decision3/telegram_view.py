"""decision3/telegram_view.py — थर v2.2 पायरी D: Telegram trader view (spec §2 chart + §6.5 कथा). फक्त फाइली तयार करतो; पाठवणं नाही.

प्रत्येक निवडलेल्या bar साठी (setup ✅ / 🟡 किंवा Abhi ची खूण):
  • 3 charts (English मजकूर): Daily (त्या bar ला माहीत state पर्यंत) · 1H (levels ★, swings) · 15M (level, K रेघ, entry / SL / target, खूण).
  • Caption 5–7 ओळी मराठी: शीर्षक + `charts.story` (कथा) + B1 / B2 योजना.
  • Debug view वेगळा (checklist ①–⑦ + पुरावे) ⇒ `debug.json` (पाठवला जात नाही).
Manifest = backtest_review.telegram चाच format (`review/v22/<run>/manifest.json`); पाठवणं फक्त VPS वरून
`scripts/send_review_to_telegram.py --run review/v22/<run>` (token फक्त VPS .env मध्ये). Order / broker / AI call नाही.
"""
import json
import os

import pandas as pd

from . import charts as CH
from . import daily as DD
from . import method as M

MAX_CAPTION = 1024


def b_plans(V, r):
    """B1 / B2 योजना (method.b_plans)."""
    return M.plans_of(V, r)


def caption(V, r, symbol):
    """Telegram caption (मराठी, 5–7 ओळी, ≤ 1024)."""
    head = f"🧭 v2.2 {symbol} · {r['ts'][:16]} · " + (f"{r['mark']} {r.get('conviction') or ''}".strip() if r.get("mark")
                                                       else {"wait": "⏳ वाट", "no_trade": "⛔ trade नाही"}.get(r["decision"], r["decision"]))
    lines = [head] + CH.story(r).splitlines()[:4]                       # 5–7 ओळी: शीर्षक + कथा ≤ 4 + B1/B2 + शेवटी disclaimer
    bp = b_plans(V, r)
    if bp:
        b2 = bp["B2"]
        lines.append(f"B1: close {bp['B1']['entry']:,.0f} वर · B2: {b2['trigger']:,.0f} break वर (R:R {b2['rr']}"
                     + ("" if b2["ok"] else " < 3 ⇒ B2 नाही") + ")")
    lines.append("Shadow / PAPER फक्त — AI order देत नाही")
    return "\n".join(lines)[:MAX_CAPTION]


def debug_view(r):
    """Debug (पाठवला जात नाही): checklist ①–⑦ + पुरावे + गहाळ."""
    return {"ts": r["ts"], "decision": r["decision"], "mark": r.get("mark"),
            "checklist": {k: v for k, v in r["checklist"].items()}, "evidence": r.get("evidence"), "missing": r.get("missing"),
            "conviction": r.get("conviction"), "conv_score": r.get("conv_score"), "risk": r.get("risk"),
            "trendline": r.get("trendline"), "liquidity": r.get("liquidity")}


def select(rows, moments=()):
    """पाठवायचे bars: सगळे setups + Abhi च्या खुणांचे दिवस (त्या दिवसाचा सर्वात पुढे गेलेला bar). क्रम वेळेनुसार, duplicate नाही."""
    pick = {r["bar"]: r for r in rows if r["decision"] == "setup"}
    keys = ("①", "②", "③", "④", "⑥", "⑦")
    for mstr in moments:
        day = pd.Timestamp(mstr).normalize()
        dr = [r for r in rows if pd.Timestamp(r["ts"]).normalize() == day]
        if dr and not any(r["bar"] in pick for r in dr):
            far = max(dr, key=lambda r: (sum(1 for k in keys if r["checklist"][k][0]), r["bar"]))
            pick[far["bar"]] = far
    return [pick[b] for b in sorted(pick)]


def build_run(V, rows, run_dir, symbol, run_id, moments=(), max_items=20):
    """run_dir मध्ये charts + manifest.json + debug.json. रिटर्न manifest dict."""
    os.makedirs(run_dir, exist_ok=True)
    items, dbg = [], []
    for n, r in enumerate(select(rows, moments)[:max_items], 1):
        t = int(r["bar"])
        st = DD.state_at(V.daily, V.bar_end[t])
        tag = r["ts"][:16].replace(" ", "_").replace(":", "")
        files = []
        if st.bar >= 0:
            f = f"{n:02d}_{tag}_daily.png"
            open(os.path.join(run_dir, f), "wb").write(CH.daily_png(V.daily_df, V.daily, symbol, upto=st.bar))
            files.append(f)
        f = f"{n:02d}_{tag}_1h.png"
        open(os.path.join(run_dir, f), "wb").write(CH.h1_png(V.levels, t, st.trend, symbol))
        files.append(f)
        f = f"{n:02d}_{tag}_15m.png"
        open(os.path.join(run_dir, f), "wb").write(CH.m15_png(V, t, symbol, r=r))
        files.append(f)
        cap = caption(V, r, symbol)
        items.append({"n": n, "date": r["ts"][:10], "item": f"{run_id}|v22:{symbol}:{r['ts'][:16]}", "reading": cap.splitlines()[0],
                      "caption": cap, "kind": "v22_check", "files": files})
        dbg.append(debug_view(r))
    if not items:
        return None
    for it in items:
        it["caption"] = it["caption"].replace("🧭 v2.2", f"🧭 v2.2 {it['n']}/{len(items)}", 1)[:MAX_CAPTION]
    man = {"run_id": run_id, "title": f"v2.2 {symbol}", "items": items}
    with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(run_dir, "debug.json"), "w", encoding="utf-8") as fh:
        json.dump(dbg, fh, ensure_ascii=False, indent=1, default=str)
    return man
