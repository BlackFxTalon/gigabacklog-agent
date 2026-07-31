from __future__ import annotations

from io import StringIO
from typing import Any

import pytest

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.cli import run_cli
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import (
    Recommendation,
    SearchToolCall,
    SimilarRequest,
    SpecialistDecision,
    TerminalStatus,
)


class FakeGigaChat:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def create_search_tool_call(self, raw_request: str) -> SearchToolCall:
        self.requests.append(raw_request)
        return SearchToolCall(name="search_similar_requests", query=raw_request)

    def recommend(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
    ) -> dict[str, Any]:
        return self._payload(similar_requests)

    def correct_recommendation(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
        validation_error: str,
        allowed_similar_request_ids: set[int],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return self._payload(similar_requests)

    @staticmethod
    def _payload(similar_requests: list[SimilarRequest]) -> dict[str, Any]:
        return {
            "title": "Не работает авторизация",
            "summary": "После обновления отдел продаж не может войти в систему заявок.",
            "category": "incident",
            "priority": "P1",
            "reason": "Отдел не может работать.",
            "affected_users": "department",
            "impact": "blocked",
            "workaround": "unavailable",
            "analysis_status": "complete",
            "missing_information": [],
            "recommended_action": "Проверить обновление.",
            "similar_request_ids": [request.id for request in similar_requests],
        }


class CorrectingFakeGigaChat(FakeGigaChat):
    def __init__(self) -> None:
        super().__init__()
        self.corrections = 0

    def recommend(self, raw_request: str, similar_requests: list[SimilarRequest]) -> dict[str, Any]:
        payload = self._payload(similar_requests)
        payload["category"] = "invalid"
        return payload

    def correct_recommendation(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
        validation_error: str,
        allowed_similar_request_ids: set[int],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.corrections += 1
        return self._payload(similar_requests)


class InvalidFakeGigaChat(CorrectingFakeGigaChat):
    def correct_recommendation(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
        validation_error: str,
        allowed_similar_request_ids: set[int],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.corrections += 1
        payload = self._payload(similar_requests)
        payload["similar_request_ids"] = [999]
        return payload


def test_specialist_can_accept_and_persist_an_offline_recommendation(tmp_path) -> None:
    model = FakeGigaChat()
    database_path = tmp_path / "prototype.db"
    store = SQLiteRunStore(database_path)
    session = ProcessingSession(model=model, run_store=store)
    specialist_input = StringIO(
        "После обновления весь отдел продаж не может войти в систему заявок.\n1\n"
    )
    terminal_output = StringIO()

    result = run_cli(session, input_stream=specialist_input, output_stream=terminal_output)

    assert model.requests == ["После обновления весь отдел продаж не может войти в систему заявок."]
    assert result.recommendation is not None
    assert result.recommendation.title == "Не работает авторизация"
    assert result.recommendation.category.value == "incident"
    assert result.recommendation.priority.value == "P1"
    assert result.recommendation.similar_request_ids == [1, 2, 3]
    assert result.review_status is SpecialistDecision.ACCEPTED
    assert result.run_id == 1
    assert store.get_run(result.run_id) == result
    database_path.rename(tmp_path / "released.db")
    output = terminal_output.getvalue()
    assert "[tool] search_similar_requests(" in output
    assert "[tool] Найдено похожих обращений: 3" in output
    assert "[tool] #1: Сбой входа отдела продаж после обновления" in output
    assert "Заголовок: Не работает авторизация" in output
    assert "Решение сохранено. Run ID: 1" in output


def test_empty_request_is_rejected_before_the_graph_runs(tmp_path) -> None:
    model = FakeGigaChat()
    store = SQLiteRunStore(tmp_path / "prototype.db")
    session = ProcessingSession(model=model, run_store=store)

    with pytest.raises(ValueError, match="Request must not be empty"):
        run_cli(
            session,
            input_stream=StringIO("   \n1\n"),
            output_stream=StringIO(),
        )

    assert model.requests == []


def test_first_invalid_analysis_is_corrected_once_before_review(tmp_path) -> None:
    model = CorrectingFakeGigaChat()
    session = ProcessingSession(model=model, run_store=SQLiteRunStore(tmp_path / "prototype.db"))

    result = session.run(
        "Отдел продаж не может войти после обновления.",
        lambda _: SpecialistDecision.ACCEPTED,
    )

    assert model.corrections == 1
    assert result.review_status is SpecialistDecision.ACCEPTED


def test_second_invalid_analysis_persists_a_terminal_result_without_human_review(tmp_path) -> None:
    model = InvalidFakeGigaChat()
    store = SQLiteRunStore(tmp_path / "prototype.db")
    session = ProcessingSession(model=model, run_store=store)

    def fail_review(_: Recommendation) -> SpecialistDecision:
        raise AssertionError("Human review must not start after validation failure")

    result = session.run("Отдел продаж не может войти после обновления.", fail_review)

    assert model.corrections == 1
    assert result.terminal_status is TerminalStatus.VALIDATION_FAILED
    assert result.recommendation is None
    assert result.review_status is SpecialistDecision.NOT_REVIEWED
    assert result.run_id == 1
    assert store.get_run(result.run_id) == result


def test_cli_reports_a_validation_failure_without_showing_a_recommendation(tmp_path) -> None:
    session = ProcessingSession(
        model=InvalidFakeGigaChat(),
        run_store=SQLiteRunStore(tmp_path / "prototype.db"),
    )
    terminal_output = StringIO()

    result = run_cli(
        session,
        input_stream=StringIO("Отдел продаж не может войти после обновления.\n"),
        output_stream=terminal_output,
    )

    assert result.terminal_status is TerminalStatus.VALIDATION_FAILED
    assert result.recommendation is None
    assert "Рекомендация агента:" not in terminal_output.getvalue()
    assert "Не удалось сформировать валидированную рекомендацию" in terminal_output.getvalue()
