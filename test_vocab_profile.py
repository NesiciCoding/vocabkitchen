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
import shutil
import tempfile

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

# --- integration: --file input -------------------------------------------------
_tmp = tempfile.mkdtemp(prefix="vocabtest_")
try:
    essay = os.path.join(_tmp, "essay.txt")
    with open(essay, "w", encoding="utf-8") as f:
        f.write("The cat sat on the mat.")
    rc, out, _ = run(["--type", "cefr", "--file", essay], "")
    check("--file rc==0", rc == 0)
    dfile = json.loads(out)
    check("--file total==6", dfile["totalWordCount"] == 6)
    check("--file A1 83%", dfile["results"]["cefr"]["A1"]["percentage"] == "83%")
    check("--file matches --text output", dfile == json.loads(
        run(["--type", "cefr", "--text", "The cat sat on the mat."], "")[1]))

    rc, out, err = run(["--type", "cefr", "--file", os.path.join(_tmp, "missing.txt")], "")
    check("--file missing errors rc==1", rc == 1 and "Could not read file" in err)

    # --- integration: --wordlists override -------------------------------------
    wl = os.path.join(_tmp, "custom")
    os.makedirs(os.path.join(wl, "AWL"))
    with open(os.path.join(wl, "AWL", "awl.txt"), "w", encoding="utf-8") as f:
        f.write("zzzcustomword\n")
    rc, out, _ = run(["--type", "awl", "--wordlists", wl, "--text", "zzzcustomword here"], "")
    check("--wordlists rc==0", rc == 0)
    dwl = json.loads(out)["results"]["awl"]["Awl"]
    check("--wordlists override matches custom word",
          dwl["percentage"] == "50%" and dwl["words"] == [{"word": "zzzcustomword", "occurrences": 1}])

    rc, out, err = run(["--type", "awl", "--wordlists", os.path.join(_tmp, "nope"), "--text", "hi"], "")
    check("--wordlists unreadable errors rc==1", rc == 1 and "Could not read word list" in err)
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

# --- integration: stdin + error handling ---------------------------------------
rc, out, err = run(["--type", "cefr"], "   ")
check("blank input errors rc==1", rc == 1 and "Usage" in err)
rc, out, err = run(["--type", "bogus", "--text", "hi"], "")
check("bad type errors rc==1", rc == 1 and "Unknown profiler type" in err)

# --- unit: --format resolution -------------------------------------------------
check("format auto+tty -> pretty", vp.resolve_format("auto", True) == "pretty")
check("format auto+pipe -> json", vp.resolve_format("auto", False) == "json")
check("format none+pipe -> json", vp.resolve_format(None, False) == "json")
check("format json overrides tty", vp.resolve_format("json", True) == "json")
check("format pretty overrides pipe", vp.resolve_format("pretty", False) == "pretty")
try:
    vp.resolve_format("bogus", True)
    check("format bogus raises", False)
except ValueError:
    check("format bogus raises", True)

# --- unit: CEFR typical/coverage verdict ---------------------------------------
_ord = [("A1", "", [("a", 80)]), ("A2", "", []), ("B1", "", []),
        ("B2", "", []), ("C1", "", []), ("C2", "", [("z", 20)]), ("Off List", "", [])]
_counts, _typ, _cov = vp._cefr_stats(_ord, 100)
check("typical is busiest band (A1)", _typ == "A1")
check("coverage needs C2 for 90%", _cov == "C2")
_counts2, _typ2, _cov2 = vp._cefr_stats([("A1", "", []), ("A2", "", []), ("B1", "", []),
                                         ("B2", "", []), ("C1", "", []), ("C2", "", []),
                                         ("Off List", "", [("x", 3)])], 3)
check("no recognised vocab -> dash", _typ2 == "—" and _cov2 == "—")

# --- unit: pretty rendering (plain, non-tty stream) ----------------------------
import io  # noqa: E402
_base = os.path.join(HERE, "WordLists")
_levels = [(n, vp.load_wordlist(_base, rel)) for n, rel in vp._PROFILERS["cefr"]]
_ordc, _totc = vp.profile("The cat sat on the mat.", _levels)
_buf = io.StringIO()
vp.render_pretty("essay.txt", {"cefr": (_ordc, _totc)}, _levels, "The cat sat on the mat.", stream=_buf)
_pretty = _buf.getvalue()
check("pretty has header", "Vocabulary Profile" in _pretty)
check("pretty has source", "essay.txt" in _pretty)
check("pretty has verdict labels", "Typical:" in _pretty and "90% coverage:" in _pretty)
check("pretty lists a word", "cat" in _pretty)
check("pretty non-tty has no ANSI", "\x1b[" not in _pretty)

# --- integration: Markdown / .docx / empty-file extraction ---------------------
_tmp2 = tempfile.mkdtemp(prefix="vocabtest_fmt_")
try:
    md = os.path.join(_tmp2, "doc.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Heading\n\nSome **bold** and a [link](https://example.com) plus `code`.")
    rc, out, _ = run(["--type", "cefr", "--file", md], "")
    check("markdown rc==0", rc == 0)
    dmd = json.loads(out)
    _words = {w["word"] for lvl in dmd["results"]["cefr"].values() for w in lvl["words"]}
    check("markdown keeps prose words", {"heading", "bold", "link", "code"} <= _words)
    check("markdown drops url host", "example" not in _words and "https" not in _words)

    # Minimal real .docx built with the stdlib (zip of XML).
    import zipfile  # noqa: E402
    docx = os.path.join(_tmp2, "doc.docx")
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    doc = (f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>'
           '<w:p><w:r><w:t>The cat sat on the mat.</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
    rc, out, _ = run(["--type", "cefr", "--file", docx], "")
    check("docx rc==0", rc == 0)
    check("docx matches equivalent text", json.loads(out) == json.loads(
        run(["--type", "cefr", "--text", "The cat sat on the mat."], "")[1]))

    empty = os.path.join(_tmp2, "empty.txt")
    with open(empty, "w", encoding="utf-8") as f:
        f.write("   \n\t")
    rc, out, err = run(["--file", empty], "")
    check("empty file errors rc==1", rc == 1 and "No analysable text" in err)

    # PDF without pypdf gives a friendly install hint (skip if pypdf is present).
    try:
        import pypdf  # noqa: F401
        _has_pypdf = True
    except Exception:
        _has_pypdf = False
    if not _has_pypdf:
        pdf = os.path.join(_tmp2, "x.pdf")
        with open(pdf, "w", encoding="utf-8") as f:
            f.write("%PDF-1.4 not-really")
        rc, out, err = run(["--file", pdf], "")
        check("pdf w/o pypdf hints install", rc == 1 and "pip install pypdf" in err)
finally:
    shutil.rmtree(_tmp2, ignore_errors=True)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
