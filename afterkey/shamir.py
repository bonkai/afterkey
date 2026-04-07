"""
Shamir's Secret Sharing over GF(p).

Split a secret integer into n shares such that any k shares
can reconstruct the original, but k-1 shares reveal nothing.
"""

import secrets
from itertools import combinations

from .config import SSS_PRIME


def _mod_inverse(a: int, p: int) -> int:
    """Modular multiplicative inverse using Fermat's little theorem."""
    return pow(a, p - 2, p)


def _eval_poly(coeffs: list[int], x: int, p: int) -> int:
    """Evaluate polynomial at x using Horner's method in GF(p)."""
    result = 0
    for coeff in reversed(coeffs):
        result = (result * x + coeff) % p
    return result


def split(secret: int, k: int, n: int, prime: int = SSS_PRIME) -> list[tuple[int, int]]:
    """Split a secret into n shares with threshold k.

    Returns list of (x, y) tuples. x values are 1..n.
    """
    if k > n:
        raise ValueError(f"Threshold k={k} cannot exceed total shares n={n}")
    if k < 1:
        raise ValueError("Threshold must be at least 1")
    if secret >= prime:
        raise ValueError("Secret must be less than the prime")

    # Random polynomial: coeffs[0] = secret, coeffs[1..k-1] = random
    coeffs = [secret] + [secrets.randbelow(prime) for _ in range(k - 1)]

    shares = []
    for x in range(1, n + 1):
        y = _eval_poly(coeffs, x, prime)
        shares.append((x, y))

    return shares


def reconstruct(shares: list[tuple[int, int]], prime: int = SSS_PRIME) -> int:
    """Reconstruct the secret from k or more shares using Lagrange interpolation."""
    if not shares:
        raise ValueError("Need at least one share")

    k = len(shares)
    secret = 0

    for i in range(k):
        xi, yi = shares[i]
        numerator = 1
        denominator = 1

        for j in range(k):
            if i == j:
                continue
            xj, _ = shares[j]
            numerator = (numerator * (-xj)) % prime
            denominator = (denominator * (xi - xj)) % prime

        lagrange = (yi * numerator * _mod_inverse(denominator, prime)) % prime
        secret = (secret + lagrange) % prime

    return secret


def verify_shares(shares: list[tuple[int, int]], k: int, prime: int = SSS_PRIME) -> bool:
    """Verify that all k-subsets of shares reconstruct to the same secret."""
    if len(shares) < k:
        return False

    secrets_found = set()
    for combo in combinations(shares, k):
        secrets_found.add(reconstruct(list(combo), prime))

    return len(secrets_found) == 1
