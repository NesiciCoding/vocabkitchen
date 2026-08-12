"""dictionary.py — the shared dictionary lookup stack (Phase 5).

The layered lookup **both** front ends use — the free replacement for the
paid Cambridge Dictionary API's ``lookupWord``, preserving its contract
(``{level, definition}``, offline-graceful, fail-silent):

1. **CEFR level** — the bundled ``WordLists/CEFR/levels.json`` index
   (built by ``build_wordlists.py`` from the OLP-EN-CEFRJ profiles). Levels
   never come from a dictionary API — the CLI and RubricMaker both answer
   from bundled data alone.
2. **Definitions + phonetics + POS** — the Free Dictionary API
   (``dictionaryapi.dev``, free, no key) — the same fetcher and **cache
   format** ``text_report.py`` uses, so teacher lookups and deck exports
   share one warmed cache (default
   ``~/.cache/vocabkitchen/dictionary.json``).
3. **Offline fallback** — the bundled Open English WordNet
   (``WordLists/dictionary/wordnet.json``, CC BY 4.0, built by
   ``build_dictionary.py``), so definitions ship even with no network.

:func:`lookup_word` is the one-call entry point (the RubricMaker-facing
contract); :func:`wordnet_fallback` is the slot ``text_report``'s deck
enrichment and ``--pre-enrich`` use, so the CLI's fallback chain is the same
WordNet layer; :func:`read_word_list` imports a class's vocabulary-list
export (CSV/JSON) so ``--pre-enrich`` can prime the cache from the app's own
data without reformatting.
"""

import csv
import json
import os

import text_report as tr  # the Free Dictionary API fetcher + cache format

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WORDNET = os.path.join(_HERE, "WordLists", "dictionary",
                                "wordnet.json")

#: Word keys accepted when reading a vocabulary-list export.
_WORD_KEYS = ("word", "headword", "term", "lemma", "vocabulary")


def default_wordnet_path():
    """The bundled Open English WordNet file
    (``WordLists/dictionary/wordnet.json`` next to this module)."""
    return _DEFAULT_WORDNET


_wordnet_cache = {}


def load_wordnet(path=None):
    """word -> [{\"definition\", \"partOfSpeech\"}] from the bundled WordNet.

    Loaded lazily and cached per path (the file is ~10 MB). Returns an empty
    dict when the bundle is missing or unreadable, so the offline fallback is
    an enhancement, never a hard dependency.
    """
    path = path or default_wordnet_path()
    if path in _wordnet_cache:
        return _wordnet_cache[path]
    data = {}
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        words = doc.get("words") if isinstance(doc, dict) else None
        if isinstance(words, dict):
            data = words
    except (OSError, ValueError):
        data = {}
    _wordnet_cache[path] = data
    return data


def wordnet_fallback(path=None, wordnet=None):
    """A callable for ``text_report``'s ``offline_fallback`` slot.

    Returns ``word -> {definition, phonetic, partOfSpeech, source}`` (or
    None when the bundle doesn't know the word), loading the bundle lazily
    on the first call so a run that never misses the API pays no cost.
    """
    state = {"loaded": False, "data": {}}

    def lookup(word):
        if not state["loaded"]:
            state["data"] = load_wordnet(path) if wordnet is None else wordnet
            state["loaded"] = True
        entries = state["data"].get(word.lower()) or []
        if not entries:
            return None
        e = entries[0]
        return {"definition": e["definition"], "phonetic": None,
                "partOfSpeech": e.get("partOfSpeech"), "source": "wordnet"}

    return lookup


def level_for_word(word, level_index=None, path=None):
    """The CEFR level of *word* from the bundled levels.json index (or None).

    *level_index* is :func:`vocab_profile.load_level_index`'s dict; when
    omitted it's loaded from *path* (default: the bundled WordLists root).
    """
    if level_index is None:
        import vocab_profile as vp
        level_index = vp.load_level_index(
            path or os.path.join(_HERE, "WordLists"))
    return (level_index.get(word.lower()) or {}).get("level")


