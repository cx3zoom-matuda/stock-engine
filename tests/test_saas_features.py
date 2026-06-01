import unittest
import os
import sqlite3
import pathlib
import sys

# Ensure project root is in the path
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from src.db import (
    init_db, seed_demo_data, get_connection, create_portfolio,
    delete_portfolio, save_holdings, get_portfolio_holdings, get_user_portfolios
)
from src.scheduler import trigger_macro_event

TEST_DB_PATH = "data/test_macro_cache.db"

class TestSaaSFeatures(unittest.TestCase):
    
    BACKUP_DB_PATH = "data/macro_cache.db.backup"
    REAL_DB_PATH = "data/macro_cache.db"
    
    @classmethod
    def setUpClass(cls):
        # Ensure data folder exists
        pathlib.Path("data").mkdir(parents=True, exist_ok=True)
        # Backup real db if exists
        if os.path.exists(cls.REAL_DB_PATH):
            if os.path.exists(cls.BACKUP_DB_PATH):
                os.remove(cls.BACKUP_DB_PATH)
            os.rename(cls.REAL_DB_PATH, cls.BACKUP_DB_PATH)
            
    @classmethod
    def tearDownClass(cls):
        # Restore real db if backup exists
        if os.path.exists(cls.REAL_DB_PATH):
            os.remove(cls.REAL_DB_PATH)
        if os.path.exists(cls.BACKUP_DB_PATH):
            os.rename(cls.BACKUP_DB_PATH, cls.REAL_DB_PATH)
            
    def setUp(self):
        # Initialize DB schemas on the default database (backed up)
        init_db()
        seed_demo_data()
        
    def tearDown(self):
        # Clear database for next test
        if os.path.exists(self.REAL_DB_PATH):
            os.remove(self.REAL_DB_PATH)
                
    def test_database_initialization(self):
        """Verifies all required tables are successfully created."""
        conn = get_connection()
        cursor = conn.cursor()
        
        tables = [
            "users", "portfolios", "holdings", "macro_events", 
            "portfolio_evaluations", "holding_evaluations", 
            "notification_settings", "notification_logs"
        ]
        
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            self.assertIsNotNone(cursor.fetchone(), f"Table {table} was not created.")
            
        conn.close()
        
    def test_demo_user_seeding(self):
        """Verifies the demo user and default portfolios are seeded."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, email, plan FROM users WHERE email='demo@example.com'")
        user = cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user["plan"], "Pro")
        
        # Check that 5 paper trading portfolios exist
        cursor.execute("SELECT count(*) as count FROM portfolios WHERE user_id=? AND is_virtual=1", (user["id"],))
        self.assertEqual(cursor.fetchone()["count"], 5)
        
        conn.close()
        
    def test_portfolio_lifecycle(self):
        """Verifies creating, loading holdings, and deleting a portfolio works without errors."""
        # 1. Create portfolio
        user_id = 1 # Demo user
        port_id = create_portfolio(
            user_id=user_id,
            name="Test Growth Portfolio",
            is_virtual=0
        )
        self.assertTrue(port_id > 0)
        
        # 2. Add Holdings
        holdings = [
            {"ticker": "AAPL", "qty": 10.0, "cost": 150.0, "name": "Apple Inc", "sector": "electronics"},
            {"ticker": "7203.T", "qty": 100.0, "cost": 2000.0, "name": "Toyota Motor", "sector": "automobile"}
        ]
        save_holdings(port_id, holdings)
        
        # 3. Retrieve Holdings
        db_holdings = get_portfolio_holdings(port_id)
        self.assertEqual(len(db_holdings), 2)
        self.assertEqual(db_holdings[0]["ticker"], "7203.T") # Ordered alphabetically by ticker ASC
        self.assertEqual(db_holdings[1]["ticker"], "AAPL")
        
        # 4. Delete Portfolio
        delete_portfolio(port_id)
        
        # Retrieve after delete
        db_holdings_after = get_portfolio_holdings(port_id)
        self.assertEqual(len(db_holdings_after), 0)
        
        user_ports = get_user_portfolios(user_id)
        # Check that the test growth portfolio is gone (only 5 virtual portfolios remain)
        self.assertEqual(len([p for p in user_ports if p["is_virtual"] == 0]), 0)

    def test_event_evaluation_and_alert_logging(self):
        """Verifies that trigger_macro_event recalculates portfolios and logs notifications."""
        import asyncio
        from src.db import get_notification_settings, save_notification_settings
        
        # 1. Create a Pro user portfolio with active holdings
        user_id = 1 # Demo user is Pro by default
        port_id = create_portfolio(
            user_id=user_id,
            name="Test Alert Portfolio",
            is_virtual=0
        )
        
        # Enable notifications for user (both email and telegram)
        save_notification_settings(
            user_id=user_id,
            email_enabled=1,
            slack_enabled=0,
            slack_webhook_url="",
            min_severity=2,
            event_types="cpi_shock,rate_hike",
            frequency="instant",
            telegram_enabled=1,
            telegram_bot_token="123456:dummy_bot_token",
            telegram_chat_id="987654321"
        )
        
        holdings = [
            {"ticker": "AAPL", "qty": 10.0, "cost": 150.0, "name": "Apple Inc", "sector": "electronics"},
            {"ticker": "7203.T", "qty": 100.0, "cost": 2000.0, "name": "Toyota Motor", "sector": "automobile"}
        ]
        save_holdings(port_id, holdings)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Trigger a Severity 3 CPI shock event
            event_id = loop.run_until_complete(
                trigger_macro_event(
                    event_type="cpi_shock",
                    region="US",
                    value=5.5,
                    prev_value=4.0,
                    change_rate=37.5,
                    severity=3,
                    source="FRED Test"
                )
            )
            self.assertTrue(event_id > 0)
            
            # Check DB for evaluation records
            conn = get_connection()
            cursor = conn.cursor()
            
            # Verify macro event is logged
            cursor.execute("SELECT id, event_type FROM macro_events WHERE id = ?", (event_id,))
            event_row = cursor.fetchone()
            self.assertIsNotNone(event_row)
            self.assertEqual(event_row["event_type"], "cpi_shock")
            
            # Verify portfolio evaluation was logged
            cursor.execute("SELECT count(*) as count FROM portfolio_evaluations WHERE portfolio_id = ? AND macro_event_id = ?", (port_id, event_id))
            self.assertEqual(cursor.fetchone()["count"], 1)
            
            # Verify notification logs for Email
            cursor.execute("SELECT count(*) as count FROM notification_logs WHERE user_id = ? AND portfolio_id = ? AND channel = 'Email'", (user_id, port_id))
            self.assertEqual(cursor.fetchone()["count"], 1)

            # Verify notification logs for Telegram (it attempts to call api.telegram.org, which fails in unit tests, logging status='Failed')
            cursor.execute("SELECT count(*) as count FROM notification_logs WHERE user_id = ? AND portfolio_id = ? AND channel = 'Telegram'", (user_id, port_id))
            self.assertEqual(cursor.fetchone()["count"], 1)
            
            conn.close()
        finally:
            loop.close()

if __name__ == "__main__":
    unittest.main()
