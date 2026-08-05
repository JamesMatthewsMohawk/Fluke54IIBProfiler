"""Phase 2 serial monitor for Fluke 54 II B IRUSB communication discovery.

Continuously monitors COM3 and prints/logs every received chunk as:

    HH:MM:SS RX
    HEX:
    55 AA 01 FF

    ASCII:
    U...

All output is duplicated to logs/fluke_serial_capture.log.
Runs until interrupted (Ctrl+C) or, if --duration is given, for that many seconds.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

DEFAULT_PORT = "COM3"
DEFAULT_BAUD = 9600
POLL_INTERVAL_S = 0.05
LOG_PATH = Path("logs") / "fluke_serial_capture.log"


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("fluke_serial_monitor")
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


def format_rx(data: bytes) -> str:
    ts = datetime.now().strftime("%H:%M:%S")
    hex_str = " ".join(f"{b:02X}" for b in data)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    return f"{ts} RX\nHEX:\n{hex_str}\n\nASCII:\n{ascii_str}\n"


def monitor(ser: serial.Serial, logger: logging.Logger, duration_s: float | None) -> int:
    end_time = time.monotonic() + duration_s if duration_s is not None else None
    total_bytes = 0
    logger.info(f"--- monitor session start port={ser.port} baud={ser.baudrate} "
                f"at {datetime.now().isoformat(timespec='seconds')} ---")
    try:
        while end_time is None or time.monotonic() < end_time:
            waiting = ser.in_waiting
            if waiting:
                data = ser.read(waiting)
                if data:
                    total_bytes += len(data)
                    logger.info(format_rx(data))
            else:
                time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        logger.info("--- monitor interrupted by user ---")
    logger.info(f"--- monitor session end total_bytes_received={total_bytes} ---")
    return total_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous serial monitor for Fluke 54 II B")
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--duration", type=float, default=None,
                         help="Seconds to monitor; omit to run until Ctrl+C")
    parser.add_argument("--log-path", type=Path, default=LOG_PATH)
    args = parser.parse_args()

    logger = setup_logging(args.log_path)

    try:
        with serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2,
        ) as ser:
            total = monitor(ser, logger, args.duration)
    except SerialException as e:
        logger.info(f"OPEN_FAIL {type(e).__name__}: {e}")
        return 1

    return 0 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
