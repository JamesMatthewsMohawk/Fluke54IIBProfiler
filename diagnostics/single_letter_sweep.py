"""Single-letter command sweep (A\\r through Z\\r) for the Fluke 54 II B.

Lesson from the 2-letter brute force incident: a bare '0\\r' ACK with no
comma-prefixed data payload is the signature of an action/write command
(see feedback memory on the CD incident), not a query. This sweep therefore
HALTS IMMEDIATELY the moment any letter produces a bare-ACK or any response
other than '1\\r' (rejected) or empty (ignored) -- it does not continue
scanning past a suspicious hit the way the earlier 2-letter sweep did.
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
RESPONSE_WINDOW_S = 1.0
INTER_COMMAND_DELAY_S = 0.2
LOG_PATH = Path("logs") / "single_letter_sweep.log"


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("single_letter_sweep")
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
    letters = list(string.ascii_uppercase)
    logger.info(f"=== single_letter_sweep start {datetime.now().isoformat(timespec='seconds')} "
                f"({len(letters)} letters) ===")
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
            for letter in letters:
                payload = (letter + "\r").encode("ascii")
                ser.reset_input_buffer()
                ser.write(payload)
                ser.flush()
                response = read_available(ser, RESPONSE_WINDOW_S)
                tested.append((letter, response))
                logger.info(f"{letter}: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")

                if response not in (b"", b"1\r"):
                    halted_on = letter
                    logger.info(f"*** HALT *** unexpected response to '{letter}' -- "
                                f"stopping sweep, not sending remaining letters.")
                    break

                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== single_letter_sweep end (tested={len(tested)}/{len(letters)}, "
                    f"halted_on={halted_on}) ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
