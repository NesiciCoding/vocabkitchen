#!/usr/bin/env python3
"""VocabKitchen unified text report — vocabulary + grammar, one answer.

A single command that runs both profilers over the same text and prints one
combined difficulty summary, instead of two separate invocations you have to
merge by hand:

  - **Vocabulary** — the CEFR band of the words (typical + 90% coverage),
    exactly as ``vocab_profile.py`` computes it.
  - **Grammar** — the CEFR band of the constructions used (typical + reaches),
    exactly as ``grammar_profile.py`` computes it.
  - **Blended estimated level** — one number: the higher of the vocabulary
    90%-coverage band and the grammar typical band, i.e. the level at which
    both most words and most structures sit comfortably.
  - **--target-level** — pass the class's level (e.g. ``--target-level B1``)
    and the report flags what exceeds it: the words above that level, the
    constructions above it, the coverage figure ("a B1 learner will already
    know ~92% of the recognised running words"), and a one-line verdict
    ("on level" / "reaches B2 — pre-teach 6 words, 2 structures").
  - **Readability** — a classic index (Flesch Reading Ease and Flesch–Kincaid
    grade) reported *alongside* — never instead of — the CEFR bands, for
    colleagues who still ask for a grade level. Disable with ``--no-readability``.

The vocabulary half is dependency-free Python 3; the grammar half needs spaCy
(``pip install spacy && python3 -m spacy download en_core_web_sm``) exactly
like ``grammar_profile.py``. When spaCy is missing the report still runs — the
grammar section is skipped with a note and the verdict is vocabulary-based.
Like ``grammar_profile.py``, a sibling ``.venv`` is auto-detected and used when
the invoking interpreter lacks spaCy.

Usage:
    python3 text_report.py --text "The cat sat on the mat." --target-level B1
    python3 text_report.py --file essay.docx --target-level A2 --format pretty
    echo "If I had known, I would have helped." | python3 text_report.py --target-level B1

Flags:
    --target-level    the class's CEFR level (A1–C2); the report flags what
                      exceeds it: words, structures, coverage, and a verdict
    --format          auto | json | pretty  (default: auto — a colour terminal
                      view when stdout is a TTY, JSON when piped/redirected)
    --text            inline text to analyse
    --file            path to a .txt, .md, .docx, or .pdf file to analyse
    --wordlists       override the vocabulary word-list directory
    --grammar-profile override the CEFR-J grammar-profile directory
    --no-grammar      skip the grammar side even if spaCy is available
    --no-readability  omit the Flesch–Kincaid / Flesch Reading Ease line
    --export          csv | md | flashcards — write the above-target words and
                      structures as a ready-made pre-teaching list for the
                      class: a CSV spreadsheet (type, item, level, count,
                      category, example), a Markdown handout (verdict +
                      coverage figure + a table per category, each row with an
                      example sentence from the text), or a flashcard deck CSV
                      in RubricMaker's import shape (word, definition, example,
                      phonetic, partOfSpeech). Requires --target-level. Decks
                      are enriched by default: definition/phonetic/partOfSpeech
                      are filled from the Free Dictionary API (no key) and the
                      in-text context sentence moves to the example column —
                      see --no-enrich. CEFR levels never come from the API:
                      they come from the bundled word lists.
    --cloze           render the exported examples as fill-the-gap sentences:
                      the target word (or construction span) becomes {{...}} —
                      RubricMaker's native fill-the-gap syntax, so the handout
                      doubles as a worksheet and pastes straight into a
                      fill-the-gap question there. Applies to --export md|csv.
    --suggest         the Phase 3 rewriting aid: for each word above the
                      target, suggest a simpler alternative from the bundled
                      curated list (WordLists/synonyms.csv) — shown in the
                      above-target list (purchase → buy (A1)), carried in
                      JSON as aboveTarget.words[i].suggestion, and added as a
                      'Simpler alternative' column in the --export md handout.
                      Requires --target-level.
    --gap-report      the Phase 3 grammar gap report: with --target-level (and
                      the grammar side on), list the target-level
                      constructions the text does NOT use yet — the
                      'introduce these structures' list for graded-reader
                      authors. Carried in JSON as grammarGap.missing and
                      added as a 'Constructions to introduce' section in the
                      --export md handout. Incompatible with --no-grammar.
    --no-enrich       --export flashcards only: skip the Free Dictionary API
                      (the back of each card stays the in-text context
                      sentence instead of a plain definition)
    --dictionary-url  --export flashcards only: override the dictionary API
                      base URL (used to point at a proxy or a test server)
    --dictionary-cache  --export flashcards only: JSON cache file for dictionary
                      lookups, so repeat exports make no repeat requests
                      (default: ~/.cache/vocabkitchen/dictionary.json;
                      --no-dictionary-cache disables it)
    --pre-enrich      prime the dictionary cache from the input — a class word
                      list (one word per line) or a whole essay — with one
                      polite, rate-limited pass over the Free Dictionary API,
                      then exit (no report, no export). Words already cached
                      (hits and misses) are skipped; --delay SECONDS spaces
                      requests out (default 0.25, 0 for none); --limit N caps
                      new lookups. Later --export flashcards runs then answer
                      from the cache.
    --output          where the --export file goes (default: with --file input,
                      <stem>-preteaching-<LEVEL>.<ext> next to the source;
                      otherwise preteaching-<LEVEL>.<ext> in the cwd; decks
                      get a -deck suffix)
    --watch [SECONDS] the Phase 3 edit → re-check loop: keep re-profiling the
                      --file input whenever it changes on disk (polling every
                      SECONDS, default 1) until Ctrl-C — for tightening a
                      graded reader while the report updates on each save
    --curriculum FILE the Phase 4 curriculum checklist: check the text against
                      a file with sections [vocabulary] (one word per line)
                      and [grammar] (construction names as shown by the
                      grammar profiler, or their ids) and report pass/fail
                      coverage — vocabulary items also carry their CEFR band
                      when recognised. Grammar items are unchecked when the
                      grammar side is off. Carried in JSON as `curriculum` and
                      rendered in pretty mode and the --export md handout.
    --cambridge       the Phase 4 exam mapping: map the report's own CEFR
                      bands (vocabulary typical/reaches, grammar
                      typical/reaches, estimated level) to the matching
                      Cambridge English Qualification — A2 Key, B1
                      Preliminary, B2 First, C1 Advanced, C2 Proficiency.
                      Carried in JSON as `cambridge`, shown in pretty mode,
                      and rendered as a 'Cambridge English mapping' section in
                      the --export md handout.
    --cando           the Phase 4 Can-Do framing: express the text's demands
                      as CEFR global-scale Can-Do descriptors — what a learner
                      at the reached/estimated band can do, the language
                      rubrics and self-assessment forms already use. Carried
                      in JSON as `cando`, shown in pretty mode, and rendered
                      as a 'Can-Do descriptors' section in the --export md
                      handout.
    (stdin)           if neither --text nor --file is given, text is read from stdin

Output: with --format json, a JSON object that is a superset of both profilers'
payloads: ``vocabulary.results`` matches vocab_profile.py's ``results.cefr``
shape and ``grammar`` is grammar_profile.py's full payload, plus the unified
fields (``estimatedLevel``, ``targetLevel``, ``aboveTarget``, ``coverage``,
``verdict``, ``readability``). With --format pretty, a single combined terminal
summary.
"""

import argparse
import difflib
import json
import os
import re
import sys
import time

import vocab_profile as vp
import grammar_profile as gp

_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
_LEVEL_INDEX = {lvl: i for i, lvl in enumerate(_CEFR_ORDER)}


# ---------------------------------------------------------------------------
# venv re-exec — mirrors grammar_profile._maybe_reexec_in_venv for this
# script's own argv, so the unified report "just works" when spaCy lives in a
# sibling .venv even though the invoking python is the system interpreter.
# ---------------------------------------------------------------------------

def _maybe_reexec_in_venv():
    """Re-launch under a spaCy-capable venv if the current interpreter lacks it.

    Skipped when ``--no-grammar`` or ``--pre-enrich`` is on the command line:
    both are vocabulary-only modes, so there's nothing spaCy would add, and
    re-exec would silently drop the invoking interpreter's extras (e.g. pypdf
    for PDFs, which a spaCy-only venv usually doesn't have).
    """
    if "--no-grammar" in sys.argv or "--pre-enrich" in sys.argv:
        return
    import importlib.util
    if importlib.util.find_spec("spacy") is not None:
        return  # this interpreter already has spaCy
    if os.environ.get("_TEXT_REPORT_REEXEC"):
        return  # already re-exec'd once; don't loop
    real_dir = os.path.dirname(os.path.realpath(__file__))
    candidates = [
        os.environ.get("GRAMMAR_PROFILE_PYTHON"),
        os.path.join(real_dir, ".venv", "bin", "python"),
        os.path.join(real_dir, "venv", "bin", "python"),
    ]
    for cand in candidates:
        if not cand or not os.path.exists(cand):
            continue
        py = os.path.abspath(cand)
        if py == os.path.abspath(sys.executable):
            return
        env = dict(os.environ, _TEXT_REPORT_REEXEC="1")
        try:
            os.execve(py, [py, os.path.abspath(__file__)] + sys.argv[1:], env)
        except OSError:
            return  # fall through to the grammar section's install note


# ---------------------------------------------------------------------------
# Readability — classic indices computed with the stdlib alone (approximate,
# reported alongside — never instead of — the CEFR bands).
# ---------------------------------------------------------------------------

_SENT_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")


def count_sentences(text):
    """Approximate sentence count for readability indices (no spaCy needed)."""
    parts = [p for p in _SENT_SPLIT_RE.split(text) if p.strip()]
    return max(len(parts), 1)


