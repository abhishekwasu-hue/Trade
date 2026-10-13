"""scripts/golden_story_check.py — R3 Chart Story golden cases (design §11.1; vision/story.py). **SHADOW — no order, no rule change.**

Abhi VPS वर चालवतो (VPS चा key; sandbox मध्ये कधीच API call नाही). प्रत्येक केस (private trade-data `golden_story/cases.json` — तारखा,
data paths आणि Abhi च्या अपेक्षा फक्त तिथे; repo / pack / prompt मध्ये कधीच नाहीत):
  data (policy guard: sealed holdout कधीच load नाही) ⇒ spot 1m (+ 1m नसलेल्या दिवसाचे 5M spot) आणि near-month FUT 5M ⇒ as-of ला कापलेले
  बंद bars ⇒ anonymise (golden_vision_check चाच) ⇒ vision.story.prepare (dossier + facts + images) ⇒ story call (role नुसार model)
  ⇒ validate (schema, facts मधल्या किंमती, cites) ⇒ Abhi च्या अपेक्षांशी तुलना. प्रत्येक निकाल **PROVISIONAL**.

    cd /root/Trade && set -a && . ./.env && set +a
    python3 scripts/golden_story_check.py --dry-run          # images + facts + token / $ अंदाज, API call नाही
    python3 scripts/golden_story_check.py                    # खरा run ⇒ trade-data/review/golden_story/run1/

Paths: trade-data root = env TRADE_DATA / TRADE_DATA_DIR, नाहीतर repo शेजारचा trade-data, /root/trade-data, /home/user/trade-data;
cases मधले data paths या root शी relative. Outputs (private trade-data फक्त): <out>/<case>/ facts.json, prompt_user.txt, input_*.png,
story.json, story_mr.txt, compare.json, cost.txt + <out>/summary.json. खर्च vision_usage मध्ये task "chart_story" (cached / uncached).
"""
import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts import golden_vision_check as GV   # noqa: E402
from vision import checklist as CK               # noqa: E402
from vision import method_pack as MP             # noqa: E402
from vision import story as ST                   # noqa: E402

PROVISIONAL = "PROVISIONAL"
CASE_KEYS = ("id", "symbol", "as_of", "read", "role", "data")             # prompt बांधायला फक्त हे; expected / notes कधीच नाहीत


def trade_data_root():
    for env in ("TRADE_DATA", "TRADE_DATA_DIR"):
        v = (os.environ.get(env) or "").strip()
        if v and os.path.isdir(v):
            return v
    for p in (os.path.join(os.path.dirname(ROOT), "trade-data"), "/root/trade-data", "/home/user/trade-data",
              os.path.expanduser("~/trade-data")):
        if os.path.isdir(p):
            return p
    return os.path.join(os.path.dirname(ROOT), "trade-data")


def _paths(td, xs):
    return [x if os.path.isabs(x) else os.path.join(td, x) for x in xs or []]


