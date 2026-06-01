# 📊 G20マクロ＆株式評価ハブ ユーザー操作ガイド (HOWTO)

本ダッシュボードは、マクロ経済の動向（インフレ、金利、為替など）を読み解き、それが保有株や監視銘柄にどのような影響を与えるかをビジュアルで確認・分析するための個人投資家向けツールです。

このガイドでは、ツールの主な機能や、**ご自身の保有株（ポートフォリオ）のCSVをアップロードして分析する機能**の使い方について詳しく解説します。

---

## 🧭 主な機能と使い方

ダッシュボードは、主に以下の4つの機能で構成されています。左側のサイドバーメニュー（Navigation）で切り替えることができます。

### 1. 🔍 マーケットスクリーナー (Market Screener)
世界主要市場（日本 🇯🇵、米国 🇺🇸、ユーロ圏 🇪🇺 など）のマクロ経済指標と、個別銘柄のバリュエーションを組み合わせて自動でスクリーニング（評価）します。

* **使い方**:
  1. 上部の国旗ボタンから分析したい市場（日本、米国など）を選択します。
  2. サイドバーの「**📋 銘柄スクリーニングリスト**」に対象としたいティッカーを入力して「**🔄 データを再読込して再評価**」をクリックします。
  3. 自動でデータが取得され、評価結果（`BUY`/`WATCH`/`AVOID`）と、その判定に至ったマクロ要因・バリュエーション要因の「判断理由（Rationale）」が表形式で出力されます。
  4. 表の下部にある「**詳細分析パネル**」で特定の銘柄を選択すると、どのマクロ指標がその業界にどうプラス・マイナスに影響しているかの内訳（ブレイクダウン）がビジュアルで確認できます。

---

### 2. 💼 保有ポートフォリオ・マクロ適合度分析 (My Portfolio Macro Analyzer)
ご自身が実際に証券会社で保有している銘柄のCSVファイルをアップロードし、現在のマクロ経済環境に対するポートフォリオ全体の「マクロ適合スコア」や「潜在的リスク」を診断する最も強力な機能です。

* **対応している証券会社・CSV形式**:
  - **楽天証券**、**SBI証券**（日本株・米国株の保有資産CSVエクスポートに対応）
  - **Interactive Brokers (IBKR)**、**Charles Schwab**、**Fidelity** などの海外証券会社の残高報告書CSV
  - **カスタムCSVテンプレート**（CSVファイルを持っていない方向けに、画面上からサンプルテンプレート `sample_portfolio.csv` をダウンロードできます）

* **利用手順**:
  1. 画面中央の「ポートフォリオ分析」セクションにあるアップロードエリアに、証券会社からエクスポートしたCSVファイルをドラッグ＆ドロップします。
  2. 読み込みが成功すると、以下の分析結果が瞬時に出力されます：
     - **加重平均マクロスコア**: ポートフォリオの保有比率に応じた、マクロ経済との適合度（追い風か逆風か）の総合スコア。
     - **🚨 マクロ逆風リスクの検出**: 現在のマクロ指標（金利上昇やインフレなど）が、保有している特定の銘柄（不動産やハイテクなど）に対して逆風となっている場合の警告。
     - **⚖️ セクターリバランス提案**: 現在の環境下で、どのセクターの比率を減らし（例: 金利上昇局面での不動産）、どのセクターを増やすべきか（例: 金利上昇局面での銀行）の具体的なアドバイス。
  3. 分析結果は、画面下部の「**📥 ポートフォリオ診断レポートの出力 (PDF/HTML)**」ボタンからローカルに保存したり印刷したりできます。

* **🔒 セキュリティとプライバシーについて**:
  - アップロードされたCSVファイルは、**完全にあなたのブラウザ内（セッションメモリ）でのみ処理されます**。
  - データが当システム側のサーバーに送信されたり保存されたりすることは一切ありません。ブラウザのタブを閉じると、アップロードした情報は即座に消去されます。

---

### 3. 🎮 仮想取引（ペーパートレード）ハブ (Paper Trading Hub)
マクロ経済のシナリオに基づいて、仮想の資金を使ってシミュレーション投資を行うことができるサンドボックス環境です。

* **用意されている5つの口座**:
  - **📈 Macro Tailwind Focus**（マクロの追い風銘柄に特化した口座）
  - **🛡️ Defensive & Income**（高配当・ディフェンシブ重視の口座）
  - **🚀 Aggressive Growth**（成長株メインの口座）
  - **💎 Long-Term Value**（割安バリュー株メインの口座）
  - **🧪 Sandbox**（自由な検証用の口座）

