# Vocabkitchen — Vocabulary Profiler

Determine the vocabulary level of any English text from the command line.

This fork turns the profiling feature of [Vocabkitchen](#about-the-original-project)
into a small standalone tool. It reads a piece of text and reports the vocabulary
level of every word against three word lists:

- **CEFR** — buckets words into A1, A2, B1, B2, C1, C2 (the standard language-proficiency scale)
- **AWL** — Coxhead's Academic Word List (is the word academic vocabulary or not)
- **NAWL** — the New Academic Word List

## What this fork adds

- **`vocab_profile.py`** — a single, dependency-free **Python 3** tool that runs
  the original app's profiler logic (the same tokenizer, matching, ordering and
  percentage-rounding as `CefrProfiler` / `AwlProfiler` / `NawlProfiler`) with
  **no database, AWS, Angular, auth — or .NET**. It reuses the exact same word
  lists and is validated to produce identical output to the original C# profiler.
- **A Claude Cowork skill** (`.claude/skills/vocab-profiler/`) that wraps the
  script, so the profiler is available out of the box in a cowork session — just
  ask for the CEFR level or vocabulary breakdown of a text.
- **Rebuilt word-list data** — the CEFR/AWL/NAWL lists in the repo had been
  truncated to only "a" words, which made scoring wrong for real text. They were
  rebuilt in full from documented public sources (each with its own licence) and
  validated against a curated dictionary so only real, correctly-spelled words
  remain. See [`WORDLISTS.md`](WORDLISTS.md) for exact sources, versions, and
  licences.

## Quick start

The profiler needs only **Python 3** (preinstalled on Linux/macOS) — no install,
no build, no dependencies:

```bash
python3 vocab_profile.py --type cefr --text "The cat sat on the mat."
python3 vocab_profile.py --type all  --file essay.txt
echo "She analysed the philosophical implications." | python3 vocab_profile.py --type awl
```

Options:

| Flag          | Meaning                                                                 |
|---------------|-------------------------------------------------------------------------|
| `--type`      | `cefr`, `awl`, `nawl`, `all` (default), or a comma-list like `cefr,awl` |
| `--text`      | inline text to analyse                                                  |
| `--file`      | path to a UTF-8 text file to analyse                                    |
| `--wordlists` | override the word-list directory (defaults to the bundled lists)        |
| (stdin)       | if neither `--text` nor `--file` is given, text is read from stdin      |

Output is JSON: a `totalWordCount` plus, per profiler, each level's percentage,
word count, and the distinct words in that level ranked by number of occurrences.
Words not found in any list appear under `Off List`. See [`WORDLISTS.md`](WORDLISTS.md)
for data provenance and accuracy notes.

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

The original profiler logic still lives in the `VkCore` / `VkInfrastructure`
projects (part of the upstream web app); `vocab_profile.py` is a faithful
standalone port of just that slice.

## About the original project

Vocabkitchen (<https://vocabkitchen.com/>) is a language-teaching application by
[jegarne](https://github.com/jegarne/vocabkitchen) that lets teachers take a text,
adjust it to a target vocabulary level, and build learning activities from it. Its
free vocabulary profiler has had a global user base for several years. The upstream
repository documents the wider application's architecture (Clean Architecture,
Domain-Driven Design, the mediator pattern, and a custom Angular text editor); this
fork focuses solely on making the profiler runnable on its own.
