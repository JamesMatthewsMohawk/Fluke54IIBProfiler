"""SQLite persistence layer for the Superba Tunnel Profiler.

Schema:
    tunnels(id, name, length_m)
    runs(id, tunnel_id, run_date, belt_speed_m_per_min,
         peak_temp_c, min_temp_c, exit_temp_c, measurement_count)
    measurements(id, run_id, elapsed_time_s, distance_m, temperature_c)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Measurement, Run, Tunnel
from .tunnel import ProfilePoint

DEFAULT_DB_PATH = Path("superba_profiler.db")

DEFAULT_TUNNELS: tuple[tuple[str, float], ...] = (
    ("Superba A", 12.0),
    ("Superba B", 12.0),
    ("Superba C", 12.0),
    ("Superba D", 12.0),
    ("Superba E", 12.0),
    ("Superba F", 12.0),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tunnels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    length_m REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tunnel_id INTEGER NOT NULL REFERENCES tunnels(id),
    run_date TEXT NOT NULL,
    belt_speed_m_per_min REAL NOT NULL,
    peak_temp_c REAL NOT NULL,
    min_temp_c REAL NOT NULL,
    exit_temp_c REAL NOT NULL,
    measurement_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    elapsed_time_s REAL NOT NULL,
    distance_m REAL NOT NULL,
    temperature_c REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_measurements_run_id ON measurements(run_id);
CREATE INDEX IF NOT EXISTS idx_runs_tunnel_id ON runs(tunnel_id);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    existing = conn.execute("SELECT COUNT(*) FROM tunnels").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT INTO tunnels (name, length_m) VALUES (?, ?)", DEFAULT_TUNNELS
        )
    conn.commit()


def list_tunnels(conn: sqlite3.Connection) -> list[Tunnel]:
    rows = conn.execute("SELECT id, name, length_m FROM tunnels ORDER BY name").fetchall()
    return [Tunnel(id=r["id"], name=r["name"], length_m=r["length_m"]) for r in rows]


def create_run(
    conn: sqlite3.Connection,
    tunnel_id: int,
    belt_speed_m_per_min: float,
    points: list[ProfilePoint],
    run_date: str | None = None,
) -> Run:
    if not points:
        raise ValueError("Cannot create a run with zero measurement points")

    temps = [p.temperature_c for p in points]
    peak_temp = max(temps)
    min_temp = min(temps)
    exit_temp = points[-1].temperature_c
    run_date = run_date or datetime.now(timezone.utc).isoformat(timespec="seconds")

    cur = conn.execute(
        """
        INSERT INTO runs (tunnel_id, run_date, belt_speed_m_per_min,
                           peak_temp_c, min_temp_c, exit_temp_c, measurement_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (tunnel_id, run_date, belt_speed_m_per_min, peak_temp, min_temp, exit_temp, len(points)),
    )
    run_id = cur.lastrowid

    conn.executemany(
        "INSERT INTO measurements (run_id, elapsed_time_s, distance_m, temperature_c) VALUES (?, ?, ?, ?)",
        [(run_id, p.elapsed_time_s, p.distance_m, p.temperature_c) for p in points],
    )
    conn.commit()

    tunnel_name = conn.execute("SELECT name FROM tunnels WHERE id = ?", (tunnel_id,)).fetchone()["name"]
    return Run(
        id=run_id, tunnel_id=tunnel_id, tunnel_name=tunnel_name, run_date=run_date,
        belt_speed_m_per_min=belt_speed_m_per_min, peak_temp_c=peak_temp,
        min_temp_c=min_temp, exit_temp_c=exit_temp, measurement_count=len(points),
    )


def list_runs(conn: sqlite3.Connection, tunnel_id: int | None = None, limit: int = 50) -> list[Run]:
    query = """
        SELECT r.id, r.tunnel_id, t.name AS tunnel_name, r.run_date, r.belt_speed_m_per_min,
               r.peak_temp_c, r.min_temp_c, r.exit_temp_c, r.measurement_count
        FROM runs r JOIN tunnels t ON t.id = r.tunnel_id
    """
    params: tuple = ()
    if tunnel_id is not None:
        query += " WHERE r.tunnel_id = ?"
        params = (tunnel_id,)
    query += " ORDER BY r.run_date DESC LIMIT ?"
    params = params + (limit,)

    rows = conn.execute(query, params).fetchall()
    return [
        Run(
            id=r["id"], tunnel_id=r["tunnel_id"], tunnel_name=r["tunnel_name"],
            run_date=r["run_date"], belt_speed_m_per_min=r["belt_speed_m_per_min"],
            peak_temp_c=r["peak_temp_c"], min_temp_c=r["min_temp_c"],
            exit_temp_c=r["exit_temp_c"], measurement_count=r["measurement_count"],
        )
        for r in rows
    ]


def get_measurements(conn: sqlite3.Connection, run_id: int) -> list[Measurement]:
    rows = conn.execute(
        """
        SELECT id, run_id, elapsed_time_s, distance_m, temperature_c
        FROM measurements WHERE run_id = ? ORDER BY elapsed_time_s
        """,
        (run_id,),
    ).fetchall()
    return [
        Measurement(
            id=r["id"], run_id=r["run_id"], elapsed_time_s=r["elapsed_time_s"],
            distance_m=r["distance_m"], temperature_c=r["temperature_c"],
        )
        for r in rows
    ]
