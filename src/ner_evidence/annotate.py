"""Authoring helper: turn inline markup into text plus exact expectation spans.

    [[p:Kim Min-su]]   expect person
    [[n:May]]          expect not-person
    [[e:Smith Jones]]  expect either

Offsets are Unicode code points over the markup-free text.
"""

from __future__ import annotations

import re
import unicodedata

_TAG = re.compile(r"\[\[([pne]):(.+?)\]\]")
_KIND = {"p": "person", "n": "not-person", "e": "either"}


def annotate(markup: str) -> tuple[str, list[dict]]:
    text_parts: list[str] = []
    spans: list[dict] = []
    pos = 0
    length = 0
    for m in _TAG.finditer(markup):
        plain = markup[pos:m.start()]
        text_parts.append(plain)
        length += len(plain)
        surface = m.group(2)
        spans.append({"start": length, "end": length + len(surface), "surface": surface, "expect": _KIND[m.group(1)]})
        text_parts.append(surface)
        length += len(surface)
        pos = m.end()
    text_parts.append(markup[pos:])
    text = "".join(text_parts)
    if unicodedata.normalize("NFC", text) != text:
        raise ValueError("markup is not NFC-normalized")
    return text, spans
