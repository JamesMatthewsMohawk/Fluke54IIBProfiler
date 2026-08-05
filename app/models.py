"""Data models for the Superba Tunnel Profiler application (database rows)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tunnel:
    id: int
    name: str
    length_m: float


@dataclass(frozen=True)
class Run:
    id: int
    tunnel_id: int
    tunnel_name: str
    run_date: str  # ISO 8601
    belt_speed_m_per_min: float
    peak_temp_c: float
    min_temp_c: float
    exit_temp_c: float
    measurement_count: int


@dataclass(frozen=True)
class Measurement:
    id: int
    run_id: int
    elapsed_time_s: float
    distance_m: float
    temperature_c: float
