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
- **Claude Code plugins & skills** — installable plugins
  ([`plugins/vocab-profiler/`](plugins/vocab-profiler),
  [`plugins/grammar-profiler/`](plugins/grammar-profiler)) plus repo-local skills
  (`.claude/skills/`) that wrap the scripts, so the profilers are available in a
  Claude Code / Cowork session — just ask for the CEFR level, vocabulary
  breakdown, or grammatical range of a text. See
  [Use in Claude Code](#use-in-claude-code).
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
| `--cloze`           | render exported examples as `{{...}}` fill-the-gap sentences (RubricMaker syntax; `--export md\|csv` only) |
| `--no-enrich`       | `--export flashcards` only: skip the Free Dictionary API (card backs stay the in-text context sentence) |
| `--dictionary-url`  | `--export flashcards` only: override the dictionary API base URL (proxy / test server) |
| `--dictionary-cache`| JSON cache file for lookups (default `~/.cache/vocabkitchen/dictionary.json`) |
| `--no-dictionary-cache` | don't read or write the lookup cache (`--pre-enrich` and `--export flashcards` only) |
| `--pre-enrich`     | prime the dictionary cache from the input (word list or essay) in one rate-limited pass, then exit |
| `--delay`          | `--pre-enrich` only: seconds between requests (default 0.25; `0` for none) |
| `--limit`          | `--pre-enrich` only: cap the number of new lookups |
| `--output`          | where the `--export` file goes (default: `<stem>-preteaching-<LEVEL>.<ext>` next to the input, or `preteaching-<LEVEL>.<ext>` in the cwd; decks get a `-deck` suffix) |
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
structures), which the exports use to show every item in context. Run the
regression tests with:

```bash
python3 test_text_report.py
```

## Use in Claude Code

Beyond the command line, the profilers ship as **Claude Code plugins**, so you
can ask Claude for a text's CEFR level, vocabulary breakdown, grammatical range —
or a unified *"is this text right for my class?"* report — right in a session
instead of invoking the scripts yourself.

### Install from the marketplace

```bash
/plugin marketplace add NesiciCoding/vocabkitchen-CLI
/plugin install vocab-profiler@vocabkitchen
/plugin install grammar-profiler@vocabkitchen
/plugin install text-report@vocabkitchen
```

Then just ask — e.g. *"What CEFR level is this paragraph?"*, *"What grammar does
this text use?"*, or *"Is this text right for my B1 class?"* — or invoke a skill
explicitly with `/vocab-profiler:vocab-profiler` /
`/grammar-profiler:grammar-profiler` / `/text-report:text-report`. The plugins
need **Python 3** on your machine (they bundle the scripts and data, not a
runtime); the grammar plugin and the grammar half of text-report additionally
need **spaCy** (`pip install spacy && python3 -m spacy download en_core_web_sm`).

Updates are automatic. The plugins are intentionally unversioned, so every push to
this repo counts as a new release and Claude Code picks it up on its next
background marketplace refresh (force one with `/plugin marketplace update`).

### Try it before installing

To load a plugin straight from a clone, without adding the marketplace:

```bash
claude --plugin-dir ./plugins/vocab-profiler
claude --plugin-dir ./plugins/grammar-profiler
claude --plugin-dir ./plugins/text-report
```

The plugins live in [`plugins/vocab-profiler/`](plugins/vocab-profiler),
[`plugins/grammar-profiler/`](plugins/grammar-profiler) and
[`plugins/text-report/`](plugins/text-report); each bundles its scripts and data
as symlinks to the canonical copies at the repo root, so there is a single
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
