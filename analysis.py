"""VocabKitchen analysis engine — the shared profiling core.

The Phase 5 milestone "one leveling engine, two front ends": both CLIs
(``text_report.py`` and ``class_profile.py``) import this engine, so a CEFR
level means exactly the same thing whether one text or a whole folder is
profiled — and RubricMaker gets a single importable entry point to build on
instead of a parallel implementation.

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

The report helpers (``words_above_target``, ``coverage_figure``, ...) live in
``text_report.py``; this module imports them lazily inside the functions that
need them, which keeps the module graph acyclic (``text_report`` imports this
module at the top).
"""

import os

import vocab_profile as vp
import grammar_profile as gp


class Engine:
    """The profilers' static state: word lists, and — when available — the
    grammar engine (spaCy model + CEFR-J levels).

    ``grammar_available`` is False when the grammar side was skipped or the
    engine is missing/errored; ``grammar_error`` then carries the note (e.g.
    the install guidance from grammar_profile) for the report to show.
    """

    def __init__(self, levels, vocab_base, grammar_available=False,
                 nlp=None, cefrj_levels=None, grammar_error=None,
                 grammar_requested=True):
        self.levels = levels
        self.vocab_base = vocab_base
        self.grammar_available = grammar_available
        self.nlp = nlp
        self.cefrj_levels = cefrj_levels
        self.grammar_error = grammar_error
        self.grammar_requested = grammar_requested


def load_engine(wordlists_dir=None, grammar_dir=None, with_grammar=True,
                script_dir=None):
    """Load the word lists (always) and the grammar engine (when requested).

    Raises ``vocab_profile.WordListError`` for a broken word-list install; a
    missing spaCy model or CEFR-J profile is **not** fatal — the engine is
    returned with ``grammar_available=False`` and the install note in
    ``grammar_error``, so the report degrades gracefully exactly like the
    CLIs always have.
    """
    script_dir = script_dir or os.path.dirname(os.path.abspath(__file__))
    vocab_base = wordlists_dir or os.path.join(script_dir, "WordLists")
    levels = [(name, vp.load_wordlist(vocab_base, rel))
              for name, rel in vp.PROFILERS["cefr"]]
    if not with_grammar:
        return Engine(levels, vocab_base, grammar_requested=False)
    try:
        gbase = grammar_dir or os.path.join(script_dir, "GrammarProfile")
        nlp = gp.load_nlp()
        cefrj = gp.load_cefrj_levels(gbase)
        return Engine(levels, vocab_base, grammar_available=True,
                      nlp=nlp, cefrj_levels=cefrj)
    except gp.EngineError as ex:
        return Engine(levels, vocab_base, grammar_error=str(ex).strip())


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
        "readability": (_compute_readability(text, total)
                        if with_readability else None),
    }


def payload(pieces, text, vocab_base, target_level=None, suggest=False,
            gap_report=False, curriculum=None, cambridge=False, cando=False,
            grammar_unavailable_note="not analysed"):
    """Assemble the text_report-shaped payload from *pieces* (see
    :func:`profile`) — the single payload builder behind ``analyze`` and
    class_profile's per-text ``--export`` payloads, so both produce the same
    keys and the folder handouts are byte-compatible with the single-text
    report. *vocab_base* feeds the synonyms list for ``suggest``;
    *grammar_unavailable_note* is the ``grammarError`` shown when the
    grammar side neither ran nor failed (``text_report`` says "skipped
    (--no-grammar)", the class profile says "not analysed").
    """
    from text_report import (  # lazy: text_report imports this module
        _LEVEL_INDEX, blend_level, build_verdict, cambridge_mapping,
        cando_mapping, coverage_figure, curriculum_report, grammar_gap_report,
        load_synonyms, structures_above_target, word_contexts,
        words_above_target,
    )
    ordered = pieces["ordered"]
    total = pieces["total"]
    gresults = pieces["grammar_results"]
    gmeta = pieces["grammar_meta"]
    grammar_available = pieces["grammar_available"]
    grammar_error = pieces["grammar_error"]

    payload = {
        "totalWordCount": total,
        "vocabulary": {
            "typical": pieces["typical"],
            "coverage": pieces["coverage"],
            "offListPercent": pieces["offListPercent"],
            "results": vp.results_to_json(ordered),
        },
        "grammar": (gp.results_to_json(gresults, gmeta)
                    if grammar_available else None),
        "grammarError": (grammar_error
                         if grammar_error
                         else (None if grammar_available
                               else grammar_unavailable_note)),
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
            syns = load_synonyms(os.path.join(vocab_base, "synonyms.csv"))
            for d in words:
                s = syns.get(d["word"])
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
            gap_report=False, curriculum=None, cambridge=False, cando=False):
    """Run both profilers and readability over *text*; return the report payload.

    The single-text pipeline — the same report ``text_report.py`` ships:
    vocabulary (always), grammar (when available), readability, and, with a
    *target_level*, the above-target words/structures, coverage figure and
    verdict. ``suggest``/``gap_report``/``curriculum``/``cambridge``/``cando``
    add the Phase 3/4 layers (rewrite aid, grammar gaps, the checklist, exam
    mapping, Can-Do framing).
    """
    engine = load_engine(wordlists_dir=wordlists_dir, grammar_dir=grammar_dir,
                         with_grammar=with_grammar)
    pieces = profile(text, engine, with_grammar=with_grammar,
                     with_readability=with_readability)
    return payload(
        pieces, text, engine.vocab_base, target_level=target_level,
        suggest=suggest, gap_report=gap_report, curriculum=curriculum,
        cambridge=cambridge, cando=cando,
        grammar_unavailable_note="skipped (--no-grammar)"
        if not with_grammar else "not analysed")


def _compute_readability(text, word_count):
    """Flesch figures via text_report's helper (lazy import, no cycle)."""
    from text_report import compute_readability
    return compute_readability(text, word_count)
