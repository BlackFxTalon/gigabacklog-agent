from __future__ import annotations

import json
import os

import pytest
from gigachat.models import (
    ChatCompletionRequest,
    ChatContentPart,
    ChatMessage,
    ChatModelOptions,
    ChatResponseFormat,
)
from pydantic import ValidationError

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.gigachat_adapter import (
    GigaChatRecommendationModel,
    _provider_schema,
    _structured_policy,
    create_gigachat_client,
)
from gigabacklog_agent.gigachat_config import GigaChatSettings
from gigabacklog_agent.models import (
    ModelContext,
    RequestAnalysis,
    SimilarRequest,
    SpecialistDecision,
    SpecialistReview,
    TerminalStatus,
)

pytestmark = pytest.mark.integration


def _safe_response_shape(error: ValidationError) -> str:
    """Describe only response container keys; never expose provider content."""
    payload = error.errors()[0].get("input")
    if not isinstance(payload, dict):
        return f"validation input type={type(payload).__name__}"

    details = [f"top-level keys={sorted(payload)}"]
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        details.append(f"choices[0] keys={sorted(choices[0])}")
        message = choices[0].get("message")
        if isinstance(message, dict):
            details.append(f"choices[0].message keys={sorted(message)}")
    return "; ".join(details)


def _assert_full_schema_probe(messages: list[ChatMessage], *, scenario: str) -> None:
    settings = GigaChatSettings.from_environment()
    client = create_gigachat_client(settings)
    request = ChatCompletionRequest(
        messages=messages,
        model_options=ChatModelOptions(
            temperature=0,
            max_tokens=512,
            response_format=ChatResponseFormat(
                type="json_schema",
                schema=_provider_schema(),
                strict=True,
            ),
        ),
    )
    try:
        response = client.chat.create(request)
    except ValidationError:
        raise AssertionError(f"{scenario}: v2 response shape invalid") from None

    response_text = "".join(
        part.text or ""
        for message in response.messages
        if message.role == "assistant"
        for part in message.content or []
    )
    if not response_text:
        raise AssertionError(f"{scenario}: v2 response has no assistant text")
    try:
        RequestAnalysis.model_validate_json(response_text)
    except ValidationError:
        raise AssertionError(f"{scenario}: generated content failed JSON/DTO validation") from None


_DIAGNOSTIC_PROBE_SKIP = pytest.mark.skipif(
    os.environ.get("RUN_GIGACHAT_INTEGRATION") != "1"
    or os.environ.get("RUN_GIGACHAT_PAYLOAD_DIAGNOSTICS") != "1"
    or not os.environ.get("GIGACHAT_CREDENTIALS"),
    reason="requires explicit live payload-diagnostics opt-in plus credentials",
)


@_DIAGNOSTIC_PROBE_SKIP
def test_live_full_schema_with_simple_user_prompt() -> None:
    _assert_full_schema_probe(
        [ChatMessage(role="user", content=[ChatContentPart(text="Верни рекомендацию.")])],
        scenario="simple_user_prompt",
    )


@_DIAGNOSTIC_PROBE_SKIP
def test_live_full_schema_with_trusted_system_policy() -> None:
    _assert_full_schema_probe(
        [
            ChatMessage(
                role="system",
                content=[
                    ChatContentPart(
                        text=_structured_policy(ModelContext.from_untrusted_inputs("", []).policy)
                    )
                ],
            ),
            ChatMessage(role="user", content=[ChatContentPart(text="Верни рекомендацию.")]),
        ],
        scenario="trusted_system_policy",
    )


@_DIAGNOSTIC_PROBE_SKIP
def test_live_full_schema_with_json_context() -> None:
    context = ModelContext.from_untrusted_inputs(
        "Проверить вход сотрудников в систему",
        [
            SimilarRequest(
                id=1,
                title="Сбой входа",
                summary="Пользователи не могут войти после обновления.",
            )
        ],
    )
    _assert_full_schema_probe(
        [
            ChatMessage(
                role="system",
                content=[ChatContentPart(text=_structured_policy(context.policy))],
            ),
            ChatMessage(
                role="user",
                content=[
                    ChatContentPart(
                        text=json.dumps(
                            {
                                "request": context.untrusted_request,
                                "similar_requests": [
                                    {
                                        "id": 1,
                                        "title": "Сбой входа",
                                        "summary": "Исторический контекст.",
                                    }
                                ],
                            },
                            ensure_ascii=False,
                        )
                    )
                ],
            ),
        ],
        scenario="json_context",
    )


@pytest.mark.skipif(
    os.environ.get("RUN_GIGACHAT_INTEGRATION") != "1"
    or os.environ.get("RUN_GIGACHAT_SCHEMA_PROBE") != "1"
    or not os.environ.get("GIGACHAT_CREDENTIALS"),
    reason="requires explicit live integration and schema-probe opt-ins plus credentials",
)
def test_live_gigachat_minimal_v2_strict_schema_probe() -> None:
    settings = GigaChatSettings.from_environment()
    client = create_gigachat_client(settings)
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content=[ChatContentPart(text="Верни статус ok.")])],
        model_options=ChatModelOptions(
            response_format=ChatResponseFormat(
                type="json_schema",
                schema={
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"],
                    "additionalProperties": True,
                },
                strict=True,
            )
        ),
    )

    try:
        response = client.chat.create(request)
    except ValidationError as error:
        raise AssertionError(
            f"Minimal v2 strict-schema response shape: {_safe_response_shape(error)}"
        ) from error

    assert response.messages
    assert any(part.text for message in response.messages for part in message.content or [])


@pytest.mark.skipif(
    os.environ.get("RUN_GIGACHAT_INTEGRATION") != "1" or not os.environ.get("GIGACHAT_CREDENTIALS"),
    reason="requires RUN_GIGACHAT_INTEGRATION=1 and GIGACHAT_CREDENTIALS",
)
def test_live_gigachat_forces_search_tool_and_accepts_strict_schema(tmp_path) -> None:
    settings = GigaChatSettings.from_environment()
    client = create_gigachat_client(settings)
    available_models = {model.id_ for model in client.get_models().data}
    assert settings.model in available_models

    session = ProcessingSession(
        model=GigaChatRecommendationModel(client),
        run_store=SQLiteRunStore(tmp_path / "live-smoke.db"),
    )
    result = session.run(
        "Проверить вход сотрудников в систему",
        lambda _: SpecialistReview(SpecialistDecision.ACCEPTED),
    )

    assert result.terminal_status is TerminalStatus.COMPLETED
    assert result.recommendation is not None
    assert result.recommendation.title
    assert set(result.recommendation.similar_request_ids) <= {1, 2, 3}
