---
name: vocab-profiler
description: Profile the vocabulary level of English text — CEFR level (A1–C2) and academic vocabulary (Coxhead's AWL, and the NAWL). Use when the user wants to know what CEFR/proficiency level a text targets, how lexically demanding its vocabulary is, which words are advanced or academic, or wants a per-word breakdown of a passage, essay, article, or reading. Reports vocabulary-level distribution, not a readability score (Flesch–Kincaid, etc.). Runs a dependency-free Python script — no .NET, build step, or third-party packages required.
---

# Vocabulary profiler

Reports the vocabulary level of English text against three word lists:

- **CEFR** — buckets words into A1, A2, B1, B2, C1, C2 (the standard
  language-proficiency scale). A word resolves to the **lowest** level it
  legitimately belongs to.
- **AWL** — Coxhead's Academic Word List (is the word academic vocabulary?).
- **NAWL** — the New Academic Word List.

This is a pure-Python port of VocabKitchen's original C# profiler, validated to
produce identical output. It needs only **Python 3** — no .NET, no build, no
third-party packages. Most Linux/macOS systems already have it; if a run fails,
confirm with `python3 --version`.

## How to run

The script is [`vocab_profile.py`](../../../vocab_profile.py) at the repo root.
It finds its word lists relative to its own location, so it can be invoked from
any directory.

```bash
python3 vocab_profile.py --type cefr --text "The cat sat on the mat."
python3 vocab_profile.py --type all  --file essay.txt
echo "She analysed the philosophical implications." | python3 vocab_profile.py --type awl
```

Flags:

| Flag          | Meaning                                                                   |
|---------------|---------------------------------------------------------------------------|
| `--type`      | `cefr`, `awl`, `nawl`, `all` (default), or a comma-list like `cefr,awl`   |
| `--format`    | `auto` (default), `json`, or `pretty` — see below                         |
| `--text`      | inline text to analyse                                                     |
| `--file`      | path to a `.txt`, `.md`, `.docx`, or `.pdf` file (PDF needs the optional `pypdf` package) |
| `--wordlists` | override the word-list directory (defaults to the bundled lists)           |
| (stdin)       | if neither `--text` nor `--file` is given, text is read from stdin         |

**Choosing input mode:** use `--text` for a short snippet, `--file` for a
document already on disk, and pipe via stdin when the text is produced by another
command. For long or multi-line text prefer `--file` or stdin over `--text` to
avoid shell-quoting issues. `--file` detects the format from the extension:
Markdown syntax is stripped to prose, `.docx` and `.pdf` have their text
extracted (`.txt` and anything else is read as UTF-8). Only PDF needs a
third-party package (`pip install pypdf`); everything else is stdlib-only.

**Output format:** when you run the script and capture its output (the normal
case here — stdout is not a terminal), it emits **JSON automatically**, so the
parsing below applies unchanged. `--format pretty` produces a colour-coded
terminal view for a human at a prompt; pass `--format json` to force JSON in any
context.

## Output

JSON on stdout. Shape:

```json
{
  "totalWordCount": 6,
  "results": {
    "cefr": {
      "A1": { "percentage": "83%", "wordCount": 5, "words": [ { "word": "the", "occurrences": 2 }, ... ] },
      "A2": { "percentage": "0%",  "wordCount": 0, "words": [] },
      "...": {},
      "Off List": { "percentage": "17%", "wordCount": 1, "words": [ ... ] }
    }
  }
}
```

- Each level lists its **percentage** of total words, its **wordCount**, and the
  distinct **words** in that level ranked by number of occurrences.
- `Off List` = words in no list — typically proper nouns, names, abbreviations,
  typos, numbers, or foreign words. A high Off-List share usually means names or
  jargon, not that the text is hard.
- For `awl`/`nawl`, the matched-words bucket is keyed `"Awl"` / `"Nawl"`; the
  rest fall under `Off List`.

## Interpreting results for the user

- **Overall level**: everyday text sits almost entirely in A1/A2; academic or
  technical text spreads into B2/C1/C2. Read the level with the highest
  non-trivial share, and note where the distribution's tail reaches.
- Don't just dump the JSON. Summarise: state the dominant CEFR band, call out the
  hardest words (highest levels / academic hits), and give the AWL/NAWL academic
  density if relevant. Show the raw JSON only if the user asks for detail.
- The profiler does exact, case-insensitive **surface-form** matching (no
  lemmatization); the lists are pre-expanded to inflected forms.

## Notes

- Verify Python is available with `python3 --version` if a run fails.
- Word-list sources, licences, and build method are documented in
  [`WORDLISTS.md`](../../../WORDLISTS.md); the lists live in the `WordLists/`
  folder at the repo root.
