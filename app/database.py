"""SQLite persistence layer for the Superba Tunnel Profiler.

Schema:
    runs(id, plant, tunnel, run_date,
         peak_temp_c, min_temp_c, measurement_count, source_unit)
    measurements(id, run_id, elapsed_time_s, temperature_c)

`plant` and `tunnel` are free-text (not a fixed lookup list) since tunnels
aren't consistently named/numbered across plants.

`source_unit` ('C' or 'F') records what the meter's display was set to
when a log was recorded. It is user-supplied at download time (there is
no known command to query it from the meter) and is *not* used to
convert temperature_c -- the parser's calibration always produces
Celsius regardless. It exists so that if the meter's C/F display
setting is ever found to affect the raw logged values (currently
unknown, see fluke54/parser.py), runs can be told apart retroactively.
"""
from __future__ import annotations

import sys
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Measurement, Run
from .profile_builder import ProfilePoint


def _default_db_path() -> Path:
    """Anchor the DB next to the app rather than relying on the process's cwd.

    A bare relative path resolves against os.getcwd(), which is fragile for
    a launched .exe (pinned shortcuts, "run as admin", etc. can change it).
    Under PyInstaller's onefile mode this matters even more: sys.executable
    is the real, persistent .exe location, whereas the temp dir the app
    actually runs from (sys._MEIPASS) is wiped after every exit -- storing
    the DB there would silently lose all data between runs.
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "superba_profiler.db"


DEFAULT_DB_PATH = _default_db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant TEXT NOT NULL,
    tunnel TEXT NOT NULL,
    run_date TEXT NOT NULL,
    peak_temp_c REAL NOT NULL,
    min_temp_c REAL NOT NULL,
    measurement_count INTEGER NOT NULL,
    source_unit TEXT NOT NULL DEFAULT 'C',
    last_viewed_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    elapsed_time_s REAL NOT NULL,
    temperature_c REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_measurements_run_id ON measurements(run_id);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_schema(conn)
    conn.commit()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Bring databases created before belt-speed/tunnel-table removal up to date."""
    run_columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    if "source_unit" not in run_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN source_unit TEXT NOT NULL DEFAULT 'C'")

    if "plant" not in run_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN plant TEXT NOT NULL DEFAULT ''")

    if "tunnel" not in run_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN tunnel TEXT NOT NULL DEFAULT ''")
        if "tunnels" in tables and "tunnel_id" in run_columns:
            conn.execute("""
                UPDATE runs SET tunnel = (
                    SELECT name FROM tunnels WHERE tunnels.id = runs.tunnel_id
                )
                WHERE tunnel = ''
            """)

    if "last_viewed_at" not in run_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN last_viewed_at TEXT NOT NULL DEFAULT ''")
        # Recent Profiles previously sorted by run_date -- backfill so
        # existing runs keep that same order until one is actually viewed.
        conn.execute("UPDATE runs SET last_viewed_at = run_date WHERE last_viewed_at = ''")

    if "tunnel_id" in run_columns:
        conn.execute("DROP INDEX IF EXISTS idx_runs_tunnel_id")
        conn.execute("ALTER TABLE runs DROP COLUMN tunnel_id")

    if "belt_speed_m_per_min" in run_columns:
        conn.execute("ALTER TABLE runs DROP COLUMN belt_speed_m_per_min")

    if "tunnels" in tables:
        conn.execute("DROP TABLE tunnels")

    if "exit_temp_c" in run_columns:
        conn.execute("ALTER TABLE runs DROP COLUMN exit_temp_c")

    measurement_columns = {row["name"] for row in conn.execute("PRAGMA table_info(measurements)")}
    if "distance_m" in measurement_columns:
        conn.execute("ALTER TABLE measurements DROP COLUMN distance_m")


