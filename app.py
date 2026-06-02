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
from src.db import init_db, seed_demo_data, get_connection, get_user_by_email

# Initialize SQLite database and seed data on startup
init_db()
seed_demo_data()

# Ensure user is in session state (default to demo user)
if "user" not in st.session_state:
    st.session_state.user = get_user_by_email("demo@example.com")


# Initialize language in session state
if "language" not in st.session_state:
    st.session_state.language = "en"

# Initialize tab and page navigation from query parameters if present
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "screener"

if "page" in st.query_params:
    page_param = st.query_params["page"].lower()
    if page_param in ["readme", "docs", "blueprint"]:
        st.session_state.active_tab = "docs"
    elif page_param == "contact":
        st.session_state.active_tab = "contact"
    else:
        st.session_state.active_tab = "screener"
        route_map = {
            "screener": t("screener_tab"),
            "portfolio": t("portfolios_tab"),
            "vault": t("portfolios_tab"),
            "timeline": t("timeline_tab"),
            "alerts": t("alerts_tab"),
            "verification": t("verification_tab"),
        }
        target_page = route_map.get(page_param)
        if target_page and ("nav_page" not in st.session_state or st.session_state.nav_page != target_page):
            st.session_state.nav_page = target_page

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

# Custom styling for premium gold-accented navigation bar (帯)
st.markdown("""
<style>
    .premium-nav-band {
        background-color: #141410;
        border: 1px solid rgba(200, 165, 90, 0.25);
        border-radius: 8px;
        padding: 8px;
        margin-bottom: 30px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }
    div[data-testid="stColumn"] button {
        border-radius: 4px !important;
        font-weight: bold !important;
        letter-spacing: 0.05em !important;
    }
</style>
""", unsafe_allow_html=True)

