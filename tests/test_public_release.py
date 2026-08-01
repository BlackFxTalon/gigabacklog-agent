from __future__ import annotations

from io import StringIO

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.cli import OfflineFakeGigaChat, run_cli
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import SpecialistDecision, TerminalStatus


def test_documented_offline_happy_path_is_persisted_and_accepted(tmp_path) -> None:
    store = SQLiteRunStore(tmp_path / "prototype.db")
    result = run_cli(
        ProcessingSession(model=OfflineFakeGigaChat(), run_store=store),
        input_stream=StringIO(
            "После обновления весь отдел продаж не может войти в систему заявок.\n1\n"
        ),
        output_stream=StringIO(),
    )

    assert result.terminal_status is TerminalStatus.COMPLETED
    assert result.review_status is SpecialistDecision.ACCEPTED
    assert result.recommendation is not None
    assert result.recommendation.category.value == "incident"
    assert result.recommendation.priority.value == "P1"
    assert result.recommendation.affected_users == "department"
    assert result.recommendation.similar_request_ids == [1, 2, 3]
