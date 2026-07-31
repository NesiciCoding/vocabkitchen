# Vocabkitchen — Vocabulary Profiler

Determine the vocabulary level of any English text from the command line.

This fork turns the profiling feature of [Vocabkitchen](#about-the-original-project)
into a small standalone tool. It reads a piece of text and reports the vocabulary
level of every word against three word lists:

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
- **A Claude Code plugin & skill** — an installable plugin
  ([`plugins/vocab-profiler/`](plugins/vocab-profiler)) plus a repo-local skill
  (`.claude/skills/vocab-profiler/`) that wrap the script, so the profiler is
  available in a Claude Code / Cowork session — just ask for the CEFR level or
  vocabulary breakdown of a text. See [Use in Claude Code](#use-in-claude-code).
- **Rebuilt word-list data** — the CEFR/AWL/NAWL lists in the repo had been
  truncated to only "a" words, which made scoring wrong for real text. They were
  rebuilt in full from documented public sources (each with its own licence) and
  validated against a curated dictionary so only real, correctly-spelled words
  remain. See [`WORDLISTS.md`](WORDLISTS.md) for exact sources, versions, and
  licences.

## Quick start

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

## Use in Claude Code

Beyond the command line, the profiler ships as a **Claude Code plugin**, so you
can ask Claude for a text's CEFR level or vocabulary breakdown right in a session
instead of invoking the script yourself.

### Install from the marketplace

```bash
/plugin marketplace add NesiciCoding/vocabkitchen-CLI
/plugin install vocab-profiler@vocabkitchen
```

Then just ask — e.g. *"What CEFR level is this paragraph?"* — or invoke the skill
explicitly with `/vocab-profiler:vocab-profiler`. The plugin still needs
**Python 3** on your machine: it bundles the script and word lists, not a runtime.

Updates are automatic. The plugin is intentionally unversioned, so every push to
this repo counts as a new release and Claude Code picks it up on its next
background marketplace refresh (force one with `/plugin marketplace update`).

### Try it before installing

To load the plugin straight from a clone, without adding the marketplace:

```bash
claude --plugin-dir ./plugins/vocab-profiler
```

The plugin lives in [`plugins/vocab-profiler/`](plugins/vocab-profiler); its
`vocab_profile.py`, `WordLists/`, and `WORDLISTS.md` are symlinks to the canonical
copies at the repo root, so there is a single source of truth and the plain CLI
usage above stays unchanged.

## About the original project

Vocabkitchen (<https://vocabkitchen.com/>) is a language-teaching application by
[jegarne](https://github.com/jegarne/vocabkitchen) that lets teachers take a text,
adjust it to a target vocabulary level, and build learning activities from it. Its
free vocabulary profiler has had a global user base for several years. The upstream
repository documents the wider application's architecture (Clean Architecture,
Domain-Driven Design, the mediator pattern, and a custom Angular text editor); this
fork focuses solely on making the profiler runnable on its own.
