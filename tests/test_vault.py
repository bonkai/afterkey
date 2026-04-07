"""Tests for vault encryption/decryption."""

import pytest

from afterkey import crypto_utils
from afterkey.shamir import reconstruct, split
from afterkey.vault import create_inventory, seal, unseal, verify_passphrase


def test_seal_unseal_roundtrip():
    """Seal a vault, reconstruct key from shares, unseal, verify contents match."""
    assets = [
        {"type": "crypto", "name": "Bitcoin", "seed": "abandon " * 11 + "about"},
        {"type": "password", "service": "email", "username": "me", "password": "hunter2"},
    ]
    inventory = create_inventory(assets)

    ciphertext, meta, shares = seal(inventory, passphrase="test-passphrase-123")

    # Reconstruct master key from 3 of 5 shares
    secret_int = reconstruct(shares[:3])
    master_key = crypto_utils.int_to_key(secret_int)

    # Unseal
    result = unseal(ciphertext, meta, master_key)
    assert result["assets"] == assets


def test_wrong_key_fails():
    """Decryption with wrong key raises an error."""
    inventory = create_inventory([{"type": "note", "text": "secret"}])
    ciphertext, meta, shares = seal(inventory, passphrase="correct")

    wrong_key = crypto_utils.generate_master_key()
    with pytest.raises(Exception):  # InvalidTag from AES-GCM
        unseal(ciphertext, meta, wrong_key)


def test_tampered_ciphertext_fails():
    """Tampered ciphertext is detected."""
    inventory = create_inventory([{"type": "note", "text": "secret"}])
    ciphertext, meta, shares = seal(inventory, passphrase="test")

    # Flip a byte
    tampered = bytearray(ciphertext)
    tampered[10] ^= 0xFF
    tampered = bytes(tampered)

    secret_int = reconstruct(shares[:3])
    master_key = crypto_utils.int_to_key(secret_int)

    with pytest.raises(Exception):
        unseal(tampered, meta, master_key)


def test_verify_passphrase_correct():
    inventory = create_inventory([])
    _, meta, _ = seal(inventory, passphrase="my-passphrase")
    assert verify_passphrase("my-passphrase", meta) is True


def test_verify_passphrase_wrong():
    inventory = create_inventory([])
    _, meta, _ = seal(inventory, passphrase="my-passphrase")
    assert verify_passphrase("wrong-passphrase", meta) is False


def test_different_share_subsets_all_work():
    """Every combination of k=3 shares decrypts the vault."""
    from itertools import combinations

    inventory = create_inventory([{"secret": "data"}])
    ciphertext, meta, shares = seal(inventory, passphrase="test")

    for combo in combinations(shares, 3):
        secret_int = reconstruct(list(combo))
        master_key = crypto_utils.int_to_key(secret_int)
        result = unseal(ciphertext, meta, master_key)
        assert result["assets"] == [{"secret": "data"}]


def test_empty_vault():
    """Empty vault seals and unseals correctly."""
    inventory = create_inventory([])
    ciphertext, meta, shares = seal(inventory, passphrase="test")

    secret_int = reconstruct(shares[:3])
    master_key = crypto_utils.int_to_key(secret_int)
    result = unseal(ciphertext, meta, master_key)
    assert result["assets"] == []


def test_large_vault():
    """Vault with many assets."""
    assets = [
        {"type": "password", "service": f"service-{i}", "password": f"pass-{i}"}
        for i in range(100)
    ]
    inventory = create_inventory(assets)
    ciphertext, meta, shares = seal(inventory, passphrase="test")

    secret_int = reconstruct(shares[:3])
    master_key = crypto_utils.int_to_key(secret_int)
    result = unseal(ciphertext, meta, master_key)
    assert len(result["assets"]) == 100


def test_meta_fields():
    """Vault metadata has all required fields."""
    inventory = create_inventory([])
    _, meta, _ = seal(inventory, passphrase="test", n=7, k=4)

    assert meta.version == 1
    assert meta.shares_n == 7
    assert meta.shares_k == 4
    assert len(meta.salt) == 64  # 32 bytes hex
    assert len(meta.nonce) == 24  # 12 bytes hex
    assert meta.key_hash  # non-empty
    assert meta.created_at
