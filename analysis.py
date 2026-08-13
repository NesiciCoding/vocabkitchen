"""VocabKitchen analysis engine — the shared profiling core and the report contract.

The Phase 5 milestone "one leveling engine, two front ends": both CLIs
(``text_report.py`` and ``class_profile.py``) import this engine, so a CEFR
level means exactly the same thing whether one text or a whole folder is
profiled — and RubricMaker gets a single importable entry point to build on
instead of a parallel implementation. This module is fully self-contained:
every report helper (readability, target flagging, Cambridge / Can-Do
mapping, the curriculum checklist) lives here, and ``text_report.py``
re-exports them for backwards compatibility.

* :class:`Engine` — the word lists plus (optionally) the grammar engine,
  loaded **once** (spaCy reloads per call, so a folder or watch run reuses
  one instance).
* :func:`profile` — per-text vocabulary + grammar + readability pieces,
  the raw material the CLIs fold into rows, aggregates, and payloads.
* :func:`payload` — the text_report-shaped report payload assembled from
  profile pieces; shared by :func:`analyze` and class_profile's per-text
  ``--export`` payloads, so a folder handout is byte-compatible with the
  single-text report.
* :func:`analyze` — the full single-text pipeline (``text_report``'s CLI).

.. _payload-schema:

The report payload contract
---------------------------

Every payload carries ``schemaVersion`` (see :data:`SCHEMA_VERSION`) and is
validated against :func:`payload_schema` (also checked in as
``analysis.schema.json``). The top-level keys:

``schemaVersion``  the contract version, e.g. ``"1.0"``.
``totalWordCount`` the text's running word count (vocab profiler tokens).
``vocabulary``     ``{"typical", "coverage", "offListPercent", "results"}``
                   — typical/reached CEFR bands, % of recognised running
                   words off-list, and the per-band word counts.
``grammar``        the grammar profile (``sentenceCount``, ``tokenCount``,
                   ``constructionCount``, ``estimatedLevel``, per-band
                   ``results``) or null when the grammar side didn't run.
``grammarCriteria`` per-construction pass/fail over every registered
                   construction (the shape RubricMaker's grammar linker
                   consumes for its apply-as-comment breakdown) or null.
``grammarComments`` per-construction rubric comments derived from
                   ``grammarCriteria`` (the apply-as-comment reference
                   implementation), or null unless ``comments`` is on; with
                   a ``targetLevel`` the list is filtered to it — at/below
                   entries keep their pass/fail comments (``kind``
                   ``"rubric"``), used above-target ones become
                   ``"pre-teach"`` notes (carrying a curated ``rewrite``
                   hint when one exists), unused above-target ones drop.
``vocabComments``   the vocabulary half of the apply-as-comment pass: one
                   comment per above-target word, or null unless ``comments``
                   is on with a ``targetLevel``.
``grammarError``   the reason grammar is missing (install note, "not
                   analysed", or null).
``targetLevel``    the class level the report was measured against.
``aboveTarget``    words/structures above *targetLevel* + ``maxLevel``.
``coverage``       the teacher number: % of recognised running words the
                   target learner already knows.
``estimatedLevel`` the blended estimate (higher of vocab coverage / grammar
                   typical).
``verdict``        the one-line "on level" / "reaches X — pre-teach …".
``grammarGap``     the Phase 3 gap report (target constructions the text
                   does not use yet).
``curriculum``     the Phase 4 checklist pass/fail coverage.
``cambridge``      each shown band mapped to its Cambridge qualification.
``cando``          each shown band framed as a CEFR Can-Do descriptor.
``readability``    Flesch Reading Ease + Flesch–Kincaid grade.
``file``           (class_profile per-text payloads only) the source file.

Version history
~~~~~~~~~~~~~~~

``1.4`` — ``vocabulary`` gains ``profile``: the pluggable vocabulary profile
in effect (``{name, kind, levelFallback}`` — which word lists produced the
bands), or null when the bundled CEFR lists were used.
``1.3`` — ``grammarComments`` entries gain ``rewrite``: pre-teach entries
carry a curated target-level rewording hint (from
``WordLists/structure-rewrites.csv``) so the "or rewrite" half of the
note is concrete.
``1.2`` — ``grammarComments`` entries gain ``kind`` (``"rubric"`` /
``"pre-teach"``) and, under a ``targetLevel``, are filtered to the class
level: at/below constructions keep their pass/fail comments, used
above-target ones become pre-teach-or-rewrite notes, unused above-target
ones are dropped.
``1.1`` — added ``vocabComments``, the vocabulary half of the apply-as-comment
pass (one comment per above-target word), completing the rubric coverage.
``1.0`` — initial documented contract: the payload keys above, including the
``grammarCriteria`` per-construction pass/fail shape and ``schemaVersion``.
"""

