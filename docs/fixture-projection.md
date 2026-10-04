# Deterministic fixture projection and lineage rules

Status: ruleset `1.0.0`. Normative data: `projections/ruleset.json`, `schemas/fixture.schema.json`.
Implementation: `src/ner_evidence/project.py`.

## Model

```text
Case (authored, reviewable reasoning)
  └─ projection p ∈ ruleset, applicable to the case
       └─ Fixture: executable text + spans + lineage
```

A **Case** is the only place expectations originate. A **Fixture** is build output. A **Scenario**
(reusable context such as "log line" or "JSON string") is a projection entry: it can wrap text but has no
vocabulary for saying anything about entities.

## Construction rule

```text
fixture.text = prefix + T(seg0) + T(span0) + T(seg1) + T(span1) + ... + T(segN) + suffix
```

`T` is a pure per-segment text transform; `prefix`/`suffix` are fixed literals. Fixture offsets are
computed from this construction, never by searching, so repeated surfaces cannot be mislocated.

| Projection | Wrapper / transform | Applies |
| --- | --- | --- |
| `plain` | identity | always; cannot be excluded |
| `quoted` | wrapped in `"` | always |
| `log-line` | `ts=... level=info msg: ` + text + ` ctx=none` | always |
| `json-string` | `{"message": "` + JSON-escaped text + `"}` | always |
| `email-like` | fixed header and footer | always |
| `nfd-decomposed` | Unicode NFD | only if NFD differs from the NFC text |

## Rules that make projections safe

1. **No invented expectations.** The fixture has exactly the Case's spans, in order, each with the same
   `expect` and `case_span_index`. The verifier rejects added, dropped or re-labelled spans.
2. **Surface transforms are declared.** A fixture surface must equal `T(authored surface)`. Nothing else may
   alter a surface.
3. **Wrappers are name-neutral.** No wrapper may contain the surface of any authored expectation
   (checked across the whole corpus). Wrappers add context, never candidates.
4. **Meaning-changing projections are opted out, with a reason.** A case whose point is, for example,
   quotation-mark boundaries sets `projections_excluded: [{projection_id, reason}]`. Exclusion is explicit
   and reviewable; it is never inferred.
5. **NFD safety.** Segment-wise NFD must equal whole-text NFD, otherwise projection fails loudly
   (the case must exclude it).
6. **Offsets in three units.** Code points (canonical), UTF-8 bytes, UTF-16 code units, all verified for
   consistency, so consumers in Python, Rust and JavaScript do not have to re-derive them.

## Lineage

Every fixture records `case_id`, `case_digest` (SHA-256 of the Case's canonical JSON), `projection_id`,
`projection_version` and `ruleset_version`. The verifier checks that:

* the Case exists and its current digest equals `case_digest` (a stale fixture is an error);
* the projection and versions exist in the ruleset in use;
* the fixture is reproducible byte-for-byte from the Case and projection;
* every applicable `(case, projection)` has a fixture and no fixture lacks one.

Fixtures are not hand-edited and are **not committed** outside snapshots; `python -m ner_evidence project`
regenerates them, and a snapshot embeds its own copy together with the Cases it came from.

## Determinism

Output depends only on Case content and the ruleset: records are sorted by `fixture_id`, serialized as
canonical JSON, and contain no timestamps or environment data. Tests regenerate in a different input order and
under different `PYTHONHASHSEED` values and require identical digests.

## Versioning

Changing wrapper text, a transform or applicability bumps the projection `version` and `ruleset_version`.
Existing snapshots keep their fixtures and remain verifiable (their embedded ruleset is authoritative for them).

## Recorded follow-up debt

* No punctuation-variant or whitespace-variant projections yet, because each needs per-case semantic review
  to prove it preserves the expectation. Candidate Beta projections: Markdown list item, CSV cell, trailing
  ellipsis, full-width punctuation for Korean.
* No case-mutating projections (case folding, ALL CAPS): they can change the correct answer and so require
  authored variants, not generated ones.
