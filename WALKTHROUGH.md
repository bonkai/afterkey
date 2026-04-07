# Afterkey — Complete Walkthrough

## What Is This?

When you die, your digital life dies with you. Your crypto wallets, your passwords, your online accounts — all locked behind credentials that nobody else knows. Your family is left filing support tickets with companies that won't help them.

Afterkey solves this. It lets you:

1. Store your important digital secrets (crypto seed phrases, passwords, final messages) in an encrypted vault
2. Split the encryption key into 5 pieces and give them to people you trust
3. Set up a dead man's switch that notices when you stop checking in
4. Automatically guide your loved ones through recovering your vault when the time comes

**The key idea:** No single person — not even you after setup — can open the vault alone. Your heirs need to combine 3 of the 5 pieces to unlock it. No company is involved. No cloud server. Everything runs on your computer.

---

## How the Cryptography Works (Plain English)

Think of it like a safety deposit box with a special lock that requires 3 keys to open, but you made 5 copies of those keys and gave each one to a different person. Any 3 of those 5 people can walk into the bank and open the box together, but 2 people can't — even if they try every combination. That's not a weakness in their attempt; it's a mathematical guarantee.

This is called **Shamir's Secret Sharing**, invented in 1979. It's not an algorithm that might be cracked someday — it's an information-theoretic proof. Two pieces literally contain zero information about the secret.

Your vault is encrypted with a random key. That key is split into the 5 pieces. The vault sits on your computer as an unreadable blob until 3 pieces are combined.

---

## Getting Started

### Step 1: Open Terminal

Open the Terminal app on your Mac. You'll use this for all Afterkey commands.

### Step 2: Go to the Project

```bash
cd ~/Documents/afterkey
```

### Step 3: Activate the Environment

```bash
source .venv/bin/activate
```

You'll see `(.venv)` appear in your prompt. **Do steps 2 and 3 every time you open a new Terminal window.**

---

## Setting Up Your Vault

Run the setup wizard:

```bash
afterkey init
```

It will walk you through everything interactively. Here's what to expect:

### 1. Your Name and Email

```
Your name: Tre Smith
Your email: tre@example.com
```

The email is used for check-in reminders if you set up email notifications later.

### 2. Adding Your Assets

The wizard asks you to add assets one at a time. You have three types:

**Crypto wallets** — for seed phrases and private keys:
```
Asset type: crypto
  Wallet name: Bitcoin main wallet
  Seed phrase or private key: abandon ability able about above absent...
  Notes: Hardware wallet is in the desk drawer
```

**Passwords** — for important accounts:
```
Asset type: password
  Service: Gmail
  Username: tre@gmail.com
  Password: my-actual-password
  Notes: Recovery email is backup@example.com
```

**Instructions** — messages for specific people:
```
Asset type: instruction
  For whom: My daughter
  Message: The Bitcoin is for your college fund. The hardware wallet is in my desk.
```

Type `done` when you've added everything. You can always create a new vault later with `afterkey vault create`.

### 3. Choosing a Passphrase

```
Choose a passphrase: ********
Confirm passphrase: ********
```

This passphrase is used for your weekly check-ins. It proves you're alive. Pick something strong that you'll remember — you'll type it once a week.

**Important:** This passphrase does NOT encrypt the vault directly. The vault is encrypted with a random key that's split into shares. The passphrase is only for check-in verification.

### 4. Naming Your Share Recipients

The wizard generates 5 shares and asks who gets each one:

```
Share #1 — recipient name: Sarah (wife)
    Saved: ~/.afterkey/shares/share-1-sarah-wife.json
    Print share #1 for Sarah (wife)? [y/N]: y

Share #2 — recipient name: Mike (brother)
    Saved: ~/.afterkey/shares/share-2-mike-brother.json

Share #3 — recipient name: Jennifer (attorney)
    ...

Share #4 — recipient name: Dad
    ...

Share #5 — recipient name: Best friend Alex
    ...
```

For each share, you can print it out — the printout includes the share data and instructions for the recipient explaining what it is and what to do with it.

### 5. Adding Designated Contacts

These are the people who get notified if you stop checking in. They're also the ones who vote to confirm you're actually gone (not just on vacation).

```
Contact #1 name: Sarah
Contact #1 email: sarah@example.com

Contact #2 name: Mike
Contact #2 email: mike@example.com

Contact #3 name: Dad
Contact #3 email: dad@example.com
```

You need at least 2 contacts. Two of three must agree before the vault becomes recoverable.

### 6. Done!

The wizard shows a summary and does your first check-in automatically.

---

## Distributing Shares

After setup, your share files are in `~/.afterkey/shares/`. Each file is a small JSON document containing one piece of the key.

**How to distribute them:**

- **For family members:** Copy the file to a USB drive and give it to them in person. Or print the share (the wizard offers this) and give them the paper.
- **For your attorney:** Print it, put it in a sealed envelope, and add it to your client file.
- **For a safe deposit box:** Put the share file on a USB drive (or print it) and store it in the box.

