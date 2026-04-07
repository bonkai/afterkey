"""Vault creation, encryption, and decryption."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import crypto_utils
from .config import APP_DIR, DEFAULT_SHARES_K, DEFAULT_SHARES_N, VAULT_FILE, VAULT_META
from .shamir import split, verify_shares


@dataclass
class VaultMeta:
    version: int
    salt: str          # hex-encoded
    nonce: str         # hex-encoded
    key_hash: str      # SHA-256 of passphrase-derived key (for check-in verification)
    shares_n: int
    shares_k: int
    created_at: str
    last_modified: str


def create_inventory(assets: list[dict]) -> dict:
    """Create a vault inventory from a list of asset dicts."""
    return {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": assets,
    }


def seal(
    inventory: dict,
    passphrase: str,
    n: int = DEFAULT_SHARES_N,
    k: int = DEFAULT_SHARES_K,
) -> tuple[bytes, VaultMeta, list[tuple[int, int]]]:
    """Encrypt the vault and split the key into shares.

    Returns (encrypted_blob, metadata, shares).
    The passphrase is used for check-in auth, NOT for vault encryption.
    The vault is encrypted with a random master key K, which is split via Shamir.
    """
    # Generate crypto material
    salt = crypto_utils.generate_salt()
    master_key = crypto_utils.generate_master_key()
    derived_key = crypto_utils.derive_key(passphrase, salt)

    # Encrypt the inventory with the master key
    plaintext = json.dumps(inventory, indent=2).encode("utf-8")
    nonce, ciphertext = crypto_utils.encrypt(master_key, plaintext)

    # Split the master key via Shamir
    secret_int = crypto_utils.key_to_int(master_key)
    shares = split(secret_int, k, n)
    assert verify_shares(shares, k), "Share verification failed — this should never happen"

    now = datetime.now(timezone.utc).isoformat()
    meta = VaultMeta(
        version=1,
        salt=salt.hex(),
        nonce=nonce.hex(),
        key_hash=crypto_utils.hash_key(derived_key),
        shares_n=n,
        shares_k=k,
        created_at=now,
        last_modified=now,
    )

    return ciphertext, meta, shares


def unseal(ciphertext: bytes, meta: VaultMeta, master_key: bytes) -> dict:
    """Decrypt the vault with the reconstructed master key."""
    nonce = bytes.fromhex(meta.nonce)
    plaintext = crypto_utils.decrypt(master_key, nonce, ciphertext)
    return json.loads(plaintext.decode("utf-8"))


def save(ciphertext: bytes, meta: VaultMeta) -> None:
    """Write vault and metadata to disk."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    VAULT_FILE.write_bytes(ciphertext)
    VAULT_META.write_text(json.dumps(asdict(meta), indent=2))


def load() -> tuple[bytes, VaultMeta] | None:
    """Read vault and metadata from disk. Returns None if not found."""
    if not VAULT_FILE.exists() or not VAULT_META.exists():
        return None
    ciphertext = VAULT_FILE.read_bytes()
    meta_dict = json.loads(VAULT_META.read_text())
    meta = VaultMeta(**meta_dict)
    return ciphertext, meta


def verify_passphrase(passphrase: str, meta: VaultMeta) -> bool:
    """Check if a passphrase matches the stored key hash."""
    salt = bytes.fromhex(meta.salt)
    derived_key = crypto_utils.derive_key(passphrase, salt)
    return crypto_utils.hash_key(derived_key) == meta.key_hash
