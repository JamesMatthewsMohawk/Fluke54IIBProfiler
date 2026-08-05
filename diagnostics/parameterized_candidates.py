"""Parameterized 2-letter command candidates for the Fluke 54 II B.

Rationale: the documented Fluke Remote Interface family only uses 2-letter
mnemonics, and at least one (SF) requires a <space><parameter> to do anything
-- sent bare, it would return the same generic '1' error as an unrecognized
command. Our earlier exhaustive 2-letter sweep only tested bare commands, so
any of GD/RD/GL/RM/GM/RC/DL could in principle be real commands that simply
need an argument.

Same halt rule as previous sweeps: stop immediately on anything other than
empty or exactly b'1\\r'.
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
RESPONSE_WINDOW_S = 1.5
INTER_COMMAND_DELAY_S = 0.3
LOG_PATH = Path("logs") / "parameterized_candidates.log"

CANDIDATES = ["GD 1", "RD 1", "GL 1", "RM 1", "GM 1", "RC 1", "DL 1"]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("parameterized_candidates")
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
    logger.info(f"=== parameterized_candidates start {datetime.now().isoformat(timespec='seconds')} "
                f"({CANDIDATES}) ===")
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
                logger.info(f"{cmd!r}: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")

                if response not in (b"", b"1\r"):
                    halted_on = cmd
                    logger.info(f"*** HALT *** unexpected response to {cmd!r} -- "
                                f"stopping, not sending remaining candidates.")
                    break

                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== parameterized_candidates end (tested={len(tested)}/{len(CANDIDATES)}, "
                    f"halted_on={halted_on}) ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
