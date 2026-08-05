"""Test DTR=HIGH / RTS=LOW line configuration against the Fluke 54 II B.

Every prior test in this investigation used pyserial's default line state
(confirmed early on to be DTR=True, RTS=True on this FTDI adapter). This is
the first test with RTS explicitly deasserted while DTR stays asserted --
notably, Fluke's own documented spec for the related 89-IV/87-IV meters
requires DTR disabled / RTS enabled for their IR cable, a different but
related asymmetric configuration we have never tried here.

Sends known commands (ID, QS) as a sanity check plus a couple of
previously-rejected ones (QM, DL) to see if the response changes under this
line configuration.
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
LOG_PATH = Path("logs") / "dtr_rts_test.log"

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
    lines = [f"=== dtr_rts_test start {datetime.now().isoformat(timespec='seconds')} ===",
             "Setting DTR=True (HIGH), RTS=False (LOW) explicitly."]

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
        ser.dtr = True
        ser.rts = False
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

    lines.append("=== dtr_rts_test end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
