"""Data models for the Fluke 54 II B communication library."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MeterInfo:
    """Result of the ID command."""
    model: str
    firmware_version: str
    raw_identify_string: str


@dataclass(frozen=True)
class Reading:
    """A single logged temperature sample.

    temperature_c is derived from the raw 16-bit log value via an empirically
    fit calibration (see parser.RAW_TO_CELSIUS_SLOPE / _INTERCEPT) -- NOT a
    simple /100 Fahrenheit encoding, which was an earlier, incorrect
    assumption disproven by comparing decoded values against precise manual
    meter readings during a rapid temperature change.
    """
    sequence: int
    temperature_c: float

    @property
    def temperature_f(self) -> float:
        return self.temperature_c * 9.0 / 5.0 + 32.0


@dataclass(frozen=True)
class LogSession:
    """A full downloaded log (one QD <index> response)."""
    index: int
    sample_count: int
    readings: list[Reading] = field(default_factory=list)
