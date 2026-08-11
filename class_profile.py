#!/usr/bin/env python3
"""VocabKitchen class profile — profile a whole folder of texts in one run.

Scales the single-text profilers to the set of candidate readings a teacher
actually has. Where ``vocab_profile.py`` scores one text and
``text_report.py`` answers *"is this text right for my class?"*, this tool
answers *"which of these texts is right for my class?"* — one command over a
directory (or glob), producing the same artefacts as RubricMaker's Vocabulary
Profile dashboard, which aggregates a class's texts into a CEFR distribution
and exports vocabulary lists by CEFR band to CSV:

  - **Batch input** — ``--file`` accepts a directory, a glob
    (``"articles/*.txt"``, ``**`` for recursion), or a single file; every
    supported text (``.txt``/``.md``/``.docx``/``.pdf``) is profiled in one
    run. Unreadable or empty files are skipped with a note, never fatal.
  - **Summary report** — one row per text: filename, typical & reached
    vocabulary band, grammar range, and (with ``--target-level``) the
    percentage of recognised running words above the class's level.
    ``--format csv`` emits it spreadsheet-ready; ``--format json`` and
    ``pretty`` show the same table plus the aggregate distribution.
  - **Rank & filter** — ``--sort`` ranks the set by estimated level
    (default) or by vocab typical / reached band, word count, or filename;
    ``--min-level`` / ``--max-level`` keep only the texts in a band — so
    *"which of these 20 articles suits B1?"* is one command:
    ``class_profile.py --file essays/ --max-level B1``.
  - **Several classes at once** — ``--targets A2,B1,B2`` shows each text's
    fits / %-above verdict for every level side by side in one run, so a
    mixed-ability set can be split across classes in a single table.
  - **Aggregate distribution** — the pooled CEFR distribution over the whole
    set (typical band, 90%-coverage band, off-list share), exactly what the
    dashboard's headline chart shows.
  - **Vocabulary-list export by band** — ``--export-vocab DIR`` writes one
    CSV per CEFR band (``vocab-A1.csv`` … ``vocab-C2.csv``, plus
    ``vocab-off-list.csv``) over the selected set: distinct words, running
    occurrences across the set, and the number of texts each word appears in —
    ready-made pre-teaching lists and glossaries.
  - **Per-text pre-teaching lists** — ``--export csv|md|flashcards`` writes
    one pre-teaching list per text (same handouts, fill-the-gap worksheets and
    RubricMaker flashcard decks as ``text_report.py``, one set per text),
    each next to its source file, so a whole folder is prepared in one run.
    With ``--export flashcards`` over more than one text, a **combined
    class-wide deck** is written too — all above-target words across the set
    in one RubricMaker deck, named after the source folder — together with a
    **markdown index** (``essays-preteaching-B1-index.md``) listing each
    word's CEFR level and the texts it came from; ``--export md|csv`` over
    more than one text likewise writes a **set-level summary handout**
    (``essays-summary-B1.md``) aggregating the pooled distribution and each
    text's verdict. With ``--targets A2,B1`` instead, one combined
    deck + index **per level** (``essays-preteaching-A2-deck.csv`` …), no
    per-text lists.
  - **Pre-enrich the folder's vocabulary** — ``--pre-enrich`` primes the
    dictionary cache from the whole folder's distinct words in one polite,
    rate-limited pass (``--delay SECONDS``, ``--limit N``), then exits —
    subsequent ``--export flashcards`` runs answer from the cache with zero
    requests. ``--dictionary-cache`` / ``--dictionary-url`` point the lookups
    at a shared or test cache/server.

The vocabulary side is dependency-free Python 3 and reuses
``vocab_profile.py``'s tokenizer, word lists and percentage rounding
verbatim. The grammar side needs spaCy exactly like ``grammar_profile.py``
and degrades gracefully when it's missing — the estimated level then falls
back to the vocabulary 90%-coverage band. Like the other tools, a sibling
``.venv`` is auto-detected and used when the invoking interpreter lacks
spaCy.

Usage:
    python3 class_profile.py --file essays/
    python3 class_profile.py --file "articles/*.txt" --target-level B1
    python3 class_profile.py --file essays/ --format csv
    python3 class_profile.py --file essays/ --max-level B1 --sort typical
    python3 class_profile.py --file essays/ --export-vocab vocab-lists/
    echo "The cat sat on the mat." | python3 class_profile.py

Flags:
    --file            a directory, a glob (recursive with **), or a single
                      .txt/.md/.docx/.pdf file to profile (batch input)
    --text            inline text to analyse (a one-text set)
    --format          auto | json | pretty | csv  (default: auto — a colour
                      terminal view when stdout is a TTY, JSON when
                      piped/redirected; csv is the spreadsheet-ready summary)
    --target-level    the class's CEFR level (A1–C2): adds each text's
                      %-above-target and a fits/no-fits verdict
    --targets         comma-separated CEFR levels (e.g. A2,B1,B2): show each
                      text's fits / %-above verdict for every level, side by
                      side (instead of --target-level)
    --min-level       keep only texts whose estimated level is at/above this
    --max-level       keep only texts whose estimated level is at/below this
                      (--max-level B1 = "which of these suits B1?")
    --sort            level (default) | typical | reached | words | name —
                      rank the set (level = estimated level, A1 first)
    --export-vocab    write one CSV per CEFR band (distinct words ×
                      occurrences × text count) into the given directory
    --export          csv | md | flashcards — write a per-text pre-teaching
                      list (like text_report's) for every text in the set,
                      next to each source (requires --target-level)
    --cloze           --export md|csv only: render exported examples as
                      {{...}} fill-the-gap sentences (RubricMaker syntax)
    --no-enrich       --export flashcards only: skip the Free Dictionary API
                      (card backs stay the in-text context sentence)
    --output          --export only: write all lists into this directory
                      (default: next to each source file)
    --pre-enrich      prime the dictionary cache from the whole folder's
                      distinct vocabulary in one polite, rate-limited pass,
                      then exit (no report, no export)
    --delay           --pre-enrich only: seconds between requests
                      (default 0.25; 0 for none)
    --limit           --pre-enrich only: cap the number of new lookups
    --dictionary-cache  JSON cache file for dictionary lookups (default:
                      ~/.cache/vocabkitchen/dictionary.json)
    --no-dictionary-cache  --pre-enrich and --export flashcards only: don't
                      read or write the lookup cache
    --dictionary-url  override the dictionary API base URL (proxy/test server)
    --no-grammar      skip the grammar side even if spaCy is available
    --wordlists       override the vocabulary word-list directory
    --grammar-profile override the CEFR-J grammar-profile directory
    (stdin)           if neither --file nor --text is given, text is read
                      from stdin

Output: with --format json, a JSON object with the per-text ``rows`` (each
carrying vocabulary typical/reached, grammar typical/reaches when available,
estimated level, above-target % and fits verdict), the pooled ``aggregate``
distribution, the ``skipped`` files, and the sort/filter settings. With
--format csv, one row per text, header included, ready for a spreadsheet.
With --format pretty, a colour-coded terminal view: aggregate distribution
bar + the ranked table.
"""

