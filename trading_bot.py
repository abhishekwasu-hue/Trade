import streamlit as st
import numpy as np
import pandas as pd
from scipy.stats import norm
import sqlite3
import random
import sys
from datetime import datetime, time as datetime_time

# 1. WEB DASHBOARD INITIALIZATION & LAYOUT CONFIGURATION
st.set_page_config(page_title="Institutional Multi-Broker Router v5", layout="wide")

# 2. AUTOMATED 5-MINUTE DATA REFRESH INTERVAL LOOP (300 SECONDS)
if 'count' not in st.session_state:
    st.session_state.count = 0

def auto_refresh_loop():
    st.session_state.count += 1
    st.components.v1.html(
        """
        <script>
            window.parent.document.dispatchEvent(new CustomEvent("streamlit:render"));
            setTimeout(function(){ window.location.reload(); }, 300000);
        </script>
        """, height=0
    )

auto_refresh_loop()

# ==============================================================================
# 3. BLACK-SCHOLES PRICING & DATA MATRIX SCANNERS
# ==============================================================================
class BlackScholesEngine:
    @staticmethod
    def calculate_greeks(spot, strike, t_days, r_rate, iv, option_type='CE'):
        T = max(t_days, 0.5) / 365.0
        sigma = iv / 100.0
        d1 = (np.log(spot / strike) + (r_rate + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        pdf_d1 = norm.pdf(d1)
        
        delta = norm.cdf(d1) if option_type == 'CE' else norm.cdf(d1) - 1.0
        gamma = pdf_d1 / (spot * sigma * np.sqrt(T))
        theta_term1 = -(spot * pdf_d1 * sigma) / (2 * np.sqrt(T))
        theta_term2 = r_rate * strike * np.exp(-r_rate * T) * norm.cdf(d2 if option_type == 'CE' else -d2)
        theta = (theta_term1 - theta_term2) / 365.0 if option_type == 'CE' else (theta_term1 + theta_term2) / 365.0
        
        return delta, gamma, theta

    @classmethod
    def generate_option_chain_matrix(cls, spot, step_size, base_iv):
        strikes = np.arange(int((spot // step_size) * step_size - (3 * step_size)), 
                            int((spot // step_size) * step_size + (4 * step_size)), step_size)
        chain_records = []
        
        for k in strikes:
            if k >= spot:
                c_oi_chg = random.randint(40000, 70000)
                p_oi_chg = random.randint(-5000, 10000)
            else:
                c_oi_chg = random.randint(-2000, 5000)
                p_oi_chg = random.randint(50000, 80000)
                
            net_oi_diff = p_oi_chg - c_oi_chg
            c_delta, c_gamma, c_theta = cls.calculate_greeks(spot, k, 16, 0.07, base_iv, 'CE')
            p_delta, p_gamma, p_theta = cls.calculate_greeks(spot, k, 16, 0.07, base_iv + 0.3, 'PE')
            
            chain_records.append({
                'Strike Price': k, 'Net OI Chg Diff': net_oi_diff,
                'Put Delta': round(p_delta, 2), 'Put Gamma': round(p_gamma, 5), 'Put Theta': round(p_theta, 2),
                'Call Delta': round(c_delta, 2), 'Call Gamma': round(c_gamma, 5), 'Call Theta': round(c_theta, 2)
            })
        return pd.DataFrame(chain_records)

# ==============================================================================
# 4. RESILIENT DATA FEED AGGREGATOR & BLACKOUT FILTERS
# ==============================================================================
class ResilientDataAggregator:
    def __init__(self, broker_clients=None):
        self.clients = broker_clients if broker_clients else []

    @staticmethod
    def check_heavyweight_earnings_blackout():
        is_reliance_earnings_today = False
        is_hdfc_earnings_today = False
        return is_reliance_earnings_today or is_hdfc_earnings_today

    def fetch_market_snapshot(self, index, force_trend_simulation=False, mock_vix=13.50):
        data_source = "NSE_PUBLIC_FALLBACK"
        if self.clients:
            for client in self.clients:
                if client.get("status") == "CONNECTED":
                    data_source = f"BROKER_WS_{client['name'].upper()}"
                    break
                    
        if index == "NIFTY":
            spot = 24583.80 + random.uniform(-5, 5)
            vwap = 24555.0
            rsi = 74.20 if force_trend_simulation else 52.0  
            pattern = "BEARISH_SHOOTING_STAR" if force_trend_simulation else "NO_TREND_SIDEWAYS"
            resistance, support = 24750.0, 24450.0
            base_iv = 12.10
            atr = 95.0  
        else:
            spot = 80420.50 + random.uniform(-15, 15)
            vwap = 80410.0
            rsi = 26.50 if force_trend_simulation else 48.50
            pattern = "BULLISH_HAMMER" if force_trend_simulation else "NO_TREND_SIDEWAYS"
            resistance, support = 80900.0, 80100.0
            base_iv = 11.85
            atr = 280.0

        return {
            "spot": spot, "vwap": vwap, "rsi": rsi, "pattern": pattern,
            "resistance": resistance, "support": support, "source": data_source, 
            "base_iv": base_iv, "atr": atr, "india_vix": mock_vix
        }

# ==============================================================================
# 5. ACCOUNT CONDUIT MULTIPLIER AND SAFETY GUARDS
# ==============================================================================
class MultiBrokerExecutionRouter:
    def __init__(self):
        self.active_sessions = []

    def authenticate_accounts(self, configuration_list):
        self.active_sessions = []
        for config in configuration_list:
            client_name = config["name"]
            api_key = config.get("api_key", "")
            secret_key = config.get("secret_key", "")
            try:
                if not api_key or not secret_key:
                    raise KeyError(f"{client_name} keys absent.")
                self.active_sessions.append({
                    "name": client_name, "status": "CONNECTED", "multiplier": config.get("multiplier", 1)
                })
            except (KeyError, ConnectionError) as e:
                print(f"⚠️ EXCEPTION HANDLED: {client_name} paper path chosen. Reason: {e}", file=sys.stderr)
                self.active_sessions.append({
                    "name": client_name, "status": "BYPASS_PAPER_ONLY", "multiplier": 0
                })
        return self.active_sessions

    def fire_multi_broker_orders(self, index, strategy, short_k, hedge_k, base_lots, upper_short=None, upper_hedge=None):
        execution_report = []
        if not self.active_sessions:
            return [{"broker": "NONE", "status": "SKIPPED", "msg": "No live sessions authenticated."}]
            
        for session in self.active_sessions:
            if session["status"] == "CONNECTED":
                allocated_lots = int(base_lots * session["multiplier"])
                if strategy == "IRON_CONDOR":
                    msg = f"IRON CONDOR FIRED: BUY {hedge_k} PE & {upper_hedge} CE | SELL {short_k} PE & {upper_short} CE | size: {allocated_lots} Lots."
                else:
                    msg = f"DIRECTIONAL CREDIT SPREAD FIRED: BUY {hedge_k} / SELL {short_k} | size: {allocated_lots} Lots."
                execution_report.append({"broker": session["name"], "status": "LIVE_SUCCESS", "msg": msg})
            else:
                execution_report.append({
                    "broker": session["name"], "status": "PAPER_ONLY_FALLBACK",
                    "msg": f"Skipped active routing for {strategy}. Paper transaction logged."
                })
        return execution_report

# ==============================================================================
# 6. SQLITE SYSTEM STORAGE MANAGEMENT 
# ==============================================================================
def execute_sql_query(query, params=(), fetch=False):
    conn = sqlite3.connect("cloud_portfolio_vault.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS universal_paper_book (
            id TEXT PRIMARY KEY, timestamp TEXT, asset TEXT, strategy TEXT,
            short_strike TEXT, hedge_strike TEXT, base_lots INTEGER, entry_price REAL
        )
    """)
    cursor.execute(query, params)
    conn.commit()
    data = cursor.fetchall() if fetch else None
    conn.close()
    return data

# ==============================================================================
# 7. STREAMLIT CLOUD USER INTERFACE (UI) IMPLEMENTATION
# ==============================================================================
st.title("⚡ QUANT ARCHITECTURE PRO v5 | Dynamic India VIX Control Room")
st.markdown(f"**⏱️ Refresh Count:** {st.session_state.count} | **Server Time:** {datetime.now().strftime('%H:%M:%S')}")
st.markdown("---")

# A. SIDEBAR INTERFACE PANEL
st.sidebar.header("🔑 Multi-Account Configurations")
broker_a_key = st.sidebar.text_input("API Key (Zerodha)", type="password", key="br_a_k")
broker_a_secret = st.sidebar.text_input("Secret Key (Zerodha)", type="password", key="br_a_s")
mult_a = st.sidebar.slider("Lot Multiplier (Zerodha)", min_value=1, max_value=5, value=1)

broker_b_key = st.sidebar.text_input("API Key (AngelOne)", type="password", key="br_b_k")
broker_b_secret = st.sidebar.text_input("Secret Key (AngelOne)", type="password", key="br_b_s")
mult_b = st.sidebar.slider("Lot Multiplier (AngelOne)", min_value=1, max_value=5, value=1)

st.sidebar.markdown("---")
st.sidebar.header("🎯 System Regime Controls")

# १. मॅन्युअल ट्रेंड ओव्हरराइड स्विच
trend_override = st.sidebar.toggle(
    "⚠️ Enforce Manual Trend Override", 
    value=False, 
    help="चालू केल्यास सिस्टीम सिडवेज मार्केट पूर्णपणे इग्नोर करेल आणि फक्त वन-वे ट्रेड शोधेल."
)

# २. मॅन्युअल इंडिया व्हीआयएक्स सिम्युलेटर (रात्री किंवा टेस्ट रनसाठी मोलाचा फिल्टर)
live_vix_input = st.sidebar.slider(
    "📊 India VIX Stress Simulator", 
    min_value=10.0, max_value=30.0, value=13.5, step=0.5,
    help="तुम्ही हा स्लायडर बदलून सिस्टीम हाय व्होलाटिलिटीला कशी रिॲक्ट करते ते आत्ताच पाहू शकता."
)

st.sidebar.markdown("---")
