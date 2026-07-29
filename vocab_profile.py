#!/usr/bin/env python3
"""VocabKitchen vocabulary profiler — pure-Python port (no .NET required).

Determines the vocabulary level of English text against three word lists:

  - CEFR  A1/A2/B1/B2/C1/C2 (language-proficiency scale)
  - AWL   Coxhead's Academic Word List (academic vocabulary or not)
  - NAWL  the New Academic Word List

This is a faithful reimplementation of VocabKitchen's original C# profiler
(CefrProfiler / AwlProfiler / NawlProfiler). It reuses the exact same word-list
.txt files and reproduces the same tokenizer, matching, ordering and
percentage-rounding, so its JSON output matches the original. It has no
third-party dependencies — only the Python 3 standard library — so it runs on
any Linux/macOS box with python3 installed.

Usage:
    python3 vocab_profile.py --type cefr --text "The cat sat on the mat."
    python3 vocab_profile.py --type all  --file essay.txt
    echo "She analysed it." | python3 vocab_profile.py --type awl

Flags:
    --type        cefr | awl | nawl | all  (default: all; also accepts a
                  comma-separated list, e.g. cefr,awl)
    --text        inline text to analyse
    --file        path to a UTF-8 text file to analyse
    --wordlists   directory holding the CEFR/AWL/NAWL word-list folders
                  (default: the WordLists folder next to this script)
    (stdin)       if neither --text nor --file is given, text is read from stdin

Output is JSON on stdout: a totalWordCount plus, per profiler, each level's
percentage, word count, and the distinct words in that level ranked by number
of occurrences. Words not in any list appear under "Off List".
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


def load_wordlist(base_dir, rel_path):
    full = os.path.join(base_dir, *rel_path.split("/"))
    with open(full, "r", encoding="utf-8") as f:
        # Match the C# reader: keep every line as-is (only newline stripped).
        return {line.rstrip("\n").rstrip("\r").lower() for line in f}


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


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True, description="VocabKitchen vocabulary profiler")
    parser.add_argument("--type", default="all")
    parser.add_argument("--text", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--wordlists", default=None)
    # Allow a bare positional text argument, matching the C# fallback.
    parser.add_argument("positional", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = args.wordlists or os.path.join(script_dir, "WordLists")

    text = args.text
    if text is None and args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        except (IOError, OSError) as ex:
            sys.stderr.write(f"Could not read file '{args.file}': {ex}\n")
            return 1
    if text is None and args.positional:
        text = args.positional[0]
    if text is None and not sys.stdin.isatty():
        text = sys.stdin.read()

    if text is None or text.strip() == "":
        sys.stderr.write(
            'Usage: vocab_profile.py [--type cefr|awl|nawl|all] '
            '[--text "..." | --file path.txt | < stdin]\n'
        )
        return 1

    requested = args.type.lower()
    types = list(_PROFILERS.keys()) if requested == "all" else [t.strip() for t in requested.split(",")]

    results = {}
    total_word_count = None
    for t in types:
        if t not in _PROFILERS:
            sys.stderr.write(f"Unknown profiler type '{t}'. Valid types: cefr, awl, nawl, all.\n")
            return 1
        levels = [(name, load_wordlist(base_dir, rel)) for name, rel in _PROFILERS[t]]
        ordered, total = profile(text, levels)
        if total_word_count is None:
            total_word_count = total
        results[t] = {
            name: {
                "percentage": pct,
                "wordCount": sum(occ for _w, occ in rows),
                "words": [{"word": w, "occurrences": occ} for w, occ in rows],
            }
            for name, pct, rows in ordered
        }

    print(json.dumps({"totalWordCount": total_word_count, "results": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