import argparse
import csv
import glob
import io
import json
import os
import re
import sys

import vocab_profile as vp
import grammar_profile as gp
import text_report as tr

_CEFR_ORDER = vp.CEFR_ORDER
_LEVEL_INDEX = {lvl: i for i, lvl in enumerate(_CEFR_ORDER)}
_DIM_RGB = (136, 136, 136)

# Extensions the folder/glob scan picks up — the same ones extract_text knows.
_SUPPORTED_EXTS = {".txt", ".md", ".markdown", ".docx", ".pdf"}
_GLOB_META = set("*?[")

_SORT_KEYS = ("level", "typical", "reached", "words", "name")


class ClassProfileError(Exception):
    """Fatal input/usage error — printed to stderr, exit code 1."""


# ---------------------------------------------------------------------------
# venv re-exec — mirrors text_report._maybe_reexec_in_venv so the batch run
# "just works" when spaCy lives in a sibling .venv even though the invoking
# python is the system interpreter.
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
    if os.environ.get("_CLASS_PROFILE_REEXEC"):
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
        env = dict(os.environ, _CLASS_PROFILE_REEXEC="1")
        try:
            os.execve(py, [py, os.path.abspath(__file__)] + sys.argv[1:], env)
        except OSError:
            return  # fall through to the graceful no-spaCy path


# ---------------------------------------------------------------------------
# Input discovery — --file takes a directory, a glob, or a single file
# ---------------------------------------------------------------------------

_ARTIFACT_RE = re.compile(
    r"-(?:preteaching|summary)-[A-C][12](?:-(?:deck|index))?\.(?:md|csv)$")


def is_export_artifact(name):
    """True for files this tool writes (``<stem>-preteaching-<LEVEL>.md``,
    ``-deck.csv``, ``-index.md``, ``<set>-summary-<LEVEL>.md``) so a re-run
    over the same folder doesn't re-profile its own handouts."""
    return bool(_ARTIFACT_RE.search(name))


def discover_files(spec):
    """Resolve a --file value to an ordered list of files to profile.

    A directory yields its supported text files (top level, sorted, hidden
    files and the tool's own export artifacts skipped); a glob (any of ``*?[``)
    is expanded with ``**`` recursion; anything else is treated as a single
    file. Raises :class:`ClassProfileError` when nothing resolves.
    """
    if os.path.isdir(spec):
        found = []
        for name in sorted(os.listdir(spec)):
            if name.startswith(".") or is_export_artifact(name):
                continue
            full = os.path.join(spec, name)
            if (os.path.isfile(full)
                    and os.path.splitext(name)[1].lower() in _SUPPORTED_EXTS):
                found.append(full)
        if not found:
            raise ClassProfileError(
                f"No supported text files ({', '.join(sorted(_SUPPORTED_EXTS))}) "
                f"found in '{spec}'.")
        return found
    if any(c in spec for c in _GLOB_META):
        # Python's glob, unlike the shell, matches dotfiles — skip them so the
        # glob scan agrees with the directory scan.
        found = sorted(p for p in glob.glob(spec, recursive=True)
                       if os.path.isfile(p)
                       and not os.path.basename(p).startswith(".")
                       and not is_export_artifact(os.path.basename(p)))
        if not found:
            raise ClassProfileError(f"Glob '{spec}' matched no files.")
        return found
    if not os.path.exists(spec):
        raise ClassProfileError(f"Could not read file '{spec}': file not found.")
    return [spec]


def _parse_level(value, flag):
    """Validate a --target/--min/--max level; raise ClassProfileError on a bad one."""
    lvl = value.strip().upper()
    if lvl not in _LEVEL_INDEX:
        raise ClassProfileError(
            f"Invalid {flag} level '{value}'. Valid: {', '.join(_CEFR_ORDER)}.")
    return lvl


def resolve_format(explicit, is_tty):
    """Resolve --format: auto by TTY (pretty) vs pipe (json); csv is explicit only."""
    if explicit in (None, "", "auto"):
        return "pretty" if is_tty else "json"
    value = explicit.strip().lower()
    if value == "json":
        return "json"
    if value == "csv":
        return "csv"
    if value in ("pretty", "text"):
        return "pretty"
    raise ClassProfileError(
        f"Unknown format '{explicit}'. Valid formats: auto, json, pretty, csv.")


# ---------------------------------------------------------------------------
# Per-text profiling — vocabulary always (dependency-free), grammar when the
# engine is available. Mirrors text_report.analyze's per-side logic so the
# numbers mean exactly the same thing as the single-text tools.
# ---------------------------------------------------------------------------

