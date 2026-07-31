from __future__ import annotations

import sqlite3

from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import SpecialistDecision, TerminalStatus


def test_ranked_search_returns_the_most_relevant_seeded_request_first(tmp_path) -> None:
    store = SQLiteRunStore(tmp_path / "demo.db")

    similar_requests = store.search_similar_requests(
        "После обновления весь отдел продаж не может войти в систему заявок."
    )

    assert [request.title for request in similar_requests[:2]] == [
        "Сбой входа отдела продаж после обновления",
        "Не открывается система заявок у нескольких сотрудников",
    ]


def test_search_does_not_match_partial_words(tmp_path) -> None:
    store = SQLiteRunStore(tmp_path / "demo.db")

    assert store.search_similar_requests("прод") == []


def test_legacy_database_is_migrated_without_losing_completed_runs(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_request TEXT NOT NULL,
                recommendation_json TEXT NOT NULL,
                review_status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_runs (raw_request, recommendation_json, review_status)
            VALUES ('Тест', '{"title": "Заголовок", "summary": "Резюме"}', 'accepted')
            """
        )

    store = SQLiteRunStore(database_path)

    migrated_run = store.get_run(1)
    assert migrated_run is not None
    assert migrated_run.terminal_status is TerminalStatus.COMPLETED
    assert migrated_run.recommendation is not None
    assert migrated_run.recommendation.title == "Заголовок"

    validation_failure_id = store.save_run(
        raw_request="Невалидный ответ модели",
        recommendation=None,
        review_status=SpecialistDecision.NOT_REVIEWED,
        terminal_status=TerminalStatus.VALIDATION_FAILED,
    )
    validation_failure = store.get_run(validation_failure_id)
    assert validation_failure is not None
    assert validation_failure.recommendation is None
    assert validation_failure.terminal_status is TerminalStatus.VALIDATION_FAILED
