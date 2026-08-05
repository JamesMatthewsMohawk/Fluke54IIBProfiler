"""Test: send DS\\r, wait 200ms, then send VA\\r, and see what comes back.

Note: 'VA' alone was already part of the exhaustive 674-combination uppercase
sweep and returned 1\\r (rejected). This checks whether DS changes that.
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
RESPONSE_WINDOW_S = 2.0
POST_DS_DELAY_S = 0.2
LOG_PATH = Path("logs") / "ds_then_va_test.log"


def hex_dump(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data) if data else "(none)"


def ascii_dump(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data) if data else "(none)"


def read_available(ser: serial.Serial, window_s: float) -> bytes:
    end_time = time.monotonic() + window_s
    buf = bytearray()
    while time.monotonic() < end_time:
        waiting = ser.in_waiting
        if waiting:
            buf.extend(ser.read(waiting))
        else:
            time.sleep(0.02)
    return bytes(buf)


def send_and_capture(ser: serial.Serial, cmd: str, lines: list[str]) -> bytes:
    payload = (cmd + "\r").encode("ascii")
    ser.reset_input_buffer()
    ser.write(payload)
    ser.flush()
    response = read_available(ser, RESPONSE_WINDOW_S)
    line = (f"{cmd}: sent HEX {hex_dump(payload)} -- got {len(response)} bytes: "
            f"HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")
    print(line)
    lines.append(line)
    return response


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== ds_then_va_test start {datetime.now().isoformat(timespec='seconds')} ==="]

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
        send_and_capture(ser, "ID", lines)
        time.sleep(0.3)

        send_and_capture(ser, "DS", lines)
        time.sleep(POST_DS_DELAY_S)
        send_and_capture(ser, "VA", lines)
        time.sleep(0.3)

        send_and_capture(ser, "ID", lines)

    lines.append("=== ds_then_va_test end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
