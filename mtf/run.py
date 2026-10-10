"""mtf/run.py — एका नमुना-दिवसाचे 8 images (W / D / 1H / 15M × (अ) रचना, (आ) entry) + caption + manifest item.

Caption (≤ 1024 UTF-16): शीर्षक · top-down (4 ओळी, ⚠ + कारण) · B1 यादी · B2 योजना. Telegram: एक संदेश = एक media group
(backtest_review.telegram, caption पहिल्या image वर). पाठवणं फक्त VPS वरून.
"""
import json
import os

import pandas as pd

import instruments as INS
from elliott import data_policy as DP
from pivots import charts as PC
from review7 import charts as RC
from review7 import settings as RS

from . import adapter as MA
from . import charts as MC
from .adapter import TFS

MAX_CAPTION = RC.MAX_CAPTION


def _short(mk, tf):
    a = mk["area"]
    ar = (f"zone{'★' * a['stars']}" + ("·self" if a["self"] else "")) if a["kind"] == "zone" else "रेघ"
    return f"{mk['type']} {pd.Timestamp(mk['real_ts']).strftime(MC.FMT[tf])} {mk['side']} {ar} ④{'+'.join(mk['c4']) or '—'}"


def caption(asof, td, per_tf, plan_tf="15M", n_img=8):
    """शीर्षक · top-down 4 ओळी (+ ⚠ कारण) · B1 · B2 (plan_tf, नसेल तर 1H)."""
    lines = [f"🗺 MTF CHECK · {INS.label()} · {pd.Timestamp(asof):%d %b %Y %H:%M} पर्यंत · {n_img} images (अ रचना · आ entry)"]
    for r in td["rows"]:
        if "na" in r:
            lines.append(f"{r['tf']}: — ({r['na']})")
        else:
            lines.append(f"{r['tf']}: {MC.ARROW.get(r['trend'], '?')} " + (f"D{r['deg']} " if r["deg"] else "") + f"{MC.TREND_MR.get(r['trend'], r['trend'])}"
                         f" · {r['state']}")
    lines += td["warn"][:2]
    b1 = []
    for tf in TFS:
        x = per_tf.get(tf)
        if x is None:
            continue
        mk = x["marks"]
        b1.append(f"{tf} ✅{sum(m['type'] == '✅' for m in mk)} 🟡{sum(m['type'] == '🟡' for m in mk)}")
    lines.append("B1 (chart खिडकीत): " + (" · ".join(b1) or "—"))
    for tf in ("15M", "1H"):
        x = per_tf.get(tf)
        for m in ((x or {}).get("marks") or [])[-2:]:
            lines.append("• " + _short(m, tf))
    ptf = plan_tf if per_tf.get(plan_tf) else "1H"
    pl = (per_tf.get(ptf) or {}).get("plan") or {}
    lines.append(f"B2 ({ptf}): {MC.ARROW.get(pl.get('trend'), '?')} D{pl.get('deg') or '—'} · regime {pl.get('regime') or '—'}")
    for k, it in enumerate((pl.get("items") or [])[:3], 1):
        tg = "—" if it.get("target") is None else f"{it['target']:,.0f}"
        lines.append(f"{k}) {it['side']} {it['bot']:,.0f}–{it['top']:,.0f} · SL {it['sl']:,.0f} · लक्ष्य {tg} · R:R {it.get('rr') or '—'}")
    if not pl.get("items"):
        lines.append("— area नाही ⇒ वाट")
    if pl.get("invalid"):
        lines.append(f"बाद: {pl['invalid']}")
    lines.append("Reply: ✔ बरोबर · ✘ कोणती TF / संकल्पना चुकली")
    out = "\n".join(lines)
    while RC.u16(out) > MAX_CAPTION and len(lines) > 6:
        lines.pop(-2)
        out = "\n".join(lines)
    while RC.u16(out) > MAX_CAPTION:
        out = out[:-1]
    return out


def display_frame(d, tf, asof):
    """display candles: फक्त asof पर्यंत **बंद** झालेल्या (real_end ≤ asof) आणि holdout instrument साठी फक्त holdout नंतरच्या."""
    ts = pd.to_datetime(d["timestamp"])
    keep = (MA.real_end(ts, tf) <= pd.Timestamp(asof)).to_numpy()
    if INS.holdout():
        keep = keep & (ts >= DP.CONTAMINATED_START).to_numpy()
    return d[keep].reset_index(drop=True)


def run_day(Cs, asof, cfg, out_dir, display=None, s=None):
    """Cs = {tf: C | None}; display = {tf: df} (NIFTY W / D राखाडी). रिटर्न {"files", "caption", "summary"}."""
    s = s or RS.load()
    os.makedirs(out_dir, exist_ok=True)
    td = MC.topdown(Cs, asof)
    files, per_tf = [], {}
    for tf in TFS:
        C = Cs.get(tf)
        if C is None:
            if display is not None and display.get(tf) is not None:
                d = display_frame(display[tf], tf, asof)
                if not len(d):
                    continue
                fn = f"{tf}_display.png"
                open(os.path.join(out_dir, fn), "wb").write(PC.png(MC.display_fig(d, tf, MC.title(tf, "अ", asof).replace("(अ) रचना", "display-only"))))
                files.append(fn)
            continue
        t = MC._bar_at(C, asof)
        if t is None:
            continue
        up = MC.upper_ctx(Cs.get(MC.UPPER.get(tf)), asof, cfg) if MC.UPPER.get(tf) else None
        marks, pl, cache = MC.tf_review(C, t, cfg, s)
        for m in marks:
            m["ts"] = m["real_ts"] = str(C.real_ts[m["bar"]])                  # कृत्रिम session वेळ नाही — खरी वेळ
            m["real_known_at"] = None if m["known_at"] is None else str(C.real_end[m["known_at"]])
        per_tf[tf] = {"t": t, "real_ts": str(C.real_ts[t]), "marks": marks, "plan": pl}
        fa = MC.structure_fig(C, t, cfg, td, up, MC.title(tf, "अ", asof, C.real_ts[t]))
        fb = MC.entry_fig(C, t, cfg, marks, pl, cache, td, up, MC.title(tf, "आ", asof, C.real_ts[t]), s)
        for fig, nm in ((fa, f"{tf}_a.png"), (fb, f"{tf}_b.png")):
            open(os.path.join(out_dir, nm), "wb").write(PC.png(fig))
            files.append(nm)
    cap = caption(asof, td, per_tf, n_img=len(files))
    summary = {"asof": str(asof), "instrument": INS.label(), "topdown": td, "tf": per_tf, "files": files}
    json.dump(summary, open(os.path.join(out_dir, "mtf_day.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    open(os.path.join(out_dir, "caption.txt"), "w", encoding="utf-8").write(cap)
    return {"files": files, "caption": cap, "summary": summary}
