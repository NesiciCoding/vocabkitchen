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
only. A small documented drop-list (:data:`_DROPPED`) excludes known
misspellings / non-words in the upstream profiles.

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

# Known misspellings / non-words in the upstream Octanove profile (identified in
# review; e.g. "misdemanour" for "misdemeanour", "porten" for "portend",
# "flatout" for the hyphenated "flat-out"). They must not ship in the lists or
# index; re-running the merge drops them again without manual list surgery.
_DROPPED = frozenset({"porten", "flatout", "misdemanour"})


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
                if not form or form in _DROPPED:
                    continue
                target = phrases if " " in form else words
                if form not in target:
                    target[form] = (level, pos)
    return words, phrases


def build_index(existing, profile_words, profile_phrases):
    """Complete word → {level, pos} index from the merged lists + profiles.

    Every list word appears at its (lowest) list level — iterating the lists
    A1→C2 makes the lowest level win automatically; profile-only words and
    phrases are added with their profile level, and profile POS enriches list
    entries that carry none.
    """
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
    return index


def merge(list_dir, write=True, olp_csv=_DEFAULT_OLP, octanove_csv=_DEFAULT_OCT):
    """Gap-fill the six CEFR lists with the bundled OLP-EN-CEFRJ profiles.

    Returns a stats dict; with ``write=False`` nothing is written (a dry run).
    """
    raw = {lvl: load_list(os.path.join(list_dir, f"{lvl}.txt"))
           for lvl in _LEVELS}
    before = {lvl: len(raw[lvl]) for lvl in _LEVELS}
    # The drop-list applies to the shipped lists too, so re-running the merge
    # removes previously-imported typos instead of only preventing re-adds.
    existing = {lvl: raw[lvl] - _DROPPED for lvl in _LEVELS}
    all_known = set().union(*existing.values())

    profile_words, profile_phrases = parse_profile(olp_csv)
    oct_words, oct_phrases = parse_profile(octanove_csv)
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

        index = build_index(existing, profile_words, profile_phrases)
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
        "before": before,
        "added": {lvl: len(added[lvl]) for lvl in _LEVELS},
        "after": {lvl: len(existing[lvl]) for lvl in _LEVELS},
        "phrases_added": len(phrases_added),
    }


def check(list_dir, olp_csv=_DEFAULT_OLP, octanove_csv=_DEFAULT_OCT):
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

    stats = merge(list_dir, write=False, olp_csv=olp_csv, octanove_csv=octanove_csv)
    parts = [f"{lvl} +{n}" for lvl, n in stats["added"].items() if n]
    if stats["phrases_added"]:
        parts.append(f"{stats['phrases_added']} phrases")
    print("  merge would add: " + (", ".join(parts) if parts else "nothing"))

    # levels.json must exist, parse, carry the right schema, and match exactly
    # what a fresh merge would write — nothing stale, nothing missing.
    index_path = os.path.join(list_dir, "levels.json")
    if os.path.exists(index_path):
        try:
            with open(index_path, encoding="utf-8") as f:
                payload = json.load(f)
        except ValueError as ex:
            print(f"  ! levels.json is not valid JSON: {ex}")
            return problems + 1
        words = payload.get("words") if isinstance(payload, dict) else None
        if not isinstance(words, dict) or not words:
            print("  ! levels.json has no (non-empty) words index — run --merge")
            problems += 1
        elif payload.get("version") != 1:
            print(f"  ! levels.json has version {payload.get('version')!r} "
                  f"(expected 1) — run --merge")
            problems += 1
        else:
            # Rebuild the expected index from the current lists + profiles.
            existing = {lvl: load_list(os.path.join(list_dir, f"{lvl}.txt"))
                        for lvl in _LEVELS}
            pwords, pphrases = parse_profile(olp_csv)
            ow, op = parse_profile(octanove_csv)
            pwords.update(ow)
            pphrases.update(op)
            expected = dict(sorted(build_index(existing, pwords, pphrases).items()))
            if words != expected:
                print("  ! levels.json is stale (differs from a fresh merge) — "
                      "run --merge")
                problems += 1
            else:
                print(f"  levels.json: {len(words)} index entries (current)")
    else:
        print("  ! levels.json missing — run: python3 build_wordlists.py --merge")
        problems += 1

    # The synonym-suggestion list (WordLists/synonyms.csv) must agree with
    # levels.json: both words recognised, the level column matching the
    # simpler word's band, and the simpler word strictly lower than the word
    # it replaces — the invariant that makes a suggestion a *simplification*.
    syn_path = os.path.join(os.path.dirname(list_dir), "synonyms.csv")
    if not os.path.exists(syn_path):
        print("  ! synonyms.csv missing — create it alongside the CEFR lists")
        problems += 1
    else:
        index_words = None
        if os.path.exists(index_path):
            try:
                index_words = json.load(open(index_path, encoding="utf-8")).get("words")
            except ValueError:
                index_words = None
        with open(syn_path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows or rows[0][:3] != ["word", "simpler", "level"]:
            print("  ! synonyms.csv must start with a word,simpler,level header")
            problems += 1
        if not isinstance(index_words, dict):
            print("  ! synonyms.csv validation skipped — levels.json unavailable")
        else:
            valid = 0
            for i, row in enumerate(rows[1:], start=2):
                ok = True
                if len(row) != 3 or not all(cell.strip() for cell in row):
                    print(f"  ! synonyms.csv line {i}: expected word,simpler,level")
                    problems += 1
                    continue
                word, simpler = (cell.strip().lower() for cell in row[:2])
                lvl = row[2].strip().upper()
                if lvl not in _LEVELS:
                    print(f"  ! synonyms.csv line {i}: unknown level '{lvl}'")
                    ok = False
                if word not in index_words:
                    print(f"  ! synonyms.csv line {i}: '{word}' not in levels.json")
                    ok = False
                if simpler not in index_words:
                    print(f"  ! synonyms.csv line {i}: '{simpler}' not in levels.json")
                    ok = False
                if not ok:
                    problems += 1
                    continue
                wlvl = index_words[word]["level"]
                slvl = index_words[simpler]["level"]
                if slvl != lvl:
                    print(f"  ! synonyms.csv line {i}: '{simpler}' is {slvl} in "
                          f"levels.json, not {lvl}")
                    problems += 1
                if _LEVELS.index(slvl) >= _LEVELS.index(wlvl):
                    print(f"  ! synonyms.csv line {i}: '{simpler}' ({slvl}) is not "
                          f"simpler than '{word}' ({wlvl})")
                    problems += 1
                valid += 1
            print(f"  synonyms.csv: {valid} of {len(rows) - 1} entries valid")
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
        stats = merge(args.list_dir, write=True,
                      olp_csv=args.olp_csv, octanove_csv=args.octanove_csv)
        print("CEFR lists rebuilt:")
        for lvl in _LEVELS:
            print(f"  {lvl}: {stats['before'][lvl]} -> {stats['after'][lvl]} "
                  f"(+{stats['added'][lvl]} from OLP-EN-CEFRJ)")
        print(f"  phrases in levels.json: +{stats['phrases_added']}")
        return 0
    if args.check:
        return 1 if check(args.list_dir,
                          olp_csv=args.olp_csv, octanove_csv=args.octanove_csv) else 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
