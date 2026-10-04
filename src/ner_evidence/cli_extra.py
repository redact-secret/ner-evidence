"""Registration point for commands added by later contract layers."""

from pathlib import Path


def _repo(args):
    from . import repo as repo_mod
    return repo_mod.load(Path(args.root) if args.root else None)


def cmd_provenance(args) -> int:
    from . import provenance
    repo = _repo(args)
    probs = provenance.check_sources(repo) + provenance.check_case_provenance(repo)
    if args.public_release:
        probs += provenance.public_release_problems(repo)
    for p in probs:
        print(p)
    print(f"provenance: {len(repo.sources)} sources, {len(probs)} problems")
    return 1 if probs else 0


def cmd_privacy(args) -> int:
    from . import privacy
    repo = _repo(args)
    findings = privacy.scan_tree(repo.root)
    for f in findings:
        print(f)
    print(f"privacy: {len(findings)} findings")
    return 1 if findings else 0


def cmd_project(args) -> int:
    from . import canonical, project
    from .repo import Problem
    repo = _repo(args)
    probs = project.check_ruleset(repo.ruleset, repo.cases)
    fixtures = project.project_all(repo.cases, repo.ruleset)
    # Determinism: a second, independent projection must be byte-identical.
    again = project.project_all(list(reversed(repo.cases)), repo.ruleset)
    data = canonical.jsonl_bytes(fixtures)
    if data != canonical.jsonl_bytes(again):
        probs.append(Problem("DETERMINISM", "project", "two projections differ"))
    probs += project.verify_all(fixtures, repo.cases, repo.ruleset, repo.schema("fixture"))
    for p in probs:
        print(p)
    if args.out:
        Path(args.out).write_bytes(data)
    print(f"project: {len(repo.cases)} cases -> {len(fixtures)} fixtures, sha256 {canonical.sha256_hex(data)}, {len(probs)} problems")
    return 1 if probs else 0


def cmd_slices(args) -> int:
    from . import project, slices
    repo = _repo(args)
    fixtures = project.project_all(repo.cases, repo.ruleset)
    report = slices.compute(repo.cases, fixtures, repo.targets)
    probs = slices.check_targets(report)
    for p in probs:
        print(p)
    print(f"slices: {report['cases']} cases, {report['fixtures']} fixtures, {len(report['unmet_targets'])} unmet, {len(report['waived_targets'])} waived")
    return 1 if probs else 0


def cmd_report(args) -> int:
    from . import project, slices
    repo = _repo(args)
    md = slices.render_markdown(slices.compute(repo.cases, project.project_all(repo.cases, repo.ruleset), repo.targets))
    path = repo.root / "docs" / "evidence-coverage.md"
    if args.write:
        path.write_text(md, encoding="utf-8")
        print(f"wrote {path.relative_to(repo.root)}")
        return 0
    if not path.exists() or path.read_text(encoding="utf-8") != md:
        print("[REPORT] docs/evidence-coverage.md is stale; run `python -m ner_evidence report --write`")
        return 1
    print("report: up to date")
    return 0


def cmd_snapshot(args) -> int:
    from . import snapshot
    repo = _repo(args)
    out = repo.root / "snapshots"
    if args.action == "build":
        if not args.label:
            print("snapshot build requires --label")
            return 2
        try:
            m = snapshot.build(repo, out, args.scope, args.label, args.stage)
        except snapshot.SnapshotError as exc:
            print(exc)
            return 1
        print(f"snapshot: {m['snapshot_id']} content_digest {m['content_digest']} cases {m['counts']['cases']} fixtures {m['counts']['fixtures']}")
        return 0
    if args.action == "verify":
        probs = snapshot.verify(Path(args.path)) if args.path else snapshot.verify_all(out)
        for p in probs:
            print(p)
        print(f"snapshot verify: {len(probs)} problems")
        return 1 if probs else 0
    probs, note = snapshot.check_immutability(repo.root, args.base)
    for p in probs:
        print(p)
    print(f"snapshot immutability: {len(probs)} problems ({note})")
    return 1 if probs else 0


def cmd_check(args) -> int:
    """Every repository gate, in one command. This is what CI runs."""
    from argparse import Namespace
    from . import cli
    base = dict(root=args.root, public_release=False, out=None, write=False, check=True,
                action=None, scope="person-en-ko", label=None, stage="alpha", path=None, base=args.base)
    steps = [
        ("validate", cli.cmd_validate, {}),
        ("fmt", cli.cmd_fmt, {}),
        ("provenance", cmd_provenance, {}),
        ("privacy", cmd_privacy, {}),
        ("project", cmd_project, {}),
        ("slices", cmd_slices, {}),
        ("report", cmd_report, {}),
        ("snapshot verify", cmd_snapshot, {"action": "verify"}),
        ("snapshot immutability", cmd_snapshot, {"action": "immutability"}),
    ]
    failed = []
    for name, fn, extra in steps:
        print(f"== {name}")
        if fn(Namespace(**{**base, **extra})) != 0:
            failed.append(name)
    print("\ncheck:", "FAILED: " + ", ".join(failed) if failed else "all gates passed")
    return 1 if failed else 0


def register(sub) -> None:
    c = sub.add_parser("check", help="run every repository gate (CI entry point)")
    c.add_argument("--base", help="git ref for the snapshot immutability comparison")
    c.set_defaults(fn=cmd_check)
    sub.add_parser("slices", help="slice counts and target evaluation").set_defaults(fn=cmd_slices)
    r = sub.add_parser("report", help="render or check docs/evidence-coverage.md")
    r.add_argument("--write", action="store_true")
    r.set_defaults(fn=cmd_report)
    s = sub.add_parser("snapshot", help="build / verify / immutability-check snapshots")
    s.add_argument("action", choices=["build", "verify", "immutability"])
    s.add_argument("--scope", default="person-en-ko")
    s.add_argument("--label", help="release label, e.g. alpha.1")
    s.add_argument("--stage", default="alpha", choices=["alpha", "beta", "stable"])
    s.add_argument("--path", help="verify a single snapshot directory (works on a downloaded copy)")
    s.add_argument("--base", help="git ref to compare against for immutability (default origin/main, main)")
    s.set_defaults(fn=cmd_snapshot)
    p = sub.add_parser("project", help="project cases to fixtures, verify lineage and determinism")
    p.add_argument("--out", help="write fixtures.jsonl here")
    p.set_defaults(fn=cmd_project)
    p = sub.add_parser("provenance", help="source registry and case provenance completeness")
    p.add_argument("--public-release", action="store_true", help="also apply the public-release gate (expected to fail while private)")
    p.set_defaults(fn=cmd_provenance)
    sub.add_parser("privacy", help="privacy/safe-data lint over committed evidence").set_defaults(fn=cmd_privacy)
