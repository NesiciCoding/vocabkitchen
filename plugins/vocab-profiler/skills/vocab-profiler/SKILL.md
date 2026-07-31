---
name: vocab-profiler
description: Profile the vocabulary level of English text — CEFR level (A1–C2) and academic vocabulary (Coxhead's AWL, and the NAWL). Use when the user wants to know what CEFR/proficiency level a text targets, how lexically demanding its vocabulary is, which words are advanced or academic, or wants a per-word breakdown of a passage, essay, article, or reading. Reports vocabulary-level distribution, not a readability score (Flesch–Kincaid, etc.). Runs a dependency-free Python 3 script — no build step or third-party packages required.
---

# Vocabulary profiler

Reports the vocabulary level of English text against three word lists:

- **CEFR** — buckets words into A1, A2, B1, B2, C1, C2 (the standard
  language-proficiency scale). A word resolves to the **lowest** level it
  legitimately belongs to.
- **AWL** — Coxhead's Academic Word List (is the word academic vocabulary?).
- **NAWL** — the New Academic Word List.

This is a pure-Python port of VocabKitchen's original C# profiler, validated to
produce identical output. It needs only **Python 3** — no build, no third-party
packages (PDF input is the one exception; see `--file`). Most Linux/macOS
systems already have Python 3; if a run fails, confirm with `python3 --version`.

## How to run

This plugin puts a **`vocab-profile`** command on your PATH — invoke it directly;
you don't need to know where the script lives. It finds its bundled word lists
automatically.

```bash
vocab-profile --type cefr --text "The cat sat on the mat."
vocab-profile --type all  --file essay.txt
echo "She analysed the philosophical implications." | vocab-profile --type awl
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

**Output format:** when the command's output is captured (the normal case here —
stdout is not a terminal), it emits **JSON automatically**, so the parsing below
applies unchanged. `--format pretty` produces a colour-coded terminal view for a
human at a prompt; pass `--format json` to force JSON in any context.

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
- If `vocab-profile` is somehow not on PATH, run the bundled script directly:
  `python3 "${CLAUDE_PLUGIN_ROOT}/vocab_profile.py" …`.
- Word-list sources, licences, and build method are documented in the bundled
  `WORDLISTS.md` (`${CLAUDE_PLUGIN_ROOT}/WORDLISTS.md`).
