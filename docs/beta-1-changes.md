# Beta 1 content: what changed since Alpha 1

This page is for consumers pinning Alpha 1 (`person-en-ko-alpha.1-65b5a0970bfe`) and for whoever publishes the Beta 1
snapshot. It describes the evidence content that is ready; the Beta 1 snapshot is `person-en-ko-beta.1-1dc0b13fe0ff` (see [`releases/beta.1.md`](releases/beta.1.md)). Nothing
here changes Alpha 1, which stays immutable.

## Counts

Alpha 1: 545 cases (EN 244, KO 301), 2,987 fixtures, 1 source. Beta 1 content: see the generated
[`evidence-coverage.md`](evidence-coverage.md) for current numbers. The groups that grew are:

| Area | Where | What |
| --- | --- | --- |
| Ambiguity semantics | group `context-ambiguity`, field `ambiguity.*` | minimal pairs and honest ambiguities with machine-readable kind, alternative reading, resolving context and acceptable outcomes |
| Collisions | groups `organization-collision`, `location-collision`, `common-word-collision` | organization, location, brand and common-word collisions with separate person / not-person / either floors |
| Korean contrasts | `particle-context`, `spacing-variation`, `title-honorific`, `mixed-script`, `surname-false-positive-trap`, `punctuation-boundary` | particle allomorphs and stacks, name-final-syllable traps, copula/quotative, honorific forms, surname-prefix traps, spacing, separators, scripts |
| English adversarial | `list-and-structured-text`, `punctuation-boundary`, `title-honorific`, `common-word-collision`, `organization-collision` | logs, labels, tables, delimited rows, markup, honorific variants, lookalike entities |
| Rare and novel names | group `uncommon-name` | reference-checked and constructed names with a documented basis |
| Reference-backed | `evidence_class: reference-backed` | cases that cite Hangul Spelling Rules, Romanization of Korean and a W3C personal-names article |
| Review | `evidence/reviews/` | registry, append-only ledger, open linguistic and factual review requests (counts in the coverage report), zero verdicts |

## Breaking changes for a consumer of Alpha 1

| Change | Alpha 1 | Beta 1 |
| --- | --- | --- |
| Case `schema_version` | `1.0.0` | `1.1.0` (additive: new optional fields only) |
| Taxonomy | `0.1.0` | `0.2.0` (new vocabularies; the `unseen-name` group became `uncommon-name`) |
| Case ids in the renamed group | `person/<lang>/unseen-name/<slug>` | `person/<lang>/uncommon-name/<slug>` (same slug) |
| Slice field and target ids | `seen` = `seen`/`unseen`; `en-seen`, `en-unseen`, `ko-seen`, `ko-unseen`, `*-unseen-share` | `name_commonness` = `common`/`uncommon`; `en-common-name`, `en-uncommon-name`, `ko-common-name`, `ko-uncommon-name`, `*-uncommon-name-share` |
| Source records | no `use`, no `policy` | `use` required; `policy` required for non-authored sources |
| Case review fields | hand-set | derived from the review ledger |
| Snapshot files | cases, fixtures, sources, taxonomy, projections, slice report, schemas | the same, plus `reviews/*`, `references/name-frequency-bands.json` and their schemas; `slice-report.json` gains `review_ledger` |
| Expectations | | unchanged for every Alpha 1 case: no expectation was edited, and nothing was added or changed because of how any system performs |

The manifest and consumer contract stay at `0.1.0`: no manifest field was added. The Alpha 1 reference consumer
(`examples/consume_snapshot.py`) ran unchanged on a trial build of the current content (verification clean, two
independent builds byte-identical) because the new content is in additional listed files. The release itself is `releases/beta.1.md`.
