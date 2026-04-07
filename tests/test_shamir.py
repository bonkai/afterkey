"""Tests for Shamir's Secret Sharing."""

import secrets
from itertools import combinations

import pytest

from afterkey.config import SSS_PRIME
from afterkey.shamir import reconstruct, split, verify_shares


def test_basic_split_and_reconstruct():
    """Any k shares reconstruct the original secret."""
    secret = secrets.randbelow(SSS_PRIME)
    shares = split(secret, k=3, n=5)
    assert len(shares) == 5
    for combo in combinations(shares, 3):
        assert reconstruct(list(combo)) == secret


def test_all_shares_reconstruct():
    """Using all n shares also works."""
    secret = 42
    shares = split(secret, k=3, n=5)
    assert reconstruct(shares) == secret


def test_insufficient_shares_wrong():
    """k-1 shares reconstruct to a DIFFERENT value (not the secret)."""
    secret = 12345678
    shares = split(secret, k=3, n=5)
    for combo in combinations(shares, 2):
        result = reconstruct(list(combo))
        assert result != secret


def test_threshold_one():
    """k=1 means every share IS the secret."""
    secret = 999
    shares = split(secret, k=1, n=5)
    for x, y in shares:
        assert y == secret


def test_threshold_equals_total():
    """k=n means all shares are required."""
    secret = 777
    shares = split(secret, k=5, n=5)
    assert reconstruct(shares) == secret
    # Any 4 should give a wrong answer
    for combo in combinations(shares, 4):
        assert reconstruct(list(combo)) != secret


def test_zero_secret():
    secret = 0
    shares = split(secret, k=3, n=5)
    assert reconstruct(shares[:3]) == secret


def test_max_secret():
    """Secret just below the prime."""
    secret = SSS_PRIME - 1
    shares = split(secret, k=3, n=5)
    assert reconstruct(shares[:3]) == secret


def test_large_random_secret():
    """Full 256-bit random secret (typical AES key)."""
    secret = int.from_bytes(secrets.token_bytes(32), "big") % SSS_PRIME
    shares = split(secret, k=3, n=5)
    assert verify_shares(shares, k=3)


def test_shares_are_different_each_time():
    """Same secret produces different shares (random coefficients)."""
    secret = 42
    shares1 = split(secret, k=3, n=5)
    shares2 = split(secret, k=3, n=5)
    # The y-values should differ (with overwhelming probability)
    ys1 = [y for _, y in shares1]
    ys2 = [y for _, y in shares2]
    assert ys1 != ys2


def test_verify_shares_passes():
    secret = 42
    shares = split(secret, k=3, n=5)
    assert verify_shares(shares, k=3) is True


def test_verify_shares_detects_corruption():
    secret = 42
    shares = split(secret, k=3, n=5)
    # Corrupt one share
    x, y = shares[2]
    shares[2] = (x, y + 1)
    assert verify_shares(shares, k=3) is False


def test_invalid_params():
    with pytest.raises(ValueError):
        split(42, k=6, n=5)  # k > n
    with pytest.raises(ValueError):
        split(42, k=0, n=5)  # k < 1
    with pytest.raises(ValueError):
        split(SSS_PRIME, k=3, n=5)  # secret >= prime


def test_various_k_n_combos():
    """Sweep multiple (k, n) configurations."""
    secret = 123456789
    for k, n in [(2, 3), (2, 5), (3, 7), (4, 10), (1, 1), (5, 5)]:
        shares = split(secret, k=k, n=n)
        assert verify_shares(shares, k=k)
