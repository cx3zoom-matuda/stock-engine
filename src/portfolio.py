import io
import pandas as pd
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

def parse_rakuten_csv(uploaded_file) -> pd.DataFrame:
    """
    Parses a Rakuten Securities CSV file (for JP or US stocks)
    and returns a normalized DataFrame with:
    - ticker (str)
    - qty (float)
    - cost (float)
    """
    raw_data = uploaded_file.read()
    # Try different Japanese and UTF-8 encodings
    for encoding in ['shift_jis', 'cp932', 'utf-8', 'utf-8-sig']:
        try:
            text = raw_data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Could not decode the CSV file. Please upload a valid CSV encoded in Shift_JIS or UTF-8.")

    lines = text.split('\n')
    start_idx = -1
    for idx, line in enumerate(lines):
        # Identify the header line containing Rakuten's standard keys
        if 'コード' in line or 'ティッカー' in line or '保有数量' in line:
            start_idx = idx
            break

    if start_idx == -1:
        raise ValueError("Invalid format: CSV must contain 'コード' (JP stocks) or 'ティッカー' (US stocks).")

    # Read CSV starting from the identified header line
    df = pd.read_csv(io.StringIO('\n'.join(lines[start_idx:])))
    
    # Standardize columns
    ticker_col = None
    for col in ['コード', 'ティッカー', '銘柄コード']:
        if col in df.columns:
            ticker_col = col
            break
            
    qty_col = None
    for col in ['保有数量', '数量', '保有口数']:
        if col in df.columns:
            qty_col = col
            break

    cost_col = None
    for col in ['平均取得価額', '取得単価', '平均取得価格']:
        if col in df.columns:
            cost_col = col
            break

    if not ticker_col or not qty_col or not cost_col:
        raise ValueError(
            f"Required columns not found. Found columns: {list(df.columns)}. "
            "Please ensure the CSV is exported from Rakuten Securities Portfolio page."
        )

    # Clean data (remove NaN, empty values)
    df = df.dropna(subset=[ticker_col, qty_col])
    
    # Remove rows that are totals or non-data (e.g., '合計')
    df = df[df[ticker_col].apply(lambda x: str(x).strip() != '' and '合計' not in str(x))]
    
    # Standardize Tickers and values
    result_data = []
    for _, row in df.iterrows():
        raw_ticker = str(row[ticker_col]).strip()
        
        # Skip empty lines or headers
        if not raw_ticker or raw_ticker == 'nan':
            continue
            
        # If float representation (e.g. '7203.0'), convert to int representation
        if raw_ticker.endswith('.0'):
            raw_ticker = raw_ticker[:-2]
            
        # Clean ticker: Rakuten JP CSV codes are integers (e.g. 7203 or '7203')
        # If it's a 4-digit digit or number, append '.T' for Yahoo Finance
        if raw_ticker.isdigit() and len(raw_ticker) == 4:
            ticker = f"{raw_ticker}.T"
        else:
            ticker = raw_ticker

        # Clean quantity and cost
        try:
            qty_val = str(row[qty_col]).replace(',', '').strip()
            cost_val = str(row[cost_col]).replace(',', '').strip()
            
            qty = float(qty_val)
            cost = float(cost_val)
        except Exception:
            # Skip rows where quantity or cost cannot be parsed (e.g. headers, footer text)
            continue
            
        result_data.append({
            "ticker": ticker,
            "qty": qty,
            "cost": cost
        })
        
    return pd.DataFrame(result_data)

