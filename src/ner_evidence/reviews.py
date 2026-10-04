"""Independent review workflow: an append-only ledger bound to exact case content.

Design rules (docs/review-workflow.md):

* A case's ``review.factual`` / ``review.linguistic`` status is *derived* from the ledger, never hand-set.
* A verdict is bound to ``subject_digest``, the digest of the case without its ``review`` block. Any later edit to
  the text, spans, dimensions, rationale, evidence class or sources changes the digest, so earlier verdicts stop
  counting and the case falls back to ``author-only``. A reviewer cannot rewrite what they reviewed unnoticed.
* Only verdicts from registered reviewers who attest independence count. Other verdicts are kept and reported.
* Disagreement is a status (``disputed``), listed in the coverage report, until the case changes or the
  disagreeing reviewer records a new verdict on the new content.
* The ledger is append-only relative to the base branch.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import canonical
from .jsonschema_lite import validate as schema_validate
from .repo import Problem, Repo

FACETS = ("factual", "linguistic")
LEDGER_PATH = "evidence/reviews/ledger.jsonl"
REVIEWERS_PATH = "evidence/reviews/reviewers.json"
ROLES = {"en-annotator": ("en", "linguistic"), "ko-native-linguist": ("ko", "linguistic"), "factual-checker": (None, "factual")}


def subject_digest(case: dict) -> str:
    return canonical.digest({k: v for k, v in case.items() if k != "review"})


def make_event_id(event: dict) -> str:
    return "ev-" + canonical.digest({k: v for k, v in event.items() if k != "event_id"})[:16]


def with_id(event: dict) -> dict:
    return {"event_id": make_event_id(event), **event}


def _independent(repo: Repo) -> dict[str, dict]:
    return {r["id"]: r for r in repo.reviewers.get("reviewers", []) if r["status"] == "active" and r["independent_of_authors"]}


def counted_verdicts(repo: Repo, case: dict, facet: str) -> dict[str, str]:
    """Latest counting verdict per independent reviewer for the case's current content."""
    digest = subject_digest(case)
    ok = _independent(repo)
    latest: dict[str, str] = {}
    for ev in repo.ledger:
        if (ev.get("event_type") == "verdict" and ev.get("case_id") == case["id"] and ev.get("facet") == facet
                and ev.get("subject_digest") == digest and ev.get("reviewer_id") in ok):
            r = ok[ev["reviewer_id"]]
            if case["language"] in r["languages"] and facet in r["facets"]:
                latest[ev["reviewer_id"]] = ev["verdict"]
    return latest


def derived_status(repo: Repo, case: dict, facet: str) -> str:
    current = case["review"][facet]
    if current == "not-required":
        return current
    verdicts = set(counted_verdicts(repo, case, facet).values())
    if "disagree" in verdicts:
        return "disputed"
    if "agree" in verdicts:
        return "independently-reviewed"
    return "author-only"