def create_run(
    conn: sqlite3.Connection,
    plant: str,
    tunnel: str,
    points: list[ProfilePoint],
    run_date: str | None = None,
    source_unit: str = "C",
) -> Run:
    if not points:
        raise ValueError("Cannot create a run with zero measurement points")

    temps = [p.temperature_c for p in points]
    peak_temp = max(temps)
    min_temp = min(temps)
    run_date = run_date or datetime.now(timezone.utc).isoformat(timespec="seconds")

    cur = conn.execute(
        """
        INSERT INTO runs (plant, tunnel, run_date, peak_temp_c, min_temp_c,
                           measurement_count, source_unit, last_viewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (plant, tunnel, run_date, peak_temp, min_temp, len(points), source_unit, run_date),
    )
    run_id = cur.lastrowid

    conn.executemany(
        "INSERT INTO measurements (run_id, elapsed_time_s, temperature_c) VALUES (?, ?, ?)",
        [(run_id, p.elapsed_time_s, p.temperature_c) for p in points],
    )
    conn.commit()

    return Run(
        id=run_id, plant=plant, tunnel=tunnel, run_date=run_date,
        peak_temp_c=peak_temp, min_temp_c=min_temp,
        measurement_count=len(points), source_unit=source_unit,
    )


def list_runs(conn: sqlite3.Connection, limit: int = 50) -> list[Run]:
    """Most recently *viewed* first (see touch_run_viewed), not most recently logged."""
    rows = conn.execute(
        """
        SELECT id, plant, tunnel, run_date, peak_temp_c, min_temp_c,
               measurement_count, source_unit
        FROM runs ORDER BY last_viewed_at DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        Run(
            id=r["id"], plant=r["plant"], tunnel=r["tunnel"], run_date=r["run_date"],
            peak_temp_c=r["peak_temp_c"], min_temp_c=r["min_temp_c"],
            measurement_count=r["measurement_count"], source_unit=r["source_unit"],
        )
        for r in rows
    ]


def touch_run_viewed(conn: sqlite3.Connection, run_id: int) -> None:
    """Mark a run as just-viewed, bumping it to the top of list_runs().

    Microsecond precision, unlike run_date's second precision -- two runs
    viewed in quick succession (a fast double-click through the list)
    would otherwise tie and leave their relative order ambiguous.
    """
    conn.execute(
        "UPDATE runs SET last_viewed_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(timespec="microseconds"), run_id),
    )
    conn.commit()


def search_runs(
    conn: sqlite3.Connection,
    plant: str = "",
    tunnel: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
) -> list[Run]:
    """Filter runs by plant/tunnel substring and an inclusive run_date range.

    date_from/date_to are plain 'YYYY-MM-DD' strings; run_date is stored as a
    full ISO 8601 timestamp, which sorts/compares correctly against a
    date-only prefix lexicographically, so no parsing is needed.
    """
    query = """
        SELECT id, plant, tunnel, run_date, peak_temp_c, min_temp_c,
               measurement_count, source_unit
        FROM runs
        WHERE plant LIKE ? AND tunnel LIKE ?
    """
    params: list = [f"%{plant}%", f"%{tunnel}%"]
    if date_from:
        query += " AND run_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND run_date <= ?"
        params.append(date_to + "T23:59:59")
    query += " ORDER BY run_date DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [
        Run(
            id=r["id"], plant=r["plant"], tunnel=r["tunnel"], run_date=r["run_date"],
            peak_temp_c=r["peak_temp_c"], min_temp_c=r["min_temp_c"],
            measurement_count=r["measurement_count"], source_unit=r["source_unit"],
        )
        for r in rows
    ]


def get_run(conn: sqlite3.Connection, run_id: int) -> Run | None:
    row = conn.execute(
        """
        SELECT id, plant, tunnel, run_date, peak_temp_c, min_temp_c,
               measurement_count, source_unit
        FROM runs WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return Run(
        id=row["id"], plant=row["plant"], tunnel=row["tunnel"], run_date=row["run_date"],
        peak_temp_c=row["peak_temp_c"], min_temp_c=row["min_temp_c"],
        measurement_count=row["measurement_count"], source_unit=row["source_unit"],
    )


def get_measurements(conn: sqlite3.Connection, run_id: int) -> list[Measurement]:
    rows = conn.execute(
        """
        SELECT id, run_id, elapsed_time_s, temperature_c
        FROM measurements WHERE run_id = ? ORDER BY elapsed_time_s
        """,
        (run_id,),
    ).fetchall()
    return [
        Measurement(
            id=r["id"], run_id=r["run_id"], elapsed_time_s=r["elapsed_time_s"],
            temperature_c=r["temperature_c"],
        )
        for r in rows
    ]
