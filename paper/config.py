"""paper/config.py — config.yaml `paper:` विभाग (instruments enabled, lot size fallback, update अंतर). वाचता आलं नाही ⇒ सुरक्षित defaults
(फक्त NIFTY enabled)."""
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = {"instruments": {"NIFTY": {"enabled": True, "lot_size_fallback": None}}, "update_every_min": 30, "near_alert_pct": 80,
            "entry_cutoff": "14:45"}


def data_dir():
    """VPS local state (lot size cache, token alert, journal). `PAPER_DATA_DIR` (tests) नाहीतर <repo>/data."""
    return os.environ.get("PAPER_DATA_DIR") or os.path.join(ROOT, "data")


def load(path=None):
    p = path or os.environ.get("PAPER_CONFIG") or os.path.join(ROOT, "config.yaml")
    try:
        with open(p, encoding="utf-8") as f:
            cfg = (yaml.safe_load(f) or {}).get("paper") or {}
    except (OSError, yaml.YAMLError):
        cfg = {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in cfg.items() if v is not None})
    return out


def enabled(symbol, cfg=None):
    cfg = cfg or load()
    return bool(((cfg.get("instruments") or {}).get(str(symbol).upper()) or {}).get("enabled", False))


def lot_fallback(symbol, cfg=None):
    cfg = cfg or load()
    v = ((cfg.get("instruments") or {}).get(str(symbol).upper()) or {}).get("lot_size_fallback")
    return int(v) if v else None
