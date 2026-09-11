#!/usr/bin/env python3
"""EFL-Tools vocabulary profiler — pure-Python port (no .NET required).

Determines the vocabulary level of English text against three word lists:

  - CEFR  A1/A2/B1/B2/C1/C2 (language-proficiency scale)
  - AWL   Coxhead's Academic Word List (academic vocabulary or not)
  - NAWL  the New Academic Word List

This is a faithful reimplementation of VocabKitchen's original C# profiler
(CefrProfiler / AwlProfiler / NawlProfiler). It reuses the exact same word-list
.txt files and reproduces the same tokenizer, matching, ordering and
percentage-rounding, so its JSON output matches the original.

The core profiler has no third-party dependencies — only the Python 3 standard
library. It reads plain text, Markdown, and Word .docx files with the stdlib
alone; PDF input additionally needs the optional ``pypdf`` package.

Usage:
    python3 vocab_profile.py --type cefr --text "The cat sat on the mat."
    python3 vocab_profile.py --type all  --file essay.pdf
    echo "She analysed it." | python3 vocab_profile.py --type awl

Flags:
    --type        cefr | awl | nawl | all  (default: all; also accepts a
                  comma-separated list, e.g. cefr,awl)
    --format      auto | json | pretty  (default: auto — a colour terminal view
                  when stdout is a TTY, JSON when piped/redirected)
    --text        inline text to analyse
    --file        path to a .txt, .md, .docx, or .pdf file to analyse
    --wordlists   directory holding the CEFR/AWL/NAWL word-list folders
                  (default: the WordLists folder next to this script)
    (stdin)       if neither --text nor --file is given, text is read from stdin

Output: with --format json, JSON on stdout (a totalWordCount plus, per profiler,
each level's percentage, word count, and the distinct words in that level ranked
by number of occurrences; words not in any list appear under "Off List"). With
--format pretty, a colour-coded terminal view of the CEFR breakdown.
"""

import argparse
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN

# ---------------------------------------------------------------------------
# Tokenizer — mirrors VkCore.Models.Profiler.PunctuationTokenizer
#
# The original replaces punctuation with placeholder tokens (e.g. "00fullstop00")
# in a fixed order, then splits on runs of non-alphanumeric characters. The
# placeholder tokens survive the split and are later recognised as punctuation
# (and therefore excluded from the word count).
# ---------------------------------------------------------------------------

# (regex pattern, placeholder-core) in the exact order of the C# Mappings dict.
_MAPPINGS = [
    (r"\r\n|\n", "00linebreak00"),
    (r"\. ", "00fullstop00"),
    (r"\.", "00decimal00"),
    (r"\, ", "00comma00"),
    (r"\,", "00quotedcomma00"),
    (r"\: ", "00colon00"),
    (r"\:", "00timecolon00"),
    (r"\? ", "00questionmark00"),
    (r"\!", "00exclamationpoint00"),
    (r"\%", "00percentsign00"),
    (r"\—", "00emdash00"),
    (r"\’ ", "00possessivecurlyquote00"),
    (r"\’", "00curlyquote00"),
    (r"\-", "00hyphen00"),
    (r" \'", "00leftsinglequote00"),
    (r"\' ", "00rightsinglequote00"),
    (r"\'", "00apostrophe00"),
    (r"\" ", "00rightdoublequote00"),
    (r" \"", "00leftdoublequote00"),
    (r" \“", "00openquote00"),
    (r"\” ", "00closequote00"),
    (r" \(", "00openparenthesis00"),
    (r"\) ", "00closeparenthesis00"),
    (r"\; ", "00semicolon00"),
    (r"\>", "00greaterthan00"),
    (r"\<", "00lessthan00"),
    (r"\?", "00quotedquestion00"),
]

_COMPILED = [(re.compile(pat), " " + core + " ") for pat, core in _MAPPINGS]

# The set of placeholder cores — any token equal to one of these is punctuation.
_PLACEHOLDERS = frozenset(core for _, core in _MAPPINGS)

_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")


def tokenize(text):
    """Return the list of tokens (words + punctuation placeholders)."""
    if text is None or text.strip() == "":
        return []
    for regex, replacement in _COMPILED:
        text = regex.sub(replacement, text)
    return [t for t in _SPLIT_RE.split(text) if t]


# ---------------------------------------------------------------------------
# Percentage formatting — mirrors ProfilerHtmlBuilder.RoundPercentage
#
# The C# code computes numerator/denominator as a double, casts to decimal
# (which keeps ~15 significant digits), rounds to 2 decimal places using
# banker's rounding (MidpointRounding.ToEven), then formats as an integer
# percentage. Because rounding to 2 decimals is the same as rounding to whole
# percents, no further rounding happens at the formatting stage.
# ---------------------------------------------------------------------------

