# Pin the official GigaChat v2 SDK source by immutable commit

The published `gigachat==0.2.1` and `langchain-gigachat==0.5.1` integration use the legacy chat response contract and cannot consume the current native v2 structured-output response. The live smoke reproduced this after successful TLS, authentication, model discovery, and forced tool calling.

The production adapter therefore uses the official `ai-forever/gigachat` v2 SDK source at commit `0b694b35d017763086a4a72e2609479e1cdee687` (`0.2.3` release commit). The Git SHA is immutable and recorded in `uv.lock`; mutable branches and unpinned source dependencies are prohibited. The adapter uses `client.chat.create()` with a forced named function and for native JSON Schema through `ChatResponseFormat(..., strict=True)`. The full `RequestAnalysis` live contract is not yet established: the provider returns assistant content that fails local strict validation, tracked in [upstream issue #122](https://github.com/ai-forever/gigachat/issues/122). `langchain-gigachat` is removed because its legacy bridge is the incompatible layer.

This exception remains temporary: replace it with the corresponding published PyPI release after a credential-gated live contract smoke proves parity.
