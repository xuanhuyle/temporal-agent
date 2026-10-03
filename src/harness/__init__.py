"""Common event runner and agent interfaces.

Contestant-facing modules (copied into contestant processes) are
``harness.agent``, ``harness.errors``, ``harness.llm`` and
``harness.tool_specs``, plus the process plumbing ``harness.wire``,
``harness.tripwire`` and ``harness.worker``. They never import ``evaluation``
and never receive paths to scenario manifests, future events, or evaluator
ground truth. Everything else in this package is harness-side.
"""

HARNESS_VERSION = "0.3.0"