import csv
import difflib
import os
import re

import vocab_profile as vp
import grammar_profile as gp

# The payload contract version. Bump when the payload shape changes
# incompatibly; RubricMaker and any other consumer should key off this.
SCHEMA_VERSION = "1.4"

_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
_LEVEL_INDEX = {lvl: i for i, lvl in enumerate(_CEFR_ORDER)}


def payload_schema():
    """The JSON Schema for the report payload — the RubricMaker contract.

    A single source of truth for the shape :func:`payload` produces; kept
    byte-identical with the checked-in ``analysis.schema.json`` (the test
    suites assert that, mirroring the skill-copy sync guard). Depth is
    pragmatic: the top level and each named object are fully specified,
    deep leaves (word/construction entries) stay open so the schema doesn't
    need a bump for cosmetic additions.
    """
    band = {"type": ["string", "null"],
            "enum": [None] + _CEFR_ORDER}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://vocabkitchen.dev/schemas/analysis.schema.json",
        "title": "VocabKitchen analysis report payload",
        "description": "The CEFR profile of one text, as produced by "
                       "text_report.py and class_profile.py per-text exports.",
        "version": SCHEMA_VERSION,
        "type": "object",
        "required": ["schemaVersion", "totalWordCount", "vocabulary",
                     "grammar", "grammarError", "grammarCriteria",
                     "grammarComments", "vocabComments", "targetLevel",
                     "aboveTarget", "coverage", "estimatedLevel",
                     "verdict", "grammarGap", "grammarGapError",
                     "curriculum", "curriculumError",
                     "cambridge", "cando", "readability"],
        "properties": {
            "schemaVersion": {"type": "string", "enum": [SCHEMA_VERSION]},
            "totalWordCount": {"type": "integer", "minimum": 0},
            "file": {"type": ["string", "null"]},
            "vocabulary": {"type": ["object", "null"],
                           "properties": {
                               "typical": band,
                               "coverage": band,
                               "offListPercent": {"type": "integer",
                                                  "minimum": 0,
                                                  "maximum": 100},
                               "profile": {"type": ["object", "null"],
                                            "required": ["name", "kind",
                                                         "levelFallback"],
                                            "properties": {
                                                "name": {"type": "string"},
                                                "kind": {"enum": ["directory", "list"]},
                                                "levelFallback": band,
                                            }},
                               "results": {"type": "object"},
                           }},
            "grammar": {"type": ["object", "null"], "properties": {
                "sentenceCount": {"type": "integer"},
                "tokenCount": {"type": "integer"},
                "constructionCount": {"type": "integer"},
                "estimatedLevel": {"type": "object"},
                "results": {"type": "object"},
            }},
            "grammarError": {"type": ["string", "null"]},
            "grammarCriteria": {"type": ["object", "null"], "properties": {
                "targetLevel": band,
                "criteria": {"type": "array", "items": {"type": "object",
                                                       "properties": {
                                                           "id": {"type": "string"},
                                                           "name": {"type": "string"},
                                                           "category": {"type": "string"},
                                                           "level": {"type": "string"},
                                                           "status": {"enum": ["used", "not used"]},
                                                           "pass": {"type": "boolean"},
                                                           "count": {"type": "integer"},
                                                           "examples": {"type": "array"},
                                                       }}},
                "passedCount": {"type": "integer"},
                "failedCount": {"type": "integer"},
                "total": {"type": "integer"},
            }},
            "grammarComments": {"type": ["array", "null"], "items": {
                "type": "object", "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "level": {"type": "string"},
                    "status": {"enum": ["used", "not used"]},
                    "pass": {"type": "boolean"},
                    "kind": {"enum": ["rubric", "pre-teach"]},
                    "rewrite": {"type": ["string", "null"]},
                    "comment": {"type": "string"},
                }}},
            "vocabComments": {"type": ["array", "null"], "items": {
                "type": "object", "properties": {
                    "word": {"type": "string"},
                    "level": {"type": "string"},
                    "occurrences": {"type": "integer"},
                    "suggestion": {"type": ["string", "null"]},
                    "comment": {"type": "string"},
                }}},
            "targetLevel": band,
            "aboveTarget": {"type": ["object", "null"], "properties": {
                "maxLevel": band,
                "words": {"type": "array"},
                "wordCount": {"type": "integer"},
                "structures": {"type": "array"},
                "structureCount": {"type": "integer"},
            }},
            "coverage": {"type": ["object", "null"], "properties": {
                "targetLevel": band,
                "knownPercent": {"type": "integer"},
                "knownWords": {"type": "integer"},
                "recognisedWords": {"type": "integer"},
                "sentence": {"type": "string"},
            }},
            "estimatedLevel": band,
            "verdict": {"type": ["string", "null"]},
            "grammarGap": {"type": ["object", "null"], "properties": {
                "targetLevel": band,
                "total": {"type": "integer"},
                "missingCount": {"type": "integer"},
                "missing": {"type": "array"},
            }},
            "grammarGapError": {"type": ["string", "null"]},
            "curriculum": {"type": ["object", "null"], "properties": {
                "vocabulary": {"type": "array"},
                "grammar": {"type": "array"},
                "vocabularyCovered": {"type": "string"},
                "grammarCovered": {"type": "string"},
                "pass": {"type": "boolean"},
                "missing": {"type": "array"},
            }},
            "curriculumError": {"type": ["string", "null"]},
            "cambridge": {"type": ["object", "null"]},
            "cando": {"type": ["object", "null"]},
            "readability": {"type": ["object", "null"], "properties": {
                "fleschReadingEase": {"type": "number"},
                "fleschKincaidGrade": {"type": "number"},
                "description": {"type": "string"},
            }},
        },
    }


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
# the grammar gap report, the per-construction pass/fail criteria, and the
# one-line verdict.
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
    # A construction counts as used whichever band it landed in: detection
    # buckets by the effective (override-aware) level, so a when-clause
    # resolves to A1 while its registry base is A2 — checking only the
    # target band would falsely report it as a gap.
    used = {e["name"] for lvl in (gresults or {}).values()
            for e in lvl.values()}
    missing = [c for c in all_at if c["name"] not in used]
    return {
        "targetLevel": target,
        "total": len(all_at),
        "missingCount": len(missing),
        "missing": missing,
    }


