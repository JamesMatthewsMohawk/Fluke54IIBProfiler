"""Phase 4 systematic 2-letter command sweep for the Fluke 54 II B.

The confirmed protocol (from fluke_probe.py / protocol_scanner.py results, matching
the documented Fluke 189/187/89-IV/87-IV Remote Interface family) uses 2-letter
ASCII command codes terminated with '\\r', responding '<status>\\r[<data>\\r]'.

This sweeps every A-Z x A-Z two-letter combination (676 total) looking for
undocumented commands specific to the 54 II B (memory count, log download,
timestamps), since ID works but QM does not on this model.

SAFETY: 'RI' (Reset Instrument -- factory reset, clears all logged memory) and
'DS' (Default Setup -- power-cycle equivalent) are HARD-EXCLUDED from this sweep
and must never be sent automatically. Every other 2-letter combination is, per
the documented protocol family, either a query or a syntax error -- nothing in
the known command set beyond RI/DS writes or clears data.
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
RESPONSE_WINDOW_S = 0.3
INTER_COMMAND_DELAY_S = 0.1
LOG_PATH = Path("logs") / "brute_force_2letter.log"

# Never send these, even by accident: RI clears logged memory (factory reset),
# DS is equivalent to a power cycle. Both are documented as state-changing.
HARD_EXCLUDED = {"RI", "DS"}


def all_two_letter_commands() -> list[str]:
    letters = string.ascii_uppercase
    combos = [a + b for a in letters for b in letters]
    return [c for c in combos if c not in HARD_EXCLUDED]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("brute_force_2letter")
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
            time.sleep(0.02)
    return bytes(buf)


def main() -> int:
    logger = setup_logging(LOG_PATH)
    commands = all_two_letter_commands()
    logger.info(f"=== brute_force_2letter session start {datetime.now().isoformat(timespec='seconds')} "
                f"({len(commands)} commands, excluded={sorted(HARD_EXCLUDED)}) ===")
    logger.info("Meter must be in 'Ir SEnd' mode (SHIFT + RECALL) for the whole sweep.")

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
    except SerialException as e:
        logger.info(f"OPEN_FAIL {type(e).__name__}: {e}")
        return 1

    interesting: list[tuple[str, bytes]] = []
    silent_streak = 0
    try:
        with ser:
            for cmd in commands:
                payload = (cmd + "\r").encode("ascii")
                ser.reset_input_buffer()
                ser.write(payload)
                ser.flush()
                response = read_available(ser, RESPONSE_WINDOW_S)

                if response == b"":
                    silent_streak += 1
                else:
                    silent_streak = 0

                if response and response != b"1\r":
                    interesting.append((cmd, response))
                    logger.info(f"HIT {cmd}: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")

                time.sleep(INTER_COMMAND_DELAY_S)

                if silent_streak == 20:
                    logger.info(f"WARNING: last 20 commands got zero response (possible mode timeout) "
                                f"around command '{cmd}' at {datetime.now().isoformat(timespec='seconds')}")
    finally:
        logger.info("=== brute_force_2letter session end ===")
        logger.info(f"Interesting responses ({len(interesting)}):")
        for cmd, response in interesting:
            logger.info(f"  {cmd}: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")

    return 0 if interesting else 1


if __name__ == "__main__":
    sys.exit(main())
