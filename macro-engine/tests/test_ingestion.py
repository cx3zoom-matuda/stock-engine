import pytest
import shutil
import os
import pathlib
from src.ingestion.fred_client import FredClient
from src.ingestion.market_data import MarketDataClient

@pytest.mark.asyncio
async def test_fred_client_mock_data():
    # Test without API key to trigger mock generation
    client = FredClient(api_key=None, enable_cache=False)
    
    # Fetch a standard series
    obs = await client.fetch_series_observations("DGS10", "2026-01-01", "2026-01-10")
    
    assert len(obs) > 0
    assert "date" in obs[0]
    assert "value" in obs[0]
    
    # Values should be parseable as floats
    val = float(obs[0]["value"])
    assert val > 0.0
    
    await client.close()

@pytest.mark.asyncio
async def test_market_data_client_offline_fallback():
    # Test market data metrics fallback
    client = MarketDataClient(enable_cache=False)
    
    # Mock yfinance to fail, forcing the offline fallback to trigger
    def mock_fail(ticker):
        raise RuntimeError("Simulated offline error")
    client._fetch_yfinance = mock_fail
    
    # 7203.T is a known offline stock
    toyota = await client.fetch_stock_metrics("7203.T")
    assert toyota["ticker"] == "7203.T"
    assert toyota["name"] == "Toyota Motor Corp"
    assert toyota["sector"] == "Automobiles & Transportation"
    assert toyota["per"] == 9.5
    assert toyota["pbr"] == 0.85
    
    # Test completely unknown stock fallback
    unknown = await client.fetch_stock_metrics("XYZ")
    assert unknown["ticker"] == "XYZ"
    assert unknown["per"] == 15.0
    assert unknown["pbr"] == 1.0
