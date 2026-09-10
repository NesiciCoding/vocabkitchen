#!/usr/bin/env python3
"""Regression guard for tui.py — the interactive front door.

Dependency-free (no pytest, no curses). Run:  python3 test_tui.py

The TUI is 700+ lines but almost all of the risk lives in a handful of pure
functions that translate a tool's form state into an argument vector and locate
the engine interpreter — the curses drawing code is a thin shell over those.
This suite freezes that logic and, crucially, guards the ONE drift risk the
front door introduces: build_argv() re-encodes flag names that really live in
each CLI's argparse, so every flag the TUI can emit is checked against that
script's own --help. A renamed or removed flag fails here instead of silently
building a broken command in front of a user.

The flag-drift check shells out to each tool's `--help`, which works without
spaCy (argparse runs before the engine import), so the whole suite runs in any
environment — no grammar engine required.
"""
import copy
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

import tui  # noqa: E402


passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}" + (f"  — {detail}" if detail else ""))


def tool(tool_id):
    """A deep copy of a tool definition, safe to mutate (TOOLS is shared state)."""
    for t in tui.TOOLS:
        if t["id"] == tool_id:
            return copy.deepcopy(t)
    raise KeyError(tool_id)


def set_field(t, key, value):
    for f in t["fields"]:
        if f["key"] == key:
            f["value"] = value
            return
    raise KeyError(key)


def argv_flags(t):
    """The set of `--flags` build_argv could emit for this tool, over all values.

    Independent of the current field values: it is the vocabulary of flags the
    form can produce, which is exactly what must stay in step with the CLI.
    """
    flags = set()
    for f in t["fields"]:
        if f["kind"] == "source":
            flags.update(("--file", "--text"))
        elif f.get("flag"):
            flags.add(f["flag"])
    return flags


def help_flags(script):
    """Long options accepted by a script, parsed from its --help output."""
    p = subprocess.run(
        [sys.executable, os.path.join(HERE, script), "--help"],
        capture_output=True, text=True, timeout=120,
    )
    if p.returncode != 0:
        return None  # signal: could not obtain help (skip, don't fail)
    return set(re.findall(r"--[A-Za-z][A-Za-z0-9-]*", p.stdout))


# --------------------------------------------------------------------------
print("engine_python()")
# --------------------------------------------------------------------------

_saved_env = os.environ.get("GRAMMAR_PROFILE_PYTHON")
try:
    # An override that exists wins and is returned absolute.
    os.environ["GRAMMAR_PROFILE_PYTHON"] = sys.executable
    got = tui.engine_python()
    check("override to an existing interpreter is honoured",
          os.path.realpath(got) == os.path.realpath(sys.executable), got)
    check("returned path is absolute", os.path.isabs(got), got)

    # An override that does not exist is ignored; falls back to a real python.
    os.environ["GRAMMAR_PROFILE_PYTHON"] = os.path.join(HERE, "no-such-python")
    got = tui.engine_python()
    check("missing override falls back to an existing interpreter",
          os.path.exists(got), got)
finally:
    if _saved_env is None:
        os.environ.pop("GRAMMAR_PROFILE_PYTHON", None)
    else:
        os.environ["GRAMMAR_PROFILE_PYTHON"] = _saved_env


# --------------------------------------------------------------------------
print("_default_source()")
# --------------------------------------------------------------------------

src = tui._default_source()
check("default source is empty or an existing sample file",
      src == "" or os.path.exists(src), src)


# --------------------------------------------------------------------------
print("build_argv() — structure")
# --------------------------------------------------------------------------

t = tool("vocab")
argv = tui.build_argv(t)
check("argv[0] is the engine interpreter", argv[0] == tui.engine_python())
check("argv[1] is the absolute script path",
      argv[1] == os.path.join(HERE, "vocab_profile.py"), argv[1])
check("vocab defaults emit --type all --format pretty",
      "--type" in argv and "all" in argv and "--format" in argv and "pretty" in argv,
      " ".join(argv))

