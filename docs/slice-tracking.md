# Balanced evidence slices and gap tracking

Purpose: make it impossible for an architecture comparison to be dominated by easy names without anyone
noticing. This page explains how slices are defined and enforced. The current numbers are in
[`evidence-coverage.md`](evidence-coverage.md) (generated; CI fails if stale).

## Principles

* Slices are defined **only** from authored, model-neutral dimensions. No model output, score or threshold
  appears anywhere in slice definitions, so the corpus cannot be tuned toward any system.
* The unit is the **Case**, not the fixture. Fixtures of one case are correlated, and Korean cases accept
  more projections than English ones, so fixture counts overweight Korean.
* Targets are **floors**, stored in `evidence/slice-targets.json`. They are regression guards and
  "this slice exists" guards, not statistical-adequacy claims: 60 cases in a slice supports a smoke
  comparison, not a tight confidence interval.
* A missed floor either fails the build or carries an explicit written **waiver** that is copied into the
  snapshot manifest. Known gaps live in the same file and are copied into the snapshot as well.

## Slices tracked

| Required slice | Dimension | Enforced as |
| --- | --- | --- |
| EN vs KO balance | `language` | per-language minimums and an EN share between 40% and 60% |
| Common vs uncommon name | `familiarity` (`common`; `rare`+`novel` = `uncommon`), `familiarity_basis` | per-language minimums; uncommon share of name-bearing cases ≥ 25%; separate floors for reference-checked and constructed names |
| Ambiguous vs unambiguous | `ambiguity.level` | per-language minimums; ambiguous share ≥ 35%; honest-ambiguity (`either`) minimums |
| Single vs multi-token | `token_class` (derived from the focus span) | per-language minimums on both sides; KO multi-token floor is lower because Korean names are normally written without spaces |
| Common-word collision | `collision_classes: common-word` | per-language minimum |
| Organization collision | `collision_classes: organization` (and `product-brand`) | per-language minimum |
| Location collision | `collision_classes: location` | per-language minimum |
| Collision balance | `collision_classes` × `kinds` | for organization, location and product-brand, per language: separate floors for cases with a `person` span, a `not-person` span and an `either` span, so a collision slice cannot be all negatives |
| Temporal, eponym, work-title collision | `collision_classes` | per-language minimums (small, see gaps) |
| Mixed-script | `context_types: mixed-script-sentence`, `script: mixed`/`han` | overall and EN-profile minimums |
| Boundary / tokenization | `boundary_tags`, `context_types` (list, structured, adjacent names, honorifics, sentence-initial, casing, possessive, particle-attached) | per-language minimums |
| Negative-only texts | `context_types: no-person` | per-language minimum |
| Controls must not dominate | common ∧ unambiguous | ceiling: at most 35% of all cases |
| Independent review | `review.factual/linguistic` | floor **waived** (see below) |

## Honest definition of "uncommon"

`uncommon` means the **name is rare or constructed in the language community** (`rare`, `novel`). It is a
model-neutral statement about the name. It does not mean unseen by any model: the repository cannot know what any
model saw. A consumer who needs a true held-out guarantee must obtain it from model provenance, which is outside
this repository. Alpha 1 called this slice "unseen"; see [`familiarity-and-rarity.md`](familiarity-and-rarity.md)
for the rename, the documented basis of each label and the reference bands.

## Known gaps and waivers

Gaps are recorded as data in `evidence/slice-targets.json` (`known_gaps`, count/ratio `waiver`) and flow into
`slice-report.json` and `manifest.json` of every snapshot. At Alpha 1 the important ones are:

* **No independent review** of any case (both independent-review targets are waived with a written reason).
* **Synthetic-only**: no naturally occurring text; real-world distribution is not represented.
* **Familiarity labels are mostly author judgments**; only `reference-frequency` cases are surname-checked against a public table.
* **No inter-annotator agreement** for the span conventions.
* Plural/family references have no convention yet; the affected cases use `either`.
* Only Latin, Hangul and hanja scripts; Korean cases are South Korean orthography only.
* Eponym and work-title slices are small.

## Workflow

```bash
python -m ner_evidence slices         # evaluates targets, fails on unmet non-waived targets
python -m ner_evidence report --write # regenerates docs/evidence-coverage.md
python -m ner_evidence report         # CI: fails if the file is stale
```

To change a floor, edit `evidence/slice-targets.json` in the same change as the evidence that motivates it and
say why in the PR. Lowering a floor to make a build pass is exactly what the waiver mechanism makes visible:
use a waiver with a reason instead, so the shortfall ships with the snapshot.
