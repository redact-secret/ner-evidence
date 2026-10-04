"""Canonical serialisation and digests.

Canonical JSON: UTF-8, object keys sorted by Unicode code point, no
insignificant whitespace, non-ASCII emitted literally. Every digest in this
repository is SHA-256 over canonical bytes (or over raw file bytes where noted).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def dumps_bytes(obj: Any) -> bytes:
    return dumps(obj).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(obj: Any) -> str:
    return sha256_hex(dumps_bytes(obj))


def jsonl_bytes(records: Iterable[Any]) -> bytes:
    """One canonical JSON record per line, LF terminated, no BOM."""
    return b"".join(dumps_bytes(r) + b"\n" for r in records)


def pretty(obj: Any) -> str:
    """Human-reviewable JSON used for authored files (2-space indent, LF)."""
    return json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
