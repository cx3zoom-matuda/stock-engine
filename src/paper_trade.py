import json
from datetime import datetime
from typing import Dict, List, Any, Optional

class PaperTradeAccount:
    """
    Manages a virtual paper trading account, holding transactions history,
    current positions, and cash balance. Supports serialization to/from dictionary/JSON.
    """
    def __init__(
        self, 
        name: str, 
        currency: str = "¥", 
        initial_balance: float = 10000000.0,
        cash: Optional[float] = None,
        holdings: Optional[Dict[str, Dict[str, float]]] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ):
        self.name = name
        self.currency = currency
        self.initial_balance = initial_balance
        self.cash = cash if cash is not None else initial_balance
        self.holdings = holdings if holdings is not None else {} # {ticker: {"qty": float, "cost": float}}
        self.history = history if history is not None else [] # [{"date": str, "ticker": str, "side": str, "qty": float, "price": float}]

    def buy(self, ticker: str, qty: float, price: float, date_str: Optional[str] = None) -> None:
        """Executes a virtual BUY transaction."""
        if qty <= 0 or price <= 0:
            raise ValueError("Quantity and price must be greater than zero.")
            
        total_cost = qty * price
        if self.cash < total_cost:
            raise ValueError(f"Insufficient cash. Required: {self.currency}{total_cost:,.2f}, Available: {self.currency}{self.cash:,.2f}")
            
        self.cash -= total_cost
        
        # Update holding positions
        if ticker in self.holdings:
            existing = self.holdings[ticker]
            new_qty = existing["qty"] + qty
            # Calculate new average cost basis
            new_cost = (existing["qty"] * existing["cost"] + total_cost) / new_qty
            self.holdings[ticker] = {"qty": new_qty, "cost": new_cost}
        else:
            self.holdings[ticker] = {"qty": qty, "cost": price}

        # Log to history
        dt = date_str if date_str else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({
            "date": dt,
            "ticker": ticker,
            "side": "BUY",
            "qty": qty,
            "price": price,
            "total": total_cost
        })

    def sell(self, ticker: str, qty: float, price: float, date_str: Optional[str] = None) -> None:
        """Executes a virtual SELL transaction."""
        if qty <= 0 or price <= 0:
            raise ValueError("Quantity and price must be greater than zero.")
            
        if ticker not in self.holdings or self.holdings[ticker]["qty"] < qty:
            available = self.holdings[ticker]["qty"] if ticker in self.holdings else 0.0
            raise ValueError(f"Insufficient holdings for {ticker}. Required: {qty}, Available: {available}")
            
        total_income = qty * price
        self.cash += total_income
        
        # Update holdings
        existing = self.holdings[ticker]
        new_qty = existing["qty"] - qty
        if new_qty <= 0:
            del self.holdings[ticker]
        else:
            self.holdings[ticker] = {"qty": new_qty, "cost": existing["cost"]} # average cost does not change on sell

        # Log to history
        dt = date_str if date_str else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({
            "date": dt,
            "ticker": ticker,
            "side": "SELL",
            "qty": qty,
            "price": price,
            "total": total_income
        })

    def reset(self) -> None:
        """Resets the account to its initial state."""
        self.cash = self.initial_balance
        self.holdings = {}
        self.history = []

    def to_dict(self) -> Dict[str, Any]:
        """Serializes account state to dictionary."""
        return {
            "name": self.name,
            "currency": self.currency,
            "initial_balance": self.initial_balance,
            "cash": self.cash,
            "holdings": self.holdings,
            "history": self.history
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaperTradeAccount':
        """Deserializes account state from dictionary."""
        return cls(
            name=data["name"],
            currency=data.get("currency", "¥"),
            initial_balance=data.get("initial_balance", 10000000.0),
            cash=data.get("cash"),
            holdings=data.get("holdings"),
            history=data.get("history")
        )

    def to_json(self) -> str:
        """Serializes account state to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'PaperTradeAccount':
        """Deserializes account state from JSON string."""
        return cls.from_dict(json.loads(json_str))
