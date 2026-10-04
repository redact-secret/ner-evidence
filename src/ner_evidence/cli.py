"""Command line entry point: ``python -m ner_evidence <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import annotate as annotate_mod
from . import canonical, repo as repo_mod, validate as validate_mod


def _load(args) -> repo_mod.Repo:
    return repo_mod.load(Path(args.root) if args.root else None)


def cmd_validate(args) -> int:
    repo = _load(args)
    probs = validate_mod.check_all(repo)
    for p in probs:
        print(p)
    print(f"validate: {len(repo.cases)} cases, {len(probs)} problems")
    return 1 if probs else 0


def cmd_fmt(args) -> int:
    repo = _load(args)
    changed = 0
    for path in sorted((repo.root / "evidence" / "cases").rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        want = repo_mod.format_case_file(data)
        if path.read_text(encoding="utf-8") != want:
            changed += 1
            if args.check:
                print(f"not formatted: {path.relative_to(repo.root)}")
            else:
                path.write_text(want, encoding="utf-8")
                print(f"formatted: {path.relative_to(repo.root)}")
    return 1 if (changed and args.check) else 0


def cmd_annotate(args) -> int:
    text, spans = annotate_mod.annotate(args.markup)
    print(canonical.pretty({"text": text, "expectations": spans}), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ner-evidence")
    ap.add_argument("--root", help="repository root (default: autodetect)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="schema + semantic validation of authored evidence").set_defaults(fn=cmd_validate)
    f = sub.add_parser("fmt", help="normalize authored case files (key order, indent, id order)")
    f.add_argument("--check", action="store_true")
    f.set_defaults(fn=cmd_fmt)
    a = sub.add_parser("annotate", help="convert [[p:..]]/[[n:..]]/[[e:..]] markup to text + spans")
    a.add_argument("markup")
    a.set_defaults(fn=cmd_annotate)
    from . import cli_extra  # later contract layers register their commands
    cli_extra.register(sub)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
