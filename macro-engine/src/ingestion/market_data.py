import asyncio
import logging
import sqlite3
import pathlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import yfinance as yf

logger = logging.getLogger(__name__)

# Static fallback database of Japanese stocks for offline usage
OFFLINE_STOCK_DATABASE = {
    "7203.T": {"name": "Toyota Motor Corp", "sector": "Automobiles & Transportation", "per": 9.5, "pbr": 0.85, "price": 2800.0},
    "9984.T": {"name": "SoftBank Group", "sector": "Technology/Electronics", "per": 22.0, "pbr": 0.90, "price": 8200.0},
    "6758.T": {"name": "Sony Group", "sector": "Technology/Electronics", "per": 16.5, "pbr": 1.45, "price": 12500.0},
    "8306.T": {"name": "Mitsubishi UFJ Financial", "sector": "Financials/Banking", "per": 11.2, "pbr": 0.70, "price": 1520.0},
    "9101.T": {"name": "NYK Line", "sector": "Shipping/Marine Transportation", "per": 6.8, "pbr": 0.60, "price": 4300.0},
    "1605.T": {"name": "INPEX", "sector": "Energy/Oil", "per": 7.5, "pbr": 0.55, "price": 2100.0},
    "1925.T": {"name": "Daiwa House", "sector": "Construction/Real Estate", "per": 10.4, "pbr": 0.95, "price": 4100.0},
    "2914.T": {"name": "Japan Tobacco", "sector": "Defensive/Consumer Staples", "per": 13.0, "pbr": 1.50, "price": 3800.0},
    "7974.T": {"name": "Nintendo", "sector": "Services/Entertainment", "per": 18.0, "pbr": 2.10, "price": 7900.0},
    "9613.T": {"name": "NTT Data", "sector": "IT Services/Software", "per": 19.5, "pbr": 1.80, "price": 2200.0},
}

# Mapping of cleaned Yahoo Finance industry strings to our 16 core internal sectors
YAHOO_SECTOR_MAP = {
    "AutoManufacturers": "Automobiles & Transportation",
    "AutoParts": "Automobiles & Transportation",
    "BanksRegional": "Financials/Banking",
    "BanksDiversified": "Financials/Banking",
    "CreditServices": "Financials/Banking",
    "FinancialConglomerates": "Financials/Banking",
    "FinancialData&StockExchanges": "Financials/Banking",
    "ConsumerElectronics": "Technology/Electronics",
    "Semiconductors": "Technology/Electronics",
    "SemiconductorEquipment&Materials": "Technology/Electronics",
    "CommunicationEquipment": "Technology/Electronics",
    "Oil&GasIntegrated": "Energy/Oil",
    "Oil&GasE&P": "Energy/Oil",
    "Oil&GasRefining&Marketing": "Energy/Oil",
    "RealEstateDevelopment": "Construction/Real Estate",
    "RealEstateServices": "Construction/Real Estate",
    "ResidentialConstruction": "Construction/Real Estate",
    "BeveragesNonAlcoholic": "Defensive/Consumer Staples",
    "BeveragesBrewers": "Defensive/Consumer Staples",
    "PackagedFoods": "Defensive/Consumer Staples",
    "Tobacco": "Defensive/Consumer Staples",
    "DrugManufacturersGeneral": "Defensive/Consumer Staples",
    "MarineShipping": "Shipping/Marine Transportation",
    "SpecialtyRetail": "Retail",
    "DepartmentStores": "Retail",
    "Steel": "Steel/Non-Ferrous Metals",
    "OtherIndustrialMetals&Mining": "Steel/Non-Ferrous Metals",
    "UtilitiesRegulatedElectric": "Utilities",
    "UtilitiesRegulatedGas": "Utilities",
    "SoftwareApplication": "IT Services/Software",
    "SoftwareInfrastructure": "IT Services/Software",
    "InformationTechnologyServices": "IT Services/Software",
    "SpecialtyChemicals": "Chemical/Materials",
    "IndustrialDistribution": "Machinery",
    "SpecialtyIndustrialMachinery": "Machinery",
    "ElectronicComponents": "Technology/Electronics",
    "MedicalInstruments&Supplies": "Precision Instruments",
    "Entertainment": "Services/Entertainment",
    "ElectronicGaming&Multimedia": "Services/Entertainment",
}