def check_reviews(repo: Repo) -> list[Problem]:
    probs: list[Problem] = []
    for e in schema_validate(repo.reviewers, repo.schema("reviewers")):
        probs.append(Problem("SCHEMA", REVIEWERS_PATH, e))
    ids = [r.get("id") for r in repo.reviewers.get("reviewers", [])]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        probs.append(Problem("REVIEW", dup, "reviewer registered twice"))
    cases = {c["id"]: c for c in repo.cases}
    registry = {r["id"]: r for r in repo.reviewers.get("reviewers", []) if "id" in r}
    forbidden = "|".join(re.escape(t) for t in repo.taxonomy["model_neutrality"]["forbidden_metadata_terms"])
    seen: set[str] = set()
    schema = repo.schema("review-event")
    for n, ev in enumerate(repo.ledger, 1):
        where = f"ledger:{n}"
        errs = schema_validate(ev, schema)
        for e in errs:
            probs.append(Problem("SCHEMA", where, e))
        if errs:
            continue
        if ev["event_id"] != make_event_id(ev):
            probs.append(Problem("REVIEW", where, "event_id does not match the event content (edited after recording?)"))
        if ev["event_id"] in seen:
            probs.append(Problem("REVIEW", where, "duplicate event_id"))
        seen.add(ev["event_id"])
        case = cases.get(ev["case_id"])
        if case is None:
            probs.append(Problem("REVIEW", where, f"unknown case {ev['case_id']!r}"))
            continue
        if ev["event_type"] == "request":
            if "requested_role" not in ev or "reviewer_id" in ev or "verdict" in ev:
                probs.append(Problem("REVIEW", where, "a request needs requested_role and no reviewer_id or verdict"))
            else:
                lang, facet = ROLES[ev["requested_role"]]
                if (lang and lang != case["language"]) or facet != ev["facet"]:
                    probs.append(Problem("REVIEW", where, f"role {ev['requested_role']!r} does not fit a {case['language']} {ev['facet']} review"))
        else:
            if "reviewer_id" not in ev or "verdict" not in ev or "comment" not in ev or "requested_role" in ev:
                probs.append(Problem("REVIEW", where, "a verdict needs reviewer_id, verdict and comment, and no requested_role"))
            elif ev["reviewer_id"] not in registry:
                probs.append(Problem("REVIEW", where, f"reviewer {ev['reviewer_id']!r} is not in {REVIEWERS_PATH}"))
        for field in ("comment", "proposed_change"):
            if field in ev and re.search(forbidden, ev[field], re.IGNORECASE):
                probs.append(Problem("MODEL_TERM", where, f"{field} mentions a model or product term; reviews must stay model-neutral"))
    for case in repo.cases:
        for facet in FACETS:
            want = derived_status(repo, case, facet)
            if case["review"][facet] != want:
                probs.append(Problem("REVIEW_STATUS", case["id"],
                                     f"review.{facet} is {case['review'][facet]!r} but the ledger derives {want!r}; run `python -m ner_evidence review sync` (status is derived, never hand-set)"))
    return probs


def summary(repo: Repo) -> dict:
    """Counts for the coverage report and snapshot metadata. Pure function of cases, registry and ledger."""
    langs = sorted({c["language"] for c in repo.cases})
    ok = _independent(repo)
    reviewed = {f: {l: 0 for l in langs} for f in FACETS}
    open_req = {f: {l: 0 for l in langs} for f in FACETS}
    disputed: list[dict] = []
    stale = self_reviews = 0
    cases = {c["id"]: c for c in repo.cases}
    for ev in repo.ledger:
        case = cases.get(ev.get("case_id"))
        if case is None:
            continue
        if ev.get("subject_digest") != subject_digest(case):
            stale += 1
        if ev.get("event_type") == "verdict" and ev.get("reviewer_id") not in ok:
            self_reviews += 1
    for case in repo.cases:
        for facet in FACETS:
            status = derived_status(repo, case, facet)
            if status == "independently-reviewed":
                reviewed[facet][case["language"]] += 1
            elif status == "disputed":
                disputed.append({"case_id": case["id"], "facet": facet})
            digest = subject_digest(case)
            requested = any(e.get("event_type") == "request" and e.get("case_id") == case["id"] and e.get("facet") == facet
                            and e.get("subject_digest") == digest for e in repo.ledger)
            if requested and status == "author-only":
                open_req[facet][case["language"]] += 1
    return {
        "events": len(repo.ledger),
        "independent_reviewers": {l: sum(1 for r in ok.values() if l in r["languages"]) for l in langs},
        "reviewed_cases": reviewed,
        "open_requests": open_req,
        "disputed": sorted(disputed, key=lambda d: (d["case_id"], d["facet"])),
        "stale_events": stale,
        "uncounted_verdicts": self_reviews,
    }


# ---- ledger immutability ---------------------------------------------------

def check_ledger_immutability(root: Path, base: str | None = None) -> tuple[list[Problem], str]:
    """Ledger lines present on the base branch must be unchanged and in place; only appends are allowed."""
    candidates = [base] if base else ["origin/main", "main"]

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)

    ref = next((r for r in candidates if r and git("rev-parse", "--verify", "-q", f"{r}^{{commit}}").returncode == 0), None)
    if ref is None:
        return [], "skipped (no base ref available)"
    old = git("show", f"{ref}:{LEDGER_PATH}")
    if old.returncode != 0:
        return [], f"compared against {ref} (no ledger there yet)"
    old_lines = old.stdout.splitlines()
    path = root / LEDGER_PATH
    new_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if new_lines[:len(old_lines)] != old_lines:
        return [Problem("REVIEW_IMMUTABLE", LEDGER_PATH, "existing ledger lines were changed, reordered or removed; the ledger is append-only")], f"compared against {ref}"
    return [], f"compared against {ref}"