def format_percentage(numerator, denominator):
    if denominator == 0:
        return "0%"
    average = numerator / denominator  # IEEE-754 double, as in C#
    # (decimal)average keeps ~15 significant digits; emulate that before rounding.
    dec = Decimal(f"{average:.15g}")
    rounded = dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    percent = (rounded * 100).to_integral_value()
    return f"{int(percent)}%"


# ---------------------------------------------------------------------------
# Document text extraction — plain text, Markdown, Word .docx, PDF
# ---------------------------------------------------------------------------

class DocumentError(Exception):
    """Raised when an input file cannot be read or yields no analysable text."""


def _read_plain(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Markdown -> prose. Not a full parser: it drops the syntax that would otherwise
# be profiled as vocabulary (fences, markers, URLs) while keeping the words.
_MD_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MD_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_MD_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_MD_LIST_MARKER_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+", re.MULTILINE)
_MD_HR_RE = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_|~~)")


def _read_markdown(path):
    md = _read_plain(path)
    md = _MD_FENCE_RE.sub(" ", md)
    md = _MD_IMAGE_RE.sub(r"\1", md)
    md = _MD_LINK_RE.sub(r"\1", md)
    md = _MD_INLINE_CODE_RE.sub(r"\1", md)
    md = _MD_HTML_TAG_RE.sub(" ", md)
    md = _MD_HR_RE.sub(" ", md)
    md = _MD_HEADING_RE.sub("", md)
    md = _MD_BLOCKQUOTE_RE.sub("", md)
    md = _MD_LIST_MARKER_RE.sub("", md)
    md = _MD_EMPHASIS_RE.sub("", md)
    md = md.replace("|", " ")  # table cell separators
    return md


# .docx is a zip of XML; the visible text lives in word/document.xml as <w:t>
# nodes grouped into <w:p> paragraphs. Extract it with the stdlib alone.
_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _read_docx(path):
    import zipfile
    import xml.etree.ElementTree as ET

    try:
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                root = ET.parse(f).getroot()
    except (zipfile.BadZipFile, KeyError) as ex:
        raise DocumentError(f"'{path}' is not a readable .docx file: {ex}")

    paragraphs = []
    for para in root.iter(_DOCX_NS + "p"):
        runs = []
        for node in para.iter():
            tag = node.tag
            if tag == _DOCX_NS + "t" and node.text:
                runs.append(node.text)
            elif tag == _DOCX_NS + "tab":
                runs.append(" ")
            elif tag == _DOCX_NS + "br":
                runs.append("\n")
        paragraphs.append("".join(runs))
    return "\n".join(paragraphs)


def _read_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # older name, same API
        except ImportError:
            raise DocumentError(
                "Reading PDF files needs the optional 'pypdf' package. "
                "Install it with:  pip install pypdf"
            )
    try:
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except DocumentError:
        raise
    except Exception as ex:  # pypdf raises a variety of parse errors
        raise DocumentError(f"Could not read PDF '{path}': {ex}")


_EXTRACTORS = {
    ".md": _read_markdown,
    ".markdown": _read_markdown,
    ".docx": _read_docx,
    ".pdf": _read_pdf,
}


def extract_text(path):
    """Read *path* and return its text, dispatching on file extension.

    ``.md``/``.markdown``, ``.docx`` and ``.pdf`` get dedicated extractors; any
    other extension (including ``.txt``) is read as UTF-8 text. Raises
    :class:`DocumentError` for unreadable files or ones with no analysable text.
    """
    if not os.path.exists(path):
        raise DocumentError(f"Could not read file '{path}': file not found.")

    ext = os.path.splitext(path)[1].lower()
    extractor = _EXTRACTORS.get(ext, _read_plain)
    try:
        text = extractor(path)
    except DocumentError:
        raise
    except (IOError, OSError, UnicodeDecodeError) as ex:
        raise DocumentError(f"Could not read file '{path}': {ex}")

    if text is None or text.strip() == "":
        hint = (
            " (a scanned or image-only PDF has no text layer; OCR is not performed)"
            if ext == ".pdf" else ""
        )
        raise DocumentError(f"No analysable text found in '{path}'{hint}.")
    return text


# ---------------------------------------------------------------------------
# Profiler
# ---------------------------------------------------------------------------