with st.container():
    # Top navigation layout
    cols_nav = st.columns([1, 3, 3, 3, 1])
    is_jp = (st.session_state.language == "jp")
    
    with cols_nav[1]:
        is_active = (st.session_state.active_tab == "screener")
        btn_label = "🚀 実行環境 (Screener Hub)" if is_jp else "🚀 Screener Hub"
        if st.button(
            btn_label, 
            key="btn_nav_screener", 
            use_container_width=True, 
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_tab = "screener"
            st.session_state.nav_page = t("screener_tab")
            st.rerun()
            
    with cols_nav[2]:
        is_active = (st.session_state.active_tab == "docs")
        btn_label = "🏛️ 設計図・仕様書 (Specs)" if is_jp else "🏛️ Obra Specs & Docs"
        if st.button(
            btn_label, 
            key="btn_nav_docs", 
            use_container_width=True, 
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_tab = "docs"
            st.rerun()
            
    with cols_nav[3]:
        is_active = (st.session_state.active_tab == "contact")
        btn_label = "✉️ お問い合わせ (Contact)" if is_jp else "✉️ Contact Support"
        if st.button(
            btn_label, 
            key="btn_nav_contact", 
            use_container_width=True, 
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_tab = "contact"
            st.rerun()

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


def render_verification_board_ui():
    from src.tracker import PredictionTracker
    db_tracker = PredictionTracker()
    
    st.subheader(t("ver_title"))
    st.markdown(t("ver_desc"))
    st.markdown("---")
    
    # 1. Update verification prices button
    col_btn, _ = st.columns([3, 4])
    with col_btn:
        if st.button(t("update_prices_btn"), use_container_width=True):
            with st.spinner("Fetching current prices from yfinance to update database..."):
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    updated, errors = loop.run_until_complete(db_tracker.update_prices())
                    st.success(f"Verification data updated: {updated} records updated, {errors} errors.")
                    st.rerun()
                finally:
                    loop.close()
                    
    st.markdown("") # Spacing

    # 2. KPI Cards
    kpis = db_tracker.calculate_kpis()
    k_cols = st.columns(4)
    k_cols[0].metric(t("overall_hit_rate"), f"{kpis['overall_hit_rate']:.1f}%")
    k_cols[1].metric(t("buy_win_rate"), f"{kpis['buy_hit_rate']:.1f}%", f"{t('avg_return')}: {kpis['buy_avg_return']:+.2f}%")
    k_cols[2].metric(t("avoid_win_rate"), f"{kpis['avoid_hit_rate']:.1f}%", f"{t('avg_return')}: {kpis['avoid_avg_return']:+.2f}%")
    k_cols[3].metric(t("total_predictions"), f"{kpis['total_tracked']}")
    
    st.markdown("---")

    # 3. Filter dropdowns
    f_col1, f_col2, _ = st.columns([3, 3, 4])
    with f_col1:
        dec_filter = st.selectbox(t("decision_filter"), ["All", "BUY", "WATCH", "AVOID"])
    with f_col2:
        stat_filter = st.selectbox(t("status_filter"), ["All", "Hit", "Miss", "Pending"])
        
    st.markdown("") # Spacing

    # 4. History Table
    history = db_tracker.get_history(decision_filter=dec_filter, status_filter=stat_filter)
    if history:
        ui_rows = []
        for item in history:
            status_val = item["hit_status"]
            status_lbl = t("status_hit") if status_val == "Hit" else t("status_miss") if status_val == "Miss" else t("status_pending")
            
            ui_rows.append({
                "Date": item["prediction_date"],
                "Ticker": item["ticker"],
                "Name": item["name"],
                "Decision": item["predicted_decision"],
                "Start Price": item["start_price"],
                "Current Price": item["current_price"] if item["current_price"] is not None else item["start_price"],
                "Return": f"{item['return_pct']:+.2f}%",
                "Status": status_lbl,
                "Macro Score": item["macro_score"],
                "Valuation Score": item["valuation_score"],
                "Combined Score": item["combined_score"]
            })
        st.dataframe(
            pd.DataFrame(ui_rows).style.map(style_decision, subset=["Decision"]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No prediction history matches the active filters.")


def render_readme_ui():
    import pathlib
    is_jp = (st.session_state.language == "jp")
    
    st.markdown("""
    <style>
        .title-text {
            background: linear-gradient(135deg, #c8a55a, #d4b06a);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-family: 'Cormorant Garamond', serif;
            font-weight: 300;
            font-size: 2.2rem;
            letter-spacing: 0.08em;
            margin-bottom: 0.2rem;
        }
        .subtitle-text {
            color: #a09888;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            letter-spacing: 0.15em;
            margin-bottom: 2rem;
            text-transform: uppercase;
        }
        .blueprint-section-title {
            font-family: 'Cormorant Garamond', serif;
            font-size: 1.8rem;
            color: #e8e0d0;
            border-bottom: 1px solid rgba(200, 165, 90, 0.15);
            padding-bottom: 0.5rem;
            margin-top: 2rem;
            margin-bottom: 1.2rem;
        }
        .blueprint-section-title em {
            font-family: 'Instrument Serif', serif;
            font-style: italic;
            color: #c8a55a;
        }
        .accent-card {
            background-color: #141410;
            border: 1px solid rgba(200, 165, 90, 0.12);
            border-left: 4px solid #c8a55a;
            padding: 1.5rem;
            border-radius: 4px;
            margin-bottom: 1.5rem;
        }
        .manifesto-text {
            font-family: 'Instrument Serif', serif;
            font-style: italic;
            font-size: 1.35rem;
            line-height: 1.7;
            color: #a09888;
        }
        .law-card {
            background-color: #141410;
            border: 1px solid rgba(200, 165, 90, 0.06);
            padding: 1rem;
            border-radius: 4px;
            margin-bottom: 1rem;
        }
        .law-num {
            font-family: 'Cormorant Garamond', serif;
            font-size: 1.5rem;
            color: #c8a55a;
            font-weight: bold;
            margin-bottom: 0.2rem;
        }
        .law-title {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
            color: #e8e0d0;
            margin-bottom: 0.4rem;
        }
        .law-desc {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: #a09888;
        }
        .link-banner {
            background: linear-gradient(90deg, rgba(200, 165, 90, 0.15), rgba(20, 20, 16, 0.9));
            border: 1px solid #c8a55a;
            padding: 1rem;
            border-radius: 6px;
            text-align: center;
            margin: 2rem 0;
        }
        .link-banner a {
            color: #e8e0d0 !important;
            font-weight: bold;
            text-decoration: underline;
        }
        .logic-header {
            color: #d4b06a;
            font-family: 'Cormorant Garamond', serif;
            font-weight: 700;
            border-bottom: 1px solid rgba(200, 165, 90, 0.15);
            padding-bottom: 0.5rem;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="title-text">🏛️ Obra — The Blueprint & Docs</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle-text">Technical Specifications, User Manual & Mathematical Logic</div>', unsafe_allow_html=True)

    # Custom Domain Branding Link
    if is_jp:
        st.markdown("""
        <div class="link-banner">
            🚀 <strong>本システムのオフィシャルドメイン:</strong> 
            <a href="https://macro.ezora.net" target="_blank">macro.ezora.net</a> から安全にアクセスいただけます。
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="link-banner">
            🚀 <strong>Official Domain for this System:</strong> 
            <a href="https://macro.ezora.net" target="_blank">macro.ezora.net</a> - Secure access.
        </div>
        """, unsafe_allow_html=True)

    # Tabs
    tab_blueprint, tab_howto, tab_logic = st.tabs([
        "🏛️ 1. Obra Blueprint (設計図)" if is_jp else "🏛️ 1. Obra Blueprint",
        "📖 2. 使い方ガイド (HOWTO)" if is_jp else "📖 2. User Guide (HOWTO)",
        "📊 3. クオンツ判定ロジック (Logic)" if is_jp else "📊 3. Quantitative Logic (Logic)"
    ])

    # ----------------- TAB 1: BLUEPRINT -----------------
    with tab_blueprint:
        st.markdown('<div class="blueprint-section-title">Introduction — <em>Obra</em></div>', unsafe_allow_html=True)
        st.markdown("""
        *From the Spanish — opus, work, masterpiece.*  
        私たちはソフトウェアの「大聖堂（Cathedral）」を作っています。ただの製品ではありません。ひとつの壮大な帝国です。
        """)

        st.markdown('<div class="blueprint-section-title">I — The Problem — <em>構造的な破壊</em></div>', unsafe_allow_html=True)
        st.markdown('<div class="accent-card"><div class="manifesto-text">'
                    'ソフトウェア業界は、構造的に崩壊しています。<br>'
                    '30年間、同じパターンが繰り返されてきました。大企業はツールを作り、あなたのデータを囲い込み、'
                    'あなた自身の成果物にアクセスするためだけに毎月のサブスクリプションを請求し、それを「イノベーション」と呼びます。'
                    '</div></div>', unsafe_allow_html=True)
        
        st.markdown("""
        * **サブスク疲れ (Subscription fatigue)**: あなたは自分自身のものにならないソフトウェアに対し、永遠にお金を払い続けます。支払いを止めた瞬間に、あなたのワークフローは死にます。
        * **クラウドへのロックイン (Cloud lock-in)**: あなたのデータは他人のサーバーに存在します。あなたはそのデータを所有していません。ただアクセス権をレンタルしているだけです。
        * **奪われたデータ主権 (Data sovereignty, surrendered)**: すべてのキーストローク、すべてのクエリ、すべての思考が、設計段階から他社に収集され、分析され、マネタイズされています。
        * **中央集権化されたAI (AI, centralized)**: 巨大企業がAIモデルを所有し、アクセスを制御し、条件を設定します。あなたは彼らの「知性」の中のただのテナント（店借人）に過ぎません。
        """)

        st.markdown('<div class="blueprint-section-title">II — Four Laws — <em>4つの非交渉的鉄則</em></div>', unsafe_allow_html=True)
        
        # 4 Laws grid
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            <div class="law-card">
                <div class="law-num">I</div>
                <div class="law-title">Data stays with the user.</div>
                <div class="law-desc">ローカルファースト。あなたのPC、あなたのファイル、あなたの主権。</div>
            </div>
            <div class="law-card">
                <div class="law-num">II</div>
                <div class="law-title">Formats are open.</div>
                <div class="law-desc">ベンダーロックインの完全な排除。公開仕様書により、いつでもシステムから離脱可能。</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="law-card">
                <div class="law-num">III</div>
                <div class="law-title">Buy once. Own forever.</div>
                <div class="law-desc">サブスクの対極。3年間の製品保証 ＋ 永続無料アップデート。</div>
            </div>
            <div class="law-card">
                <div class="law-num">IV</div>
                <div class="law-title">AI is not owned — you bring your own.</div>
                <div class="law-desc">あなたのLLM。あなたの選択。ローカルでもクラウドでも、あなたの好きな利用規約で。</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div class="blueprint-section-title">III — Three Phases — <em>3つのロードマップ</em></div>', unsafe_allow_html=True)
        st.markdown("""
        * **Phase 1: Office 2.0 (The Software Suite) [開発中]**
          * クラウド生産性スタックに置き換わる7つのAIネイティブツール。
        * **Phase 2: Enterprise (Oracle 2.0) [計画中]**
          * 企業のインフラ基盤を再構築するセキュリティ・システム。
        * **Phase 3: Hardware (Apple 2.0) [構想]**
          * 垂直統合の実現。OSから独自のハードウェアデバイスを自社保有。
        """)

        st.markdown('<div class="blueprint-section-title">IV — Seven Tools — <em>7つのエコシステム</em></div>', unsafe_allow_html=True)
        
        # Showcase 7 Tools
        t_cols = st.columns(2)
        with t_cols[0]:
            st.write("📁 **DaviCore (The Hub)**")
            st.caption("LLMアグリゲーター。中央ベクトルデータベース。ローカル監査エンジン。データを囲い込むことなくすべてを接続する、システムの核となる脳。")
            
            st.write("🎥 **EZRA (The Output)**")
            st.caption("動画・ナレーション生成エンジン。GPU独立設計。独自のSaaSとして、あるいはローカルマシンで動作可能。")
            
            st.write("🎨 **Ezora (The Input)**")
            st.caption("思考のキャンバスから完成文書へ。手書きのアイデアを、AIが他人に提出できるレベルの洗練されたPDFやスライドに変換。")
            
            st.write("🧠 **Elix (The Cognitive OS)**")
            st.caption("思考の可視化キャンバス。あなたが気づかなかったデータやインサイトのパターンを抽出し、潜在的な関心を浮き彫りにする。")
        
        with t_cols[1]:
            st.write("🪨 **Lithex (The Knowledge Base)**")
            st.caption("スクラップとメモの蓄積。キャプチャしたすべての情報が接続された知識体系となり、自動タグ付けと検索を可能にする。")
            
            st.write("⏳ **Viox (The Execution)**")
            st.caption("バイオ同期タスク管理。あなたのスケジュールをあなたの身体（エネルギー、集中力、体内リズム）に自動で適合させる。")
            
            st.write("⚖️ **RegLex (The Regulation)**")
            st.caption("規制および行政処理プロセスの自動化。あなたに代わって複雑な官僚主義的手続きをナビゲートする。")

        st.markdown('<div class="blueprint-section-title">V — The Builder — <em>指揮官とエージェント</em></div>', unsafe_allow_html=True)
        st.markdown("""
        * **一人の指揮官とAIエージェントの軍隊**:
          * 開発者は一般的なエンジニアではありません。ソフトウェアのあるべき姿を追求し、大企業の逆を行く現状を見続けてきた「30年のテクノロジーリーダーシップ経験を持つ元CIO」。
          * コードを自ら一行ずつ書くのではなく、一人の人間のビジョンの下、並行して自律動作する「4つのAIエージェントシステム」をオーケストレーション（指揮・統率）して構築されています。
          * **バルセロナから**: ガウディの街。大聖堂が、その創作者たちよりも長生きするように設計される場所から、このソフトウェアは生まれました。
        """)

    # ----------------- TAB 2: HOWTO GUIDE -----------------
    with tab_howto:
        if is_jp:
            st.markdown('<h3 class="logic-header">保有ポートフォリオ診断 ＆ ツール操作手順</h3>', unsafe_allow_html=True)
            howto_file = "HOWTO.md"
        else:
            st.markdown('<h3 class="logic-header">Brokerage Portfolio Diagnostics & System Operations</h3>', unsafe_allow_html=True)
            howto_file = "HOWTO_EN.md"
            
        current_dir = pathlib.Path(__file__).parent
        howto_path = current_dir / howto_file
        if howto_path.exists():
            with open(howto_path, "r", encoding="utf-8") as f:
                howto_content = f.read()
            st.markdown(howto_content)
        else:
            st.error(f"Required guide file ({howto_file}) not found.")

    # ----------------- TAB 3: QUANT LOGIC -----------------
    with tab_logic:
        if is_jp:
            st.markdown('<h3 class="logic-header">システムアーキテクチャ & パイプライン</h3>', unsafe_allow_html=True)
            st.write(
                "本システムは、リアルタイムのマクロ時系列データ（経済環境）と個別銘柄の財務指標（ミクロデータ）を融合させて投資判断を導き出す、「トップダウン・アプローチ」を採用したクオンツ評価エンジンです。"
            )
            st.info("""
            **🔄 処理パイプラインの4つのステップ:**
            1. **データ取得 (Data Ingestion)**: FRED APIおよびyfinanceからマクロ時系列データと個別財務データを取得・クレンジング。
            2. **シグナル検出 (Event Detector)**: 移動平均線（SMA）や前月比、30日変化率を用いて、現在のマクロ指標から12種のエコノミックイベントを検出し、その深刻度（Severity）を決定。
            3. **セクタースコアリング (Rule Engine)**: 検出されたイベントを、静的な「産業別インパクトマトリクス」へ通し、17セクターに対する累積影響度スコアを算出・正規化。
            4. **銘柄総合スクリーニング (Stock Evaluator)**: 各国の市場特性に適合させたバリュエーションモデル（PER/PBR評価）を適用し、マクロ適合度と統合して最終意思決定（BUY / WATCH / AVOID）を決定。
            """)
        else:
            st.markdown('<h3 class="logic-header">System Architecture & Processing Pipeline</h3>', unsafe_allow_html=True)
            st.write(
                "This platform implements a **top-down quantitative model** that dynamically integrates macro-economic variables (FRED indicators) with micro-level equity financials to formulate robust asset allocation advice."
            )
            st.info("""
            **🔄 4-Stage Core Processing Pipeline:**
            1. **Data Ingestion**: Programmatically aggregates and cleans macro-economic series from FRED and stock quotes from Yahoo Finance.
            2. **Event Detector**: Analyzes monthly rate of change, 30-day volatility, and deviation from 50-day Simple Moving Averages (SMA) to identify 12 discrete economic shocks and compute their Severity.
            3. **Rule Engine**: Maps active events to a static 'Industry Impact Matrix' to calculate weighted, normalized momentum scores across 17 distinct sectors.
            4. **Stock Evaluator**: Combines normalized sector momentum with dynamic local market valuation filters (PER/PBR thresholds) to issue clear trading ratings (`BUY` / `WATCH` / `AVOID`).
            """)
            
        # Text flow diagram
        st.markdown("```")
        if is_jp:
            st.markdown(" [マクロデータ (FRED)]                [市場データ (yfinance)]")
            st.markdown("         │                                     │")
            st.markdown("         ▼ (1. Ingestion)                      ▼ (1. Ingestion)")
            st.markdown(" [時系列データクレンジング]              [PER, PBR, 株価データ]")
            st.markdown("         │                                     │")
            st.markdown("         ▼ (2. EventDetector)                  │")
            st.markdown(" [マクロイベント検出 / Severity判定]            │")
            st.markdown("         │                                     │")
            st.markdown("         ▼ (3. RuleEngine)                     │")
            st.markdown(" [17セクター別マクロ影響度スコア]               │")
            st.markdown("         │                                     │")
            st.markdown("         └───────────────► ─── ◄───────────────┘")
            st.markdown("                           │ (4. StockEvaluator)")
            st.markdown("                           ▼")
            st.markdown("              [総合スコア (Combined Score)]")
            st.markdown("                           │")
            st.markdown("                           ▼")
            st.markdown("              [投資判断 (BUY / WATCH / AVOID)]")
        else:
            st.markdown(" [Macro Data (FRED)]                  [Market Data (yfinance)]")
            st.markdown("         │                                     │")
            st.markdown("         ▼ (1. Ingestion)                      ▼ (1. Ingestion)")
            st.markdown(" [Time-Series Data Cleansing]             [PER, PBR, Price Data]")
            st.markdown("         │                                     │")
            st.markdown("         ▼ (2. EventDetector)                  │")
            st.markdown(" [Macro Event Detection & Severity]            │")
            st.markdown("         │                                     │")
            st.markdown("         ▼ (3. RuleEngine)                     │")
            st.markdown(" [Macro Impact Scores (17 Sectors)]            │")
            st.markdown("         │                                     │")
            st.markdown("         └───────────────► ─── ◄───────────────┘")
            st.markdown("                           │ (4. StockEvaluator)")
            st.markdown("                           ▼")
            st.markdown("              [Combined Score]")
            st.markdown("                           │")
            st.markdown("                           ▼")
            st.markdown("              [Investment Decision (BUY / WATCH / AVOID)]")
        st.markdown("```")

        if is_jp:
            st.markdown('<h3 class="logic-header">12のマクロイベント検出ロジック</h3>', unsafe_allow_html=True)
            st.markdown("""
            | 検出シグナル名 | 検出ロジック・閾値の計算 | Severity (重要度) の判定基準 |
            | :--- | :--- | :--- |
            | **金利上昇 (RATE_RISING)** | 10年国債利回りが50日単純移動平均(SMA)を上回っている状態 | 利回りと50日SMAの乖離幅に応じて **1 〜 3** |
            | **金利下落 (RATE_FALLING)** | 10年国債利回りが50日SMAを下回っている状態 | 50日SMAと利回りの乖離幅に応じて **1 〜 3** |
            | **高金利環境 (HIGH_RATE_ENVIRONMENT)** | 10年債利回りが長期警戒閾値（4.5%）を突破しているか | 利回りそのものの絶対値に応じて決定 |
            | **インフレ加速 (INFLATION_ACCELERATING)** | 前年比(YoY)消費者物価指数(CPI)が上昇、または前月比(MoM)年率換算で 4.0% 以上 | YoYインフレ率が 3%以上で **Severity 2**, 5%以上で **Severity 3** |
            | **インフレ減速 (INFLATION_DECELERATING)**| YoY CPIが低下傾向、または前月比年率換算が 2.0% 未満 | YoYインフレ率が 1.5%以下で **Severity 1**, 1%以下で **Severity 2**, マイナス（デフレ）で **Severity 3** |
            | **原油ショック (ENERGY_SHOCK / OIL_SPIKE)** | WTI原油価格の30日変化率が大きく上昇している状態 | 30日変化率が +10%で **1**, +20%で **2**, +40%で **3** |
            | **原油急落 (ENERGY_DECLINE / OIL_CRASH)** | WTI原油価格の30日変化率が大きく下落している状態 | 30日変化率が -10%で **1**, -20%で **2**, -40%で **3** |
            | **通貨減価 / 自国通貨安 (YEN_DEPRECIATING)** | 対ドル為替レート（USD/JPY等）が50日SMAを上回り、30日変化率がマイナス（自国通貨安） | 30日変化率が 2%で **1**, 4%で **2**, 6%で **3** |
            | **通貨増価 / 自国通貨高 (YEN_APPRECIATING)** | 対ドル為替レートが50日SMAを下回り、30日変化率がプラス（自国通貨高） | 30日変化率が 2%で **1**, 4%で **2**, 6%で **3** |
            | **景気拡大 (BUSINESS_EXPANSION)** | ビジネス信頼感指数（PMIや短観）が好不況の閾値（50または100）を上回っている | 閾値から上方への乖離率に応じて **1 〜 3** |
            | **景気後退 (BUSINESS_CONTRACTION)** | ビジネス信頼感指数（PMIや短観）が好不況の閾値（50または100）を下回っている | 閾値から下方への乖離率に応じて **1 〜 3** |
            | **逆イールド (YIELD_CURVE_INVERSION)** | 10年国債利回り － 政策金利 ≦ 0% （イールドカーブ逆転） | 逆イールド検出時に一律 **Severity 2** （景気後退の強力な先行指標） |
            """)
        else:
            st.markdown('<h3 class="logic-header">12 Macro Economic Event Detection Rules</h3>', unsafe_allow_html=True)
            st.markdown("""
            | Signal Name | Detection Logic & Metrics Thresholds | Severity Level Assessment Criteria |
            | :--- | :--- | :--- |
            | **RATE_RISING** (Interest rate spike) | 10-year government bond yield sits above its 50-day Simple Moving Average (SMA). | Severity ranges **1 to 3** based on percentage-point gap over the 50-day SMA. |
            | **RATE_FALLING** (Interest rate drop) | 10-year government bond yield sits below its 50-day SMA. | Severity ranges **1 to 3** based on negative gap under the 50-day SMA. |
            | **HIGH_RATE_ENVIRONMENT** | 10-year yield breaks standard baseline defensive threshold (4.5%). | Automatically triggered based on absolute height of the yield. |
            | **INFLATION_ACCELERATING** | Year-over-Year (YoY) Consumer Price Index (CPI) increases, or annualized MoM rate >= 4.0%. | **Severity 2** when YoY CPI >= 3.0%, **Severity 3** when YoY CPI >= 5.0%. |
            | **INFLATION_DECELERATING** | YoY CPI slows or annualized MoM rate falls under 2.0% baseline. | **Severity 1** if <=1.5%, **Severity 2** if <=1.0%, **Severity 3** if negative (deflation). |
            | **ENERGY_SHOCK / OIL_SPIKE** | 30-day rate of change in WTI crude oil futures rises significantly. | **Severity 1** at +10% gain, **Severity 2** at +20% gain, **Severity 3** at +40% gain. |
            | **ENERGY_DECLINE / OIL_CRASH** | 30-day rate of change in WTI crude oil futures falls significantly. | **Severity 1** at -10% drop, **Severity 2** at -20% drop, **Severity 3** at -40% drop. |
            | **CURRENCY_WEAKENING** (Weakening) | FX rate (e.g. USD/JPY) sits above 50-day SMA, 30-day change is negative. | **Severity 1** at 2% drop, **Severity 2** at 4% drop, **Severity 3** at 6% drop. |
            | **CURRENCY_STRENGTHENING** (Strengthening) | FX rate sits below 50-day SMA, 30-day change is positive. | **Severity 1** at 2% gain, **Severity 2** at 4% gain, **Severity 3** at 6% gain. |
            | **BUSINESS_EXPANSION** | Business sentiment index (PMI or Tankan) sits above standard neutral value (50 or 100). | Severity **1 to 3** scaled based on the size of the upward deviation. |
            | **BUSINESS_CONTRACTION** | Business sentiment index (PMI or Tankan) sits below standard neutral value (50 or 100). | Severity **1 to 3** scaled based on the size of the downward deviation. |
            | **YIELD_CURVE_INVERSION** | 10-Year yield minus Central Bank policy rate <= 0.0% (Inversion detected). | Flat **Severity 2** (highly predictive leading indicator of recessions). |
            """)

        if is_jp:
            st.markdown('<h3 class="logic-header">計算ロジックとバリュエーション評価</h3>', unsafe_allow_html=True)
            st.latex(r"Raw\_Score_{Sector} = \sum_{Event} \left( Base\_Weight_{Event, Sector} \times Severity_{Event} \right)")
            st.latex(r"Normalized\_Score_{Sector} = \frac{Raw\_Score_{Sector}}{\max \left( |Raw\_Score_{All\_Sectors}|, 1.0 \right)}")
            
            st.markdown("""
            #### 国別バリュエーション（PER / PBR）の評価基準 (日本 vs 米国/欧州 vs 中国)
            * **日本 (JP) 基準**: PER ≦ 8.0 (+30点) / ≦ 13.0 (+15点) / ≦ 20.0 (0点) / ＞ 20.0 (-15点). PBR ≦ 0.7 (+20点) / ≦ 1.0 (+10点) / ≦ 1.8 (0点).
            * **米国 (US) 基準**: PER ≦ 14.0 (+30点) / ≦ 22.0 (+15点) / ≦ 30.0 (0点) / ＞ 30.0 (-15点). PBR ≦ 1.5 (+20点) / ≦ 3.0 (+10点) / ≦ 5.5 (0点).
            * **中国 (CN) 基準**: PER ≦ 10.0 (+30点) / ≦ 16.0 (+15点) / ≦ 24.0 (0点) / ＞ 24.0 (-15点). PBR ≦ 1.0 (+20点) / ≦ 1.8 (+10点) / ≦ 3.2 (0点).
            """)

            st.markdown("""
            #### 投資判断ルール
            * **BUY**: マクロ影響度スコア ≧ 15 かつ バリュエーションスコア ≧ 10 (かつ PER > 0)
            * **AVOID**: マクロ影響度スコア ≦ -20、または バリュエーションスコア ≦ -25、または 赤字、または 各国の過剰高PER値（日40 / 中48 / 米60超）
            * **WATCH**: 上記に当てはまらない中立・監視銘柄
            """)
        else:
            st.markdown('<h3 class="logic-header">Scoring Formulation & Valuation Metrics</h3>', unsafe_allow_html=True)
            st.latex(r"Raw\_Score_{Sector} = \sum_{Event} \left( Base\_Weight_{Event, Sector} \times Severity_{Event} \right)")
            st.latex(r"Normalized\_Score_{Sector} = \frac{Raw\_Score_{Sector}}{\max \left( |Raw\_Score_{All\_Sectors}|, 1.0 \right)}")
            
            st.markdown("""
            #### Valuation Filters by Country/Region (PER / PBR) (Japan vs. US/EU vs. China)
            * **Japan (JP) Rules**: PER <= 8.0 (+30 pts) / <= 13.0 (+15 pts) / <= 20.0 (0 pts) / > 20.0 (-15 pts). PBR <= 0.7 (+20 pts) / <= 1.0 (+10 pts) / <= 1.8 (0 pts).
            * **United States (US) Rules**: PER <= 14.0 (+30 pts) / <= 22.0 (+15 pts) / <= 30.0 (0 pts) / > 30.0 (-15 pts). PBR <= 1.5 (+20 pts) / <= 3.0 (+10 pts) / <= 5.5 (0 pts).
            * **China (CN) Rules**: PER <= 10.0 (+30 pts) / <= 16.0 (+15 pts) / <= 24.0 (0 pts) / > 24.0 (-15 pts). PBR <= 1.0 (+20 pts) / <= 1.8 (+10 pts) / <= 3.2 (0 pts).
            """)

            st.markdown("""
            #### Final Investment Recommendation Matrix
            * **BUY**: Macro alignment score >= 15 AND Valuation score >= 10 (and PER > 0)
            * **AVOID**: Macro score <= -20 OR Valuation score <= -25 OR PER <= 0 OR PER exceeding limit (JP 40 / CN 48 / US 60)
            * **WATCH**: All other situations (default)
            """)
            


# ==========================================
# PRO TIER CUSTOM SCREENS (PORTFOLIOS VAULT, TIMELINE, ALERTS)
# ==========================================

def render_portfolios_vault_ui():
    import sqlite3
    import pandas as pd
    import asyncio
    from src.db import (
        get_user_portfolios, get_portfolio_holdings, create_portfolio, 
        delete_portfolio, save_holdings, get_notification_settings
    )
    from src.portfolio import parse_portfolio_csv, evaluate_portfolio_macro, recommend_rebalancing
    from src.evaluator import StockEvaluator
    from src.engine import RuleEngine
    from src.market_data import MarketDataClient
    
    st.subheader(t("portfolios_tab"))
    user = st.session_state.user
    user_id = user["id"]
    is_jp = (st.session_state.language == "jp")
    
    # 1. Fetch User Portfolios
    portfolios = get_user_portfolios(user_id)
    
    # 2. Portfolio Creation Section
    with st.expander("➕ Create New Portfolio or Upload CSV" if not is_jp else "➕ 新規ポートフォリオの作成・CSVのアップロード"):
        real_ports_count = sum(1 for p in portfolios if p["is_virtual"] == 0)
        
        if user["plan"] != "Pro" and real_ports_count >= 1:
            st.warning("⚠️ **Active Monitoring Limit**\n\nManual verification mode allows saving **1 portfolio**. Please enable Active Monitoring in the sidebar settings to register unlimited portfolios.")
            allow_create = False
        else:
            allow_create = True
            
        p_name = st.text_input("Portfolio Name (e.g. My Retirement, Sandbox)" if not is_jp else "ポートフォリオ名 (例: 退職金運用, 成長株Sandbox)")
        p_type = st.radio("Account Type" if not is_jp else "口座タイプ", ["Real Portfolio (Upload CSV)" if not is_jp else "実保有ポートフォリオ (CSVアップロード)", "Virtual Account (Paper Trading)" if not is_jp else "仮想口座 (ペーパートレード)"], index=0)
        
        uploaded_file = None
        if p_type.startswith("Real") or p_type.startswith("実保有"):
            uploaded_file = st.file_uploader(t("upload_label"), type=["csv"], key="vault_csv_uploader")
            st.markdown(t("privacy_notice"))
            
        if st.button("Create Portfolio" if not is_jp else "ポートフォリオ作成", disabled=not allow_create):
            if not p_name:
                st.error("Please enter a portfolio name." if not is_jp else "ポートフォリオ名を入力してください。")
            else:
                is_virt = 1 if (p_type.startswith("Virtual") or p_type.startswith("仮想")) else 0
                port_id = create_portfolio(user_id, p_name, is_virtual=is_virt)
                if port_id:
                    if is_virt == 0 and uploaded_file is not None:
                        try:
                            csv_content = uploaded_file.read().decode("utf-8")
                            holdings = parse_portfolio_csv(csv_content)
                            save_holdings(port_id, holdings)
                            st.success(t("import_success"))
                        except Exception as csv_err:
                            st.error(f"Failed to parse CSV: {csv_err}" if not is_jp else f"CSVのパースに失敗しました: {csv_err}")
                    st.success(f"Portfolio '{p_name}' created successfully!" if not is_jp else f"ポートフォリオ「{p_name}」が作成されました！")
                    st.rerun()

    # 3. Portfolio Selector
    if not portfolios:
        st.info("No portfolios found. Please create one above." if not is_jp else "保存されたポートフォリオはありません。上記から作成してください。")
        return
        
    p_options = {p["id"]: f"{p['name']} ({'Paper Trading' if p['is_virtual'] == 1 else 'Real Holdings'})" for p in portfolios}
    selected_p_id = st.selectbox("Select Portfolio to Inspect" if not is_jp else "表示するポートフォリオの選択", options=list(p_options.keys()), format_func=lambda x: p_options[x])
    
    selected_portfolio = next(p for p in portfolios if p["id"] == selected_p_id)
    is_virtual = selected_portfolio["is_virtual"] == 1
    
    # Recalculate Now and Delete Buttons Row
    col_recalc, col_del, _ = st.columns([2, 2, 6])
    
    market_client = MarketDataClient()
    evaluator = StockEvaluator()
    rule_engine = RuleEngine()
    
    # Run Recalculation
    async def run_eval():
        db_holdings = get_portfolio_holdings(selected_p_id)
        if not db_holdings:
            return {
                "holdings": [],
                "portfolio_macro_score": 0.0,
                "total_cost": 0.0,
                "total_value": 0.0,
                "total_gain_loss": 0.0,
                "total_gain_loss_percent": 0.0,
                "sector_allocation": {}
            }
            
        portfolio_data = []
        for h in db_holdings:
            portfolio_data.append({
                "ticker": h["ticker"],
                "qty": h["quantity"],
                "cost": h["average_cost"]
            })
        portfolio_df = pd.DataFrame(portfolio_data)
        
        # Calculate active indicators and evaluate
        results = await evaluate_portfolio_macro(portfolio_df, market_client, evaluator, {})
        return results

    if col_recalc.button("🔄 Recalculate Now" if not is_jp else "🔄 今すぐ再評価"):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with st.spinner("Evaluating portfolio against G20 macro environment..." if not is_jp else "G20マクロ環境に合わせたポートフォリオ評価を実行中..."):
                eval_results = loop.run_until_complete(run_eval())
                st.success("Re-evaluation completed!" if not is_jp else "ポートフォリオの再評価が完了しました！")
        finally:
            loop.close()

    if col_del.button("🗑️ Delete Portfolio" if not is_jp else "🗑️ ポートフォリオ削除"):
        delete_portfolio(selected_p_id)
        st.success("Portfolio deleted successfully!" if not is_jp else "ポートフォリオが削除されました！")
        st.rerun()

    # Load Holdings
    db_holdings = get_portfolio_holdings(selected_p_id)
    
    # Rentering Virtual Paper Trading or Real Portfolio Holdings
    if is_virtual:
        st.markdown("### 🎮 Virtual Order Entry" if not is_jp else "### 🎮 仮想注文の実行")
        t_col1, t_col2, t_col3, t_col4 = st.columns(4)
        with t_col1:
            trade_ticker = st.text_input(t("ticker_symbol"), key="vault_trade_ticker").strip()
        with t_col2:
            trade_side = st.selectbox(t("action"), ["BUY", "SELL"], key="vault_trade_side")
        with t_col3:
            trade_qty = st.number_input(t("quantity"), min_value=0.01, step=1.0, key="vault_trade_qty")
        with t_col4:
            manual_p = st.number_input(t("price"), min_value=0.0, step=1.0, key="vault_trade_price", help=t("price_help"))
            
        if st.button(t("submit_trade"), key="vault_submit_trade", use_container_width=True):
            if not trade_ticker:
                st.error(t("valid_ticker_error"))
            else:
                conn = sqlite3.connect("data/macro_cache.db")
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                try:
                    price = manual_p
                    if price == 0.0:
                        import yfinance as yf
                        t_data = yf.Ticker(trade_ticker)
                        price = t_data.history(period="1d")["Close"].iloc[-1]
                    
                    cursor.execute("SELECT id, quantity, average_cost FROM holdings WHERE portfolio_id=? AND ticker=?", (selected_p_id, trade_ticker))
                    pos = cursor.fetchone()
                    
                    if trade_side == "BUY":
                        if pos:
                            new_qty = pos["quantity"] + trade_qty
                            new_cost = ((pos["quantity"] * pos["average_cost"]) + (trade_qty * price)) / new_qty
                            cursor.execute("UPDATE holdings SET quantity=?, average_cost=? WHERE id=?", (new_qty, new_cost, pos["id"]))
                        else:
                            cursor.execute("INSERT INTO holdings (portfolio_id, ticker, quantity, average_cost, company_name, sector) VALUES (?, ?, ?, ?, ?, ?)",
                                           (selected_p_id, trade_ticker, trade_qty, price, trade_ticker, "unknown"))
                        st.success(t("bought_success", ticker=trade_ticker, qty=trade_qty, price=price, symbol="$"))
                    elif trade_side == "SELL":
                        if pos and pos["quantity"] >= trade_qty:
                            new_qty = pos["quantity"] - trade_qty
                            if new_qty == 0:
                                cursor.execute("DELETE FROM holdings WHERE id=?", (pos["id"],))
                            else:
                                cursor.execute("UPDATE holdings SET quantity=? WHERE id=?", (new_qty, pos["id"]))
                            st.success(t("sold_success", ticker=trade_ticker, qty=trade_qty, price=price, symbol="$"))
                        else:
                            st.error("Insufficient holdings to sell." if not is_jp else "売却するための保有残高が不足しています。")
                    conn.commit()
                except Exception as trade_err:
                    st.error(t("fetch_price_error") + f" ({trade_err})")
                finally:
                    conn.close()
                    st.rerun()

    # Show Holdings Table
    if not db_holdings:
        st.info(t("no_positions_paper") if is_virtual else t("no_positions_real"))
        return
        
    st.markdown("### 📁 Portfolio Positions" if not is_jp else "### 📁 保有銘柄一覧")
    
    # Recalculate evaluated scores
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        eval_results = loop.run_until_complete(run_eval())
    finally:
        loop.close()
        
    holdings_display = []
    for h in eval_results["holdings"]:
        holdings_display.append({
            "Ticker": h["ticker"],
            "Quantity": h["qty"],
            "Cost Basis": f"${h['cost']:,.2f}",
            "Market Price": f"${h['price']:,.2f}",
            "Total Cost": f"${h['cost_basis']:,.2f}",
            "Current Value": f"${h['value']:,.2f}",
            "Macro Score": f"{h['macro_score']:+.1f}",
            "Valuation Score": f"{h['valuation_score']:+.1f}",
            "Decision": h["decision"]
        })
    st.dataframe(pd.DataFrame(holdings_display), use_container_width=True, hide_index=True)
    
    # Portfolio Metrics Summary
    tot_val = eval_results["total_value"]
    tot_cost = eval_results["total_cost"]
    gain = eval_results["total_gain_loss"]
    gain_pct = eval_results["total_gain_loss_percent"]
    macro_s = eval_results["portfolio_macro_score"]
    
    met1, met2, met3, met4 = st.columns(4)
    met1.metric("Total Asset Value" if not is_jp else "総資産額", f"${tot_val:,.2f}")
    met2.metric("Total Cost" if not is_jp else "投資原資", f"${tot_cost:,.2f}")
    met3.metric("Profit / Loss" if not is_jp else "評価損益", f"${gain:+,.2f}", f"{gain_pct:+.2f}%")
    met4.metric("Portfolio Macro Score" if not is_jp else "ポートフォリオマクロスコア", f"{macro_s:+.2f}")
    
    # Sector Allocation & Rebalancing Recommendations
    st.markdown("### ⚖️ Sector Allocations & Rebalancing Suggestions" if not is_jp else "### ⚖️ セクターアロケーション＆リバランス提案")
    rebalance_data = recommend_rebalancing(
        eval_results,
        {},
        "US",
        {},
        language=("en" if not is_jp else "jp")
    )
    
    st.write(rebalance_data["summary"])
    if rebalance_data["has_recommendations"]:
        for action in rebalance_data["actions"]:
            st.info(action["description"])
            
    # PDF / HTML Review Export
    st.markdown("---")
    st.subheader(t("dl_report_btn"))
    
    def build_report_data():
        tot_val = eval_results["total_value"]
        tot_cost = eval_results["total_cost"]
        gain = eval_results["total_gain_loss"]
        gain_pct = eval_results["total_gain_loss_percent"]
        macro_s = eval_results["portfolio_macro_score"]
        
        score_status = ("Tailwind 🟢" if macro_s >= 10.0 else "Headwind 🔴" if macro_s <= -10.0 else "Neutral 🟡") if not is_jp else ("追い風 🟢" if macro_s >= 10.0 else "逆風 🔴" if macro_s <= -10.0 else "中立 🟡")
        score_color = "#10b981" if macro_s >= 10.0 else "#ef4444" if macro_s <= -10.0 else "#f59e0b"
        
        rows_html = ""
        for h in eval_results["holdings"]:
            rating = h["decision"]
            badge_bg = "#dcfce7" if rating == "BUY" else "#fee2e2" if rating == "AVOID" else "#fef9c3"
            badge_fg = "#15803d" if rating == "BUY" else "#b91c1c" if rating == "AVOID" else "#a16207"
            
            rows_html += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><span style="display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; background-color: {badge_bg}; color: {badge_fg};">{rating}</span></td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-weight: bold;">{h['ticker']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{h.get('company_name', h.get('name', 'N/A'))}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right;">{h['qty']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right;">${h['cost']:,.2f}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right;">${h['price']:,.2f}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: {score_color};">{h.get('macro_score', 0.0):+.1f}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold;">{h.get('valuation_score', 0.0):+.1f}</td>
            </tr>
            """
            
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Portfolio Macro Diagnosis Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #334155; background-color: #f8fafc; padding: 40px; line-height: 1.6; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); padding: 40px; }}
        h1 {{ font-size: 24px; font-weight: 700; color: #0f172a; margin-top: 0; }}
        .header-meta {{ font-size: 14px; color: #64748b; margin-bottom: 30px; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 40px; }}
        .metric-card {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-lbl {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-bottom: 5px; }}
        .metric-val {{ font-size: 18px; font-weight: 700; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }}
        th {{ background: #f1f5f9; padding: 10px; text-align: left; font-weight: bold; color: #475569; }}
        td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{"Portfolio Macro Evaluation Report" if not is_jp else "ポートフォリオ・マクロ環境診断レポート"}</h1>
        <div class="header-meta">
            {"Portfolio Name:" if not is_jp else "ポートフォリオ名:"} <strong>{selected_portfolio['name']}</strong> | 
            {"Date:" if not is_jp else "診断日時:"} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-lbl">{"Asset Value" if not is_jp else "総資産評価額"}</div>
                <div class="metric-val">${tot_val:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-lbl">{"Total Cost" if not is_jp else "投資原資"}</div>
                <div class="metric-val">${tot_cost:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-lbl">{"Profit / Loss" if not is_jp else "評価損益"}</div>
                <div class="metric-val" style="color: {'#10b981' if gain >= 0 else '#ef4444'}">${gain:+,.2f} ({gain_pct:+.2f}%)</div>
            </div>
            <div class="metric-card">
                <div class="metric-lbl">{"Macro Score" if not is_jp else "マクロ適合スコア"}</div>
                <div class="metric-val" style="color: {score_color};">{macro_s:+.2f} ({score_status})</div>
            </div>
        </div>
        
        <h3>{"Holdings Analysis" if not is_jp else "保有銘柄の内訳"}</h3>
        <table>
            <thead>
                <tr>
                    <th>Rating</th>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th style="text-align: right;">Qty</th>
                    <th style="text-align: right;">Cost</th>
                    <th style="text-align: right;">Price</th>
                    <th style="text-align: right;">Macro</th>
                    <th style="text-align: right;">Val</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        return html

    report_content = build_report_data()
    st.download_button(
        label="📥 Download Review Report (HTML)" if not is_jp else "📥 診断レポートをダウンロード (HTML)",
        data=report_content,
        file_name=f"macro_report_{selected_portfolio['name'].replace(' ', '_')}.html",
        mime="text/html",
        use_container_width=True
    )


def render_macro_timeline_ui():
    import pandas as pd
    import asyncio
    from src.db import get_macro_events_history, get_user_portfolios, get_portfolio_evaluations
    from src.scheduler import trigger_macro_event
    
    st.subheader(t("timeline_tab"))
    is_jp = (st.session_state.language == "jp")
    user = st.session_state.user
    
    if user["plan"] != "Pro":
        st.info("🔒 **Pro Tier Subscription Required**\n\nUpgrade to the $49/month Pro plan to access the Macro Event Timeline, review historical evaluations of your portfolio, and test automated trigger events.")
        
        st.markdown("### 📅 Live Demo (Timeline Preview)")
        mock_events = [
            {"detected_at": "2026-06-01 10:00:00", "event_type": "cpi_shock", "region": "US", "value": 5.2, "previous_value": 4.8, "severity": 3, "source": "FRED"},
            {"detected_at": "2026-05-15 14:30:00", "event_type": "rate_hike", "region": "EZ", "value": 4.5, "previous_value": 4.25, "severity": 2, "source": "ECB"},
            {"detected_at": "2026-05-01 09:00:00", "event_type": "oil_price_spike", "region": "Global", "value": 85.4, "previous_value": 72.1, "severity": 2, "source": "yfinance"}
        ]
        st.dataframe(pd.DataFrame(mock_events), use_container_width=True, hide_index=True)
        return

    col_trigger, col_timeline = st.columns([1, 1])
    
    with col_trigger:
        st.markdown("### 🚨 Simulate Macro Economic Shock" if not is_jp else "### 🚨 定性マクロショックのシミュレーション")
        st.markdown("デモ用にマクロショックを意図的に発生させ、保存されたポートフォリオの自動再評価およびアラート送信（ダミー送信/ログ出力）のライフサイクルをテストできます。" if is_jp else "You can simulate macro economic shocks to test the lifecycle of automated portfolio re-evaluations and alert dispatches (mocked log outputs).")
        
        ev_choice = st.selectbox(
            "Event Type to Trigger" if not is_jp else "トリガーするイベントの種類",
            ["cpi_shock", "rate_hike", "rate_cut", "gdp_drop", "oil_price_spike", "currency_crash"]
        )
        region_choice = st.selectbox("Region" if not is_jp else "対象国/地域", ["US", "JP", "EZ", "CN", "Global"])
        val_input = st.number_input("Event Value" if not is_jp else "指標値", value=5.5)
        prev_val_input = st.number_input("Previous Value" if not is_jp else "前回指標値", value=4.0)
        sev_choice = st.slider("Event Severity" if not is_jp else "イベント深刻度 (Severity)", min_value=1, max_value=3, value=2)
        
        if st.button("Trigger Macro Shock" if not is_jp else "マクロショックをトリガー"):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                with st.spinner("Processing event and notifying user..." if not is_jp else "イベントを処理中＆ユーザーへの通知中..."):
                    event_id = loop.run_until_complete(
                        trigger_macro_event(
                            event_type=ev_choice,
                            region=region_choice,
                            value=val_input,
                            prev_value=prev_val_input,
                            change_rate=37.5,
                            severity=sev_choice,
                            source="Demo Simulator"
                        )
                    )
                    st.success(f"Macro Event (ID: {event_id}) processed and automated alerts logged!" if not is_jp else f"マクロイベント (ID: {event_id}) がトリガーされ、自動アラートが記録されました！")
                    st.rerun()
            finally:
                loop.close()

    with col_timeline:
        st.markdown("### 📅 Macro Event History" if not is_jp else "### 📅 マクロ経済イベントログ履歴")
        events = get_macro_events_history()
        if events:
            events_df = pd.DataFrame(events)
            st.dataframe(events_df, use_container_width=True, hide_index=True)
        else:
            st.info("No macro events recorded in DB." if not is_jp else "DBに記録されたマクロイベントはありません。")


def render_alert_settings_ui():
    from src.db import get_notification_settings, save_notification_settings, update_user_plan, get_user_by_email
    
    st.subheader(t("alerts_tab"))
    user = st.session_state.user
    user_id = user["id"]
    
    # Reload user data to sync plan changes
    user = get_user_by_email(user["email"])
    st.session_state.user = user
    current_plan = user["plan"]
    
    is_jp = (st.session_state.language == "jp")
    
    st.markdown("""
    <style>
        .premium-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid rgba(200, 165, 90, 0.2);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
        }
        .pro-badge {
            background: linear-gradient(135deg, #c8a55a 0%, #b48a32 100%);
            color: #141410 !important;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: inline-block;
        }
        .free-badge {
            background-color: #475569;
            color: #f1f5f9 !important;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            text-transform: uppercase;
            display: inline-block;
        }
        .price-text {
            font-size: 32px;
            font-weight: 800;
            color: #e2e8f0;
            margin: 15px 0;
        }
        .price-sub {
            font-size: 14px;
            color: #94a3b8;
            font-weight: normal;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Demo controls: Allow switching active monitoring state
    st.sidebar.markdown("---")
    st.sidebar.subheader("🕹️ Monitoring Configurations" if not is_jp else "🕹️ 監視設定")
    test_monitoring = st.sidebar.radio(
        "Active Background Monitoring:" if not is_jp else "バックグラウンド監視の有効化:",
        ["Disabled (Manual Mode)" if not is_jp else "無効 (手動確認モード)", "Enabled (Active Alerts)" if not is_jp else "有効 (自動マクロアラート発信)"],
        index=0 if current_plan == "Free" else 1,
        key="set_demo_plan"
    )
    test_plan = "Pro" if "Enabled" in test_monitoring or "有効" in test_monitoring else "Free"
    if test_plan != current_plan:
        update_user_plan(user_id, test_plan)
        st.success("Monitoring settings updated!" if not is_jp else "バックグラウンド監視プランを更新しました！")
        st.rerun()

    # Display Current Active Status
    if current_plan == "Pro":
        st.markdown(f'<div class="premium-card"><h4>System Monitoring Status</h4><span class="pro-badge">ACTIVE MONITORING ENABLED</span><p style="color: #94a3b8; font-size:14px; margin-top: 10px;">The engine is continuously evaluating your holdings against changing macroeconomic environments.</p></div>' if not is_jp else f'<div class="premium-card"><h4>システム自動監視ステータス</h4><span class="pro-badge">自動バックグラウンド監視有効化</span><p style="color: #94a3b8; font-size:14px; margin-top: 10px;">マクロエンジンが市場指標の変更を検出し、保存されたポートフォリオへの影響をリアルタイムで監視しています。</p></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="premium-card"><h4>System Monitoring Status</h4><span class="free-badge">MANUAL VERIFICATION MODE</span><p style="color: #94a3b8; font-size:14px; margin-top: 10px;">You are currently in manual verification mode. Enable Active Monitoring in the sidebar controls to unlock automated macro alerts.</p></div>' if not is_jp else f'<div class="premium-card"><h4>システム自動監視ステータス</h4><span class="free-badge">手動検証モード</span><p style="color: #94a3b8; font-size:14px; margin-top: 10px;">手動診断のみ利用可能です。サイドバーの「バックグラウンド監視の有効化」を選択すると、Pro機能が有効になり、自動再評価とアラート通知が開始されます。</p></div>', unsafe_allow_html=True)
        
    # Get settings from DB
    settings = get_notification_settings(user_id)
    
    # Alerts Setting Form
    st.markdown("### ⚙️ Notification Preferences" if not is_jp else "### ⚙️ 自動通知アラート設定")
    if current_plan != "Pro":
        if is_jp:
            st.info("⚠️ **自動監視はProプラン専用機能です。**サイドバーから「有効（自動マクロアラート発信）」を選択して、リアルタイム通知をテストしてください。")
        else:
            st.info("⚠️ **Active Monitoring must be enabled in the sidebar** to configure automated background notifications.")
        
    email_on = st.checkbox("Email Notifications Enabled" if not is_jp else "メール通知を有効化", value=(settings["email_enabled"] == 1), disabled=(current_plan != "Pro"))
    
    # SMTP Settings (Visible when email notifications are enabled)
    if email_on:
        st.markdown("##### 📧 SMTP Config" if not is_jp else "##### 📧 SMTP 送信設定")
        col_smtp1, col_smtp2 = st.columns(2)
        with col_smtp1:
            smtp_host = st.text_input("SMTP Host", value=settings.get("smtp_host", ""), disabled=(current_plan != "Pro"))
            smtp_user = st.text_input("SMTP Username", value=settings.get("smtp_username", ""), disabled=(current_plan != "Pro"))
            smtp_from = st.text_input("Sender Address (From)", value=settings.get("smtp_from", ""), disabled=(current_plan != "Pro"), placeholder="noreply@macro-stock-engine.com")
        with col_smtp2:
            smtp_port = st.number_input("SMTP Port", value=int(settings.get("smtp_port", 587) or 587), step=1, disabled=(current_plan != "Pro"))
            smtp_pass = st.text_input("SMTP Password", value=settings.get("smtp_password", ""), type="password", disabled=(current_plan != "Pro"))
    else:
        smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from = "", 587, "", "", ""

    # Slack Settings
    slack_on = st.checkbox("Slack Notifications Enabled" if not is_jp else "Slack通知を有効化", value=(settings.get("slack_enabled", 0) == 1), disabled=(current_plan != "Pro"))
    if slack_on:
        slack_url = st.text_input("Slack Webhook URL", value=settings.get("slack_webhook_url", ""), disabled=(current_plan != "Pro"), placeholder="https://hooks.slack.com/services/...")
    else:
        slack_url = ""

    telegram_on = st.checkbox("Telegram Notifications Enabled" if not is_jp else "Telegram通知を有効化", value=(settings.get("telegram_enabled", 0) == 1), disabled=(current_plan != "Pro"))
    
    col1, col2 = st.columns(2)
    with col1:
        telegram_token = st.text_input(
            "Telegram Bot Token" if not is_jp else "Telegram Botトークン",
            value=settings.get("telegram_bot_token", ""),
            type="password",
            disabled=(not telegram_on or current_plan != "Pro"),
            help="Get this from @BotFather on Telegram"
        )
    with col2:
        telegram_chat = st.text_input(
            "Telegram Chat ID" if not is_jp else "Telegram チャットID",
            value=settings.get("telegram_chat_id", ""),
            type="password",
            disabled=(not telegram_on or current_plan != "Pro"),
            help="Your chat or channel ID"
        )
    
    min_sev = st.slider(
        "Minimum Event Severity to Alert" if not is_jp else "通知する最小のイベント深刻度",
        min_value=1,
        max_value=3,
        value=settings.get("min_severity", 2),
        disabled=(current_plan != "Pro"),
        help="1 = Mild, 2 = Moderate, 3 = Severe shock events"
    )
    
    # Checklist for event types
    st.write("**Alert on Event Types:**" if not is_jp else "**通知対象イベントの選択:**")
    db_events = [x.strip().lower() for x in settings.get("event_types", "").split(",") if x.strip()]
    
    event_options = {
        "cpi_shock": "CPI / Inflation shock" if not is_jp else "インフレ加速ショック (CPI)",
        "rate_hike": "FOMC / Policy rate changes" if not is_jp else "利上げ / 政策金利の変更",
        "gdp_drop": "GDP deceleration" if not is_jp else "GDP成長率の急減速",
        "oil_price_spike": "Oil price spikes" if not is_jp else "原油価格の急騰ショック"
    }
    
    selected_event_types = []
    for ev_key, ev_label in event_options.items():
        if st.checkbox(ev_label, value=(ev_key in db_events), disabled=(current_plan != "Pro"), key=f"alert_ev_{ev_key}"):
            selected_event_types.append(ev_key)
            
    if st.button("Save Alert Settings" if not is_jp else "通知設定を保存", disabled=(current_plan != "Pro")):
        save_notification_settings(
            user_id=user_id,
            email_enabled=1 if email_on else 0,
            slack_enabled=1 if slack_on else 0,
            slack_webhook_url=slack_url,
            min_severity=min_sev,
            event_types=",".join(selected_event_types),
            frequency="instant",
            telegram_enabled=1 if telegram_on else 0,
            telegram_bot_token=telegram_token,
            telegram_chat_id=telegram_chat,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_user,
            smtp_password=smtp_pass,
            smtp_from=smtp_from
        )
        st.success("Alert settings saved!" if not is_jp else "通知設定が正常に保存されました！")

def render_contact_form_ui():
    import requests
    from src.db import save_inquiry, get_inquiries
    
    st.subheader(t("contact_title"))
    st.markdown(t("contact_desc"))
    st.markdown("---")
    
    is_jp = (st.session_state.language == "jp")
    
    with st.form("contact_inquiry_form", clear_on_submit=True):
        name = st.text_input(t("contact_name"), placeholder="John Doe" if not is_jp else "山田 太郎")
        email = st.text_input(t("contact_email"), placeholder="john@example.com" if not is_jp else "yamada@example.com")
        subject = st.text_input(t("contact_subj"), placeholder="Feedback/Question" if not is_jp else "質問・フィードバック")
        message = st.text_area(t("contact_msg"), placeholder="Write your message here..." if not is_jp else "お問い合わせ内容を入力してください...")
        
        submitted = st.form_submit_button(t("contact_submit"), use_container_width=True)
        
        if submitted:
            if not name or not email or not message:
                st.error("Please fill in Name, Email, and Message." if not is_jp else "お名前、メールアドレス、本文を入力してください。")
            else:
                try:
                    # Submit to FormSubmit AJAX endpoint
                    payload = {
                        "name": name,
                        "email": email,
                        "_subject": f"[{subject}] from Stock Screener Hub",
                        "message": message,
                        "_captcha": "false"
                    }
                    response = requests.post(
                        "https://formsubmit.co/ajax/macro@z0a.net",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200 and response.json().get("success") == "true":
                        # Save in SQLite DB
                        save_inquiry(name=name, email=email, subject=subject, message=message)
                        st.success(t("contact_success"))
                    else:
                        # Fallback: Save in SQLite DB anyway
                        save_inquiry(name=name, email=email, subject=subject, message=message)
                        warning_msg = "Your inquiry was saved to the local database, but we encountered an issue forwarding the email. Reason: " + response.text[:200] if st.session_state.language == "en" else "お問い合わせはローカルデータベースに保存されましたが、メール転送時に問題が発生しました。理由: " + response.text[:200]
                        st.warning(warning_msg)
                except Exception as ex:
                    # Fallback: Save in SQLite DB anyway
                    save_inquiry(name=name, email=email, subject=subject, message=message)
                    warning_msg = f"Your inquiry was saved to the local database, but email routing is temporarily offline. Reason: {str(ex)[:200]}" if st.session_state.language == "en" else f"お問い合わせはローカルデータベースに保存されましたが、メールサービスに接続できませんでした。理由: {str(ex)[:200]}"
                    st.warning(warning_msg)
                    
    # Notice for first time setup
    st.info(t("contact_first_time_notice"))
    st.markdown("---")
    
    # Render history
    st.subheader(t("contact_history_title"))
    history = get_inquiries(limit=10)
    if history:
        ui_rows = []
        for item in history:
            ui_rows.append({
                "Date": item["submitted_at"],
                "Name": item["name"],
                "Email": item["email"],
                "Subject": item["subject"],
                "Message": item["message"]
            })
        st.dataframe(pd.DataFrame(ui_rows), use_container_width=True, hide_index=True)
    else:
        st.info(t("contact_no_history"))

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
    real_portfolio_name = "🇯🇵/🇺🇸 Real Portfolio (Rakuten CSV Sync)" if st.session_state.language == "en" else "🇯🇵/🇺🇸 Real Portfolio (楽天CSV連携)"
    st.session_state.real_portfolio = PaperTradeAccount(real_portfolio_name, currency=CURRENCY_MAP.get("US", "$"))

# Sync account currency dynamically based on current target market
current_curr = CURRENCY_MAP.get(st.session_state.selected_country if "selected_country" in st.session_state else "US", "$")
for acc_key, acc_obj in st.session_state.paper_accounts.items():
    acc_obj.currency = current_curr
if "real_portfolio" in st.session_state:
    st.session_state.real_portfolio.currency = current_curr
    st.session_state.real_portfolio.name = "🇯🇵/🇺🇸 Real Portfolio (Rakuten CSV Sync)" if st.session_state.language == "en" else "🇯🇵/🇺🇸 Real Portfolio (楽天CSV連携)"

# Sidebar configuration
st.sidebar.header(t("sidebar_title"))

# Language selector
lang_choice = st.sidebar.selectbox(
    t("language_label"),
    ["English", "日本語"],
    index=0 if st.session_state.language == "en" else 1
)
new_lang = "en" if lang_choice == "English" else "jp"
if new_lang != st.session_state.language:
    st.session_state.language = new_lang
    st.rerun()

# Navigation Page Selector
if st.session_state.active_tab == "screener":
    page_selection = st.sidebar.radio(
        "🧭 Navigation" if st.session_state.language == "en" else "🧭 ナビゲーション",
        [
            t("screener_tab"),
            t("portfolios_tab"),
            t("timeline_tab"),
            t("alerts_tab"),
            t("verification_tab")
        ],
        key="nav_page"
    )
else:
    page_selection = ""

# Sync active_tab and page selection back to URL query params
if st.session_state.active_tab == "docs":
    st.query_params["page"] = "docs"
elif st.session_state.active_tab == "contact":
    st.query_params["page"] = "contact"
else:
    reverse_route_map = {
        t("screener_tab"): "screener",
        t("portfolios_tab"): "vault",
        t("timeline_tab"): "timeline",
        t("alerts_tab"): "alerts",
        t("verification_tab"): "verification",
    }
    if page_selection in reverse_route_map:
        st.query_params["page"] = reverse_route_map[page_selection]

# Handle routing based on active_tab or page_selection
if st.session_state.active_tab == "docs":
    # Inject CSS to hide sidebar completely and center the content
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }
            [data-testid="stSidebarCollapsedControl"] {
                display: none !important;
            }
            [data-testid="stAppViewContainer"] {
                padding-left: 0rem !important;
            }
            .main .block-container {
                max-width: 900px !important;
                margin: 0 auto !important;
                padding-top: 2rem !important;
                padding-bottom: 2rem !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    render_readme_ui()
    st.stop()

if st.session_state.active_tab == "contact":
    # Inject CSS to hide sidebar completely and center the content
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }
            [data-testid="stSidebarCollapsedControl"] {
                display: none !important;
            }
            [data-testid="stAppViewContainer"] {
                padding-left: 0rem !important;
            }
            .main .block-container {
                max-width: 900px !important;
                margin: 0 auto !important;
                padding-top: 2rem !important;
                padding-bottom: 2rem !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    render_contact_form_ui()
    st.stop()

# Screener Sub-pages Routing (only if active_tab is "screener")
if st.session_state.active_tab == "screener":
    if page_selection == t("portfolios_tab"):
        render_portfolios_vault_ui()
        st.stop()
    elif page_selection == t("timeline_tab"):
        render_macro_timeline_ui()
        st.stop()
    elif page_selection == t("alerts_tab"):
        render_alert_settings_ui()
        st.stop()
    elif page_selection == t("verification_tab"):
        render_verification_board_ui()
        st.stop()

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
        for ticker in t_list:
            stock_metrics_map[ticker] = {
                "ticker": ticker,
                "name": ticker.split(".")[0],
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
for ticker in country_tickers:
    m = stock_metrics_map.get(ticker)
    if m:
        country_stock_metrics.append(m)

# Run StockEvaluator
evaluator = StockEvaluator()
evaluated_stocks = evaluator.evaluate_stocks(country_stock_metrics, sector_scores, market=current_country)

if evaluated_stocks:
    # Log predictions to tracking database
    try:
        from src.tracker import PredictionTracker
        db_tracker = PredictionTracker()
        db_tracker.log_predictions(evaluated_stocks)
    except Exception as log_err:
        logger.warning(f"Failed to log predictions to database: {log_err}")

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

# --- 8. REDIRECTION TO PREMIUM PORTFOLIOS VAULT ---
st.markdown("---")
st.markdown(f"""
<div style="background: linear-gradient(90deg, rgba(200, 165, 90, 0.1), rgba(30, 41, 59, 0.9)); border-left: 4px solid #c8a55a; padding: 25px; border-radius: 8px; margin-top: 30px;">
    <h3 style="margin-top:0; color:#e8e0d0;">{t('redirect_banner_title')}</h3>
    <p style="color:#94a3b8; font-size:14px; line-height: 1.5;">
        {t('redirect_banner_desc1')}
    </p>
    <p style="color:#94a3b8; font-size:14px; line-height: 1.5;">
        {t('redirect_banner_desc2')}
    </p>
</div>
""", unsafe_allow_html=True)
