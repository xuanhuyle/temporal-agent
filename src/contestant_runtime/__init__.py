"""Shared runtime of every model-backed contestant (contestant code).

- ``protocol``: the text protocol ``tab.llm-protocol/1`` (prompts, observations, reply parsing);
- ``loop``: the budget-aware model loop that executes tool calls;
- ``memory``: the ``MemorySystem`` interface, the only part that differs between contestants;
- ``agent``: ``LLMAgent``, the harness-facing lifecycle.

Imports only the standard library and the contestant API of the harness
(``harness.agent``, ``harness.errors``, ``harness.llm``, ``harness.tool_specs``).
"""

from contestant_runtime.protocol import PROTOCOL_VERSION

__all__ = ["PROTOCOL_VERSION"]
