"""Low-level command/response protocol for the Fluke 54 II B.

Confirmed empirically (see project memory / diagnostics/ for the full
reverse-engineering history):
    - Command format: ASCII text + '\\r'.
    - Response format: '<status>\\r[<data>]' where status is '0' (OK) or
      '1' (error/unrecognized). Data, when present, is NOT reliably
      terminated by '\\r' for binary-payload commands (e.g. QD), so
      responses must be read with a quiet-period cutoff, not a fixed
      terminator.
    - The meter only responds while in "Ir SEnd" mode (SHIFT + RECALL on
      the meter). In normal display mode it is completely silent.
    - The parser reads only the first 2 characters of any command; longer
      command names collapse onto their 2-character prefix.

Known dangerous commands -- NEVER send these:
    - CD: undocumented, empirically caused the meter's logged memory to be
      cleared during protocol discovery.
    - RI: documented factory reset (clears all logged memory).
    - DS: documented as a settings reset / power-cycle equivalent. Confirmed
      empirically NOT to clear logged memory, but still excluded from the
      general-purpose command sender below as a precaution -- send it only
      via an explicit, deliberate call if ever needed.
"""
from __future__ import annotations

import time

import serial

STATUS_OK = "0"
STATUS_ERROR = "1"

DANGEROUS_COMMANDS = {"CD", "RI", "DS"}

DEFAULT_MAX_WINDOW_S = 5.0
DEFAULT_QUIET_CUTOFF_S = 1.5


class FlukeProtocolError(Exception):
    """Base class for Fluke 54 II B protocol errors."""


class FlukeCommandRejected(FlukeProtocolError):
    """The meter responded with an error status ('1') to a command."""

    def __init__(self, command: str):
        super().__init__(f"Meter rejected command {command!r} (status '1')")
        self.command = command


class FlukeNoResponse(FlukeProtocolError):
    """The meter did not respond at all -- likely not in 'Ir SEnd' mode."""

    def __init__(self, command: str):
        super().__init__(
            f"No response to {command!r}. Meter may not be in 'Ir SEnd' mode "
            f"(SHIFT + RECALL on the meter) or the cable may be misaligned."
        )
        self.command = command


class FlukeMalformedResponse(FlukeProtocolError):
    """The response didn't start with a recognized status byte."""


def _read_until_quiet(
    ser: serial.Serial,
    max_window_s: float = DEFAULT_MAX_WINDOW_S,
    quiet_cutoff_s: float = DEFAULT_QUIET_CUTOFF_S,
) -> bytes:
    end_time = time.monotonic() + max_window_s
    buf = bytearray()
    last_growth = time.monotonic()
    while time.monotonic() < end_time:
        waiting = ser.in_waiting
        if waiting:
            buf.extend(ser.read(waiting))
            last_growth = time.monotonic()
        else:
            time.sleep(0.02)
        if buf and (time.monotonic() - last_growth) > quiet_cutoff_s:
            break
    return bytes(buf)


def send_command(
    ser: serial.Serial,
    command: str,
    max_window_s: float = DEFAULT_MAX_WINDOW_S,
    quiet_cutoff_s: float = DEFAULT_QUIET_CUTOFF_S,
) -> bytes:
    """Send a command and return the raw data following the status prefix.

    Raises FlukeNoResponse if the meter is silent, FlukeCommandRejected if
    the meter returns status '1', FlukeMalformedResponse if the response
    doesn't start with a recognized status byte.
    """
    prefix = command.split(" ", 1)[0].upper()
    if prefix in DANGEROUS_COMMANDS:
        raise ValueError(
            f"Refusing to send {command!r}: {prefix} is excluded as a known-dangerous "
            f"command. Call it explicitly via a dedicated function if truly intended."
        )

    payload = (command + "\r").encode("ascii")
    ser.reset_input_buffer()
    ser.write(payload)
    ser.flush()

    response = _read_until_quiet(ser, max_window_s, quiet_cutoff_s)
    if not response:
        raise FlukeNoResponse(command)

    if len(response) < 2 or response[1:2] != b"\r":
        raise FlukeMalformedResponse(f"Unexpected response to {command!r}: {response!r}")

    status = chr(response[0])
    data = response[2:]

    if status == STATUS_ERROR:
        raise FlukeCommandRejected(command)
    if status != STATUS_OK:
        raise FlukeMalformedResponse(f"Unknown status {status!r} for {command!r}: {response!r}")

    return data
