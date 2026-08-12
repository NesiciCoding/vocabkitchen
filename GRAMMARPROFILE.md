# Grammar-profile data & provenance

The grammar profiler (`grammar_profile.py`) reports which grammatical
constructions a text uses and maps each to a CEFR level. The levels come from the
**CEFR-J Grammar Profile**, bundled in `GrammarProfile/` as a single CSV.

## Source

- **CEFR-J Grammar Profile** — `cefrj-grammar-profile-20180315.csv` from the
  [openlanguageprofiles/olp-en-cefrj](https://github.com/openlanguageprofiles/olp-en-cefrj)
  repository (file bundled here as `GrammarProfile/cefrj-grammar-profile.csv`,
  unmodified). It is a list of ~500 English grammatical items, each with a
  "shorthand code", a description, a sentence type, and level annotations against
  several frameworks (CEFR-J, the British Council/EAQUALS *Core Inventory*, the
  *English Grammar Profile* (EGP), and GSE Learning Objectives).
- **Copyright / licence** — the CEFR-J resources are © Tono Laboratory, Tokyo
  University of Foreign Studies, and are made available for research and
  commercial use **at no cost, provided the source is cited**. Cite as:

  > Tono, Y. (ed.) *The CEFR-J Grammar Profile*. Tono Laboratory, Tokyo
  > University of Foreign Studies. <https://www.cefr-j.org/>

  The upstream repository notes the grammar profile is only partially translated
  from the original Japanese (some `Notes` are in Japanese); this affects only the
  free-text notes, not the codes or levels used here.

## How levels are resolved

Each detector in `grammar_profile.py` declares the CEFR-J **shorthand code** it
corresponds to (usually the affirmative-declarative form of the construction).
At startup the tool reads the CSV and resolves that code's level, preferring the
`CEFR-J Level` column and falling back to `Core Inventory`, then `EGP`, when
CEFR-J itself is blank. Fine-grained sublevels are coarsened to the six CEFR
bands (`A1.2` → `A1`, `B1-C1` → `B1`, etc.). A few constructions use a documented
**fallback** level instead — either because their code carries no level in any
column (e.g. `had better`), or because no single CEFR-J code fits (the generic
adverbial clause, and relative *whom*/*whose*, which the PREL family doesn't
list). These are marked ⟨fallback⟩ below.

Because the mapping lives in the data, you can point the tool at an edited or
alternative profile with `--grammar-profile <dir>` (the directory must contain a
`cefrj-grammar-profile.csv` with the same columns).

## Constructions detected and their levels

~70 constructions across every major CEFR-J family. Level column shows the CEFR
band; the code is the CEFR-J shorthand it is read from (⟨fallback⟩ marks the few
that use a fallback level because the source code is unlevelled).

### Tense & aspect

| Construction | Level | CEFR-J code |
|---|---|---|
| Present simple / Present simple (be) | A1 | `TA.PRESENT.do.AFF` / `TA.PRESENT.be.AFF` |
| Past simple / Past simple (be) | A1 | `TA.PAST.do.AFF` / `TA.PAST.be.AFF` |
| Present progressive | A1 | `TA.PRPRG.AFF` |
| Past progressive | A2 | `TA.PASTPRG.AFF` |
| Present perfect | A2 | `TA.PRPF.AFF` |
| Future (will) | A2 | `TA.FUT.AFF` |
| Past perfect | B1 | `TA.PASTPF.AFF` |
| Present perfect progressive | B2 | `TA.PRPFPRG.AFF` |
| Past perfect progressive | B2 | `TA.PASTPFPRG.AFF` |

### Modality

| Construction | Level | CEFR-J code |
|---|---|---|
| Modal: can | A1 | `MD.can.AFF` |
| Modal: shall / should / would | A2 | `MD.shall.AFF` / `MD.should.AFF` / `MD.would.AFF` |
| Future (be going to) | A2 | `MD.be_going_to.AFF` |
| have to (obligation) | A2 | `MD.have_to.AFF` |
| Modal: could / may / might / must | B1 | `MD.could.AFF` / `MD.may.AFF` / `MD.might.AFF` / `MD.must.AFF` |
| be able to / ought to / used to | B1 | `MD.be_able_to.AFF` / `MD.ought_to.AFF` / `MD.used_to.AFF` |
| Modal + perfect / Modal + progressive | B2 | `MD.MD_PF.AFF` / `MD.MD_PRG.AFF` |
| had better ⟨fallback B2⟩ | B2 | `MD.had_better.AFF` |

### Voice

| Construction | Level | CEFR-J code |
|---|---|---|
| Passive (present) | A1 | `PASS.PRESENT` |
| Passive (past) | A2 | `PASS.PAST.AFF` |
| Passive (with modal) | B1 | `PASS.MD.AFF` |
| get-passive | B1 | `PASS.get_VN` |
| Passive (perfect) | B2 | `PASS.PRSPF.AFF` |
| Passive (progressive) | B2 | `PASS.PRSPRG.AFF` |

### Non-finite

| Construction | Level | CEFR-J code |
|---|---|---|
| -ing form (gerund/participle) | A1 | `VG` |
| to-infinitive (to do) | A1 | `TO.to_do` |
| negative to-infinitive (not to do) | B1 | `TO.not_to_do` |
| being / having + past participle | B2 | `VG.being_VN` / `VG.having_VN` |
| passive to-infinitive (to be done) | B2 | `TO.to_be_done` |
| perfect to-infinitive (to have done) | C1 | `TO.to_have_done` |

### Comparison

| Construction | Level | CEFR-J code |
|---|---|---|
| Comparative (-er) / Superlative (-est) | A1 | `COMP.JJR.RBR.er` / `COMP.JJS.RBS.est` |
| Comparative (more) / Superlative (most) | A2 | `COMP.JJR.RBR.more` / `COMP.JJS.RBS.most` |
| Comparison of equality (as … as) | B2 | `COMP.EQ.as_as` |

### Relative clauses

| Construction | Level | CEFR-J code |
|---|---|---|
| Relative clause: who / that | A1 | `PREL.who` / `PREL.that` |
| Non-restrictive relative clause | B1 | `PREL.NR` |
| Relative clause: whose ⟨fallback B1⟩ | B1 | — (no PREL code) |
| Relative clause: whom ⟨fallback B2⟩ | B2 | — (no PREL code) |
| Relative clause: which | B2 | `PREL.which` |

### Subordination

| Construction | Level | CEFR-J code |
|---|---|---|
| Adverbial (subordinate) clause | A1–A2 | `CL.when` / `CL.as`; ⟨fallback A2⟩ for other subordinators |
| that-clause complement | A2 | `CL.that.OBJ` |
| Embedded wh- / question clause | B1 | `CL.WH.OBJ` |

### Questions

| Construction | Level | CEFR-J code |
|---|---|---|
| Wh- question | A1–B2 | `INT.what` (level varies by wh-word) |
| Yes/no question (inversion) | A1 | `TA.PRESENT.be.INT.AFF` |
| Tag question | B1 | `TAG.AFF` |

### Existential, imperative & mood

| Construction | Level | CEFR-J code |
|---|---|---|
| Existential there + be | A1 | `EX.there.AFF` |
| Imperative / let's … | A1 | `IMP.V.AFF` / `IMP.let's_V.AFF` |
| Negative imperative | B1 | `IMP.V.NEG` |

### Conditionals

| Construction | Level | CEFR-J code |
|---|---|---|
| First conditional | A2 | `CL.if` |
| Second conditional | B1 | `SUBJ.PAST.AFF` |
| Third conditional | B1 | `SUBJ.PASTPF.AFF` |
| wish + past (unreal) | B2 | `SUBJ.wish_PAST` |

### Causative, inversion, subjunctive

| Construction | Level | CEFR-J code |
|---|---|---|
| Causative (make/let/have + inf) | A2 | `CAUS.have.let.make` |
| ask/tell + object + to-infinitive | B1 | `CAUS.ask.tell_NP_to_do` |
| Causative (have/get + past participle) | B2 | `CAUS.have.get_NP_VN` |
| Negative-adverbial inversion | C1 | `INV.never.etc` |
| Mandative subjunctive | C1 | `SUBJ.PRS.AFF` |

## The shared taxonomy — one levelling, both tools

The construction registry above is also the **single source of truth for
grammar** between the CLI and the app. It is exported as a machine-readable
document — every construction with its `id`, display `name`, `category`,
`level` (resolved exactly as detection resolves it) and `cefrjCode` — via

```bash
python3 grammar_profile.py --taxonomy
```

The same document is checked in at `GrammarProfile/taxonomy.json` (kept
byte-equal by the test suites and CI), so a consumer — e.g. RubricMaker's
grammar linker — can bundle the taxonomy without running anything. Because the
levels come from the same `cefrj_levels.get(code, fallback)` lookup the
profilers use, a construction is levelled the same way whether it's detected in
a reading (the CLI) or an essay (the app): the taxonomy *is* the registry the
`grammarCriteria` payload is built from.

## Accuracy notes

- Detection is **rule-based over a spaCy parse** (`en_core_web_sm`), not an
  exhaustive grammar. It targets a curated, high-value subset of the CEFR-J
  profile — the constructions above — chosen because each is reliably detectable
  from part-of-speech and dependency information. Rare or highly ambiguous items
  in the full 500-row profile are intentionally not attempted.
- Accuracy is bounded by the parser: mis-tagging or mis-parsing (common in very
  informal text, fragments, or unusual phrasing) can cause a missed or spurious
  detection. Counts are best read as an **estimate of grammatical range**, not an
  exact census.
- The profiler reports *distinct constructions and how often each occurs*, banded
  by CEFR level. The `estimatedLevel` gives the busiest band (`typical`) and the
  highest band reached (`reaches`). It is **not** a readability score.
- Constructions can legitimately overlap (a third conditional also contains a
  past-perfect verb form); the tool reports each construction it recognises rather
  than collapsing them, so related structures may both appear.
- For a fuller picture, pair this with the **vocabulary** profiler
  (`vocab_profile.py`): grammar range + vocabulary level together describe a
  text's difficulty far better than either alone.
