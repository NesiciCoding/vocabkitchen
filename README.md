# Vocabkitchen — Vocabulary & Grammar Profilers

Determine the CEFR level of any English text from the command line — its
**vocabulary**, its **grammar**, and — with one command — both at once.

This fork turns the profiling feature of [Vocabkitchen](#about-the-original-project)
into small standalone tools:

- **[Vocabulary profiler](#vocabulary-profiler)** (`vocab_profile.py`) — reports the
  vocabulary level of every word against three word lists. Dependency-free Python 3.
- **[Grammar profiler](#grammar-profiler)** (`grammar_profile.py`) — reports which
  grammatical constructions a text uses (tenses, the passive, modals, relative
  clauses, conditionals, …) and what CEFR level each maps to. Rule-based over a
  spaCy parse, using the CEFR-J Grammar Profile.
- **[Text report](#text-report)** (`text_report.py`) — runs **both** profilers and
  answers *"is this text right for my class?"* in one command: vocabulary band +
  grammatical range + a blended estimated level, and with `--target-level B1` the
  coverage figure, what exceeds the level, and a one-line verdict.
- **[Class profile](#class-profile)** (`class_profile.py`) — scales that from one
  text to the folder of candidate readings a teacher actually has: profile a whole
  directory (or glob) in one run, get a spreadsheet-ready summary (one row per
  text), rank and filter the set by level — *"which of these 20 articles suits
  B1?"* — and export the distinct vocabulary of each CEFR band to CSV.

The vocabulary profiler scores against three word lists:

- **CEFR** — buckets words into A1, A2, B1, B2, C1, C2 (the standard language-proficiency scale)
- **AWL** — Coxhead's Academic Word List (is the word academic vocabulary or not)
- **NAWL** — the New Academic Word List

## What this fork adds

- **`vocab_profile.py`** — a single, dependency-free **Python 3** tool that
  reproduces the original app's profiler logic (the same tokenizer, matching,
  ordering and percentage-rounding as its `CefrProfiler` / `AwlProfiler` /
  `NawlProfiler`) with **no database, AWS, Angular, auth — or .NET**. It reuses
  the exact same word lists and is validated to produce identical output to the
  original C# profiler.
- **`analysis.py`** — the **shared analysis engine** (Phase 5): the word lists
  plus the grammar engine loaded once, and the one payload builder both CLIs
  call — `text_report.py` and `class_profile.py` import it, so a CEFR level
  means the same thing whether one text or a whole folder is profiled, and
  RubricMaker gets a single importable entry point.
- **`grammar_profile.py`** — a companion **grammar** profiler. Where the
  vocabulary tool scores *which words* a text uses, this reports *which
  grammatical constructions* it uses — present perfect, the passive, relative
  clauses, conditionals, modals, and ~70 more — and maps each to a CEFR level
  using the **CEFR-J Grammar Profile**. Detection is rule-based over a spaCy
  parse. See [Grammar profiler](#grammar-profiler).
- **`text_report.py`** — a **unified difficulty report** that runs both
  profilers and prints one combined summary: vocabulary band + grammatical
  range + a blended estimated level, plus (with `--target-level`) what exceeds
  the class's level, the coverage figure, and a one-line verdict. See
  [Text report](#text-report).
- **`class_profile.py`** — a **class-set profiler** that runs the same
  vocabulary + grammar analysis over a whole folder of candidate readings at
  once, mirroring RubricMaker's Vocabulary Profile dashboard: a pooled CEFR
  distribution for the set, a per-text summary ready for a spreadsheet, level
  ranking and band filtering, and vocabulary lists exported by CEFR band. See
  [Class profile](#class-profile).
- **Claude Code plugins & skills** — installable plugins
  ([`plugins/vocab-profiler/`](plugins/vocab-profiler),
  [`plugins/grammar-profiler/`](plugins/grammar-profiler),
  [`plugins/text-report/`](plugins/text-report),
  [`plugins/class-profile/`](plugins/class-profile)) plus repo-local skills
  (`.claude/skills/`) that wrap the scripts, so the profilers are available in a
  Claude Code / Cowork session — just ask for the CEFR level, vocabulary
  breakdown, grammatical range, or *"which of these articles suits B1?"* of a
  folder. See [Use in Claude Code](#use-in-claude-code).
- **Rebuilt word-list data** — the CEFR/AWL/NAWL lists in the repo had been
  truncated to only "a" words, which made scoring wrong for real text. They were
  rebuilt in full from documented public sources (each with its own licence) and
  validated against a curated dictionary so only real, correctly-spelled words
  remain. The CEFR lists are now additionally **gap-filled with the open
  OLP-EN-CEFRJ profiles** (CEFR-J A1–B2 + Octanove C1/C2) via
  [`build_wordlists.py`](build_wordlists.py), which also emits
  `WordLists/CEFR/levels.json` — a complete `word → {level, pos}` index, so
  CEFR levels never need a dictionary API. See [`WORDLISTS.md`](WORDLISTS.md)
  for exact sources, versions, and licences.

## Vocabulary profiler

### Quick start

The profiler needs only **Python 3** — no build, and no third-party dependencies
for text, Markdown, and `.docx` input (PDF input optionally uses `pypdf`; see
[Input formats](#input-formats)). Most Linux and macOS systems already have
Python (on macOS it may require the Xcode Command Line Tools); confirm with
`python3 --version` before running:

```bash
python3 vocab_profile.py --type cefr --text "The cat sat on the mat."
python3 vocab_profile.py --type all  --file essay.pdf
echo "She analysed the philosophical implications." | python3 vocab_profile.py --type awl
```

Options:

| Flag          | Meaning                                                                 |
|---------------|-------------------------------------------------------------------------|
| `--type`      | `cefr`, `awl`, `nawl`, `all` (default), or a comma-list like `cefr,awl` |
| `--format`    | `auto` (default), `json`, or `pretty` — see [Output](#output-formats)  |
| `--text`      | inline text to analyse                                                  |
| `--file`      | path to a `.txt`, `.md`, `.docx`, or `.pdf` file to analyse            |
| `--wordlists` | override the word-list directory (defaults to the bundled lists)        |
| (stdin)       | if neither `--text` nor `--file` is given, text is read from stdin      |

### Input formats

`--file` detects the format from the extension:

| Extension            | How it's read                                                     |
|----------------------|------------------------------------------------------------------|
| `.txt` / (other)     | read as UTF-8 text (the fallback for any unknown extension)       |
| `.md` / `.markdown`  | Markdown syntax (headings, emphasis, links, code) stripped to prose |
| `.docx`              | paragraph text extracted from the Word XML (stdlib only)          |
| `.pdf`               | text layer extracted with [`pypdf`](https://pypi.org/project/pypdf/) |

Everything except PDF is handled with the Python standard library alone. PDF is
the one optional dependency — install it only if you need it:

```bash
pip install pypdf
```

Image-only / scanned PDFs have no text layer and yield no words (there is no OCR).

### Output formats

Selected by `--format`:

- **`json`** — a `totalWordCount` plus, per profiler, each level's percentage,
  word count, and the distinct words in that level ranked by occurrences
  (`Off List` holds unrecognised words). Ideal for scripts, tools, and the Cowork skill.
- **`pretty`** — a colour-coded terminal view: a CEFR distribution summary
  (typical level + 90%-coverage level + a breakdown bar), per-level word lists,
  and the source text tinted by level (A1 blue → C2 pink).

`--format auto` (the default) picks `pretty` when stdout is an interactive
terminal and `json` when stdout is piped or redirected, so downstream tools keep
receiving JSON automatically. Pass `--format json`/`--format pretty` to force
either. See [`WORDLISTS.md`](WORDLISTS.md) for data provenance and accuracy notes.

### Planned / future ideas

Not yet implemented — noted so they aren't lost: an explicit `--no-color` flag
(colour already auto-disables when output isn't a terminal and honours the
`NO_COLOR` env var); paging/truncation for the highlighted-text block on very
long inputs; and a richer AWL/NAWL section with its own coverage bar.

Run the regression tests with:

```bash
python3 test_vocab_profile.py
```

### Example

```console
$ python3 vocab_profile.py --type cefr --text "Yesterday I walked to the shop to buy bread and milk."
```

Everyday text like this scores as almost entirely A1/A2, while academic text
spreads into the higher bands — e.g. *chlorophyll*, *photosynthesis*, and
*synthesize* resolve to C2.

`vocab_profile.py` is a faithful standalone port of the profiler slice of the
original C# application (see below); it carries no other part of that codebase.

## Grammar profiler

`grammar_profile.py` is the grammar counterpart to the vocabulary profiler. It
reports which **grammatical constructions** a text uses and maps each to a CEFR
level, so you can see how grammatically demanding it is and where its structural
range reaches. It detects ~70 constructions across every major family — tense &
aspect, modality, voice (the passive), non-finite forms, comparison, relative
clauses, subordination, conditionals, questions, imperatives, causatives, and
inversion — with levels taken from the **CEFR-J Grammar Profile**. Detection is
**rule-based**: deterministic rules run over a spaCy parse, with no LLM involved.

### Requirements

Unlike the vocabulary profiler, the grammar profiler **requires spaCy** and the
small English model, because reliable grammar detection needs part-of-speech and
dependency parsing.

**Recommended (works everywhere, including Arch and other "externally-managed"
systems):** install into a virtual environment at the repo root. The tool
auto-detects a `.venv` next to itself and re-launches under it, so you don't have
to activate anything — `python3 grammar_profile.py …` and the plugin both just
work:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install spacy
.venv/bin/python -m spacy download en_core_web_sm
```

On Arch specifically, `pip install spacy` into the **system** Python is blocked by
PEP 668 (`externally-managed-environment`) — the venv above is the fix; don't use
`--break-system-packages`. If you keep your environment elsewhere, point the tool
at it with `GRAMMAR_PROFILE_PYTHON=/path/to/python`.

On a system with a writable Python (not Arch) the plain form also works:

```bash
pip install spacy && python3 -m spacy download en_core_web_sm
```

If spaCy or the model is still missing, the tool prints these exact install
commands and exits — it never crashes with a traceback. (spaCy ships compiled
dependencies whose wheels can lag on brand-new Python releases; if the install
fails on the newest Python, use a 3.11–3.13 virtual environment.)

### Usage

```bash
python3 grammar_profile.py --text "If I had known, I would have helped."
python3 grammar_profile.py --file essay.docx
echo "The results were analysed by the team." | python3 grammar_profile.py
```

| Flag                | Meaning                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `--format`          | `auto` (default), `json`, or `pretty`                                   |
| `--text`            | inline text to analyse                                                   |
| `--file`            | path to a `.txt`, `.md`, `.docx`, or `.pdf` file (PDF needs `pypdf`)     |
| `--grammar-profile` | override the CEFR-J data directory (defaults to the bundled profile)     |
| (stdin)             | if neither `--text` nor `--file` is given, text is read from stdin       |

The same `--format auto` rule applies: a colour-coded terminal view when stdout is
a TTY, JSON when piped or redirected. The JSON has sentence/token counts, an
`estimatedLevel` (`typical` = busiest band, `reaches` = highest band present), and
every detected construction banded by CEFR level with counts and example spans.

### Output

- **`pretty`** — a CEFR summary (typical level, reaches, a distribution bar) then,
  per level, the constructions found with an example of each.
- **`json`** — the machine-readable analysis (ideal for the Claude Code skill),
  banded A1–C2. See [`GRAMMARPROFILE.md`](GRAMMARPROFILE.md) for the full
  construction-to-level table, data provenance, licensing/citation for the CEFR-J
  Grammar Profile, and accuracy caveats.

Run the regression tests with:

```bash
python3 test_grammar_profile.py
```

(The detector checks skip automatically when spaCy isn't installed, so the suite
still passes.)

### Pair the two tools

The profilers are complementary: **vocabulary level + grammatical range** together
describe a text's difficulty far better than either alone. Profile the same text
with both — e.g. an article that is A2 on vocabulary but reaches B2 grammar (heavy
use of the passive and relative clauses) is harder than its word list suggests.

[`text_report.py`](#text-report) does exactly this pairing for you: one command,
one combined summary, one verdict.

## Text report

`text_report.py` is the **unified difficulty report**: one command that runs both
profilers over the same text and prints one combined summary, instead of two
invocations you'd have to merge by hand. It answers *"is this text right for my
class?"*

```bash
python3 text_report.py --file essay.docx --target-level B1
python3 text_report.py --text "If I had known, I would have helped." --target-level B1 --format pretty
echo "The results were analysed by the team." | python3 text_report.py
python3 text_report.py --file essay.docx --target-level B1 --export md              # pre-teaching handout
python3 text_report.py --file essay.docx --target-level B1 --export md --cloze      # ...as a fill-the-gap worksheet
python3 text_report.py --file essay.docx --target-level B1 --export flashcards      # ...as a RubricMaker flashcard deck
```

It reports:

- **Vocabulary band** — typical level + 90%-coverage level (from `vocab_profile.py`).
- **Grammatical range** — typical level + highest band reached (from `grammar_profile.py`).
- **Blended estimated level** — one number: the higher of the vocabulary
  90%-coverage band and the grammar typical band, i.e. the level at which most
  words *and* most structures sit comfortably.
- **`--target-level B1`** — flag what exceeds the class's level: the words above
  B1, the constructions above B1, the **coverage figure** (*"a B1 learner will
  already know ~92% of the recognised running words"*), and a one-line
  **verdict** (*"on level"* / *"reaches B2 — pre-teach 6 words, 2 structures"*).
- **Readability line** — Flesch–Kincaid grade + Flesch Reading Ease, reported
  *alongside* — never instead of — the CEFR bands (omit with `--no-readability`).
- **`--export csv|md|flashcards`** — write the above-target words and
  structures as a ready-made **pre-teaching list** for the class: a CSV
  spreadsheet (`type,item,level,count,category,example`), a Markdown handout
  (verdict + coverage figure + one table per category, every row with an
  example sentence straight from the text), or a flashcard deck CSV in
  **RubricMaker's** import shape (`word, definition, example, phonetic,
  partOfSpeech` — its deck importer skips that header and reads front/back
  automatically). Requires `--target-level`; `--output PATH` overrides the
  default location.
- **Decks ship with real content** — `--export flashcards` enriches each card
  by default: the back becomes the **Free Dictionary API's** plain definition
  (`dictionaryapi.dev`, free, no key), the in-text context sentence moves to
  the `example` column, and `phonetic` / `partOfSpeech` are filled in (POS
  falls back to the bundled word-list index). Offline or on a miss, the back
  gracefully falls back to the in-text sentence, so a deck always imports.
  CEFR levels never come from the API — they come from the bundled
  OLP-EN-CEFRJ word lists. `--no-enrich` skips the network entirely;
  `--dictionary-url` points at a proxy/test server.
- **Lookups are cached between runs** — successful lookups *and* definitive
  misses are stored in a small JSON cache (default
  `~/.cache/vocabkitchen/dictionary.json`, keyed by API URL and word), so
  repeat exports make **no repeat requests** — fast, and polite to the hobby
  API. `--dictionary-cache PATH` overrides the file, `--no-dictionary-cache`
  disables it.
- **Pre-enrich a whole class in one pass** — `--pre-enrich` primes that cache
  from a word list (one word per line) or an essay in a single polite,
  rate-limited pass, then exits (no report, no export):

  ```bash
  python3 text_report.py --pre-enrich --file class_vocab.txt
  python3 text_report.py --pre-enrich --text "the whole essay…" --delay 0.5
  ```

  Words already cached (hits and misses) are skipped; `--delay SECONDS`
  spaces requests out (default 0.25, `0` for none); `--limit N` caps new
  lookups. Subsequent `--export flashcards` runs then answer from the cache.
- **`--cloze`** — render the exported examples as **fill-the-gap sentences**:
  each target word (or construction span) becomes `{{...}}` — RubricMaker's
  native fill-the-gap syntax. Paste a sentence into a RubricMaker fill-the-gap
  question and the gap becomes an input blank (auto-graded
  case-insensitively); on paper, the gap doubles as a worksheet blank with the
  item's row as the answer key. Applies to `--export md|csv`.
- **Rewrite aid** — `--suggest` adds a **simpler alternative** for each
  above-target word that has one in the bundled curated list
  ([`WordLists/synonyms.csv`](WordLists/synonyms.csv), validated by
  `build_wordlists.py --check` against `levels.json`): the above-target list
  shows it inline (`purchase → buy (A1)`), JSON carries it as
  `aboveTarget.words[i].suggestion`, and the `--export md` handout gains a
  **Simpler alternative** column — the Phase 3 "what do I change?" answer
  next to the "what's above level?" list. Requires `--target-level`.
- **Grammar gap report** — `--gap-report` lists the **target-level
  constructions the text does not use yet** (the mirror of the
  above-target list): the "introduce these structures" checklist for
  graded-reader authors, grouped by category in the terminal, carried in
  JSON as `grammarGap.missing`, and added as a **Constructions to introduce**
  section in the `--export md` handout. Requires `--target-level` and the
  grammar side (spaCy).
- **Watch mode** — `--watch` keeps re-profiling a `--file` input whenever
  it changes on disk (polling every second, `--watch 0.2` for faster), for a
  tight **edit → re-check loop**: save the graded reader and the report
  updates on the spot, until Ctrl-C.
- **Curriculum checklist** — `--curriculum FILE` checks the text against a
  checklist file (sections `[vocabulary]`, one word per line, and
  `[grammar]`, construction names as shown by the grammar profiler or their
  ids) and reports **pass/fail coverage**: each required word's presence
  plus its CEFR band when recognised, each required construction used or
  not, and a `pass` verdict when everything is covered. Carried in JSON as
  `curriculum`, shown in the terminal, and rendered as a **Curriculum
  checklist** section in the `--export md` handout. Grammar items are
  flagged unchecked when the grammar side is off.
- **Cambridge English mapping** — `--cambridge` maps the report's own CEFR
  bands to the matching **Cambridge English Qualification**: A2 Key, B1
  Preliminary, B2 First, C1 Advanced, C2 Proficiency (A1 is below the exam
  ladder). Carried in JSON as `cambridge`, shown in the terminal, and
  rendered as a **Cambridge English mapping** section in the `--export md`
  handout — the answer to "what exam is a student at this level working
  toward?".
- **CEFR Can-Do framing** — `--cando` expresses the text's **demands as
  Can-Do descriptors** (the CEFR global scale): what a learner at the
  reached / estimated band can actually do, in the language rubrics and
  self-assessment forms already use. Carried in JSON as `cando`, shown in
  the terminal, and rendered as a **Can-Do descriptors** section in the
  `--export md` handout. With `--target-level`, each dimension also reports
  `aboveTarget` — the descriptors the text demands **beyond** what the
  class is expected to do yet (every level strictly above the target up to
  the text's own band), shown as an **Above the {target} target** block in
  the terminal and the handout. With `--export flashcards` it writes a
  companion **Can-Do reference deck** (`essay-preteaching-B1-cando-deck.csv`)
  next to the word deck — the demands as cards in the same RubricMaker
  import shape.

Flags:

| Flag                | Meaning                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `--target-level`    | the class's CEFR level (A1–C2); the report flags what exceeds it        |
| `--format`          | `auto` (default), `json`, or `pretty` — see [Output formats](#output-formats) |
| `--text`            | inline text to analyse                                                   |
| `--file`            | path to a `.txt`, `.md`, `.docx`, or `.pdf` file (PDF needs `pypdf`)     |
| `--wordlists`       | override the vocabulary word-list directory                              |
| `--grammar-profile` | override the CEFR-J data directory                                      |
| `--no-grammar`      | skip the grammar side even if spaCy is available                        |
| `--no-readability`  | omit the readability line                                               |
| `--export`          | `csv`, `md`, or `flashcards` — write the above-target items as a pre-teaching list (requires `--target-level`) |
| `--suggest`         | rewrite aid: suggest a simpler alternative for each word above the target (requires `--target-level`) |
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
| (stdin)             | if neither `--text` nor `--file` is given, text is read from stdin      |

The vocabulary half is dependency-free Python 3. The grammar half needs spaCy
exactly like the grammar profiler — and when spaCy is missing the report **still
runs**, skipping the grammar section with a note (the verdict then covers
vocabulary only). Like `grammar_profile.py`, a sibling `.venv` is auto-detected.

The JSON output is a superset of both profilers' payloads: `vocabulary.results`
matches the vocab profiler's `results.cefr` shape and `grammar` is the grammar
profiler's full payload, plus the unified fields (`estimatedLevel`, `targetLevel`,
`aboveTarget`, `coverage`, `verdict`, `readability`). Each `aboveTarget` entry
carries an example sentence from the text (`context` on words, `examples` on
structures), which the exports use to show every item in context.Run the regression tests with:

```bash
python3 test_text_report.py
```

## Class profile

`class_profile.py` scales the profilers from one text to the **folder of
candidate readings a teacher actually has** — it mirrors RubricMaker's
Vocabulary Profile dashboard, which aggregates a class's texts into a CEFR
distribution and exports vocabulary lists by CEFR band to CSV, and turns the
shell loops of use cases 5 and 10 into first-class features.

```bash
python3 class_profile.py --file essays/                          # profile a whole folder
python3 class_profile.py --file "articles/*.txt" --target-level B1
python3 class_profile.py --file essays/ --format csv             # spreadsheet summary
python3 class_profile.py --file essays/ --max-level B1           # "which of these suits B1?"
python3 class_profile.py --file essays/ --targets A2,B1,B2       # fit across classes
python3 class_profile.py --file essays/ --export-vocab vocab-lists/   # glossaries per band
python3 class_profile.py --file essays/ --target-level B1 --export md --output pret/  # handouts
python3 class_profile.py --file essays/ --target-level B1 --export md --gap-report --suggest  # + rewrite aid
python3 class_profile.py --file essays/ --target-level B1 --interleave   # spaced introduction schedule
python3 class_profile.py --file essays/ --pre-enrich             # warm the deck cache once
python3 class_profile.py --file sample-readings/                 # try it on the bundled demo folder
```

It reports:

- **Batch input** — `--file` accepts a **directory**, a **glob**
  (`"articles/*.txt"`, `**` for recursion), or a single file; every supported
  text (`.txt`/`.md`/`.docx`/`.pdf`) is profiled in one run. Unreadable or
  empty files are **skipped with a note**, never fatal.
- **Summary report** — one row per text: filename, typical & reached
  vocabulary band, grammar range (typical → reaches), blended estimated level,
  and — with `--target-level` — the **percentage of recognised running words
  above the class's level** (the same coverage figure `text_report.py`
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
  CSV** (`vocab-A1.csv` … `vocab-C2.csv`, plus `vocab-off-list.csv` for the
  unrecognised words) over the selected set: each row is a word, its running
  occurrences across the set, and how many texts contain it — ready-made
  pre-teaching lists and glossaries.
- **`--export csv|md|flashcards`** — write a **per-text pre-teaching list**
  (the same handouts, fill-the-gap worksheets and RubricMaker flashcard decks
  as `text_report.py`) for every text in the set, each next to its source
  file, so a whole folder is prepared in one run. Requires `--target-level`;
  `--cloze` blanks examples as `{{...}}` (RubricMaker syntax); `--no-enrich`
  skips the dictionary API; `--output DIR` collects all lists in one folder.
  With `--export flashcards` over more than one text, a **combined class-wide
  deck** is written too — all above-target words across the set in one
  RubricMaker deck, named after the source folder — together with a
  **markdown index** (`essays-preteaching-B1-index.md`) listing each word
  with its **CEFR level** (so the handout doubles as a level-keyed glossary),
  occurrences, and the texts it came from; with `--targets A2,B1`
  instead, one combined deck + index **per level**
  (`essays-preteaching-A2-deck.csv` …), no per-text lists. And for
  `--export csv|md` over more than one text, a **set-level summary handout**
  (`essays-summary-B1.md`) aggregates the pooled distribution plus each
  text's verdict and %-above in one page, next to the per-text lists.
  (A re-run over the same folder skips these handouts — it never re-profiles
  its own exports.) `--suggest` adds a **Simpler alternative** column to the
  per-text handouts: a curated lower-band swap (`purchase → buy`) for each
  above-target word, from the same list the text report uses.
  `--gap-report` adds a **Grammar gaps** section to each per-text handout —
  the target-level constructions the text does not use yet (e.g. the second
  conditional), the same list `text_report.py` reports, so a folder run shows
  every text's missing grammar at a glance.
- **Spaced introduction (`--interleave`)** — build a **vocabulary
  interleaving schedule** across the whole set: each reading introduces at
  most `--new-words-per-reading` new above-target words (overflow is deferred
  to the next reading with room), words that recur later are flagged for
  **spaced review**, and words absent for two or more readings are marked
  **due**. With `--export md|csv` it writes a `<set>-interleave-<LEVEL>.md|csv`
  schedule next to the handouts — the teacher's plan for introducing a
  folder's vocabulary at a controlled rate across repeated readings. With
  `--export md` it also writes **one printable handout per reading**
  (`essays-interleave-B1-reading-2.md`) listing that reading's Introduce /
  Review / Due words — defined from the dictionary cache when a
  `--pre-enrich` pass has primed it, else the sentence the word appears in
  — for printing and handing out.
- **Curriculum checklist** — `--curriculum FILE` checks every text against
  the checklist file (`[vocabulary]` + `[grammar]` sections, same format as
  the text report). With `--export md` it adds a **Curriculum checklist**
  section to each per-text handout (words and constructions marked present /
  missing) and the same **coverage matrix** to the set-level summary
  handout; with `--export csv` it writes the matrix as a spreadsheet
  (`essays-curriculum-coverage-B1.csv`) — one row per text, one column per
  required item, with a pass verdict — so which texts cover the unit's
  requirements is visible at a glance. The same grid rides in the JSON
  report as `curriculumCoverage` (items × rows × cells), so scripts can
  consume the pass/fail matrix without CSV parsing.
- **Can-Do framing** — `--cando` adds each per-text handout's **CEFR
  Can-Do descriptors** (what a learner at the text's demand level can do)
  plus an **Above the target** list — the descriptors the text demands
  beyond what the class is expected to do yet, ready to pre-teach or
  rewrite. With `--export flashcards` it also writes a **combined Can-Do
  reference deck** (`essays-preteaching-B1-cando-deck.csv`) next to the
  word decks: one card per above-target demand in the RubricMaker import
  shape, so a deck doubles as Can-Do reference cards — under `--targets
  A2,B1` each level gets its own deck
  (`essays-preteaching-A2-cando-deck.csv` …), the demands measured against
  that level. With `--cando-diff`
  the summary handout gains a **Can-Do demands across the set** section:
  which above-target descriptors the texts share, most-common first, with
  the demanding texts listed — `--cando-diff-sort band` re-orders it by the
  CEFR ladder ascending, to see which demand levels to tackle in order.
- **Folder watch mode** — `--watch` keeps re-profiling the `--file` input
  whenever any text in it changes on disk (polling every second,
  `--watch 0.2` for faster), until Ctrl-C — the edit → re-check loop for a
  whole folder, not just one text. Every cycle rebuilds all the exports,
  so the flashcard decks and band glossaries stay **warm** while you edit.
- **`--pre-enrich`** — prime the dictionary cache from the **whole folder's
  distinct vocabulary** in one polite, rate-limited pass, then exit:
  subsequent `--export flashcards` runs answer from the cache with zero
  requests. Combined with `--interleave`, it primes **exactly the words the
  schedule will introduce** — the reading handouts and decks then never hit
  the network, even mid-watch. `--delay SECONDS` spaces requests out
  (default 0.25), `--limit N` caps new lookups; `--dictionary-cache` /
  `--dictionary-url` point the lookups at a shared or test cache/server.

Flags:

| Flag                | Meaning                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `--file`            | a **directory**, a **glob** (recursive with `**`), or a single `.txt`/`.md`/`.docx`/`.pdf` file |
| `--format`          | `auto` (default), `json`, `pretty`, or `csv` — the spreadsheet summary  |
| `--target-level`    | the class's CEFR level (A1–C2): adds each text's %-above-target and fits verdict |
| `--targets`         | comma-separated levels (e.g. `A2,B1,B2`): fits/%above per level, side by side (instead of `--target-level`) |
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

`--format auto` follows the sibling tools: a colour-coded terminal view when
stdout is a TTY, JSON when piped. The vocabulary side is dependency-free
Python 3; the grammar side needs spaCy exactly like `grammar_profile.py` and
degrades gracefully when it's missing (the estimated level then falls back to
the vocabulary 90%-coverage band). Like the other tools, a sibling `.venv`
is auto-detected — except under `--no-grammar`, where re-exec is skipped so
an interpreter's extras (e.g. pypdf for PDFs) are kept. The repo bundles a
small demo folder, [`sample-readings/`](sample-readings), with a level
gradient from A1 to C2: `python3 class_profile.py --file sample-readings/`.
Run the regression tests with:

```bash
python3 test_class_profile.py
```

CI runs the same suite and additionally a **golden check** of the batch CLI
against [`sample-readings/`](sample-readings): it asserts the CSV/JSON contract
(one row per text, ranked by level, aggregate = sum of the rows), the
grammar-enabled pass, and every export shape — per-level combined decks and
level-keyed indexes, the set summary handout, and the per-band vocabulary CSVs.
A plugin-skill check also keeps each plugin's two `SKILL.md` copies
flavour-consistent and its `plugin.json` `commands` matching the skill's stated
command.

## Use in Claude CodeBeyond the command line, the profilers ship as **Claude Code plugins**, so
you can ask Claude for a text's CEFR level, vocabulary breakdown, grammatical range —
or a unified *"is this text right for my class?"* report, or *"which of these
articles suits B1?"* over a whole folder — right in a session instead of
invoking the scripts yourself.

### Install from the marketplace

```bash
/plugin marketplace add NesiciCoding/vocabkitchen-CLI
/plugin install vocab-profiler@vocabkitchen
/plugin install grammar-profiler@vocabkitchen
/plugin install text-report@vocabkitchen
/plugin install class-profile@vocabkitchen
```

Then just ask — e.g. *"What CEFR level is this paragraph?"*, *"What grammar does
this text use?"*, *"Is this text right for my B1 class?"*, or *"which of the
articles in this folder suit B1?"* — or invoke a skill explicitly with
`/vocab-profiler:vocab-profiler` /
`/grammar-profiler:grammar-profiler` / `/text-report:text-report` /
`/class-profile:class-profile`. The plugins
need **Python 3** on your machine (they bundle the scripts and data, not a
runtime); the grammar plugin and the grammar half of text-report and
class-profile additionally need **spaCy** (`pip install spacy && python3 -m
spacy download en_core_web_sm`).

Updates are automatic. The plugins are intentionally unversioned, so every push to
this repo counts as a new release and Claude Code picks it up on its next
background marketplace refresh (force one with `/plugin marketplace update`).

### Try it before installing

To load a plugin straight from a clone, without adding the marketplace:

```bash
claude --plugin-dir ./plugins/vocab-profiler
claude --plugin-dir ./plugins/grammar-profiler
claude --plugin-dir ./plugins/text-report
claude --plugin-dir ./plugins/class-profile
```

The plugins live in [`plugins/vocab-profiler/`](plugins/vocab-profiler),
[`plugins/grammar-profiler/`](plugins/grammar-profiler),
[`plugins/text-report/`](plugins/text-report) and
[`plugins/class-profile/`](plugins/class-profile); each bundles its scripts and
data as symlinks to the canonical copies at the repo root, so there is a single
source of truth and the plain CLI usage above stays unchanged.

> **Note:** those symlinks point outside the plugin directory (to the repo root).
> Installing from the marketplace copies the plugin and dereferences the symlinks,
> so that path is unaffected. Loading a clone in place with `--plugin-dir` relies
> on the loader following those external symlinks, which isn't guaranteed on every
> Claude Code version — if a plugin's command or data doesn't resolve that way,
> install it from the marketplace, or just run the script directly
> (`python3 grammar_profile.py …` / `python3 vocab_profile.py …`).

## About the original project

Vocabkitchen (<https://vocabkitchen.com/>) is a language-teaching application by
[jegarne](https://github.com/jegarne/vocabkitchen) that lets teachers take a text,
adjust it to a target vocabulary level, and build learning activities from it. Its
free vocabulary profiler has had a global user base for several years. The upstream
repository documents the wider application's architecture (Clean Architecture,
Domain-Driven Design, the mediator pattern, and a custom Angular text editor); this
fork focuses solely on making the profiler runnable on its own.
