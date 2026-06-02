import sqlite3
import pathlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = "data/macro_cache.db"

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a sqlite3 connection with Row factory enabled."""
    db_dir = pathlib.Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DB_PATH):
    """Initializes the database schema for the premium SaaS Pro roadmap features."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # 1. users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                plan TEXT DEFAULT 'Free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. portfolios Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                is_virtual INTEGER DEFAULT 0,
                cash_balance REAL DEFAULT 0.0,
                initial_balance REAL DEFAULT 100000.0,
                base_currency TEXT DEFAULT '$',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # 3. holdings Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                company_name TEXT,
                country TEXT,
                sector TEXT,
                quantity REAL NOT NULL,
                average_cost REAL NOT NULL,
                current_price REAL,
                market_value REAL,
                weight REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
            )
        """)

        # 4. macro_events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS macro_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                region TEXT NOT NULL,
                value REAL,
                previous_value REAL,
                change_rate REAL,
                severity INTEGER NOT NULL,
                source TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. portfolio_evaluations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                macro_event_id INTEGER,
                portfolio_macro_score REAL,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(portfolio_id) REFERENCES portfolios(id),
                FOREIGN KEY(macro_event_id) REFERENCES macro_events(id)
            )
        """)

        # 6. holding_evaluations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holding_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_evaluation_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                previous_rating TEXT,
                new_rating TEXT,
                macro_score REAL,
                valuation_score REAL,
                rationale TEXT,
                FOREIGN KEY(portfolio_evaluation_id) REFERENCES portfolio_evaluations(id)
            )
        """)

        # 7. notification_settings Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                email_enabled INTEGER DEFAULT 0,
                slack_enabled INTEGER DEFAULT 0,
                slack_webhook_url TEXT,
                telegram_enabled INTEGER DEFAULT 0,
                telegram_bot_token TEXT,
                telegram_chat_id TEXT,
                min_severity INTEGER DEFAULT 2,
                event_types TEXT DEFAULT 'cpi,fomc,oil_spike,rate_hike',
                frequency TEXT DEFAULT 'instant',
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Dynamically add Telegram & SMTP columns if table exists but lacks them
        try:
            cursor.execute("PRAGMA table_info(notification_settings)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "telegram_enabled" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN telegram_enabled INTEGER DEFAULT 0")
            if "telegram_bot_token" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN telegram_bot_token TEXT")
            if "telegram_chat_id" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN telegram_chat_id TEXT")
            if "smtp_host" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN smtp_host TEXT")
            if "smtp_port" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN smtp_port INTEGER DEFAULT 587")
            if "smtp_username" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN smtp_username TEXT")
            if "smtp_password" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN smtp_password TEXT")
            if "smtp_from" not in columns:
                cursor.execute("ALTER TABLE notification_settings ADD COLUMN smtp_from TEXT")
        except Exception as col_err:
            logger.warning(f"Failed to check/alter notification_settings schema: {col_err}")

        # 8. notification_logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                portfolio_id INTEGER,
                macro_event_id INTEGER,
                channel TEXT,
                status TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(portfolio_id) REFERENCES portfolios(id),
                FOREIGN KEY(macro_event_id) REFERENCES macro_events(id)
            )
        """)

        # 9. inquiries Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                message TEXT NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info("Successfully initialized stock-engine database tables.")
    except Exception as e:
        logger.error(f"Failed to initialize stock-engine database: {e}")
        raise e

