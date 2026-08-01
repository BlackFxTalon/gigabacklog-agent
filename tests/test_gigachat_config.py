from __future__ import annotations

import pytest

from gigabacklog_agent.gigachat_config import (
    DEFAULT_MODEL,
    PERSONAL_SCOPE,
    GigaChatConfigurationError,
    GigaChatSettings,
)


def test_gigachat_settings_force_personal_scope_tls_and_default_model() -> None:
    settings = GigaChatSettings.from_environment({"GIGACHAT_CREDENTIALS": "test-key"})

    assert settings.model == DEFAULT_MODEL
    assert settings.scope == PERSONAL_SCOPE
    assert settings.ca_bundle_file is None
    assert settings.max_retries == 2


def test_gigachat_settings_allow_model_and_existing_ca_bundle_override(tmp_path) -> None:
    ca_bundle = tmp_path / "root-ca.pem"
    ca_bundle.write_text("certificate", encoding="utf-8")

    settings = GigaChatSettings.from_environment(
        {
            "GIGACHAT_CREDENTIALS": "test-key",
            "GIGACHAT_MODEL": "GigaChat-2-Pro",
            "GIGACHAT_CA_BUNDLE_FILE": str(ca_bundle),
        }
    )

    assert settings.model == "GigaChat-2-Pro"
    assert settings.ca_bundle_file == ca_bundle


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"GIGACHAT_CREDENTIALS": "   "},
        {"GIGACHAT_CREDENTIALS": "x", "GIGACHAT_CA_BUNDLE_FILE": "missing.pem"},
    ],
)
def test_gigachat_settings_reject_missing_credentials_or_ca_bundle(environ: dict[str, str]) -> None:
    with pytest.raises(GigaChatConfigurationError):
        GigaChatSettings.from_environment(environ)
