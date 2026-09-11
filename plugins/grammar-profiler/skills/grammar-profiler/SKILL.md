---
name: grammar-profiler
description: Profile the grammar of English text by CEFR level — which grammatical constructions it uses (tenses, aspect, the passive, modals, relative clauses, conditionals, non-finite forms, …) and what CEFR level each maps to. Use when the user wants to know how grammatically demanding a text is, which structures a passage uses, its grammatical range or level, or a construction-by-construction breakdown. Reports grammar-construction distribution, not vocabulary and not a readability score. Companion to the vocab-profiler skill. Requires Python 3 + spaCy (en_core_web_sm).
---

# Grammar profiler

Reports which **grammatical constructions** a text uses and maps each to a CEFR
level, so you can see how grammatically demanding it is and where its structural
range reaches — the grammar counterpart to the vocabulary profiler.

It detects ~70 constructions across every major family: tense & aspect (present
perfect, past progressive, …), modality (modals, *have to*, *be going to*),
voice (the passive, *get*-passive), non-finite forms (to-infinitives, gerunds,
*having/being* + past participle), comparison, relative clauses, subordination,
conditionals, questions, imperatives, causatives, and inversion. Each is mapped
to a CEFR level taken from the **CEFR-J Grammar Profile**.

Detection is **rule-based** — deterministic rules over a spaCy part-of-speech and
dependency parse. There is no LLM in the loop; the JSON is a mechanical analysis
you then interpret.

## Requirements

Unlike the vocabulary profiler, this tool **requires spaCy** and the small
English model, because reliable grammar detection needs real parsing. The
plugin bundles a one-command installer — when the command reports the engine is
missing, offer to run it:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/install.sh"
```

It creates a `.venv` next to the bundled script and installs spaCy, the English
model, and pypdf, verifying each step. The tool **auto-detects that `.venv`** and
re-launches under it, so nothing needs activating. This works even on
"externally-managed" systems (Arch, Debian, …) where `pip install` into the
system Python is blocked.

If you'd rather set it up by hand, the installer's core is just:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"   # so .venv lands where the tool looks for it
python3 -m venv .venv
.venv/bin/python -m pip install spacy pypdf
.venv/bin/python -m spacy download en_core_web_sm
```

(`pypdf` is only needed for PDF input; drop it otherwise. On a system with a
writable Python, plain `pip install spacy pypdf && python3 -m spacy download
en_core_web_sm` also works. To use an environment elsewhere, set
`GRAMMAR_PROFILE_PYTHON=/path/to/python`.) If spaCy or the model can't be found,
the command exits with install guidance on stderr — surface it to the user and
offer to run the installer rather than guessing. The plugin bundles the script,
CEFR-J data, and the installer, not a Python runtime or spaCy.

## How to run

This plugin puts a **`grammar-profile`** command on your PATH — invoke it
directly; you don't need to know where the script lives. It finds its bundled
CEFR-J data automatically.

```bash
grammar-profile --text "If I had known, I would have helped."
grammar-profile --file essay.docx
echo "The results were analysed by the team." | grammar-profile
```

Flags:

| Flag                | Meaning                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `--format`          | `auto` (default), `json`, or `pretty`                                   |
| `--text`            | inline text to analyse                                                   |
| `--file`            | path to a `.txt`, `.md`, `.docx`, or `.pdf` file (PDF needs `pypdf`)     |
| `--grammar-profile` | override the CEFR-J data directory (defaults to the bundled profile)     |
| (stdin)             | if neither `--text` nor `--file` is given, text is read from stdin       |

**Choosing input mode:** `--text` for a snippet, `--file` for a document on disk,
stdin when piping. For long or multi-line text prefer `--file` or stdin over
`--text` to avoid shell-quoting issues. `--file` detects the format from the
extension (Markdown is stripped to prose; `.docx`/`.pdf` have their text
extracted; anything else is read as UTF-8).

**Output format:** when you capture the output (stdout is not a terminal), it
emits **JSON automatically**. `--format pretty` gives a colour-coded terminal view
for a human; `--format json` forces JSON in any context.

## Output

JSON on stdout. Shape:

```json
{
  "sentenceCount": 3,
  "tokenCount": 24,
  "constructionCount": 6,
  "estimatedLevel": { "typical": "A2", "reaches": "B2" },
  "results": {
    "A1": { "constructionCount": 2, "distinct": 2,
            "constructions": [
              { "id": "there_be", "name": "Existential there + be",
                "category": "Existential", "count": 1,
                "examples": [ { "span": "There is", "sentence": "There is a book here." } ] }
            ] },
    "A2": { "...": {} }, "B1": {}, "B2": {}, "C1": {}, "C2": {}
  }
}
```

- `results` is banded by CEFR level (A1–C2). Each band lists its total
  `constructionCount`, the number of `distinct` constructions, and each
  construction's `name`, `category`, `count`, and up to three `examples`
  (matched `span` + the `sentence` it came from).
- `estimatedLevel.typical` is the busiest band; `estimatedLevel.reaches` is the
  highest band with any construction.

## Interpreting results for the user

- **Grammatical range**: everyday text stays in A1/A2 (simple present/past,
  basic modals); more advanced writing reaches B2/C1 (perfect aspect, the
  passive, conditionals, relative clauses, inversion). Read `typical` for the
  centre of gravity and `reaches` for the ceiling.
- Don't just dump the JSON. Summarise: state the typical level and the range,
  then name the most advanced constructions found (highest bands) with a short
  example each. Show raw JSON only if asked.
- This is an **estimate of grammatical range**, not a readability score and not a
  census — detection is bounded by the parser and a curated construction set.
- Constructions can overlap by design (a third conditional also contains a past
  perfect); report them as found rather than implying double-counting is an error.

## Pair with the vocabulary profiler

For a fuller analysis, also run the **vocab-profiler** plugin (or better: the
**text-report** plugin, which runs both at once): grammar range + vocabulary
level together describe a text's difficulty far better than either alone, and
text-report adds a target-level verdict and coverage figure for teachers. A
typical combined answer states the CEFR vocabulary band *and* the grammatical
range, then flags the hardest words and the most advanced structures.

## Notes

- If `grammar-profile` is somehow not on PATH, run the bundled script directly:
  `python3 "${CLAUDE_PLUGIN_ROOT}/grammar_profile.py" …`.
- Data provenance, the full construction-to-level table, and licensing/citation
  for the CEFR-J Grammar Profile are in the bundled `GRAMMARPROFILE.md`
  (`${CLAUDE_PLUGIN_ROOT}/GRAMMARPROFILE.md`).
