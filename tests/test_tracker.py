import os
import pytest
import sqlite3
from src.tracker import PredictionTracker

DB_PATH = "tests/temp_test_cache.db"

@pytest.fixture(autouse=True)
def cleanup_db():
    # Setup - delete temp DB if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    # Teardown - delete temp DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_tracker_initialization_and_seeding():
    tracker = PredictionTracker(db_path=DB_PATH)
    
    # Verify DB file is created
    assert os.path.exists(DB_PATH)
    
    # Verify it seeded data since it was empty
    history = tracker.get_history()
    assert len(history) == 6
    
    # Verify specific seeded record
    toyota = [item for item in history if item["ticker"] == "7203.T"][0]
    assert toyota["name"] == "Toyota Motor Corp"
    assert toyota["predicted_decision"] == "BUY"
    assert toyota["hit_status"] == "Hit"
    assert toyota["return_pct"] > 0

def test_kpis_calculation():
    tracker = PredictionTracker(db_path=DB_PATH)
    kpis = tracker.calculate_kpis()
    
    # Verify overall calculations
    assert kpis["total_tracked"] == 6
    assert kpis["buy_total"] == 3  # Toyota, Softbank, INPEX
    assert kpis["avoid_total"] == 2 # MUFG, NYK Line
    
    # Overall hit rate = 2 Hits / 4 Evaluated active calls = 50.0%
    assert kpis["overall_hit_rate"] == 50.0
    assert kpis["buy_hit_rate"] == 50.0
    assert kpis["avoid_hit_rate"] == 50.0

def test_log_predictions_insert_and_update():
    tracker = PredictionTracker(db_path=DB_PATH)
    
    # Initial count
    initial_count = len(tracker.get_history())
    
    # Log a new ticker
    new_stock = {
        "ticker": "6501.T",
        "name": "Hitachi",
        "sector": "electronics",
        "price": 3200.0,
        "per": 12.0,
        "pbr": 1.1,
        "macro_score": 10.0,
        "valuation_score": 15.0,
        "combined_score": 25.0,
        "decision": "BUY",
        "rationale": "Test rationale",
        "valuation_notes": "Test notes"
    }
    
    tracker.log_predictions([new_stock])
    history = tracker.get_history()
    assert len(history) == initial_count + 1
    
    hitachi_rec = [item for item in history if item["ticker"] == "6501.T"][0]
    assert hitachi_rec["predicted_decision"] == "BUY"
    assert hitachi_rec["start_price"] == 3200.0
    assert hitachi_rec["hit_status"] == "Pending"  # Should be pending initially (same day)

    # Log same ticker again to verify same-day update
    updated_stock = new_stock.copy()
    updated_stock["price"] = 3300.0
    updated_stock["decision"] = "WATCH"
    
    tracker.log_predictions([updated_stock])
    history2 = tracker.get_history()
    assert len(history2) == initial_count + 1  # Should not increase count
    
    hitachi_rec_updated = [item for item in history2 if item["ticker"] == "6501.T"][0]
    assert hitachi_rec_updated["predicted_decision"] == "WATCH"
    assert hitachi_rec_updated["start_price"] == 3300.0

def test_filtering():
    tracker = PredictionTracker(db_path=DB_PATH)
    
    # Filter by BUY
    buys = tracker.get_history(decision_filter="BUY")
    assert len(buys) == 3
    assert all(item["predicted_decision"] == "BUY" for item in buys)
    
    # Filter by Hit
    hits = tracker.get_history(status_filter="Hit")
    assert len(hits) == 2
    assert all(item["hit_status"] == "Hit" for item in hits)
    
    # Filter by BUY and Miss
    buy_misses = tracker.get_history(decision_filter="BUY", status_filter="Miss")
    assert len(buy_misses) == 1
    assert buy_misses[0]["ticker"] == "9984.T"