def load_structure_rewrites(path=None):
    """The curated rewrite guidance: construction id -> simpler phrasing.

    Reads ``WordLists/structure-rewrites.csv`` (columns ``id,simpler``) — the
    Phase 5 rewriting aid for above-target constructions: each hint is a
    target-level rewording strategy a teacher can apply to the example
    sentence. Returns an empty dict when the file is absent, so rewrites are
    an opt-in enhancement, never a hard dependency. The list is validated by
    ``build_wordlists.py --check`` against the grammar registry's ids.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "WordLists", "structure-rewrites.csv")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for row in rows[1:]:
        if len(row) != 2 or not all(cell.strip() for cell in row):
            continue
        out[row[0].strip()] = row[1].strip()
    return out


def grammar_comments(gc, target_level=None, rewrites=None):
    """Turn ``grammarCriteria`` into per-construction rubric comments.

    The apply-as-comment reference implementation: one comment per
    construction — a positive one for each used criterion (with the first
    detected span as evidence) and a next-step one for each not-used
    criterion — so RubricMaker's grammar linker can attach a comment per
    construction without writing its own phrasing. Each entry keeps the
    criterion's identity (``id``/``name``/``category``/``level``,
    ``status``/``pass``) alongside the generated ``comment`` text.

    With a *target_level* the list is **filtered to the class level**: only
    constructions at or below the target are commented (``kind``
    ``"rubric"`` — the pass/fail comments above). A construction the text
    **uses** above the target is a demand, so it becomes a ``"pre-teach"``
    entry instead (``Uses the … — above the {target} target: pre-teach or
    rewrite.``, mirroring the above-target vocabulary words); a construction
    **not used** above the target is dropped entirely — a B1 class isn't
    expected to produce C2 structures, so flagging them as gaps would be
    noise. Without a target, every construction keeps its rubric comment
    (``kind`` ``"rubric"``), as before.

    *rewrites* — the :func:`load_structure_rewrites` dict, loaded from
    ``WordLists/structure-rewrites.csv`` when omitted — adds the rewrite aid:
    a pre-teach entry whose construction has a curated hint carries it as
    ``rewrite`` and appends ``Rewrite: …`` to the comment, so the "or
    rewrite" half of the note is concrete rather than an instruction.
    """
    if rewrites is None:
        rewrites = load_structure_rewrites()
    out = []
    tgt = _LEVEL_INDEX.get(target_level) if target_level is not None else None
    for c in (gc or {}).get("criteria") or []:
        idx = _LEVEL_INDEX.get(c["level"])
        if tgt is not None and idx is not None and idx > tgt:
            if not c["pass"]:
                continue  # above the class level and unused: not a demand
            comment = (f"Uses the {c['name']} ({c['level']}) — above the "
                       f"{target_level} target: pre-teach or rewrite.")
            ex = (c.get("examples") or [{}])[0].get("span")
            if ex:
                # Escape the pipe before interpolation: the expression must
                # stay backslash-free so Python 3.11 can parse this file.
                ex_escaped = ex.replace("|", "\\|")
                comment += f' E.g. "{ex_escaped}"'
            rw = rewrites.get(c["id"])
            if rw:
                comment += f" Rewrite: {rw}"
            out.append({"id": c["id"], "name": c["name"],
                        "category": c["category"], "level": c["level"],
                        "status": c["status"], "pass": c["pass"],
                        "kind": "pre-teach", "rewrite": rw or None,
                        "comment": comment})
            continue
        if c["pass"]:
            comment = f"Uses the {c['name']} ({c['level']})."
            ex = (c.get("examples") or [{}])[0].get("span")
            if ex:
                ex_escaped = ex.replace("|", "\\|")
                comment += f' E.g. "{ex_escaped}"'
        else:
            comment = f"Doesn't use the {c['name']} ({c['level']}) yet."
        out.append({"id": c["id"], "name": c["name"],
                    "category": c["category"], "level": c["level"],
                    "status": c["status"], "pass": c["pass"],
                    "kind": "rubric", "rewrite": None,
                    "comment": comment})
    return out


def vocabulary_comments(words, target_level):
    """Turn *target_level*-above vocabulary words into rubric comments.

    The vocabulary half of the apply-as-comment reference implementation:
    one comment per above-target word — ``Above {target}: "{word}"
    ({level}) — used {n}×.`` — with the first sentence containing it as
    evidence (``E.g. "…"``, when available) and the curated simpler
    alternative (``Swap for "…"``, when ``suggest`` was on). Each entry
    carries the word's identity (``word``/``level``/``occurrences``/
    ``suggestion``) alongside the generated ``comment``, so RubricMaker's
    vocabulary linker can attach one comment per word the way the grammar
    linker does per construction.
    """
    out = []
    for d in (words or []):
        comment = (f'Above {target_level}: "{d["word"]}" ({d["level"]})'
                   f" — used {d['occurrences']}×.")
        ctx = d.get("context")
        if ctx:
            comment += f' E.g. "{ctx}"'
        s = d.get("suggestion")
        if s:
            comment += f' Swap for "{s["word"]}" ({s["level"]}).'
        out.append({"word": d["word"], "level": d["level"],
                    "occurrences": d["occurrences"],
                    "suggestion": s["word"] if s else None,
                    "comment": comment})
    return out


def grammar_criteria(gresults, cefrj_levels, target_level=None):
    """Per-construction pass/fail over **every** registered construction.

    The shape RubricMaker's grammar linker consumes for its apply-as-comment
    breakdown: one entry per construction in the grammar profiler's registry,
    judged ``used`` (pass, with count + up to two examples) or ``not used``
    (fail) — so a comment can be attached per criterion without re-deriving
    anything. Levels resolve exactly like the profiler's
    (``cefrj_levels.get(code, fallback)``); the list is sorted by band ladder
    then name.
    """
    used = {}
    for _lvl, entries in (gresults or {}).items():
        for cid, entry in entries.items():
            used[cid] = entry
    criteria = []
    for cid, (name, category, code, fallback) in gp._CONSTRUCTIONS.items():
        entry = used.get(cid)
        level = (entry or {}).get("level") or cefrj_levels.get(code, fallback)
        criteria.append({
            "id": cid,
            "name": name,
            "category": category,
            "level": level,
            "status": "used" if entry else "not used",
            "pass": entry is not None,
            "count": entry["count"] if entry else 0,
            "examples": (entry["examples"][:2] if entry else []),
        })
    criteria.sort(key=lambda d: (_LEVEL_INDEX.get(d["level"], 99), d["name"].lower()))
    passed = sum(1 for c in criteria if c["pass"])
    return {
        "targetLevel": target_level,
        "criteria": criteria,
        "passedCount": passed,
        "failedCount": len(criteria) - passed,
        "total": len(criteria),
    }


# ---------------------------------------------------------------------------
# Cambridge English Qualifications (Phase 4 exam mapping)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Curriculum checklist (Phase 4) — parse + validate up front, report pass/fail
# ---------------------------------------------------------------------------

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
    # One pass over the whole checklist: word_contexts compiles a pattern per
    # requested word, so per-word calls would re-walk the text every time.
    present_ctx = word_contexts(text, curriculum["vocabulary"])
    for w in curriculum["vocabulary"]:
        vocabulary.append({"word": w, "present": w in present_ctx,
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


# ---------------------------------------------------------------------------
# Contexts, the one-line verdict, and the blended estimate
# ---------------------------------------------------------------------------

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
# The shared engine: word lists + grammar, loaded once
# ---------------------------------------------------------------------------

class Engine:
    """The profilers' static state: word lists, and — when available — the
    grammar engine (spaCy model + CEFR-J levels).

    ``grammar_available`` is False when the grammar side was skipped or the
    engine is missing/errored; ``grammar_error`` then carries the note (e.g.
    the install guidance from grammar_profile) for the report to show.
    """

    def __init__(self, levels, vocab_base, grammar_available=False,
                 nlp=None, cefrj_levels=None, grammar_error=None,
                 grammar_requested=True, profile_label=None,
                 profile_meta=None):
        self.levels = levels
        self.vocab_base = vocab_base
        self.grammar_available = grammar_available
        self.nlp = nlp
        self.cefrj_levels = cefrj_levels
        self.grammar_error = grammar_error
        self.grammar_requested = grammar_requested
        self.profile_label = profile_label
        self.profile_meta = profile_meta


def load_engine(wordlists_dir=None, grammar_dir=None, with_grammar=True,
                script_dir=None, profile=None, profile_level="B1"):
    """Load the word lists (always) and the grammar engine (when requested).

    With *profile* (a pluggable vocabulary profile — see
    :func:`vocab_profile.load_profile`), the CEFR lists are swapped for the
    profile's (Oxford 3000/5000, a licensed list, the Octanove C1/C2 export,
    ...); ``profile_level`` is the fallback band for single-file profiles.
    Raises ``vocab_profile.WordListError`` for a broken word-list install; a
    missing spaCy model or CEFR-J profile is **not** fatal — the engine is
    returned with ``grammar_available=False`` and the install note in
    ``grammar_error``, so the report degrades gracefully exactly like the
    CLIs always have.
    """
    script_dir = script_dir or os.path.dirname(os.path.abspath(__file__))
    vocab_base = wordlists_dir or os.path.join(script_dir, "WordLists")
    profile_label = profile_meta = None
    if profile:
        levels, profile_label, profile_meta = vp.load_profile(
            profile, level_index=vp.load_level_index(vocab_base),
            fallback_level=profile_level)
    else:
        levels = [(name, vp.load_wordlist(vocab_base, rel))
                  for name, rel in vp.PROFILERS["cefr"]]
    if not with_grammar:
        return Engine(levels, vocab_base, grammar_requested=False,
                      profile_label=profile_label, profile_meta=profile_meta)
    try:
        gbase = grammar_dir or os.path.join(script_dir, "GrammarProfile")
        nlp = gp.load_nlp()
        cefrj = gp.load_cefrj_levels(gbase)
        return Engine(levels, vocab_base, grammar_available=True,
                      nlp=nlp, cefrj_levels=cefrj,
                      profile_label=profile_label, profile_meta=profile_meta)
    except gp.EngineError as ex:
        return Engine(levels, vocab_base, grammar_error=str(ex).strip(),
                      profile_label=profile_label, profile_meta=profile_meta)


def profile(text, engine, with_grammar=True, with_readability=True):
    """Profile one text with the shared *engine*; return the pieces.

    The dict carries everything both CLIs build on: ``ordered`` (the
    vocab_profile per-level result), ``total``, ``typical``/``coverage``/
    ``offListPercent``, the grammar payload (``grammar_results`` /
    ``grammar_meta`` / ``grammar_available`` / ``grammar_error`` /
    ``cefrj_levels``), and ``readability``. ``with_grammar`` skips the
    grammar side per-call even when the engine has it loaded (the class
    profile's ``--pre-enrich`` pass).
    """
    ordered, total = vp.profile(text, engine.levels)
    counts = {name: sum(occ for _w, occ in rows)
              for name, _pct, rows in ordered}
    _c, typical, coverage = vp.cefr_stats(ordered, total)
    off_list_percent = (round(counts.get("Off List", 0) / total * 100)
                        if total else 0)

    gresults = gmeta = None
    grammar_available = False
    grammar_error = None
    if with_grammar and engine.grammar_available:
        try:
            if len(text) > engine.nlp.max_length:
                raise ValueError(
                    f"input too long for the parser ({len(text):,} characters; "
                    f"limit {engine.nlp.max_length:,}) — split the text and re-run")
            gresults, gmeta = gp.profile(text, engine.nlp, engine.cefrj_levels)
            grammar_available = True
        except (gp.EngineError, ValueError) as ex:
            grammar_error = str(ex).strip()
    elif with_grammar:
        # The engine itself failed to load — carry its note so the report
        # shows the install guidance instead of silently skipping.
        grammar_error = engine.grammar_error

    return {
        "ordered": ordered,
        "total": total,
        "counts": counts,
        "typical": typical,
        "coverage": coverage,
        "offListPercent": off_list_percent,
        "grammar_results": gresults,
        "grammar_meta": gmeta,
        "grammar_available": grammar_available,
        "grammar_error": grammar_error,
        "cefrj_levels": engine.cefrj_levels if with_grammar else None,
        "profile": engine.profile_meta,
        "readability": (compute_readability(text, total)
                        if with_readability else None),
    }


def payload(pieces, text, vocab_base, target_level=None, suggest=False,
            gap_report=False, curriculum=None, cambridge=False, cando=False,
            comments=False, grammar_unavailable_note="not analysed",
            synonyms=None, rewrites=None):
    """Assemble the text_report-shaped payload from *pieces* (see
    :func:`profile`) — the single payload builder behind ``analyze`` and
    class_profile's per-text ``--export`` payloads, so both produce the same
    keys and the folder handouts are byte-compatible with the single-text
    report. *vocab_base* feeds the synonyms list for ``suggest``;
    *grammar_unavailable_note* is the ``grammarError`` shown when the
    grammar side neither ran nor failed (``text_report`` says "skipped
    (--no-grammar)", the class profile says "not analysed"). With
    ``comments=True`` the payload carries the full apply-as-comment pass:
    ``grammarComments`` (per-construction, derived from ``grammarCriteria``,
    when the grammar side is available) **and** ``vocabComments`` (per
    above-target word, when a ``target_level`` is given) — the rubric
    reference implementation for RubricMaker's grammar and vocabulary
    linkers. Under a ``target_level``, ``grammarComments`` is filtered to
    the class level (see :func:`grammar_comments`): used above-target
    constructions become ``"pre-teach"`` notes instead of rubric comments.
    """
    ordered = pieces["ordered"]
    total = pieces["total"]
    gresults = pieces["grammar_results"]
    gmeta = pieces["grammar_meta"]
    grammar_available = pieces["grammar_available"]
    grammar_error = pieces["grammar_error"]
    gc_obj = (grammar_criteria(gresults, pieces["cefrj_levels"],
                               target_level)
              if grammar_available else None)

    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "totalWordCount": total,
        "vocabulary": {
            "typical": pieces["typical"],
            "coverage": pieces["coverage"],
            "offListPercent": pieces["offListPercent"],
            "profile": pieces.get("profile"),
            "results": vp.results_to_json(ordered),
        },
        "grammar": (gp.results_to_json(gresults, gmeta)
                    if grammar_available else None),
        "grammarError": (grammar_error
                         if grammar_error
                         else (None if grammar_available
                               else grammar_unavailable_note)),
        "grammarCriteria": gc_obj,
        "grammarComments": (grammar_comments(gc_obj, target_level,
                                             rewrites=rewrites)
                            if gc_obj is not None and comments else None),
        "vocabComments": None,
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
        "readability": pieces["readability"],
    }

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
            if synonyms is None:
                synonyms = load_synonyms(os.path.join(vocab_base, "synonyms.csv"))
            for d in words:
                s = synonyms.get(d["word"])
                if s:
                    d["suggestion"] = s
        payload["aboveTarget"] = {
            "maxLevel": max(bands, key=lambda lvl: _LEVEL_INDEX[lvl])
                        if bands else None,
            "words": words,
            "wordCount": len(words),
            "structures": structures,
            "structureCount": len(structures),
        }
        payload["coverage"] = coverage_figure(ordered, target_level)
        payload["verdict"] = build_verdict(words, structures, grammar_available)

    payload["vocabComments"] = (vocabulary_comments(
        (payload["aboveTarget"] or {}).get("words") or [], target_level)
        if comments and target_level is not None else None)

    if gap_report:
        if target_level is None:
            payload["grammarGapError"] = "requires --target-level"
        elif not grammar_available:
            payload["grammarGapError"] = (payload["grammarError"]
                                          or "not analysed")
        else:
            payload["grammarGap"] = grammar_gap_report(
                gresults, pieces["cefrj_levels"], target_level)

    grammar_typical = gmeta["estimatedLevel"]["typical"] if gmeta else None
    payload["estimatedLevel"] = blend_level(pieces["coverage"], grammar_typical)

    if cambridge:
        payload["cambridge"] = cambridge_mapping(payload)
    if cando:
        payload["cando"] = cando_mapping(payload, target_level)

    if curriculum:
        # Re-run the checklist with the grammar results now that the grammar
        # side has (or hasn't) run; vocabulary presence needs `ordered`.
        payload["curriculum"] = curriculum_report(
            text, curriculum, ordered, gresults)
        if not grammar_available:
            payload["curriculum"]["grammarAvailable"] = False
            payload["curriculumError"] = (
                payload["grammarError"] or "grammar not analysed")
        else:
            payload["curriculum"]["grammarAvailable"] = True
    return payload


def analyze(text, target_level=None, wordlists_dir=None, grammar_dir=None,
            with_grammar=True, with_readability=True, suggest=False,
            gap_report=False, curriculum=None, cambridge=False, cando=False,
            comments=False, profile_path=None, profile_level="B1"):
    """Run both profilers and readability over *text*; return the report payload.

    The single-text pipeline — the same report ``text_report.py`` ships:
    vocabulary (always), grammar (when available), readability, and, with a
    *target_level*, the above-target words/structures, coverage figure and
    verdict. ``suggest``/``gap_report``/``curriculum``/``cambridge``/``cando``
    add the Phase 3/4 layers (rewrite aid, grammar gaps, the checklist, exam
    mapping, Can-Do    framing); ``comments`` adds the full apply-as-comment pass — the
    per-construction rubric comments (``grammarComments``) and, with a
    target level, the per-word comments for above-target vocabulary
    (``vocabComments``) — so the rubric covers the whole report.
    ``profile_path`` swaps the bundled CEFR lists for a pluggable vocabulary
    profile (see :func:`load_engine`).
    """
    engine = load_engine(wordlists_dir=wordlists_dir, grammar_dir=grammar_dir,
                         with_grammar=with_grammar, profile=profile_path,
                         profile_level=profile_level)
    pieces = profile(text, engine, with_grammar=with_grammar,
                     with_readability=with_readability)
    return payload(
        pieces, text, engine.vocab_base, target_level=target_level,
        suggest=suggest, gap_report=gap_report, curriculum=curriculum,
        cambridge=cambridge, cando=cando, comments=comments,
        grammar_unavailable_note="skipped (--no-grammar)"
        if not with_grammar else "not analysed")
