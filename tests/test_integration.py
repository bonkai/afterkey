"""Full lifecycle integration tests."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from afterkey import crypto_utils
from afterkey.checkin import perform_checkin
from afterkey.shamir import reconstruct
from afterkey.shares import (
    collect_shares_for_recovery,
    decode_share,
    encode_share,
    save_share,
    share_to_compact,
    share_to_printable,
)
from afterkey.vault import create_inventory, load, save, seal, unseal, verify_passphrase
from afterkey.watchdog import (
    WatchdogState,
    check_votes,
    evaluate,
    load_state as load_watchdog,
    record_vote,
    reset,
    save_state as save_watchdog,
)


@pytest.fixture(autouse=True)
def isolated_app_dir(tmp_path, monkeypatch):
    """Redirect all file I/O to a temp directory."""
    import afterkey.config as cfg
    import afterkey.checkin as ci
    import afterkey.vault as v
    import afterkey.shares as sh
    import afterkey.watchdog as wd
    import afterkey.notify as no

    for mod in [cfg, ci, v, sh, no]:
        monkeypatch.setattr(mod, "APP_DIR", tmp_path)

    monkeypatch.setattr(cfg, "VAULT_FILE", tmp_path / "vault.enc")
    monkeypatch.setattr(cfg, "VAULT_META", tmp_path / "vault.meta.json")
    monkeypatch.setattr(cfg, "SHARES_DIR", tmp_path / "shares")
    monkeypatch.setattr(cfg, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(cfg, "CHECKIN_LOG", tmp_path / "checkins.log")

    monkeypatch.setattr(v, "VAULT_FILE", tmp_path / "vault.enc")
    monkeypatch.setattr(v, "VAULT_META", tmp_path / "vault.meta.json")

    monkeypatch.setattr(ci, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(ci, "CHECKIN_LOG", tmp_path / "checkins.log")

    monkeypatch.setattr(sh, "SHARES_DIR", tmp_path / "shares")

    monkeypatch.setattr(wd, "STATE_FILE", tmp_path / "state.json")

    return tmp_path


class TestFullLifecycle:
    """Simulate the complete owner setup → death → heir recovery flow."""

    def test_setup_checkin_silence_recover(self, isolated_app_dir):
        """The golden path: create vault, check in, go silent, recover."""
        passphrase = "my-secure-passphrase"
        assets = [
            {"type": "crypto", "name": "Bitcoin", "seed": "abandon ability able about above absent"},
            {"type": "password", "service": "Gmail", "username": "me@gmail.com", "password": "hunter2"},
            {"type": "instruction", "recipient": "My daughter", "message": "I love you. The BTC is for your college fund."},
        ]

        # --- OWNER: Create vault ---
        inventory = create_inventory(assets)
        ciphertext, meta, shares = seal(inventory, passphrase)
        save(ciphertext, meta)

        # Encode and save shares
        share_paths = []
        recipients = ["Alice", "Bob", "Carol", "Dave", "Eve"]
        for i, share in enumerate(shares):
            encoded = encode_share(share, i + 1, "Owner", recipients[i])
            path = save_share(encoded, isolated_app_dir / "shares")
            share_paths.append(path)

        assert len(share_paths) == 5

        # --- OWNER: Initial check-in ---
        assert perform_checkin(passphrase) is True

        # --- OWNER: Weekly check-ins for a month ---
        for week in range(4):
            assert perform_checkin(passphrase) is True

        # --- TIME PASSES: Owner stops checking in ---
        # Simulate by manually setting last_checkin to 91 days ago
        state = json.loads((isolated_app_dir / "state.json").read_text())
        state["last_checkin"] = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
        (isolated_app_dir / "state.json").write_text(json.dumps(state))

        # --- WATCHDOG: Evaluate (should be past all thresholds) ---
        ws = load_watchdog()
        new_stage, actions = evaluate(ws)
        assert new_stage == "voting"  # no votes yet, so stuck at voting
        assert "request_votes" in actions

        # --- CONTACTS: Submit votes ---
        ws = record_vote(ws, "Alice")
        ws = record_vote(ws, "Bob")
        assert check_votes(ws) is True
        save_watchdog(ws)

        # Re-evaluate — should now release
        ws = load_watchdog()
        new_stage, actions = evaluate(ws)
        assert new_stage == "released"
        assert "release_shares" in actions

        # --- HEIR: Recover vault ---
        recovered_shares = collect_shares_for_recovery(share_paths[:3])
        secret_int = reconstruct(recovered_shares)
        master_key = crypto_utils.int_to_key(secret_int)

        vault_data = load()
        assert vault_data is not None
        ct, mt = vault_data
        recovered_inventory = unseal(ct, mt, master_key)

        # Verify contents match
        assert recovered_inventory["assets"] == assets

    def test_resurrection_resets_everything(self, isolated_app_dir):
        """Owner checks in during the notification stage — everything resets."""
        passphrase = "test-pass"
        inventory = create_inventory([{"type": "note", "text": "data"}])
        ciphertext, meta, shares = seal(inventory, passphrase)
        save(ciphertext, meta)
        perform_checkin(passphrase)

        # Simulate 45 days of silence (notifying stage)
        state = json.loads((isolated_app_dir / "state.json").read_text())
        state["last_checkin"] = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        (isolated_app_dir / "state.json").write_text(json.dumps(state))

        ws = load_watchdog()
        new_stage, actions = evaluate(ws)
        assert new_stage == "notifying"

        # Owner comes back!
        assert perform_checkin(passphrase) is True
        ws = load_watchdog()
        ws = reset(ws, datetime.now(timezone.utc).isoformat())
        save_watchdog(ws)

        # Should be back to active
        ws = load_watchdog()
        new_stage, actions = evaluate(ws)
        assert new_stage == "active"
        assert actions == []

    def test_partial_shares_fail(self, isolated_app_dir):
        """2 shares (below threshold of 3) cannot decrypt."""
        passphrase = "test"
        inventory = create_inventory([{"type": "note", "text": "secret"}])
        ciphertext, meta, shares = seal(inventory, passphrase)
        save(ciphertext, meta)

        # Save only 2 shares
        paths = []
        for i in range(2):
            encoded = encode_share(shares[i], i + 1, "Owner", f"Person{i}")
            paths.append(save_share(encoded, isolated_app_dir / "shares"))

        # Try to recover with 2 — wrong key, should fail
        recovered = collect_shares_for_recovery(paths)
        secret_int = reconstruct(recovered)
        wrong_key = crypto_utils.int_to_key(secret_int)

        vault_data = load()
        ct, mt = vault_data
        with pytest.raises(Exception):
            unseal(ct, mt, wrong_key)

    def test_4_of_5_shares_succeed(self, isolated_app_dir):
        """4 shares (above threshold) still reconstruct correctly."""
        passphrase = "test"
        assets = [{"type": "note", "text": "important"}]
        inventory = create_inventory(assets)
        ciphertext, meta, shares = seal(inventory, passphrase)
        save(ciphertext, meta)

        paths = []
        for i in range(4):
            encoded = encode_share(shares[i], i + 1, "Owner", f"Person{i}")
            paths.append(save_share(encoded, isolated_app_dir / "shares"))

        recovered = collect_shares_for_recovery(paths)
        secret_int = reconstruct(recovered[:3])
        master_key = crypto_utils.int_to_key(secret_int)

        vault_data = load()
        ct, mt = vault_data
        result = unseal(ct, mt, master_key)
        assert result["assets"] == assets


class TestShareFormats:
    """Test share encoding/decoding across formats."""

    def test_encode_decode_roundtrip(self):
        from afterkey.shamir import split
        shares = split(42, k=3, n=5)
        for i, share in enumerate(shares):
            encoded = encode_share(share, i + 1, "Owner", "Alice")
            decoded = decode_share(encoded)
            assert decoded == share

    def test_printable_contains_share_data(self):
        from afterkey.shamir import split
        shares = split(42, k=3, n=5)
        encoded = encode_share(shares[0], 1, "Owner", "Alice")
        text = share_to_printable(encoded)
        assert "Owner" in text
        assert "Alice" in text
        assert encoded["y"] in text

    def test_compact_format(self):
        from afterkey.shamir import split
        shares = split(42, k=3, n=5)
        encoded = encode_share(shares[0], 1, "Owner", "Alice")
        compact = share_to_compact(encoded)
        assert compact.startswith("afterkey:v1:")
        parts = compact.split(":")
        assert len(parts) == 4

    def test_save_and_load_share_file(self, isolated_app_dir):
        from afterkey.shamir import split
        shares = split(12345, k=3, n=5)
        encoded = encode_share(shares[0], 1, "Owner", "Bob")
        path = save_share(encoded, isolated_app_dir / "shares")

        from afterkey.shares import load_share
        loaded = load_share(path)
        assert loaded == shares[0]
