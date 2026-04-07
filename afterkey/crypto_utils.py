"""Low-level cryptographic operations."""

import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .config import AAD, SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_KEY_LENGTH


def generate_master_key() -> bytes:
    """Generate a random 256-bit master key."""
    return os.urandom(32)


def generate_salt() -> bytes:
    """Generate a random salt for key derivation."""
    return os.urandom(32)


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a passphrase using Scrypt."""
    kdf = Scrypt(salt=salt, length=SCRYPT_KEY_LENGTH, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(passphrase.encode("utf-8"))


def hash_key(key: bytes) -> str:
    """SHA-256 hash of a key, for verification without storing the key."""
    return hashlib.sha256(key).hexdigest()


def encrypt(key: bytes, plaintext: bytes, aad: bytes = AAD) -> tuple[bytes, bytes]:
    """AES-256-GCM encrypt. Returns (nonce, ciphertext)."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    return nonce, ciphertext


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = AAD) -> bytes:
    """AES-256-GCM decrypt. Raises InvalidTag on failure."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, aad)


def key_to_int(key: bytes) -> int:
    """Convert a 256-bit key to an integer for Shamir splitting."""
    return int.from_bytes(key, "big")


def int_to_key(n: int) -> bytes:
    """Convert an integer back to a 256-bit key."""
    return n.to_bytes(32, "big")
