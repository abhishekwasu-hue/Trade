"""instruments.py — index instruments ची एकच नोंद (thar 1–7 charts / review / probes / downloader साठी). Code मध्ये instrument नाव
hardcode नाही: scripts `--instrument` ने `set_current()` करतात; engine फक्त holdout नियमासाठी `holdout()` वाचतो (NIFTY sealed holdout
तसाच; इतर instruments ना NIFTY चा holdout लागू नाही). Volume फक्त ज्या instrument ला futures volume आहे तिथे; बाकी NA."""
import os

REGISTRY = {
    "NIFTY": {"key": "NSE_INDEX|Nifty 50", "label": "NIFTY", "holdout": True, "futures": "NIFTY", "dir": "upstox"},
    "BANKNIFTY": {"key": "NSE_INDEX|Nifty Bank", "label": "BANKNIFTY", "holdout": False, "futures": None, "dir": "banknifty"},
}
DEFAULT = "NIFTY"
_current = {"name": None}


def names():
    return sorted(REGISTRY)


def get(name=None):
    n = (name or current()).upper()
    if n not in REGISTRY:
        raise ValueError(f"instrument {n!r} माहीत नाही — {names()} पैकी")
    return dict(REGISTRY[n], name=n)


def set_current(name):
    _current["name"] = get(name)["name"]
    return _current["name"]


def current():
    return _current["name"] or os.environ.get("TRADE_INSTRUMENT", DEFAULT).upper()


def label(name=None):
    return get(name)["label"]


def holdout(name=None):
    """हा instrument NIFTY च्या sealed holdout नियमाखाली आहे का."""
    return bool(get(name)["holdout"])
