from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "GigaChat-2-Max"
PERSONAL_SCOPE = "GIGACHAT_API_PERS"


class GigaChatConfigurationError(ValueError):
    """Safe configuration failure for the official GigaChat adapter."""


@dataclass(frozen=True, slots=True)
class GigaChatSettings:
    """Validated provider settings with TLS verification permanently enabled."""

    credentials: str
    model: str
    scope: str
    ca_bundle_file: Path | None
    max_retries: int = 2
    retry_backoff_factor: float = 0.5

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> GigaChatSettings:
        values = os.environ if environ is None else environ
        credentials = values.get("GIGACHAT_CREDENTIALS", "").strip()
        if not credentials:
            raise GigaChatConfigurationError("Не задана переменная GIGACHAT_CREDENTIALS")

        model = values.get("GIGACHAT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        ca_bundle_value = values.get("GIGACHAT_CA_BUNDLE_FILE", "").strip()
        ca_bundle_file = Path(ca_bundle_value) if ca_bundle_value else None
        if ca_bundle_file is not None and not ca_bundle_file.is_file():
            raise GigaChatConfigurationError(
                "Файл CA bundle для GigaChat не найден. Инструкция: "
                "https://developers.sber.ru/docs/ru/gigachat/certificates"
            )

        return cls(
            credentials=credentials,
            model=model,
            scope=PERSONAL_SCOPE,
            ca_bundle_file=ca_bundle_file,
        )
