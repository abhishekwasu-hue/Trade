"""
pullback_credit_spread/settings.py
----------------------------------
🎓 सर्व settings एकाच schema मध्ये: key, विभाग (dashboard expander), मराठी label, ⓘ मदत ("हे काय करतं, वाढवल्यास काय होतं"), प्रकार,
डीफॉल्ट, min/max/पर्याय. Code मध्ये कुठलीही strategy-संख्या hard-coded नाही — सर्व `get(settings, key)` मधून.
Presets (Conservative / Balanced / Aggressive) फक्त काही keys बदलतात; बाकी डीफॉल्ट. Validation: प्रकार, min/max, पर्याय, आणि परस्पर-नियम
(उदा. min_distance ≤ max_distance). Snapshot: प्रत्येक trade सोबत साठवण्यासाठी (sorted JSON + hash).
"""
import datetime as _dt
import hashlib
import json
import math

SECTIONS = (
    ("mode", "1. Mode आणि symbols"),
    ("trend", "2. Trend"),
    ("levels", "3. Levels"),
    ("pullback", "4. Pullback"),
    ("reversal", "5. Entry reversal"),
    ("expiry", "6. Expiry"),
    ("strike", "7. Strike"),
    ("risk", "8. Risk"),
    ("exit", "9. Exit / adjustment"),
    ("events", "10. Events"),
    ("orders", "11. Orders"),
)

TF_CHOICES = ("5m", "15m", "30m", "1h", "4h", "1d")


def _s(key, section, label, help_, kind, default, lo=None, hi=None, choices=None, step=None):
    return {"key": key, "section": section, "label": label, "help": help_, "type": kind, "default": default, "min": lo, "max": hi,
            "choices": choices, "step": step}


