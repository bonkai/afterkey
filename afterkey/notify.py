"""Email notification system. Falls back to console if SMTP not configured."""

import json
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

from .config import APP_DIR, STATE_FILE


def _get_smtp_config() -> dict | None:
    """Read SMTP config from state file."""
    if not STATE_FILE.exists():
        return None
    state = json.loads(STATE_FILE.read_text())
    smtp = state.get("smtp")
    if smtp and smtp.get("host") and smtp.get("user"):
        return smtp
    return None


def send_email(to: str, subject: str, body: str, smtp_config: dict | None = None) -> bool:
    """Send an email. Returns True on success."""
    config = smtp_config or _get_smtp_config()
    if not config:
        return False

    msg = MIMEText(body)
    msg["Subject"] = f"[Afterkey] {subject}"
    msg["From"] = config.get("from", config["user"])
    msg["To"] = to

    try:
        with smtplib.SMTP(config["host"], config.get("port", 587)) as server:
            server.starttls()
            server.login(config["user"], config["password"])
            server.send_message(msg)
        return True
    except Exception:
        return False


def send_owner_alert(owner_email: str, days_silent: int) -> bool:
    """Alert the owner they haven't checked in."""
    return send_email(
        to=owner_email,
        subject=f"You haven't checked in for {days_silent} days",
        body=(
            f"Your Afterkey vault has not received a check-in for {days_silent} days.\n\n"
            f"If you are okay, please run:\n\n"
            f"    afterkey checkin\n\n"
            f"If no check-in is received within 30 days, your designated contacts\n"
            f"will be notified as part of your digital legacy plan.\n\n"
            f"— Afterkey"
        ),
    )


def send_contact_notification(
    contact_email: str,
    contact_name: str,
    owner_name: str,
    days_silent: int,
) -> bool:
    """Notify a contact that the owner has been silent."""
    return send_email(
        to=contact_email,
        subject=f"Wellness check for {owner_name}",
        body=(
            f"Dear {contact_name},\n\n"
            f"You are a designated contact in {owner_name}'s Afterkey digital legacy plan.\n\n"
            f"We have not heard from {owner_name} in {days_silent} days.\n\n"
            f"If you know they are okay (traveling, etc.), no action is needed.\n\n"
            f"If you believe {owner_name} is deceased or permanently incapacitated,\n"
            f"you will be asked to submit a confirmation vote in the coming weeks.\n\n"
            f"— Afterkey"
        ),
    )


def send_vote_request(
    contact_email: str,
    contact_name: str,
    owner_name: str,
) -> bool:
    """Request a trigger vote from a contact."""
    return send_email(
        to=contact_email,
        subject=f"Action needed: confirm status of {owner_name}",
        body=(
            f"Dear {contact_name},\n\n"
            f"{owner_name}'s Afterkey system has entered the confirmation stage.\n\n"
            f"If you believe {owner_name} is deceased or permanently incapacitated,\n"
            f"please run the following command (or ask the designated executor to):\n\n"
            f"    afterkey vote --contact \"{contact_name}\"\n\n"
            f"When enough designated contacts confirm, the digital legacy vault\n"
            f"will become recoverable by the designated executor.\n\n"
            f"If {owner_name} is alive and well, please ask them to run:\n\n"
            f"    afterkey checkin\n\n"
            f"— Afterkey"
        ),
    )


def log_notification(action: str, details: str) -> None:
    """Log a notification action to disk (always, regardless of email success)."""
    log_file = APP_DIR / "notifications.log"
    APP_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(log_file, "a") as f:
        f.write(f"{timestamp} [{action}] {details}\n")
