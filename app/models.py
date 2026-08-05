"""Data models for the Superba Tunnel Profiler application (database rows)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Run:
    id: int
    plant: str
    tunnel: str
    run_date: str  # ISO 8601
    peak_temp_c: float
    min_temp_c: float
    measurement_count: int
    source_unit: str = "C"  # what the meter displayed at log time ('C' or 'F')


@dataclass(frozen=True)
class Measurement:
    id: int
    run_id: int
    elapsed_time_s: float
    temperature_c: float
