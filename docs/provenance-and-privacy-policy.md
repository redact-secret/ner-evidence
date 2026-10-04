# Provenance, licensing, privacy and safe-data policy

Applies to every file under `evidence/`, `projections/`, `taxonomy/` and `snapshots/`. Rules marked
**[enforced]** are checked by `python -m ner_evidence check`; the rest are review obligations.

## 1. Principles

1. Do not commit personal data because the project is about names. Names are the *subject*; people are not.
2. Prefer synthetic or generic-composed names wherever a real identity is not essential to the case.
3. Every body of evidence has a registered `Source` record. A case without provenance does not exist. **[enforced]**
4. Licensing facts are recorded before use, not after. Uncertainty is recorded as `pending`/`internal-only`, never guessed.

## 2. What may be committed

| Material | Rule |
| --- | --- |
| Project-authored sentences with generic, constructed or common names | Allowed. Source kind `project-authored`, `name_origin` `synthetic` or `generic-composed`. **[enforced]** |
| Names of real, identifiable individuals (public figures included) | Not in Alpha. A later release may admit them only for a case that cannot be expressed otherwise, with a cited public source and independent legal review. **[enforced for authored sources]** |
| Public corpus excerpts | Only with: exact origin locator, version/date, SHA-256 of the retrieved artifact, retrieval date, an allow-listed license (or reviewed `LicenseRef-`), listed transformations, known bias, independent legal review. **[enforced]** |
| Licensed (non-open) corpora | Same as public, plus the contractual redistribution limit recorded as `internal-only` or `cite-only`. Never placed in a snapshot that is redistributed. **[enforced via redistribution aggregation]** |
| Customer data, private messages, health records, unpublished employee/user lists, scraped personal data | **Prohibited.** `contains_personal_data: true` is rejected. **[enforced]** |
| Raw corpora, dumps, spreadsheets, archives, databases | Prohibited. Only `.json`, `.jsonl`, `.md` are accepted under scanned directories and files are size-capped. **[enforced]** |

### Public-name examples

Common given-name/surname combinations are used as *generic compositions* (the way "John Smith" is used). A
case must never be written to depict a specific real person. If a real public figure's name is genuinely
required for a linguistic point, record `name_origin: public-figure`, cite why, and obtain legal review; the
Alpha tooling refuses this combination for authored sources, so doing so is an explicit policy change.

### Licensed corpora and generated variants

* A generated fixture inherits the **most restrictive** redistribution level of every source its Case
  references. A snapshot's `redistribution` field is that aggregate. **[enforced]**
* A snapshot with `internal-only` content must not be published outside the organization.
* Generated variants (projections) add no new facts. They are build output and carry the source constraints of
  their Case through lineage.

## 2a. Imported corpora and reference sources (Beta 1 controls)

Every non-authored source declares **how** it reaches the evidence (`use`) and carries a machine-checked `policy`.
Rules marked **[enforced]** are checked by `python -m ner_evidence provenance` (and so by `check` and snapshot build).

| `use` | Meaning | What a case may store |
| --- | --- | --- |
| `authored` | written by the project | the project's own text |
| `text-incorporated` | excerpts from a public or licensed corpus | a minimized excerpt, at most `policy.max_excerpt_chars` characters **[enforced on every citing case]**; names that occur naturally in the source are `replaced-with-synthetic` **[enforced]** |
| `derived-labels-only` | only a label derived from a table (for example a surname frequency band) | the label, never the table row, count or rank (`evidence/references/name-frequency-bands.json`) |
| `cited-rule` | a rule or fact cited as justification | nothing from the source; the case carries `citations[]` with the article or section **[enforced for `reference-backed` cases]** |

`policy` fields: `text_redistribution` (must agree with `license.redistribution` **[enforced]**), `attribution_required`
with the credit line in `attribution` **[enforced]**, `share_alike` (only with a share-alike license **[enforced]**),
`max_excerpt_chars`, and `names_in_cases`. Imported corpora also still need an exact version, `artifact_sha256`,
`retrieved_on`, an allow-listed license (or reviewed `LicenseRef-`), listed transformations, known bias and independent
legal review **[enforced]**. No source of kind `public-corpus` or `licensed-corpus` may back an authored case, and a
`corpus-backed` case needs a corpus source **[enforced]**.

Synthetic, reference-backed and corpus-backed evidence stay distinguishable: `evidence_class` is
`authored-*`, `reference-backed` or `corpus-backed`, and the slice dimension `provenance_basis`
(`synthetic-authored`, `reference-backed`, `corpus-backed`) counts them separately in every report and snapshot.
Sources whose `use` is `derived-labels-only` or `cited-rule` put no source text in a snapshot, so they do not lower the
snapshot's `redistribution` level; the public-release gate still requires their legal review.

Personal data: a source with `contains_personal_data: true` is rejected. Naturally occurring names may be mentioned in a
source record only when nothing is stored (`derived-labels-only`, `cited-rule`) or when they are replaced before they
enter a case. See `docs/corpus-candidates.md` for the corpora considered and why none is imported yet.

## 3. Automated privacy lint **[enforced]**

`python -m ner_evidence privacy` rejects, anywhere in scanned directories: email addresses outside reserved
domains (`example.*`, `.invalid`, `.test`, `.example`, `.localhost`), URLs to non-reserved hosts, phone-like
digit runs (9+ digits), Korean resident registration numbers, US SSN-shaped values, Luhn-valid card numbers,
public IPv4 addresses, common credential formats (AWS, GitHub, Slack, API-key-like, JWT, private key blocks)
and private-data markers ("customer export", "internal use only", ...). Findings report rule and location, never
the matched value. The lint is a tripwire, not a guarantee: it does not replace reviewer judgment.

## 4. Review obligations

Review facets are tracked separately on each Case (`factual`, `linguistic`, `schema`) and on each Source
(`provenance`, `legal`). `author-only` is an honest status, not a defect; it is reported in every snapshot's
`review_summary` so consumers can see how much evidence has had independent review. A model's current output is
never a review. Agreement among models is never ground truth. The case review facets are derived from the
append-only review ledger and bound to exact case content; see [`review-workflow.md`](review-workflow.md).

## 5. Contribution checklist

1. Can the case use a synthetic or constructed name? If yes, use one.
2. Is every sentence written by you, or from a registered source with a locator, checksum and license?
3. Does the text contain anything that identifies a real, non-public person? Remove it.
4. Is `why` a reason a skeptical reviewer would accept, independent of any model?
5. Run `python -m ner_evidence check` and fix every finding. Do not edit the lint to make a case pass.

## 6. Public-release gate

`python -m ner_evidence provenance --public-release` fails while any source is `internal-only`/`cite-only`,
has a pending license, or lacks independent legal or provenance review. **It is expected to fail during the
private Alpha.** The repository license has not been chosen; choosing it is an owner decision recorded as
follow-up debt, not something this tooling guesses.

## 7. Recorded follow-up debt

* Choose the repository license; then update `src/project-authored-synthetic` and re-snapshot (new identity).
* Obtain independent provenance and legal review of the authored source.
* The privacy lint has no named-entity detector for real people; it cannot catch a real person's name
  embedded in an authored sentence. Human review is the only control there.
