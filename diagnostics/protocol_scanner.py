"""Phase 4 automated protocol scanner for the Fluke 54 II B.

Extends the Phase 3 handshake discovery (fluke_probe.py) with a broader set of
read-only candidate commands, looking specifically for memory-count, log-count,
record-download, and timestamp-related queries.

Confirmed wire format (see fluke_probe.py results):
    command + '\\r'  ->  '<status>\\r[<data>\\r]'   (0 = OK, 1 = error/unrecognized)

Safety: every candidate here is a read/query-style command. Nothing in this
list writes, clears, resets, or deletes meter data or settings.
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
INTER_COMMAND_DELAY_S = 0.4
LOG_PATH = Path("logs") / "protocol_scanner.log"

# label -> raw bytes. All are read/query candidates; no write/clear/reset/delete verbs.
CANDIDATE_COMMANDS: list[tuple[str, bytes]] = [
    # already-known-good baseline, kept for regression reference
    ("ID", b"ID\r"),

    # two/three letter query abbreviations: memory / log / record / count themed
    ("MC", b"MC\r"),
    ("LC", b"LC\r"),
    ("NR", b"NR\r"),
    ("RC", b"RC\r"),
    ("DL", b"DL\r"),
    ("RD", b"RD\r"),
    ("GD", b"GD\r"),
    ("GM", b"GM\r"),
    ("GL", b"GL\r"),
    ("RL", b"RL\r"),
    ("QL", b"QL\r"),
    ("QD", b"QD\r"),
    ("QN", b"QN\r"),
    ("QC", b"QC\r"),
    ("QR", b"QR\r"),
    ("QT", b"QT\r"),
    ("MEM", b"MEM\r"),
    ("LOG", b"LOG\r"),
    ("CNT", b"CNT\r"),
    ("NUM", b"NUM\r"),
    ("REC", b"REC\r"),
    ("DATA", b"DATA\r"),
    ("READ", b"READ\r"),
    ("DUMP", b"DUMP\r"),
    ("STAT", b"STAT\r"),
    ("STATUS", b"STATUS\r"),
    ("INFO", b"INFO\r"),
    ("VER", b"VER\r"),
    ("REV", b"REV\r"),
    ("TIME", b"TIME\r"),
    ("DATE", b"DATE\r"),
    ("CLK", b"CLK\r"),

    # single-letter candidates
    ("M", b"M\r"),
    ("L", b"L\r"),
    ("D", b"D\r"),
    ("N", b"N\r"),
    ("C", b"C\r"),
    ("R", b"R\r"),
    ("S", b"S\r"),
    ("V", b"V\r"),
    ("T", b"T\r"),

    # common generic serial query patterns (harmless even if unsupported)
    ("SCPI *IDN?", b"*IDN?\r"),
    ("empty CR", b"\r"),

    # single control-byte probes
    ("ENQ 0x05", b"\x05"),
    ("ACK 0x06", b"\x06"),
    ("STX 0x02", b"\x02"),
]


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("protocol_scanner")
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


def scan_one(ser: serial.Serial, logger: logging.Logger, label: str, payload: bytes) -> bytes:
    ts = datetime.now().isoformat(timespec="milliseconds")
    ser.reset_input_buffer()
    ser.write(payload)
    ser.flush()
    response = read_available(ser, RESPONSE_WINDOW_S)

    logger.info(
        f"Command Sent: {label}\nHEX: {hex_dump(payload)}\n"
        f"Response:\nHEX: {hex_dump(response)}\nASCII: {ascii_dump(response)!r}\n"
        f"Timestamp: {ts}\n"
    )
    return response


def main() -> int:
    logger = setup_logging(LOG_PATH)
    logger.info(f"=== protocol_scanner session start {datetime.now().isoformat(timespec='seconds')} "
                f"({len(CANDIDATE_COMMANDS)} candidates) ===")
    logger.info("Meter must be showing 'Ir SEnd' (SHIFT + RECALL); re-trigger if it times out mid-scan.")

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
    except SerialException as e:
        logger.info(f"OPEN_FAIL {type(e).__name__}: {e}")
        return 1

    hits: list[tuple[str, bytes]] = []
    try:
        with ser:
            for label, payload in CANDIDATE_COMMANDS:
                response = scan_one(ser, logger, label, payload)
                if response and response != b"1\r":
                    hits.append((label, response))
                time.sleep(INTER_COMMAND_DELAY_S)
    finally:
        logger.info(f"=== protocol_scanner session end ===")
        logger.info(f"Candidates producing a non-error / non-empty response ({len(hits)}):")
        for label, response in hits:
            logger.info(f"  {label}: HEX {hex_dump(response)} ASCII {ascii_dump(response)!r}")

    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
