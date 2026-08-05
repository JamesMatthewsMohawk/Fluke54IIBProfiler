"""Scan QD 0 through QD <max_index> to find how many samples are stored
after a fresh 30-second log at a 1-second interval."""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

PORT = "COM3"
BAUD = 9600
RESPONSE_WINDOW_S = 1.2
INTER_COMMAND_DELAY_S = 0.2
LOG_PATH = Path("logs") / "qd_range_scan.log"

MAX_INDEX = 40


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


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== qd_range_scan start {datetime.now().isoformat(timespec='seconds')} ==="]

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

    valid_count = 0
    with ser:
        for idx in range(MAX_INDEX + 1):
            payload = f"QD {idx}\r".encode("ascii")
            ser.reset_input_buffer()
            ser.write(payload)
            ser.flush()
            response = read_available(ser, RESPONSE_WINDOW_S)
            ok = response.startswith(b"0\r")
            if ok:
                valid_count += 1
            line = (f"QD {idx}: {len(response)} bytes {'OK' if ok else 'REJECTED'} -- "
                    f"HEX {hex_dump(response)}")
            print(line)
            lines.append(line)
            time.sleep(INTER_COMMAND_DELAY_S)

    lines.append(f"=== qd_range_scan end, valid_count={valid_count} ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
