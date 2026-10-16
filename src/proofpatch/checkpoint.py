"""Durable incident snapshots and model-call ledger for process restart."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class Checkpoints:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS snapshots (sequence INTEGER PRIMARY KEY, "
            "created_at TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS model_ledger (id INTEGER PRIMARY KEY CHECK(id=1), "
            "payload TEXT NOT NULL)"
        )
        self.connection.commit()

    def save(self, payload: dict):
        with self.connection:
            self.connection.execute(
                "INSERT INTO snapshots (created_at, payload) VALUES (?, ?)",
                (datetime.now(UTC).isoformat(), json.dumps(payload)),
            )

    def latest(self) -> dict:
        row = self.connection.execute(
            "SELECT payload FROM snapshots ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise ValueError("No completed incident checkpoint is available")
        return json.loads(row[0])

    def save_usage(self, entries: list[dict]):
        with self.connection:
            self.connection.execute(
                "INSERT INTO model_ledger (id, payload) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (json.dumps(entries),),
            )

    def usage(self) -> list[dict]:
        row = self.connection.execute("SELECT payload FROM model_ledger WHERE id=1").fetchone()
        return json.loads(row[0]) if row else []

    def close(self):
        self.connection.close()
