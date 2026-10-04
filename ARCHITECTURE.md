# Architecture

## 1. Purpose

`ner-evidence` separates NER knowledge from model implementation.

Architectural test:

> Would this repository still be useful to another NER implementation?

If not, the content probably belongs elsewhere.

## 2. Ownership boundary

This repository owns evidence and provenance. It does not own model code, weights, training policy, inference runtime, product qualification, or release policy.

## 3. Core entities

Expected record types:

```text
EntityType
LanguageProfile
Source
Case
Scenario
FixtureProjection
ReviewEvent
SnapshotManifest
```

Schemas are defined (`schemas/`, versioned) but not yet frozen; see `docs/taxonomy-and-case-schema.md`. `Scenario` is realised as a projection wrapper in the ruleset rather than a separate record (`docs/fixture-projection.md`). `ReviewEvent` is recorded as per-case review facets (`review.factual/linguistic/schema`) rather than an event log.

## 4. Cases before fixtures

A fixture is executable input. A Case is the reasoning unit that explains why the fixture exists.

One Case may project into many fixtures:

```text
Case
  +-> plain sentence
  +-> email-like sentence
  +-> log line
  +-> JSON string
  +-> punctuation variant
  +-> Unicode variant
```

Generated fixtures must retain lineage to the authored Case or Scenario.

## 5. PERSON case taxonomy

Initial corpus should explicitly cover:

- common given names/surnames;
- rare and novel names (community-relative, never model-relative);
- single-token and multi-token names;
- honorific/title contexts;
- person/location collisions;
- person/organization collisions;
- common-word/name collisions;
- sentence-initial capitalization traps;
- mixed-script names;
- romanized Korean names;
- Hangul names;
- Korean particle contexts;
- punctuation/quotation contexts;
- adjacent names;
- token-boundary edge cases.

## 6. Negative evidence

High-quality negatives are first-class. Examples include `May 2026`, `Central Park`, `Ford Mustang`, `Jordan River`, `Rose Garden`, `Young people`, and `Song title`.

The repository should explain why an example is negative, not merely label it.

## 7. Privacy and licensing

Dataset imports must record source, license, allowed use, redistribution constraints, transformations, whether personal data exists, and whether names are synthetic or naturally occurring.

Raw private/customer data is prohibited.

## 8. Snapshot immutability

Released snapshots are immutable inputs to evaluation. Changes require a new snapshot identity.

A snapshot manifest identifies taxonomy/schema versions, case and fixture counts, source manifest digest, content digest, generation tooling identity and the snapshot identity, which is derived from the content digest (`docs/snapshot-and-consumer-contract.md`). Released snapshots live under `snapshots/<id>/`; `snapshot immutability` fails CI if one is altered.

## 9. Generated content

Generated fixtures are build output, never hand-edited, and are only committed inside snapshots. Canonical authored reasoning stays reviewable in `evidence/cases/`. Projection rules: `docs/fixture-projection.md`.

## 10. Consumer contract

Primary downstream consumer is `ner-eval`. Consumers rely on snapshot schemas/artifacts, not private source-tree layout. What the contract deliberately does not provide is listed in `docs/handoff-ner-eval.md`.

## 11. Public-release gate

Before publishing:

- schemas versioned;
- snapshot generation reproducible;
- provenance machine-checkable;
- privacy checks exist;
- license compatibility reviewed;
- authored-vs-generated lineage inspectable.
