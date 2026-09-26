"""
cloud_db.py
---------------
OI Diff Snapshot डेटासाठी Cloud Database (Supabase/PostgreSQL) — वापरकर्त्याशी चर्चा करून
ठरवलेली सुधारणा. Local machine वरच्या unattended scripts (oi_snapshot_collector.py) आणि Streamlit
Cloud वरचं Dashboard — दोन्ही याच एका, सामायिक (shared) database शी बोलतात, त्यामुळे local script ने
साठवलेला डेटा लगेच Cloud Dashboard वरही दिसतो (आधीच्या स्वतंत्र, न-जोडलेल्या SQLite फाईल्सच्या
समस्येवर हाच खरा उपाय).

⚙️ Setup (एकदाच, वापरकर्त्याने स्वतः करायचं):
  १. https://supabase.com वर मोफत खातं तयार करा, नवीन Project बनवा.
  २. Project Settings -> Database -> Connection String (URI) कॉपी करा
     (उदा. postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres)
  ३. ही स्ट्रिंग पर्यावरण चल (environment variable) 'SUPABASE_DB_URL' मध्ये ठेवा, किंवा
     data/notification_config.json मध्ये {"supabase_db_url": "..."} असं जोडा.
  ४. Streamlit Cloud वर: App Settings -> Secrets मध्ये SUPABASE_DB_URL जोडा.

Connection string सेट केलेली नसेल तर — सर्व function शांतपणे (None, "...उपलब्ध नाही") परत देतात,
कुठेही crash होत नाही (त्या स्थितीत Dashboard जुन्याच local SQLite कडे आपोआप वळतो).

⚠️ प्रामाणिक इशारा: हा कोड psycopg2 + मानक PostgreSQL syntax वापरून लिहिला आहे, पण या विकास
वातावरणात खऱ्या Supabase/PostgreSQL सर्व्हरशी जोडून चाचणी करता आलेली नाही (network प्रतिबंधामुळे) —
फक्त तर्कशास्त्र (mocked connection सह) पडताळलं आहे. कृपया तुमच्या स्वतःच्या Supabase वर एकदा
प्रत्यक्ष चाचणी करा.
"""
import datetime
import json
import os

import pandas as pd

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.extensions
except ImportError:
    psycopg2 = None

# 🎓 वापरकर्त्याने प्रत्यक्ष VPS वर सापडवलेली, गंभीर bug — MCX Level Hit Log (आणि संभाव्यतः
# NIFTY/BANKNIFTY/SENSEX चा Signal Log सुद्धा, तोच कोड-मार्ग) कायम रिकामाच दिसायचा — प्रत्यक्ष
# `data/app.log` मध्ये सापडलं: `psycopg2.errors.InvalidSchemaName: schema "np" does not exist`,
# SQL मध्ये अक्षरशः `np.float64(1416.2)` असा मजकूर embed झालेला. मूळ कारण: `zone_low`/`level_price`
# सारखी मूल्यं pandas DataFrame मधून येतात (numpy.float64 प्रकारात, कधीच plain Python float मध्ये
# रूपांतरित न होता — dynamic_sr_instant_trader.py/mcx_futures_trader.py दोन्हीकडे). NumPy 2.x
# (requirements.txt: `numpy~=2.4`) पासून `numpy.float64` चं repr "np.float64(1416.2)" असं दाखवतं
# (जुन्या NumPy मध्ये नुसतं "1416.2") — आणि psycopg2 चा डीफॉल्ट adapter त्याच repr वर अवलंबून असल्याने,
# प्रत्येक असा INSERT/UPDATE (कुठलाही error/exception caller ला कधीच न दिसता, फक्त `data/app.log`
# मध्ये शांतपणे नोंदवला जायचा — save_signal_log() सारख्या सर्वच function मध्ये `except Exception`
# आहे) सुरुवातीपासूनच अयशस्वी होत होता. एकाच, केंद्रीय ठिकाणी (इथेच, import च्या वेळीच एकदा) योग्य
# adapters नोंदवून, कुठल्याही caller ला स्वतः `float()`/`int()` cast लक्षात ठेवायची गरज उरत नाही —
# आत्ताचे आणि भविष्यातले सर्वच numpy-सोर्स्ड मूल्यं आपोआप बरोबर लिहिली जातील.
if psycopg2 is not None:
    try:
        import numpy as _np
        psycopg2.extensions.register_adapter(_np.float64, lambda val: psycopg2.extensions.AsIs(float(val)))
        psycopg2.extensions.register_adapter(_np.float32, lambda val: psycopg2.extensions.AsIs(float(val)))
        psycopg2.extensions.register_adapter(_np.int64, lambda val: psycopg2.extensions.AsIs(int(val)))
        psycopg2.extensions.register_adapter(_np.int32, lambda val: psycopg2.extensions.AsIs(int(val)))
        psycopg2.extensions.register_adapter(_np.bool_, lambda val: psycopg2.extensions.AsIs(bool(val)))
    except ImportError:
        pass  # numpy उपलब्ध नाही (अत्यंत दुर्मिळ) -- तरी psycopg2 इतर सर्व प्रकारांसाठी काम करत राहील

from crypto_utils import encrypt_token, decrypt_token
from log_setup import get_logger

