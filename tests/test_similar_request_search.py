from __future__ import annotations

from gigabacklog_agent.database import SQLiteRunStore


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
