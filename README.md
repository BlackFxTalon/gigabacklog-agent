# GigaBacklog Agent

[![Offline quality gates](https://github.com/BlackFxTalon/gigabacklog-agent/actions/workflows/quality.yml/badge.svg)](https://github.com/BlackFxTalon/gigabacklog-agent/actions/workflows/quality.yml)

Русскоязычное portfolio demo для первичной обработки внутренних обращений сервисным специалистом. Агент **не выполняет внешних действий**: он находит похожие обращения, предлагает структурированную рекомендацию, а специалист принимает или отклоняет её. Решение и безопасный аудит сохраняются в SQLite.

> Это демонстрационный прототип, не production-система. Не используйте его для персональных, банковских или иных чувствительных реальных данных. Границы prompt-injection защиты намеренно ограничены структурным разделением trusted policy и untrusted input; это не полноценная security boundary.

## Проблема и сценарий

Специалист получает свободный текст внутреннего обращения. Для каждого непустого обращения workflow ровно один раз ищет похожие обращения в локальной SQLite-базе, формирует рекомендацию, валидирует её и запрашивает human review.

Канонический happy path: массовый сбой авторизации после обновления → `incident` / `P1` / `department`, найден релевантный прецедент, решение специалиста — `accepted`.

```text
CLI → explicit LangGraph StateGraph → named search_similar_requests tool → SQLite
                                           ↓
                                  GigaChat / offline adapter
                                           ↓
                          Pydantic + provenance validation → human review → audit
```

LLM не получает SQL-инструмент и не может выполнять произвольные действия. Модель формирует только поисковый запрос; поиск выполняет приложение.

## Quick start (offline, без credentials)

Требования: Python 3.11 и [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --all-groups
uv run python scripts/seed_database.py --reset
uv run gigabacklog
```

Введите обращение, например:

```text
После обновления весь отдел продаж не может войти в систему заявок.
```

Затем выберите `1`, чтобы принять рекомендацию. Offline adapter детерминирован и предназначен для демонстрации workflow без внешнего API.

### Пример CLI-сессии

```text
[tool] search_similar_requests
[tool] Найдено похожих обращений: 1
Рекомендация агента:
Категория: incident
Приоритет: P1
Затронутые пользователи: department
Решение специалиста:
1. Принять рекомендацию
...
Решение сохранено. Run ID: 1
```

## Quality gate

Эта последовательность соответствует GitHub Actions и не вызывает внешние API:

```bash
uv run pytest -q -m "not integration"
uv run ruff check .
uv run ruff format --check .
uvx ty check src tests
uv lock --check
uv build
```

## Reset local demo data

SQLite-база локальна и не коммитится. Полностью пересоздать synthetic history и audit records:

```bash
uv run python scripts/seed_database.py --reset
```

По умолчанию используется `data/prototype.db`; можно указать другой путь через `--database`.

## Optional live GigaChat mode

Обычный запуск всегда offline. Для явно выбранного официального GigaChat adapter задайте переменные окружения по примеру `.env.example`; этот reference-файл не загружается CLI автоматически и не содержит секретов:

```bash
export GIGACHAT_LIVE=1
export GIGACHAT_CREDENTIALS="<authorization-key>"
export GIGACHAT_MODEL="GigaChat-2-Max" # optional override
export GIGACHAT_CA_BUNDLE_FILE="/path/to/ca.pem" # optional
uv run gigabacklog
```

По умолчанию используется `GigaChat-2-Max` и scope `GIGACHAT_API_PERS`. TLS verification всегда включена; отключающей переменной или флага нет. Для CA/certificate guidance: https://developers.sber.ru/docs/ru/gigachat/certificates

Live smoke test запускается **только** при явном opt-in и credentials:

```bash
RUN_GIGACHAT_INTEGRATION=1 GIGACHAT_CREDENTIALS="<authorization-key>" uv run pytest -m integration -q
```

Никогда не коммитьте `.env`, authorization key или локальную SQLite-базу.

## GigaChat v2 и upstream LangGraph

Production adapter использует официальный GigaChat v2 SDK: `client.chat.create()` для принудительного именованного function call и для JSON Schema через `ChatResponseFormat(..., strict=True)`. До публикации совместимого PyPI-релиза SDK закреплён по immutable official Git SHA; причина и правила замены описаны в [ADR-0003](docs/adr/0003-pinned-gigachat-v2-sdk-source.md). Полный live-контракт `RequestAnalysis` пока заблокирован поведением provider и отслеживается в [upstream issue #122](https://github.com/ai-forever/gigachat/issues/122); free-form fallback не используется. Orchestration остаётся явным upstream [`langgraph`](https://langchain-ai.github.io/langgraph/) `StateGraph`; `langchain-gigachat`, deprecated GigaChain/GigaGraph packages и prebuilt `create_react_agent` не используются.

## License

[MIT](LICENSE). Видео намеренно не входит в scope репозитория.
