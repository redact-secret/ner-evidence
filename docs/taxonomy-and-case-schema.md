# PERSON taxonomy, language profiles and Case schema

Status: schema `1.0.0`, taxonomy `0.1.0` (Alpha: contracts may still change before Beta).

Machine-readable sources of truth:

| File | Role |
| --- | --- |
| `taxonomy/person.taxonomy.json` | Entity definition, language profiles, span conventions, every controlled vocabulary |
| `schemas/case.schema.json` | Shape of an authored Case |
| `schemas/case-file.schema.json` | Shape of a file under `evidence/cases/` |
| `schemas/fixture.schema.json` | Shape of a generated fixture (see `fixture-projection.md`) |

This page explains the model; the JSON files are normative.

## Record types

```text
EntityType      PERSON (this release)
LanguageProfile en, ko: scripts and span conventions
Source          provenance record          -> provenance-and-privacy-policy.md
Case            authored reasoning unit    (this page)
FixtureProjection  generated executable form -> fixture-projection.md
SnapshotManifest   immutable release         -> snapshot-and-consumer-contract.md
```

`Scenario` (a reusable context wrapper) is realised as an entry in the projection ruleset rather than as
a separate record: a wrapper never carries expectations, so it cannot be a reasoning unit.

## What a Case contains

| Field | Meaning |
| --- | --- |
| `id` | `person/<language>/<group>/<slug>`. Semantic only: no issue numbers, stages, model names or scores. Group must exist in `case_groups` and be defined for the language. |
| `title`, `why` | What is tested, and why the case exists. `why` must explain the failure mode, not restate the title. |
| `text` | NFC-normalized context, at most 600 code points, no control characters. |
| `expectations[]` | Exact spans: `start`/`end` (code points, half-open), `surface`, `expect`. |
| `focus_span` | Which expectation the case is primarily about. |
| `dimensions` | Slice dimensions (below). |
| `ambiguity` | `level` plus a `note` explaining what is confusable and what resolves it. |
| `evidence_class` | `corpus-backed`, `reference-backed`, `tool-corroborated`, `authored-adversarial`, `research-needed`. |
| `source_ids` | Registered provenance records. |
| `review` | Three separate facets: `factual`, `linguistic`, `schema`. |
| `projections_excluded` | Projections that would change the meaning of this case, each with a reason. |

### Expectation kinds

* `person`: a PERSON mention here.
* `not-person`: name-like but not a person here. **No PERSON prediction should overlap this span.**
* `either`: both readings are defensible from the text alone. Consumers must not score it as a hard
  positive or hard negative. A case has an `either` span if and only if its ambiguity level is
  `genuinely-ambiguous`.

### Span conventions

Offsets are Unicode code points over NFC text. Spans never overlap, are sorted by `start`, and never begin or
end with whitespace. Per-language boundary conventions (titles, possessives, Korean particles, honorific
suffixes, spacing) live in `taxonomy/person.taxonomy.json` under `language_profiles[].conventions`.
They are part of the evidence: a boundary expectation is only meaningful together with the convention.

### Dimensions

| Dimension | Values | Notes |
| --- | --- | --- |
| `familiarity` | `common`, `rare`, `novel`, `not-applicable` | Model-neutral proxy for seen/unseen: `common` is "seen", `rare`+`novel` are "unseen". It describes the name in the language community, **not** any model's training data, which this repository cannot know. |
| `script` | `latin`, `hangul`, `han`, `mixed` | **Derived** from the focus span and verified. |
| `token_class` | `single`, `multi` | **Derived**: whitespace tokens in the focus span. |
| `ambiguity.level` | `unambiguous`, `context-resolvable`, `genuinely-ambiguous` | A case with any collision class cannot be `unambiguous`. |
| `collision_classes` | `common-word`, `organization`, `location`, `temporal`, `product-brand` | May be empty. |
| `context_types` | prose, sentence-initial, title-honorific, quotation, list, possessive, particle-attached, structured-text, dialogue, vocative, parenthetical, mixed-script-sentence, no-person | `no-person` iff no span expects `person`. |
| `name_features` | structure tags, language-specific ones prefixed `ko-` | Korean-only tags are rejected on English cases. |
| `boundary_tags` | punctuation, quote, honorific, particle, spacing, ... | Tag what makes the boundary non-trivial. |

## Model neutrality

Schemas use `additionalProperties: false` everywhere, so there is no field in which a model name, threshold,
support status or score could be stored. In addition, `forbidden_metadata_terms` in the taxonomy are rejected
in titles, rationales and notes (case text is exempt, because `Presidio` may legitimately be a surname).

## Validation

```bash
python -m ner_evidence validate     # schema + semantic checks
python -m ner_evidence fmt --check  # canonical formatting of authored files
python -m ner_evidence annotate 'Dr. [[p:Reyes]] visited [[n:Jordan River]].'   # compute spans
```

Semantic checks beyond JSON Schema: surface equals the text slice, spans sorted/non-overlapping, text is NFC,
derived dimensions match the focus span, vocabulary membership, ambiguity/`either`/collision consistency,
`no-person` consistency, group/language compatibility, identity rules, model-neutrality of metadata.

## Recorded follow-up debt

* `familiarity` is an authored judgment; Beta should corroborate against public name-frequency references.
* Handles/usernames and email-local-part names are out of scope for taxonomy `0.1.0`.
* No annotation guidelines for non-Latin, non-Hangul scripts or for code-switching beyond Korean/English.
