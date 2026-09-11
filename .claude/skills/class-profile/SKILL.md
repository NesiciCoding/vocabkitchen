---
name: class-profile
description: 'Profile a whole folder of English texts against CEFR levels in ONE run — the "class set, not one text" tool. Answers "which of these texts suits my class?" instead of "is this one text right?": point --file at a directory (or glob), and it profiles every text''s vocabulary + grammar, ranks and filters the set by level (--max-level B1 = "which of these suits B1?"), prints a spreadsheet-ready summary (--format csv, one row per text: typical & reached vocab band, grammar range, % above target), shows each text''s fit across several class levels side by side (--targets A2,B1,B2), and exports the distinct vocabulary of each CEFR band to CSV (--export-vocab) or one pre-teaching handout/worksheet/RubricMaker flashcard deck per text (--export md|csv|flashcards). Mirrors RubricMaker''s Vocabulary Profile dashboard from the command line. Use when the user has a folder/collection of candidate readings and wants to compare, rank, filter, or pre-teach them — not for a single text (use the text-report skill for that). Requires Python 3; the grammar side needs spaCy (degrades gracefully without it).'
---

# Class profile (a class set, not one text)

Scales the single-text profilers to the **folder of candidate readings a
teacher actually has**. Where `text-report` answers *"is this text right for
my class?"*, this answers *"which of these texts is right for my class?"* —
one command over a directory (or glob), producing the same artefacts as
RubricMaker's Vocabulary Profile dashboard (a pooled CEFR distribution +
vocabulary lists exported by band), plus ranking and filtering the dashboard
doesn't have.

- **Batch input** — `--file` accepts a **directory**, a **glob**
  (`"articles/*.txt"`, `**` for recursion), or a single file; every supported
  text (`.txt`/`.md`/`.docx`/`.pdf`) is profiled in one run. Unreadable or
  empty files are **skipped with a note**, never fatal.
- **Summary report** — one row per text: filename, typical & reached
  vocabulary band, grammar range (typical → reaches), blended estimated
  level, and — with `--target-level` — the **percentage of recognised running
  words above the class's level** (the same coverage figure `text-report`
  reports, flipped) and a fits/no-fits verdict. `--format csv` prints it
  ready for a spreadsheet.
- **Rank & filter** — `--sort` ranks the set by estimated level (default) or
  by vocabulary typical / reached band, word count, or filename; `--min-level`
  / `--max-level` keep only the texts whose estimated level is in the band —
  so *"which of these 20 articles suits B1?"* is exactly
  `--file essays/ --max-level B1`.
- **Several classes at once** — `--targets A2,B1,B2` shows each text's fits /
  %-above verdict for every level side by side in one run, so a mixed-ability
  set can be split across classes in a single table.
- **Aggregate distribution** — the pooled CEFR distribution over the whole
  set (typical band, 90%-coverage band, off-list share, a coloured bar in the
  terminal view) — the dashboard's headline chart, from the command line.
- **`--export-vocab DIR`** — dump the **distinct words in each CEFR band to
  CSV** (`vocab-A1.csv` … `vocab-C2.csv`, plus `vocab-off-list.csv`) over the
  selected set: each row is a word, its running occurrences across the set,
  and how many texts contain it — ready-made pre-teaching lists and glossaries.
- **`--export csv|md|flashcards`** — write a **per-text pre-teaching list**
  (same handouts, fill-the-gap worksheets and RubricMaker flashcard decks as
  `text-report`) for every text in the set, each next to its source file, so
  a whole folder is prepared in one run. Requires `--target-level`; `--cloze`
  blanks examples as `{{...}}`; `--no-enrich` skips the dictionary API;
  `--output DIR` collects all lists in one folder. With `--export flashcards`
  over more than one text, a **combined class-wide deck** is written too —
  all above-target words across the set in one RubricMaker deck, named after
  the source folder — together with a **markdown index**
  (`essays-preteaching-B1-index.md`) listing each word with its **CEFR
  level** (so the handout doubles as a level-keyed glossary), occurrences,
  and the texts it came from; with `--targets A2,B1` instead, one combined
  deck + index **per level** (`essays-preteaching-A2-deck.csv` …), no
  per-text lists. And for `--export csv|md` over more than one text, a
  **set-level summary handout** (`essays-summary-B1.md`) aggregates the
  pooled distribution plus each text's verdict and %-above in one page.
  (A re-run over the same folder skips these handouts — it never re-profiles
  its own exports.) `--suggest` adds a **Simpler alternative** column to the
  per-text handouts: a curated lower-band swap (`purchase → buy`) for each
  above-target word, from the same list the text report uses.
  `--gap-report` adds a **Grammar gaps** section to each per-text handout —
  the target-level constructions the text does not use yet (e.g. the second
  conditional), so a folder run shows every text's missing grammar.
