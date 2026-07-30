from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SpecialistDecision(StrEnum):
    """Decision recorded after a specialist reviews a recommendation."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NOT_REVIEWED = "not_reviewed"


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Minimal recommendation produced by the offline walking skeleton."""

    title: str
    summary: str


@dataclass(frozen=True, slots=True)
class SimilarRequest:
    """A historical request returned as context for a specialist."""

    id: int
    title: str
    summary: str


@dataclass(frozen=True, slots=True)
class SearchToolCall:
    """The only tool call the model may request in this processing slice."""

    name: str
    query: str


@dataclass(frozen=True, slots=True)
class SessionResult:
    """Observable outcome of one completed processing session."""

    raw_request: str
    recommendation: Recommendation
    review_status: SpecialistDecision
    run_id: int