def load_grammar_engine(grammar_dir=None):
    """Load spaCy + CEFR-J levels once for the whole set.

    Returns ``(nlp, cefrj_levels)`` or ``(None, note)`` when the engine is
    unavailable (note carries the install guidance from grammar_profile).
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gbase = grammar_dir or os.path.join(script_dir, "GrammarProfile")
        nlp = gp.load_nlp()
        cefrj = gp.load_cefrj_levels(gbase)
        return nlp, cefrj
    except gp.EngineError as ex:
        return None, str(ex).strip()


def grammar_levels_for(text, nlp, cefrj_levels):
    """(estimatedLevel, results, meta, error) for one text.

    ``results``/``meta`` are the full grammar profiler payload — kept for the
    per-text ``--export`` mode; ``error`` explains an unparseable input.
    """
    if nlp is None:
        return None, None, None, None
    try:
        if len(text) > nlp.max_length:
            raise ValueError(
                f"input too long for the parser ({len(text):,} characters; "
                f"limit {nlp.max_length:,}) — split the text and re-run")
        results, meta = gp.profile(text, nlp, cefrj_levels)
        return meta["estimatedLevel"], results, meta, None
    except ValueError as ex:
        return None, None, None, str(ex).strip()


def _target_outcomes(ordered, targets, estimated):
    """Per-target %-above-target and fits verdicts for one text.

    The %-above is the complement of text_report's coverage figure — the
    share of recognised running words above the class's level. "Fits" means
    the text's estimated level is at or below the target band.
    """
    out = {}
    for t in targets:
        cov = tr.coverage_figure(ordered, t)
        above = (100 - cov["knownPercent"]) if cov is not None else None
        fits = (estimated is not None
                and _LEVEL_INDEX[estimated] <= _LEVEL_INDEX[t])
        out[t] = {"aboveTargetPercent": above, "fits": fits}
    return out


def build_row(text, label, levels, nlp, cefrj_levels, with_grammar, targets):
    """Profile in-memory *text*; return ``(row, ordered, ctx)``.

    *ordered* is vocab_profile's per-level result (level → word × occurrences)
    — the caller folds it into the pooled aggregate. *targets* is a single
    CEFR level, a list of them, or None: with one level the row carries the
    singular ``aboveTargetPercent``/``fits`` fields; with several, a
    per-target ``targets`` map. *ctx* holds the text and the full grammar
    payload so the per-text ``--export`` mode can reuse text_report's writers
    verbatim. Raises nothing; reading the text itself is the caller's job.
    """
    if isinstance(targets, str):
        targets = [targets]
    ordered, total = vp.profile(text, levels)
    counts = {name: sum(occ for _w, occ in rows) for name, _pct, rows in ordered}
    _c, typical, coverage = vp.cefr_stats(ordered, total)
    off_list_percent = (round(counts.get("Off List", 0) / total * 100)
                        if total else 0)

    grammar = None
    grammar_error = None
    grammar_results = grammar_meta = None
    if with_grammar:
        g_est, grammar_results, grammar_meta, grammar_error = \
            grammar_levels_for(text, nlp, cefrj_levels)
        if g_est is not None:
            grammar = {"typical": g_est["typical"], "reaches": g_est["reaches"]}

    # Blended estimated level — the same number text_report reports: the
    # higher of the vocab 90%-coverage band and the grammar typical band.
    # Without grammar it falls back to the vocab coverage band.
    g_typical = grammar["typical"] if grammar else None
    estimated = tr.blend_level(coverage, g_typical)

    above_target_pct = None
    fits = None
    row_targets = None
    if targets:
        outcomes = _target_outcomes(ordered, targets, estimated)
        if len(targets) == 1:
            t = targets[0]
            above_target_pct = outcomes[t]["aboveTargetPercent"]
            fits = outcomes[t]["fits"]
        else:
            row_targets = outcomes

    row = {
        "file": label,
        "totalWordCount": total,
        "vocabulary": {"typical": typical, "coverage": coverage,
                       "offListPercent": off_list_percent},
        "grammar": grammar,
        "grammarError": grammar_error,
        "estimatedLevel": estimated,
        "aboveTargetPercent": above_target_pct,
        "fits": fits,
        "targets": row_targets,
    }
    ctx = {
        "text": text,
        "grammar_results": grammar_results,
        "grammar_meta": grammar_meta,
        "grammar_error": grammar_error,
    }
    return row, ordered, ctx


def profile_file(path, label, levels, nlp, cefrj_levels, with_grammar, targets):
    """Read *path* and build its row; raises DocumentError on unreadable text."""
    text = vp.extract_text(path)
    return build_row(text, label, levels, nlp, cefrj_levels, with_grammar, targets)


# ---------------------------------------------------------------------------
# Pooled aggregate — the dashboard's headline: the CEFR distribution of the
# whole set's words, plus the distinct-word index the band export uses.
# ---------------------------------------------------------------------------

def new_aggregate():
    """A fresh aggregate: level counts, distinct-word index, running total."""
    return {"counts": {}, "words": {}, "total": 0}


def add_to_aggregate(agg, ordered):
    """Fold one text's profile (vocab_profile's ordered result) into *agg*."""
    for name, _pct, rows in ordered:
        n = sum(occ for _w, occ in rows)
        agg["counts"][name] = agg["counts"].get(name, 0) + n
        agg["total"] += n
        bucket = agg["words"].setdefault(name, {})
        for word, occ in rows:
            info = bucket.get(word)
            if info is None:
                bucket[word] = {"occurrences": occ, "texts": 1}
            else:
                info["occurrences"] += occ
                info["texts"] += 1


def aggregate_summary(agg):
    """The pooled distribution: typical/coverage bands + per-level stats."""
    ordered = ([(lvl, "", [("", agg["counts"].get(lvl, 0))]) for lvl in _CEFR_ORDER]
               + [("Off List", "", [("", agg["counts"].get("Off List", 0))])])
    _c, typical, coverage = vp.cefr_stats(ordered, agg["total"])
    off_pct = (round(agg["counts"].get("Off List", 0) / agg["total"] * 100)
               if agg["total"] else 0)
    levels = {}
    for lvl in _CEFR_ORDER + ["Off List"]:
        n = agg["counts"].get(lvl, 0)
        levels[lvl] = {
            "percentage": vp.format_percentage(n, agg["total"]),
            "wordCount": n,
            "distinctWordCount": len(agg["words"].get(lvl, {})),
        }
    return {
        "totalWordCount": agg["total"],
        "typical": typical,
        "coverage": coverage,
        "offListPercent": off_pct,
        "levels": levels,
    }


# ---------------------------------------------------------------------------
# Rank & filter
# ---------------------------------------------------------------------------

def _level_rank(lvl):
    """Sort rank of a CEFR level; unknown ('—') sorts after C2."""
    return _LEVEL_INDEX[lvl] if lvl in _LEVEL_INDEX else len(_CEFR_ORDER)


def sort_rows(rows, key):
    """Sort *rows* by *key* ('level'|'typical'|'reached'|'words'|'name')."""
    def k(row):
        if key == "name":
            return (row["file"].lower(),)
        if key == "words":
            return (-row["totalWordCount"], row["file"].lower())
        if key == "typical":
            return (_level_rank(row["vocabulary"]["typical"]), row["file"].lower())
        if key == "reached":
            return (_level_rank(row["vocabulary"]["coverage"]), row["file"].lower())
        # level — the blended estimated level (A1 first)
        return (_level_rank(row["estimatedLevel"]), row["file"].lower())
    return sorted(rows, key=k)


def filter_rows(rows, min_level, max_level):
    """Keep only rows whose estimated level is within [min_level, max_level].

    Rows without an estimated level ('—') never match a filter — they can't
    be said to fit any band.
    """
    min_idx = _LEVEL_INDEX[min_level] if min_level else None
    max_idx = _LEVEL_INDEX[max_level] if max_level else None
    if min_idx is None and max_idx is None:
        return list(rows)
    out = []
    for row in rows:
        est = row["estimatedLevel"]
        if est is None or est not in _LEVEL_INDEX:
            continue
        idx = _LEVEL_INDEX[est]
        if (min_idx is None or idx >= min_idx) and (max_idx is None or idx <= max_idx):
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# Output — CSV (the spreadsheet artefact), JSON, and a colour-coded terminal
# ---------------------------------------------------------------------------

def rows_to_csv(rows, target, targets=None):
    """One row per text, header included, ready for a spreadsheet.

    With a single *target* the row adds ``above_target_pct`` + ``fits``; with
    *targets* (several levels) it adds a ``fits_<L>``/``above_pct_<L>`` pair
    per level so the set can be compared across classes side by side.
    """
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    header = ["file", "total_words", "vocab_typical", "vocab_reached",
              "grammar_typical", "grammar_reaches", "estimated_level"]
    if target is not None:
        header += ["above_target_pct", "fits"]
    if targets:
        for t in targets:
            header += [f"fits_{t}", f"above_pct_{t}"]
    w.writerow(header)
    for r in rows:
        g = r["grammar"]
        fields = [r["file"], r["totalWordCount"],
                  r["vocabulary"]["typical"], r["vocabulary"]["coverage"],
                  g["typical"] if g else "", g["reaches"] if g else "",
                  r["estimatedLevel"] or ""]
        if target is not None:
            fields += [
                r["aboveTargetPercent"] if r["aboveTargetPercent"] is not None else "",
                "yes" if r["fits"] else ("no" if r["fits"] is False else ""),
            ]
        if targets:
            for t in targets:
                o = (r.get("targets") or {}).get(t) or {}
                fields += [
                    "yes" if o.get("fits") else ("no" if o.get("fits") is False else ""),
                    o.get("aboveTargetPercent") if o.get("aboveTargetPercent") is not None else "",
                ]
        w.writerow(fields)
    return buf.getvalue()


def _cell(text, width, align="left", paint=None):
    """Pad *text* to *width* (plain length), optionally applying *paint* first."""
    shown = paint(text) if paint else text
    pad = width - len(text)
    if pad <= 0:
        return shown
    if align == "right":
        return " " * pad + shown
    if align == "center":
        left = pad // 2
        return " " * left + shown + " " * (pad - left)
    return shown + " " * pad


def _truncate(text, width):
    return text if len(text) <= width else text[:width - 1] + "…"


def _distribution_bar(counts, total, width, colour):
    """Pooled-CEFR bar + legend, using the profilers' level palette."""
    segments, legend = [], []
    for lvl in _CEFR_ORDER + ["Off List"]:
        n = counts.get(lvl, 0)
        if n == 0:
            continue
        cells = round(n / total * width) if total else 0
        if cells:
            segments.append(vp.paint(vp.LEVEL_RGB[lvl], "█" * cells, colour))
        pct = round(n / total * 100) if total else 0
        legend.append(vp.paint(vp.LEVEL_RGB[lvl], "■", colour) + f" {lvl} {pct}%")
    return "".join(segments), "   ".join(legend)


