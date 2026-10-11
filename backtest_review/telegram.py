"""backtest_review/telegram.py — review charts (K-10, Golden Gallery, backtest visual review) Telegram वर, आणि Abhi चे replies नोंद.

  Charts + manifest फक्त private trade-data मध्ये (`review/<kind>/<run_id>/manifest.json`); पाठवणं फक्त VPS वरून (token तिथल्या .env मध्ये,
  `notifications` च्याच credentials — कधीच print नाही). Approve बटण नाही.
  Manifest: {"run_id", "title" (उदा. "K-10"), "items": [{"n", "date", "item", "reading" (एक ओळ), "files": [1–10]}]}. `item` = backtest_review
  मधला item_id जसाच्या तसा (backtest review run ⇒ "day:YYYY-MM-DD" / "trade:…" — page शी जुळतो; K-10 ⇒ "k10/run1|day:…" — rounds वेगळे).
  Caption = "🔎 {title} {unit (default दिवस)} n/N · date" + reading. Images = एक media group (caption पहिल्या image वर).
  Sent log (VPS local JSON, `REVIEW_TG_SENT_PATH`, default data/review_tg_sent.json): {run_id|item: {message_ids, date, item, run_id}} —
  आधी पाठवलेलं पुन्हा नाही; listener (vision/telegram_bot) reply चा message_id इथून ओळखतो.
  Item मध्ये "caption" असेल तर तोच (vision_test); "kind" sent log मध्ये ⇒ reply त्याच प्रकाराने नोंद.
  Reply (फक्त approver): "✔ …" ⇒ OK · "✘ कारण" ⇒ WRONG · "?" ⇒ UNCLEAR · "सुटलेला trade 13:30 bear" ⇒ missed (verdict नसेल तर WRONG).
  नोंद = `backtest_review` (item_id = manifest item, item_type day / trade, review_date, verdict, reason, missed_trade, settings_hash = run)
  ⇒ bot "नोंद ✓". Telegram चुका: 429 ⇒ retry_after थांबून तेच पुन्हा; 400 / 413 (size / dims) ⇒ लहान करून एकदा; network ⇒ पुन्हा नाही
  (duplicate album टाळा — पुढच्या run मध्ये). Sent log खराब ⇒ sender थांबतो (सगळं पुन्हा पाठवत नाही).
"""
import io
import json
import os
import re
import time

SENT_ENV = "REVIEW_TG_SENT_PATH"
MAX_CAPTION = 1024
MAX_READING = 800                    # Telegram caption मर्यादा UTF-16 units मध्ये — reading इतक्या अक्षरांत
MAX_FILES = 10                       # media group मर्यादा
VS16 = "\ufe0f"
OK_MARKS = ("✔", "✅", "✓", "👍")
BAD_MARKS = ("✘", "✗", "❌", "✖", "👎")


class NoCredentials(RuntimeError):
    """Token / chat id नाही (संदेशात token कधीच नाही)."""


# ---------------------------------------------------------------------------------------------------------------- manifest
def load_manifest(run_dir):
    """manifest.json वाचा आणि तपासा ⇒ dict. चूक ⇒ ValueError (कारणासह)."""
    p = os.path.join(run_dir, "manifest.json")
    m = json.load(open(p, encoding="utf-8"))
    for k in ("run_id", "title", "items"):
        if k not in m:
            raise ValueError(f"manifest मध्ये '{k}' नाही")
    if not isinstance(m["items"], list) or not m["items"]:
        raise ValueError("manifest items रिकामे")
    for i, it in enumerate(m["items"]):
        for k in ("date", "item", "reading", "files"):
            if k not in it:
                raise ValueError(f"item {i}: '{k}' नाही")
        if not isinstance(it["files"], list) or not 1 <= len(it["files"]) <= MAX_FILES:
            raise ValueError(f"item {i} ({it['date']}): files 1–{MAX_FILES} हव्यात")
        missing = [f for f in it["files"] if not os.path.exists(os.path.join(run_dir, f))]
        if missing:
            raise ValueError(f"item {i} ({it['date']}): files नाहीत {missing}")
        digests = [_sha(os.path.join(run_dir, f)) for f in it["files"]]
        if len(set(it["files"])) != len(it["files"]) or len(set(digests)) != len(digests):
            raise ValueError(f"item {i} ({it['date']}): album मध्ये एकच chart दोनदा — पाठवत नाही")
        it.setdefault("n", i + 1)
    return m