def count_syllables(word):
    """Approximate syllable count: vowel-group heuristic with silent -e / -ed / -le.

    A standard written-method approximation, not a dictionary: strips a
    trailing silent -e ("make"), drops the -ed of past tenses unless it follows
    t/d ("walked" vs "wanted"), and keeps the -e of consonant+le ("table").
    """
    w = word.lower()
    if len(w) <= 3:
        return 1
    extra = 0
    if w.endswith("ed") and len(w) > 3:
        w = w[:-2]  # walk(ed), want(ed) — drop the -ed ending
        if w[-1] in "td":  # -ted/-ded keep their own syllable: wanted, needed
            extra = 1
    if w.endswith("e") and not (w.endswith("le") and len(w) > 2
                                 and w[-3] not in "aeiou"):
        w = w[:-1]  # make -> mak; keep the e in table
    if not w:
        return 1
    count = 0
    in_vowel = False
    for ch in w:
        if ch in "aeiouy":
            if not in_vowel:
                count += 1
            in_vowel = True
        else:
            in_vowel = False
    return max(count + extra, 1)


def _flesch_description(fre):
    if fre >= 90:
        return "very easy"
    if fre >= 80:
        return "easy"
    if fre >= 70:
        return "fairly easy"
    if fre >= 60:
        return "plain English"
    if fre >= 50:
        return "fairly difficult"
    if fre >= 30:
        return "difficult"
    return "very difficult"


def compute_readability(text, word_count):
    """Flesch Reading Ease + Flesch–Kincaid grade, or None when wordless.

    Words are counted with the vocab profiler's tokenizer so the readability
    figures line up with ``totalWordCount``.
    """
    if not word_count:
        return None
    sentences = count_sentences(text)
    syllables = sum(count_syllables(t) for t in vp.tokenize(text)
                    if t not in vp.PLACEHOLDERS)
    words_per_sentence = word_count / sentences
    syllables_per_word = syllables / word_count
    fre = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    fk = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59
    return {
        "fleschReadingEase": round(fre, 1),
        "fleschKincaidGrade": round(fk, 1),
        "description": _flesch_description(fre),
    }


# ---------------------------------------------------------------------------
# Target-level flagging: coverage figure, words/structures above the level,
# the one-line verdict, and the blended estimated level.
# ---------------------------------------------------------------------------

def coverage_figure(ordered, target):
    """Share of recognised running words at/below *target* — the teacher number.

    Off-List tokens (names, typos, jargon) are excluded from both sides: they
    aren't teachable vocabulary, so they shouldn't drag the figure down.
    """
    counts = {name: sum(occ for _w, occ in rows) for name, _pct, rows in ordered}
    recognised = sum(counts.get(lvl, 0) for lvl in _CEFR_ORDER)
    known = sum(counts.get(lvl, 0) for lvl in _CEFR_ORDER[:_LEVEL_INDEX[target] + 1])
    if recognised == 0:
        return None
    pct = round(known / recognised * 100)
    return {
        "targetLevel": target,
        "knownPercent": pct,
        "knownWords": known,
        "recognisedWords": recognised,
        "sentence": (f"A {target} learner will already know ~{pct}% of the "
                     "recognised running words."),
    }


