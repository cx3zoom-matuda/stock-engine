import pytest
import json
from src.paper_trade import PaperTradeAccount

def test_paper_trade_account_initialization():
    acc = PaperTradeAccount("Test Account", currency="$", initial_balance=50000.0)
    assert acc.name == "Test Account"
    assert acc.currency == "$"
    assert acc.initial_balance == 50000.0
    assert acc.cash == 50000.0
    assert acc.holdings == {}
    assert acc.history == []

def test_paper_trade_buy_success():
    acc = PaperTradeAccount("JP Account", currency="¥", initial_balance=10000000.0)
    
    # Buy 100 shares of Toyota at 2500 yen
    acc.buy("7203.T", 100, 2500.0, date_str="2026-05-31")
    assert acc.cash == 10000000.0 - 250000.0 # 9,750,000
    assert acc.holdings["7203.T"] == {"qty": 100.0, "cost": 2500.0}
    assert len(acc.history) == 1
    assert acc.history[0]["side"] == "BUY"
    assert acc.history[0]["total"] == 250000.0

    # Buy another 100 shares of Toyota at 3000 yen (avg cost check)
    acc.buy("7203.T", 100, 3000.0, date_str="2026-05-31")
    assert acc.cash == 9750000.0 - 300000.0 # 9,450,000
    # Weighted avg cost = (100 * 2500 + 100 * 3000) / 200 = 2750
    assert acc.holdings["7203.T"] == {"qty": 200.0, "cost": 2750.0}
    assert len(acc.history) == 2

def test_paper_trade_buy_insufficient_cash():
    acc = PaperTradeAccount("Mini Account", currency="$", initial_balance=1000.0)
    with pytest.raises(ValueError, match="Insufficient cash"):
        acc.buy("AAPL", 10, 150.0) # Total cost 1500 > 1000

def test_paper_trade_sell_success():
    acc = PaperTradeAccount("US Account", currency="$", initial_balance=10000.0)
    acc.buy("AAPL", 10, 150.0) # cash: 8500, holdings AAPL: 10 @ 150
    
    # Sell 5 shares of AAPL at 180.0
    acc.sell("AAPL", 5, 180.0, date_str="2026-05-31")
    assert acc.cash == 8500.0 + 900.0 # 9400
    assert acc.holdings["AAPL"] == {"qty": 5.0, "cost": 150.0} # cost basis remains 150
    assert len(acc.history) == 2
    assert acc.history[1]["side"] == "SELL"
    assert acc.history[1]["total"] == 900.0

    # Sell remaining 5 shares
    acc.sell("AAPL", 5, 200.0)
    assert acc.cash == 9400.0 + 1000.0 # 10400
    assert "AAPL" not in acc.holdings
    assert len(acc.history) == 3

def test_paper_trade_sell_insufficient_holdings():
    acc = PaperTradeAccount("US Account", currency="$", initial_balance=10000.0)
    acc.buy("AAPL", 5, 150.0)
    with pytest.raises(ValueError, match="Insufficient holdings"):
        acc.sell("AAPL", 10, 180.0)
    with pytest.raises(ValueError, match="Insufficient holdings"):
        acc.sell("MSFT", 1, 400.0)

def test_paper_trade_serialization():
    acc = PaperTradeAccount("Serialization Test", currency="¥", initial_balance=500000.0)
    acc.buy("7203.T", 10, 2000.0)
    
    json_data = acc.to_json()
    
    # Recover from json
    recovered = PaperTradeAccount.from_json(json_data)
    assert recovered.name == "Serialization Test"
    assert recovered.currency == "¥"
    assert recovered.initial_balance == 500000.0
    assert recovered.cash == acc.cash
    assert recovered.holdings == acc.holdings
    assert len(recovered.history) == 1
    assert recovered.history[0]["ticker"] == "7203.T"
