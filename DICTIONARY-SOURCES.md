# Dictionary sources — replacing the Cambridge Dictionary API enrichment

Research notes (August 2026) on free/open alternatives to the paid Cambridge
Dictionary API used for vocabulary enrichment. Applies to RubricMaker's
vocabulary panel ("Look up" → fills CEFR level + definition) and to the
`--export flashcards` deck in `text_report.py`, which currently ships without
definitions or phonetics.

## What is being replaced

`RubricMaker/src/services/cambridgeApi.ts` (`lookupWord`) returns exactly two
fields per word:

- **CEFR level** (`<lvl>` element, A1–C2) — used as a *secondary* lookup "to
  fill gaps in the bundled CEFR-J dataset"; never overwrites teacher-entered
  values.
- **Plain-text definition** (`<def>` element, first sense).

It is optional, offline-graceful, and fails silently on any error. The
replacement must preserve that contract.

## What "OpenDict" is (and isn't)

"OpenDict" is an ambiguous name — none of the things it points at is a
drop-in replacement on its own:

- **`open-dict-data`** (github.com/open-dict-data, open-dict-data.github.io) —
  an org collecting *open-licensed dictionary data*. Its flagship repo,
  **`ipa-dict`**, is **IPA pronunciations only** (word → phonemic IPA, including
  inflected forms). No definitions, no CEFR levels. Useful for the deck's
  `phonetic` column, nothing more. Licensing caveat: the English-US data is
  MIT-derived (cmudict-ipa), but **English-UK is GPL-3.0-derived** — keep it out
  of anything you redistribute.
- The org's `wikidict-*` repos are bilingual reference wordlists (Wikipedia
  titles ↔ Wikidata labels) — no definitions or levels.
- The old **"OpenDict" desktop dictionary app** (Debian package) — not embeddable.
- **국립국어원 "opendict"** — a Korean dictionary API. Korean-only.
- There is **no `opendict` package on PyPI** (404).

**Verdict:** OpenDict the project covers *phonetics* (via `ipa-dict`) and can
back the deck's `phonetic` column, but it does not solve definitions or CEFR
levels.

## The definition half — candidates

| Source | Cost / key | Definition | IPA | POS | Examples | Licensing | Notes |
|---|---|---|---|---|---|---|---|
| **Free Dictionary API** (`dictionaryapi.dev`) | free, no key | ✅ | ✅ text+audio | ✅ | ✅ (some entries) | Wiktionary CC BY-SA 3.0/4.0 | Live-verified JSON (`word`, `phonetic`, `phonetics[]`, `meanings[].partOfSpeech`, `definitions[].definition`). Hobby project, no SLA; hosted fork `freedictionaryapi.com` publishes 1,000 req/hr/IP. Cache aggressively. |
| **Wiktionary API** (direct) | free, no key | ✅ | ✅ | ✅ | ✅ | CC BY-SA 4.0 (+GFDL) | The upstream. Requires a descriptive User-Agent; generous rate limits. Definitions are learner-quality and plentiful. Dumps (Kaikki.org) allow a fully offline build at index cost. |
| **Open English WordNet** (`globalwordnet/english-wordnet`) | free, **offline** | ✅ | ❌ | ✅ | ✅ (gloss examples) | **CC BY 4.0** — permissive, bundle-safe | 161,875 words / 120k synsets. Glosses are dictionary-style, not learner-facing. Ships as JSON/WNDB; `wn` Python lib; also a hosted API (en-word.net). Best offline fallback. |
| **Wordnik** | free developer key | ✅ | ✅ (IPA+audio) | ✅ | ✅ | proprietary, display-only | Definitions/examples/frequency are good; data can't be bundled; project maintenance has been spotty. |
| **Merriam-Webster** | free key, non-commercial | ✅ | ✅ | ✅ | ✅ | proprietary | Free tier is non-commercial only — not a fit for a commercial app. |

## The CEFR-level half — no free *API* does this

No free dictionary API returns CEFR levels (Cambridge's learner dictionary is
unusual in tagging `<lvl>`; Oxford 3000/5000 and the English Vocabulary Profile
are licensed, not open). CEFR-tagged vocabulary only exists as **wordlists**,
and the project already bundles the best open one:

- `WordLists/CEFR/*.txt` — built from **Maximax67/Words-CEFR-Dataset** (MIT;
  itself CEFR-J + Google Books N-Gram derived), with part-of-speech data
  (`word_pos.csv`) and a public-domain validation dictionary. See WORDLISTS.md.