def load_synonyms(path=None):
    """The curated simpler-synonym list: word -> ``{"word", "level"}``.

    Reads ``WordLists/synonyms.csv`` (columns ``word,simpler,level``) — the
    Phase 3 rewriting aid. Returns an empty dict when the file is absent, so
    suggestions are an opt-in enhancement, never a hard dependency. The list
    is validated by ``build_wordlists.py --check`` against ``levels.json``.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "WordLists", "synonyms.csv")
    out = {}
    if not os.path.exists(path):
        return out
    import csv
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for row in rows[1:]:
        if len(row) != 3 or not all(cell.strip() for cell in row):
            continue
        word = row[0].strip().lower()
        lvl = row[2].strip().upper()
        if lvl in _LEVEL_INDEX:
            out[word] = {"word": row[1].strip().lower(), "level": lvl}
    return out


def words_above_target(ordered, target):
    """Distinct recognised words at a CEFR level above *target*, ranked by use."""
    out = []
    for name, _pct, rows in ordered:
        if name not in _LEVEL_INDEX or _LEVEL_INDEX[name] <= _LEVEL_INDEX[target]:
            continue
        for word, occ in rows:
            out.append({"word": word, "level": name, "occurrences": occ})
    out.sort(key=lambda d: (-d["occurrences"], d["word"]))
    return out


def structures_above_target(results, target):
    """Distinct constructions at a CEFR level above *target*, ranked by use.

    Each entry carries up to two ``examples`` (``{"span", "sentence"}`` pairs)
    from the grammar profiler, so exports can show the construction in context.
    """
    out = []
    for lvl in _CEFR_ORDER:
        if _LEVEL_INDEX[lvl] <= _LEVEL_INDEX[target]:
            continue
        for entry in results.get(lvl, {}).values():
            out.append({"name": entry["name"], "level": lvl,
                        "count": entry["count"], "category": entry["category"],
                        "examples": entry["examples"][:2]})
    out.sort(key=lambda d: (-d["count"], d["name"]))
    return out


def grammar_gap_report(gresults, cefrj_levels, target):
    """The Phase 3 grammar gap report: target-level constructions the text
    does **not** use yet.

    The full set of constructions at *target* (from the grammar profile's
    registry, resolved exactly like the profiler) minus the ones detected in
    the text — the "introduce these structures" list for graded-reader
    authors, the mirror of the above-target "remove these" list.
    """
    all_at = gp.constructions_at_level(cefrj_levels, target)
    used = {e["name"] for e in (gresults or {}).get(target, {}).values()}
    missing = [c for c in all_at if c["name"] not in used]
    return {
        "targetLevel": target,
        "total": len(all_at),
        "missingCount": len(missing),
        "missing": missing,
    }


_CAMBRIDGE = {
    "A1": None,                     # below the exam ladder
    "A2": "A2 Key (KET)",
    "B1": "B1 Preliminary (PET)",
    "B2": "B2 First (FCE)",
    "C1": "C1 Advanced (CAE)",
    "C2": "C2 Proficiency (CPE)",
}


def cambridge_for(band):
    """The Cambridge English Qualification matching a CEFR band
    (None for A1 — below the exam ladder, and for unknown bands)."""
    return _CAMBRIDGE.get(band)


def cambridge_mapping(payload):
    """The report's own bands, each mapped to its Cambridge qualification.

    Built from the payload so it always matches what the report actually
    shows: vocabulary typical/reaches, grammar typical/reaches (when
    analysed), and the blended estimated level. Grammar stays null when the
    grammar side didn't run.
    """
    v = payload.get("vocabulary") or {}
    g = payload.get("grammar") or {}
    gl = g.get("estimatedLevel") or {}
    est = payload.get("estimatedLevel")
    return {
        "vocabulary": {"typical": cambridge_for(v.get("typical")),
                        "reaches": cambridge_for(v.get("coverage"))},
        "grammar": {"typical": cambridge_for(gl.get("typical")),
                     "reaches": cambridge_for(gl.get("reaches"))},
        "estimated": cambridge_for(est),
    }


# CEFR global-scale Can-Do descriptors (condensed from the common reference
# levels) — what a learner at each band can do, the language rubrics and
# self-assessment forms already use.
_CANDO = {
    "A1": "understand and use familiar everyday expressions and very basic phrases",
    "A2": "understand sentences and frequently used expressions about areas of "
          "immediate relevance",
    "B1": "deal with most situations while travelling; describe experiences, "
          "events, and opinions",
    "B2": "understand the main ideas of complex text on both concrete and "
          "abstract topics",
    "C1": "understand a wide range of demanding, longer texts and recognise "
          "implicit meaning",
    "C2": "understand with ease virtually everything heard or read",
}


def cando_for(band):
    """The CEFR Can-Do descriptor for a band (None for unknown bands)."""
    return _CANDO.get(band)


def _cando_above(band, target_level):
    """The Can-Do descriptors a text at *band* demands above *target_level*.

    One entry per level strictly above the target, up to and including the
    text's own band — everything the class is not expected to do yet but the
    text asks for. Empty when the text demands nothing beyond the target
    (or either band is unknown).
    """
    if band is None or target_level is None:
        return []
    ti = _LEVEL_INDEX.get(target_level)
    bi = _LEVEL_INDEX.get(band)
    if ti is None or bi is None or bi <= ti:
        return []
    return [{"band": lvl, "descriptor": _CANDO[lvl]}
            for lvl in _CEFR_ORDER[ti + 1:bi + 1]]


def cando_mapping(payload, target_level=None):
    """The report's own bands, each with its Can-Do descriptor — what a
    learner at that band can do with the text's demands.

    With *target_level*, each dimension also carries ``aboveTarget``: the
    Can-Do descriptors the text demands **beyond** what the class is
    expected to do yet (every level strictly above the target, up to the
    text's own demand band), and the mapping carries ``targetLevel``.
    """
    v = payload.get("vocabulary") or {}
    g = payload.get("grammar") or {}
    gl = g.get("estimatedLevel") or {}
    est = payload.get("estimatedLevel")
    result = {
        "vocabulary": {"typical": cando_for(v.get("typical")),
                        "reaches": cando_for(v.get("coverage"))},
        "grammar": {"typical": cando_for(gl.get("typical")),
                     "reaches": cando_for(gl.get("reaches"))},
        "estimated": cando_for(est),
    }
    if target_level is not None:
        result["targetLevel"] = target_level
        result["aboveTarget"] = {
            "vocabulary": _cando_above(v.get("coverage"), target_level),
            "grammar": _cando_above(gl.get("reaches"), target_level),
            "estimated": _cando_above(est, target_level),
        }
    return result


class CurriculumError(Exception):
    """A problem with the --curriculum checklist file."""


_CURRICULUM_HEADERS = (("[vocabulary]", "vocabulary"),
                       ("[vocab]", "vocabulary"),
                       ("[grammar]", "grammar"))


def _parse_curriculum(path):
    """Parse the checklist file into sections + non-fatal warnings.

    Section headers are ``[vocabulary]`` (or ``[vocab]``) and ``[grammar]``,
    one per line; lines before any header count as vocabulary; ``#``/``;``
    start comments. Raises ``CurriculumError`` for a missing file or a
    malformed / unknown section header — with a *did you mean* hint for
    typos — so a typo'd checklist is reported **before** any profiling.
    Returns ``(sections, warnings)``; warnings are notes that do not stop
    the run, e.g. an empty required section.
    """
    if not os.path.isfile(path):
        raise CurriculumError(f"curriculum file not found: {path}")
    sections = {"vocabulary": [], "grammar": []}
    current = "vocabulary"
    grammar_lines = []  # (item, lineno) — resolved against the grammar list
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith(("#", ";")):
                continue
            low = line.lower()
            matched = next((section for header, section in _CURRICULUM_HEADERS
                            if low == header), None)
            if matched is not None:
                current = matched
            elif low.startswith("["):
                if low.endswith("]"):
                    close = difflib.get_close_matches(
                        low, [h for h, _s in _CURRICULUM_HEADERS], n=1)
                    hint = f" Did you mean {close[0]}?" if close else ""
                    raise CurriculumError(
                        f"unknown curriculum section on line {lineno}: {line}."
                        + hint)
                raise CurriculumError(
                    f"malformed curriculum section header on line {lineno}: "
                    f"{line!r} — section headers are exactly [vocabulary] or "
                    "[grammar], alone on their line")
            else:
                sections[current].append(line)
                if current == "grammar":
                    grammar_lines.append((line, lineno))
    warnings = [
        f"curriculum section [{name}] is empty — nothing required from it"
        for name in ("vocabulary", "grammar") if not sections[name]]
    # Grammar items resolved against the construction list up front: an
    # unrecognised or ambiguous entry is flagged here — before any profiling
    # — with a *did you mean* hint where one exists. (The report would only
    # show it as unrecognised later, so catching it early saves a run.)
    candidates = sorted(
        {cid for cid, (_n, _c, _f, _g) in gp._CONSTRUCTIONS.items()}
        | {name for _cid, (name, _c, _f, _g) in gp._CONSTRUCTIONS.items()},
        key=str.lower)
    for item, lineno in grammar_lines:
        if _resolve_construction(item) is None:
            close = difflib.get_close_matches(item.strip().lower(),
                                              [c.lower() for c in candidates],
                                              n=1)
            hint = f" Did you mean '{close[0]}'?" if close else ""
            tip = ("" if hint else " Check the name or id against "
                                          "grammar_profile.py --list.")
            warnings.append(
                f"curriculum grammar item on line {lineno}: '{item}' is not "
                f"recognised as a construction.{hint}{tip}")
    return sections, warnings


def load_curriculum(path):
    """Parse a curriculum checklist file into required vocabulary + grammar.

    Sections ``[vocabulary]`` (one word per line) and ``[grammar]``
    (construction names as shown by the grammar profiler, e.g. "second
    conditional", or their ids, e.g. ``cond_second``); lines before any
    section header count as vocabulary; ``#``/``;`` start comments. Returns
    ``{"vocabulary": [...], "grammar": [...]}``; raises
    ``CurriculumError`` for a missing file, a malformed header, or an
    unknown section (typos get a *did you mean* hint).
    """
    sections, _warnings = _parse_curriculum(path)
    return sections


def validate_curriculum(path):
    """Parse the checklist file and return ``(sections, warnings)``.

    The CLI calls this before profiling so a typo'd section header fails
    fast; warnings (e.g. an empty required section) print to stderr without
    stopping the run.
    """
    return _parse_curriculum(path)


def _resolve_construction(query):
    """Map a curriculum grammar entry to ``(id, name, category)``.

    Matches by construction id (``cond_second``), by display name
    (``Second conditional``), or by an unambiguous substring (``past
    perfect``), case-insensitively; None when unknown or ambiguous — the
    item then shows as unrecognised, never silently matched.
    """
    spec = gp._CONSTRUCTIONS.get(query.strip())
    if spec:
        return query.strip(), spec[0], spec[1]
    q = query.strip().lower()
    # An exact display-name match wins even when it is also a substring of
    # another construction's name ("past perfect" vs "past perfect
    # progressive"); otherwise an unambiguous substring match is used.
    exact = [(cid, name, category) for cid, (name, category, _c, _f)
             in gp._CONSTRUCTIONS.items() if name.lower() == q]
    if len(exact) == 1:
        return exact[0]
    hits = [(cid, name, category) for cid, (name, category, _c, _f)
            in gp._CONSTRUCTIONS.items() if q in name.lower()]
    if len(hits) == 1:
        return hits[0]
    return None


def curriculum_report(text, curriculum, ordered=None, gresults=None):
    """Check *text* against the required vocabulary and grammar.

    Vocabulary items are present when the exact word form appears in the
    text (the same whole-word, case-insensitive matching the in-text
    contexts use); each also carries its CEFR band when the profiler
    recognises it. Grammar items are present when the construction was
    detected by the grammar profiler (``gresults``; None/empty → not
    present). ``pass`` is true only when every item is covered — the
    pass/fail coverage report of the roadmap's curriculum checklist.
    """
    word_band = {}
    if ordered:
        for name, _pct, rows in ordered:
            for w, _occ in rows:
                word_band[w] = name
    vocabulary = []
    for w in curriculum["vocabulary"]:
        present = word_contexts(text, [w]).get(w) is not None
        vocabulary.append({"word": w, "present": present,
                           "level": word_band.get(w)})
    used = set()
    if gresults:
        for lvl in gresults.values():
            for entry in lvl.values():
                used.add(entry["name"].lower())
    grammar = []
    for entry in curriculum["grammar"]:
        resolved = _resolve_construction(entry)
        present = resolved is not None and resolved[1].lower() in used
        grammar.append({"name": resolved[1] if resolved else entry,
                        "category": resolved[2] if resolved else None,
                        "present": present})
    covered_v = sum(1 for d in vocabulary if d["present"])
    covered_g = sum(1 for d in grammar if d["present"])
    missing = ([d["word"] for d in vocabulary if not d["present"]]
               + [d["name"] for d in grammar if not d["present"]])
    return {
        "vocabulary": vocabulary,
        "grammar": grammar,
        "vocabularyCovered": f"{covered_v} of {len(vocabulary)}",
        "grammarCovered": f"{covered_g} of {len(grammar)}",
        "pass": covered_v == len(vocabulary) and covered_g == len(grammar),
        "missing": missing,
    }


def word_contexts(text, word_forms):
    """First sentence containing each whole-word form, case-insensitive.

    Matches the profiler's exact token forms (already lowercased), so a word
    that appears at sentence start ('Circumstances ...') is still found.
    Sentences are split with the same approximation used for readability.
    """
    sentences = [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]
    contexts = {}
    for w in word_forms:
        pat = re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
        for sent in sentences:
            if pat.search(sent):
                contexts[w] = sent
                break
    return contexts


def _plural(n, noun):
    return f"{n} {noun}{'' if n == 1 else 's'}"


def build_verdict(words, structures, grammar_available=True):
    """One-line verdict: 'on level' or 'reaches X — pre-teach n words, m structures'.

    Clauses for a zero count are omitted, so a text that only exceeds the
    target in vocabulary reads 'reaches C1 — pre-teach 1 word', not
    'pre-teach 1 word, 0 structures'.
    """
    n_words = len(words)
    n_structs = len(structures) if grammar_available else 0
    if n_words == 0 and n_structs == 0:
        return "on level"
    bands = [d["level"] for d in words] + [d["level"] for d in structures]
    max_band = max(bands, key=lambda lvl: _LEVEL_INDEX[lvl])
    clauses = []
    if n_words:
        clauses.append(_plural(n_words, "word"))
    if n_structs:
        clauses.append(_plural(n_structs, "structure"))
    return f"reaches {max_band} — pre-teach {', '.join(clauses)}"


def blend_level(vocab_coverage, grammar_typical):
    """Blended estimate: the higher of the vocab 90%-coverage band and the
    grammar typical band — the level at which most words AND most structures
    sit comfortably. Returns None when neither side has a level."""
    bands = [lvl for lvl in (vocab_coverage, grammar_typical) if lvl in _LEVEL_INDEX]
    return max(bands, key=lambda lvl: _LEVEL_INDEX[lvl]) if bands else None


# ---------------------------------------------------------------------------
# Analysis driver — run both profilers + readability, build the payload
# ---------------------------------------------------------------------------

def analyze(text, target_level=None, wordlists_dir=None, grammar_dir=None,
            with_grammar=True, with_readability=True, suggest=False,
            gap_report=False, curriculum=None, cambridge=False, cando=False):
    """Run both profilers and readability over *text*; return the report payload.

    With ``suggest=True`` (and a *target_level*), each above-target word that
    has an entry in the bundled synonyms list carries a ``suggestion`` — the
    simpler alternative to rewrite it with. With ``gap_report=True`` (and a
    *target_level*), ``grammarGap`` lists the target-level constructions the
    text does not use yet. With ``curriculum`` (a parsed checklist), the
    payload carries a ``curriculum`` pass/fail coverage report. With
    ``cambridge=True``/``cando=True``, the payload also maps its own bands to
    the matching Cambridge English Qualifications / CEFR Can-Do descriptors
    (the Phase 4 exam-mapping and Can-Do-framing items).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Vocabulary (always runs; dependency-free).
    vocab_base = wordlists_dir or os.path.join(script_dir, "WordLists")
    levels = [(name, vp.load_wordlist(vocab_base, rel))
              for name, rel in vp.PROFILERS["cefr"]]
    ordered, total = vp.profile(text, levels)
    counts, typical, coverage = vp.cefr_stats(ordered, total)

    payload = {
        "totalWordCount": total,
        "vocabulary": {
            "typical": typical,
            "coverage": coverage,
            "offListPercent": (round(counts.get("Off List", 0) / total * 100)
                               if total else 0),
            "results": vp.results_to_json(ordered),
        },
        "grammar": None,
        "grammarError": None,
        "targetLevel": target_level,
        "aboveTarget": None,
        "coverage": None,
        "estimatedLevel": None,
        "verdict": None,
        "grammarGap": None,
        "grammarGapError": None,
        "curriculum": None,
        "curriculumError": None,
        "cambridge": None,
        "cando": None,
        "readability": compute_readability(text, total) if with_readability else None,
    }

    # Grammar (needs spaCy; degrades gracefully when it's missing).
    grammar_available = False
    gresults = None
    gmeta = None
    if with_grammar:
        try:
            gbase = grammar_dir or os.path.join(script_dir, "GrammarProfile")
            nlp = gp.load_nlp()
            cefrj_levels = gp.load_cefrj_levels(gbase)
            if len(text) > nlp.max_length:
                raise ValueError(
                    f"input too long for the parser ({len(text):,} characters; "
                    f"limit {nlp.max_length:,}) — split the text and re-run"
                )
            gresults, gmeta = gp.profile(text, nlp, cefrj_levels)
            payload["grammar"] = gp.results_to_json(gresults, gmeta)
            grammar_available = True
        except gp.EngineError as ex:
            payload["grammarError"] = str(ex).strip()
        except ValueError as ex:
            payload["grammarError"] = str(ex).strip()
    else:
        payload["grammarError"] = "skipped (--no-grammar)"

    if target_level is not None:
        words = words_above_target(ordered, target_level)
        structures = (structures_above_target(gresults, target_level)
                      if grammar_available else [])
        bands = [d["level"] for d in words] + [d["level"] for d in structures]
        if words:
            ctx = word_contexts(text, [d["word"] for d in words])
            for d in words:
                d["context"] = ctx.get(d["word"])
        if suggest:
            syns = load_synonyms(os.path.join(vocab_base, "synonyms.csv"))
            for d in words:
                s = syns.get(d["word"])
                if s:
                    d["suggestion"] = s
        payload["aboveTarget"] = {
            "maxLevel": max(bands, key=lambda lvl: _LEVEL_INDEX[lvl]) if bands else None,
            "words": words,
            "wordCount": len(words),
            "structures": structures,
            "structureCount": len(structures),
        }
        payload["coverage"] = coverage_figure(ordered, target_level)
        payload["verdict"] = build_verdict(words, structures, grammar_available)

    if gap_report:
        if target_level is None:
            payload["grammarGapError"] = "requires --target-level"
        elif not grammar_available:
            payload["grammarGapError"] = (payload["grammarError"]
                                          or "not analysed")
        else:
            payload["grammarGap"] = grammar_gap_report(
                gresults, cefrj_levels, target_level)

    grammar_typical = gmeta["estimatedLevel"]["typical"] if gmeta else None
    payload["estimatedLevel"] = blend_level(coverage, grammar_typical)

    if cambridge:
        payload["cambridge"] = cambridge_mapping(payload)
    if cando:
        payload["cando"] = cando_mapping(payload, target_level)

    if curriculum:
        # Re-run the checklist with the grammar results now that the grammar
        # side has (or hasn't) run; vocabulary presence needs `ordered`.
        payload["curriculum"] = curriculum_report(
            text, curriculum, ordered, gresults)
        if curriculum and not grammar_available:
            payload["curriculum"]["grammarAvailable"] = False
            payload["curriculumError"] = (
                payload["grammarError"] or "grammar not analysed")
        else:
            payload["curriculum"]["grammarAvailable"] = True
    return payload


# ---------------------------------------------------------------------------
# Pretty terminal rendering (reuses the profilers' CEFR palette)
# ---------------------------------------------------------------------------

_DIM_RGB = (136, 136, 136)


def _lvl(lvl, colour):
    return vp.paint(vp.LEVEL_RGB.get(lvl, _DIM_RGB), lvl, colour)


def render_pretty(payload, source_label, stream=None):
    """Render the combined summary as a colour-coded terminal view."""
    stream = stream or sys.stdout
    colour = vp.use_colour(stream)

    def dim(s):
        return vp.paint(_DIM_RGB, s, colour)

    def bold(s):
        return vp.bold(s, colour)

    out = []
    out.append(bold("Text Report"))
    if source_label:
        out.append(dim(f"Source: {source_label}"))
    out.append("")
    out.append(f"{bold('Words:')} {payload['totalWordCount']}")

    v = payload["vocabulary"]
    out.append("")
    out.append(bold("Vocabulary"))
    out.append(f"  {bold('Typical:')} {_lvl(v['typical'], colour)}"
               f"   {bold('90% coverage:')} {_lvl(v['coverage'], colour)}")
    if v["offListPercent"]:
        out.append(dim(f"  {v['offListPercent']}% of words unrecognised (Off List — "
                       "names, typos, jargon; excluded from the coverage figure)"))

    out.append("")
    out.append(bold("Grammar"))
    g = payload["grammar"]
    if g is None:
        note = (payload.get("grammarError") or "not analysed").splitlines()[0]
        out.append(dim(f"  not analysed — {note}"))
    else:
        gl = g["estimatedLevel"]
        n = g['constructionCount']
        out.append(f"  {bold('Typical:')} {_lvl(gl['typical'], colour)}"
                   f"   {bold('Reaches:')} {_lvl(gl['reaches'], colour)}"
                   f"   {dim('(' + str(n) + ' construction' + ('' if n == 1 else 's') + ')')}")

    est = payload["estimatedLevel"]
    out.append("")
    if est is not None:
        out.append(f"{bold('Estimated level:')} {_lvl(est, colour)}"
                   + dim("  (blend: vocabulary coverage + grammar centre)"))
    else:
        out.append(f"{bold('Estimated level:')} {dim('—')}")

    cm = payload.get("cambridge")
    if cm is not None:
        def _exam(d):
            return d or "—"
        out.append("")
        out.append(bold("Cambridge English"))
        out.append(f"  vocabulary typical {_lvl(v['typical'], colour)} → "
                   f"{_exam(cm['vocabulary']['typical'])}"
                   f"  ·  reaches {_lvl(v['coverage'], colour)} → "
                   f"{_exam(cm['vocabulary']['reaches'])}")
        if cm["grammar"]["typical"] or cm["grammar"]["reaches"]:
            out.append(f"  grammar typical → {_exam(cm['grammar']['typical'])}"
                       f"  ·  reaches → {_exam(cm['grammar']['reaches'])}")
        if est is not None:
            out.append(f"  estimated {_lvl(est, colour)} → {_exam(cm['estimated'])}")
        out.append(dim("  (the exam a candidate at each reported band is working toward)"))

    cd = payload.get("cando")
    if cd is not None:
        def _desc(d):
            return ('"' + d + '"') if d else "—"
        out.append("")
        out.append(bold("Can-Do (CEFR global scale)"))
        if v.get("coverage"):
            out.append(f"  reaches {_lvl(v['coverage'], colour)}: "
                       f"{_desc(cd['vocabulary']['reaches'])}")
        if est is not None and est != v.get("coverage"):
            out.append(f"  estimated {_lvl(est, colour)}: "
                       f"{_desc(cd['estimated'])}")
        out.append(dim("  (what a learner at the text's demand level can do — "
                       "the language rubrics and self-assessment forms use)"))
        above = cd.get("aboveTarget")
        tgt = cd.get("targetLevel")
        if above and tgt:
            _gl = (g or {}).get("estimatedLevel") or {}
            for key, label, band in (
                    ("vocabulary", "Vocabulary", v.get("coverage")),
                    ("grammar", "Grammar", _gl.get("reaches")),
                    ("estimated", "Estimated", est)):
                entries = above.get(key) or []
                if not entries:
                    continue
                out.append("")
                out.append(bold(f"{label} — above the {tgt} target"))
                for e in entries:
                    out.append(f"  {_lvl(e['band'], colour)}: "
                               f"\"{e['descriptor']}\"")
            art = "an " if tgt.startswith("A") else "a "
            out.append(dim(f"  (demands beyond what {art + tgt} class is "
                           "expected to do yet — pre-teach or rewrite)"))

    target = payload["targetLevel"]
    if target is not None:
        out.append("")
        out.append(bold(f"Target: {target}"))
        cov = payload["coverage"]
        if cov:
            out.append("  " + cov["sentence"])
        above = payload["aboveTarget"] or {}
        words = above.get("words") or []
        structures = above.get("structures") or []
        if words:
            shown = words[:12]
            parts = []
            for d in shown:
                occ = f" ×{d['occurrences']}" if d['occurrences'] > 1 else ""
                s = d.get("suggestion")
                if s:
                    parts.append(f"{d['word']} ({d['level']}){occ} → "
                                 f"{s['word']} ({s['level']})")
                else:
                    parts.append(f"{d['word']} ({d['level']}){occ}")
            if len(words) > 12:
                parts.append(f"+{len(words) - 12} more")
            out.append(f"  {bold(f'Above {target} — words:')} {', '.join(parts)}")
            if any(d.get("suggestion") for d in words):
                out.append(dim("  → suggests a simpler alternative (rewrite aid)"))
        if structures:
            shown = structures[:12]
            parts = [f"{d['name']} ({d['level']})"
                     + (f" ×{d['count']}" if d['count'] > 1 else "")
                     for d in shown]
            if len(structures) > 12:
                parts.append(f"+{len(structures) - 12} more")
            out.append(f"  {bold(f'Above {target} — structures:')} {', '.join(parts)}")
        verdict = payload.get("verdict")
        if verdict:
            out.append("")
            out.append(f"{bold('Verdict:')} {bold(verdict)}")
        gap = payload.get("grammarGap")
        if gap is not None:
            missing = gap.get("missing") or []
            out.append("")
            out.append(bold(f"Gap report — {target} constructions not used "
                            f"({gap['missingCount']} of {gap['total']})"))
            if not missing:
                out.append(dim("  every target-level construction is present"))
            else:
                for d in missing:
                    out.append(f"  • {d['name']} — {d['category']}")
            out.append(dim("  (the structures a graded-reader author should "
                           "introduce; grammar gap report)"))
        elif payload.get("grammarGapError"):
            out.append("")
            out.append(bold("Gap report"))
            out.append(dim("  unavailable — "
                           + payload["grammarGapError"].splitlines()[0]))

    curr = payload.get("curriculum")
    if curr is not None:
        out.append("")
        ok = curr["pass"]
        mark = "✓" if ok else "✗"
        out.append(bold(f"Curriculum checklist — "
                        f"{curr['vocabularyCovered']} vocabulary, "
                        f"{curr['grammarCovered']} grammar {mark}"))
        for d in curr["vocabulary"]:
            state = "✓" if d["present"] else "✗"
            lvl = f" ({d['level']})" if d.get("level") else ""
            out.append(f"  {state} {d['word']}{lvl}")
        for d in curr["grammar"]:
            state = "✓" if d["present"] else "✗"
            out.append(f"  {state} {d['name']}")
        if not ok:
            out.append(dim("  missing: " + ", ".join(curr["missing"])))
        if curr.get("grammarAvailable") is False:
            out.append(dim("  (grammar not analysed — grammar items unchecked)"))

    read = payload["readability"]
    if read:
        out.append("")
        out.append(bold("Readability"))
        out.append(f"  Flesch–Kincaid grade {read['fleschKincaidGrade']} · "
                   f"Flesch Reading Ease {read['fleschReadingEase']} — {read['description']}")
        out.append(dim("  (classic indices, reported alongside — never instead of — "
                       "the CEFR bands)"))

    stream.write("\n".join(out) + "\n")


# ---------------------------------------------------------------------------
# Dictionary enrichment — Free Dictionary API (dictionaryapi.dev), no key.
#
# Fills the flashcard deck's definition / phonetic / part-of-speech columns.
# CEFR levels never come from here: they come from the bundled word lists
# (WordLists/CEFR/levels.json, built by build_wordlists.py from the
# OLP-EN-CEFRJ profiles), so no dictionary API is needed for levels.
# ---------------------------------------------------------------------------

_DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en"
_DICT_TIMEOUT = 6


class _DictNetworkError(Exception):
    """Network-level failure (offline, DNS, timeout, unparseable body).

    Raised so the deck export can stop enriching early instead of hammering
    an unreachable host once per word.
    """


def parse_dictionary_entry(data):
    """Extract (definition, phonetic, partOfSpeech) from a Free Dictionary API entry.

    *data* is the JSON payload (an array of entries). Returns None when it is
    not a usable entry; otherwise a dict with the first plain definition, the
    first phonetic (top-level ``phonetic`` or the first ``phonetics[].text``),
    and the first part of speech. Fields the API didn't return stay None.
    """
    if not isinstance(data, list) or not data:
        return None
    entry = data[0] if isinstance(data[0], dict) else None
    if not entry:
        return None
    phonetic = entry.get("phonetic") or None
    for ph in entry.get("phonetics") or []:
        if isinstance(ph, dict) and ph.get("text") and not phonetic:
            phonetic = ph["text"]
    meanings = entry.get("meanings") or []
    pos = None
    definition = None
    for m in meanings:
        if not isinstance(m, dict):
            continue
        if pos is None:
            pos = m.get("partOfSpeech") or None
        for d in m.get("definitions") or []:
            if isinstance(d, dict) and d.get("definition"):
                definition = d["definition"]
                break
        if definition:
            break
    return {"definition": definition, "phonetic": phonetic, "partOfSpeech": pos}


def lookup_dictionary(word, base_url=None, timeout=_DICT_TIMEOUT):
    """Look *word* up in the Free Dictionary API (stdlib only).

    Returns :func:`parse_dictionary_entry`'s dict on success, None when the
    API definitively doesn't know the word (HTTP 404), and raises
    :class:`_DictNetworkError` for network-level failures — offline, DNS,
    timeout, non-JSON body, rate limits (HTTP 429) and server errors (5xx) —
    so callers can bail out of a doomed batch instead of caching transient
    failures as "word not found".
    """
    import urllib.error
    import urllib.parse
    import urllib.request
    url = f"{(base_url or _DICT_API).rstrip('/')}/{urllib.parse.quote(word.lower(), safe='')}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "vocabkitchen-text-report/1.0 (CEFR text report; deck enrichment)",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            return None  # word not found — a definitive miss, safe to cache
        raise _DictNetworkError(f"HTTP {ex.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as ex:
        raise _DictNetworkError(str(ex))
    return parse_dictionary_entry(payload)


# ---------------------------------------------------------------------------
# Lookup cache — a small JSON file keyed by (base URL, word), so repeat deck
# exports are fast and polite to the dictionary API. Successful lookups and
# definitive misses (HTTP 404) are stored; network errors are never cached.
# ---------------------------------------------------------------------------

_CACHE_VERSION = 1


def default_dictionary_cache_path():
    """User-level cache file: ``~/.cache/vocabkitchen/dictionary.json``
    (``$XDG_CACHE_HOME``-aware on Linux)."""
    base = os.environ.get("XDG_CACHE_HOME") \
        or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "vocabkitchen", "dictionary.json")


def load_dictionary_cache(path):
    """Read the cache file into ``{url: {word: entry-or-None}}``.

    A ``None`` entry means the API definitively doesn't know the word (a cached
    miss). Returns an empty dict when the file is absent, unreadable, or
    malformed — including a version that doesn't match the writer's
    :data:`_CACHE_VERSION`, which means the on-disk shape can't be trusted. The
    cache is an optimisation, never a hard dependency.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
            return {}
        entries = data.get("entries")
        return entries if isinstance(entries, dict) else {}
    except (OSError, ValueError):
        return {}


def save_dictionary_cache(path, cache):
    """Atomically write the cache file (temp + rename). Never raises."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": _CACHE_VERSION, "entries": cache},
                      f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Pre-teaching export — the above-target words and structures as a ready-made
# handout (Markdown), spreadsheet (CSV), or flashcard deck (CSV in RubricMaker's
# import shape) for the class.
# ---------------------------------------------------------------------------

def blank_gap(sentence, target):
    """Replace the first whole-word occurrence of *target* with ``{{target}}``.

    ``{{...}}`` is RubricMaker's native fill-the-gap syntax (pipe-separated
    alternatives, case-insensitive auto-scoring), so a cloze sentence pasted
    into a fill-the-gap question becomes an input blank automatically.
    Returns the sentence unchanged when the target isn't found.
    """
    if not sentence or not target:
        return sentence or ""
    # The replacement is a function so backslashes or regex group references in
    # *target* are inserted literally instead of being interpreted by re.
    return re.sub(rf"(?i)\b{re.escape(target)}\b",
                  lambda _m: "{{" + target + "}}", sentence, count=1)


def _example_sentence(d):
    """First example sentence for an above-target structure entry."""
    for e in d.get("examples") or []:
        ex = e.get("sentence") or e.get("span") or ""
        if ex:
            return ex
    return ""


def export_csv(payload, cloze=False):
    """Render the above-target items as a CSV spreadsheet (one row per item).

    Columns: type (word|structure), item, level, count, category (structures
    only), example (a sentence from the text). Words carry their first
    in-text context; structures carry the grammar profiler's example. With
    ``cloze=True`` the example blanks the target as ``{{item}}`` (RubricMaker
    fill-the-gap syntax).
    """
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["type", "item", "level", "count", "category", "example"])
    above = payload.get("aboveTarget") or {}
    for d in above.get("words") or []:
        ex = (d.get("context") or "").replace("\n", " ")
        if cloze:
            ex = blank_gap(ex, d["word"])
        w.writerow(["word", d["word"], d["level"], d["occurrences"], "", ex])
    for d in above.get("structures") or []:
        ex = _example_sentence(d).replace("\n", " ")
        if cloze:
            for e in d.get("examples") or []:
                if e.get("span"):
                    ex = blank_gap(ex, e["span"])
                    break
        w.writerow(["structure", d["name"], d["level"], d["count"],
                    d.get("category", ""), ex])
    return buf.getvalue()


