from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from gigabacklog_agent.models import (
    AnalysisStatus,
    Impact,
    Recommendation,
    RecommendedPriority,
    RequestCategory,
    RunEvent,
    SessionResult,
    SimilarRequest,
    SpecialistDecision,
    TerminalStatus,
    Workaround,
)

_WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)
_SEARCH_LIMIT = 3
_SEED_REQUESTS = (
    (
        "Сбой входа отдела продаж после обновления",
        "После обновления весь отдел продаж не может войти в систему заявок.",
    ),
    (
        "Не открывается система заявок у нескольких сотрудников",
        "Несколько сотрудников видят ошибку при открытии системы заявок.",
    ),
    (
        "Запрос доступа новому сотруднику",
        "Нужно предоставить новому сотруднику права на просмотр заявок.",
    ),
)


class SQLiteRunStore:
    """Persist sessions and search historical requests in SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()
        self._seed_history_if_empty()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def reset(self) -> None:
        """Recreate the complete local demonstration database and seed history."""
        if self._database_path.exists():
            self._database_path.unlink()
        self._initialize_schema()
        self._seed_history_if_empty()

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_request TEXT NOT NULL,
                    recommendation_json TEXT,
                    review_status TEXT NOT NULL,
                    review_comment TEXT,
                    terminal_status TEXT NOT NULL DEFAULT 'completed',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._migrate_agent_runs(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    run_id INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES agent_runs(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    normalized_text TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _migrate_agent_runs(connection: sqlite3.Connection) -> None:
        columns = {
            row[1]: {"not_null": bool(row[3])}
            for row in connection.execute("PRAGMA table_info(agent_runs)")
        }
        if "review_comment" not in columns:
            connection.execute("ALTER TABLE agent_runs ADD COLUMN review_comment TEXT")
            columns["review_comment"] = {"not_null": False}
        if "terminal_status" in columns and not columns["recommendation_json"]["not_null"]:
            return

        terminal_status = "terminal_status" if "terminal_status" in columns else "'completed'"
        connection.execute(
            """
            CREATE TABLE agent_runs_migrated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_request TEXT NOT NULL,
                recommendation_json TEXT,
                review_status TEXT NOT NULL,
                review_comment TEXT,
                terminal_status TEXT NOT NULL DEFAULT 'completed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            f"""
            INSERT INTO agent_runs_migrated (
                id, raw_request, recommendation_json, review_status,
                review_comment, terminal_status, created_at
            )
            SELECT
                id, raw_request, recommendation_json, review_status,
                NULL, {terminal_status}, created_at
            FROM agent_runs
            """
        )
        connection.execute("DROP TABLE agent_runs")
        connection.execute("ALTER TABLE agent_runs_migrated RENAME TO agent_runs")

    @staticmethod
    def _normalize_text(value: str) -> str:
        return f" {' '.join(_WORD_PATTERN.findall(value.casefold()))} "

    def _seed_history_if_empty(self) -> None:
        with closing(self._connect()) as connection, connection:
            (count,) = connection.execute("SELECT COUNT(*) FROM historical_requests").fetchone()
            if count:
                return
            connection.executemany(
                """
                INSERT INTO historical_requests (title, summary, normalized_text)
                VALUES (?, ?, ?)
                """,
                [
                    (title, summary, self._normalize_text(f"{title} {summary}"))
                    for title, summary in _SEED_REQUESTS
                ],
            )

    def search_similar_requests(self, query: str) -> list[SimilarRequest]:
        """Find historical requests through safe normalized-word matching."""
        normalized_words = self._normalize_text(query).split()
        if not normalized_words:
            return []

        where_parts = ["normalized_text LIKE ?" for _ in normalized_words]
        parameters = [f"% {word} %" for word in normalized_words]
        sql = (
            "SELECT id, title, summary, normalized_text FROM historical_requests WHERE "
            + " OR ".join(where_parts)
        )
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, parameters).fetchall()

        ranked_rows = sorted(
            rows,
            key=lambda row: (
                -sum(word in row[3].split() for word in normalized_words),
                row[0],
            ),
        )
        return [
            SimilarRequest(id=row[0], title=row[1], summary=row[2])
            for row in ranked_rows[:_SEARCH_LIMIT]
        ]

    def save_run(
        self,
        raw_request: str,
        recommendation: Recommendation | None,
        review_status: SpecialistDecision,
        terminal_status: TerminalStatus,
        review_comment: str | None = None,
        events: list[RunEvent] | None = None,
    ) -> int:
        recommendation_json = (
            json.dumps(asdict(recommendation), ensure_ascii=False)
            if recommendation is not None
            else None
        )
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO agent_runs (
                    raw_request, recommendation_json, review_status, review_comment, terminal_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    raw_request,
                    recommendation_json,
                    review_status.value,
                    review_comment,
                    terminal_status.value,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a run identifier")
            run_id = cursor.lastrowid
            connection.executemany(
                """
                INSERT INTO run_events (run_id, sequence, event_type, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        event.sequence,
                        event.event_type,
                        json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                    )
                    for event in events or []
                ],
            )
            return run_id

    def get_run_events(self, run_id: int) -> list[RunEvent]:
        """Return a run's safe audit events in their recorded sequence."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_type, payload_json
                FROM run_events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return [
            RunEvent(sequence=sequence, event_type=event_type, payload=json.loads(payload_json))
            for sequence, event_type, payload_json in rows
        ]

    def get_run(self, run_id: int) -> SessionResult | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT raw_request, recommendation_json, review_status,
                       review_comment, terminal_status
                FROM agent_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        raw_request, recommendation_json, review_status, review_comment, terminal_status = row
        recommendation = None
        if recommendation_json is not None:
            payload = json.loads(recommendation_json)
            if set(payload) == {"title", "summary"}:
                payload |= {
                    "category": RequestCategory.OTHER,
                    "priority": RecommendedPriority.P4,
                    "reason": "Legacy recommendation without structured analysis.",
                    "affected_users": "unknown",
                    "impact": Impact.UNKNOWN,
                    "workaround": Workaround.UNKNOWN,
                    "analysis_status": AnalysisStatus.NEEDS_INFORMATION,
                    "missing_information": ["Structured analysis was not recorded."],
                    "recommended_action": "Review the original request.",
                    "similar_request_ids": [],
                }
            recommendation = Recommendation(**payload)
        return SessionResult(
            raw_request=raw_request,
            recommendation=recommendation,
            review_status=SpecialistDecision(review_status),
            review_comment=review_comment,
            terminal_status=TerminalStatus(terminal_status),
            run_id=run_id,
        )
