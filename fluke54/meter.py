"""High-level API for talking to a Fluke 54 II B thermometer.

IMPORTANT: the meter only responds while showing "Ir SEnd" on its display
(entered via SHIFT + RECALL). There is no way to trigger this remotely --
the user must press it on the meter before any of these calls will succeed.
"""
from __future__ import annotations

from .connection import FlukeConnection
from .logger import get_logger
from .models import LogSession, MeterInfo
from .parser import parse_id, parse_qd
from .protocol import FlukeCommandRejected, FlukeNoResponse, send_command

logger = get_logger(__name__)


class FlukeMeter:
    """High-level, read-only interface to a Fluke 54 II B.

    Only operations empirically confirmed safe and working are exposed.
    `read_live()` and `clear_memory()` are intentionally NOT implemented --
    see their docstrings for why.
    """

    def __init__(self, port: str | None = None):
        self._connection = FlukeConnection(port)

    def connect(self) -> MeterInfo:
        """Open the serial connection and verify the meter responds to ID.

        Raises FlukeConnectionError if the port can't be opened, or
        FlukeNoResponse if the meter doesn't answer (most commonly because
        it isn't in "Ir SEnd" mode).
        """
        self._connection.open()
        try:
            info = self.meter_info()
        except Exception:
            self._connection.close()
            raise
        logger.info("Connected: %s", info)
        return info

    def disconnect(self) -> None:
        self._connection.close()

    @property
    def is_connected(self) -> bool:
        return self._connection.is_open

    def meter_info(self) -> MeterInfo:
        """Send ID and return the meter's model/firmware info."""
        data = send_command(self._connection.serial, "ID")
        return parse_id(data)

    def download_memory(self, index: int = 1) -> LogSession:
        """Download a logged session via QD <index>.

        Index 1 has empirically held the full sample log in every test so
        far; index 0 returns a small, different-shaped response believed to
        be an internal status/summary value, not log data. The valid index
        range is meter-state-dependent (it reflects what's currently
        logged), so callers should be prepared for FlukeCommandRejected if
        the requested index doesn't currently hold data.
        """
        data = send_command(
            self._connection.serial, f"QD {index}",
            max_window_s=10.0, quiet_cutoff_s=2.0,
        )
        session = parse_qd(data)
        return LogSession(index=index, sample_count=session.sample_count, readings=session.readings)

    def read_live(self) -> None:
        """Not supported.

        The documented live-reading command for this Fluke product family
        (QM) was tested extensively against this specific meter (bare,
        with arguments, after DS, after ID, with inter-character delays)
        and always rejected. No working live-reading command was found.
        """
        raise NotImplementedError(
            "read_live() is not supported: this meter rejects QM (the documented "
            "live-measurement query) in every tested configuration. No working "
            "alternative was found during protocol discovery."
        )

    def clear_memory(self) -> None:
        """Not supported, deliberately.

        RI (Reset Instrument) is documented to factory-reset the meter and
        clear all logged memory -- far more than "clear the log." CD is an
        undocumented command that was empirically observed to clear the
        meter's logged memory during protocol discovery, with unknown side
        effects otherwise. Neither is safe to expose as a casual "clear
        memory" action, so this is intentionally left unimplemented rather
        than wired to either command.
        """
        raise NotImplementedError(
            "clear_memory() is deliberately not implemented -- the only known "
            "commands that clear memory (RI, CD) are a full factory reset or an "
            "undocumented command with unverified side effects. Clear memory "
            "manually on the meter instead."
        )

    def __enter__(self) -> "FlukeMeter":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