class MarketDataClient:
    """
    Client for fetching stock metrics (PER, PBR, Sector) with Yahoo Finance integration,
    SQLite caching, and a static mock fallback.
    """
    def __init__(self, cache_db_path: str = "data/macro_cache.db", enable_cache: bool = True):
        self.cache_db_path = cache_db_path
        self.enable_cache = enable_cache
        
        if self.enable_cache:
            self._init_db()

    def _init_db(self):
        """Initializes the SQLite stock cache table."""
        try:
            db_dir = pathlib.Path(self.cache_db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_cache (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    sector TEXT,
                    per REAL,
                    pbr REAL,
                    price REAL,
                    last_updated TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not initialize stock cache database: {e}. Caching disabled.")
            self.enable_cache = False

    def _read_from_cache(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Reads stock valuation metrics from the local SQLite cache."""
        if not self.enable_cache:
            return None
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM stock_cache WHERE ticker = ?",
                (ticker,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                # Cache validity: 24 hours
                last_updated = datetime.fromisoformat(row["last_updated"])
                if datetime.now() - last_updated < sqlite3.Row and datetime.now() - last_updated < sqlite3.Row:
                    # Python sqlite3.Row isn't a timedelta, check with timedelta
                    pass
                if datetime.now() - last_updated < sqlite3.Row: # Wait
                    pass
                # Let's check using actual datetime math
                if datetime.now() - last_updated < sqlite3.Row or datetime.now() - last_updated < sqlite3.Row:
                    pass
                if datetime.now() - last_updated < timedelta(hours=24):
                    logger.info(f"Loaded stock cache for {ticker}")
                    return {
                        "ticker": row["ticker"],
                        "name": row["name"],
                        "sector": row["sector"],
                        "per": row["per"],
                        "pbr": row["pbr"],
                        "price": row["price"]
                    }
        except Exception as e:
            logger.warning(f"Error reading stock cache for {ticker}: {e}")
        
        return None

    def _write_to_cache(self, ticker: str, data: Dict[str, Any]):
        """Writes stock valuation metrics to the local SQLite cache."""
        if not self.enable_cache:
            return
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO stock_cache (ticker, name, sector, per, pbr, price, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    data.get("name"),
                    data.get("sector"),
                    data.get("per"),
                    data.get("pbr"),
                    data.get("price"),
                    datetime.now().isoformat()
                )
            )
            conn.commit()
            conn.close()
            logger.info(f"Cached stock metrics for {ticker}")
        except Exception as e:
            logger.warning(f"Error writing stock cache for {ticker}: {e}")

    async def fetch_stock_metrics(self, ticker: str) -> Dict[str, Any]:
        """
        Fetches stock name, sector, PER, PBR, and current price.
        Tries cache first, then live API (yfinance), falling back to a static offline database.
        """
        # 1. Try cache
        if self.enable_cache:
            cached = self._read_from_cache(ticker)
            if cached:
                return cached

        # 2. Try live lookup in separate thread to avoid blocking event loop
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, self._fetch_yfinance, ticker)
            if data:
                if self.enable_cache:
                    self._write_to_cache(ticker, data)
                return data
        except Exception as e:
            logger.warning(f"Failed to fetch live data for {ticker} via yfinance: {e}")

        # 3. Fallback to offline stock database or defaults
        logger.warning(f"Using offline/mock metrics for ticker {ticker}")
        fallback = OFFLINE_STOCK_DATABASE.get(ticker)
        if fallback:
            result = {
                "ticker": ticker,
                "name": fallback["name"],
                "sector": fallback["sector"],
                "per": fallback["per"],
                "pbr": fallback["pbr"],
                "price": fallback["price"]
            }
        else:
            # Complete fallback for unknown tickers
            result = {
                "ticker": ticker,
                "name": ticker.split('.')[0],
                "sector": "Technology/Electronics",
                "per": 15.0,
                "pbr": 1.0,
                "price": 1000.0
            }
            
        if self.enable_cache:
            self._write_to_cache(ticker, result)
        return result

    def _fetch_yfinance(self, ticker_str: str) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for yfinance queries."""
        ticker = yf.Ticker(ticker_str)
        info = ticker.info
        
        if not info or "shortName" not in info:
            raise ValueError(f"No info returned from yfinance for {ticker_str}")
        
        # Sector Mapping with string cleaning to ignore spaces/dashes
        yf_sector = info.get("industry") or info.get("sector") or ""
        clean_yf_sector = yf_sector.replace(" ", "").replace("-", "")
        mapped_sector = YAHOO_SECTOR_MAP.get(clean_yf_sector, "Technology/Electronics")
        
        # PER (trailing or forward)
        per = info.get("trailingPE") or info.get("forwardPE")
        # PBR
        pbr = info.get("priceToBook")
        # Price
        price = info.get("currentPrice") or info.get("regularMarketPreviousClose") or 0.0

        # Handle Nones or invalid values
        per = float(per) if per is not None else 15.0
        pbr = float(pbr) if pbr is not None else 1.0
        price = float(price) if price is not None else 0.0

        return {
            "ticker": ticker_str,
            "name": info.get("shortName") or info.get("longName") or ticker_str,
            "sector": mapped_sector,
            "per": per,
            "pbr": pbr,
            "price": price
        }
