from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Any

class BaseMacroProvider(ABC):
    """Abstract interface for macro data providers."""
    
    @abstractmethod
    async def fetch_series(self, series_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch historical macroeconomic data for a given series ID.
        Returns a pandas DataFrame with datetime index and 'value' column.
        """
        pass

class BaseStockProvider(ABC):
    """Abstract interface for stock data providers."""
    
    @abstractmethod
    async def fetch_stock_metrics(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch essential metrics for a given stock ticker.
        Returns a dictionary containing ticker info.
        """
        pass

    @abstractmethod
    async def fetch_historical_prices(self, ticker: str, days: int = 60) -> pd.Series:
        """
        Fetch historical close prices for a given ticker.
        Returns a pandas Series with datetime index.
        """
        pass
