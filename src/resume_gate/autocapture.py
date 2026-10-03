from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any


ContextProvider = Callable[[Any, Mapping[str, Any]], Mapping[str, Any] | None]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _schema_fingerprint(graph: Any) -> str:
    input_schema = graph.get_input_jsonschema()
    output_schema = graph.get_output_jsonschema()
    channels = []
    for name in getattr(graph, "channels", {}) or {}:
        if not str(name).startswith(("branch:", "join:", "__")):
            channels.append(str(name))
    payload = {
        "input": input_schema,
        "output": output_schema,
        "state_channels": sorted(channels),
    }
    return f"sha256:{_digest(payload)}"


def _graph_fingerprint(graph: Any) -> str:
    drawable = graph.get_graph()
    payload = drawable.to_json()
    return f"sha256:{_digest(payload)}"


def _tool_schema(tool: Any) -> Any:
    args = getattr(tool, "args", None)
    if args is not None:
        return args
    get_input_schema = getattr(tool, "get_input_schema", None)
    if callable(get_input_schema):
        try:
            schema = get_input_schema()
            model_json_schema = getattr(schema, "model_json_schema", None)
            if callable(model_json_schema):
                return model_json_schema()
        except Exception:
            return None
    return None


def _tool_record(tool: Any, name: str) -> dict[str, Any]:
    payload = {
        "name": name,
        "description": getattr(tool, "description", None),
        "schema": _tool_schema(tool),
    }
    record: dict[str, Any] = {"version": f"sha256:{_digest(payload)}"}

    metadata = getattr(tool, "metadata", None)
    if isinstance(metadata, Mapping):
        permission = metadata.get("resume_gate_permission", metadata.get("permission"))
        if permission is not None:
            record["permission"] = str(permission)
    return record


def _discover_tools(graph: Any) -> dict[str, dict[str, Any]]:
    """Best-effort discovery of tools registered in LangGraph ToolNodes.

    This intentionally walks only a small set of known runnable-container
    attributes. It does not crawl arbitrary object internals.
    """

    found: dict[str, dict[str, Any]] = {}
    seen: set[int] = set()

    def visit(obj: Any, depth: int = 0) -> None:
        if obj is None or depth > 8:
            return
        marker = id(obj)
        if marker in seen:
            return
        seen.add(marker)

        tools_by_name = getattr(obj, "tools_by_name", None)
        if isinstance(tools_by_name, Mapping):
            for name, tool in tools_by_name.items():
                found[str(name)] = _tool_record(tool, str(name))

        for attr in ("bound", "runnable", "first", "last"):
            child = getattr(obj, attr, None)
            if child is not None and child is not obj:
                visit(child, depth + 1)

        for attr in ("steps", "middle"):
            children = getattr(obj, attr, None)
            if isinstance(children, (list, tuple)):
                for child in children:
                    visit(child, depth + 1)

    for node in (getattr(graph, "nodes", {}) or {}).values():
        visit(node)
    return dict(sorted(found.items()))


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in overlay.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, Mapping)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


@dataclass
class AutoManifestBuilder:
    """Build Resume Gate manifests directly from a compiled LangGraph.

    Structural/runtime fields require no application annotations. A single
    optional context provider can add live business state such as policy,
    authorities and dependencies. The same provider is sampled once when the
    graph pauses and again immediately before resume.
    """

    graph: Any
    context_provider: ContextProvider | None = None
    app_version: str | None = None

    def __call__(self, snapshot: Any, config: Mapping[str, Any]) -> dict[str, Any]:
        checkpoint_id = (
            (getattr(snapshot, "config", None) or {})
            .get("configurable", {})
            .get("checkpoint_id")
        )
        langgraph_version = _package_version("langgraph")
        graph_fingerprint = _graph_fingerprint(self.graph)
        runtime_version_payload = {
            "app_version": self.app_version,
            "langgraph_version": langgraph_version,
            "graph": graph_fingerprint,
        }
        manifest: dict[str, Any] = {
            "checkpoint_id": checkpoint_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "runtime": {
                "agent_version": f"sha256:{_digest(runtime_version_payload)}",
                "state_schema": _schema_fingerprint(self.graph),
                "framework": "langgraph",
                "framework_version": langgraph_version,
                "graph_fingerprint": graph_fingerprint,
            },
            "tools": _discover_tools(self.graph),
            "authorities": [],
            "dependencies": [],
            "side_effects": [],
        }

        if self.context_provider is not None:
            overlay = self.context_provider(snapshot, config)
            if overlay:
                manifest = _deep_merge(manifest, overlay)

        return manifest


__all__ = ["AutoManifestBuilder", "ContextProvider"]
