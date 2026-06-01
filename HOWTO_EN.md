# 📊 G20 Macro & Stock Screener Hub User Guide (HOWTO)

This dashboard is an interactive tool for retail investors to analyze how macroeconomic shifts (inflation, interest rates, currency fluctuations, energy prices) translate into direct tailwinds or headwinds for stock holdings and watchlists.

This guide explains the key features and walks you through **uploading your own brokerage portfolio CSV file** for instant macro alignment diagnostics.

---

## 🧭 Key Features & Navigation

You can switch between the following pages using the **🧭 Navigation** selector in the sidebar:

### 1. 🔍 Market Screener & Hub
Combines real-time G20 macroeconomic data with equity valuation models (PER, PBR) to automatically screen and rank target watchlists.

*   **How to Use**:
    1.  Select your target market (e.g., United States 🇺🇸, Japan 🇯🇵, Euro Area 🇪🇺) using the country buttons at the top of the screener.
    2.  Add comma-separated tickers in the "**📋 Stock Screening List**" input in the sidebar, then click "**🔄 Reload Data & Re-Screen**".
    3.  The system pulls metrics and outputs evaluation ratings (`BUY`, `WATCH`, `AVOID`) with detailed logic reasons (Rationale).
    4.  Select a ticker in the "**🕵️ Analysis Detail Panel**" to visualize how specific macro metrics score and affect its underlying sector.

---

### 2. 💼 Portfolios Vault
Upload your actual holdings export from brokerages to calculate your portfolio's weighted "Macro Score", identify headwind risks, and get rebalancing recommendations.

*   **Supported Brokerages & Formats**:
    -   **Interactive Brokers (IBKR)**, **Charles Schwab**, and **Fidelity** exports.
    -   **Rakuten Securities** and **SBI Securities** (domestic/US stock balances) exports.
    -   **Universal CSV Template**: If you don't have a CSV, click the "**📥 Download sample_portfolio.csv**" button to get a basic template (`ticker,qty,cost`), edit it, and upload it.

*   **Steps to Analyze**:
    1.  Drag and drop your exported brokerage CSV into the file uploader.
    2.  The engine immediately parses columns and computes:
        -   **Weighted average macro score**: Overall macro alignment score weighted by position value.
        -   **🚨 Headwind risks**: Warning notifications highlighting stocks currently facing strong economic headwinds (e.g., real estate or tech in high-rate regimes).
        -   **⚖️ Sector rebalancing suggestions**: Concrete recommendations on which sectors to trim or add.
    3.  Click "**📥 Export Portfolio Review (PDF/HTML)**" to generate a printable report.

*   **🔒 Security & Privacy Notice**:
    -   Your uploaded CSV file is processed **entirely in your browser's session memory**.
    -   No data is sent to our servers, and closing the browser tab instantly deletes all information.

---

### 3. 🎮 Paper Trading Vault (Virtual Accounts)
A sandbox paper trading environment to test macro investment thesis using virtual funds.

*   **5 Preset Accounts**:
    -   **📈 Macro Tailwind Focus** (Focuses on sectors with positive macro alignment)
    -   **🛡️ Defensive & Income** (Focuses on high-yield and low-beta sectors)
    -   **🚀 Aggressive Growth** (Focuses on high-growth technology)
    -   **💎 Long-Term Value** (Focuses on undervalued, cash-rich stocks)
    -   **🧪 Sandbox** (Free experimentation)

*   **How to Use**:
    1.  Select the desired tab.
    2.  Use the execution form to input a ticker, side (BUY/SELL), and quantity (set price as 0 to auto-fetch the current market price).
    3.  Review updated holdings, macro scores, and unrealized gains/losses.
    4.  Click "**📥 Save Account (JSON)**" to back up your trades locally, and upload the file via "**Load Saved Account (JSON)**" to resume your session later.

---

### 4. 📊 Historical Accuracy (Track Record)
A transparent scorecard measuring the historical performance and accuracy of the macro-engine's stock predictions over time.

*   **How to Use**:
    1.  Go to the Historical Accuracy tab.
    2.  Click "**🔄 Verify & Update Prices**" to pull the latest stock prices from Yahoo Finance and calculate whether past logged predictions were a "Hit" or a "Miss".
    3.  Review hit rates, average returns, and historical log data.

---

### 5. 🔔 Automated Macro Event Alerts
Continuously monitors G20 macro trends and automatically pushes real-time alert notifications to your email or Telegram when economic shocks are detected.

*   **How to Configure**:
    1.  **Enable Active Monitoring**: Toggle the sidebar control setting to "Enabled (Active Alerts)" to activate background evaluations.
    2.  **Notification Channels**:
        -   **Email Alerts**: Sends a detailed HTML report to your email upon macro rating changes. In local environments, mock HTML reports are saved under `data/sent_emails/`.
        -   **Telegram Alerts**: Configure your Telegram Bot Token and Chat ID to receive instant HTML-formatted re-evaluation alerts directly on your devices.
    3.  **Filtering & Frequency**: Adjust the *Minimum Severity* slider, choose specific *Event Types* to monitor, and set the digest frequency (Instant, Daily, or Weekly).