# File vs inline text mode drives the source flag.
t = tool("vocab")
set_field(t, "mode", "File")
set_field(t, "source", "/tmp/some file.txt")
argv = tui.build_argv(t)
check("File mode emits --file with the raw (unsplit) value",
      "--file" in argv and "/tmp/some file.txt" in argv and "--text" not in argv,
      " ".join(argv))

t = tool("vocab")
set_field(t, "mode", "Inline text")
set_field(t, "source", "the cat sat")
argv = tui.build_argv(t)
check("Inline text mode emits --text, not --file",
      "--text" in argv and "the cat sat" in argv and "--file" not in argv,
      " ".join(argv))

t = tool("vocab")
set_field(t, "source", "   ")
argv = tui.build_argv(t)
check("blank source emits neither --file nor --text (stdin)",
      "--file" not in argv and "--text" not in argv, " ".join(argv))

# choice sentinels emit nothing.
t = tool("text_report")
set_field(t, "target", "(none)")
set_field(t, "export", "(none)")
argv = tui.build_argv(t)
check("choice sentinel (none) emits no flag",
      "--target-level" not in argv and "--export" not in argv, " ".join(argv))

t = tool("text_report")
set_field(t, "target", "B1")
argv = tui.build_argv(t)
check("a real choice emits `flag value`",
      argv[argv.index("--target-level") + 1] == "B1", " ".join(argv))

# flag_when: --no-grammar only appears for the "off" value.
t = tool("text_report")
set_field(t, "grammar", "on")
check("grammar 'on' does NOT emit --no-grammar",
      "--no-grammar" not in tui.build_argv(t))
set_field(t, "grammar", "off")
check("grammar 'off' emits --no-grammar (and nothing else for that field)",
      "--no-grammar" in tui.build_argv(t) and "off" not in tui.build_argv(t))

# toggles.
t = tool("text_report")
set_field(t, "suggest", True)
check("toggle True emits its bare flag", "--suggest" in tui.build_argv(t))
set_field(t, "suggest", False)
check("toggle False emits nothing", "--suggest" not in tui.build_argv(t))

# free-text field.
t = tool("class_profile")
set_field(t, "targets", "A2,B1,B2")
argv = tui.build_argv(t)
check("non-empty text field emits `flag value`",
      argv[argv.index("--targets") + 1] == "A2,B1,B2", " ".join(argv))
set_field(t, "targets", "   ")
check("blank text field emits nothing", "--targets" not in tui.build_argv(t))

# extra args are shell-split and appended verbatim.
t = tool("vocab")
set_field(t, "extra", "--foo 'a b' --bar")
argv = tui.build_argv(t)
check("extra args are shlex-split and appended",
      argv[-3:] == ["--foo", "a b", "--bar"], " ".join(argv))


# --------------------------------------------------------------------------
print("build_argv() — flags stay in step with each CLI (anti-drift)")
# --------------------------------------------------------------------------

for t in tui.TOOLS:
    accepted = help_flags(t["script"])
    if accepted is None:
        print(f"  skip {t['script']} --help unavailable (engine missing?)")
        continue
    for flag in sorted(argv_flags(t)):
        check(f"{t['script']} accepts {flag}", flag in accepted,
              f"TUI can emit {flag} but {t['script']} --help does not list it")


# --------------------------------------------------------------------------
print("check_engine() / engine_ready()")
# --------------------------------------------------------------------------

st = tui.check_engine()
check("check_engine returns the documented keys",
      set(st) == {"python", "spacy", "model", "pypdf"}, str(sorted(st)))
check("engine_ready needs both spaCy and the model",
      tui.engine_ready({"spacy": "3.8", "model": True}) is True
      and tui.engine_ready({"spacy": None, "model": True}) is False
      and tui.engine_ready({"spacy": "3.8", "model": False}) is False)


# --------------------------------------------------------------------------
print("main() refuses a non-interactive terminal")
# --------------------------------------------------------------------------

p = subprocess.run(
    [sys.executable, os.path.join(HERE, "tui.py")],
    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
)
check("non-tty run exits 1 with guidance, not a traceback",
      p.returncode == 1 and "interactive terminal" in p.stderr
      and "Traceback" not in p.stderr, p.stderr.strip()[:120])


print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
