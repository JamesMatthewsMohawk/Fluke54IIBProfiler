"""Temperature unit conversion for display.

Measurements are always stored in the database as Celsius (this is what
the parser's calibration formula produces, see fluke54/parser.py).
Fahrenheit is only ever a display-time conversion of that stored value.
"""
from __future__ import annotations


def celsius_to_fahrenheit(temp_c: float) -> float:
    return temp_c * 9.0 / 5.0 + 32.0


def convert_from_celsius(temp_c: float, unit: str) -> float:
    return celsius_to_fahrenheit(temp_c) if unit == "F" else temp_c
