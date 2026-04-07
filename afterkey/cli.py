"""Afterkey CLI — dead man's switch for your digital legacy."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import __version__
from .config import APP_DIR, SHARES_DIR, SILENCE_THRESHOLDS, STATE_FILE
from .crypto_utils import int_to_key, key_to_int
from .shamir import reconstruct, verify_shares
from .shares import (
    collect_shares_for_recovery,
    encode_share,
    save_share,
    share_to_printable,
)
from .vault import (
    create_inventory,
    load,
    save,
    seal,
    unseal,
    verify_passphrase,
)
from .watchdog import (
    WatchdogState,
    check_votes,
    evaluate,
    load_state as load_watchdog,
    record_vote,
    reset,
    save_state as save_watchdog,
    transition,
)
from .checkin import days_since_checkin, get_last_checkin, perform_checkin
from .notify import (
    log_notification,
    send_contact_notification,
    send_owner_alert,
    send_vote_request,
)

console = Console()


def _load_full_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_full_state(state: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ──────────────────────────────────────────────
# Root group
# ──────────────────────────────────────────────
@click.group()
@click.version_option(__version__, prog_name="afterkey")
def cli():
    """Afterkey — dead man's switch for your digital legacy."""
    pass


# ──────────────────────────────────────────────
# INIT — full setup wizard
# ──────────────────────────────────────────────
@cli.command()
def init():
    """Set up your Afterkey vault for the first time."""
    console.print(Panel.fit(
        "[bold]Welcome to Afterkey[/bold]\n\n"
        "This wizard will help you:\n"
        "1. Create an encrypted vault for your digital assets\n"
        "2. Split the key into shares for your trusted people\n"
        "3. Set up a dead man's switch for automatic notification",
        title="[bold cyan]Afterkey Setup[/bold cyan]",
        border_style="cyan",
    ))
    console.print()

    # Owner info
    owner_name = Prompt.ask("[bold]Your name[/bold]")
    owner_email = Prompt.ask("[bold]Your email[/bold]")

    # Collect assets
    console.print("\n[bold]Add your digital assets[/bold]")
    console.print("[dim]You can add crypto wallets, passwords, and instructions.[/dim]\n")

    assets = []
    while True:
        asset_type = Prompt.ask(
            "Asset type",
            choices=["crypto", "password", "instruction", "done"],
            default="done",
        )
        if asset_type == "done":
            break

        if asset_type == "crypto":
            name = Prompt.ask("  Wallet name (e.g. 'Bitcoin main')")
            seed = Prompt.ask("  Seed phrase or private key")
            notes = Prompt.ask("  Notes (optional)", default="")
            assets.append({"type": "crypto", "name": name, "seed": seed, "notes": notes})

        elif asset_type == "password":
            service = Prompt.ask("  Service (e.g. 'Gmail')")
            username = Prompt.ask("  Username")
            password = Prompt.ask("  Password")
            notes = Prompt.ask("  Notes (optional)", default="")
            assets.append({"type": "password", "service": service, "username": username, "password": password, "notes": notes})

        elif asset_type == "instruction":
            recipient = Prompt.ask("  For whom")
            message = Prompt.ask("  Message/instruction")
            assets.append({"type": "instruction", "recipient": recipient, "message": message})

        console.print(f"  [green]Added {asset_type}[/green]")

    if not assets:
        console.print("[yellow]No assets added. You can add them later with 'afterkey vault create'[/yellow]")
        assets = [{"type": "note", "text": "(empty vault — add assets later)"}]

    # Passphrase
    console.print()
    passphrase = Prompt.ask("[bold]Choose a passphrase[/bold] (used for check-ins)", password=True)
    confirm = Prompt.ask("Confirm passphrase", password=True)
    if passphrase != confirm:
        console.print("[red]Passphrases don't match. Run 'afterkey init' again.[/red]")
        return

    # Seal the vault
    console.print("\n[dim]Encrypting vault and generating shares...[/dim]")
    inventory = create_inventory(assets)
    ciphertext, meta, shares = seal(inventory, passphrase)
    save(ciphertext, meta)
    console.print("[green]Vault encrypted and saved.[/green]")

    # Encode and save shares
    console.print(f"\n[bold]Your key has been split into {meta.shares_n} shares.[/bold]")
    console.print(f"Any {meta.shares_k} of them can unlock the vault.\n")

    recipients = []
    for i, share in enumerate(shares):
        recipient = Prompt.ask(f"  Share #{i+1} — recipient name")
        recipients.append(recipient)
        encoded = encode_share(share, i + 1, owner_name, recipient)
        path = save_share(encoded)
        console.print(f"    [green]Saved: {path}[/green]")

        if Confirm.ask(f"    Print share #{i+1} for {recipient}?", default=False):
            console.print()
            console.print(share_to_printable(encoded))
            console.print()

    # Add contacts
    console.print("\n[bold]Designated contacts[/bold]")
    console.print("[dim]These people will be notified if you stop checking in.[/dim]\n")

    contacts = []
    for i in range(3):
        name = Prompt.ask(f"  Contact #{i+1} name (or 'skip')")
        if name.lower() == "skip":
            break
        email = Prompt.ask(f"  Contact #{i+1} email")
        contacts.append({"name": name, "email": email})
        console.print(f"  [green]Added: {name}[/green]")

    # Save state
    state = _load_full_state()
    state["owner"] = {"name": owner_name, "email": owner_email}
    state["contacts"] = contacts
    state["last_checkin"] = datetime.now(timezone.utc).isoformat()
    state["checkin_count"] = 1
    state["watchdog"] = {
        "stage": "active",
        "last_alert_sent": "",
        "contacts_notified": False,
        "votes": {},
        "vote_threshold": 2,
    }
    _save_full_state(state)

    # Do the first check-in
    perform_checkin(passphrase)

    # Summary
    console.print()
    console.print(Panel.fit(
        f"[bold green]Setup complete![/bold green]\n\n"
        f"Vault: {len(assets)} asset(s) encrypted\n"
        f"Shares: {meta.shares_n} generated ({meta.shares_k} needed to unlock)\n"
        f"Contacts: {len(contacts)} designated\n\n"
        f"[bold]What to do now:[/bold]\n"
        f"1. Distribute the share files to your recipients\n"
        f"2. Run [bold]afterkey checkin[/bold] weekly to stay active\n"
        f"3. Run [bold]afterkey status[/bold] anytime to check your setup\n\n"
        f"Share files are in: {SHARES_DIR}",
        title="[bold cyan]Afterkey[/bold cyan]",
        border_style="green",
    ))


