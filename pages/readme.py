import os
import streamlit as st
import pathlib

st.set_page_config(
    page_title="Readme / G20 Macro Hub",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide sidebar completely for clean single column view
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
            max-width: 800px !important;
            margin: 0 auto !important;
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# Link back to the main app
st.markdown("### [◀ Back to Screener Hub / メインアプリに戻る](https://macro-stock-engine.streamlit.app/)")
st.markdown("---")

# Styling overrides
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

st.markdown('<div class="title-text">📊 G20 Macro & Stock Screener Hub</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Technical Specifications, User Manual & Mathematical Logic</div>', unsafe_allow_html=True)

# Custom Domain Branding Link
st.markdown("""
<div class="link-banner">
    🚀 <strong>本システムのオフィシャルカスタムドメイン:</strong> 
    <a href="https://stock.z0a.net" target="_blank">stock.z0a.net</a> から安全にアクセスいただけます。
</div>
""", unsafe_allow_html=True)

tab_howto, tab_logic = st.tabs([
    "📖 1. 使い方ガイド (HOWTO)",
    "📊 2. クオンツ判定ロジック (Logic)"
])

with tab_howto:
    st.markdown('<h3 class="logic-header">保有ポートフォリオ診断 ＆ ツール操作手順</h3>', unsafe_allow_html=True)
    current_dir = pathlib.Path(__file__).parent
    howto_path = current_dir.parent / "HOWTO.md"  # Resolved from root folder
    if howto_path.exists():
        with open(howto_path, "r", encoding="utf-8") as f:
            howto_content = f.read()
        st.markdown(howto_content)
    else:
        st.error("使い方ガイド（HOWTO.md）ファイルが見つかりません。")

with tab_logic:
    st.markdown('<h3 class="logic-header">システムアーキテク架构 & パイプライン</h3>', unsafe_allow_html=True)
    st.write(
        "本システムは、リアルタイムのマクロ時系列データ（経済環境）と個別銘柄の財務指標（ミクロデータ）を融合させて投資判断を導き出す、**「トップダウン・アプローチ」**を採用したクオンツ評価エンジンです。"
    )
    
    st.info("""
    **🔄 処理パイプラインの4つのステップ:**
    1. **データ取得 (Data Ingestion)**: FRED APIおよびyfinanceからマクロ時系列データと個別財務データを取得・クレンジング。
    2. **シグナル検出 (Event Detector)**: 移動平均線（SMA）や前月比、30日変化率を用いて、現在のマクロ指標から12種のエコノミックイベントを検出し、その深刻度（Severity）を決定。
    3. **セクタースコアリング (Rule Engine)**: 検出されたイベントを、静的な「産業別インパクトマトリクス」へ通し、17セクターに対する累積影響度スコアを算出・正規化。
    4. **銘柄総合スクリーニング (Stock Evaluator)**: 各国の市場特性に適合させたバリュエーションモデル（PER/PBR評価）を適用し、マクロ適合度と統合して最終意思決定（BUY / WATCH / AVOID）を決定。
    """)
    
    # Text flow diagram
    st.markdown("```")
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
    st.markdown("```")

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
