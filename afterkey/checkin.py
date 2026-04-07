"""Proof-of-life check-in mechanism."""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import APP_DIR, CHECKIN_LOG, STATE_FILE
from .vault import load, verify_passphrase


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def perform_checkin(passphrase: str) -> bool:
    """Verify passphrase and record a check-in. Returns True on success."""
    vault_data = load()
    if vault_data is None:
        return False

    _, meta = vault_data
    if not verify_passphrase(passphrase, meta):
        return False

    now = datetime.now(timezone.utc).isoformat()
    token = generate_checkin_token(passphrase, now)

    # Update state
    state = _load_state()
    state["last_checkin"] = now
    state["checkin_count"] = state.get("checkin_count", 0) + 1
    _save_state(state)

    # Append to log
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKIN_LOG, "a") as f:
        f.write(f"{now} {token}\n")

    return True


def generate_checkin_token(passphrase: str, timestamp: str) -> str:
    """HMAC-SHA256 of timestamp with passphrase — non-repudiable check-in record."""
    return hmac.new(
        passphrase.encode("utf-8"),
        timestamp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def get_last_checkin() -> datetime | None:
    """Return the last check-in timestamp, or None."""
    state = _load_state()
    ts = state.get("last_checkin")
    if ts:
        return datetime.fromisoformat(ts)
    return None


def days_since_checkin() -> int | None:
    """Days since last check-in, or None if never checked in."""
    last = get_last_checkin()
    if last is None:
        return None
    now = datetime.now(timezone.utc)
    return (now - last).days