def export_markdown(payload, cloze=False):
    """Render the above-target items as a ready-made Markdown handout.

    Verdict and coverage figure on top, then a table of words and a table of
    structures, each with an example sentence straight from the text. With
    ``cloze=True`` every example blanks its target as ``{{item}}`` so the
    handout doubles as a worksheet: RubricMaker reads ``{{...}}`` as a
    fill-the-gap input, and a printed copy shows the item to be filled in.
    """
    target = payload.get("targetLevel")
    title = f"Pre-teaching list — Target {target}" if target else "Pre-teaching list"
    lines = [f"# {title}", ""]
    verdict = payload.get("verdict")
    if verdict:
        lines.append(f"**Verdict:** {verdict}")
        lines.append("")
    cov = payload.get("coverage")
    if cov:
        lines.append(cov["sentence"])
        lines.append("")
    above = payload.get("aboveTarget") or {}
    words = above.get("words") or []
    structures = above.get("structures") or []
    if not words and not structures:
        tgt = f" for {target}" if target else ""
        lines.append(f"No words or structures above the target{tgt} — "
                     "nothing to pre-teach.")
    if words:
        lines.append(f"## Words above {target} ({len(words)})" if target
                     else f"## Words above target ({len(words)})")
        lines.append("")
        has_sugg = any(d.get("suggestion") for d in words)
        if has_sugg:
            lines.append("| Word | Level | Occurrences | Simpler alternative | Example |")
            lines.append("|---|---|---|---|---|")
        else:
            lines.append("| Word | Level | Occurrences | Example |")
            lines.append("|---|---|---|---|")
        for d in words:
            ex = (d.get("context") or "").replace("\n", " ")
            if cloze:
                ex = blank_gap(ex, d["word"])
            ex = ex.replace("|", "\\|")
            if has_sugg:
                s = d.get("suggestion")
                cell = f"{s['word']} ({s['level']})" if s else ""
                lines.append(f"| {d['word']} | {d['level']} | {d['occurrences']} "
                             f"| {cell} | {ex} |")
            else:
                lines.append(f"| {d['word']} | {d['level']} | {d['occurrences']} | {ex} |")
        lines.append("")
    if structures:
        lines.append(f"## Structures above {target} ({len(structures)})" if target
                     else f"## Structures above target ({len(structures)})")
        lines.append("")
        lines.append("| Structure | Level | Category | Example |")
        lines.append("|---|---|---|---|")
        for d in structures:
            ex = _example_sentence(d)
            if cloze:
                for e in d.get("examples") or []:
                    if e.get("span"):
                        ex = blank_gap(ex, e["span"])
                        break
            ex = ex.replace("\n", " ").replace("|", "\\|")
            lines.append(f"| {d['name']} | {d['level']} | {d.get('category', '')}"
                         f" | {ex} |")
        lines.append("")
    gap = payload.get("grammarGap")
    if gap is not None and (gap.get("missing") or []):
        tgt = gap.get("targetLevel") or target or "target"
        lines.append(f"## Constructions to introduce at {tgt} "
                     f"({gap['missingCount']} of {gap['total']} not used)")
        lines.append("")
        for d in gap["missing"]:
            lines.append(f"- **{d['name']}** ({d['category']})")
        lines.append("")
    curr = payload.get("curriculum")
    if curr is not None:
        mark = "✅ covered" if curr["pass"] else "❌ missing items"
        lines.append(f"## Curriculum checklist — {mark}")
        lines.append("")
        lines.append(f"Vocabulary {curr['vocabularyCovered']} · "
                     f"grammar {curr['grammarCovered']} covered.")
        lines.append("")
        lines.append("| Item | Kind | Status | Level |")
        lines.append("|---|---|---|---|")
        for d in curr["vocabulary"]:
            lines.append(f"| {d['word']} | vocabulary | "
                         f"{'present' if d['present'] else 'missing'} "
                         f"| {d.get('level') or '—'} |")
        for d in curr["grammar"]:
            lines.append(f"| {d['name']} | grammar | "
                         f"{'used' if d['present'] else 'not used'} | — |")
        lines.append("")
        if curr.get("grammarAvailable") is False:
            lines.append("_Grammar items unchecked — the grammar side was not "
                         "available._")
            lines.append("")
    cm = payload.get("cambridge")
    if cm is not None:
        lines.append("## Cambridge English mapping")
        lines.append("")
        lines.append("| Reported band | Cambridge English |")
        lines.append("|---|---|")
        v = payload.get("vocabulary") or {}
        g = payload.get("grammar") or {}
        gl = g.get("estimatedLevel") or {}
        rows = [
            (f"Vocabulary typical ({v.get('typical')})", cm["vocabulary"]["typical"]),
            (f"Vocabulary reaches ({v.get('coverage')})", cm["vocabulary"]["reaches"]),
        ]
        if cm["grammar"]["typical"] or cm["grammar"]["reaches"]:
            rows.append((f"Grammar typical ({gl.get('typical')})",
                         cm["grammar"]["typical"]))
            rows.append((f"Grammar reaches ({gl.get('reaches')})",
                         cm["grammar"]["reaches"]))
        est = payload.get("estimatedLevel")
        if est:
            rows.append((f"Estimated level ({est})", cm["estimated"]))
        for label, exam in rows:
            lines.append(f"| {label} | {exam or '—'} |")
        lines.append("")
    cd = payload.get("cando")
    if cd is not None:
        lines.append("## Can-Do descriptors")
        lines.append("")
        lines.append("| Demand level | Can-Do descriptor (CEFR global scale) |")
        lines.append("|---|---|")
        v = payload.get("vocabulary") or {}
        g = payload.get("grammar") or {}
        gl = g.get("estimatedLevel") or {}
        rows = [
            (f"Vocabulary reaches ({v.get('coverage')})",
             cd["vocabulary"]["reaches"]),
        ]
        if cd["grammar"]["reaches"]:
            rows.append((f"Grammar reaches ({gl.get('reaches')})",
                         cd["grammar"]["reaches"]))
        est = payload.get("estimatedLevel")
        if est:
            rows.append((f"Estimated level ({est})", cd["estimated"]))
        for label, desc in rows:
            lines.append(f"| {label} | {desc or '—'} |")
        lines.append("")
        above = cd.get("aboveTarget")
        tgt = cd.get("targetLevel")
        if above and tgt and any(above.get(k) for k in ("vocabulary",
                                                        "grammar",
                                                        "estimated")):
            lines.append(f"### Above the {tgt} target")
            lines.append("")
            lines.append("| Demand | Level | Can-Do descriptor |")
            lines.append("|---|---|---|")
            for key, label in (("vocabulary", "Vocabulary"),
                               ("grammar", "Grammar"),
                               ("estimated", "Estimated")):
                for e in above.get(key) or []:
                    lines.append(f"| {label} | {e['band']} | "
                                 f"{e['descriptor']} |")
            lines.append("")
            art = "an " if tgt.startswith("A") else "a "
            lines.append("_Demands beyond what " + art + tgt + " class is "
                         "expected to do yet — pre-teach or rewrite._")
            lines.append("")
    read = payload.get("readability")
    if read:
        lines.append(f"Readability: Flesch–Kincaid grade "
                     f"{read['fleschKincaidGrade']} · Flesch Reading Ease "
                     f"{read['fleschReadingEase']}.")
        lines.append("")
    lines.append("_Generated by text_report.py · VocabKitchen._")
    if cloze:
        lines.append("")
        lines.append("_Worksheet mode — gaps use RubricMaker's fill-the-gap "
                     "syntax: paste a sentence into a fill-the-gap question and "
                     "{{...}} becomes an input blank (auto-graded "
                     "case-insensitively). For paper, replace {{...}} with a "
                     "blank; the word column is the answer key._")
    return "\n".join(lines) + "\n"


