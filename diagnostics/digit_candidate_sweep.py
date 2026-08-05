"""Targeted letter+digit candidate sweep for the Fluke 54 II B.

The full A-Z x A-Z sweep never tried anything containing a digit. This tests
a small, hand-picked set of channel/log-selector-shaped candidates (T1/T2
matching the meter's two thermocouple channels, plus similar read-flavored
guesses), one at a time, in the same session.

Same halt rule as single_letter_sweep.py: stop immediately on any response
other than empty or exactly b'1\\r' (a bare ACK or data response both count
as "stop and look", since we don't know yet whether it's a query or an action).
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

PORT = "COM3"
BAUD = 9600
RESPONSE_WINDOW_S = 1.0
INTER_COMMAND_DELAY_S = 0.2
LOG_PATH = Path("logs") / "digit_candidate_sweep.log"

CANDIDATES = ["T1", "T2", "L1", "L2", "M1", "M2", "R1", "R2",
              "D1", "D2", "S1", "S2", "N1", "N2", "C1", "C2"]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("digit_candidate_sweep")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


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
    logger = setup_logging(LOG_PATH)
    logger.info(f"=== digit_candidate_sweep start {datetime.now().isoformat(timespec='seconds')} "
                f"({len(CANDIDATES)} candidates: {CANDIDATES}) ===")
    logger.info("HALT RULE: stop immediately on any response other than empty or exactly b'1\\r'.")

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
    except SerialException as e:
        logger.info(f"OPEN_FAIL {type(e).__name__}: {e}")
        return 1

    halted_on: str | None = None
    tested: list[tuple[str, bytes]] = []
    try:
        with ser:
            for cmd in CANDIDATES:
                payload = (cmd + "\r").encode("ascii")
                ser.reset_input_buffer()
                ser.write(payload)
                ser.flush()
                response = read_available(ser, RESPONSE_WINDOW_S)
                tested.append((cmd, response))
                logger.info(f"{cmd}: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")

                if response not in (b"", b"1\r"):
                    halted_on = cmd
                    logger.info(f"*** HALT *** unexpected response to '{cmd}' -- "
                                f"stopping sweep, not sending remaining candidates.")
                    break

                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== digit_candidate_sweep end (tested={len(tested)}/{len(CANDIDATES)}, "
                    f"halted_on={halted_on}) ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
