"""Dead man's switch state machine with progressive disclosure."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import APP_DIR, SILENCE_THRESHOLDS, STATE_FILE


STAGES = ["active", "alerting", "notifying", "voting", "released"]


@dataclass
class WatchdogState:
    stage: str = "active"
    last_checkin: str = ""
    last_alert_sent: str = ""
    contacts_notified: bool = False
    votes: dict = field(default_factory=dict)
    vote_threshold: int = 2


def load_state() -> WatchdogState:
    """Load watchdog state from disk."""
    if not STATE_FILE.exists():
        return WatchdogState()
    data = json.loads(STATE_FILE.read_text())
    wd = data.get("watchdog", {})
    return WatchdogState(
        stage=wd.get("stage", "active"),
        last_checkin=data.get("last_checkin", ""),
        last_alert_sent=wd.get("last_alert_sent", ""),
        contacts_notified=wd.get("contacts_notified", False),
        votes=wd.get("votes", {}),
        vote_threshold=wd.get("vote_threshold", 2),
    )


def save_state(ws: WatchdogState) -> None:
    """Save watchdog state to disk (merges with existing state)."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if STATE_FILE.exists():
        existing = json.loads(STATE_FILE.read_text())

    existing["last_checkin"] = ws.last_checkin
    existing["watchdog"] = {
        "stage": ws.stage,
        "last_alert_sent": ws.last_alert_sent,
        "contacts_notified": ws.contacts_notified,
        "votes": ws.votes,
        "vote_threshold": ws.vote_threshold,
    }
    STATE_FILE.write_text(json.dumps(existing, indent=2))


def evaluate(ws: WatchdogState, now: datetime | None = None) -> tuple[str, list[str]]:
    """Evaluate the current state and return (new_stage, actions).

    Actions are strings like "send_owner_alert", "notify_contacts",
    "request_votes", "release_shares". This is a pure function.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not ws.last_checkin:
        return ws.stage, []

    last = datetime.fromisoformat(ws.last_checkin)
    silent_days = (now - last).days
    actions = []

    if silent_days < SILENCE_THRESHOLDS["alerting"]:
        new_stage = "active"
    elif silent_days < SILENCE_THRESHOLDS["notifying"]:
        new_stage = "alerting"
        actions.append("send_owner_alert")
    elif silent_days < SILENCE_THRESHOLDS["voting"]:
        new_stage = "notifying"
        if not ws.contacts_notified:
            actions.append("notify_contacts")
    elif silent_days < SILENCE_THRESHOLDS["released"]:
        new_stage = "voting"
        if not ws.contacts_notified:
            actions.append("notify_contacts")
        actions.append("request_votes")
    else:
        # Past the final threshold
        if check_votes(ws):
            new_stage = "released"
            actions.append("release_shares")
        else:
            new_stage = "voting"
            actions.append("request_votes")

    return new_stage, actions


def transition(ws: WatchdogState, new_stage: str) -> WatchdogState:
    """Update state to a new stage."""
    ws.stage = new_stage
    return ws


def reset(ws: WatchdogState, checkin_time: str) -> WatchdogState:
    """Owner checked in — reset everything to active."""
    ws.stage = "active"
    ws.last_checkin = checkin_time
    ws.last_alert_sent = ""
    ws.contacts_notified = False
    ws.votes = {}
    return ws


def record_vote(ws: WatchdogState, contact_name: str) -> WatchdogState:
    """Record a trigger vote from a designated contact."""
    ws.votes[contact_name] = {
        "voted": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return ws


def check_votes(ws: WatchdogState) -> bool:
    """Return True if enough votes have been submitted."""
    yes_votes = sum(1 for v in ws.votes.values() if v.get("voted"))
    return yes_votes >= ws.vote_threshold
