"""Converts raw meter readings into elapsed-time/temperature profile points."""
from __future__ import annotations

from dataclasses import dataclass

from fluke54.models import Reading


@dataclass(frozen=True)
class ProfilePoint:
    elapsed_time_s: float
    temperature_c: float


def build_profile(readings: list[Reading], sample_interval_s: float = 1.0) -> list[ProfilePoint]:
    """Convert a sequence of readings into (elapsed time, temperature) points.

    Elapsed time is derived from each reading's position in the sequence
    (index * sample_interval_s) rather than the raw sequence field on
    Reading, since the sample interval is a value the user configures on
    the meter and we want the app's timing to match that configuration
    explicitly rather than assume the raw counter's units.
    """
    return [
        ProfilePoint(elapsed_time_s=i * sample_interval_s, temperature_c=reading.temperature_c)
        for i, reading in enumerate(readings)
    ]