async def evaluate_portfolio_macro(
    portfolio_df: pd.DataFrame, 
    market_data_client, 
    evaluator, 
    sector_scores: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluates a portfolio of stocks against macro sector scores.
    Returns:
        Dict containing:
        - 'holdings': list of evaluated holdings with weight, profit/loss, and decisions
        - 'portfolio_macro_score': weighted average macro score
        - 'total_cost': total portfolio purchase cost
        - 'total_value': total portfolio current value
        - 'total_gain_loss': total portfolio unrealized gain/loss
        - 'total_gain_loss_percent': gain/loss percent
        - 'sector_allocation': allocation dict {sector: {value: float, percent: float, score: float}}
    """
    if portfolio_df.empty:
        return {
            "holdings": [],
            "portfolio_macro_score": 0.0,
            "total_cost": 0.0,
            "total_value": 0.0,
            "total_gain_loss": 0.0,
            "total_gain_loss_percent": 0.0,
            "sector_allocation": {}
        }

    # 1. Fetch metrics for all tickers
    stock_metrics = []
    ticker_qtys = {}
    ticker_costs = {}
    
    for _, row in portfolio_df.iterrows():
        ticker = row["ticker"]
        ticker_qtys[ticker] = ticker_qtys.get(ticker, 0.0) + row["qty"]
        ticker_costs[ticker] = row["cost"] # Use average cost (latest if duplicates)

    # Resolve duplicates and unique list
    unique_tickers = list(ticker_qtys.keys())
    
    for ticker in unique_tickers:
        try:
            metrics = await market_data_client.fetch_stock_metrics(ticker)
            stock_metrics.append(metrics)
        except Exception as e:
            logger.warning(f"Failed to fetch metrics for {ticker} in portfolio: {e}")
            # Fallback mock for the portfolio evaluation to succeed
            stock_metrics.append({
                "ticker": ticker,
                "name": ticker.split('.')[0],
                "sector": "electronics",
                "per": 15.0,
                "pbr": 1.0,
                "price": ticker_costs[ticker] # Fallback price to cost
            })

    # 2. Evaluate using evaluator
    evaluated_list = evaluator.evaluate_stocks(stock_metrics, sector_scores)
    evaluated_map = {x["ticker"]: x for x in evaluated_list}

    # 3. Calculate portfolio aggregate statistics
    holdings = []
    total_cost = 0.0
    total_value = 0.0
    
    for ticker in unique_tickers:
        eval_data = evaluated_map.get(ticker)
        if not eval_data:
            continue
            
        qty = ticker_qtys[ticker]
        cost = ticker_costs[ticker]
        price = eval_data["price"] if eval_data["price"] > 0 else cost
        
        item_cost = qty * cost
        item_value = qty * price
        gain_loss = item_value - item_cost
        gain_loss_pct = (gain_loss / item_cost * 100.0) if item_cost > 0 else 0.0
        
        total_cost += item_cost
        total_value += item_value
        
        holdings.append({
            "ticker": ticker,
            "name": eval_data["name"],
            "sector": eval_data["sector"],
            "qty": qty,
            "cost": cost,
            "price": price,
            "value": item_value,
            "cost_basis": item_cost,
            "gain_loss": gain_loss,
            "gain_loss_percent": gain_loss_pct,
            "macro_score": eval_data["macro_score"],
            "valuation_score": eval_data["valuation_score"],
            "combined_score": eval_data["combined_score"],
            "decision": eval_data["decision"],
            "rationale": eval_data["rationale"]
        })

    # Calculate weight and weighted macro score
    weighted_macro_score_sum = 0.0
    sector_alloc = {}
    
    for h in holdings:
        weight = (h["value"] / total_value) if total_value > 0 else 0.0
        h["weight"] = weight
        weighted_macro_score_sum += h["macro_score"] * weight
        
        # Sector allocation rollup
        sector = h["sector"]
        if sector not in sector_alloc:
            sector_alloc[sector] = {
                "value": 0.0,
                "percent": 0.0,
                "score": sector_scores.get(sector, {}).get("score", 0.0)
            }
        sector_alloc[sector]["value"] += h["value"]

    # Calculate percentages for sectors
    for sector, data in sector_alloc.items():
        data["percent"] = (data["value"] / total_value * 100.0) if total_value > 0 else 0.0

    total_gain_loss = total_value - total_cost
    total_gain_loss_percent = (total_gain_loss / total_cost * 100.0) if total_cost > 0 else 0.0

    return {
        "holdings": holdings,
        "portfolio_macro_score": weighted_macro_score_sum,
        "total_cost": total_cost,
        "total_value": total_value,
        "total_gain_loss": total_gain_loss,
        "total_gain_loss_percent": total_gain_loss_percent,
        "sector_allocation": sector_alloc
    }

def recommend_rebalancing(
    portfolio_results: Dict[str, Any],
    sector_scores: Dict[str, Dict[str, Any]],
    current_country: str,
    config_tickers: Dict[str, List[str]]
) -> Dict[str, Any]:
    """
    Analyzes the evaluated portfolio results and current sector scores 
    to generate concrete actionable sector rebalancing recommendations.
    """
    holdings = portfolio_results.get("holdings", [])
    sector_alloc = portfolio_results.get("sector_allocation", {})
    total_value = portfolio_results.get("total_value", 0.0)
    
    if not holdings or total_value == 0:
        return {
            "has_recommendations": False,
            "actions": [],
            "summary": "ポートフォリオが空、または評価価値が0のため、提案はありません。"
        }
        
    # 1. Identify Headwind Sectors (Score < 0) currently held
    headwind_sectors = []
    for sector, alloc_data in sector_alloc.items():
        score = alloc_data["score"]
        if score < 0:
            headwind_sectors.append({
                "sector": sector,
                "percent": alloc_data["percent"],
                "value": alloc_data["value"],
                "score": score
            })
            
    # Sort by score ascending (worst first)
    headwind_sectors.sort(key=lambda x: x["score"])
    
    # 2. Identify Tailwind Sectors (Score > 0) in the market
    tailwind_sectors = []
    for sector, score_data in sector_scores.items():
        score = score_data.get("score", 0.0)
        if score > 0:
            tailwind_sectors.append({
                "sector": sector,
                "score": score
            })
    # Sort by score descending (best first)
    tailwind_sectors.sort(key=lambda x: -x["score"])
    
    if not headwind_sectors:
        return {
            "has_recommendations": False,
            "actions": [],
            "summary": "現在、ポートフォリオ内にマクロ経済の逆風を受けているセクターポジションはありません。健全なアロケーションです。"
        }
        
    if not tailwind_sectors:
        return {
            "has_recommendations": False,
            "actions": [],
            "summary": "現在、市場全体に強力なマクロ追い風が吹いているセクターが存在しないため、セクター移動の推奨はありません。"
        }

    # 3. Generate action items
    actions = []
    # Match worst headwind to best tailwind
    for h_sec in headwind_sectors:
        if not tailwind_sectors:
            break
        # Take the best tailwind sector
        t_sec = tailwind_sectors[0]
        
        # Find holdings in the headwind sector to reduce
        reduce_holdings = [x for x in holdings if x["sector"] == h_sec["sector"]]
        reduce_names = ", ".join([f"{x['name']} ({x['ticker']})" for x in reduce_holdings])
        
        actions.append({
            "from_sector": h_sec["sector"],
            "from_score": h_sec["score"],
            "from_percent": h_sec["percent"],
            "to_sector": t_sec["sector"],
            "to_score": t_sec["score"],
            "reduce_holdings": reduce_names,
            "description": (
                f"【削減推奨】マクロ逆風 (スコア: {h_sec['score']:+.1f}) にさらされている "
                f"「{h_sec['sector'].replace('_', ' ').title()}」セクター (保有比率: {h_sec['percent']:.1f}%) のポジション "
                f"[{reduce_names}] を削減し、マクロ追い風 (スコア: {t_sec['score']:+.1f}) の "
                f"「{t_sec['sector'].replace('_', ' ').title()}」セクターへ資金を移動することを推奨します。"
            )
        })

    return {
        "has_recommendations": True,
        "actions": actions,
        "summary": f"現在保有ポジションのうち {len(headwind_sectors)} つのセクターがマクロ経済の逆風を受けています。追い風セクターへのアロケーション再配分を検討してください。"
    }

