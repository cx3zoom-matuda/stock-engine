import asyncio
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

from .db import (
    get_connection, save_macro_event, save_portfolio_evaluation,
    get_user_portfolios, get_portfolio_holdings, get_notification_settings,
    save_notification_log, get_user_by_email
)
from .notifier import (
    send_email_alert, send_slack_alert, send_telegram_alert,
    build_portfolio_evaluation_email_html, build_slack_alert_payload,
    build_telegram_alert_text
)
from .market_data import MarketDataClient
from .evaluator import StockEvaluator
from .engine import RuleEngine
from .detector import EventDetector
from .config import COUNTRY_SERIES_MAP

logger = logging.getLogger(__name__)

async def evaluate_and_notify_portfolio(
    portfolio_id: int,
    macro_event_id: Optional[int],
    macro_event: Dict[str, Any],
    market_client: MarketDataClient,
    evaluator: StockEvaluator,
    sector_scores: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates a specific portfolio, saves findings to the DB, and dispatches notification alerts
    to the owner based on their user notification preferences.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Load Portfolio Info
    cursor.execute("""
        SELECT p.*, u.email, u.plan 
        FROM portfolios p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.id = ?
    """, (portfolio_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise ValueError(f"Portfolio ID {portfolio_id} not found.")
        
    portfolio = dict(p_row)
    user_id = portfolio["user_id"]
    user_email = portfolio["email"]
    user_plan = portfolio["plan"]
    portfolio_name = portfolio["name"]
    conn.close()
    
    # 2. Get portfolio holdings
    db_holdings = get_portfolio_holdings(portfolio_id)
    if not db_holdings:
        logger.info(f"Skipping evaluation for empty portfolio: {portfolio_name}")
        return {}
        
    # Convert DB holdings to DataFrame expected by evaluate_portfolio_macro
    portfolio_data = []
    for h in db_holdings:
        portfolio_data.append({
            "ticker": h["ticker"],
            "qty": h["quantity"],
            "cost": h["average_cost"]
        })
    portfolio_df = pd.DataFrame(portfolio_data)
    
    # 3. Evaluate Portfolio
    from .portfolio import evaluate_portfolio_macro
    results = await evaluate_portfolio_macro(
        portfolio_df=portfolio_df,
        market_data_client=market_client,
        evaluator=evaluator,
        sector_scores=sector_scores
    )
    
    summary_text = (
        f"Evaluation triggered by macro event. Weighted macro score is {results['portfolio_macro_score']:+.2f}. "
        f"Portfolio Value: {portfolio['base_currency']}{results['total_value']:,.2f}."
    )
    
    # 4. Save evaluation summary and holdings details to DB
    eval_id = save_portfolio_evaluation(
        portfolio_id=portfolio_id,
        macro_event_id=macro_event_id,
        score=results["portfolio_macro_score"],
        summary=summary_text,
        holdings_evals=results["holdings"]
    )
    logger.info(f"Saved portfolio evaluation {eval_id} for portfolio '{portfolio_name}'")
    
    # 5. Dispatch Alert Notifications (Only for Pro users with notifications enabled)
    if user_plan == "Pro":
        settings = get_notification_settings(user_id)
        severity = macro_event.get("severity", 1)
        event_code = macro_event.get("event_type", "")
        
        # Check if severity and event type match filters
        severity_match = severity >= settings.get("min_severity", 2)
        
        allowed_events = [x.strip().lower() for x in settings.get("event_types", "").split(",") if x.strip()]
        event_match = any(e in event_code.lower() for e in allowed_events)
        
        if severity_match and event_match:
            # Send Email
            if settings.get("email_enabled") == 1:
                subject = f"{macro_event.get('event_type', 'Macro Shock').upper().replace('_', ' ')} Detected: Your Portfolio Was Re-Evaluated"
                try:
                    import streamlit as st
                    user_lang = st.session_state.get("language", "en")
                except Exception:
                    user_lang = "en"
                html_body = build_portfolio_evaluation_email_html(
                    portfolio_name=portfolio_name,
                    macro_event=macro_event,
                    eval_summary=results,
                    holdings_evals=results["holdings"],
                    language=user_lang
                )
                # Build SMTP config from database settings
                smtp_config = {
                    "enabled": True,
                    "host": settings.get("smtp_host", ""),
                    "port": int(settings.get("smtp_port", 587) or 587),
                    "username": settings.get("smtp_username", ""),
                    "password": settings.get("smtp_password", ""),
                    "from_address": settings.get("smtp_from", "noreply@macro-stock-engine.com")
                }
                success = send_email_alert(
                    to_email=user_email,
                    subject=subject,
                    html_body=html_body,
                    smtp_config=smtp_config
                )
                save_notification_log(
                    user_id=user_id,
                    portfolio_id=portfolio_id,
                    event_id=macro_event_id,
                    channel="Email",
                    status="Success" if success else "Failed"
                )
                
            # Send Telegram
            if settings.get("telegram_enabled") == 1 and settings.get("telegram_bot_token") and settings.get("telegram_chat_id"):
                try:
                    import streamlit as st
                    user_lang = st.session_state.get("language", "en")
                except Exception:
                    user_lang = "en"
                text_body = build_telegram_alert_text(
                    portfolio_name=portfolio_name,
                    macro_event=macro_event,
                    eval_summary=results,
                    holdings_evals=results["holdings"],
                    language=user_lang
                )
                success = send_telegram_alert(
                    bot_token=settings["telegram_bot_token"],
                    chat_id=settings["telegram_chat_id"],
                    message_text=text_body
                )
                save_notification_log(
                    user_id=user_id,
                    portfolio_id=portfolio_id,
                    event_id=macro_event_id,
                    channel="Telegram",
                    status="Success" if success else "Failed"
                )

            # Send Slack
            if settings.get("slack_enabled") == 1 and settings.get("slack_webhook_url"):
                slack_payload = build_slack_alert_payload(
                    portfolio_name=portfolio_name,
                    macro_event=macro_event,
                    eval_summary=results,
                    holdings_evals=results["holdings"]
                )
                success = send_slack_alert(
                    webhook_url=settings["slack_webhook_url"],
                    message_payload=slack_payload
                )
                save_notification_log(
                    user_id=user_id,
                    portfolio_id=portfolio_id,
                    event_id=macro_event_id,
                    channel="Slack",
                    status="Success" if success else "Failed"
                )
                
    return results

async def trigger_macro_event(
    event_type: str,
    region: str,
    value: float,
    prev_value: float,
    change_rate: float,
    severity: int,
    source: str = "FRED"
) -> int:
    """
    Registers a new macro economic shock, evaluates all relevant portfolios in the database,
    and dispatches alerts.
    """
    # 1. Log event in database
    event_id = save_macro_event(
        event_type=event_type,
        region=region,
        value=value,
        prev_value=prev_value,
        change_rate=change_rate,
        severity=severity,
        source=source
    )
    logger.info(f"Registered macro event {event_id}: {event_type} in {region} with Severity {severity}")
    
    # Construct event metadata dict
    macro_event = {
        "id": event_id,
        "event_type": event_type,
        "region": region,
        "value": value,
        "previous_value": prev_value,
        "change_rate": change_rate,
        "severity": severity,
        "source": source
    }
    
    # 2. Setup evaluators and engines to run evaluation pipeline
    market_client = MarketDataClient()
    evaluator = StockEvaluator()
    rule_engine = RuleEngine()
    
    # Construct simulated active events list
    active_events = [
        {
            "event": event_type,
            "severity": severity,
            "description": f"{event_type.upper().replace('_', ' ')} Shock detected."
        }
    ]
    
    # Calculate industry scores
    engine_results = rule_engine.calculate_industry_scores(active_events)
    
    # Transform to sector_scores format expected by evaluator
    sector_scores = {}
    for item in engine_results["rankings"]:
        sector_scores[item["sector"]] = {
            "score": item["score"],
            "breakdown": [
                {
                    "signal": b["event"],
                    "impact": b["impact_contribution"],
                    "description": b["description"]
                }
                for b in item["breakdown"]
            ]
        }
    
    # 3. Pull all portfolios in the DB to re-evaluate (only for Pro user portfolios)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id 
        FROM portfolios p 
        JOIN users u ON p.user_id = u.id 
        WHERE u.plan = 'Pro'
    """)
    portfolio_ids = [row["id"] for row in cursor.fetchall()]
    conn.close()
    
    tasks = []
    for p_id in portfolio_ids:
        tasks.append(
            evaluate_and_notify_portfolio(
                portfolio_id=p_id,
                macro_event_id=event_id,
                macro_event=macro_event,
                market_client=market_client,
                evaluator=evaluator,
                sector_scores=sector_scores
            )
        )
        
    if tasks:
        await asyncio.gather(*tasks)
        
    return event_id

async def run_manual_recalculation(portfolio_id: int) -> Dict[str, Any]:
    """
    Executes an immediate manually triggered recalculation for a specific portfolio.
    (Saves evaluation to DB, but does not log a new macro event nor send alert notifications)
    """
    market_client = MarketDataClient()
    evaluator = StockEvaluator()
    rule_engine = RuleEngine()
    
    # Calculate base neutral sector scores
    engine_results = rule_engine.calculate_industry_scores([])
    
    # Transform to sector_scores format expected by evaluator
    sector_scores = {}
    for item in engine_results["rankings"]:
        sector_scores[item["sector"]] = {
            "score": item["score"],
            "breakdown": [
                {
                    "signal": b["event"],
                    "impact": b["impact_contribution"],
                    "description": b["description"]
                }
                for b in item["breakdown"]
            ]
        }
    
    # Dummy event metadata for tracking
    dummy_event = {
        "event_type": "manual_recalc",
        "severity": 1,
        "region": "US"
    }
    
    return await evaluate_and_notify_portfolio(
        portfolio_id=portfolio_id,
        macro_event_id=None,
        macro_event=dummy_event,
        market_client=market_client,
        evaluator=evaluator,
        sector_scores=sector_scores
    )

def trigger_test_macro_event_sync(
    event_type: str,
    region: str,
    value: float,
    prev_value: float,
    change_rate: float,
    severity: int
) -> int:
    """Synchronous wrapper to trigger a macro event from non-async Streamlit buttons."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        event_id = loop.run_until_complete(
            trigger_macro_event(
                event_type=event_type,
                region=region,
                value=value,
                prev_value=prev_value,
                change_rate=change_rate,
                severity=severity,
                source="FRED Test Trigger"
            )
        )
        return event_id
    finally:
        loop.close()

import threading
import time

_scheduler_thread = None
_scheduler_lock = threading.Lock()
_scheduler_running = False

def start_background_scheduler(interval_seconds: int = 3600):
    """Starts a background thread that periodically checks for new macro data updates."""
    global _scheduler_thread, _scheduler_running
    with _scheduler_lock:
        if _scheduler_running:
            logger.info("Background scheduler is already running.")
            return
        
        _scheduler_running = True
        
        def run_loop():
            logger.info("Background scheduler thread started.")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            while _scheduler_running:
                try:
                    logger.info("Background scheduler: Polling FRED for new macro events...")
                    # Polling logic placeholder (simulates checking macro timeline dates)
                    # In a full production loop, this queries the detector periodically.
                except Exception as poll_err:
                    logger.error(f"Error in background scheduler polling: {poll_err}")
                
                # Sleep in increments of 1 second to respond to shutdown fast
                for _ in range(interval_seconds):
                    if not _scheduler_running:
                        break
                    time.sleep(1)
            
            logger.info("Background scheduler thread stopped.")
            loop.close()

        _scheduler_thread = threading.Thread(target=run_loop, daemon=True)
        _scheduler_thread.start()
        logger.info("Background scheduler thread initialized.")

def stop_background_scheduler():
    global _scheduler_running
    with _scheduler_lock:
        _scheduler_running = False
        logger.info("Background scheduler stop request registered.")
