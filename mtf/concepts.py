"""mtf/concepts.py — chart वरच्या संकल्पना: कोणती दाखवायची (dashboard वरून, code मध्ये hardcode नाही).

Config (`chart_concepts`): {"mode": "all" | "primary", "concepts": {key: {"show": bool, "tier": "primary" | "secondary"}},
"window": {tf: candles}}. Default: सगळ्या show = true, mode = all. mode = primary ⇒ फक्त tier primary + show.
Store: JSON (VPS local; `MTF_CHART_CONCEPTS_PATH`, default data/chart_concepts.json) — Backtest Review पानावरून बदलतो; CLI
`--concepts-off` / `--mode` त्या run पुरते override. Layer ला output नाही ⇒ legend मध्ये "NA (अजून नाही)".
"""
import json
import os

PATH_ENV = "MTF_CHART_CONCEPTS_PATH"
MODES = ("all", "primary")
TIERS = ("primary", "secondary")

# key: (मराठी नाव, image: "अ" रचना / "आ" entry / "both", default tier)
CONCEPTS = {
    "swings": ("swings (degree-निहाय H / L / HH / HL / LH / LL)", "both", "primary"),
    "protected": ("संरक्षित swing (degree-निहाय)", "both", "primary"),
    "trend": ("trend (degree-निहाय)", "both", "primary"),
    "range": ("range कडा", "both", "primary"),
    "impulse": ("impulse (I)", "अ", "primary"),
    "abc": ("A-B-C (प्रकार + गुण)", "अ", "secondary"),
    "k_extreme": ("K टोक", "both", "primary"),
    "k_base": ("K आधार-रेघ", "both", "secondary"),
    "k_reset": ("K-reset खूण", "अ", "secondary"),
    "zones": ("zones ★ + प्रकार (flip / origin / sweep) + अवस्था", "both", "primary"),
    "zone_self": ("self zone खूण", "both", "secondary"),
    "zone_dead": ("मेलेले zones + कारण", "अ", "secondary"),
    "lines": ("trendlines (trade-योग्य ठळक · provisional फिकट)", "both", "primary"),
    "sweep": ("sweep / false-break खुणा", "अ", "secondary"),
    "area_touch": ("area-touch box", "आ", "primary"),
    "corr_end": ("correction संपतेय ✔ (shrink / overlap / counter-wick / momentum)", "आ", "secondary"),
    "rsi_div": ("RSI divergence प्रकार", "आ", "secondary"),
    "commitment": ("commitment candle G1–G8 ✔", "आ", "primary"),
    "engine": ("engine निर्णय + अडलेला gate", "आ", "primary"),
    "b1": ("B1 बाण (✅ / 🟡, एका चाचणीला एक)", "आ", "primary"),
    "b2": ("B2 योजना (areas, SL / लक्ष्य / R:R, बाद पातळी, range कडा)", "आ", "primary"),
    "upper_tf": ("वरच्या TF चे zones / संरक्षित (फिकट)", "both", "secondary"),
    "topdown": ("top-down पट्टी", "both", "primary"),
}
WINDOW = {"W": 80, "D": 110, "1H": 90, "15M": 100}          # chart वरच्या candles (थर पूर्ण इतिहासावर; हे फक्त दाखवणं)


def defaults():
    return {"mode": "all", "concepts": {k: {"show": True, "tier": v[2]} for k, v in CONCEPTS.items()}, "window": dict(WINDOW)}


def _path(path=None):
    return path or os.environ.get(PATH_ENV) or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
                                                            "chart_concepts.json")


def validate(cfg):
    """अज्ञात key / अवैध mode / tier ⇒ ValueError."""
    if cfg.get("mode", "all") not in MODES:
        raise ValueError(f"mode '{cfg.get('mode')}' — {MODES} पैकी हवा")
    for k, v in (cfg.get("concepts") or {}).items():
        if k not in CONCEPTS:
            raise ValueError(f"संकल्पना '{k}' माहीत नाही")
        if "tier" in v and v["tier"] not in TIERS:
            raise ValueError(f"{k}: tier '{v['tier']}' — {TIERS} पैकी")
        if "show" in v and not isinstance(v["show"], bool):
            raise ValueError(f"{k}: show true / false हवा")
    for tf, n in (cfg.get("window") or {}).items():
        if tf not in WINDOW or not isinstance(n, int) or n < 10:
            raise ValueError(f"window {tf}: {n} (W / D / 1H / 15M, ≥ 10 candles)")


def merge(base, over):
    out = {"mode": over.get("mode", base["mode"]), "concepts": {k: dict(v) for k, v in base["concepts"].items()},
           "window": dict(base["window"], **(over.get("window") or {}))}
    for k, v in (over.get("concepts") or {}).items():
        out["concepts"].setdefault(k, {}).update(v)
    return out


def load(path=None, overrides=None):
    """defaults ⊕ store ⊕ overrides (CLI). Store खराब / नाही ⇒ defaults."""
    cfg = defaults()
    p = _path(path)
    if os.path.exists(p):
        try:
            st = json.load(open(p, encoding="utf-8")) or {}
            validate(st)
            cfg = merge(cfg, st)
        except (OSError, ValueError):
            pass
    if overrides:
        validate(overrides)
        cfg = merge(cfg, overrides)
    return cfg


def save(cfg, path=None):
    validate(cfg)
    p = _path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1, sort_keys=True)
    return p


def cli_overrides(off=None, mode=None):
    """--concepts-off a,b · --mode primary ⇒ overrides dict."""
    o = {}
    if mode:
        o["mode"] = mode
    if off:
        o["concepts"] = {k.strip(): {"show": False} for k in off.split(",") if k.strip()}
    return o


def on(cfg, key, image=None):
    """ही संकल्पना या image वर काढायची का."""
    c = cfg["concepts"].get(key) or {}
    if not c.get("show", True):
        return False
    if cfg.get("mode") == "primary" and c.get("tier", CONCEPTS[key][2]) != "primary":
        return False
    return image is None or CONCEPTS[key][1] in ("both", image)


def keys_for(image):
    return [k for k, v in CONCEPTS.items() if v[1] in ("both", image)]
