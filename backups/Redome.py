import streamlit as st
import pathlib

st.set_page_config(
    page_title="Obra — The Blueprint & Docs",
    page_icon="🏛️",
    layout="wide"
)

# Custom premium styling matching Obra's aesthetic (Gaudí / Amber / Stone Grid theme)
st.markdown("""
<style>
    .reportview-container {
        background: #0a0a08;
    }
    .title-text {
        background: linear-gradient(135deg, #c8a55a, #d4b06a);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-family: 'Cormorant Garamond', serif;
        font-weight: 300;
        font-size: 2.5rem;
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
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">🏛️ Obra — The Blueprint</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Seven AI-Native Tools. One Unified Vision. Office 2.0 for the Age of Intelligence.</div>', unsafe_allow_html=True)

# Custom Domain Branding Link
st.markdown("""
<div class="link-banner">
    🚀 <strong>本システムのオフィシャルカスタムドメイン:</strong> 
    <a href="https://macro.ezora.net" target="_blank">macro.ezora.net</a> から安全にアクセスいただけます。
</div>
""", unsafe_allow_html=True)

# Tabs
tab_blueprint, tab_howto, tab_logic = st.tabs([
    "🏛️ 1. Obra Blueprint (設計図)",
    "📖 2. 使い方ガイド (HOWTO)",
    "📊 3. クオンツ判定ロジック (Logic)"
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
    st.markdown('<h3 class="logic-header">保有ポートフォリオ診断 ＆ ツール操作手順</h3>', unsafe_allow_html=True)
    current_dir = pathlib.Path(__file__).parent.parent
    howto_path = current_dir / "HOWTO.md"
    if howto_path.exists():
        with open(howto_path, "r", encoding="utf-8") as f:
            howto_content = f.read()
        st.markdown(howto_content)
    else:
        st.error("使い方ガイド（HOWTO.md）ファイルが見つかりません。")

# ----------------- TAB 3: QUANT LOGIC -----------------
with tab_logic:
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
