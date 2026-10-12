"""paper/config.py — config.yaml `paper:` विभाग (instruments enabled, lot size fallback, update अंतर). वाचता आलं नाही ⇒ सुरक्षित defaults
(फक्त NIFTY enabled)."""
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = {"instruments": {"NIFTY": {"enabled": True, "lot_size_fallback": None}}, "update_every_min": 30, "near_alert_pct": 80,
            "entry_cutoff": "14:45", "watch_min_interval_sec": 15}


def data_dir():
    """VPS local state (lot size cache, token alert, journal). `PAPER_DATA_DIR` (tests) नाहीतर <repo>/data."""
    return os.environ.get("PAPER_DATA_DIR") or os.path.join(ROOT, "data")


def local_path():
    """VPS-local instruments override (git मध्ये नाही; `scripts/set_one_bot_mode.py` लिहितो / --revert परत करतो)."""
    return os.environ.get("PAPER_LOCAL_CONFIG") or os.path.join(data_dir(), "paper_local.yaml")


def local_instruments(path=None):
    """local override मधले `instruments:` (फक्त `enabled`). नाही / वाचता आलं नाही ⇒ {} (config.yaml तसाच)."""
    try:
        with open(path or local_path(), encoding="utf-8") as f:
            ins = (yaml.safe_load(f) or {}).get("instruments") or {}
        return {str(k).upper(): {"enabled": bool(v.get("enabled"))} for k, v in ins.items() if isinstance(v, dict) and "enabled" in v}
    except (OSError, yaml.YAMLError, AttributeError):
        return {}


def load(path=None):
    p = path or os.environ.get("PAPER_CONFIG") or os.path.join(ROOT, "config.yaml")
    try:
        with open(p, encoding="utf-8") as f:
            cfg = (yaml.safe_load(f) or {}).get("paper") or {}
    except (OSError, yaml.YAMLError):
        cfg = {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in cfg.items() if v is not None})
    if path is None:                                                     # स्पष्ट path (tests / तपासणी) ⇒ फक्त तीच file
        loc = local_instruments()
        if loc:
            ins = {k: dict(v) for k, v in (out.get("instruments") or {}).items()}
            for k, v in loc.items():
                ins[k] = {**ins.get(k, {}), **v}
            out["instruments"] = ins
    cut = out.get("entry_cutoff")
    if isinstance(cut, int):                                             # YAML मध्ये quote नसलेलं 14:45 ⇒ sexagesimal 885 (मिनिटं)
        out["entry_cutoff"] = f"{cut // 60:02d}:{cut % 60:02d}"
    try:
        h, m = (int(x) for x in str(out["entry_cutoff"]).split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except (ValueError, AssertionError):
        out["entry_cutoff"] = DEFAULTS["entry_cutoff"]                  # चुकीचं ⇒ default (fail-closed: नवीन entries 14:45 नंतर नाहीत)
    return out


def enabled(symbol, cfg=None):
    cfg = cfg or load()
    return bool(((cfg.get("instruments") or {}).get(str(symbol).upper()) or {}).get("enabled", False))


def lot_fallback(symbol, cfg=None):
    cfg = cfg or load()
    v = ((cfg.get("instruments") or {}).get(str(symbol).upper()) or {}).get("lot_size_fallback")
    return int(v) if v else None
