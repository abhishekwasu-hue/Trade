"""opportunity_engine/cas.py — NSE Closing Auction Session (CAS) चे 1m index bars ओळखणं आणि structure मधून वगळणं.

🎓 का (Abhi 2026-10-08, TRADE_CODE_FIX_CROSSVERIFY_PROMPT §1):
  NSE ने 2026-08-03 पासून cash market मध्ये CAS सुरू केलं (circular NSE/CMTR/75479, 2026-07-30; framework NSE/CMTR/74466, SEBI 2026-01-16):
  15:15–15:20 reference price, 15:20–15:30 order entry (शेवटच्या 2 मिनिटांत random closure), 15:30–15:35 matching.
  Index चे 1m bars 15:15 पासून गोठतात (flat) आणि 15:28/15:29 च्या bar मध्ये auction close ची उडी छापली जाते
  (6 Oct 2026: 15:15–15:28 = 22,717.70, 15:29 high/close = 22,776.10; खरं दिवसाचं टोक ~22,731).
  ही उडी व्यवहारातली किंमत नाही ⇒ swings / HH-LL / BOS-CHoCH / areas / trendlines / pools / MR / candidates / real break / PDH-PDL मध्ये
  **वापरायची नाही**. मात्र official close (PDC) हीच auction close ⇒ `official_close` column मध्ये तशीच ठेवतो (gap / PDC / fill गणित).

Setting `cas_window` (hard-code नाही): code मधले DEFAULT फक्त circular चा fallback; `config.yaml` → `market_data.cas_window` ने बदलता येतं.
  enabled · effective_from (या तारखेपासूनचे sessions; आधीच्या data मध्ये CAS नाही — IS 2015–2024 अबाधित) · start / end (bar-start वेळ,
  start ≤ t < end) · chart: "grey" (राखाडी + "CAS" label) | "exclude" (chart वरून वगळा) · circular (स्रोत).
"""
import copy
import os

import pandas as pd

DEFAULT_CAS_WINDOW = {
    "enabled": True,
    "effective_from": "2026-08-03",
    "start": "15:15",
    "end": "15:30",
    "chart": "grey",
    "circular": "NSE/CMTR/75479 (2026-07-30): CAS 15:15–15:35 from 2026-08-03",
}
DEFAULT_OUTLIER_WICK_MR = 5.0         # data-quality flag: wick > हे × median 1-bar range (मागचे 20 bars)
_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")


def _hm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


_YAML_CACHE = {}


def _from_yaml(path):
    """config.yaml → market_data.cas_window (mtime नुसार cache; प्रत्येक resample ला YAML पुन्हा वाचत नाही)."""
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return {}
    hit = _YAML_CACHE.get(path)
    if hit and hit[0] == mt:
        return dict(hit[1])
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        val = dict((cfg.get("market_data") or {}).get("cas_window") or {})
    except (OSError, ImportError, ValueError, AttributeError):
        val = {}
    _YAML_CACHE[path] = (mt, val)
    return dict(val)


def load_cas_window(overrides=None, path=_CONFIG):
    """DEFAULT ← config.yaml `market_data.cas_window` ← overrides. `overrides=False` ⇒ CAS हाताळणी बंद."""
    if overrides is False:
        return dict(DEFAULT_CAS_WINDOW, enabled=False)
    out = copy.deepcopy(DEFAULT_CAS_WINDOW)
    out.update(_from_yaml(path))
    if isinstance(overrides, dict):
        out.update(overrides)
    _hm(out["start"]), _hm(out["end"])                                  # वेळेचं स्वरूप चुकीचं ⇒ इथेच error
    if out.get("chart") not in ("grey", "exclude"):
        raise ValueError(f"cas_window.chart: grey / exclude (मिळालं {out.get('chart')!r})")
    return out


def resolve(cas):
    """None ⇒ setting वाचा; False ⇒ बंद; dict ⇒ तेच (अपूर्ण असेल तर DEFAULT ने भरा)."""
    if cas is None:
        return load_cas_window()
    if cas is False:
        return dict(DEFAULT_CAS_WINDOW, enabled=False)
    return dict(DEFAULT_CAS_WINDOW, **cas)


