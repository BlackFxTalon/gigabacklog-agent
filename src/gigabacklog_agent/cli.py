from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import (
    Recommendation,
    SearchToolCall,
    SessionResult,
    SimilarRequest,
    SpecialistDecision,
)


class OfflineFakeGigaChat:
    """Temporary deterministic adapter for the offline walking skeleton."""

    def create_search_tool_call(self, raw_request: str) -> SearchToolCall:
        return SearchToolCall(name="search_similar_requests", query=raw_request)

    def recommend(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
    ) -> Recommendation:
        return Recommendation(title="Предварительный анализ обращения", summary=raw_request)


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
        output_stream.write(f"[tool] {tool_call.name}(query={tool_call.query!r})\n")
        output_stream.write(f"[tool] Найдено похожих обращений: {len(similar_requests)}\n")
        for request in similar_requests:
            output_stream.write(f"[tool] #{request.id}: {request.title}\n")

    def request_review(recommendation: Recommendation) -> SpecialistDecision:
        output_stream.write("Рекомендация агента:\n")
        output_stream.write(f"Заголовок: {recommendation.title}\n")
        output_stream.write(f"Резюме: {recommendation.summary}\n\n")
        output_stream.write("Решение специалиста:\n1. Принять рекомендацию\n> ")
        output_stream.flush()
        if input_stream.readline().strip() != "1":
            raise ValueError("The offline walking skeleton only supports acceptance")
        output_stream.write("\n")
        return SpecialistDecision.ACCEPTED

    result = session.run(raw_request, request_review, show_tool_result)
    output_stream.write(f"Решение сохранено. Run ID: {result.run_id}\n")
    return result


def main() -> None:
    store = SQLiteRunStore(Path("data") / "prototype.db")
    session = ProcessingSession(model=OfflineFakeGigaChat(), run_store=store)
    run_cli(session, input_stream=sys.stdin, output_stream=sys.stdout)
