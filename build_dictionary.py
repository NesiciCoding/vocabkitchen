#!/usr/bin/env python3
"""build_dictionary.py — bundle the Open English WordNet as the offline
definition fallback.

The shipped ``WordLists/dictionary/wordnet.json`` is a **compact, derived**
build of the Open English WordNet 2025 JSON export: for every word, the first
few sense glosses with their part of speech — enough for a definition lookup
when the Free Dictionary API is unreachable or misses, at a fraction of the
upstream file's size. The upstream data is licensed **CC BY 4.0** (see the
``_meta`` block in the output); the build script is the reproducibility
path: re-running it against a downloaded copy regenerates the bundle.

Input — the upstream JSON export (either accepted):

  - ``--input PATH``   a path to the extracted OEWN JSON directory (the
                       ``entries-*.json`` + synset files, as the
                       ``english-wordnet-2025-json.zip`` from
                       https://en-word.net/downloads unpacks), or
  - no input           the script downloads the canonical 2025 JSON zip to
                       a cache dir (``~/.cache/vocabkitchen/``) and unpacks
                       it there — one fetch, then ``--input`` that dir.

Output:

  - ``WordLists/dictionary/wordnet.json`` — ``{"_meta": {...}, "words":
    {"word": [{"definition": "...", "partOfSpeech": "n"}, ...]}}``.

Usage:
    python3 build_dictionary.py --check              # validate the bundle
    python3 build_dictionary.py                      # download + rebuild
    python3 build_dictionary.py --input /tmp/oewn    # rebuild from a local copy
    python3 build_dictionary.py --max-senses 2 --output out.json
"""

import argparse
import json
import os
import sys
import urllib.request
import zipfile

_LEVELS = None  # not needed here; kept for parity with build_wordlists naming

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_OUT = os.path.join(_HERE, "WordLists", "dictionary", "wordnet.json")
_DEFAULT_URL = "https://en-word.net/static/english-wordnet-2025-json.zip"
_VERSION = "Open English WordNet 2025 (2025-12-31)"

_POS_NAME = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective",
             "r": "adverb"}


def _cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") \
        or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "vocabkitchen")