def lookup_word(word, base_url=None, cache_path=None, level_index=None,
                wordnet=None, wordnet_path=None, timeout=tr._DICT_TIMEOUT):
    """The layered lookup — the ``cambridgeApi.lookupWord`` replacement.

    Returns ``{"word", "level", "definition", "phonetic", "partOfSpeech",
    "source"}``: *level* always from the bundled levels.json index (never the
    API), definition/phonetic/POS from the Free Dictionary API, falling back
    to the bundled Open English WordNet when the API is unreachable or
    misses. With *cache_path* the result is read from / written to **the same
    cache** ``text_report``'s deck exports use (keyed by API URL and word),
    so a cache warmed by one front end serves the other.

    Fail-silent exactly like the contract being replaced: no exception ever
    escapes for a lookup failure — a word nobody knows returns a result with
    ``definition``/``phonetic``/``partOfSpeech`` None and ``source``
    ``\"cache-miss\"`` / ``\"offline\"``, and an unreachable API falls through
    to WordNet before that.
    """
    lower = word.lower()
    level = level_for_word(lower, level_index) \
        if level_index is not None else None
    cache = tr.load_dictionary_cache(cache_path) if cache_path else {}
    url_key = base_url or tr._DICT_API
    bucket = cache.get(url_key) or {}

    if lower in bucket:
        cached = bucket[lower]
        if cached is None:
            return {"word": lower, "level": level, "definition": None,
                    "phonetic": None, "partOfSpeech": None,
                    "source": "cache-miss"}
        return {"word": lower,
                "level": level or cached.get("level"),
                "definition": cached.get("definition"),
                "phonetic": cached.get("phonetic"),
                "partOfSpeech": cached.get("partOfSpeech"),
                "source": cached.get("source") or "api"}

    try:
        result = tr.lookup_dictionary(lower, base_url=base_url, timeout=timeout)
        source = "api"
    except tr._DictNetworkError:
        result = None
        source = "offline"
    definition = (result or {}).get("definition")
    phonetic = (result or {}).get("phonetic")
    pos = (result or {}).get("partOfSpeech")
    if not definition:
        entries = (wordnet if wordnet is not None
                   else load_wordnet(wordnet_path)).get(lower) or []
        if entries:
            definition = entries[0]["definition"]
            pos = pos or entries[0].get("partOfSpeech")
            source = "wordnet"
    learned = {"definition": definition, "phonetic": phonetic,
               "partOfSpeech": pos, "level": level, "source": source}
    if cache_path:
        cache.setdefault(url_key, {})[lower] = learned
        tr.save_dictionary_cache(cache_path, cache)
    return {"word": lower, "level": level, "definition": definition,
            "phonetic": phonetic, "partOfSpeech": pos, "source": source}


def _clean_words(items):
    """Lowercase, de-duplicate, and drop empties from a raw word list."""
    out, seen = [], set()
    for item in items:
        w = str(item).strip().lower()
        if not w or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def _words_from_json(data):
    """Words from the JSON vocabulary-list export shapes a class might have:
    an array of strings, an array of ``{word: ...}`` objects, or an object
    with a ``words``/``vocabulary``/``items``/``entries`` array — plus a flat
    ``word -> anything`` object (e.g. a levels.json-style index)."""
    words = []

    def collect(items):
        for item in items:
            if isinstance(item, str):
                words.append(item)
            elif isinstance(item, dict):
                for key in _WORD_KEYS:
                    if item.get(key):
                        words.append(item[key])
                        break

    if isinstance(data, list):
        collect(data)
    elif isinstance(data, dict):
        for key in ("words", "vocabulary", "items", "entries"):
            value = data.get(key)
            if isinstance(value, list):
                collect(value)
        if not words:
            # A flat word -> anything object (e.g. a levels.json-style index);
            # the container keys above are excluded even when present-but-
            # empty so a "words": [] export doesn't become the word "words".
            keys = [k for k in data
                    if k not in ("words", "vocabulary", "items", "entries")]
            if keys and all(isinstance(k, str) for k in keys):
                words = keys
    return _clean_words(words)


def _words_from_csv(path):
    """Words from a CSV vocabulary-list export.

    Detects a header row (``word``/``headword``/``term``/...) and reads that
    column; a header-less single-column list reads the first column. The
    RubricMaker deck shape (``word, definition, example, phonetic,
    partOfSpeech``) therefore imports straight in.
    """
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    header_idx = None
    if rows:
        header = [c.strip().lower() for c in rows[0]]
        for i, cell in enumerate(header):
            if cell in _WORD_KEYS:
                header_idx = i
                break
    words = []
    for row in rows[1:] if header_idx is not None else rows:
        if not row:
            continue
        cell = row[header_idx if header_idx is not None else 0].strip()
        if cell:
            words.append(cell)
    return _clean_words(words)


def read_word_list(path):
    """Words from a class's vocabulary-list export, without reformatting.

    - ``.csv`` — the ``word`` column (RubricMaker's deck/export shape) or the
      first column of a header-less list;
    - ``.json`` — the export shapes above (:func:`_words_from_json`);
    - anything else — one word per line, the tool's own list format.

    Returns a sorted, de-duplicated, lowercased list (sorted so repeated
    pre-enrich passes are deterministic).
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            words = _words_from_json(json.load(f))
    elif ext == ".csv":
        words = _words_from_csv(path)
    else:
        with open(path, encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip()]
        words = _clean_words(words)
    return sorted(words)
