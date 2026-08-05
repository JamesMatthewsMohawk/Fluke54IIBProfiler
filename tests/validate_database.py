"""End-to-end validation: real meter download -> tunnel conversion -> SQLite.

Not a pytest suite -- run directly. Requires the meter in 'Ir SEnd' mode.
Uses a throwaway test database file, not the app's real one.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import database  # noqa: E402
from app.tunnel import build_profile  # noqa: E402
from fluke54 import FlukeMeter  # noqa: E402

TEST_DB_PATH = Path("logs") / "validate_database_test.db"


def main() -> int:
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEST_DB_PATH.unlink(missing_ok=True)

    conn = database.get_connection(TEST_DB_PATH)
    database.init_db(conn)

    tunnels = database.list_tunnels(conn)
    print(f"Tunnels seeded: {[t.name for t in tunnels]}")
    assert len(tunnels) == 6, f"expected 6 default tunnels, got {len(tunnels)}"

    print("\nConnecting to meter and downloading real log...")
    with FlukeMeter() as meter:
        session = meter.download_memory(index=1)
    print(f"Downloaded {len(session.readings)} real readings.")

    points = build_profile(session.readings, belt_speed_m_per_min=24.0, sample_interval_s=1.0)
    print(f"Built {len(points)} profile points. "
          f"First: {points[0]}  Last: {points[-1]}")

    tunnel_a = next(t for t in tunnels if t.name == "Superba A")
    run = database.create_run(conn, tunnel_id=tunnel_a.id, belt_speed_m_per_min=24.0, points=points)
    print(f"\nCreated run: id={run.id} tunnel={run.tunnel_name} "
          f"peak={run.peak_temp_c:.2f}C min={run.min_temp_c:.2f}C exit={run.exit_temp_c:.2f}C "
          f"count={run.measurement_count}")

    fetched_measurements = database.get_measurements(conn, run.id)
    assert len(fetched_measurements) == len(points), "measurement count mismatch after round-trip"
    print(f"Round-trip OK: {len(fetched_measurements)} measurements read back from DB.")

    recent_runs = database.list_runs(conn)
    print(f"\nRecent runs: {[(r.id, r.tunnel_name, r.measurement_count) for r in recent_runs]}")

    conn.close()
    print("\nAll database validation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
