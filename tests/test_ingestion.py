import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.ingestion import FredDataFetcher

def test_fetcher_initialization():
    # Test fallback to env var
    with patch.dict("os.environ", {"FRED_API_KEY": "test_env_key"}):
        fetcher = FredDataFetcher()
        assert fetcher.api_key == "test_env_key"

    # Test initialization with explicit arg
    fetcher = FredDataFetcher(api_key="explicit_key")
    assert fetcher.api_key == "explicit_key"

def test_validate_key_raises_error():
    fetcher = FredDataFetcher(api_key=None)
    with patch.dict("os.environ", {}, clear=True):
        fetcher.api_key = None
        # validate_key raises ValueError
        with pytest.raises(ValueError) as excinfo:
            fetcher.validate_key()
        assert "FRED API Key is missing" in str(excinfo.value)

def test_get_value_at_days_offset():
    # Create sample DataFrame
    dates = pd.date_range(end="2026-05-30", periods=60)
    # Values rising daily
    df = pd.DataFrame({"value": [float(i) for i in range(60)]}, index=dates)
    
    fetcher = FredDataFetcher()
    # Get offset of 30 days
    past_val, latest_val, latest_date_str = fetcher.get_value_at_days_offset(df, offset_days=30)
    
    assert latest_val == 59.0
    assert latest_date_str == "2026-05-30"
    # 30 days before is index 29 (since end is 59, 59-30 = 29)
    assert past_val == 29.0

@patch("src.ingestion.FredDataFetcher.fetch_series_dataframe")
def test_prepare_detector_inputs(mock_fetch):
    # Mock data for DGS10 (rates)
    rates_dates = pd.date_range(end="2026-05-30", periods=60)
    df_rates = pd.DataFrame({"value": [3.5] * 30 + [4.0] * 30}, index=rates_dates)
    
    # Mock data for WTI (oil)
    oil_dates = pd.date_range(end="2026-05-30", periods=60)
    df_oil = pd.DataFrame({"value": [80.0] * 60}, index=oil_dates)
    
    # Mock data for USD/JPY
    jpy_dates = pd.date_range(end="2026-05-30", periods=60)
    df_jpy = pd.DataFrame({"value": [150.0] * 60}, index=jpy_dates)
    
    # Mock data for CPI
    cpi_dates = pd.date_range(end="2026-05-30", freq="ME", periods=24)
    df_cpi = pd.DataFrame({"value": [250.0] * 12 + [260.0] * 12}, index=cpi_dates)
    
    # Mock data for GDP
    gdp_dates = pd.date_range(end="2026-05-30", freq="QE", periods=8)
    df_gdp = pd.DataFrame({"value": [100.0] * 4 + [104.0] * 4}, index=gdp_dates)
    
    def side_effect(series_id, days_back):
        if series_id == "DGS10":
            return df_rates
        elif series_id == "DCOILWTICO":
            return df_oil
        elif series_id == "DEXJPUS":
            return df_jpy
        elif series_id == "CPIAUCSL":
            return df_cpi
        elif series_id == "GDP":
            return df_gdp
        return pd.DataFrame()
        
    mock_fetch.side_effect = side_effect
    
    fetcher = FredDataFetcher(api_key="test_key")
    inputs = fetcher.prepare_detector_inputs()
    
    assert "10Y_RATE" in inputs
    assert "OIL_PRICE" in inputs
    assert "USD_JPY" in inputs
    assert "CPI_YOY" in inputs
    assert "GDP_YOY" in inputs
    
    # Check rate logic (latest is index 59 -> 4.0, 30 days offset is index 29 -> 3.5)
    assert inputs["10Y_RATE"] == [3.5, 4.0]
    # Check oil (80, 80)
    assert inputs["OIL_PRICE"] == [80.0, 80.0]
    # Check CPI (index 23 is 260.0. index 11 (one year ago) is 250.0. YoY: (260-250)/250 * 100 = 4.0%)
    assert inputs["CPI_YOY"] == pytest.approx([4.0])
    # Check GDP (index 7 is 104.0. index 3 (one year ago) is 100.0. YoY: (104-100)/100 * 100 = 4.0%)
    assert inputs["GDP_YOY"] == pytest.approx([4.0])