def download(input_url=_DEFAULT_URL, dest_dir=None):
    """Download + unpack the OEWN JSON zip into *dest_dir*; return the dir."""
    dest_dir = dest_dir or os.path.join(_cache_dir(), "oewn-2025")
    if os.path.isdir(dest_dir) and os.path.exists(
            os.path.join(dest_dir, "entries-a.json")):
        return dest_dir
    os.makedirs(dest_dir, exist_ok=True)
    os.makedirs(_cache_dir(), exist_ok=True)
    zip_path = os.path.join(_cache_dir(), "oewn-2025.json.zip")
    if not os.path.exists(zip_path):
        print(f"Downloading {input_url} …")
        urllib.request.urlretrieve(input_url, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        root = os.path.realpath(dest_dir)
        for member in z.infolist():
            target = os.path.realpath(os.path.join(root, member.filename))
            if os.path.commonpath([root, target]) != root:
                raise SystemExit(f"Unsafe ZIP member: {member.filename!r}")
        z.extractall(root)
    return dest_dir


def _load_synsets(data_dir):
    """synset id -> {"definition", "partOfSpeech"} from the synset JSON files."""
    synsets = {}
    for name in sorted(os.listdir(data_dir)):
        if not name.endswith(".json") or name.startswith("entries"):
            continue
        path = os.path.join(data_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as ex:
            raise SystemExit(f"Could not read synset file '{path}': {ex}")
        if not isinstance(data, dict):
            continue  # not a synset file (e.g. frames.json)
        for sid, entry in data.items():
            if not isinstance(entry, dict):
                continue
            defs = entry.get("definition") or []
            if not defs:
                continue
            synsets[sid] = {
                "definition": defs[0],
                "partOfSpeech": _POS_NAME.get(entry.get("partOfSpeech"), ""),
            }
    return synsets


def build(data_dir, max_senses=3):
    """word -> [{"definition", "partOfSpeech"}, ...] from an OEWN JSON dir."""
    synsets = _load_synsets(data_dir)
    words = {}
    for name in sorted(os.listdir(data_dir)):
        if not (name.startswith("entries") and name.endswith(".json")):
            continue
        path = os.path.join(data_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as ex:
            raise SystemExit(f"Could not read entries file '{path}': {ex}")
        for word, senses in data.items():
            w = word.strip().lower()
            if not w or " " in w:
                continue  # single surface forms only (token lookups)
            collected = []
            seen = set()
            # First pass: the first sense of each POS — sense diversity beats
            # same-POS repetition for a definition dictionary ("purchase"
            # should show its noun *and* verb senses, not two noun glosses).
            for pos in ("n", "v", "a", "r"):
                if len(collected) >= max_senses:
                    break
                for sense in (senses.get(pos) or {}).get("sense") or []:
                    syn = synsets.get(sense.get("synset"))
                    if not syn or not syn["definition"]:
                        continue
                    key = (syn["definition"], syn["partOfSpeech"])
                    if key not in seen:
                        seen.add(key)
                        collected.append({"definition": syn["definition"],
                                          "partOfSpeech": syn["partOfSpeech"]})
                    break  # first sense of this POS only
            # Second pass: upstream sense order fills the remaining slots.
            for pos in ("n", "v", "a", "r"):
                for sense in (senses.get(pos) or {}).get("sense") or []:
                    if len(collected) >= max_senses:
                        break
                    syn = synsets.get(sense.get("synset"))
                    if not syn or not syn["definition"]:
                        continue
                    key = (syn["definition"], syn["partOfSpeech"])
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append({"definition": syn["definition"],
                                      "partOfSpeech": syn["partOfSpeech"]})
            if collected:
                words[w] = collected
    return words


def document(words, max_senses):
    return {
        "_meta": {
            "source": _VERSION,
            "url": "https://en-word.net/downloads",
            "license": "CC BY 4.0 — Open English Wordnet is derived from "
                       "Princeton WordNet by the Open English Wordnet "
                       "Community; https://creativecommons.org/licenses/by/4.0/",
            "derived": True,
            "note": ("compact build: per word, the first up-to-%d distinct "
                     "sense glosses with part of speech, in upstream sense "
                     "order; single surface forms only" % max_senses),
            "regenerate": "python3 build_dictionary.py [--input DIR] "
                          "[--max-senses N]",
        },
        "words": words,
    }


def check(path=_DEFAULT_OUT):
    """Validate a bundled wordnet.json; return a stats dict."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict) and "_meta" in data, "missing _meta"
    words = data["words"]
    assert isinstance(words, dict) and words, "no words"
    n_entries = 0
    for w, entries in words.items():
        assert w == w.lower() and " " not in w, f"bad word key {w!r}"
        assert isinstance(entries, list) and entries, f"empty {w!r}"
        for e in entries:
            assert e.get("definition"), f"missing definition for {w!r}"
            assert e.get("partOfSpeech"), f"missing pos for {w!r}"
        n_entries += len(entries)
    return {"words": len(words), "entries": n_entries}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bundle Open English WordNet as the offline dictionary")
    ap.add_argument("--input", default=None,
                    help="directory of the extracted OEWN JSON export "
                         "(entries-*.json + synset files); defaults to "
                         "downloading the canonical zip")
    ap.add_argument("--output", default=_DEFAULT_OUT)
    def _positive_int(value):
        n = int(value)
        if n < 1:
            raise argparse.ArgumentTypeError("must be at least 1")
        return n

    ap.add_argument("--max-senses", type=_positive_int, default=3,
                    help="keep at most this many distinct glosses per word "
                         "(default: 3)")
    ap.add_argument("--check", action="store_true",
                    help="validate the bundled wordnet.json and exit")
    args = ap.parse_args(argv)

    if args.check:
        try:
            stats = check(args.output)
        except (OSError, AssertionError, ValueError) as ex:
            sys.stderr.write(f"wordnet bundle check failed: {ex}\n")
            return 1
        print(f"wordnet bundle OK: {stats['words']:,} words, "
              f"{stats['entries']:,} glosses in {args.output}")
        return 0

    data_dir = args.input or download()
    print(f"Building from {data_dir} …")
    words = build(data_dir, max_senses=args.max_senses)
    doc = document(words, args.max_senses)
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = os.path.getsize(args.output) / 1024 / 1024
    print(f"Wrote {args.output}: {len(words):,} words, "
          f"{sum(len(v) for v in words.values()):,} glosses, {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
