"""Test whether the Fluke 54 II B expects its own response echoed back to it.

For each command in the list: send the command, capture the meter's response,
then echo that exact response back to the meter verbatim, then listen again
for anything further. This is purely read-only in effect (we're only ever
re-transmitting bytes the meter itself already sent, never anything new),
but if the meter is waiting for an echo before continuing a multi-part
transfer, this could reveal it.
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
MAX_WINDOW_S = 4.0
QUIET_CUTOFF_S = 1.2
INTER_STEP_DELAY_S = 0.3
LOG_PATH = Path("logs") / "echo_handshake_test.log"

COMMANDS = ["ID", "QS", "QM", "DL", "DUMP"]


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
    lines = [f"=== echo_handshake_test start {datetime.now().isoformat(timespec='seconds')} ===",
             f"Commands: {COMMANDS}"]

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
            ser.write(payload)
            ser.flush()
            response = read_available_adaptive(ser)
            line = (f"[{cmd}] sent {hex_dump(payload)} -- response ({len(response)}B): "
                    f"HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")
            print(line)
            lines.append(line)

            if response:
                time.sleep(INTER_STEP_DELAY_S)
                ser.write(response)  # echo the meter's own bytes back to it
                ser.flush()
                follow_up = read_available_adaptive(ser)
                line2 = (f"[{cmd}] echoed response back -- follow-up ({len(follow_up)}B): "
                         f"HEX {hex_dump(follow_up)} ASCII {ascii_dump(follow_up)!r}")
                print(line2)
                lines.append(line2)
            else:
                lines.append(f"[{cmd}] no response to echo, skipping echo step")

            time.sleep(INTER_STEP_DELAY_S)

    lines.append("=== echo_handshake_test end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
