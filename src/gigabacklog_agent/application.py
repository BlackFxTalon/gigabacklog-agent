from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import (
    Recommendation,
    SearchToolCall,
    SessionResult,
    SimilarRequest,
    SpecialistDecision,
)


class RecommendationModel(Protocol):
    """Model adapter used by a processing session."""

    def create_search_tool_call(self, raw_request: str) -> SearchToolCall: ...

    def recommend(
        self,
        raw_request: str,
        similar_requests: list[SimilarRequest],
    ) -> Recommendation: ...


class SessionState(TypedDict, total=False):
    raw_request: str
    search_call: SearchToolCall
    similar_requests: list[SimilarRequest]
    recommendation: Recommendation
    review_status: SpecialistDecision
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
            return {
                "recommendation": self._model.recommend(
                    state["raw_request"], state["similar_requests"]
                )
            }

        def review(state: SessionState) -> SessionState:
            return {"review_status": review_decision_provider(state["recommendation"])}

        def persist(state: SessionState) -> SessionState:
            return {
                "run_id": self._run_store.save_run(
                    raw_request=state["raw_request"],
                    recommendation=state["recommendation"],
                    review_status=state["review_status"],
                )
            }

        graph.add_node("request_search", request_search)
        graph.add_node("search", search)
        graph.add_node("recommend", recommend)
        graph.add_node("review", review)
        graph.add_node("persist", persist)
        graph.add_edge(START, "request_search")
        graph.add_edge("request_search", "search")
        graph.add_edge("search", "recommend")
        graph.add_edge("recommend", "review")
        graph.add_edge("review", "persist")
        graph.add_edge("persist", END)

        initial_state: SessionState = {"raw_request": raw_request}
        final_state = graph.compile().invoke(initial_state)  # ty: ignore[invalid-argument-type]
        return SessionResult(
            raw_request=final_state["raw_request"],
            recommendation=final_state["recommendation"],
            review_status=final_state["review_status"],
            run_id=final_state["run_id"],
        )
