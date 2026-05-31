import pytest
import pandas as pd
from datetime import datetime, timedelta
from src.providers.factory import ProviderFactory
from src.providers.base import BaseMacroProvider, BaseStockProvider
from src.providers.fred import FredProvider
from src.providers.yfinance_provider import YFinanceProvider

@pytest.mark.asyncio
async def test_provider_factory():
    # Factory resolves default plugins
    macro_provider = ProviderFactory.get_macro_provider(enable_cache=False)
    stock_provider = ProviderFactory.get_stock_provider(enable_cache=False)
    
    assert isinstance(macro_provider, BaseMacroProvider)
    assert isinstance(macro_provider, FredProvider)
    assert isinstance(stock_provider, BaseStockProvider)
    assert isinstance(stock_provider, YFinanceProvider)

@pytest.mark.asyncio
async def test_fred_provider_mock_data():
    macro_provider = ProviderFactory.get_macro_provider(
        provider_name="fred",
        api_key=None,  # Forces mock generation
        enable_cache=False
    )
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    
    # Test Japanese series mock
    df = await macro_provider.fetch_series("IRSTCB01JPM156N", start_date, end_date)
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "value" in df.columns
    assert isinstance(df.index, pd.DatetimeIndex)

@pytest.mark.asyncio
async def test_yfinance_provider_fallback():
    stock_provider = ProviderFactory.get_stock_provider(
        provider_name="yfinance",
        enable_cache=False
    )
    
    # Fetch offline registered stock
    metrics = await stock_provider.fetch_stock_metrics("8306.T")
    
    assert isinstance(metrics, dict)
    assert metrics["ticker"] == "8306.T"
    assert metrics["name"].strip().upper().startswith("MITSUBISHI UFJ")
    assert metrics["sector"] == "bank"
    assert metrics["per"] > 0
    assert metrics["pbr"] > 0
    assert metrics["price"] > 0
