"""Tests for the dead man's switch state machine."""

from datetime import datetime, timedelta, timezone

import pytest

from afterkey.watchdog import (
    WatchdogState,
    check_votes,
    evaluate,
    record_vote,
    reset,
    transition,
)


def _make_state(days_silent: int, stage: str = "active", **kwargs) -> WatchdogState:
    """Helper: create a state with last_checkin N days ago."""
    checkin = (datetime.now(timezone.utc) - timedelta(days=days_silent)).isoformat()
    return WatchdogState(stage=stage, last_checkin=checkin, **kwargs)


def _now():
    return datetime.now(timezone.utc)


# --- Stage transitions ---

def test_active_when_recent_checkin():
    ws = _make_state(days_silent=3)
    new_stage, actions = evaluate(ws)
    assert new_stage == "active"
    assert actions == []


def test_alerting_at_7_days():
    ws = _make_state(days_silent=7)
    new_stage, actions = evaluate(ws)
    assert new_stage == "alerting"
    assert "send_owner_alert" in actions


def test_alerting_at_15_days():
    ws = _make_state(days_silent=15)
    new_stage, actions = evaluate(ws)
    assert new_stage == "alerting"
    assert "send_owner_alert" in actions


def test_notifying_at_30_days():
    ws = _make_state(days_silent=30)
    new_stage, actions = evaluate(ws)
    assert new_stage == "notifying"
    assert "notify_contacts" in actions


def test_notifying_already_notified():
    ws = _make_state(days_silent=45, contacts_notified=True)
    new_stage, actions = evaluate(ws)
    assert new_stage == "notifying"
    assert "notify_contacts" not in actions


def test_voting_at_60_days():
    ws = _make_state(days_silent=60)
    new_stage, actions = evaluate(ws)
    assert new_stage == "voting"
    assert "request_votes" in actions


def test_released_at_90_days_with_votes():
    ws = _make_state(days_silent=90)
    ws.votes = {
        "alice": {"voted": True, "timestamp": ""},
        "bob": {"voted": True, "timestamp": ""},
    }
    ws.vote_threshold = 2
    new_stage, actions = evaluate(ws)
    assert new_stage == "released"
    assert "release_shares" in actions


def test_not_released_at_90_without_votes():
    ws = _make_state(days_silent=90)
    ws.votes = {}
    ws.vote_threshold = 2
    new_stage, actions = evaluate(ws)
    assert new_stage == "voting"
    assert "request_votes" in actions


def test_not_released_with_insufficient_votes():
    ws = _make_state(days_silent=95)
    ws.votes = {"alice": {"voted": True, "timestamp": ""}}
    ws.vote_threshold = 2
    new_stage, actions = evaluate(ws)
    assert new_stage == "voting"


# --- Reset from any stage ---

def test_reset_from_active():
    ws = _make_state(days_silent=0, stage="active")
    ws = reset(ws, datetime.now(timezone.utc).isoformat())
    assert ws.stage == "active"


def test_reset_from_alerting():
    ws = _make_state(days_silent=10, stage="alerting")
    ws = reset(ws, datetime.now(timezone.utc).isoformat())
    assert ws.stage == "active"
    assert ws.contacts_notified is False


def test_reset_from_notifying():
    ws = _make_state(days_silent=40, stage="notifying", contacts_notified=True)
    ws = reset(ws, datetime.now(timezone.utc).isoformat())
    assert ws.stage == "active"
    assert ws.contacts_notified is False


def test_reset_from_voting():
    ws = _make_state(days_silent=70, stage="voting")
    ws.votes = {"alice": {"voted": True, "timestamp": ""}}
    ws = reset(ws, datetime.now(timezone.utc).isoformat())
    assert ws.stage == "active"
    assert ws.votes == {}


def test_reset_clears_votes():
    ws = WatchdogState(
        stage="voting",
        last_checkin="2026-01-01T00:00:00",
        votes={"a": {"voted": True}, "b": {"voted": True}},
    )
    ws = reset(ws, datetime.now(timezone.utc).isoformat())
    assert ws.votes == {}


# --- Vote mechanics ---

def test_record_vote():
    ws = WatchdogState()
    ws = record_vote(ws, "alice")
    assert "alice" in ws.votes
    assert ws.votes["alice"]["voted"] is True


def test_check_votes_passes():
    ws = WatchdogState(vote_threshold=2)
    ws = record_vote(ws, "alice")
    ws = record_vote(ws, "bob")
    assert check_votes(ws) is True


def test_check_votes_fails():
    ws = WatchdogState(vote_threshold=2)
    ws = record_vote(ws, "alice")
    assert check_votes(ws) is False


def test_check_votes_exceeds_threshold():
    ws = WatchdogState(vote_threshold=2)
    ws = record_vote(ws, "alice")
    ws = record_vote(ws, "bob")
    ws = record_vote(ws, "charlie")
    assert check_votes(ws) is True


# --- Edge cases ---

def test_no_checkin_yet():
    ws = WatchdogState()
    new_stage, actions = evaluate(ws)
    assert new_stage == "active"
    assert actions == []


def test_exactly_on_threshold():
    """Exactly 30 days should be 'notifying', not 'alerting'."""
    ws = _make_state(days_silent=30)
    new_stage, _ = evaluate(ws)
    assert new_stage == "notifying"


def test_exactly_on_release_threshold_no_votes():
    ws = _make_state(days_silent=90)
    ws.vote_threshold = 2
    new_stage, _ = evaluate(ws)
    assert new_stage == "voting"  # blocked by votes


def test_transition_updates_stage():
    ws = WatchdogState(stage="active")
    ws = transition(ws, "alerting")
    assert ws.stage == "alerting"
