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


def register(sub) -> None:
    p = sub.add_parser("provenance", help="source registry and case provenance completeness")
    p.add_argument("--public-release", action="store_true", help="also apply the public-release gate (expected to fail while private)")
    p.set_defaults(fn=cmd_provenance)
    sub.add_parser("privacy", help="privacy/safe-data lint over committed evidence").set_defaults(fn=cmd_privacy)
