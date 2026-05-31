import pytest
from src.scoring.impact_matrix import ImpactScorer
from src.evaluation.evaluator import StockEvaluator

def test_impact_scorer():
    scorer = ImpactScorer()
    
    # Enable a single signal: YEN_DEPRECIATING
    active_signals = {
        "YEN_DEPRECIATING": {
            "active": True,
            "description": "Yen weakening",
            "value": 150.0
        },
        "YIELD_INVERSION": {
            "active": False,
            "description": "",
            "value": 0.0
        }
    }
    
    sector_scores = scorer.calculate_sector_scores(active_signals)
    
    # Automobiles should get +45 points for yen depreciating
    assert sector_scores["Automobiles & Transportation"]["score"] == 45
    assert len(sector_scores["Automobiles & Transportation"]["breakdown"]) == 1
    
    # Utilities should get -40 points for yen depreciating (cost imports)
    assert sector_scores["Utilities"]["score"] == -40

def test_stock_evaluator_buy_decision():
    evaluator = StockEvaluator()
    
    # Ticker toyota is in Automobiles & Transportation (has +45 macro score)
    # PER is cheap (8.0 -> +30 valuation), PBR is cheap (0.6 -> +20 valuation)
    stock_metrics = [{
        "ticker": "7203.T",
        "name": "Toyota Motor Corp",
        "sector": "Automobiles & Transportation",
        "per": 8.0,
        "pbr": 0.6,
        "price": 2500.0
    }]
    
    sector_scores = {
        "Automobiles & Transportation": {
            "score": 45.0,
            "breakdown": []
        }
    }
    
    results = evaluator.evaluate_stocks(stock_metrics, sector_scores)
    assert len(results) == 1
    assert results[0]["decision"] == "BUY"
    assert results[0]["combined_score"] == 95.0  # 45 + 30 + 20 = 95
    assert "Strong industry macroeconomic tailwinds" in results[0]["rationale"]

def test_stock_evaluator_avoid_decision():
    evaluator = StockEvaluator()
    
    # Utilities has -40 macro score
    # PER is expensive (30 -> -15 valuation), PBR is expensive (2.5 -> -10 valuation)
    stock_metrics = [{
        "ticker": "9501.T",
        "name": "Tokyo Electric Power",
        "sector": "Utilities",
        "per": 30.0,
        "pbr": 2.5,
        "price": 800.0
    }]
    
    sector_scores = {
        "Utilities": {
            "score": -40.0,
            "breakdown": []
        }
    }
    
    results = evaluator.evaluate_stocks(stock_metrics, sector_scores)
    assert len(results) == 1
    assert results[0]["decision"] == "AVOID"
    assert results[0]["combined_score"] == -65.0  # -40 - 15 - 10 = -65
    assert "Avoid" in results[0]["rationale"]
