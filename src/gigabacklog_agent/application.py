from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.models import (
    ModelContext,
    Recommendation,
    RequestAnalysis,
    RunEvent,
    SearchToolCall,
    SessionResult,
    SimilarRequest,
    SpecialistDecision,
    SpecialistReview,
    TerminalStatus,
    validate_request_analysis,
)


class RecommendationModel(Protocol):
    """Model adapter used by a processing session."""

    def create_search_tool_call(self, raw_request: str) -> SearchToolCall: ...

    def recommend(self, context: ModelContext) -> dict[str, Any]: ...

    def correct_recommendation(
        self,
        context: ModelContext,
        validation_error: str,
        allowed_similar_request_ids: set[int],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]: ...


class SessionState(TypedDict, total=False):
    raw_request: str
    search_call: SearchToolCall
    similar_requests: list[SimilarRequest]
    recommendation: Recommendation | None
    review: SpecialistReview
    terminal_status: TerminalStatus
    run_id: int


ReviewDecisionProvider = Callable[[Recommendation], SpecialistReview]
ToolObserver = Callable[[SearchToolCall, list[SimilarRequest]], None]
EventObserver = Callable[[RunEvent], None]


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
        event_observer: EventObserver | None = None,
    ) -> SessionResult:
        events: list[RunEvent] = []

        def emit(event_type: str, payload: dict[str, object]) -> None:
            event = RunEvent(sequence=len(events) + 1, event_type=event_type, payload=payload)
            events.append(event)
            if event_observer is not None:
                event_observer(event)

        raw_request = raw_request.strip()
        if not raw_request:
            raise ValueError("Request must not be empty")
        if len(raw_request) > 4000:
            raise ValueError("Длина обращения не должна превышать 4 000 символов")

        graph = StateGraph(SessionState)  # ty: ignore[invalid-argument-type]

        def request_search(state: SessionState) -> SessionState:
            for attempt in range(2):
                try:
                    tool_call = self._model.create_search_tool_call(state["raw_request"])
                except Exception:
                    emit("model_failure", {"stage": "search_tool_call", "outcome": "failed"})
                    return {
                        "recommendation": None,
                        "review": SpecialistReview(SpecialistDecision.NOT_REVIEWED),
                        "terminal_status": TerminalStatus.MODEL_FAILED,
                    }
                if tool_call.name == "search_similar_requests" and tool_call.query.strip():
                    emit(
                        "model_stage",
                        {"stage": "search_tool_call", "outcome": "tool_call_requested"},
                    )
                    return {"search_call": tool_call}
                emit("model_protocol", {"attempt": attempt + 1, "outcome": "failed"})
            return {
                "recommendation": None,
                "review": SpecialistReview(SpecialistDecision.NOT_REVIEWED),
                "terminal_status": TerminalStatus.MODEL_PROTOCOL_FAILED,
            }

        def search(state: SessionState) -> SessionState:
            tool_call = state["search_call"]
            emit("tool_input", {"tool_name": tool_call.name})
            try:
                similar_requests = self._run_store.search_similar_requests(tool_call.query)
            except Exception:
                emit("tool_failure", {"tool_name": tool_call.name, "outcome": "failed"})
                return {
                    "recommendation": None,
                    "review": SpecialistReview(SpecialistDecision.NOT_REVIEWED),
                    "terminal_status": TerminalStatus.TOOL_FAILED,
                }
            emit(
                "tool_output",
                {
                    "similar_request_count": len(similar_requests),
                    "similar_request_ids": [request.id for request in similar_requests],
                },
            )
            if tool_observer is not None:
                tool_observer(tool_call, similar_requests)
            return {"similar_requests": similar_requests}

        def recommend(state: SessionState) -> SessionState:
            allowed_ids = {request.id for request in state["similar_requests"]}
            emit("model_stage", {"stage": "recommendation", "outcome": "response_requested"})
            try:
                context = ModelContext.from_untrusted_inputs(
                    state["raw_request"], state["similar_requests"]
                )
                payload = self._model.recommend(context)
            except Exception:
                emit("model_failure", {"stage": "recommendation", "outcome": "failed"})
                return {
                    "recommendation": None,
                    "review": SpecialistReview(SpecialistDecision.NOT_REVIEWED),
                    "terminal_status": TerminalStatus.MODEL_FAILED,
                }
            for attempt in range(2):
                try:
                    analysis: RequestAnalysis = validate_request_analysis(payload, allowed_ids)
                    emit("validation", {"attempt": attempt + 1, "outcome": "passed"})
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
                except (ValueError, TypeError):
                    emit("validation", {"attempt": attempt + 1, "outcome": "failed"})
                    if attempt == 1:
                        return {
                            "recommendation": None,
                            "review": SpecialistReview(SpecialistDecision.NOT_REVIEWED),
                            "terminal_status": TerminalStatus.VALIDATION_FAILED,
                        }
                    emit(
                        "model_stage",
                        {"stage": "recommendation_correction", "outcome": "response_requested"},
                    )
                    try:
                        payload = self._model.correct_recommendation(
                            context,
                            "Recommendation did not match the required schema.",
                            allowed_ids,
                            RequestAnalysis.model_json_schema(),
                        )
                    except Exception:
                        emit(
                            "model_failure",
                            {"stage": "recommendation_correction", "outcome": "failed"},
                        )
                        return {
                            "recommendation": None,
                            "review": SpecialistReview(SpecialistDecision.NOT_REVIEWED),
                            "terminal_status": TerminalStatus.MODEL_FAILED,
                        }
            raise AssertionError("Validation retry loop must return")

        def review(state: SessionState) -> SessionState:
            recommendation = state["recommendation"]
            if recommendation is None:
                raise AssertionError("A validation failure must bypass human review")
            return {"review": review_decision_provider(recommendation)}

        def persist(state: SessionState) -> SessionState:
            review = state["review"]
            emit(
                "review",
                {
                    "decision": review.decision.value,
                    "comment_recorded": bool((review.comment or "").strip()),
                },
            )
            return {
                "run_id": self._run_store.save_run(
                    raw_request=state["raw_request"],
                    recommendation=state["recommendation"],
                    review_status=review.decision,
                    review_comment=review.comment,
                    terminal_status=state["terminal_status"],
                    events=events,
                )
            }

        def next_after_search(state: SessionState) -> str:
            if state.get("terminal_status") is TerminalStatus.TOOL_FAILED:
                return "persist"
            return "recommend"

        def next_after_recommendation(state: SessionState) -> str:
            if state["terminal_status"] in {
                TerminalStatus.VALIDATION_FAILED,
                TerminalStatus.MODEL_FAILED,
            }:
                return "persist"
            return "review"

        def next_after_request_search(state: SessionState) -> str:
            if state.get("terminal_status") in {
                TerminalStatus.MODEL_PROTOCOL_FAILED,
                TerminalStatus.MODEL_FAILED,
            }:
                return "persist"
            return "search"

        graph.add_node("request_search", request_search)
        graph.add_node("search", search)
        graph.add_node("recommend", recommend)
        graph.add_node("review", review)
        graph.add_node("persist", persist)
        graph.add_edge(START, "request_search")
        graph.add_conditional_edges("request_search", next_after_request_search)
        graph.add_conditional_edges("search", next_after_search)
        graph.add_conditional_edges("recommend", next_after_recommendation)
        graph.add_edge("review", "persist")
        graph.add_edge("persist", END)

        initial_state: SessionState = {"raw_request": raw_request}
        final_state = graph.compile().invoke(initial_state)  # ty: ignore[invalid-argument-type]
        return SessionResult(
            raw_request=final_state["raw_request"],
            recommendation=final_state["recommendation"],
            review_status=final_state["review"].decision,
            review_comment=final_state["review"].comment,
            terminal_status=final_state["terminal_status"],
            run_id=final_state["run_id"],
        )