def cached_definitions(cache_path, base_url=None):
    """word -> definition from the dictionary cache, no network.

    Lets cache-adjacent exports (the class profile's per-reading interleave
    handouts) use real definitions when a ``--pre-enrich`` pass has primed
    the cache, falling back to in-text sentences offline. An unreadable or
    missing cache yields an empty dict, never an error.
    """
    try:
        cache = load_dictionary_cache(cache_path)
    except Exception:
        return {}
    bucket = cache.get(base_url or _DICT_API) or {}
    return {w: e["definition"] for w, e in bucket.items()
            if e and e.get("definition")}


def _lookup_with_cache(word, url_key, cache, fetcher, offline):
    """One cache-aware lookup, shared by deck export and pre-enrichment.

    Returns ``(result, source)`` where *source* is ``"cache"`` (answered from
    *cache* without a request), ``"network"`` (fetched just now; the learned
    entry — definition or definitive miss — is stored into *cache*), or
    ``"offline"`` (network failure; nothing cached). When *offline* is already
    True, only cached answers are returned.
    """
    lower = word.lower()
    bucket = cache.get(url_key)
    if bucket is not None and lower in bucket:
        return bucket[lower], "cache"
    if offline:
        return None, "offline"
    try:
        result = fetcher(word)
    except _DictNetworkError:
        return None, "offline"
    cache.setdefault(url_key, {})[lower] = (
        result if result and result.get("definition") else None)
    return result, "network"


