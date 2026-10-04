"""Immutable snapshot build, verification and immutability checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import __version__, canonical, privacy, project, provenance, slices, validate
from .jsonschema_lite import validate as schema_validate
from .repo import Problem, Repo, read_json

DIGEST_SPEC = "ner-evidence-snapshot-digest/1"
MANIFEST_VERSION = "0.1.0"
CONSUMER_CONTRACT_VERSION = "0.1.0"
EMBEDDED_SCHEMAS = ["case", "fixture", "source", "snapshot-manifest", "projection-ruleset"]
MANIFEST_NAME = "manifest.json"


class SnapshotError(Exception):
    pass


def content_digest(files: list[dict]) -> str:
    """SHA-256 over ``DIGEST_SPEC\\n`` followed by ``<sha256>  <path>\\n`` for each file sorted by path."""
    lines = "".join(f"{f['sha256']}  {f['path']}\n" for f in sorted(files, key=lambda f: f["path"]))
    return canonical.sha256_hex(f"{DIGEST_SPEC}\n{lines}".encode("utf-8"))


def tool_source_digest(root: Path) -> str:
    pkg = Path(__file__).resolve().parent
    parts = "".join(f"{p.name}\0{canonical.sha256_hex(p.read_bytes())}\n" for p in sorted(pkg.glob("*.py")))
    return canonical.sha256_hex(parts.encode("utf-8"))


def build_files(repo: Repo) -> tuple[dict[str, bytes], dict, list[dict]]:
    fixtures = project.project_all(repo.cases, repo.ruleset)
    report = slices.compute(repo.cases, fixtures, repo.targets)
    files: dict[str, bytes] = {
        "cases.jsonl": canonical.jsonl_bytes(sorted(repo.cases, key=lambda c: c["id"])),
        "fixtures.jsonl": canonical.jsonl_bytes(fixtures),
        "sources.json": canonical.pretty({"sources": sorted(repo.sources, key=lambda s: s["id"])}).encode(),
        "taxonomy.json": canonical.pretty(repo.taxonomy).encode(),
        "projections.json": canonical.pretty(repo.ruleset).encode(),
        "slice-report.json": canonical.pretty(report).encode(),
    }
    for name in EMBEDDED_SCHEMAS:
        files[f"schemas/{name}.schema.json"] = canonical.pretty(repo.schema(name)).encode()
    return files, report, fixtures


def make_manifest(repo: Repo, files: dict[str, bytes], report: dict, scope: str, label: str, stage: str) -> dict:
    listing = [{"path": p, "sha256": canonical.sha256_hex(b), "bytes": len(b)} for p, b in sorted(files.items())]
    digest = content_digest(listing)
    rv = {"factual": {}, "linguistic": {}}
    rv.update(report["review"])
    return {
        "manifest_version": MANIFEST_VERSION,
        "snapshot_id": f"{scope}-{label}-{digest[:12]}",
        "scope": scope, "release_label": label, "stage": stage,
        "entity_types": ["PERSON"], "languages": sorted(report["cases_by_language"]),
        "schema_version": repo.cases[0]["schema_version"],
        "taxonomy_version": repo.taxonomy["taxonomy_version"],
        "projection_ruleset_version": repo.ruleset["ruleset_version"],
        "consumer_contract_version": CONSUMER_CONTRACT_VERSION,
        "counts": {"cases": report["cases"], "fixtures": report["fixtures"], "sources": len(repo.sources),
                   "cases_by_language": report["cases_by_language"], "fixtures_by_language": report["fixtures_by_language"]},
        "source_manifest_digest": canonical.sha256_hex(files["sources.json"]),
        "digest_spec": DIGEST_SPEC, "content_digest": digest, "files": listing,
        "generation": {"tool": "ner-evidence-tools", "tool_version": __version__, "tool_source_digest": tool_source_digest(repo.root)},
        "redistribution": provenance.redistribution_level(repo),
        "review_summary": rv,
        "waived_targets": report["waived_targets"], "known_gaps": report["known_gaps"],
    }


def preflight(repo: Repo) -> list[Problem]:
    probs = validate.check_all(repo)
    probs += provenance.check_sources(repo) + provenance.check_case_provenance(repo)
    probs += [Problem("PRIVACY", f.where, f.rule) for f in privacy.scan_tree(repo.root)]
    probs += project.check_ruleset(repo.ruleset, repo.cases)
    if not probs:
        fixtures = project.project_all(repo.cases, repo.ruleset)
        probs += project.verify_all(fixtures, repo.cases, repo.ruleset, repo.schema("fixture"))
        probs += slices.check_targets(slices.compute(repo.cases, fixtures, repo.targets))
    return probs


def index_path(out_root: Path) -> Path:
    return out_root / "index.json"


def read_index(out_root: Path) -> list[dict]:
    p = index_path(out_root)
    return read_json(p)["snapshots"] if p.exists() else []


def build(repo: Repo, out_root: Path, scope: str, label: str, stage: str) -> dict:
    probs = preflight(repo)
    if probs:
        raise SnapshotError("refusing to build; fix first:\n" + "\n".join(str(p) for p in probs))
    files, report, _ = build_files(repo)
    manifest = make_manifest(repo, files, report, scope, label, stage)
    existing = read_index(out_root)
    for e in existing:
        if e["scope"] == scope and e["release_label"] == label and e["content_digest"] != manifest["content_digest"]:
            raise SnapshotError(
                f"{scope} {label} is already released as {e['snapshot_id']}; released snapshots are immutable. "
                "A correction needs a new release label (new snapshot identity).")
    target = out_root / manifest["snapshot_id"]
    if target.exists():
        if verify(target):
            raise SnapshotError(f"{target} exists but does not verify")
        return manifest  # identical content already released: idempotent
    target.mkdir(parents=True)
    for rel, data in files.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    (target / MANIFEST_NAME).write_text(canonical.pretty(manifest), encoding="utf-8")
    entry = {"snapshot_id": manifest["snapshot_id"], "scope": scope, "release_label": label, "stage": stage,
             "content_digest": manifest["content_digest"], "path": manifest["snapshot_id"]}
    index = sorted([*existing, entry], key=lambda e: e["snapshot_id"])
    index_path(out_root).write_text(canonical.pretty({"snapshots": index}), encoding="utf-8")
    return manifest


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]


def verify(snap: Path) -> list[Problem]:
    """Verify a snapshot using only its own contents (plus the reference tool's logic)."""
    probs: list[Problem] = []
    sid = snap.name

    def bad(code: str, msg: str) -> None:
        probs.append(Problem(code, sid, msg))

    mpath = snap / MANIFEST_NAME
    if not mpath.exists():
        return [Problem("SNAPSHOT", sid, "manifest.json missing")]
    manifest = read_json(mpath)
    mschema_path = snap / "schemas" / "snapshot-manifest.schema.json"
    if not mschema_path.exists():
        return [Problem("SNAPSHOT", sid, "embedded manifest schema missing")]
    errs = schema_validate(manifest, read_json(mschema_path))
    if errs:
        return [Problem("SCHEMA", sid, e) for e in errs]

    listed = {f["path"]: f for f in manifest["files"]}
    if len(listed) != len(manifest["files"]):
        bad("SNAPSHOT", "duplicate paths in manifest")
    on_disk = {p.relative_to(snap).as_posix() for p in snap.rglob("*") if p.is_file()} - {MANIFEST_NAME}
    for extra in sorted(on_disk - set(listed)):
        bad("SNAPSHOT", f"unlisted file {extra}")
    for path, f in sorted(listed.items()):
        fp = snap / path
        if not fp.exists():
            bad("SNAPSHOT", f"listed file missing: {path}")
            continue
        data = fp.read_bytes()
        if canonical.sha256_hex(data) != f["sha256"] or len(data) != f["bytes"]:
            bad("DIGEST", f"{path} does not match its recorded sha256/size")
    if probs:
        return probs

    if content_digest(manifest["files"]) != manifest["content_digest"]:
        bad("DIGEST", "content_digest does not match the file list")
    want_id = f"{manifest['scope']}-{manifest['release_label']}-{manifest['content_digest'][:12]}"
    if manifest["snapshot_id"] != want_id:
        bad("IDENTITY", f"snapshot_id {manifest['snapshot_id']!r} != derived {want_id!r}")
    if snap.name != manifest["snapshot_id"]:
        bad("IDENTITY", "directory name differs from snapshot_id")
    if manifest["source_manifest_digest"] != listed["sources.json"]["sha256"]:
        bad("DIGEST", "source_manifest_digest does not match sources.json")

    cases = _read_jsonl(snap / "cases.jsonl")
    fixtures = _read_jsonl(snap / "fixtures.jsonl")
    taxonomy = read_json(snap / "taxonomy.json")
    ruleset = read_json(snap / "projections.json")
    sources = read_json(snap / "sources.json")["sources"]
    c = manifest["counts"]
    if (c["cases"], c["fixtures"], c["sources"]) != (len(cases), len(fixtures), len(sources)):
        bad("COUNTS", f"manifest counts {c['cases']}/{c['fixtures']}/{c['sources']} != actual {len(cases)}/{len(fixtures)}/{len(sources)}")
    for key, items in (("cases_by_language", cases), ("fixtures_by_language", fixtures)):
        actual: dict[str, int] = {}
        for it in items:
            actual[it["language"]] = actual.get(it["language"], 0) + 1
        if dict(sorted(actual.items())) != c[key]:
            bad("COUNTS", f"{key} disagrees with content")
    if taxonomy["taxonomy_version"] != manifest["taxonomy_version"]:
        bad("VERSION", "taxonomy_version differs from taxonomy.json")
    if ruleset["ruleset_version"] != manifest["projection_ruleset_version"]:
        bad("VERSION", "projection_ruleset_version differs from projections.json")
    if {x["schema_version"] for x in cases} != {manifest["schema_version"]}:
        bad("VERSION", "schema_version differs from the cases")
    if [x["id"] for x in cases] != sorted(x["id"] for x in cases) or [x["fixture_id"] for x in fixtures] != sorted(x["fixture_id"] for x in fixtures):
        bad("ORDER", "records must be sorted by id")

    # Everything below runs the same checks as authoring, against the embedded copies.
    emb = Repo(root=snap, taxonomy=taxonomy, sources=sources, ruleset=ruleset, cases=cases)
    for case in cases:
        probs.extend(validate.check_case(case, emb))
    probs.extend(provenance.check_sources(emb))
    probs.extend(provenance.check_case_provenance(emb))
    probs.extend(project.check_ruleset(ruleset, cases))
    probs.extend(project.verify_all(fixtures, cases, ruleset, read_json(snap / "schemas" / "fixture.schema.json")))
    if manifest["redistribution"] != provenance.redistribution_level(emb):
        bad("PROVENANCE", "manifest redistribution disagrees with the sources")
    for rel in ("cases.jsonl", "fixtures.jsonl", "sources.json", "taxonomy.json", "projections.json"):
        for n, line in enumerate((snap / rel).read_text(encoding="utf-8").splitlines(), 1):
            for rule in privacy.scan_text(line):
                bad("PRIVACY", f"{rel}:{n} {rule}")
    report = read_json(snap / "slice-report.json")
    again = slices.compute(cases, fixtures, {"targets_version": report["targets_version"], "known_gaps": report["known_gaps"]})
    for key in ("cases", "fixtures", "cases_by_language", "fixtures_by_language", "mentions", "dimensions", "review"):
        if again[key] != report[key]:
            bad("SLICES", f"slice-report {key} does not match the content")
    if report["unmet_targets"]:
        bad("SLICES", f"snapshot was built with unmet targets: {report['unmet_targets']}")
    if manifest["waived_targets"] != report["waived_targets"] or manifest["known_gaps"] != report["known_gaps"]:
        bad("SLICES", "manifest waivers/gaps differ from slice-report")
    if manifest["review_summary"] != report["review"]:
        bad("SLICES", "manifest review_summary differs from slice-report")
    return probs


def verify_all(out_root: Path) -> list[Problem]:
    probs: list[Problem] = []
    index = read_index(out_root)
    listed = {e["snapshot_id"] for e in index}
    for e in index:
        snap = out_root / e["path"]
        if not snap.is_dir():
            probs.append(Problem("SNAPSHOT", e["snapshot_id"], "listed in index but directory missing"))
            continue
        probs.extend(verify(snap))
        m = read_json(snap / MANIFEST_NAME) if (snap / MANIFEST_NAME).exists() else {}
        if m.get("content_digest") != e["content_digest"]:
            probs.append(Problem("IDENTITY", e["snapshot_id"], "index content_digest differs from manifest"))
    if out_root.exists():
        for d in sorted(p for p in out_root.iterdir() if p.is_dir()):
            if d.name not in listed:
                probs.append(Problem("SNAPSHOT", d.name, "snapshot directory not listed in index.json"))
    return probs


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def check_immutability(root: Path, base: str | None = None) -> tuple[list[Problem], str]:
    """Released snapshot files may only be added, never changed or removed, relative to ``base``."""
    candidates = [base] if base else ["origin/main", "main"]
    ref = next((r for r in candidates if r and _git(root, "rev-parse", "--verify", "-q", f"{r}^{{commit}}").returncode == 0), None)
    if ref is None:
        return [], "skipped (no base ref available)"
    probs: list[Problem] = []
    diff = _git(root, "diff", "--name-status", "--no-renames", ref, "--", "snapshots")
    for line in diff.stdout.splitlines():
        status, path = line.split("\t", 1)
        if path == "snapshots/index.json" and status == "M":
            old = json.loads(_git(root, "show", f"{ref}:{path}").stdout)["snapshots"]
            new = read_index(root / "snapshots")
            if any(e not in new for e in old):
                probs.append(Problem("IMMUTABLE", path, "an existing release entry was changed or removed"))
        elif status != "A":
            probs.append(Problem("IMMUTABLE", path, f"released snapshot file {status}; released snapshots are immutable (publish a new snapshot instead)"))
    return probs, f"compared against {ref}"
