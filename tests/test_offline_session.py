from __future__ import annotations

from io import StringIO

import pytest

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.cli import run_cli
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import Recommendation, SpecialistDecision


class FakeGigaChat:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def recommend(self, raw_request: str) -> Recommendation:
        self.requests.append(raw_request)
        return Recommendation(
            title="Не работает авторизация",
            summary="После обновления отдел продаж не может войти в систему заявок.",
        )


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
    assert result.recommendation == Recommendation(
        title="Не работает авторизация",
        summary="После обновления отдел продаж не может войти в систему заявок.",
    )
    assert result.review_status is SpecialistDecision.ACCEPTED
    assert result.run_id == 1
    assert store.get_run(result.run_id) == result
    database_path.rename(tmp_path / "released.db")
    assert terminal_output.getvalue() == (
        "GigaBacklog Agent — offline prototype\n"
        "\n"
        "Опишите проблему:\n"
        "> "
        "\n"
        "Рекомендация агента:\n"
        "Заголовок: Не работает авторизация\n"
        "Резюме: После обновления отдел продаж не может войти в систему заявок.\n"
        "\n"
        "Решение специалиста:\n"
        "1. Принять рекомендацию\n"
        "> "
        "\n"
        "Решение сохранено. Run ID: 1\n"
    )


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