def render_pretty(rows, summary, meta, stream=None):
    """Colour-coded terminal view: aggregate distribution + ranked table.

    *meta* carries the run's settings and diagnostics (source, skipped,
    target, sort, min/max level, fits count, grammar note).
    """
    stream = stream or sys.stdout
    colour = vp.use_colour(stream)

    def dim(s):
        return vp.paint(_DIM_RGB, s, colour)

    def bold(s):
        return vp.bold(s, colour)

    def lvl(s):
        return vp.paint(vp.LEVEL_RGB.get(s, _DIM_RGB), s, colour)

    out = []
    out.append(bold("Class Profile"))
    n = meta["texts"]
    out.append(dim(f"Source: {meta['source']} — {n} text"
                   f"{'' if n == 1 else 's'}"))
    if meta["skipped"]:
        names = ", ".join(s["file"] for s in meta["skipped"][:5])
        more = f" (+{len(meta['skipped']) - 5})" if len(meta["skipped"]) > 5 else ""
        out.append(dim(f"  {len(meta['skipped'])} file(s) skipped: {names}{more}"))

    bits = [f"ranked by {meta['sort']}"]
    if meta["target"] is not None:
        bits.insert(0, f"Target {meta['target']} — {meta['fitsCount']} of "
                       f"{meta['texts']} fit")
    elif meta["targets"]:
        parts = [f"{t} {(meta['fitsCount'] or {}).get(t, 0)}/{meta['texts']}"
                 for t in meta["targets"]]
        bits.insert(0, "Targets " + ", ".join(meta["targets"])
                       + " — fits " + " · ".join(parts))
    if meta["min_level"] or meta["max_level"]:
        band = "–".join(x for x in (meta["min_level"], meta["max_level"]) if x)
        n = meta["hidden"]
        bits.append(f"{n} text{'' if n == 1 else 's'} hidden outside {band}")
    out.append(dim(" · ".join(bits)))
    out.append("")

    # Aggregate distribution — the dashboard's headline.
    out.append(bold("Aggregate vocabulary")
               + dim(f" ({meta['selected']} text"
                     f"{'' if meta['selected'] == 1 else 's'}, "
                     f"{summary['totalWordCount']:,} words)"))
    out.append(
        f"  {bold('Typical:')} {lvl(summary['typical'])}"
        f"   {bold('90% coverage:')} {lvl(summary['coverage'])}"
        + (dim(f"   {summary['offListPercent']}% off list")
           if summary["offListPercent"] else ""))
    try:
        import shutil
        width = min(shutil.get_terminal_size((80, 20)).columns, 100)
    except Exception:
        width = 80
    bar, legend = _distribution_bar(
        {lvl: summary["levels"][lvl]["wordCount"] for lvl in _CEFR_ORDER
         + ["Off List"]}, summary["totalWordCount"], min(width, 60), colour)
    if bar:
        out.append("  " + bar)
        out.append("  " + legend)
    out.append("")

    # The per-text table.
    out.append(bold("Texts"))
    headers = ["#", "file", "words", "typical", "reached", "grammar", "est"]
    aligns = ["right", "left", "right", "center", "center", "center", "center"]
    if meta["target"] is not None:
        headers += ["%above", "fits"]
        aligns += ["right", "center"]
    elif meta["targets"]:
        # One column per class level: "✓ 8%" = fits at that level, with the
        # share of recognised running words above it.
        for t in meta["targets"]:
            headers.append(t)
            aligns.append("center")
    cells = []
    for i, r in enumerate(rows, 1):
        g = r["grammar"]
        fields = [str(i), r["file"], f"{r['totalWordCount']:,}",
                  r["vocabulary"]["typical"], r["vocabulary"]["coverage"],
                  (f"{g['typical']}→{g['reaches']}" if g else "—"),
                  r["estimatedLevel"] or "—"]
        if meta["target"] is not None:
            fields += [
                f"{r['aboveTargetPercent']}%" if r["aboveTargetPercent"] is not None else "—",
                "✓" if r["fits"] else ("✗" if r["fits"] is False else "·"),
            ]
        elif meta["targets"]:
            for t in meta["targets"]:
                o = (r.get("targets") or {}).get(t) or {}
                above = o.get("aboveTargetPercent")
                mark = "✓" if o.get("fits") else ("✗" if o.get("fits") is False else "·")
                fields.append(f"{mark} {above}%" if above is not None else mark)
        cells.append(fields)
    widths = []
    for j, header in enumerate(headers):
        w = len(header)
        for f in cells:
            w = max(w, len(f[j]))
        widths.append(w)
    # Keep the file column from dominating narrow terminals.
    widths[1] = min(widths[1], 32)
    out.append("  " + "  ".join(_cell(h, widths[j], aligns[j])
                                for j, h in enumerate(headers)))
    out.append("  " + "  ".join(_cell("─" * w, w, aligns[j])
                                for j, w in enumerate(widths)))
    for f in cells:
        f[1] = _truncate(f[1], widths[1])
        painted = []
        for j, value in enumerate(f):
            if j in (3, 4, 6) and value in vp.LEVEL_RGB:
                painted.append(_cell(value, widths[j], aligns[j], paint=lvl))
            else:
                painted.append(_cell(value, widths[j], aligns[j]))
        out.append("  " + "  ".join(painted))
    if not rows:
        out.append(dim("  no texts match the selected band"))

    if meta["grammar_note"]:
        out.append("")
        out.append(dim("Grammar: " + meta["grammar_note"].splitlines()[0]))
    stream.write("\n".join(out) + "\n")