def seed_demo_data(db_path: str = DB_PATH):
    """Seeds the database with a demo user and initial paper trade accounts/portfolios."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Seed Demo User
        cursor.execute("SELECT id FROM users WHERE email = 'demo@example.com'")
        user_row = cursor.fetchone()
        if not user_row:
            cursor.execute("INSERT INTO users (email, plan) VALUES ('demo@example.com', 'Pro')")
            user_id = cursor.lastrowid
            logger.info("Seeded demo user.")
        else:
            user_id = user_row["id"]

        # Seed Default Notification Settings for Demo User
        cursor.execute("SELECT id FROM notification_settings WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO notification_settings 
                (user_id, email_enabled, slack_enabled, min_severity, event_types, frequency) 
                VALUES (?, 1, 0, 2, 'cpi,fomc,rate_hike,oil_spike', 'instant')
            """, (user_id,))
            logger.info("Seeded notification settings for demo user.")

        # Seed 5 Paper Trade Portfolios if they do not exist
        cursor.execute("SELECT count(*) as count FROM portfolios WHERE user_id = ? AND is_virtual = 1", (user_id,))
        if cursor.fetchone()["count"] == 0:
            accounts = [
                ("📈 Macro Tailwind Focus", 100000.0, "$"),
                ("🛡️ Defensive & Income", 100000.0, "$"),
                ("🚀 Aggressive Growth", 100000.0, "$"),
                ("💎 Long-Term Value", 100000.0, "$"),
                ("🧪 Sandbox", 100000.0, "$")
            ]
            for name, balance, curr in accounts:
                cursor.execute("""
                    INSERT INTO portfolios (user_id, name, is_virtual, cash_balance, initial_balance, base_currency)
                    VALUES (?, ?, 1, ?, ?, ?)
                """, (user_id, name, balance, balance, curr))
            logger.info("Seeded paper trading portfolios.")

        # Seed positions/holdings inside the virtual portfolios if they are empty
        cursor.execute("SELECT id, name FROM portfolios WHERE user_id = ?", (user_id,))
        portfolios = cursor.fetchall()
        for p in portfolios:
            p_id = p["id"]
            p_name = p["name"]
            
            cursor.execute("SELECT count(*) as count FROM holdings WHERE portfolio_id = ?", (p_id,))
            if cursor.fetchone()["count"] == 0:
                # Assign holdings representing famous institutional profiles
                if "Macro Tailwind" in p_name:  # Warren Buffett / Berkshire Hathaway model
                    holdings = [
                        ("AAPL", "Apple Inc.", "US", "technology", 200, 170.0),
                        ("BAC", "Bank of America", "US", "financials", 500, 30.0),
                        ("AXP", "American Express", "US", "financials", 100, 180.0),
                        ("KO", "Coca-Cola Co.", "US", "consumer_staples", 300, 58.0),
                        ("CVX", "Chevron Corp.", "US", "energy", 80, 150.0)
                    ]
                elif "Defensive" in p_name:  # Ray Dalio / Bridgewater All-Weather tilt
                    holdings = [
                        ("PG", "Procter & Gamble", "US", "consumer_staples", 150, 145.0),
                        ("COST", "Costco Wholesale", "US", "consumer_staples", 40, 520.0),
                        ("WMT", "Walmart Inc.", "US", "consumer_staples", 180, 155.0),
                        ("JNJ", "Johnson & Johnson", "US", "healthcare", 120, 160.0),
                        ("XLU", "Utilities Select Sector", "US", "utilities", 250, 65.0)
                    ]
                elif "Aggressive Growth" in p_name:  # Cathie Wood / ARKK Innovation model
                    holdings = [
                        ("TSLA", "Tesla Inc.", "US", "automotive", 80, 220.0),
                        ("COIN", "Coinbase Global", "US", "financials", 50, 110.0),
                        ("ROKU", "Roku Inc.", "US", "technology", 120, 65.0),
                        ("ZM", "Zoom Video", "US", "technology", 150, 70.0),
                        ("SQ", "Block Inc.", "US", "financials", 100, 68.0)
                    ]
                elif "Long-Term Value" in p_name:  # Mixed G20 Value & High Dividends
                    holdings = [
                        ("8306.T", "Mitsubishi UFJ Financial", "JP", "financials", 1000, 1200.0),
                        ("7203.T", "Toyota Motor", "JP", "automotive", 500, 2500.0),
                        ("6758.T", "Sony Group", "JP", "technology", 100, 12000.0),
                        ("JPM", "JPMorgan Chase & Co.", "US", "financials", 80, 145.0),
                        ("NSRGY", "Nestle SA ADR", "US", "consumer_staples", 100, 105.0)
                    ]
                else:  # Sandbox / Neutral Mix
                    holdings = [
                        ("AAPL", "Apple Inc.", "US", "technology", 100, 175.0),
                        ("7203.T", "Toyota Motor", "JP", "automotive", 200, 2600.0)
                    ]
                
                # Bulk insert holdings
                for ticker, comp_name, country, sector, qty, cost in holdings:
                    cursor.execute("""
                        INSERT INTO holdings (portfolio_id, ticker, company_name, country, sector, quantity, average_cost, current_price, market_value, weight)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (p_id, ticker, comp_name, country, sector, qty, cost, cost, qty * cost, 0.0))
            
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error seeding database: {e}")

# --- Portfolio CRUD Helpers ---

def get_user_by_email(email: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves user by email or creates one if it doesn't exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    if row:
        user = dict(row)
    else:
        cursor.execute("INSERT INTO users (email, plan) VALUES (?, 'Free')", (email,))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
        user = dict(cursor.fetchone())
    conn.close()
    return user

def update_user_plan(user_id: int, plan: str, db_path: str = DB_PATH):
    """Updates user plan (Free / Pro)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
    conn.commit()
    conn.close()

def get_user_portfolios(user_id: int, is_virtual: Optional[int] = None, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves portfolios owned by a user."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    if is_virtual is not None:
        cursor.execute("SELECT * FROM portfolios WHERE user_id = ? AND is_virtual = ? ORDER BY name ASC", (user_id, is_virtual))
    else:
        cursor.execute("SELECT * FROM portfolios WHERE user_id = ? ORDER BY name ASC", (user_id,))
    rows = cursor.fetchall()
    portfolios = [dict(row) for row in rows]
    conn.close()
    return portfolios

def create_portfolio(user_id: int, name: str, is_virtual: int = 0, initial_balance: float = 100000.0, cash_balance: float = 0.0, base_currency: str = "$", db_path: str = DB_PATH) -> int:
    """Creates a new portfolio or paper trading account."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO portfolios (user_id, name, is_virtual, cash_balance, initial_balance, base_currency, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (user_id, name, is_virtual, cash_balance, initial_balance, base_currency))
    portfolio_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return portfolio_id

def delete_portfolio(portfolio_id: int, db_path: str = DB_PATH):
    """Deletes a portfolio and all its holdings/evaluations."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    # Delete holdings
    cursor.execute("DELETE FROM holdings WHERE portfolio_id = ?", (portfolio_id,))
    # Delete evaluations
    cursor.execute("SELECT id FROM portfolio_evaluations WHERE portfolio_id = ?", (portfolio_id,))
    eval_ids = [row["id"] for row in cursor.fetchall()]
    for eval_id in eval_ids:
        cursor.execute("DELETE FROM holding_evaluations WHERE portfolio_evaluation_id = ?", (eval_id,))
    cursor.execute("DELETE FROM portfolio_evaluations WHERE portfolio_id = ?", (portfolio_id,))
    # Delete portfolio
    cursor.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    conn.commit()
    conn.close()

def update_portfolio_cash(portfolio_id: int, cash: float, db_path: str = DB_PATH):
    """Updates cash balance of a virtual portfolio."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE portfolios SET cash_balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (cash, portfolio_id))
    conn.commit()
    conn.close()

def save_holdings(portfolio_id: int, holdings_list: List[Dict[str, Any]], db_path: str = DB_PATH):
    """Saves holdings to a portfolio, overwriting old holdings."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    # Clear existing holdings
    cursor.execute("DELETE FROM holdings WHERE portfolio_id = ?", (portfolio_id,))
    
    # Insert new ones
    for h in holdings_list:
        cursor.execute("""
            INSERT INTO holdings (portfolio_id, ticker, company_name, country, sector, quantity, average_cost, current_price, market_value, weight, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            portfolio_id, h["ticker"], h.get("name"), h.get("country"), h.get("sector"),
            h["qty"], h["cost"], h.get("price"), h.get("value"), h.get("weight")
        ))
    cursor.execute("UPDATE portfolios SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (portfolio_id,))
    conn.commit()
    conn.close()

def get_portfolio_holdings(portfolio_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all holdings for a specific portfolio."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM holdings WHERE portfolio_id = ? ORDER BY ticker ASC", (portfolio_id,))
    rows = cursor.fetchall()
    holdings = [dict(row) for row in rows]
    conn.close()
    return holdings

# --- Notification & Alerts CRUD ---

def get_notification_settings(user_id: int, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Retrieves or initializes notification settings for a user."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notification_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        settings = dict(row)
    else:
        cursor.execute("""
            INSERT INTO notification_settings (user_id, email_enabled, slack_enabled, min_severity, event_types, frequency)
            VALUES (?, 1, 0, 2, 'cpi,fomc,rate_hike,oil_spike', 'instant')
        """, (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM notification_settings WHERE user_id = ?", (user_id,))
        settings = dict(cursor.fetchone())
    conn.close()
    return settings

def save_notification_settings(
    user_id: int,
    email_enabled: int,
    slack_enabled: int,
    slack_webhook_url: str,
    min_severity: int,
    event_types: str,
    frequency: str,
    telegram_enabled: int = 0,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_username: str = "",
    smtp_password: str = "",
    smtp_from: str = "",
    db_path: str = DB_PATH
):
    """Updates user notification settings including Slack, Telegram, and SMTP."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notification_settings (
            user_id, email_enabled, slack_enabled, slack_webhook_url,
            telegram_enabled, telegram_bot_token, telegram_chat_id,
            smtp_host, smtp_port, smtp_username, smtp_password, smtp_from,
            min_severity, event_types, frequency
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            email_enabled = excluded.email_enabled,
            slack_enabled = excluded.slack_enabled,
            slack_webhook_url = excluded.slack_webhook_url,
            telegram_enabled = excluded.telegram_enabled,
            telegram_bot_token = excluded.telegram_bot_token,
            telegram_chat_id = excluded.telegram_chat_id,
            smtp_host = excluded.smtp_host,
            smtp_port = excluded.smtp_port,
            smtp_username = excluded.smtp_username,
            smtp_password = excluded.smtp_password,
            smtp_from = excluded.smtp_from,
            min_severity = excluded.min_severity,
            event_types = excluded.event_types,
            frequency = excluded.frequency
    """, (
        user_id, email_enabled, slack_enabled, slack_webhook_url,
        telegram_enabled, telegram_bot_token, telegram_chat_id,
        smtp_host, smtp_port, smtp_username, smtp_password, smtp_from,
        min_severity, event_types, frequency
    ))
    conn.commit()
    conn.close()

# --- Macro Events & Evaluations CRUD ---

def save_macro_event(event_type: str, region: str, value: float, prev_value: float, change_rate: float, severity: int, source: str = "FRED", db_path: str = DB_PATH) -> int:
    """Saves a detected macro event to database and returns its ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO macro_events (event_type, region, value, previous_value, change_rate, severity, source, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (event_type, region, value, prev_value, change_rate, severity, source))
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id

def get_macro_events_history(limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves historical macro events."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM macro_events ORDER BY detected_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    events = [dict(row) for row in rows]
    conn.close()
    return events

def save_portfolio_evaluation(portfolio_id: int, macro_event_id: Optional[int], score: float, summary: str, holdings_evals: List[Dict[str, Any]], db_path: str = DB_PATH) -> int:
    """Saves a complete portfolio evaluation run, including individual holding decisions."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO portfolio_evaluations (portfolio_id, macro_event_id, portfolio_macro_score, summary, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (portfolio_id, macro_event_id, score, summary))
    evaluation_id = cursor.lastrowid
    
    for h in holdings_evals:
        cursor.execute("""
            INSERT INTO holding_evaluations (portfolio_evaluation_id, ticker, previous_rating, new_rating, macro_score, valuation_score, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            evaluation_id, h["ticker"], h.get("previous_rating"), h["decision"], 
            h["macro_score"], h["valuation_score"], h["rationale"]
        ))
        
    conn.commit()
    conn.close()
    return evaluation_id

def get_portfolio_evaluations(portfolio_id: int, limit: int = 20, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Gets historical evaluation runs for a specific portfolio."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pe.*, me.event_type as trigger_event, me.severity as event_severity
        FROM portfolio_evaluations pe
        LEFT JOIN macro_events me ON pe.macro_event_id = me.id
        WHERE pe.portfolio_id = ?
        ORDER BY pe.created_at DESC LIMIT ?
    """, (portfolio_id, limit))
    rows = cursor.fetchall()
    evaluations = [dict(row) for row in rows]
    conn.close()
    return evaluations

def get_evaluation_details(evaluation_id: int, db_path: str = DB_PATH) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Gets details of a single evaluation run and its holding evaluations."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM portfolio_evaluations WHERE id = ?", (evaluation_id,))
    eval_row = cursor.fetchone()
    if not eval_row:
        conn.close()
        raise ValueError(f"Evaluation with ID {evaluation_id} not found.")
    
    evaluation = dict(eval_row)
    
    cursor.execute("SELECT * FROM holding_evaluations WHERE portfolio_evaluation_id = ?", (evaluation_id,))
    holding_rows = cursor.fetchall()
    holdings_evals = [dict(row) for row in holding_rows]
    
    conn.close()
    return evaluation, holdings_evals

def save_notification_log(user_id: int, portfolio_id: int, event_id: Optional[int], channel: str, status: str, db_path: str = DB_PATH):
    """Logs a sent notification."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notification_logs (user_id, portfolio_id, macro_event_id, channel, status, sent_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (user_id, portfolio_id, event_id, channel, status))
    conn.commit()
    conn.close()

def save_inquiry(name: str, email: str, subject: str, message: str, db_path: str = DB_PATH) -> int:
    """Saves an inquiry to the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO inquiries (name, email, subject, message)
        VALUES (?, ?, ?, ?)
    """, (name, email, subject, message))
    inquiry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return inquiry_id

def get_inquiries(limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves list of saved inquiries."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inquiries ORDER BY submitted_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    inquiries = [dict(row) for row in rows]
    conn.close()
    return inquiries
