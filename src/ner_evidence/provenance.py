"""Machine-checkable provenance, licensing and redistribution rules."""

from __future__ import annotations

from .jsonschema_lite import validate as schema_validate
from .repo import Problem, Repo

# SPDX identifiers acceptable for imported material once legally reviewed.
IMPORT_LICENSE_ALLOWLIST = {
    "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0",
    "Apache-2.0", "MIT", "BSD-3-Clause", "ODbL-1.0", "PDDL-1.0", "LicenseRef-public-domain",
}
# Evidence classes each source kind may back.
KIND_FOR_CLASS = {
    "authored-adversarial": {"project-authored"},
    "corpus-backed": {"public-corpus", "licensed-corpus"},
    "reference-backed": {"reference", "project-authored"},
    "tool-corroborated": {"project-authored", "public-corpus", "licensed-corpus", "reference"},
    "research-needed": {"project-authored", "public-corpus", "licensed-corpus", "reference"},
}
RANK = {"allowed": 0, "internal-only": 1, "cite-only": 2}


def check_sources(repo: Repo) -> list[Problem]:
    probs: list[Problem] = []
    schema = repo.schema("source")
    seen: set[str] = set()
    for src in repo.sources:
        sid = src.get("id", "<no id>") if isinstance(src, dict) else "<not an object>"

        def bad(code: str, msg: str, sid: str = sid) -> None:
            probs.append(Problem(code, sid, msg))

        errs = schema_validate(src, schema)
        for e in errs:
            bad("SCHEMA", e)
        if errs:
            continue
        if sid in seen:
            bad("DUPLICATE_ID", "source id defined twice")
        seen.add(sid)

        lic, pd, kind = src["license"], src["personal_data"], src["kind"]
        if pd["contains_personal_data"]:
            bad("PRIVACY", "sources containing personal data are not accepted in this release line")
        if kind == "project-authored":
            if src["origin"]["type"] != "authored":
                bad("PROVENANCE", "project-authored sources must have origin.type 'authored'")
            if pd["name_origin"] not in {"synthetic", "generic-composed"}:
                bad("PRIVACY", "project-authored sources may only use synthetic or generic-composed names")
        else:
            if src["origin"]["type"] == "authored" or "locator" not in src["origin"]:
                bad("PROVENANCE", "imported/reference sources need an origin locator (url or citation)")
            if kind in {"public-corpus", "licensed-corpus"}:
                for k in ("artifact_sha256", "retrieved_on"):
                    if k not in src["origin"]:
                        bad("PROVENANCE", f"imported corpora require origin.{k}")
                if lic["spdx"] not in IMPORT_LICENSE_ALLOWLIST and not lic["spdx"].startswith("LicenseRef-"):
                    bad("LICENSE", f"license {lic['spdx']!r} is not on the import allowlist")
                if lic["spdx"].endswith("license-pending") or "pending" in lic["spdx"]:
                    bad("LICENSE", "imported corpora cannot have a pending license")
                if src["review"]["legal"] != "independently-reviewed":
                    bad("LICENSE", "imported corpora require independent legal review before use")
                if not src["transformations"]:
                    bad("PROVENANCE", "imported corpora must list their filtering/transformation steps (even if 'none')")
            if pd["name_origin"] in {"public-figure", "naturally-occurring"} and src["review"]["legal"] != "independently-reviewed":
                bad("PRIVACY", "naturally occurring or public-figure names require independent legal review")
        if lic["redistribution"] == "allowed" and (lic["spdx"].endswith("pending") or "pending" in lic["spdx"]):
            bad("LICENSE", "redistribution cannot be 'allowed' while the license is pending")
    return probs


def check_case_provenance(repo: Repo) -> list[Problem]:
    probs: list[Problem] = []
    by_id = {s["id"]: s for s in repo.sources if isinstance(s, dict) and "id" in s}
    used: set[str] = set()
    for case in repo.cases:
        cid = case["id"]
        for sid in case.get("source_ids", []):
            used.add(sid)
            src = by_id.get(sid)
            if src is None:
                probs.append(Problem("PROVENANCE", cid, f"unknown source {sid!r}"))
                continue
            allowed = KIND_FOR_CLASS.get(case.get("evidence_class", ""), set())
            if src.get("kind") not in allowed:
                probs.append(Problem("PROVENANCE", cid, f"evidence_class {case.get('evidence_class')!r} cannot be backed by a {src.get('kind')!r} source"))
        if case.get("evidence_class") == "corpus-backed" and not any(by_id.get(s, {}).get("kind", "").endswith("corpus") for s in case.get("source_ids", [])):
            probs.append(Problem("PROVENANCE", cid, "corpus-backed case without a corpus source"))
    for sid in sorted(set(by_id) - used):
        probs.append(Problem("PROVENANCE", sid, "registered source is referenced by no case; remove it or use it"))
    return probs


def redistribution_level(repo: Repo) -> str:
    """Most restrictive redistribution among sources actually referenced by cases."""
    by_id = {s["id"]: s for s in repo.sources}
    levels = {by_id[sid]["license"]["redistribution"] for c in repo.cases for sid in c["source_ids"] if sid in by_id}
    return "allowed" if levels <= {"allowed"} else "internal-only"


def public_release_problems(repo: Repo) -> list[Problem]:
    """Gate for making the repository or a snapshot public. Expected to FAIL during private Alpha."""
    probs: list[Problem] = []
    for s in repo.sources:
        sid = s["id"]
        if s["license"]["redistribution"] != "allowed":
            probs.append(Problem("PUBLIC_GATE", sid, f"redistribution is {s['license']['redistribution']!r}"))
        if "pending" in s["license"]["spdx"]:
            probs.append(Problem("PUBLIC_GATE", sid, "license is pending"))
        if s["review"]["legal"] != "independently-reviewed":
            probs.append(Problem("PUBLIC_GATE", sid, "no independent legal review"))
        if s["review"]["provenance"] != "independently-reviewed":
            probs.append(Problem("PUBLIC_GATE", sid, "no independent provenance review"))
    return probs
