"""Send exactly one command, once, and capture a long response window.

Usage: python test_single_cmd.py "QS 1"
The command text has '\\r' appended automatically.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

PORT = "COM3"
BAUD = 9600
RESPONSE_WINDOW_S = 10.0
LOG_PATH = Path("logs") / "test_single_cmd.log"


def hex_dump(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data) if data else "(none)"


def ascii_dump(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data) if data else "(none)"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: test_single_cmd.py <command text, without CR>")
        return 2

    cmd_text = sys.argv[1]
    payload = (cmd_text + "\r").encode("ascii")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== test_single_cmd session start {datetime.now().isoformat(timespec='seconds')} ===",
             f"Command: {cmd_text!r}"]

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
    except SerialException as e:
        msg = f"OPEN_FAIL {type(e).__name__}: {e}"
        print(msg)
        lines.append(msg)
        LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
        return 1

    with ser:
        ser.reset_input_buffer()
        ser.write(payload)
        ser.flush()
        lines.append(f"Sent: HEX {hex_dump(payload)} ASCII {ascii_dump(payload)!r}")

        end_time = time.monotonic() + RESPONSE_WINDOW_S
        buf = bytearray()
        last_growth = time.monotonic()
        while time.monotonic() < end_time:
            waiting = ser.in_waiting
            if waiting:
                buf.extend(ser.read(waiting))
                last_growth = time.monotonic()
            else:
                time.sleep(0.02)
            if buf and (time.monotonic() - last_growth) > 2.0:
                break

        response = bytes(buf)
        lines.append(f"Total bytes: {len(response)}")
        lines.append(f"HEX: {hex_dump(response)}")
        lines.append(f"ASCII: {ascii_dump(response)!r}")

    output = "\n".join(lines)
    print(output)
    LOG_PATH.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
