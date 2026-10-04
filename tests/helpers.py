"""Shared test fixtures: a known-good case and helpers to mutate copies."""

import copy

import _bootstrap  # noqa: F401
from ner_evidence import repo as repo_mod

GOOD_CASE = {
    "id": "person/en/common-word-collision/may-month",
    "schema_version": "1.0.0",
    "entity_type": "PERSON",
    "language": "en",
    "title": "May as a month, not a person",
    "why": "Surface-form lookup alone cannot tell the month from the given name; only the sentence context can.",
    "text": "The meeting is in May and May will attend.",
    "expectations": [
        {"start": 18, "end": 21, "surface": "May", "expect": "not-person"},
        {"start": 26, "end": 29, "surface": "May", "expect": "person"},
    ],
    "focus_span": 1,
    "dimensions": {
        "familiarity": "common",
        "script": "latin",
        "token_class": "single",
        "collision_classes": ["temporal", "common-word"],
        "context_types": ["plain-prose"],
        "name_features": ["given-only"],
        "boundary_tags": [],
    },
    "ambiguity": {"level": "context-resolvable", "note": "The same surface form appears twice with different readings, resolved by the verb phrase."},
    "evidence_class": "authored-adversarial",
    "source_ids": ["src/project-authored-synthetic"],
    "review": {"factual": "author-only", "linguistic": "author-only", "schema": "machine-validated"},
}


def good_case(**overrides):
    case = copy.deepcopy(GOOD_CASE)
    for k, v in overrides.items():
        case[k] = v
    return case


def load_repo():
    return repo_mod.load(_bootstrap.ROOT)
