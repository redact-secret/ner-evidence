"""Semantic validation of authored evidence beyond what JSON Schema can say."""

from __future__ import annotations

import re
import unicodedata

from .jsonschema_lite import validate as schema_validate
from .repo import Problem, Repo

_HANGUL = re.compile(r"[ᄀ-ᇿ㄰-㆏ꥠ-꥿가-힯ힰ-퟿]")
_HAN = re.compile(r"[⺀-⿟㐀-䶿一-鿿豈-﫿]")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def letter_scripts(s: str) -> set[str]:
    out = set()
    for ch in s:
        if _HANGUL.match(ch):
            out.add("hangul")
        elif _HAN.match(ch):
            out.add("han")
        elif ch.isalpha() and unicodedata.name(ch, "").startswith("LATIN"):
            out.add("latin")
        elif ch.isalpha():
            out.add("other")
    return out


def derive_script(surface: str) -> str:
    scripts = letter_scripts(surface)
    return next(iter(scripts)) if len(scripts) == 1 else "mixed"


def derive_token_class(surface: str) -> str:
    return "single" if len(surface.split()) == 1 else "multi"


def vocab_ids(taxonomy: dict, dim: str) -> set[str]:
    return {v["id"] for v in taxonomy["dimensions"][dim]}


def metadata_strings(case: dict):
    for k in ("title", "why", "notes"):
        if k in case:
            yield f"{k}", case[k]
    if "note" in case.get("ambiguity", {}):
        yield "ambiguity.note", case["ambiguity"]["note"]
    for i, e in enumerate(case.get("expectations", [])):
        if "note" in e:
            yield f"expectations[{i}].note", e["note"]
    for i, x in enumerate(case.get("projections_excluded", [])):
        yield f"projections_excluded[{i}].reason", x.get("reason", "")


