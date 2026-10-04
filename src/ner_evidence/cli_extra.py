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
    from . import reviews
    report = slices.compute(repo.cases, fixtures, repo.targets, reviews.summary(repo))
    probs = slices.check_targets(report)
    for p in probs:
        print(p)
    print(f"slices: {report['cases']} cases, {report['fixtures']} fixtures, {len(report['unmet_targets'])} unmet, {len(report['waived_targets'])} waived")
    return 1 if probs else 0


def cmd_report(args) -> int:
    from . import project, slices
    repo = _repo(args)
    from . import reviews
    md = slices.render_markdown(slices.compute(repo.cases, project.project_all(repo.cases, repo.ruleset), repo.targets, reviews.summary(repo)))
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


def cmd_references_check(args) -> int:
    from . import references
    repo = _repo(args)
    probs = references.check_bands(repo)
    for p in probs:
        print(p)
    n = sum(len(r["entries"]) for r in repo.bands.get("references", []))
    print(f"references: {n} derived bands, {len(probs)} problems")
    return 1 if probs else 0


def cmd_review(args) -> int:
    import datetime
    from . import reviews
    repo = _repo(args)
    if args.action == "check":
        probs = reviews.check_reviews(repo)
        for p in probs:
            print(p)
        rl = reviews.summary(repo)
        print(f"reviews: {rl['events']} events, {len(probs)} problems, {len(rl['disputed'])} unresolved disagreements")
        return 1 if probs else 0
    if args.action == "immutability":
        probs, note = reviews.check_ledger_immutability(repo.root, args.base)
        for p in probs:
            print(p)
        print(f"review immutability: {len(probs)} problems ({note})")
        return 1 if probs else 0
    if args.action == "sync":
        changed = reviews.sync(repo)
        print("synced: " + (", ".join(changed) if changed else "nothing to change"))
        return 0
    if args.action == "summary":
        import json
        print(json.dumps(reviews.summary(repo), indent=2, ensure_ascii=False))
        return 0
    if args.action == "verdict":
        import datetime
        from . import canonical
        case = next((c for c in repo.cases if c["id"] == args.case), None)
        if case is None or not (args.facet and args.reviewer and args.verdict and args.comment):
            print("review verdict needs --case (an existing id), --facet, --reviewer, --verdict and --comment")
            return 2
        if args.reviewer not in {r["id"] for r in repo.reviewers.get("reviewers", [])}:
            print(f"{args.reviewer} is not registered in evidence/reviews/reviewers.json")
            return 2
        ev = {"event_type": "verdict", "case_id": case["id"], "subject_digest": reviews.subject_digest(case), "facet": args.facet,
              "recorded_on": args.date or datetime.date.today().isoformat(), "reviewer_id": args.reviewer, "verdict": args.verdict, "comment": args.comment}
        if args.proposed_change:
            ev["proposed_change"] = args.proposed_change
        ev = reviews.with_id(ev)
        with open(repo.root / reviews.LEDGER_PATH, "a", encoding="utf-8") as f:
            f.write(canonical.dumps(ev) + "\n")
        print(f"recorded {ev['event_id']}; now run `review sync` and `review check`")
        return 0
    if not args.language or not args.facet:
        print(f"review {args.action} needs --language and --facet")
        return 2
    if args.action == "packet":
        text = reviews.render_packet(repo, args.language, args.facet, args.limit, args.blind)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(text, end="")
        return 0
    role = args.role or {("en", "linguistic"): "en-annotator", ("ko", "linguistic"): "ko-native-linguist"}.get((args.language, args.facet), "factual-checker")
    events = reviews.request_events(repo, args.language, args.facet, role, args.limit, args.date or datetime.date.today().isoformat(), args.only_referenced)
    if not events:
        print("nothing to request")
        return 0
    from . import canonical
    with open(repo.root / reviews.LEDGER_PATH, "a", encoding="utf-8") as f:
        for ev in events:
            f.write(canonical.dumps(ev) + "\n")
    print(f"requested {len(events)} {args.language} {args.facet} reviews ({role})")
    return 0


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
        ("references", cmd_references_check, {}),
        ("reviews", cmd_review, {"action": "check"}),
        ("review immutability", cmd_review, {"action": "immutability"}),
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
    r = sub.add_parser("review", help="independent review workflow: check, sync, request, packet, summary, immutability")
    r.add_argument("action", choices=["check", "sync", "request", "packet", "verdict", "summary", "immutability"])
    r.add_argument("--language", choices=["en", "ko"])
    r.add_argument("--facet", choices=["factual", "linguistic"])
    r.add_argument("--role", choices=["en-annotator", "ko-native-linguist", "factual-checker"])
    r.add_argument("--limit", type=int, default=50)
    r.add_argument("--out", help="packet: write here instead of stdout")
    r.add_argument("--blind", action="store_true", help="packet: hide expected labels and rationale (for blind annotation)")
    r.add_argument("--date", help="request/verdict: recorded_on (default today)")
    r.add_argument("--only-referenced", action="store_true", help="request: only cases that cite a reference rule or a familiarity reference (factual review)")
    r.add_argument("--case", help="verdict: case id")
    r.add_argument("--reviewer", help="verdict: registered reviewer id (rev/...)")
    r.add_argument("--verdict", choices=["agree", "disagree", "abstain"])
    r.add_argument("--comment", help="verdict: at least 20 characters")
    r.add_argument("--proposed-change", help="verdict: text only; never applied automatically")
    r.add_argument("--base", help="immutability: git ref to compare the ledger against")
    r.set_defaults(fn=cmd_review)
    p = sub.add_parser("project", help="project cases to fixtures, verify lineage and determinism")
    p.add_argument("--out", help="write fixtures.jsonl here")
    p.set_defaults(fn=cmd_project)
    p = sub.add_parser("provenance", help="source registry and case provenance completeness")
    p.add_argument("--public-release", action="store_true", help="also apply the public-release gate (expected to fail while private)")
    p.set_defaults(fn=cmd_provenance)
    from . import references
    references.register(sub)
    sub.add_parser("privacy", help="privacy/safe-data lint over committed evidence").set_defaults(fn=cmd_privacy)
