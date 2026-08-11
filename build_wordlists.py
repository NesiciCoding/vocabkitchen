#!/usr/bin/env python3
"""build_wordlists.py — (re)build the CEFR word lists from their sources.

The shipped ``WordLists/CEFR/{A1..C2}.txt`` lists (one word per line, from the
Words-CEFR-Dataset build described in WORDLISTS.md) are **gap-filled** with the
open OLP-EN-CEFRJ profiles, both bundled next to the lists:

  - ``cefrj-vocabulary-profile-1.5.csv``          — CEFR-J A1–B2 (7,798 rows)
  - ``octanove-vocabulary-profile-c1c2-1.0.csv``  — Octanove C1/C2 (2,135 rows)

Merge rule — *existing classifications are authoritative; the profiles only
fill gaps*: a profile headword is added at its level only when it is absent
from all six current lists. Nothing already classified ever moves, so the
profiler's published outputs (and its regression tests) stay stable while
previously unrecognised words gain a level. Slash-separated spelling variants
(``adviser/advisor``) are split; multi-word phrases (``according to``) cannot
be matched by the token profiler, so they land in the machine-readable index
only.

Outputs:

  - ``WordLists/CEFR/{A1..C2}.txt`` — merged lists (sorted, deduped, lowercase)
  - ``WordLists/CEFR/levels.json``  — complete ``word -> {level, pos}`` index,
    the API-free CEFR-level lookup (levels never need a dictionary API).

Usage:
    python3 build_wordlists.py --check              # validate lists + index
    python3 build_wordlists.py --merge              # regenerate from the bundled CSVs
    python3 build_wordlists.py --merge --list-dir DIR --olp-csv X --octanove-csv Y
"""

import argparse
import csv
import json
import os
import sys

_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DIR = os.path.join(_HERE, "WordLists", "CEFR")
_DEFAULT_OLP = os.path.join(_DEFAULT_DIR, "cefrj-vocabulary-profile-1.5.csv")
_DEFAULT_OCT = os.path.join(_DEFAULT_DIR, "octanove-vocabulary-profile-c1c2-1.0.csv")
_PREA1 = {"PRE-A1": "A1", "PREA1": "A1"}


def load_list(path):
    """Read a one-word-per-line list into a set of lowercase words."""
    words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.rstrip("\r\n").strip().lower()
            if w:
                words.add(w)
    return words


