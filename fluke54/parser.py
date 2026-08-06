"""Parsers for Fluke 54 II B response payloads.

QD <index> payload structure (reverse-engineered empirically, see
project memory for the full derivation):

    [sample_count: uint16 LE]
    [block_0: 8 bytes -- metadata/header block, not a temperature reading]
    [block_1 .. block_{sample_count-1}: 8 bytes each -- temperature readings,
     OR a run-boundary marker block, see below]
    [checksum: 1 byte -- additive sum (mod 256) of all bytes from block_0
     onward, i.e. excluding the leading sample_count field]

Each 8-byte reading block: `FF FF <temp_raw: uint16 LE> <sequence: uint16 LE,
+1 per sample> 01 00`.

If the meter logged more than one run (started/stopped RECALL logging
more than once) without a memory clear or download in between, all of
them come back concatenated in a single QD response, with one
run-boundary marker block between each pair of runs: `00 00 00 00 <2
bytes, unknown> <2 bytes, unknown>` -- i.e. the same 8-byte shape as a
reading block, but tagged `00 00` where a real reading is always tagged
`FF FF`. Confirmed empirically against a real two-run log (Tunnel 8,
then Tunnel 9, ~60s each, no download in between): the marker's own
would-be "temp_raw" field decodes to 0 (an impossible temperature) and
its would-be "sequence" field is unrelated to the surrounding readings'
sequence numbers, consistent with it being a distinct record type we
haven't fully decoded rather than a corrupt/glitched reading. Each run's
own readings still increment their sequence field by exactly +1 per
sample; only the base value differs from one run to the next.

temp_raw -> degrees Celsius via an empirically fit linear calibration:

    temperature_c = temp_raw * RAW_TO_CELSIUS_SLOPE + RAW_TO_CELSIUS_INTERCEPT

This was derived by comparing decoded values against precise manual
readings taken directly off the meter's RECALL display during a rapid
temperature change (needed because a slow/stable test log can't distinguish
between a correct scale and a merely-close one -- an earlier assumption,
temp_raw/100 interpreted as degrees Fahrenheit, matched a stable-temperature
test to within ~0.9C but was off by up to 6C during a fast temperature
ramp, revealing it was the wrong formula despite looking plausible).

The fitted constants are close to `temp_raw / 27 - 273.15` -- notably,
273.15 is exactly the Celsius/Kelvin offset, suggesting temp_raw is an
internal fixed-point Kelvin-scaled ADC value. The empirical fit is used
here rather than that clean approximation since it matches the precise
ground-truth readings more exactly (max error ~0.03C vs ~0.05C).
"""
from __future__ import annotations

import struct

from .logger import get_logger
from .models import LogSession, MeterInfo, Reading

logger = get_logger(__name__)

ID_DATA_TERMINATOR = b"\r"
QD_PREFIX = b"QD,"
READING_TAG = b"\xff\xff"
RUN_BOUNDARY_TAG = b"\x00\x00"

# Empirically fit via linear regression against 6 precise manual meter
# readings taken during a rapid temperature ramp (raw values 8154-8303
# against ground truth 28.9-34.4C). See module docstring.
RAW_TO_CELSIUS_SLOPE = 0.037171
RAW_TO_CELSIUS_INTERCEPT = -274.2066


class FlukeParseError(Exception):
    """Raised when a meter response can't be parsed as expected."""


def parse_id(data: bytes) -> MeterInfo:
    """Parse the data portion of an ID response.

    `data` is the raw bytes following the '0\\r' status prefix, e.g.
    b'FLUKE 54-II, V1.5\\r'.
    """
    text = data.rstrip(ID_DATA_TERMINATOR).decode("ascii", errors="replace")
    if not text.upper().startswith("FLUKE"):
        raise FlukeParseError(f"Unexpected ID response (doesn't start with FLUKE): {text!r}")

    parts = text.split(",", 1)
    model = parts[0].strip()
    version = parts[1].strip() if len(parts) > 1 else ""
    return MeterInfo(model=model, firmware_version=version, raw_identify_string=text)


def parse_qd(data: bytes) -> LogSession:
    """Parse the data portion of a QD <index> response.

    `data` is the raw bytes following the '0\\r' status prefix, e.g.
    b'QD,<binary payload>'.
    """
    if not data.startswith(QD_PREFIX):
        raise FlukeParseError(f"QD response missing expected 'QD,' prefix: {data[:16]!r}...")

    payload = data[len(QD_PREFIX):]
    if len(payload) < 3:
        raise FlukeParseError(f"QD payload too short: {len(payload)} bytes")

    sample_count = struct.unpack_from("<H", payload, 0)[0]
    expected_len = 2 + sample_count * 8 + 1
    if len(payload) != expected_len:
        raise FlukeParseError(
            f"QD payload length mismatch: expected {expected_len} bytes for "
            f"sample_count={sample_count}, got {len(payload)}"
        )

    checksum_expected = payload[-1]
    # Checksum covers the reading blocks only, not the leading sample_count field.
    checksum_actual = sum(payload[2:-1]) & 0xFF
    if checksum_actual != checksum_expected:
        logger.warning(
            "QD checksum mismatch: expected 0x%02X, computed 0x%02X -- data may be corrupt",
            checksum_expected, checksum_actual,
        )

    readings: list[Reading] = []
    run_starts = [0]
    # block_0 (right after the count field) is a metadata/header block, not a
    # reading -- real readings start at block_1.
    for i in range(1, sample_count):
        offset = 2 + i * 8
        block = payload[offset:offset + 8]
        tag = block[:2]

        if tag == READING_TAG:
            temp_raw = struct.unpack_from("<H", block, 2)[0]
            seq = struct.unpack_from("<H", block, 4)[0]
            temp_c = temp_raw * RAW_TO_CELSIUS_SLOPE + RAW_TO_CELSIUS_INTERCEPT
            readings.append(Reading(sequence=seq, temperature_c=temp_c))
        elif tag == RUN_BOUNDARY_TAG:
            # Not a reading -- marks that the next one starts a new logged
            # run. Dropped from `readings`; recorded as a split point instead.
            if readings and run_starts[-1] != len(readings):
                run_starts.append(len(readings))
        else:
            logger.warning("Unrecognized block tag %s at block %d -- skipping", tag.hex(), i)

    return LogSession(index=-1, sample_count=sample_count, readings=readings, run_starts=run_starts)