# ---- workflow helpers ------------------------------------------------------

def priority(case: dict) -> tuple:
    d = case["dimensions"]
    if case["ambiguity"]["level"] == "genuinely-ambiguous":
        rank = 0
    elif d.get("contrast_classes") or d["boundary_tags"]:
        rank = 1
    elif d["collision_classes"]:
        rank = 2
    else:
        rank = 3
    return (rank, case["id"])


def sync(repo: Repo) -> list[str]:
    """Rewrite review.* in case files from the ledger. Touches nothing else."""
    from . import repo as repo_mod
    changed: list[str] = []
    by_file: dict[str, list[dict]] = {}
    for case in repo.cases:
        by_file.setdefault(repo.case_files[case["id"]], []).append(case)
    for rel, cases in by_file.items():
        path = repo.root / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for c in data["cases"]:
            for facet in FACETS:
                want = derived_status(repo, c, facet)
                if c["review"][facet] != want:
                    c["review"][facet] = want
                    touched = True
        if touched:
            path.write_text(repo_mod.format_case_file(data), encoding="utf-8")
            changed.append(rel)
    return changed


def request_events(repo: Repo, language: str, facet: str, role: str, limit: int, recorded_on: str, only_referenced: bool = False) -> list[dict]:
    chosen = []
    for case in sorted((c for c in repo.cases if c["language"] == language), key=priority):
        if case["review"][facet] != "author-only":
            continue
        if only_referenced and not (case.get("citations") or case["dimensions"].get("familiarity_reference")):
            continue
        digest = subject_digest(case)
        if any(e.get("event_type") == "request" and e.get("case_id") == case["id"] and e.get("facet") == facet
               and e.get("subject_digest") == digest for e in repo.ledger):
            continue
        chosen.append(with_id({"event_type": "request", "case_id": case["id"], "subject_digest": digest, "facet": facet,
                               "recorded_on": recorded_on, "requested_role": role}))
        if len(chosen) >= limit:
            break
    return chosen


def render_packet(repo: Repo, language: str, facet: str, limit: int, blind: bool = False) -> str:
    """Self-contained reviewer packet: what to judge, for each case, and a verdict template."""
    lines = [f"# Review packet: {language} {facet}", "",
             "You are asked for an independent opinion on the expectations below. You do not edit cases.",
             "Record each opinion as a ledger line (see docs/review-workflow.md). Disagreement is welcome and stays visible.",
             "Judge the expectation from the text alone: a model's output is not evidence either way.", ""]
    if blind:
        lines[3:3] = ["BLIND MODE: expected labels and the author's rationale are hidden. For every span say person / not-person / either,",
                      "then compare with the author's labels (maintainer unblinds) and record agree or disagree per case.", ""]
    conventions = next(p["conventions"] for p in repo.taxonomy["language_profiles"] if p["id"] == language)
    lines += ["## Span conventions in force", ""] + [f"* {c}" for c in conventions] + [""]
    n = 0
    for case in sorted((c for c in repo.cases if c["language"] == language), key=priority):
        if derived_status(repo, case, facet) != "author-only":
            continue
        n += 1
        if n > limit:
            break
        lines += [f"## {case['id']}", "", f"* subject_digest: `{subject_digest(case)}`"] + ([] if blind else [f"* title: {case['title']}"]) + [f"* text: `{case['text']}`"]
        for i, e in enumerate(case["expectations"]):
            mark = " (focus)" if i == case["focus_span"] else ""
            label = "" if blind else f" expected **{e['expect']}**"
            lines.append(f"* span {i}{mark}: `{e['surface']}` [{e['start']}:{e['end']}]{label}")
        if blind:
            lines.append("")
            continue
        lines += [f"* why: {case['why']}", f"* ambiguity: {case['ambiguity']['level']}" + (f" - {case['ambiguity']['note']}" if 'note' in case['ambiguity'] else ""), ""]
    return "\n".join(lines) + "\n"