- **Spaced introduction (`--interleave`)** — build a **vocabulary
  interleaving schedule** across the whole set: each reading introduces at
  most `--new-words-per-reading` new above-target words (overflow is deferred
  to the next reading with room), words that recur later are flagged for
  **spaced review**, and words absent for two or more readings are marked
  **due**. With `--export md|csv` it writes a `<set>-interleave-<LEVEL>.md|csv`
  schedule next to the handouts — the plan for introducing the folder's
  vocabulary at a controlled rate across repeated readings. With `--export
  md` it also writes **one printable handout per reading**
  (`essays-interleave-B1-reading-2.md`) listing that reading's Introduce /
  Review / Due words with the sentence each appears in, for printing.
- **`--curriculum`** — check every text against a curriculum checklist file
  (`[vocabulary]` + `[grammar]` sections, same format as the text report):
  with `--export md`, a pass/fail **Curriculum checklist** section per
  per-text handout; with `--export csv`, a **folder-level coverage grid**
  (`essays-curriculum-coverage-B1.csv`) — one row per text, one column per
  required item, with a pass verdict — so which texts cover the unit's
  requirements is visible at a glance. The same grid rides in the JSON
  report as `curriculumCoverage` (items × rows × cells), for scripts.
- **Can-Do framing (`--cando`)** — with `--export md|csv`, each per-text
  handout gains the text's **CEFR Can-Do descriptors** (what a learner at
  the text's demand level can do) plus an **Above the target** list — the
  descriptors the text demands beyond what the class is expected to do yet,
  the Phase 4 Can-Do framing per text. With `--export flashcards` the run
  also writes a **combined Can-Do reference deck**
  (`essays-preteaching-B1-cando-deck.csv`) next to the word decks: one card
  per above-target demand in the same RubricMaker import shape, so a deck
  doubles as Can-Do reference cards. Under `--targets A2,B1` each level
  gets its own deck (`essays-preteaching-A2-cando-deck.csv`,
  `essays-preteaching-B1-cando-deck.csv`), the demands measured against
  that level.
- **Set-level Can-Do diff (`--cando-diff`)** — with `--export md|csv`, the
  summary handout gains a **Can-Do demands across the set** section: which
  above-target descriptors the texts share, most-common first, with the
  demanding texts listed — the class-level challenge in one table (implies
  `--cando`). `--cando-diff-sort band` re-orders the section by the CEFR
  ladder ascending, to see which demand levels to tackle in order.
- **`--watch`** — the edit → re-check loop for a whole folder: keep
  re-profiling the `--file` input whenever any text in it changes on disk
  (polls every second; `--watch 0.2` for faster) until Ctrl-C.
- **`--pre-enrich`** — prime the dictionary cache from the **whole folder's
  distinct vocabulary** in one polite, rate-limited pass, then exit, so
  subsequent `--export flashcards` runs answer from the cache with zero
  requests. Combined with `--interleave`, it primes **exactly the words the
  schedule will introduce** — the reading handouts and decks then never hit
  the network, even mid-watch. `--delay SECONDS` spaces requests out
  (default 0.25), `--limit N` caps new lookups; `--dictionary-cache` /
  `--dictionary-url` point the lookups at a shared or test cache/server.

The vocabulary side is dependency-free Python 3 and reuses `vocab_profile`'s
tokenizer, word lists and percentage rounding verbatim. The grammar side
needs spaCy exactly like `grammar_profile` and degrades gracefully when it's
missing — the estimated level then falls back to the vocabulary 90%-coverage
band. Like the other tools, a sibling `.venv` is auto-detected; the one-command
`./install.sh` at the repo root creates it (spaCy + the English model + pypdf) —
offer to run it when the grammar column comes back blank.

## How to run

The script is [`class_profile.py`](../../../class_profile.py) at the repo
root; it finds its word lists and grammar data relative to its own location,
so it can be run from any directory.

```bash
python3 class_profile.py --file essays/                          # whole folder
python3 class_profile.py --file "articles/*.txt" --target-level B1
python3 class_profile.py --file essays/ --format csv             # spreadsheet summary
python3 class_profile.py --file essays/ --max-level B1           # "which of these suits B1?"
python3 class_profile.py --file essays/ --targets A2,B1,B2       # fit across classes
python3 class_profile.py --file essays/ --export-vocab vocab-lists/   # glossaries per band
python3 class_profile.py --file essays/ --target-level B1 --export md --output pret/  # handouts
python3 class_profile.py --file essays/ --target-level B1 --export md --gap-report --suggest  # + rewrite aid
python3 class_profile.py --file essays/ --target-level B1 --interleave   # spaced introduction schedule
python3 class_profile.py --file essays/ --pre-enrich             # warm the deck cache once
```

