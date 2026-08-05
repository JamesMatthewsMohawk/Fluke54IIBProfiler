"""Phase 3 command discovery for the Fluke 54 II B.

Sends a fixed list of candidate handshake commands to the meter while it is
showing "Ir SEnd" and captures whatever comes back, as raw bytes (no ASCII
assumption). Every attempt -- command sent, response bytes, timestamp -- is
logged to logs/fluke_probe.log and printed to the console.

This is read-only: none of the candidate commands write to or clear the
meter's memory or settings.
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
RESPONSE_WINDOW_S = 2.0
INTER_COMMAND_DELAY_S = 0.5
LOG_PATH = Path("logs") / "fluke_probe.log"

CANDIDATE_COMMANDS: list[tuple[str, bytes]] = [
    ("ID\\r", b"ID\r"),
    ("ID\\n", b"ID\n"),
    ("ID\\r\\n", b"ID\r\n"),
    ("QM\\r", b"QM\r"),
    ("QM\\n", b"QM\n"),
    ("?\\r", b"?\r"),
    ("HELP\\r", b"HELP\r"),
]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("fluke_probe")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

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
            time.sleep(0.05)
    return bytes(buf)


def probe_one(ser: serial.Serial, logger: logging.Logger, label: str, payload: bytes) -> bytes:
    ts = datetime.now().isoformat(timespec="milliseconds")
    logger.info(f"--- attempt {label} @ {ts} ---")
    logger.info(f"Command Sent:\nHEX: {hex_dump(payload)}\nASCII: {ascii_dump(payload)!r}")

    ser.reset_input_buffer()
    ser.write(payload)
    ser.flush()

    response = read_available(ser, RESPONSE_WINDOW_S)
    logger.info(f"Response:\nHEX: {hex_dump(response)}\nASCII: {ascii_dump(response)!r}")
    logger.info(f"Timestamp: {ts}")
    logger.info(f"Bytes received: {len(response)}\n")
    return response


def main() -> int:
    logger = setup_logging(LOG_PATH)
    logger.info(f"=== fluke_probe session start {datetime.now().isoformat(timespec='seconds')} ===")
    logger.info("Meter must be showing 'Ir SEnd' (SHIFT + RECALL) before this runs.")

    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2,
        )
    except SerialException as e:
        logger.info(f"OPEN_FAIL {type(e).__name__}: {e}")
        return 1

    any_response = False
    try:
        with ser:
            for label, payload in CANDIDATE_COMMANDS:
                response = probe_one(ser, logger, label, payload)
                if response:
                    any_response = True
                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== fluke_probe session end any_response={any_response} ===")

    return 0 if any_response else 1


if __name__ == "__main__":
    sys.exit(main())