# ──────────────────────────────────────────────
# VAULT commands
# ──────────────────────────────────────────────
@cli.group()
def vault():
    """Manage the encrypted vault."""
    pass


@vault.command(name="create")
@click.option("--from-file", type=click.Path(exists=True), help="Import assets from a JSON file")
def vault_create(from_file):
    """Create or replace the vault with new assets."""
    if from_file:
        data = json.loads(Path(from_file).read_text())
        assets = data if isinstance(data, list) else data.get("assets", [data])
    else:
        console.print("[bold]Add assets interactively[/bold] (type 'done' when finished)\n")
        assets = []
        while True:
            asset_type = Prompt.ask("Asset type", choices=["crypto", "password", "instruction", "done"], default="done")
            if asset_type == "done":
                break
            if asset_type == "crypto":
                assets.append({"type": "crypto", "name": Prompt.ask("  Name"), "seed": Prompt.ask("  Seed/key"), "notes": Prompt.ask("  Notes", default="")})
            elif asset_type == "password":
                assets.append({"type": "password", "service": Prompt.ask("  Service"), "username": Prompt.ask("  Username"), "password": Prompt.ask("  Password"), "notes": Prompt.ask("  Notes", default="")})
            elif asset_type == "instruction":
                assets.append({"type": "instruction", "recipient": Prompt.ask("  For whom"), "message": Prompt.ask("  Message")})

    passphrase = Prompt.ask("Passphrase", password=True)
    inventory = create_inventory(assets)
    ciphertext, meta, shares = seal(inventory, passphrase)
    save(ciphertext, meta)

    state = _load_full_state()
    owner_name = state.get("owner", {}).get("name", "owner")
    for i, share in enumerate(shares):
        encoded = encode_share(share, i + 1, owner_name, f"recipient-{i+1}")
        save_share(encoded)

    console.print(f"[green]Vault sealed with {len(assets)} asset(s). {len(shares)} shares saved to {SHARES_DIR}[/green]")


