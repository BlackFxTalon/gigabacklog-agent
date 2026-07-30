# Рекомендуемый Python-стек GigaChat + LangGraph для GigaBacklog Agent

**Срез состояния:** 31 июля 2026 года.  
**Область:** Python, доступ физического лица (`GIGACHAT_API_PERS`), явный `langgraph.graph.StateGraph`.  
**Метод:** официальная документация GigaChat/Sber, официальные репозитории и метаданные PyPI, официальная документация LangChain/LangGraph. Вторичные источники не использовались.

## Краткий вывод

Для нового GigaBacklog Agent следует использовать обычный upstream-стек LangChain/LangGraph и отдельную официальную интеграцию GigaChat:

```text
Python >=3.10,<4
langchain-gigachat==0.5.1
gigachat==0.2.1
langgraph==1.2.10
langchain==1.3.14       # нужен для langchain.agents.create_agent; для чистого StateGraph не обязателен напрямую
```

На дату среза это последние стабильные версии в официальных PyPI-проектах: [`langchain-gigachat` 0.5.1](https://pypi.org/project/langchain-gigachat/), [`gigachat` 0.2.1](https://pypi.org/project/gigachat/), [`langgraph` 1.2.10](https://pypi.org/project/langgraph/) и [`langchain` 1.3.14](https://pypi.org/project/langchain/). `langchain-gigachat` требует Python `>=3.10,<4`, `langchain-core>=1,<2` и `gigachat>=0.2.1,<0.3`; это зафиксировано и в [официальном `pyproject.toml`](https://github.com/ai-forever/langchain-gigachat/blob/master/libs/gigachat/pyproject.toml).

**Не устанавливать** `gigachain`, `gigagraph` или старые пакеты семейства `gigachain-*`. Официальные PyPI-метаданные версий `100.0.4` прямо помечают [`gigachain`](https://pypi.org/project/gigachain/) и [`gigagraph`](https://pypi.org/project/gigagraph/) как deprecated и требуют перейти на чистые `langchain` + `langchain_gigachat` и удалить все `gigachain-*`. Репозиторий GigaChain также называет [`langchain-gigachat` интеграционной библиотекой для LangChain и LangGraph](https://github.com/ai-forever/gigachain#python).

Практический pin для `pyproject.toml`:

```toml
requires-python = ">=3.10,<4"
dependencies = [
  "gigachat==0.2.1",
  "langchain-gigachat==0.5.1",
  "langgraph==1.2.10",
  # Добавлять только если нужен create_agent или другие API верхнего уровня:
  "langchain==1.3.14",
]
```

## 1. Какие пакеты за что отвечают

| Пакет | Назначение | Рекомендация |
|---|---|---|
| `gigachat` | Официальный низкоуровневый Python SDK для REST API; OAuth, HTTP, модели запроса/ответа | Оставить явным pin, хотя он транзитивно устанавливается интеграцией |
| `langchain-gigachat` | Официальный `BaseChatModel`/embeddings-адаптер GigaChat для LangChain | Основной LLM-адаптер: `from langchain_gigachat import GigaChat` |
| `langgraph` | Upstream runtime и Graph API (`StateGraph`, `ToolNode`, checkpointers) | Использовать напрямую |
| `langchain` | Высокоуровневый `create_agent`, middleware и agent structured-output strategies | Не нужен для собственного цикла `StateGraph`; нужен, если выбран `create_agent` |
| `gigachain`, `gigagraph`, `gigachain-*` | Старые fork/namespace-пакеты | Не использовать, удалить |

Официальный README интеграции говорит, что `langchain-gigachat` оборачивает GigaChat Python SDK интерфейсами LangChain и поддерживает structured output ([README](https://github.com/ai-forever/langchain-gigachat/blob/master/libs/gigachat/README.md)).

## 2. Модели, доступные физическому лицу

Официальная страница выбора модели перечисляет следующие актуальные ID ([«Выбор модели для генерации»](https://developers.sber.ru/docs/ru/gigachat/guides/selecting-a-model)):

- `GigaChat-2` — Lite, скорость/стоимость;
- `GigaChat-2-Pro` — лучшее следование сложным инструкциям;
- `GigaChat-2-Max` — сложные задачи, качество и креативность;
- `GigaChat-3-Ultra` — новая модель только для физических лиц в freemium.

Тарифная страница физлиц дополнительно подтверждает рабочие алиасы и лимиты ([«Тарифы GigaChat API для физлиц»](https://developers.sber.ru/docs/ru/gigachat/tariffs/individual-tariffs)):

| Семейство | Рекомендуемый явный ID | Совместимый алиас | Freemium на 12 месяцев |
|---|---|---|---:|
| Lite | `GigaChat-2` | `GigaChat` | 250 млн токенов |
| Pro | `GigaChat-2-Pro` | `GigaChat-Pro` | 40 млн токенов |
| Max | `GigaChat-2-Max` | `GigaChat-Max` | 25 млн токенов |
| Ultra | `GigaChat-3-Ultra` | — | 50 млн токенов |

`GigaChat-3-Ultra` на дату среза доступна физлицам **только** в freemium; платные тарифы физлиц и юрлиц доступа к Ultra пока не имеют ([официальная страница Ultra](https://developers.sber.ru/docs/ru/gigachat/models/gigachat-3-ultra)).

**Рекомендация для агента:** начать с `GigaChat-2-Max`, потому что официальные примеры function calling и native JSON Schema документированы именно на Max; сделать имя модели конфигурируемым и отдельно прогнать контрактные тесты на `GigaChat-3-Ultra` перед переключением. Наличие модели в аккаунте в рантайме проверять через `GET /v1/models`; этот метод возвращает массив реально доступных моделей, а preview-модели имеют суффикс `-preview` ([справка `GET /models`](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/get-models)).

## 3. Authentication и SSL

### 3.1. OAuth для физлица

1. В Studio создаётся проект GigaChat API и получается **Authorization Key** — Base64 от `Client ID:Client Secret` (или готовое значение из кабинета).
2. Этот ключ передаётся по Basic-схеме в `POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth` вместе с обязательным UUIDv4 `RqUID` и `scope=GIGACHAT_API_PERS`.
3. Возвращаемый Access token используется по Bearer-схеме и действует 30 минут. SDK сам получает/обновляет токен при передаче `credentials`.

Это описано в [быстром старте для физлиц](https://developers.sber.ru/docs/ru/gigachat/quickstart/ind-using-api) и в [справке OAuth endpoint](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-token). Допустимые scope: `GIGACHAT_API_PERS`, `GIGACHAT_API_B2B`, `GIGACHAT_API_CORP`; для данного проекта нужен первый.

Рекомендуемая конфигурация:

```python
import os
from langchain_gigachat import GigaChat

llm = GigaChat(
    credentials=os.environ["GIGACHAT_CREDENTIALS"],
    scope="GIGACHAT_API_PERS",
    base_url="https://api.giga.chat/v1",
    model=os.getenv("GIGACHAT_MODEL", "GigaChat-2-Max"),
    ca_bundle_file=os.environ["GIGACHAT_CA_BUNDLE_FILE"],
    # verify_ssl_certs=True — не отключать в production
)
```

Не хранить Authorization Key или 30-минутный Access token в Git. Предпочтительно хранить `GIGACHAT_CREDENTIALS` в secret manager; не реализовывать ручное кеширование токена поверх SDK без необходимости.

### 3.2. Сертификаты

GigaChat требует корневой сертификат НУЦ Минцифры; без него OAuth/SDK могут завершаться `CERTIFICATE_VERIFY_FAILED`. Официально поддерживаются установка в trust store ОС, добавление в certifi либо передача пути через `ca_bundle_file` ([«Использование сертификатов НУЦ Минцифры»](https://developers.sber.ru/docs/ru/gigachat/certificates)).

Для production:

- скачать сертификат из официального источника Госуслуг;
- установить в системное хранилище либо передать `ca_bundle_file`;
- сохранить проверку TLS включённой.

`verify_ssl_certs=False` встречается в примерах документации как упрощение, но фактически отключает проверку подлинности сервера; для production это не рекомендуемый способ исправления сертификатов.

## 4. Tool calling и `tool_choice`

### 4.1. Нативный API GigaChat

В REST API транспорт остаётся **function-oriented**: запрос содержит `functions` и `function_call`, а ответ — `function_call` и `functions_state_id`. Официально поддерживаются три режима ([режимы работы с функциями](https://developers.sber.ru/docs/ru/gigachat/guides/functions/function-calling-modes), [справка `POST /chat/completions`](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-chat)):

- `"none"` — отключить функции;
- `"auto"` — модель решает, вызывать ли функцию;
- `{"name": "function_name"}` — принудительно вызвать конкретную функцию.

### 4.2. Адаптер LangChain

`langchain-gigachat` предоставляет стандартный `bind_tools(...)`, переводит LangChain tools в GigaChat `functions`, а `tool_choice` — в `function_call` ([исходник `GigaChat.bind_tools`](https://github.com/ai-forever/langchain-gigachat/blob/master/libs/gigachat/langchain_gigachat/chat_models/gigachat.py#L910-L963)):

| LangChain `tool_choice` | Реальный GigaChat `function_call` |
|---|---|
| `None` | не форсируется |
| `"auto"` | `"auto"` |
| `"none"` | `"none"` |
| `"my_tool"` | `{"name": "my_tool"}` |
| `True` | первая переданная функция |
| `"any"` | **не поддерживается**, по умолчанию `ValueError` |

Можно включить `allow_any_tool_choice_fallback=True`, тогда `"any"` будет преобразовано в `"auto"`, но сам исходник предупреждает, что модель может не вызвать инструмент и поведение агента станет непредсказуемым. Для детерминированного шага нужно указывать конкретное имя tool, а не `any`.

Ещё одно ограничение адаптера: GigaChat не поддерживает несколько tool calls в одном сообщении; при сериализации `AIMessage` с более чем одним `tool_calls` интеграция выбрасывает `ValueError` ([исходник преобразования сообщений](https://github.com/ai-forever/langchain-gigachat/blob/master/libs/gigachat/langchain_gigachat/chat_models/gigachat.py#L267-L275)). Граф следует проектировать как «не более одного tool call за LLM-turn».

## 5. Structured output / JSON Schema

### 5.1. Нативная возможность провайдера

`POST /v1/chat/completions` поддерживает:

```json
{
  "response_format": {
    "type": "json_schema",
    "schema": { "type": "object", "properties": {}, "required": [] },
    "strict": true
  }
}
```

Если `required` отсутствует, модель может вернуть произвольный JSON. Для строгого соответствия нужны одновременно `required` и `strict: true` ([официальное руководство structured output](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output), [REST schema](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-chat#zapros)). Ответ представляет JSON как строку в `message.content`; его всё равно нужно распарсить и провалидировать.

### 5.2. `langchain-gigachat` 0.5.1

Интеграция реализует:

```python
structured_llm = llm.with_structured_output(
    MyPydanticModel,
    method="json_schema",
    strict=True,
)
result: MyPydanticModel = structured_llm.invoke(messages)
```

Поддерживаемые методы в официальном исходнике ([`with_structured_output`](https://github.com/ai-forever/langchain-gigachat/blob/master/libs/gigachat/langchain_gigachat/chat_models/gigachat.py#L793-L909)):

- `function_calling` — default, схема превращается в форсированный вызов функции;
- `json_schema` — нативный `response_format`, рекомендуемый вариант;
- `json_mode` — deprecated alias, не использовать в новом коде;
- `format_instructions` — legacy prompt-based fallback.

Для GigaBacklog Agent предпочтителен `method="json_schema", strict=True`: он использует провайдерное ограничение схемой и не зависит от unsupported `tool_choice="any"`. После ответа всё равно сохранять Pydantic-валидацию и обработку ошибки парсинга (`include_raw=True` полезен для диагностики).

При `method="function_calling"` Pydantic-класс должен иметь содержательное описание/docstring, а поля — descriptions: интеграция требует описание функции при конвертации схемы. Нативный `json_schema` этого искусственного требования не имеет.

## 6. Совместимость с явным `StateGraph`

Совместимость прямая:

- `langchain_gigachat.GigaChat` — стандартный `BaseChatModel`;
- `.invoke(messages)` возвращает `AIMessage`;
- `.bind_tools()` формирует `AIMessage.tool_calls` из GigaChat `function_call`;
- `ToolMessage` адаптер сериализует обратно как провайдерное сообщение роли `function`;
- `StateGraph` не требует конкретного провайдера: nodes — обычные функции и могут содержать LLM или обычный код. Официальная документация называет `StateGraph` основной graph-классом и требует вызвать `.compile()` перед использованием ([Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api#stategraph)). Для истории сообщений следует использовать reducer `add_messages` ([раздел messages in graph state](https://docs.langchain.com/oss/python/langgraph/graph-api#working-with-messages-in-graph-state)).

Минимальный рекомендуемый каркас без prebuilt-agent API:

```python
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

llm_with_tools = llm.bind_tools(tools, tool_choice="auto")

def call_model(state: AgentState) -> dict:
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

def route(state: AgentState) -> Literal["tools", "__end__"]:
    return "tools" if state["messages"][-1].tool_calls else END

builder = StateGraph(AgentState)
builder.add_node("model", call_model)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "model")
builder.add_conditional_edges("model", route)
builder.add_edge("tools", "model")
graph = builder.compile()
```

Это предпочтительно для GigaBacklog Agent: явные state channels, routing, лимиты циклов, human approval и error policy остаются под контролем приложения. Следует учитывать лимит одного tool call на LLM-turn.

## 7. `create_react_agent` и актуальная замена

`langgraph.prebuilt.create_react_agent` устарел. В исходнике LangGraph он помечен deprecated с сообщением: функция перемещена в `langchain.agents`, новый импорт — `from langchain.agents import create_agent` ([официальный исходник LangGraph](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py#L274-L278)). Официальное руководство миграции говорит, что до v1 рекомендовался `create_react_agent`, а теперь рекомендуется [`langchain.agents.create_agent`](https://docs.langchain.com/oss/python/migrate/langchain-v1#migrate-to-create_agent).

Для нового кода возможны два корректных пути:

1. **Предпочтительно для GigaBacklog:** собственный явный `StateGraph`, как выше. Он не зависит от deprecated factory и лучше подходит для детерминированного workflow.
2. **Если нужен готовый ReAct-loop:**

   ```python
   from langchain.agents import create_agent

   agent = create_agent(
       model=llm,
       tools=tools,
       system_prompt="...",
   )
   ```

   Но для GigaChat не следует выбирать стратегию, которая требует `tool_choice="any"`; для structured output надёжнее выделенный узел с `llm.with_structured_output(..., method="json_schema")`.

Не переносить в новый код:

```python
from langgraph.prebuilt import create_react_agent  # deprecated
```

Также не использовать старые `LLMChain`/`ConversationChain` без осознанной необходимости: LangChain v1 вынес legacy chains в `langchain-classic` ([migration guide](https://docs.langchain.com/oss/python/migrate/langchain-v1#langchain-classic)).

## 8. Локальная проверка совместимости

В чистом временном Python 3.11 virtualenv были реально установлены точные версии:

```text
gigachat 0.2.1
langchain-gigachat 0.5.1
langgraph 1.2.10
langchain 1.3.14
```

Без сетевого вызова (фиктивные credentials) проверено:

- создание `GigaChat(model="GigaChat-2-Max", scope="GIGACHAT_API_PERS")`;
- `bind_tools` для `None`, `auto`, `none` и конкретного имени;
- ожидаемый отказ для `tool_choice="any"`;
- создание wrapper-ов `with_structured_output` для `json_schema` и `function_calling`;
- компиляция явного `StateGraph` с LLM-node.

Результат: `StateGraph compile: OK; bind_tools auto/none/name: OK; any rejected: OK; structured wrappers: OK`.

Живой API-вызов не выполнялся, поскольку в исследовательской среде не было пользовательского Authorization Key. Поэтому перед релизом обязательны короткие контрактные тесты с реальным `GIGACHAT_API_PERS`: `/models`, один auto tool call, один forced tool call и один strict JSON Schema response для выбранной модели.

## 9. Итоговая рекомендация для реализации

1. Зафиксировать Python 3.11 или 3.12 и четыре версии из начала отчёта.
2. Удалить/не добавлять `gigachain`, `gigagraph`, `gigachain-*`.
3. Использовать `langchain_gigachat.GigaChat` + upstream `langgraph.StateGraph`.
4. По умолчанию выбрать `GigaChat-2-Max`, модель вынести в env; Ultra включать после контрактных тестов.
5. Использовать `scope="GIGACHAT_API_PERS"`, Authorization Key в secret manager, SDK-managed access token.
6. Настроить НУЦ Минцифры через trust store/`ca_bundle_file`; не отключать SSL verification в production.
7. Для tools использовать `auto`, `none` или конкретное имя; не использовать `any`; проектировать один tool call за turn.
8. Для типизированных результатов использовать native `json_schema` + `strict=True` + Pydantic validation.
9. Не использовать `create_react_agent`; при необходимости готового агента — `langchain.agents.create_agent`, но для основного backlog workflow оставить явный граф.

## Источники

### GigaChat / Sber

1. [Начало работы с API для физических лиц](https://developers.sber.ru/docs/ru/gigachat/quickstart/ind-using-api)
2. [Получить токен доступа (`POST /api/v2/oauth`)](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-token)
3. [Использование сертификатов НУЦ Минцифры](https://developers.sber.ru/docs/ru/gigachat/certificates)
4. [Выбор модели для генерации](https://developers.sber.ru/docs/ru/gigachat/guides/selecting-a-model)
5. [Тарифы GigaChat API для физлиц](https://developers.sber.ru/docs/ru/gigachat/tariffs/individual-tariffs)
6. [GigaChat 3 Ultra](https://developers.sber.ru/docs/ru/gigachat/models/gigachat-3-ultra)
7. [Список моделей (`GET /v1/models`)](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/get-models)
8. [Сгенерировать ответ (`POST /v1/chat/completions`)](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-chat)
9. [Режимы работы с функциями](https://developers.sber.ru/docs/ru/gigachat/guides/functions/function-calling-modes)
10. [Генерация структурированных данных](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output)

### Официальные пакеты и репозитории

11. [`ai-forever/gigachat`](https://github.com/ai-forever/gigachat) и [`gigachat` на PyPI](https://pypi.org/project/gigachat/)
12. [`ai-forever/langchain-gigachat`](https://github.com/ai-forever/langchain-gigachat), [`pyproject.toml`](https://github.com/ai-forever/langchain-gigachat/blob/master/libs/gigachat/pyproject.toml), [`GigaChat` implementation](https://github.com/ai-forever/langchain-gigachat/blob/master/libs/gigachat/langchain_gigachat/chat_models/gigachat.py), [`langchain-gigachat` на PyPI](https://pypi.org/project/langchain-gigachat/)
13. [`ai-forever/gigachain`](https://github.com/ai-forever/gigachain), deprecated [`gigachain`](https://pypi.org/project/gigachain/) и [`gigagraph`](https://pypi.org/project/gigagraph/) на PyPI

### LangChain / LangGraph

14. [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
15. [LangGraph Graph API / `StateGraph`](https://docs.langchain.com/oss/python/langgraph/graph-api)
16. [LangChain v1 migration guide: `create_react_agent` → `create_agent`](https://docs.langchain.com/oss/python/migrate/langchain-v1#migrate-to-create_agent)
17. [Исходник deprecation `create_react_agent`](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py#L274-L278)
18. [`langgraph` на PyPI](https://pypi.org/project/langgraph/) и [`langchain` на PyPI](https://pypi.org/project/langchain/)
