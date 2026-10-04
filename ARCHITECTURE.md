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

The schemas are not yet frozen.

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
- rare/unseen names;
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

A snapshot manifest should identify taxonomy version, case count, fixture count, source manifest digest, content digest, and generation tooling version where relevant.

## 9. Generated content

Generated fixtures should normally be build output rather than hand-edited canonical knowledge. Canonical authored reasoning must remain reviewable.

## 10. Consumer contract

Primary downstream consumer is `ner-eval`. Consumers should rely on snapshot schemas/artifacts, not private source-tree layout.

## 11. Public-release gate

Before publishing:

- schemas versioned;
- snapshot generation reproducible;
- provenance machine-checkable;
- privacy checks exist;
- license compatibility reviewed;
- authored-vs-generated lineage inspectable.
