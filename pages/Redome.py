import streamlit as st
import pathlib

st.set_page_config(
    page_title="Macro & Stock Evaluation Engine - Logic & Docs",
    page_icon="📖",
    layout="wide"
)

# Custom premium styling
st.markdown("""
<style>
    .reportview-container {
        background: #0f172a;
    }
    .title-text {
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.2rem;
        margin-bottom: 0.5rem;
    }
    .subtitle-text {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .logic-header {
        color: #38bdf8;
        font-weight: 700;
        border-bottom: 2px solid #1e293b;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .info-card {
        background-color: #1e293b;
        border-left: 5px solid #818cf8;
        padding: 1.2rem;
        border-radius: 4px;
        margin-bottom: 1.5rem;
    }
    .table-container {
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">📊 ドキュメント＆操作マニュアル</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">ツールの具体的な操作方法（保有株CSVの分析など）や、裏側で動作する数理評価アルゴリズムについて解説します。</div>', unsafe_allow_html=True)

# Tabs to organize information
tab_howto, tab_overview, tab_events, tab_matrix, tab_valuation, tab_decision = st.tabs([
    "📖 使い方ガイド (HOWTO)",
    "🔍 1. 全体像・処理フロー",
    "🔔 2. マクロシグナル検出ロジック",
    "🏆 3. セクター影響度マトリクス",
    "⚖️ 4. 国別バリュエーション評価",
    "🎯 5. 投資判断決定ツリー"
])

# ----------------- TAB 0: HOWTO GUIDE -----------------
with tab_howto:
    st.markdown('<h3 class="logic-header">保有ポートフォリオ診断 ＆ ツール操作手順</h3>', unsafe_allow_html=True)
    current_dir = pathlib.Path(__file__).parent.parent
    howto_path = current_dir / "HOWTO.md"
    if howto_path.exists():
        with open(howto_path, "r", encoding="utf-8") as f:
            howto_content = f.read()
        # Display the HOWTO.md content
        st.markdown(howto_content)
    else:
        st.error("使い方ガイド（HOWTO.md）ファイルが見つかりません。")

# ----------------- TAB 1: OVERVIEW -----------------
with tab_overview:
    st.markdown('<h3 class="logic-header">システムアーキテクチャ & パイプライン</h3>', unsafe_allow_html=True)
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

# ----------------- TAB 2: EVENTS -----------------
with tab_events:
    st.markdown('<h3 class="logic-header">12のマクロイベント検出ロジック</h3>', unsafe_allow_html=True)
    st.write(
        "システムは、インプットされた時系列データを元に、以下のルールを用いてマクロ経済の「シグナル」を検出します。"
        "各イベントには、その大きさに応じて **Severity（深刻度/重要度: 1=軽微, 2=中等度, 3=重大）** が割り当てられます。"
    )

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

# ----------------- TAB 3: MATRIX -----------------
with tab_matrix:
    st.markdown('<h3 class="logic-header">産業別インパクトマトリクスと累積スコア計算</h3>', unsafe_allow_html=True)
    st.write(
        "検出されたマクロイベントが、各産業セクターにどのような影響を与えるかは、**「インパクトマトリクス (Impact Matrix)」**という係数テーブルによって定義されています。"
        "影響度は **-50 (深刻な逆風)** から **+50 (強力な追い風)** までの範囲で設定されています。"
    )

    st.markdown("""
    #### 累積影響度スコアの数式
    検出された複数のマクロイベントによる累積スコアは、各マクロイベントの「基本加重値」に「検出された重要度（Severity）」を掛け合わせて線形加算します。
    """)
    
    st.latex(r"Raw\_Score_{Sector} = \sum_{Event} \left( Base\_Weight_{Event, Sector} \times Severity_{Event} \right)")
    
    st.markdown("""
    #### 正規化処理
    セクター間の比較を容易にするため、算出された累積スコアを最大絶対値で割り、**[-1.0, 1.0]** の範囲にスケールします。
    """)
    st.latex(r"Normalized\_Score_{Sector} = \frac{Raw\_Score_{Sector}}{\max \left( |Raw\_Score_{All\_Sectors}|, 1.0 \right)}")

    st.write("**主要イベントとセクター加重値の対応例（抜粋）:**")
    st.markdown("""
    * **金利上昇 (RATE_RISING)**: 銀行（`+30〜+40`）, 保険（`+20〜+30`）は収益改善のため**追い風**。一方、不動産（`-30〜-40`）, 建設（`-20`）は資金調達コスト増と住宅ローン抑制のため**大逆風**。
    * **インフレ加速 (INFLATION_ACCELERATING)**: エネルギー（`+40`）, 素材/鉱業（`+30`）は資源価格上昇で**追い風**。小売/食品（`-20〜-30`）は仕入コスト上昇を価格転嫁しづらいため**逆風**。
    * **自国通貨安 (YEN_DEPRECIATING等)**: 輸出産業である自動車（`+40`）, 電機・半導体（`+40`）, 機械（`+30`）は**追い風**。輸入コストが増加する小売（`-20`）, 空運（`-20`）は**逆風**。
    * **AI投資ブーム (AI_INVESTMENT_BOOM)**: 半導体（`+50`）, データセンター/通信（`+40`）, 電源装置/電子部品（`+30`）に**極めて強い追い風**。
    """)

# ----------------- TAB 4: VALUATION -----------------
with tab_valuation:
    st.markdown('<h3 class="logic-header">国別バリュエーション（割安度）のスコアリング</h3>', unsafe_allow_html=True)
    st.write(
        "どれだけマクロ環境が良くても、株価が割高すぎる局面での投資はリスクを伴います。"
        "そこで個別銘柄の **PER (株価収益率)** と **PBR (純資産倍率)** を元に、バリュエーションスコア（最大 50点満点）を算出します。"
    )
    st.write(
        "国（市場）によって平均的なバリュエーション水準が異なるため、システムは**日本(JP)、米国(US/EU)、中国(CN)**それぞれに最適化された閾値テーブルを使い分けています。"
    )

    st.markdown('<div class="info-card"><strong>💡 スコア計算式:</strong><br>バリュエーションスコア（最大50点） ＝ PER評価点（最大30点） ＋ PBR評価点（最大20点）</div>', unsafe_allow_html=True)

    # Tables showing thresholds
    col1, col2 = st.columns(2)
    with col1:
        st.write("**PER（株価収益率）の評価基準 (点数配分)**")
        st.markdown("""
        | 区分 | 日本 (JP) | 米国・欧州 (US/EZ) | 中国 (CN) | 評価点 |
        | :--- | :--- | :--- | :--- | :---: |
        | **極めて割安** | 8.0 倍 以下 | 14.0 倍 以下 | 10.0 倍 以下 | **+30 点** |
        | **割安** | 8.0 〜 13.0 倍 | 14.0 〜 22.0 倍 | 10.0 〜 16.0 倍 | **+15 点** |
        | **適正水準** | 13.0 〜 20.0 倍 | 22.0 〜 30.0 倍 | 16.0 〜 24.0 倍 | **0 点** |
        | **割高** | 20.0 倍 超 | 30.0 倍 超 | 24.0 倍 超 | **-15 点** |
        | **赤字 / 異常値** | 0 倍 以下 | 0 倍 以下 | 0 倍 以下 | **-20 点** |
        """)
        
    with col2:
        st.write("**PBR（純資産倍率）の評価基準 (点数配分)**")
        st.markdown("""
        | 区分 | 日本 (JP) | 米国・欧州 (US/EZ) | 中国 (CN) | 評価点 |
        | :--- | :--- | :--- | :--- | :---: |
        | **極めて割安** | 0.7 倍 以下 | 1.5 倍 以下 | 1.0 倍 以下 | **+20 点** |
        | **割安** | 0.7 〜 1.0 倍 | 1.5 〜 3.0 倍 | 1.0 〜 1.8 倍 | **+10 点** |
        | **適正水準** | 1.0 〜 1.8 倍 | 3.0 〜 5.5 倍 | 1.8 〜 3.2 倍 | **0 点** |
        | **割高** | 1.8 倍 超 | 5.5 倍 超 | 3.2 倍 超 | **-10 点** |
        | **債務超過** | 0 倍 以下 | 0 倍 以下 | 0 倍 以下 | **-10 点** |
        """)

# ----------------- TAB 5: DECISION -----------------
with tab_decision:
    st.markdown('<h3 class="logic-header">総合意思決定ルール（デシジョンツリー）</h3>', unsafe_allow_html=True)
    st.write(
        "最終的な投資判断（**BUY: 買い推奨**, **WATCH: 監視**, **AVOID: 回避**）は、"
        "セクターのマクロ影響度スコアと、個別銘柄のバリュエーションスコアを統合した総合スコア、および「絶対除外ルール」に基づいて決定されます。"
    )

    st.markdown("""
    ### 投資判断の振り分け条件
    """)

    c_buy, c_watch, c_avoid = st.columns(3)
    
    with c_buy:
        st.success("🟢 **BUY (買い推奨)**")
        st.markdown("""
        次の条件を**すべて**満たす銘柄：
        1. **マクロ影響度スコア** が **+15 以上**  
           (業界に強い追い風が吹いている)
        2. **バリュエーションスコア** が **+10 以上**  
           (割安または適正な水準にある)
        3. **赤字ではない** (PER > 0)
        """)
        
    with c_avoid:
        st.error("🔴 **AVOID (回避推奨)**")
        st.markdown("""
        次の条件の**いずれか一つでも**満たす銘柄：
        1. **マクロ影響度スコア** が **-20 以下**  
           (業界に重大な逆風リスクがある)
        2. **バリュエーションスコア** が **-25 以下**  
           (株価が極めて割高で割に合わない)
        3. **過剰な高PER**  
           (日本: PER > 40, 中国: PER > 48, 米国/欧州: PER > 60)
        4. **赤字または債務超過** (PER ≦ 0 または PBR ≦ 0)
        """)

    with c_watch:
        st.warning("🟡 **WATCH (様子見・監視)**")
        st.markdown("""
        上記の **BUY** および **AVOID** のいずれの条件にも該当しない銘柄。
        * 例: マクロの追い風はあるが株価がやや高水準にある銘柄。
        * 例: 非常に割安だが、マクロイベントによる後押しがまだ弱い銘柄。
        
        *※株価調整やマクロ指標の好転を待つ「ウォッチリスト」へ分類されます。*
        """)

    st.markdown("---")
    st.markdown("""
    ### 🚀 本ツールの強み
    単に「割安な株」や「トレンドが良い株」を買うのではなく、
    1. **「追い風が吹いている業界（マクロ）」**
    2. **「実態価値に対して割安な株（バリュエーション）」**
    
    この2つが**ピタリと合致した瞬間のみを `BUY` と判定する**ため、トレンドの転換点やバリュートラップ（安物買いの失速）を回避しやすい極めて厳格なクオンツ判定ロジックになっています。
    """)
