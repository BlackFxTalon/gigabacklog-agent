from __future__ import annotations

import os

import pytest

from gigabacklog_agent.gigachat_adapter import GigaChatRecommendationModel, create_gigachat_client
from gigabacklog_agent.gigachat_config import GigaChatSettings
from gigabacklog_agent.models import ModelContext, SimilarRequest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.environ.get("RUN_GIGACHAT_INTEGRATION") != "1" or not os.environ.get("GIGACHAT_CREDENTIALS"),
    reason="requires RUN_GIGACHAT_INTEGRATION=1 and GIGACHAT_CREDENTIALS",
)
def test_live_gigachat_forces_search_tool_and_accepts_strict_schema() -> None:
    settings = GigaChatSettings.from_environment()
    client = create_gigachat_client(settings)
    available_models = {model.id_ for model in client.get_models().data}
    assert settings.model in available_models

    bridge = GigaChatRecommendationModel(client)

    tool_call = bridge.create_search_tool_call("Проверить вход сотрудников в систему")

    assert tool_call.name == "search_similar_requests"
    assert tool_call.query.strip()

    recommendation = bridge.recommend(
        ModelContext.from_untrusted_inputs(
            "Проверить вход сотрудников в систему",
            [
                SimilarRequest(
                    id=1,
                    title="Сбой входа",
                    summary="Пользователи не могут войти после обновления.",
                )
            ],
        )
    )

    assert recommendation["title"]
    assert recommendation["similar_request_ids"] == [1]
