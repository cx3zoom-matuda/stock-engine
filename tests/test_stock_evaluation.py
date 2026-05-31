import pytest
from unittest.mock import patch
from src.fred_client import FredClient
from src.market_data import MarketDataClient
from src.evaluator import StockEvaluator

@pytest.mark.asyncio
async def test_fred_client_mock_data():
    client = FredClient(api_key=None, enable_cache=False)
    # Generate mock observations for DGS10
    obs = await client.fetch_series_observations("DGS10", observation_start="2026-01-01", observation_end="2026-01-10")
    assert len(obs) > 0
    assert "date" in obs[0]
    assert "value" in obs[0]

@pytest.mark.asyncio
async def test_market_data_client_live():
    client = MarketDataClient(enable_cache=False)
    # Fetch a live ticker (if online) or it will fallback if offline
    metrics = await client.fetch_stock_metrics("7203.T")
    assert metrics["ticker"] == "7203.T"
    assert "TOYOTA" in metrics["name"].upper()
    assert metrics["sector"] == "automobile"
    assert metrics["per"] > 0
    assert metrics["pbr"] > 0
    assert metrics["price"] > 0

@pytest.mark.asyncio
async def test_market_data_client_offline_fallback():
    client = MarketDataClient(enable_cache=False)
    # Force mock fallback by raising error in live fetch method
    with patch.object(client, "_fetch_yfinance", side_effect=RuntimeError("Offline simulated error")):
        metrics = await client.fetch_stock_metrics("7203.T")
        assert metrics["ticker"] == "7203.T"
        assert metrics["name"] == "Toyota Motor Corp"
        assert metrics["sector"] == "automobile"
        assert metrics["per"] == 9.5
        assert metrics["pbr"] == 0.85
        assert metrics["price"] == 2800.0

def test_stock_evaluator_scoring():
    evaluator = StockEvaluator()
    
    # Mock stock metrics list
    stock_metrics = [
        {
            "ticker": "7203.T",
            "name": "Toyota",
            "sector": "automobile",
            "per": 7.5,    # Undervalued PER (<= 8.0) -> +30 pts
            "pbr": 0.6,    # Asset Discount PBR (<= 0.7) -> +20 pts
            "price": 2500.0 # Total Valuation Score: +50 pts
        },
        {
            "ticker": "9984.T",
            "name": "Softbank",
            "sector": "trading_company",
            "per": 22.0,   # Overvalued PER (> 20.0) -> -15 pts
            "pbr": 2.5,    # Asset Premium PBR (> 1.8) -> -10 pts
            "price": 8000.0 # Total Valuation Score: -25 pts
        }
    ]
    
    # Mock sector scores
    sector_scores = {
        "automobile": {
            "score": 20.0, # Tailwinds
            "breakdown": []
        },
        "trading_company": {
            "score": -25.0, # Headwinds
            "breakdown": []
        }
    }
    
    evaluated = evaluator.evaluate_stocks(stock_metrics, sector_scores)
    assert len(evaluated) == 2
    
    # Check Toyota
    toyota = next(s for s in evaluated if s["ticker"] == "7203.T")
    assert toyota["decision"] == "BUY" # macro >= 15 and val >= 10
    assert toyota["valuation_score"] == 50.0
    assert toyota["macro_score"] == 20.0
    assert toyota["combined_score"] == 70.0
    
    # Check Softbank
    softbank = next(s for s in evaluated if s["ticker"] == "9984.T")
    assert softbank["decision"] == "AVOID" # macro <= -20 or val <= -25
    assert softbank["valuation_score"] == -25.0
    assert softbank["macro_score"] == -25.0
    assert softbank["combined_score"] == -50.0

def test_us_stock_evaluation():
    evaluator = StockEvaluator()
    
    stock_metrics = [
        {
            "ticker": "AAPL",
            "name": "Apple",
            "sector": "electronics",
            "per": 28.0,   # US Fair Value PER (22.0 - 30.0) -> +0 pts
            "pbr": 5.0,    # US Fair Value PBR (3.0 - 5.5) -> +0 pts
            "price": 170.0 # Total Valuation Score: +0 pts
        },
        {
            "ticker": "XOM",
            "name": "Exxon Mobil",
            "sector": "energy",
            "per": 12.0,   # US Highly Undervalued PER (<= 14.0) -> +30 pts
            "pbr": 2.2,    # US Asset Discount PBR (1.5 - 3.0) -> +10 pts
            "price": 115.0 # Total Valuation Score: +40 pts
        }
    ]
    
    sector_scores = {
        "electronics": {
            "score": 10.0,
            "breakdown": []
        },
        "energy": {
            "score": 25.0, # Strong macro tailwinds
            "breakdown": []
        }
    }
    
    evaluated = evaluator.evaluate_stocks(stock_metrics, sector_scores)
    assert len(evaluated) == 2
    
    # Check Exxon Mobil
    xom = next(s for s in evaluated if s["ticker"] == "XOM")
    assert xom["decision"] == "BUY" # macro >= 15 and val >= 10
    assert xom["valuation_score"] == 40.0
    assert xom["macro_score"] == 25.0
    
    # Check Apple
    aapl = next(s for s in evaluated if s["ticker"] == "AAPL")
    assert aapl["decision"] == "WATCH" # macro < 15 or val < 10
    assert aapl["valuation_score"] == 0.0
    assert aapl["macro_score"] == 10.0