Flags:

| Flag                | Meaning                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `--file`            | a **directory**, a **glob** (recursive with `**`), or a single `.txt`/`.md`/`.docx`/`.pdf` file |
| `--format`          | `auto` (default), `json`, `pretty`, or `csv` — the spreadsheet summary  |
| `--target-level`    | the class's CEFR level (A1–C2): adds each text's %-above-target and fits verdict |
| `--targets`         | comma-separated levels (e.g. `A2,B1,B2`): fits/%above per level, side by side |
| `--min-level`       | keep only texts whose estimated level is at/above this band            |
| `--max-level`       | keep only texts whose estimated level is at/below this band            |
| `--sort`            | `level` (default), `typical`, `reached`, `words`, or `name`            |
| `--export-vocab`    | write one CSV per CEFR band (distinct words × occurrences × texts) into the given directory |
| `--export`          | `csv`, `md`, or `flashcards` — per-text pre-teaching lists (requires `--target-level`) |
| `--cloze`           | `--export md\|csv` only: render exported examples as `{{...}}` fill-the-gap sentences |
| `--suggest`         | `--export md\|csv` only: suggest a simpler alternative for each word above the target in the handouts |
| `--gap-report`      | `--export md\|csv` only: list the target-level constructions each text does not use yet, per handout |
| `--interleave`      | build a spaced-introduction schedule across the set (new words per reading, review + due flags) |
| `--new-words-per-reading` | `--interleave` only: max new words introduced per reading (default 5) |
| `--curriculum`      | check every text against a curriculum checklist file (md: per-text sections; csv: the folder-level coverage grid; json: `curriculumCoverage` in the payload); validated before profiling — header typos fail fast, empty sections and unrecognised grammar items warn with a hint |
| `--cando`           | add each text's CEFR Can-Do descriptors + the ones above the target's expectations to the handouts (md\|csv), or write a combined Can-Do reference deck (flashcards) |
| `--cando-diff`      | `--export md\|csv` only: add the set-level Can-Do demands section to the summary handout — which above-target descriptors the texts share (implies `--cando`) |
| `--cando-diff-sort` | `--cando-diff` only: order the demands by text count (`texts`, default) or by the CEFR band ladder ascending (`band`) |
| `--comments`        | add the full apply-as-comment rubric to each per-text handout: one comment per construction (used / not used yet, filtered to the class level — used above-target constructions become "pre-teach or rewrite" notes with a curated rewrite suggestion) plus one comment per above-target vocabulary word; `--export md` adds a **Demand scan** table to the set summary; `--export flashcards` writes a combined **rubric-comment deck** (one per `--targets` level) |
| `--schema`          | print the versioned analysis payload schema (`analysis.schema.json` — the RubricMaker report contract, currently 1.3) as JSON and exit |
| `--watch`           | re-profile the `--file` input whenever any text in it changes on disk (edit → re-check loop; optional interval in seconds, default 1) |
| `--no-enrich`       | `--export flashcards` only: skip the Free Dictionary API               |
| `--output`          | `--export` only: write all lists into this directory (default: next to each source) |
| `--pre-enrich`      | prime the dictionary cache in one rate-limited pass, then exit (the whole folder's vocabulary, or — with `--interleave` — exactly the schedule's words) |
| `--delay`           | `--pre-enrich` only: seconds between requests (default 0.25; `0` for none) |
| `--limit`           | `--pre-enrich` only: cap the number of new lookups                     |
| `--dictionary-cache`| JSON cache file for dictionary lookups (default `~/.cache/vocabkitchen/dictionary.json`) |
| `--no-dictionary-cache` | don't read or write the lookup cache (`--pre-enrich` and `--export flashcards` only) |
| `--dictionary-url`  | override the dictionary API base URL (proxy / test server)            |
| `--no-grammar`      | skip the grammar side even if spaCy is available                       |
| `--wordlists`       | override the vocabulary word-list directory                             |
| `--grammar-profile` | override the CEFR-J data directory                                     |
| (stdin)             | if neither `--file` nor `--text` is given, text is read from stdin     |

**Choosing input mode:** `--file` for a folder/glob/single document on disk
(the normal case), `--text` or stdin for a one-text set.

**Output format:** when the output is captured (the normal case here — stdout
is not a terminal), it emits **JSON automatically**. `--format csv` gives the
spreadsheet summary; `--format pretty` gives a colour-coded terminal view;
`--format json` forces JSON in any context.

## Output

JSON on stdout. Shape:

