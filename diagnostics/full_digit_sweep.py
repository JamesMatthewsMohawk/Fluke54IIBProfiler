"""Remaining-character-space sweep for the Fluke 54 II B: digit-containing 2-char commands.

Covers everything not yet tested:
  - digit+digit    (00-99):        100 combos
  - letter+digit   (A1-Z9):        260 combos, minus the 16 already tested
                                   in digit_candidate_sweep.py
  - digit+letter   (1A-9Z):        260 combos

Same halt rule as the previous sweeps: stop immediately on any response other
than empty or exactly b'1\\r' -- a bare ACK or data response both mean "stop
and look", not "log it and keep going" (see the CD incident).
"""
from __future__ import annotations

import logging
import string
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

PORT = "COM3"
BAUD = 9600
RESPONSE_WINDOW_S = 0.6
INTER_COMMAND_DELAY_S = 0.15
LOG_PATH = Path("logs") / "full_digit_sweep.log"

ALREADY_TESTED = {"T1", "T2", "L1", "L2", "M1", "M2", "R1", "R2",
                  "D1", "D2", "S1", "S2", "N1", "N2", "C1", "C2"}


def build_candidates() -> list[str]:
    letters = string.ascii_uppercase
    digits = string.digits
    candidates: list[str] = []
    # digit+digit
    for a in digits:
        for b in digits:
            candidates.append(a + b)
    # letter+digit
    for a in letters:
        for b in digits:
            combo = a + b
            if combo not in ALREADY_TESTED:
                candidates.append(combo)
    # digit+letter
    for a in digits:
        for b in letters:
            candidates.append(a + b)
    return candidates


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("full_digit_sweep")
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
    candidates = build_candidates()
    logger.info(f"=== full_digit_sweep start {datetime.now().isoformat(timespec='seconds')} "
                f"({len(candidates)} candidates) ===")
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
    tested_count = 0
    try:
        with ser:
            for cmd in candidates:
                payload = (cmd + "\r").encode("ascii")
                ser.reset_input_buffer()
                ser.write(payload)
                ser.flush()
                response = read_available(ser, RESPONSE_WINDOW_S)
                tested_count += 1

                if response not in (b"", b"1\r"):
                    halted_on = cmd
                    logger.info(f"*** HALT *** {cmd}: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")
                    logger.info(f"*** HALT *** unexpected response to '{cmd}' -- "
                                f"stopping sweep, not sending remaining candidates.")
                    break

                if tested_count % 50 == 0:
                    logger.info(f"... progress: {tested_count}/{len(candidates)} tested, "
                                f"last={cmd}, all clean so far")

                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== full_digit_sweep end (tested={tested_count}/{len(candidates)}, "
                    f"halted_on={halted_on}) ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
