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
    for v in dims.get("contrast_classes", []):
        if v not in vocab_ids(tax, "contrast_class"):
            bad("VOCAB", f"dimensions.contrast_classes value {v!r} unknown")
        elif not v.startswith(case["language"] + "-"):
            bad("VOCAB", f"contrast class {v!r} is not defined for language {case['language']!r}")
    for v in dims["name_features"]:
        if v.startswith("ko-") and case["language"] != "ko":
            bad("VOCAB", f"name feature {v!r} is Korean-specific")

    probs.extend(check_familiarity(case, repo))
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
    amb = case["ambiguity"]
    structured = [k for k in ("kind", "alternative_reading", "resolved_by") if k in amb]
    if level == "unambiguous":
        if structured or "acceptable_outcomes" in amb:
            bad("AMBIGUITY", "structured ambiguity fields are only allowed on ambiguous cases")
    elif structured or "acceptable_outcomes" in amb:
        if len(structured) != 3:
            bad("AMBIGUITY", "kind, alternative_reading and resolved_by must be given together")
        else:
            for key, dim in (("kind", "ambiguity_kind"), ("alternative_reading", "alternative_reading")):
                if amb[key] not in vocab_ids(tax, dim):
                    bad("VOCAB", f"ambiguity.{key} {amb[key]!r} unknown")
            for v in amb["resolved_by"]:
                if v not in vocab_ids(tax, "resolving_context"):
                    bad("VOCAB", f"ambiguity.resolved_by value {v!r} unknown")
            nothing = "nothing" in amb["resolved_by"]
            if nothing and amb["resolved_by"] != ["nothing"]:
                bad("AMBIGUITY", "'nothing' cannot be combined with other resolving contexts")
            if nothing != (level == "genuinely-ambiguous"):
                bad("AMBIGUITY", "resolved_by is ['nothing'] if and only if ambiguity.level is genuinely-ambiguous")
            if (level == "genuinely-ambiguous") != ("acceptable_outcomes" in amb):
                bad("AMBIGUITY", "acceptable_outcomes is required on, and only on, genuinely-ambiguous cases")
            elif "acceptable_outcomes" in amb and set(amb["acceptable_outcomes"]) != {"person", "not-person"}:
                bad("AMBIGUITY", "acceptable_outcomes must list both person and not-person")
    may_have_person = any(s["expect"] in {"person", "either"} for s in spans)
    if ("no-person" in dims["context_types"]) == may_have_person:
        bad("CONTEXT", "context type 'no-person' must be present exactly when no span expects 'person' or 'either'")

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


def band_for(repo: Repo, source_id: str, component: str) -> str | None:
    for ref in repo.bands.get("references", []):
        if ref["source_id"] == source_id:
            return ref["entries"].get(component)
    return None


def check_familiarity(case: dict, repo: Repo) -> list[Problem]:
    """Familiarity label, its documented basis and (when claimed) the mechanical reference check."""
    cid = case["id"]
    if "familiarity_basis" not in repo.taxonomy["dimensions"]:
        return []  # taxonomy that predates familiarity bases (released snapshots)
    dims = case["dimensions"]
    fam = dims["familiarity"]
    basis = dims.get("familiarity_basis")
    ref = dims.get("familiarity_reference")
    probs: list[Problem] = []

    def bad(code: str, msg: str) -> None:
        probs.append(Problem(code, cid, msg))

    if fam == "not-applicable":
        if basis or ref:
            bad("FAMILIARITY", "familiarity_basis/familiarity_reference are only allowed when a familiarity label applies")
        return probs
    if basis is None:
        bad("FAMILIARITY", "familiarity_basis is required when familiarity is common, rare or novel")
        return probs
    if basis not in vocab_ids(repo.taxonomy, "familiarity_basis"):
        bad("VOCAB", f"familiarity_basis {basis!r} unknown")
        return probs
    if basis == "constructed" and fam != "novel":
        bad("FAMILIARITY", "'constructed' only supports familiarity 'novel'")
    if basis != "reference-frequency":
        if ref:
            bad("FAMILIARITY", "familiarity_reference requires familiarity_basis 'reference-frequency'")
        return probs
    if not ref:
        bad("FAMILIARITY", "familiarity_basis 'reference-frequency' requires familiarity_reference")
        return probs
    focus = case["expectations"][case["focus_span"]]["surface"]
    if ref["component"] not in focus:
        bad("FAMILIARITY", f"reference component {ref['component']!r} does not occur in the focus span {focus!r}")
    if ref["source_id"] not in case["source_ids"]:
        bad("PROVENANCE", f"reference source {ref['source_id']!r} must also be listed in source_ids")
    band = band_for(repo, ref["source_id"], ref["component"])
    if band is None:
        bad("FAMILIARITY", f"no derived band for {ref['component']!r} in {ref['source_id']!r} (evidence/references/name-frequency-bands.json)")
    elif band != fam:
        bad("FAMILIARITY", f"familiarity {fam!r} but the reference band of {ref['component']!r} is {band!r}")
    for r in repo.bands.get("references", []):
        if r["source_id"] == ref["source_id"] and r["language"] != case["language"]:
            bad("FAMILIARITY", f"reference {ref['source_id']!r} is defined for language {r['language']!r}, not {case['language']!r}")
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
