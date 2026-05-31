import sys
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QSplitter,
    QProgressBar, QHeaderView, QFrame, QScrollArea, QTextEdit,
    QTabWidget, QComboBox
)
from PySide6.QtGui import QFont, QColor, QBrush

from ..config import load_config
from ..ingestion.fred_client import FredClient
from ..ingestion.market_data import MarketDataClient
from ..signal.detector import SignalDetector
from ..scoring.impact_matrix import ImpactScorer
from ..evaluation.evaluator import StockEvaluator
from ..evaluation.tracker import PredictionTracker

# Modern Dark Theme Stylesheet (QSS)
DARK_STYLE = """
QMainWindow {
    background-color: #0f172a;
}
QWidget {
    color: #e2e8f0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}
QFrame#sidebar {
    background-color: #1e293b;
    border-right: 1px solid #334155;
}
QFrame#main_container {
    background-color: #0f172a;
}
QFrame#card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
}
QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #38bdf8;
    margin-bottom: 15px;
}
QLabel#section_header {
    font-size: 14px;
    font-weight: bold;
    color: #94a3b8;
    margin-top: 10px;
    margin-bottom: 5px;
}
QPushButton#primary_btn {
    background-color: #0284c7;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 15px;
    font-weight: bold;
}
QPushButton#primary_btn:hover {
    background-color: #0369a1;
}
QPushButton#primary_btn:pressed {
    background-color: #075985;
}
QTableWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    gridline-color: #334155;
    selection-background-color: #0f172a;
    selection-color: #38bdf8;
}
QTableWidget::item {
    padding: 8px;
}
QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 8px;
    border: none;
    font-weight: bold;
}
QProgressBar {
    border: 1px solid #334155;
    border-radius: 4px;
    text-align: center;
    background-color: #0f172a;
    color: #e2e8f0;
}
QProgressBar::chunk {
    background-color: #0284c7;
    border-radius: 3px;
}
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #475569;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #64748b;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QTextEdit#details_box {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #cbd5e1;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #0f172a;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: bold;
}
QTabBar::tab:hover {
    background-color: #334155;
    color: #e2e8f0;
}
QTabBar::tab:selected {
    background-color: #0f172a;
    color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
}
QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e2e8f0;
    min-width: 120px;
}
QComboBox::drop-down {
    border: none;
}
"""

