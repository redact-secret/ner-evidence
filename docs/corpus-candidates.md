# Corpus candidates considered for Beta 1

Beta 1 imports **no corpus text**. This page records what was looked at, what the publisher states, and what blocks
an import. Statements about licenses are what the publisher's own README says on the retrieval date (2026-10-04),
not legal advice; legal review of the exact version is a precondition for any import (`provenance.check_sources`).

## Gate every candidate must pass

1. Exact version and `artifact_sha256` of the file that would be used.
2. An allow-listed or reviewed license and an independent legal review of the underlying text rights, not only of the annotation layer.
3. `contains_personal_data: false` after transformation: naturally occurring names are replaced with synthetic names before a sentence frame enters a case (`policy.names_in_cases: replaced-with-synthetic`).
4. A cap on excerpt length (`policy.max_excerpt_chars`), enforced on every citing case.
5. Share-alike and attribution obligations compatible with the repository license, which is not yet chosen.
6. A written known-bias statement (domain, period, annotation guideline).

## Candidates

| Candidate | What the publisher states | Why it is not imported at Beta 1 |
| --- | --- | --- |
| KLUE benchmark (Korean) | Repository README: Creative Commons Attribution-ShareAlike 4.0. The origin and rights of the text behind the NER task data were not reviewed. | Names in news-style text are naturally occurring personal data and must be replaced; share-alike conflicts with an unchosen repository license; underlying text rights unreviewed. |
| Universal Dependencies, Korean GSD | README: UD annotations CC BY-SA 4.0; the sentences were collected by Google, which "asserts no ownership" and says some may be copyrighted in some jurisdictions; provided as is. | Underlying text rights are explicitly uncertain; requires legal review. |
| Universal Dependencies, English EWT | README: CC BY-SA 4.0. Underlying web text provenance not reviewed. | Same as above: naturally occurring names, share-alike, unreviewed text rights. |
| Corpora distributed under membership or publisher agreements (for example newswire NER sets) | Not evaluated. Commonly distributed under restrictive agreements; verify before any use. | Would be `licensed-corpus` with `internal-only` redistribution and could never enter a redistributed snapshot. |

## What exists instead

* **Reference-backed cases** that rest on a cited public rule (Hangul Spelling Rules Articles 41 and 48, Romanization of Korean Articles 3 and 4, a W3C article on personal names). Sentences are authored; the source is cited by article or section; nothing is copied.
* **Reference-checked familiarity labels** that use derived surname bands from the US 2010 Census surname table and the 2015 South Korean census surname table (`docs/familiarity-and-rarity.md`). Only band labels are stored.

Both stay clearly separate from synthetic evidence through `evidence_class` and the `provenance_basis` slice.
