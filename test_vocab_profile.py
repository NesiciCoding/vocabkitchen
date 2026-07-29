#!/usr/bin/env python3
"""Regression guard for vocab_profile.py.

Dependency-free (no pytest). Run:  python3 test_vocab_profile.py

Checks the tokenizer/percentage logic and freezes a couple of known-good
outputs, so word-list drift or a logic change is caught. The frozen values were
verified byte-for-byte against the original C# profiler (CefrProfiler / AwlProfiler / NawlProfiler).
"""
import json
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "vocab_profile.py")

import vocab_profile as vp  # noqa: E402


def run(args, text):
    p = subprocess.run(
        [sys.executable, SCRIPT] + args,
        input=text, capture_output=True, text=True,
    )
    return p.returncode, p.stdout, p.stderr


passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


# --- unit: tokenizer strips punctuation, keeps words & numbers -----------------
toks = [t for t in vp.tokenize("Hello, world! 42 don't") if t not in vp._PLACEHOLDERS]
check("tokenizer keeps words+numbers", toks == ["Hello", "world", "42", "don", "t"])
check("tokenizer empty -> []", vp.tokenize("   ") == [])

# --- unit: percentage rounding (banker's, whole percent) -----------------------
check("pct 5/6 -> 83%", vp.format_percentage(5, 6) == "83%")
check("pct 1/6 -> 17%", vp.format_percentage(1, 6) == "17%")
check("pct 0 denom -> 0%", vp.format_percentage(0, 0) == "0%")
check("pct 1/1 -> 100%", vp.format_percentage(1, 1) == "100%")

# --- integration: frozen known-good output (verified vs C#) --------------------
rc, out, _ = run(["--type", "cefr", "--text", "The cat sat on the mat."], "")
check("cefr rc==0", rc == 0)
d = json.loads(out)
check("total==6", d["totalWordCount"] == 6)
cefr = d["results"]["cefr"]
check("A1 83% / 5 words", cefr["A1"]["percentage"] == "83%" and cefr["A1"]["wordCount"] == 5)
check("A1 'the' occurs twice, ranked first",
      cefr["A1"]["words"][0] == {"word": "the", "occurrences": 2})
check("mat -> C1", cefr["C1"]["words"] == [{"word": "mat", "occurrences": 1}])
check("nothing off-list", cefr["Off List"]["wordCount"] == 0)

# --- integration: academic word list -------------------------------------------
rc, out, _ = run(["--type", "awl"], "Academic research demonstrates significant methodology.")
d = json.loads(out)
check("awl 100%", d["results"]["awl"]["Awl"]["percentage"] == "100%")

# --- integration: stdin + error handling ---------------------------------------
rc, out, err = run(["--type", "cefr"], "   ")
check("blank input errors rc==1", rc == 1 and "Usage" in err)
rc, out, err = run(["--type", "bogus", "--text", "hi"], "")
check("bad type errors rc==1", rc == 1 and "Unknown profiler type" in err)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
