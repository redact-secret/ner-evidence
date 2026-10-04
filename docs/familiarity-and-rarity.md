# Familiarity and rarity semantics

Status: taxonomy `0.2.0`, schema `1.1.0`. Replaces the Alpha 1 wording "seen / unseen".

## What the label says, and what it does not

`dimensions.familiarity` says how routinely the **focus name** is used **in its language community**:

| Value | Meaning |
| --- | --- |
| `common` | Every checked component of the name is in routine public use (it would appear in a national top-names or surname list). |
| `rare` | A genuine name with at least one component that is attested but uncommon. |
| `novel` | A constructed or very unusual name with at least one component that is not found in the name references for its community (for reference-checked cases: absent from the registered table), so a name list built from them would not contain the combination. A real but rare surname absent from a US-centric table can therefore be `novel` by the reference. |
| `not-applicable` | The focus span is not a name candidate that has a familiarity (a plain noun). |

It is **not** a statement about any model. This repository cannot know what any model has seen, so nothing here is
named "seen" or "unseen". The Alpha 1 slices `seen` / `unseen` and the group `unseen-name` are renamed:

| Alpha 1 | Beta 1 |
| --- | --- |
| slice field `seen` = `seen` / `unseen` | `name_commonness` = `common` / `uncommon` (`rare` + `novel`) |
| targets `en-seen`, `en-unseen`, `ko-seen`, `ko-unseen`, `*-unseen-share` | `en-common-name`, `en-uncommon-name`, `ko-common-name`, `ko-uncommon-name`, `*-uncommon-name-share` |
| case group `unseen-name` (ids `person/<lang>/unseen-name/<slug>`) | `uncommon-name` (ids `person/<lang>/uncommon-name/<slug>`); the slug is unchanged |

A consumer that needs a held-out guarantee must get it from model provenance, which is outside this repository.

## The documented basis (`familiarity_basis`)

Every case with a familiarity label states how the label was established:

| Basis | Meaning | Checked |
| --- | --- | --- |
| `reference-frequency` | The label equals the band of the **surname** component in a registered public reference table. The given name is asserted by the author to be a very common one. | mechanically, from `evidence/references/name-frequency-bands.json` |
| `author-judgment` | Authored judgment against the criteria above; no reference was consulted for the case. | no |
| `constructed` | The author assembled the name (or a component) so that it is not attested. Only with `novel`. | no |

A `reference-frequency` case also carries `familiarity_reference: {source_id, component}`; the source must be a
registered `reference` source that is also listed in the case's `source_ids`, the component must occur in the
focus span, and the committed band for that component must equal the label. Cases written before Beta 1 are
backfilled as `author-judgment` (`common`, `rare`) or `constructed` (`novel`), which is exactly how Alpha 1 defined
them.

## Reference bands

| Language | Source | Band rules |
| --- | --- | --- |
| English | `src/ref-us-census-2010-surnames` (US Census Bureau, 2010 surname table of 162,253 names) | `common`: normalized surname ranks 1000 or better; `rare`: in the table but below rank 1000; `novel`: absent from the table (fewer than 100 occurrences) |
| Korean | `src/ref-ko-surname-population-2015` (Statistics Korea 2015 census table, read through English Wikipedia revision 1377792072) | `common`: listed and at least 0.5% of the 2015 population; `rare`: listed and below 0.5%. No `novel` band: the parsed table is partial |

Only the band of each cited surname is stored, never a count, rank or table row (minimization). The raw artifacts
are registered with their sha256 and are not committed. To re-derive and compare the committed bands:

```bash
python -m ner_evidence references verify --census-zip names.zip --kosis-wikitext kosur_rev.txt
python -m ner_evidence references audit  --census-zip names.zip --kosis-wikitext kosur_rev.txt   # informational
python -m ner_evidence references check                                                          # gate (no raw data needed)
```

`references audit` compares the Alpha-era author-judged labels with the surname band. Disagreement is reported,
not enforced: a `common` label on a surname the US table calls rare is usually a limitation of a US-centric table,
and a `novel` or `rare` label on a common surname is correct when the given name is the unusual part. The recorded
gaps are in `evidence/slice-targets.json`.

## Coverage growth

Beta 1 adds 39 cases to the `uncommon-name` group (19 English, 20 Korean): rare and absent English surnames with
very common given names, rare Korean one- and two-syllable surnames, and four constructed Korean names, each in
varied contexts (title, quotation, list, label, lowercase text, possessive, vocative, namesake road or company).
Alpha 1 had 69 English and 59 Korean uncommon-name cases; floors are now 100 and 90.
