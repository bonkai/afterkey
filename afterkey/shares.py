"""Share encoding, distribution, and recovery."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import APP_DIR, SHARES_DIR


def encode_share(
    share: tuple[int, int],
    share_index: int,
    owner_name: str,
    recipient: str,
) -> dict:
    """Package a share with metadata for distribution."""
    x, y = share
    return {
        "version": 1,
        "app": "afterkey",
        "owner": owner_name,
        "recipient": recipient,
        "share_index": share_index,
        "x": x,
        "y": format(y, "x"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "instructions": (
            f"This is share #{share_index} of {owner_name}'s Afterkey vault.\n"
            f"It was given to you ({recipient}) as part of their digital legacy plan.\n\n"
            f"DO NOT share this with anyone. Store it safely.\n\n"
            f"If {owner_name} passes away or becomes incapacitated, you will be\n"
            f"contacted with instructions on how to use this share to help unlock\n"
            f"their digital vault. You will need to combine this share with shares\n"
            f"held by other designated people.\n\n"
            f"This share alone cannot unlock anything."
        ),
    }


def decode_share(data: dict) -> tuple[int, int]:
    """Extract (x, y) from an encoded share."""
    return (data["x"], int(data["y"], 16))


def save_share(encoded: dict, output_dir: Path | None = None) -> Path:
    """Write a share to a JSON file."""
    output_dir = output_dir or SHARES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"share-{encoded['share_index']}-{encoded['recipient'].lower().replace(' ', '-')}.json"
    path = output_dir / filename
    path.write_text(json.dumps(encoded, indent=2))
    return path


def load_share(path: Path) -> tuple[int, int]:
    """Read a share from a JSON file."""
    data = json.loads(path.read_text())
    return decode_share(data)


def share_to_printable(encoded: dict) -> str:
    """Format a share for printing on paper."""
    lines = [
        "=" * 60,
        "AFTERKEY — DIGITAL LEGACY SHARE",
        "=" * 60,
        "",
        f"Owner:      {encoded['owner']}",
        f"Recipient:  {encoded['recipient']}",
        f"Share #:    {encoded['share_index']}",
        f"Created:    {encoded['created_at'][:10]}",
        "",
        "-" * 60,
        "SHARE DATA (keep this secret):",
        "-" * 60,
        f"X: {encoded['x']}",
        f"Y: {encoded['y']}",
        "-" * 60,
        "",
        encoded["instructions"],
        "",
        "=" * 60,
    ]
    return "\n".join(lines)


def share_to_compact(encoded: dict) -> str:
    """Compact string for QR code generation."""
    return f"afterkey:v1:{encoded['x']}:{encoded['y']}"


def collect_shares_for_recovery(share_paths: list[Path]) -> list[tuple[int, int]]:
    """Load multiple share files for vault recovery."""
    shares = []
    for path in share_paths:
        shares.append(load_share(path))
    return shares
