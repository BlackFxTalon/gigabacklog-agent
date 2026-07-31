from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import (
    Recommendation,
    RequestAnalysis,
    SearchToolCall,
    SessionResult,
    SimilarRequest,
    SpecialistDecision,
    TerminalStatus,
    validate_request_analysis,
)


class RecommendationModel(Protocol):
    """Model adapter used by a processing session."""

    def create_search_tool_call(self, raw_request: str) -> SearchToolCall: ...

    def recommend(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
    ) -> dict[str, Any]: ...

    def correct_recommendation(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
        validation_error: str,
        allowed_similar_request_ids: set[int],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]: ...


class SessionState(TypedDict, total=False):
    raw_request: str
    search_call: SearchToolCall
    similar_requests: list[SimilarRequest]
    recommendation: Recommendation | None
    review_status: SpecialistDecision
    terminal_status: TerminalStatus
    run_id: int


ReviewDecisionProvider = Callable[[Recommendation], SpecialistDecision]
ToolObserver = Callable[[SearchToolCall, list[SimilarRequest]], None]


class ProcessingSession:
    """Run the complete offline workflow behind one small interface."""

    def __init__(self, model: RecommendationModel, run_store: SQLiteRunStore) -> None:
        self._model = model
        self._run_store = run_store

    def run(
        self,
        raw_request: str,
        review_decision_provider: ReviewDecisionProvider,
        tool_observer: ToolObserver | None = None,
    ) -> SessionResult:
        raw_request = raw_request.strip()
        if not raw_request:
            raise ValueError("Request must not be empty")

        graph = StateGraph(SessionState)  # ty: ignore[invalid-argument-type]

        def request_search(state: SessionState) -> SessionState:
            for _ in range(2):
                tool_call = self._model.create_search_tool_call(state["raw_request"])
                if tool_call.name == "search_similar_requests" and tool_call.query.strip():
                    return {"search_call": tool_call}
            raise ValueError("Model did not produce a valid search tool call")

        def search(state: SessionState) -> SessionState:
            tool_call = state["search_call"]
            similar_requests = self._run_store.search_similar_requests(tool_call.query)
            if tool_observer is not None:
                tool_observer(tool_call, similar_requests)
            return {"similar_requests": similar_requests}

        def recommend(state: SessionState) -> SessionState:
            allowed_ids = {request.id for request in state["similar_requests"]}
            payload = self._model.recommend(state["raw_request"], state["similar_requests"])
            for attempt in range(2):
                try:
                    analysis: RequestAnalysis = validate_request_analysis(payload, allowed_ids)
                    return {
                        "recommendation": Recommendation(
                            title=analysis.title,
                            summary=analysis.summary,
                            category=analysis.category,
                            priority=analysis.priority,
                            reason=analysis.reason,
                            affected_users=analysis.affected_users,
                            impact=analysis.impact,
                            workaround=analysis.workaround,
                            analysis_status=analysis.analysis_status,
                            missing_information=analysis.missing_information,
                            recommended_action=analysis.recommended_action,
                            similar_request_ids=analysis.similar_request_ids,
                        ),
                        "terminal_status": TerminalStatus.COMPLETED,
                    }
                except (ValueError, TypeError) as error:
                    if attempt == 1:
                        return {
                            "recommendation": None,
                            "review_status": SpecialistDecision.NOT_REVIEWED,
                            "terminal_status": TerminalStatus.VALIDATION_FAILED,
                        }
                    payload = self._model.correct_recommendation(
                        state["raw_request"],
                        state["similar_requests"],
                        str(error),
                        allowed_ids,
                        RequestAnalysis.model_json_schema(),
                    )
            raise AssertionError("Validation retry loop must return")

        def review(state: SessionState) -> SessionState:
            recommendation = state["recommendation"]
            if recommendation is None:
                raise AssertionError("A validation failure must bypass human review")
            return {"review_status": review_decision_provider(recommendation)}

        def persist(state: SessionState) -> SessionState:
            return {
                "run_id": self._run_store.save_run(
                    raw_request=state["raw_request"],
                    recommendation=state["recommendation"],
                    review_status=state["review_status"],
                    terminal_status=state["terminal_status"],
                )
            }

        def next_after_recommendation(state: SessionState) -> str:
            if state["terminal_status"] is TerminalStatus.VALIDATION_FAILED:
                return "persist"
            return "review"

        graph.add_node("request_search", request_search)
        graph.add_node("search", search)
        graph.add_node("recommend", recommend)
        graph.add_node("review", review)
        graph.add_node("persist", persist)
        graph.add_edge(START, "request_search")
        graph.add_edge("request_search", "search")
        graph.add_edge("search", "recommend")
        graph.add_conditional_edges("recommend", next_after_recommendation)
        graph.add_edge("review", "persist")
        graph.add_edge("persist", END)

        initial_state: SessionState = {"raw_request": raw_request}
        final_state = graph.compile().invoke(initial_state)  # ty: ignore[invalid-argument-type]
        return SessionResult(
            raw_request=final_state["raw_request"],
            recommendation=final_state["recommendation"],
            review_status=final_state["review_status"],
            terminal_status=final_state["terminal_status"],
            run_id=final_state["run_id"],
        )
