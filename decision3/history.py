"""decision3/history.py — Q33 (Abhi): Daily structure पूर्ण उपलब्ध history वर (degree तिच्यावर अवलंबून), पण NIFTY साठी holdout
तारखांचा कोणताही report / metric / chart / log ओळ नाही (holdout evaluation साठी sealed; आधीच्या candles म्हणून वापर चालतो).

  • load_daily(paths): एक किंवा अधिक Daily files (csv / csv.gz / parquet) ⇒ एक मालिका; एकाच दिवसाचे दोन ⇒ नंतरच्या file चा.
  • sealed_fn(symbol): NIFTY ⇒ ts ⇒ holdout? (elliott.data_policy); इतर symbols ⇒ None.
  • display_start(ts, upto, sealed, sessions): chart कुठून दाखवायचा — शेवटच्या `sessions` पैकी, पण शेवटच्या sealed तारखेनंतरच.
"""
import pandas as pd

NIFTY_NAMES = ("NIFTY", "NIFTY50", "NIFTYINDEX", "NIFTY50INDEX", "NSENIFTY", "NSENIFTY50")


def is_nifty(symbol):
    """NIFTY / NIFTY50 / "NIFTY 50" / NIFTY_INDEX / NSE:NIFTY … (sealed holdout नियम); BANKNIFTY / FINNIFTY नाही."""
    s = "".join(ch for ch in str(symbol).upper() if ch.isalnum())
    return s in NIFTY_NAMES


def sealed_fn(symbol):
    if not is_nifty(symbol):
        return None
    from elliott import data_policy as DP
    return lambda ts: DP.period(ts) == "HOLDOUT"


def _read(path):
    return pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path)


def load_daily(paths, prepare=None):
    paths = [paths] if isinstance(paths, str) else list(paths)
    frames = []
    for k, p in enumerate(paths):
        x = _read(p)
        x["timestamp"] = pd.to_datetime(x["timestamp"])
        if getattr(x["timestamp"].dt, "tz", None) is not None:
            x["timestamp"] = x["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        x["timestamp"] = x["timestamp"].dt.normalize()
        x = prepare(x) if prepare else x
        frames.append(x.assign(_src=k))
    d = pd.concat(frames, ignore_index=True)
    d = d.sort_values(["timestamp", "_src"]).drop_duplicates("timestamp", keep="last").drop(columns="_src")
    return d.reset_index(drop=True)


def last_sealed(ts, sealed, upto=None):
    """[0, upto] मधली शेवटची sealed row (नसेल ⇒ -1)."""
    if sealed is None:
        return -1
    ts = list(ts)
    n = len(ts) if upto is None else upto + 1
    for j in range(n - 1, -1, -1):
        if sealed(ts[j]):
            return j
    return -1


def display_start(ts, upto=None, sealed=None, sessions=250):
    """Chart start index: शेवटच्या `sessions` Daily candles (upto पर्यंत), sealed तारखांनंतरच."""
    ts = list(ts)
    n = len(ts) if upto is None else upto + 1
    return max(0, n - int(sessions), last_sealed(ts, sealed, upto) + 1)
