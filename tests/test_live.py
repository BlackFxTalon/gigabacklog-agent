from __future__ import annotations

from typing import Any

from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.live import create_live_processing_session


class NonNetworkClient:
    def bind_tools(self, tools: list[dict[str, Any]], *, tool_choice: str) -> Any:
        raise AssertionError("Model invocation must not happen during construction")

    def with_structured_output(self, schema: type, **kwargs: Any) -> Any:
        raise AssertionError("Model invocation must not happen during construction")


def test_live_session_construction_is_opt_in_and_sends_no_request(tmp_path) -> None:
    received_settings: list[Any] = []

    def factory(settings: Any) -> NonNetworkClient:
        received_settings.append(settings)
        return NonNetworkClient()

    session = create_live_processing_session(
        SQLiteRunStore(tmp_path / "prototype.db"),
        environ={"GIGACHAT_CREDENTIALS": "not-a-real-key"},
        client_factory=factory,
    )

    assert session is not None
    assert len(received_settings) == 1
    assert received_settings[0].model == "GigaChat-2-Max"
    assert received_settings[0].scope == "GIGACHAT_API_PERS"