def _sha(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def _kind(b):
    """bytes ⇒ (extension, mime): shrink नंतर JPEG असतो."""
    return ("jpg", "image/jpeg") if b[:3] == b"\xff\xd8\xff" else ("png", "image/png")


def caption(m, it):
    if it.get("caption"):                                                   # item चा स्वतःचा caption (उदा. vision_test) — तसाच
        return str(it["caption"])[:MAX_CAPTION]
    return (f"🔎 {m['title']} {m.get('unit') or 'दिवस'} {it['n']}/{len(m['items'])} · {it['date']}\n{str(it['reading'])[:MAX_READING]}\n"
            "Reply: ✔ / ✘ कारण / सुटलेला trade HH:MM bear|bull")


# ---------------------------------------------------------------------------------------------------------------- sent log
def sent_path(path=None):
    return path or os.environ.get(SENT_ENV) or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
                                                             "review_tg_sent.json")


def load_sent(path=None, strict=False):
    """strict (sender) ⇒ खराब file वर ValueError (सगळं पुन्हा पाठवू नये); listener ⇒ {}."""
    p = sent_path(path)
    try:
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    except (OSError, ValueError) as exc:
        if strict:
            raise ValueError(f"sent log {p} वाचता येत नाही ({type(exc).__name__}) — दुरुस्त करा / हलवा") from exc
        return {}


def _save_sent(log, path=None):
    p = sent_path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def key(run_id, item):
    return f"{run_id}|{item}"


def lookup_message(message_id, path=None):
    """reply_to message_id ⇒ sent log नोंद (run_id, item, date) किंवा None."""
    for v in load_sent(path).values():
        if int(message_id) in [int(x) for x in v.get("message_ids") or []]:
            return v
    return None


# ---------------------------------------------------------------------------------------------------------------- sending
def shrink(png, factor=0.6):
    """Telegram ने नाकारलं ⇒ लहान (PIL) PNG→JPEG. PIL नसेल ⇒ मूळ bytes."""
    try:
        from PIL import Image
    except ImportError:                                                     # pragma: no cover
        return png
    try:
        im = Image.open(io.BytesIO(png)).convert("RGB")
    except OSError:
        return png
    im = im.resize((max(1, int(im.width * factor)), max(1, int(im.height * factor))))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue()


def raw_call(creds):
    """Telegram call जे error_code / retry_after सुद्धा परत देतं (vision.tg._call फक्त None देतो). Network चूक ⇒ None. Token print नाही."""
    import requests

    def call(method, data=None, files=None, timeout=60):
        tok = creds()[0]
        try:
            r = requests.post(f"https://api.telegram.org/bot{tok}/{method}", data=data, files=files, timeout=timeout)
            return r.json()
        except (requests.RequestException, ValueError):
            return None
    return call


def _media_group(call, chat_id, imgs, cap):
    """रिटर्न (message_ids | None, Telegram JSON | None)."""
    if len(imgs) == 1:
        ext, mime = _kind(imgs[0])
        j = call("sendPhoto", {"chat_id": chat_id, "caption": cap}, {"photo": (f"a.{ext}", imgs[0], mime)}, timeout=90)
        return ([j["result"]["message_id"]] if j and j.get("ok") else None), j
    media = [{"type": "photo", "media": f"attach://img{i}"} for i in range(len(imgs))]
    media[0]["caption"] = cap
    files = {f"img{i}": (f"img{i}.{_kind(b)[0]}", b, _kind(b)[1]) for i, b in enumerate(imgs)}
    j = call("sendMediaGroup", {"chat_id": chat_id, "media": json.dumps(media)}, files, timeout=120)
    return ([r["message_id"] for r in j["result"]] if j and j.get("ok") else None), j


def _send_item(call, cid, imgs, cap, sleep, max_429=3):
    """429 ⇒ retry_after थांबून तेच; 400 / 413 ⇒ एकदा लहान; network (None) ⇒ पुन्हा नाही. रिटर्न (ids | None, कारण)."""
    shrunk = False
    for _ in range(max_429 + 2):
        ids, j = _media_group(call, cid, imgs, cap)
        if ids:
            return ids, "ok"
        if j is None:
            return None, "network (Telegram पर्यंत पोचलं का अनिश्चित — duplicate टाळायला पुन्हा नाही)"
        code = j.get("error_code")
        if code == 429:
            sleep(float((j.get("parameters") or {}).get("retry_after") or 5) + 1)
            continue
        if code in (400, 413) and not shrunk:
            imgs, shrunk = [shrink(b) for b in imgs], True
            continue
        return None, f"Telegram {code}: {str(j.get('description'))[:120]}"
    return None, "429 वारंवार"


