from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import Recommendation, SessionResult, SpecialistDecision


class OfflineFakeGigaChat:
    """Temporary deterministic adapter for the first offline walking skeleton."""

    def recommend(self, raw_request: str) -> Recommendation:
        return Recommendation(
            title="Предварительный анализ обращения",
            summary=raw_request,
        )


def run_cli(
    session: ProcessingSession,
    *,
    input_stream: TextIO,
    output_stream: TextIO,
) -> SessionResult:
    output_stream.write("GigaBacklog Agent — offline prototype\n\n")
    output_stream.write("Опишите проблему:\n> ")
    output_stream.flush()
    raw_request = input_stream.readline().strip()
    output_stream.write("\n")

    def request_review(recommendation: Recommendation) -> SpecialistDecision:
        output_stream.write("Рекомендация агента:\n")
        output_stream.write(f"Заголовок: {recommendation.title}\n")
        output_stream.write(f"Резюме: {recommendation.summary}\n\n")
        output_stream.write("Решение специалиста:\n")
        output_stream.write("1. Принять рекомендацию\n> ")
        output_stream.flush()
        choice = input_stream.readline().strip()
        output_stream.write("\n")
        if choice != "1":
            raise ValueError("The offline walking skeleton only supports acceptance")
        return SpecialistDecision.ACCEPTED

    result = session.run(raw_request, request_review)
    output_stream.write(f"Решение сохранено. Run ID: {result.run_id}\n")
    return result


def main() -> None:
    store = SQLiteRunStore(Path("data") / "prototype.db")
    session = ProcessingSession(model=OfflineFakeGigaChat(), run_store=store)
    run_cli(session, input_stream=sys.stdin, output_stream=sys.stdout)
