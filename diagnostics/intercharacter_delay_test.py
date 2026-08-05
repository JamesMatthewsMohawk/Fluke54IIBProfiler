"""Test sending commands one character at a time with a small inter-character
delay, instead of writing the whole string in a single burst.

Every previous test wrote the full command + '\\r' in one ser.write() call.
This sends each byte individually with a delay in between, in case the
meter's firmware polling loop has trouble with a command arriving as one
fast USB-buffered burst.
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
INTER_COMMAND_DELAY_S = 0.4
INTER_CHAR_DELAY_S = 0.008  # 8ms, middle of the requested 5-10ms range
LOG_PATH = Path("logs") / "intercharacter_delay_test.log"

COMMANDS = ["ID", "QS", "QM", "DL"]


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


def write_slow(ser: serial.Serial, payload: bytes, delay_s: float) -> None:
    for b in payload:
        ser.write(bytes([b]))
        ser.flush()
        time.sleep(delay_s)


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== intercharacter_delay_test start {datetime.now().isoformat(timespec='seconds')} ===",
             f"Inter-character delay: {INTER_CHAR_DELAY_S * 1000:.0f}ms"]

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
        for cmd in COMMANDS:
            payload = (cmd + "\r").encode("ascii")
            ser.reset_input_buffer()
            write_slow(ser, payload, INTER_CHAR_DELAY_S)
            response = read_available(ser, RESPONSE_WINDOW_S)
            line = (f"{cmd}: sent (char-by-char, {INTER_CHAR_DELAY_S*1000:.0f}ms gaps) HEX {hex_dump(payload)} "
                    f"-- got {len(response)} bytes: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")
            print(line)
            lines.append(line)
            time.sleep(INTER_COMMAND_DELAY_S)

    lines.append("=== intercharacter_delay_test end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
