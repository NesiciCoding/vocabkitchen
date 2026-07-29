# VkProfilerCli

A small standalone command-line tool that runs VocabKitchen's **vocabulary profiler**
logic directly — no database, no AWS, no Angular/Node, no authentication. It reads a
piece of text and reports the vocabulary level of every word against three word lists:

- **CEFR** — buckets words into A1, A2, B1, B2, C1, C2 (the standard language-proficiency scale)
- **AWL** — Coxhead's Academic Word List (binary: academic word or not)
- **NAWL** — the New Academic Word List (binary)

It reuses the real profiler code from `VkCore` and `VkInfrastructure`
(`CefrProfiler` / `AwlProfiler` / `NawlProfiler`), so it exercises the same
tokenizer and scoring the web app used — just wrapped in a console entry point
that targets `net8.0`.

## Requirements

- .NET 8 SDK and the ASP.NET Core 8 runtime (pulled in transitively by the
  referenced projects). On Arch/CachyOS: `sudo pacman -S dotnet-sdk-8.0 aspnet-runtime-8.0`.

## Build

```bash
dotnet build VkProfilerCli
```

The word-list `.txt` files in `VkInfrastructure/Profilers/WordLists` are copied
next to the executable at build time, which is where the profilers read them from.

## Usage

```bash
# from the VkProfilerCli directory
dotnet run -- --type cefr --text "The cat sat on the mat."
dotnet run -- --type all  --file essay.txt
echo "She analysed the philosophical implications." | dotnet run -- --type awl
```

Options:

| Flag        | Meaning                                                        |
|-------------|---------------------------------------------------------------|
| `--type`    | `cefr`, `awl`, `nawl`, or `all` (default `all`)                |
| `--text`    | inline text to analyse                                        |
| `--file`    | path to a UTF-8 text file to analyse                          |
| (stdin)     | if neither `--text` nor `--file` is given, text is read from stdin |

Output is JSON: a `totalWordCount` plus, per profiler, each level's percentage,
word count, and the distinct words in that level ranked by number of occurrences.
Words not found in any list appear under `Off List`.

## Word-list data & provenance

The lists that ship in this repo are compiled from public, permissively-licensed sources:

- **CEFR (A1–C2)** — derived from the
  [Words-CEFR-Dataset](https://github.com/Maximax67/Words-CEFR-Dataset) (MIT),
  which is itself built from the CEFR-J dataset and Google N-Gram frequency data.
  Each word is assigned the **lowest** CEFR level among its parts of speech, and the
  profiler matches the lowest-level list first — so common words resolve to the
  lowest level they legitimately belong to.
- **AWL** — the complete
  [Academic Word List](https://www.wgtn.ac.nz/lals/resources/academicwordlist)
  (Coxhead, 2000), all 570 word families expanded to their member forms.
- **NAWL** — the
  [New Academic Word List 1.2](http://www.newgeneralservicelist.org/) headwords
  (Browne, Culligan & Phillips, 2013), expanded with regular inflections to
  improve matching.

### Accuracy notes

- The profiler does exact, case-insensitive **surface-form** matching (no
  lemmatization). Word lists are pre-expanded to inflected forms to compensate.
- The CEFR C2 bucket is large: any real-but-rare word that the dataset knows
  resolves to C2 rather than falling `Off List`. `Off List` therefore tends to
  mean proper nouns, typos, or foreign words.
- These lists are a good, reproducible baseline. For higher precision you could
  swap in a licensed vocabulary profile (e.g. the Oxford 3000/5000 or the
  Octanove C1/C2 profile) using the same one-word-per-line `.txt` format.
