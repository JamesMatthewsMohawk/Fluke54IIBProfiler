"""Offline license key tooling. Run by hand -- never shipped in the built app.

Usage:
    python tools/generate_license.py keygen
        Creates license_signing_key.pem (KEEP THIS SECRET, never commit it)
        and prints the public key hex to paste into app/licensing.py.

    python tools/generate_license.py issue "Customer Name" <machine-id>
        Signs a license key for that customer/machine using
        license_signing_key.pem. The machine ID comes from the Settings
        tab's License card on the PC that will run the app.
"""
from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEY_PREFIX = "KOTPRO-"
PRIVATE_KEY_PATH = Path(__file__).resolve().parent.parent / "license_signing_key.pem"


def cmd_keygen() -> None:
    if PRIVATE_KEY_PATH.exists():
        print(f"Refusing to overwrite existing {PRIVATE_KEY_PATH}")
        sys.exit(1)

    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIVATE_KEY_PATH.write_bytes(pem)

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    print(f"Wrote private key to {PRIVATE_KEY_PATH} -- keep this secret, never commit it.")
    print()
    print("Paste this into app/licensing.py as _PUBLIC_KEY_HEX:")
    print(public_bytes.hex())


def cmd_issue(customer: str, machine_id: str) -> None:
    """customer is only printed here for your own bookkeeping -- it is not
    part of the signed key, so keep your own record of who has which key."""
    if not PRIVATE_KEY_PATH.exists():
        print(f"No signing key at {PRIVATE_KEY_PATH} -- run 'keygen' first.")
        sys.exit(1)

    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        print(f"{PRIVATE_KEY_PATH} is not an Ed25519 private key.")
        sys.exit(1)

    try:
        machine_id_bytes = uuid.UUID(machine_id).bytes
    except ValueError:
        print(f"'{machine_id}' doesn't look like a machine ID (expected a GUID).")
        sys.exit(1)

    signature = private_key.sign(machine_id_bytes)
    blob = machine_id_bytes + signature

    b32 = base64.b32encode(blob).decode("ascii").rstrip("=")
    grouped = "-".join(b32[i:i + 5] for i in range(0, len(b32), 5))
    print(f"License for {customer} ({machine_id}):")
    print(f"{KEY_PREFIX}{grouped}")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "keygen":
        cmd_keygen()
        return 0
    if len(sys.argv) == 4 and sys.argv[1] == "issue":
        cmd_issue(sys.argv[2], sys.argv[3])
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
