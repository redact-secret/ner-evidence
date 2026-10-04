# ner-evidence

Canonical, model-neutral NER knowledge and evidence for the FastNER ecosystem.

> **Status:** Private research and architecture phase.

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

The exact scheme is not frozen, but evidence should distinguish at least corpus-backed, linguistic/reference-backed, tool-corroborated, project-authored adversarial, and unresolved/research-needed cases.

A majority vote among NER models is not ground truth.

## Data policy

Do not commit sensitive personal data merely because the project is about names.

Allowed evidence should be synthetic, properly licensed public corpus material, or other examples whose reuse is legally and ethically appropriate. Every imported dataset must have explicit provenance and licensing notes.

## Snapshot model

Downstream consumers should pin immutable evidence snapshots containing snapshot identity, corpus digest, taxonomy version, case/fixture lineage, and provenance manifest.

## Relationship to `ner-eval`

`ner-eval` consumes pinned snapshots and measures model output. `ner-evidence` does not execute models and does not interpret product readiness.

## Relationship to `fastner-benchmarks`

FastNER qualification may use this evidence plus product-owned regression, adversarial, or protected corpora. This repository is not the only qualification population.

## Public-release gate

Before public release:

- licensing/provenance policy complete;
- privacy contribution policy explicit;
- snapshot/release format defined;
- EN/KR PERSON taxonomy reviewed;
- sensitive-data checks running in CI.
