"""One careful, single-pass test of DLE-stuffed binary framing on the Fluke 54 II B.

Some Fluke instruments (per community reverse-engineering notes on the related
28X/190 families) use a binary frame of the form:
    DLE STX <DATA> DLE ETX <CRC>
where DLE=0x10, STX=0x02, ETX=0x03, and the CRC algorithm is not publicly
documented. We have no known valid DATA payload or CRC for the 54 II B, so
this is a low-probability, exploratory test -- not a guess we expect to
succeed, but a cheap way to check whether the meter reacts to this framing
at all (a real ACK/NAK response vs. total silence).

Every candidate is sent once, response captured with a generous adaptive
window, and NOTHING is repeated automatically based on the result -- this
script sends its fixed list once and stops, full stop, regardless of what
comes back.
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
MAX_WINDOW_S = 3.0
QUIET_CUTOFF_S = 1.0
INTER_ATTEMPT_DELAY_S = 0.5
LOG_PATH = Path("logs") / "binary_framing_test.log"

DLE, STX, ETX = 0x10, 0x02, 0x03

CANDIDATES: list[tuple[str, bytes]] = [
    ("empty frame, no CRC", bytes([DLE, STX, DLE, ETX])),
    ("empty frame, 1-byte zero CRC", bytes([DLE, STX, DLE, ETX, 0x00])),
    ("single zero data byte, 1-byte zero CRC", bytes([DLE, STX, 0x00, DLE, ETX, 0x00])),
]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("binary_framing_test")
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
    logger = setup_logging(LOG_PATH)
    logger.info(f"=== binary_framing_test start {datetime.now().isoformat(timespec='seconds')} ===")
    logger.info(f"{len(CANDIDATES)} candidates, single pass, no follow-up sends regardless of result.")

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
    except SerialException as e:
        logger.info(f"OPEN_FAIL {type(e).__name__}: {e}")
        return 1

    results: list[tuple[str, bytes]] = []
    try:
        with ser:
            for label, payload in CANDIDATES:
                ser.reset_input_buffer()
                ser.write(payload)
                ser.flush()
                response = read_available_adaptive(ser)
                results.append((label, response))
                logger.info(f"{label}: sent HEX {hex_dump(payload)} -- "
                            f"got {len(response)} bytes: HEX {hex_dump(response)} "
                            f"ASCII {ascii_dump(response)!r}")
                time.sleep(INTER_ATTEMPT_DELAY_S)
    finally:
        logger.info("=== binary_framing_test end ===")
        any_response = any(r for _, r in results)
        logger.info(f"Any response at all: {any_response}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
