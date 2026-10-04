# Immutable snapshot manifest, digests and consumer contract

Status: manifest `0.1.0`, consumer contract `0.1.0` (Alpha: may change before Beta; every change is versioned).
Normative: `schemas/snapshot-manifest.schema.json`, `schemas/fixture.schema.json`, `schemas/case.schema.json`.
Reference implementation: `src/ner_evidence/snapshot.py`.

Consumers (primarily `ner-eval`) depend on **snapshot artifacts only**. They must not read `evidence/`,
`src/` or any other source-tree layout, and nothing in this repository imports from a consumer.

## Layout of a snapshot

```text
snapshots/index.json                       list of released snapshots (append-only)
snapshots/<snapshot_id>/
  manifest.json                            this contract (not part of content_digest)
  cases.jsonl                              authored Cases, canonical JSON, sorted by id
  fixtures.jsonl                           executable projections, canonical JSON, sorted by fixture_id
  sources.json                             provenance / license / privacy records
  taxonomy.json                            vocabularies, language profiles, span conventions
  projections.json                         the projection ruleset that produced fixtures.jsonl
  slice-report.json                        slice counts, target results, waivers, known gaps
  references/name-frequency-bands.json    derived surname bands cited by reference-frequency cases (present from Beta 1 when any case cites one)
  schemas/*.schema.json                    schemas the content conforms to
```

JSONL records are canonical JSON: UTF-8, keys sorted by code point, no insignificant whitespace, one record per
line, LF terminated.

## Manifest fields

| Field | Meaning |
| --- | --- |
| `snapshot_id` | `<scope>-<release_label>-<first 12 hex of content_digest>`, e.g. `person-en-ko-alpha.1-0123456789ab` |
| `scope`, `release_label`, `stage` | what it covers, human label, `alpha`/`beta`/`stable` |
| `schema_version`, `taxonomy_version`, `projection_ruleset_version`, `consumer_contract_version` | versions the content conforms to |
| `counts` | cases, fixtures, sources, and per-language counts |
| `source_manifest_digest` | SHA-256 of `sources.json` bytes |
| `digest_spec`, `content_digest` | see below |
| `files[]` | `{path, sha256, bytes}` for every content file |
| `generation` | tool name, version and a digest of the tool source that generated it |
| `redistribution` | most restrictive redistribution level among the sources actually used |
| `review_summary` | how many cases are `author-only`, `independently-reviewed`, ... per facet |
| `waived_targets`, `known_gaps` | coverage targets knowingly unmet and gaps recorded as debt |

There are **no timestamps** and no environment data: a snapshot is a pure function of its content.

## Digest algorithm (`ner-evidence-snapshot-digest/1`)

```text
content_digest = SHA-256( "ner-evidence-snapshot-digest/1\n"
                          + for each file in files[] sorted by path (code point order):
                              "<sha256 hex of file bytes>  <path>\n" )
```

`manifest.json` is excluded, which is why it can contain its own `content_digest`. The identity of a snapshot is
therefore a function of every content byte (cases, fixtures, sources, taxonomy, ruleset, schemas, slice
report). Any change, however small, yields a different `snapshot_id`.

## Consumer verification procedure

1. Read `manifest.json`; validate against `schemas/snapshot-manifest.schema.json`.
2. For every `files[]` entry: file exists, byte length and SHA-256 match. Reject unlisted files.
3. Recompute `content_digest` by the algorithm above; it must equal the manifest value and `snapshot_id`'s suffix.
4. Compare `snapshot_id` to the id you pinned. **Pin the full `snapshot_id` (and ideally `content_digest`).**
5. Check `schema_version` / `consumer_contract_version` against what you support; refuse unknown majors.

The reference tool also performs deeper checks (schema + semantic validation, lineage, projection
reproducibility, provenance, privacy, slice-report consistency):

```bash
python -m ner_evidence snapshot verify --path snapshots/<snapshot_id>     # works on a downloaded copy
python -m ner_evidence snapshot verify                                   # every released snapshot
```

A dependency-free reference consumer implementing steps 1-5 and the fixture/case join is in
`examples/consume_snapshot.py`; it imports nothing from this package and is exercised by the test suite.

## Reading the data

* A **fixture** is the unit to run a model on: `text` plus `spans`. Join to its Case by `case_id` in
  `cases.jsonl` for dimensions, ambiguity and rationale. Fixture records carry `language` only, on purpose.
* Offsets: `start`/`end` code points, `utf8_*` bytes, `utf16_*` code units, half-open. Use whichever your
  runtime indexes by; they are verified consistent.
* **Expectation semantics**
  * `person`: a PERSON mention. Counting it as found or missed is the consumer's scoring decision.
  * `not-person`: no PERSON prediction should overlap this span.
  * `either`: genuinely ambiguous. Do not score as a hard positive or negative; report it separately.
  * Text outside any span is **unannotated**. It is not asserted to be free of persons, except in cases whose
    context type is `no-person`, where the whole text has no person.
* `taxonomy.json` `language_profiles[].conventions` define span boundaries (titles, possessives, Korean
  particles). A prediction that includes a particle or title is a boundary error under these conventions.
* Slice by Case dimensions. `slice-report.json` shows counts and known gaps. Treat tiny slices as anecdotes.

## Immutability

Released snapshots are immutable. `python -m ner_evidence snapshot immutability` (run by CI against the base
branch) fails if any file under a released `snapshots/<id>/` is modified or deleted, or an `index.json` entry is
changed or removed. Correction = a new release label = a new `snapshot_id`; the old snapshot stays verifiable
and is marked superseded in release notes, never edited. Building a label that was already released with
different content is refused.

## Redistribution

`redistribution` is the aggregate of source constraints. `internal-only` snapshots must not leave the
organization. The Alpha snapshot is `internal-only` because the repository license is undecided; this is
reported, not hidden, and blocks the public-release gate.

## Out of scope for this contract (see `docs/handoff-ner-eval.md`)

Scoring rules, boundary tolerance, label mapping, metric definitions, model comparison, thresholds, support
status and release policy are owned by consumers. This contract carries evidence and its provenance.
