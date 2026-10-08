"""vision/decide.py — V1 निर्णय नियम (pure functions): mode × verdict ⇒ पुढचं पाऊल, drift guard, callback HMAC.

🎓 Reduce-only: factor कधीच 1.0 पेक्षा जास्त नाही; 0 ⇒ skip (shadow track). Exits ला यातलं काहीच लागत नाही.

  auto_veto          agree ⇒ 1 · gray ⇒ vision_gray_action (half 0.5 / skip 0 / ignore 1) · disagree ⇒ vision_disagree_action
                     (skip 0 / half 0.5 / ignore 1) · unavailable ⇒ vision_fail_action (ignore 1 / skip 0)
  human_confirm      नेहमी Telegram (✅/❌). Approve ⇒ agree / unavailable / disagree 1, gray 0.5 · Reject / timeout ⇒ skip
  veto_then_confirm  disagree ⇒ आपोआप skip (फक्त माहिती, बटण नाही) · agree / gray ⇒ Telegram (gray ⇒ अर्धा) ·
                     timeout ⇒ timeout_action (auto_veto: agree पूर्ण, gray अर्धा · skip) · unavailable ⇒ Telegram, timeout ⇒ algorithm (1)
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Optional

ACTION_F = {"half": 0.5, "skip": 0.0, "ignore": 1.0}
MR_FALLBACK_PCT = 0.10                 # median range नसेल (chart अपयश) तर spot च्या 0.10% (NIFTY 5m bar ~ 0.08%) — drift तपासणी वगळत नाही


@dataclass
class Decision:
    status: str                        # APPROVED | REJECTED | PENDING_HUMAN
    factor: float                      # APPROVED चा (आणि PENDING_HUMAN मध्ये Approve केल्यास) size factor
    reason: str
    timeout_status: Optional[str] = None
    timeout_factor: Optional[float] = None
    ask_human: bool = False


def _final(f, reason):
    f = max(0.0, min(1.0, float(f)))
    return Decision("APPROVED" if f > 0 else "REJECTED", f, reason)


def verdict_factor(verdict, s):
    if verdict == "agree":
        return 1.0
    if verdict == "gray":
        return ACTION_F[s["vision_gray_action"]]
    if verdict == "disagree":
        return ACTION_F[s["vision_disagree_action"]]
    return {"ignore": 1.0, "skip": 0.0}[s["vision_fail_action"]]          # unavailable


def decide(mode, verdict, s):
    """Vision मतानंतरचा निर्णय."""
    if mode == "auto_veto":
        return _final(verdict_factor(verdict, s), f"auto_veto: {verdict}")
    if mode == "human_confirm":
        f = 0.5 if verdict == "gray" else 1.0
        return Decision("PENDING_HUMAN", f, f"human_confirm: {verdict}", "REJECTED", 0.0, True)
    if mode == "veto_then_confirm":
        if verdict == "disagree":
            return Decision("REJECTED", 0.0, "veto_then_confirm: vision disagree ⇒ आपोआप skip")
        if verdict == "unavailable":
            return Decision("PENDING_HUMAN", 1.0, "veto_then_confirm: vision unavailable ⇒ तुम्हाला विचारलं", "APPROVED", 1.0, True)
        f = 1.0 if verdict == "agree" else 0.5
        tf = f if s.get("timeout_action", "auto_veto") == "auto_veto" else 0.0
        return Decision("PENDING_HUMAN", f, f"veto_then_confirm: {verdict}", "APPROVED" if tf > 0 else "REJECTED", tf, True)
    raise ValueError(f"V1 mode नाही: {mode}")


def scaled_lots(lots, factor):
    """Reduce-only: floor(lots × factor), कधीच lots पेक्षा जास्त नाही."""
    return max(0, min(int(lots), int(float(lots) * float(factor) + 1e-9)))


def drift_guard(row, spot, direction, max_drift_mr, origin=None):
    """Approve ते entry च्या क्षणी पुन्हा तपासणी. रिटर्न अपयशांची यादी (रिकामी ⇒ ठीक).
      1. spot signal-spot पासून max_drift_mr × median range पेक्षा दूर
      2. invalidation ओलांडली: setup मध्ये invalidation असेल तर ती; नाहीतर level ची बाजू बदलली (bot ची चालू दिशा signal च्या उलट)
      3. pullback origin ओलांडला — bot ने origin दिला तरच (सध्याचे 5-Min / 15M bots origin मोजत नाहीत ⇒ हा नियम त्यांच्यासाठी लागू नाही)
      4. Bot चे daily loss / kill switch / max-open: bot चे नेहमीचे gates entry पर्यंत पुन्हा चालतात ⇒ इथे तपासणी नाही (रचनेनेच)."""
    out = []
    s0, mr = row.get("spot"), row.get("median_range")
    if not mr and s0:
        mr = abs(float(s0)) * MR_FALLBACK_PCT / 100.0
    if s0 is not None and mr and spot is not None and abs(float(spot) - float(s0)) > float(max_drift_mr) * float(mr):
        out.append(f"drift: spot {float(spot):,.1f} वि. signal {float(s0):,.1f} (> {max_drift_mr} × median range {float(mr):.1f})")
    bull = str(row.get("direction", "")).upper().startswith("BULL")
    inv = row.get("invalidation")
    if inv is None and row.get("setup_json"):
        try:
            import json
            inv = json.loads(row["setup_json"]).get("invalidation")
        except (ValueError, AttributeError):
            inv = None
    inv = float(inv) if inv is not None else None
    if inv is not None and spot is not None and ((bull and spot < inv) or (not bull and spot > inv)):
        out.append(f"invalidation {float(inv):,.1f} ओलांडली")
    elif direction is not None and str(direction).upper() != str(row.get("direction", "")).upper():
        out.append(f"level ची बाजू बदलली ({row.get('direction')} → {direction})")
    if origin is not None and spot is not None and ((bull and spot > origin) or (not bull and spot < origin)):
        out.append(f"pullback origin {float(origin):,.1f} ओलांडला (breakout)")
    return out


# --------------------------------------------------------------------------------------------------------- callback HMAC
def secret():
    return (os.environ.get("VISION_CALLBACK_SECRET") or "").strip()


def sign(signal_id, action, key=None):
    k = (key if key is not None else secret()).encode("utf-8")
    return hmac.new(k, f"{signal_id}|{action}".encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def callback_data(signal_id, action, key=None):
    return f"v1|{signal_id}|{action}|{sign(signal_id, action, key)}"


def parse_callback(data, key=None):
    """(signal_id, action) किंवा None (format / HMAC चूक). action ∈ {A, R}."""
    try:
        tag, sid, action, sig = str(data).split("|")
    except ValueError:
        return None
    k = key if key is not None else secret()
    if tag != "v1" or action not in ("A", "R") or not k:
        return None
    return (sid, action) if hmac.compare_digest(sig, sign(sid, action, k)) else None


def approver_ids():
    return {x.strip() for x in (os.environ.get("TELEGRAM_APPROVER_IDS") or "").split(",") if x.strip()}