def cas_mask(ts, cas=None):
    """bar-start timestamps → bool: CAS window मधला bar (effective_from पासूनच्या sessions मध्ये, start ≤ वेळ < end)."""
    w = resolve(cas)
    t = pd.to_datetime(pd.Series(ts)).reset_index(drop=True)
    if not w.get("enabled") or t.empty:
        return pd.Series(False, index=t.index)
    mins = t.dt.hour * 60 + t.dt.minute
    on = t.dt.normalize() >= pd.Timestamp(w["effective_from"])
    return (on & (mins >= _hm(w["start"])) & (mins < _hm(w["end"]))).astype(bool)


def official_close(df1m, cas=None):
    """दिवसागणिक official close (= शेवटच्या bar चा close, CAS असलं तरी). Series index = तारीख (normalize)."""
    d = df1m.assign(_d=pd.to_datetime(df1m["timestamp"]).dt.normalize())
    return d.groupby("_d")["close"].last()


def daily_levels(df1m, cas=None):
    """1m ⇒ दिवसागणिक open / high / low (CAS bars वगळून) · close = official close (CAS सकट शेवटचा close) · clean_close (CAS आधीचा) · n (सर्व bars).
    PDH / PDL / PDC साठी एकच व्याख्या (chart_reader areas, vision gap_context, vision_led facts)."""
    cols = ["open", "high", "low", "close", "clean_close", "n"]
    if df1m is None or len(df1m) == 0:
        return pd.DataFrame(columns=cols)
    ts = pd.to_datetime(df1m["timestamp"])
    m = cas_mask(ts, cas).to_numpy()
    d = pd.DataFrame({"_d": ts.dt.normalize().to_numpy(), "open": df1m["open"].to_numpy(float), "high": df1m["high"].to_numpy(float),
                      "low": df1m["low"].to_numpy(float), "close": df1m["close"].to_numpy(float)})
    d["clean_close"] = d["close"]
    if m.any():
        d.loc[m, ["open", "high", "low", "clean_close"]] = float("nan")
    g = d.groupby("_d").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                            clean_close=("clean_close", "last"), n=("close", "size"))
    g.index.name = None
    return g[cols]


def pdc_col(daily):
    """Daily frame चा PDC column: `official_close` (CAS auction close) असेल तर तो, नाहीतर `close`. (resample_nse_daily चा `close` =
    CAS-आधीचा structure close; PDC / gap / fill गणित official close वर — V3 review.)"""
    if "official_close" in daily.columns:
        return daily["official_close"].where(daily["official_close"].notna(), daily["close"])
    return daily["close"]


def strip_cas(df1m, cas=None):
    """CAS bars काढलेला 1m df (structure साठी). मूळ df अबाधित."""
    m = cas_mask(df1m["timestamp"], cas).to_numpy()
    return df1m[~m].reset_index(drop=True) if m.any() else df1m


def outlier_wicks(df, k=DEFAULT_OUTLIER_WICK_MR, n=20):
    """Data-quality flag (no-lookahead): bar ची range (wick सकट) > k × मागच्या n non-flat bars च्या range चा median. bool Series.
    (CAS उडी O=L, H=C असते — wick नाही, पण range सामान्य 1m range च्या ~8 पट; गोठलेले flat bars median मध्ये घेत नाही.)"""
    h, l = df["high"].astype(float).reset_index(drop=True), df["low"].astype(float).reset_index(drop=True)
    rng = h - l
    ref = rng.where(rng > 0).shift(1).rolling(n * 3, min_periods=5).median()
    return ((rng > k * ref) & ref.gt(0)).fillna(False).astype(bool).set_axis(df.index)


__all__ = ["DEFAULT_CAS_WINDOW", "load_cas_window", "resolve", "cas_mask", "official_close", "daily_levels", "pdc_col", "strip_cas", "outlier_wicks"]
