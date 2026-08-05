"""Test DTR=LOW / RTS=HIGH line configuration against the Fluke 54 II B.

This is the inverse of dtr_rts_test.py (DTR=HIGH/RTS=LOW), and matches the
literal wording of Fluke's documented spec for the related 89-IV/87-IV IR
cable: "DTR disabled, RTS enabled."
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
LOG_PATH = Path("logs") / "dtr_rts_test_inverted.log"

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


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== dtr_rts_test_inverted start {datetime.now().isoformat(timespec='seconds')} ===",
             "Setting DTR=False (LOW/disabled), RTS=True (HIGH/enabled) explicitly."]

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
        ser.dtr = False
        ser.rts = True
    except SerialException as e:
        msg = f"OPEN_FAIL {type(e).__name__}: {e}"
        print(msg)
        lines.append(msg)
        LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
        return 1

    with ser:
        line = f"Line state after set: dtr={ser.dtr} rts={ser.rts} cts={ser.cts} dsr={ser.dsr}"
        print(line)
        lines.append(line)
        time.sleep(0.5)  # let the line state settle before sending anything

        for cmd in COMMANDS:
            payload = (cmd + "\r").encode("ascii")
            ser.reset_input_buffer()
            ser.write(payload)
            ser.flush()
            response = read_available(ser, RESPONSE_WINDOW_S)
            line = (f"{cmd}: sent HEX {hex_dump(payload)} -- got {len(response)} bytes: "
                    f"HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")
            print(line)
            lines.append(line)
            time.sleep(INTER_COMMAND_DELAY_S)

    lines.append("=== dtr_rts_test_inverted end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
