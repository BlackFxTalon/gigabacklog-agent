from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from gigabacklog_agent.models import Recommendation, SessionResult, SpecialistDecision


class SQLiteRunStore:
    """Persist and retrieve completed processing sessions in SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_request TEXT NOT NULL,
                    recommendation_json TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save_run(
        self,
        raw_request: str,
        recommendation: Recommendation,
        review_status: SpecialistDecision,
    ) -> int:
        recommendation_json = json.dumps(asdict(recommendation), ensure_ascii=False)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO agent_runs (raw_request, recommendation_json, review_status)
                VALUES (?, ?, ?)
                """,
                (raw_request, recommendation_json, review_status.value),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a run identifier")
            return cursor.lastrowid

    def get_run(self, run_id: int) -> SessionResult | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT raw_request, recommendation_json, review_status
                FROM agent_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        raw_request, recommendation_json, review_status = row
        return SessionResult(
            raw_request=raw_request,
            recommendation=Recommendation(**json.loads(recommendation_json)),
            review_status=SpecialistDecision(review_status),
            run_id=run_id,
        )