def send_document(path, cap, run_key, call=None, creds=None, sent=None):
    """एक file (उदा. PDF अहवाल) Telegram document म्हणून — एकदाच (sent log key `run_key|doc:<नाव>`). रिटर्न "sent" / "skipped" / कारण."""
    if creds is None:
        from vision import tg as TG
        creds = TG._creds
    tok, cid = creds()
    if not tok or not cid:
        raise NoCredentials("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID .env मध्ये नाहीत — काहीच पाठवलं नाही")
    call = call or raw_call(creds)
    log = load_sent(sent, strict=True)
    k = key(run_key, f"doc:{os.path.basename(path)}")
    if k in log:
        return "skipped"
    with open(path, "rb") as fh:
        j = call("sendDocument", {"chat_id": cid, "caption": cap[:1024]}, {"document": (os.path.basename(path), fh.read(), "application/pdf")},
                 timeout=180)
    if j is None:                                                           # network: पोचलं का अनिश्चित ⇒ पुन्हा पाठवायचं नाही (duplicate टाळा)
        log[k] = {"run": run_key, "item": f"doc:{os.path.basename(path)}", "message_ids": [], "kind": "document", "uncertain": True}
        _save_sent(log, sent)
        return "network (अनिश्चित — पुन्हा पाठवत नाही; sent log मधून नोंद काढल्यासच पुन्हा)"
    if not j.get("ok"):
        return f"Telegram {j.get('error_code')}"
    log[k] = {"run": run_key, "item": f"doc:{os.path.basename(path)}", "message_ids": [j["result"]["message_id"]], "kind": "document"}
    _save_sent(log, sent)
    return "sent"


def send_run(run_dir, call=None, creds=None, sent=None, pause_s=3.0, sleep=time.sleep, dry_run=False, run_key=None, auditor=None):
    """manifest मधले न पाठवलेले items पाठवा. रिटर्न {"sent": n, "skipped": n, "failed": [(date, कारण)]} + "audits": […] (फक्त v2.2 audit झाले तर).
    auditor(run_dir, item) ⇒ decision3.vision_audit dict (v2.2 items, kind "v22…"): Telegram **आधी** audit; caption मध्ये audit ओळ,
    media group नंतर "Vision report" reply. Audit अपयश / budget संपला ⇒ chart तरीही जातो (caption मध्ये तसं).
    run_key = sent log मधली run ओळख (default manifest run_id; script ⇒ --run path). call(method, data, files, timeout) ⇒ Telegram JSON
    (ok false सुद्धा) | None (network); creds() ⇒ (token, chat_id) — default notifications credentials."""
    m = load_manifest(run_dir)
    run_key = run_key or m["run_id"]
    if creds is None:
        from vision import tg as TG
        creds = TG._creds
    tok, cid = creds()
    if not dry_run and (not tok or not cid):
        raise NoCredentials("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID .env मध्ये नाहीत — काहीच पाठवलं नाही")
    call = call or raw_call(creds)
    log = load_sent(sent, strict=True)
    out = {"sent": 0, "skipped": 0, "failed": []}
    for it in m["items"]:
        k = key(run_key, it["item"])
        if k in log:
            out["skipped"] += 1
            continue
        cap = caption(m, it)
        aud = None
        if auditor is not None and str(it.get("kind") or "").startswith("v22") and not dry_run:
            from decision3 import vision_audit as VA
            try:
                aud = auditor(run_dir, it)                                  # chart → Vision audit → Telegram
            except Exception as exc:                                        # noqa: BLE001 — audit अपयश chart अडवत नाही (Abhi)
                aud = {"status": "failed", "why": f"auditor {type(exc).__name__}", "verdict": None, "sections": {}, "issues": [],
                       "cost_usd": 0.0, "item": it["item"], "chart": it["files"][0]}
            cap = VA.with_audit_line(cap, VA.caption_line(aud))
            out.setdefault("audits", []).append(aud)
        elif str(it.get("kind") or "").startswith("v22") and not dry_run:   # audit बंद ⇒ caption मध्ये स्पष्ट
            from decision3 import vision_audit as VA
            cap = VA.with_audit_line(cap, "Vision audit skipped: off")
        if dry_run:
            print(f"[dry-run] {cap.splitlines()[0]} · {len(it['files'])} images")
            out["sent"] += 1
            continue
        imgs = [open(os.path.join(run_dir, f), "rb").read() for f in it["files"]]
        ids, why = _send_item(call, cid, imgs, cap, sleep)
        if ids is None:
            out["failed"].append((it["date"], why))
        else:
            log[k] = {"run": run_key, "item": it["item"], "date": it["date"], "message_ids": ids, "kind": it.get("kind"),
                      "files": it["files"], "sha": [_sha(os.path.join(run_dir, f)) for f in it["files"]]}
            if aud is not None:                                              # Vision report = chart चा reply (वेगळा संदेश)
                from decision3 import vision_audit as VA
                j = call("sendMessage", {"chat_id": cid, "text": VA.report_text(aud, cap.splitlines()[0]),
                                         "reply_to_message_id": ids[0]}, None, timeout=30)
                log[k]["vision_report_ok"] = bool(j and j.get("ok"))
                if not log[k]["vision_report_ok"]:                          # chart गेला, report नाही ⇒ गुपचूप नाही
                    out["failed"].append((it["date"], f"Vision report reply: {(j or {}).get('error_code', 'network')}"))
            _save_sent(log, sent)
            out["sent"] += 1
        sleep(pause_s)                                                      # rate limit: संदेशांमध्ये विराम
    return out