# ---------------------------------------------------------------------------
# Vocabulary-list export by band — one CSV per CEFR band over the selected set
# ---------------------------------------------------------------------------

def export_vocab_lists(agg_words, out_dir):
    """Write ``vocab-<band>.csv`` per band with distinct words in it.

    Columns: word, occurrences (running words across the set), texts (how
    many of the set's texts contain the word). Returns the written paths.
    """
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for lvl in _CEFR_ORDER + ["Off List"]:
        bucket = agg_words.get(lvl, {})
        if not bucket:
            continue
        rows = sorted(bucket.items(),
                      key=lambda kv: (-kv[1]["occurrences"], kv[0]))
        fname = f"vocab-{lvl.lower().replace(' ', '-')}.csv"
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["word", "occurrences", "texts"])
            for word, info in rows:
                w.writerow([word, info["occurrences"], info["texts"]])
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# Per-text pre-teaching export — reuses text_report's writers verbatim, so a
# folder run produces the same handouts / worksheets / RubricMaker decks as
# the single-text tool, one set per text.
# ---------------------------------------------------------------------------

def export_payload(row, ordered, ctx, target):
    """Build a text_report-shaped payload for one row's text.

    Mirrors ``text_report.analyze``'s output (vocabulary + grammar shapes,
    above-target words with in-text contexts, coverage figure, verdict,
    readability) by composing the same helpers, so ``export_csv`` /
    ``export_markdown`` / ``export_flashcards`` run unmodified — same
    columns, same enrichment, same cloze.
    """
    text = ctx["text"]
    gresults = ctx["grammar_results"]
    gmeta = ctx["grammar_meta"]
    grammar_available = gresults is not None and gmeta is not None

    file_label = row["file"]

    words = tr.words_above_target(ordered, target)
    structures = (tr.structures_above_target(gresults, target)
                  if grammar_available else [])
    if words:
        ctxts = tr.word_contexts(text, [d["word"] for d in words])
        for d in words:
            d["context"] = ctxts.get(d["word"])

    bands = [d["level"] for d in words] + [d["level"] for d in structures]
    return {
        "file": file_label,
        "totalWordCount": row["totalWordCount"],
        "vocabulary": {
            "typical": row["vocabulary"]["typical"],
            "coverage": row["vocabulary"]["coverage"],
            "offListPercent": row["vocabulary"]["offListPercent"],
            "results": vp.results_to_json(ordered),
        },
        "grammar": (gp.results_to_json(gresults, gmeta)
                     if grammar_available else None),
        "grammarError": (None if grammar_available
                         else (ctx["grammar_error"] or "not analysed")),
        "targetLevel": target,
        "aboveTarget": {
            "maxLevel": max(bands, key=lambda lvl: _LEVEL_INDEX[lvl])
                        if bands else None,
            "words": words,
            "wordCount": len(words),
            "structures": structures,
            "structureCount": len(structures),
        },
        "coverage": tr.coverage_figure(ordered, target),
        "verdict": tr.build_verdict(words, structures, grammar_available),
        "readability": tr.compute_readability(text, row["totalWordCount"]),
    }


def folder_vocabulary(profiled):
    """The distinct words across a set of ``(row, ordered, ctx)`` profiles.

    Used by ``--pre-enrich`` to prime the dictionary cache for the whole
    folder's vocabulary in one pass.
    """
    words = set()
    for _row, ordered, _ctx in profiled:
        for _name, _pct, rows in ordered:
            for w, _occ in rows:
                if any(ch.isalpha() for ch in w):
                    words.add(w)
    return sorted(words)


def _combined_deck_payload(payloads):
    """Merge per-text payloads into one class-wide deck payload.

    Distinct above-target words across the set, summed occurrences, the first
    in-text context, and the set of source texts each word appeared in — the
    shape ``text_report.export_flashcards`` reads (it ignores the extra
    ``texts`` key), so the combined deck goes through the identical writer.
    """
    merged = {}
    for p in payloads:
        src = os.path.basename(p.get("file") or "(input)")
        for d in (p.get("aboveTarget") or {}).get("words") or []:
            entry = merged.get(d["word"])
            if entry is None:
                entry = {"word": d["word"], "level": d["level"],
                         "occurrences": 0, "context": d.get("context"),
                         "texts": []}
                merged[d["word"]] = entry
            entry["occurrences"] += d["occurrences"]
            if entry["context"] is None and d.get("context"):
                entry["context"] = d["context"]
            if src not in entry["texts"]:
                entry["texts"].append(src)
    words = sorted(merged.values(),
                   key=lambda d: (-d["occurrences"], d["word"]))
    return {
        "totalWordCount": sum(p.get("totalWordCount", 0) for p in payloads),
        "targetLevel": payloads[0].get("targetLevel") if payloads else None,
        "aboveTarget": {"words": words, "wordCount": len(words)},
    }


def _set_name(source_label):
    """The set's name for file naming: the source folder's basename, else
    ``class`` (glob/stdin/single-file input)."""
    if source_label and os.path.isdir(source_label):
        base = os.path.basename(os.path.normpath(source_label))
        if base and base not in (".", os.sep):
            return base
    return "class"


def combined_deck_path(source_label, target, output_dir):
    """Where the class-wide combined deck goes.

    Named after the source folder (``essays-preteaching-B1-deck.csv``), or
    ``class-…`` for glob/stdin input; into ``--output`` when given, else next
    to the source folder, else the current directory.
    """
    fname = f"{_set_name(source_label)}-preteaching-{target}-deck.csv"
    if output_dir:
        return os.path.join(output_dir, fname)
    if source_label and os.path.isdir(source_label):
        return os.path.join(source_label, fname)
    return fname


def combined_index_path(source_label, target, output_dir):
    """Where the combined deck's markdown index goes — its deck path with a
    ``-index.md`` suffix (``essays-preteaching-B1-index.md``)."""
    deck = combined_deck_path(source_label, target, output_dir)
    return deck[:-len("-deck.csv")] + "-index.md"