- **`openlanguageprofiles/olp-en-cefrj`** — the open CEFR-J profiles:
  `cefrj-vocabulary-profile-1.5.csv` (verified: `headword,pos,CEFR,CoreInventory…`,
  ~7,800 rows, even topic tags) plus the Octanove C1/C2 profile. Same lineage as
  the bundled data — a natural gap-filler for words the current lists miss.

So the `<lvl>` gap-filling should come from **merging open wordlists**, not an
API. This matches how the tools already work offline, costs nothing, and needs
no key.

## Recommended architecture

Layered, preserving the "fill only what's empty, fail silently offline" contract:

1. **Definitions + IPA + POS + examples** — **Free Dictionary API**
   (`dictionaryapi.dev`) as the turnkey online lookup: one fetch, JSON, no key.
   Cache results (definitions are stable). On failure/offline → fall through.
2. **Offline fallback** — bundle **Open English WordNet** (CC BY 4.0, JSON
   download) for definitions when the API is unreachable or misses; glosses are
   acceptable as a last resort and the app is already offline-capable.
3. **CEFR levels** — drop the API for levels entirely; extend the bundled
   CEFR lists with the OLP-EN-CEFRJ profiles (MIT/CEFR-J lineage) so "gaps"
   get filled from open wordlists.
4. **Phonetics for the deck** — `phonetic` from the Free Dictionary API first;
   `ipa-dict` en_US as a local fallback (avoid en_UK, GPL).

Licensing for a commercial/self-hosted product with a marketplace: Wiktionary
data used via an API (display, not redistribution) needs only an attribution
line ("Definitions © Wiktionary, CC BY-SA"); WordNet and the CEFR wordlists are
safe to bundle; ipa-dict en_UK is the only thing to exclude.

## Open questions

- Freq of lookup (per-word on demand vs. batch pre-enrich of a deck) — batching
  needs rate-limit politeness and a cache.
- Whether the app should self-host the Free Dictionary API data (it's
  open-source) to remove the hobby-host dependency entirely.
- Attribution UI: where to show the CC BY-SA / CC BY credit line.

## Status (August 2026)

Done in the CLI (`vocabkitchen-CLI`):

1. **OLP-EN-CEFRJ merged into the wordlist build** — `build_wordlists.py --merge`
   gap-fills `WordLists/CEFR/*.txt` from the bundled `cefrj-vocabulary-profile-1.5.csv`
   (CEFR-J A1–B2) and `octanove-vocabulary-profile-c1c2-1.0.csv` (Octanove C1/C2)
   and emits `WordLists/CEFR/levels.json` — a complete `word → {level, pos}`
   index. CEFR-level lookup now needs **no dictionary API**. (Existing
   classifications are authoritative; the profiles only fill gaps.)
2. **Definitions + phonetics wired into `--export flashcards`** — the deck is
   enriched by default from the Free Dictionary API (no key): back = plain
   definition, example = the in-text context sentence, phonetic + partOfSpeech
   filled (POS falls back to the OLP index). Offline/miss → in-context back,
   `--no-enrich` to skip, `--dictionary-url` to override. Lookups (hits **and**
   definitive misses) are cached in a JSON file keyed by API URL and word
   (default `~/.cache/efl-tools/dictionary.json`, `--dictionary-cache PATH`
   to override, `--no-dictionary-cache` to disable), so repeat exports make no
   repeat requests — the politeness layer for the hobby-host API.
3. **Batch pre-enrichment** — `--pre-enrich --file class_vocab.txt` (or
   `--text`/stdin with an essay) primes the cache for a whole class in one
   polite, rate-limited pass: `--delay SECONDS` spaces requests out (default
   0.25), `--limit N` caps new lookups, cached words are skipped, and later
   deck exports answer entirely from the cache.

Not done (deferred):

1. **RubricMaker-side `lookupWord` swap** — replace `cambridgeApi.lookupWord`
   with the free stack: the `{ level, definition }` contract plus phonetic/POS
   was prototyped conceptually here, but RubricMaker still calls
   `cambridgeApi.ts`. Its CEFR-J + open-vocab merge already covers level
   lookup locally; the definition half is the remaining swap, and the CLI's
   `levels.json`/deck output give it the same data the CLI now uses.
