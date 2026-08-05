"""Manual validation of the fluke54 library against the real meter.

Not a pytest suite -- run directly. Requires the meter in 'Ir SEnd' mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fluke54 import FlukeMeter  # noqa: E402


def main() -> int:
    print("Connecting...")
    with FlukeMeter() as meter:
        info = meter.meter_info()
        print(f"Meter info: model={info.model!r} firmware={info.firmware_version!r}")

        print("Downloading log at index 1...")
        session = meter.download_memory(index=1)
        print(f"Sample count (incl. header block): {session.sample_count}")
        print(f"Parsed readings: {len(session.readings)}")
        if session.readings:
            for r in session.readings:
                print(f"  seq={r.sequence} temp_f={r.temperature_f:.2f} temp_c={r.temperature_c:.3f}")
            temps_c = [r.temperature_c for r in session.readings]
            print(f"Min/Max/Avg (C): {min(temps_c):.3f} / {max(temps_c):.3f} / "
                  f"{sum(temps_c)/len(temps_c):.3f}")

    print("Disconnected cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
