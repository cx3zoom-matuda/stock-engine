import sys
import json
from src.detector import EventDetector
from src.engine import RuleEngine
from src.ingestion import FredDataFetcher

def run_mvp_demo():
    print("="*60)
    print(" MACRO → INDUSTRY TRANSLATION ENGINE MVP DEMO")
    print("="*60)

    # 1. Fetch real-world macro time-series data from FRED
    print("\n[Step 1] Ingesting macroeconomic indicator time series from FRED API...")
    fetcher = FredDataFetcher()
    try:
        macro_data = fetcher.prepare_detector_inputs()
        # Add tech cycle manual triggers to combine with real FRED data
        macro_data["ai_investment_boom"] = True
        macro_data["semiconductor_capex_cycle"] = True
    except ValueError as e:
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: Failed to fetch FRED data: {e}\n")
        sys.exit(1)

    print(f"\n  * 10Y Yield Change (30 days):  {macro_data['10Y_RATE'][-1] - macro_data['10Y_RATE'][-2]:+.2f}% points (Latest: {macro_data['10Y_RATE'][-1]:.2f}%, Prev: {macro_data['10Y_RATE'][-2]:.2f}%)")
    print(f"  * Latest CPI YoY:              {macro_data['CPI_YOY'][-1]:.2f}%")
    print(f"  * Oil Price Change (30 days):  {((macro_data['OIL_PRICE'][-1] - macro_data['OIL_PRICE'][-2]) / macro_data['OIL_PRICE'][-2]) * 100:+.1f}% (${macro_data['OIL_PRICE'][-2]:.2f} -> ${macro_data['OIL_PRICE'][-1]:.2f})")
    print(f"  * USD/JPY Change (30 days):    {((macro_data['USD_JPY'][-1] - macro_data['USD_JPY'][-2]) / macro_data['USD_JPY'][-2]) * 100:+.1f}% ({macro_data['USD_JPY'][-2]:.2f} -> {macro_data['USD_JPY'][-1]:.2f})")
    print(f"  * Latest GDP YoY Growth:       {macro_data['GDP_YOY'][-1]:.2f}%")

    # 2. Execute Event Detector
    print("\n[Step 2] Running Event Detection Engine...")
    detector = EventDetector()
    active_events = detector.detect_events(macro_data)

    print("\n--- TRIGGERED MACRO EVENTS ---")
    for event in active_events:
        sev_label = "MINOR" if event["severity"] == 1 else "MODERATE" if event["severity"] == 2 else "MAJOR"
        print(f"🟢 [{sev_label}] {event['event']:25} | {event['description']}")
    print("-" * 30)

    # 3. Translate to Sector Scores using Rule Engine
    print("\n[Step 3] Applying Rule Engine Translation Matrix...")
    engine = RuleEngine()
    results = engine.calculate_industry_scores(active_events)

    # 4. Output rankings formatted as a text table
    print("\n" + "="*95)
    print(f"{'RANK':4} | {'CORE SECTOR':18} | {'SCORE':8} | {'NORMALIZED':10} | {'CONTRIBUTING FACTORS & IMPACTS'}")
    print("="*95)

    for i, item in enumerate(results["rankings"], 1):
        sector = item["sector"]
        score = item["score"]
        norm_score = item["normalized_score"]
        
        # Color code positive, negative, and neutral sectors
        if score > 0:
            score_col = f"\033[92m{score:+6.1f}\033[0m" # Green
            norm_col = f"\033[92m{norm_score:+10.4f}\033[0m"
        elif score < 0:
            score_col = f"\033[91m{score:+6.1f}\033[0m" # Red
            norm_col = f"\033[91m{norm_score:+10.4f}\033[0m"
        else:
            score_col = f"{score:6.1f}"
            norm_col = f"{norm_score:10.4f}"

        # Build list of contributions
        contributions = []
        for c in item["breakdown"]:
            contributions.append(f"{c['event']} ({c['base_weight']:+d} * {c['severity']} = {c['impact_contribution']:+d})")
        cont_str = ", ".join(contributions) if contributions else "No direct macro exposure."

        print(f"{i:4d} | {sector:18} | {score_col:8} | {norm_col:10} | {cont_str}")
        print("-" * 95)

    print("\nMacro to Industry Translation run completed successfully.\n")

if __name__ == "__main__":
    run_mvp_demo()
