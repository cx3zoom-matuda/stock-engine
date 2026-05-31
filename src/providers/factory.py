from typing import Dict, Any, Optional
from src.providers.base import BaseMacroProvider, BaseStockProvider
from src.providers.fred import FredProvider
from src.providers.yfinance_provider import YFinanceProvider
from src.config import load_config

class ProviderFactory:
    """
    Factory class to instantiate macro and stock providers based on system configuration.
    Allows easy plugin selection and loose coupling.
    """
    
    @staticmethod
    def get_macro_provider(
        provider_name: Optional[str] = None, 
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> BaseMacroProvider:
        """
        Instantiates a macro data provider.
        """
        cfg = config or load_config()
        name = provider_name or cfg.get("providers", {}).get("macro", "fred")
        
        # Read API key and cache config
        api_key = cfg.get("api", {}).get("fred_api_key")
        cache_cfg = cfg.get("cache", {})
        enable_cache = cache_cfg.get("enable_cache", True)
        cache_db_path = cache_cfg.get("cache_db_path", "data/macro_cache.db")
        
        # Overwrite with kwargs
        api_key = kwargs.get("api_key", api_key)
        enable_cache = kwargs.get("enable_cache", enable_cache)
        cache_db_path = kwargs.get("cache_db_path", cache_db_path)
        
        if name.lower() == "fred":
            return FredProvider(
                api_key=api_key,
                enable_cache=enable_cache,
                cache_db_path=cache_db_path,
                session=kwargs.get("session")
            )
        else:
            raise ValueError(f"Unknown macro provider type: {name}")

    @staticmethod
    def get_stock_provider(
        provider_name: Optional[str] = None, 
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> BaseStockProvider:
        """
        Instantiates a stock data provider.
        """
        cfg = config or load_config()
        name = provider_name or cfg.get("providers", {}).get("stock", "yfinance")
        
        cache_cfg = cfg.get("cache", {})
        enable_cache = cache_cfg.get("enable_cache", True)
        cache_db_path = cache_cfg.get("cache_db_path", "data/macro_cache.db")
        
        # Overwrite with kwargs
        enable_cache = kwargs.get("enable_cache", enable_cache)
        cache_db_path = kwargs.get("cache_db_path", cache_db_path)
        
        if name.lower() == "yfinance":
            return YFinanceProvider(
                enable_cache=enable_cache,
                cache_db_path=cache_db_path
            )
        else:
            raise ValueError(f"Unknown stock provider type: {name}")