# ----------------------------------------------------------------------------------------------------------- data
def _bars(df, minutes):
    """NSE 09:15-anchored resample (opportunity_engine.sessions.resample_nse) with decision3's CAS policy (market_state.core.frame /
    pivots.engine.bars_15m: CAS setting, closing-auction bars dropped), only closed bars — facts match the engine."""
    from opportunity_engine import sessions as OS
    if df is None or not len(df):
        return pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close"])
    r = OS.resample_nse(df[["timestamp", "open", "high", "low", "close"]], minutes, cas=None)
    r = r[r["bar_closed"].astype(bool)]
    return r[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


def assemble(m1, s5):
    """Spot inputs for vision.story.prepare: 1m जिथे आहे तिथे 1m वरून 5M / 15M; 1m नसलेले दिवस 5M spot export वरून. "1m" slot = 1m rows
    (bar_end + 1 min) + त्या दिवसांचे 5M rows (bar_end + 5 min) — फक्त context / gap owners साठी (open, opening range, PDH / PDL)."""
    m1 = m1 if m1 is not None else pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])
    days1 = set(pd.to_datetime(m1["timestamp"]).dt.normalize().unique())
    s5x = None
    if s5 is not None and len(s5):
        s5x = s5[~pd.to_datetime(s5["timestamp"]).dt.normalize().isin(days1)].reset_index(drop=True)
    m15 = pd.concat([_bars(m1, 15), _bars(s5x, 15)], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    f5 = pd.concat([_bars(m1, 5), _bars(s5x, 5)], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    one = m1[["timestamp", "open", "high", "low", "close"]].assign(bar_end=pd.to_datetime(m1["timestamp"]) + pd.Timedelta(minutes=1))
    if s5x is not None and len(s5x):
        one = pd.concat([one, s5x[["timestamp", "open", "high", "low", "close"]].assign(
            bar_end=pd.to_datetime(s5x["timestamp"]) + pd.Timedelta(minutes=5))], ignore_index=True)
    note = None
    if s5x is not None and len(s5x):                                        # तारीख नाही (anonymised prompt मध्ये खरी तारीख गळू नये)
        n = pd.to_datetime(s5x["timestamp"]).dt.normalize().nunique()
        note = (f"{n} session(s) have no 1m data: their 15M / 5M bars, open and opening range come from 5M spot bars")
    return {"15M": m15, "5M": f5, "1m": one.sort_values("timestamp").reset_index(drop=True)}, note


def load_case(case, td):
    """Case ⇒ (bars_by_tf (real), fut5 (real), note). Policy: GV.load_data (holdout file नकार + holdout rows filter), FUT GV.load_futures."""
    d = case.get("data") or {}
    m1 = GV.load_data(_paths(td, d.get("spot_1m"))) if d.get("spot_1m") else None
    s5 = GV.load_data(_paths(td, d.get("spot_5m"))) if d.get("spot_5m") else None
    bars, note = assemble(m1, s5)
    fut = GV.load_futures(_paths(td, d.get("fut_5m")))
    return bars, fut, note


def anon_of(a):
    return {"shift_weeks": a.shift_weeks, "scale": a.scale, "tick": a.tick}


# ----------------------------------------------------------------------------------------------------------- compare (after the call)
def _get(d, path):
    x = d
    for k in path.split("."):
        x = (x or {}).get(k) if isinstance(x, dict) else None
    return x


def _real_prices(text, scale):
    return [v / scale for v, _, _ in CK.numbers(str(text).translate(ST._DEV))]


def _part_texts(data, where):
    out = []
    for p in where:
        x = data.get(p)
        if isinstance(x, dict):
            out += [str(v) for k, v in x.items() if k not in ("facts",) and isinstance(v, str)]
            for z in x.get("items") or []:
                out += [z.get("zone", ""), z.get("far_side_swing", "")]
        elif isinstance(x, str):
            out.append(x)
    return out


def check(data, c, scale, tol):
    """One expectation ⇒ (got, mark). mark ✔ / ✘ / REVIEW (Abhi reads it) / — (no story)."""
    kind = c.get("kind")
    if kind == "manual":
        return "see story", "REVIEW"
    if not data:
        return None, "—"
    if kind == "field":
        g = _get(data, c["path"])
        return g, "✔" if g in c["in"] else "✘"
    if kind == "not_setup":
        sr = data["setup_read"]
        g = f"{sr['decision']} / {sr['side']}"
        return g, "✘" if (sr["decision"] == "setup" and sr["side"] == c["side"]) else "✔"
    if kind == "zone":
        lo, hi = sorted(c["range"])
        for z in data["zones"]["items"]:
            ps = _real_prices(z["zone"], scale)
            if z["state"] == c["state"] and z["role"] == c["role"] and ps and min(ps) <= hi + tol and max(ps) >= lo - tol:
                return f"{z['state']} {z['role']} {z['zone']}", "✔"
        return "; ".join(f"{z['state']} {z['role']} {z['zone']}" for z in data["zones"]["items"]) or "no zones", "✘"
    if kind == "price":
        vals = [v for t in _part_texts(data, c.get("where") or ST.PARTS) for v in _real_prices(t, scale)]
        hit = [v for v in vals if any(abs(v - x) <= tol for x in c["values"])]
        return (f"{hit[0]:,.2f} (real)" if hit else "not mentioned"), ("✔" if hit else "✘")
    return None, "?"


def compare(data, case, scale):
    tol = float(case.get("price_tol", 15.0))
    rows = []
    for c in case.get("checks") or []:
        got, mark = check(data, c, scale, tol)
        rows.append({"id": c.get("id"), "what": c.get("what"), "got": got, "mark": mark, "label": PROVISIONAL})
    return rows


# ----------------------------------------------------------------------------------------------------------- run
def _save(cdir, name, data, mode="w"):
    with open(os.path.join(cdir, name), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        fh.write(data)


def run_case(case, a, deps, state, td):
    rec = {"id": case.get("id"), "label": PROVISIONAL, "case_status": case.get("status"), "read": case.get("read")}
    try:
        role = ST.role_of(case["read"], case.get("role"))
    except (KeyError, ValueError) as exc:
        rec.update(status="BAD_CASE", why=str(exc))
        return rec
    as_of = pd.Timestamp(case["as_of"])
    try:
        deps["guard"](as_of)
    except Exception as exc:                                               # noqa: BLE001 — HoldoutError / अवैध तारीख
        rec.update(status="REFUSED_POLICY", why=str(exc))
        return rec
    model = a.model or ST.model_for(role, state.get("g"))[0]
    rec.update(role=role, model=model)
    bars, fut, note = deps["load"]({k: case.get(k) for k in CASE_KEYS}, td)
    prep = deps["prepare"](bars, fut, as_of, case["read"], anon=anon_of(a), meta_extra={"data_note": note} if note else None,
                           symbol=str(case.get("symbol") or "INDEX").upper(), hide=(str(case.get("symbol") or ""),))
    pack = deps["pack"]()
    est = ST.estimate(len(prep["images"]), prep["text"], pack[0], model, a.max_tokens)
    rec.update(n_images=len(prep["images"]), pack_version=pack[1], estimate=est, anon_as_of=str(prep["as_of"]),
               last_bar=prep["facts"]["meta"]["last_closed_15m_bar"])
    cdir = os.path.join(a.out_dir, str(case["id"]))
    os.makedirs(cdir, exist_ok=True)
    _save(cdir, "facts.json", json.dumps(prep["facts"], ensure_ascii=False, indent=1, default=str))
    _save(cdir, "prompt_user.txt", prep["text"])
    for name, png in prep["images"]:
        _save(cdir, f"input_{name}.png", png, "wb")
    if a.dry_run:
        rec["status"] = "DRY_RUN"
        rec["compare"] = compare(None, case, a.scale)
        return rec
    ok, why = ST.budget_ok(est["usd_uncached"], state["g"], state["by_task"], state["today"])
    if not ok:
        rec.update(status="NOT_RUN_BUDGET", why=why)
        return rec
    res = ST.run(deps["client"](), prep, model, pack=pack, on_usage=deps["on_usage"](model, pack[1]), max_tokens_=a.max_tokens,
                 effort=deps["effort"](), thinking=deps["thinking"]())
    d, m, n = state["by_task"].get(ST.TASK, (0.0, 0.0, 0))
    c = res.get("cost_usd") or 0.0
    state["by_task"][ST.TASK] = (d + c, m + c, n + 1)
    rec.update(status=res["status"].upper(), error=res.get("error"), cost_usd=c, usage=res.get("usage"), cost_line=ST.cost_line(res))
    story = {"label": PROVISIONAL, "status": res["status"], "model": model, "role": role, "pack_version": pack[1],
             "prompt_version": ST.PROMPT_VERSION, "data": res.get("data"), "error": res.get("error")}
    if res.get("status") != "done":
        story["raw_text"] = res.get("raw_text")                            # नाकारलेलं उत्तर नोंदीत (कधीच शांत accept नाही)
    _save(cdir, "story.json", json.dumps(story, ensure_ascii=False, indent=1))
    if res.get("data"):
        _save(cdir, "story_mr.txt", f"[{PROVISIONAL}]\n" + ST.telegram_text(res["data"], title=str(case["id"])) + "\n")
    _save(cdir, "cost.txt", rec["cost_line"] + "\n")
    rec["compare"] = compare(res.get("data"), case, a.scale)
    _save(cdir, "compare.json", json.dumps(rec["compare"], ensure_ascii=False, indent=1, default=str))
    return rec


def print_case(rec, out=print):
    out(f"\n=== {rec['id']} · {rec.get('status')} · {PROVISIONAL} (shadow; Abhi decides) ===")
    for k in ("why", "error", "role", "model", "anon_as_of", "last_bar", "cost_line"):
        if rec.get(k):
            out(f"  {k}: {rec[k]}")
    e = rec.get("estimate")
    if e:
        out(f"  tokens: system ≈ {e['system_tokens']:,} (cached prefix) + fresh ≈ {e['fresh_input_tokens']:,} ({rec['n_images']} images)"
            f" + output ≤ {e['max_output_tokens']:,}")
        out(f"  cost est.: uncached ${e['usd_uncached']:.4f} · first call (cache write) ${e['usd_cache_write']:.4f} · cached "
            f"${e['usd_cached']:.4f}" + ("" if rec.get("model") else "  (model not set ⇒ conservative unknown-model prices)"))
    for r in rec.get("compare") or []:
        out(f"  [{r['mark']}] {r['id']}: {r['what']} · got {r['got']} ({PROVISIONAL})")


def default_deps(a):
    from vision import config as VC

    def client():
        import anthropic
        return anthropic.Anthropic(timeout=600.0, max_retries=0)           # retry नाही ⇒ दुहेरी billing नाही

    def on_usage(model, ver):
        from vision import store as VS
        return lambda u, c: VS.add_usage(ST.TASK, model, u, c, pack_version=ver)
    return {"guard": GV.guard, "load": load_case, "prepare": ST.prepare, "pack": MP.load, "client": client, "on_usage": on_usage,
            "effort": lambda: VC.env_effort("story"), "thinking": lambda: VC.env_thinking("story")}


def main(argv=None, deps=None, out=print):
    td = trade_data_root()
    ap = argparse.ArgumentParser(description="Chart Story golden cases (SHADOW; results PROVISIONAL)")
    ap.add_argument("--cases", default=os.path.join(td, "golden_story", "cases.json"), help="private cases JSON (trade-data)")
    ap.add_argument("--only", nargs="+", help="फक्त हे case ids")
    ap.add_argument("--out-dir", default=None, help="default: trade-data review/golden_story/run1 (dry-run: …/dryrun)")
    ap.add_argument("--model", default=None, help="role setting / env ऐवजी (उदा. एकदाच वेगळा model)")
    ap.add_argument("--max-tokens", type=int, default=None, help="default env VISION_STORY_MAX_TOKENS किंवा vision.story.MAX_TOKENS")
    ap.add_argument("--shift-weeks", type=int, default=GV.SHIFT_WEEKS)
    ap.add_argument("--scale", type=float, default=GV.SCALE)
    ap.add_argument("--tick", type=float, default=GV.TICK)
    ap.add_argument("--dry-run", action="store_true", help="API call नाही — images + facts + token / $ अंदाज")
    a = ap.parse_args(argv)
    a.max_tokens = a.max_tokens or ST.max_tokens()
    a.out_dir = a.out_dir or os.path.join(td, "review", "golden_story", "dryrun" if a.dry_run else "run1")
    deps = {**default_deps(a), **(deps or {})}
    state = {"by_task": {}, "g": None, "today": None}
    if not a.dry_run:
        from vision import config as VC
        from vision import store as VS
        if not VC.api_key_present():
            out("⛔ API key env मध्ये नाही (VPS: set -a && . ./.env && set +a)")
            return 1
        now = VS.now_ist()
        state.update(by_task=dict(VS.spent_by_task()), g=VC.load("_global"),
                     today=now.replace(tzinfo=None) if getattr(now, "tzinfo", None) else now)
    cases = json.load(open(a.cases, encoding="utf-8"))["cases"]
    if a.only:
        cases = [c for c in cases if c.get("id") in a.only]
    if not a.dry_run:
        for c in cases:
            role = ST.role_of(c["read"], c.get("role"))
            if not (a.model or ST.model_for(role, state["g"])[0]):
                out(f"⛔ {c.get('id')}: model for role '{role}' — {ST.model_for(role, state['g'])[1]}")
                return 1
    os.makedirs(a.out_dir, exist_ok=True)
    recs = []
    for c in cases:
        try:
            r = run_case(c, a, deps, state, td)
        except Exception as exc:                                           # noqa: BLE001 — एका केसची चूक बाकी थांबवत नाही
            r = {"id": c.get("id"), "status": "ERROR", "error": f"{type(exc).__name__}: {str(exc)[:300]}", "label": PROVISIONAL}
        recs.append(r)
        print_case(r, out)
    json.dump(recs, open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    est = [r["estimate"] for r in recs if r.get("estimate")]
    first = sum(e["usd_cache_write"] for e in est[:1]) + sum(e["usd_cached"] for e in est[1:])
    spent = sum(r.get("cost_usd") or 0.0 for r in recs)
    out(f"\nCases {len(recs)} · est. total: uncached ${sum(e['usd_uncached'] for e in est):.4f} · with the pack cached after the first "
        f"call ${first:.4f}" + ("" if a.dry_run else f" · spent ${spent:.4f}") + f" · all results {PROVISIONAL} · out {a.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
