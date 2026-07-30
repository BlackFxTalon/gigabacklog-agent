from __future__ import annotations

import pytest
from pydantic import ValidationError

from gigabacklog_agent.models import RequestAnalysis, validate_request_analysis


def test_request_analysis_rejects_an_unknown_category() -> None:
    with pytest.raises(ValidationError):
        RequestAnalysis.model_validate(
            {
                "title": "Ошибка входа",
                "summary": "Отдел не может войти.",
                "category": "unknown",
                "priority": "P1",
                "reason": "Критичный процесс заблокирован.",
                "affected_users": "department",
                "impact": "blocked",
                "workaround": "unavailable",
                "analysis_status": "complete",
                "missing_information": [],
                "recommended_action": "Проверить обновление.",
                "similar_request_ids": [1],
            }
        )


def test_request_analysis_rejects_a_hallucinated_similar_request_id() -> None:
    payload = {
        "title": "Ошибка входа",
        "summary": "Отдел не может войти.",
        "category": "incident",
        "priority": "P1",
        "reason": "Критичный процесс заблокирован.",
        "affected_users": "department",
        "impact": "blocked",
        "workaround": "unavailable",
        "analysis_status": "complete",
        "missing_information": [],
        "recommended_action": "Проверить обновление.",
        "similar_request_ids": [999],
    }

    with pytest.raises(ValueError, match="unknown similar request IDs"):
        validate_request_analysis(payload, {1, 2})


def test_request_analysis_rejects_malformed_output() -> None:
    with pytest.raises(ValidationError):
        RequestAnalysis.model_validate({"title": "Only one field"})
