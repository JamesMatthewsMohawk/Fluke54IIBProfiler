"""Offline, machine-locked license keys gating meter downloads.

A key is issued by tools/generate_license.py (run by hand, offline, with
the private signing key -- never shipped in the app) and looks like
KOTPRO-XXXXX-XXXXX-.... It's this machine's ID, Ed25519-signed. This
module only ever holds the public key, so verifying a key here can't be
used to forge new ones.

This is a soft gate, not DRM: anyone with full access to their own
machine and enough patience could patch the check out of the app. It's
meant to make unlicensed meter use require deliberate effort, not to
withstand a determined attacker.
"""
from __future__ import annotations

import base64
import uuid
import winreg

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

KEY_PREFIX = "KOTPRO-"
_MACHINE_ID_BYTES = 16

# Public half of the offline signing keypair -- safe to embed, since it
# can only verify keys, not create them. Generated once by
# tools/generate_license.py; the private half never leaves that machine.
_PUBLIC_KEY_HEX = "a05964bfad91c9716aa639aa8a0ad02649ebcc302205b15f5e743448e068aa4b"


def get_machine_id() -> str:
    """A stable per-Windows-install identifier, used to lock a key to one PC."""
    key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Cryptography",
        0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
    )
    try:
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value)
    finally:
        winreg.CloseKey(key)


def is_licensed(key_text: str | None) -> bool:
    """Whether key_text is a validly-signed license for this machine."""
    if not key_text:
        return False
    key_text = key_text.strip()
    if not key_text.upper().startswith(KEY_PREFIX):
        return False

    body = key_text[len(KEY_PREFIX):].replace("-", "").replace(" ", "").upper()
    padded = body + "=" * ((-len(body)) % 8)
    try:
        blob = base64.b32decode(padded)
    except (ValueError, TypeError):
        return False
    if len(blob) <= _MACHINE_ID_BYTES:
        return False

    machine_id_bytes, signature = blob[:_MACHINE_ID_BYTES], blob[_MACHINE_ID_BYTES:]

    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(_PUBLIC_KEY_HEX))
    try:
        public_key.verify(signature, machine_id_bytes)
    except InvalidSignature:
        return False

    try:
        machine_id = str(uuid.UUID(bytes=machine_id_bytes))
    except ValueError:
        return False
    return machine_id == get_machine_id()
