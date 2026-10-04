# Conventions

## Principle

Evidence must be model-neutral, inspectable, and reproducible.

## Language

Documentation and canonical metadata should be in English. Examples may contain English, Korean, or other language text required by the case.

## Naming

Use semantic identities, for example:

```text
person/en/common-word-collision/may-month
person/ko/particle-context/topic-marker
```

Avoid identities containing issue numbers, milestones, FastNER versions, model names, or benchmark scores.

## Case authoring

Every Case should state what is tested, expected entity behavior, why it matters, evidence/provenance, and ambiguity/uncertainty where relevant.

## Synthetic data

Prefer synthetic names where a real identity is unnecessary. Do not contribute customer text, private messages, health records, unpublished employee/user lists, or scraped personal data without explicit legal/provenance review.

## Corpus imports

Every imported corpus must document exact source, version/date, license, redistribution terms, filtering/transformation, and known bias/coverage limits.

## Generated fixtures

Generated fixtures must be deterministic, preserve case lineage, never silently invent new expectations, and be reproducible from committed source records/tooling.

## Reviews

Evidence review should distinguish factual/provenance review, linguistic expectation review, and schema review. A model's current behavior is not evidence that the expectation is correct.

## Snapshot changes

Released snapshots are immutable. Fixes create a new snapshot.

## Cross-repository boundary

Do not add FastNER thresholds, FastNER support statuses, competitor ranking, or product release blockers.

## Public-readiness

Before public release, contribution rules must explicitly address personal data, license/provenance checks must run in CI, examples must be safe to redistribute, and unresolved evidence must be marked honestly.

## Tooling gates

`python -m ner_evidence check` runs every repository gate and is what CI runs. Do not weaken a lint, a target
or a schema to make a change pass: fix the evidence, or record the shortfall as a written waiver or known gap
in `evidence/slice-targets.json`.

## Review honesty

Review status is derived from the append-only review ledger (`docs/review-workflow.md`); it is never hand-set.

`review.*` fields describe who looked, not how sure the author is. Use `author-only` until someone other than the
author has reviewed that facet. Never use a model's output, or agreement between models, as a review.
