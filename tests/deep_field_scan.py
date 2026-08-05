"""Download the log fresh and dump every possible numeric interpretation of
each 8-byte reading block, for the first several samples, to search for a
field matching precisely-read ground-truth values."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fluke54.connection import FlukeConnection  # noqa: E402
from fluke54.protocol import send_command  # noqa: E402

GROUND_TRUTH_C = [28.9, 28.9, 28.9, 31.9, 33.9, 34.4]


def main() -> int:
    conn = FlukeConnection()
    conn.open()
    try:
        data = send_command(conn.serial, "ID")
        print(f"ID: {data!r}")

        data = send_command(conn.serial, "QD 1", max_window_s=10.0, quiet_cutoff_s=2.0)
        assert data.startswith(b"QD,")
        payload = data[3:]
        count = struct.unpack_from("<H", payload, 0)[0]
        print(f"payload length: {len(payload)} bytes, sample_count field: {count}")
        expected_len = 2 + count * 8 + 1
        print(f"expected length: {expected_len} -- {'MATCH' if len(payload) == expected_len else 'MISMATCH'}")
    finally:
        conn.close()

    print("\nDumping first 8 blocks (block_0 = header, block_1.. = readings):")
    for i in range(min(8, count)):
        offset = 2 + i * 8
        block = payload[offset:offset + 8]
        print(f"\nblock_{i} raw: {block.hex(' ')}")
        for j in range(len(block) - 1):
            u16 = struct.unpack_from('<H', block, j)[0]
            print(f"  off={j} u16={u16:6d} /100={u16/100:8.3f} /10={u16/10:8.2f} "
                  f"as_F->C={((u16/100)-32)*5/9:8.3f}")

    print(f"\nGround truth (mem1-6, degrees C): {GROUND_TRUTH_C}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