def pre_enrich_words(words, base_url=None, lookup=None, cache_path=None,
                     delay=0.25, limit=None, on_progress=None):
    """Prime the dictionary cache for *words* in one polite, rate-limited pass.

    Each word is looked up against the Free Dictionary API (skipping words
    already in the cache, hits and misses alike) and the result is stored, so
    later ``--export flashcards`` runs answer from the cache. *delay* seconds
    are slept between requests (politeness to the hobby-host API); *limit*
    caps the number of **new** lookups (None = no cap); *on_progress* is
    called with the stats dict after every 25 new lookups so a caller can
    print progress.

    Returns ``{"requested": int, "skipped": int, "looked_up": int,
    "found": int, "missed": int, "offline": bool}`` — ``requested`` is the
    number of distinct words passed in, ``skipped`` were already cached.
    """
    cache = load_dictionary_cache(cache_path) if cache_path else {}
    url_key = base_url or _DICT_API
    fetcher = lookup or (lambda wd: lookup_dictionary(wd, base_url))
    # requested = the full distinct input count, regardless of --limit.
    stats = {"requested": len(words), "skipped": 0, "looked_up": 0,
             "found": 0, "missed": 0, "offline": False}
    offline = False
    bucket = cache.setdefault(url_key, {})  # live view; new entries are visible
    for word in words:
        if limit is not None and stats["looked_up"] >= limit:
            break
        lower = word.lower()
        if lower in bucket:
            stats["skipped"] += 1
            continue
        result, source = _lookup_with_cache(lower, url_key, cache, fetcher, offline)
        if source == "offline":
            stats["offline"] = True
            offline = True
            continue
        if source == "network":
            stats["looked_up"] += 1
            if result is not None and result.get("definition"):
                stats["found"] += 1
            else:
                stats["missed"] += 1
            if delay:
                time.sleep(delay)
            if on_progress and stats["looked_up"] % 25 == 0:
                on_progress(dict(stats))
    if cache_path and stats["looked_up"]:
        save_dictionary_cache(cache_path, cache)
    return stats


