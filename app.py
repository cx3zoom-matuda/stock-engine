import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple

from src.detector import EventDetector
from src.engine import RuleEngine
from src.evaluator import StockEvaluator
from src.config import load_config, COUNTRY_SERIES_MAP
from src.providers.factory import ProviderFactory
from src.translations import t

# Initialize language in session state
if "language" not in st.session_state:
    st.session_state.language = "jp"

# Set page config with premium dashboard settings
st.set_page_config(
    page_title=t("page_title"),
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling for premium look and feel
st.markdown("""
<style>
    .reportview-container {
        background: #0f172a;
    }
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Load configuration
config = load_config()
default_tickers_dict = config.get("settings", {}).get("tickers", {})
default_api_key = config.get("api", {}).get("fred_api_key", "")

# Fallback to Streamlit Secrets if deployed in Streamlit Community Cloud
if not default_api_key:
    try:
        if "api" in st.secrets and "fred_api_key" in st.secrets["api"]:
            default_api_key = st.secrets["api"]["fred_api_key"]
    except Exception:
        pass

# Application Header
st.title(t("app_title"))
st.markdown(t("app_desc"))

# Initialize component engines
detector = EventDetector()
engine = RuleEngine()

def prepare_country_detector_inputs(
    raw_macro: Dict[str, pd.DataFrame], 
    country_code: str,
    futures_history: Dict[str, pd.Series] = None
) -> Dict[str, Any]:
    """
    Extracts and structures time series data from raw FRED DataFrames
    for a specific G20 country so that EventDetector can parse it.
    """
    inputs = {}
    cmap = COUNTRY_SERIES_MAP.get(country_code, {})
    
    def get_series(series_id: str) -> pd.Series:
        if not series_id:
            return pd.Series(dtype=float)
        df = raw_macro.get(series_id, pd.DataFrame())
        if df.empty:
            return pd.Series(dtype=float)
        return df["value"]

    # 1. 10Y Yield
    inputs["YIELD_10Y"] = get_series(cmap.get("YIELD_10Y"))
    
    # 2. Central Bank Policy Rate
    inputs["POLICY_RATE"] = get_series(cmap.get("POLICY_RATE"))
    
    # 3. CPI
    df_cpi = raw_macro.get(cmap.get("CPI", ""), pd.DataFrame())
    if not df_cpi.empty:
        cpi_val = df_cpi["value"]
        if country_code == "US":  # US CPIAUCSL is an index level, calculate YoY
            cpi_yoy = []
            for i in range(len(cpi_val)):
                if i >= 12:
                    yoy = ((cpi_val.iloc[i] - cpi_val.iloc[i-12]) / cpi_val.iloc[i-12]) * 100
                    cpi_yoy.append(yoy)
                else:
                    cpi_yoy.append(2.0)
            inputs["CPI"] = pd.Series(cpi_yoy, index=df_cpi.index)
        else:  # Other countries' CPALTT01 series are already YoY growth percentage
            inputs["CPI"] = cpi_val
    else:
        inputs["CPI"] = pd.Series([2.0, 2.0], dtype=float)

    # 4. Confidence (PMI/Tankan proxy)
    inputs["CONFIDENCE"] = get_series(cmap.get("CONFIDENCE"))
    
    # 5. GDP Growth
    df_gdp = raw_macro.get(cmap.get("GDP", ""), pd.DataFrame())
    if not df_gdp.empty:
        gdp_val = df_gdp["value"]
        if country_code == "US":  # US GDPC1 is index level, calculate YoY
            gdp_yoy = []
            for i in range(len(gdp_val)):
                if i >= 4:
                    yoy = ((gdp_val.iloc[i] - gdp_val.iloc[i-4]) / gdp_val.iloc[i-4]) * 100
                    gdp_yoy.append(yoy)
                else:
                    gdp_yoy.append(2.0)
            inputs["GDP"] = pd.Series(gdp_yoy, index=df_gdp.index)
        else:  # Other countries' GDP series are YoY growth rates
            inputs["GDP"] = gdp_val
    else:
        inputs["GDP"] = pd.Series([2.0, 2.0], dtype=float)

    # 6. Global Oil Price
    inputs["OIL_PRICE"] = get_series("DCOILWTICO")

    # 7. Commodity Futures
    if futures_history:
        inputs["GOLD_PRICE"] = futures_history.get("GC=F", pd.Series(dtype=float))
        inputs["COPPER_PRICE"] = futures_history.get("HG=F", pd.Series(dtype=float))
        inputs["NATURAL_GAS"] = futures_history.get("NG=F", pd.Series(dtype=float))
        cl_f = futures_history.get("CL=F")
        if cl_f is not None and not cl_f.empty:
            inputs["OIL_PRICE"] = cl_f
    else:
        inputs["GOLD_PRICE"] = pd.Series(dtype=float)
        inputs["COPPER_PRICE"] = pd.Series(dtype=float)
        inputs["NATURAL_GAS"] = pd.Series(dtype=float)

    # 8. Money Supply M2/M3 YoY Growth
    df_m2 = raw_macro.get(cmap.get("MONEY_SUPPLY", ""), pd.DataFrame())
    if not df_m2.empty:
        m2_val = df_m2["value"]
        m2_yoy = []
        for i in range(len(m2_val)):
            if i >= 12:
                yoy = ((m2_val.iloc[i] - m2_val.iloc[i-12]) / m2_val.iloc[i-12]) * 100
                m2_yoy.append(yoy)
            else:
                m2_yoy.append(5.0)
        inputs["MONEY_SUPPLY"] = pd.Series(m2_yoy, index=df_m2.index)
    else:
        inputs["MONEY_SUPPLY"] = pd.Series([5.0, 5.0], dtype=float)

    # 9. Local Currency & Quote
    cc_map = {
        "US": {"ticker": "DX-Y.NYB", "quote": "dollar_index"},
        "JP": {"ticker": "USDJPY=X", "quote": "indirect"},
        "EZ": {"ticker": "EURUSD=X", "quote": "direct"},
        "GB": {"ticker": "GBPUSD=X", "quote": "direct"},
        "CN": {"ticker": "USDCNY=X", "quote": "indirect"},
        "CA": {"ticker": "USDCAD=X", "quote": "indirect"},
        "AU": {"ticker": "AUDUSD=X", "quote": "direct"},
    }
    c_info = cc_map.get(country_code, {"ticker": "DX-Y.NYB", "quote": "dollar_index"})
    ticker = c_info["ticker"]
    quote = c_info["quote"]
    inputs["CURRENCY_QUOTE"] = quote
    if futures_history and ticker in futures_history:
        inputs["LOCAL_CURRENCY"] = futures_history[ticker]
    else:
        inputs["LOCAL_CURRENCY"] = pd.Series(dtype=float)
    
    return inputs

# Async client pipeline wrapped with Streamlit's caching
@st.cache_data(show_spinner="Running quant screening pipeline (fetching macro & stock data)...")
def run_screening_pipeline(tickers_by_country, fred_api_key):
    async def run_pipeline_async():
        macro_provider = ProviderFactory.get_macro_provider(api_key=fred_api_key)
        stock_provider = ProviderFactory.get_stock_provider()
        
        # Collect all FRED series IDs needed across G20 countries
        series_ids = ["DCOILWTICO", "DTB3", "DGS2", "DGS5"]  # WTI, and 3M, 2Y, 5Y yields for US yield curve
        for country, map_ids in COUNTRY_SERIES_MAP.items():
            for key, sid in map_ids.items():
                if sid:
                    series_ids.append(sid)
        series_ids = list(set(series_ids))
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=600)).strftime("%Y-%m-%d")
        
        fred_tasks = {sid: macro_provider.fetch_series(sid, start_date, end_date) for sid in series_ids}
        raw_macro = {}
        for sid, task in fred_tasks.items():
            raw_macro[sid] = await task
            
        if hasattr(macro_provider, "close"):
            await macro_provider.close()
        
        # Gather all G20 tickers to load
        all_tickers = []
        for country, t_list in tickers_by_country.items():
            all_tickers.extend(t_list)
        all_tickers.extend(["^VIX", "GC=F", "CL=F", "HG=F", "NG=F", "USDJPY=X", "EURUSD=X", "GBPUSD=X", "USDCNY=X", "USDCAD=X", "AUDUSD=X", "DX-Y.NYB"])  # VIX, Commodities & Exchange Rates
        all_tickers = list(set(all_tickers))
        
        stock_tasks = [stock_provider.fetch_stock_metrics(t) for t in all_tickers]
        stock_metrics = await asyncio.gather(*stock_tasks)
        
        # Group stock metrics by ticker for easy retrieval
        stock_metrics_map = {m["ticker"]: m for m in stock_metrics if m}

        # Fetch historical prices for futures and currencies to calculate changes
        futures_tickers = ["^VIX", "GC=F", "CL=F", "HG=F", "NG=F", "USDJPY=X", "EURUSD=X", "GBPUSD=X", "USDCNY=X", "USDCAD=X", "AUDUSD=X", "DX-Y.NYB"]
        futures_tasks = {t: stock_provider.fetch_historical_prices(t, days=60) for t in futures_tickers}
        futures_history = {}
        for t, task in futures_tasks.items():
            futures_history[t] = await task
        
        return raw_macro, stock_metrics_map, futures_history

    # Execute async loop synchronously inside Streamlit
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        raw_macro, stock_metrics_map, futures_history = loop.run_until_complete(run_pipeline_async())
    finally:
        loop.close()
        
    return raw_macro, stock_metrics_map, futures_history

# Sidebar configuration
st.sidebar.header(t("sidebar_title"))

# Language selector
lang_choice = st.sidebar.selectbox(
    t("language_label"),
    ["日本語", "English"],
    index=0 if st.session_state.language == "jp" else 1
)
new_lang = "jp" if lang_choice == "日本語" else "en"
if new_lang != st.session_state.language:
    st.session_state.language = new_lang
    st.rerun()

# API Keys
fred_api_key_input = st.sidebar.text_input(
    t("fred_key_label"),
    value=default_api_key,
    type="password", 
    help=t("fred_key_help")
)

# Target Stock Tickers Input (Split by Region dynamically)
st.sidebar.subheader(t("screening_list"))
active_tickers_dict = {}
for country_code in COUNTRY_SERIES_MAP.keys():
    defaults = default_tickers_dict.get(country_code, [])
    val_str = st.sidebar.text_input(
        t("tickers_label", country_code),
        value=", ".join(defaults)
    )
    active_tickers_dict[country_code] = [t.strip() for t in val_str.split(",") if t.strip()]

# Refresh button
if st.sidebar.button(t("reload_btn"), use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader(t("qualitative_title"))

# Manual switches/sliders for event cycles
ai_investment_boom = st.sidebar.slider(t("ai_boom_label"), min_value=0, max_value=3, value=1, step=1)
semiconductor_capex_cycle = st.sidebar.slider(t("semi_cycle_label"), min_value=0, max_value=3, value=1, step=1)
defense_spending_increase = st.sidebar.slider(t("defense_label"), min_value=0, max_value=3, value=0, step=1)
china_recovery = st.sidebar.checkbox(t("china_rec_label"), value=False)
china_slowing = st.sidebar.checkbox(t("china_slow_label"), value=False)

# Added overrides for G20 countries
st.sidebar.markdown(t("macro_overrides"))
rate_hike_override = st.sidebar.checkbox(t("cb_hike_label"))
rate_cut_override = st.sidebar.checkbox(t("cb_cut_label"))
business_expansion_override = st.sidebar.checkbox(t("expansion_label"))
business_contraction_override = st.sidebar.checkbox(t("contraction_label"))
labor_tightening_override = st.sidebar.checkbox(t("labor_label"))
china_mfg_slowdown_override = st.sidebar.checkbox(t("china_mfg_label"))
yield_curve_inversion_override = st.sidebar.checkbox(t("yield_inv_label"))

# Fetch API and stock metrics data
try:
    all_active_tickers = []
    for country, t_list in active_tickers_dict.items():
        all_active_tickers.extend(t_list)
    all_active_tickers = list(set(all_active_tickers))
    
    raw_macro_data, stock_metrics_map, futures_history = run_screening_pipeline(active_tickers_dict, fred_api_key_input)
except Exception as e:
    st.error(f"Failed to execute pipeline: {e}")
    # Simulated fallback if everything fails
    raw_macro_data = {}
    stock_metrics_map = {}
    futures_history = {}
    for country, t_list in active_tickers_dict.items():
        for t in t_list:
            stock_metrics_map[t] = {
                "ticker": t,
                "name": t.split(".")[0],
                "sector": "electronics",
                "per": 15.0,
                "pbr": 1.0,
                "price": 100.0
            }

# Add manual qualitative overrides helper
def apply_manual_overrides(inputs_dict: Dict[str, Any]):
    if ai_investment_boom > 0:
        inputs_dict["ai_investment_boom"] = ai_investment_boom
    if semiconductor_capex_cycle > 0:
        inputs_dict["semiconductor_capex_cycle"] = semiconductor_capex_cycle
    if defense_spending_increase > 0:
        inputs_dict["defense_spending_increase"] = defense_spending_increase
    if china_recovery:
        inputs_dict["china_recovery"] = True
    if china_slowing:
        inputs_dict["china_slowing"] = True

    # Generic overrides
    if rate_hike_override:
        inputs_dict["rate_hike"] = True
    if rate_cut_override:
        inputs_dict["rate_cut"] = True
    if business_expansion_override:
        inputs_dict["business_expansion"] = True
    if business_contraction_override:
        inputs_dict["business_contraction"] = True
    if labor_tightening_override:
        inputs_dict["labor_market_tightening"] = True
    if china_mfg_slowdown_override:
        inputs_dict["china_manufacturing_slowdown"] = True
    if yield_curve_inversion_override:
        inputs_dict["yield_curve_inversion"] = True
        
    # VIX risk-off automated override
    vix_p = stock_metrics_map.get("^VIX", {}).get("price", 15.0)
    if vix_p > 22.0:
        inputs_dict["business_contraction"] = True

# Country names & maps
COUNTRY_NAMES = {
    "US": "United States" if st.session_state.language == "en" else "米国",
    "JP": "Japan" if st.session_state.language == "en" else "日本",
    "EZ": "Euro Area" if st.session_state.language == "en" else "ユーロ圏",
    "GB": "United Kingdom" if st.session_state.language == "en" else "英国",
    "CN": "China" if st.session_state.language == "en" else "中国",
    "CA": "Canada" if st.session_state.language == "en" else "カナダ",
    "AU": "Australia" if st.session_state.language == "en" else "オーストラリア"
}

COUNTRY_FLAGS = {
    "US": "🇺🇸",
    "JP": "🇯🇵",
    "EZ": "🇪🇺",
    "GB": "🇬🇧",
    "CN": "🇨🇳",
    "CA": "🇨🇦",
    "AU": "🇦🇺"
}

CURRENCY_MAP = {
    "JP": "¥",
    "US": "$",
    "EZ": "€",
    "GB": "£",
    "CA": "$",
    "AU": "$"
}

def style_decision(val):
    if val == "BUY":
        return "background-color: rgba(46, 204, 113, 0.2); color: #2ecc71; font-weight: bold;"
    elif val == "AVOID":
        return "background-color: rgba(231, 76, 60, 0.2); color: #e74c3c; font-weight: bold;"
    else:
        return "background-color: rgba(241, 196, 15, 0.2); color: #f1c40f; font-weight: bold;"

from src.paper_trade import PaperTradeAccount

# Initialize paper trade accounts and real portfolio in session state
if "paper_accounts" not in st.session_state:
    st.session_state.paper_accounts = {
        "Macro Tailwind Focus": PaperTradeAccount("📈 Macro Tailwind Focus", currency=CURRENCY_MAP.get("US", "$")),
        "Defensive & Income": PaperTradeAccount("🛡️ Defensive & Income", currency=CURRENCY_MAP.get("US", "$")),
        "Aggressive Growth": PaperTradeAccount("🚀 Aggressive Growth", currency=CURRENCY_MAP.get("US", "$")),
        "Long-Term Value": PaperTradeAccount("💎 Long-Term Value", currency=CURRENCY_MAP.get("US", "$")),
        "Sandbox": PaperTradeAccount("🧪 Sandbox", currency=CURRENCY_MAP.get("US", "$"))
    }

if "real_portfolio" not in st.session_state:
    st.session_state.real_portfolio = PaperTradeAccount("🇯🇵/🇺🇸 Real Portfolio (楽天CSV連携)", currency=CURRENCY_MAP.get("US", "$"))

# Sync account currency dynamically based on current target market
current_curr = CURRENCY_MAP.get(st.session_state.selected_country if "selected_country" in st.session_state else "US", "$")
for acc_key, acc_obj in st.session_state.paper_accounts.items():
    acc_obj.currency = current_curr
if "real_portfolio" in st.session_state:
    st.session_state.real_portfolio.currency = current_curr

# --- VISUAL COUNTRY SELECTOR (BIG FLAGS) AT THE TOP ---
available_countries = [c for c in COUNTRY_SERIES_MAP.keys() if active_tickers_dict.get(c)]
if not available_countries:
    available_countries = ["US", "JP"]

# Initialize session state for selected country
if "selected_country" not in st.session_state:
    st.session_state.selected_country = available_countries[0]

# Fallback check if # Render big flag buttons side by side
st.markdown(f"### {t('select_market')}")
cols_flags = st.columns(len(available_countries))

for idx, country_code in enumerate(available_countries):
    flag = COUNTRY_FLAGS.get(country_code, "🏳️")
    name = COUNTRY_NAMES.get(country_code, country_code)
    
    is_active = (st.session_state.selected_country == country_code)
    
    # Render styled button - active is 'primary' (visually highlighted)
    if cols_flags[idx].button(
        f"{flag} {name}", 
        key=f"flag_btn_{country_code}", 
        use_container_width=True,
        type="primary" if is_active else "secondary"
    ):
        st.session_state.selected_country = country_code
        st.rerun()

st.markdown("---")

# --- RENDER DATA FOR THE SELECTED COUNTRY ---
current_country = st.session_state.selected_country

# 1. Structure Inputs for Event Detector
country_inputs = prepare_country_detector_inputs(raw_macro_data, current_country, futures_history)
apply_manual_overrides(country_inputs)

# 2. RENDER KPI CARDS
st.subheader(t("macro_indicators", COUNTRY_FLAGS.get(current_country), COUNTRY_NAMES.get(current_country)))
cols = st.columns(6)

try:
    # POLICY RATE Card
    policy_rate = country_inputs["POLICY_RATE"]
    if len(policy_rate) >= 2:
        latest_pol = policy_rate.iloc[-1]
        prev_pol = policy_rate.iloc[-2]
        diff_pol = latest_pol - prev_pol
        cols[0].metric(
            label=t("policy_rate"),
            value=f"{latest_pol:.2f}%",
            delta=f"{diff_pol:+.2f}% pts (30d)"
        )
    else:
        cols[0].metric(label=t("policy_rate"), value="N/A")

    # 10Y Yield Card
    yield_10y = country_inputs["YIELD_10Y"]
    if len(yield_10y) >= 2:
        latest_10y = yield_10y.iloc[-1]
        prev_10y = yield_10y.iloc[-2]
        diff_10y = latest_10y - prev_10y
        cols[1].metric(
            label=t("ten_year_yield"),
            value=f"{latest_10y:.2f}%",
            delta=f"{diff_10y:+.2f}% pts (30d)"
        )
    else:
        cols[1].metric(label=t("ten_year_yield"), value="N/A")

    # CPI Card
    cpi = country_inputs["CPI"]
    if not cpi.empty:
        latest_cpi = cpi.iloc[-1]
        cols[2].metric(
            label=t("cpi"),
            value=f"{latest_cpi:.2f}%",
            delta=t("cpi_target"),
            delta_color="inverse" if latest_cpi > 2.0 else "normal"
        )
    else:
        cols[2].metric(label=t("cpi"), value="N/A")

    # Business Confidence Card
    conf = country_inputs["CONFIDENCE"]
    if not conf.empty:
        latest_conf = conf.iloc[-1]
        threshold = 50.0 if latest_conf < 75.0 else 100.0
        cols[3].metric(
            label=t("business_confidence"),
            value=f"{latest_conf:.1f}",
            delta=f"Threshold: {threshold}",
            delta_color="normal" if latest_conf >= threshold else "inverse"
        )
    else:
        cols[3].metric(label=t("business_confidence"), value="N/A")

    # GDP YoY Card
    gdp = country_inputs["GDP"]
    if not gdp.empty:
        latest_gdp = gdp.iloc[-1]
        cols[4].metric(
            label=t("gdp_growth"),
            value=f"{latest_gdp:.2f}%",
            delta=t("gdp_exp")
        )
    else:
        cols[4].metric(label=t("gdp_growth"), value="N/A")

    # Money Supply (M2/M3) Card
    m2 = country_inputs["MONEY_SUPPLY"]
    if not m2.empty:
        latest_m2 = m2.iloc[-1]
        prev_m2 = m2.iloc[-2] if len(m2) >= 2 else latest_m2
        diff_m2 = latest_m2 - prev_m2
        cols[5].metric(
            label=t("money_supply"),
            value=f"{latest_m2:.2f}%",
            delta=f"{diff_m2:+.2f}% pts (30d)",
            help=t("money_supply_help")
        )
    else:
        cols[5].metric(label=t("money_supply"), value="N/A")
except Exception as kpi_err:
    st.error(f"Error rendering KPI indicators: {kpi_err}")
    
st.markdown("---")

# --- GLOBAL MARKET SENTIMENT & YIELD CURVE PANEL ---
def get_futures_change(ticker: str) -> Tuple[float, float]:
    series = futures_history.get(ticker, pd.Series(dtype=float))
    if len(series) >= 2:
        latest_val = float(series.iloc[-1])
        target_date = series.index[-1] - timedelta(days=30)
        past_dates = series.index[series.index <= target_date]
        if len(past_dates) > 0:
            past_val = float(series.loc[past_dates[-1]])
        else:
            past_val = float(series.iloc[0])
        pct_change = ((latest_val - past_val) / past_val) * 100
        return latest_val, pct_change
    latest_val = stock_metrics_map.get(ticker, {}).get("price", 0.0)
    return latest_val, 0.0

st.subheader(t("global_sentiment"))
m_col1, m_col2 = st.columns([2, 3])

with m_col1:
    st.write(f"**{t('volatility_commodities')}**")
    
    sub_col1, sub_col2, sub_col3 = st.columns(3)
    
    vix_val, vix_chg = get_futures_change("^VIX")
    vix_status = ""
    if st.session_state.language == "en":
        vix_status = "Fear 🔴" if vix_val > 22.0 else "Stable 🟢"
    else:
        vix_status = "恐怖 🔴" if vix_val > 22.0 else "安定 🟢"
        
    sub_col1.metric(
        label=t("vix_label"),
        value=f"{vix_val:.2f}",
        delta=vix_status,
        delta_color="normal" if vix_val <= 22.0 else "inverse"
    )
    
    gold_val, gold_chg = get_futures_change("GC=F")
    sub_col2.metric(
        label=t("gold_label"),
        value=f"${gold_val:,.1f}",
        delta=f"{gold_chg:+.1f}%"
    )
    
    oil_val, oil_chg = get_futures_change("CL=F")
    sub_col3.metric(
        label=t("oil_label"),
        value=f"${oil_val:,.2f}",
        delta=f"{oil_chg:+.1f}%"
    )
    
    st.write("") # Spacing
    sub_col4, sub_col5, sub_col6 = st.columns(3)
    
    copper_val, copper_chg = get_futures_change("HG=F")
    sub_col4.metric(
        label=t("copper_label"),
        value=f"${copper_val:,.4f}",
        delta=f"{copper_chg:+.1f}%"
    )
    
    gas_val, gas_chg = get_futures_change("NG=F")
    sub_col5.metric(
        label=t("gas_label"),
        value=f"${gas_val:,.3f}",
        delta=f"{gas_chg:+.1f}%"
    )

    # Local Currency Exchange Rate Metric Card
    is_en = (st.session_state.language == "en")
    c_info = {
        "US": {"ticker": "DX-Y.NYB", "label": "US Dollar Index (DXY)" if is_en else "米ドル指数 (DXY)"},
        "JP": {"ticker": "USDJPY=X", "label": "USD/JPY (Weak/Strong Yen)" if is_en else "USD/JPY (円安/円高)"},
        "EZ": {"ticker": "EURUSD=X", "label": "EUR/USD (Euro/Dollar)" if is_en else "EUR/USD (ユーロドル)"},
        "GB": {"ticker": "GBPUSD=X", "label": "GBP/USD (Pound/Dollar)" if is_en else "GBP/USD (ポンドドル)"},
        "CN": {"ticker": "USDCNY=X", "label": "USD/CNY (Yuan)" if is_en else "USD/CNY (人民元)"},
        "CA": {"ticker": "USDCAD=X", "label": "USD/CAD (Loonie)" if is_en else "USD/CAD (加ドル)"},
        "AU": {"ticker": "AUDUSD=X", "label": "AUD/USD (Aussie)" if is_en else "AUD/USD (豪ドル)"},
    }.get(current_country, {"ticker": "DX-Y.NYB", "label": "US Dollar Index (DXY)" if is_en else "米ドル指数 (DXY)"})
    
    curr_val, curr_chg = get_futures_change(c_info["ticker"])
    curr_format = f"{curr_val:.4f}" if curr_val < 5.0 else f"{curr_val:.2f}"
    sub_col6.metric(
        label=c_info["label"],
        value=curr_format,
        delta=f"{curr_chg:+.1f}%"
    )
    
    if vix_val > 22.0:
        st.info(t("vix_elevated"))
    else:
        st.success(t("vix_stable"))

with m_col2:
    st.write(f"**{t('yield_curve_label')}**")
    try:
        y_3m = raw_macro_data.get("DTB3", pd.DataFrame())
        y_2y = raw_macro_data.get("DGS2", pd.DataFrame())
        y_5y = raw_macro_data.get("DGS5", pd.DataFrame())
        y_10y = raw_macro_data.get("DGS10", pd.DataFrame())
        
        val_3m = y_3m["value"].iloc[-1] if not y_3m.empty else 4.0
        val_2y = y_2y["value"].iloc[-1] if not y_2y.empty else 4.2
        val_5y = y_5y["value"].iloc[-1] if not y_5y.empty else 4.1
        val_10y = y_10y["value"].iloc[-1] if not y_10y.empty else 4.0
        
        fig_curve = go.Figure()
        fig_curve.add_trace(go.Scatter(
            x=["3-Month", "2-Year", "5-Year", "10-Year"],
            y=[val_3m, val_2y, val_5y, val_10y],
            mode='lines+markers',
            line=dict(color='#38bdf8', width=3),
            marker=dict(size=8),
            name="US Yield Curve"
        ))
        fig_curve.update_layout(
            height=250,
            margin=dict(l=20, r=20, t=10, b=10),
            yaxis_title="Yield (%)",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            xaxis=dict(gridcolor="#334155"),
            yaxis=dict(gridcolor="#334155")
        )
        st.plotly_chart(fig_curve, use_container_width=True, key="yield_curve_chart")
        
        if val_2y > val_10y or val_3m > val_10y:
            st.error(t("yield_inverted", val_3m=val_3m, val_2y=val_2y, val_10y=val_10y))
        else:
            st.success(t("yield_normal"))
    except Exception as curve_err:
        st.warning(f"Unable to render yield curve: {curve_err}")

st.markdown("---")

# 3. RUN ALGORITHMS FOR THIS COUNTRY
active_events = detector.detect_events(country_inputs)
results = engine.calculate_industry_scores(active_events)

# 4. MIDDLE ROW: ACTIVE EVENTS & SECTOR RANKINGS
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader(t("active_events"))
    if active_events:
        for event in active_events:
            severity = event["severity"]
            sev_color = "red" if severity == 3 else "orange" if severity == 2 else "blue"
            st.markdown(
                f"**🟢 `{event['event']}`** (Severity: :{sev_color}[{severity}])  \n"
                f"*{event['description']}*"
            )
    else:
        st.info(t("no_active_events"))

with col_right:
    st.subheader(t("core_rankings"))
    rankings = results["rankings"]
    sectors = [r["sector"] for r in rankings]
    scores = [r["score"] for r in rankings]
    
    # Create color list based on score polarity
    colors = []
    for score in scores:
        if score > 0:
            colors.append("#2ecc71")  # Green
        elif score < 0:
            colors.append("#e74c3c")  # Red
        else:
            colors.append("#95a5a6")  # Grey
            
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=sectors,
        x=scores,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(color='rgba(0,0,0,0.1)', width=1)
        ),
        text=[f"{score:+.1f}" if score != 0 else "0.0" for score in scores],
        textposition='auto',
    ))
    
    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=10, b=10),
        yaxis=dict(autorange="reversed"),
        xaxis_title="Aggregate Score",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0")
    )
    st.plotly_chart(fig, use_container_width=True, key=f"plot_{current_country}")

# 5. DETAILED FACTOR BREAKDOWN
with st.expander(t("breakdown_title")):
    breakdown_rows = []
    for item in rankings:
        sector = item["sector"]
        score = item["score"]
        norm_score = item["normalized_score"]
        
        if not item["breakdown"]:
            breakdown_rows.append({
                "Core Sector": sector,
                "Total Score": score,
                "Normalized Score": norm_score,
                "Active Trigger": "None",
                "Base Weight": 0,
                "Severity": 0,
                "Net Impact": 0
            })
        else:
            for b in item["breakdown"]:
                breakdown_rows.append({
                    "Core Sector": sector,
                    "Total Score": score,
                    "Normalized Score": norm_score,
                    "Active Trigger": b["event"],
                    "Base Weight": b["base_weight"],
                    "Severity": b["severity"],
                    "Net Impact": b["impact_contribution"]
                })

    df_breakdown = pd.DataFrame(breakdown_rows)
    st.dataframe(
        df_breakdown,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total Score": st.column_config.NumberColumn(format="%.1f"),
            "Normalized Score": st.column_config.NumberColumn(format="%.4f"),
            "Base Weight": st.column_config.NumberColumn(format="%+d"),
            "Net Impact": st.column_config.NumberColumn(format="%+d")
        },
        key=f"df_breakdown_{current_country}"
    )

st.markdown("---")

# 6. STOCK RANKING & DETAILS PANEL
st.subheader(t("stock_screening"))

# Transform RuleEngine rankings into StockEvaluator expected format
sector_scores = {}
for item in results["rankings"]:
    sector_scores[item["sector"]] = {
        "score": item["score"],
        "breakdown": [
            {
                "signal": b["event"],
                "impact": b["impact_contribution"],
                "description": b["description"]
            }
            for b in item["breakdown"]
        ]
    }

# Filter stock metrics for this specific country
country_tickers = active_tickers_dict.get(current_country, [])
country_stock_metrics = []
for t in country_tickers:
    m = stock_metrics_map.get(t)
    if m:
        country_stock_metrics.append(m)

# Run StockEvaluator
evaluator = StockEvaluator()
evaluated_stocks = evaluator.evaluate_stocks(country_stock_metrics, sector_scores, market=current_country)

if evaluated_stocks:
    col_tbl, col_pnl = st.columns([5, 4])
    
    with col_tbl:
        st.write(f"**{t('screened_rankings')}**")
        
        df_stocks_ui = []
        symbol = CURRENCY_MAP.get(current_country, "$")
        for s in evaluated_stocks:
            price_str = f"{symbol}{s['price']:,.2f}" if symbol != "¥" else f"¥{s['price']:,.1f}"
            df_stocks_ui.append({
                "Decision": s["decision"],
                "Ticker": s["ticker"],
                "Name": s["name"],
                "Sector": s["sector"].replace("_", " ").title(),
                "Price": price_str if s['price'] > 0 else "N/A",
                "PER": f"{s['per']:.1f}",
                "PBR": f"{s['pbr']:.2f}",
                "Macro Score": f"{s['macro_score']:+.1f}",
                "Combined Score": f"{s['combined_score']:+.1f}"
            })
        
        df_stocks = pd.DataFrame(df_stocks_ui)
        
        st.dataframe(
            df_stocks.style.map(style_decision, subset=["Decision"]),
            use_container_width=True,
            hide_index=True,
            key=f"df_stocks_{current_country}"
        )

    with col_pnl:
        st.write(f"**{t('analysis_panel')}**")
        
        selected_ticker = st.selectbox(
            t("select_ticker"),
            options=[s["ticker"] for s in evaluated_stocks],
            format_func=lambda t: f"{t} - {next(s['name'] for s in evaluated_stocks if s['ticker'] == t)}",
            key=f"sel_ticker_{current_country}"
        )
        
        selected_stock = next(s for s in evaluated_stocks if s["ticker"] == selected_ticker)
        symbol = CURRENCY_MAP.get(current_country, "$")
        price_str = f"{symbol}{selected_stock['price']:,.2f}" if symbol != "¥" else f"¥{selected_stock['price']:,.1f}"
        
        drivers_title = t("macro_drivers", selected_stock['sector'].replace('_', ' ').title(), selected_stock['macro_score'])
        
        # Render details panel HTML card
        st.markdown(f"""
        <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; color: #e2e8f0;">
            <h3 style="color: #38bdf8; margin-top:0; margin-bottom: 5px;">{selected_stock['name']} ({selected_stock['ticker']})</h3>
            <p style="margin-top:0; color: #94a3b8; font-size: 14px;"><b>Sector:</b> {selected_stock['sector'].replace('_', ' ').title()} | <b>Price:</b> {price_str}</p>
            <p style="font-size: 14px;"><b>Valuation Metrics:</b> PER: {selected_stock['per']:.1f} ({selected_stock['valuation_notes']}) | PBR: {selected_stock['pbr']:.2f}</p>
            <hr style="border: 0; border-top: 1px solid #334155; margin: 15px 0;" />
            <h4 style="color: #38bdf8; margin-top:0;">{t("investment_summary")}</h4>
            <p style="font-size: 14px;"><b>Decision:</b> <span style="color: {'#2ecc71' if selected_stock['decision'] == 'BUY' else '#f1c40f' if selected_stock['decision'] == 'WATCH' else '#e74c3c'}; font-weight: bold;">{selected_stock['decision']}</span> (Combined Score: {selected_stock['combined_score']:+.1f})</p>
            <p style="font-size: 14px; font-style: italic; line-height: 1.4;">"{selected_stock['rationale']}"</p>
            <hr style="border: 0; border-top: 1px solid #334155; margin: 15px 0;" />
            <h4 style="color: #38bdf8; margin-top:0; margin-bottom: 10px;">{drivers_title}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Display the contributing factors list below the card
        stock_sector = selected_stock['sector']
        sector_info = sector_scores.get(stock_sector, {"score": 0.0, "breakdown": []})
        if sector_info["breakdown"]:
            for b in sector_info["breakdown"]:
                color = "#2ecc71" if b["impact"] > 0 else "#e74c3c"
                st.markdown(f"""
                <div style="padding-left: 10px; border-left: 3px solid {color}; margin-bottom: 10px;">
                    <span style="color: {color}; font-weight: bold;">{b['impact']:+d} points</span> from <b>{b['signal']}</b><br/>
                    <span style="font-size: 12px; color: #94a3b8; font-style: italic;">{b['description']}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info(t("no_macro_triggers"))
else:
    st.info(t("no_stocks_loaded"))

# --- INVISIBLE LOGIC: Sync uploaded CSV to Real Portfolio ---
from src.portfolio import parse_portfolio_csv, evaluate_portfolio_macro, recommend_rebalancing

# Process file upload BEFORE rendering so that positions are updated instantly
if "portfolio_uploader" in st.session_state and st.session_state.portfolio_uploader is not None:
    try:
        st.session_state.portfolio_uploader.seek(0)
        portfolio_df = parse_portfolio_csv(st.session_state.portfolio_uploader)
        
        if not portfolio_df.empty:
            real_acc = st.session_state.real_portfolio
            real_acc.holdings = {}
            for _, row in portfolio_df.iterrows():
                real_acc.holdings[row["ticker"]] = {"qty": row["qty"], "cost": row["cost"]}
    except Exception as parse_err:
        pass

# --- 8. PAPER TRADING SECTION (5 SECTIONS) ---
st.markdown("---")
st.subheader(t("paper_trading_title"))
st.markdown(t("paper_trading_desc"))

from src.market_data import MarketDataClient
market_client = MarketDataClient()

def render_account_ui(acc, key_suffix, show_transaction_form=True):
    # 1. Save and Load UI (File upload & download button)
    s_col1, s_col2, s_col3 = st.columns([2, 2, 3])
    with s_col1:
        json_str = acc.to_json()
        st.download_button(
            label=t("save_json"),
            data=json_str,
            file_name=f"trance_engine_portfolio_{key_suffix.lower().replace(' ', '_')}.json",
            mime="application/json",
            key=f"dl_btn_{key_suffix}"
        )
    with s_col2:
        load_file = st.file_uploader(
            t("load_json"), 
            type=["json"], 
            key=f"ul_file_{key_suffix}",
            label_visibility="collapsed"
        )
        if load_file is not None:
            try:
                loaded_acc = PaperTradeAccount.from_json(load_file.read().decode('utf-8'))
                if key_suffix == "real_portfolio":
                    st.session_state.real_portfolio = loaded_acc
                else:
                    st.session_state.paper_accounts[key_suffix] = loaded_acc
                st.success(t("load_success"))
                st.rerun()
            except Exception as load_err:
                st.error(t("load_failed", load_err))
    with s_col3:
        if st.button(t("reset_acc"), key=f"reset_btn_{key_suffix}", use_container_width=True):
            acc.reset()
            st.success(t("reset_success"))
            st.rerun()

    # 2. Construct portfolio_df from virtual positions
    pos_data = []
    for ticker, pos in acc.holdings.items():
        pos_data.append({
            "ticker": ticker,
            "qty": pos["qty"],
            "cost": pos["cost"]
        })
        
    pos_df = pd.DataFrame(pos_data)
    
    # Evaluate virtual portfolio
    async def run_virtual_eval():
        return await evaluate_portfolio_macro(
            pos_df,
            market_client,
            evaluator,
            sector_scores
        )
        
    if not pos_df.empty:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            v_results = loop.run_until_complete(run_virtual_eval())
        finally:
            loop.close()
    else:
        v_results = {
            "holdings": [],
            "portfolio_macro_score": 0.0,
            "total_cost": 0.0,
            "total_value": 0.0,
            "total_gain_loss": 0.0,
            "total_gain_loss_percent": 0.0,
            "sector_allocation": {}
        }

    # 3. Account metrics summary
    c_val = acc.cash + v_results["total_value"]
    gain = c_val - acc.initial_balance
    gain_pct = (gain / acc.initial_balance * 100.0) if acc.initial_balance > 0 else 0.0
    
    m_cols = st.columns(5)
    m_cols[0].metric(t("cash_balance"), f"{acc.currency}{acc.cash:,.2f}" if acc.currency != "¥" else f"¥{acc.cash:,.0f}")
    m_cols[1].metric(t("stock_value"), f"{acc.currency}{v_results['total_value']:,.2f}" if acc.currency != "¥" else f"¥{v_results['total_value']:,.0f}")
    m_cols[2].metric(t("total_assets"), f"{acc.currency}{c_val:,.2f}" if acc.currency != "¥" else f"¥{c_val:,.0f}")
    gain_c = "normal" if gain >= 0 else "inverse"
    m_cols[3].metric(t("profit_loss"), f"{acc.currency}{gain:+,.2f}" if acc.currency != "¥" else f"¥{gain:+,.0f}", f"{gain_pct:+.2f}%", delta_color=gain_c)
    
    p_score = v_results["portfolio_macro_score"]
    is_en = (st.session_state.language == "en")
    p_status = ("Tailwind 🟢" if is_en else "追い風 🟢") if p_score >= 10.0 else ("Headwind 🔴" if is_en else "逆風 🔴") if p_score <= -10.0 else ("Neutral 🟡" if is_en else "中立 🟡")
    m_cols[4].metric(t("macro_score"), f"{p_score:+.2f}", p_status)

    # 4. Form for executing virtual BUY/SELL
    if show_transaction_form:
        with st.expander(t("execute_transaction")):
            t_col1, t_col2, t_col3, t_col4 = st.columns(4)
            with t_col1:
                trade_ticker = st.text_input(t("ticker_symbol"), key=f"t_ticker_{key_suffix}").strip()
            with t_col2:
                trade_side = st.selectbox(t("action"), ["BUY", "SELL"], key=f"t_side_{key_suffix}")
            with t_col3:
                trade_qty = st.number_input(t("quantity"), min_value=0.01, step=1.0, key=f"t_qty_{key_suffix}")
            with t_col4:
                manual_p = st.number_input(t("price"), min_value=0.0, step=1.0, key=f"t_price_{key_suffix}", 
                                           help=t("price_help"))

            if st.button(t("submit_trade"), key=f"t_submit_{key_suffix}", use_container_width=True):
                if not trade_ticker:
                    st.error(t("valid_ticker_error"))
                else:
                    try:
                        trade_price = manual_p
                        if trade_price == 0.0:
                            async def fetch_p():
                                return await market_client.fetch_stock_metrics(trade_ticker)
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                met = loop.run_until_complete(fetch_p())
                                trade_price = met["price"]
                            finally:
                                loop.close()
                            if trade_price == 0.0:
                                st.error(t("fetch_price_error"))
                                st.stop()
                        
                        if trade_side == "BUY":
                            acc.buy(trade_ticker, trade_qty, trade_price)
                            st.success(t("bought_success", qty=trade_qty, ticker=trade_ticker, price=trade_price, symbol=acc.currency))
                        else:
                            acc.sell(trade_ticker, trade_qty, trade_price)
                            st.success(t("sold_success", qty=trade_qty, ticker=trade_ticker, price=trade_price, symbol=acc.currency))
                        st.rerun()
                    except Exception as t_err:
                        st.error(f"Transaction failed: {t_err}")

    # 5. Position table and charts
    v_col_left, v_col_right = st.columns([3, 2])
    with v_col_left:
        st.write(f"**{t('current_positions')}**")
        if not pos_df.empty:
            v_holdings_ui = []
            for h in v_results["holdings"]:
                symbol = acc.currency
                h_val_str = f"{symbol}{h['value']:,.2f}" if symbol != "¥" else f"¥{h['value']:,.0f}"
                h_cost_str = f"{symbol}{h['cost']:,.2f}" if symbol != "¥" else f"¥{h['cost']:,.0f}"
                h_gain_str = f"{symbol}{h['gain_loss']:+,.2f}" if symbol != "¥" else f"¥{h['gain_loss']:+,.0f}"
                
                v_holdings_ui.append({
                    "Decision": h["decision"],
                    "Ticker": h["ticker"],
                    "Name": h["name"],
                    "Sector": h["sector"].replace("_", " ").title(),
                    "Weight": f"{h['weight']*100:.1f}%",
                    "Avg Cost": h_cost_str,
                    "Price": f"{symbol}{h['price']:,.2f}" if symbol != "¥" else f"¥{h['price']:,.0f}",
                    "Current Value": h_val_str,
                    "Unrealized Gain/Loss": f"{h_gain_str} ({h['gain_loss_percent']:+.2f}%)",
                    "Macro Score": f"{h['macro_score']:+.1f}"
                })
            st.dataframe(
                pd.DataFrame(v_holdings_ui).style.map(style_decision, subset=["Decision"]),
                use_container_width=True,
                hide_index=True,
                key=f"pt_positions_tbl_{key_suffix}"
            )
            
            # Rebalancing recommendations
            st.markdown("---")
            st.write(f"⚖️ **{t('rebalance_title')}**")
            recs = recommend_rebalancing(v_results, sector_scores, current_country, active_tickers_dict)
            if recs["has_recommendations"]:
                st.info(recs["summary"])
                for action in recs["actions"]:
                    st.markdown(f"* {action['description']}")
            else:
                st.success(recs["summary"])
        else:
            if key_suffix == "real_portfolio":
                st.info(t("no_positions_real"))
            else:
                st.info(t("no_positions_paper"))
            
    with v_col_right:
        st.write(f"**{t('risk_title')}**")
        if not pos_df.empty:
            v_headwind_holdings = [h for h in v_results["holdings"] if h["macro_score"] <= -10.0]
            if v_headwind_holdings:
                st.warning(t("risk_detected", count=len(v_headwind_holdings)))
                for h in v_headwind_holdings:
                    st.markdown(f"""
                    * **{h['name']} ({h['ticker']})**: Macro Score: `{h['macro_score']:+.1f}`
                      *Rationale:* {h['rationale']}
                    """)
            else:
                st.success(t("no_risk"))
        else:
            st.info(t("empty_account"))

        st.write(f"**{t('tx_history')}**")
        if acc.history:
            hist_ui = []
            for h in reversed(acc.history):
                symbol = acc.currency
                hist_ui.append({
                    "Date": h["date"].split()[0] if " " in h["date"] else h["date"],
                    "Ticker": h["ticker"],
                    "Type": h["side"],
                    "Qty": f"{h['qty']:.1f}" if h['qty'] % 1 != 0 else f"{h['qty']:.0f}",
                    "Price": f"{symbol}{h['price']:,.2f}" if symbol != "¥" else f"¥{h['price']:,.0f}",
                    "Total": f"{symbol}{h['total']:,.2f}" if symbol != "¥" else f"¥{h['total']:,.0f}"
                })
            st.dataframe(
                pd.DataFrame(hist_ui),
                use_container_width=True,
                hide_index=True,
                key=f"pt_history_tbl_{key_suffix}"
            )
        else:
            st.write(t("no_tx_logs"))

# Setup tabs for 5 accounts
account_keys = ["Macro Tailwind Focus", "Defensive & Income", "Aggressive Growth", "Long-Term Value", "Sandbox"]
pt_tabs = st.tabs([st.session_state.paper_accounts[k].name for k in account_keys])

for tab_idx, k in enumerate(account_keys):
    with pt_tabs[tab_idx]:
        acc = st.session_state.paper_accounts[k]
        render_account_ui(acc, k, show_transaction_form=True)

# --- 9. MY PORTFOLIO ANALYSIS SECTION (ACTUAL LAST SECTION) ---
st.markdown("---")
st.subheader(t("portfolio_analyzer_title"))
st.markdown(t("portfolio_analyzer_desc"))
st.markdown(t("privacy_notice"))

# Download template CSV
st.info(t("sample_info"))
sample_csv = "ticker,qty,cost\nAAPL,10,150.0\n7203.T,100,2000.0\n8306.T,200,1000.0\nMSFT,5,350.0\n"
st.download_button(
    label=t("dl_sample_btn"),
    data=sample_csv,
    file_name="sample_portfolio.csv",
    mime="text/csv",
    key="dl_sample_portfolio_csv"
)

uploaded_file = st.file_uploader(
    t("upload_label"), 
    type=["csv", "txt"],
    key="portfolio_uploader"
)

if uploaded_file is not None:
    st.success(t("import_success"))

# Display the Portfolio analysis report here!
real_portfolio_acc = st.session_state.real_portfolio
render_account_ui(real_portfolio_acc, "real_portfolio", show_transaction_form=True)
