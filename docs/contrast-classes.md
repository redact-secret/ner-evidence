# Contrast classes

A **contrast class** names the linguistic contrast a case was written to probe, independent of the broader
collision, ambiguity and boundary dimensions. It is the unit in which authored rationale and remaining gaps are
reported for the harder language-specific slices.

* Field: `dimensions.contrast_classes` (optional list), schema `1.1.0`.
* Vocabulary and the authored rationale of every class: `taxonomy/person.taxonomy.json`, `dimensions.contrast_class`.
  Each definition says what the class is and **why** it is a contrast worth testing.
* Language prefix: a class id starts with the language of the case (`ko-...`, later `en-...`); the validator
  rejects a class from another language.
* Counts per class, per language, are in the generated `evidence-coverage.md` (dimension `contrast_classes`) and
  floors are in `evidence/slice-targets.json` (`contrast-*`). Remaining gaps are listed there as `known_gaps`.

Classes are assigned only to cases authored from Beta 1 on; earlier cases are not retro-tagged (recorded as the
known gap `contrast-classes-beta-cases-only`).

## Korean classes (Beta 1)

| Class | Group(s) it lives in | Minimal-pair idea |
| --- | --- | --- |
| `ko-particle-allomorph` | `particle-context` | 는/은, 를/을, 와/과, 랑/이랑, 로/으로 (and ㄹ-final 로) after vowel- vs consonant-final names |
| `ko-name-final-syllable-trap` | `surname-false-positive-trap` | a name whose last syllable equals the particle that follows (지은+은, 하이+가, 정유도+도) |
| `ko-particle-stacking` | `particle-context` | 에게는, 에서도, 에게만, 까지도, 으로부터, 한테도, 이야말로 |
| `ko-copula-quotative` | `particle-context` | 입니다, 이다, 이라고, 이라는, 이며 after names |
| `ko-genitive-apposition` | `particle-context` | 의, 이자 |
| `ko-honorific-suffix` | `title-honorific` | spaced vs attached 님/씨/군/양, 팀장님, 박사, 께서 |
| `ko-surname-prefix-trap` | `surname-false-positive-trap` | 정부 vs 정부영, 조사 vs 조사랑, 배우 vs 배우진 |
| `ko-noun-name-homograph` | `common-word-collision` | 가람, 한울 as noun vs name |
| `ko-spacing-variation` | `spacing-variation` | detached particles, spaced surname/given, attached titles |
| `ko-separator-punctuation` | `punctuation-boundary`, `spacing-variation` | middle dot, slash, comma without space, corner brackets, curly quotes |
| `ko-romanized-hangul-mixture` | `mixed-script` | Hangul + Latin parenthetical, Latin name with a Korean particle |
| `ko-script-boundary` | `mixed-script` | 3팀김하나, A팀의 최지훈, 2024년박서연 |
| `ko-hanja-annotation` | `mixed-script` | Hangul(hanja) and hanja(Hangul) |

Classes other than the two lexical ones (`ko-surname-prefix-trap`, `ko-noun-name-homograph`) include cases with
rare surnames next to common-surname cases, so they are not exercised only on names a frequency list contains.

## English classes (Beta 1)

| Class | Group(s) it lives in | Minimal-pair idea |
| --- | --- | --- |
| `en-log-line` | `list-and-structured-text` | `actor=Dana Whitlow` vs `service=Marlowe Gateway`, `thread=Hunter`, stack-frame class names |
| `en-key-value-label` | `list-and-structured-text` | the identical value under `Name:` vs `Country:`/`City:` (Jordan, Charlotte); `Attn:` person vs committee; court captions |
| `en-table-or-columns` | `list-and-structured-text` | pipe, tab and column rows with a city cell beside a name cell |
| `en-delimited-row` | `list-and-structured-text` | quoted inverted names in CSV, semicolon and pipe rows without spaces |
| `en-punctuation-dense` | `punctuation-boundary` | nested quotes, bracket-and-slash contacts, repeated `!!!`, semicolon author lists with initials, post-nominal degrees |
| `en-markup-embedded` | `punctuation-boundary` | `**bold**`, `_italic_`, `<b>` tags, Markdown link text |
| `en-honorific-variant` | `title-honorific` | stacked titles, Mx., Dame, Hon., Ms without a period, `, PhD`, `The Rev. Dr. ... Jr.` |
| `en-common-word-name` | `common-word-collision`, `sentence-initial-trap` | `Will you ask Will to sign the will?`, `Bill paid the bill`, recipients Hunter and Mason vs virtues in a list |
| `en-lookalike-entity` | `organization-collision` | brand modifier (`Her Marlowe handbag`), named storm, prize, eponymous effect |

Convention added with these cases: post-nominal degrees and honours, and titles written without a period, are
excluded from the PERSON span like prefixed titles (`taxonomy/person.taxonomy.json`, `language_profiles[en]`).

## Adding a class

1. Add the id and a definition that states the contrast and why it matters to `dimensions.contrast_class`.
2. Tag at least a minimal pair of cases with it.
3. Add a floor in `evidence/slice-targets.json`, or record the shortfall as a known gap.
