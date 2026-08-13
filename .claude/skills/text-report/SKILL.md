---
name: text-report
description: Run the unified VocabKitchen difficulty report — ONE command that profiles both the vocabulary and the grammar of English text against CEFR levels and answers "is this text right for my class?" in a single summary: vocabulary band + grammatical range + a blended estimated level, plus (with --target-level) the coverage figure ("a B1 learner will already know ~92% of the recognised running words"), what exceeds the class level, and a one-line verdict ("on level" / "reaches B2 — pre-teach 6 words, 2 structures"). Optionally reports a Flesch–Kincaid readability line alongside the CEFR bands. Use when the user wants a combined CEFR difficulty report for a text — a whole article, essay, or reading — instead of running the vocab-profiler and grammar-profiler skills separately, or wants to know what to pre-teach for a class at a given level. Requires Python 3; the grammar half needs spaCy (the tool degrades gracefully without it).
---

# Text report (unified difficulty report)

A single command that runs **both** profilers over the same text and prints one
combined summary, instead of two separate invocations you'd have to merge by
hand:

- **Vocabulary** — the CEFR band of the words: `typical` (busiest band) and
  `90% coverage` (the band you need to know ~90% of the words).
- **Grammar** — the CEFR band of the constructions used: `typical` (busiest
  band) and `reaches` (highest band present).
- **Blended estimated level** — one number: the higher of the vocabulary
  90%-coverage band and the grammar typical band, i.e. the level at which both
  most words and most structures sit comfortably.