SCHEMA = [
    # 1. Mode
    _s("mode", "mode", "Mode", "OFF = काहीच करत नाही. PAPER = फक्त कागदावर trades (खरे orders नाहीत). LIVE फक्त तुमच्या स्पष्ट मंजुरीनंतर (G3) "
       "उपलब्ध होईल.", "choice", "OFF", choices=("OFF", "PAPER")),
    _s("symbol_enabled", "mode", "हा symbol चालू", "बंद असेल तर या symbol वर नवीन entry नाही (उघड्या positions चे exits चालूच).", "bool", False),
    # 2. Trend
    _s("scan_tf", "mode", "Scan timeframe", "Runner किती वेळाने setups तपासतो (प्रत्येक पूर्ण झालेल्या या TF च्या candle नंतर).", "choice", "15m",
       choices=TF_CHOICES),
    _s("trend_tf", "trend", "Trend timeframe", "Structure (UPTREND/DOWNTREND) कोणत्या timeframe वर ठरवायचा. मोठा TF ⇒ कमी पण स्थिर signals.",
       "choice", "1h", choices=TF_CHOICES),
    _s("htf_veto_tf", "trend", "HTF veto timeframe", "या मोठ्या TF वरचा trend उलट असेल तर entry नाही. 'none' ⇒ veto बंद.", "choice", "1d",
       choices=("none",) + TF_CHOICES),
    _s("skip_on_weak", "trend", "WEAK trend मध्ये skip", "UPTREND_WEAK / DOWNTREND_WEAK (CHoCH नंतर) असेल तर entry नाही.", "bool", True),
    # 3. Levels
    _s("level_engine", "levels", "Level engine", "कोणत्या engine चे levels वापरायचे. major_levels = Trader's Eye (प्रमाणित होईपर्यंत प्रायोगिक); "
       "srv3 = SR Levels V3; oe_zones = Opportunity Engine zones.", "choice", "srv3", choices=("srv3", "major_levels", "oe_zones")),
    _s("level_tf", "levels", "Level timeframe", "Levels कोणत्या TF वरून. Entry candle डीफॉल्टने याच TF चा.", "choice", "1h", choices=TF_CHOICES),
    _s("require_role_reversal", "levels", "फक्त role-reversal levels", "चालू ⇒ फक्त आधी resistance → आता support (किंवा उलट) असे levels. "
       "कमी पण दर्जेदार setups.", "bool", False),
    _s("approach_lookback_bars", "levels", "Approach तपासणी (bars)", "Level कडे किंमत trend च्या बाजूने आली का (LONG ⇒ वरून खाली) हे मागच्या "
       "इतक्या level-TF bars मध्ये तपासतो. नाहीतर ते breakout आहे ⇒ entry नाही.", "int", 10, 3, 100),
    _s("max_level_distance_pct", "levels", "Level किती दूर चालेल (%)", "Spot पासून level यापेक्षा दूर असेल तर तो विचारात नाही.", "float", 1.5,
       0.1, 10.0, step=0.1),
    # 4. Pullback
    _s("require_healthy_pullback", "pullback", "HEALTHY pullback हवा", "Level कडे येणारा leg HEALTHY (हळू, overlap, उलट displacement नाही) "
       "असावा (spec §1.4). बंद ⇒ फक्त DANGEROUS वगळतो (MIXED चालतो). ⚠️ NIFTY 15M वर HEALTHY फार दुर्मिळ (~1–1.5% pullbacks).", "bool", True),
    _s("max_pullback_depth", "pullback", "Pullback depth कमाल (impulse चा भाग)", "Pullback ने आधीच्या impulse चा किती भाग परत घेतला तरी चालेल "
       "(leg classifier चा DANGEROUS उंबरठाही हाच). जास्त ⇒ खोल pullbacks चालतात (धोका जास्त).", "float", 0.75, 0.2, 0.95, step=0.05),
    _s("max_speed_ratio", "pullback", "Speed ratio कमाल", "Pullback चा वेग ÷ impulse चा वेग. 1 किंवा जास्त ⇒ pullback impulse इतका/पेक्षा वेगवान — "
       "classifier तो DANGEROUS मानतो, म्हणून कमाल 1.", "float", 1.0, 0.2, 1.0, step=0.05),
    _s("min_overlap", "pullback", "Overlap किमान", "Pullback candles एकमेकांवर किती overlap (0–1). जास्त ⇒ फक्त 'थकलेले' pullbacks.", "float", 0.4,
       0.0, 1.0, step=0.05),
    # 5. Reversal
    _s("entry_candle_tf", "reversal", "Entry candle TF", "'same' ⇒ level च्या TF वरच (डीफॉल्ट). लहान TF ⇒ लवकर पण जास्त गोंगाट.", "choice",
       "same", choices=("same",) + TF_CHOICES),
    _s("reversal_strength_k", "reversal", "Reversal strength (k × median range)", "Level पासून reclaim नंतर किंमत किती दूर गेली पाहिजे. "
       "जास्त ⇒ पक्की पण उशिरा entry.", "float", 1.2, 0.3, 4.0, step=0.1),
    _s("min_rejection_score", "reversal", "किमान rejection score", "Logical rejection score (0–100). जास्त ⇒ कमी पण स्पष्ट reversals.", "float",
       60.0, 0.0, 100.0, step=5.0),
    _s("max_range_mult", "reversal", "Reversal candle कमाल आकार (× median range)", "यापेक्षा मोठी candle(s) ⇒ exhaustion, reversal मानत नाही.",
       "float", 2.5, 1.0, 10.0, step=0.1),
    _s("touch_pct", "reversal", "Touch tolerance (%)", "किंमत level च्या इतक्या % आत आली तर 'touch' मानतो.", "float", 0.10, 0.01, 1.0, step=0.01),
    # 6. Expiry
    _s("expiry_type", "expiry", "Expiry प्रकार", "weekly (डीफॉल्ट) किंवा monthly. तारखा instrument master वरून — वार गृहीत धरत नाही.", "choice",
       "weekly", choices=("weekly", "monthly")),
    _s("min_dte", "expiry", "किमान DTE (दिवस)", "Expiry ला यापेक्षा कमी दिवस उरले असतील तर पुढची expiry. आज expiry असेल तर नेहमी पुढची.",
       "int", 1, 0, 30),
    # 7. Strike
    _s("strike_mode", "strike", "Short strike पद्धत", "beyond_level = level पलीकडे buffer; distance_pct = spot पासून %; delta = |Δ|; "
       "premium = ठराविक premium; strikes_otm = ATM पासून N strikes.", "choice", "beyond_level",
       choices=("beyond_level", "distance_pct", "delta", "premium", "strikes_otm")),
    _s("beyond_level_unit", "strike", "Buffer एकक", "beyond_level buffer % मध्ये की points मध्ये.", "choice", "pct", choices=("pct", "points")),
    _s("beyond_level_buffer_pct", "strike", "Level पलीकडे buffer (%)", "beyond_level mode: level पासून आणखी इतके % दूर. जास्त ⇒ सुरक्षित पण कमी "
       "credit.", "float", 0.3, 0.0, 5.0, step=0.05),
    _s("beyond_level_buffer_points", "strike", "Level पलीकडे buffer (points)", "beyond_level mode (एकक = points).", "float", 50.0, 0.0, 5000.0,
       step=5.0),
    _s("distance_pct", "strike", "Spot पासून अंतर (%)", "distance_pct mode साठी.", "float", 1.5, 0.1, 10.0, step=0.1),
    _s("target_delta", "strike", "Target |Δ|", "delta mode: short strike चा |delta| याच्या जवळ. कमी ⇒ दूर strike, कमी credit.", "float", 0.15,
       0.02, 0.5, step=0.01),
    _s("target_premium", "strike", "Target premium (₹)", "premium mode: short leg चा premium याच्या जवळ.", "float", 20.0, 0.5, 500.0, step=0.5),
    _s("strikes_otm", "strike", "ATM पासून strikes (N)", "strikes_otm mode साठी.", "int", 6, 1, 40),
    _s("min_distance_pct", "strike", "किमान अंतर (%)", "कुठल्याही mode मध्ये short strike spot पासून किमान इतका दूर.", "float", 0.8, 0.0, 10.0,
       step=0.1),
    _s("max_distance_pct", "strike", "कमाल अंतर (%)", "यापेक्षा दूर strike नको (credit फारच कमी होतो).", "float", 4.0, 0.2, 15.0, step=0.1),
    _s("min_credit", "strike", "किमान net credit (₹ प्रति unit)", "Short − long premium यापेक्षा कमी ⇒ entry नाही.", "float", 5.0, 0.0, 500.0,
       step=0.5),
    _s("min_credit_to_width_ratio", "strike", "किमान credit ÷ width", "उदा. 0.15 ⇒ 200-point spread साठी किमान ₹30 credit.", "float", 0.10, 0.0,
       0.9, step=0.01),
    _s("width_mode", "strike", "Hedge width प्रकार", "points = ठराविक points; strikes = N strikes दूर.", "choice", "points",
       choices=("points", "strikes")),
    _s("width_points", "strike", "Hedge width (points)", "Short आणि long strike मधलं अंतर. जास्त ⇒ जास्त credit पण जास्त max loss.", "float", 200.0,
       25.0, 2000.0, step=25.0),
    _s("width_strikes", "strike", "Hedge width (strikes)", "width_mode = strikes साठी.", "int", 4, 1, 40),
    # 8. Risk
    _s("risk_per_trade_pct", "risk", "प्रति trade धोका (capital च्या %)", "Lots = floor(हा धोका ÷ प्रति lot max loss).", "float", 1.0, 0.1, 10.0,
       step=0.1),
    _s("max_lots", "risk", "कमाल lots", "कितीही गणित आलं तरी यापेक्षा जास्त lots नाहीत.", "int", 2, 1, 100),
    _s("max_open_spreads", "risk", "एकूण उघडे spreads कमाल", "सर्व symbols मिळून.", "int", 2, 1, 20),
    _s("max_open_spreads_per_symbol", "risk", "प्रति symbol उघडे spreads कमाल", "एकाच symbol वर एका वेळी इतकेच spreads. एकूण मर्यादेपेक्षा जास्त "
       "असू शकत नाही.", "int", 1, 1, 10),
    _s("daily_loss_cap", "risk", "दैनिक तोटा मर्यादा (₹)", "आजचा realized तोटा यापेक्षा जास्त ⇒ नवीन entry नाही (exits चालू).", "float", 5000.0,
       0.0, 1e7, step=500.0),
    _s("event_day_size_multiplier", "risk", "Event दिवशी size गुणक", "Event दिवशी lots × हा गुणक (blackout बाहेर entry झाली तरी).", "float", 0.5,
       0.0, 1.0, step=0.1),
    _s("check_margin", "risk", "Broker margin तपासा", "Entry आधी broker margin API ने पुरेसा margin आहे का तपासणे.", "bool", True),
    # 9. Exit
    _s("profit_target_pct_of_credit", "exit", "Profit target (credit चा %)", "Credit चा इतका % नफा झाला की बंद.", "float", 60.0, 5.0, 100.0,
       step=5.0),
    _s("hard_stop_credit_multiple", "exit", "Hard stop (credit च्या पट)", "Spread ची किंमत credit च्या इतक्या पट झाली की **कुठलंही logic असो** "
       "लगेच बंद.", "float", 2.0, 1.1, 10.0, step=0.1),
    _s("spot_stop_distance_pct", "exit", "Spot stop (short strike पासून %)", "Spot short strike च्या इतक्या % आत आला की बंद. 0 ⇒ बंद.", "float",
       0.5, 0.0, 5.0, step=0.05),
    _s("real_break_exit", "exit", "Level च्या खऱ्या break वर exit", "False break (परत आत close) वर exit नाही.", "bool", True),
    _s("break_buffer_pct", "exit", "Break buffer (%)", "Level च्या दूरच्या कडेपलीकडे इतके % गेल्यावरच break मानतो.", "float", 0.1, 0.0, 2.0,
       step=0.05),
    _s("no_reclaim_bars", "exit", "Reclaim नसलेले bars", "Break नंतर इतके confirm-TF bars परत आत close नाही ⇒ खरा break.", "int", 3, 1, 20),
    _s("break_lookback_bars", "exit", "Break तपासणी (bars)", "Entry guard मध्ये level चा खरा break शोधण्यासाठी मागचे इतके confirm-TF bars.",
       "int", 60, 5, 500),
    _s("break_confirm_tf", "exit", "Break confirm TF", "खरा break कोणत्या TF वर ठरवायचा.", "choice", "1h", choices=TF_CHOICES),
    _s("adjustment_mode", "exit", "Adjustment", "close = बंद; roll = पुढचा strike / पुढची expiry; add_hedge = आणखी hedge. (v1: फक्त close अंमलात.)",
       "choice", "close", choices=("close", "roll", "add_hedge")),
    _s("time_exit", "exit", "Expiry दिवशी वेळ-exit (HH:MM)", "Expiry दिवशी या वेळी उरलेली position बंद.", "time", "14:30"),
    # 10. Events
    _s("event_blackout_enabled", "events", "Event blackout", "Blackout window मध्ये नवीन entry नाही (exits चालू).", "bool", True),
    _s("event_dates", "events", "Event तारखा", "स्वल्पविरामाने: YYYY-MM-DD (RBI, Budget इ.). त्या दिवशी खालच्या window मध्ये नवीन entry नाही; "
       "window बाहेर entry झाली तर size × event गुणक.", "text", ""),
    _s("event_blackout_start", "events", "Event दिवशी blackout सुरू (HH:MM)", "", "time", "09:15"),
    _s("event_blackout_end", "events", "Event दिवशी blackout संपतो (HH:MM)", "उदा. RBI 10:00 ला ⇒ 11:30 पर्यंत.", "time", "11:30"),
    _s("blackout_expiry_morning_until", "events", "Expiry सकाळी blackout (HH:MM पर्यंत)", "Expiry दिवशी या वेळेपर्यंत नवीन entry नाही. रिकामं ⇒ "
       "बंद.", "time", "10:30"),
    # 11. Orders
    _s("market_protection_pct", "orders", "Market protection (%)", "0 ⇒ broker डीफॉल्ट (field पाठवत नाही). 1–25 ⇒ MARKET orders मध्ये हा %.",
       "int", 0, 0, 25),
    _s("hedge_first", "orders", "आधी hedge (BUY) मग SELL", "नेहमी चालू ठेवण्याची शिफारस (margin आणि धोका कमी).", "bool", True),
]