def export_flashcards(payload, enrich=True, base_url=None, level_index=None,
                      lookup=None, cache_path=None):
    """The above-target words as a flashcard deck in RubricMaker's import shape.

    Exactly the columns RubricMaker's deck importer reads
    (``word, definition, example, phonetic, partOfSpeech``); the header row is
    auto-skipped there and the word is the card front. With ``enrich=True``
    (the default) the ``definition`` column becomes the Free Dictionary API's
    plain definition, the in-text context sentence moves to ``example``, and
    ``phonetic``/``partOfSpeech`` are filled from the API (partOfSpeech falls
    back to the bundled OLP-EN-CEFRJ index's POS when the API misses). When
    the API is offline or doesn't know a word, the back falls back to the
    in-text context sentence, so a deck always ships usable cards. Structures
    stay in the Markdown/CSV exports; a deck is a vocabulary artefact.

    With *cache_path*, lookups are persisted between runs: a JSON file keyed
    by (base URL, word) that stores successful results and definitive misses,
    so repeat exports make no requests for words the API already answered
    (see :func:`default_dictionary_cache_path`). Network errors are never
    cached.

    *lookup* overrides :func:`lookup_dictionary` for tests; *level_index* is
    the dict from :func:`vocab_profile.load_level_index`.

    Returns ``(csv_string, stats)`` with ``stats = {"enriched": int,
    "missed": int, "offline": bool, "cached": int}`` (``cached`` counts
    words answered from the cache without a request).
    """
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["word", "definition", "example", "phonetic", "partOfSpeech"])
    above = payload.get("aboveTarget") or {}
    words = above.get("words") or []
    stats = {"enriched": 0, "missed": 0, "offline": False, "cached": 0}
    cache = load_dictionary_cache(cache_path) if cache_path else {}
    cache_dirty = False
    url_key = base_url or _DICT_API
    fetcher = lookup or (lambda wd: lookup_dictionary(wd, base_url))
    for d in words:
        word = d["word"]
        context = (d.get("context") or "").replace("\n", " ")
        back, example, phonetic, pos = context, context, "", ""
        if enrich:
            result, source = _lookup_with_cache(
                word, url_key, cache, fetcher, stats["offline"])
            if source == "offline":
                stats["offline"] = True
            elif source == "cache":
                stats["cached"] += 1
            else:
                cache_dirty = True
            if result is not None and result.get("definition"):
                back = result["definition"]
                phonetic = result.get("phonetic") or ""
                pos = result.get("partOfSpeech") or ""
                stats["enriched"] += 1
            elif not stats["offline"]:
                # The API (or cache) definitively doesn't know this word.
                stats["missed"] += 1
        if not pos and level_index:
            entry = level_index.get(word.lower()) or {}
            pos = entry.get("pos") or ""
        if not back:
            # No context sentence and no definition — keep the card findable
            # rather than silently dropping the row.
            back = word
        w.writerow([word, back, example, phonetic, pos])
    if cache_path and cache_dirty:
        save_dictionary_cache(cache_path, cache)
    return buf.getvalue(), stats


def _cando_cards(payload):
    """The single text's Can-Do demands as reference cards.

    One card per demand (dimension × band) — the ``## Can-Do descriptors``
    table — plus one per level in the ``aboveTarget`` diff, so the deck
    doubles as a Can-Do reference: front ``B2 — vocabulary demand``, back
    the descriptor plus whether it's above the target. Deduplicated by
    (dimension, band), keeping the demand card over its diff duplicate.
    """
    cd = payload.get("cando")
    if not cd:
        return []
    target = payload.get("targetLevel")
    v = payload.get("vocabulary") or {}
    g = payload.get("grammar") or {}
    gl = g.get("estimatedLevel") or {}
    est = payload.get("estimatedLevel")

    def _above(band):
        return (target is not None and band in _LEVEL_INDEX
                and target in _LEVEL_INDEX
                and _LEVEL_INDEX[band] > _LEVEL_INDEX[target])

    demands = []
    if v.get("coverage") and cd["vocabulary"]["reaches"]:
        demands.append(("Vocabulary", v["coverage"], cd["vocabulary"]["reaches"]))
    if cd["grammar"]["reaches"] and gl.get("reaches"):
        demands.append(("Grammar", gl["reaches"], cd["grammar"]["reaches"]))
    if est and cd["estimated"]:
        demands.append(("Estimated", est, cd["estimated"]))

    cards = []
    seen = set()
    for dim, band, desc in demands:
        if (dim, band) in seen:
            continue
        seen.add((dim, band))
        note = (f" · above the {target} target — pre-teach or rewrite"
                if _above(band)
                else (f" · at the {target} target" if target else ""))
        cards.append({"word": f"{band} — {dim.lower()} demand",
                      "definition": desc,
                      "example": f"{dim} reaches {band}{note}"})
    for key, dim in (("vocabulary", "Vocabulary"),
                     ("grammar", "Grammar"),
                     ("estimated", "Estimated")):
        for e in (cd.get("aboveTarget") or {}).get(key) or []:
            if (dim, e["band"]) in seen:
                continue
            seen.add((dim, e["band"]))
            cards.append({"word": f"{e['band']} — {dim.lower()} demand",
                          "definition": e["descriptor"],
                          "example": f"above the {target} target — "
                                     "pre-teach or rewrite"})
    return cards


def cando_deck_csv(cards):
    """Render Can-Do reference *cards* as a RubricMaker deck (same columns
    as :func:`export_flashcards`: word, definition, example, phonetic,
    partOfSpeech) so decks double as Can-Do reference cards; None when
    there are no cards."""
    if not cards:
        return None
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["word", "definition", "example", "phonetic", "partOfSpeech"])
    for c in cards:
        w.writerow([c["word"], c["definition"], c["example"], "", "cando"])
    return buf.getvalue()


def export_cando_deck(payload):
    """The text's Can-Do demands as a companion RubricMaker deck (CSV
    string, or None when ``--cando`` wasn't requested): front = the demand
    level (``B2 — vocabulary demand``), back = the CEFR descriptor plus
    whether it's above the target — the ``## Can-Do descriptors`` table and
    the ``aboveTarget`` diff as flashcard reference cards."""
    return cando_deck_csv(_cando_cards(payload))


def cando_deck_path(word_deck_path):
    """The companion Can-Do deck next to a word deck:
    ``essay-preteaching-B1-deck.csv`` → ``essay-preteaching-B1-cando-deck.csv``
    (also handles an explicit ``--output`` path without the ``-deck``
    suffix, e.g. ``out.csv`` → ``out-cando-deck.csv``)."""
    stem, ext = os.path.splitext(word_deck_path)
    if stem.endswith("-deck"):
        stem = stem[:-len("-deck")]
    return stem + "-cando-deck" + ext


def export_path(source_file, output_path, target, fmt):
    """Where the pre-teaching list goes: --output, else a sensible default.

    With --file input the default sits next to the source
    (``essay-preteaching-B1.md`` / ``...-B1.csv`` / ``...-B1-deck.csv``); with
    --text/stdin it's ``preteaching-B1.<ext>`` in the current directory.
    """
    ext = "csv" if fmt in ("csv", "flashcards") else "md"
    deck = "-deck" if fmt == "flashcards" else ""
    if output_path:
        return output_path
    if source_file:
        d = os.path.dirname(os.path.abspath(source_file))
        stem = os.path.splitext(os.path.basename(source_file))[0]
        return os.path.join(d, f"{stem}-preteaching-{target}{deck}.{ext}")
    return f"preteaching-{target}{deck}.{ext}"


def resolve_format(explicit, is_tty):
    """Resolve --format exactly like the two profilers (auto by TTY/pipe)."""
    if explicit in (None, "", "auto"):
        return "pretty" if is_tty else "json"
    value = explicit.strip().lower()
    if value == "json":
        return "json"
    if value in ("pretty", "text"):
        return "pretty"
    raise ValueError(f"Unknown format '{explicit}'. Valid formats: auto, json, pretty.")


def _validate_args(args, target):
    """Validate flag combinations; return an error message or None."""
    if target is not None and target not in _LEVEL_INDEX:
        return (f"Invalid target level '{args.target_level}'. "
                f"Valid: {', '.join(_CEFR_ORDER)}.")
    if args.pre_enrich and args.export:
        return ("--pre-enrich primes the dictionary cache and exits; "
                "it can't be combined with --export.")
    if args.pre_enrich and args.no_dictionary_cache:
        return ("--pre-enrich writes the dictionary cache; it can't be combined "
                "with --no-dictionary-cache.")
    if args.export is not None and target is None:
        return ("--export requires --target-level (the pre-teaching list is the "
                "words and structures above the class's level).")
    if args.suggest and target is None:
        return ("--suggest requires --target-level (it suggests a simpler "
                "alternative for each word above the class's level).")
    if args.gap_report and target is None:
        return ("--gap-report requires --target-level (it lists the target-level "
                "constructions the text does not use yet).")
    if args.gap_report and args.no_grammar:
        return ("--gap-report needs the grammar side; it can't be combined "
                "with --no-grammar.")
    if args.curriculum and not os.path.isfile(args.curriculum):
        return f"curriculum file not found: {args.curriculum}"
    if args.watch is not None and not args.file:
        return ("--watch re-profiles a file on save; it requires --file "
                "(the file to watch).")
    if args.watch is not None and args.pre_enrich:
        return ("--watch and --pre-enrich don't combine (--pre-enrich primes "
                "the dictionary cache and exits).")
    if args.cloze and args.export is None:
        return ("--cloze requires --export (it renders the exported examples as "
                "fill-the-gap sentences).")
    if args.cloze and args.export == "flashcards":
        return ("--cloze applies to the md/csv exports; --export flashcards "
                "produces RubricMaker deck cards instead.")
    return None