@vault.command(name="show")
def vault_show():
    """Decrypt and display vault contents."""
    vault_data = load()
    if not vault_data:
        console.print("[red]No vault found. Run 'afterkey init' first.[/red]")
        return

    ciphertext, meta = vault_data
    passphrase = Prompt.ask("Passphrase", password=True)
    if not verify_passphrase(passphrase, meta):
        console.print("[red]Wrong passphrase.[/red]")
        return

    # Need to reconstruct from shares to actually decrypt
    share_files = sorted(SHARES_DIR.glob("share-*.json")) if SHARES_DIR.exists() else []
    if not share_files:
        console.print("[red]No share files found. Cannot decrypt without shares.[/red]")
        return

    shares = collect_shares_for_recovery(share_files[:meta.shares_k])
    master_key = int_to_key(reconstruct(shares))
    inventory = unseal(ciphertext, meta, master_key)

    table = Table(title="Vault Contents", border_style="cyan")
    table.add_column("Type", style="bold")
    table.add_column("Name/Service")
    table.add_column("Details")

    for asset in inventory.get("assets", []):
        atype = asset.get("type", "?")
        if atype == "crypto":
            table.add_row("Crypto", asset.get("name", ""), f"[dim]{asset.get('seed', '')[:20]}...[/dim]")
        elif atype == "password":
            table.add_row("Password", asset.get("service", ""), f"{asset.get('username', '')}")
        elif atype == "instruction":
            table.add_row("Instruction", f"For: {asset.get('recipient', '')}", asset.get("message", "")[:50])
        else:
            table.add_row(atype, "", str(asset)[:50])

    console.print(table)


# ──────────────────────────────────────────────
# SHARES commands
# ──────────────────────────────────────────────
@cli.group()
def shares():
    """Manage key shares."""
    pass


@shares.command(name="show")
def shares_show():
    """List generated share files."""
    if not SHARES_DIR.exists():
        console.print("[yellow]No shares generated yet.[/yellow]")
        return

    files = sorted(SHARES_DIR.glob("share-*.json"))
    if not files:
        console.print("[yellow]No share files found.[/yellow]")
        return

    table = Table(title="Share Files", border_style="cyan")
    table.add_column("#", justify="right")
    table.add_column("Recipient")
    table.add_column("Created")
    table.add_column("File")

    for f in files:
        data = json.loads(f.read_text())
        table.add_row(
            str(data.get("share_index", "?")),
            data.get("recipient", "?"),
            data.get("created_at", "?")[:10],
            f.name,
        )

    console.print(table)


@shares.command(name="verify")
def shares_verify():
    """Verify that share files can reconstruct the vault key."""
    vault_data = load()
    if not vault_data:
        console.print("[red]No vault found.[/red]")
        return

    _, meta = vault_data
    files = sorted(SHARES_DIR.glob("share-*.json")) if SHARES_DIR.exists() else []
    if len(files) < meta.shares_k:
        console.print(f"[red]Need at least {meta.shares_k} shares, found {len(files)}[/red]")
        return

    all_shares = collect_shares_for_recovery(files)
    if verify_shares(all_shares, meta.shares_k):
        console.print(f"[green]All {len(files)} shares verified. Any {meta.shares_k} can reconstruct the key.[/green]")
    else:
        console.print("[red]Share verification FAILED. Shares may be corrupted.[/red]")


# ──────────────────────────────────────────────
# CHECKIN
# ──────────────────────────────────────────────
@cli.command()
def checkin():
    """Check in to confirm you're alive and well."""
    vault_data = load()
    if not vault_data:
        console.print("[red]No vault found. Run 'afterkey init' first.[/red]")
        return

    passphrase = Prompt.ask("Passphrase", password=True)
    if perform_checkin(passphrase):
        # Reset watchdog
        ws = load_watchdog()
        ws = reset(ws, datetime.now(timezone.utc).isoformat())
        save_watchdog(ws)
        console.print("[green]Check-in recorded. Dead man's switch reset.[/green]")
    else:
        console.print("[red]Check-in failed. Wrong passphrase?[/red]")


