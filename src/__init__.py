# Macro to Industry Translation Engine Package
__version__ = "0.1.0"

from .detector import EventDetector
from .engine import RuleEngine
from .evaluator import StockEvaluator
from .providers.base import BaseMacroProvider, BaseStockProvider
from .providers.fred import FredProvider
from .providers.yfinance_provider import YFinanceProvider
from .providers.factory import ProviderFactory

# Keep legacy clients for backward compatibility during transition if needed
from .fred_client import FredClient
from .market_data import MarketDataClient

__all__ = [
    "EventDetector",
    "RuleEngine",
    "StockEvaluator",
    "BaseMacroProvider",
    "BaseStockProvider",
    "FredProvider",
    "YFinanceProvider",
    "ProviderFactory",
    "FredClient",
    "MarketDataClient"
]


