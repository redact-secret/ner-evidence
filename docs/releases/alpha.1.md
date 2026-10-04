# Release alpha.1: person-en-ko

| | |
| --- | --- |
| Snapshot id | `person-en-ko-alpha.1-65b5a0970bfe` |
| Content digest (SHA-256) | `65b5a0970bfe9307d4c5fb4c0ad5dbdd11546ce3d591e0afe583249955757415` |
| Source manifest digest | `7efa86e4f80e1e78533666ff0321374bedabde0dd40105562ddba7f29503dd00` |
| Location | `snapshots/person-en-ko-alpha.1-65b5a0970bfe/` |
| Versions | schema 1.0.0, taxonomy 0.1.0, projection ruleset 1.0.0, manifest/consumer contract 0.1.0 |
| Counts | 545 cases (EN 244, KO 301), 2,987 fixtures (EN 1,212, KO 1,775), 1 source |
| Redistribution | `internal-only` (repository license not yet chosen) |
| Review | all cases `author-only` for factual and linguistic review |

Pin the full `snapshot_id` and `content_digest`. Verify with `python -m ner_evidence snapshot verify --path <dir>`
or the dependency-free reference consumer `examples/consume_snapshot.py`.

This snapshot is immutable. A correction is a new release label and a new snapshot id; this entry is then
marked superseded here and the files are left untouched.

## What this snapshot is for

First balanced, reproducible evidence set for an EN+KO PERSON architecture comparison. It is deliberately
weighted toward hard cases: rare/constructed names, collisions, boundaries and honest ambiguities. Slice counts
and gaps: [`../evidence-coverage.md`](../evidence-coverage.md).

## What it must not be used for

* As an estimate of real-world accuracy: all text is project-authored; there is no naturally occurring corpus.
* As a held-out guarantee: "unseen" is a name-rarity proxy, not a statement about any model's training data.
* As reviewed ground truth: no case has had independent review (waived targets and known gaps are in the manifest).

## Reproducibility evidence

* Built twice, in the working tree and in a fresh clone under a different `PYTHONHASHSEED`: byte-identical
  `manifest.json`.
* Tests rebuild in different record orders and assert identical digests.
