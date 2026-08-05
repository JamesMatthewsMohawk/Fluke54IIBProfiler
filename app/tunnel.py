"""Tunnel distance conversion: elapsed time -> distance through the tunnel.

distance (m) = belt_speed (m/s) * elapsed_time (s)
belt_speed (m/s) = belt_speed (m/min) / 60
"""
from __future__ import annotations

from dataclasses import dataclass

from fluke54.models import Reading

BELT_SPEEDS_M_PER_MIN: tuple[float, ...] = (22.0, 24.0)
DEFAULT_TUNNEL_LENGTH_M = 12.0


@dataclass(frozen=True)
class ProfilePoint:
    elapsed_time_s: float
    distance_m: float
    temperature_c: float


def belt_speed_m_per_s(belt_speed_m_per_min: float) -> float:
    return belt_speed_m_per_min / 60.0


def elapsed_time_to_distance(elapsed_time_s: float, belt_speed_m_per_min: float) -> float:
    return elapsed_time_s * belt_speed_m_per_s(belt_speed_m_per_min)


def build_profile(
    readings: list[Reading],
    belt_speed_m_per_min: float,
    sample_interval_s: float = 1.0,
) -> list[ProfilePoint]:
    """Convert a sequence of readings into (elapsed time, distance, temperature) points.

    Elapsed time is derived from each reading's position in the sequence
    (index * sample_interval_s) rather than the raw sequence field on
    Reading, since the sample interval is a value the user configures on
    the meter and we want the app's distance math to match that
    configuration explicitly rather than assume the raw counter's units.
    """
    points: list[ProfilePoint] = []
    for i, reading in enumerate(readings):
        elapsed = i * sample_interval_s
        distance = elapsed_time_to_distance(elapsed, belt_speed_m_per_min)
        points.append(ProfilePoint(
            elapsed_time_s=elapsed,
            distance_m=distance,
            temperature_c=reading.temperature_c,
        ))
    return points
