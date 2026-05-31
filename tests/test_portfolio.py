import io
import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock
from src.portfolio import parse_rakuten_csv, evaluate_portfolio_macro, recommend_rebalancing
# (Replace import at the top of file or here)

from src.evaluator import StockEvaluator

# Mock CSV for Japanese stocks from Rakuten
MOCK_RAKUTEN_JP_CSV = """保有商品一覧 (国内株式)
商品名,コード,銘柄名,保有数量,平均取得価額,現在値,前日比,評価損益
トヨタ(7203),7203,トヨタ自動車,100,"2,000",2200,50,"20,000"
三菱UFJ(8306),8306,三菱UFJFG,200,"1,000",1200,20,"40,000"
合計,,,,,,-,60000
"""

# Mock CSV for US stocks from Rakuten
MOCK_RAKUTEN_US_CSV = """保有商品一覧 (米国株式)
ティッカー,銘柄,保有数量,平均取得価額,現在値,前日比,評価損益
AAPL,Apple Inc.,10,150,180,2,"300"
NVDA,NVIDIA Corp,5,800,900,15,"500"
"""

def test_parse_rakuten_csv_jp():
    file_mock = io.BytesIO(MOCK_RAKUTEN_JP_CSV.encode('shift_jis'))
    df = parse_rakuten_csv(file_mock)
    assert len(df) == 2
    assert list(df.columns) == ["ticker", "qty", "cost"]
    
    toyota = df[df["ticker"] == "7203.T"].iloc[0]
    assert toyota["qty"] == 100.0
    assert toyota["cost"] == 2000.0

    mufg = df[df["ticker"] == "8306.T"].iloc[0]
    assert mufg["qty"] == 200.0
    assert mufg["cost"] == 1000.0

def test_parse_rakuten_csv_us():
    file_mock = io.BytesIO(MOCK_RAKUTEN_US_CSV.encode('utf-8'))
    df = parse_rakuten_csv(file_mock)
    assert len(df) == 2
    
    aapl = df[df["ticker"] == "AAPL"].iloc[0]
    assert aapl["qty"] == 10.0
    assert aapl["cost"] == 150.0

    nvda = df[df["ticker"] == "NVDA"].iloc[0]
    assert nvda["qty"] == 5.0
    assert nvda["cost"] == 800.0

@pytest.mark.asyncio
async def test_evaluate_portfolio_macro():
    # Setup inputs
    portfolio_data = [
        {"ticker": "7203.T", "qty": 100.0, "cost": 2000.0},
        {"ticker": "AAPL", "qty": 10.0, "cost": 150.0}
    ]
    portfolio_df = pd.DataFrame(portfolio_data)

    # Mock components
    market_data_client = MagicMock()
    # async method mock
    market_data_client.fetch_stock_metrics = AsyncMock()
    market_data_client.fetch_stock_metrics.side_effect = lambda ticker: {
        "7203.T": {"ticker": "7203.T", "name": "Toyota", "sector": "automobile", "per": 7.5, "pbr": 0.6, "price": 2500.0},
        "AAPL": {"ticker": "AAPL", "name": "Apple", "sector": "electronics", "per": 28.0, "pbr": 5.0, "price": 200.0}
    }[ticker]

    evaluator = StockEvaluator()
    sector_scores = {
        "automobile": {"score": 20.0, "breakdown": []},
        "electronics": {"score": -10.0, "breakdown": []}
    }

    result = await evaluate_portfolio_macro(
        portfolio_df, 
        market_data_client, 
        evaluator, 
        sector_scores
    )

    assert result["total_cost"] == (100 * 2000.0) + (10 * 150.0) # 200000 + 1500 = 201500
    assert result["total_value"] == (100 * 2500.0) + (10 * 200.0) # 250000 + 2000 = 252000
    assert result["total_gain_loss"] == 252000 - 201500 # 50500
    assert abs(result["total_gain_loss_percent"] - (50500 / 201500 * 100.0)) < 0.01

    # Check holdings details
    holdings = result["holdings"]
    assert len(holdings) == 2
    
    toyota = next(h for h in holdings if h["ticker"] == "7203.T")
    assert toyota["decision"] == "BUY"
    assert toyota["macro_score"] == 20.0
    
    apple = next(h for h in holdings if h["ticker"] == "AAPL")
    assert apple["decision"] == "WATCH"
    assert apple["macro_score"] == -10.0

    # Check sector allocation
    sectors = result["sector_allocation"]
    assert "automobile" in sectors
    assert "electronics" in sectors
    assert sectors["automobile"]["value"] == 250000.0
    assert sectors["electronics"]["value"] == 2000.0
    # Portfolio macro score = (20.0 * 250000 + -10.0 * 2000) / 252000
    expected_score = (20.0 * 250000.0 + -10.0 * 2000.0) / 252000.0
    assert abs(result["portfolio_macro_score"] - expected_score) < 0.01

def test_recommend_rebalancing():
    portfolio_results = {
        "holdings": [
            {"ticker": "7203.T", "name": "Toyota", "sector": "automobile", "value": 10000.0, "macro_score": -15.0},
            {"ticker": "8306.T", "name": "MUFG", "sector": "bank", "value": 30000.0, "macro_score": 10.0}
        ],
        "sector_allocation": {
            "automobile": {"percent": 25.0, "value": 10000.0, "score": -15.0},
            "bank": {"percent": 75.0, "value": 30000.0, "score": 10.0}
        },
        "total_value": 40000.0
    }
    
    sector_scores = {
        "automobile": {"score": -15.0},
        "bank": {"score": 10.0},
        "energy": {"score": 25.0} # Strongest tailwind
    }
    
    config_tickers = {"JP": ["7203.T", "8306.T", "1605.T"]}
    
    recs = recommend_rebalancing(
        portfolio_results,
        sector_scores,
        "JP",
        config_tickers
    )
    
    assert recs["has_recommendations"] is True
    assert len(recs["actions"]) == 1
    
    action = recs["actions"][0]
    assert action["from_sector"] == "automobile"
    assert action["to_sector"] == "energy"
    assert "Toyota" in action["reduce_holdings"]
    assert "削減推奨" in action["description"]

