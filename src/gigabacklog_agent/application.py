from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import Recommendation, SessionResult, SpecialistDecision


class RecommendationModel(Protocol):
    """Model adapter used by a processing session."""

    def recommend(self, raw_request: str) -> Recommendation: ...


class SessionState(TypedDict, total=False):
    raw_request: str
    recommendation: Recommendation
    review_status: SpecialistDecision
    run_id: int


ReviewDecisionProvider = Callable[[Recommendation], SpecialistDecision]


class ProcessingSession:
    """Run the complete offline workflow behind one small interface."""

    def __init__(self, model: RecommendationModel, run_store: SQLiteRunStore) -> None:
        self._model = model
        self._run_store = run_store

    def run(
        self,
        raw_request: str,
        review_decision_provider: ReviewDecisionProvider,
    ) -> SessionResult:
        raw_request = raw_request.strip()
        if not raw_request:
            raise ValueError("Request must not be empty")

        # LangGraph supports TypedDict schemas at runtime; ty cannot resolve its bound.
        graph = StateGraph(SessionState)  # ty: ignore[invalid-argument-type]

        def recommend(state: SessionState) -> SessionState:
            return {"recommendation": self._model.recommend(state["raw_request"])}

        def review(state: SessionState) -> SessionState:
            return {
                "review_status": review_decision_provider(state["recommendation"]),
            }

        def persist(state: SessionState) -> SessionState:
            run_id = self._run_store.save_run(
                raw_request=state["raw_request"],
                recommendation=state["recommendation"],
                review_status=state["review_status"],
            )
            return {"run_id": run_id}

        graph.add_node("recommend", recommend)
        graph.add_node("review", review)
        graph.add_node("persist", persist)
        graph.add_edge(START, "recommend")
        graph.add_edge("recommend", "review")
        graph.add_edge("review", "persist")
        graph.add_edge("persist", END)

        initial_state: SessionState = {"raw_request": raw_request}
        final_state = graph.compile().invoke(
            initial_state  # ty: ignore[invalid-argument-type]
        )
        return SessionResult(
            raw_request=final_state["raw_request"],
            recommendation=final_state["recommendation"],
            review_status=final_state["review_status"],
            run_id=final_state["run_id"],
        )
