"""Test-only contestants for ``tests/test_process.py``.

They run inside a contestant process started by ``harness.process.ProcessAgent``
and import only the standard library and the contestant-facing harness
modules (``harness.agent``, ``harness.errors``, ``harness.llm``). They are not
benchmark contestants.
"""