# ──────────────────────────────────────────────
# STATUS
# ──────────────────────────────────────────────
@cli.command()
def status():
    """Show current Afterkey status."""
    vault_data = load()
    state = _load_full_state()
    ws = load_watchdog()

    table = Table(title="Afterkey Status", border_style="cyan")
    table.add_column("", style="bold")
    table.add_column("")

    # Vault
    if vault_data:
        _, meta = vault_data
        table.add_row("Vault", f"[green]Sealed[/green] ({meta.shares_n} shares, {meta.shares_k} threshold)")
    else:
        table.add_row("Vault", "[red]Not created[/red]")

    # Owner
    owner = state.get("owner", {})
    if owner:
        table.add_row("Owner", f"{owner.get('name', '?')} ({owner.get('email', '?')})")

    # Check-in
    last = get_last_checkin()
    days = days_since_checkin()
    if last:
        table.add_row("Last check-in", f"{last.strftime('%Y-%m-%d %H:%M UTC')} ({days} days ago)")
    else:
        table.add_row("Last check-in", "[yellow]Never[/yellow]")

    table.add_row("Check-in count", str(state.get("checkin_count", 0)))

    # Watchdog stage
    stage = ws.stage
    stage_colors = {
        "active": "green",
        "alerting": "yellow",
        "notifying": "yellow",
        "voting": "red",
        "released": "bold red",
    }
    color = stage_colors.get(stage, "white")
    table.add_row("Watchdog stage", f"[{color}]{stage.upper()}[/{color}]")

    # Contacts
    contacts = state.get("contacts", [])
    table.add_row("Contacts", str(len(contacts)))

    # Votes
    if ws.votes:
        yes = sum(1 for v in ws.votes.values() if v.get("voted"))
        table.add_row("Votes", f"{yes}/{ws.vote_threshold} required")

    # Shares
    share_files = sorted(SHARES_DIR.glob("share-*.json")) if SHARES_DIR.exists() else []
    table.add_row("Share files", str(len(share_files)))

    console.print(table)

    # Thresholds
    if days is not None:
        console.print()
        for stage_name, threshold in SILENCE_THRESHOLDS.items():
            remaining = threshold - days
            if remaining > 0:
                console.print(f"  [dim]{stage_name}: {remaining} days until trigger[/dim]")
            else:
                console.print(f"  [yellow]{stage_name}: TRIGGERED ({-remaining} days past)[/yellow]")


# ──────────────────────────────────────────────
# WATCHDOG
# ──────────────────────────────────────────────
@cli.group()
def watchdog():
    """Dead man's switch operations."""
    pass


@watchdog.command(name="run")
@click.option("--dry-run", is_flag=True, help="Show what would happen without acting")
def watchdog_run(dry_run):
    """Evaluate the dead man's switch and send notifications if needed."""
    ws = load_watchdog()
    new_stage, actions = evaluate(ws)
    state = _load_full_state()

    if not actions:
        console.print(f"[green]Stage: {new_stage}. No action needed.[/green]")
        return

    console.print(f"[bold]Stage: {ws.stage} -> {new_stage}[/bold]")
    owner = state.get("owner", {})
    contacts = state.get("contacts", [])

    for action in actions:
        if dry_run:
            console.print(f"  [yellow]DRY RUN: would {action}[/yellow]")
            continue

        if action == "send_owner_alert":
            days = days_since_checkin() or 0
            sent = send_owner_alert(owner.get("email", ""), days)
            log_notification("owner_alert", f"days={days} sent={sent}")
            console.print(f"  [yellow]Owner alert sent ({days} days silent)[/yellow]" if sent else f"  [dim]Owner alert logged (email not configured)[/dim]")

        elif action == "notify_contacts":
            days = days_since_checkin() or 0
            for c in contacts:
                sent = send_contact_notification(c["email"], c["name"], owner.get("name", ""), days)
                log_notification("contact_notify", f"to={c['name']} sent={sent}")
            ws.contacts_notified = True
            console.print(f"  [yellow]Contacts notified ({len(contacts)} people)[/yellow]")

        elif action == "request_votes":
            for c in contacts:
                sent = send_vote_request(c["email"], c["name"], owner.get("name", ""))
                log_notification("vote_request", f"to={c['name']} sent={sent}")
            console.print(f"  [bold yellow]Vote requests sent to {len(contacts)} contacts[/bold yellow]")

        elif action == "release_shares":
            console.print(f"  [bold red]SHARES RELEASED. Vault is now recoverable.[/bold red]")
            log_notification("shares_released", "vault recoverable")

    ws = transition(ws, new_stage)
    save_watchdog(ws)


