import io
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

def parse_portfolio_csv(uploaded_file) -> pd.DataFrame:
    """
    Parses a portfolio CSV file (from Rakuten, SBI, or standard Universal format)
    and returns a normalized DataFrame with:
    - ticker (str)
    - qty (float)
    - cost (float)
    """
    raw_data = uploaded_file.read()
    # Try different encodings
    for encoding in ['utf-8', 'utf-8-sig', 'shift_jis', 'cp932']:
        try:
            text = raw_data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Could not decode the CSV file. Please upload a valid CSV encoded in UTF-8 or Shift_JIS.")

    lines = text.split('\n')
    start_idx = -1
    
    # Supported column mappings case-insensitive (supports Rakuten, SBI, IBKR, Schwab, Robinhood, etc.)
    ticker_synonyms = ['ticker', 'symbol', 'code', 'コード', 'ティッカー', '銘柄コード', '銘柄']
    qty_synonyms = ['qty', 'quantity', 'shares', '保有数量', '数量', '保有口数', '残高', '株数']
    cost_synonyms = [
        'cost_basis', 'cost basis', 'average price', 'average_price', 
        'average cost', 'average_cost', 'avg price', 'avg_cost', 'avg cost', 
        '取得単価', '平均取得価額', '平均取得価格', '参考単価', '単価',
        'cost', 'price'
    ]

    # Find the header row
    for idx, line in enumerate(lines):
        line_lower = line.lower()
        has_ticker = any(s in line_lower for s in ticker_synonyms)
        has_qty = any(s in line_lower for s in qty_synonyms)
        has_cost = any(s in line_lower for s in cost_synonyms)
        if has_ticker and has_qty and has_cost:
            start_idx = idx
            break

    if start_idx == -1:
        raise ValueError(
            "Could not identify header row. The CSV must contain columns for Ticker/Symbol, Quantity, and Average Cost. "
            "(CSVのヘッダー行が見つかりませんでした。銘柄コード/ティッカー、保有数量、平均取得単価に対応する列が必要です。)"
        )

    # Read CSV starting from the identified header line
    df = pd.read_csv(io.StringIO('\n'.join(lines[start_idx:])))
    
    # Strip column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # Map columns
    ticker_col = None
    for s in ticker_synonyms:
        if s in df.columns:
            ticker_col = s
            break
            
    qty_col = None
    for s in qty_synonyms:
        if s in df.columns:
            qty_col = s
            break

    cost_col = None
    for s in cost_synonyms:
        if s in df.columns:
            cost_col = s
            break

    if not ticker_col or not qty_col or not cost_col:
        raise ValueError("Failed to map required columns.")

    # Clean data (remove NaN, empty values)
    df = df.dropna(subset=[ticker_col, qty_col])
    
    # Remove rows that are totals or non-data (e.g., '合計')
    df = df[df[ticker_col].apply(lambda x: str(x).strip() != '' and '合計' not in str(x) and 'total' not in str(x).lower())]
    
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
            
        # Clean ticker: If it's a 4-digit digit or number, append '.T' for Yahoo Finance
        if raw_ticker.isdigit() and len(raw_ticker) == 4:
            ticker = f"{raw_ticker}.T"
        else:
            ticker = raw_ticker.upper() # Standardize to uppercase for global tickers (e.g. AAPL)

        # Clean quantity and cost
        try:
            qty_val = str(row[qty_col]).replace(',', '').strip()
            cost_val = str(row[cost_col]).replace(',', '').strip()
            
            qty = float(qty_val)
            cost = float(cost_val)
        except Exception:
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
    config_tickers: Dict[str, List[str]],
    language: str = "jp"
) -> Dict[str, Any]:
    """
    Analyzes the evaluated portfolio results and current sector scores 
    to generate concrete actionable sector rebalancing recommendations.
    """
    holdings = portfolio_results.get("holdings", [])
    sector_alloc = portfolio_results.get("sector_allocation", {})
    total_value = portfolio_results.get("total_value", 0.0)
    is_en = (language == "en")
    
    if not holdings or total_value == 0:
        return {
            "has_recommendations": False,
            "actions": [],
            "summary": "No holdings or portfolio value is 0. No suggestions available." if is_en else "ポートフォリオが空、または評価価値が0のため、提案はありません。"
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
            "summary": "No active positions in this portfolio are facing macroeconomic headwinds. Allocation is healthy." if is_en else "現在、ポートフォリオ内にマクロ経済の逆風を受けているセクターポジションはありません。健全なアロケーションです。"
        }
        
    if not tailwind_sectors:
        return {
            "has_recommendations": False,
            "actions": [],
            "summary": "No sector moves recommended as there are no strong macroeconomic tailwinds in the market currently." if is_en else "現在、市場全体に強力なマクロ追い風が吹いているセクターが存在しないため、セクター移動の推奨はありません。"
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
        
        from_sector_name = h_sec["sector"].replace('_', ' ').title()
        to_sector_name = t_sec["sector"].replace('_', ' ').title()
        
        if is_en:
            desc = (
                f"[Recommend Reduction] Positions [{reduce_names}] in the '{from_sector_name}' sector "
                f"(allocation: {h_sec['percent']:.1f}%) are facing macro headwinds (score: {h_sec['score']:+.1f}). "
                f"It is recommended to reduce these positions and reallocate capital to the '{to_sector_name}' sector "
                f"which has macro tailwinds (score: {t_sec['score']:+.1f})."
            )
        else:
            desc = (
                f"【削減推奨】マクロ逆風 (スコア: {h_sec['score']:+.1f}) にさらされている "
                f"「{from_sector_name}」セクター (保有比率: {h_sec['percent']:.1f}%) のポジション "
                f"[{reduce_names}] を削減し、マクロ追い風 (スコア: {t_sec['score']:+.1f}) の "
                f"「{to_sector_name}」セクターへ資金を移動することを推奨します。"
            )
            
        actions.append({
            "from_sector": h_sec["sector"],
            "from_score": h_sec["score"],
            "from_percent": h_sec["percent"],
            "to_sector": t_sec["sector"],
            "to_score": t_sec["score"],
            "reduce_holdings": reduce_names,
            "description": desc
        })

    if is_en:
        summary = f"Currently, {len(headwind_sectors)} sectors in your holdings are facing macroeconomic headwinds. Consider rebalancing into tailwind sectors."
    else:
        summary = f"現在保有ポジションのうち {len(headwind_sectors)} つのセクターがマクロ経済の逆風を受けています。追い風セクターへのアロケーション再配分を検討してください。"

    return {
        "has_recommendations": True,
        "actions": actions,
        "summary": summary
    }


def generate_portfolio_html_report(acc, results, sector_scores, current_country, language="en") -> str:
    """
    Generates a beautifully formatted, print-ready HTML review report of the portfolio,
    including summary statistics, holdings breakdown, risk analysis, and rebalancing suggestions.
    Supports English and Japanese.
    """
    is_jp = (language == "jp")
    
    # 1. Setup Localized Labels
    labels = {
        "title": "📊 G20マクロ・ポートフォリオ診断レポート" if is_jp else "📊 G20 Macro Portfolio Review Report",
        "acc_name": "口座名" if is_jp else "Account Name",
        "gen_date": "診断日時" if is_jp else "Generated Date",
        "market": "分析対象市場" if is_jp else "Target Market",
        "summary_title": "💰 資産運用サマリー" if is_jp else "💰 Asset Management Summary",
        "cash": "現金残高" if is_jp else "Cash Balance",
        "stock_value": "株式保有時価" if is_jp else "Stock Value",
        "total_assets": "総資産額" if is_jp else "Total Assets",
        "profit_loss": "通算純損益" if is_jp else "Total Profit/Loss",
        "macro_score": "ポートフォリオ・マクロ適合度" if is_jp else "Portfolio Macro Score",
        "positions_title": "📁 保有ポジション詳細" if is_jp else "📁 Current Holdings Details",
        "col_decision": "判定" if is_jp else "Decision",
        "col_ticker": "コード" if is_jp else "Ticker",
        "col_name": "銘柄名" if is_jp else "Name",
        "col_sector": "セクター" if is_jp else "Sector",
        "col_weight": "保有比率" if is_jp else "Weight",
        "col_cost": "取得単価" if is_jp else "Avg Cost",
        "col_price": "現在値" if is_jp else "Price",
        "col_val": "評価額" if is_jp else "Current Value",
        "col_return": "損益 (率)" if is_jp else "Return",
        "col_m_score": "マクロ" if is_jp else "Macro",
        "risk_title": "🚨 マクロ経済の逆風リスク" if is_jp else "🚨 Macro Headwind Risks",
        "rebalance_title": "⚖️ セクターリバランス提案" if is_jp else "⚖️ Sector Rebalancing Recommendations",
        "footer": "本レポートはマクロエンジンによって自動生成されました。投資の最終判断は自己責任で行ってください。" if is_jp else "This report was auto-generated by Macro Engine. Final investment decisions are your own responsibility."
    }

    # Format numbers helper
    symbol = acc.currency
    def fmt_currency(val):
        if symbol == "¥":
            return f"¥{val:,.0f}"
        return f"{symbol}{val:,.2f}"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 2. Extract values
    cash = acc.cash
    total_val = results.get("total_value", 0.0)
    total_assets = cash + total_val
    gain_loss = total_assets - acc.initial_balance
    gain_loss_pct = (gain_loss / acc.initial_balance * 100.0) if acc.initial_balance > 0 else 0.0
    macro_score = results.get("portfolio_macro_score", 0.0)
    
    # Macro score status label
    if macro_score >= 10.0:
        macro_status = "追い風 🟢 (Tailwind)" if is_jp else "Tailwind 🟢"
        macro_status_class = "tailwind"
    elif macro_score <= -10.0:
        macro_status = "逆風 🔴 (Headwind)" if is_jp else "Headwind 🔴"
        macro_status_class = "headwind"
    else:
        macro_status = "中立 🟡 (Neutral)" if is_jp else "Neutral 🟡"
        macro_status_class = "neutral"

    # Profit class
    profit_class = "profit" if gain_loss >= 0 else "loss"

    # Build holdings table rows
    holdings_rows = ""
    for h in results.get("holdings", []):
        ret_val = h["gain_loss"]
        ret_pct = h["gain_loss_percent"]
        ret_class = "profit" if ret_val >= 0 else "loss"
        
        dec = h["decision"]
        dec_class = dec.lower()
        
        holdings_rows += f"""
        <tr>
            <td><span class="badge badge-{dec_class}">{dec}</span></td>
            <td><strong>{h['ticker']}</strong></td>
            <td>{h['name']}</td>
            <td>{h['sector'].replace('_', ' ').title()}</td>
            <td>{h['weight']*100:.1f}%</td>
            <td>{fmt_currency(h['cost'])}</td>
            <td>{fmt_currency(h['price'])}</td>
            <td>{fmt_currency(h['value'])}</td>
            <td class="{ret_class}">{fmt_currency(ret_val)} ({ret_pct:+.2f}%)</td>
            <td>{h['macro_score']:+.1f}</td>
        </tr>
        """

    # Build risk list
    headwind_holdings = [h for h in results.get("holdings", []) if h["macro_score"] <= -10.0]
    risk_html = ""
    if headwind_holdings:
        risk_html = "<ul>"
        for h in headwind_holdings:
            risk_html += f"""
            <li>
                <strong>{h['name']} ({h['ticker']})</strong>: マクロスコア {h['macro_score']:+.1f}<br/>
                <span class="text-muted">理由: {h['rationale']}</span>
            </li>
            """
        risk_html += "</ul>"
    else:
        risk_html = f"<p class='success-text'>{'このポートフォリオ内にはマクロ経済の逆風を受けているポジションはありません。' if is_jp else 'No positions in this portfolio are facing macroeconomic headwinds.'}</p>"

    # Build rebalance recommendation
    recs = recommend_rebalancing(results, sector_scores, current_country, {})
    rebalance_html = f"<p><strong>{recs['summary']}</strong></p>"
    if recs.get("has_recommendations"):
        rebalance_html += "<ul>"
        for action in recs["actions"]:
            rebalance_html += f"<li>{action['description']}</li>"
        rebalance_html += "</ul>"

    # HTML Output
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{labels['title']}</title>
    <style>
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Hiragino Kaku Gothic ProN', Meiryo, sans-serif;
            color: #334155;
            background-color: #f8fafc;
            margin: 0;
            padding: 30px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid #e2e8f0;
        }}
        .header {{
            border-bottom: 2px solid #0284c7;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #0f172a;
            margin: 0 0 10px 0;
            font-size: 26px;
        }}
        .meta-info {{
            display: flex;
            justify-content: space-between;
            font-size: 14px;
            color: #64748b;
        }}
        h2 {{
            color: #0f172a;
            font-size: 18px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
            margin-top: 30px;
        }}
        .grid-summary {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }}
        .card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .card .label {{
            font-size: 12px;
            color: #64748b;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .card .value {{
            font-size: 18px;
            font-weight: bold;
            color: #0f172a;
        }}
        .card-macro {{
            grid-column: span 4;
            background: #f0f9ff;
            border-color: #bae6fd;
            display: flex;
            justify-content: space-between;
            align-items: center;
            text-align: left;
            padding: 15px 25px;
        }}
        .card-macro .value-container {{
            text-align: right;
        }}
        .card-macro .macro-tag {{
            font-size: 20px;
            font-weight: bold;
        }}
        .tailwind {{ color: #10b981; }}
        .headwind {{ color: #ef4444; }}
        .neutral {{ color: #f59e0b; }}
        .profit {{ color: #10b981; }}
        .loss {{ color: #ef4444; }}
        .text-muted {{ color: #94a3b8; font-size: 13px; }}
        .success-text {{ color: #10b981; font-weight: bold; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            margin-bottom: 30px;
            font-size: 13px;
        }}
        th {{
            background-color: #f1f5f9;
            color: #475569;
            font-weight: bold;
            text-align: left;
            padding: 10px;
            border-bottom: 2px solid #cbd5e1;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            text-align: center;
        }}
        .badge-buy {{ background-color: #dcfce7; color: #15803d; }}
        .badge-watch {{ background-color: #fef9c3; color: #a16207; }}
        .badge-avoid {{ background-color: #fee2e2; color: #b91c1c; }}
        ul {{
            padding-left: 20px;
            margin: 15px 0;
        }}
        li {{
            margin-bottom: 10px;
        }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: #94a3b8;
            margin-top: 50px;
            border-top: 1px solid #e2e8f0;
            padding-top: 15px;
        }}
        .print-btn-container {{
            text-align: right;
            margin-bottom: 20px;
        }}
        .btn {{
            background-color: #0284c7;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
        }}
        .btn:hover {{
            background-color: #0369a1;
        }}
        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                border: none;
                padding: 0;
                max-width: 100%;
            }}
            .no-print {{
                display: none !important;
            }}
            tr {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="print-btn-container no-print">
            <button class="btn" onclick="window.print()">🖨️ PDFとして印刷・保存</button>
        </div>
        
        <div class="header">
            <h1>{labels['title']}</h1>
            <div class="meta-info">
                <div><strong>{labels['acc_name']}:</strong> {acc.name}</div>
                <div><strong>{labels['market']}:</strong> {current_country}</div>
                <div><strong>{labels['gen_date']}:</strong> {now_str}</div>
            </div>
        </div>

        <h2>{labels['summary_title']}</h2>
        <div class="grid-summary">
            <div class="card">
                <div class="label">{labels['cash']}</div>
                <div class="value">{fmt_currency(cash)}</div>
            </div>
            <div class="card">
                <div class="label">{labels['stock_value']}</div>
                <div class="value">{fmt_currency(total_val)}</div>
            </div>
            <div class="card">
                <div class="label">{labels['total_assets']}</div>
                <div class="value">{fmt_currency(total_assets)}</div>
            </div>
            <div class="card">
                <div class="label">{labels['profit_loss']}</div>
                <div class="value {profit_class}">{fmt_currency(gain_loss)} ({gain_loss_pct:+.2f}%)</div>
            </div>
            
            <div class="card card-macro">
                <div>
                    <div class="label" style="margin-bottom:2px;">{labels['macro_score']}</div>
                    <span style="font-size:13px; color:#64748b;">(ポートフォリオ加重平均マクロスコア)</span>
                </div>
                <div class="value-container">
                    <div class="macro-tag {macro_status_class}">{macro_score:+.2f}</div>
                    <div class="label {macro_status_class}" style="margin-top:2px;">{macro_status}</div>
                </div>
            </div>
        </div>

        <h2>{labels['positions_title']}</h2>
        <table>
            <thead>
                <tr>
                    <th>{labels['col_decision']}</th>
                    <th>{labels['col_ticker']}</th>
                    <th>{labels['col_name']}</th>
                    <th>{labels['col_sector']}</th>
                    <th>{labels['col_weight']}</th>
                    <th>{labels['col_cost']}</th>
                    <th>{labels['col_price']}</th>
                    <th>{labels['col_val']}</th>
                    <th>{labels['col_return']}</th>
                    <th>{labels['col_m_score']}</th>
                </tr>
            </thead>
            <tbody>
                {holdings_rows}
            </tbody>
        </table>

        <h2>{labels['risk_title']}</h2>
        {risk_html}

        <h2>{labels['rebalance_title']}</h2>
        {rebalance_html}

        <div class="footer">
            <p>{labels['footer']}</p>
        </div>
    </div>
</body>
</html>
"""
    return html


