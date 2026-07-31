from __future__ import annotations

import pytest

from gigabacklog_agent.models import SpecialistDecision, SpecialistReview


def test_rejected_review_requires_a_non_empty_comment() -> None:
    with pytest.raises(ValueError, match="requires a comment"):
        SpecialistReview(SpecialistDecision.REJECTED, "  ")


def test_accepted_review_allows_no_comment() -> None:
    review = SpecialistReview(SpecialistDecision.ACCEPTED)

    assert review.comment is None
