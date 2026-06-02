import html
import smtplib
import urllib.request
import json
import logging
import pathlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Directory to save mock email outputs for user verification
MOCK_EMAIL_DIR = "data/sent_emails"

def send_email_alert(
    to_email: str,
    subject: str,
    html_body: str,
    smtp_config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Sends an HTML email alert using SMTP. 
    If smtp_config is not provided or fails, it falls back to writing a mock email file 
    under data/sent_emails for verification.
    """
    if smtp_config and smtp_config.get("enabled"):
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_config.get("from_address", "noreply@macro-stock-engine.com")
            msg["To"] = to_email
            
            msg.attach(MIMEText(html_body, "html"))
            
            host = smtp_config.get("host", "smtp.gmail.com")
            port = smtp_config.get("port", 587)
            username = smtp_config.get("username")
            password = smtp_config.get("password")
            
            server = smtplib.SMTP(host, port)
            server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(msg["From"], to_email, msg.as_string())
            server.quit()
            logger.info(f"Email successfully sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}. Falling back to mock file logging.")
            
    # Mock fallback
    try:
        pathlib.Path(MOCK_EMAIL_DIR).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{MOCK_EMAIL_DIR}/email_{timestamp}_{to_email.replace('@', '_')}.html"
        
        # Add metadata banner at the top of the mock HTML file for developer visibility
        banner = f"""
        <div style="background-color: #fef08a; border: 1px solid #eab308; padding: 15px; color: #854d0e; font-family: sans-serif; font-size: 14px; margin-bottom: 20px; border-radius: 6px;">
            <strong>ℹ️ [Developer Notice] Mock Email Alert Logged</strong><br/>
            This is a mock representation of the email sent to: <strong>{to_email}</strong><br/>
            Subject: <strong>{subject}</strong><br/>
            Time logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        """
        full_content = banner + html_body
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(full_content)
        
        logger.info(f"[MOCK EMAIL] Saved email alert to {filename}")
        return True
    except Exception as mock_err:
        logger.error(f"Failed to write mock email file: {mock_err}")
        return False

def send_slack_alert(webhook_url: str, message_payload: Dict[str, Any]) -> bool:
    """
    Sends an alert notification to a Slack channel via Incoming Webhook.
    """
    try:
        data = json.dumps(message_payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            if status == 200:
                logger.info("Slack alert successfully dispatched.")
                return True
            else:
                logger.error(f"Slack webhook returned non-200 status: {status}")
                return False
    except Exception as e:
        logger.error(f"Error sending Slack alert: {e}")
        return False

def send_telegram_alert(bot_token: str, chat_id: str, message_text: str) -> bool:
    """
    Sends an alert notification to a Telegram chat/channel via Bot API.
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            if status == 200:
                logger.info("Telegram alert successfully dispatched.")
                return True
            else:
                logger.error(f"Telegram API returned non-200 status: {status}")
                return False
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")
        return False

def build_telegram_alert_text(
    portfolio_name: str,
    macro_event: Dict[str, Any],
    eval_summary: Dict[str, Any],
    holdings_evals: List[Dict[str, Any]],
    language: str = "en"
) -> str:
    """
    Builds a clean, styled HTML text block for Telegram messages.
    """
    ev_type = macro_event.get("event_type", "Macro Shift").upper().replace("_", " ")
    severity = macro_event.get("severity", 1)
    severity_stars = "🚨" * severity
    region = macro_event.get("region", "Global")
    score = eval_summary.get("portfolio_macro_score", 0.0)
    
    is_jp = (language == "jp")
    if is_jp:
        status_lbl = "追い風 🟢" if score >= 10.0 else "逆風 🔴" if score <= -10.0 else "中立 🟡"
        header = f"<b>{severity_stars} 【マクロショック検知: {ev_type}】</b>\n"
        body = (
            f"地域: <b>{region}</b> | 深刻度: <b>{severity}</b>\n\n"
            f"ポートフォリオ「<b>{portfolio_name}</b>」への影響を自動評価しました。\n"
            f"総合マクロスコア: <b>{score:+.2f} ({status_lbl})</b>\n\n"
            f"<b>📊 主な銘柄判定の変動:</b>\n"
        )
    else:
        status_lbl = "Tailwind 🟢" if score >= 10.0 else "Headwind 🔴" if score <= -10.0 else "Neutral 🟡"
        header = f"<b>{severity_stars} [MACRO SHOCK DETECTED: {ev_type}]</b>\n"
        body = (
            f"Region: <b>{region}</b> | Severity: <b>{severity}</b>\n\n"
            f"Portfolio \"<b>{portfolio_name}</b>\" has been automatically re-evaluated.\n"
            f"Weighted Macro Score: <b>{score:+.2f} ({status_lbl})</b>\n\n"
            f"<b>📊 Key Holdings Impact:</b>\n"
        )
        
    for h in holdings_evals[:8]:  # Limit to top 8 to avoid hitting Telegram text length limits
        ticker = h.get("ticker", "")
        rating = h.get("new_rating", h.get("decision", "WATCH"))
        badge = "🟢 BUY" if rating == "BUY" else "🔴 AVOID" if rating == "AVOID" else "🟡 WATCH"
        body += f" • {ticker} → <b>{badge}</b>\n"
        
    if is_jp:
        body += "\n<b>👉 推奨アクション:</b>\n"
        if score >= 10.0:
            body += " - マクロの追い風に乗るため、買い推奨（BUY）セクターの配分を維持・拡大してください。\n"
        elif score <= -10.0:
            body += " - 逆風セクター（AVOID）のポジションを縮小し、ディフェンシブ資産へのリバランスを検討してください。\n"
        else:
            body += " - ポートフォリオは中立です。マクロ指標の次の変動を注視してください。\n"
    else:
        body += "\n<b>👉 Suggested Actions:</b>\n"
        if score >= 10.0:
            body += " - Capitalize on tailwinds. Maintain or expand BUY sector exposures.\n"
        elif score <= -10.0:
            body += " - Reduce exposure to rate-sensitive/AVOID assets and shift into defensive sectors.\n"
        else:
            body += " - Portfolio is neutral. Monitor subsequent indicators.\n"
            
    return header + body

def build_portfolio_evaluation_email_html(
    portfolio_name: str,
    macro_event: Dict[str, Any],
    eval_summary: Dict[str, Any],
    holdings_evals: List[Dict[str, Any]],
    user_email: str = "user@example.com",
    app_url: str = "https://macro.ezora.net",
    language: str = "en"
) -> str:
    """
    Builds a beautifully styled HTML body for a macro event portfolio evaluation alert.
    """
    ev_type = macro_event.get("event_type", "Macro Shift").upper().replace("_", " ")
    severity = macro_event.get("severity", 1)
    severity_stars = "🚨" * severity
    region = macro_event.get("region", "Global")
    
    score = eval_summary.get("portfolio_macro_score", 0.0)
    score_color = "#10b981" if score >= 10.0 else "#ef4444" if score <= -10.0 else "#f59e0b"
    
    safe_email = html.escape(user_email)
    is_jp = (language == "jp")
    if is_jp:
        score_status = "追い風 🟢" if score >= 10.0 else "逆風 🔴" if score <= -10.0 else "中立 🟡"
        description_html = f"""
        マクロ経済の突発的な指標変更（<strong>{ev_type}</strong>）が検出されました。<br/>
        ご登録のポートフォリオ「<strong>{portfolio_name}</strong>」への影響を自動再評価いたしました。
        """
        btn_lbl = "Open Dashboard (ダッシュボードを開く)"
        user_lbl = f"ログインユーザー名: {safe_email} (Proプラン)"
        footer_html = """
        本メールはマクロ経済評価エンジンによって自動送信されました。<br/>
        配信設定の変更は、ダッシュボードの「Alert Settings」画面から行うことができます。<br/>
        """
    else:
        score_status = "Tailwind 🟢" if score >= 10.0 else "Headwind 🔴" if score <= -10.0 else "Neutral 🟡"
        description_html = f"""
        A sudden macroeconomic shift (<strong>{ev_type}</strong>) has been detected.<br/>
        We have automatically re-evaluated the impact on your registered portfolio "<strong>{portfolio_name}</strong>".
        """
        btn_lbl = "Open Dashboard"
        user_lbl = f"Logged in as: {safe_email} (Pro Plan)"
        footer_html = """
        This email was automatically sent by the Macro Evaluation Engine.<br/>
        You can change your delivery settings in the Alert Settings screen of your dashboard.<br/>
        """
        
    # Generate Holdings rows
    rows_html = ""
    for h in holdings_evals:
        rating = h.get("new_rating", h.get("decision", "WATCH"))
        badge_bg = "#dcfce7" if rating == "BUY" else "#fee2e2" if rating == "AVOID" else "#fef9c3"
        badge_fg = "#15803d" if rating == "BUY" else "#b91c1c" if rating == "AVOID" else "#a16207"
        
        ret_val = h.get("gain_loss", 0.0)
        ret_pct = h.get("gain_loss_percent", 0.0)
        ret_color = "#10b981" if ret_val >= 0 else "#ef4444"
        ret_sign = "+" if ret_val >= 0 else ""
        
        rows_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">
                <span style="display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; background-color: {badge_bg}; color: {badge_fg};">{rating}</span>
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-weight: bold;">{h['ticker']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{h.get('company_name', h.get('name', 'N/A'))}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right; color: {ret_color};">
                {ret_sign}{ret_pct:.2f}%
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold;">{h.get('macro_score', 0.0):+.1f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 12px; color: #64748b;">{h.get('rationale', '')}</td>
        </tr>
        """
        
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; padding: 20px; color: #334155; line-height: 1.6;">
    <div style="max-width: 650px; margin: 0 auto; background: white; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); overflow: hidden;">
        
        <!-- Header Banner -->
        <div style="background-color: #0f172a; padding: 30px; text-align: center; color: white; border-bottom: 3px solid #0284c7;">
            <h2 style="margin: 0; font-size: 20px; font-weight: 500; letter-spacing: 0.05em; color: #94a3b8;">MACRO SHOCK DETECTED</h2>
            <h1 style="margin: 10px 0 0 0; font-size: 24px; font-weight: 700; color: white;">{ev_type}</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px; color: #38bdf8;">
                {severity_stars} Severity {severity} | Region: {region} | Detected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
        
        <!-- Summary Block -->
        <div style="padding: 30px; border-bottom: 1px solid #e2e8f0;">
            <p style="margin-top: 0; font-size: 16px;">
                {description_html}
            </p>
            
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; display: flex; justify-content: space-between; align-items: center; margin: 25px 0;">
                <div>
                    <div style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase; margin-bottom: 2px;">Portfolio Macro Score</div>
                    <div style="font-size: 24px; font-weight: bold; color: {score_color};">{score:+.2f}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase; margin-bottom: 2px;">Overall Impact</div>
                    <div style="font-size: 16px; font-weight: bold; color: {score_color};">{score_status}</div>
                </div>
            </div>
        </div>
        
        <!-- Holdings Impact Table -->
        <div style="padding: 30px 30px 20px 30px; border-bottom: 1px solid #e2e8f0;">
            <h3 style="margin-top: 0; font-size: 16px; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px;">Holdings Impact Detail</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background-color: #f1f5f9; text-align: left;">
                        <th style="padding: 8px; font-weight: bold; color: #475569;">Rating</th>
                        <th style="padding: 8px; font-weight: bold; color: #475569;">Ticker</th>
                        <th style="padding: 8px; font-weight: bold; color: #475569;">Name</th>
                        <th style="padding: 8px; font-weight: bold; color: #475569; text-align: right;">Return</th>
                        <th style="padding: 8px; font-weight: bold; color: #475569; text-align: right;">Macro</th>
                        <th style="padding: 8px; font-weight: bold; color: #475569;">Rationale</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        
        <!-- Action Button -->
        <div style="padding: 30px; text-align: center;">
            <a href="{app_url}" style="background-color: #0284c7; color: white; text-decoration: none; padding: 12px 25px; border-radius: 6px; font-size: 15px; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px -1px rgba(2, 132, 199, 0.2);">
                {btn_lbl}
            </a>
            <p style="font-size: 11px; color: #94a3b8; margin-top: 15px;">
                {user_lbl}
            </p>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f8fafc; padding: 20px; text-align: center; color: #94a3b8; font-size: 11px; border-top: 1px solid #e2e8f0;">
            {footer_html}
            © 2026 Macro Stock Engine, Inc. All rights reserved.
        </div>
    </div>
</body>
</html>
"""
    return html

def build_slack_alert_payload(
    portfolio_name: str,
    macro_event: Dict[str, Any],
    eval_summary: Dict[str, Any],
    holdings_evals: List[Dict[str, Any]],
    app_url: str = "https://macro.ezora.net"
) -> Dict[str, Any]:
    """
    Builds a structured Slack payload for webhook dispatch.
    """
    ev_type = macro_event.get("event_type", "Macro Shift").upper().replace("_", " ")
    severity = macro_event.get("severity", 1)
    severity_indicators = "🚨" * severity
    region = macro_event.get("region", "Global")
    score = eval_summary.get("portfolio_macro_score", 0.0)
    
    # Categorize holdings
    negatives = []
    positives = []
    for h in holdings_evals:
        rating = h.get("new_rating", h.get("decision", "WATCH"))
        ticker = h["ticker"]
        name = h.get("company_name", h.get("name", "N/A"))
        mac = h.get("macro_score", 0.0)
        
        rep = f"• *{ticker}* ({name}): Rating: `{rating}`, Macro Score: `{mac:+.1f}`"
        if mac <= -10.0 or rating == "AVOID":
            negatives.append(rep)
        elif mac >= 10.0 or rating == "BUY":
            positives.append(rep)
            
    neg_str = "\n".join(negatives) if negatives else "None"
    pos_str = "\n".join(positives) if positives else "None"
    
    payload = {
        "text": f"{severity_indicators} *{ev_type} Detected* (Severity {severity})",
        "attachments": [
            {
                "color": "#ef4444" if score <= -10.0 else "#10b981" if score >= 10.0 else "#f59e0b",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{severity_indicators} {ev_type} Shock Detected - Severity {severity}*\n"
                                    f"Region: `{region}`\n\n"
                                    f"Portfolio: *{portfolio_name}*\n"
                                    f"Macro Score: *{score:+.2f}*"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🔴 Negative Impact / AVOID:*\n{neg_str}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🟢 Positive Impact / BUY:*\n{pos_str}"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"📍 *Open dashboard:*\n<{app_url}|macro.ezora.net>"
                        }
                    }
                ]
            }
        ]
    }
    
    return payload
