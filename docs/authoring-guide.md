# Authoring guide for PERSON cases

Read `taxonomy-and-case-schema.md` and `provenance-and-privacy-policy.md` first.

## Workflow

1. Pick the failure mode or ambiguity you want to probe. If you cannot say it in one sentence, the case is
   not ready: that sentence is the `why`.
2. Write the smallest natural sentence that exhibits it. Prefer minimal pairs: the same surface form with
   opposite expectations (`will-modal-question` / `will-given-name`).
3. Mark spans with `python -m ner_evidence annotate '...[[p:Name]]...[[n:Decoy]]...'` and paste the
   resulting `text` and `expectations` into a case in the matching `evidence/cases/person/<lang>/<group>.json`.
4. Fill in dimensions. `script` and `token_class` are checked against the focus span; the rest is your judgment.
5. Run `python -m ner_evidence fmt` (canonical formatting) then `python -m ner_evidence check`.

## What a good `why` says

* Names the failure mode ("a lookup on surface form cannot tell the month from the name").
* Is independent of any model: never "to see if X handles it".
* Explains boundary decisions when the case pins one ("the period inside `Jr.` is part of the span").

## When the answer is not clear

Do not guess a label to keep the corpus tidy. If the text does not decide it, use `either`, set the case
`genuinely-ambiguous`, and explain what is missing. If you are unsure about a linguistic judgment, leave
`review.linguistic` at `author-only` and set `evidence_class` to `research-needed` rather than overstating it.

## Things that are always wrong

* Mentioning a model, product, threshold, score or support status in metadata.
* Adding a case because a model fails (or passes) it. Cases come from linguistic reasoning, not model behavior.
* Copying text from a corpus, article or message without a registered source.
* Using a real, identifiable person's name.
* Hand-editing generated fixtures or snapshots.
