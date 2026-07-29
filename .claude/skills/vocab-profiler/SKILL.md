---
name: vocab-profiler
description: Profile the vocabulary level of English text — CEFR level (A1–C2), academic vocabulary (Coxhead's AWL, and the NAWL), and reading difficulty. Use when the user wants to know how hard a text is, what CEFR/proficiency level it targets, which words are advanced or academic, or wants a per-word breakdown of a passage, essay, article, or reading. Runs a dependency-free Python script — no .NET, build step, or install required.
---

# Vocabulary profiler

Reports the vocabulary level of English text against three word lists:

- **CEFR** — buckets words into A1, A2, B1, B2, C1, C2 (the standard
  language-proficiency scale). A word resolves to the **lowest** level it
  legitimately belongs to.
- **AWL** — Coxhead's Academic Word List (is the word academic vocabulary?).
- **NAWL** — the New Academic Word List.

This is a pure-Python port of VocabKitchen's original C# profiler, validated to
produce identical output. It needs only **Python 3** (preinstalled on
Linux/macOS) — no .NET, no build, no third-party packages.

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
| `--text`      | inline text to analyse                                                     |
| `--file`      | path to a UTF-8 text file to analyse                                       |
| `--wordlists` | override the word-list directory (defaults to the bundled lists)           |
| (stdin)       | if neither `--text` nor `--file` is given, text is read from stdin         |

**Choosing input mode:** use `--text` for a short snippet, `--file` for a
document already on disk, and pipe via stdin when the text is produced by another
command. For long or multi-line text prefer `--file` or stdin over `--text` to
avoid shell-quoting issues.

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
  [`WORDLISTS.md`](../../../WORDLISTS.md); the lists live in
  `VkInfrastructure/Profilers/WordLists/`.
