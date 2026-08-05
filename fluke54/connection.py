"""Serial connection management for the Fluke 54 II B / IRUSB cable."""
from __future__ import annotations

from types import TracebackType

import serial
import serial.tools.list_ports as list_ports
from serial import SerialException

from .logger import get_logger

logger = get_logger(__name__)

BAUD_RATE = 9600
FTDI_VID_PID = ("0403", "6001")  # Fluke IRUSB Rev II cable's FTDI chip


class FlukeConnectionError(Exception):
    """Raised when the IRUSB cable / COM port can't be opened."""


def find_fluke_port() -> str | None:
    """Auto-detect the Fluke IRUSB cable's COM port by FTDI VID:PID.

    Returns None if no matching device is found (caller should fall back
    to an explicit port name).
    """
    vid, pid = FTDI_VID_PID
    for port in list_ports.comports():
        hwid_upper = port.hwid.upper()
        if f"VID:PID={vid.upper()}:{pid.upper()}" in hwid_upper or (
            f"VID_{vid.upper()}" in hwid_upper and f"PID_{pid.upper()}" in hwid_upper
        ):
            logger.info("Auto-detected Fluke IRUSB cable at %s (%s)", port.device, port.hwid)
            return port.device
    return None


class FlukeConnection:
    """Owns the serial.Serial handle to the Fluke 54 II B's IRUSB cable."""

    def __init__(self, port: str | None = None):
        self._requested_port = port
        self._serial: serial.Serial | None = None

    @property
    def port(self) -> str:
        if self._serial is None:
            raise FlukeConnectionError("Not connected")
        return self._serial.port

    @property
    def serial(self) -> serial.Serial:
        if self._serial is None:
            raise FlukeConnectionError("Not connected")
        return self._serial

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def open(self) -> None:
        port = self._requested_port or find_fluke_port()
        if port is None:
            raise FlukeConnectionError(
                "Could not auto-detect the Fluke IRUSB cable (FTDI VID 0403:6001) "
                "and no explicit port was given."
            )
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=BAUD_RATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.2,
            )
        except SerialException as e:
            raise FlukeConnectionError(f"Failed to open {port}: {e}") from e
        logger.info("Opened connection to %s at %d baud", port, BAUD_RATE)

    def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
            logger.info("Closed connection to %s", self._serial.port)
        self._serial = None

    def __enter__(self) -> "FlukeConnection":
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
