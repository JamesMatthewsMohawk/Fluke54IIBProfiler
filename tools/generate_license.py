"""Offline license key tooling. Run by hand -- never shipped in the built app.

Usage:
    python tools/generate_license.py keygen
        Creates license_signing_key.pem (KEEP THIS SECRET, never commit it)
        and prints the public key hex to paste into app/licensing.py.

    python tools/generate_license.py issue "Customer Name" <machine-id>
        Signs a license key for that customer/machine using
        license_signing_key.pem. The machine ID comes from the Settings
        tab's License card on the PC that will run the app.

See license_key_gui.py for a point-and-click version of "issue" that
doesn't need a terminal.
"""
from __future__ import annotations

import sys

from license_key_logic import generate_keypair, issue_key, private_key_path


def cmd_keygen() -> None:
    try:
        public_key_hex = generate_keypair()
    except FileExistsError as e:
        print(e)
        sys.exit(1)

    print(f"Wrote private key to {private_key_path()} -- keep this secret, never commit it.")
    print()
    print("Paste this into app/licensing.py as _PUBLIC_KEY_HEX:")
    print(public_key_hex)


def cmd_issue(customer: str, machine_id: str) -> None:
    """customer is only printed here for your own bookkeeping -- it is not
    part of the signed key, so keep your own record of who has which key."""
    try:
        key = issue_key(machine_id)
    except (ValueError, FileNotFoundError) as e:
        print(e)
        sys.exit(1)

    print(f"License for {customer} ({machine_id}):")
    print(key)


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
