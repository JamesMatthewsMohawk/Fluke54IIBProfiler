"""Exhaustive lowercase 2-letter command sweep for the Fluke 54 II B.

Every previous sweep in this investigation (2-letter, 1-letter, digit-containing,
parameterized, sibling-family names) used UPPERCASE letters only. This is a
genuinely untested space: other Fluke models document commands as
case-insensitive, but this meter has already proven to differ from those
models in multiple ways, so case-sensitivity has never actually been verified
here.

Same halt rule as previous sweeps: stop immediately on any response other
than empty or exactly b'1\\r'. Lowercase versions of the known-dangerous
commands (cd, ri, ds) are hard-excluded, same as their uppercase originals.
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
RESPONSE_WINDOW_S = 0.5
INTER_COMMAND_DELAY_S = 0.15
LOG_PATH = Path("logs") / "lowercase_sweep.log"

HARD_EXCLUDED = {"cd", "ri", "ds"}


def build_candidates() -> list[str]:
    letters = string.ascii_lowercase
    return [a + b for a in letters for b in letters if (a + b) not in HARD_EXCLUDED]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("lowercase_sweep")
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
    logger.info(f"=== lowercase_sweep start {datetime.now().isoformat(timespec='seconds')} "
                f"({len(candidates)} candidates, excluded={sorted(HARD_EXCLUDED)}) ===")
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
                    logger.info(f"*** HALT *** unexpected response to '{cmd}' -- stopping sweep.")
                    break

                if tested_count % 100 == 0:
                    logger.info(f"... progress: {tested_count}/{len(candidates)} tested, "
                                f"last={cmd}, all clean so far")

                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== lowercase_sweep end (tested={tested_count}/{len(candidates)}, "
                    f"halted_on={halted_on}) ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
