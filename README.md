# Vocabkitchen — Vocabulary Profiler

Determine the vocabulary level of any English text from the command line.

This fork turns the profiling feature of [Vocabkitchen](#about-the-original-project)
into a small standalone tool. It reads a piece of text and reports the vocabulary
level of every word against three word lists:

- **CEFR** — buckets words into A1, A2, B1, B2, C1, C2 (the standard language-proficiency scale)
- **AWL** — Coxhead's Academic Word List (is the word academic vocabulary or not)
- **NAWL** — the New Academic Word List

## What this fork adds

- **`VkProfilerCli`** — a `net8.0` console tool that runs the original app's
  profiler logic (`CefrProfiler` / `AwlProfiler` / `NawlProfiler` in `VkCore` +
  `VkInfrastructure`) directly, with **no database, AWS, Angular, or auth**. It's
  the same domain code the site used, wrapped in a console entry point.
- **Rebuilt word-list data** — the CEFR/AWL/NAWL lists in the repo had been
  truncated to only "a" words, which made scoring wrong for real text. They were
  rebuilt in full from documented public sources (each with its own licence) and
  validated against a curated dictionary so only real, correctly-spelled words
  remain. See [`VkProfilerCli/README.md`](VkProfilerCli/README.md) for exact
  sources, versions, and licences.

## Quick start

Requires the .NET 8 SDK and the ASP.NET Core 8 runtime (pulled in transitively by
the referenced projects). On Arch / CachyOS:

```bash
sudo pacman -S dotnet-sdk-8.0 aspnet-runtime-8.0
```

Build and run:

```bash
dotnet build VkProfilerCli

cd VkProfilerCli
dotnet run -- --type cefr --text "The cat sat on the mat."
dotnet run -- --type all  --file essay.pdf
echo "She analysed the philosophical implications." | dotnet run -- --type awl
```

Options:

| Flag       | Meaning                                                            |
|------------|-------------------------------------------------------------------|
| `--type`   | `cefr`, `awl`, `nawl`, or `all` (default `all`)                    |
| `--format` | `auto` (default), `json`, or `pretty`                             |
| `--text`   | inline text to analyse                                            |
| `--file`   | path to a `.txt`, `.md`, `.docx`, or `.pdf` file to analyse       |
| (stdin)    | if neither `--text` nor `--file` is given, text is read from stdin |

**Input** — `--file` detects the format from the extension: Markdown
(`.md`/`.markdown`, syntax stripped to prose), Word `.docx`, or `.pdf` (its text
layer; no OCR for scanned pages). Any other extension (`.txt` included) is read
as plain UTF-8 text. See [`VkProfilerCli/README.md`](VkProfilerCli/README.md#input-formats)
for the full table.

**Output** — two shapes, selected by `--format`:

- **JSON** — a `totalWordCount` plus, per profiler, each level's percentage, word
  count, and the distinct words in that level ranked by occurrences (`Off List`
  holds unrecognised words). Ideal for scripting and other tools.
- **Pretty** — a colour-coded terminal view: a CEFR distribution summary,
  per-level word lists, and the text tinted by level (A1 blue → C2 pink).

`--format auto` (default) shows the pretty view in an interactive terminal and
emits JSON when piped/redirected, so downstream tools always get JSON. Full
details, output shape, and accuracy notes are in
[`VkProfilerCli/README.md`](VkProfilerCli/README.md).

### Example

```console
$ dotnet run -- --type cefr --text "Yesterday I walked to the shop to buy bread and milk."
```

Everyday text like this scores as almost entirely A1/A2, while academic text
spreads into the higher bands — e.g. *chlorophyll*, *photosynthesis*, and
*synthesize* resolve to C2.

## About the original project

Vocabkitchen (<https://vocabkitchen.com/>) is a language-teaching application by
[jegarne](https://github.com/jegarne/vocabkitchen) that lets teachers take a text,
adjust it to a target vocabulary level, and build learning activities from it. Its
free vocabulary profiler has had a global user base for several years. The upstream
repository documents the wider application's architecture (Clean Architecture,
Domain-Driven Design, the mediator pattern, and a custom Angular text editor); this
fork focuses solely on making the profiler runnable on its own.
