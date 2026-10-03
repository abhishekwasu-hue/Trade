"""
htf_alignment.py
------------------
🎓 वापरकर्त्याने सांगितलेला lookahead audit (fix/completed-bars-1h) — "मोठ्या timeframe (1H/4H/Daily) चा bar कमी timeframe
ला फक्त त्याच्या **bar_end नंतरच** उपलब्ध व्हावा" याचं एकच, चाचणीयोग्य ठिकाण.

मूळ समस्या: `merge_asof(direction="backward")` ने HTF चा Supertrend/S-R कमी TF च्या bar ला त्या HTF bar च्या **सुरुवातीच्या**
timestamp (label) वर जोडला जायचा. म्हणजे 10:15 चा 15M bar, 10:00-label चा 1H bar (प्रत्यक्षात 10:15–11:15) चा **अंतिम**
Supertrend वापरायचा — अजून न घडलेला (भविष्यातला) bar. शिवाय NSE वर `resample_to_1h(30M)` चे label `09:00, 10:00…` असतात
पण bar प्रत्यक्षात `:15` ला सुरू होतो आणि `:15` ला संपतो (Upstox 30M bars 09:15 ला सुरू होतात).

उपाय: प्रत्येक HTF bar ची खरी **bar_end** (तो पूर्ण होण्याची वेळ) आणि प्रत्येक LTF bar ची **निर्णयाची वेळ** (= त्याचा स्वतःचा bar_end;
Entry नेहमी शेवटच्या closed candle च्या close वर) यावर जोडणी: HTF bar उपलब्ध ⇔ `htf_bar_end <= ltf_bar_end`.

`bar_end` कसा मिळतो:
  1. resample करणारी functions (`signals.resample_to_1h/4h`, `real_nifty_data.resample_ohlc`) `bar_end` column देतात —
     `compute_bar_end()` ने, source bars च्या त्या दिवसाच्या सुरुवातीपासूनच्या grid वरून (म्हणजे NSE 30M source असेल तर 09:15-anchored,
     1M source असेल तर clock-hour). हे अपूर्ण (चालू) bar साठीही बरोबर येतं, कारण ते उपलब्ध source bars वर नाही, अपेक्षित grid वर आधारित आहे.
  2. `bar_end` column नसेल (Upstox चे थेट 5M/15M/30M bars — label = खरी सुरुवात): `label + (अनुमानित bar कालावधी)`.
  3. Daily (सर्व label 00:00): `date + session_close` (NSE 15:30).
शेवटच्या bar चा end जाणीवपूर्वक थोडा **उशिरा** (conservative: उदा. 15:45, 16:15) येऊ शकतो — तो कधीही खऱ्या वेळेपेक्षा आधी येत नाही,
आणि त्या वेळी (बाजार बंद) कुठलाही LTF bar नसतो.

हा module फक्त pandas/numpy वापरतो (कुठलाही circular import नाही) आणि कोणताही strategy parameter बदलत नाही.
"""
import datetime

import numpy as np
import pandas as pd

NSE_CLOSE = datetime.time(15, 30)
_MAX_INTRADAY_STEP = pd.Timedelta(hours=20)


def _naive_ist(series):
    """tz-aware (Upstox, +05:30) आणि naive (offline, IST) timestamps एकाच (naive IST) रूपात — तुलना/जोडणीसाठी."""
    s = pd.Series(pd.to_datetime(series)).reset_index(drop=True)
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    # 🎓 pandas 3 मध्ये datetime64[us] आणि [ns] वेगवेगळे dtype असतात (resample/पार्स केलेल्या स्रोतावर अवलंबून) -- merge_asof ला दोन्ही बाजू एकाच
    # dtype च्या हव्यात, नाहीतर MergeError. सर्वत्र [ns].
    return s.astype("datetime64[ns]")


def infer_step(timestamps):
    """सलग timestamps मधला मध्यक (median) फरक — रात्रीचे/सुट्टीचे मोठे (>20 तास) फरक वगळून. पुरेसा डेटा नसेल तर None."""
    s = _naive_ist(timestamps).sort_values()
    diffs = s.diff().dropna()
    diffs = diffs[(diffs > pd.Timedelta(0)) & (diffs < _MAX_INTRADAY_STEP)]
    return diffs.median() if len(diffs) else None


