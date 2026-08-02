from __future__ import annotations

from typing import Any

from gigabacklog_agent.gigachat_adapter import create_gigachat_client
from gigabacklog_agent.gigachat_config import GigaChatSettings


class RecordingFactory:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def __call__(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return object()


def test_official_adapter_factory_forces_tls_and_disables_any_fallback(tmp_path) -> None:
    ca_bundle = tmp_path / "root-ca.pem"
    ca_bundle.write_text("certificate", encoding="utf-8")
    settings = GigaChatSettings.from_environment(
        {
            "GIGACHAT_CREDENTIALS": "not-a-real-key",
            "GIGACHAT_CA_BUNDLE_FILE": str(ca_bundle),
        }
    )
    factory = RecordingFactory()

    result = create_gigachat_client(settings, client_factory=factory)

    assert result is not None
    assert factory.kwargs == {
        "base_url": "https://api.giga.chat/v1",
        "credentials": "not-a-real-key",
        "scope": "GIGACHAT_API_PERS",
        "model": "GigaChat-2-Max",
        "verify_ssl_certs": True,
        "ca_bundle_file": str(ca_bundle),
        "max_retries": 2,
        "retry_backoff_factor": 0.5,
    }
