from __future__ import annotations

from collections.abc import Callable

from gigabacklog_agent.application import ProcessingSession
from gigabacklog_agent.database import SQLiteRunStore
from gigabacklog_agent.gigachat_adapter import (
    GigaChatBridgeClient,
    GigaChatRecommendationModel,
    create_gigachat_client,
)
from gigabacklog_agent.gigachat_config import GigaChatSettings


def create_live_processing_session(
    run_store: SQLiteRunStore,
    *,
    environ: dict[str, str] | None = None,
    client_factory: Callable[..., GigaChatBridgeClient] = create_gigachat_client,
) -> ProcessingSession:
    """Create the live opt-in session; construction itself sends no request."""
    settings = GigaChatSettings.from_environment(environ)
    return ProcessingSession(
        model=GigaChatRecommendationModel(client_factory(settings)),
        run_store=run_store,
    )
