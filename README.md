# ner-evidence

Canonical, model-neutral NER knowledge and evidence for the FastNER ecosystem.

> **Status:** Private research phase, Beta 1. Pinned release: `person-en-ko-beta.1-1dc0b13fe0ff` (digest
> `1dc0b13fe0ff13e24616fef6d9c4b7aec3b9ab9672e531a2a02bcfffdac46ba9`; see `docs/releases/beta.1.md`). Contracts are defined but not stable (case schema `1.1.0`, taxonomy `0.2.0`,
> manifest/consumer contract `0.1.0`). Content is `internal-only` until the repository license is chosen. What changed
> since Alpha 1: [`docs/beta-1-changes.md`](docs/beta-1-changes.md).

This repository is intended to become the long-term source of truth for named-entity evidence, corpus provenance, taxonomy, authored cases, ambiguity cases, and evaluation-ready projections.

It must remain meaningful even if FastNER itself did not exist.

## Core principle

```text
NER evidence != model behavior
model behavior != product support
product support != marketing claim
```

This repository owns the first layer only: evidence.

## Initial scope

```text
PERSON
├─ English
└─ Korean
```

Future entity classes may include ORGANIZATION, LOCATION, ADDRESS, and other narrowly defined entities after their contracts are reviewed.

## What this repository owns

- entity taxonomy;
- language/script taxonomy;
- evidence source provenance;
- authored cases;
- ambiguity cases;
- negative/collision cases;
- boundary and cross-script cases;
- case-to-fixture lineage;
- evidence review history;
- snapshot identity and digest.

## What this repository does not own

- FastNER inference code;
- FastNER model weights or thresholds;
- generic evaluator implementation;
- FastNER qualification policy;
- release blockers;
- competitor ranking;
- redaction policy.

## Knowledge model

```text
Entity Type
  └─ Language / Script Profile
       ├─ Evidence Sources
       ├─ Authored Cases
       ├─ Ambiguity Cases
       ├─ Negative Cases
       ├─ Boundary Cases
       ├─ Context Variants
       └─ Fixture Projections
```

A Case should explain why the example matters, not merely provide text.

Example:

```text
Case:
"May" as a month versus "May" as a person name

Expectation:
context determines whether PERSON should be emitted

Why:
surface-form lookup alone cannot resolve the ambiguity
```

## Evidence classes

`corpus-backed`, `reference-backed`, `tool-corroborated`, `authored-baseline`, `authored-adversarial` and
`research-needed` (see `taxonomy/person.taxonomy.json`). The Alpha corpus was entirely project-authored; Beta 1 adds `reference-backed` cases (cited public rules) and
reference-checked familiarity labels, and still contains no corpus-backed case.

A majority vote among NER models is not ground truth.

## Data policy

Do not commit sensitive personal data merely because the project is about names.

Allowed evidence should be synthetic, properly licensed public corpus material, or other examples whose reuse is legally and ethically appropriate. Every imported dataset must have explicit provenance and licensing notes.

## Snapshot model

Downstream consumers pin immutable evidence snapshots under `snapshots/` containing snapshot identity, content
digest, taxonomy/schema versions, case-to-fixture lineage and the provenance manifest. See
[`docs/snapshot-and-consumer-contract.md`](docs/snapshot-and-consumer-contract.md).

## Working in this repository

```bash
PYTHONPATH=src python -m unittest discover -s tests   # unit tests
PYTHONPATH=src python -m ner_evidence check            # every gate: schema, provenance, privacy, lineage,
                                                       # determinism, slice targets, snapshots, immutability
PYTHONPATH=src python -m ner_evidence annotate '[[p:Name]] ...'   # compute spans for a new case
```

Standard-library Python only (3.10+). Start with [`docs/authoring-guide.md`](docs/authoring-guide.md).

| Document | Contents |
| --- | --- |
| [`docs/taxonomy-and-case-schema.md`](docs/taxonomy-and-case-schema.md) | PERSON taxonomy, language profiles, Case schema |
| [`docs/provenance-and-privacy-policy.md`](docs/provenance-and-privacy-policy.md) | Provenance, licensing, privacy, safe-data policy |
| [`docs/fixture-projection.md`](docs/fixture-projection.md) | Deterministic projection and lineage rules |
| [`docs/snapshot-and-consumer-contract.md`](docs/snapshot-and-consumer-contract.md) | Snapshot manifest, digests, consumer contract |
| [`docs/corpus-candidates.md`](docs/corpus-candidates.md) | Corpora considered for import and what blocks them |
| [`docs/review-workflow.md`](docs/review-workflow.md) | Independent review: registry, ledger, derived status, blind packets |
| [`docs/contrast-classes.md`](docs/contrast-classes.md) | Authored contrast classes and their rationale |
| [`docs/familiarity-and-rarity.md`](docs/familiarity-and-rarity.md) | What `common` / `rare` / `novel` mean, their documented basis, reference bands |
| [`docs/slice-tracking.md`](docs/slice-tracking.md), [`docs/evidence-coverage.md`](docs/evidence-coverage.md) | Slice targets, counts, known gaps |
| [`docs/handoff-ner-eval.md`](docs/handoff-ner-eval.md) | What `ner-eval` must decide itself |

## Relationship to `ner-eval`

`ner-eval` consumes pinned snapshots and measures model output. `ner-evidence` does not execute models and does not interpret product readiness.

## Relationship to `fastner-benchmarks`

FastNER qualification may use this evidence plus product-owned regression, adversarial, or protected corpora. This repository is not the only qualification population.

## Public-release gate

Before public release (status at Beta 1 content):

- licensing/provenance policy complete: **policy written and enforced; repository license not yet chosen, and the
  authored source has no independent legal review** (`python -m ner_evidence provenance --public-release` fails on purpose);
- privacy contribution policy explicit: **done**;
- snapshot/release format defined: **done (version `0.1.0`)**;
- EN/KR PERSON taxonomy reviewed: **not done; the independent review workflow exists and reviews are requested, but no
  independent verdict is recorded, so every case is still author-only** (`docs/review-workflow.md`);
- reference sources legally reviewed: **not done; every reference source has legal review `pending`**;
- sensitive-data checks running in CI: **done** (`.github/workflows/ci.yml`).
