# Afterkey

Dead man's switch for your digital legacy. Encrypt your crypto seeds, passwords, and final instructions in a vault, split the key across trusted people using [Shamir's Secret Sharing](https://en.wikipedia.org/wiki/Shamir%27s_secret_sharing), and let a dead man's switch handle the rest.

No company to trust. No cloud servers. Everything runs locally.

## How It Works

1. **You create a vault** with your digital assets (crypto seeds, passwords, instructions for loved ones)
2. **The vault is encrypted** with a random 256-bit key, then the key is split into 5 shares — any 3 can reconstruct it
3. **You distribute the shares** to trusted people (family, friends, attorney)
4. **You check in weekly** by running `afterkey checkin`
5. **If you stop checking in**, the system progressively alerts you, then your contacts, then asks them to confirm, then makes the vault recoverable

No single person can access your vault. No single company can shut it down. Your heirs need 3 of 5 shares to unlock it, and the dead man's switch ensures they know when and how.

## Install

```bash
pip install afterkey
```

Or from source:
```bash
git clone https://github.com/yourusername/afterkey.git
cd afterkey
pip install .
```

## Quick Start

```bash
# Set up your vault (interactive wizard)
afterkey init

# Check in weekly to stay active
afterkey checkin

# Check your status anytime
afterkey status
```

## The Dead Man's Switch

When you stop checking in, the system escalates in stages:

| Days Silent | Stage | What Happens |
|-------------|-------|-------------|
| 0-6 | **Active** | All good |
| 7-29 | **Alerting** | You get emailed: "Hey, check in" |
| 30-59 | **Notifying** | Your contacts get notified: "Have you heard from them?" |
| 60-89 | **Voting** | Contacts are asked to confirm you're gone (2 of 3 must agree) |
| 90+ | **Released** | Vault becomes recoverable with 3 shares |

A check-in at **any stage** resets everything back to Active.

## Commands

```bash
afterkey init                    # Full setup wizard
afterkey checkin                 # Weekly proof-of-life
afterkey status                  # Dashboard

afterkey vault create            # Create/update vault
afterkey vault show              # View vault contents

afterkey shares show             # List share files
afterkey shares verify           # Verify shares can reconstruct the key

afterkey watchdog run            # Run the dead man's switch (put this in cron)
afterkey watchdog run --dry-run  # See what would happen without acting

afterkey vote --contact "Alice"  # Contact confirms owner is gone
afterkey recover s1.json s2.json s3.json  # Heir decrypts vault with 3 shares
afterkey recover s1.json s2.json s3.json -o vault.json  # Save to file

afterkey contacts add "Alice" alice@email.com
afterkey contacts list
afterkey contacts remove "Alice"
```

## Automating the Watchdog

Add a daily cron job to run the dead man's switch automatically:

```bash
crontab -e
```

Add this line:
```
0 9 * * * /path/to/afterkey watchdog run
```

This checks your status every morning at 9am and sends notifications if needed.

## For Heirs: Recovering the Vault

If you've received a share file and been told it's time to recover the vault:

```bash
# You need 3 share files (from 3 different people)
afterkey recover share-1-alice.json share-2-bob.json share-3-carol.json

# Or save to a file
afterkey recover share-1-alice.json share-2-bob.json share-3-carol.json -o recovered.json
```

## Security

- **AES-256-GCM** encryption for the vault
- **Shamir's Secret Sharing** over GF(2^256-189) — information-theoretically secure, meaning k-1 shares reveal zero information about the key regardless of computational power
- **Scrypt** key derivation for passphrase verification (n=2^20, r=8, p=1)
- **No network required** — everything is local files. Email notifications are optional.
- **No dependencies beyond** `click`, `rich`, and `cryptography` (maintained by the Python Cryptographic Authority)
- The Shamir implementation is ~80 lines of auditable Python with no external dependencies

## Data Storage

Everything lives in `~/.afterkey/`:

```
~/.afterkey/
├── vault.enc          # Encrypted vault blob
├── vault.meta.json    # Salt, nonce, share params (not secret)
├── shares/            # Generated share files (distribute these!)
├── state.json         # Check-in timestamps, contacts, watchdog state
└── checkins.log       # Append-only check-in log
```

## License

BSL 1.1 — source available, free for personal use.
