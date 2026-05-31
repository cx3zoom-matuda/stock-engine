import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class FredDataFetcher:
    """
    Fetches macroeconomic series from the FRED API and calculates
    comparison values (latest vs historical offset) to prepare inputs for the EventDetector.
    """
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str = None):
        # Read from argument or fall back to environment variable
        self.api_key = api_key or os.getenv("FRED_API_KEY")

    def validate_key(self):
        """Raises a ValueError if no API key is provided."""
        if not self.api_key:
            raise ValueError(
                "\n" + "="*80 + "\n"
                " ERROR: FRED API Key is missing!\n"
                "================================================================================\n"
                " Please set the FRED_API_KEY environment variable, or create a '.env' file in\n"
                " the root of the project with the following content:\n\n"
                " FRED_API_KEY=your_free_api_key_here\n\n"
                " You can obtain a free API key instantly at: https://fred.stlouisfed.org/api_key.html\n"
                "================================================================================\n"
            )

    def fetch_series_dataframe(self, series_id: str, days_back: int = 500) -> pd.DataFrame:
        """
        Queries the FRED API for a specific series ID and parses it into a cleaned DataFrame.
        If no API key is set, falls back to downloading the public FRED CSV export.
        """
        if not self.api_key:
            print(f"    ⚠️  [FRED_API_KEY is not set] Downloading public CSV data for {series_id}...")
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            try:
                df = pd.read_csv(url)
                df = df.rename(columns={"observation_date": "date", series_id: "value"})
            except Exception as e:
                raise RuntimeError(f"Failed to download public CSV for {series_id} from {url}: {e}")
        else:
            # Use authenticated JSON API
            start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date
            }
            
            response = requests.get(self.BASE_URL, params=params)
            if response.status_code != 200:
                raise RuntimeError(
                    f"FRED API Request failed for {series_id} (HTTP {response.status_code}): {response.text}"
                )
                
            data = response.json()
            observations = data.get("observations", [])
            
            if not observations:
                raise ValueError(f"No observations returned from FRED for series ID: {series_id}")

            df = pd.DataFrame(observations)

        df["date"] = pd.to_datetime(df["date"])
        # Replace missing values '.' with NaN
        df["value"] = df["value"].replace(".", np.nan)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        df = df.set_index("date").sort_index()

        # If we downloaded the CSV (which contains the full history), filter by lookback window
        start_cutoff = pd.to_datetime(datetime.now() - timedelta(days=days_back))
        df = df[df.index >= start_cutoff]
        return df

    def get_value_at_days_offset(self, df: pd.DataFrame, offset_days: int) -> Tuple[float, float, str]:
        """
        Extracts the latest value and the historical value closest to (latest_date - offset_days).
        """
        if df.empty:
            raise ValueError("Empty DataFrame passed to offset extractor.")
            
        latest_date = df.index[-1]
        latest_val = float(df.iloc[-1]["value"])
        
        target_date = latest_date - timedelta(days=offset_days)
        # Find index with date closest to target_date (going backward)
        past_dates = df.index[df.index <= target_date]
        if len(past_dates) == 0:
            # Fallback to the oldest available value
            past_date = df.index[0]
        else:
            past_date = past_dates[-1]
            
        past_val = float(df.loc[past_date]["value"])
        return past_val, latest_val, latest_date.strftime("%Y-%m-%d")

    def prepare_detector_inputs(self) -> Dict[str, List[float]]:
        """
        Fetches all standard series and builds the exact input structure for EventDetector.
        """
        inputs = {}
        
        # 1. 10-Year Bond Rate (DGS10) - 30 days change
        print("  * Fetching 10-Year Treasury Yield (DGS10)...")
        df_rates = self.fetch_series_dataframe("DGS10", days_back=60)
        prev_rate, latest_rate, _ = self.get_value_at_days_offset(df_rates, offset_days=30)
        inputs["10Y_RATE"] = [prev_rate, latest_rate]
        
        # 2. Oil Price (DCOILWTICO) - 30 days change
        print("  * Fetching WTI Crude Oil Price (DCOILWTICO)...")
        df_oil = self.fetch_series_dataframe("DCOILWTICO", days_back=60)
        prev_oil, latest_oil, _ = self.get_value_at_days_offset(df_oil, offset_days=30)
        inputs["OIL_PRICE"] = [prev_oil, latest_oil]

        # 3. USD/JPY Spot Rate (DEXJPUS) - 30 days change
        print("  * Fetching USD/JPY Exchange Rate (DEXJPUS)...")
        df_jpy = self.fetch_series_dataframe("DEXJPUS", days_back=60)
        prev_jpy, latest_jpy, _ = self.get_value_at_days_offset(df_jpy, offset_days=30)
        inputs["USD_JPY"] = [prev_jpy, latest_jpy]

        # 4. CPI YoY Inflation (CPIAUCSL) - calculated YoY from monthly index
        print("  * Fetching CPI Index (CPIAUCSL) and computing YoY Inflation...")
        df_cpi = self.fetch_series_dataframe("CPIAUCSL", days_back=500)
        # Latest CPI value
        latest_cpi_val = float(df_cpi.iloc[-1]["value"])
        # Fetch the value from 1 year ago (365 days)
        prev_cpi_date = df_cpi.index[-1] - timedelta(days=365)
        # Find closest monthly date in the past
        past_cpi_dates = df_cpi.index[df_cpi.index <= prev_cpi_date]
        if len(past_cpi_dates) > 0:
            cpi_year_ago_val = float(df_cpi.loc[past_cpi_dates[-1]]["value"])
        else:
            cpi_year_ago_val = float(df_cpi.iloc[0]["value"])
            
        cpi_yoy_latest = ((latest_cpi_val - cpi_year_ago_val) / cpi_year_ago_val) * 100
        inputs["CPI_YOY"] = [cpi_yoy_latest]

        # 5. GDP YoY (GDP) - calculated YoY from quarterly index
        print("  * Fetching GDP Index (GDP) and computing YoY Growth...")
        df_gdp = self.fetch_series_dataframe("GDP", days_back=600)
        latest_gdp_val = float(df_gdp.iloc[-1]["value"])
        prev_gdp_date = df_gdp.index[-1] - timedelta(days=365)
        past_gdp_dates = df_gdp.index[df_gdp.index <= prev_gdp_date]
        if len(past_gdp_dates) > 0:
            gdp_year_ago_val = float(df_gdp.loc[past_gdp_dates[-1]]["value"])
        else:
            gdp_year_ago_val = float(df_gdp.iloc[0]["value"])
            
        gdp_yoy_latest = ((latest_gdp_val - gdp_year_ago_val) / gdp_year_ago_val) * 100
        inputs["GDP_YOY"] = [gdp_yoy_latest]
        
        return inputs
