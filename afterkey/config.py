from pathlib import Path

# --- App data directory ---
APP_DIR = Path.home() / ".afterkey"
VAULT_FILE = APP_DIR / "vault.enc"
VAULT_META = APP_DIR / "vault.meta.json"
SHARES_DIR = APP_DIR / "shares"
STATE_FILE = APP_DIR / "state.json"
CHECKIN_LOG = APP_DIR / "checkins.log"

# --- Shamir parameters ---
DEFAULT_SHARES_N = 5
DEFAULT_SHARES_K = 3
# Safe prime larger than any 256-bit key
SSS_PRIME = 2**256 - 189

# --- Timing defaults (days) ---
CHECKIN_INTERVAL_DAYS = 7
SILENCE_THRESHOLDS = {
    "alerting": 7,
    "notifying": 30,
    "voting": 60,
    "released": 90,
}

# --- Scrypt parameters ---
SCRYPT_N = 2**20
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 32

# --- AES-GCM ---
AAD = b"afterkey-v1"
