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
    "authored-adversarial": {"project-authored", "reference"},
    "authored-baseline": {"project-authored", "reference"},
    "corpus-backed": {"public-corpus", "licensed-corpus"},
    "reference-backed": {"reference", "project-authored"},
    "tool-corroborated": {"project-authored", "public-corpus", "licensed-corpus", "reference"},
    "research-needed": {"project-authored", "public-corpus", "licensed-corpus", "reference"},
}
RANK = {"allowed": 0, "internal-only": 1, "cite-only": 2}
# license.redistribution -> the only policy.text_redistribution that agrees with it
POLICY_FOR_REDISTRIBUTION = {"allowed": "allowed", "internal-only": "internal-only", "cite-only": "prohibited"}
USE_FOR_KIND = {"project-authored": {"authored"}, "public-corpus": {"text-incorporated"}, "licensed-corpus": {"text-incorporated"},
                "reference": {"cited-rule", "derived-labels-only", "text-incorporated"}}
NO_CONTENT_USES = {"derived-labels-only", "cited-rule"}  # nothing from the source is stored in cases


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
            aggregate_labels_only = src.get("use") in NO_CONTENT_USES and not pd["contains_personal_data"]
            if pd["name_origin"] in {"public-figure", "naturally-occurring"} and src["review"]["legal"] != "independently-reviewed" and not aggregate_labels_only:
                bad("PRIVACY", "naturally occurring or public-figure names require independent legal review")
        use = src.get("use")
        if use is not None:
            if use not in USE_FOR_KIND[kind]:
                bad("POLICY", f"a {kind} source cannot have use {use!r}")
            probs.extend(_check_policy(src, sid))
        if lic["redistribution"] == "allowed" and (lic["spdx"].endswith("pending") or "pending" in lic["spdx"]):
            bad("LICENSE", "redistribution cannot be 'allowed' while the license is pending")
    return probs


def _check_policy(src: dict, sid: str) -> list[Problem]:
    """Machine-checkable import controls (policy block) for non-authored sources."""
    out: list[Problem] = []

    def bad(msg: str) -> None:
        out.append(Problem("POLICY", sid, msg))

    kind, use, lic, pd = src["kind"], src["use"], src["license"], src["personal_data"]
    pol = src.get("policy")
    if kind == "project-authored":
        if pol:
            bad("project-authored sources carry no import policy")
        return out
    if pol is None:
        bad("non-authored sources need a policy block (redistribution, attribution, share-alike, names, excerpt cap)")
        return out
    if pol["text_redistribution"] != POLICY_FOR_REDISTRIBUTION[lic["redistribution"]]:
        bad(f"policy.text_redistribution {pol['text_redistribution']!r} disagrees with license.redistribution {lic['redistribution']!r}")
    if pol["attribution_required"] and not pol.get("attribution"):
        bad("attribution_required needs the credit line in policy.attribution")
    if use == "text-incorporated":
        if "max_excerpt_chars" not in pol:
            bad("text-incorporated sources need policy.max_excerpt_chars (excerpts are minimized and capped)")
        if pol["names_in_cases"] == "not-applicable":
            bad("text-incorporated sources must say what happens to names: replaced-with-synthetic or as-found-non-personal")
        if lic["redistribution"] == "cite-only":
            bad("text cannot be incorporated from a cite-only source")
        if kind in {"public-corpus", "licensed-corpus"} and pd["name_origin"] in {"public-figure", "naturally-occurring"} and pol["names_in_cases"] != "replaced-with-synthetic":
            bad("names that occur naturally in the source must be replaced with synthetic names before they enter cases")
    else:
        if pol["names_in_cases"] != "not-applicable" or "max_excerpt_chars" in pol:
            bad(f"a {use} source stores no source text, so names_in_cases is not-applicable and there is no excerpt cap")
        if pol["text_redistribution"] == "allowed" and lic["redistribution"] != "allowed":
            bad("inconsistent redistribution")
    if pol["names_in_cases"] == "as-found-non-personal" and (pd["contains_personal_data"] or pd["name_origin"] not in {"synthetic", "generic-composed"}):
        bad("as-found names are only allowed when they are synthetic or generic and the source holds no personal data")
    if pol["share_alike"] and "SA" not in lic["spdx"].upper().split("-") and not lic["spdx"].startswith("LicenseRef-"):
        bad("share_alike is set but the SPDX license is not a share-alike license")
    return out


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
        cls = case.get("evidence_class")
        for sid in case.get("source_ids", []):
            src = by_id.get(sid, {})
            cap = src.get("policy", {}).get("max_excerpt_chars")
            if src.get("use") == "text-incorporated" and cap is not None and len(case.get("text", "")) > cap:
                probs.append(Problem("POLICY", cid, f"case text is {len(case['text'])} characters but {sid} allows excerpts of at most {cap}"))
        cites = case.get("citations", [])
        for ct in cites:
            if ct["source_id"] not in case.get("source_ids", []):
                probs.append(Problem("PROVENANCE", cid, f"citation to {ct['source_id']!r} which is not in source_ids"))
            elif by_id.get(ct["source_id"], {}).get("kind") != "reference":
                probs.append(Problem("PROVENANCE", cid, f"citation to {ct['source_id']!r}: only reference sources are cited by locator"))
        if cls == "reference-backed":
            if not any(by_id.get(c["source_id"], {}).get("use") in {"cited-rule", "text-incorporated"} for c in cites):
                probs.append(Problem("PROVENANCE", cid, "a reference-backed case must cite (citations[]) a registered reference rule it rests on"))
        elif cites:
            probs.append(Problem("PROVENANCE", cid, "citations are for reference-backed cases; other classes state their basis in why/notes"))
        if case.get("evidence_class") == "corpus-backed" and not any(by_id.get(s, {}).get("kind", "").endswith("corpus") for s in case.get("source_ids", [])):
            probs.append(Problem("PROVENANCE", cid, "corpus-backed case without a corpus source"))
    for sid in sorted(set(by_id) - used):
        probs.append(Problem("PROVENANCE", sid, "registered source is referenced by no case; remove it or use it"))
    return probs


def redistribution_level(repo: Repo) -> str:
    """Most restrictive redistribution among sources actually referenced by cases."""
    by_id = {s["id"]: s for s in repo.sources}
    levels = {by_id[sid]["license"]["redistribution"] for c in repo.cases for sid in c["source_ids"]
              if sid in by_id and by_id[sid].get("use") not in NO_CONTENT_USES}
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