def combined_index_markdown(words, target):
    """A handout-style markdown index for one combined deck: every word with
    its CEFR level and the texts it came from
    (``Word | Level | Occurrences | Texts``) — doubles as a level-keyed
    glossary."""
    lines = [f"# Vocabulary index — above {target}", ""]
    if not words:
        lines.append("No words above the target in this set.")
        lines.append("")
    else:
        lines.append("| Word | Level | Occurrences | Texts |")
        lines.append("|---|---|---|---|")
        for d in words:
            lines.append(f"| {d['word']} | {d.get('level', '')} | "
                         f"{d['occurrences']} | {', '.join(d.get('texts') or [])} |")
        lines.append("")
    lines.append("_Generated by class_profile.py · VocabKitchen._")
    return "\n".join(lines) + "\n"


def set_summary_path(source_label, target, output_dir):
    """Where the set-level summary handout goes — named after the source
    folder like the combined deck (``essays-summary-B1.md``)."""
    fname = f"{_set_name(source_label)}-summary-{target}.md"
    if output_dir:
        return os.path.join(output_dir, fname)
    if source_label and os.path.isdir(source_label):
        return os.path.join(source_label, fname)
    return fname


def set_summary_markdown(rows, summary, payloads, target):
    """One handout for the whole set, aggregating the per-text lists:
    the pooled distribution plus a per-text table and per-text verdicts
    (fits / reaches-X with the %-above) — the ``--export md|csv`` counterpart
    of the combined flashcard deck."""
    n = len(rows)
    lines = [f"# Set summary — Target {target} ({n} text{'s' if n != 1 else ''})", ""]
    lines.append(
        f"**Aggregate vocabulary:** {summary['totalWordCount']:,} words · "
        f"Typical {summary['typical']} · 90% coverage {summary['coverage']}"
        + (f" · {summary['offListPercent']}% off list"
           if summary["offListPercent"] else ""))
    lines.append("")
    lines.append("| Text | Words | Vocab typical | Vocab reached | Grammar | "
                 "Est. | % above | Fits |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        g = r["grammar"]
        grammar = f"{g['typical']}→{g['reaches']}" if g else "—"
        above = (f"{r['aboveTargetPercent']}%"
                 if r["aboveTargetPercent"] is not None else "—")
        fits = "✓" if r["fits"] else ("✗" if r["fits"] is False else "·")
        lines.append(f"| {os.path.basename(r['file'])} | {r['totalWordCount']} | "
                     f"{r['vocabulary']['typical']} | {r['vocabulary']['coverage']} | "
                     f"{grammar} | {r['estimatedLevel'] or '—'} | {above} | {fits} |")
    lines.append("")
    lines.append("**Per text:**")
    for r, p in zip(rows, payloads):
        above = r["aboveTargetPercent"]
        above_txt = f" ({above}% above)" if above is not None else ""
        verdict = p.get("verdict") or ("on level" if r["fits"] else "—")
        lines.append(f"- `{os.path.basename(r['file'])}` — {verdict}{above_txt}.")
    lines.append("")
    lines.append("_Generated by class_profile.py · VocabKitchen._")
    return "\n".join(lines) + "\n"


def write_per_text_exports(profiled, target, fmt, cloze=False, enrich=True,
                           wordlists_dir=None, output_dir=None,
                           source_label=None, base_url=None, cache_path=None,
                           targets=None, rows=None, summary=None):
    """Write the pre-teaching lists for *profiled* (the selected set).

    With a single *target*: one list per text next to its source (or into
    *output_dir*) using text_report's naming — ``<stem>-preteaching-
    <LEVEL>.<ext>`` (decks get a ``-deck`` suffix) — plus, for ``--export
    flashcards`` over more than one text, a **combined class-wide deck** of
    all above-target words across the set; for ``--export md|csv`` over more
    than one text, a **set-level summary handout** (``essays-summary-B1.md``)
    aggregating the pooled distribution and each text's verdict.

    With *targets* (several levels) and ``--export flashcards``: one
    **combined deck per level** (``essays-preteaching-A2-deck.csv`` …), no
    per-text lists — those are per-level and would explode the folder.

    *rows* (the sorted row dicts) and *summary* (the pooled aggregate) feed
    the set-level handout. Returns ``(written, failed, deck_stats)``;
    ``deck_stats`` aggregates the flashcard enrichment counters across the
    set. *base_url*/*cache_path* override the dictionary API and its JSON
    lookup cache.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = wordlists_dir or os.path.join(script_dir, "WordLists")
    cache_path = cache_path or tr.default_dictionary_cache_path()
    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as ex:
            return [], [("<output dir>", str(ex))], \
                {"enriched": 0, "missed": 0, "offline": False, "cached": 0}
    deck_stats = {"enriched": 0, "missed": 0, "offline": False, "cached": 0}
    written, failed = [], []

    def _write(path, content):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            written.append(path)
        except OSError as ex:
            failed.append((path, str(ex)))

    def _fold_stats(stats):
        for k in deck_stats:
            if isinstance(stats[k], bool):
                deck_stats[k] = deck_stats[k] or stats[k]
            else:
                deck_stats[k] += stats[k]

    def _deck(payload):
        content, stats = tr.export_flashcards(
            payload, enrich=enrich, base_url=base_url,
            level_index=vp.load_level_index(base_dir), cache_path=cache_path)
        _fold_stats(stats)
        return content

    if targets and fmt == "flashcards":
        # One combined class-wide deck (plus its markdown index) per level,
        # no per-text lists.
        for t in targets:
            payloads = [export_payload(row, ordered, ctx, t)
                        for row, ordered, ctx in profiled]
            combined = _combined_deck_payload(payloads)
            _write(combined_deck_path(source_label, t, output_dir),
                   _deck(combined))
            _write(combined_index_path(source_label, t, output_dir),
                   combined_index_markdown(combined["aboveTarget"]["words"], t))
        return written, failed, deck_stats

    payloads = []
    for row, ordered, ctx in profiled:
        payload = export_payload(row, ordered, ctx, target)
        payloads.append(payload)
        if fmt == "flashcards":
            content = _deck(payload)
        else:
            content = (tr.export_csv(payload, cloze=cloze) if fmt == "csv"
                       else tr.export_markdown(payload, cloze=cloze))
        path = tr.export_path(row["file"], None, target, fmt)
        if output_dir:
            path = os.path.join(output_dir, os.path.basename(path))
        _write(path, content)
    # The class-wide combined deck (plus its markdown index), in addition to
    # the per-text decks.
    if fmt == "flashcards" and len(profiled) > 1:
        combined = _combined_deck_payload(payloads)
        _write(combined_deck_path(source_label, target, output_dir),
               _deck(combined))
        _write(combined_index_path(source_label, target, output_dir),
               combined_index_markdown(combined["aboveTarget"]["words"], target))
    # The set-level summary handout, aggregating the per-text lists.
    if fmt in ("csv", "md") and len(profiled) > 1 and rows is not None and summary is not None:
        payload_by_file = {p["file"]: p for p in payloads}
        ordered_payloads = [payload_by_file[r["file"]] for r in rows]
        _write(set_summary_path(source_label, target, output_dir),
               set_summary_markdown(rows, summary, ordered_payloads, target))
    return written, failed, deck_stats


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main(argv=None):
    _maybe_reexec_in_venv()
    parser = argparse.ArgumentParser(
        add_help=True, description="VocabKitchen class profile — one command over a folder of texts")
    parser.add_argument("--file", default=None,
                        help="a directory, a glob, or a single .txt/.md/.docx/.pdf file")
    parser.add_argument("--text", default=None)
    parser.add_argument("--format", default="auto")
    parser.add_argument("--target-level", dest="target_level", default=None)
    parser.add_argument("--targets", default=None,
                        help="comma-separated CEFR levels (e.g. A2,B1,B2): show each text's "
                             "fits/%above verdict per level, side by side (instead of "
                             "--target-level)")
    parser.add_argument("--min-level", dest="min_level", default=None)
    parser.add_argument("--max-level", dest="max_level", default=None)
    parser.add_argument("--sort", default="level")
    parser.add_argument("--export-vocab", dest="export_vocab", default=None)
    parser.add_argument("--export", choices=["csv", "md", "flashcards"], default=None,
                        help="write a per-text pre-teaching list (like text_report's) for "
                             "every text in the set, next to each source (requires "
                             "--target-level)")
    parser.add_argument("--cloze", action="store_true",
                        help="--export md|csv only: render exported examples as {{...}} "
                             "fill-the-gap sentences (RubricMaker syntax)")
    parser.add_argument("--no-enrich", action="store_true",
                        help="--export flashcards only: skip the Free Dictionary API "
                             "(card backs stay the in-text context sentence)")
    parser.add_argument("--output", default=None,
                        help="--export only: write all lists into this directory "
                             "(default: next to each source file)")
    parser.add_argument("--pre-enrich", action="store_true",
                        help="prime the dictionary cache from the whole folder's distinct "
                             "vocabulary in one polite, rate-limited pass, then exit "
                             "(no report, no export)")
    parser.add_argument("--delay", type=float, default=0.25,
                        help="--pre-enrich only: seconds between dictionary requests "
                             "(politeness; 0 for none)")
    parser.add_argument("--limit", type=int, default=None,
                        help="--pre-enrich only: cap the number of new lookups")
    parser.add_argument("--dictionary-cache", dest="dictionary_cache", default=None,
                        help="JSON cache file for dictionary lookups (default: "
                             "~/.cache/vocabkitchen/dictionary.json)")
    parser.add_argument("--no-dictionary-cache", action="store_true",
                        help="--pre-enrich and --export flashcards only: don't read or write "
                             "the lookup cache")
    parser.add_argument("--dictionary-url", dest="dictionary_url", default=None,
                        help="override the dictionary API base URL (proxy / test server)")
    parser.add_argument("--no-grammar", action="store_true")
    parser.add_argument("--wordlists", default=None)
    parser.add_argument("--grammar-profile", dest="grammar_profile", default=None)
    args = parser.parse_args(argv)

    try:
        out_format = resolve_format(args.format, sys.stdout.isatty())
        target = (_parse_level(args.target_level, "--target-level")
                  if args.target_level else None)
        targets = None
        if args.targets:
            if args.target_level:
                raise ClassProfileError(
                    "Use either --target-level (one class) or --targets "
                    "(several classes side by side), not both.")
            targets = []
            for part in args.targets.split(","):
                part = part.strip().upper()
                if not part:
                    continue
                if part not in _LEVEL_INDEX:
                    raise ClassProfileError(
                        f"Invalid --targets level '{part}'. "
                        f"Valid: {', '.join(_CEFR_ORDER)}.")
                if part not in targets:
                    targets.append(part)
        min_level = (_parse_level(args.min_level, "--min-level")
                     if args.min_level else None)
        max_level = (_parse_level(args.max_level, "--max-level")
                     if args.max_level else None)
        if (min_level and max_level
                and _LEVEL_INDEX[min_level] > _LEVEL_INDEX[max_level]):
            raise ClassProfileError(
                f"--min-level {min_level} is above --max-level {max_level}.")
        sort = args.sort.strip().lower()
        if sort not in _SORT_KEYS:
            raise ClassProfileError(
                f"Unknown --sort '{args.sort}'. Valid: {', '.join(_SORT_KEYS)}.")
        if args.pre_enrich and args.export:
            raise ClassProfileError(
                "--pre-enrich primes the dictionary cache and exits; "
                "it can't be combined with --export (run --pre-enrich once, "
                "then --export answers from the cache).")
        if args.pre_enrich and args.no_dictionary_cache:
            raise ClassProfileError(
                "--pre-enrich writes the dictionary cache; it can't be combined "
                "with --no-dictionary-cache.")
        if args.export == "flashcards":
            # One combined class-wide deck per level under --targets; per-text
            # decks plus one combined deck under --target-level.
            if target is None and not targets:
                raise ClassProfileError(
                    "--export flashcards needs --target-level (per-text decks "
                    "plus one combined class-wide deck) or --targets (one "
                    "combined deck per level).")
        elif args.export is not None:  # csv | md — per-text lists need one level
            if target is None:
                raise ClassProfileError(
                    "--export csv|md requires --target-level (the pre-teaching "
                    "list is the words above a single class level).")
        if args.cloze and args.export is None:
            raise ClassProfileError(
                "--cloze requires --export (it renders the exported examples as "
                "fill-the-gap sentences).")
        if args.cloze and args.export == "flashcards":
            raise ClassProfileError(
                "--cloze applies to the md/csv exports; --export flashcards "
                "produces RubricMaker deck cards instead.")
    except ClassProfileError as ex:
        sys.stderr.write(str(ex) + "\n")
        return 1

    # The levels each row is judged against: one for the singular
    # aboveTargetPercent/fits fields, several for the per-target map.
    profiling_targets = targets if targets else ([target] if target else None)

    # Dictionary lookup cache — skipped entirely under --no-dictionary-cache.
    cache_path = (None if args.no_dictionary_cache
                  else (args.dictionary_cache or tr.default_dictionary_cache_path()))

    # ---- Input: directory | glob | single file | --text | stdin ----------
    paths = []
    single_text = None
    single_label = None
    if args.file:
        try:
            paths = discover_files(args.file)
        except ClassProfileError as ex:
            sys.stderr.write(str(ex) + "\n")
            return 1
        source_label = args.file
    elif args.text is not None:
        single_text = args.text
        single_label = "(text)"
        source_label = "(text)"
    elif not sys.stdin.isatty():
        single_text = sys.stdin.read()
        single_label = "(stdin)"
        source_label = "(stdin)"
    else:
        sys.stderr.write(
            "Usage: class_profile.py --file DIR|GLOB|FILE [--target-level A1|A2|B1|B2|C1|C2] "
            "[--targets A2,B1,B2] [--min-level L] [--max-level L] "
            "[--sort level|typical|reached|words|name] "
            "[--format auto|json|pretty|csv] [--export-vocab DIR] "
            "[--export csv|md|flashcards [--cloze] [--no-enrich] [--output DIR]] "
            "[--pre-enrich [--delay SECONDS] [--limit N]] "
            "[--no-grammar]\n"
        )
        return 1
    if single_text is not None and single_text.strip() == "":
        sys.stderr.write("No analysable text found in the input.\n")
        return 1

    # ---- Word lists + grammar engine (both loaded once) -------------------
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = args.wordlists or os.path.join(script_dir, "WordLists")
    try:
        levels = [(name, vp.load_wordlist(base_dir, rel))
                  for name, rel in vp.PROFILERS["cefr"]]
    except vp.WordListError as ex:
        sys.stderr.write(str(ex) + "\n")
        return 1

    grammar_note = None
    nlp = cefrj_levels = None
    if args.no_grammar:
        grammar_note = "skipped (--no-grammar)"
    else:
        nlp, cefrj_levels = load_grammar_engine(args.grammar_profile)
        if nlp is None:
            grammar_note = cefrj_levels  # the engine's unavailable note

    # ---- Profile everything -------------------------------------------------
    # --pre-enrich only needs the vocabulary, so skip the grammar side.
    with_grammar = not args.no_grammar and not args.pre_enrich
    profiled = []          # (row, ordered, ctx) for each analysable input
    skipped = []
    for path in paths:
        try:
            profiled.append(profile_file(path, path, levels, nlp, cefrj_levels,
                                         with_grammar, profiling_targets))
        except vp.DocumentError as ex:
            skipped.append({"file": path, "error": str(ex)})
    if single_text is not None:
        profiled.append(build_row(single_text, single_label, levels, nlp,
                                  cefrj_levels, with_grammar, profiling_targets))

    if not profiled:
        sys.stderr.write("No analysable text found in any of the inputs."
                         + (" Skipped files: " + "; ".join(
                             f"{s['file']} ({s['error']})" for s in skipped)
                            if skipped else "")
                         + "\n")
        return 1

    # ---- Pre-enrich: prime the dictionary cache for the whole folder -------
    if args.pre_enrich:
        words = folder_vocabulary(profiled)

        def _progress(s):
            sys.stderr.write(
                f"  pre-enriching… {s['looked_up']} looked up "
                f"({s['found']} found, {s['missed']} not found)\n")

        stats = tr.pre_enrich_words(
            words, base_url=args.dictionary_url, cache_path=cache_path,
            delay=args.delay, limit=args.limit, on_progress=_progress)
        tail = " Offline — remaining words left unprimed." if stats["offline"] else ""
        sys.stderr.write(
            f"Pre-enriched {stats['looked_up']} word"
            f"{'s' if stats['looked_up'] != 1 else ''} "
            f"({stats['found']} found, {stats['missed']} not found); "
            f"{stats['skipped']} of {stats['requested']} already cached."
            + tail + "\n")
        return 0

    all_rows = [row for row, _o, _c in profiled]
    selected = filter_rows(all_rows, min_level, max_level)

    # ---- Pooled aggregate over the selected set -----------------------------
    agg = new_aggregate()
    for row, ordered, _ctx in profiled:
        if any(r is row for r in selected):
            add_to_aggregate(agg, ordered)
    summary = aggregate_summary(agg)

    rows = sort_rows(selected, sort)

    # ---- Export vocab lists by band (over the selected set) -----------------
    if args.export_vocab:
        written = export_vocab_lists(agg["words"], args.export_vocab)
        sys.stderr.write(
            f"Wrote {len(written)} vocabulary list{'s' if len(written) != 1 else ''} "
            f"to {args.export_vocab}\n")

    # ---- Output --------------------------------------------------------------
    if target:
        fits_count = sum(1 for r in all_rows if r["fits"] is True)
    elif targets:
        fits_count = {t: sum(1 for r in all_rows
                             if (r.get("targets") or {}).get(t, {}).get("fits") is True)
                      for t in targets}
    else:
        fits_count = None
    payload = {
        "source": source_label,
        "texts": len(all_rows),
        "skipped": skipped,
        "targetLevel": target,
        "targets": targets,
        "minLevel": min_level,
        "maxLevel": max_level,
        "sort": sort,
        "grammarError": grammar_note,
        "fitsCount": fits_count,
        "hiddenByFilter": len(all_rows) - len(selected),
        "aggregate": summary,
        "rows": rows,
    }

    if out_format == "pretty":
        meta = {
            "source": source_label,
            "texts": len(all_rows),
            "selected": len(selected),
            "skipped": skipped,
            "target": target,
            "targets": targets,
            "fitsCount": payload["fitsCount"],
            "sort": sort,
            "min_level": min_level,
            "max_level": max_level,
            "hidden": payload["hiddenByFilter"],
            "grammar_note": grammar_note,
        }
        render_pretty(rows, summary, meta)
    elif out_format == "csv":
        sys.stdout.write(rows_to_csv(rows, target, targets))
        if skipped:
            sys.stderr.write(f"Skipped {len(skipped)} file(s): "
                             + "; ".join(f"{s['file']} ({s['error']})"
                                         for s in skipped) + "\n")
        if payload["hiddenByFilter"]:
            n = payload["hiddenByFilter"]
            sys.stderr.write(f"{n} text{'' if n == 1 else 's'} hidden "
                             "outside the selected band\n")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    # ---- Per-text pre-teaching lists (over the selected set) ----------------
    if args.export:
        selected_profiled = [p for p in profiled if p[0] in selected]
        written, failed, deck_stats = write_per_text_exports(
            selected_profiled, target, args.export, cloze=args.cloze,
            enrich=not args.no_enrich, wordlists_dir=args.wordlists,
            output_dir=args.output, source_label=source_label,
            base_url=args.dictionary_url, cache_path=cache_path, targets=targets,
            rows=rows, summary=summary)
        for path in written:
            sys.stderr.write(f"Wrote pre-teaching list to {path}\n")
        for path, err in failed:
            sys.stderr.write(f"Could not write pre-teaching list {path}: {err}\n")
        if args.export == "flashcards":
            if deck_stats["offline"]:
                sys.stderr.write("Dictionary enrichment unavailable (offline?); "
                                 "decks shipped with in-context backs. "
                                 "Use --no-enrich to silence this.\n")
            elif deck_stats["enriched"] or deck_stats["missed"]:
                cache_clause = (f" ({deck_stats['cached']} from cache)"
                                if deck_stats["cached"] else "")
                sys.stderr.write(
                    f"Dictionary enrichment: {deck_stats['enriched']} definition"
                    f"{'s' if deck_stats['enriched'] != 1 else ''} added"
                    f"{cache_clause}, {deck_stats['missed']} word"
                    f"{'s' if deck_stats['missed'] != 1 else ''} not found.\n")
        if failed:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
