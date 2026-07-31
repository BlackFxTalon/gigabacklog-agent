from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import (
    Recommendation,
    RunEvent,
    SearchToolCall,
    SessionResult,
    SimilarRequest,
    SpecialistDecision,
    SpecialistReview,
    TerminalStatus,
)


class OfflineFakeGigaChat:
    """Temporary deterministic adapter for the offline walking skeleton."""

    def create_search_tool_call(self, raw_request: str) -> SearchToolCall:
        return SearchToolCall(name="search_similar_requests", query=raw_request)

    def recommend(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
    ) -> dict[str, Any]:
        return self._payload(raw_request, similar_requests)

    def correct_recommendation(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
        validation_error: str,
        allowed_similar_request_ids: set[int],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return self._payload(raw_request, similar_requests)

    @staticmethod
    def _payload(raw_request: str, similar_requests: list[SimilarRequest]) -> dict[str, Any]:
        return {
            "title": "Предварительный анализ обращения",
            "summary": raw_request,
            "category": "other",
            "priority": "P3",
            "reason": "Нужна проверка специалистом.",
            "affected_users": "unknown",
            "impact": "unknown",
            "workaround": "unknown",
            "analysis_status": "needs_information",
            "missing_information": ["Уточнить количество затронутых пользователей."],
            "recommended_action": "Проверить обращение.",
            "similar_request_ids": [request.id for request in similar_requests],
        }


def run_cli(
    session: ProcessingSession,
    *,
    input_stream: TextIO,
    output_stream: TextIO,
) -> SessionResult:
    output_stream.write("GigaBacklog Agent — offline prototype\n\nОпишите проблему:\n> ")
    output_stream.flush()
    raw_request = input_stream.readline().strip()
    output_stream.write("\n")

    def show_tool_result(tool_call: SearchToolCall, similar_requests: list[SimilarRequest]) -> None:
        output_stream.write(f"[tool] {tool_call.name}\n")
        output_stream.write(f"[tool] Найдено похожих обращений: {len(similar_requests)}\n")
        for request in similar_requests:
            output_stream.write(f"[tool] #{request.id}: {request.title}\n")

    def show_event(event: RunEvent) -> None:
        payload = json.dumps(event.payload, ensure_ascii=False, sort_keys=True)
        output_stream.write(f"[event {event.sequence}] {event.event_type} {payload}\n")

    def request_review(recommendation: Recommendation) -> SpecialistReview:
        output_stream.write("Рекомендация агента:\n")
        output_stream.write(f"Заголовок: {recommendation.title}\n")
        output_stream.write(f"Резюме: {recommendation.summary}\n\n")
        output_stream.write(f"Категория: {recommendation.category.value}\n")
        output_stream.write(f"Приоритет: {recommendation.priority.value}\n")
        output_stream.write(f"Обоснование: {recommendation.reason}\n")
        output_stream.write(f"Затронутые пользователи: {recommendation.affected_users}\n")
        output_stream.write(f"Влияние: {recommendation.impact.value}\n")
        output_stream.write(f"Обходной путь: {recommendation.workaround.value}\n")
        output_stream.write(f"Рекомендуемое действие: {recommendation.recommended_action}\n")
        similar_ids = ", ".join(map(str, recommendation.similar_request_ids)) or "нет"
        output_stream.write(f"Похожие обращения: {similar_ids}\n\n")
        if recommendation.analysis_status.value == "needs_information":
            output_stream.write("Недостающая информация:\n")
            for item in recommendation.missing_information:
                output_stream.write(f"- {item}\n")
            output_stream.write("\n")
        output_stream.write(
            "Решение специалиста:\n"
            "1. Принять рекомендацию\n"
            "2. Отклонить рекомендацию\n"
            "3. Не рассматривать сейчас\n> "
        )
        output_stream.flush()
        choice = input_stream.readline().strip()
        if choice == "1":
            output_stream.write("\n")
            return SpecialistReview(SpecialistDecision.ACCEPTED)
        if choice == "2":
            output_stream.write("Комментарий к отклонению:\n> ")
            output_stream.flush()
            comment = input_stream.readline().strip()
            output_stream.write("\n")
            return SpecialistReview(SpecialistDecision.REJECTED, comment)
        if choice == "3":
            output_stream.write("\n")
            return SpecialistReview(SpecialistDecision.NOT_REVIEWED)
        raise ValueError("Unknown specialist review decision")

    result = session.run(
        raw_request,
        request_review,
        tool_observer=show_tool_result,
        event_observer=show_event,
    )
    if result.terminal_status is TerminalStatus.VALIDATION_FAILED:
        output_stream.write(
            "Не удалось сформировать валидированную рекомендацию. "
            "Обращение сохранено без решения специалиста.\n"
        )
        return result

    output_stream.write(f"Решение сохранено. Run ID: {result.run_id}\n")
    return result


def main() -> None:
    store = SQLiteRunStore(Path("data") / "prototype.db")
    session = ProcessingSession(model=OfflineFakeGigaChat(), run_store=store)
    result = run_cli(session, input_stream=sys.stdin, output_stream=sys.stdout)
    if result.terminal_status is TerminalStatus.VALIDATION_FAILED:
        raise SystemExit(1)