class PipelineWorker(QThread):
    """
    QThread worker to run the async data ingestion, signal detection,
    and stock evaluation pipeline in the background.
    """
    finished = Signal(dict)
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, tickers: List[str], fred_api_key: str):
        super().__init__()
        self.tickers = tickers
        self.fred_api_key = fred_api_key

    def run(self):
        # Create a new event loop for this thread to handle async calls
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            self.progress.emit("Connecting to API clients...")
            fred_client = FredClient(api_key=self.fred_api_key)
            market_client = MarketDataClient()
            
            # 1. Ingest FRED data
            self.progress.emit("Downloading macroeconomic indicators from FRED...")
            raw_macro = {}
            series_ids = ["DGS10", "DGS2", "CPIAUCSL", "DCOILWTICO", "DEXJPUS"]
            
            # Fetch FRED data asynchronously in the event loop
            async def fetch_all_fred():
                tasks = {}
                for sid in series_ids:
                    tasks[sid] = fred_client.fetch_series_observations(sid)
                return {sid: await task for sid, task in tasks.items()}
                
            raw_macro = loop.run_until_complete(fetch_all_fred())
            
            # 2. Ingest Stock Valuation metrics
            self.progress.emit(f"Retrieving stock valuation metrics for {len(self.tickers)} tickers...")
            stock_metrics = []
            
            async def fetch_all_stocks():
                tasks = [market_client.fetch_stock_metrics(t) for t in self.tickers]
                return await asyncio.gather(*tasks)
                
            stock_metrics = loop.run_until_complete(fetch_all_stocks())
            
            # Close connection sessions
            loop.run_until_complete(fred_client.close())
            
            # 3. Detect signals
            self.progress.emit("Analyzing macro economic signals...")
            detector = SignalDetector()
            active_signals = detector.detect_signals(raw_macro)
            
            # 4. Score industry impacts
            self.progress.emit("Calculating sector macro scores...")
            scorer = ImpactScorer()
            sector_scores = scorer.calculate_sector_scores(active_signals)
            
            # 5. Evaluate stocks
            self.progress.emit("Evaluating stock ranks...")
            evaluator = StockEvaluator()
            evaluated_stocks = evaluator.evaluate_stocks(stock_metrics, sector_scores)
            
            # Package and emit results
            results = {
                "active_signals": active_signals,
                "sector_scores": sector_scores,
                "evaluated_stocks": evaluated_stocks,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.finished.emit(results)
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Pipeline run failed")
            self.error.emit(str(e))
        finally:
            loop.close()


class UpdatePricesWorker(QThread):
    """
    QThread worker to run yfinance stock updates for verification in the background.
    """
    finished = Signal(tuple) # (updated_count, error_count)
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, tracker: PredictionTracker):
        super().__init__()
        self.tracker = tracker

    def run(self):
        # Create a new event loop for this thread to handle async calls
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            self.progress.emit("Connecting to yfinance and fetching prices...")
            updated_count, errors = loop.run_until_complete(self.tracker.update_prices())
            self.finished.emit((updated_count, errors))
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Update prices run failed")
            self.error.emit(str(e))
        finally:
            loop.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Engine - Verification Dashboard")
        self.resize(1250, 800)
        self.setStyleSheet(DARK_STYLE)
        
        # Load configuration
        self.config = load_config()
        self.tickers = self.config.get("settings", {}).get("tickers", [])
        self.fred_api_key = self.config.get("api", {}).get("fred_api_key", "")
        
        # State storage
        self.current_results = {}
        self.tracker = PredictionTracker()
        
        self._init_ui()
        
        # Load verification data on start
        self.load_verification_data()
        
        # Run pipeline on startup
        self.run_pipeline()

    def _init_ui(self):
        # Create QTabWidget as central widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # TAB 1: SCREENER (Original UI)
        screener_tab = QWidget()
        screener_layout = QVBoxLayout(screener_tab)
        screener_layout.setContentsMargins(0, 0, 0, 0)
        
        # Base Splitter
        main_splitter = QSplitter(Qt.Horizontal)
        screener_layout.addWidget(main_splitter)
        
        # Sidebar Left
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 15)
        
        app_title = QLabel("Macro Engine ⚙️")
        app_title.setObjectName("title")
        sidebar_layout.addWidget(app_title)
        
        sidebar_layout.addWidget(QLabel("Macro Signals", objectName="section_header"))
        
        # Scroll Area for signals
        self.signals_scroll = QScrollArea()
        self.signals_scroll.setWidgetResizable(True)
        self.signals_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.signals_widget = QWidget()
        self.signals_widget.setStyleSheet("background: transparent;")
        self.signals_layout = QVBoxLayout(self.signals_widget)
        self.signals_layout.setAlignment(Qt.AlignTop)
        self.signals_scroll.setWidget(self.signals_widget)
        sidebar_layout.addWidget(self.signals_scroll)
        
        # Sidebar bottom action
        self.refresh_btn = QPushButton("Run Screening", objectName="primary_btn")
        self.refresh_btn.clicked.connect(self.run_pipeline)
        sidebar_layout.addWidget(self.refresh_btn)
        
        # Sidebar status label
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sidebar_layout.addWidget(self.status_lbl)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        sidebar_layout.addWidget(self.progress_bar)
        
        # Main Area Right (Splitter inside main container)
        right_container = QFrame()
        right_container.setObjectName("main_container")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(20, 20, 20, 20)
        
        # Summary Header Panel
        header_panel = QFrame(objectName="card")
        header_layout = QHBoxLayout(header_panel)
        header_layout.setContentsMargins(15, 12, 15, 12)
        
        self.stat_buy = QLabel("<b>BUY:</b> 0")
        self.stat_buy.setStyleSheet("color: #10b981; font-size: 14px;")
        self.stat_watch = QLabel("<b>WATCH:</b> 0")
        self.stat_watch.setStyleSheet("color: #f59e0b; font-size: 14px;")
        self.stat_avoid = QLabel("<b>AVOID:</b> 0")
        self.stat_avoid.setStyleSheet("color: #ef4444; font-size: 14px;")
        self.last_update_lbl = QLabel("Last Updated: Never")
        self.last_update_lbl.setStyleSheet("color: #64748b;")
        
        header_layout.addWidget(self.stat_buy)
        header_layout.addWidget(self.stat_watch)
        header_layout.addWidget(self.stat_avoid)
        header_layout.addStretch()
        header_layout.addWidget(self.last_update_lbl)
        right_layout.addWidget(header_panel)
        
        # Splitter between Table and Detail box
        content_splitter = QSplitter(Qt.Vertical)
        right_layout.addWidget(content_splitter)
        
        # Table of Stock Rankings
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Ticker", "Name", "Sector", "Price", 
            "PER", "PBR", "Macro Score", "Combined Score", "Decision"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.display_stock_details)
        content_splitter.addWidget(self.table)
        
        # Detail Panel (Rationale and Sector impact)
        detail_panel = QFrame(objectName="card")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(15, 15, 15, 15)
        
        detail_layout.addWidget(QLabel("Stock Evaluation & Sector Breakdown", objectName="section_header"))
        
        self.detail_box = QTextEdit()
        self.detail_box.setObjectName("details_box")
        self.detail_box.setReadOnly(True)
        self.detail_box.setPlaceholderText("Select a stock to view details and macroeconomic factors.")
        detail_layout.addWidget(self.detail_box)
        
        content_splitter.addWidget(detail_panel)
        
        # Set splitter sizes
        main_splitter.addWidget(sidebar)
        main_splitter.addWidget(right_container)
        main_splitter.setSizes([300, 900])
        content_splitter.setSizes([450, 200])
        
        self.tabs.addTab(screener_tab, "Screener (スクリーナー)")
        
        # TAB 2: VERIFICATION BOARD (自己検証ボード)
        self.ver_tab = QWidget()
        self.ver_layout = QVBoxLayout(self.ver_tab)
        self.ver_layout.setContentsMargins(20, 20, 20, 20)
        
        # Verification KPI Header Panel
        ver_kpi_panel = QFrame(objectName="card")
        ver_kpi_layout = QHBoxLayout(ver_kpi_panel)
        ver_kpi_layout.setContentsMargins(20, 15, 20, 15)
        
        self.kpi_overall_hit = QLabel("<b>Overall Hit Rate:</b> --%")
        self.kpi_overall_hit.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        
        self.kpi_buy_perf = QLabel("<b>BUY Win Rate:</b> --% (Avg Return: --%)")
        self.kpi_buy_perf.setStyleSheet("font-size: 14px; color: #10b981;")
        
        self.kpi_avoid_perf = QLabel("<b>AVOID Win Rate:</b> --% (Avg Return: --%)")
        self.kpi_avoid_perf.setStyleSheet("font-size: 14px; color: #ef4444;")
        
        self.kpi_total_tracked = QLabel("<b>Total Predictions:</b> 0")
        self.kpi_total_tracked.setStyleSheet("font-size: 14px; color: #94a3b8;")
        
        ver_kpi_layout.addWidget(self.kpi_overall_hit)
        ver_kpi_layout.addSpacing(40)
        ver_kpi_layout.addWidget(self.kpi_buy_perf)
        ver_kpi_layout.addSpacing(40)
        ver_kpi_layout.addWidget(self.kpi_avoid_perf)
        ver_kpi_layout.addStretch()
        ver_kpi_layout.addWidget(self.kpi_total_tracked)
        
        self.ver_layout.addWidget(ver_kpi_panel)
        
        # Filter & Action Control Panel
        filter_panel = QHBoxLayout()
        filter_panel.setContentsMargins(0, 10, 0, 10)
        
        filter_panel.addWidget(QLabel("Decision Filter:"))
        self.filter_decision = QComboBox()
        self.filter_decision.addItems(["All", "BUY", "WATCH", "AVOID"])
        self.filter_decision.currentTextChanged.connect(self.on_filter_changed)
        filter_panel.addWidget(self.filter_decision)
        
        filter_panel.addSpacing(20)
        
        filter_panel.addWidget(QLabel("Status Filter:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["All", "Hit", "Miss", "Pending"])
        self.filter_status.currentTextChanged.connect(self.on_filter_changed)
        filter_panel.addWidget(self.filter_status)
        
        filter_panel.addStretch()
        
        self.ver_refresh_btn = QPushButton("Verify & Update Prices", objectName="primary_btn")
        self.ver_refresh_btn.clicked.connect(self.verify_predictions)
        filter_panel.addWidget(self.ver_refresh_btn)
        
        self.ver_layout.addLayout(filter_panel)
        
        # Verification History Table
        self.ver_table = QTableWidget()
        self.ver_table.setColumnCount(11)
        self.ver_table.setHorizontalHeaderLabels([
            "Prediction Date", "Ticker", "Name", "Decision", 
            "Start Price", "Current Price", "Return (%)", "Status",
            "Macro", "Valuation", "Combined"
        ])
        self.ver_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ver_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ver_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ver_table.verticalHeader().setVisible(False)
        self.ver_layout.addWidget(self.ver_table)
        
        self.tabs.addTab(self.ver_tab, "Verification Board (自己検証ボード)")

    def run_pipeline(self):
        """Spawns the background worker to execute the quant pipeline."""
        self.refresh_btn.setEnabled(False)
        self.status_lbl.setText("Starting pipeline...")
        self.progress_bar.setRange(0, 0) # Indeterminate progress
        self.progress_bar.show()
        
        self.worker = PipelineWorker(self.tickers, self.fred_api_key)
        self.worker.progress.connect(self.on_pipeline_progress)
        self.worker.finished.connect(self.on_pipeline_finished)
        self.worker.error.connect(self.on_pipeline_error)
        self.worker.start()

    @Slot(str)
    def on_pipeline_progress(self, msg: str):
        self.status_lbl.setText(msg)

    @Slot(str)
    def on_pipeline_error(self, err_msg: str):
        self.status_lbl.setText(f"Error: {err_msg}")
        self.refresh_btn.setEnabled(True)
        self.progress_bar.hide()

    @Slot(dict)
    def on_pipeline_finished(self, results: dict):
        self.current_results = results
        self.refresh_btn.setEnabled(True)
        self.progress_bar.hide()
        self.status_lbl.setText("Pipeline run completed successfully.")
        
        # Log to tracker database
        if "evaluated_stocks" in results:
            self.tracker.log_predictions(results["evaluated_stocks"])
            self.load_verification_data()
            
        # Update timestamp
        self.last_update_lbl.setText(f"Last Updated: {results['timestamp']}")
        
        # 1. Update active macro signals sidebar
        # Clear old signals layout
        while self.signals_layout.count():
            item = self.signals_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        signals = results["active_signals"]
        for sig_name, sig_info in signals.items():
            if sig_info.get("active"):
                lbl = QLabel(f"🟢 {sig_name}\n   <font color='#94a3b8'>{sig_info['description']}</font>")
                lbl.setWordWrap(True)
                lbl.setStyleSheet("background-color: #0f172a; border-radius: 4px; padding: 6px; margin-bottom: 5px; border: 1px solid #1e293b;")
                self.signals_layout.addWidget(lbl)
                
        # If no active signals
        if not any(v.get("active") for v in signals.values()):
            self.signals_layout.addWidget(QLabel("No active macro signals.", styleSheet="color: #64748b;"))

        # 2. Update stock table
        stocks = results["evaluated_stocks"]
        self.table.setRowCount(len(stocks))
        
        buy_count = 0
        watch_count = 0
        avoid_count = 0
        
        for row_idx, stock in enumerate(stocks):
            decision = stock["decision"]
            if decision == "BUY":
                buy_count += 1
            elif decision == "WATCH":
                watch_count += 1
            else:
                avoid_count += 1
                
            self.table.setItem(row_idx, 0, QTableWidgetItem(stock["ticker"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(stock["name"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(stock["sector"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"{stock['price']:,.1f}"))
            
            # Highlight valuation
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{stock['per']:.1f}"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(f"{stock['pbr']:.2f}"))
            
            # Macro score
            macro_item = QTableWidgetItem(f"{stock['macro_score']:+.1f}")
            if stock["macro_score"] > 0:
                macro_item.setForeground(QBrush(QColor("#10b981"))) # green
            elif stock["macro_score"] < 0:
                macro_item.setForeground(QBrush(QColor("#ef4444"))) # red
            self.table.setItem(row_idx, 6, macro_item)

            # Combined score
            comb_item = QTableWidgetItem(f"{stock['combined_score']:+.1f}")
            comb_item.setFont(QFont("Segoe UI", weight=QFont.Bold))
            self.table.setItem(row_idx, 7, comb_item)

            # Decision with colored badges
            dec_item = QTableWidgetItem(decision)
            dec_item.setFont(QFont("Segoe UI", weight=QFont.Bold))
            if decision == "BUY":
                dec_item.setForeground(QBrush(QColor("#10b981")))
            elif decision == "WATCH":
                dec_item.setForeground(QBrush(QColor("#f59e0b")))
            else:
                dec_item.setForeground(QBrush(QColor("#ef4444")))
            self.table.setItem(row_idx, 8, dec_item)
            
        # Update summary stats labels
        self.stat_buy.setText(f"<b>BUY:</b> {buy_count}")
        self.stat_watch.setText(f"<b>WATCH:</b> {watch_count}")
        self.stat_avoid.setText(f"<b>AVOID:</b> {avoid_count}")
        
        # Select first item to trigger detail display
        if stocks:
            self.table.selectRow(0)

    @Slot()
    def display_stock_details(self):
        """Displays rich text details of the selected stock in the bottom panel."""
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges or not self.current_results:
            return
            
        row_idx = selected_ranges[0].topRow()
        stocks = self.current_results.get("evaluated_stocks", [])
        if row_idx >= len(stocks):
            return
            
        stock = stocks[row_idx]
        sector = stock["sector"]
        sector_info = self.current_results.get("sector_scores", {}).get(sector, {"score": 0.0, "breakdown": []})
        
        # Build HTML detail description
        html = f"""
        <h2><b>{stock['name']} ({stock['ticker']})</b></h2>
        <p><b>Sector:</b> {sector} | <b>Price:</b> ¥{stock['price']:,.1f}</p>
        <p><b>Valuation Metrics:</b> PER: {stock['per']:.1f} ({stock['valuation_notes']}) | PBR: {stock['pbr']:.2f}</p>
        <hr/>
        <h3><b>Investment Summary</b></h3>
        <p><b>Decision:</b> <font color="{'#10b981' if stock['decision'] == 'BUY' else '#f59e0b' if stock['decision'] == 'WATCH' else '#ef4444'}"><b>{stock['decision']}</b></font> (Combined Score: {stock['combined_score']:+.1f})</p>
        <p><b>Rationale:</b> {stock['rationale']}</p>
        <hr/>
        <h3><b>Industry Macroeconomic Drivers ({sector} Score: {stock['macro_score']:+.1f})</b></h3>
        """
        
        if sector_info["breakdown"]:
            html += "<ul>"
            for b in sector_info["breakdown"]:
                color = "#10b981" if b["impact"] > 0 else "#ef4444"
                html += f"""
                <li>
                    <b>{b['signal']}</b>: 
                    <font color="{color}"><b>{b['impact']:+d} points</b></font> <br/>
                    <i>{b['description']}</i>
                </li>
                """
            html += "</ul>"
        else:
            html += "<p>No active macroeconomic triggers directly impacting this sector.</p>"
            
        self.detail_box.setHtml(html)

    # === VERIFICATION BOARD METHODS ===
    
    def load_verification_data(self):
        """Loads and filters prediction history, updates KPI labels and populates the history table."""
        dec_filter = self.filter_decision.currentText()
        stat_filter = self.filter_status.currentText()
        
        # 1. Update KPI Labels
        kpis = self.tracker.calculate_kpis()
        self.kpi_overall_hit.setText(f"<b>Overall Hit Rate:</b> {kpis['overall_hit_rate']:.1f}%")
        self.kpi_buy_perf.setText(f"<b>BUY Hit Rate:</b> {kpis['buy_hit_rate']:.1f}% (Avg Return: {kpis['buy_avg_return']:+.2f}%)")
        self.kpi_avoid_perf.setText(f"<b>AVOID Hit Rate:</b> {kpis['avoid_hit_rate']:.1f}% (Avg Return: {kpis['avoid_avg_return']:+.2f}%)")
        self.kpi_total_tracked.setText(f"<b>Total Predictions:</b> {kpis['total_tracked']}")
        
        # 2. Populate History Table
        history = self.tracker.get_history(decision_filter=dec_filter, status_filter=stat_filter)
        self.ver_table.setRowCount(len(history))
        
        for row_idx, item in enumerate(history):
            self.ver_table.setItem(row_idx, 0, QTableWidgetItem(item["prediction_date"]))
            self.ver_table.setItem(row_idx, 1, QTableWidgetItem(item["ticker"]))
            self.ver_table.setItem(row_idx, 2, QTableWidgetItem(item["name"]))
            
            # Decision item with color
            dec = item["predicted_decision"]
            dec_item = QTableWidgetItem(dec)
            dec_item.setFont(QFont("Segoe UI", weight=QFont.Bold))
            if dec == "BUY":
                dec_item.setForeground(QBrush(QColor("#10b981")))
            elif dec == "WATCH":
                dec_item.setForeground(QBrush(QColor("#f59e0b")))
            else:
                dec_item.setForeground(QBrush(QColor("#ef4444")))
            self.ver_table.setItem(row_idx, 3, dec_item)
            
            # Prices
            self.ver_table.setItem(row_idx, 4, QTableWidgetItem(f"{item['start_price']:,.1f}"))
            curr_price = item["current_price"]
            curr_price_str = f"{curr_price:,.1f}" if curr_price is not None else "--"
            self.ver_table.setItem(row_idx, 5, QTableWidgetItem(curr_price_str))
            
            # Return pct with color
            ret_pct = item["return_pct"]
            ret_val = ret_pct if ret_pct is not None else 0.0
            ret_item = QTableWidgetItem(f"{ret_val:+.2f}%")
            if ret_val > 0:
                ret_item.setForeground(QBrush(QColor("#10b981")))
            elif ret_val < 0:
                ret_item.setForeground(QBrush(QColor("#ef4444")))
            self.ver_table.setItem(row_idx, 6, ret_item)
            
            # Status badge
            status = item["hit_status"]
            status_item = QTableWidgetItem(status)
            status_item.setFont(QFont("Segoe UI", weight=QFont.Bold))
            if status == "Hit":
                status_item.setText("Hit 🟢")
                status_item.setForeground(QBrush(QColor("#10b981")))
            elif status == "Miss":
                status_item.setText("Miss 🔴")
                status_item.setForeground(QBrush(QColor("#ef4444")))
            else:
                status_item.setText("Pending ⏳")
                status_item.setForeground(QBrush(QColor("#94a3b8")))
            self.ver_table.setItem(row_idx, 7, status_item)
            
            # Score details
            self.ver_table.setItem(row_idx, 8, QTableWidgetItem(f"{item['macro_score']:+.1f}"))
            self.ver_table.setItem(row_idx, 9, QTableWidgetItem(f"{item['valuation_score']:+.1f}"))
            self.ver_table.setItem(row_idx, 10, QTableWidgetItem(f"{item['combined_score']:+.1f}"))

    @Slot(str)
    def on_filter_changed(self, text: str):
        self.load_verification_data()

    def verify_predictions(self):
        """Spawns the background worker to fetch current prices and update statuses."""
        self.ver_refresh_btn.setEnabled(False)
        self.ver_refresh_btn.setText("Updating Prices...")
        self.status_lbl.setText("Updating verification database...")
        
        self.update_worker = UpdatePricesWorker(self.tracker)
        self.update_worker.progress.connect(self.on_verify_progress)
        self.update_worker.finished.connect(self.on_verify_finished)
        self.update_worker.error.connect(self.on_verify_error)
        self.update_worker.start()

    @Slot(str)
    def on_verify_progress(self, msg: str):
        self.status_lbl.setText(msg)

    @Slot(str)
    def on_verify_error(self, err_msg: str):
        self.status_lbl.setText(f"Update Error: {err_msg}")
        self.ver_refresh_btn.setEnabled(True)
        self.ver_refresh_btn.setText("Verify & Update Prices")

    @Slot(tuple)
    def on_verify_finished(self, stats: tuple):
        updated, errors = stats
        self.ver_refresh_btn.setEnabled(True)
        self.ver_refresh_btn.setText("Verify & Update Prices")
        self.status_lbl.setText(f"Verification updated: {updated} records updated, {errors} errors.")
        self.load_verification_data()


def run_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
