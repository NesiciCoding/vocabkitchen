# Word-list data & provenance

The profiler scores text against the CEFR / AWL / NAWL word lists in the
`WordLists/` folder at the repo root (one word per line, plain UTF-8 `.txt`).
Each list is built from a documented source and validated against a curated
dictionary so that only real, correctly-spelled words are included. Sources and
their licences differ, so they are listed per-list rather than under a single
blanket claim.

## Sources

- **CEFR (A1–C2)** — the
  [Words-CEFR-Dataset](https://github.com/Maximax67/Words-CEFR-Dataset)
  (`csv/words.csv` + `csv/word_pos.csv`), **MIT-licensed**, itself derived from
  the CEFR-J dataset and Google Books N-Gram frequency data.
- **CEFR gap-fill (A1–C2)** — the
  [OLP-EN-CEFRJ](https://github.com/openlanguageprofiles/olp-en-cefrj)
  profiles, bundled alongside the lists as
  `WordLists/CEFR/cefrj-vocabulary-profile-1.5.csv` (CEFR-J A1–B2, 7,798 rows)
  and `WordLists/CEFR/octanove-vocabulary-profile-c1c2-1.0.csv` (Octanove
  C1/C2, 2,135 rows). The CEFR-J resources are © Tono Laboratory, Tokyo
  University of Foreign Studies, made available for research and commercial
  use **at no cost, provided the source is cited** — cite as *Tono, Y. (ed.)
  The CEFR-J Vocabulary Profile. Tono Laboratory, Tokyo University of Foreign
  Studies. <https://www.cefr-j.org/>*; the Octanove profile is the same
  project's open C1/C2 banding.
- **AWL** — Coxhead's Academic Word List (Coxhead, A. 2000, *A New Academic Word
  List*, TESOL Quarterly 34(2): 213–238): 570 word families, all member forms.
  Published for research/education use by Victoria University of Wellington
  ([archived copy](https://web.archive.org/web/20191117100958/https://www.victoria.ac.nz/lals/resources/academicwordlist);
  the [live page](https://www.wgtn.ac.nz/lals/resources/academicwordlist) was
  reachable at the time of writing).
- **NAWL** — the New Academic Word List v1.2 (Browne, C., Culligan, B. &
  Phillips, J. 2013): ~960 headwords. Licensed under
  [**Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**](https://creativecommons.org/licenses/by-sa/4.0/):
  *"New Academic Word List by Browne, C., Culligan, B., and Phillips, J. is
  licensed under a Creative Commons Attribution-ShareAlike 4.0 International
  License."* The authors' canonical site is
  [charlie-browne.com](https://www.charlie-browne.com/); the original host
  (`newgeneralservicelist.org`) still carries the list and its licence notice but
  its site chrome now shows **unrelated third-party content**, so for stability
  this also references the
  [archived copy (Jan 2020)](https://web.archive.org/web/20200108211829/http://www.newgeneralservicelist.org/).
  Because CC BY-SA 4.0 is a share-alike licence, `WordLists/NAWL/nawl.txt` is
  redistributed here under the same terms with the attribution above.
- **Dictionary (validation filter)** — the
  [12dicts](http://wordlist.aspell.net/12dicts/) `2of12inf` list, package
  **v6.0.2** (compiled by Alan Beale, released to the **public domain**),
  supplemented with algorithmically derived British `-ise`/`-yse` spelling
  variants. Every word that ships in the CEFR and NAWL lists must appear in this
  dictionary.

## How the lists are built from those sources

- **CEFR** — each word is assigned the **lowest** CEFR level among its parts of
  speech; words whose only part-of-speech tags are proper nouns (NNP/NNPS) are
  dropped; every remaining surface form must be in the validation dictionary.
  The profiler then matches the lowest-level list first, so common words resolve
  to the lowest level they legitimately belong to.
- **CEFR OLP-EN-CEFRJ merge** — `build_wordlists.py --merge` gap-fills the six
  lists from the bundled OLP-EN-CEFRJ profiles. The merge rule is
  **conservative: existing classifications are authoritative; the profiles only
  fill gaps** — a profile headword is added at its level only when it is absent
  from all six current lists, so nothing already classified ever moves (the
  profiler's published outputs and regression tests stay stable while
  previously unrecognised words gain a level). Slash-separated spelling
  variants (`adviser/advisor`) are split into separate forms; multi-word
  phrases (`according to`) can't be matched by the token profiler, so they land
  in the machine-readable index only. The script is idempotent
  (`--check` verifies the lists and reports what a merge would change) and
  also writes **`WordLists/CEFR/levels.json`**: a complete `word → {level,
  pos}` index of every list word plus the profile phrases — the API-free CEFR
  level lookup that `--export flashcards` and RubricMaker-style tools use.
- **AWL** — the published word families, all member forms, as distributed.
- **NAWL** — the canonical headwords plus regular inflections, keeping only
  inflected forms that are attested in the validation dictionary (so
  over-generated non-words are excluded).

## Accuracy notes

- The profiler does exact, case-insensitive **surface-form** matching (no
  lemmatization). Word lists are pre-expanded to inflected forms to compensate.
- The OLP-EN-CEFRJ merge adds the profile's **headword forms** as-is (plus any
  inflected forms the profile itself lists, e.g. `abandoned` B2) — no
  heuristic inflection expansion, matching the profiler's exact surface-form
  matching. A word added by the merge is therefore recognised in the form the
  profile lists, not in every inflection.
- `Off List` covers words outside the validation dictionary — typically proper
  nouns, abbreviations, typos, or foreign words.
- These lists are a reproducible baseline. For higher precision you could swap in
  a licensed vocabulary profile (e.g. the Oxford 3000/5000 or the Octanove C1/C2
  profile) using the same one-word-per-line `.txt` format.
