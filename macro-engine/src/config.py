import os
import pathlib
from typing import List, Dict, Any

try:
    import tomllib
except ImportError:
    # Fallback to third-party tomli if running on python < 3.11
    import tomli as tomllib  # type: ignore

DEFAULT_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config.toml"

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
                "tickers": [
                    "7203.T", "9984.T", "6758.T", "8306.T", "9101.T",
                    "1605.T", "1925.T", "2914.T", "7974.T", "9613.T"
                ]
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
