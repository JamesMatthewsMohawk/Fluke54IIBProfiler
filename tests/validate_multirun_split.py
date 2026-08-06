"""Regression check for run-boundary splitting, against a real captured
two-run log (Tunnel 8 then Tunnel 9, ~60s each, no download in between).
Doesn't need the meter -- fixtures/qd1_two_runs_raw.bin is the raw QD 1
response bytes captured from it. Not a pytest suite -- run directly."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fluke54.parser import parse_qd  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "qd1_two_runs_raw.bin"


def main() -> int:
    session = parse_qd(FIXTURE.read_bytes())
    print(f"sample_count={session.sample_count} readings={len(session.readings)} "
          f"run_starts={session.run_starts}")

    assert session.run_starts == [0, 61], f"expected a boundary at reading 61, got {session.run_starts}"

    runs = session.split_runs()
    assert len(runs) == 2, f"expected 2 runs, got {len(runs)}"
    assert all(len(run) == 61 for run in runs), [len(run) for run in runs]

    # The marker block itself must never show up as a reading.
    all_temps = [r.temperature_c for run in runs for r in run]
    assert all(t > -100 for t in all_temps), "a marker block's impossible temperature leaked into readings"

    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