* **使い方**:
  1. 取引したい口座を切り替えます。
  2. 取引フォームに「ティッカー」「売買区分 (BUY/SELL)」「数量」を入力して送信します（単価を0にすると、現在のリアルタイム株価を自動取得します）。
  3. 保有ポジションと、現在のポートフォリオ全体の「マクロスコア」「含み損益」がリアルタイムで更新されます。
  4. 「**📥 口座データを保存 (JSON)**」ボタンを押すことで、取引状態をローカルファイルとして保存でき、次回アクセス時に「**口座データを読み込む (JSON)**」から続きを実行できます。

---

### 4. 📊 過去の予測実績 (Track Record)

マクロ評価エンジンが過去に出した予測（BUY/AVOIDなど）が、その後の実際の市場でどれだけ当たっていたか（的中率・リターン）を統計的に検証・公開する画面です。

* **使い方**:
  1. ナビゲーションメニューから「過去の予測実績」を選択します。
  2. 「**🔄 最新株価で検証・更新**」をクリックすると、データベース内の過去の予測判定時の株価と現在の最新株価を比較し、予測が「Hit（成功）」か「Miss（失敗）」かを自動計算します。
  3. 全体の的中率や、BUY・AVOID別の成功率、保有期間ごとの平均リターンを確認し、エンジンの精度を検証できます。

---

## 5. 🔔 自動マクロイベント通知機能 / Automated Event Alerts

G20マクロ指標の突変（インフレ高進、長期金利急騰、原油ショックなど）が発生すると、クラウドに保存された保有ポートフォリオを自動的に再評価し、あらかじめ設定された条件に従って即座にアラート通知を送信します。

When a G20 macroeconomic event is detected (e.g., CPI/inflation shock, rate spike, energy shock), the system automatically re-evaluates all saved portfolios and dispatches real-time alert reports based on your notification preferences.

### ⚙️ 設定手順 / How to Configure Alerts:
1. **アラート機能の有効化 (Enable Alert Functionality)**:
   - サイドバー最上部にあるコントロール機能から **自動監視 (Active Monitoring)** が有効化されていることを確認します。
   - Ensure **Active Monitoring** is enabled in the sidebar configuration controls.
  2. **通知チャンネルの有効化 (Enable Notification Channels)**:
   - **Eメール通知 (Email Alerts)**: 有効にすると、マクロスコアの変動や個別銘柄の評価判定（BUY/AVOID）の変更を記した詳細なHTMLメールレポートが自動送信されます。ローカル開発環境では、`data/sent_emails/` ディレクトリ配下にモックHTMLファイルとして保存されます。
   - **Telegram通知 (Telegram Alerts)**: 有効にして、Telegram BotトークンとチャットIDを設定すると、マクロの追い風・逆風や推奨リバランスのアクションガイドが直接TelegramにHTMLフォーマットで届きます。
   - *Email*: Receives a responsive HTML dashboard displaying your weighted macro score and sector-by-sector ratings. (Saved as mock HTML files under `data/sent_emails/` during development).
   - *Telegram*: Receives a formatted HTML message summarizing your portfolio score, rating adjustments, and suggested action guidelines.
3. **通知フィルター条件の設定 (Alert Filtering Parameters)**:
   - **最小深刻度 (Minimum Severity)**: 通知対象とするイベントの重要度（1 = 軽微, 2 = 中程度, 3 = 重大）をスライダーで調節できます。
   - **イベント選択 (Event Types)**: インフレ(CPI)、金利政策(FOMC)、GDP増減速、長期金利急変(Rate Hike)、原油急騰(Oil Spike)、為替ショック(FX Shock)から、受け取るイベントの種類を選択できます。
   - **通知頻度 (Frequency)**: 「即時 (Instant)」「日次要約 (Daily Digest)」「週次要約 (Weekly Digest)」から設定可能です。
   - Configure your *Minimum Severity* threshold, check specific *Event Types*, and choose the *Digest Frequency* (Instant, Daily, or Weekly).
4. **アラート送信ログの確認 (View Dispatch Logs)**:
   - ナビゲーションメニューの「Alert Settings」画面下部では、過去に送信された通知ログ（送信先チャンネル、配信ステータス、タイムスタンプ）をデータベース履歴から確認できます。
   - You can inspect recent alerts and status history directly inside the **Alert Settings** page under the dispatch logs table.
