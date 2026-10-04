# Release beta.1: person-en-ko

| | |
| --- | --- |
| Snapshot id | `person-en-ko-beta.1-1dc0b13fe0ff` |
| Content digest (SHA-256) | `1dc0b13fe0ff13e24616fef6d9c4b7aec3b9ab9672e531a2a02bcfffdac46ba9` |
| Source manifest digest | `f877dcfc3c46e2bf0642379efd81a411b69a237dac360b1473b7b33890b2bcfe` |
| Location | `snapshots/person-en-ko-beta.1-1dc0b13fe0ff/` |
| Versions | case schema 1.1.0, taxonomy 0.2.0, projection ruleset 1.0.0, manifest/consumer contract 0.1.0 |
| Counts | 872 cases (EN 390, KO 482), 4,803 fixtures (EN 1,945, KO 2,858), 6 sources |
| Redistribution | `internal-only` (repository license not yet chosen) |
| Review | all 872 cases `author-only` for factual and linguistic review; no independent verdict recorded |

Pin the full `snapshot_id` and `content_digest`. Verify with `python -m ner_evidence snapshot verify --path <dir>` or the
dependency-free `examples/consume_snapshot.py`. The snapshot is immutable; a correction is a new release label.

## Reproducibility evidence

* Built in the working tree and again from the committed files in a separate directory under a different
  `PYTHONHASHSEED`: byte-identical `manifest.json`.
* `snapshot verify` reports 0 problems; the Alpha 1 reference consumer verifies it and iterates its fixtures.
* `snapshot immutability` against `origin/main`: 0 problems (Alpha 1 untouched).

## What changed since Alpha 1

See [`../beta-1-changes.md`](../beta-1-changes.md): structured ambiguity, balanced collision slices, Korean and English
contrast classes, documented familiarity basis with reference-checked surname bands, reference-backed cases, the
append-only review ledger, and the import-policy controls. Renamed ids and slice fields are listed there.

## What it is for

A harder, better documented EN+KO PERSON evidence set than Alpha 1, weighted toward ambiguity, collisions, boundaries and
rare names, with provenance for every case.

## What it must not be used for

* Real-world accuracy: all text is project-authored; there is no corpus-backed case.
* A held-out guarantee: `uncommon` describes a name in its language community, not any model's training data.
* Reviewed ground truth: no independent verdict exists yet (120+ review requests are open in the ledger inside the snapshot).
* Public redistribution: license undecided and every reference source has legal review pending.

Known gaps and waivers are in the manifest (`known_gaps`, `waived_targets`) and `slice-report.json`.
