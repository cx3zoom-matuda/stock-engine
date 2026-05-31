import sys
import argparse
import asyncio
import logging
from typing import List

from src.config import load_config
from src.ingestion.fred_client import FredClient
from src.ingestion.market_data import MarketDataClient
from src.signal.detector import SignalDetector
from src.scoring.impact_matrix import ImpactScorer
from src.evaluation.evaluator import StockEvaluator
from src.evaluation.tracker import PredictionTracker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("macro_engine")

async def run_cli_pipeline(tickers: List[str], fred_api_key: str):
    """Executes the complete screening pipeline in the terminal and prints the results."""
    logger.info("Starting Macro Engine CLI pipeline...")
    
    # 1. Ingest FRED macro data
    logger.info("Initializing FRED client and fetching indicators...")
    fred_client = FredClient(api_key=fred_api_key)
    
    series_ids = ["DGS10", "DGS2", "CPIAUCSL", "DCOILWTICO", "DEXJPUS"]
    raw_macro = {}
    for sid in series_ids:
        logger.info(f"Downloading FRED series: {sid}...")
        raw_macro[sid] = await fred_client.fetch_series_observations(sid)
    
    await fred_client.close()
    
    # 2. Ingest Stock metrics
    logger.info(f"Retrieving market valuation metrics for {len(tickers)} tickers...")
    market_client = MarketDataClient()
    stock_metrics = []
    for t in tickers:
        logger.info(f"Fetching stock metrics for {t}...")
        stock_metrics.append(await market_client.fetch_stock_metrics(t))

    # 3. Detect signals
    logger.info("Analyzing macroeconomic trends...")
    detector = SignalDetector()
    active_signals = detector.detect_signals(raw_macro)
    
    print("\n" + "="*50)
    print(" ACTIVE MACROECONOMIC SIGNALS")
    print("="*50)
    any_active = False
    for sig, info in active_signals.items():
        if info["active"]:
            print(f"🟢 {sig:25} | {info['description']}")
            any_active = True
    if not any_active:
        print("No active macro signals detected (Neutral environment).")
    print("="*50 + "\n")

    # 4. Score industry impacts
    logger.info("Computing macro impact scores on industries...")
    scorer = ImpactScorer()
    sector_scores = scorer.calculate_sector_scores(active_signals)

    # 5. Evaluate stocks
    logger.info("Calculating stock scores and rankings...")
    evaluator = StockEvaluator()
    evaluated_stocks = evaluator.evaluate_stocks(stock_metrics, sector_scores)

    # Output results in a structured text layout
    print("="*110)
    print(f"{'TICKER':8} | {'NAME':25} | {'SECTOR':30} | {'PRICE':8} | {'PER':5} | {'PBR':5} | {'MACRO':5} | {'SCORE':5} | {'DECISION':8}")
    print("="*110)
    
    for s in evaluated_stocks:
        decision_str = s["decision"]
        if decision_str == "BUY":
            dec_col = f"\033[92m{decision_str:8}\033[0m" # Green
        elif decision_str == "WATCH":
            dec_col = f"\033[93m{decision_str:8}\033[0m" # Yellow
        else:
            dec_col = f"\033[91m{decision_str:8}\033[0m" # Red
            
        print(f"{s['ticker']:8} | {s['name'][:25]:25} | {s['sector'][:30]:30} | {s['price']:8.1f} | {s['per']:5.1f} | {s['pbr']:5.2f} | {s['macro_score']:+5.1f} | {s['combined_score']:+5.1f} | {dec_col}")
        print(f"   Rationale: {s['rationale']}")
        print("-"*110)
        
    print(f"Completed screening at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 6. Log predictions to tracking database
    logger.info("Logging predictions to tracking database...")
    tracker = PredictionTracker()
    tracker.log_predictions(evaluated_stocks)

def main():
    parser = argparse.ArgumentParser(description="Macro Engine - Macroeconomic Stock Screener (Phase 1)")
    parser.add_argument("--cli", action="store_true", help="Run in Command Line Interface mode instead of PySide6 GUI")
    args = parser.parse_args()

    # Load configuration
    config = load_config()
    tickers = config.get("settings", {}).get("tickers", [])
    fred_api_key = config.get("api", {}).get("fred_api_key", "")

    if args.cli:
        # Run async CLI pipeline
        asyncio.run(run_cli_pipeline(tickers, fred_api_key))
    else:
        # Run PySide6 GUI
        logger.info("Initializing PySide6 desktop interface...")
        try:
            from src.ui.main_window import run_gui
            run_gui()
        except ImportError as e:
            logger.error("Could not import PySide6. Make sure to run 'pip install -r requirements.txt'")
            logger.error(f"Error details: {e}")
            logger.info("Falling back to CLI mode...")
            asyncio.run(run_cli_pipeline(tickers, fred_api_key))

if __name__ == "__main__":
    from datetime import datetime
    main()
