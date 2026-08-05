"""Phase 2 diagnostic utility for the Fluke 54 II B / IRUSB serial link.

Makes no assumptions about the meter's protocol. Supports:
  - listening for idle/unsolicited traffic
  - transmitting an arbitrary manual command and capturing the response
  - falling back through common baud rates if 9600 yields nothing
  - hex + ASCII + timestamped logging to console and to a log file

Usage:
    python serial_diag.py listen --port COM3 --baud 9600 --duration 15
    python serial_diag.py listen --port COM3 --fallback-baud
    python serial_diag.py send --port COM3 --hex "1B 00" --response-window 5
    python serial_diag.py send --port COM3 --ascii "SEND\\r\\n" --response-window 5
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

COMMON_BAUD_RATES = [9600, 4800, 2400, 19200, 38400, 1200, 300]
# (bytesize, parity, stopbits) combos worth ruling out beyond plain 8-N-1
FRAMING_VARIANTS = [
    (serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
    (serial.SEVENBITS, serial.PARITY_EVEN, serial.STOPBITS_ONE),
    (serial.SEVENBITS, serial.PARITY_ODD, serial.STOPBITS_ONE),
]
DEFAULT_PORT = "COM3"
POLL_INTERVAL_S = 0.05


@dataclass
class SerialSettings:
    port: str
    baud: int
    bytesize: int = serial.EIGHTBITS
    parity: str = serial.PARITY_NONE
    stopbits: float = serial.STOPBITS_ONE
    timeout: float = 0.2


def setup_logging(log_dir: Path) -> tuple[logging.Logger, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"serial_diag_{datetime.now():%Y%m%d_%H%M%S}.log"

    logger = logging.getLogger("fluke_serial_diag")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s.%(msecs)03d %(message)s", datefmt="%H:%M:%S")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger, log_file


def open_port(settings: SerialSettings, dtr: bool | None = None, rts: bool | None = None) -> serial.Serial:
    ser = serial.Serial(
        port=settings.port,
        baudrate=settings.baud,
        bytesize=settings.bytesize,
        parity=settings.parity,
        stopbits=settings.stopbits,
        timeout=settings.timeout,
    )
    if dtr is not None:
        ser.dtr = dtr
    if rts is not None:
        ser.rts = rts
    return ser


def format_chunk(data: bytes) -> str:
    hex_str = " ".join(f"{b:02X}" for b in data)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    return f"[{len(data):3d} bytes] HEX: {hex_str}  ASCII: {ascii_str!r}"


def listen(ser: serial.Serial, duration_s: float, logger: logging.Logger) -> int:
    logger.info(f"LISTEN start port={ser.port} baud={ser.baudrate} duration={duration_s}s")
    end_time = time.monotonic() + duration_s
    total_bytes = 0
    while time.monotonic() < end_time:
        waiting = ser.in_waiting
        if waiting:
            data = ser.read(waiting)
            if data:
                total_bytes += len(data)
                logger.info(format_chunk(data))
        else:
            time.sleep(POLL_INTERVAL_S)
    logger.info(f"LISTEN end total_bytes_received={total_bytes}")
    return total_bytes


def send_and_capture(
    ser: serial.Serial, payload: bytes, response_window_s: float, logger: logging.Logger
) -> int:
    logger.info(f"SEND {format_chunk(payload)}")
    ser.write(payload)
    ser.flush()
    return listen(ser, response_window_s, logger)


def parse_hex_string(hex_str: str) -> bytes:
    cleaned = hex_str.replace("0x", "").replace(",", " ")
    parts = cleaned.split()
    return bytes(int(p, 16) for p in parts)


def run_baud_fallback(port: str, duration_s: float, logger: logging.Logger) -> int | None:
    for baud in COMMON_BAUD_RATES:
        logger.info(f"FALLBACK trying baud={baud}")
        settings = SerialSettings(port=port, baud=baud)
        try:
            with open_port(settings) as ser:
                received = listen(ser, duration_s, logger)
                if received > 0:
                    logger.info(f"FALLBACK baud={baud} produced {received} bytes -- candidate match")
                    return baud
        except SerialException as e:
            logger.error(f"FALLBACK baud={baud} OPEN_FAIL {type(e).__name__}: {e}")
    logger.warning("FALLBACK exhausted all common baud rates with no data received")
    return None


def cmd_listen(args: argparse.Namespace, logger: logging.Logger) -> None:
    settings = SerialSettings(port=args.port, baud=args.baud)
    try:
        with open_port(settings, dtr=args.dtr, rts=args.rts) as ser:
            logger.info(f"OPEN_OK {settings} dtr={ser.dtr} rts={ser.rts} cts={ser.cts} dsr={ser.dsr}")
            received = listen(ser, args.duration, logger)
    except SerialException as e:
        logger.error(f"OPEN_FAIL {type(e).__name__}: {e}")
        return

    if received == 0 and args.fallback_baud:
        logger.info("No data at requested baud; starting common-baud-rate fallback sweep")
        match = run_baud_fallback(args.port, args.fallback_duration, logger)
        if match:
            logger.info(f"RESULT possible working baud rate: {match}")
        else:
            logger.info("RESULT no baud rate in the common set produced traffic")


def cmd_sweep(args: argparse.Namespace, logger: logging.Logger) -> None:
    logger.info(f"SWEEP start port={args.port} bauds={COMMON_BAUD_RATES} framings={FRAMING_VARIANTS}")
    for bytesize, parity, stopbits in FRAMING_VARIANTS:
        for baud in COMMON_BAUD_RATES:
            settings = SerialSettings(
                port=args.port, baud=baud, bytesize=bytesize, parity=parity, stopbits=stopbits
            )
            logger.info(f"SWEEP trying baud={baud} bytesize={bytesize} parity={parity} stopbits={stopbits}")
            try:
                with open_port(settings, dtr=True, rts=True) as ser:
                    received = listen(ser, args.per_combo_duration, logger)
                    if received > 0:
                        logger.info(f"SWEEP MATCH baud={baud} bytesize={bytesize} parity={parity} "
                                    f"stopbits={stopbits} -- {received} bytes received")
            except SerialException as e:
                logger.error(f"SWEEP OPEN_FAIL baud={baud}: {type(e).__name__}: {e}")
    logger.info("SWEEP end")


def cmd_send(args: argparse.Namespace, logger: logging.Logger) -> None:
    if args.hex:
        payload = parse_hex_string(args.hex)
    elif args.ascii is not None:
        payload = args.ascii.encode("ascii")
    else:
        logger.error("send requires --hex or --ascii")
        return

    settings = SerialSettings(port=args.port, baud=args.baud)
    try:
        with open_port(settings) as ser:
            logger.info(f"OPEN_OK {settings}")
            send_and_capture(ser, payload, args.response_window, logger)
    except SerialException as e:
        logger.error(f"OPEN_FAIL {type(e).__name__}: {e}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fluke 54 II B serial diagnostic utility")
    parser.add_argument("--log-dir", default="logs", type=Path)
    sub = parser.add_subparsers(dest="mode", required=True)

    listen_p = sub.add_parser("listen", help="Passively listen for traffic")
    listen_p.add_argument("--port", default=DEFAULT_PORT)
    listen_p.add_argument("--baud", type=int, default=9600)
    listen_p.add_argument("--duration", type=float, default=15.0)
    listen_p.add_argument("--fallback-baud", action="store_true",
                           help="If no data received, sweep common baud rates")
    listen_p.add_argument("--fallback-duration", type=float, default=5.0)
    listen_p.add_argument("--dtr", action=argparse.BooleanOptionalAction, default=None,
                           help="Explicitly assert/deassert DTR line (default: platform default)")
    listen_p.add_argument("--rts", action=argparse.BooleanOptionalAction, default=None,
                           help="Explicitly assert/deassert RTS line (default: platform default)")
    listen_p.set_defaults(func=cmd_listen)

    send_p = sub.add_parser("send", help="Transmit a manual command and capture the response")
    send_p.add_argument("--port", default=DEFAULT_PORT)
    send_p.add_argument("--baud", type=int, default=9600)
    send_p.add_argument("--hex", help='Space-separated hex bytes, e.g. "1B 00 0D"')
    send_p.add_argument("--ascii", help="ASCII/text command to send")
    send_p.add_argument("--response-window", type=float, default=5.0)
    send_p.set_defaults(func=cmd_send)

    sweep_p = sub.add_parser("sweep", help="Sweep baud rates and framing variants")
    sweep_p.add_argument("--port", default=DEFAULT_PORT)
    sweep_p.add_argument("--per-combo-duration", type=float, default=2.5)
    sweep_p.set_defaults(func=cmd_sweep)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logger, log_file = setup_logging(args.log_dir)
    logger.info(f"=== Fluke serial diagnostic session start (log: {log_file}) ===")
    try:
        args.func(args, logger)
    finally:
        logger.info("=== session end ===")


if __name__ == "__main__":
    main()
