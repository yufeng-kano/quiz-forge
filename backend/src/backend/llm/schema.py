"""Strict-mode JSON Schema construction for OpenAI-compatible structured outputs.

`response_format: json_schema` with `strict: true` requires every object
node to set `additionalProperties: false` and list *all* of its properties
in `required` (an "optional" field is instead a nullable type union).
Pydantic's `BaseModel.model_json_schema()` doesn't produce that shape on its
own, so this module rewrites it recursively — this is the only place the
schema is ever hand-adjusted; callers just pass a Pydantic model type.
"""

from typing import Any

from pydantic import BaseModel


def build_strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Build a strict-mode JSON Schema for `model`, ready for `response_format`."""
    schema = model.model_json_schema()
    defs = schema.get("$defs", {})
    _tighten(schema, defs)
    for definition in defs.values():
        _tighten(definition, defs)
    return schema


def _tighten(node: dict[str, Any], defs: dict[str, Any]) -> None:
    """Recursively enforce strict-mode object rules on a (sub)schema node."""
    if "properties" in node:
        node["additionalProperties"] = False
        node["required"] = list(node["properties"].keys())
        for prop_schema in node["properties"].values():
            _tighten(prop_schema, defs)

    items = node.get("items")
    if isinstance(items, dict):
        _tighten(items, defs)

    for key in ("anyOf", "oneOf", "allOf"):
        for branch in node.get(key, []):
            if isinstance(branch, dict):
                _tighten(branch, defs)
