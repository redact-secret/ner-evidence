"""Deterministic projection of authored Cases into executable fixtures.

A projection is ``prefix + T(seg0) + T(span0) + T(seg1) + ... + suffix`` where
``T`` is a pure per-segment text transform declared in the ruleset. Offsets are
computed from the construction, never searched for, and expectations are copied
from the Case unchanged. Nothing here can create an expectation.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Callable

from . import canonical
from .jsonschema_lite import validate as schema_validate
from .repo import Problem, Repo


class ProjectionError(Exception):
    pass


def _json_escape(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)[1:-1]


TRANSFORMS: dict[str, Callable[[str], str]] = {
    "identity": lambda s: s,
    "json-escape": _json_escape,
    "nfd": lambda s: unicodedata.normalize("NFD", s),
}


def case_digest(case: dict) -> str:
    return canonical.digest(case)


def applies(proj: dict, case: dict) -> bool:
    if proj["id"] in {x["projection_id"] for x in case.get("projections_excluded", [])}:
        return False
    if proj["applies_when"] == "always":
        return True
    if proj["applies_when"] == "text-changes-under-nfd":
        return unicodedata.normalize("NFD", case["text"]) != case["text"]
    raise ProjectionError(f"unknown applies_when {proj['applies_when']!r}")


def _offsets(text: str, start: int, end: int) -> dict:
    return {
        "start": start, "end": end,
        "utf8_start": len(text[:start].encode("utf-8")), "utf8_end": len(text[:end].encode("utf-8")),
        "utf16_start": len(text[:start].encode("utf-16-le")) // 2, "utf16_end": len(text[:end].encode("utf-16-le")) // 2,
    }


def project_one(case: dict, proj: dict, ruleset_version: str) -> dict:
    t = TRANSFORMS[proj["segment_transform"]]
    text, out, pos = case["text"], proj["prefix"], 0
    placed: list[tuple[int, int, str]] = []
    for e in case["expectations"]:
        out += t(text[pos:e["start"]])
        surface = t(e["surface"])
        placed.append((len(out), len(out) + len(surface), surface))
        out += surface
        pos = e["end"]
    out += t(text[pos:]) + proj["suffix"]
    if proj["segment_transform"] == "nfd" and out != unicodedata.normalize("NFD", case["text"]):
        raise ProjectionError(f"{case['id']}: segment-wise NFD differs from whole-text NFD; exclude this projection")
    spans = []
    for i, (e, (s, en, surface)) in enumerate(zip(case["expectations"], placed)):
        assert out[s:en] == surface
        spans.append({"case_span_index": i, **_offsets(out, s, en), "surface": surface, "expect": e["expect"]})
    return {
        "fixture_id": f"{case['id']}@{proj['id']}",
        "case_id": case["id"],
        "language": case["language"],
        "projection_id": proj["id"],
        "text": out,
        "spans": spans,
        "lineage": {
            "case_id": case["id"], "case_digest": case_digest(case), "projection_id": proj["id"],
            "projection_version": proj["version"], "ruleset_version": ruleset_version,
        },
    }


def project_case(case: dict, ruleset: dict) -> list[dict]:
    return [project_one(case, p, ruleset["ruleset_version"]) for p in ruleset["projections"] if applies(p, case)]


def project_all(cases: list[dict], ruleset: dict) -> list[dict]:
    fixtures = [f for c in sorted(cases, key=lambda c: c["id"]) for f in project_case(c, ruleset)]
    return sorted(fixtures, key=lambda f: f["fixture_id"])


def check_ruleset(ruleset: dict, cases: list[dict]) -> list[Problem]:
    probs: list[Problem] = []
    ids = [p["id"] for p in ruleset.get("projections", [])]
    if len(ids) != len(set(ids)):
        probs.append(Problem("RULESET", "projections", "duplicate projection ids"))
    plain = next((p for p in ruleset.get("projections", []) if p["id"] == "plain"), None)
    if plain is None or plain["prefix"] or plain["suffix"] or plain["segment_transform"] != "identity":
        probs.append(Problem("RULESET", "plain", "a pure-identity 'plain' projection is required"))
    surface_words = {w.lower() for c in cases for e in c["expectations"] for w in re.findall(r"\w+", e["surface"]) if len(w) >= 2}
    for p in ruleset.get("projections", []):
        clash = sorted({w.lower() for w in re.findall(r"\w+", p["prefix"] + " " + p["suffix"])} & surface_words)
        if clash:
            probs.append(Problem("RULESET", p["id"], f"wrapper words {clash} also occur in authored expectation surfaces; wrappers must not introduce name-like content"))
    return probs


def verify_fixture(fx: dict, cases_by_id: dict[str, dict], ruleset: dict, fixture_schema: dict) -> list[str]:
    """Lineage and no-invented-expectation verification for one fixture."""
    errs = [f"schema: {e}" for e in schema_validate(fx, fixture_schema)]
    if errs:
        return errs
    lin = fx["lineage"]
    if fx["fixture_id"] != f"{fx['case_id']}@{fx['projection_id']}":
        errs.append("fixture_id does not equal case_id@projection_id")
    if lin["case_id"] != fx["case_id"] or lin["projection_id"] != fx["projection_id"]:
        errs.append("lineage disagrees with fixture identity")
    case = cases_by_id.get(fx["case_id"])
    if case is None:
        return errs + [f"lineage: case {fx['case_id']!r} does not exist"]
    if lin["case_digest"] != case_digest(case):
        errs.append("lineage: case digest differs from the authored case (stale fixture)")
    proj = next((p for p in ruleset["projections"] if p["id"] == fx["projection_id"]), None)
    if proj is None:
        return errs + [f"lineage: projection {fx['projection_id']!r} not in ruleset"]
    if proj["version"] != lin["projection_version"] or ruleset["ruleset_version"] != lin["ruleset_version"]:
        errs.append("lineage: projection/ruleset version differs from the ruleset in use")
    if len(fx["spans"]) != len(case["expectations"]):
        errs.append("fixture has a different number of spans than its case (expectation invented or dropped)")
    else:
        t = TRANSFORMS[proj["segment_transform"]]
        for i, (sp, e) in enumerate(zip(fx["spans"], case["expectations"])):
            if sp["case_span_index"] != i:
                errs.append(f"span {i}: case_span_index {sp['case_span_index']} != {i}")
            if sp["expect"] != e["expect"]:
                errs.append(f"span {i}: expectation {sp['expect']!r} != authored {e['expect']!r}")
            if sp["surface"] != t(e["surface"]):
                errs.append(f"span {i}: surface is not the declared transform of the authored surface")
            if fx["text"][sp["start"]:sp["end"]] != sp["surface"]:
                errs.append(f"span {i}: surface does not match text slice")
            if _offsets(fx["text"], sp["start"], sp["end"]) != {k: sp[k] for k in ("start", "end", "utf8_start", "utf8_end", "utf16_start", "utf16_end")}:
                errs.append(f"span {i}: byte/UTF-16 offsets inconsistent with code point offsets")
    if not errs and project_one(case, proj, ruleset["ruleset_version"]) != fx:
        errs.append("fixture is not reproducible from its case and projection")
    return errs


def verify_all(fixtures: list[dict], cases: list[dict], ruleset: dict, fixture_schema: dict, expect_complete: bool = True) -> list[Problem]:
    probs: list[Problem] = []
    by_id = {c["id"]: c for c in cases}
    seen: set[str] = set()
    for fx in fixtures:
        fid = fx.get("fixture_id", "<no id>") if isinstance(fx, dict) else "<not an object>"
        if fid in seen:
            probs.append(Problem("LINEAGE", fid, "duplicate fixture id"))
        seen.add(fid)
        for e in verify_fixture(fx, by_id, ruleset, fixture_schema):
            probs.append(Problem("LINEAGE", fid, e))
    if expect_complete:
        want = {f["fixture_id"] for f in project_all(cases, ruleset)}
        for missing in sorted(want - seen):
            probs.append(Problem("LINEAGE", missing, "fixture missing for an applicable projection"))
        for extra in sorted(seen - want):
            probs.append(Problem("LINEAGE", extra, "fixture has no applicable case/projection"))
    return probs
