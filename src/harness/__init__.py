"""Common event runner and agent interfaces.

Contestant-facing modules are ``harness.agent``, ``harness.tools`` and
``harness.workspace``. They never import ``evaluation`` and never receive
paths to scenario manifests, future events, or evaluator ground truth.
"""

HARNESS_VERSION = "0.1.0"