def is_daily(timestamps):
    """सर्व timestamps 00:00 वर असतील तर Daily मालिका (label = तारीख)."""
    s = _naive_ist(timestamps)
    return len(s) > 0 and bool(((s.dt.hour == 0) & (s.dt.minute == 0)).all())


def compute_bar_end(labels, source_timestamps, bin_minutes):
    """resample केलेल्या प्रत्येक bar (`labels` = bin ची सुरुवात) ची अपेक्षित पूर्णता-वेळ.

    bin ची वरची सीमा `label + bin_minutes`; पण source bars चा grid त्या दिवसाच्या पहिल्या source bar पासून (`origin`) `step` च्या पटीत
    असतो. bar प्रत्यक्षात त्या grid वरच्या पहिल्या बिंदूला संपतो जो `label + bin_minutes` ला किंवा नंतर आहे:
        end = origin + ceil((label + bin_minutes − origin) / step) × step
    उदा. NSE 30M source (origin 09:15, step 30): label 09:00 → 10:15 ; 1M source (origin 09:15, step 1): label 09:00 → 10:00.
    रिटर्न: `labels` च्या क्रमाने pandas Series (मूळ tz जपलेला)."""
    lab_raw = pd.Series(pd.to_datetime(labels)).reset_index(drop=True)
    tz = getattr(lab_raw.dt, "tz", None)
    lab = _naive_ist(lab_raw)
    src = _naive_ist(source_timestamps).sort_values().reset_index(drop=True)
    step = infer_step(src) or pd.Timedelta(minutes=bin_minutes)
    origin_by_date = src.groupby(src.dt.date).min()
    origin = lab.dt.date.map(origin_by_date)
    upper = lab + pd.Timedelta(minutes=bin_minutes)
    ratio = (upper - origin) / step
    steps_n = np.ceil(ratio.astype("float64"))
    end = origin + pd.to_timedelta(steps_n * step.value, unit="ns")
    end = end.where(origin.notna(), upper).astype("datetime64[ns]")      # origin माहीत नसेल तर साधं label + कालावधी
    if tz is not None:
        end = end.dt.tz_localize("Asia/Kolkata").dt.tz_convert(tz)
    return end


def bar_end_times(df, session_close=NSE_CLOSE):
    """df च्या प्रत्येक bar ची पूर्णता-वेळ (naive IST Series). `bar_end` column असेल तर तेच; Daily असेल तर date + session_close;
    नाहीतर label + अनुमानित bar कालावधी (थेट Upstox bars — label = खरी सुरुवात). कालावधी अनुमानता न आल्यास label (जुनं वर्तन)."""
    if "bar_end" in df.columns:
        return _naive_ist(df["bar_end"])
    labels = _naive_ist(df["timestamp"])
    if is_daily(labels):
        close = datetime.timedelta(hours=session_close.hour, minutes=session_close.minute)
        return labels.dt.normalize() + close
    step = infer_step(labels)
    return labels if step is None else labels + step


def align_asof(ltf_df, htf_df, columns):
    """HTF df चे `columns` प्रत्येक LTF bar ला जोडणे — **फक्त** जे HTF bars LTF bar च्या निर्णय-वेळेपर्यंत (त्याच्या bar_end पर्यंत) पूर्ण झालेले आहेत.
    रिटर्न: ltf_df च्याच row-क्रमाने (RangeIndex) DataFrame; अजून कुठलाच HTF bar पूर्ण नसेल तर NaN."""
    columns = list(columns)
    left = pd.DataFrame({"_key": bar_end_times(ltf_df).values, "_pos": np.arange(len(ltf_df))}).sort_values("_key")
    right = htf_df[columns].reset_index(drop=True).copy()
    right["_key"] = bar_end_times(htf_df).values
    right = right.sort_values("_key")
    aligned = pd.merge_asof(left, right, on="_key", direction="backward").sort_values("_pos")
    return aligned[columns].reset_index(drop=True)
