"""Probe how the meter exposes more than one logged session.

Existing code only ever reads QD 1 (see fluke54/meter.py -- "Index 1 has
empirically held the full sample log in every test so far"), but that was
only ever verified with a single logged session on the meter. This script
answers the open question: if you log two separate runs on the meter
before ever connecting to the app (e.g. Tunnel 8, then Tunnel 9, with no
download or memory-clear in between), does each show up at its own QD
index, does one overwrite the other, or does QD 1 return both concatenated?

Usage:
    1. On the meter: log Tunnel 8, stop. Log Tunnel 9, stop. Do NOT clear
       memory or download in between.
    2. Connect the IRUSB cable, put the meter in "Ir SEnd" mode
       (SHIFT + RECALL).
    3. Run this script. It uses the same FlukeMeter/parse_qd code the app
       does, so its results reflect real app behavior, not a guess.
    4. Share the printed output (also written to logs/qd_multi_session_scan.log)
       back for interpretation.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fluke54 import FlukeMeter  # noqa: E402
from fluke54.parser import FlukeParseError  # noqa: E402
from fluke54.protocol import FlukeCommandRejected, FlukeMalformedResponse, FlukeNoResponse  # noqa: E402

MAX_INDEX = 10
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "qd_multi_session_scan.log"


def describe(session) -> str:
    if not session.readings:
        return f"sample_count={session.sample_count}, 0 usable readings"
    temps = [r.temperature_c for r in session.readings]
    seqs = [r.sequence for r in session.readings]
    return (
        f"sample_count={session.sample_count}, {len(session.readings)} readings, "
        f"seq {seqs[0]}..{seqs[-1]}, temp {min(temps):.1f}..{max(temps):.1f}C "
        f"(first {temps[0]:.1f}C, last {temps[-1]:.1f}C)"
    )


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"=== qd_multi_session_scan start {datetime.now().isoformat(timespec='seconds')} ==="]

    try:
        with FlukeMeter() as meter:
            lines.append(f"Connected: {meter.meter_info()}")
            for idx in range(MAX_INDEX + 1):
                try:
                    session = meter.download_memory(index=idx)
                    line = f"QD {idx}: OK -- {describe(session)}"
                except FlukeCommandRejected:
                    line = f"QD {idx}: REJECTED (no data at this index)"
                except FlukeNoResponse:
                    line = f"QD {idx}: NO RESPONSE"
                except FlukeMalformedResponse as e:
                    line = f"QD {idx}: MALFORMED -- {e}"
                except FlukeParseError as e:
                    line = f"QD {idx}: PARSE ERROR (likely a non-log-data response, e.g. index 0's summary) -- {e}"
                print(line)
                lines.append(line)
    except Exception as e:  # noqa: BLE001 -- report any connection failure plainly
        line = f"FAILED to connect: {type(e).__name__}: {e}"
        print(line)
        lines.append(line)
        LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
        return 1

    lines.append("=== qd_multi_session_scan end ===")
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nFull log written to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
