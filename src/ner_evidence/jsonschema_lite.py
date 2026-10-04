"""A small, strict JSON Schema (draft 2020-12 subset) validator.

The schemas in ``schemas/`` are standard JSON Schema documents so that
consumers can validate with any implementation. This module exists so that the
repository can validate without third-party dependencies. It fails loudly on
any keyword it does not implement instead of silently ignoring it.
"""

from __future__ import annotations

import re
from typing import Any

_ANNOTATIONS = {"$schema", "$id", "$comment", "$defs", "title", "description", "default", "examples"}
_IMPLEMENTED = {
    "type", "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
    "uniqueItems", "enum", "const", "pattern", "minLength", "maxLength", "minimum", "maximum",
    "$ref", "anyOf", "format",
}
_FORMATS = {
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "sha256": re.compile(r"^[0-9a-f]{64}$"),
}


class SchemaError(Exception):
    """The schema itself uses something this validator does not support."""


def _type_ok(value: Any, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "null":
        return value is None
    raise SchemaError(f"unknown type {name!r}")


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise SchemaError(f"only local $ref supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def validate(instance: Any, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Return a list of human-readable errors (empty means valid)."""
    root = schema if root is None else root
    unknown = set(schema) - _IMPLEMENTED - _ANNOTATIONS
    if unknown:
        raise SchemaError(f"unsupported schema keywords at {path}: {sorted(unknown)}")
    if "$ref" in schema:
        return validate(instance, _resolve(schema["$ref"], root), root, path)

    errors: list[str] = []
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(instance, n) for n in names):
            return [f"{path}: expected {'|'.join(names)}, got {type(instance).__name__}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']}")
    if "anyOf" in schema:
        if not any(not validate(instance, s, root, path) for s in schema["anyOf"]):
            errors.append(f"{path}: matches none of anyOf")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match /{schema['pattern']}/")
        if "format" in schema:
            fmt = _FORMATS.get(schema["format"])
            if fmt is None:
                raise SchemaError(f"unsupported format {schema['format']!r}")
            if not fmt.match(instance):
                errors.append(f"{path}: not a valid {schema['format']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen: list[Any] = []
            for item in instance:
                if item in seen:
                    errors.append(f"{path}: duplicate item {item!r}")
                seen.append(item)
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], root, f"{path}[{i}]"))
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        for key, value in instance.items():
            if key in props:
                errors.extend(validate(value, props[key], root, f"{path}.{key}"))
            else:
                extra = schema.get("additionalProperties", True)
                if extra is False:
                    errors.append(f"{path}: unexpected property {key!r}")
                elif isinstance(extra, dict):
                    errors.extend(validate(value, extra, root, f"{path}.{key}"))
    return errors
