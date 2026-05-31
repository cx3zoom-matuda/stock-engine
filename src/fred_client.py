import aiohttp
import asyncio
import logging
import sqlite3
import random
import os
import pathlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FredClient:
    """
    Asynchronous client wrapper for the Federal Reserve Economic Data (FRED) API.
    Supports SQLite caching and synthetic data generation for offline/no-key testing.
    """
    BASE_URL = "https://api.stlouisfed.org/fred"
    
    # Tracked macroeconomic series
    SERIES_MAP = {
        "10Y_BOND": "DGS10",      # 10-Year Treasury Constant Maturity Rate (Daily)
        "2Y_BOND": "DGS2",        # 2-Year Treasury Constant Maturity Rate (Daily)
        "CPI": "CPIAUCSL",        # CPI for All Urban Consumers (Monthly)
        "WTI_OIL": "DCOILWTICO"    # WTI Crude Oil Price (Daily)
    }

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        session: Optional[aiohttp.ClientSession] = None,
        cache_db_path: Optional[str] = "data/macro_cache.db",
        enable_cache: bool = True
    ):
        self.api_key = api_key
        self._session = session
        self._own_session = False
        self.enable_cache = enable_cache
        self.cache_db_path = cache_db_path
        
        if self.enable_cache and self.cache_db_path:
            self._init_db()

    def _init_db(self):
        """Initializes the SQLite cache database."""
        try:
            db_dir = pathlib.Path(self.cache_db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    series_id TEXT,
                    date TEXT,
                    value REAL,
                    last_updated TIMESTAMP,
                    PRIMARY KEY (series_id, date)
                )
            """)
            conn.commit()
            conn.close()
            logger.info(f"Initialized FRED cache database at {self.cache_db_path}")
        except Exception as e:
            logger.warning(f"Could not initialize SQLite cache: {e}. Caching disabled.")
            self.enable_cache = False

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self):
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    def _read_from_cache(self, series_id: str, start: str, end: str) -> Optional[List[Dict[str, Any]]]:
        """Reads observations from SQLite cache if they are fresh (updated within 12 hours)."""
        if not self.enable_cache or not self.cache_db_path:
            return None
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check the newest record update time for this series
            cursor.execute(
                "SELECT MAX(last_updated) as newest FROM observations WHERE series_id = ?",
                (series_id,)
            )
            row = cursor.fetchone()
            if not row or not row["newest"]:
                conn.close()
                return None
            
            # If the cache is older than 12 hours, treat it as expired
            newest_update = datetime.fromisoformat(row["newest"])
            if datetime.now() - newest_update > timedelta(hours=12):
                conn.close()
                logger.info(f"Cache expired for series {series_id}")
                return None

            # Get observations in date range
            cursor.execute(
                """
                SELECT date, value FROM observations 
                WHERE series_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
                """,
                (series_id, start, end)
            )
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                logger.info(f"Loaded {len(rows)} observations for {series_id} from cache.")
                return [{"date": r["date"], "value": str(r["value"])} for r in rows]
        except Exception as e:
            logger.warning(f"Error reading cache for {series_id}: {e}")
        
        return None

    def _write_to_cache(self, series_id: str, observations: List[Dict[str, Any]]):
        """Writes observations to the SQLite cache."""
        if not self.enable_cache or not self.cache_db_path:
            return
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            data_to_insert = []
            for obs in observations:
                val_str = obs.get("value")
                if val_str == "." or val_str is None:
                    continue
                try:
                    val = float(val_str)
                    data_to_insert.append((series_id, obs["date"], val, now))
                except ValueError:
                    continue
            
            cursor.executemany(
                """
                INSERT OR REPLACE INTO observations (series_id, date, value, last_updated)
                VALUES (?, ?, ?, ?)
                """,
                data_to_insert
            )
            conn.commit()
            conn.close()
            logger.info(f"Cached {len(data_to_insert)} observations for {series_id}.")
        except Exception as e:
            logger.warning(f"Error writing cache for {series_id}: {e}")

    async def fetch_series_observations(
        self, 
        series_id: str, 
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None,
        units: str = "lin"
    ) -> List[Dict[str, Any]]:
        """
        Fetches observations for a given FRED series.
        If no API key is specified, falls back to generating mock data.
        """
        # Determine boundary dates
        start = observation_start or (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
        end = observation_end or datetime.now().strftime("%Y-%m-%d")
        
        # Try reading cache
        if self.enable_cache:
            cached_data = self._read_from_cache(series_id, start, end)
            if cached_data is not None:
                return cached_data

        # Fallback to mock data if no key
        if not self.api_key:
            logger.warning(f"No FRED API key provided. Generating mock data for {series_id}.")
            mock_data = self._generate_mock_data(series_id, start, end)
            if self.enable_cache:
                self._write_to_cache(series_id, mock_data)
            return mock_data

        # Fetch from Live API
        session = await self.get_session()
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "units": units,
            "observation_start": start,
            "observation_end": end
        }

        url = f"{self.BASE_URL}/series/observations"
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    observations = data.get("observations", [])
                    if self.enable_cache:
                        self._write_to_cache(series_id, observations)
                    return observations
                else:
                    error_text = await response.text()
                    logger.error(f"FRED API HTTP {response.status}: {error_text}")
                    raise Exception(f"FRED API HTTP {response.status}: {error_text}")
        except Exception as e:
            logger.warning(f"API request failed for {series_id} (error: {e}). Trying to fallback to cache...")
            if self.enable_cache:
                conn = sqlite3.connect(self.cache_db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT date, value FROM observations 
                    WHERE series_id = ? AND date >= ? AND date <= ?
                    ORDER BY date ASC
                    """,
                    (series_id, start, end)
                )
                rows = cursor.fetchall()
                conn.close()
                if rows:
                    logger.warning(f"Returned stale cache for {series_id} after API error.")
                    return [{"date": r["date"], "value": str(r["value"])} for r in rows]
            
            logger.warning(f"No cache available. Returning mock data for {series_id}.")
            return self._generate_mock_data(series_id, start, end)

    def _generate_mock_data(
        self, 
        series_id: str, 
        start_date_str: str, 
        end_date_str: str
    ) -> List[Dict[str, Any]]:
        """Generates realistic synthetic data for macroeconomic indicators."""
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        
        observations = []
        current_date = start_date
        
        if series_id in ["DGS10", "10Y_RATE", "GDP"]:
            val = 4.2  # 10Y Yield Base (~4.2%) or GDP base
            step_days = 1
            drift = -0.0005
            vol = 0.04
        elif series_id == "DGS2":
            val = 4.5  # 2Y Yield Base (~4.5%, inverted initially)
            step_days = 1
            drift = -0.001
            vol = 0.05
        elif series_id in ["CPIAUCSL", "CPI_YOY"]:
            val = 308.0  # CPI Base
            step_days = 30  # Monthly
            drift = 0.8
            vol = 0.3
        elif series_id in ["DCOILWTICO", "OIL_PRICE"]:
            val = 80.0  # Oil Price Base ($80)
            step_days = 1
            drift = -0.01
            vol = 1.2
        elif series_id in ["DEXJPUS", "USD_JPY"]:
            val = 150.0  # USD/JPY Exchange Rate Base
            step_days = 1
            drift = 0.05
            vol = 0.4
        else:
            val = 100.0
            step_days = 1
            drift = 0.0
            vol = 1.0

        random.seed(sum(ord(c) for c in series_id))  # Consistent seed per indicator

        while current_date <= end_date:
            if step_days == 1 and current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
                
            change = random.normalvariate(drift, vol)
            val = max(0.1, val + change)

            observations.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "value": f"{val:.4f}"
            })
            current_date += timedelta(days=step_days)
            
        return observations
