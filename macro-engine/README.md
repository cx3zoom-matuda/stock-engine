# Macro Engine (マクロ評価スクリーニングエンジン)

本プロジェクトは、FRED (Federal Reserve Economic Data) から取得したリアルタイムのマクロ経済データを解析し、金利、インフレ、原油価格、為替などのマクロトレンドシグナルを検出した上で、16つの産業セクターおよび個別銘柄への影響スコアを算出して投資判断のスクリーニングを行うシステムです。

PySide6を用いたデスクトップGUI、およびコマンドライン(CLI)の両インターフェースをサポートしています。

---

## 主な機能

1. **データインジェスト (Ingestion)**
   - FRED APIから米国債利回り(10年/2年)、CPI、WTI原油価格、USD/JPY為替レートの時系列データを非同期で取得。
   - APIキーが未設定の場合のオフラインフォールバック/キャッシュ機能を搭載。
   - `yfinance` を利用した個別銘柄のバリュエーションデータ (PER, PBR) の取得。

2. **マクロシグナル検出 (Signal Detection)**
   - 12種類のマクロ経済シグナル（イールドカーブ逆イールド・フラット化、金利上昇/下落、インフレ加速/減速、原油ショック、円安/円高など）を時系列データの移動平均(SMA)等から動的に検知。

3. **産業セクター影響度スコアリング (Impact Scoring)**
   - 検出したシグナルを静的インパクトマトリクス（-50〜+50の範囲）にマッピングし、16種類の主要産業セクターごとのマクロ影響度スコアを算出。

4. **銘柄評価 (Stock Evaluation)**
   - セクターごとのマクロスコアと、各銘柄のバリュエーション（割安度）スコアを統合し、総合的な投資判断（`BUY`, `WATCH`, `AVOID`）と判断理由（Rationale）を出力。

5. **予測トラッキング (Prediction Tracker)**
   - スクリーニング結果と予測データをSQLiteデータベース（`data/macro_cache.db` 等）に保存し、バックテストや予測精度の検証を可能にするトラッキング機能を搭載。

6. **GUI / CLI デュアルインターフェース**
   - **GUI:** PySide6を使用した直感的でインタラクティブなデスクトップダッシュボード。
   - **CLI:** 自動実行やパイプライン連携に適したターミナル表示モード。

---

## ディレクトリ構成

```
/Users/p/developer/services/macro-engine/
├── README.md               # プロジェクト説明書 (本書)
├── requirements.txt        # 依存ライブラリ一覧 (PySide6, pandas, yfinance 等)
├── config.toml             # 設定ファイル (FRED APIキー、対象ティッカー一覧など)
├── config.toml.example     # 設定ファイルのテンプレート
├── main.py                 # アプリケーションのエントリーポイント
├── data/
│   └── macro_cache.db      # SQLiteキャッシュ・トラッキング用データベース
├── src/
│   ├── __init__.py
│   ├── config.py           # 設定ファイルの読み込み・環境変数制御
│   ├── ingestion/          # FRED・市場データ取得クライアント
│   ├── signal/             # マクロシグナルの検出ロジック
│   ├── scoring/            # セクター別スコアリングマトリクス
│   ├── evaluation/         # 個別銘柄の総合評価および予測トラッカー
│   └── ui/                 # PySide6 GUI ウィンドウおよびコンポーネント
└── tests/                  # 単体テストコード (pytest)
```

---

## セットアップ手順

### 1. 仮想環境の作成とライブラリのインストール
```bash
# 仮想環境の作成
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 2. 設定ファイルの準備
プロジェクトルートにある `config.toml` に、ご自身のFRED APIキーと分析対象のティッカーシンボルを設定します。

```toml
[api]
fred_api_key = "YOUR_FRED_API_KEY"

[settings]
tickers = [
    "7203.T",  # トヨタ自動車
    "9984.T",  # ソフトバンクグループ
    "6758.T",  # ソニーグループ
    # ...他銘柄を追加
]

[cache]
enable_cache = true
cache_db_path = "data/macro_cache.db"
```
*※ `FRED_API_KEY` は環境変数としてエクスポート（`export FRED_API_KEY="..."`）することでも適用可能です。*

---

## 実行方法

### デスクトップGUIの起動
```bash
python main.py
```

### CLIモードでの起動 (非GUI環境/バッチ実行)
```bash
python main.py --cli
```

---

## テストの実行

`pytest` を使用して、各モジュールのテストスイートを実行します。

```bash
# テストの実行
pytest tests/

# 詳細ログ付きで実行する場合
pytest -v tests/
```
