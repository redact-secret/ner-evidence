# Independent review workflow

Alpha 1 evidence was author-only. This page defines how independent review is recorded, what makes a review
count, and what stays visible. Tooling: `src/ner_evidence/reviews.py`, `python -m ner_evidence review ...`.

## Principles

1. **A review is an opinion about exact content.** Every verdict names the case and the `subject_digest`, the
   SHA-256 of the case without its `review` block. Any later edit to the text, spans, dimensions, rationale,
   evidence class or sources changes the digest, so earlier verdicts no longer count. Nobody, reviewer or
   author, can change what was reviewed (for instance rewrite provenance after approval) without the review
   status falling back to `author-only` in plain sight.
2. **Status is derived, never hand-set.** `review.factual` and `review.linguistic` in a case file must equal the
   status derived from the ledger; `python -m ner_evidence review check` (part of `check`) fails otherwise and
   `review sync` rewrites only those two fields.
3. **Reviewers do not edit cases.** A verdict can carry a `proposed_change` as text. Applying it is an ordinary
   change by a maintainer, which creates a new digest and therefore needs a fresh verdict.
4. **The ledger is append-only** relative to the base branch (`review immutability` gate). A reviewer who changes
   their mind appends a new verdict; the latest verdict per reviewer on the current digest counts.
5. **Disagreement stays visible.** One counting `disagree` on the current digest makes the status `disputed`. Disputed
   cases are listed in `docs/evidence-coverage.md` and in every snapshot's `slice-report.json`.
6. **Models are not reviewers.** A model's output, or agreement between models, is never a verdict. Reviewers judge
   from the text and the written span conventions.

## Records

| File | Contents |
| --- | --- |
| `evidence/reviews/reviewers.json` | Pseudonymous reviewer registry (`rev/<pseudonym>`): languages, facets, qualification, `independent_of_authors`, status. No real name, email or other personal identifier. |
| `evidence/reviews/ledger.jsonl` | One canonical JSON event per line: `request` (a review is wanted, with a role) or `verdict` (`agree`, `disagree`, `abstain`, with a comment). Event ids are derived from content, so an edited line is detected. |
| `schemas/review-event.schema.json`, `schemas/reviewers.schema.json` | Shapes of the above. |

Facets: `linguistic` (are the expectations and span boundaries right under the language conventions) and
`factual` (is any factual claim, citation or provenance statement right). The `schema` facet stays
`machine-validated`.

## Derived status per facet

| Condition on the current digest | Status |
| --- | --- |
| at least one counting `disagree` | `disputed` |
| else at least one counting `agree` | `independently-reviewed` |
| else | `author-only` (`not-required` is kept as is) |

A verdict **counts** only if its reviewer is registered, `active`, attests `independent_of_authors`, and is
registered for the case's language and the facet. Other verdicts are kept and reported as uncounted.

## Roles and requests

| Role | Judges |
| --- | --- |
| `en-annotator` | English cases, linguistic facet (span boundaries for titles, possessives, initials, structured text) |
| `ko-native-linguist` | Korean cases, linguistic facet (particles, honorifics, spacing, name vs noun, romanization) |
| `factual-checker` | factual facet of any case (citations, eponyms, cited reference rules) |

```bash
python -m ner_evidence review request --language ko --facet linguistic --limit 60   # append request events, prioritized
python -m ner_evidence review packet  --language ko --facet linguistic --limit 60 --out ko-packet.md
python -m ner_evidence review packet  --language ko --facet linguistic --limit 60 --blind --out ko-blind.md
python -m ner_evidence review sync                                                  # after verdicts are appended
python -m ner_evidence review check                                                 # gate
python -m ner_evidence review summary
```

Requests are prioritized: genuinely-ambiguous cases first, then cases with non-trivial boundaries or contrast
classes, then collisions, then the rest. A **blind** packet hides the expected labels and the rationale, so a
reviewer labels spans independently; a maintainer unblinds and records `agree` or `disagree`, and the blind
labels stay in the verdict comment. That gives an agreement measure instead of an anchored approval.

## How a reviewer works

1. A maintainer registers the reviewer (pseudonym, languages, facets, qualification, independence attestation)
   in `evidence/reviews/reviewers.json` in a reviewed change.
2. The reviewer receives a packet and answers per case.
3. A verdict line is appended to `ledger.jsonl` (by the reviewer's own change or by a maintainer transcribing it).
   `python -m ner_evidence review verdict --case <id> --facet linguistic --reviewer rev/<pseudonym> --verdict agree --comment "..."`
   computes the digest and the event id for the current content and appends the line.
4. `review sync` updates the derived statuses; `check` must pass.

## Snapshot metadata

A snapshot embeds `reviews/reviewers.json` and `reviews/ledger.jsonl`, re-derives every case's status when it is
verified, and carries the ledger summary in `slice-report.json` (`review_ledger`: counts of independently
reviewed cases per language and facet, open requests, stale events, uncounted verdicts and the disputed case
list). The manifest `review_summary` counts statuses per facet as before.

## Status at Beta 1

The workflow is implemented and tested end to end (see `tests/test_reviews.py`). Review requests (linguistic, and factual for cases that cite a reference) are in the
ledger for English and Korean linguistic review. **No independent reviewer is registered and no verdict has been
recorded**, so every case remains `author-only`; the two independent-review floors stay waived and the gap
`no-independent-review` stays open. Reviewing Korean cases needs a native speaker or linguist; that cannot be
substituted by tooling or by a model.