_logger = get_logger("cloud_db.py")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, "data", "notification_config.json")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS oi_diff_snapshots (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    total_call_oi BIGINT,
    total_put_oi BIGINT,
    diff BIGINT,
    delta_diff BIGINT,
    signal TEXT,
    underlying_price REAL,
    total_call_premium REAL,
    total_put_premium REAL,
    PRIMARY KEY (symbol, trade_date, snapshot_time)
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Upstox Access Token Request + Notifier Webhook
# पद्धतीने रोज एका टॅपवर मिळणारा नवीन token, इथे साठवला जातो — GitHub Actions आणि Streamlit Dashboard
# दोन्ही इथूनच वाचतील, त्यामुळे कुठेही मॅन्युअल paste लागणार नाही.
CREATE_TOKEN_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS upstox_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT NOT NULL,
    account_id TEXT,
    received_at TIMESTAMP NOT NULL DEFAULT NOW()
);
ALTER TABLE upstox_tokens ADD COLUMN IF NOT EXISTS account_id TEXT;
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — S/R, Order Block, Demand/Supply Zone, Unfilled Gap
# या सर्व विश्लेषणाचा निकाल इथेच साठवला जातो — प्रत्येक वेळी पुन्हा गणना न करता, Dashboard/रणनीती
# थेट इथूनच वाचू शकतील (भविष्यातलं trade-planning जलद व्हावं म्हणून).
CREATE_ZONES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS market_zones (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    zone_type TEXT NOT NULL,
    zone_low REAL NOT NULL,
    zone_high REAL NOT NULL,
    strength REAL,
    formed_date TIMESTAMP,
    status TEXT NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull च्या "Multi Strike OI" सारखं, प्रत्येक strike
# चा OI इतिहास (वेळेनुसार) साठवण्यासाठी — आधी फक्त एकूण (Total) Call/Put OI साठवला जायचा.
# oi_snapshot_collector.py आधीच प्रत्येक strike चा डेटा वाचतो (aggregate करण्यासाठी) — तोच पुनर्वापर.
CREATE_STRIKE_OI_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strike_oi_history (
    symbol TEXT NOT NULL,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    oi BIGINT,
    PRIMARY KEY (symbol, strike, option_type, trade_date, snapshot_time)
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Record iv of option premium daily for analysis") —
# रोज "काल IV काय होता, आज काय आहे" अशी तुलना हाताने (PDF/live fetch वरून) करण्याऐवजी, iv_snapshot_
# collector.py कडून रोज एकदा (EOD आधी) साठवलेला, ATM-भोवतीचा IV इतिहास — strike_oi_history सारखाच
# upsert पॅटर्न (त्याच दिवशी पुन्हा चालवलं तरी duplicate rows नाहीत, फक्त अद्ययावत).
CREATE_IV_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS iv_history (
    symbol TEXT NOT NULL,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    expiry TEXT,
    iv REAL,
    ltp REAL,
    underlying_price REAL,
    PRIMARY KEY (symbol, strike, option_type, trade_date, snapshot_time)
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — गेल्या ५+ वर्षांचा (प्रत्यक्षात संपूर्ण उपलब्ध इतिहास,
# 2015 पासून) NIFTY 1-मिनिट OHLC डेटा, रोज आपोआप अद्ययावत होणारा — जेणेकरून Backtest/Demand-Supply/
# S-R गणना प्रत्येक वेळी थेट Upstox वरून (मर्यादित lookback सह) डेटा न मागवता, इथूनच वाचू शकतील.
CREATE_NIFTY_1MIN_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nifty_1min_ohlc (
    timestamp TIMESTAMP PRIMARY KEY,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume BIGINT DEFAULT 0
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — High-Frequency 1-मिनिट S/R रणनीतीचा प्रत्येक शोधलेला
# सिग्नल (trade झाला किंवा न झाला तरीही) — Dashboard वर संपूर्ण intraday Signal Log दाखवण्यासाठी.
CREATE_SIGNAL_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS signal_log (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    signal_time TIMESTAMP NOT NULL,
    level_type TEXT NOT NULL,
    level_price REAL NOT NULL,
    hit_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    ltp_at_signal REAL,
    trade_status TEXT,
    reason TEXT
);
"""

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Nifty SRv2 Momentum-Filter Reversal" रणनीतीचं
# राज्य (One-Touch Rule + Cooldown Period) — GitHub Actions प्रत्येक वेळी नवीन (rikama) environment
# मध्ये चालत असल्याने, हे राज्य Supabase मध्येच साठवावं लागतं (स्थानिक फाईल टिकत नाही).
CREATE_SRV2_STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS srv2_strategy_state (
    symbol TEXT PRIMARY KEY,
    last_tested_level REAL,
    last_sl_hit_time TIMESTAMP
);
"""

# वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — SRv2 चे lots/hedge_width_points आता Dashboard वरून
# बदलता येतील (hardcode नाही). symbol प्रत्येकाची स्वतंत्र नोंद.
CREATE_SRV2_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS srv2_settings (
    symbol TEXT PRIMARY KEY,
    lots INTEGER NOT NULL DEFAULT 1,
    hedge_width_points REAL NOT NULL DEFAULT 100,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

# वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) — एकाच, flexible
# table मध्ये कुठल्याही strategy चे settings — नवीन field जोडायला schema-बदल (migration) लागू नये
# म्हणून JSONB. (strategy_name, symbol) प्रत्येकाची स्वतंत्र नोंद.
CREATE_STRATEGY_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strategy_settings (
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    settings JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (strategy_name, symbol)
);
"""

# वापरकर्त्याशी चर्चा करून ठरवलेले, नवीन नियम-संचातले डीफॉल्ट — Dashboard वरून बदलले नसतील तर हेच
# वापरले जातात (कधीच hardcoded राहत नाहीत — इथूनच, एकाच जागी, बदलण्याजोगे).
STRATEGY_SETTINGS_DEFAULTS = {
    "1m_instant": {
        "lots": 1,
        "itm_depth_points": 50,          # Short leg — ATM पासून किती points ITM
        "hedge_width_points": 150,       # Long hedge — short strike पासून किती दूर
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — 1M touches प्रत्यक्षात profitable नाहीत असं
        # वापरकर्त्याने backtest/live track-record वरून सांगितलं, त्यामुळे डीफॉल्ट आता फक्त "5M"
        # (आधी "BOTH", म्हणजे 1M+5M दोन्ही एकत्र पूल केलेले). वापरकर्ता Dashboard वरून "1M" किंवा
        # "BOTH" निवडून जुनं वर्तनही परत आणू शकतो — फक्त डीफॉल्ट बदलला आहे.
        "timeframe_choice": "5M",      # "BOTH" | "1M" | "5M"
        # वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Entry Gate — RSI/PCR आता on/off + adjustable) —
        # आधी RSI उंबरठे (Support<40/Resistance>60) module मध्ये hardcoded होते, PCR गेट कधीच बंद
        # करता येत नव्हता. आता दोन्ही Dashboard वरून (Entry Gate विभाग) नियंत्रित करता येतात —
        # डीफॉल्ट दोन्ही चालू, जुनेच उंबरठे, म्हणजे न बदलणाऱ्या वापरकर्त्यांसाठी वर्तन तेच राहतं.
        "entry_rsi_gate_enabled": True,
        "rsi_support_max": 40,           # Support/Bullish साठी RSI यापेक्षा कमी हवा
        "rsi_resistance_min": 60,        # Resistance/Bearish साठी RSI यापेक्षा जास्त हवा
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — फक्त त्या दिशेचे नवीन trades थांबतात (आधीच उघडलेले चालूच राहतात) — इतर
        # सर्व gates च्याही आधी तपासलं जातं. डीफॉल्ट दोन्ही चालू (जुनंच वर्तन).
        "bullish_entry_enabled": True,
        "bearish_entry_enabled": True,
        "entry_pcr_gate_enabled": True,
        # PCR < pcr_bullish_min -> Bullish trade नाही. PCR > pcr_bearish_max -> Bearish trade नाही.
        # डेटा गहाळ/जुना असल्यास trade थांबवणे (fail-safe) — हे PCR गेट बंद असतानाही लागू होत नाही.
        "pcr_bullish_min": 0.80,
        "pcr_bearish_max": 1.10,
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("5 minute instant dynamic sr strategy work
        # better in sideways, low iv or average iv market, but in trending when Breakout happen it
        # books loss") — Average IV Breakout Gate — आजचा ATM IV गेल्या iv_lookback_days दिवसांच्या
        # सरासरी ATM IV पेक्षा iv_change_max_pct% पेक्षा जास्त वाढलेला असेल, तर (दोन्ही दिशांना
        # सारखंच — PCR सारखा directional नाही, VIX Spike Halt सारखं regime-सिग्नल) नवीन entry
        # थांबवली जाते. डीफॉल्ट बंद (नवीन/अपरीक्षित — पुरेसा iv_history इतिहास जमेपर्यंत वापरकर्त्याने
        # स्वतः चालू करायचा).
        "entry_iv_gate_enabled": False,
        "iv_change_max_pct": 15.0,
        "iv_lookback_days": 10,
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("All should be user friendly gate, no
        # hardcoded" + "Simple day candle is marabozu ... is trending") — baseline साठी कुठले
        # मागचे दिवस "sideways" धरायचे हे ठरवणारा Marubozu body_ratio threshold — आधी module-level
        # हार्डकोड (MARUBOZU_TRENDING_THRESHOLD=0.8) होता, आता Dashboard वरून बदलण्याजोगा.
        "iv_marubozu_threshold": 0.8,
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Max 2 trade on same level hit, he honar
        # donhi sl or tsl hit jhalet, ani nantr jar Breakout buildup and 5 minute candle closed
        # happen then take entry in the same direction") — Breakout Entry — max-2-hits च्या
        # पलीकडचा, तिसरा trade. "buildup" पूर्णपणे price-data वरून (trade-outcome/live_trades वर
        # अवलंबून नाही, त्यामुळे IV/RSI/PCR Gate ने आधीचे touches block केले तरी काम करतं) —
        # breakout-candle च्या आधीच्या `breakout_lookback_candles` 5-मिनिट candles मध्ये price
        # level च्या ±`breakout_tolerance_pct`% च्या आत consolidate झालेला असावा, आणि नंतर एक
        # 5-मिनिट candle त्या level च्या पलीकडे breakout-दिशेने close झाला तरच. डीफॉल्ट बंद — इतर
        # नवीन gates सारखाच, वापरकर्त्याने स्वतः Dashboard वरून चालू करायचा.
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Candle 5 minute chi asel tar kiman 12
        # candle chi range calculator hawi") — डीफॉल्ट lookback 6 (30 मिनिट) वरून 12 (1 तास) —
        # Dashboard वरून बदलण्याजोगंच (hardcoded नाही, already user-friendly number_input).
        "entry_breakout_gate_enabled": False,
        "breakout_lookback_candles": 12,
        "breakout_tolerance_pct": 0.30,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Same level war pahilya trade cha sl tsl hit jhalyas
        # kiman 15 minute same level war trade ghewu naye, cooldown") — established (max-2-hits
        # असूनही) आजचा दुसरा touch त्याच level वर पहिल्या touch नंतर अवघ्या 1 मिनिटातच entry घेऊ
        # शकतो (established generic 30-मिनिट cooldown established फक्त breakout trade साठी वगळलेला
        # आहे, पण established दुसऱ्या (max-2-hits च्या आतल्याच) touch साठी established लागू व्हायला
        # हवा होता — तरीही प्रत्यक्ष रिपोर्टमध्ये तो अवघ्या 1 मिनिटात bypass झालेला दिसला, त्यामुळे
        # हा वेगळा, established exit-वेळेवर आधारित (entry-signal-वेळेऐवजी) गेट — established त्याच
        # exact level वर established आधीचा SL/TSL-प्रकारचा exit किती मिनिटांपूर्वी झाला हे थेट
        # live_trades वरून बघतो, established entry_level_price + exit_reason LIKE '%SL%' वरून).
        # TARGET/EOD/इतर profitable/neutral exits यांना लागू होत नाही — फक्त whipsaw/fakeout नंतरचं
        # संरक्षण. डीफॉल्ट 15 मिनिटं (वापरकर्त्याने तेच सांगितलं) — 0 केलं की हा गेट पूर्णपणे बंद.
        "sl_tsl_cooldown_minutes": 15,
        "spread_sl_spot_pct": 0.05,
        "spread_sl_premium_points": 5,
        "spread_tsl_spot_pct": 0.10,
        "spread_tsl_premium_points": 10,
        "spread_target_spot_pct": 0.20,
        "spread_target_premium_points": 15,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Naked Option Buy आणि Credit Spread दोन्ही
        # independently optional असायला पाहिजेत — कमी कॅपिटल असलेला user फक्त naked करणं
        # पसंत करतो") — आधी credit spread नेहमीच चालायचा (toggle नव्हता), फक्त naked ऐच्छिक
        # होता. आता दोन्ही स्वतंत्रपणे on/off — डीफॉल्ट True (आधीच्याच वर्तनाशी सुसंगत).
        "credit_spread_enabled": True,
        "naked_enabled": True,           # "on the same signal" -- डीफॉल्ट सक्रिय, Dashboard वरून बंद करता येईल
        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Credit Spread ITM वि. OTM स्ट्राइक निवड —
        # "profit loss आणि charges या सर्व गोष्टींचा विचार करून त्या स्ट्राइक प्राइस फायदेशीर वाटतात
        # का की OTM स्ट्राइक निवडावा") — जुन्या expired तारखांचा actual option premium डेटा Upstox
        # कडून मिळत नसल्याने खरा historical backtest शक्य नाही (बघा backtest.py ची स्वतःचीच मर्यादा-
        # टिप्पणी); त्याऐवजी forward-test — याच सिग्नलवर, खऱ्या (ITM) trade सोबतच, एक स्वतंत्र, निव्वळ
        # PAPER-only OTM पर्याय (select_credit_spread_fixed_strikes(), वेगळ्याच
        # source="dynamic_sr_instant_otm_shadow" ने — मूळ strategy च्या PAPER/LIVE आकडेवारीत कधीच
        # मिसळत नाही) समांतर लॉग होतो — काही काळानंतर Performance Report वर दोन्हींची प्रत्यक्ष तुलना
        # करता येईल. डीफॉल्ट बंद, आणि सुरुवातीला (वापरकर्त्याच्या सूचनेनुसार) फक्त "5M" touches पुरतंच
        # मर्यादित (timeframe_suffix तपासूनच, dynamic_sr_instant_trader.py मध्ये).
        "otm_shadow_enabled": False,
        "otm_shadow_strikes_count": 2,   # ATM पासून किती strikes OTM (select_credit_spread_fixed_strikes चा strikes_otm)
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा — Naked Option Trade आधी नेहमी Credit Spread च्याच
        # "lots" इतकेच lots घ्यायचा (वेगळं सेटिंगच नव्हतं) — पण दोन्ही वेगळ्या जोखीम/भांडवल-गरजेचे
        # trade-प्रकार असल्याने वापरकर्त्याला ते स्वतंत्रपणे ठरवता यायला हवं. डीफॉल्ट "lots" इतकाच
        # (1) — आधीच सेटिंग्ज न बदललेल्या वापरकर्त्यांसाठी वर्तन तेच राहतं.
        "naked_lots": 1,
        "naked_hedge_enabled": False,    # डीफॉल्ट: निव्वळ (naked) buy, hedge नाही
        "naked_hedge_width_points": 150,
        "naked_sl_spot_pct": 0.05,
        "naked_sl_premium_points": 10,
        "naked_tsl_spot_pct": 0.10,
        "naked_tsl_premium_points": 20,
        "naked_target_spot_pct": 0.20,
        "naked_target_premium_points": 30,
        # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("user defined trailing stop loss for all
        # strategies") — आधीचा TSL_SL एकदाच सक्रिय झाल्यावर SL कायमचा Entry/Breakeven वर अडकायचा
        # (evaluate_point_spot_exit, अजूनही न बदललेला). आता, हा नवीन टॉगल चालू केल्यास, TSL सक्रिय
        # झाल्यानंतर SL Breakeven ऐवजी सतत नफ्याच्या मागे-मागे (Peak Premium Points - trailing
        # distance) सरकत राहतो — Premium Points याच युनिटमध्ये (वापरकर्त्याने निवडलेल्या पद्धतीनुसार).
        # डीफॉल्ट बंद — जुनं (Breakeven-only) वर्तन न बदलणाऱ्या वापरकर्त्यांसाठी तेच राहतं.
        "spread_trailing_sl_enabled": False,
        "spread_trailing_distance_points": 5,
        "naked_trailing_sl_enabled": False,
        "naked_trailing_distance_points": 10,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("PAPER/LIVE toggle + broker selection, per strategy") —
        # डीफॉल्ट नेहमी PAPER (न बदलणाऱ्या वापरकर्त्यांसाठी जुनंच, सुरक्षित वर्तन कायम). LIVE केलं तरच
        # bot scripts (dynamic_sr_instant_trader.py/srv2_momentum_reversal_strategy.py/
        # classic_sr_reversal_trader.py) खरे ऑर्डर्स पाठवतात.
        "trading_mode": "PAPER",     # "PAPER" | "LIVE" | "LIVE_PAPER" (LIVE + शॅडो PAPER तुलना)
        # broker_account_ids — रिकामी यादी (डीफॉल्ट) = शुद्ध Upstox, single trade (जुनंच वर्तन).
        # वापरकर्त्याने broker_accounts मधून एक किंवा अनेक account_id निवडले, तर त्या प्रत्येक
        # account वर स्वतंत्र trade उघडला जातो (प्रत्येकाचं स्वतःचं SL/TSL/Target management).
        "broker_account_ids": [],
        # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL") — डीफॉल्ट बंद.
        # चालू केल्यास, entry नंतर लगेच Upstox कडेच resting SL-M order ठेवला जातो (फक्त LIVE —
        # PAPER/LIVE_PAPER मध्ये फक्त trigger price ची dry-run गणना+लॉग होते, खरा order नाही) —
        # trade_monitor.py च्या polling-based SL सोबतच, exchange-level backstop म्हणून.
        "broker_side_sl_enabled": False,
    },
    "15m_dynamic_sr": {
        "lots": 1,
        "itm_depth_points": 100,
        "hedge_width_points": 150,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("RSI setting 60/40 अशी करा") — established single,
        # सममित rsi_neutral_level (50, Support<50/Resistance>50) ऐवजी आता 1m_instant/mcx_futures
        # सारखाच dual-threshold RSI गेट.
        "entry_rsi_gate_enabled": True,
        "rsi_support_max": 40,           # Support/Bullish साठी RSI यापेक्षा कमी हवा
        "rsi_resistance_min": 60,        # Resistance/Bearish साठी RSI यापेक्षा जास्त हवा
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — फक्त त्या दिशेचे नवीन trades थांबतात (आधीच उघडलेले चालूच राहतात). डीफॉल्ट
        # दोन्ही चालू (जुनंच वर्तन).
        "bullish_entry_enabled": True,
        "bearish_entry_enabled": True,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("3 वेगवेगळे timeframe आहेत, selection user friendly
        # असू द्या, डीफॉल्ट 15 मिनिट ठेवा, 30 आणि 60 मिनिट optional राहील") — आधी तिन्ही (15M/30M/60M)
        # नेहमीच एकत्र तपासले जायचे, निवडीची सोयच नव्हती.
        "active_timeframes": ["15M"],    # ["15M"] | ["15M","30M"] | ["15M","30M","60M"] | इ. — किमान एक हवा
        "entry_pcr_gate_enabled": True,
        "pcr_bullish_min": 0.80,
        "pcr_bearish_max": 1.10,
        "spread_sl_spot_pct": 0.15,
        "spread_sl_premium_points": 10,
        "spread_tsl_spot_pct": 0.30,
        "spread_tsl_premium_points": 25,
        "spread_target_pct_of_premium": 80,
        "carry_forward_min_profit_pct": 30,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Same level war pahilya trade cha sl tsl hit jhalyas
        # kiman 15 minute same level war trade ghewu naye, cooldown") — 1m_instant सारखीच (वरची
        # टिप्पणी बघा) — त्याच exact level वर आधीचा SL/TSL-प्रकारचा exit किती मिनिटांपूर्वी झाला हे
        # थेट live_trades वरून बघणारा गेट. डीफॉल्ट 15 मिनिटं — 0 केलं की बंद.
        "sl_tsl_cooldown_minutes": 15,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Naked Option Buy आणि Credit Spread दोन्ही
        # independently optional असायला पाहिजेत — कमी कॅपिटल असलेला user फक्त naked करणं
        # पसंत करतो") — आधी credit spread नेहमीच चालायचा (toggle नव्हता), फक्त naked ऐच्छिक
        # होता. आता दोन्ही स्वतंत्रपणे on/off — डीफॉल्ट True (आधीच्याच वर्तनाशी सुसंगत).
        "credit_spread_enabled": True,
        "naked_enabled": True,
        "naked_lots": 1,                 # 🎓 1m_instant सारखीच सुधारणा — Credit Spread पासून स्वतंत्र lots
        "naked_hedge_enabled": False,
        "naked_hedge_width_points": 150,
        "naked_sl_spot_pct": 0.05,
        "naked_sl_premium_points": 10,
        "naked_tsl_spot_pct": 0.10,
        "naked_tsl_premium_points": 20,
        "naked_target_spot_pct": 0.40,
        "naked_target_premium_points": 50,
        "naked_eod_hour": 15,            # Naked trades कधीच carry-forward नाहीत, नेहमी आजच 3:00pm ला बंद
        "naked_eod_minute": 0,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("user defined trailing stop loss for all strategies") —
        # 1m_instant सारखीच, Premium Points आधारित सतत Trailing Stop (TSL सक्रिय झाल्यानंतर, Breakeven
        # ऐवजी). डीफॉल्ट बंद.
        "spread_trailing_sl_enabled": False,
        "spread_trailing_distance_points": 8,
        "naked_trailing_sl_enabled": False,
        "naked_trailing_distance_points": 15,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("PAPER/LIVE toggle + broker selection, per strategy") —
        # 1m_instant सारखीच. डीफॉल्ट नेहमी PAPER, broker_account_ids रिकामी (= शुद्ध Upstox).
        "trading_mode": "PAPER",
        "broker_account_ids": [],
        # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL") — 1m_instant
        # सारखीच, डीफॉल्ट बंद.
        "broker_side_sl_enabled": False,
    },
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली स्वतंत्र, नवीन strategy — "Classical Support/Resistance
    # Reversal" (5M+15M pooled, Support touch -> Bull Put Spread, Resistance touch -> Bear Call
    # Spread — तोच classical Dynamic S/R अल्गोरिदम जो Market Zones साठी वापरला जातो). backtest मध्ये
    # ठरल्याप्रमाणे — PCR गेट मुद्दाम नाही (फक्त "शुद्ध classical S/R" कल्पना, RSI गेटच फक्त),
    # आणि तीन नवीन ऐच्छिक Entry Refinement गेट्स (Swing High/Low, Demand/Supply, Trendline) — सर्व
    # डीफॉल्ट बंद, backtest मध्ये वापरलेल्याच डीफॉल्ट मूल्यांसह.
    "classic_sr_reversal": {
        "lots": 1,
        "itm_depth_points": 50,
        "hedge_width_points": 150,
        "timeframe_choice": "BOTH",      # "BOTH" | "5M" | "15M"
        "entry_rsi_gate_enabled": True,
        "rsi_neutral_level": 50,
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — फक्त त्या दिशेचे नवीन trades थांबतात (आधीच उघडलेले चालूच राहतात). डीफॉल्ट
        # दोन्ही चालू (जुनंच वर्तन).
        "bullish_entry_enabled": True,
        "bearish_entry_enabled": True,
        # Entry Refinement — तिन्ही ऐच्छिक, स्वतंत्र (backtest.run_classic_sr_reversal_backtest()
        # मधल्याच गेट्सशी सुसंगत तर्क आणि डीफॉल्ट मूल्यं).
        "swing_confluence_enabled": False,
        "swing_tolerance_pct": 0.15,
        # 🎓 वापरकर्त्याने प्रत्यक्ष चार्ट screenshot वरून "major swings only" (किरकोळ noise-स्विंग्स
        # वगळून फक्त खरोखर लक्षणीय turning points) दाखवलं आणि तीच कल्पना strategy मध्ये आणायला सांगितलं
        # — दोन्ही एकत्र: (१) swing_order डीफॉल्ट 3 वरून 5 केला (fractal शोधासाठी दोन्ही बाजूला जास्त
        # bars, आपोआप किरकोळ wiggles कमी पकडले जातात), (२) नवीन swing_min_move_pct (डीफॉल्ट 0.5%) —
        # signals.filter_major_swings() द्वारे, मागच्या स्विंगपासून किमान इतकी % हालचाल नसेल तर तो
        # स्विंग confluence साठी वापरला जात नाही (ZigZag-सारखा magnitude फिल्टर, fractal शोधीच्या वर).
        "swing_order": 5,
        "swing_min_move_pct": 0.5,
        "demand_supply_gate_enabled": False,
        "trendline_gate_enabled": False,
        "trendline_lookback_swings": 4,
        "spread_sl_spot_pct": 0.4,
        "spread_sl_premium_points": 5,
        "spread_tsl_spot_pct": 0.6,
        "spread_tsl_premium_points": 10,
        "spread_target_spot_pct": 0.8,
        "spread_target_premium_points": 15,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Same level war pahilya trade cha sl tsl hit jhalyas
        # kiman 15 minute same level war trade ghewu naye, cooldown") — 1m_instant सारखीच (बघा तिथली
        # टिप्पणी) — त्याच exact level वर आधीचा SL/TSL-प्रकारचा exit किती मिनिटांपूर्वी झाला हे थेट
        # live_trades वरून बघणारा गेट. डीफॉल्ट 15 मिनिटं — 0 केलं की बंद.
        "sl_tsl_cooldown_minutes": 15,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Naked Option Buy आणि Credit Spread दोन्ही
        # independently optional असायला पाहिजेत — कमी कॅपिटल असलेला user फक्त naked करणं
        # पसंत करतो") — आधी credit spread नेहमीच चालायचा (toggle नव्हता), फक्त naked ऐच्छिक
        # होता. आता दोन्ही स्वतंत्रपणे on/off — डीफॉल्ट True (आधीच्याच वर्तनाशी सुसंगत).
        "credit_spread_enabled": True,
        "naked_enabled": True,
        "naked_lots": 1,                 # 🎓 1m_instant सारखीच सुधारणा — Credit Spread पासून स्वतंत्र lots
        "naked_hedge_enabled": False,
        "naked_hedge_width_points": 150,
        "naked_sl_spot_pct": 0.4,
        "naked_sl_premium_points": 10,
        "naked_tsl_spot_pct": 0.6,
        "naked_tsl_premium_points": 20,
        "naked_target_spot_pct": 0.8,
        "naked_target_premium_points": 30,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("user defined trailing stop loss for all strategies") —
        # 1m_instant सारखीच, Premium Points आधारित सतत Trailing Stop (TSL सक्रिय झाल्यानंतर, Breakeven
        # ऐवजी). डीफॉल्ट बंद.
        "spread_trailing_sl_enabled": False,
        "spread_trailing_distance_points": 5,
        "naked_trailing_sl_enabled": False,
        "naked_trailing_distance_points": 10,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("PAPER/LIVE toggle + broker selection, per strategy") —
        # 1m_instant सारखीच. डीफॉल्ट नेहमी PAPER, broker_account_ids रिकामी (= शुद्ध Upstox).
        "trading_mode": "PAPER",
        "broker_account_ids": [],
        # 🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Phase 2 — broker-side SL") — 1m_instant
        # सारखीच, डीफॉल्ट बंद.
        "broker_side_sl_enabled": False,
    },
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली, संपूर्णपणे नवीन, स्वतंत्र strategy — MCX Futures Trader
    # (CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER). इतर तिन्ही strategies (NIFTY/BANKNIFTY/SENSEX options)
    # यांना अजिबात हात लावलेला नाही — पूर्णपणे वेगळी, स्वतःची settings/execution. Upstox चा Option
    # Chain API MCX साठी उपलब्धच नाही, त्यामुळे ही options (credit spread/naked) नाही — सरळ Futures
    # contract खरेदी/विक्री (S/R touch झाला की), त्यामुळे इथे net_credit/strike-निवड/hedge हे concept
    # लागू नाहीत — SL/Target सरळ futures points मध्ये.
    "mcx_futures": {
        "lots": 1,                       # प्रत्यक्ष quantity = lots × commodity चा स्वतःचा lot_size (Upstox कडून)
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("30 minute candle", नंतर explicit केलं — हा MCX strategy
        # साठीच, existing NIFTY bots साठी नाही) — डीफॉल्ट फक्त 30M, 15M हा पर्यायच नाही (कधीच नाही).
        "timeframe_choice": "30M",       # "30M" | "60M" | "ALL" (30M+60M दोन्ही — 15M कधीच नाही)
        "entry_rsi_gate_enabled": True,
        "rsi_support_max": 40,           # Support/Bullish साठी RSI यापेक्षा कमी हवा
        "rsi_resistance_min": 60,        # Resistance/Bearish साठी RSI यापेक्षा जास्त हवा
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
        # सुद्धा पाहिजे") — फक्त त्या दिशेचे नवीन trades थांबतात (आधीच उघडलेले चालूच राहतात). डीफॉल्ट
        # दोन्ही चालू (जुनंच वर्तन).
        "bullish_entry_enabled": True,
        "bearish_entry_enabled": True,
        "sl_points": 20,                 # Stop Loss — underlying futures points (options premium नाही)
        "target_points": 40,             # Target — underlying futures points
        "trailing_sl_enabled": False,
        "trailing_distance_points": 10,
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा ("SL/Target/Trailing SL also on percentage, add other
        # gate") — Points सोबतच आता Percentage (entry किंमतीच्या % वर आधारित) हा पर्यायी mode —
        # डीफॉल्ट "POINTS" (आधीचंच वर्तन, backward-compatible). दोन्ही सेटिंग्ज कायम साठवलेली राहतात
        # (mode बदलला तरी मागचा भरलेला आकडा हरवत नाही) — फक्त निवडलेला mode प्रत्यक्ष वापरला जातो.
        "sl_target_mode": "POINTS",      # "POINTS" | "PERCENT"
        "sl_pct": 2.0,                   # Stop Loss — entry किंमतीच्या % (sl_target_mode="PERCENT" असेल तरच)
        "target_pct": 4.0,               # Target — entry किंमतीच्या %
        "trailing_pct": 1.0,             # Trailing SL अंतर — सद्य किंमतीच्या % (trailing_sl_enabled सोबतच)
        "trading_mode": "PAPER",
        "broker_account_ids": [],
        # 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Mcx comodity sathi suddha he feature add
        # kra, Breakout buildup waril A and C mix logic") — 1m_instant मधलाच Breakout Entry
        # (max-2-hits च्या पलीकडचा, तिसरा trade) आता MCX Futures साठीही — तेच price-consolidation
        # (A: hit_count_so_far>=2, C: check_breakout_price_consolidation) लॉजिक, फक्त इथे स्वतंत्र
        # 5-मिनिट candles fetch न करता, त्याच candidate च्या स्वतःच्याच timeframe (30M/60M) candles
        # वर (todays_closes) चालवलेलं — MCX ची touch-granularity आधीच त्या timeframe इतकी असल्याने
        # वेगळी finer-interval fetch ची गरज नाही. डीफॉल्ट बंद, Dashboard वरून बदलण्याजोगं.
        "entry_breakout_gate_enabled": False,
        "breakout_lookback_candles": 12,
        "breakout_tolerance_pct": 0.30,
    },
}

# वापरकर्त्याने सापडवलेली bug — वरचे itm_depth_points/hedge_width_points/naked_hedge_width_points
# डीफॉल्ट NIFTY (strike step 50) साठी ठरवलेले आहेत, पण सर्व तीनही symbols साठी तेच सपाट आकडे
# दाखवले जायचे — BANKNIFTY/SENSEX चा strike step 100 (NIFTY च्या दुप्पट) असल्याने तोच आकडा त्यांच्यासाठी
# प्रत्यक्षात निम्म्या strikes-ITM ला जातो, प्रमाणाबाहेर. खालचा STRIKE_STEP आणि _scale_strike_relative_defaults()
# हे फक्त strike-निवडीशी संबंधित (points) fields, symbol च्या स्वतःच्या strike step नुसार प्रमाणात
# मोठे/लहान करतात — फक्त वापरकर्त्याने अजून त्या symbol साठी स्वतः customize न केलेल्या डीफॉल्टवरच लागू
# होतं (एकदा जतन केलं की तोच जतन केलेला आकडा कायम वापरला जातो, इथे काही बदलत नाही).
STRIKE_STEP = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}
_STRIKE_RELATIVE_FIELDS = ("itm_depth_points", "hedge_width_points", "naked_hedge_width_points")


def _scale_strike_relative_defaults(defaults, symbol):
    step = STRIKE_STEP.get(symbol, STRIKE_STEP["NIFTY"])
    baseline_step = STRIKE_STEP["NIFTY"]
    if step == baseline_step:
        return defaults
    scaled = dict(defaults)
    for field in _STRIKE_RELATIVE_FIELDS:
        if field in scaled:
            scaled[field] = max(round(scaled[field] / baseline_step) * step, step)
    return scaled

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" — कुठले accounts
# (कुठल्या broker वर) established रणनींतींनी वापरायचे, याची नोंदणी.
CREATE_BROKER_ACCOUNTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS broker_accounts (
    account_id TEXT PRIMARY KEY,
    broker_type TEXT NOT NULL,
    nickname TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    lot_multiplier REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW()
);
"""


def get_supabase_url():
    """पर्यावरण चल आधी तपासणे, नंतर config फाईल — दोन्हीपैकी काहीच नसेल तर None."""
    url = os.environ.get("SUPABASE_DB_URL")
    if url:
        return url
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            return cfg.get("supabase_db_url")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def is_cloud_db_configured():
    return psycopg2 is not None and get_supabase_url() is not None


def get_connection():
    """Cloud DB शी जोडणी करणे. Configured नसेल किंवा जोडणी अयशस्वी झाली तर None (कधीही raise होत नाही)."""
    if psycopg2 is None:
        return None
    url = get_supabase_url()
    if not url:
        return None
    try:
        return psycopg2.connect(url, connect_timeout=10)
    except Exception:
        _logger.exception("get_connection() मध्ये अनपेक्षित चूक (silently handled)")
        return None


def get_connection_with_error():
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — फक्त निदान/टेस्टिंगसाठी (test_supabase_connection.py).
    get_connection() प्रमाणेच, पण अयशस्वी झाल्यास खरा, तपशीलवार error संदेश सुद्धा परत देतं — जेणेकरून
    "जोडणी झाली नाही" इतकंच नाही, तर *नेमकं का* (उदा. password चुकीचा, project paused, DNS सापडला
    नाही) हे स्पष्टपणे कळेल. get_connection() चं मूळ वर्तन (production साठी शांतपणे None) अबाधित आहे.
    रिटर्न: (connection_किंवा_None, error_message_किंवा_None)
    """
    if psycopg2 is None:
        return None, "psycopg2 library स्थापित नाही (pip install psycopg2-binary)"
    url = get_supabase_url()
    if not url:
        return None, "SUPABASE_DB_URL सापडली नाही (environment variable रिकामी आहे)"
    try:
        return psycopg2.connect(url, connect_timeout=10), None
    except Exception as exc:
        return None, str(exc)


def init_cloud_table():
    """oi_diff_snapshots, upstox_tokens, market_zones, strike_oi_history, iv_history, nifty_1min_ohlc,
    signal_log, srv2_strategy_state, srv2_settings आणि broker_accounts tables (नसतील तर) तयार करणे."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.execute(CREATE_TOKEN_TABLE_SQL)
            cur.execute(CREATE_ZONES_TABLE_SQL)
            cur.execute(CREATE_STRIKE_OI_TABLE_SQL)
            cur.execute(CREATE_IV_HISTORY_TABLE_SQL)
            cur.execute(CREATE_NIFTY_1MIN_TABLE_SQL)
            cur.execute(CREATE_SIGNAL_LOG_TABLE_SQL)
            cur.execute(CREATE_SRV2_STATE_TABLE_SQL)
            cur.execute(CREATE_SRV2_SETTINGS_TABLE_SQL)
            cur.execute(CREATE_STRATEGY_SETTINGS_TABLE_SQL)
            cur.execute(CREATE_BROKER_ACCOUNTS_TABLE_SQL)
        conn.commit()
        return True
    finally:
        conn.close()


def add_broker_account(account_id, broker_type, nickname=None, lot_multiplier=1.0):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" रणनीतीसाठी नवीन account
    नोंदवणे. account_id (nickname, unique) आधीच असेल तर अद्ययावत (upsert) होतो.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO broker_accounts (account_id, broker_type, nickname, lot_multiplier)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (account_id) DO UPDATE SET
                       broker_type = EXCLUDED.broker_type, nickname = EXCLUDED.nickname,
                       lot_multiplier = EXCLUDED.lot_multiplier""",
                (account_id, broker_type, nickname, lot_multiplier),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("add_broker_account() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_all_broker_accounts(active_only=True):
    """established, नोंदवलेले सर्व accounts वाचणे (established रणनींतींनी loop करून प्रत्येकावर trade घेण्यासाठी)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            query = "SELECT account_id, broker_type, nickname, is_active, lot_multiplier FROM broker_accounts"
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY account_id"
            cur.execute(query)
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=["account_id", "broker_type", "nickname", "is_active", "lot_multiplier"])
    except Exception:
        _logger.exception("get_all_broker_accounts() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def set_broker_account_active(account_id, is_active):
    """established account सक्रिय/निष्क्रिय करणे (Dashboard वरच्या toggle साठी)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE broker_accounts SET is_active=%s WHERE account_id=%s", (is_active, account_id))
        conn.commit()
        return True
    except Exception:
        _logger.exception("set_broker_account_active() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def delete_broker_account(account_id):
    """established account पूर्णपणे काढून टाकणे."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM broker_accounts WHERE account_id=%s", (account_id,))
        conn.commit()
        return True
    except Exception:
        _logger.exception("delete_broker_account() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_srv2_state(symbol):
    """established srv2 रणनीतीचं राज्य वाचणे (One-Touch + Cooldown साठी) — नसेल तर सुरक्षित डीफॉल्ट."""
    conn = get_connection()
    if conn is None:
        return {"last_tested_level": None, "last_sl_hit_time": None}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT last_tested_level, last_sl_hit_time FROM srv2_strategy_state WHERE symbol=%s", (symbol,))
            row = cur.fetchone()
            if row is None:
                return {"last_tested_level": None, "last_sl_hit_time": None}
            return {"last_tested_level": row[0], "last_sl_hit_time": row[1]}
    except Exception:
        _logger.exception("get_srv2_state() मध्ये अनपेक्षित चूक (silently handled)")
        return {"last_tested_level": None, "last_sl_hit_time": None}
    finally:
        conn.close()


def save_srv2_state(symbol, last_tested_level=None, last_sl_hit_time=None):
    """srv2 रणनीतीचं राज्य साठवणे (upsert — symbol आधीच असेल तर अद्ययावत, नसेल तर नवीन)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO srv2_strategy_state (symbol, last_tested_level, last_sl_hit_time)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (symbol) DO UPDATE SET
                       last_tested_level = EXCLUDED.last_tested_level,
                       last_sl_hit_time = EXCLUDED.last_sl_hit_time""",
                (symbol, last_tested_level, last_sl_hit_time),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_srv2_state() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_srv2_settings(symbol):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — SRv2 चे lots/hedge_width_points Dashboard वरून
    बदलता येण्यासाठी. नोंद नसेल तर सुरक्षित डीफॉल्ट (lots=1, hedge_width_points=100 — जुनं hardcoded
    मूल्य)."""
    conn = get_connection()
    if conn is None:
        return {"lots": 1, "hedge_width_points": 100.0}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT lots, hedge_width_points FROM srv2_settings WHERE symbol=%s", (symbol,))
            row = cur.fetchone()
            if row is None:
                return {"lots": 1, "hedge_width_points": 100.0}
            return {"lots": int(row[0]), "hedge_width_points": float(row[1])}
    except Exception:
        _logger.exception("get_srv2_settings() मध्ये अनपेक्षित चूक (silently handled)")
        return {"lots": 1, "hedge_width_points": 100.0}
    finally:
        conn.close()


def save_srv2_settings(symbol, lots, hedge_width_points):
    """SRv2 चे lots/hedge_width_points साठवणे (upsert)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO srv2_settings (symbol, lots, hedge_width_points, updated_at)
                   VALUES (%s, %s, %s, NOW())
                   ON CONFLICT (symbol) DO UPDATE SET
                       lots = EXCLUDED.lots,
                       hedge_width_points = EXCLUDED.hedge_width_points,
                       updated_at = NOW()""",
                (symbol, lots, hedge_width_points),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_srv2_settings() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_strategy_settings(strategy_name, symbol):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo — नवीन नियम-संच) —
    strategy_name ("1m_instant" किंवा "15m_dynamic_sr") + symbol साठी settings. Supabase मध्ये
    साठवलेले (Dashboard वरून बदललेले) आणि डीफॉल्ट (STRATEGY_SETTINGS_DEFAULTS) यांचं मिश्रण —
    वापरकर्त्याने फक्त काही fields बदलले असतील, तर बाकीचे डीफॉल्ट कायम राहतात. Supabase न मिळाल्यास
    (किंवा नोंद नसल्यास) संपूर्णपणे डीफॉल्ट (itm_depth_points/hedge_width_points/naked_hedge_width_points
    symbol च्या स्वतःच्या strike step नुसार आधीच प्रमाणात मोठे/लहान केलेले — _scale_strike_relative_defaults() बघा)."""
    defaults = _scale_strike_relative_defaults(dict(STRATEGY_SETTINGS_DEFAULTS.get(strategy_name, {})), symbol)
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (symbol_enabled) — "उपलब्ध भांडवलानुसार वापरकर्ताच
    # symbol निवडणार" — त्यामुळे NIFTY डीफॉल्ट सक्रिय (आधीपासूनचं वर्तन कायम), पण BANKNIFTY/SENSEX
    # डीफॉल्ट निष्क्रिय (opt-in) — वापरकर्त्याने Dashboard वरून स्पष्टपणे सक्रिय केल्यासच त्या
    # symbol वर प्रत्यक्ष (PAPER) trade घेतला जातो.
    # "classic_sr_reversal" (नवीन, अजून backtest-टप्प्यातच असलेली strategy) साठी मात्र सर्व symbols
    # (NIFTY सकट) डीफॉल्ट निष्क्रियच — वापरकर्त्याने Bot Dynamic SR Algo वरून स्वतः, जाणीवपूर्वक
    # सक्रिय केल्याशिवाय कुठलाही (अगदी PAPER) trade घेतला जाऊ नये.
    defaults["symbol_enabled"] = (symbol == "NIFTY") if strategy_name != "classic_sr_reversal" else False
    conn = get_connection()
    if conn is None:
        return defaults
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT settings FROM strategy_settings WHERE strategy_name=%s AND symbol=%s",
                (strategy_name, symbol),
            )
            row = cur.fetchone()
            if row is None:
                return defaults
            stored = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            merged = dict(defaults)
            merged.update(stored)
            return merged
    except Exception:
        return defaults
    finally:
        conn.close()


# 🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — LIVE Kill Switch / Daily Loss Limit, गंभीर
# यादीतला चौथा मुद्दा) — तिन्ही bots साठी एकत्रित, संपूर्ण-खात्यासाठीचं (per-strategy/symbol नाही)
# सुरक्षा-सेटिंग. नवीन टेबल न बनवता, आधीच अस्तित्वात असलेल्या (आणि आधीच पूर्णपणे टेस्ट केलेल्या)
# strategy_settings infra चाच पुनर्वापर — strategy_name="__global_kill_switch__", symbol="ALL" ही
# एकच, स्थिर जोडी वापरून.
KILL_SWITCH_STRATEGY_KEY = "__global_kill_switch__"
KILL_SWITCH_SYMBOL_KEY = "ALL"
# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Kill switch मध्ये loss limit पाहिजे का discuss" -> "ekun
# capital chya respected te asayla pahije both loss and profit, certain profit book jhalyanantr,
# automatic trading stop karne awashyak") — आधी max_daily_loss एक स्थिर ₹ आकडा होता (₹10,000,
# capital वाढलं/कमी झालं तरी न बदलणारा). आता दोन्ही मर्यादा (तोटा आणि नफा दोन्ही) **एकूण capital
# च्या %** म्हणून साठवल्या जातात — प्रत्यक्ष ₹ रक्कम trading_engine.check_kill_switch() मध्ये,
# त्या क्षणीच्या upstox_api.get_total_capital() वरून काढली जाते. max_daily_profit_pct — नवीन —
# आजचा नफा इतका % गाठला की उरलेल्या दिवसासाठी नवीन LIVE trades आपोआप थांबतात (नफा दिला जाऊ नये
# म्हणून, तोट्याप्रमाणेच एक सुरक्षा-मर्यादा).
KILL_SWITCH_DEFAULTS = {
    "enabled": True,
    "max_daily_loss_pct": 2.0,
    "max_daily_profit_pct": 3.0,
    "max_trades_per_day": 15,
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("1 trade profit मध्ये exit जाला, दुसरा उघडा असेल,
    # तर काही नफा नेहमी लॉक व्हावा, जेणेकरून नफ्यातून तोटा होणार नाही") — max_daily_profit_pct (वरचं)
    # एक स्थिर, ठराविक लक्ष्य आहे — profit_lock हे त्याहून वेगळं, गतिशील (ratchet): दिवसभरात कधीही
    # गाठलेला सर्वोच्च नफा (peak, वरचं लक्ष्य गाठण्याआधीही) घेऊन, त्यातला profit_lock_pct% कायमचा
    # "मजला" (floor) म्हणून लॉक — सद्य एकूण नफा त्या मजल्याखाली घसरला की नवीन LIVE trades थांबतात
    # (आधीच उघडे trades मात्र त्यांच्याच SL/Target नुसार चालू राहतात — established pattern, इतर सर्व
    # kill switches प्रमाणेच). डीफॉल्ट बंद — जुनं वर्तन (फक्त max_daily_profit_pct) कायम राहतं.
    "profit_lock_enabled": False,
    "profit_lock_pct": 50.0,
}


def get_kill_switch_settings():
    """आजचा एकत्रित (सर्व symbols/strategies मिळून) LIVE Kill Switch — enabled/max_daily_loss_pct/
    max_daily_profit_pct/max_trades_per_day/profit_lock_enabled/profit_lock_pct. Supabase न
    मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट."""
    settings = get_strategy_settings(KILL_SWITCH_STRATEGY_KEY, KILL_SWITCH_SYMBOL_KEY)
    return {
        "enabled": bool(settings.get("enabled", KILL_SWITCH_DEFAULTS["enabled"])),
        "max_daily_loss_pct": settings.get("max_daily_loss_pct", KILL_SWITCH_DEFAULTS["max_daily_loss_pct"]),
        "max_daily_profit_pct": settings.get("max_daily_profit_pct", KILL_SWITCH_DEFAULTS["max_daily_profit_pct"]),
        "max_trades_per_day": settings.get("max_trades_per_day", KILL_SWITCH_DEFAULTS["max_trades_per_day"]),
        "profit_lock_enabled": bool(settings.get("profit_lock_enabled", KILL_SWITCH_DEFAULTS["profit_lock_enabled"])),
        "profit_lock_pct": settings.get("profit_lock_pct", KILL_SWITCH_DEFAULTS["profit_lock_pct"]),
    }


def save_kill_switch_settings(enabled, max_daily_loss_pct, max_daily_profit_pct, max_trades_per_day,
                               profit_lock_enabled=False, profit_lock_pct=50.0):
    return save_strategy_settings(KILL_SWITCH_STRATEGY_KEY, KILL_SWITCH_SYMBOL_KEY, {
        "enabled": bool(enabled), "max_daily_loss_pct": float(max_daily_loss_pct),
        "max_daily_profit_pct": float(max_daily_profit_pct), "max_trades_per_day": int(max_trades_per_day),
        "profit_lock_enabled": bool(profit_lock_enabled), "profit_lock_pct": float(profit_lock_pct),
    })


# 🎓 वापरकर्त्याने मागितलेली सुधारणा (MCX LIVE करण्याआधी — "MCX साठी वेगळा Kill Switch/capital cap") —
# वरचा ग्लोबल Kill Switch (सर्व symbols/strategies मिळून, एकच %) MCX लाही लागू होतोच, पण MCX ही
# brand-new (शून्य दिवसांचा LIVE इतिहास असलेली) रणनीती आहे — तिला स्वतःची, जास्त कडक, स्वतंत्र मर्यादा
# हवी (ग्लोबल मर्यादा अजून बरीच दूर असतानाही, फक्त MCX मध्येच मोठा तोटा होत असेल तर लवकर थांबावं).
# दोन्ही Kill Switches स्वतंत्रपणे तपासले जातात — कुठलाही एक ट्रिप झाला तरी नवीन MCX LIVE trade अडतो.
MCX_KILL_SWITCH_STRATEGY_KEY = "__mcx_kill_switch__"
MCX_KILL_SWITCH_SYMBOL_KEY = "ALL"
MCX_KILL_SWITCH_DEFAULTS = {
    "enabled": True,
    "max_daily_loss_pct": 1.0,
    "max_open_positions": 2,
    # 🎓 ग्लोबल KILL_SWITCH_DEFAULTS च्या profit_lock_enabled/profit_lock_pct सारखंच, पण फक्त MCX
    # (source='mcx_futures') पुरतं — बघा तिथली टिप्पणी. डीफॉल्ट बंद.
    "profit_lock_enabled": False,
    "profit_lock_pct": 50.0,
}


def get_mcx_kill_switch_settings():
    """MCX-विशिष्ट (5 commodities मिळून) Kill Switch — enabled/max_daily_loss_pct/max_open_positions/
    profit_lock_enabled/profit_lock_pct. Supabase न मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट
    (ग्लोबलपेक्षा जाणीवपूर्वक कडक — 1% loss cap, कमाल 2 positions एकाच वेळी, brand-new रणनीतीसाठी)."""
    settings = get_strategy_settings(MCX_KILL_SWITCH_STRATEGY_KEY, MCX_KILL_SWITCH_SYMBOL_KEY)
    return {
        "enabled": bool(settings.get("enabled", MCX_KILL_SWITCH_DEFAULTS["enabled"])),
        "max_daily_loss_pct": settings.get("max_daily_loss_pct", MCX_KILL_SWITCH_DEFAULTS["max_daily_loss_pct"]),
        "max_open_positions": settings.get("max_open_positions", MCX_KILL_SWITCH_DEFAULTS["max_open_positions"]),
        "profit_lock_enabled": bool(settings.get("profit_lock_enabled", MCX_KILL_SWITCH_DEFAULTS["profit_lock_enabled"])),
        "profit_lock_pct": settings.get("profit_lock_pct", MCX_KILL_SWITCH_DEFAULTS["profit_lock_pct"]),
    }


def save_mcx_kill_switch_settings(enabled, max_daily_loss_pct, max_open_positions,
                                   profit_lock_enabled=False, profit_lock_pct=50.0):
    return save_strategy_settings(MCX_KILL_SWITCH_STRATEGY_KEY, MCX_KILL_SWITCH_SYMBOL_KEY, {
        "enabled": bool(enabled), "max_daily_loss_pct": float(max_daily_loss_pct),
        "max_open_positions": int(max_open_positions),
        "profit_lock_enabled": bool(profit_lock_enabled), "profit_lock_pct": float(profit_lock_pct),
    })


# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("kill switch paper trading la pn lagu aahe ka... trading stop
# असा वेगळा button पाहिजे") — वरचा Kill Switch फक्त LIVE साठी, आपोआप (daily loss/trade-count
# मर्यादेवरून) ट्रिप होतो — PAPER trades कधीच अडवत नाही. हे पूर्णपणे वेगळं, नवीन फीचर — वापरकर्ता
# स्वतः, केव्हाही, एका क्लिकवर नवीन trades थांबवू शकतो — PAPER आणि LIVE दोन्हीसाठी लागू (हा
# risk-threshold-आधारित नाही, वापरकर्त्याचा थेट निर्णय आहे). आधीच उघडलेल्या positions वर (trade_monitor.py
# चं SL/Target/Trailing/EOD monitoring) याचा **काहीही** परिणाम होत नाही — फक्त नवीन trade उघडणं थांबतं,
# उर्वरित Dashboard/bots जसेच्या तसे चालू राहतात (trading_engine.open_multi_leg_trade() च्या अगदी
# सुरुवातीलाच एकाच ठिकाणी तपासलं जातं — सर्व 4 entry bots इथूनच trades उघडतात).
TRADING_PAUSE_STRATEGY_KEY = "__global_trading_pause__"
TRADING_PAUSE_SYMBOL_KEY = "ALL"


def get_trading_pause_settings():
    """सर्व symbols/strategies/PAPER+LIVE साठी एकत्रित — मॅन्युअल 'नवीन Trades थांबवा' स्थिती.
    Supabase न मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट — paused=False (चालू)."""
    settings = get_strategy_settings(TRADING_PAUSE_STRATEGY_KEY, TRADING_PAUSE_SYMBOL_KEY)
    return {
        "paused": bool(settings.get("paused", False)),
        "reason": settings.get("reason", ""),
        "paused_at": settings.get("paused_at"),
    }


def set_trading_pause(paused, reason=""):
    """paused=True -> नवीन trades थांबवले (कुठलाही bot नवीन position उघडणार नाही, PAPER+LIVE दोन्ही).
    paused=False -> पुन्हा सुरू. आधीच्या उघड्या positions वर कधीच परिणाम नाही."""
    payload = {"paused": bool(paused), "reason": str(reason or "")}
    payload["paused_at"] = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).isoformat() if paused else None
    return save_strategy_settings(TRADING_PAUSE_STRATEGY_KEY, TRADING_PAUSE_SYMBOL_KEY, payload)


# 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("India VIX ने पहिल्या 5 मिनिटांत ठराविक% क्रॉस केली तर
# त्या दिवशी NIFTY साठी bot ने automatic trading थांबवावी") — फक्त NIFTY साठी (वापरकर्त्याने स्पष्ट
# सांगितलं), फक्त LIVE (established Kill Switch पॅटर्नप्रमाणेच PAPER कधीच अडत नाही). % move आदल्या
# दिवसाच्या VIX close च्या तुलनेत मोजला जातो (वापरकर्त्याने निवडलेला आधार — "खरंच किती वाढला" हेच
# traders सहसा म्हणतात, आजच्या 9:15 open शी नाही), डीफॉल्ट threshold 5%. check_vix_spike_halt.py
# (सकाळी 9:20 IST cron, बाजार उघडून ~5 मिनिटांनी) एकदाच तपासून आजचा निकाल इथेच साठवतो —
# trading_engine.check_vix_spike_halt() हा फक्त तोच निकाल वाचतो, प्रत्येक trade attempt ला नवीन VIX
# API कॉल करत नाही.
VIX_SPIKE_HALT_STRATEGY_KEY = "__vix_spike_halt__"
VIX_SPIKE_HALT_SYMBOL_KEY = "NIFTY"
VIX_SPIKE_HALT_DEFAULTS = {"enabled": True, "threshold_pct": 5.0}


def get_vix_spike_halt_settings():
    """NIFTY-विशिष्ट VIX Spike Halt — enabled/threshold_pct (वापरकर्ता-निवडलेले, Dashboard वरून
    बदलता येण्याजोगे), अधिक आजच्या दिवसाची स्थिती (halted/trade_date/prev_close/current_vix/
    pct_change/checked_at — check_vix_spike_halt.py ने सकाळी साठवलेली, अजून तपासणी न झालेली असेल तर
    सर्व None/False). Supabase न मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट."""
    settings = get_strategy_settings(VIX_SPIKE_HALT_STRATEGY_KEY, VIX_SPIKE_HALT_SYMBOL_KEY)
    return {
        "enabled": bool(settings.get("enabled", VIX_SPIKE_HALT_DEFAULTS["enabled"])),
        "threshold_pct": settings.get("threshold_pct", VIX_SPIKE_HALT_DEFAULTS["threshold_pct"]),
        "halted": bool(settings.get("halted", False)),
        "trade_date": settings.get("trade_date"),
        "prev_close": settings.get("prev_close"),
        "current_vix": settings.get("current_vix"),
        "pct_change": settings.get("pct_change"),
        "checked_at": settings.get("checked_at"),
    }


def save_vix_spike_halt_settings(enabled, threshold_pct):
    """वापरकर्त्याने Dashboard वरून बदलता येणारे — enabled (चालू/बंद) आणि threshold_pct (किती% वाढ
    झाली तर थांबवायचं). आजच्या दिवसाच्या स्थितीला (save_vix_spike_halt_status()) हात लावत नाही —
    save_strategy_settings() आंशिक (partial) merge करतं, त्यामुळे दोन्ही स्वतंत्रपणे बदलता येतात."""
    return save_strategy_settings(VIX_SPIKE_HALT_STRATEGY_KEY, VIX_SPIKE_HALT_SYMBOL_KEY, {
        "enabled": bool(enabled), "threshold_pct": float(threshold_pct),
    })


def save_vix_spike_halt_status(trade_date, halted, prev_close, current_vix, pct_change):
    """check_vix_spike_halt.py (सकाळी 9:20 IST cron) रोज एकदाच कॉल करतं — आजचा निकाल साठवणे.
    enabled/threshold_pct (वापरकर्त्याचे सेटिंग्ज) ला हात लावत नाही (आंशिक merge)."""
    return save_strategy_settings(VIX_SPIKE_HALT_STRATEGY_KEY, VIX_SPIKE_HALT_SYMBOL_KEY, {
        "halted": bool(halted), "trade_date": trade_date,
        "prev_close": prev_close, "current_vix": current_vix, "pct_change": pct_change,
        "checked_at": (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).isoformat(),
    })


def get_all_strategy_trading_modes():
    """
    🎓 वापरकर्त्याने मागितलेली सुधारणा (Bot Dynamic SR Algo — नवीन वापरकर्त्यालाही सहज वापरता यावं
    म्हणून) — पानाच्या सर्वात वर, सध्या कुठली strategy+symbol combo LIVE आहे हे एका दृष्टीक्षेपात
    दाखवण्यासाठी. सर्व (strategy_name, symbol) combos एकाच query मध्ये — प्रत्येकासाठी वेगळा
    get_strategy_settings() कॉल (वेगळी DB round-trip) टाळण्यासाठी.

    ज्या combo साठी कधीच काही साठवलंच गेलेलं नाही, ते इथे अजिबात दिसणार नाहीत — असे सर्व आपोआप
    डीफॉल्ट (PAPER, शुद्ध Upstox) आहेत हे गृहीत धरता येतं.

    रिटर्न: {(strategy_name, symbol): {"trading_mode": "PAPER"/"LIVE"/"LIVE_PAPER", "broker_account_ids": [...]}, ...}
    Supabase न मिळाल्यास रिकामा dict (कुठलीही चूक न देता)."""
    conn = get_connection()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT strategy_name, symbol, settings FROM strategy_settings")
            rows = cur.fetchall()
        result = {}
        for strategy_name, symbol, raw_settings in rows:
            settings = raw_settings if isinstance(raw_settings, dict) else json.loads(raw_settings)
            result[(strategy_name, symbol)] = {
                "trading_mode": settings.get("trading_mode", "PAPER"),
                "broker_account_ids": settings.get("broker_account_ids") or [],
            }
        return result
    except Exception:
        _logger.exception("get_all_strategy_trading_modes() मध्ये अनपेक्षित चूक (silently handled)")
        return {}
    finally:
        conn.close()


def save_strategy_settings(strategy_name, symbol, settings_dict):
    """strategy_name + symbol साठी settings साठवणे (upsert, आंशिक अपडेट — फक्त दिलेले fields
    बदलतात, बाकीचे आधीचेच राहतात — PostgreSQL JSONB `||` merge-operator वापरून)."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO strategy_settings (strategy_name, symbol, settings, updated_at)
                   VALUES (%s, %s, %s, NOW())
                   ON CONFLICT (strategy_name, symbol) DO UPDATE SET
                       settings = strategy_settings.settings || EXCLUDED.settings,
                       updated_at = NOW()""",
                (strategy_name, symbol, json.dumps(settings_dict)),
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_next_level_in_direction(symbol, entry_level_price, direction_bullish, timeframe_suffixes=("15M", "30M", "60M")):
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Timeframe SRv2, Next-Level-Exit) —
    entry_level_price पासून favourable दिशेने, दिलेल्या timeframe_suffixes (डीफॉल्ट तिन्ही पूल
    केलेले — पण caller ने विशिष्ट एकच timeframe दिल्यास, उदा. ("15M",), "same-timeframe exit"
    हेही याच function ने साध्य होतं) मधला सर्वात जवळचा ACTIVE level शोधणे.
    direction_bullish=True -> entry_level_price पेक्षा वर, सर्वात जवळचा (favourable = वर जाणं).
    direction_bullish=False -> entry_level_price पेक्षा खाली, सर्वात जवळचा (favourable = खाली जाणं).
    रिटर्न: level_price (float) किंवा None (सापडला नाही तर)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        zone_types = []
        for tf in timeframe_suffixes:
            zone_types.append(f"DYNAMIC_SR_SUPPORT_{tf}")
            zone_types.append(f"DYNAMIC_SR_RESISTANCE_{tf}")
        placeholders = ",".join(["%s"] * len(zone_types))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT zone_low FROM market_zones WHERE symbol=%s AND zone_type IN ({placeholders}) AND status='ACTIVE'",
                (symbol, *zone_types),
            )
            rows = cur.fetchall()
        candidates = [float(r[0]) for r in rows]
        if direction_bullish:
            above = [c for c in candidates if c > entry_level_price]
            return min(above) if above else None
        below = [c for c in candidates if c < entry_level_price]
        return max(below) if below else None
    except Exception:
        _logger.exception("get_next_level_in_direction() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def zone_role_from_type(zone_type):
    """zone_type (उदा. 'DYNAMIC_SR_SUPPORT_1M', 'SUPPORT', 'DYNAMIC_SR_RESISTANCE_30M') मधून
    'SUPPORT'/'RESISTANCE'/None काढणे — get_zone_hits_today() ला role पुरवण्यासाठी."""
    if not zone_type:
        return None
    if "SUPPORT" in zone_type:
        return "SUPPORT"
    if "RESISTANCE" in zone_type:
        return "RESISTANCE"
    return None


def get_zone_hits_today(symbol, level_price, trade_date, role=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit Dynamic S/R) — established एकाच zone ला
    दिवसातून जास्तीत जास्त किती वेळा (आणि केव्हा शेवटचं) hit झालाय, हे established signal_log वरूनच
    काढणे (वेगळं table/column लागत नाही — प्रत्येक hit आधीच इथे साठवलेला असतो).
    रिटर्न: (hit_count: int, last_hit_time: datetime किंवा None, last_trade_time: datetime किंवा None)

    🎓 वापरकर्त्याशी चर्चा करून जोडलेला `role` पर्याय — आधी हा counter फक्त (symbol, price, day)
    वर होता, support/resistance वेगळे मोजायचा नाही — त्यामुळे एखादा level support म्हणून 2 वेळा hit
    झाला की, तोच किंमत ओलांडून नंतर resistance म्हणून काम करू लागला तरी पुढचा trade block व्हायचा
    (वापरकर्त्याने सापडवलेली, वास्तविक मर्यादा). आता support आणि resistance साठी स्वतंत्र कमाल-2
    counter (`role="SUPPORT"`/`"RESISTANCE"` दिलं की फक्त त्याच role च्या — `level_type` मध्ये तो
    शब्द असलेल्या — hits मोजल्या जातात) — एकाच किंमतीवर दिवसातून जास्तीत जास्त 2+2=4 trades शक्य.
    `role=None` (डीफॉल्ट) दिलं तर आधीचंच वर्तन (दोन्ही मिळून एकत्र मोजणी) — backward compatible.

    🎓 वापरकर्त्याशी चर्चा करून जोडलेला `last_trade_time` (वेगळा, `last_hit_time` पासून स्वतंत्र) —
    वापरकर्त्याने CSV export मधून दाखवून दिलं: 30-मिनिटांचा cooldown आधी **कुठल्याही touch** पासून
    (RSI/PCR gate ने नाकारलेला touch सुद्धा) मोजला जायचा — त्यामुळे सलग RSI-नाकारलेले touches
    (प्रत्यक्ष trade कधीच न होता) घड्याळ सतत रीसेट करत राहायचे. आता `last_trade_time` फक्त **खऱ्या
    trade attempt** (`_is_no_action_trade_status()` False असलेल्या, उदा. "OPENED") च्या वेळेवरून —
    cooldown साठी हेच वापरायचं (max-2-hits चा `hit_count`/`last_hit_time` मात्र आधीसारखाच touch-आधारित
    राहतो, तो बदललेला नाही).
    """
    conn = get_connection()
    if conn is None:
        return 0, None, None
    try:
        with conn.cursor() as cur:
            if role:
                cur.execute(
                    """SELECT signal_time, trade_status FROM signal_log
                       WHERE symbol=%s AND trade_date=%s AND level_price=%s AND hit_type != 'NO_HIT'
                       AND level_type LIKE %s
                       ORDER BY signal_time DESC""",
                    (symbol, trade_date, level_price, f"%{role}%"),
                )
            else:
                cur.execute(
                    """SELECT signal_time, trade_status FROM signal_log
                       WHERE symbol=%s AND trade_date=%s AND level_price=%s AND hit_type != 'NO_HIT'
                       ORDER BY signal_time DESC""",
                    (symbol, trade_date, level_price),
                )
            rows = cur.fetchall()
            if not rows:
                return 0, None, None
            last_trade_time = next((r[0] for r in rows if not _is_no_action_trade_status(r[1])), None)
            return len(rows), rows[0][0], last_trade_time
    except Exception:
        _logger.exception("get_zone_hits_today() मध्ये अनपेक्षित चूक (silently handled)")
        return 0, None, None
    finally:
        conn.close()


def _is_no_action_trade_status(trade_status):
    """कधीच खरा order attempt न झालेली स्थिती — None (अजून NO_HIT), STRATEGY_SELECTION_FAILED,
    किंवा कुठलंही SKIPPED_* (RSI/PCR/Cooldown/Max-Hits/इ. गेट). प्रत्यक्ष trade attempt चा निकाल
    (open_multi_leg_trade()/execute_trade_on_all_accounts() कडून, उदा. "OPENED" किंवा
    "A1:OPENED; A2:FAILED") यापैकी कधीच नसतो."""
    return trade_status is None or trade_status == "STRATEGY_SELECTION_FAILED" or str(trade_status).startswith("SKIPPED_")


def save_signal_log(entry):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — High-Frequency 1-मिनिट S/R रणनीतीचा प्रत्येक शोधलेला
    सिग्नल साठवणे (trade झाला किंवा न झाला तरीही) — Dashboard वरच्या संपूर्ण Signal Log साठी.
    entry: {"symbol":.., "trade_date":.., "signal_time":.., "level_type":.., "level_price":..,
            "hit_type":.., "direction":.., "ltp_at_signal":.., "trade_status":.., "reason":..}

    🎓 वापरकर्त्याने सापडवलेली bug (Dashboard वर Signal Log "2-3 वेळा repeat" दिसणे) — bot दर १
    मिनिटाला चालतो (candle timeframe 5M/15M/इ. असला तरी touch-तपासणी नेहमी अलीकडच्या candles वरून,
    दर cron cycle ला). किंमत एखाद्या level जवळ बराच वेळ राहिली (उदा. 30-मिनिटांचा cooldown, किंवा
    max-hits आधीच गाठलेला), तर प्रत्येक cron cycle ला तीच नेमकी स्थिती पुन्हा-पुन्हा नवीन row म्हणून
    साठवली जायची — Dashboard वर निरुपयोगी, जवळजवळ-सारख्याच नोंदींचा ढीग दिसायचा.

    🎓 वापरकर्त्याने code-review द्वारे सापडवलेली, पहिल्या फिक्सची (हीच सुधारणा, आधीची आवृत्ती) गंभीर
    त्रुटी — dedup-तुलना आधी `reason` column सकट करायची, पण bot script चं `reason` प्रत्येक cycle ला
    बदलणारं, जिवंत मूल्य embed करतं (उदा. "मागच्या hit ला फक्त {elapsed_minutes:.1f} मिनिटं झालीत" —
    दर मिनिटाला 5.0 -> 6.0 -> 7.0 ...; किंवा RSI/PCR gate चा live RSI/PCR आकडा) — त्यामुळे `reason`
    जवळजवळ प्रत्येक cycle ला वेगळाच असायचा, आणि dedup-तुलना कधीच जुळायचीच नाही — नेमकं cooldown/RSI/PCR
    या सर्वात सामान्य, सर्वाधिक repeat होणाऱ्या केसेससाठीच फिक्स काम करायचा नाही (फक्त खरोखर static
    reason असलेले MAX_2_HITS_REACHED/PREVIOUS_POSITION_STILL_OPEN/TOO_LATE_FOR_NEW_ENTRY काम करायचे).
    आता तुलना फक्त hit_type + trade_status वरून (reason वगळून) — trade_status हाच स्थिर, अर्थपूर्ण
    "का थांबवलं" चा enum आहे (उदा. "SKIPPED_COOLDOWN_30MIN"), reason ही फक्त त्याचं तपशीलवार, बदलतं
    वर्णन — तेच dedup साठी वापरणं चुकीचं होतं.

    फक्त "काहीच प्रत्यक्ष प्रयत्न झाला नाही" अशा नोंदींसाठीच (_is_no_action_trade_status), त्याच
    दिवशीची, त्याच level ची, सर्वात अलीकडची नोंद hit_type+trade_status मध्ये सारखीच असेल, तर पुन्हा
    साठवत नाही (प्रत्येक दिवशी किमान एक नोंद कायम राहते, त्यामुळे bot चालू आहे की नाही हे तपासताही
    येतं). प्रत्यक्ष trade attempt कधीच dedupe होत नाही — तो नेहमी नव्याने साठवला जातो.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            trade_status = entry.get("trade_status")
            if _is_no_action_trade_status(trade_status):
                cur.execute(
                    """SELECT hit_type, trade_status FROM signal_log
                       WHERE symbol=%s AND trade_date=%s AND level_type=%s AND level_price=%s
                       ORDER BY signal_time DESC LIMIT 1""",
                    (entry["symbol"], entry["trade_date"], entry["level_type"], entry["level_price"]),
                )
                last = cur.fetchone()
                if last is not None and last[0] == entry["hit_type"] and last[1] == trade_status:
                    return True  # आधीच्याच स्थितीची नोंद -- पुन्हा साठवली नाही, पण हे अपयश नाही
            cur.execute(
                """INSERT INTO signal_log (symbol, trade_date, signal_time, level_type, level_price,
                                            hit_type, direction, ltp_at_signal, trade_status, reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (entry["symbol"], entry["trade_date"], entry["signal_time"], entry["level_type"],
                 entry["level_price"], entry["hit_type"], entry["direction"], entry.get("ltp_at_signal"),
                 trade_status, entry.get("reason")),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_signal_log() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def _as_trade_date_str(value):
    """🎓 वापरकर्त्याने सापडवलेली गंभीर bug (Signal Log कधीच काहीच दाखवायचं नाही, Dashboard restart
    केल्यावरही) — signal_log.trade_date column **TEXT** आहे (bot scripts नेहमी plain string
    "YYYY-MM-DD" साठवतात — dynamic_sr_instant_trader.py/srv2_momentum_reversal_strategy.py चा
    trade_date = now.strftime("%Y-%m-%d")). पण Dashboard (page_dashboard.py) Signal Log tab
    get_ist_today() (datetime.date object) किंवा st.date_input() (तेही date object) थेट पास करायचं.
    psycopg2 datetime.date ला SQL मध्ये आपोआप ::date cast सकट पाठवतो — त्यामुळे झालेली
    "trade_date BETWEEN date AND date" (TEXT विरुद्ध DATE) तुलना PostgreSQL मध्येच
    "operator does not exist: text >= date" error द्यायचं — जी except Exception: नेच शांतपणे
    गिळली जायची (return None), आणि Dashboard ला "कुठलाही signal सापडला नाही" असं (चुकीचं) दिसायचं —
    प्रत्यक्षात bot scripts व्यवस्थित लिहीत होते, फक्त हा वाचनाचा query कधीच यशस्वी व्हायचाच नाही.
    आता कुठलाही caller date object किंवा string दोन्ही सुरक्षितपणे पाठवू शकतो."""
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else value


def get_signal_log(symbol, trade_date):
    """त्या दिवसाचा संपूर्ण Signal Log वाचणे (अलीकडचा वेळ सर्वात वर)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT signal_time, level_type, level_price, hit_type, direction, ltp_at_signal,
                          trade_status, reason
                   FROM signal_log WHERE symbol=%s AND trade_date=%s ORDER BY signal_time DESC""",
                (symbol, _as_trade_date_str(trade_date)),
            )
            rows = cur.fetchall()
            cols = ["signal_time", "level_type", "level_price", "hit_type", "direction", "ltp_at_signal", "trade_status", "reason"]
            return pd.DataFrame(rows, columns=cols)
    except Exception:
        _logger.exception("get_signal_log() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def get_signal_log_range(symbol, start_date, end_date):
    """दिलेल्या तारीख-रेंजमधला (दोन्ही तारखा सहित) संपूर्ण Signal Log वाचणे — Market Zones टॅबवरच्या
    तारीख-रेंज फिल्टरसाठी (get_signal_log() फक्त एका दिवसापुरता मर्यादित आहे)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT signal_time, level_type, level_price, hit_type, direction, ltp_at_signal,
                          trade_status, reason
                   FROM signal_log WHERE symbol=%s AND trade_date BETWEEN %s AND %s ORDER BY signal_time DESC""",
                (symbol, _as_trade_date_str(start_date), _as_trade_date_str(end_date)),
            )
            rows = cur.fetchall()
            cols = ["signal_time", "level_type", "level_price", "hit_type", "direction", "ltp_at_signal", "trade_status", "reason"]
            return pd.DataFrame(rows, columns=cols)
    except Exception:
        _logger.exception("get_signal_log_range() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def save_nifty_1min_batch(rows):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — मोठ्या प्रमाणात (लाखो) 1-मिनिट candles efficiently
    साठवण्यासाठी — psycopg2.extras.execute_values() वापरून एकाच वेळी batch-insert (एक-एक row करत
    नाही, जे ८,५०,०००+ रांगांसाठी अत्यंत संथ ठरलं असतं). ON CONFLICT DO NOTHING -- आधीच असलेल्या
    timestamps पुन्हा दिले तरी सुरक्षितपणे वगळले जातात (idempotent -- पुन्हा चालवलं तरी डुप्लिकेट नाही).
    rows: [{"timestamp":.., "open":.., "high":.., "low":.., "close":.., "volume":..}, ...]
    """
    if not rows:
        return True
    conn = get_connection()
    if conn is None:
        return False
    try:
        import psycopg2.extras
        with conn.cursor() as cur:
            values = [(r["timestamp"], r["open"], r["high"], r["low"], r["close"], r.get("volume", 0)) for r in rows]
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO nifty_1min_ohlc (timestamp, open, high, low, close, volume) VALUES %s "
                "ON CONFLICT (timestamp) DO NOTHING",
                values,
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_nifty_1min_batch() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_nifty_1min_range(from_date=None, to_date=None):
    """साठवलेला NIFTY 1-मिनिट डेटा, ऐच्छिक तारीख-रेंज फिल्टरसह वाचणे (established load_nifty_1min()
    च्याच interface शी जुळणारं — columns: timestamp, open, high, low, close, volume)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            query = "SELECT timestamp, open, high, low, close, volume FROM nifty_1min_ohlc WHERE 1=1"
            params = []
            if from_date is not None:
                query += " AND timestamp >= %s"
                params.append(from_date)
            if to_date is not None:
                query += " AND timestamp <= %s"
                params.append(to_date)
            query += " ORDER BY timestamp ASC"
            cur.execute(query, params)
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    except Exception:
        _logger.exception("get_nifty_1min_range() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def get_nifty_1min_latest_timestamp():
    """साठवलेल्या डेटातली सर्वात अलीकडची timestamp (gap-fill/daily-update स्क्रिप्टसाठी -- कुठून पुढे भरायचं ते ठरवण्यासाठी)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(timestamp) FROM nifty_1min_ohlc")
            result = cur.fetchone()
            return result[0] if result else None
    except Exception:
        _logger.exception("get_nifty_1min_latest_timestamp() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def save_strike_oi_snapshot(symbol, trade_date, snapshot_time, strikes_data):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — प्रत्येक strike चा CE/PE OI, त्याच snapshot_time
    साठी, एकत्रित साठवणे. strikes_data: [{"strike":x, "ce_oi":n, "pe_oi":n}, ...] (oi_snapshot_collector
    कडे आधीच उपलब्ध, aggregate करण्यासाठी वापरलेलाच डेटा -- नवीन API कॉल्स लागत नाहीत).
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            for d in strikes_data:
                for option_type, oi_val in [("CE", d["ce_oi"]), ("PE", d["pe_oi"])]:
                    cur.execute(
                        """INSERT INTO strike_oi_history (symbol, strike, option_type, trade_date, snapshot_time, oi)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (symbol, strike, option_type, trade_date, snapshot_time)
                           DO UPDATE SET oi = EXCLUDED.oi""",
                        (symbol, d["strike"], option_type, trade_date, snapshot_time, oi_val),
                    )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_strike_oi_snapshot() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_strike_oi_history(symbol, trade_date, strikes=None):
    """दिलेल्या दिवसाचा, प्रत्येक strike चा (हवं तर विशिष्ट strikes फिल्टर करून) OI इतिहास वाचणे."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if strikes:
                placeholders = ",".join(["%s"] * len(strikes))
                cur.execute(
                    f"""SELECT strike, option_type, snapshot_time, oi FROM strike_oi_history
                        WHERE symbol=%s AND trade_date=%s AND strike IN ({placeholders})
                        ORDER BY snapshot_time ASC""",
                    (symbol, trade_date, *strikes),
                )
            else:
                cur.execute(
                    """SELECT strike, option_type, snapshot_time, oi FROM strike_oi_history
                       WHERE symbol=%s AND trade_date=%s ORDER BY snapshot_time ASC""",
                    (symbol, trade_date),
                )
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=["strike", "option_type", "snapshot_time", "oi"])
    except Exception:
        _logger.exception("get_strike_oi_history() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def save_iv_snapshot(symbol, trade_date, snapshot_time, rows):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Record iv of option premium daily for analysis") —
    दिलेल्या strikes/option_types चा IV (व सोबतच LTP, expiry, underlying_price — त्याच fetch_option_
    greeks() कॉल मधून आधीच उपलब्ध) एकत्रित साठवणे. save_strike_oi_snapshot() सारखाच upsert पॅटर्न —
    त्याच दिवशी/वेळेला पुन्हा चालवलं तरी duplicate rows नाहीत, फक्त अद्ययावत.
    rows: [{"strike":.., "option_type":"CE"/"PE", "expiry":.., "iv":.., "ltp":.., "underlying_price":..}, ...]
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    """INSERT INTO iv_history (symbol, strike, option_type, trade_date, snapshot_time,
                                                expiry, iv, ltp, underlying_price)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (symbol, strike, option_type, trade_date, snapshot_time)
                       DO UPDATE SET expiry = EXCLUDED.expiry, iv = EXCLUDED.iv, ltp = EXCLUDED.ltp,
                                     underlying_price = EXCLUDED.underlying_price""",
                    (symbol, r["strike"], r["option_type"], trade_date, snapshot_time,
                     r.get("expiry"), r.get("iv"), r.get("ltp"), r.get("underlying_price")),
                )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_iv_snapshot() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_iv_history(symbol, from_date=None, to_date=None, strikes=None):
    """IV इतिहास वाचणे — "काल IV काय होता, आज काय आहे" अशी तुलना यावरूनच करता येते. from_date/to_date
    दिले तर त्या range मधलाच (both inclusive) इतिहास, दोन्ही न दिल्यास संपूर्ण साठवलेला इतिहास.
    strikes दिलं तर तेवढेच strikes."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            clauses = ["symbol=%s"]
            params = [symbol]
            if from_date:
                clauses.append("trade_date >= %s")
                params.append(from_date)
            if to_date:
                clauses.append("trade_date <= %s")
                params.append(to_date)
            if strikes:
                placeholders = ",".join(["%s"] * len(strikes))
                clauses.append(f"strike IN ({placeholders})")
                params.extend(strikes)
            where_sql = " AND ".join(clauses)
            cur.execute(
                f"""SELECT trade_date, snapshot_time, expiry, strike, option_type, iv, ltp, underlying_price
                    FROM iv_history WHERE {where_sql} ORDER BY trade_date ASC, snapshot_time ASC""",
                params,
            )
            rows = cur.fetchall()
            cols = ["trade_date", "snapshot_time", "expiry", "strike", "option_type", "iv", "ltp", "underlying_price"]
            return pd.DataFrame(rows, columns=cols)
    except Exception:
        _logger.exception("get_iv_history() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def _atm_avg_iv_from_rows(rows_df):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Average IV Breakout Gate) — दिलेल्या (एकाच
    दिवसाच्या/snapshot च्या) iv_history rows मधून, त्या वेळच्या underlying_price च्या सर्वात
    जवळचा strike शोधून त्याची CE+PE IV सरासरी काढणे — एकाच प्रातिनिधिक "ATM IV" संख्येसाठी."""
    if rows_df is None or rows_df.empty:
        return None
    underlying = rows_df["underlying_price"].iloc[-1]
    if not underlying:
        return None
    rows_df = rows_df.copy()
    rows_df["_dist"] = (rows_df["strike"] - underlying).abs()
    nearest_strike = rows_df.loc[rows_df["_dist"].idxmin(), "strike"]
    ivs = rows_df.loc[rows_df["strike"] == nearest_strike, "iv"].dropna()
    if ivs.empty:
        return None
    return float(ivs.mean())


# 🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Average IV Breakout Gate — "2 category Trending
# diwsacha iv ani sideways diwsacha iv ha data आपल्याकडे asawa. Fakt N diwsacha average फायद्याचा
# नाही") — plain N-दिवसांची सरासरी trending आणि sideways दोन्ही प्रकारचे दिवस मिसळते, त्यामुळे
# baseline सौम्य/दिशाभूल करणारा ठरतो. इंडिकेटरशिवाय ("indicator मध्ये interest नाही") — फक्त plain
# daily candle (Open/High/Low/Close) वरून "Marubozu (किंवा जवळपास तसा, छोट्या wicks सह) = trending"
# हे body_ratio (body / day's range) ने मोजलं जातं — 1.0 च्या जवळ म्हणजे wicks जवळपास नाहीतच (शुद्ध
# दिशेने गेलेला दिवस), 0 च्या जवळ म्हणजे मोठे wicks (इकडे-तिकडे होऊन जवळपास तिथेच बंद — sideways).
# वापरकर्त्याने चर्चा करून ठरवलेला threshold 0.8.
MARUBOZU_TRENDING_THRESHOLD = 0.8


def compute_body_ratio(open_, high, low, close):
    """|Close-Open| / (High-Low) — 0 (मोठे wicks, sideways) ते 1 (Marubozu, trending). दिवसाचा
    range शून्य असेल (हालचालच नाही) तर सुरक्षितपणे 0.0 (sideways च समजायचं)."""
    day_range = high - low
    if day_range <= 0:
        return 0.0
    return abs(close - open_) / day_range


def is_sideways_day(open_, high, low, close, marubozu_threshold=MARUBOZU_TRENDING_THRESHOLD):
    """body_ratio marubozu_threshold पेक्षा कमी असेल तरच sideways (trending नाही)."""
    return compute_body_ratio(open_, high, low, close) < marubozu_threshold


def get_nifty_daily_ohlc(from_date=None, to_date=None):
    """established `nifty_1min_ohlc` (रोज अद्ययावत होणारा, गेल्या ५+ वर्षांचा NIFTY 1-मिनिट डेटा)
    मधून प्रत्येक ट्रेडिंग दिवसाचा daily Open/High/Low/Close (resample — दिवसाचा पहिला open, कमाल
    high, किमान low, शेवटचा close) — Marubozu-आधारित trending/sideways classification साठी. नवीन
    कुठलाही API कॉल/cron लागत नाही. फक्त NIFTY साठी (established टेबलच फक्त NIFTY साठी आहे).
    रिटर्न: DataFrame [trade_date, open, high, low, close] किंवा (डेटा नसल्यास) None."""
    df = get_nifty_1min_range(from_date=from_date, to_date=to_date)
    if df is None or df.empty:
        return None
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d")
    daily = df.groupby("trade_date").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
    ).reset_index()
    return daily


def get_iv_change_from_average(symbol, lookback_days=10, max_age_minutes=20, marubozu_threshold=MARUBOZU_TRENDING_THRESHOLD):
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Average IV Breakout Gate — "5 minute instant
    dynamic sr strategy work better in sideways, low iv or average iv market, but in trending when
    Breakout happen it books loss") — आजचा ताजा ATM IV, मागच्या **फक्त Marubozu-आधारित SIDEWAYS-
    classified** ट्रेडिंग दिवसांच्या (जास्तीत जास्त lookback_days, जितके उपलब्ध असतील तितकेच, सर्वात
    अलीकडच्यापासून मागे शोधत) EOD ATM IV च्या सरासरीशी किती% वाढला हे मोजणे — trending दिवसांचा
    नेहमीच जास्त असणारा IV बेसलाइनला विचलित करू नये म्हणून (plain सर्व-दिवसांची सरासरी दिशाभूल करते).
    आजचा snapshot max_age_minutes पेक्षा जुना असेल (collector थांबलेला असू शकतो), किंवा किमान १
    sideways दिवसही सापडला नाही (पुरेसा इतिहास अजून जमलेला नाही), तर None — established PCR Gate
    च्या fail-safe पॅटर्नप्रमाणेच, caller ने तेव्हा trade थांबवावा.
    ⚠️ फक्त NIFTY साठी (day-classification `nifty_1min_ohlc` वरून, जो फक्त NIFTY साठीच आहे) — इतर
    symbols साठी नेहमीच None (sideways दिवसच classify करता येत नसल्याने, जुनं सरसकट-सरासरी वर्तन
    परत येत नाही — fail-safe).
    रिटर्न: {"today_iv":.., "baseline_avg_iv":.., "change_pct":.., "days_in_baseline":..} किंवा None."""
    df = get_iv_history(symbol)
    if df is None or df.empty:
        return None

    now_ist = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    today_str = now_ist.strftime("%Y-%m-%d")

    trade_dates = sorted(df["trade_date"].unique())
    if today_str not in trade_dates:
        return None

    today_rows = df[df["trade_date"] == today_str]
    latest_snapshot_time = today_rows["snapshot_time"].max()
    latest_today_rows = today_rows[today_rows["snapshot_time"] == latest_snapshot_time]
    today_atm_iv = _atm_avg_iv_from_rows(latest_today_rows)
    if today_atm_iv is None:
        return None

    try:
        snap_dt = datetime.datetime.strptime(f"{today_str} {latest_snapshot_time}", "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None
    age_minutes = (now_ist.replace(tzinfo=None) - snap_dt).total_seconds() / 60.0
    if age_minutes > max_age_minutes:
        return None

    daily_ohlc = get_nifty_daily_ohlc() if symbol == "NIFTY" else None
    if daily_ohlc is None or daily_ohlc.empty:
        return None
    sideways_dates = {
        row["trade_date"] for _, row in daily_ohlc.iterrows()
        if is_sideways_day(row["open"], row["high"], row["low"], row["close"], marubozu_threshold)
    }

    prior_dates_sideways = [d for d in trade_dates if d < today_str and d in sideways_dates]
    prior_dates = prior_dates_sideways[-lookback_days:]
    if not prior_dates:
        return None

    daily_ivs = []
    for d in prior_dates:
        day_rows = df[df["trade_date"] == d]
        last_time = day_rows["snapshot_time"].max()
        last_rows = day_rows[day_rows["snapshot_time"] == last_time]
        iv = _atm_avg_iv_from_rows(last_rows)
        if iv is not None:
            daily_ivs.append(iv)

    if not daily_ivs:
        return None

    baseline_avg_iv = sum(daily_ivs) / len(daily_ivs)
    if baseline_avg_iv <= 0:
        return None

    change_pct = (today_atm_iv - baseline_avg_iv) / baseline_avg_iv * 100
    return {
        "today_iv": today_atm_iv, "baseline_avg_iv": baseline_avg_iv,
        "change_pct": change_pct, "days_in_baseline": len(daily_ivs),
    }


def merge_dynamic_sr_zones(symbol, dyn_sr_result, timeframe_suffix, tolerance_pct=0.02, formed_date=None):
    """
    हलका (5-मिनिट/10-मिनिट) Dynamic S/R refresh — save_market_zones() (पूर्ण replace) च्या उलट, इथे
    फक्त DYNAMIC_SR_*_{timeframe_suffix} (उदा. "1M" किंवा "15M") प्रकारचे zones merge केले जातात:
      - नवीन गणना केलेला level जुन्या ACTIVE level च्या ±tolerance_pct% च्या आत असेल, तर जुनाच
        level_price कायम ठेवला जातो (Multi-Hit hit-count history टिकून राहावी म्हणून — ते
        signal_log वरून काढलं जातं, zone row मध्ये नाही, त्यामुळे status बदलल्याने हरवत नाही).
      - नवीन, न जुळणारा उमेदवार असेल, तो नव्याने ACTIVE म्हणून जोडला जातो.
      - जुना, नव्या गणनेत न सापडलेला (म्हणजे आताच्या ताज्या "सर्वोत्तम ५" यादीत नसलेला) level आता
        DELETE होत नाही, पण 'STALE' म्हणून चिन्हांकित होतो (इतिहासासाठी row टिकून राहतो, पण
        status='ACTIVE' फिल्टर करणाऱ्या सर्व bots/queries ना (उदा. dynamic_sr_instant_trader.py)
        तो आपोआप दिसेनासा होतो).

    🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा — आधी जुना level कायमचा ACTIVE राहायचा (दिवसभर
    यादी फक्त वाढतच जायची, कधीच prune व्हायची नाही — रात्रीच्या पूर्ण refresh_market_zones.py
    शिवाय) — त्यामुळे चार्टवरचं (नेहमी ताजं टॉप-5) आणि Signal Log मधलं (साचत गेलेलं, prune न
    झालेलं) असं दोन वेगळं चित्र दिसायचं. आता दर 5-मिनिटांच्या प्रत्येक cycle ला — म्हणजे बाजार
    उघडल्या-उघडल्याच्या पहिल्या cycle पासूनच — ACTIVE यादी नेहमी ताज्या गणनेइतकीच राहते.
    रिटर्न: True/False (यशस्वी झालं की नाही).
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        formed_date = formed_date or datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
        support_type = f"DYNAMIC_SR_SUPPORT_{timeframe_suffix}"
        resistance_type = f"DYNAMIC_SR_RESISTANCE_{timeframe_suffix}"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, zone_type, zone_low FROM market_zones WHERE symbol = %s "
                "AND zone_type IN (%s, %s) AND status = 'ACTIVE'",
                (symbol, support_type, resistance_type),
            )
            existing = cur.fetchall()  # [(id, zone_type, zone_low), ...]

            for zone_type, candidates in [
                (support_type, dyn_sr_result.get("support", [])),
                (resistance_type, dyn_sr_result.get("resistance", [])),
            ]:
                existing_of_type = [(row_id, zone_low) for (row_id, zt, zone_low) in existing if zt == zone_type]
                matched_existing_ids = set()

                for cand in candidates:
                    cand_level = float(cand["level"])
                    buffer = cand_level * tolerance_pct / 100
                    matched = next(
                        (row_id for (row_id, zone_low) in existing_of_type
                         if abs(float(zone_low) - cand_level) <= buffer and row_id not in matched_existing_ids),
                        None,
                    )
                    if matched is not None:
                        matched_existing_ids.add(matched)  # जुनाच level_price कायम -- काहीही न बदलता
                    else:
                        cur.execute(
                            """INSERT INTO market_zones (symbol, zone_type, zone_low, zone_high, strength, formed_date, status)
                               VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')""",
                            (symbol, zone_type, cand_level, cand_level, float(cand["touches"]), formed_date),
                        )

                stale_ids = [row_id for (row_id, _zone_low) in existing_of_type if row_id not in matched_existing_ids]
                if stale_ids:
                    placeholders = ",".join(["%s"] * len(stale_ids))
                    cur.execute(
                        f"UPDATE market_zones SET status = 'STALE' WHERE id IN ({placeholders})",
                        tuple(stale_ids),
                    )

        conn.commit()
        return True
    except Exception:
        _logger.exception("merge_dynamic_sr_zones() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def merge_dynamic_sr_1m_zones(symbol, dyn_sr_result, tolerance_pct=0.02, formed_date=None):
    """Backward-compatible wrapper — merge_dynamic_sr_zones() ला "1M" सह कॉल करते."""
    return merge_dynamic_sr_zones(symbol, dyn_sr_result, "1M", tolerance_pct, formed_date)


def save_market_zones(zones_df, symbol, scoped=False):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — दिलेल्या symbol चे जुने zones काढून, नवीन गणना केलेले
    zones साठवणे (replace-on-refresh — market_zones हे "सद्य स्थिती" दाखवतं, वाढत जाणारा इतिहास नाही).

    🎓 वापरकर्त्याशी चर्चा करून मागे-घेतलेली सुधारणा — DYNAMIC_SR_*_1M/*_5M ला या nightly DELETE
    मधून वगळून, ते कायमचे फक्त त्यांच्याच दर-५-मिनिटांच्या merge-cron कडे सोपवण्याचा आधीचा प्रयत्न
    चुकीचा ठरला — त्या merge-cron चं "जुने levels कधीच न काढणे" फक्त त्याच दिवसापुरतं योग्य आहे,
    कायमचं नाही: nightly वगळल्यामुळे आठवडाभर जुना, आता पूर्णपणे अप्रस्तुत 1-मिनिट pivot अजूनही ACTIVE
    राहून खरा trade घेऊ शकत होता (वापरकर्त्याने विचारून सापडवलेली, वेगळी bug). योग्य उपाय: nightly
    refresh आताही **सर्वच** zone_types (1M/5M सकट) रोज साफ करून, ताज्या (अलीकडच्या काही दिवसांच्या)
    डेटावरून पुन्हा गणना करतो — बघा market_zones.compute_all_zones() मधली df_1m_recent/df_5m_recent
    टिप्पणी.

    🎓 वापरकर्त्याशी चर्चा करून जोडलेला नवीन पर्याय (`scoped`) — NIFTY/BANKNIFTY/SENSEX चे 15M/30M/60M
    zones बाजार चालू असताना (intraday) वारंवार ताजे करायचे होते, पण वरचा डीफॉल्ट (symbol-व्यापी, सगळेच
    zone_types काढणारा) DELETE बाजार चालू असताना वापरणं **धोकादायक** ठरलं असतं — `DYNAMIC_SR_*_1M/*_5M`
    zones त्याच क्षणी `dynamic_sr_instant_trader.py` दर मिनिटाला वेगळ्या (जुने न काढता फक्त STALE
    करणाऱ्या) पद्धतीने live जपत असतो, त्यावरच प्रत्यक्ष trade चालू असू शकतो — ते intraday इथून उडवणं
    live trading मध्ये अचानक व्यत्यय आणू शकलं असतं. `scoped=True` दिलं की DELETE फक्त `zones_df` मध्ये
    प्रत्यक्ष दिलेल्या zone_types पुरतंच मर्यादित राहतं (`zones_df["zone_type"].unique()`) — caller ने
    फक्त 15M/30M/60M रांगा दिल्या, तर फक्त तेवढेच zone_types बदलतात, इतर कशालाही (1M/5M, SUPPORT/
    RESISTANCE, Order Blocks इ.) हात लागत नाही. डीफॉल्ट `False` — established रोजच्या पूर्ण
    (refresh_market_zones.py/refresh_market_zones_mcx.py) refresh चं वर्तन पूर्णपणे अबाधित.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            if scoped:
                zone_types = zones_df["zone_type"].dropna().unique().tolist()
                if zone_types:
                    cur.execute(
                        "DELETE FROM market_zones WHERE symbol = %s AND zone_type = ANY(%s)",
                        (symbol, zone_types),
                    )
            else:
                cur.execute("DELETE FROM market_zones WHERE symbol = %s", (symbol,))
            for _, row in zones_df.iterrows():
                cur.execute(
                    """INSERT INTO market_zones (symbol, zone_type, zone_low, zone_high, strength, formed_date, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (symbol, row["zone_type"], float(row["zone_low"]), float(row["zone_high"]),
                     float(row["strength"]) if pd.notna(row.get("strength")) else None,
                     row["formed_date"], row["status"]),
                )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_market_zones() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_market_zones(symbol, status=None):
    """साठवलेले zones वाचणे — status दिलं (उदा. 'ACTIVE') तर फक्त तेवढेच, नाहीतर सर्व."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT symbol, zone_type, zone_low, zone_high, strength, formed_date, status FROM market_zones "
                    "WHERE symbol = %s AND status = %s ORDER BY zone_type",
                    (symbol, status),
                )
            else:
                cur.execute(
                    "SELECT symbol, zone_type, zone_low, zone_high, strength, formed_date, status FROM market_zones "
                    "WHERE symbol = %s ORDER BY zone_type",
                    (symbol,),
                )
            rows = cur.fetchall()
            cols = ["symbol", "zone_type", "zone_low", "zone_high", "strength", "formed_date", "status"]
            return pd.DataFrame(rows, columns=cols)
    except Exception:
        _logger.exception("get_market_zones() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def save_upstox_token(access_token, account_id=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — नवीन Upstox token (webhook कडून मिळालेला)
    Supabase मध्ये साठवणे. जुने token (इतिहास ठेवण्यासाठी) राहतात, फक्त नवीन ओळ (row) जोडली जाते —
    वाचताना नेहमी सर्वात नवीनच (get_latest_upstox_token) वापरला जातो.
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "Multi-Broker Multi-Account" — account_id दिला
    (established broker_accounts मधलं nickname) तर तो त्याच account साठी वेगळा साठवला जातो;
    न दिल्यास established, एकमेव (single) खात्यासाठीचं जुनं वर्तन तसंच (backward-compatible) राहतं.
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Plaintext Broker Credentials) -- TOKEN_ENCRYPTION_KEY
            # सेट असेल तर encrypt करूनच साठवला जातो (नसेल तर आधीसारखाच plaintext, backward-compatible).
            cur.execute("INSERT INTO upstox_tokens (access_token, account_id) VALUES (%s, %s)", (encrypt_token(access_token), account_id))
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_upstox_token() मध्ये अनपेक्षित चूक (silently handled)")
        return False
    finally:
        conn.close()


def get_latest_upstox_token(account_id=None):
    """सर्वात अलीकडे साठवलेला Upstox token परत करणे, किंवा काहीच नसेल/जोडणी अयशस्वी झाली तर None.
    🎓 account_id दिला तर फक्त त्याच account चा token; न दिल्यास established, जुना (account_id
    नसलेला/single-account) token वाचला जातो — backward-compatible."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if account_id is not None:
                cur.execute(
                    "SELECT access_token FROM upstox_tokens WHERE account_id=%s ORDER BY received_at DESC LIMIT 1",
                    (account_id,),
                )
            else:
                cur.execute(
                    "SELECT access_token FROM upstox_tokens WHERE account_id IS NULL ORDER BY received_at DESC LIMIT 1"
                )
            row = cur.fetchone()
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Plaintext Broker Credentials) -- encrypt_token()
            # प्रमाणेच, पारदर्शक decrypt (उपसर्ग नसलेले जुने plaintext rows जसेच्या तसे परत येतात).
            return decrypt_token(row[0]) if row else None
    except Exception:
        _logger.exception("get_latest_upstox_token() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def get_token_age_hours(account_id=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — रोजचा manual OAuth login (get_upstox_token_manual.py)
    चुकल्यास सर्व cron jobs शांतपणे token न मिळाल्याने थांबतात, कुणालाच कळत नाही — यासाठी सर्वात
    अलीकडचा token किती तासांपूर्वी साठवला गेला, ते तपासण्यासाठी (check_token_freshness.py वापरतं).
    रिटर्न: तासांमधलं वय (float), किंवा token च नसेल/जोडणी अयशस्वी झाली तर None.
    """
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            if account_id is not None:
                cur.execute(
                    "SELECT EXTRACT(EPOCH FROM (NOW() - received_at)) / 3600.0 FROM upstox_tokens "
                    "WHERE account_id=%s ORDER BY received_at DESC LIMIT 1",
                    (account_id,),
                )
            else:
                cur.execute(
                    "SELECT EXTRACT(EPOCH FROM (NOW() - received_at)) / 3600.0 FROM upstox_tokens "
                    "WHERE account_id IS NULL ORDER BY received_at DESC LIMIT 1"
                )
            row = cur.fetchone()
            return float(row[0]) if row else None
    except Exception:
        _logger.exception("get_token_age_hours() मध्ये अनपेक्षित चूक (silently handled)")
        return None
    finally:
        conn.close()


def get_effective_upstox_token(cli_token, account_id=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Upstox Token Webhook (VPS वर, एका
    मोबाईल-टॅपवर रोज नवीन token) पूर्ण automation साठी वापरण्यायोग्य करणे. established --token
    (GitHub Secret) दिलेला असेल तर तोच वापरणे (backward-compatible, जुनी पद्धत अजूनही चालते) —
    नाहीतर established get_latest_upstox_token() (Supabase, Webhook ने साठवलेला) आपोआप वापरणे.
    account_id दिला तर established multi-account token वाचला जातो (backward-compatible, डीफॉल्ट None).
    """
    if cli_token:
        return cli_token
    return get_latest_upstox_token(account_id)


def save_oi_snapshot_cloud(symbol, trade_date, snapshot_time, total_call_oi, total_put_oi,
                             diff, delta_diff, signal, underlying_price, total_call_premium, total_put_premium):
    """
    एक OI snapshot cloud DB मध्ये साठवणे — त्याच (symbol, trade_date, snapshot_time) साठी आधीच
    नोंद असेल तर काहीही न करता (ON CONFLICT DO NOTHING) शांतपणे वगळणे — डुप्लिकेट टाळण्यासाठी
    (SQLite च्या INSERT OR IGNORE सारखंच).
    रिटर्न: True (यशस्वी) / False (जोडणी उपलब्ध नाही किंवा अयशस्वी).
    """
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO oi_diff_snapshots
                   (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff,
                    signal, underlying_price, total_call_premium, total_put_premium)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (symbol, trade_date, snapshot_time) DO NOTHING""",
                (symbol, trade_date, snapshot_time, total_call_oi, total_put_oi, diff, delta_diff,
                 signal, underlying_price, total_call_premium, total_put_premium),
            )
        conn.commit()
        return True
    except Exception:
        _logger.exception("save_oi_snapshot_cloud() मध्ये अनपेक्षित चूक (silently handled)")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_recent_oi_snapshots_cloud(symbol, trade_date, before_time=None, limit=5):
    """Signal Engine (स्थिरता तपासणी) साठी — दिलेल्या वेळेपूर्वीचे शेवटचे N snapshots (जुनं->नवीन क्रमाने)."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if before_time:
                cur.execute(
                    """SELECT diff, total_put_oi, total_call_oi, signal FROM oi_diff_snapshots
                       WHERE symbol=%s AND trade_date=%s AND snapshot_time < %s
                       ORDER BY snapshot_time DESC LIMIT %s""",
                    (symbol, trade_date, before_time, limit),
                )
            else:
                cur.execute(
                    """SELECT diff, total_put_oi, total_call_oi, signal FROM oi_diff_snapshots
                       WHERE symbol=%s AND trade_date=%s
                       ORDER BY snapshot_time DESC LIMIT %s""",
                    (symbol, trade_date, limit),
                )
            rows = cur.fetchall()
        return list(reversed(rows))  # जुनं->नवीन
    finally:
        conn.close()


def get_latest_oi_snapshot_cloud(symbol, trade_date):
    """वापरकर्त्याने VPS वरून प्रत्यक्ष तपासून सापडवलेली bug (PCR Gate) — त्या दिवसाचा सर्वात
    अलीकडचा snapshot, फक्त एकच रांग (oi_analysis.get_latest_pcr() साठी). आधी हे function
    अस्तित्वातच नव्हतं — get_latest_pcr() नेहमी फक्त local SQLite कडेच बघायचं, Cloud DB configured
    असतानाही. पण oi_snapshot_collector.py Cloud DB configured असेल तर तिथेच लिहितो (local SQLite
    मध्ये काहीच लिहीत नाही) — त्यामुळे PCR Gate ला कायम "डेटा उपलब्ध नाही" दिसायचं आणि प्रत्येक
    trade अडवला जायचा, जरी collector स्वतः दर ५ मिनिटांनी व्यवस्थित (Supabase मध्ये) डेटा साठवत असला तरी."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT snapshot_time, total_call_oi, total_put_oi FROM oi_diff_snapshots
                   WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time DESC LIMIT 1""",
                (symbol, trade_date),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_latest_oi_signal_cloud(symbol, trade_date):
    """त्या दिवसाचा सर्वात अलीकडचा 'signal' — oi_analysis.get_latest_oi_signal() साठी (A1 Engine
    च्या OI Confirmation Gate मध्ये वापरलं जातं — get_latest_pcr() सारखीच, Cloud DB configured
    असताना local SQLite कडे बघण्याची चूक इथेही होती)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT signal FROM oi_diff_snapshots WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time DESC LIMIT 1""",
                (symbol, trade_date),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def get_previous_day_oi_cloud(symbol, today_str):
    """आजच्या आधीच्या शेवटच्या ट्रेडिंग दिवसाचा शेवटचा एकूण (Call+Put) OI — oi_analysis.
    get_previous_day_total_oi() साठी (Swing मोडचं OI-Price Matrix — तीच local-SQLite-only चूक)."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT total_call_oi, total_put_oi FROM oi_diff_snapshots
                   WHERE symbol=%s AND trade_date < %s ORDER BY trade_date DESC, snapshot_time DESC LIMIT 1""",
                (symbol, today_str),
            )
            row = cur.fetchone()
            return (row[0] + row[1]) if row else None
    finally:
        conn.close()


def get_oi_price_history_cloud(symbol, trade_date):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — PCR + NIFTY किंमत, वेळेनुसार Chart (Sensibull-सारखं)
    साठी. established get_oi_history_cloud() पेक्षा वेगळं (त्यात बदल टाळला, सुरक्षिततेसाठी) —
    इथे underlying_price सुद्धा वाचला जातो (जो table मध्ये आधीच साठवलेला आहे, पण जुनं function वाचत
    नव्हतं). अलीकडचा वेळ शेवटी (ASC) -- chart plotting साठी योग्य क्रम.
    """
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT snapshot_time, total_call_oi, total_put_oi, underlying_price
                   FROM oi_diff_snapshots WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time ASC""",
                (symbol, trade_date),
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_oi_history_cloud(symbol, trade_date):
    """Dashboard च्या टेबलसाठी — त्या दिवसाचा संपूर्ण इतिहास (अलीकडचा वेळ सर्वात वर), premium सहित."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT snapshot_time, total_call_oi, total_put_oi, diff, delta_diff, signal,
                          total_call_premium, total_put_premium
                   FROM oi_diff_snapshots WHERE symbol=%s AND trade_date=%s
                   ORDER BY snapshot_time DESC""",
                (symbol, trade_date),
            )
            return cur.fetchall()
    finally:
        conn.close()