BY_KEY = {s["key"]: s for s in SCHEMA}
DEFAULTS = {s["key"]: s["default"] for s in SCHEMA}

PRESETS = {
    "Conservative": {"skip_on_weak": True, "require_role_reversal": True, "require_healthy_pullback": True,
                     "max_pullback_depth": 0.6, "min_rejection_score": 70.0, "strike_mode": "beyond_level", "beyond_level_buffer_pct": 0.5,
                     "min_distance_pct": 1.2, "target_delta": 0.10, "risk_per_trade_pct": 0.5, "max_lots": 1, "profit_target_pct_of_credit": 50.0,
                     "hard_stop_credit_multiple": 1.8, "spot_stop_distance_pct": 0.7, "min_dte": 2},
    "Balanced": {},
    "Aggressive": {"skip_on_weak": False, "require_role_reversal": False, "require_healthy_pullback": False, "max_pullback_depth": 0.9,
                   "min_rejection_score": 50.0, "beyond_level_buffer_pct": 0.15, "min_distance_pct": 0.5, "target_delta": 0.22,
                   "risk_per_trade_pct": 1.5, "max_lots": 4, "profit_target_pct_of_credit": 70.0, "hard_stop_credit_multiple": 2.5,
                   "spot_stop_distance_pct": 0.3, "min_dte": 0},
}


