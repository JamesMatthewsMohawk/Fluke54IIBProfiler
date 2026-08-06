"""Shared logic for issuing license keys, used by both the CLI
(generate_license.py) and the standalone GUI (license_key_gui.py).

Kept separate from app/licensing.py on purpose: that module ships inside
the main app and only ever verifies a key against the public half of the
signing keypair. Nothing here is imported by the main app, so the private
key handling in this file never ends up bundled into a customer's build.
"""
from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEY_PREFIX = "KOTPRO-"


def private_key_path() -> Path:
    """Where license_signing_key.pem lives, next to this tool wherever it runs from.

    Mirrors app/database.py's DB-next-to-the-exe resolution: under
    PyInstaller, __file__ resolves inside a temp extraction dir that's
    wiped after every run, so the persistent signing key must be anchored
    to sys.executable's real, stable location instead.
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "license_signing_key.pem"


def has_signing_key() -> bool:
    return private_key_path().exists()


def generate_keypair() -> str:
    """Create license_signing_key.pem. Returns the public key hex to bake
    into app/licensing.py. Raises FileExistsError if a key is already there."""
    path = private_key_path()
    if path.exists():
        raise FileExistsError(f"A signing key already exists at {path} -- refusing to overwrite it.")

    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return public_bytes.hex()


def issue_key(machine_id: str) -> str:
    """Sign a license key for machine_id (a GUID string). Raises ValueError
    for a malformed machine_id, FileNotFoundError if there's no signing key."""
    path = private_key_path()
    if not path.exists():
        raise FileNotFoundError(f"No signing key at {path} -- generate one first.")

    try:
        machine_id_bytes = uuid.UUID(machine_id.strip()).bytes
    except ValueError:
        raise ValueError(f"'{machine_id}' doesn't look like a machine ID (expected a GUID).") from None

    private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError(f"{path} is not an Ed25519 private key.")

    signature = private_key.sign(machine_id_bytes)
    blob = machine_id_bytes + signature

    b32 = base64.b32encode(blob).decode("ascii").rstrip("=")
    grouped = "-".join(b32[i:i + 5] for i in range(0, len(b32), 5))
    return f"{KEY_PREFIX}{grouped}"
