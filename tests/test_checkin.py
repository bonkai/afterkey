"""Tests for check-in mechanism."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from afterkey.checkin import (
    days_since_checkin,
    generate_checkin_token,
    get_last_checkin,
    perform_checkin,
)
from afterkey.config import APP_DIR, CHECKIN_LOG, STATE_FILE, VAULT_FILE, VAULT_META
from afterkey.vault import create_inventory, save, seal


@pytest.fixture(autouse=True)
def clean_app_dir(tmp_path, monkeypatch):
    """Use a temp directory for all tests."""
    import afterkey.config as cfg
    import afterkey.checkin as ci
    import afterkey.vault as v

    monkeypatch.setattr(cfg, "APP_DIR", tmp_path)
    monkeypatch.setattr(cfg, "VAULT_FILE", tmp_path / "vault.enc")
    monkeypatch.setattr(cfg, "VAULT_META", tmp_path / "vault.meta.json")
    monkeypatch.setattr(cfg, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(cfg, "CHECKIN_LOG", tmp_path / "checkins.log")

    monkeypatch.setattr(ci, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(ci, "CHECKIN_LOG", tmp_path / "checkins.log")
    monkeypatch.setattr(ci, "APP_DIR", tmp_path)

    monkeypatch.setattr(v, "APP_DIR", tmp_path)
    monkeypatch.setattr(v, "VAULT_FILE", tmp_path / "vault.enc")
    monkeypatch.setattr(v, "VAULT_META", tmp_path / "vault.meta.json")


def _setup_vault(passphrase="test123"):
    inventory = create_inventory([{"type": "note", "text": "hello"}])
    ciphertext, meta, shares = seal(inventory, passphrase=passphrase)
    save(ciphertext, meta)
    return shares


def test_checkin_success():
    _setup_vault("mypass")
    assert perform_checkin("mypass") is True


def test_checkin_wrong_passphrase():
    _setup_vault("mypass")
    assert perform_checkin("wrongpass") is False


def test_checkin_no_vault():
    assert perform_checkin("anything") is False


def test_checkin_records_timestamp():
    _setup_vault("mypass")
    perform_checkin("mypass")
    last = get_last_checkin()
    assert last is not None
    assert (datetime.now(timezone.utc) - last).total_seconds() < 5


def test_checkin_increments_count(tmp_path):
    _setup_vault("mypass")
    perform_checkin("mypass")
    perform_checkin("mypass")
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["checkin_count"] == 2


def test_checkin_appends_to_log(tmp_path):
    _setup_vault("mypass")
    perform_checkin("mypass")
    perform_checkin("mypass")
    log = (tmp_path / "checkins.log").read_text().strip().split("\n")
    assert len(log) == 2


def test_days_since_checkin_none_when_never():
    assert days_since_checkin() is None


def test_days_since_checkin_zero():
    _setup_vault("mypass")
    perform_checkin("mypass")
    d = days_since_checkin()
    assert d == 0


def test_token_is_deterministic():
    t1 = generate_checkin_token("pass", "2026-01-01T00:00:00")
    t2 = generate_checkin_token("pass", "2026-01-01T00:00:00")
    assert t1 == t2


def test_token_changes_with_time():
    t1 = generate_checkin_token("pass", "2026-01-01T00:00:00")
    t2 = generate_checkin_token("pass", "2026-01-02T00:00:00")
    assert t1 != t2