# ---------------------------------------------------------------------------------------------------------------- replies
_TIME_SIDE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*(bear|bull|sell|buy|short|long)\b", re.I)
_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_BEAR = re.compile(r"\b(bear|sell|short)\b", re.I)
_BULL = re.compile(r"\b(bull|buy|long)\b", re.I)
SIDE_OF = {"bear": "bear_call", "sell": "bear_call", "short": "bear_call", "bull": "bull_put", "buy": "bull_put", "long": "bull_put"}


def _in_session(h, m):
    return (9, 15) <= (h, m) <= (15, 30)


def parse_reply(text):
    """"✔" / "✘ कारण" / "?" / "सुटलेला trade 13:30 bear" ⇒ {verdict, reason, missed}; review उत्तर नाही ⇒ None;
    "सुटलेला" पण वेळ (09:15–15:30) + bear/bull स्पष्ट नाही ⇒ {"error": …} (नोंद नाही, ❓)."""
    t = (text or "").replace(VS16, "").strip()
    if not t:
        return None
    verdict, rest = None, t
    for marks, v in ((OK_MARKS, "OK"), (BAD_MARKS, "WRONG")):
        mk = next((x for x in marks if t.startswith(x)), None)
        if mk:
            verdict, rest = v, t[len(mk):].strip(" :-—,")
            break
    if verdict is None and t.startswith("?"):
        verdict, rest = "UNCLEAR", t[1:].strip(" :-—,")
    missed = None
    if "सुटलेला" in t or "missed" in t.lower():
        ms = _TIME_SIDE.search(t)
        if ms:
            h, mi, side = int(ms.group(1)), ms.group(2), SIDE_OF[ms.group(3).lower()]
        else:
            tm = _TIME.search(t)
            bear, bull = bool(_BEAR.search(t)), bool(_BULL.search(t))
            if not tm or bear == bull:
                return {"error": "सुटलेला trade: वेळ HH:MM आणि bear / bull (एकच) लिहा, उदा. \"सुटलेला trade 13:30 bear\""}
            h, mi, side = int(tm.group(1)), tm.group(2), "bear_call" if bear else "bull_put"
        if not _in_session(h, int(mi)):
            return {"error": f"सुटलेला trade: वेळ {h:02d}:{mi} session (09:15–15:30) बाहेर"}
        missed = {"time": f"{h:02d}:{mi}", "side": side}
        verdict = verdict or "WRONG"
    if verdict is None:
        return None
    return {"verdict": verdict, "reason": rest, "missed": missed}


def handle_reply(msg, authorized, save=None, send=None, sent=None):
    """Telegram message (reply) ⇒ (ok, कारण). authorized(from, chat) ⇒ bool (approver ids). save = store.save_review सारखं."""
    rt = msg.get("reply_to_message") or {}
    if not rt:
        return False, "not_reply"
    rec = lookup_message(rt.get("message_id"), sent)
    if rec is None or rec.get("kind") == "document":                       # PDF अहवाल ⇒ review item नाही (✔ / ✘ albums वर)
        return False, "not_review"
    if not authorized(msg.get("from"), msg.get("chat")):
        return False, "unauthorized"
    p = parse_reply(msg.get("text") or msg.get("caption"))
    if p is None or p.get("error"):
        if send:
            send("❓ " + (p["error"] if p else "समजलं नाही — ✔ / ✘ कारण / सुटलेला trade HH:MM bear|bull") + " — नोंद केली नाही")
        return False, "unparsed"
    if save is None:
        from . import store as ST
        save = ST.save_review
    kind = rec.get("kind") or ("trade" if "trade:" in rec["item"] else "day")     # vision_test ⇒ स्वतंत्र प्रकार (मोजमापात वेगळा)
    ok = save(rec["item"], rec["date"], kind, p["verdict"], p["reason"], p["missed"] if kind == "day" else None, rec.get("run"))
    if send:
        send(f"नोंद ✓ {rec['date']} · {p['verdict']}" + (f" · सुटलेला {p['missed']['time']} {p['missed']['side']}" if p["missed"] else "")
             if ok else f"⚠️ नोंद अयशस्वी ({rec['date']}) — DB तपासा")
    return bool(ok), "saved" if ok else "db_fail"
