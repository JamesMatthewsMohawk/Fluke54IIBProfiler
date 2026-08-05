"""Send an exact raw hex byte sequence: 02 10 51 00 00 03."""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

PORT = "COM3"
BAUD = 9600
MAX_WINDOW_S = 4.0
QUIET_CUTOFF_S = 1.5
LOG_PATH = Path("logs") / "raw_hex_test2.log"

RAW_PAYLOAD = bytes([0x02, 0x10, 0x51, 0x00, 0x00, 0x03])


def hex_dump(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data) if data else "(none)"


def ascii_dump(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data) if data else "(none)"


def read_available_adaptive(ser: serial.Serial) -> bytes:
    end_time = time.monotonic() + MAX_WINDOW_S
    buf = bytearray()
    last_growth = time.monotonic()
    while time.monotonic() < end_time:
        waiting = ser.in_waiting
        if waiting:
            buf.extend(ser.read(waiting))
            last_growth = time.monotonic()
        else:
            time.sleep(0.02)
        if buf and (time.monotonic() - last_growth) > QUIET_CUTOFF_S:
            break
    return bytes(buf)


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== raw_hex_test2 start {datetime.now().isoformat(timespec='seconds')} ===",
             f"Raw payload: {hex_dump(RAW_PAYLOAD)}"]

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
        ser.write(RAW_PAYLOAD)
        ser.flush()
        response = read_available_adaptive(ser)
        line = (f"Sent HEX {hex_dump(RAW_PAYLOAD)} -- got {len(response)} bytes: "
                f"HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")
        print(line)
        lines.append(line)

    lines.append("=== raw_hex_test2 end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
