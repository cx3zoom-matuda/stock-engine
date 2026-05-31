import os
import pathlib
from typing import List, Dict, Any

try:
    import tomllib
except ImportError:
    # Fallback to third-party tomli if running on python < 3.11
    import tomli as tomllib  # type: ignore

DEFAULT_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config.toml"

COUNTRY_SERIES_MAP = {
    "US": {
        "POLICY_RATE": "FEDFUNDS",
        "YIELD_10Y": "DGS10",
        "CPI": "CPIAUCSL",
        "CONFIDENCE": "USPMIMNSMEI",
        "GDP": "GDPC1",
        "MONEY_SUPPLY": "M2SL"
    },
    "JP": {
        "POLICY_RATE": "IRSTCB01JPM156N",
        "YIELD_10Y": "IRLTLT01JPM156N",
        "CPI": "CPALTT01JPM657N",
        "CONFIDENCE": "BSCICP03JPM665S",
        "GDP": "JPNRGDPQDSMEI",
        "MONEY_SUPPLY": "MYAGM2JPM189S"
    },
    "EZ": {
        "POLICY_RATE": "IRSTCI01EZM156N",
        "YIELD_10Y": "IRLTLT01EZM156N",
        "CPI": "CPALTT01EZM657N",
        "CONFIDENCE": "BSCICP03EZM665S",
        "GDP": "CLVMEURSCAB1GQEZ",
        "MONEY_SUPPLY": "MYAGM2EZM196N"
    },
    "GB": {
        "POLICY_RATE": "IRSTCB01GBM156N",
        "YIELD_10Y": "IRLTLT01GBM156N",
        "CPI": "CPALTT01GBM657N",
        "CONFIDENCE": "BSCICP03GBM665S",
        "GDP": "UKNGDPQDSMEI",
        "MONEY_SUPPLY": "MABMM301GBM189S"
    },
    "CN": {
        "POLICY_RATE": "IRSTCB01CNM156N",
        "YIELD_10Y": "IRLTLT01CNM156N",
        "CPI": "CPALTT01CNM657N",
        "CONFIDENCE": "CHINAPMIMNSMEI",
        "GDP": "CHNRGDPQDSMEI",
        "MONEY_SUPPLY": "MYAGM2CNM189N"
    },
    "CA": {
        "POLICY_RATE": "IRSTCB01CAM156N",
        "YIELD_10Y": "IRLTLT01CAM156N",
        "CPI": "CPALTT01CAM657N",
        "CONFIDENCE": "BSCICP03CAO665S",
        "GDP": "CANRGDPQDSMEI",
        "MONEY_SUPPLY": "MABMM301CAM189S"
    },
    "AU": {
        "POLICY_RATE": "IRSTCB01AUM156N",
        "YIELD_10Y": "IRLTLT01AUM156N",
        "CPI": "CPALTT01AUM657N",
        "CONFIDENCE": "BSCICP03AUM665S",
        "GDP": "AUSRGDPQDSMEI",
        "MONEY_SUPPLY": "MABMM301AUM189S"
    }
}

def load_config(config_path: str | pathlib.Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Loads configuration from config.toml, falling back to environment variables or defaults."""
    config_path = pathlib.Path(config_path)
    if not config_path.exists():
        # Fallback config
        return {
            "api": {
                "fred_api_key": os.getenv("FRED_API_KEY", "")
            },
            "settings": {
                "tickers": {
                    "US": ["AAPL", "MSFT", "NVDA", "JPM", "XOM"],
                    "JP": ["7203.T", "8306.T", "1605.T"],
                    "EZ": ["MC.PA", "ASML.AS", "SAP.DE"],
                    "GB": ["BP.L", "HSBA.L", "AZN.L"],
                    "CN": ["0700.HK", "9988.HK"],
                    "CA": ["RY.TO", "TD.TO"],
                    "AU": ["BHP.AX", "CBA.AX"]
                }
            },
            "cache": {
                "enable_cache": True,
                "cache_db_path": "data/macro_cache.db"
            }
        }
    
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    
    # Overwrite API key with environment variable if present
    env_api_key = os.getenv("FRED_API_KEY")
    if env_api_key:
        if "api" not in config:
            config["api"] = {}
        config["api"]["fred_api_key"] = env_api_key

    return config