def check_case(case: dict, repo: Repo) -> list[Problem]:
    tax = repo.taxonomy
    cid = case.get("id", "<no id>")
    probs: list[Problem] = []

    def bad(code: str, msg: str) -> None:
        probs.append(Problem(code, cid, msg))

    errs = schema_validate(case, repo.schema("case"))
    for e in errs:
        bad("SCHEMA", e)
    if errs:
        return probs  # semantic checks assume structural validity

    parts = cid.split("/")
    if parts[1] != case["language"]:
        bad("ID", f"id language {parts[1]!r} != language {case['language']!r}")
    groups = {g["id"]: g for g in tax["case_groups"]}
    if parts[2] not in groups:
        bad("VOCAB", f"unknown case group {parts[2]!r}")
    elif case["language"] not in groups[parts[2]]["languages"]:
        bad("VOCAB", f"group {parts[2]!r} not defined for language {case['language']!r}")
    banned = {"issue", "alpha", "beta", "stable", "fastner", "score", "benchmark", "threshold"}
    if banned & set(re.split(r"[-/]", cid)) or re.search(r"\d{2,}", cid):
        bad("ID", "identity must not contain issue numbers, stages, product or score words")

    text = case["text"]
    if unicodedata.normalize("NFC", text) != text:
        bad("TEXT", "text is not NFC-normalized")
    if _CONTROL.search(text):
        bad("TEXT", "text contains control characters")
    if text != text.strip():
        bad("TEXT", "text has leading/trailing whitespace")

    spans = case["expectations"]
    prev_end = -1
    for i, s in enumerate(spans):
        if not (0 <= s["start"] < s["end"] <= len(text)):
            bad("SPAN", f"expectations[{i}] offsets {s['start']}:{s['end']} outside text of length {len(text)}")
            continue
        if text[s["start"]:s["end"]] != s["surface"]:
            bad("SPAN", f"expectations[{i}] surface {s['surface']!r} != text slice {text[s['start']:s['end']]!r}")
        if s["surface"] != s["surface"].strip():
            bad("SPAN", f"expectations[{i}] surface has leading/trailing whitespace")
        if s["start"] < prev_end:
            bad("SPAN", f"expectations[{i}] overlaps or is out of order (must be sorted by start)")
        prev_end = max(prev_end, s["end"])
    kinds = {k["id"] for k in tax["expectation_kinds"]}
    for i, s in enumerate(spans):
        if s["expect"] not in kinds:
            bad("VOCAB", f"expectations[{i}].expect {s['expect']!r} unknown")
    if not 0 <= case["focus_span"] < len(spans):
        bad("SPAN", f"focus_span {case['focus_span']} out of range")
        return probs

    dims = case["dimensions"]
    focus = spans[case["focus_span"]]
    if dims["script"] != derive_script(focus["surface"]):
        bad("DERIVED", f"script {dims['script']!r} but focus surface implies {derive_script(focus['surface'])!r}")
    if dims["token_class"] != derive_token_class(focus["surface"]):
        bad("DERIVED", f"token_class {dims['token_class']!r} but focus surface implies {derive_token_class(focus['surface'])!r}")
    if case["language"] == "en" and "hangul" in letter_scripts(text) and "mixed-script-sentence" not in dims["context_types"]:
        bad("DERIVED", "English case contains Hangul but is not tagged mixed-script-sentence")

    for dim, key in (("familiarity", "familiarity"), ("script", "script"), ("token_class", "token_class")):
        if dims[key] not in vocab_ids(tax, dim):
            bad("VOCAB", f"dimensions.{key} {dims[key]!r} unknown")
    for dim in ("collision_classes", "context_types", "name_features", "boundary_tags"):
        for v in dims[dim]:
            if v not in vocab_ids(tax, dim):
                bad("VOCAB", f"dimensions.{dim} value {v!r} unknown")
    for v in dims["name_features"]:
        if v.startswith("ko-") and case["language"] != "ko":
            bad("VOCAB", f"name feature {v!r} is Korean-specific")

    level = case["ambiguity"]["level"]
    if level not in vocab_ids(tax, "ambiguity_level"):
        bad("VOCAB", f"ambiguity.level {level!r} unknown")
    has_either = any(s["expect"] == "either" for s in spans)
    if level != "unambiguous" and "note" not in case["ambiguity"]:
        bad("AMBIGUITY", "ambiguity.note is required unless level is unambiguous")
    if dims["collision_classes"] and level == "unambiguous":
        bad("AMBIGUITY", "a case with collision classes cannot be 'unambiguous' (the surface form is confusable by definition)")
    if has_either != (level == "genuinely-ambiguous"):
        bad("AMBIGUITY", "an 'either' expectation must exist if and only if ambiguity.level is genuinely-ambiguous")
    has_person = any(s["expect"] == "person" for s in spans)
    if ("no-person" in dims["context_types"]) == has_person:
        bad("CONTEXT", "context type 'no-person' must be present exactly when no span expects 'person'")

    if case["evidence_class"] not in {e["id"] for e in tax["evidence_classes"]}:
        bad("VOCAB", f"evidence_class {case['evidence_class']!r} unknown")
    rv = tax["review_statuses"]
    for facet in ("factual", "linguistic", "schema"):
        if case["review"][facet] not in rv[facet]:
            bad("VOCAB", f"review.{facet} {case['review'][facet]!r} unknown")

    known = {p["id"] for p in repo.ruleset.get("projections", [])}
    for x in case.get("projections_excluded", []):
        if x["projection_id"] not in known:
            bad("PROJECTION", f"excluded projection {x['projection_id']!r} unknown")
        if x["projection_id"] == "plain":
            bad("PROJECTION", "the plain projection cannot be excluded")

    pattern = "|".join(re.escape(t) for t in tax["model_neutrality"]["forbidden_metadata_terms"])
    for where, value in metadata_strings(case):
        m = re.search(pattern, value, re.IGNORECASE)
        if m:
            bad("MODEL_TERM", f"{where} mentions {m.group(0)!r}; evidence metadata must stay model-neutral")
    if case["why"].strip().lower() == case["title"].strip().lower():
        bad("WHY", "'why' must explain, not repeat the title")
    return probs


def check_taxonomy(tax: dict) -> list[Problem]:
    probs: list[Problem] = []
    for dim, items in tax["dimensions"].items():
        ids = [v["id"] for v in items]
        if len(ids) != len(set(ids)):
            probs.append(Problem("TAXONOMY", dim, "duplicate vocabulary ids"))
    ids = [g["id"] for g in tax["case_groups"]]
    if len(ids) != len(set(ids)):
        probs.append(Problem("TAXONOMY", "case_groups", "duplicate ids"))
    return probs


def check_all(repo: Repo) -> list[Problem]:
    probs = list(repo.problems) + check_taxonomy(repo.taxonomy)
    for case in repo.cases:
        if isinstance(case, dict):
            probs.extend(check_case(case, repo))
    return probs