- **`--target-level B1`** — pass the class's level and the report flags what
  exceeds it: the words above B1, the constructions above B1, the **coverage
  figure** ("a B1 learner will already know ~92% of the recognised running
  words"), and a one-line **verdict** ("on level" / "reaches B2 — pre-teach 6
  words, 2 structures").
- **Readability** — a classic index (Flesch Reading Ease + Flesch–Kincaid
  grade) reported *alongside* — never instead of — the CEFR bands.
- **`--export csv|md|flashcards`** — with `--target-level`, write the
  above-target words and structures as a ready-made **pre-teaching list** for
  the class: a CSV spreadsheet (`type,item,level,count,category,example`), a
  Markdown handout (verdict + coverage figure + a table per category, every
  row with an example sentence straight from the text), or a flashcard deck
  CSV in **RubricMaker's** import shape (`word, definition, example, phonetic,
  partOfSpeech`). `--output PATH` overrides the default location
  (`<stem>-preteaching-<LEVEL>.<ext>` next to the input file).
- **Decks ship with real content** — `--export flashcards` enriches each card
  by default: the back becomes the **Free Dictionary API's** plain definition
  (`dictionaryapi.dev`, free, no key), the in-text context sentence moves to
  the `example` column, and `phonetic`/`partOfSpeech` are filled in (POS falls
  back to the bundled OLP-EN-CEFRJ index). Offline or on a miss, the back
  falls back to the in-text sentence, so the deck always imports. CEFR levels
  never come from the API — they come from the bundled word lists
  (`WordLists/CEFR/levels.json`, built by `build_wordlists.py`).
  `--no-enrich` skips the network; `--dictionary-url` points at a proxy/test
  server; lookups are cached between runs (default
  `~/.cache/vocabkitchen/dictionary.json`, `--dictionary-cache PATH` to
  override, `--no-dictionary-cache` to disable) so repeat exports make no
  repeat requests.
- **`--cloze`** — render the exported examples as **fill-the-gap sentences**:
  each target word (or construction span) becomes `{{...}}`, RubricMaker's
  native fill-the-gap syntax — paste a sentence into a fill-the-gap question
  there and the gap becomes an input blank (auto-graded case-insensitively);
  on paper the gap doubles as a worksheet blank with the item's row as answer
  key. Applies to `--export md|csv`.
- **`--suggest`** — the rewrite aid: for each above-target word that has a
  curated alternative in the bundled list (`WordLists/synonyms.csv`, validated
  by `build_wordlists.py --check`), suggest the simpler word — shown inline in
  the above-target list (`purchase → buy (A1)`), carried in JSON as
  `aboveTarget.words[i].suggestion`, and added as a **Simpler alternative**
  column in the `--export md|csv` handout. Requires `--target-level`.
- **`--gap-report`** — the grammar gap report: with `--target-level`, list the
  target-level constructions the text does **not** use yet — the "introduce
  these structures" checklist for graded-reader authors, grouped by category
  in the terminal, carried in JSON as `grammarGap.missing`, and added as a
  **Constructions to introduce** section in the `--export md` handout. Needs
  the grammar side (spaCy); incompatible with `--no-grammar`.
- **`--watch`** — the edit → re-check loop: keep re-profiling the `--file`
  input whenever it changes on disk (polls every second; `--watch 0.2` for
  faster) until Ctrl-C — tighten a graded reader while the report updates on
  each save.
- **`--curriculum`** — the curriculum checklist: check the text against a
  checklist file (sections `[vocabulary]`, one word per line, and
  `[grammar]`, construction names as shown by the grammar profiler or their
  ids) and report **pass/fail coverage** — each required word present or
  missing (with its CEFR band when recognised), each required construction
  used or not, `curriculum.pass` in JSON, and a **Curriculum checklist**
  section in the `--export md` handout. Grammar items are flagged unchecked
  when the grammar side is off.
- **`--cambridge`** — the Phase 4 exam mapping: map the report's own CEFR
  bands (vocabulary typical/reaches, grammar typical/reaches, estimated
  level) to the matching Cambridge English Qualification — A2 Key, B1
  Preliminary, B2 First, C1 Advanced, C2 Proficiency. Carried in JSON as
  `cambridge`, shown in pretty mode, and rendered as a **Cambridge English
  mapping** section in the `--export md` handout.
- **`--cando`** — the Phase 4 Can-Do framing: express the text's demands as
  CEFR global-scale Can-Do descriptors — what a learner at the reached /
  estimated band can do, the language rubrics and self-assessment forms
  already use. Carried in JSON as `cando`, shown in pretty mode, and
  rendered as a **Can-Do descriptors** section in the `--export md` handout.
  With `--target-level`, each dimension also reports **`aboveTarget`** — the
  descriptors the text demands **beyond** what the class is expected to do
  yet (every level strictly above the target up to the text's own band), as
  an **Above the {target} target** block in pretty mode and the handout.
  With `--export flashcards` it writes a companion **Can-Do reference deck**
  (`essay-preteaching-B1-cando-deck.csv`) next to the word deck — the
  demands as cards in the same RubricMaker import shape.
- **`--pre-enrich`** — prime the dictionary cache for a whole class in one
  polite, rate-limited pass: point it at a word list (one word per line) or
  an essay (`--file`/`--text`/stdin), it looks each distinct word up against
  the Free Dictionary API (skipping words already cached), stores the results,
  and exits without a report. `--delay SECONDS` spaces requests out (default
  0.25), `--limit N` caps new lookups. After it, `--export flashcards` runs
  answer from the cache — fast and with zero requests. Use this when a teacher
  has a full class vocabulary list; offer `--delay 0.3` for long lists.

The vocabulary half and readability are dependency-free Python 3. The grammar
half needs spaCy like the grammar-profiler skill; **when spaCy is missing the
report still runs** — the grammar section is skipped with a note and the
verdict is vocabulary-based. Like grammar_profile.py, a sibling `.venv` is
auto-detected, so the tool "just works" when spaCy lives in a virtual
environment.

## How to run

The script is [`text_report.py`](../../../text_report.py) at the repo root; it
finds its word lists and grammar data relative to its own location, so it can
be run from any directory.

```bash
python3 text_report.py --text "If I had known, I would have helped." --target-level B1
python3 text_report.py --file essay.docx --target-level A2 --format pretty
echo "The results were analysed by the team." | python3 text_report.py --target-level B1
python3 text_report.py --file essay.docx --target-level B1 --export md   # pre-teaching handout
python3 text_report.py --file essay.docx --target-level B1 --export md --cloze  # ...as fill-the-gap worksheet
python3 text_report.py --file essay.docx --target-level B1 --export flashcards  # ...as a RubricMaker deck
```

Flags:

| Flag                | Meaning                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `--target-level`    | the class's CEFR level (A1–C2); report flags what exceeds it            |
| `--format`          | `auto` (default), `json`, or `pretty` — see below                       |
| `--text`            | inline text to analyse                                                   |
| `--file`            | path to a `.txt`, `.md`, `.docx`, or `.pdf` file (PDF needs `pypdf`)    |
| `--wordlists`       | override the vocabulary word-list directory (defaults to the bundled lists) |
| `--grammar-profile` | override the CEFR-J data directory (defaults to the bundled profile)    |
| `--no-grammar`      | skip the grammar side even if spaCy is available                        |
| `--no-readability`  | omit the Flesch–Kincaid / Flesch Reading Ease line                      |
| `--export`          | `csv`, `md`, or `flashcards` — write the above-target items as a pre-teaching list (requires `--target-level`) |
| `--suggest`         | rewrite aid: suggest a simpler alternative for each above-target word that has a curated mapping (requires `--target-level`) |
| `--gap-report`      | grammar gap report: list the target-level constructions the text does not use yet (requires `--target-level`; needs spaCy) |
| `--cloze`           | render exported examples as `{{...}}` fill-the-gap sentences (RubricMaker syntax; `--export md\|csv` only) |
| `--no-enrich`       | `--export flashcards` only: skip the Free Dictionary API (card backs stay the in-text context sentence) |
| `--dictionary-url`  | `--export flashcards` only: override the dictionary API base URL (proxy / test server) |
| `--dictionary-cache`| JSON cache file for lookups (default `~/.cache/vocabkitchen/dictionary.json`) |
| `--no-dictionary-cache` | don't read or write the lookup cache (`--pre-enrich` and `--export flashcards` only) |
| `--pre-enrich`     | prime the dictionary cache from the input (word list or essay) in one rate-limited pass, then exit |
| `--delay`          | `--pre-enrich` only: seconds between requests (default 0.25; `0` for none) |
| `--limit`          | `--pre-enrich` only: cap the number of new lookups |
| `--output`          | where the `--export` file goes (default: `<stem>-preteaching-<LEVEL>.<ext>` next to the input, or `preteaching-<LEVEL>.<ext>` in the cwd; decks get a `-deck` suffix) |
| `--watch`           | re-profile the `--file` input whenever it changes on disk (edit → re-check loop; optional interval in seconds, default 1) |
| `--curriculum`      | check the text against a curriculum checklist file (`[vocabulary]` + `[grammar]` sections) and report pass/fail coverage; validated before profiling — header typos like `[grammer]` fail fast with a hint, empty sections and unrecognised grammar items (typos like `second conditinal`) warn with a suggestion |
| `--cambridge`       | map the report's own CEFR bands to the matching Cambridge English Qualification (A2 Key, B1 Preliminary, B2 First, C1 Advanced, C2 Proficiency) |
| `--cando`           | express the text's demands as CEFR global-scale Can-Do descriptors; with `--target-level`, also list the ones above the target's expectations |
| `--comments`        | add the full apply-as-comment rubric: one comment per construction (used / not used yet, from `grammarCriteria`; filtered to the class level under `--target-level` — used above-target constructions become "pre-teach or rewrite" notes carrying a curated rewrite suggestion, unused ones drop) plus one comment per above-target vocabulary word |
| `--schema`          | print the versioned analysis payload schema (`analysis.schema.json` — the RubricMaker report contract, currently 1.3) as JSON and exit |
| (stdin)             | if neither `--text` nor `--file` is given, text is read from stdin      |

**Choosing input mode:** `--text` for a snippet, `--file` for a document on
disk, stdin when piping. `--file` detects the format from the extension
(Markdown is stripped to prose; `.docx`/`.pdf` have their text extracted).

**Output format:** when the output is captured (the normal case here — stdout
is not a terminal), it emits **JSON automatically**. `--format pretty` gives a
colour-coded terminal summary; `--format json` forces JSON in any context.

## Output

JSON on stdout. Shape:

```json
{
  "totalWordCount": 123,
  "estimatedLevel": "B1",
  "vocabulary": {
    "typical": "A2", "coverage": "B1", "offListPercent": 5,
    "results": { "A1": { "...": {} }, "...": {}, "Off List": { "...": {} } }
  },
  "grammar": {
    "sentenceCount": 8, "tokenCount": 118, "constructionCount": 12,
    "estimatedLevel": { "typical": "A2", "reaches": "B2" },
    "results": { "A1": { "...": {} }, "...": {} }
  },
  "targetLevel": "B1",
  "aboveTarget": {
    "maxLevel": "B2",
    "words": [ { "word": "circumstances", "level": "B2", "occurrences": 1 } ],
    "wordCount": 6,
    "structures": [ { "name": "Modal + perfect (e.g. would have done)", "level": "B2", "count": 1, "category": "Modality" } ],
    "structureCount": 2
  },
  "coverage": {
    "targetLevel": "B1", "knownPercent": 92, "knownWords": 113,
    "recognisedWords": 123,
    "sentence": "A B1 learner will already know ~92% of the recognised running words."
  },
  "verdict": "reaches B2 — pre-teach 6 words, 2 structures",
  "readability": { "fleschReadingEase": 62.3, "fleschKincaidGrade": 7.2, "description": "plain English" }
}
```

- `vocabulary.results` matches vocab_profile.py's `results.cefr` shape exactly;
  `grammar` is grammar_profile.py's full payload — the unified report is a
  superset of both, so existing parsing of either tool's output still works.
- `estimatedLevel` is the blended number: the higher of the vocabulary
  90%-coverage band and the grammar typical band. `aboveTarget.words` /
  `.structures` are the distinct recognised words / constructions at a CEFR
  level strictly above `targetLevel`; `maxLevel` is the highest of those.
- The coverage figure counts **recognised** running words (Off-List tokens —
  names, typos, jargon — are excluded from both sides, and their share is in
  `vocabulary.offListPercent`).
- `grammarError` (when set) explains why `grammar` is null: spaCy/model not
  installed (with install guidance), input too long for the parser, or
  `--no-grammar`.

## Interpreting results for the user

- The answer to "is this text right for my class?" is the **verdict** plus the
  **coverage figure**: state them first, then the blended estimated level, and
  only then the above-target words/structures if the user wants detail.
- **On level**: nothing exceeds the target — the text fits the class as-is.
- **"reaches B2 — pre-teach 6 words, 2 structures"**: the text goes above the
  target; name the specific words and structures to pre-teach (the hardest
  ones first — they're ranked by occurrence/count).
- The **blended estimated level** is one number but always shows its
  components (`vocabulary.typical/coverage`, `grammar.typical/reaches`) so the
  reasoning is transparent. A text that is A2 on words but reaches B2 in
  grammar is harder than its word list suggests — say so.
- Readability (Flesch–Kincaid grade etc.) is a rough classic index, never a
  substitute for the CEFR bands; mention it only if the user asks for a "grade
  level".
- When the user wants something to give the class (or a colleague), run the
  report with **`--export md`** (handout), `--export csv` (spreadsheet), or
  `--export flashcards` (RubricMaker deck) and hand over the file — each row
  already has the item, its level, and an example sentence from the text.
  Mention the written path.
- **RubricMaker import**: add **`--cloze`** to the md/csv export and the
  examples become `{{...}}` gaps — the exact syntax RubricMaker's fill-the-gap
  questions parse, so sentences paste straight in as auto-graded input blanks.
  `--export flashcards` writes a deck CSV with the header RubricMaker's deck
  importer expects (`word, definition, example, phonetic, partOfSpeech`), so
  it imports one click into a Vocabulary deck. The deck is enriched by
  default — back = a plain definition from the Free Dictionary API, example =
  the in-context sentence, phonetic/partOfSpeech filled in — and falls back
  to the in-context back when offline (`--no-enrich` to skip the network).
- **Short-text caveat**: on very short inputs a single rare word can push the
  90%-coverage band (and thus the blend) to a high level; the above-target
  list shows exactly which word did it, so the verdict stays interpretable.
- Show raw JSON only if the user asks; otherwise summarise in prose.

## Notes

- If a run fails, verify Python with `python3 --version`; if the grammar
  section is skipped, install spaCy (or activate the repo's `.venv`):
  `pip install spacy && python3 -m spacy download en_core_web_sm`.
- The unified report reuses the two profilers verbatim — word-list provenance
  is in [`WORDLISTS.md`](../../../WORDLISTS.md) and the CEFR-J grammar data in
  [`GRAMMARPROFILE.md`](../../../GRAMMARPROFILE.md).
- Run the regression tests with `python3 test_text_report.py` (grammar checks
  skip automatically if spaCy isn't installed).
