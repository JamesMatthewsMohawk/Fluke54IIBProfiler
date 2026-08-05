"""Verify QM 1 behaves the same as bare QM."""
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
LOG_PATH = Path("logs") / "qm1_test.log"


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


INTER_CHAR_DELAY_S = 0.025  # 25ms


def send_and_capture(ser: serial.Serial, cmd: str, lines: list[str]) -> bytes:
    payload = (cmd + "\r").encode("ascii")
    ser.reset_input_buffer()
    for b in payload:
        ser.write(bytes([b]))
        ser.flush()
        time.sleep(INTER_CHAR_DELAY_S)
    response = read_available(ser, RESPONSE_WINDOW_S)
    line = (f"{cmd!r}: sent (char-by-char, {INTER_CHAR_DELAY_S*1000:.0f}ms gaps) HEX {hex_dump(payload)} "
            f"-- got {len(response)} bytes: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")
    print(line)
    lines.append(line)
    return response


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== qm1_test start {datetime.now().isoformat(timespec='seconds')} ==="]

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
        send_and_capture(ser, "QM", lines)
        time.sleep(0.3)
        send_and_capture(ser, "QM 1", lines)

    lines.append("=== qm1_test end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
