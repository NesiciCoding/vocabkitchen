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
- **AWL** — the published word families, all member forms, as distributed.
- **NAWL** — the canonical headwords plus regular inflections, keeping only
  inflected forms that are attested in the validation dictionary (so
  over-generated non-words are excluded).

## Accuracy notes

- The profiler does exact, case-insensitive **surface-form** matching (no
  lemmatization). Word lists are pre-expanded to inflected forms to compensate.
- `Off List` covers words outside the validation dictionary — typically proper
  nouns, abbreviations, typos, or foreign words.
- These lists are a reproducible baseline. For higher precision you could swap in
  a licensed vocabulary profile (e.g. the Oxford 3000/5000 or the Octanove C1/C2
  profile) using the same one-word-per-line `.txt` format.
