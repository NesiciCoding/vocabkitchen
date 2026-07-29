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

Each list is built from a documented source and validated against a curated
dictionary so that only real, correctly-spelled words are included. Sources and
their licences differ, so they are listed per-list rather than under a single
blanket claim.

### Sources

- **CEFR (A1–C2)** — the
  [Words-CEFR-Dataset](https://github.com/Maximax67/Words-CEFR-Dataset)
  (`csv/words.csv` + `csv/word_pos.csv`), **MIT-licensed**, itself derived from
  the CEFR-J dataset and Google Books N-Gram frequency data.
- **AWL** — Coxhead's Academic Word List (Coxhead, A. 2000, *A New Academic Word
  List*, TESOL Quarterly 34(2): 213–238): 570 word families, all member forms.
  Published for research/education use by Victoria University of Wellington
  ([archived copy](https://web.archive.org/web/20191117100958/https://www.victoria.ac.nz/lals/resources/academicwordlist);
  the [live page](https://www.wgtn.ac.nz/lals/resources/academicwordlist) was
  reachable at the time of writing).
- **NAWL** — the New Academic Word List v1.2 (Browne, C., Culligan, B. &
  Phillips, J. 2013): ~960 headwords. The original host
  (`newgeneralservicelist.org`) is **no longer controlled by the authors and now
  serves unrelated content**, so this cites the
  [archived copy (Jan 2020)](https://web.archive.org/web/20200108211829/http://www.newgeneralservicelist.org/)
  instead of the live domain.
- **Dictionary (validation filter)** — the
  [12dicts](http://wordlist.aspell.net/12dicts/) `2of12inf` list, package
  **v6.0.2** (compiled by Alan Beale, released to the **public domain**),
  supplemented with algorithmically derived British `-ise`/`-yse` spelling
  variants. Every word that ships in the CEFR and NAWL lists must appear in this
  dictionary.

### How the lists are built from those sources

- **CEFR** — each word is assigned the **lowest** CEFR level among its parts of
  speech; words whose only part-of-speech tags are proper nouns (NNP/NNPS) are
  dropped; every remaining surface form must be in the validation dictionary.
  The profiler then matches the lowest-level list first, so common words resolve
  to the lowest level they legitimately belong to.
- **AWL** — the published word families, all member forms, as distributed.
- **NAWL** — the canonical headwords plus regular inflections, keeping only
  inflected forms that are attested in the validation dictionary (so
  over-generated non-words are excluded).

### Accuracy notes

- The profiler does exact, case-insensitive **surface-form** matching (no
  lemmatization). Word lists are pre-expanded to inflected forms to compensate.
- `Off List` covers words outside the validation dictionary — typically proper
  nouns, abbreviations, typos, or foreign words.
- These lists are a reproducible baseline. For higher precision you could swap in
  a licensed vocabulary profile (e.g. the Oxford 3000/5000 or the Octanove C1/C2
  profile) using the same one-word-per-line `.txt` format.