def parse_profile(path):
    """Parse an OLP profile CSV into (words, phrases).

    ``words`` maps a single-word surface form to (level, pos); ``phrases``
    does the same for multi-word entries. Slash-separated spelling variants
    are split apart; the level column is normalised to the six CEFR bands.
    """
    words, phrases = {}, {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            head = (row.get("headword") or "").strip().lower()
            if not head:
                continue
            level = (row.get("CEFR") or "").strip().upper()
            level = _PREA1.get(level, level)
            if level not in _LEVELS:
                continue
            pos = (row.get("pos") or "").strip().lower() or None
            for form in (v.strip() for v in head.split("/")):
                if not form:
                    continue
                target = phrases if " " in form else words
                if form not in target:
                    target[form] = (level, pos)
    return words, phrases


def merge(list_dir, write=True):
    """Gap-fill the six CEFR lists with the bundled OLP-EN-CEFRJ profiles.

    Returns a stats dict; with ``write=False`` nothing is written (a dry run).
    """
    existing = {lvl: load_list(os.path.join(list_dir, f"{lvl}.txt"))
                for lvl in _LEVELS}
    all_known = set().union(*existing.values())

    profile_words, profile_phrases = parse_profile(_DEFAULT_OLP)
    oct_words, oct_phrases = parse_profile(_DEFAULT_OCT)
    profile_words.update(oct_words)
    profile_phrases.update(oct_phrases)

    added = {lvl: set() for lvl in _LEVELS}
    for form, (level, _pos) in profile_words.items():
        if form in all_known:
            continue
        existing[level].add(form)
        added[level].add(form)

    phrases_added = {form for form in profile_phrases
                     if form not in all_known}

    if write:
        for lvl in _LEVELS:
            path = os.path.join(list_dir, f"{lvl}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("".join(w + "\n" for w in sorted(existing[lvl])))

        # Complete index: every list word at its (lowest) list level, plus the
        # profile's phrases and any POS the lists can't carry. Iterating the
        # lists A1→C2 makes the lowest level win automatically.
        index = {}
        for lvl in _LEVELS:
            for form in existing[lvl]:
                index.setdefault(form, {"level": lvl, "pos": None})
        for form, (level, pos) in {**profile_words, **profile_phrases}.items():
            entry = index.get(form)
            if entry is None:
                index[form] = {"level": level, "pos": pos}
            elif pos:
                entry["pos"] = pos
        payload = {
            "version": 1,
            "sources": [
                "cefrj-vocabulary-profile-1.5.csv (OLP-EN-CEFRJ, CEFR-J A1-B2)",
                "octanove-vocabulary-profile-c1c2-1.0.csv (OLP-EN-CEFRJ, Octanove C1/C2)",
            ],
            "words": dict(sorted(index.items())),
        }
        index_path = os.path.join(list_dir, "levels.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, ensure_ascii=False)
            f.write("\n")

    return {
        "before": {lvl: len(existing[lvl]) - len(added[lvl]) for lvl in _LEVELS},
        "added": {lvl: len(added[lvl]) for lvl in _LEVELS},
        "after": {lvl: len(existing[lvl]) for lvl in _LEVELS},
        "phrases_added": len(phrases_added),
    }


def check(list_dir):
    """Validate the shipped lists and index; report what a merge would change."""
    problems = 0
    for lvl in _LEVELS:
        path = os.path.join(list_dir, f"{lvl}.txt")
        words = load_list(path)
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\r\n") for ln in f]
        if lines != sorted(lines):
            print(f"  ! {lvl}.txt is not sorted")
            problems += 1
        if len(lines) != len(set(lines)):
            print(f"  ! {lvl}.txt has duplicates")
            problems += 1
        if any(ln != ln.lower() or not ln for ln in lines):
            print(f"  ! {lvl}.txt has non-lowercase or blank lines")
            problems += 1
        print(f"  {lvl}: {len(words)} words")

    stats = merge(list_dir, write=False)
    print("  merge would add: "
          + ", ".join(f"{lvl} +{n}" for lvl, n in stats["added"].items() if n)
          + (f", {stats['phrases_added']} phrases" if stats["phrases_added"] else ""))

    index_path = os.path.join(list_dir, "levels.json")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            payload = json.load(f)
        print(f"  levels.json: {len(payload.get('words', {}))} index entries")
    else:
        print("  ! levels.json missing — run: python3 build_wordlists.py --merge")
        problems += 1
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild/validate the CEFR word lists")
    parser.add_argument("--merge", action="store_true",
                        help="regenerate WordLists/CEFR/*.txt + levels.json from the bundled profiles")
    parser.add_argument("--check", action="store_true",
                        help="validate the current lists and index (no writes)")
    parser.add_argument("--list-dir", default=_DEFAULT_DIR,
                        help="directory holding the CEFR lists and profiles")
    parser.add_argument("--olp-csv", default=_DEFAULT_OLP)
    parser.add_argument("--octanove-csv", default=_DEFAULT_OCT)
    args = parser.parse_args(argv)

    if args.merge:
        stats = merge(args.list_dir, write=True)
        print("CEFR lists rebuilt:")
        for lvl in _LEVELS:
            print(f"  {lvl}: {stats['before'][lvl]} -> {stats['after'][lvl]} "
                  f"(+{stats['added'][lvl]} from OLP-EN-CEFRJ)")
        print(f"  phrases in levels.json: +{stats['phrases_added']}")
        return 0
    if args.check:
        return 1 if check(args.list_dir) else 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