**Rules of thumb:**
- Give shares to people who won't collude against you
- Spread them geographically (don't give all 5 to people in the same house)
- Make sure at least 3 recipients will be reachable when the time comes
- Tell each recipient what it is and that they should store it safely

---

## Weekly Check-In

Once a week, run:

```bash
afterkey checkin
```

It asks for your passphrase, verifies it, and records the timestamp. That's it. Takes 5 seconds.

**If you forget:** Nothing bad happens immediately. The dead man's switch has a 7-day grace period before it even starts alerting you. You have 90 days total before the vault becomes recoverable.

**To automate reminders:** Set a weekly calendar reminder or phone alarm.

---

## What Happens If You Stop Checking In

The dead man's switch has four stages. Each stage gives you (or your contacts) a chance to stop the process.

### Day 7-29: Alerting
You get emailed: "You haven't checked in. Run `afterkey checkin` if you're okay."

**If you check in:** Everything resets. Nothing happened.

### Day 30-59: Notifying
Your designated contacts get emailed: "We haven't heard from [your name] in 30+ days. Do you know if they're okay?"

**If you check in:** Everything resets. Your contacts are told it was a false alarm.

### Day 60-89: Voting
Contacts are asked to confirm: "Do you believe [your name] is deceased or permanently incapacitated?" Two of three must agree.

**If you check in:** Everything resets, votes are cleared.

### Day 90+: Released (only if 2 of 3 voted yes)
The vault becomes recoverable. Your executor can now assemble 3 shares and decrypt your assets.

**If you check in even at this stage:** Everything resets. The vault re-locks.

---

## Checking Your Status

Anytime, run:

```bash
afterkey status
```

You'll see:
- Whether your vault exists
- When you last checked in
- What stage the watchdog is in
- How many days until each stage triggers
- How many contacts and shares you have

---

## Automating the Watchdog

The dead man's switch needs to run periodically to evaluate whether to send notifications. The simplest way:

```bash
crontab -e
```

Add this line (runs every morning at 9am):
```
0 9 * * * /Users/tresmith/Documents/afterkey/.venv/bin/afterkey watchdog run
```

Or run it manually whenever you want:
```bash
afterkey watchdog run
```

Use `--dry-run` to see what would happen without actually sending anything:
```bash
afterkey watchdog run --dry-run
```

---

## Setting Up Email Notifications

Email is optional — without it, the watchdog still tracks stages and logs everything, but nobody gets emailed. To enable it, you need SMTP credentials.

If you have a Gmail account, you can use an [App Password](https://myaccount.google.com/apppasswords). Edit your state file:

```bash
nano ~/.afterkey/state.json
```

Add an `smtp` section:
```json
{
  "smtp": {
    "host": "smtp.gmail.com",
    "port": 587,
    "user": "your.email@gmail.com",
    "password": "your-app-password",
    "from": "your.email@gmail.com"
  }
}
```

---

## For Your Heirs: How to Recover the Vault

When the time comes, your heirs need three things:

1. **The vault file** — at `~/.afterkey/vault.enc` on your computer
2. **The metadata file** — at `~/.afterkey/vault.meta.json` on your computer
3. **Three share files** — from three different recipients

### Step by step:

1. Get access to the deceased's computer (or copy the `~/.afterkey/` folder to another machine with Afterkey installed)

2. Collect at least 3 share files from the designated recipients

3. Run the recovery:
```bash
afterkey recover share-1-sarah.json share-2-mike.json share-3-dad.json
```

4. The vault contents will be displayed on screen — crypto seeds, passwords, and messages

5. To save to a file instead:
```bash
afterkey recover share-1-sarah.json share-2-mike.json share-3-dad.json -o recovered.json
```

### If recovery fails:
- Make sure you have at least 3 share files (2 is not enough — this is by design)
- Make sure the share files haven't been modified or corrupted
- Make sure you're using the vault files from the same setup (if the owner re-created their vault, old shares won't work)

---

## Updating Your Vault

If you need to add or change assets:

```bash
afterkey vault create
```

**Important:** This creates a new encryption key and new shares. You'll need to distribute the new shares to your recipients and tell them to discard the old ones. The old shares become useless after this.

---

## Managing Contacts

```bash
# Add a contact
afterkey contacts add "Sarah" sarah@example.com

# See all contacts
afterkey contacts list

# Remove a contact
afterkey contacts remove "Sarah"
```

---

## Verifying Your Setup

Run this periodically to make sure everything still works:

```bash
# Check that your shares can reconstruct the key
afterkey shares verify

# See your share distribution
afterkey shares show

# Check overall status
afterkey status
```

---

## Common Questions

**What if I lose my passphrase?**
You can't check in anymore, which means the dead man's switch will eventually trigger. Your heirs can still recover the vault with 3 shares — the passphrase is for check-in only, not for decrypting the vault.

**What if a share recipient dies before me?**
That's why there are 5 shares with a threshold of 3. You can lose up to 2 shares and still recover. If a recipient dies, you can re-create the vault (`afterkey vault create`) with new shares for new people.

**What if I go on a long trip?**
Check in before you leave. You have 90 days before the vault becomes recoverable, and even then, 2 of your 3 contacts must vote to confirm. If you'll be gone more than a few weeks, tell your contacts in advance so they don't worry.

**Can someone hack this?**
The vault is AES-256-GCM encrypted — the same encryption used by governments and banks. The key splitting uses Shamir's Secret Sharing, which has a mathematical proof (not just an algorithm) that fewer than 3 shares reveal zero information. The weakest link is the people you give shares to, not the cryptography.

**What if my computer is stolen?**
The thief has the encrypted vault but no shares. The vault is useless without 3 shares. Your assets are safe.

**What if I want to change who has shares?**
Run `afterkey vault create` to generate a new vault with new shares. Distribute the new shares and tell old recipients to destroy their copies.

**Where is my data stored?**
Everything is in `~/.afterkey/` on your computer. Nothing is sent to any server (unless you set up email notifications, which only sends alert messages, never vault contents or shares).

---

## Yearly Checkup

Once a year, do this:

1. **Run `afterkey status`** — make sure everything looks right
2. **Run `afterkey shares verify`** — confirm shares are intact
3. **Contact your share recipients** — make sure they still have their shares and know what they're for
4. **Review your vault contents** — run `afterkey vault show` and update if needed
5. **Check your contacts** — make sure email addresses are current

The system is designed to work for decades with minimal maintenance. But checking in with the humans in the system is just as important as checking in with the software.
