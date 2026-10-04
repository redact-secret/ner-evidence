"""Repository layout and loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import canonical


def find_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for p in [here, *here.parents]:
        if (p / "taxonomy" / "person.taxonomy.json").exists():
            return p
    raise FileNotFoundError("repository root (taxonomy/person.taxonomy.json) not found")


@dataclass
class Problem:
    code: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.where}: {self.message}"


@dataclass
class Repo:
    root: Path
    taxonomy: dict = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)
    ruleset: dict = field(default_factory=dict)
    targets: dict = field(default_factory=dict)
    cases: list[dict] = field(default_factory=list)
    case_files: dict[str, str] = field(default_factory=dict)  # case id -> relative file
    problems: list[Problem] = field(default_factory=list)

    def schema(self, name: str) -> dict:
        return read_json(self.root / "schemas" / f"{name}.schema.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load(root: Path | None = None) -> Repo:
    """Load every authored file. Structural problems are collected, not raised."""
    from .jsonschema_lite import validate

    root = find_root(root)
    repo = Repo(root=root)
    repo.taxonomy = read_json(root / "taxonomy" / "person.taxonomy.json")
    for rel, attr, schema in (
        ("projections/ruleset.json", "ruleset", "projection-ruleset"),
        ("evidence/slice-targets.json", "targets", "slice-targets"),
    ):
        path = root / rel
        if not path.exists():
            continue  # defined by later contract layers; absence is reported by `check`
        setattr(repo, attr, read_json(path))
        for e in validate(getattr(repo, attr), repo.schema(schema)):
            repo.problems.append(Problem("SCHEMA", rel, e))

    src_path = root / "evidence" / "sources" / "sources.json"
    src_file = read_json(src_path)
    for e in validate(src_file, repo.schema("source-file")):
        repo.problems.append(Problem("SCHEMA", "evidence/sources/sources.json", e))
    repo.sources = list(src_file.get("sources", []))

    seen: dict[str, str] = {}
    for path in sorted((root / "evidence" / "cases").rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        try:
            data = read_json(path)
        except json.JSONDecodeError as exc:
            repo.problems.append(Problem("PARSE", rel, str(exc)))
            continue
        for e in validate(data, repo.schema("case-file")):
            repo.problems.append(Problem("SCHEMA", rel, e))
        for case in data.get("cases", []) if isinstance(data, dict) else []:
            cid = case.get("id", "<no id>") if isinstance(case, dict) else "<not an object>"
            if cid in seen:
                repo.problems.append(Problem("DUPLICATE_ID", rel, f"{cid} also defined in {seen[cid]}"))
                continue
            seen[cid] = rel
            repo.case_files[cid] = rel
            repo.cases.append(case)
    repo.cases.sort(key=lambda c: c.get("id", "") if isinstance(c, dict) else "")
    return repo


CASE_KEY_ORDER = [
    "id", "schema_version", "entity_type", "language", "title", "why", "text", "expectations", "focus_span",
    "dimensions", "ambiguity", "evidence_class", "source_ids", "review", "projections_excluded", "notes",
]
EXPECT_KEY_ORDER = ["start", "end", "surface", "expect", "note"]
DIM_KEY_ORDER = ["familiarity", "script", "token_class", "collision_classes", "context_types", "name_features", "boundary_tags"]


def ordered_case(case: dict) -> dict:
    out: dict = {}
    for k in CASE_KEY_ORDER:
        if k in case:
            out[k] = case[k]
    for k in sorted(set(case) - set(out)):
        out[k] = case[k]
    out["expectations"] = [
        {**{k: e[k] for k in EXPECT_KEY_ORDER if k in e}, **{k: e[k] for k in sorted(set(e) - set(EXPECT_KEY_ORDER))}}
        for e in case["expectations"]
    ]
    dims = case["dimensions"]
    out["dimensions"] = {**{k: dims[k] for k in DIM_KEY_ORDER if k in dims}, **{k: dims[k] for k in sorted(set(dims) - set(DIM_KEY_ORDER))}}
    return out


def format_case_file(data: dict) -> str:
    cases = sorted((ordered_case(c) for c in data["cases"]), key=lambda c: c["id"])
    head = {k: data[k] for k in data if k != "cases"}
    return canonical.pretty({**head, "cases": cases})
