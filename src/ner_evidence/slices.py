"""Slice accounting: how many cases/mentions fall in each evidence slice, and which targets are unmet.

Slices are defined only over authored, model-neutral dimensions. There is no
notion of a model result here, so nothing in this module can reward a corpus
for being easy for any particular system.
"""

from __future__ import annotations

from typing import Any

from .repo import Problem

SEEN = {"common": "seen", "rare": "unseen", "novel": "unseen", "not-applicable": "not-applicable"}
LIST_FIELDS = {"collision_classes", "context_types", "name_features", "boundary_tags", "kinds"}
SCALAR_FIELDS = {
    "language", "script", "familiarity", "seen", "token_class", "ambiguity_level", "ambiguity",
    "evidence_class", "review_factual", "review_linguistic", "group",
}
DIMENSION_ORDER = [
    "language", "seen", "familiarity", "script", "token_class", "ambiguity", "ambiguity_level",
    "collision_classes", "context_types", "name_features", "boundary_tags", "kinds", "group",
    "evidence_class", "review_factual", "review_linguistic",
]


def fields(case: dict) -> dict[str, Any]:
    d = case["dimensions"]
    level = case["ambiguity"]["level"]
    return {
        "language": case["language"],
        "script": d["script"],
        "familiarity": d["familiarity"],
        "seen": SEEN[d["familiarity"]],
        "token_class": d["token_class"],
        "ambiguity_level": level,
        "ambiguity": "unambiguous" if level == "unambiguous" else "ambiguous",
        "collision_classes": list(d["collision_classes"]) or ["none"],
        "context_types": list(d["context_types"]),
        "name_features": list(d["name_features"]) or ["none"],
        "boundary_tags": list(d["boundary_tags"]) or ["none"],
        "kinds": sorted({e["expect"] for e in case["expectations"]}),
        "evidence_class": case["evidence_class"],
        "review_factual": case["review"]["factual"],
        "review_linguistic": case["review"]["linguistic"],
        "group": case["id"].split("/")[2],
    }


def matches(case: dict, where: dict) -> bool:
    f = fields(case)
    for key, want in where.items():
        if key not in f:
            raise KeyError(f"unknown slice field {key!r}")
        allowed = want if isinstance(want, list) else [want]
        have = f[key] if isinstance(f[key], list) else [f[key]]
        if not set(allowed) & set(have):
            return False
    return True


def count(cases: list[dict], where: dict) -> int:
    return sum(1 for c in cases if matches(c, where))


def compute(cases: list[dict], fixtures: list[dict], targets: dict) -> dict:
    langs = sorted({c["language"] for c in cases})
    dims: dict[str, dict[str, dict[str, int]]] = {}
    for dim in DIMENSION_ORDER:
        table: dict[str, dict[str, int]] = {}
        for c in cases:
            f = fields(c)
            vals = f[dim] if isinstance(f[dim], list) else [f[dim]]
            for v in vals:
                row = table.setdefault(v, {"all": 0, **{l: 0 for l in langs}})
                row["all"] += 1
                row[c["language"]] += 1
        dims[dim] = dict(sorted(table.items()))
    mentions = {"all": {}, **{l: {} for l in langs}}
    for c in cases:
        for e in c["expectations"]:
            for key in ("all", c["language"]):
                mentions[key][e["expect"]] = mentions[key].get(e["expect"], 0) + 1
    fx_by_lang: dict[str, int] = {}
    for fx in fixtures:
        fx_by_lang[fx["language"]] = fx_by_lang.get(fx["language"], 0) + 1
    review: dict[str, dict[str, int]] = {"factual": {}, "linguistic": {}}
    for c in cases:
        for facet in review:
            review[facet][c["review"][facet]] = review[facet].get(c["review"][facet], 0) + 1

    results = []
    for t in targets.get("count_targets", []):
        value = count(cases, t["where"])
        status = "met" if value >= t["min"] else ("waived" if "waiver" in t else "unmet")
        results.append({"id": t["id"], "kind": "count", "description": t["description"], "value": value, "min": t["min"], "status": status,
                        **({"waiver": t["waiver"]} if status == "waived" else {})})
    for t in targets.get("ratio_targets", []):
        num, den = count(cases, t["numerator"]), count(cases, t["denominator"])
        value = round(num / den, 4) if den else None
        ok = value is not None and value >= t.get("min", 0) and value <= t.get("max", 1)
        status = "met" if ok else ("waived" if "waiver" in t else "unmet")
        row = {"id": t["id"], "kind": "ratio", "description": t["description"], "value": value, "numerator": num, "denominator": den, "status": status}
        for k in ("min", "max"):
            if k in t:
                row[k] = t[k]
        if status == "waived":
            row["waiver"] = t["waiver"]
        results.append(row)
    return {
        "cases": len(cases), "fixtures": len(fixtures),
        "cases_by_language": {l: sum(1 for c in cases if c["language"] == l) for l in langs},
        "fixtures_by_language": dict(sorted(fx_by_lang.items())),
        "mentions": mentions, "dimensions": dims, "review": review,
        "targets_version": targets.get("targets_version", ""),
        "targets": results,
        "unmet_targets": [r["id"] for r in results if r["status"] == "unmet"],
        "waived_targets": [{"id": r["id"], "waiver": r["waiver"]} for r in results if r["status"] == "waived"],
        "known_gaps": targets.get("known_gaps", []),
    }


def check_targets(report: dict) -> list[Problem]:
    return [Problem("SLICE_TARGET", r["id"], f"{r['description']}: value {r['value']} vs min {r.get('min')} max {r.get('max')}")
            for r in report["targets"] if r["status"] == "unmet"]


def render_markdown(report: dict) -> str:
    langs = sorted(report["cases_by_language"])
    L = ["# Evidence coverage", "",
         "Generated by `python -m ner_evidence report --write`; do not edit by hand. CI fails if this file is stale.", "",
         f"* Cases: **{report['cases']}** ({', '.join(f'{l}: {n}' for l, n in report['cases_by_language'].items())})",
         f"* Fixtures: **{report['fixtures']}** ({', '.join(f'{l}: {n}' for l, n in report['fixtures_by_language'].items())})",
         "* Mentions: " + "; ".join(f"{l}: " + ", ".join(f"{k}={v}" for k, v in sorted(m.items())) for l, m in report["mentions"].items()), ""]
    L += ["## Targets", "", "| Target | Description | Value | Bound | Status |", "| --- | --- | --- | --- | --- |"]
    for r in report["targets"]:
        bound = ", ".join(f"{k} {r[k]}" for k in ("min", "max") if k in r)
        L.append(f"| `{r['id']}` | {r['description']} | {r['value']} | {bound} | {r['status']} |")
    L += ["", "## Known gaps", ""]
    L += [f"* `{g['id']}`: {g['description']}" for g in report["known_gaps"]] or ["* none recorded"]
    L += ["", "## Review status", ""]
    for facet, counts in report["review"].items():
        L.append(f"* {facet}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    L += ["", "## Case counts by dimension", "", "Cases with several values (collision classes, context types, ...) count once per value.", ""]
    for dim, table in report["dimensions"].items():
        L += [f"### {dim}", "", "| value | all | " + " | ".join(langs) + " |", "| --- | " + " | ".join("---" for _ in range(len(langs) + 1)) + " |"]
        for v, row in table.items():
            L.append(f"| {v} | {row['all']} | " + " | ".join(str(row[l]) for l in langs) + " |")
        L.append("")
    return "\n".join(L) + "\n"