```json
{
  "source": "essays/",
  "texts": 20, "skipped": [],
  "targetLevel": "B1", "targets": null,
  "sort": "level", "minLevel": null, "maxLevel": "B1",
  "fitsCount": 7, "hiddenByFilter": 13,
  "grammarError": null,
  "aggregate": {
    "totalWordCount": 12345,
    "typical": "A2", "coverage": "B1", "offListPercent": 5,
    "levels": { "A1": { "percentage": "47%", "wordCount": 5800, "distinctWordCount": 900 }, "...": {} }
  },
  "rows": [
    {
      "file": "essays/article-01.txt",
      "totalWordCount": 320,
      "vocabulary": { "typical": "A2", "coverage": "B1", "offListPercent": 3 },
      "grammar": { "typical": "A2", "reaches": "B2" },
      "grammarError": null,
      "estimatedLevel": "B1",
      "aboveTargetPercent": 12,
      "fits": true,
      "targets": null
    }
  ],
  "interleave": null
}
```

- `grammarError` at the top level is the set-wide grammar note (e.g.
  "not analysed" when the grammar side didn't run); each row carries its own
  per-text `grammarError` too.
- With `--interleave`, the top-level `interleave` object carries the spaced
  schedule: `{"targetLevel": "B1", "budget": 5, "readings": [{"index": 1,
  "file": "...", "introduce": [{"word": "...", "level": "B2",
  "deferredFrom": 1}], "review": [...], "due": [...]}], "words":
  [{"word": "...", "level": "B2", "introducedAt": 1, "appearsIn": [1],
  "deferredFrom": 1}]}` — the per-reading Introduce/Review/Due lists plus the
  global word index, and `unscheduled` for words that never made it into an
  introduction.

- `rows` are sorted by `sort` (level by default, A1 first) and already
  filtered by `--min-level`/`--max-level`; `hiddenByFilter` is how many were
  filtered out, `fitsCount` how many (of all profiled texts) fit the target.
- With `--targets A2,B1,B2` instead of `--target-level`, each row carries a
  `targets` map (`{"A2": {"fits": bool, "aboveTargetPercent": int}, ...}`),
  `fitsCount` is a per-level map, and the singular `aboveTargetPercent`/`fits`
  fields are null.
- `aboveTargetPercent` is the share of **recognised** running words above the
  class's level (off-list tokens are excluded, same as text-report's coverage
  figure). `estimatedLevel` is the blend: the higher of the vocabulary
  90%-coverage band and the grammar typical band (vocab-only without grammar).
- `aggregate` is the pooled CEFR distribution over the selected set; `skipped`
  lists files that couldn't be read (each with its reason — e.g. a scanned
  PDF or a file that isn't a supported format).

## Interpreting results for the user

- The headline answer is the **fits/%-above column** (or `--targets`
  side-by-side columns): name the texts that fit the class level and the few
  that just miss it (with their %-above). Then the aggregate distribution, so
  the user sees the whole set's lexical shape.
- **"Which of these suits B1?"** → run with `--max-level B1` (optionally
  `--target-level B1` too) — the output is exactly the fitting texts.
- **Ranking a set by difficulty** → `--sort level` (default) is estimated
  level, easiest first. `--sort words` gives the longest texts first.
- **Mixed-ability class** → `--targets A2,B1,B2` produces one table with a
  column per level, so texts can be assigned to groups in one glance.
- **Pre-teaching the set** → `--export-vocab` for band glossaries (the
  distinct A2/B1 words across all texts), or `--export md` for one handout
  per text, `--export flashcards` for RubricMaker decks (`--no-enrich` when
  offline). Mention the written paths.
- **The %-above is the teacher number**: ~0–10% means the text sits almost
  exactly on the class's level; much higher means it will need real
  pre-teaching or is too hard. Off-list tokens (names, typos, jargon) never
  drag it down.
- Show raw JSON only if the user asks; otherwise summarise in prose — the
  ranked list of fits and the aggregate band are the two things to state.

## Notes

- If a run fails, verify Python with `python3 --version`; if the grammar
  column is blank, run the one-command installer `./install.sh` (creates the
  repo's `.venv` with spaCy + the English model + pypdf), or set it up by hand
  with `python3 -m pip install spacy pypdf && python3 -m spacy download en_core_web_sm`.
- The class profile reuses the three sibling tools verbatim — word-list
  provenance is in [`WORDLISTS.md`](../../../WORDLISTS.md), the CEFR-J
  grammar data in [`GRAMMARPROFILE.md`](../../../GRAMMARPROFILE.md).
- Run the regression tests with `python3 test_class_profile.py` (grammar
  checks skip automatically if spaCy isn't installed).
