# Handoff to ner-eval: what the snapshot contract does and does not provide

`ner-eval` is the primary consumer of snapshots (see `snapshot-and-consumer-contract.md`). This page lists
everything `ner-eval` needs that is **not** expressed in the evidence snapshot, so that no hidden coupling
grows around it. Nothing here is implemented in this repository, and this repository imports nothing from
`ner-eval`.

## Provided by the snapshot

* Fixtures (text + spans in three offset units) with `person` / `not-person` / `either` expectations.
* Cases with dimensions, ambiguity level and rationale, joined by `case_id`.
* Span-boundary conventions per language (`taxonomy.json`).
* Provenance, redistribution level, review status per case, known gaps, waived targets.
* Pinning by `snapshot_id` and `content_digest`, plus a verification recipe.

## Not provided; decisions `ner-eval` must make and document on its side

1. **Matching rule**: exact span, overlap, or boundary-tolerant matching. The snapshot defines the boundary
   convention only; it does not define how much boundary error is acceptable.
2. **Treatment of `either`**: exclude from precision/recall, score leniently, or report separately. The
   snapshot only guarantees these are honestly ambiguous.
3. **Treatment of unannotated text**: a PERSON prediction on text with no overlapping span is *not* labelled
   wrong by the snapshot (only `not-person` spans and `no-person` cases assert absence). Whether such
   predictions count as false positives is a scoring choice and must be stated with results.
4. **Label mapping**: how a model's label set maps to `PERSON`.
5. **Slice weighting and aggregation**: per-slice vs micro/macro averages, minimum slice sizes, confidence
   intervals. The slice report gives counts, not statistical guidance.
6. **Which projections to run**: all fixtures, or a subset such as `plain` only. Fixtures from one case are
   correlated; averaging across fixtures weights multi-projection cases more. `ner-eval` should aggregate to
   case level or declare otherwise.
7. **Model, runtime, threshold and support-status reporting**: outside the evidence layer by design.

## Known contract gaps (candidates for contract `0.2.0`)

* No per-span *alternate acceptable boundaries* (for example, honorific included vs excluded). Consumers
  needing leniency must implement tolerance themselves.
* No tokenization-level annotation (BIO tags): consumers must align spans to their tokenizer.
* Fixtures do not repeat Case dimensions; consumers must join to `cases.jsonl`. If `ner-eval` needs denormalized
  slices at fixture level, request it as a contract change rather than parsing ids.
* No machine-readable "superseded by" pointer between snapshots yet; use release notes.

## How to request a change

Open an issue in `ner-evidence` describing the missing information as *evidence* (what is true about the
text), not as a scoring preference. Contract additions bump `consumer_contract_version` and create new
snapshots; they never alter existing ones.