# ──────────────────────────────────────────────
# VOTE — contacts submit trigger votes
# ──────────────────────────────────────────────
@cli.command()
@click.option("--contact", required=True, help="Name of the contact voting")
def vote(contact):
    """Submit a trigger vote confirming the owner is deceased/incapacitated."""
    ws = load_watchdog()
    ws = record_vote(ws, contact)
    save_watchdog(ws)

    yes = sum(1 for v in ws.votes.values() if v.get("voted"))
    console.print(f"[yellow]Vote recorded for {contact}. ({yes}/{ws.vote_threshold} needed)[/yellow]")

    if check_votes(ws):
        console.print("[bold red]Threshold reached. Vault will become recoverable on next watchdog run.[/bold red]")


# ──────────────────────────────────────────────
# RECOVER — heir-side vault recovery
# ──────────────────────────────────────────────
@cli.command()
@click.argument("share_files", nargs=-1, type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Save decrypted vault to file")
def recover(share_files, output):
    """Recover the vault using share files.

    Provide at least 3 share file paths (or as many as you have).
    """
    vault_data = load()
    if not vault_data:
        console.print("[red]No vault found at ~/.afterkey/[/red]")
        return

    ciphertext, meta = vault_data

    if len(share_files) < meta.shares_k:
        console.print(f"[red]Need at least {meta.shares_k} shares. Got {len(share_files)}.[/red]")
        return

    console.print(f"[dim]Loading {len(share_files)} shares...[/dim]")
    shares = collect_shares_for_recovery([Path(f) for f in share_files])

    console.print("[dim]Reconstructing key...[/dim]")
    secret_int = reconstruct(shares[:meta.shares_k])
    master_key = int_to_key(secret_int)

    console.print("[dim]Decrypting vault...[/dim]")
    try:
        inventory = unseal(ciphertext, meta, master_key)
    except Exception:
        console.print("[bold red]Decryption failed. Shares may be incorrect or corrupted.[/bold red]")
        return

    if output:
        Path(output).write_text(json.dumps(inventory, indent=2))
        console.print(f"[green]Vault decrypted and saved to {output}[/green]")
    else:
        console.print(Panel("[bold green]Vault decrypted successfully[/bold green]", border_style="green"))
        console.print()
        for asset in inventory.get("assets", []):
            atype = asset.get("type", "unknown")
            if atype == "crypto":
                console.print(Panel(
                    f"[bold]{asset.get('name', 'Wallet')}[/bold]\n"
                    f"Seed: {asset.get('seed', '')}\n"
                    f"Notes: {asset.get('notes', '')}",
                    title="Crypto Wallet",
                    border_style="yellow",
                ))
            elif atype == "password":
                console.print(Panel(
                    f"[bold]{asset.get('service', '?')}[/bold]\n"
                    f"Username: {asset.get('username', '')}\n"
                    f"Password: {asset.get('password', '')}\n"
                    f"Notes: {asset.get('notes', '')}",
                    title="Password",
                    border_style="blue",
                ))
            elif atype == "instruction":
                console.print(Panel(
                    f"[bold]For: {asset.get('recipient', '?')}[/bold]\n"
                    f"{asset.get('message', '')}",
                    title="Instruction",
                    border_style="green",
                ))
            else:
                console.print(f"  {asset}")


# ──────────────────────────────────────────────
# CONTACTS
# ──────────────────────────────────────────────
@cli.group()
def contacts():
    """Manage designated contacts."""
    pass


@contacts.command(name="add")
@click.argument("name")
@click.argument("email")
def contacts_add(name, email):
    """Add a designated contact."""
    state = _load_full_state()
    state.setdefault("contacts", []).append({"name": name, "email": email})
    _save_full_state(state)
    console.print(f"[green]Added contact: {name} ({email})[/green]")


@contacts.command(name="list")
def contacts_list():
    """List designated contacts."""
    state = _load_full_state()
    contact_list = state.get("contacts", [])
    if not contact_list:
        console.print("[yellow]No contacts. Add with: afterkey contacts add NAME EMAIL[/yellow]")
        return
    table = Table(title="Designated Contacts", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Email")
    for c in contact_list:
        table.add_row(c["name"], c["email"])
    console.print(table)


@contacts.command(name="remove")
@click.argument("name")
def contacts_remove(name):
    """Remove a designated contact by name."""
    state = _load_full_state()
    before = len(state.get("contacts", []))
    state["contacts"] = [c for c in state.get("contacts", []) if c["name"] != name]
    _save_full_state(state)
    removed = before - len(state["contacts"])
    if removed:
        console.print(f"[green]Removed {name}[/green]")
    else:
        console.print(f"[yellow]Contact '{name}' not found[/yellow]")
