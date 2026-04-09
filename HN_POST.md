# HN Post Draft

## Title (pick one):

**Option A:** Show HN: Afterkey – Dead man's switch for crypto inheritance using Shamir's Secret Sharing

**Option B:** Show HN: I built a self-hosted dead man's switch so my family can access my crypto when I die

**Option C:** Show HN: Afterkey – Split your encryption key across trusted people, let a dead man's switch handle the rest

---

## Body:

Hey HN,

A friend of mine passed away last year with ~$40K in Bitcoin on a hardware wallet. His family had no idea the seed phrase existed. It's gone forever.

This bothered me enough to build something. Afterkey is a CLI tool that:

1. Encrypts your digital assets (crypto seeds, passwords, final messages to family) in a vault using AES-256-GCM
2. Splits the encryption key into N shares using Shamir's Secret Sharing — you pick how many shares and the threshold (e.g. any 3 of 5)
3. You distribute the shares to trusted people (family, attorney, safe deposit box)
4. A dead man's switch monitors your weekly check-ins and escalates through 4 stages if you stop: alert you → notify contacts → contacts vote to confirm → shares released

No single person can open the vault alone. No company involved. No cloud. Everything is local files.

**Technical decisions I'd love feedback on:**

- Rolled my own Shamir SSS (~80 lines over GF(2^256-189)) rather than using a library. The existing PyPI packages are unmaintained or have dependency issues. The implementation is trivially auditable, which matters for a security tool. Was this the right call?

- The passphrase ≠ the vault key. Your passphrase is only for check-in authentication (Scrypt-derived, compared by hash). The vault is encrypted with a random 256-bit master key that gets Shamir-split. This means changing your passphrase doesn't require new shares. Tradeoff: if you forget your passphrase, the dead man's switch eventually triggers (which may actually be the right behavior).

- Progressive disclosure instead of a binary switch. 4 stages over 90 days with human-in-the-loop confirmation (2 of 3 contacts must vote). This dramatically reduces false positives but means actual recovery takes ~3 months.

- No daemon. The watchdog is a cron job that runs `afterkey watchdog run` daily. Simpler, more transparent, nothing to crash.

The whole thing is ~925 lines of Python, 62 tests, pip installable.

Install: `pip install afterkey`

GitHub: https://github.com/bonkai/afterkey

I'm a solo developer and this is v0.1. I know it's rough around the edges — no web UI, no mobile check-in, share distribution is manual. I'd rather ship and get feedback than polish in isolation.

What am I missing? What would make you actually trust this with your keys?