# Each profiler is (json_key, [(level_name, wordlist_relative_path), ...]).
# Level order matters: CEFR matches the lowest level first.
_PROFILERS = {
    "cefr": [
        ("A1", "CEFR/A1.txt"),
        ("A2", "CEFR/A2.txt"),
        ("B1", "CEFR/B1.txt"),
        ("B2", "CEFR/B2.txt"),
        ("C1", "CEFR/C1.txt"),
        ("C2", "CEFR/C2.txt"),
    ],
    "awl": [("Awl", "AWL/awl.txt")],
    "nawl": [("Nawl", "NAWL/nawl.txt")],
}


class WordListError(Exception):
    """Raised when a word-list file cannot be read (missing/unreadable/non-UTF-8)."""


def load_wordlist(base_dir, rel_path):
    full = os.path.join(base_dir, *rel_path.split("/"))
    try:
        with open(full, encoding="utf-8") as f:
            # Match the C# reader: keep every line as-is (only newline stripped).
            return {line.rstrip("\n").rstrip("\r").lower() for line in f}
    except UnicodeDecodeError as ex:
        raise WordListError(f"Word list '{full}' is not valid UTF-8: {ex}")
    except OSError as ex:
        raise WordListError(f"Could not read word list '{full}': {ex}")


def load_level_index(base_dir):
    """Load the merged word → level index from WordLists/CEFR/levels.json.

    The index (built by build_wordlists.py from the OLP-EN-CEFRJ profiles; see
    WORDLISTS.md) maps each surface form to ``{"level": ..., "pos": ...}`` and
    lets tools answer "what CEFR level is this word?" from bundled data alone
    — no dictionary API. Returns an empty dict when the index is absent.
    """
    path = os.path.join(base_dir, "CEFR", "levels.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        words = data.get("words") if isinstance(data, dict) else None
        return words if isinstance(words, dict) else {}
    except (OSError, ValueError):
        return {}


def profile(text, levels):
    """Run one profiler (list of (level_name, word_set)) over the text.

    Returns (ordered list of (level_name, percentage, rows), total_word_count)
    where rows is a list of (word, occurrences).
    """
    tokens = tokenize(text)

    results = [(name, wordset, {}) for name, wordset in levels]
    off_list = {}
    total = 0

    for token in tokens:
        if token in _PLACEHOLDERS:
            continue  # punctuation, not counted
        total += 1

        lower = token.lower()
        matched = False
        for _name, wordset, counts in results:
            if lower in wordset:
                counts[lower] = counts.get(lower, 0) + 1
                matched = True
                break
        if not matched:
            off_list[lower] = off_list.get(lower, 0) + 1

    ordered = []
    for name, _wordset, counts in results:
        ordered.append((name, format_percentage(sum(counts.values()), total), build_rows(counts)))
    ordered.append(("Off List", format_percentage(sum(off_list.values()), total), build_rows(off_list)))
    return ordered, total


def build_rows(counts):
    """Rows ordered as in the C#: alphabetical by word, then stable-sorted by
    descending occurrences (so ties stay alphabetical)."""
    alpha = sorted(counts.items(), key=lambda kv: kv[0])
    by_count = sorted(alpha, key=lambda kv: kv[1], reverse=True)
    return by_count  # list of (word, occurrences)


def results_to_json(ordered):
    """Shape one profiler's ordered result as the JSON `results[type]` mapping."""
    return {
        name: {
            "percentage": pct,
            "wordCount": sum(occ for _w, occ in rows),
            "words": [{"word": w, "occurrences": occ} for w, occ in rows],
        }
        for name, pct, rows in ordered
    }


# ---------------------------------------------------------------------------
# Pretty terminal rendering (colour-coded, dependency-free ANSI)
# ---------------------------------------------------------------------------

# CEFR level colours, matching the original Vocabkitchen web app (RGB).
_LEVEL_RGB = {
    "A1": (0, 153, 204),
    "A2": (0, 187, 0),
    "B1": (255, 153, 0),
    "B2": (179, 0, 0),
    "C1": (215, 51, 255),
    "C2": (219, 112, 147),
    "Off List": (136, 136, 136),
}
_DEFAULT_RGB = (200, 200, 200)
_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
_COVERAGE_TARGET = 0.90


def _use_colour(stream):
    return stream.isatty() and os.environ.get("NO_COLOR") is None


def _paint(rgb, text, enabled):
    if not enabled:
        return text
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


def _bold(text, enabled):
    return f"\x1b[1m{text}\x1b[0m" if enabled else text


def _cefr_stats(ordered, total):
    """From a CEFR `ordered` result, return (level_counts, typical, coverage)."""
    counts = {name: sum(occ for _w, occ in rows) for name, _pct, rows in ordered}
    bands = [(lvl, counts.get(lvl, 0)) for lvl in _CEFR_ORDER]
    classified = sum(c for _lvl, c in bands)

    if classified == 0:
        return counts, "—", "—"

    # Typical = band with the most words (ties resolve to the lower level).
    typical = max(bands, key=lambda lc: (lc[1], -_CEFR_ORDER.index(lc[0])))[0]

    # Coverage = lowest band at which cumulative coverage reaches the target.
    cumulative = 0
    coverage = next((lvl for lvl, c in reversed(bands) if c > 0), "—")
    for lvl, c in bands:
        cumulative += c
        if cumulative >= classified * _COVERAGE_TARGET:
            coverage = lvl
            break
    return counts, typical, coverage


def _distribution_bar(counts, total, width, colour):
    segments, legend = [], []
    for lvl in _CEFR_ORDER + ["Off List"]:
        c = counts.get(lvl, 0)
        if c == 0:
            continue
        cells = round(c / total * width) if total else 0
        if cells:
            segments.append(_paint(_LEVEL_RGB[lvl], "█" * cells, colour))
        pct = round(c / total * 100) if total else 0
        legend.append(_paint(_LEVEL_RGB[lvl], "■", colour) + f" {lvl} {pct}%")
    return "".join(segments), "   ".join(legend)


def _wrap_words(items, width):
    """Greedy-wrap (visible_text, plain_len) items into lines of at most *width*."""
    lines, cur, cur_len = [], "", 0
    for visible, plain_len in items:
        add = plain_len + (1 if cur else 0)
        if cur and cur_len + add > width:
            lines.append(cur)
            cur, cur_len = visible, plain_len
        else:
            cur = (cur + " " + visible) if cur else visible
            cur_len += add
    if cur:
        lines.append(cur)
    return lines


def _render_highlight(text, cefr_levels, width, colour):
    def level_of(word):
        w = word.lower()
        for name, wordset in cefr_levels:
            if w in wordset:
                return name
        return "Off List"

    def paint_chunk(chunk):
        out = []
        for seg in re.split(r"([A-Za-z0-9]+)", chunk):
            if not seg:
                continue
            if seg.isalnum():
                out.append(_paint(_LEVEL_RGB[level_of(seg)], seg, colour))
            else:
                out.append(seg)
        return "".join(out)

    lines = []
    for para in text.split("\n"):
        chunks = [c for c in para.split(" ") if c]
        items = [(paint_chunk(c), len(c)) for c in chunks]
        lines.extend(_wrap_words(items, width) if items else [""])
    return lines


def render_pretty(source_label, per_type, cefr_levels, text, stream=None):
    """Render a colour-coded CEFR view. *per_type* maps type -> (ordered, total)."""
    stream = stream or sys.stdout
    colour = _use_colour(stream)
    try:
        import shutil
        width = min(shutil.get_terminal_size((80, 20)).columns, 100)
    except Exception:
        width = 80
    out = []

    out.append(_bold("Vocabulary Profile", colour))
    if source_label:
        out.append(_paint(_LEVEL_RGB["Off List"], f"Source: {source_label}", colour))
    out.append("")

    if "cefr" in per_type:
        ordered, total = per_type["cefr"]
        counts, typical, coverage = _cefr_stats(ordered, total)

        out.append(f"{_bold('Total words:', colour)} {total}")
        verdict = (
            f"Most recognised words are {typical}."
            if typical == coverage
            else f"Most words are {typical}; you need {coverage} to cover ~90%."
        )
        out.append(
            f"{_bold('Typical:', colour)} {_paint(_LEVEL_RGB.get(typical, _DEFAULT_RGB), typical, colour)}"
            f"   {_bold('90% coverage:', colour)} {_paint(_LEVEL_RGB.get(coverage, _DEFAULT_RGB), coverage, colour)}"
        )
        out.append(_paint(_LEVEL_RGB["Off List"], verdict, colour))
        out.append("")

        bar, legend = _distribution_bar(counts, total, min(width, 64), colour)
        out.append(bar)
        out.append(legend)
        out.append("")

        for name, pct, rows in ordered:
            if not rows:
                continue
            rgb = _LEVEL_RGB.get(name, _DEFAULT_RGB)
            out.append(_paint(rgb, _bold(name, colour), colour) + f"  {pct}")
            items = []
            for w, occ in rows:
                label = f"{w} ×{occ}" if occ > 1 else w
                items.append((_paint(rgb, label, colour), len(label)))
            for line in _wrap_words(items, width - 2):
                out.append("  " + line)
            out.append("")

        if cefr_levels is not None:
            out.append(_bold("Text", colour))
            out.extend(_render_highlight(text, cefr_levels, width, colour))
            out.append("")

    for t in ("awl", "nawl"):
        if t not in per_type:
            continue
        ordered, _total = per_type[t]
        out.append(_bold(f"{t.upper()} — academic vocabulary", colour))
        # Only the on-list bucket is interesting here; "Off List" is every
        # non-academic word, which would just be noise.
        academic = [(name, pct, rows) for name, pct, rows in ordered
                    if name != "Off List" and rows]
        if not academic:
            out.append(_paint(_LEVEL_RGB["Off List"], "  No academic-list words found.", colour))
        for name, pct, rows in academic:
            words = ", ".join(w for w, _occ in rows)
            out.append(f"  {_bold(name, colour)}  {pct} ({sum(o for _w, o in rows)})")
            for line in _wrap_words([(words, len(words))], width - 4):
                out.append("    " + line)
        out.append("")

    stream.write("\n".join(out) + "\n")


# ---------------------------------------------------------------------------
# Public aliases — the names text_report.py and other consumers use. The
# underscore forms remain as aliases so existing callers keep working.
# ---------------------------------------------------------------------------

#: Punctuation-placeholder tokens the tokenizer produces (excluded from counts).
PLACEHOLDERS = _PLACEHOLDERS
#: CEFR level -> RGB colour for the terminal view.
LEVEL_RGB = _LEVEL_RGB
DEFAULT_RGB = _DEFAULT_RGB
#: The three profilers' (json_key, [(level, wordlist_path), ...]) definitions.
PROFILERS = _PROFILERS
CEFR_ORDER = _CEFR_ORDER
#: Band statistics (level_counts, typical, coverage) from a CEFR ordered result.
cefr_stats = _cefr_stats
#: Whether ANSI colour should be used for *stream* (TTY and not NO_COLOR).
use_colour = _use_colour
#: Paint *text* in an RGB colour when *enabled*.
paint = _paint
#: Bold *text* when *enabled*.
bold = _bold


def resolve_format(explicit, is_tty):
    """Resolve --format: explicit value wins, else auto by TTY (pretty) vs pipe (json)."""
    if explicit in (None, "", "auto"):
        return "pretty" if is_tty else "json"
    value = explicit.strip().lower()
    if value == "json":
        return "json"
    if value in ("pretty", "text"):
        return "pretty"
    raise ValueError(f"Unknown format '{explicit}'. Valid formats: auto, json, pretty.")


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True, description="EFL-Tools vocabulary profiler")
    parser.add_argument("--type", default="all")
    parser.add_argument("--format", default="auto")
    parser.add_argument("--text", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--wordlists", default=None)
    # Allow a bare positional text argument, matching the C# fallback.
    parser.add_argument("positional", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        out_format = resolve_format(args.format, sys.stdout.isatty())
    except ValueError as ex:
        sys.stderr.write(str(ex) + "\n")
        return 1

    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = args.wordlists or os.path.join(script_dir, "WordLists")

    source_label = None
    text = args.text
    if text is None and args.file:
        try:
            text = extract_text(args.file)
            source_label = os.path.basename(args.file)
        except DocumentError as ex:
            sys.stderr.write(str(ex) + "\n")
            return 1
    if text is None and args.positional:
        text = args.positional[0]
    if text is None and not sys.stdin.isatty():
        text = sys.stdin.read()

    if text is None or text.strip() == "":
        sys.stderr.write(
            'Usage: vocab_profile.py [--type cefr|awl|nawl|all] '
            '[--format auto|json|pretty] '
            '[--text "..." | --file path{.txt|.md|.docx|.pdf} | < stdin]\n'
        )
        return 1

    requested = args.type.lower()
    types = list(_PROFILERS.keys()) if requested == "all" else [t.strip() for t in requested.split(",")]

    results = {}
    per_type = {}
    cefr_levels = None
    total_word_count = None
    for t in types:
        if t not in _PROFILERS:
            sys.stderr.write(f"Unknown profiler type '{t}'. Valid types: cefr, awl, nawl, all.\n")
            return 1
        try:
            levels = [(name, load_wordlist(base_dir, rel)) for name, rel in _PROFILERS[t]]
        except WordListError as ex:
            sys.stderr.write(str(ex) + "\n")
            return 1
        ordered, total = profile(text, levels)
        if total_word_count is None:
            total_word_count = total
        results[t] = results_to_json(ordered)
        per_type[t] = (ordered, total)
        if t == "cefr":
            cefr_levels = levels

    if out_format == "pretty":
        render_pretty(source_label, per_type, cefr_levels, text)
    else:
        print(json.dumps({"totalWordCount": total_word_count, "results": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
