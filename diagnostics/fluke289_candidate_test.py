"""Test real Fluke 289-family command names against the 54 II B.

These are NOT blind guesses -- they come from the actual dmm_util Ruby driver
(github.com/fvaleur/dmm_util) implementing Fluke's documented 289/287 Remote
Interface commands. The 54 II B is a different (older, simpler) product line,
so there's no guarantee it recognizes any of these, but they're real,
read-only Fluke query commands, not invented mnemonics.

Excluded on purpose (write/reset-type, from the same family): DS, RI, RMP,
"mp <prop>,<val>", "mpq <prop>,<val>".

Same halt rule as previous sweeps: stop immediately on any response other
than empty or exactly b'1\\r'. Note the 289 spec documents additional status
codes '2' (execution error) and '5' (no data available) -- if the 54 II B
ever returns one of those, that itself means the command was RECOGNIZED
(just not executable in current state), which is important new information,
so it must also halt for inspection rather than being treated as a plain
rejection.
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
MAX_WINDOW_S = 5.0
QUIET_CUTOFF_S = 1.5
INTER_COMMAND_DELAY_S = 0.4
LOG_PATH = Path("logs") / "fluke289_candidate_test.log"

CANDIDATES = ["QDDA", "QSLS", "QRSI 0", "QSRR 0,0", "QMMSI 0", "QPSI 0", "QSMR 0"]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("fluke289_candidate_test")
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
    logger.info(f"=== fluke289_candidate_test start {datetime.now().isoformat(timespec='seconds')} "
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
                response = read_available_adaptive(ser)
                tested.append((cmd, response))
                logger.info(f"{cmd!r}: {len(response)} bytes -- HEX {hex_dump(response)} "
                            f"ASCII {ascii_dump(response)!r}")

                if response not in (b"", b"1\r"):
                    halted_on = cmd
                    logger.info(f"*** HALT *** unexpected/interesting response to {cmd!r} -- "
                                f"stopping, not sending remaining candidates.")
                    break

                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== fluke289_candidate_test end (tested={len(tested)}/{len(CANDIDATES)}, "
                    f"halted_on={halted_on}) ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
