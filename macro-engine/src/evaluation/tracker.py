import sqlite3
import pathlib
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from ..ingestion.market_data import MarketDataClient

logger = logging.getLogger(__name__)

class PredictionTracker:
    """
    Logs stock evaluation decisions and tracks their historical performance (hit/miss rate).
    """
    def __init__(self, db_path: str = "data/macro_cache.db"):
        self.db_path = db_path
        self._init_db()
        self.seed_mock_data_if_empty()

    def _init_db(self):
        """Initializes the prediction history database table."""
        try:
            db_dir = pathlib.Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    name TEXT NOT NULL,
                    prediction_date TIMESTAMP NOT NULL,
                    predicted_decision TEXT NOT NULL,
                    start_price REAL NOT NULL,
                    current_price REAL,
                    return_pct REAL,
                    hit_status TEXT, -- 'Hit', 'Miss', 'Pending'
                    macro_score REAL,
                    valuation_score REAL,
                    combined_score REAL,
                    last_updated TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize prediction database: {e}")

    def log_predictions(self, evaluated_stocks: List[Dict[str, Any]]):
        """
        Logs current predictions. If a prediction for the same ticker already exists
        on the same calendar day, it is updated; otherwise a new record is inserted.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            now_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

            for stock in evaluated_stocks:
                ticker = stock["ticker"]
                name = stock["name"]
                decision = stock["decision"]
                price = stock["price"]
                macro = stock["macro_score"]
                val = stock["valuation_score"]
                comb = stock["combined_score"]

                # Check if a record exists for this ticker on the same calendar day
                cursor.execute(
                    "SELECT id FROM prediction_history WHERE ticker = ? AND date(prediction_date) = ?",
                    (ticker, today_str)
                )
                row = cursor.fetchone()

                if row:
                    # Update existing record
                    cursor.execute(
                        """
                        UPDATE prediction_history
                        SET name = ?, predicted_decision = ?, start_price = ?,
                            macro_score = ?, valuation_score = ?, combined_score = ?,
                            last_updated = ?
                        WHERE id = ?
                        """,
                        (name, decision, price, macro, val, comb, now_timestamp, row[0])
                    )
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO prediction_history 
                        (ticker, name, prediction_date, predicted_decision, start_price, 
                         current_price, return_pct, hit_status, macro_score, valuation_score, 
                         combined_score, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (ticker, name, now_timestamp, decision, price, 
                         price, 0.0, "Pending", macro, val, comb, now_timestamp)
                    )
                    
            conn.commit()
            conn.close()
            logger.info(f"Successfully logged {len(evaluated_stocks)} predictions.")
        except Exception as e:
            logger.error(f"Error logging predictions: {e}")

    def get_history(self, decision_filter: str = "All", status_filter: str = "All") -> List[Dict[str, Any]]:
        """
        Retrieves historical predictions with optional filters.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM prediction_history WHERE 1=1"
            params = []

            if decision_filter != "All":
                query += " AND predicted_decision = ?"
                params.append(decision_filter)

            if status_filter != "All":
                query += " AND hit_status = ?"
                params.append(status_filter)

            query += " ORDER BY prediction_date DESC"

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "prediction_date": row["prediction_date"],
                    "predicted_decision": row["predicted_decision"],
                    "start_price": row["start_price"],
                    "current_price": row["current_price"],
                    "return_pct": row["return_pct"],
                    "hit_status": row["hit_status"],
                    "macro_score": row["macro_score"],
                    "valuation_score": row["valuation_score"],
                    "combined_score": row["combined_score"],
                    "last_updated": row["last_updated"]
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching prediction history: {e}")
            return []

    async def update_prices(self) -> Tuple[int, int]:
        """
        Fetches current prices for all stocks in the history and updates return percentages and statuses.
        Returns:
            Tuple containing (updated_count, error_count)
        """
        history = self.get_history()
        if not history:
            return 0, 0

        # Unique tickers to update
        tickers = list(set(item["ticker"] for item in history))
        
        # Instantiate MarketDataClient (enable cache check)
        market_client = MarketDataClient(cache_db_path=self.db_path)
        
        # Fetch current metrics
        logger.info(f"Fetching current prices for {len(tickers)} tickers to update verification board...")
        current_prices = {}
        errors = 0
        
        async def fetch_price(t):
            try:
                metrics = await market_client.fetch_stock_metrics(t)
                return t, metrics.get("price")
            except Exception as e:
                logger.warning(f"Could not fetch price for ticker {t}: {e}")
                return t, None

        tasks = [fetch_price(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        for t, price in results:
            if price is not None:
                current_prices[t] = price
            else:
                errors += 1

        # Update records in db
        updated_count = 0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for item in history:
                ticker = item["ticker"]
                start_price = item["start_price"]
                decision = item["predicted_decision"]
                pred_date_str = item["prediction_date"]
                
                curr_price = current_prices.get(ticker)
                if curr_price is None:
                    continue

                # Calculate return
                ret_pct = 0.0
                if start_price > 0:
                    ret_pct = ((curr_price - start_price) / start_price) * 100.0

                # Determine hit status
                # If prediction is same calendar day, set as Pending
                pred_date = datetime.strptime(pred_date_str, "%Y-%m-%d %H:%M:%S")
                is_same_day = pred_date.date() == datetime.now().date()
                
                if decision == "WATCH":
                    hit_status = "Pending"  # Watch isn't an active directional call
                elif is_same_day:
                    hit_status = "Pending"  # Same day predictions are pending
                else:
                    if decision == "BUY":
                        hit_status = "Hit" if ret_pct > 0.0 else "Miss"
                    elif decision == "AVOID":
                        hit_status = "Hit" if ret_pct < 0.0 else "Miss"
                    else:
                        hit_status = "Pending"

                cursor.execute(
                    """
                    UPDATE prediction_history
                    SET current_price = ?, return_pct = ?, hit_status = ?, last_updated = ?
                    WHERE id = ?
                    """,
                    (curr_price, ret_pct, hit_status, now_str, item["id"])
                )
                updated_count += 1

            conn.commit()
            conn.close()
            logger.info(f"Updated {updated_count} prediction records in database.")
        except Exception as e:
            logger.error(f"Error updating prices in database: {e}")
            errors += len(history)

        return updated_count, errors

    def calculate_kpis(self) -> Dict[str, Any]:
        """
        Calculates and returns performance metrics for the verification board.
        """
        history = self.get_history()
        
        total_tracked = len(history)
        buy_total = 0
        buy_hits = 0
        buy_returns = []
        
        avoid_total = 0
        avoid_hits = 0
        avoid_returns = []
        
        active_hits = 0
        active_evaluated = 0

        for item in history:
            decision = item["predicted_decision"]
            status = item["hit_status"]
            ret = item["return_pct"] or 0.0

            if decision == "BUY":
                buy_total += 1
                buy_returns.append(ret)
                if status == "Hit":
                    buy_hits += 1
                    active_hits += 1
                    active_evaluated += 1
                elif status == "Miss":
                    active_evaluated += 1

            elif decision == "AVOID":
                avoid_total += 1
                avoid_returns.append(ret)
                if status == "Hit":
                    avoid_hits += 1
                    active_hits += 1
                    active_evaluated += 1
                elif status == "Miss":
                    active_evaluated += 1

        overall_hit_rate = 0.0
        if active_evaluated > 0:
            overall_hit_rate = (active_hits / active_evaluated) * 100.0

        buy_hit_rate = 0.0
        if buy_total - sum(1 for item in history if item["predicted_decision"] == "BUY" and item["hit_status"] == "Pending") > 0:
            evaluated_buys = sum(1 for item in history if item["predicted_decision"] == "BUY" and item["hit_status"] in ("Hit", "Miss"))
            if evaluated_buys > 0:
                buy_hit_rate = (buy_hits / evaluated_buys) * 100.0

        avoid_hit_rate = 0.0
        if avoid_total - sum(1 for item in history if item["predicted_decision"] == "AVOID" and item["hit_status"] == "Pending") > 0:
            evaluated_avoids = sum(1 for item in history if item["predicted_decision"] == "AVOID" and item["hit_status"] in ("Hit", "Miss"))
            if evaluated_avoids > 0:
                avoid_hit_rate = (avoid_hits / evaluated_avoids) * 100.0

        avg_buy_return = sum(buy_returns) / len(buy_returns) if buy_returns else 0.0
        avg_avoid_return = sum(avoid_returns) / len(avoid_returns) if avoid_returns else 0.0

        return {
            "overall_hit_rate": overall_hit_rate,
            "buy_hit_rate": buy_hit_rate,
            "buy_avg_return": avg_buy_return,
            "buy_total": buy_total,
            "avoid_hit_rate": avoid_hit_rate,
            "avoid_avg_return": avg_avoid_return,
            "avoid_total": avoid_total,
            "total_tracked": total_tracked
        }

    def seed_mock_data_if_empty(self):
        """Seeds mock historical prediction data to verify functionality immediately."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT count(*) FROM prediction_history")
            count = cursor.fetchone()[0]
            
            if count > 0:
                conn.close()
                return

            logger.info("Database is empty. Seeding mock predictions...")
            
            now = datetime.now()
            
            # Helper to calculate date string
            def days_ago(d):
                return (now - timedelta(days=d)).strftime("%Y-%m-%d 09:00:00")

            # Mock predictions list
            # Format: (ticker, name, prediction_date, decision, start_price, current_price, return_pct, hit_status, macro, val, comb, last_updated)
            mock_data = [
                # 30 Days Ago: Success BUY (Toyota)
                ("7203.T", "Toyota Motor Corp", days_ago(30), "BUY", 2600.0, 2800.0, 7.69, "Hit", 15.0, 10.0, 25.0, now.strftime("%Y-%m-%d %H:%M:%S")),
                # 14 Days Ago: Failed BUY (Softbank)
                ("9984.T", "SoftBank Group", days_ago(14), "BUY", 8500.0, 8200.0, -3.53, "Miss", 10.0, 5.0, 15.0, now.strftime("%Y-%m-%d %H:%M:%S")),
                # 7 Days Ago: Success AVOID (MUFG) - return is negative, which is a success for AVOID!
                ("8306.T", "Mitsubishi UFJ Financial", days_ago(7), "AVOID", 1600.0, 1520.0, -5.00, "Hit", -20.0, -10.0, -30.0, now.strftime("%Y-%m-%d %H:%M:%S")),
                # 30 Days Ago: Failed AVOID (NYK Line) - return is positive, which is a miss for AVOID!
                ("9101.T", "NYK Line", days_ago(30), "AVOID", 4100.0, 4300.0, 4.88, "Miss", -15.0, -15.0, -30.0, now.strftime("%Y-%m-%d %H:%M:%S")),
                # 7 Days Ago: WATCH (Sony)
                ("6758.T", "Sony Group", days_ago(7), "WATCH", 12400.0, 12500.0, 0.81, "Pending", 0.0, 0.0, 0.0, now.strftime("%Y-%m-%d %H:%M:%S")),
                # Today: Same day (INPEX) - status is Pending
                ("1605.T", "INPEX", now.strftime("%Y-%m-%d %H:%M:%S"), "BUY", 2100.0, 2100.0, 0.00, "Pending", 15.0, 10.0, 25.0, now.strftime("%Y-%m-%d %H:%M:%S"))
            ]

            cursor.executemany(
                """
                INSERT INTO prediction_history 
                (ticker, name, prediction_date, predicted_decision, start_price, 
                 current_price, return_pct, hit_status, macro_score, valuation_score, 
                 combined_score, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                mock_data
            )
            
            conn.commit()
            conn.close()
            logger.info("Successfully seeded mock historical predictions.")
        except Exception as e:
            logger.error(f"Error seeding mock data: {e}")
