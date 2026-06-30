#!/usr/bin/env python
"""SQLite 저장소 (몸무게 측정 기록). 파일 1개로 동작."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# 배포 시 볼륨 경로로 바꿀 수 있도록 환경변수 우선 (예: WEIGHT_DB=/data/weights.db)
DB_PATH = Path(os.environ.get("WEIGHT_DB") or (Path(__file__).parent / "weights.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS measurements (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                weight     REAL    NOT NULL,
                taken_at   TEXT    NOT NULL,   -- ISO8601, 사진 올린 시간
                conf       REAL,
                image_file TEXT,
                crop_file  TEXT
            )
            """
        )


def add_measurement(
    weight: float,
    taken_at: str,
    conf: float | None = None,
    image_file: str | None = None,
    crop_file: str | None = None,
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO measurements (weight, taken_at, conf, image_file, crop_file)"
            " VALUES (?, ?, ?, ?, ?)",
            (weight, taken_at, conf, image_file, crop_file),
        )
        row = conn.execute(
            "SELECT * FROM measurements WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


def list_measurements() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM measurements ORDER BY taken_at ASC, id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_weight(measurement_id: int, weight: float) -> dict | None:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE measurements SET weight = ? WHERE id = ?",
            (weight, measurement_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM measurements WHERE id = ?", (measurement_id,)
        ).fetchone()
    return dict(row)


def delete_measurement(measurement_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM measurements WHERE id = ?", (measurement_id,)
        )
    return cur.rowcount > 0