def _write_export(args, payload, target):
    """Render and write the --export pre-teaching list; True on success."""
    if args.export == "csv":
        content = export_csv(payload, cloze=args.cloze)
    elif args.export == "flashcards":
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = args.wordlists or os.path.join(script_dir, "WordLists")
        cache_path = None
        if not args.no_dictionary_cache:
            cache_path = args.dictionary_cache or default_dictionary_cache_path()
        content, deck_stats = export_flashcards(
            payload, enrich=not args.no_enrich, base_url=args.dictionary_url,
            level_index=vp.load_level_index(base_dir), cache_path=cache_path)
        if deck_stats["offline"]:
            sys.stderr.write("Dictionary enrichment unavailable (offline?); "
                             "the deck shipped with in-context backs. "
                             "Use --no-enrich to silence this.\n")
        elif deck_stats["enriched"] or deck_stats["missed"]:
            cache_clause = (f" ({deck_stats['cached']} from cache)"
                            if deck_stats["cached"] else "")
            sys.stderr.write(
                f"Dictionary enrichment: {deck_stats['enriched']} definition"
                f"{'s' if deck_stats['enriched'] != 1 else ''} added"
                f"{cache_clause}, {deck_stats['missed']} word"
                f"{'s' if deck_stats['missed'] != 1 else ''} not found.\n")
    else:
        content = export_markdown(payload, cloze=args.cloze)
    path = export_path(args.file, args.output, target, args.export)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as ex:
        sys.stderr.write(f"Could not write pre-teaching list: {ex}\n")
        return False
    # stderr, so --format json stdout stays machine-parseable
    sys.stderr.write(f"Wrote pre-teaching list to {path}\n")
    if args.export == "flashcards":
        # The deck doubles as a Can-Do reference when --cando is on: a
        # companion deck with one card per demand descriptor + the
        # above-target diff, in the same RubricMaker import shape.
        cd_csv = export_cando_deck(payload)
        if cd_csv is not None:
            cd_path = cando_deck_path(path)
            try:
                with open(cd_path, "w", encoding="utf-8") as f:
                    f.write(cd_csv)
                sys.stderr.write(f"Wrote Can-Do reference deck to {cd_path}\n")
            except OSError as ex:
                sys.stderr.write(f"Could not write Can-Do reference deck: {ex}\n")
                return False
    return True


def _file_snapshot(path):
    """(mtime_ns, size) of *path* for change detection; None if gone."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def watch_file(path, interval, callback, timeout=None):
    """Re-run ``callback()`` whenever ``path`` changes on disk.

    The Phase 3 watch mode: a dependency-free edit → re-check loop that polls
    the file's mtime/size every ``interval`` seconds (default 1.0) and re-runs
    the report on each save. Stops when the file disappears (or after
    ``timeout`` seconds, for tests) and returns the number of re-runs.
    """
    last = _file_snapshot(path)
    runs = 0
    deadline = (time.monotonic() + timeout) if timeout else None
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            return runs
        time.sleep(interval)
        snap = _file_snapshot(path)
        if snap is None:
            sys.stderr.write(f"Watched file {path} disappeared — stopping.\n")
            return runs
        if snap != last:
            last = snap
            callback()
            runs += 1


def main(argv=None):
    _maybe_reexec_in_venv()
    parser = argparse.ArgumentParser(add_help=True, description="VocabKitchen unified text report")
    parser.add_argument("--target-level", dest="target_level", default=None)
    parser.add_argument("--format", default="auto")
    parser.add_argument("--text", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--wordlists", default=None)
    parser.add_argument("--grammar-profile", dest="grammar_profile", default=None)
    parser.add_argument("--no-grammar", action="store_true")
    parser.add_argument("--no-readability", action="store_true")
    parser.add_argument("--export", choices=["csv", "md", "flashcards"], default=None)
    parser.add_argument("--cloze", action="store_true")
    parser.add_argument("--suggest", action="store_true",
                        help="suggest a simpler alternative (WordLists/synonyms.csv) for "
                             "each word above --target-level — the Phase 3 rewriting aid")
    parser.add_argument("--gap-report", action="store_true",
                        help="list the target-level constructions the text does not use yet "
                             "(the Phase 3 grammar gap report; needs the grammar side)")
    parser.add_argument("--no-enrich", action="store_true",
                        help="--export flashcards only: skip the Free Dictionary API; "
                             "the back of each card stays the in-text context sentence")
    parser.add_argument("--dictionary-url", default=None,
                        help="--export flashcards only: override the dictionary API base URL")
    parser.add_argument("--dictionary-cache", default=None,
                        help="--export flashcards only: JSON cache file for dictionary lookups "
                             "(default: ~/.cache/vocabkitchen/dictionary.json)")
    parser.add_argument("--no-dictionary-cache", action="store_true",
                        help="--export flashcards only: don't read or write the lookup cache")
    parser.add_argument("--pre-enrich", action="store_true",
                        help="prime the dictionary cache from the input (a class word list or "
                             "an essay) in one polite, rate-limited pass, then exit")
    parser.add_argument("--delay", type=float, default=0.25,
                        help="--pre-enrich only: seconds between dictionary requests "
                             "(politeness; 0 for none)")
    parser.add_argument("--limit", type=int, default=None,
                        help="--pre-enrich only: cap the number of new lookups")
    parser.add_argument("--output", default=None)
    parser.add_argument("--watch", nargs="?", const=1.0, type=float, default=None,
                        help="re-profile the --file input whenever it changes on disk "
                             "(the Phase 3 edit → re-check loop; interval in seconds, "
                             "default 1)")
    parser.add_argument("--curriculum", default=None,
                        help="check the text against a curriculum checklist file "
                             "(sections [vocabulary] and [grammar]) and report pass/fail "
                             "coverage of the required words and constructions")
    parser.add_argument("--cambridge", action="store_true",
                        help="map the report's own CEFR bands to the matching Cambridge "
                             "English Qualification (A2 Key, B1 Preliminary, B2 First, "
                             "C1 Advanced, C2 Proficiency) — the Phase 4 exam mapping")
    parser.add_argument("--cando", action="store_true",
                        help="frame the text's demands as CEFR Can-Do descriptors — what a "
                             "learner at the reached/estimated band can do, the language "
                             "rubrics and self-assessment forms use (the Phase 4 Can-Do item)")
    parser.add_argument("positional", nargs="*", help=argparse.SUPPRESS)
    parser.add_argument("positional", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        out_format = resolve_format(args.format, sys.stdout.isatty())
    except ValueError as ex:
        sys.stderr.write(str(ex) + "\n")
        return 1

    target = args.target_level.strip().upper() if args.target_level else None
    error = _validate_args(args, target)
    if error:
        sys.stderr.write(error + "\n")
        return 1
    source_label = None
    text = args.text
    if text is None and args.file:
        try:
            text = vp.extract_text(args.file)
            source_label = os.path.basename(args.file)
        except vp.DocumentError as ex:
            sys.stderr.write(str(ex) + "\n")
            return 1
    if text is None and args.positional:
        text = args.positional[0]
    if text is None and not sys.stdin.isatty():
        text = sys.stdin.read()

    if text is None or text.strip() == "":
        sys.stderr.write(
            "Usage: text_report.py [--target-level A1|A2|B1|B2|C1|C2] "
            "[--format auto|json|pretty] "
            "[--text \"...\" | --file path{.txt|.md|.docx|.pdf} | < stdin] "
            "[--no-grammar] [--no-readability] "
            "[--export csv|md|flashcards [--cloze] [--no-enrich] "
            "[--dictionary-cache PATH|--no-dictionary-cache] [--output PATH]] "
            "[--pre-enrich [--delay SECONDS] [--limit N]]\n"
        )
        return 1

    if args.pre_enrich:
        tokens = [t.lower() for t in vp.tokenize(text)
                  if t not in vp._PLACEHOLDERS]
        words = sorted({t for t in tokens if any(c.isalpha() for c in t)})
        cache_path = args.dictionary_cache or default_dictionary_cache_path()

        def _progress(s):
            sys.stderr.write(
                f"  pre-enriching… {s['looked_up']} looked up "
                f"({s['found']} found, {s['missed']} not found)\n")

        stats = pre_enrich_words(
            words, base_url=args.dictionary_url, cache_path=cache_path,
            delay=args.delay, limit=args.limit, on_progress=_progress)
        tail = ""
        if stats["offline"]:
            tail = " Offline — remaining words left unprimed."
        sys.stderr.write(
            f"Pre-enriched {stats['looked_up']} word"
            f"{'s' if stats['looked_up'] != 1 else ''} "
            f"({stats['found']} found, {stats['missed']} not found); "
            f"{stats['skipped']} of {stats['requested']} already cached."
            + tail + "\n")
        return 0

    curriculum = None
    if args.curriculum:
        try:
            # validate_curriculum parses AND checks the schema — a typo'd
            # section header (e.g. [grammer]) fails here, before profiling.
            curriculum, warnings = validate_curriculum(args.curriculum)
            for w in warnings:
                sys.stderr.write("warning: " + w + "\n")
        except CurriculumError as ex:
            sys.stderr.write(str(ex) + "\n")
            return 1

    def _run_once():
        nonlocal text
        if args.watch is not None and args.file:
            try:
                text = vp.extract_text(args.file)
            except vp.DocumentError as ex:
                sys.stderr.write(str(ex) + "\n")
                return 1
        try:
            payload = analyze(
                text,
                target_level=target,
                wordlists_dir=args.wordlists,
                grammar_dir=args.grammar_profile,
                with_grammar=not args.no_grammar,
                with_readability=not args.no_readability,
                suggest=args.suggest,
                gap_report=args.gap_report,
                curriculum=curriculum,
                cambridge=args.cambridge,
                cando=args.cando,
            )
        except vp.WordListError as ex:
            sys.stderr.write(str(ex) + "\n")
            return 1

        if payload["totalWordCount"] == 0:
            sys.stderr.write("No analysable words found in the input.\n")
            return 1

        if out_format == "pretty":
            render_pretty(payload, source_label)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))

        if args.export and not _write_export(args, payload, target):
            return 1
        return 0

    rc = _run_once()
    if rc:
        return rc
    if args.watch is not None:
        sys.stderr.write(
            f"Watching {args.file} (re-profile on save; Ctrl-C to stop)\n")
        try:
            watch_file(args.file, args.watch, _run_once)
        except KeyboardInterrupt:
            sys.stderr.write("\nStopped.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