def preset(name):
    if name not in PRESETS:
        raise KeyError(f"अज्ञात preset: {name}")
    return {**DEFAULTS, **PRESETS[name]}


def _coerce(spec, v):
    t = spec["type"]
    if t == "bool":
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on", "हो")
        return bool(v)
    if t in ("int", "float"):
        f = float(v)
        if not math.isfinite(f):
            raise ValueError("NaN/inf")
        return int(round(f)) if t == "int" else f
    if t == "time":
        s = str(v).strip()
        if not s:
            return ""
        hh, mm = s.split(":")
        hh, mm = int(hh), int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("वेळ HH:MM")
        return f"{hh:02d}:{mm:02d}"
    return str(v) if v is not None else ""


def validate(raw):
    """raw dict → (clean dict — डीफॉल्टसह पूर्ण, errors list). अवैध मूल्य ⇒ डीफॉल्ट वापरतो आणि error नोंदवतो. अज्ञात keys दुर्लक्षित."""
    clean, errors = dict(DEFAULTS), []
    for k, v in (raw or {}).items():
        spec = BY_KEY.get(k)
        if spec is None:
            continue
        try:
            val = _coerce(spec, v)
        except (TypeError, ValueError):
            errors.append(f"{spec['label']}: अवैध मूल्य {v!r} — डीफॉल्ट {spec['default']!r} वापरला")
            continue
        if spec["choices"] and val not in spec["choices"]:
            errors.append(f"{spec['label']}: {val!r} पर्यायांत नाही — डीफॉल्ट वापरला")
            continue
        if spec["min"] is not None and val < spec["min"] or spec["max"] is not None and val > spec["max"]:
            errors.append(f"{spec['label']}: {val} मर्यादेबाहेर ({spec['min']}–{spec['max']}) — डीफॉल्ट वापरला")
            continue
        clean[k] = val
    if clean["min_distance_pct"] > clean["max_distance_pct"]:
        errors.append("किमान अंतर कमाल अंतरापेक्षा जास्त — दोन्ही डीफॉल्ट")
        clean["min_distance_pct"], clean["max_distance_pct"] = DEFAULTS["min_distance_pct"], DEFAULTS["max_distance_pct"]
    if clean["max_open_spreads_per_symbol"] > clean["max_open_spreads"]:
        errors.append("प्रति symbol मर्यादा एकूण मर्यादेपेक्षा जास्त — एकूण मर्यादेइतकी केली")
        clean["max_open_spreads_per_symbol"] = clean["max_open_spreads"]
    bad = []
    for x in str(clean["event_dates"] or "").split(","):
        x = x.strip()
        if x:
            try:
                _dt.date.fromisoformat(x)
            except ValueError:
                bad.append(x)
    if bad:
        errors.append(f"Event तारखा अवैध: {', '.join(bad)} (YYYY-MM-DD) — event तारखा रिकाम्या केल्या")
        clean["event_dates"] = ""
    if clean["event_blackout_start"] and clean["event_blackout_end"] and clean["event_blackout_start"] > clean["event_blackout_end"]:
        errors.append("Event blackout सुरू > संपतो — डीफॉल्ट")
        clean["event_blackout_start"], clean["event_blackout_end"] = DEFAULTS["event_blackout_start"], DEFAULTS["event_blackout_end"]
    if clean["mode"] not in ("OFF", "PAPER"):
        clean["mode"] = "OFF"
    return clean, errors


def diff(old, new):
    """बदललेल्या keys: [(key, जुनं, नवं)] — इतिहासासाठी."""
    return [(k, old.get(k), new.get(k)) for k in sorted(set(old) | set(new)) if k in BY_KEY and old.get(k) != new.get(k)]


def snapshot(settings):
    """प्रत्येक trade सोबत साठवण्यासाठी: {"settings": {...}, "hash": sha1[:12]} (sorted JSON)."""
    s = {k: settings.get(k, DEFAULTS[k]) for k in sorted(DEFAULTS)}
    blob = json.dumps(s, sort_keys=True, ensure_ascii=False)
    return {"settings": s, "hash": hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]}


def tf_minutes(tf):
    return {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}[tf]
