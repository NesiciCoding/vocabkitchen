#!/usr/bin/env python3
"""Regression guard for class_profile.py — the folder/class-set profiler.

Dependency-free harness (no pytest). Run:  python3 test_class_profile.py

Unit checks (input discovery, level parsing, row building, aggregate, rank &
filter, band export, CSV/pretty rendering) always run. The CLI is exercised
through subprocess. Checks that need spaCy for the grammar side are skipped
when it isn't installed, like the other grammar-dependent suites.
"""

import csv as _csv
import http.server
import io
import json
import os
import re as _re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "class_profile.py")

import class_profile as cp  # noqa: E402
import analysis as engine  # noqa: E402
import vocab_profile as vp  # noqa: E402
import grammar_profile as gp  # noqa: E402
import text_report as tr  # noqa: E402

try:
    _NLP = gp.load_nlp()
    _CEFRJ = gp.load_cefrj_levels(os.path.join(HERE, "GrammarProfile"))
    HAVE_GRAMMAR = True
except Exception:
    _NLP = _CEFRJ = None
    HAVE_GRAMMAR = False

_BASE = os.path.join(HERE, "WordLists")
_LEVELS = [(name, vp.load_wordlist(_BASE, rel)) for name, rel in vp.PROFILERS["cefr"]]
# The Phase 5 shared engine: word lists + the same grammar engine the CLI
# loads once for the whole set (built here per-interpreter for the unit
# tests; the CLI builds it once in main).
_ENG = engine.Engine(_LEVELS, _BASE, grammar_available=HAVE_GRAMMAR,
                     nlp=_NLP if HAVE_GRAMMAR else None,
                     cefrj_levels=_CEFRJ if HAVE_GRAMMAR else None)
_ENG_GRAMMAR = engine.Engine(_LEVELS, _BASE, grammar_available=HAVE_GRAMMAR,
                             nlp=_NLP if HAVE_GRAMMAR else None,
                             cefrj_levels=_CEFRJ if HAVE_GRAMMAR else None,
                             grammar_requested=True)

_EASY = "The cat sat on the mat. I like bread and milk and apples."
_MID = ("The results were analysed by the committee and the findings were "
        "published in a reputable journal.")
_HARD = ("Circumstances notwithstanding, the philosophical implications of "
         "synthesizing chlorophyll remain contentious among scholars.")

passed = failed = skipped = 0


def check(name, cond, detail=None):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}" + (f" — {detail}" if detail is not None else ""))


def run(args, text=""):
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       input=text, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def _make_dir(prefix="classprof_test_"):
    """A folder fixture: 3 supported texts (1 empty), a hidden file, a binary."""
    d = tempfile.mkdtemp(prefix=prefix)

    def write(name, content):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write(content)

    write("easy.txt", _EASY)
    write("mid.md", "# Title\n\n" + _MID)
    write("hard.txt", _HARD)
    write("empty.txt", "   \n\t")
    write(".hidden.txt", _EASY)
    write("binary.bin", "\x00\x01 not utf-8")
    return d


def _make_docx(path):
    """A minimal real .docx built with the stdlib (zip of XML)."""
    import zipfile  # noqa: E402
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    doc = (f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>'
           '<w:p><w:r><w:t>The cat sat on the mat.</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)


def _minimal_pdf(text):
    """A small but valid PDF with a text layer, offsets computed by hand."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    stream = (b"<< /Length " + str(len(content)).encode()
              + b" >>\nstream\n" + content + b"\nendstream")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
         b"/Resources << /Font << /F1 5 0 R >> >> >>"),
        stream,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n").encode()
    return bytes(out)


try:
    import pypdf  # noqa: F401
    _HAS_PYPDF = True
except Exception:
    _HAS_PYPDF = False


# --- mock Free Dictionary API (mirrors test_text_report) ---------------------
class _DictHandler(http.server.BaseHTTPRequestHandler):
    _lock = threading.Lock()
    requests = 0

    def do_GET(self):
        with _DictHandler._lock:
            _DictHandler.requests += 1
        word = self.path.rsplit("/", 1)[-1]
        body = _DICT_PAYLOADS.get(word)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


_DICT_PAYLOADS = {
    "circumstances": [{"word": "circumstances", "phonetic": "/s/",
                        "meanings": [{"partOfSpeech": "noun",
                                      "definitions": [{"definition": "a fact connected with an event"}]}]}],
    "implications": [{"word": "implications",
                       "meanings": [{"partOfSpeech": "noun",
                                     "definitions": [{"definition": "likely consequences"}]}]}],
}
_dict_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _DictHandler)
threading.Thread(target=_dict_server.serve_forever, daemon=True).start()
_dict_url = f"http://127.0.0.1:{_dict_server.server_address[1]}"


# --- unit: input discovery ---------------------------------------------------
_tmp = _make_dir()
try:
    names = [os.path.basename(f) for f in cp.discover_files(_tmp)]
    # empty.txt is a supported extension, so it IS discovered — it's skipped
    # later, at profile time, for having no analysable text.
    check("discover dir: supported exts, sorted, hidden skipped",
          names == ["easy.txt", "empty.txt", "hard.txt", "mid.md"])

    # --- unit: the venv re-exec is skipped in vocabulary-only modes -----------
    _saved_argv = list(sys.argv)
    try:
        sys.argv = ["class_profile.py", "--file", ".", "--no-grammar"]
        cp._maybe_reexec_in_venv()  # must return; never exec's with --no-grammar
        sys.argv = ["class_profile.py", "--file", ".", "--pre-enrich"]
        cp._maybe_reexec_in_venv()  # ...and with --pre-enrich
        check("re-exec skipped for vocab-only modes", True)
    except Exception as ex:
        check("re-exec skipped for vocab-only modes", False, str(ex))
    finally:
        sys.argv = _saved_argv

    os.makedirs(os.path.join(_tmp, "sub"))
    with open(os.path.join(_tmp, "sub", "inner.txt"), "w", encoding="utf-8") as f:
        f.write(_EASY)
    names = [os.path.basename(f) for f in cp.discover_files(_tmp)]
    check("discover dir is non-recursive", "inner.txt" not in names)

    md_only = cp.discover_files(os.path.join(_tmp, "*.md"))
    check("discover glob", [os.path.basename(f) for f in md_only] == ["mid.md"])

    # A re-run over a folder with the tool's own handouts in it must not
    # re-profile them (they'd pollute the set and the deck indexes).
    with open(os.path.join(_tmp, "easy-preteaching-B1.md"), "w",
              encoding="utf-8") as f:
        f.write(_EASY)
    with open(os.path.join(_tmp, "essays-summary-B1.md"), "w",
              encoding="utf-8") as f:
        f.write(_EASY)
    with open(os.path.join(_tmp, "essays-interleave-B1.md"), "w",
              encoding="utf-8") as f:
        f.write(_EASY)
    names = [os.path.basename(f) for f in cp.discover_files(_tmp)]
    check("discover skips the tool's own export artifacts",
          "easy-preteaching-B1.md" not in names
          and "essays-summary-B1.md" not in names
          and "essays-interleave-B1.md" not in names
          and "hard.txt" in names)
    check("is_export_artifact recognises decks and indexes",
          cp.is_export_artifact("essays-preteaching-B1-deck.csv")
          and cp.is_export_artifact("essays-preteaching-B1-index.md")
          and cp.is_export_artifact("class-summary-C2.md")
          and cp.is_export_artifact("essays-interleave-B1.md")
          and not cp.is_export_artifact("lesson-notes.md")
          and not cp.is_export_artifact("handout-summary.docx"))
    os.remove(os.path.join(_tmp, "easy-preteaching-B1.md"))
    os.remove(os.path.join(_tmp, "essays-summary-B1.md"))
    os.remove(os.path.join(_tmp, "essays-interleave-B1.md"))

    one = cp.discover_files(os.path.join(_tmp, "easy.txt"))
    check("discover single file", one == [os.path.join(_tmp, "easy.txt")])

    for bad, frag in [(os.path.join(_tmp, "*.nope"), "matched no files"),
                      (os.path.join(_tmp, "missing.txt"), "file not found")]:
        try:
            cp.discover_files(bad)
            check(f"discover error: {frag}", False)
        except cp.ClassProfileError as ex:
            check(f"discover error: {frag}", frag in str(ex))

    # --- unit: level parsing + format resolution ------------------------------
    check("parse level case-insensitive", cp._parse_level("b1", "--target-level") == "B1")
    try:
        cp._parse_level("Z9", "--target-level")
        check("parse bad level raises", False)
    except cp.ClassProfileError:
        check("parse bad level raises", True)
    check("format csv explicit", cp.resolve_format("csv", True) == "csv")
    check("format auto+pipe -> json", cp.resolve_format("auto", False) == "json")
    try:
        cp.resolve_format("bogus", True)
        check("format bogus raises", False)
    except cp.ClassProfileError:
        check("format bogus raises", True)

    # --- Phase 5: the shared analysis engine -----------------------------------
    check("class_profile imports the shared engine",
          cp.engine.__name__ == "analysis"
          and callable(cp.engine.load_engine)
          and callable(cp.engine.payload))

    # --- unit: row building (vocab only; no grammar engine needed) -------------
    row, ordered, _ctx = cp.build_row(_EASY, "easy.txt", _ENG, False, "B1")
    check("row easy typical A1", row["vocabulary"]["typical"] == "A1")
    check("row easy coverage A1", row["vocabulary"]["coverage"] == "A1")
    check("row grammar None without engine", row["grammar"] is None)
    check("row estimated A1", row["estimatedLevel"] == "A1")
    check("row aboveTargetPercent numeric",
          isinstance(row["aboveTargetPercent"], int) and 0 <= row["aboveTargetPercent"] <= 100)
    check("row easy fits B1 target", row["fits"] is True)
    check("row ctx carries the text", _ctx["text"] == _EASY)

    row2, _o2, _c2 = cp.build_row(_HARD, "hard.txt", _ENG, False, "B1")
    check("row hard estimated C2", row2["estimatedLevel"] == "C2")
    check("row hard does not fit B1", row2["fits"] is False)

    row3, _o3, _c3 = cp.build_row(_EASY, "x.txt", _ENG, False, None)
    check("row without target: above/fits null",
          row3["aboveTargetPercent"] is None and row3["fits"] is None)

    # --- unit: multiple targets side by side ----------------------------------
    rowm, _om, _cm = cp.build_row(_EASY, "easy.txt", _ENG, False,
                                  ["A2", "B1"])
    check("multi-target: per-target map populated",
          set(rowm["targets"]) == {"A2", "B1"})
    check("multi-target: easy fits A2 and B1",
          rowm["targets"]["A2"]["fits"] is True and rowm["targets"]["B1"]["fits"] is True)
    check("multi-target: singular fields null",
          rowm["aboveTargetPercent"] is None and rowm["fits"] is None)
    rowm2, _om2, _cm2 = cp.build_row(_HARD, "hard.txt", _ENG, False,
                                     ["A2", "B1"])
    check("multi-target: hard fits neither",
          rowm2["targets"]["A2"]["fits"] is False
          and rowm2["targets"]["B1"]["fits"] is False)
    check("multi-target: above pct per level",
          isinstance(rowm2["targets"]["A2"]["aboveTargetPercent"], int)
          and isinstance(rowm2["targets"]["B1"]["aboveTargetPercent"], int))

    # --- unit: per-text export payload (text_report's writers' input) ---------
    payload = cp.export_payload(row, ordered, _ctx, "B1")
    check("export payload targetLevel", payload["targetLevel"] == "B1")
    check("export payload verdict",
          isinstance(payload["verdict"], str) and payload["verdict"] != "")
    check("export payload coverage figure", payload["coverage"]["knownPercent"] == 92)
    check("export payload grammar null w/o engine", payload["grammar"] is None)
    check("export payload carries the contract schemaVersion",
          payload["schemaVersion"] == engine.SCHEMA_VERSION)
    check("export payload grammarCriteria null w/o engine",
          payload["grammarCriteria"] is None)
    check("export payload above-target words have context",
          all(d.get("context") for d in payload["aboveTarget"]["words"]))
    check("export payload above-target nonempty", payload["aboveTarget"]["wordCount"] >= 1)

    # --- unit: --suggest annotates the per-text payload -----------------------
    _prof_p = cp.build_row("We purchase fresh bread daily, and the "
                           "circumstances rarely change.", "p.txt", _ENG,
                           False, "B1")
    _pp = cp.export_payload(_prof_p[0], _prof_p[1], _prof_p[2], "B1", suggest=True)
    _pw = next(d for d in _pp["aboveTarget"]["words"] if d["word"] == "purchase")
    check("export payload suggest annotates the word",
          _pw.get("suggestion") == {"word": "buy", "level": "A1"})
    _pn = cp.export_payload(_prof_p[0], _prof_p[1], _prof_p[2], "B1")
    _pwn = next(d for d in _pn["aboveTarget"]["words"] if d["word"] == "purchase")
    check("export payload without suggest: no suggestion key",
          "suggestion" not in _pwn)

    # --- unit: --gap-report wires text_report's gap report per text -----------
    _gap_prof = cp.build_row(_EASY, "g.txt", _ENG, False, "B1")
    _gap_p = cp.export_payload(_gap_prof[0], _gap_prof[1], _gap_prof[2], "B1",
                               gap_report=True)
    check("export payload gap report w/o engine sets grammarGapError",
          _gap_p.get("grammarGap") is None
          and bool(_gap_p.get("grammarGapError")))
    check("export payload without gap report: grammarGap stays None",
          cp.export_payload(_gap_prof[0], _gap_prof[1], _gap_prof[2], "B1")
          .get("grammarGap") is None)
    if HAVE_GRAMMAR:
        _gap_full = cp.build_row(_MID, "g.txt", _ENG_GRAMMAR, True, "B1")
        _gap_pf = cp.export_payload(_gap_full[0], _gap_full[1], _gap_full[2],
                                    "B1", gap_report=True)
        _gap = _gap_pf.get("grammarGap")
        check("gap report lists the B1 constructions",
              _gap is not None and _gap["targetLevel"] == "B1"
              and 0 < _gap["missingCount"] <= _gap["total"])
        check("gap report entries carry name and category",
              all(set(d) == {"name", "category"} for d in _gap["missing"]))
        check("gap handout renders the constructions-to-introduce section",
              "## Constructions to introduce at B1" in tr.export_markdown(_gap_pf))
        # grammarCriteria rides in the same payload: one entry per registered
        # construction, ladder-ordered, used entries with count + examples.
        _gc_full = _gap_pf["grammarCriteria"]
        check("export payload grammarCriteria covers the registry",
              _gc_full is not None
              and _gc_full["total"] == len(gp._CONSTRUCTIONS)
              and _gc_full["passedCount"] + _gc_full["failedCount"]
              == _gc_full["total"])
        check("export payload grammarCriteria ladder-ordered",
              [engine._LEVEL_INDEX.get(c["level"], 99) for c in _gc_full["criteria"]]
              == sorted(engine._LEVEL_INDEX.get(c["level"], 99)
                        for c in _gc_full["criteria"]))
        check("export payload grammarCriteria used entries have examples",
              all(c["count"] >= 1 and isinstance(c["examples"], list)
                  for c in _gc_full["criteria"] if c["pass"]))
        # --comments: the full apply-as-comment pass rides in the same
        # payload (grammar constructions + above-target words), off by default.
        _cm_full = cp.export_payload(_gap_full[0], _gap_full[1], _gap_full[2],
                                     "B1", comments=True)
        _cm_list = _cm_full["grammarComments"]
        _idx = engine._LEVEL_INDEX
        check("export payload comments=True filters to the class level",
              _cm_list is not None and len(_cm_list) < _gc_full["total"]
              and all((c["kind"] == "rubric"
                       and _idx[c["level"]] <= _idx["B1"])
                      or (c["kind"] == "pre-teach" and c["pass"]
                          and _idx[c["level"]] > _idx["B1"]
                          and "pre-teach or rewrite" in c["comment"])
                      for c in _cm_list))
        check("export payload comments=True carries the vocabulary half",
              _cm_full["vocabComments"] is not None
              and len(_cm_full["vocabComments"])
              == len((_cm_full.get("aboveTarget") or {}).get("words") or [])
              and all(c["comment"].startswith('Above B1: "')
                      for c in _cm_full["vocabComments"]))
        check("export payload without comments: both halves null",
              cp.export_payload(_gap_full[0], _gap_full[1], _gap_full[2], "B1")
              .get("grammarComments") is None
              and cp.export_payload(_gap_full[0], _gap_full[1], _gap_full[2], "B1")
              .get("vocabComments") is None)
    else:
        skipped += 1

    # --- unit: folder vocabulary + combined deck ------------------------------
    prof_a = cp.build_row(_EASY, "a", _ENG, False, None)
    prof_b = cp.build_row(_HARD, "b", _ENG, False, None)
    vocab = cp.folder_vocabulary([prof_a, prof_b])
    check("folder_vocabulary distinct across texts",
          {"the", "cat", "circumstances", "chlorophyll"} <= set(vocab))
    check("folder_vocabulary sorted", vocab == sorted(vocab))

    payloads = [cp.export_payload(r, o, c, "B1") for r, o, c in
                (cp.build_row(_EASY, "a", _ENG, False, "B1"),
                 cp.build_row(_HARD, "b", _ENG, False, "B1"))]
    combined = cp._combined_deck_payload(payloads)
    check("combined payload merges distinct words",
          {w["word"] for w in combined["aboveTarget"]["words"]}
          == {w["word"] for p in payloads for w in p["aboveTarget"]["words"]})
    check("combined payload carries the target", combined["targetLevel"] == "B1")
    circ = next(w for w in combined["aboveTarget"]["words"]
                if w["word"] == "circumstances")
    check("combined payload tracks source texts", circ["texts"] == ["b"])
    check("combined index path derives from the deck path",
          cp.combined_index_path(_tmp, "B1", None)
          == cp.combined_deck_path(_tmp, "B1", None)[:-len("-deck.csv")] + "-index.md")
    check("combined index markdown has the level-keyed table header",
          "| Word | Level | Occurrences | Texts |" in cp.combined_index_markdown(
              [{"word": "x", "occurrences": 2, "texts": ["a.txt", "b.txt"]}], "B1"))
    check("combined index carries each word's CEFR level",
          "| x | B2 | 2 | a.txt, b.txt |" in cp.combined_index_markdown(
              [{"word": "x", "level": "B2", "occurrences": 2,
                "texts": ["a.txt", "b.txt"]}], "B1"))
    check("combined deck named after source folder",
          cp.combined_deck_path(_tmp, "B1", None)
          == os.path.join(_tmp, os.path.basename(_tmp) + "-preteaching-B1-deck.csv"))
    check("combined deck into --output dir",
          cp.combined_deck_path(None, "B1", os.path.join(_tmp, "decks"))
          == os.path.join(_tmp, "decks", "class-preteaching-B1-deck.csv"))

    # --- unit: aggregate + rank/filter ----------------------------------------
    agg = cp.new_aggregate()
    for _r, _o, _c in (cp.build_row(_EASY, "a", _ENG, False, None),
                       cp.build_row(_HARD, "b", _ENG, False, None)):
        cp.add_to_aggregate(agg, _o)
    summ = cp.aggregate_summary(agg)
    check("aggregate total words", summ["totalWordCount"] == 13 + 12)
    check("aggregate typical A1", summ["typical"] == "A1")
    check("aggregate has per-level stats",
          set(summ["levels"]["A1"]) == {"percentage", "wordCount", "distinctWordCount"})

    # --- unit: set-level summary handout ---------------------------------------
    check("summary path named after source folder",
          cp.set_summary_path(_tmp, "B1", None)
          == os.path.join(_tmp, os.path.basename(_tmp) + "-summary-B1.md"))
    check("summary path into --output dir",
          cp.set_summary_path(None, "B1", os.path.join(_tmp, "decks"))
          == os.path.join(_tmp, "decks", "class-summary-B1.md"))
    _prof = [cp.build_row(t, label, _ENG, False, "B1")
             for label, t in [("easy.txt", _EASY), ("hard.txt", _HARD)]]
    _srows = [r for r, _o, _c in _prof]
    _spays = [cp.export_payload(r, o, c, "B1") for r, o, c in _prof]
    summ_md = cp.set_summary_markdown(_srows, summ, _spays, "B1")
    check("summary header names the target and count",
          "# Set summary — Target B1 (2 texts)" in summ_md)
    check("summary aggregates the pooled distribution",
          "Aggregate vocabulary" in summ_md and "Typical A1" in summ_md)
    check("summary has a per-text table with verdicts",
          "| Text | Words |" in summ_md
          and "easy.txt" in summ_md and "hard.txt" in summ_md
          and "pre-teach" in summ_md)
    check("summary marks fits and misses", "✓" in summ_md and "✗" in summ_md)

    # --- unit: curriculum coverage matrix in the set summary ------------------
    _cc_pays = [
        {"file": "a.txt", "verdict": "on level", "curriculum": {
            "vocabulary": [{"word": "purchase", "present": True},
                           {"word": "mat", "present": False}],
            "grammar": [{"name": "Passive (present)", "present": False}],
            "pass": False}},
        {"file": "b.txt", "verdict": "on level", "curriculum": {
            "vocabulary": [{"word": "purchase", "present": False},
                           {"word": "mat", "present": True}],
            "grammar": [{"name": "Passive (present)", "present": True}],
            "pass": False}},
    ]
    _cc_summ_md = cp.set_summary_markdown(_srows, summ, _cc_pays, "B1")
    check("summary md gains the curriculum coverage matrix",
          "## Curriculum coverage" in _cc_summ_md
          and "| Text | purchase | mat | Passive (present) | pass |" in _cc_summ_md
          and "| easy.txt | ✓ | ✗ | ✗ | ✗ |" in _cc_summ_md
          and "| hard.txt | ✗ | ✓ | ✓ | ✗ |" in _cc_summ_md)
    check("summary without curriculum has no matrix",
          "Curriculum coverage" not in cp.set_summary_markdown(
              _srows, summ, _spays, "B1"))
    check("curriculum_items shares the csv column list",
          cp.curriculum_items(_cc_pays[0])
          == [("vocabulary", "purchase"), ("vocabulary", "mat"),
              ("grammar", "Passive (present)")]
          and cp.curriculum_items({"file": "x"}) == [])

    # --- unit: vocabulary interleaving ----------------------------------------
    def _ord(b2=(), c1=()):
        return [("A1", "0", []), ("A2", "0", []), ("B1", "0", []),
                ("B2", "0", [(w, 1) for w in b2]),
                ("C1", "0", [(w, 1) for w in c1]), ("C2", "0", [])]

    _il_prof = [
        ({"file": "r1.txt"}, _ord(b2=("alpha", "bravo", "charlie")), {}),
        ({"file": "r2.txt"}, _ord(b2=("delta",)), {}),
        ({"file": "r3.txt"}, _ord(), {}),
    ]
    sch = cp.interleave_schedule(_il_prof, "B1", budget=2)
    check("interleave target and budget",
          sch["targetLevel"] == "B1" and sch["budget"] == 2)
    check("reading 1 introduces within budget",
          [d["word"] for d in sch["readings"][0]["introduce"]]
          == ["alpha", "bravo"])
    _r2 = sch["readings"][1]
    check("overflow deferred to the next reading",
          any(d["word"] == "charlie" and d.get("deferredFrom") == 1
              for d in _r2["introduce"]))
    check("deferred reading also introduces its own new word",
          any(d["word"] == "delta" for d in _r2["introduce"]))
    check("word index marks the deferred word",
          any(w["word"] == "charlie" and w["introducedAt"] == 2
              and w.get("deferredFrom") == 1 for w in sch["words"]))
    _il2 = [
        ({"file": "r1.txt"}, _ord(b2=("alpha",)), {}),
        ({"file": "r2.txt"}, _ord(b2=("alpha",)), {}),
        ({"file": "r3.txt"}, _ord(c1=("gamma",)), {}),
    ]
    sch2 = cp.interleave_schedule(_il2, "B1", budget=5)
    check("recurring word is listed for review",
          [d["word"] for d in sch2["readings"][1]["review"]] == ["alpha"])
    check("recurring word is not due", sch2["readings"][1]["due"] == [])
    _il3 = [
        ({"file": "r1.txt"}, _ord(b2=("alpha",)), {}),
        ({"file": "r2.txt"}, _ord(c1=("gamma",)), {}),
        ({"file": "r3.txt"}, _ord(c1=("delta",)), {}),
    ]
    sch3 = cp.interleave_schedule(_il3, "B1", budget=5)
    check("absent word not yet due after one gap",
          sch3["readings"][1]["due"] == [])
    check("absent word is due after two readings",
          [d["word"] for d in sch3["readings"][2]["due"]] == ["alpha"])
    _il_md = cp.interleave_markdown(sch)
    check("interleave md header names target, count, budget",
          "# Vocabulary interleaving — Target B1 (3 readings, 2 new words/reading)"
          in _il_md)
    check("interleave md has per-reading sections",
          "## Reading 1 — r1.txt" in _il_md and "**Introduce (2):**" in _il_md)
    check("interleave md flags the deferral", "deferred from reading 1" in _il_md)
    check("interleave md has the word index table",
          "| Word | Level | Introduced at | Appears in |" in _il_md)
    _il_csv = cp.interleave_csv(sch)
    _ilc_rows = list(_csv.reader(_il_csv.splitlines()))
    check("interleave csv header",
          _ilc_rows[0] == ["word", "level", "introducedAt", "appearsIn",
                           "deferredFrom"])
    check("interleave csv carries the deferred word",
          any(r[0] == "charlie" and r[2] == "2" and r[4] == "1"
              for r in _ilc_rows[1:]))
    check("interleave path named after source folder",
          cp.interleave_path(_tmp, "B1", None)
          == os.path.join(_tmp, os.path.basename(_tmp) + "-interleave-B1.md"))
    check("interleave path csv ext into --output",
          cp.interleave_path(None, "B1", os.path.join(_tmp, "decks"), "csv")
          == os.path.join(_tmp, "decks", "class-interleave-B1.csv"))
    _il_pretty = cp.render_interleave_pretty(sch)
    check("interleave pretty one line per reading",
          len(_il_pretty) == 1 + len(sch["readings"])
          and "Reading 1 (r1.txt):" in _il_pretty[1]
          and "1 deferred from earlier reading(s)" in _il_pretty[2])

    # --- unit: per-reading interleave handouts -------------------------------
    _il_rprof = [
        ({"file": "r1.txt"}, _ord(b2=("alpha", "bravo")),
         {"text": "The alpha result is bravo news."}),
        ({"file": "r2.txt"}, _ord(b2=("delta",)),
         {"text": "We need a delta plan."}),
        ({"file": "r3.txt"}, _ord(),
         {"text": "Nothing above target here."}),
    ]
    _ils = cp.interleave_schedule(_il_rprof, "B1", budget=5)
    _rmd = cp.interleave_reading_markdown(_ils, _ils["readings"][0], _il_rprof)
    check("reading handout names the reading and its source",
          "# Reading 1 — r1.txt" in _rmd)
    check("reading handout defines introduced words in context",
          "| `alpha` | B2 | The alpha result is bravo news |" in _rmd
          and "| `bravo` | B2 | The alpha result is bravo news |" in _rmd)
    check("reading handout carries review and due sections",
          "## Review (0)" in _rmd
          and "## Due for review (not seen for 2+ readings) (0)" in _rmd
          and "_None._" in _rmd)
    _rmd3 = cp.interleave_reading_markdown(_ils, _ils["readings"][2], _il_rprof)
    check("due words are defined from their last-seen reading",
          "## Due for review (not seen for 2+ readings) (2)" in _rmd3
          and "| `alpha` | B2 | The alpha result is bravo news |" in _rmd3
          and "| `bravo` | B2 | The alpha result is bravo news |" in _rmd3)
    check("reading handout path named after source folder",
          cp.interleave_reading_path(_tmp, "B1", 1, None)
          == os.path.join(_tmp, os.path.basename(_tmp)
                          + "-interleave-B1-reading-1.md"))
    check("reading handout path into --output dir",
          cp.interleave_reading_path(None, "B1", 2, os.path.join(_tmp, "decks"))
          == os.path.join(_tmp, "decks", "class-interleave-B1-reading-2.md"))

    # Reading handouts reuse the dictionary cache for definitions when
    # available (falling back to the in-text sentence offline).
    _cached_rmd = cp.interleave_reading_markdown(
        _ils, _ils["readings"][0], _il_rprof,
        lookup={"alpha": "a Greek letter"}.get)
    check("reading handout uses the cached definition when present",
          "| `alpha` | B2 | a Greek letter |" in _cached_rmd
          and "| `bravo` | B2 | The alpha result is bravo news |" in _cached_rmd)

    # --- unit: folder-level curriculum coverage grid --------------------------
    _cpays = [
        {"file": "a.txt", "curriculum": {
            "vocabulary": [{"word": "purchase", "present": True},
                           {"word": "mat", "present": False}],
            "grammar": [{"name": "Passive (present)", "present": False}],
            "pass": False}},
        {"file": "b.txt", "curriculum": {
            "vocabulary": [{"word": "purchase", "present": False},
                           {"word": "mat", "present": True}],
            "grammar": [{"name": "Passive (present)", "present": True}],
            "pass": False}},
    ]
    _grid = cp.curriculum_coverage_csv(_cpays, "B1")
    _grid_rows = list(_csv.reader(_grid.splitlines()))
    check("curriculum grid: one column per item + pass",
          _grid_rows[0] == ["text", "purchase", "mat", "Passive (present)", "pass"])
    check("curriculum grid: one row per text with yes/no cells",
          _grid_rows[1] == ["a.txt", "yes", "no", "no", "no"]
          and _grid_rows[2] == ["b.txt", "no", "yes", "yes", "no"])
    check("curriculum grid: no curriculum -> None",
          cp.curriculum_coverage_csv([{"file": "a.txt"}], "B1") is None)
    _ggrid = cp.curriculum_coverage_grid(_cpays)
    check("curriculum grid structured data (items/rows/passCount)",
          _ggrid["items"] == [("vocabulary", "purchase"),
                               ("vocabulary", "mat"),
                               ("grammar", "Passive (present)")]
          and _ggrid["rows"][0] == {"text": "a.txt",
                                     "cells": [True, False, False],
                                     "pass": False}
          and _ggrid["rows"][1]["cells"] == [False, True, True]
          and _ggrid["passCount"] == 0 and _ggrid["textCount"] == 2)
    check("curriculum grid structured: no curriculum -> None",
          cp.curriculum_coverage_grid([{"file": "a.txt"}]) is None)

    # --- unit: Can-Do demands across the set + the reference deck -------------
    _cdpays = [
        {"file": "a.txt", "cando": {"aboveTarget": {
            "vocabulary": [{"band": "B2",
                            "descriptor": "understand the main ideas of complex text"}],
            "grammar": [], "estimated": []}}},
        {"file": "b.txt", "cando": {"aboveTarget": {
            "vocabulary": [{"band": "B2",
                            "descriptor": "understand the main ideas of complex text"},
                           {"band": "C1",
                            "descriptor": "understand a wide range of demanding, longer texts"}],
            "grammar": [], "estimated": []}}},
    ]
    _dems = cp.aggregate_cando_demands(_cdpays)
    check("aggregate_cando_demands: most-common first with text lists",
          _dems[0]["band"] == "B2" and _dems[0]["texts"] == ["a.txt", "b.txt"]
          and _dems[1]["band"] == "C1" and _dems[1]["texts"] == ["b.txt"])
    check("aggregate_cando_demands: empty without a diff",
          cp.aggregate_cando_demands([{"file": "a.txt"}]) == [])
    # A case where band order and text-count order disagree: the C1 demand
    # is shared by both texts, the B1 demand by only one — so "texts" puts
    # C1 first and "band" puts B1 first.
    _sort_pays = [
        {"file": "a.txt", "cando": {"aboveTarget": {
            "vocabulary": [{"band": "B1", "descriptor": "deal with situations"},
                           {"band": "C1", "descriptor": "understand demanding texts"}],
            "grammar": [], "estimated": []}}},
        {"file": "b.txt", "cando": {"aboveTarget": {
            "vocabulary": [{"band": "C1", "descriptor": "understand demanding texts"}],
            "grammar": [], "estimated": []}}},
    ]
    check("aggregate_cando_demands: texts sort is most-common first",
          [r["band"] for r in cp.aggregate_cando_demands(_sort_pays)] == ["C1", "B1"])
    check("aggregate_cando_demands: band sort follows the ladder",
          [r["band"] for r in cp.aggregate_cando_demands(_sort_pays, sort="band")]
          == ["B1", "C1"])
    _cddeck = cp.combined_cando_deck(_cdpays, "B1")
    _cdd_rows = list(_csv.reader(_cddeck.splitlines()))
    check("combined_cando_deck: RubrikMaker shape, one card per demand",
          _cdd_rows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"]
          and len(_cdd_rows) == 3
          and _cdd_rows[1][0] == "B2 — vocabulary demand"
          and "demanded by 2 of 2 texts" in _cdd_rows[1][2]
          and all(r[4] == "cando" for r in _cdd_rows[1:]))
    check("combined_cando_deck: None without demands",
          cp.combined_cando_deck([{"file": "a.txt"}], "B1") is None)
    _cdsum = cp.set_summary_markdown(
        [{"file": "a.txt", "totalWordCount": 1, "vocabulary": {"typical": "A1",
                                                                  "coverage": "A1"},
          "grammar": None, "estimatedLevel": "A1", "aboveTargetPercent": 0,
          "fits": True},
         {"file": "b.txt", "totalWordCount": 1, "vocabulary": {"typical": "A1",
                                                                  "coverage": "A1"},
          "grammar": None, "estimatedLevel": "A1", "aboveTargetPercent": 0,
          "fits": True}],
        {"totalWordCount": 2, "typical": "A1", "coverage": "A1",
         "offListPercent": 0},
        _cdpays, "B1", cando_diff=True)
    check("summary cando-diff: section lists the shared demands",
          "## Can-Do demands across the set" in _cdsum
          and "| Vocabulary | B2 |" in _cdsum
          and "a.txt, b.txt" in _cdsum
          and "distinct Can-Do levels above the target" in _cdsum)
    _cdsum_band = cp.set_summary_markdown(
        [{"file": "a.txt", "totalWordCount": 1,
          "vocabulary": {"typical": "A1", "coverage": "A1"},
          "grammar": None, "estimatedLevel": "A1", "aboveTargetPercent": 0,
          "fits": True},
         {"file": "b.txt", "totalWordCount": 1,
          "vocabulary": {"typical": "A1", "coverage": "A1"},
          "grammar": None, "estimatedLevel": "A1", "aboveTargetPercent": 0,
          "fits": True}],
        {"totalWordCount": 2, "typical": "A1", "coverage": "A1",
         "offListPercent": 0},
        _sort_pays, "B1", cando_diff=True, cando_diff_sort="band")
    check("summary cando-diff: band sort renders ladder-first",
          _cdsum_band.index("| Vocabulary | B1 |")
          < _cdsum_band.index("| Vocabulary | C1 |"))
    check("summary without cando-diff has no demands section",
          "Can-Do demands" not in cp.set_summary_markdown(
              [{"file": "a.txt", "totalWordCount": 1,
                "vocabulary": {"typical": "A1", "coverage": "A1"},
                "grammar": None, "estimatedLevel": "A1",
                "aboveTargetPercent": 0, "fits": True}],
              {"totalWordCount": 1, "typical": "A1", "coverage": "A1",
               "offListPercent": 0},
              [{"file": "a.txt", "cando": None}], "B1"))
    check("curriculum grid path named after source folder",
          cp.curriculum_coverage_path(_tmp, "B1", None)
          == os.path.join(_tmp, os.path.basename(_tmp) + "-curriculum-coverage-B1.csv"))
    check("curriculum grid path into --output dir",
          cp.curriculum_coverage_path(None, "B1", os.path.join(_tmp, "decks"))
          == os.path.join(_tmp, "decks", "class-curriculum-coverage-B1.csv"))
    check("curriculum grid is an export artifact (re-scan skips it)",
          cp.is_export_artifact("essays-curriculum-coverage-B1.csv"))

    # --- unit: folder watch mode ----------------------------------------------
    _wdir = tempfile.mkdtemp(prefix="classprof_watch_")
    try:
        with open(os.path.join(_wdir, "a.txt"), "w", encoding="utf-8") as f:
            f.write(_EASY)
        _snap1 = cp._input_snapshot(_wdir)
        time.sleep(0.02)
        with open(os.path.join(_wdir, "a.txt"), "w", encoding="utf-8") as f:
            f.write(_EASY + " More words here.")
        _snap2 = cp._input_snapshot(_wdir)
        check("folder snapshot detects a change",
              _snap1 is not None and _snap2 is not None and _snap1 != _snap2)
        with open(os.path.join(_wdir, "b.txt"), "w", encoding="utf-8") as f:
            f.write(_MID)
        _snap3 = cp._input_snapshot(_wdir)
        check("folder snapshot detects added files",
              _snap3 is not None and set(_snap3) - set(_snap2))
        check("folder snapshot of a missing dir is None",
              cp._input_snapshot(os.path.join(_wdir, "nope")) is None)
        _w_runs = []

        def _w_cb():
            _w_runs.append(cp._input_snapshot(_wdir))

        _tw = threading.Thread(target=lambda: cp.watch_input(_wdir, 0.01, _w_cb,
                                                             timeout=2), daemon=True)
        _tw.start()
        time.sleep(0.1)
        with open(os.path.join(_wdir, "c.txt"), "w", encoding="utf-8") as f:
            f.write(_HARD)
        time.sleep(0.1)
        for _f in os.listdir(_wdir):
            os.remove(os.path.join(_wdir, _f))
        _tw.join(3)
        check("folder watch: re-runs on change and stops when empty",
              len(_w_runs) >= 1)
    finally:
        shutil.rmtree(_wdir, ignore_errors=True)

    # --- unit: --curriculum wires the checklist per text ----------------------
    _curr_dir2 = tempfile.mkdtemp(prefix="classprof_curr_")
    _curr_path2 = os.path.join(_curr_dir2, "unit.txt")
    with open(_curr_path2, "w", encoding="utf-8") as f:
        f.write("[vocabulary]\npurchase\nmat\n\n[grammar]\npassive_present\n")
    _curriculum2 = tr.load_curriculum(_curr_path2)
    _prof_cc = cp.build_row("We purchase the equipment daily.", "c.txt", _ENG,
                            False, "B1")
    _cc = cp.export_payload(_prof_cc[0], _prof_cc[1], _prof_cc[2], "B1",
                            curriculum=_curriculum2)
    check("export payload carries the curriculum checklist",
          _cc.get("curriculum") is not None
          and _cc["curriculum"]["grammarAvailable"] is False)
    check("curriculum marks presence per text with the band",
          any(d["word"] == "purchase" and d["present"] is True
              and d["level"] == "B2" for d in _cc["curriculum"]["vocabulary"])
          and any(d["word"] == "mat" and d["present"] is False
                  for d in _cc["curriculum"]["vocabulary"]))
    check("per-text handout renders the curriculum checklist section",
          "## Curriculum checklist" in tr.export_markdown(_cc))
    check("export payload without curriculum: no checklist",
          cp.export_payload(_prof_cc[0], _prof_cc[1], _prof_cc[2], "B1")
          .get("curriculum") is None)

    rows = []
    for label, text in [("b", _EASY), ("a", _HARD)]:
        _r, _o, _c = cp.build_row(text, label, _ENG, False, None)
        rows.append(_r)

    # --- unit: CSV with multiple targets ---------------------------------------
    csv_multi = cp.rows_to_csv(rows + [rowm, rowm2], None, ["A2", "B1"])
    csv_multi_rows = list(_csv.reader(csv_multi.splitlines()))
    check("csv targets header", csv_multi_rows[0][7:] ==
          ["fits_A2", "above_pct_A2", "fits_B1", "above_pct_B1"])
    check("sort level: A1 before C2", [r["file"] for r in cp.sort_rows(rows, "level")] == ["b", "a"])
    check("sort name: a before b", [r["file"] for r in cp.sort_rows(rows, "name")] == ["a", "b"])
    check("sort words: longest first", [r["file"] for r in cp.sort_rows(rows, "words")] == ["b", "a"])
    check("filter max A2 keeps easy only",
          [r["file"] for r in cp.filter_rows(rows, None, "A2")] == ["b"])
    check("filter min C2 keeps hard only",
          [r["file"] for r in cp.filter_rows(rows, "C2", None)] == ["a"])
    check("filter no bounds keeps all", len(cp.filter_rows(rows, None, None)) == 2)

    # --- unit: vocab-list export by band --------------------------------------
    outdir = os.path.join(_tmp, "vlists")
    written = cp.export_vocab_lists(agg["words"], outdir)
    check("export writes per-band files", len(written) >= 3)
    bnames = {os.path.basename(p) for p in written}
    check("export band filenames", {"vocab-a1.csv", "vocab-c2.csv"} <= bnames)
    with open(os.path.join(outdir, "vocab-a1.csv"), encoding="utf-8") as f:
        export_rows = list(_csv.reader(f))
    check("export header", export_rows[0] == ["word", "occurrences", "texts"])
    the_row = next((r for r in export_rows[1:] if r[0] == "the"), None)
    # 'The' + 'on the mat' in EASY, plus one in HARD -> 3 occurrences, 2 texts.
    check("export aggregates 'the' across texts",
          the_row is not None and the_row[1] == "3" and the_row[2] == "2")

    # --- unit: CSV + pretty rendering -----------------------------------------
    csv_txt = cp.rows_to_csv(rows, "B1")
    csv_rows = list(_csv.reader(csv_txt.splitlines()))
    check("csv header with target",
          csv_rows[0] == ["file", "total_words", "vocab_typical", "vocab_reached",
                          "grammar_typical", "grammar_reaches", "estimated_level",
                          "above_target_pct", "fits"])
    check("csv 2 data rows", len(csv_rows) == 3)

    buf = io.StringIO()
    cp.render_pretty(rows, summ, {
        "source": _tmp, "texts": 2, "selected": 2, "skipped": [],
        "target": "B1", "fitsCount": 1, "sort": "level",
        "min_level": None, "max_level": "B1", "hidden": 1, "grammar_note": None,
    }, stream=buf)
    pretty = buf.getvalue()
    check("pretty header", "Class Profile" in pretty)
    check("pretty aggregate", "Aggregate vocabulary" in pretty and "Typical:" in pretty)
    check("pretty table header", "fits" in pretty)
    check("pretty non-tty has no ANSI", "\x1b[" not in pretty)

    buf2 = io.StringIO()
    cp.render_pretty([rowm, rowm2], summ, {
        "source": _tmp, "texts": 2, "selected": 2, "skipped": [],
        "target": None, "targets": ["A2", "B1"],
        "fitsCount": {"A2": 1, "B1": 1}, "sort": "level",
        "min_level": None, "max_level": None, "hidden": 0, "grammar_note": None,
    }, stream=buf2)
    pretty2 = buf2.getvalue()
    check("pretty targets summary line", "Targets A2, B1" in pretty2)
    check("pretty targets columns", "  A2  " in pretty2 and "  B1  " in pretty2)
    check("pretty targets fit marks", "✓" in pretty2 and "✗" in pretty2)

    # --- integration: directory -> JSON ---------------------------------------
    rc, out, err = run(["--file", _tmp, "--target-level", "B1"])
    check("dir json rc==0", rc == 0)
    d = json.loads(out)
    check("json texts 3", d["texts"] == 3)
    check("json skipped has the empty file",
          len(d["skipped"]) == 1 and "empty.txt" in d["skipped"][0]["file"])
    check("json fitsCount 2", d["fitsCount"] == 2)
    check("json rows sorted by estimated level asc",
          [r["estimatedLevel"] for r in d["rows"]] == ["A1", "B1", "C2"])
    # 13 (easy) + 17 (mid.md: 'Title' heading text survives md-stripping) + 12 (hard).
    check("json aggregate total matches sum", d["aggregate"]["totalWordCount"] == 42)
    check("json row carries grammar null or dict",
          all(r["grammar"] is None or set(r["grammar"]) == {"typical", "reaches"}
              for r in d["rows"]))
    if HAVE_GRAMMAR:
        check("json grammar populated", all(r["grammar"] is not None for r in d["rows"]))
        check("json grammar bands valid",
              all(r["grammar"]["typical"] in vp.CEFR_ORDER
                  and r["grammar"]["reaches"] in vp.CEFR_ORDER for r in d["rows"]))
        check("json grammarError null", d["grammarError"] is None)
    else:
        skipped += 1

    # --- integration: --format csv --------------------------------------------
    rc, out, err = run(["--file", _tmp, "--target-level", "B1", "--format", "csv"])
    check("csv rc==0", rc == 0)
    csv_rows = list(_csv.reader(out.splitlines()))
    check("csv header + 3 rows", len(csv_rows) == 4)
    check("csv fits column", [r[-1] for r in csv_rows[1:]] == ["yes", "yes", "no"])

    # --- integration: rank & filter -------------------------------------------
    rc, out, _ = run(["--file", _tmp, "--max-level", "B1", "--format", "csv"])
    csv_rows = list(_csv.reader(out.splitlines()))
    check("max-level B1 keeps 2 texts", len(csv_rows) == 3)
    check("max-level B1 excludes hard", all("hard" not in r[0] for r in csv_rows[1:]))

    rc, out, _ = run(["--file", _tmp, "--sort", "words", "--format", "csv"])
    csv_rows = list(_csv.reader(out.splitlines()))
    check("sort words: mid (16) first",
          len(csv_rows) == 4 and "mid.md" in csv_rows[1][0])

    # --- integration: glob / single file / --text / stdin ----------------------
    rc, out, _ = run(["--file", os.path.join(_tmp, "*.md"), "--format", "csv"])
    csv_rows = list(_csv.reader(out.splitlines()))
    check("glob md only", len(csv_rows) == 2 and "mid.md" in csv_rows[1][0])

    rc, out, _ = run(["--file", os.path.join(_tmp, "easy.txt"), "--format", "csv"])
    csv_rows = list(_csv.reader(out.splitlines()))
    check("single file -> one row", len(csv_rows) == 2)

    rc, out, _ = run(["--text", _EASY, "--format", "csv"])
    csv_rows = list(_csv.reader(out.splitlines()))
    check("--text -> one row labelled (text)", len(csv_rows) == 2 and csv_rows[1][0] == "(text)")

    rc, out, _ = run(["--format", "csv"], _EASY)
    csv_rows = list(_csv.reader(out.splitlines()))
    check("stdin -> one row labelled (stdin)", len(csv_rows) == 2 and csv_rows[1][0] == "(stdin)")

    # --- integration: export-vocab through the CLI -----------------------------
    vdir = os.path.join(_tmp, "cli-vlists")
    rc, out, err = run(["--file", _tmp, "--no-grammar", "--export-vocab", vdir])
    check("export-vocab rc==0", rc == 0)
    check("export-vocab note on stderr", "Wrote" in err)
    check("export-vocab wrote band files", os.path.isfile(os.path.join(vdir, "vocab-a1.csv")))

    # --- integration: .docx and .pdf in the folder scan ------------------------
    _tmpf = tempfile.mkdtemp(prefix="classprof_fmt_")
    try:
        with open(os.path.join(_tmpf, "easy.txt"), "w", encoding="utf-8") as f:
            f.write(_EASY)
        _make_docx(os.path.join(_tmpf, "doc.docx"))
        with open(os.path.join(_tmpf, "doc.pdf"), "wb") as f:
            f.write(_minimal_pdf("The cat sat on the mat."))
        names = [os.path.basename(p) for p in cp.discover_files(_tmpf)]
        check("folder scan discovers txt + docx + pdf",
              names == ["doc.docx", "doc.pdf", "easy.txt"])

        rc, out, err = run(["--file", _tmpf, "--no-grammar", "--format", "csv"])
        check("formats csv rc==0", rc == 0)
        rows_f = list(_csv.reader(out.splitlines()))
        docx_row = next((r for r in rows_f[1:] if r[0].endswith("doc.docx")), None)
        check("formats: docx profiled from the scan",
              docx_row is not None and docx_row[1] == "6")
        # --no-grammar skips the venv re-exec, so the subprocess runs in the
        # same interpreter as this test: the PDF is profiled exactly when
        # pypdf is importable here, otherwise skipped gracefully (never
        # fatal). This also guards the re-exec-skip behaviour itself.
        pdf_row = next((r for r in rows_f[1:] if r[0].endswith("doc.pdf")), None)
        if _HAS_PYPDF:
            check("formats w/ pypdf: pdf profiled (re-exec skipped)",
                  pdf_row is not None and pdf_row[1] == "6")
        else:
            check("formats w/o pypdf: pdf skipped with hint",
                  pdf_row is None and "doc.pdf" in err and "pip install pypdf" in err)
    finally:
        shutil.rmtree(_tmpf, ignore_errors=True)

    # --- integration: --targets across several class levels --------------------
    rc, out, _ = run(["--file", _tmp, "--targets", "A2,B1", "--no-grammar"])
    d = json.loads(out)
    check("targets payload list", d["targets"] == ["A2", "B1"])
    check("targets fitsCount map", d["fitsCount"] == {"A2": 1, "B1": 2})
    hard_row = next(r for r in d["rows"] if "hard.txt" in r["file"])
    check("targets row map populated",
          hard_row["targets"]["A2"]["fits"] is False
          and hard_row["targets"]["B1"]["fits"] is False)
    check("targets singular fields null",
          hard_row["aboveTargetPercent"] is None and hard_row["fits"] is None)

    rc, out, _ = run(["--file", _tmp, "--targets", "A2,B1", "--no-grammar",
                      "--format", "csv"])
    csv_rows = list(_csv.reader(out.splitlines()))
    check("targets csv header",
          csv_rows[0][7:] == ["fits_A2", "above_pct_A2", "fits_B1", "above_pct_B1"])
    check("targets csv values", all(len(r) == 11 for r in csv_rows[1:]))

    # --- integration: per-text pre-teaching export -----------------------------
    pret = os.path.join(_tmp, "pret")
    rc, out, err = run(["--file", _tmp, "--target-level", "B1", "--no-grammar",
                        "--export", "md", "--output", pret])
    check("export md rc==0", rc == 0)
    check("export md wrote one list per text",
          os.path.isfile(os.path.join(pret, "easy-preteaching-B1.md"))
          and os.path.isfile(os.path.join(pret, "hard-preteaching-B1.md")))
    with open(os.path.join(pret, "easy-preteaching-B1.md"), encoding="utf-8") as f:
        handout = f.read()
    check("export md is a real handout",
          "Pre-teaching list" in handout and "Verdict:" in handout
          and "Words above B1" in handout)
    summaries = [f for f in os.listdir(pret) if f.endswith("-summary-B1.md")]
    check("export md writes one set-level summary handout", len(summaries) == 1)
    with open(os.path.join(pret, summaries[0]), encoding="utf-8") as f:
        s_md = f.read()
    check("set summary aggregates the whole set",
          "# Set summary — Target B1 (3 texts)" in s_md
          and "Aggregate vocabulary" in s_md
          and "easy.txt" in s_md and "mid.md" in s_md and "hard.txt" in s_md
          and "pre-teach" in s_md)
    # A next-to-source export must not be re-profiled on a later re-run:
    # write handouts into the folder itself, then re-scan.
    rc, _, _ = run(["--file", _tmp, "--target-level", "B1", "--no-grammar",
                    "--export", "md", "--output", _tmp])
    check("next-to-source md export rc==0", rc == 0)
    names = [os.path.basename(f) for f in cp.discover_files(_tmp)]
    check("re-scan skips the handouts it just wrote",
          "easy-preteaching-B1.md" not in names
          and "hard-preteaching-B1.md" not in names
          and not any(f.endswith("-summary-B1.md") for f in names))
    for _h in ("easy-preteaching-B1.md", "mid-preteaching-B1.md",
               "hard-preteaching-B1.md",
               os.path.basename(os.path.join(pret, summaries[0]))):
        _p = os.path.join(_tmp, _h)
        if os.path.isfile(_p):
            os.remove(_p)

    # --- integration: --suggest in the per-text handouts -----------------------
    _sug_in = tempfile.mkdtemp(prefix="classprof_sug_")
    try:
        with open(os.path.join(_sug_in, "purchase.txt"), "w",
                  encoding="utf-8") as f:
            f.write("We purchase fresh bread daily, and the circumstances "
                    "rarely change.")
        _sug_out = os.path.join(_sug_in, "out")
        rc, out, err = run(["--file", _sug_in, "--target-level", "B1", "--no-grammar",
                            "--export", "md", "--suggest", "--output", _sug_out])
        check("class --suggest rc==0", rc == 0)
        with open(os.path.join(_sug_out, "purchase-preteaching-B1.md"),
                  encoding="utf-8") as f:
            _sug_md = f.read()
        check("class --suggest handout suggests the swaps",
              "Simpler alternative" in _sug_md
              and "| buy (A1) |" in _sug_md
              and "| situation (A2) |" in _sug_md)
        rc, _, err = run(["--file", _sug_in, "--target-level", "B1", "--suggest"])
        check("class --suggest without export rc==1",
              rc == 1 and "--suggest requires --export" in err)
        rc, _, err = run(["--file", _sug_in, "--target-level", "B1",
                          "--export", "flashcards", "--suggest", "--no-enrich"])
        check("class --suggest with flashcards rc==1",
              rc == 1 and "applies to the md/csv" in err)
    finally:
        shutil.rmtree(_sug_in, ignore_errors=True)

    # --- integration: --gap-report in the per-text handouts -------------------
    if HAVE_GRAMMAR:
        _gap_out = os.path.join(_tmp, "gapout")
        rc, out, err = run(["--file", _tmp, "--target-level", "B1",
                            "--gap-report", "--export", "md", "--output", _gap_out])
        check("class --gap-report rc==0", rc == 0)
        with open(os.path.join(_gap_out, "easy-preteaching-B1.md"),
                  encoding="utf-8") as f:
            _gap_md = f.read()
        check("class --gap-report handout lists missing constructions",
              "## Constructions to introduce at B1" in _gap_md
              and "not used" in _gap_md)
        check("class --gap-report only on request",
              "Constructions to introduce" not in handout)
    else:
        skipped += 1
    rc, _, err = run(["--file", _tmp, "--target-level", "B1", "--gap-report"])
    check("class --gap-report without export rc==1",
          rc == 1 and "--gap-report requires --export" in err)
    rc, _, err = run(["--file", _tmp, "--target-level", "B1",
                      "--export", "flashcards", "--gap-report", "--no-enrich"])
    check("class --gap-report with flashcards rc==1",
          rc == 1 and "applies to the md/csv" in err)

    # --- integration: --curriculum in the per-text handouts -------------------
    _curr_cl_dir = tempfile.mkdtemp(prefix="classprof_currcl_")
    _curr_cl = os.path.join(_curr_cl_dir, "unit.txt")
    with open(_curr_cl, "w", encoding="utf-8") as f:
        f.write("[vocabulary]\npurchase\nmat\n\n[grammar]\npassive_present\n")
    _curr_in = tempfile.mkdtemp(prefix="classprof_currcli_")
    try:
        with open(os.path.join(_curr_in, "purchase.txt"), "w",
                  encoding="utf-8") as f:
            f.write("We purchase fresh bread daily.")
        _curr_out = os.path.join(_curr_in, "out")
        rc, out, err = run(["--file", _curr_in, "--target-level", "B1",
                            "--no-grammar", "--export", "md", "--curriculum",
                            _curr_cl, "--output", _curr_out])
        check("class --curriculum rc==0", rc == 0)
        with open(os.path.join(_curr_out, "purchase-preteaching-B1.md"),
                  encoding="utf-8") as f:
            _cc_md = f.read()
        check("class --curriculum handout carries the checklist",
              "## Curriculum checklist" in _cc_md
              and "| purchase | vocabulary | present | B2 |" in _cc_md
              and "| mat | vocabulary | missing | — |" in _cc_md)
        rc, _, err = run(["--file", _curr_in, "--target-level", "B1",
                          "--curriculum", _curr_cl])
        check("class --curriculum without --export rc==1",
              rc == 1 and "--curriculum needs --export md" in err)
        rc, _, err = run(["--file", _curr_in, "--target-level", "B1", "--export", "md",
                          "--curriculum", os.path.join(_curr_cl_dir, "nope.txt")])
        check("class --curriculum missing file rc==1",
              rc == 1 and "curriculum file not found" in err)
        # Grammar items are resolved against the construction list up front:
        # a typo'd name warns (with a hint) before profiling, run continues.
        _typo_curr = os.path.join(_curr_cl_dir, "gramtypo.txt")
        with open(_typo_curr, "w", encoding="utf-8") as f:
            f.write("[grammar]\nsecond conditinal\n")
        rc, out, err = run(["--file", _curr_in, "--target-level", "B1", "--no-grammar",
                            "--format", "json", "--curriculum", _typo_curr])
        check("class --curriculum grammar-item warning before profiling",
              rc == 0 and "Did you mean 'second conditional'?" in err
              and "is not recognised" in err)
        # --export csv --curriculum: the folder-level coverage grid.
        _cc_csv_out = os.path.join(_curr_in, "csvout")
        rc, out, err = run(["--file", _curr_in, "--target-level", "B1", "--no-grammar",
                            "--export", "csv", "--curriculum", _curr_cl,
                            "--output", _cc_csv_out])
        check("class --curriculum csv grid rc==0", rc == 0)
        with open(os.path.join(_cc_csv_out,
                               os.path.basename(_curr_in) + "-curriculum-coverage-B1.csv"),
                  encoding="utf-8") as f:
            _cc_rows = list(_csv.reader(f))
        check("class --curriculum csv grid shape",
              _cc_rows[0] == ["text", "purchase", "mat", "Passive (present)", "pass"]
              and len(_cc_rows) == 2
              and _cc_rows[1][0] == "purchase.txt"
              and _cc_rows[1][1] == "yes" and _cc_rows[1][2] == "no"
              and _cc_rows[1][4] == "no")
        # --format json --curriculum: the same grid inside the payload, so
        # scripts can consume the pass/fail matrix without CSV parsing.
        rc, out, err = run(["--file", _curr_in, "--target-level", "B1",
                            "--no-grammar", "--format", "json",
                            "--curriculum", _curr_cl])
        _ccj = json.loads(out)["curriculumCoverage"]
        check("class --curriculum json grid in payload",
              rc == 0 and _ccj["items"] == [["vocabulary", "purchase"],
                                             ["vocabulary", "mat"],
                                             ["grammar", "Passive (present)"]]
              and len(_ccj["rows"]) == 1
              and _ccj["rows"][0]["text"] == "purchase.txt"
              and _ccj["rows"][0]["cells"] == [True, False, False]
              and _ccj["rows"][0]["pass"] is False
              and _ccj["textCount"] == 1 and _ccj["passCount"] == 0)
    finally:
        shutil.rmtree(_curr_in, ignore_errors=True)
        shutil.rmtree(_curr_cl_dir, ignore_errors=True)

    # --- integration: --cando Can-Do framing in the per-text handouts --------
    _cd_in = tempfile.mkdtemp(prefix="classprof_cando_")
    try:
        with open(os.path.join(_cd_in, "purchase.txt"), "w",
                  encoding="utf-8") as f:
            f.write("We purchase fresh bread daily.")
        _cd_out = os.path.join(_cd_in, "out")
        rc, out, err = run(["--file", _cd_in, "--target-level", "B1",
                            "--no-grammar", "--export", "md", "--cando",
                            "--output", _cd_out])
        check("class --cando rc==0", rc == 0)
        with open(os.path.join(_cd_out, "purchase-preteaching-B1.md"),
                  encoding="utf-8") as f:
            _cd_md = f.read()
        check("class --cando handout carries the Can-Do framing",
              "## Can-Do descriptors" in _cd_md
              and "### Above the B1 target" in _cd_md
              and "| Vocabulary | B2 |" in _cd_md
              and "pre-teach or rewrite" in _cd_md)
        rc, _, err = run(["--file", _cd_in, "--target-level", "B1", "--cando"])
        check("class --cando without --export rc==1",
              rc == 1 and "--cando requires --export" in err)
        # --cando --export flashcards: a combined Can-Do reference deck next
        # to the word decks, in the same RubricMaker shape.
        _cd_deck = os.path.join(_cd_in, "deckout")
        rc, out, err = run(["--file", _cd_in, "--target-level", "B1",
                            "--no-grammar", "--cando", "--export", "flashcards",
                            "--no-enrich", "--output", _cd_deck])
        check("class --cando deck rc==0", rc == 0)
        with open(os.path.join(
                _cd_deck, os.path.basename(_cd_in) + "-preteaching-B1-cando-deck.csv"),
                encoding="utf-8") as f:
            _cd_rows = list(_csv.reader(f))
        check("class --cando deck carries the demands in RubricMaker shape",
              _cd_rows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"]
              and len(_cd_rows) >= 2
              and all(r[0].endswith("demand") and r[4] == "cando"
                      for r in _cd_rows[1:]))
        # --cando-diff: the set-level demands section in the summary handout.
        rc, _, err = run(["--file", _cd_in, "--target-level", "B1",
                          "--cando-diff", "--export", "flashcards", "--no-enrich"])
        check("class --cando-diff with flashcards rc==1",
              rc == 1 and "--cando-diff" in err and "requires --export md|csv" in err)
        # A two-text folder: --cando-diff --export md puts the shared
        # above-target demands into the summary handout.
        with open(os.path.join(_cd_in, "easy.txt"), "w", encoding="utf-8") as f:
            f.write("I am a student.")
        _cd_sum = os.path.join(_cd_in, "sumout")
        rc, out, err = run(["--file", _cd_in, "--target-level", "B1",
                            "--no-grammar", "--cando-diff", "--export", "md",
                            "--output", _cd_sum])
        check("class --cando-diff md rc==0", rc == 0)
        with open(os.path.join(_cd_sum, os.path.basename(_cd_in) + "-summary-B1.md"),
                  encoding="utf-8") as f:
            _cd_sum_md = f.read()
        check("class --cando-diff summary lists the shared demands",
              "## Can-Do demands across the set" in _cd_sum_md
              and "| Vocabulary | B2 |" in _cd_sum_md
              and "purchase.txt" in _cd_sum_md
              and "distinct Can-Do levels above the target" in _cd_sum_md)
        # --cando-diff-sort band: the same section ordered by the ladder.
        # Two bands above the B1 target (B2 from purchase.txt, C1 from a
        # text using a C1 word), so the ordering assertion is meaningful.
        with open(os.path.join(_cd_in, "advanced.txt"), "w",
                  encoding="utf-8") as f:
            f.write("We purchase fresh bread and cite the results.")
        rc, out, err = run(["--file", _cd_in, "--target-level", "B1",
                            "--no-grammar", "--cando-diff", "--cando-diff-sort", "band",
                            "--export", "md", "--output", _cd_sum])
        check("class --cando-diff-sort band rc==0", rc == 0)
        with open(os.path.join(_cd_sum, os.path.basename(_cd_in) + "-summary-B1.md"),
                  encoding="utf-8") as f:
            _cd_sort_md = f.read()
        check("class --cando-diff-sort band renders ladder-first",
              "## Can-Do demands across the set" in _cd_sort_md
              and "| Vocabulary | B2 |" in _cd_sort_md
              and "| Vocabulary | C1 |" in _cd_sort_md
              and _cd_sort_md.index("| Vocabulary | B2 |")
              < _cd_sort_md.index("| Vocabulary | C1 |"))
        rc, _, err = run(["--file", _cd_in, "--target-level", "B1",
                          "--cando-diff-sort", "band", "--export", "md"])
        check("class --cando-diff-sort without --cando-diff rc==1",
              rc == 1 and "--cando-diff-sort" in err and "requires --cando-diff" in err)
        rc, _, err = run(["--file", _cd_in, "--target-level", "B1",
                          "--cando-diff", "--cando-diff-sort", "weird", "--export", "md"])
        check("class --cando-diff-sort unknown value rc==2",
              rc == 2 and "invalid choice" in err)
    finally:
        shutil.rmtree(_cd_in, ignore_errors=True)

    # --- integration: --interleave spaced introduction schedule ---------------
    _il_in = tempfile.mkdtemp(prefix="classprof_il_")
    try:
        with open(os.path.join(_il_in, "a.txt"), "w", encoding="utf-8") as f:
            f.write("We purchase fresh bread and the circumstances matter. "
                    "We utilize the tools and acquire the equipment.")
        with open(os.path.join(_il_in, "b.txt"), "w", encoding="utf-8") as f:
            f.write("The committee will announce the outcome next week.")
        _il_out = os.path.join(_il_in, "out")
        rc, out, err = run(["--file", _il_in, "--target-level", "B1",
                            "--no-grammar", "--interleave", "--export", "md",
                            "--output", _il_out])
        check("class --interleave rc==0", rc == 0)
        _sched = os.path.join(_il_out, os.path.basename(_il_in)
                              + "-interleave-B1.md")
        check("interleave schedule written next to the handouts",
              os.path.isfile(_sched))
        with open(_sched, encoding="utf-8") as f:
            _il_md = f.read()
        check("interleave schedule header and sections",
              "# Vocabulary interleaving — Target B1 (2 readings, "
              "5 new words/reading)" in _il_md
              and "## Reading 1 — a.txt" in _il_md
              and "## Reading 2 — b.txt" in _il_md
              and "## Word index" in _il_md)
        # One printable handout per reading: that reading's introduce words
        # with the in-text sentence each appears in (the definition back).
        _r1_md = os.path.join(_il_out, os.path.basename(_il_in)
                              + "-interleave-B1-reading-1.md")
        with open(_r1_md, encoding="utf-8") as f:
            _rmd = f.read()
        check("reading handout written with introduce definitions",
              "# Reading 1 — a.txt" in _rmd
              and "## Introduce (" in _rmd
              and "| Word | Level | Definition |" in _rmd
              and "| `purchase` | B2 |" in _rmd
              and "| `circumstances` | B2 |" in _rmd
              and "We purchase fresh bread and the circumstances matter" in _rmd)
        rc, out, err = run(["--file", _il_in, "--target-level", "B1",
                            "--no-grammar", "--interleave", "--format", "json"])
        d = json.loads(out)
        _il = d["interleave"]
        check("interleave json key with readings and word index",
              _il["targetLevel"] == "B1" and len(_il["readings"]) == 2
              and len(_il["words"]) >= 1
              and all(r["file"].endswith(".txt") for r in _il["readings"]))
        rc, out, err = run(["--file", _il_in, "--target-level", "B1",
                            "--no-grammar", "--interleave", "--export", "csv",
                            "--output", _il_out])
        _ilcsv = os.path.join(_il_out, os.path.basename(_il_in)
                              + "-interleave-B1.csv")
        with open(_ilcsv, encoding="utf-8") as f:
            _ilc_rows = list(_csv.reader(f))
        check("interleave csv shape",
              _ilc_rows[0] == ["word", "level", "introducedAt", "appearsIn",
                               "deferredFrom"] and len(_ilc_rows) >= 2)
        # A schedule written next to the sources must not be re-profiled.
        rc, _, _ = run(["--file", _il_in, "--target-level", "B1", "--no-grammar",
                        "--interleave", "--export", "md", "--output", _il_in])
        _il_names = [os.path.basename(f) for f in cp.discover_files(_il_in)]
        check("re-scan skips the interleave schedule",
              not any(f.endswith("-interleave-B1.md") for f in _il_names)
              and "a.txt" in _il_names)
        rc, _, err = run(["--file", _il_in, "--interleave"])
        check("class --interleave without target rc==1",
              rc == 1 and "--interleave builds a spaced" in err)
        rc, _, err = run(["--file", _il_in, "--target-level", "B1",
                          "--interleave", "--export", "flashcards", "--no-enrich"])
        check("class --interleave with flashcards rc==1",
              rc == 1 and "writes a csv/md schedule" in err)
        rc, _, err = run(["--file", _il_in, "--target-level", "B1",
                          "--interleave", "--new-words-per-reading", "0"])
        check("class --new-words-per-reading 0 rc==1",
              rc == 1 and "at least 1" in err)
    finally:
        shutil.rmtree(_il_in, ignore_errors=True)

    # --- integration: --watch validation + cache-backed reading handouts ------
    _wcli_in = tempfile.mkdtemp(prefix="classprof_watchcli_")
    try:
        with open(os.path.join(_wcli_in, "a.txt"), "w", encoding="utf-8") as f:
            f.write("We purchase fresh bread and the circumstances matter.")
        rc, _, err = run(["--watch", "--text", "hi"])
        check("class --watch requires --file",
              rc == 1 and "--watch re-profiles the input" in err)
        rc, _, err = run(["--file", _wcli_in, "--no-grammar", "--watch",
                          "--pre-enrich"])
        check("class --watch rejects --pre-enrich",
              rc == 1 and "--watch and --pre-enrich don't combine" in err)
        # Reading handouts reuse the dictionary cache when primed.
        _cache_path = os.path.join(_wcli_in, "cache.json")
        with open(_cache_path, "w", encoding="utf-8") as f:
            json.dump({"version": tr._CACHE_VERSION,
                       "entries": {tr._DICT_API: {
                           "purchase": {"definition": "to buy something",
                                         "phonetic": "/p/",
                                         "partOfSpeech": "verb"}}}},
                      f)
        _wcli_out = os.path.join(_wcli_in, "out")
        rc, out, err = run(["--file", _wcli_in, "--target-level", "B1", "--no-grammar",
                            "--interleave", "--export", "md", "--dictionary-cache",
                            _cache_path, "--output", _wcli_out])
        check("class reading handout with cache rc==0", rc == 0)
        with open(os.path.join(_wcli_out, os.path.basename(_wcli_in)
                               + "-interleave-B1-reading-1.md"),
                  encoding="utf-8") as f:
            _rh_md = f.read()
        check("reading handout uses the cached definition",
              "| `purchase` | B2 | to buy something |" in _rh_md
              and "| `circumstances` | B2 | We purchase fresh bread" in _rh_md)
    finally:
        shutil.rmtree(_wcli_in, ignore_errors=True)

    # --- integration: --pre-enrich --interleave primes the schedule's words ---
    _pe_in = tempfile.mkdtemp(prefix="classprof_pe_")
    try:
        with open(os.path.join(_pe_in, "a.txt"), "w", encoding="utf-8") as f:
            f.write("We purchase fresh bread and the circumstances matter.")
        with open(os.path.join(_pe_in, "b.txt"), "w", encoding="utf-8") as f:
            f.write("The committee will announce the outcome.")
        _pe_cache = os.path.join(_pe_in, "cache.json")
        rc, out, err = run(["--file", _pe_in, "--target-level", "B1", "--no-grammar",
                            "--pre-enrich", "--interleave", "--dictionary-cache",
                            _pe_cache, "--dictionary-url", _dict_url])
        check("interleave pre-enrich rc==0 and scoped note",
              rc == 0 and "interleave schedule's words" in err)
        with open(_pe_cache, encoding="utf-8") as f:
            _pe_data = json.load(f)
        _pe_bucket = list(_pe_data["entries"].values())[0]
        check("interleave pre-enrich primes exactly the schedule's words",
              set(_pe_bucket) == {"circumstances", "outcome", "purchase"})
    finally:
        shutil.rmtree(_pe_in, ignore_errors=True)

    # --- integration: --watch rebuilds decks and band exports on each save ----
    _warm_in = tempfile.mkdtemp(prefix="classprof_warm_")
    try:
        with open(os.path.join(_warm_in, "a.txt"), "w", encoding="utf-8") as f:
            f.write("We purchase fresh bread daily.")
        with open(os.path.join(_warm_in, "b.txt"), "w", encoding="utf-8") as f:
            f.write("The cat sat on the mat.")
        _warm_out = os.path.join(_warm_in, "out")
        rc, out, err = run(["--file", _warm_in, "--target-level", "B1", "--no-grammar",
                            "--export", "flashcards", "--no-enrich", "--export-vocab",
                            _warm_out, "--output", _warm_out])
        check("warm run rc==0", rc == 0)
        _deck_path = os.path.join(_warm_out, os.path.basename(_warm_in)
                                  + "-preteaching-B1-deck.csv")
        _deck1 = open(_deck_path, encoding="utf-8").read()
        _b2_path = os.path.join(_warm_out, "vocab-b2.csv")
        _b2_1 = open(_b2_path, encoding="utf-8").read()
        check("warm artifacts lack the new word",
              "purchase" in _deck1 and "circumstances" not in _deck1
              and "circumstances" not in _b2_1)
        _wlog = open(os.path.join(_warm_in, "watch.log"), "w")
        _wproc = subprocess.Popen(
            [sys.executable, SCRIPT, "--file", _warm_in, "--target-level", "B1",
             "--no-grammar", "--watch", "0.05", "--export", "flashcards",
             "--no-enrich", "--export-vocab", _warm_out, "--output", _warm_out],
            stdout=_wlog, stderr=subprocess.STDOUT, cwd=HERE)
        try:
            time.sleep(1.2)
            with open(os.path.join(_warm_in, "a.txt"), "a", encoding="utf-8") as f:
                f.write(" The committee will analyse the circumstances.")
            time.sleep(1.2)
        finally:
            _wproc.terminate()
            try:
                _wproc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _wproc.kill()
            _wlog.close()
        _deck2 = open(_deck_path, encoding="utf-8").read()
        _b2_2 = open(_b2_path, encoding="utf-8").read()
        check("watch rebuilds the combined deck with the new word",
              "circumstances" in _deck2)
        check("watch rebuilds the band export with the new word",
              "circumstances" in _b2_2)
    finally:
        shutil.rmtree(_warm_in, ignore_errors=True)

    rc, out, err = run(["--file", os.path.join(_tmp, "easy.txt"), "--target-level", "B1",
                        "--no-grammar", "--export", "csv"])
    check("export csv written next to source",
          rc == 0 and os.path.isfile(os.path.join(_tmp, "easy-preteaching-B1.csv")))

    deckdir = os.path.join(_tmp, "decks")
    rc, out, err = run(["--file", _tmp, "--target-level", "B1", "--no-grammar",
                        "--export", "flashcards", "--no-enrich", "--output", deckdir])
    check("export flashcards rc==0", rc == 0)
    deck = os.path.join(deckdir, "easy-preteaching-B1-deck.csv")
    check("deck written", os.path.isfile(deck))
    with open(deck, encoding="utf-8") as f:
        deck_rows = list(_csv.reader(f))
    check("deck has RubricMaker import shape",
          deck_rows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"])
    check("deck backs are in-context without enrichment",
          deck_rows[1][1] == "The cat sat on the mat"
          and deck_rows[1][1] == deck_rows[1][2])

    # --- integration: combined class-wide deck --------------------------------
    per_text_decks = {"easy-preteaching-B1-deck.csv", "mid-preteaching-B1-deck.csv",
                      "hard-preteaching-B1-deck.csv"}
    combined = [f for f in os.listdir(deckdir)
                if f.endswith("-preteaching-B1-deck.csv") and f not in per_text_decks]
    check("combined deck written alongside per-text decks", len(combined) == 1)
    with open(os.path.join(deckdir, combined[0]), encoding="utf-8") as f:
        combined_rows = list(_csv.reader(f))
    check("combined deck header", combined_rows[0] ==
          ["word", "definition", "example", "phonetic", "partOfSpeech"])
    combined_words = {r[0] for r in combined_rows[1:]}
    check("combined deck aggregates words across texts",
          {"circumstances", "implications", "mat"} <= combined_words)
    combined_index = os.path.join(
        deckdir, combined[0][:-len("-deck.csv")] + "-index.md")
    check("combined deck index written too", os.path.isfile(combined_index))
    with open(combined_index, encoding="utf-8") as f:
        index_md = f.read()
    check("combined index lists words and their source texts",
          "mat" in index_md and "easy.txt" in index_md and "hard.txt" in index_md)
    check("combined index is level-keyed (glossary per band)",
          "| Word | Level | Occurrences | Texts |" in index_md
          and "| circumstances |" in index_md and "| B2 |" in index_md)
    check("index texts column lists only sources, not the tool's own files",
          "-preteaching-" not in index_md and "-summary-" not in index_md)

    # --- integration: one combined deck per level with --targets ---------------
    lvl_decks = os.path.join(_tmp, "lvl-decks")
    rc, out, err = run(["--file", _tmp, "--targets", "A2,B1", "--no-grammar",
                        "--export", "flashcards", "--no-enrich", "--output", lvl_decks])
    check("targets+flashcards rc==0", rc == 0)
    lvl_files = sorted(os.listdir(lvl_decks))
    base = os.path.basename(_tmp)
    check("targets+flashcards: one deck + index per level, no per-text decks",
          lvl_files == [f"{base}-preteaching-A2-deck.csv",
                        f"{base}-preteaching-A2-index.md",
                        f"{base}-preteaching-B1-deck.csv",
                        f"{base}-preteaching-B1-index.md"])
    with open(os.path.join(lvl_decks, f"{base}-preteaching-B1-index.md"),
              encoding="utf-8") as f:
        lvl_index = f.read()
    check("per-level index lists words and their sources",
          "circumstances" in lvl_index and "hard.txt" in lvl_index)
    with open(os.path.join(lvl_decks, f"{base}-preteaching-A2-deck.csv"),
              encoding="utf-8") as f:
        a2_words = {r[0] for r in list(_csv.reader(f))[1:]}
    with open(os.path.join(lvl_decks, f"{base}-preteaching-B1-deck.csv"),
              encoding="utf-8") as f:
        b1_words = {r[0] for r in list(_csv.reader(f))[1:]}
    check("per-level decks: B1-above words are a subset of A2-above words",
          b1_words <= a2_words)
    check("per-level decks: A2 deck has words B1 deck doesn't",
          len(a2_words) > len(b1_words))

    # --- integration: --pre-enrich against the mock dictionary API -------------
    _pen = tempfile.mkdtemp(prefix="classprof_pen_")
    try:
        with open(os.path.join(_pen, "words.txt"), "w", encoding="utf-8") as f:
            f.write("circumstances implications mat")
        _pre_cache = os.path.join(_pen, "pre-cache.json")
        _before = _DictHandler.requests
        rc, out, err = run(["--file", _pen, "--pre-enrich", "--delay", "0",
                            "--dictionary-url", _dict_url,
                            "--dictionary-cache", _pre_cache])
        _after = _DictHandler.requests
        check("pre-enrich primes the cache in one pass",
              rc == 0 and out == "" and _after - _before == 3
              and "Pre-enriched 3 words (2 found, 1 not found)" in err)
        check("pre-enrich wrote the cache file", os.path.isfile(_pre_cache))
        rc2, _, err2 = run(["--file", _pen, "--pre-enrich", "--delay", "0",
                            "--dictionary-url", _dict_url,
                            "--dictionary-cache", _pre_cache])
        check("pre-enrich second pass makes no requests",
              rc2 == 0 and _DictHandler.requests == _after
              and "3 of 3 already cached" in err2)
    finally:
        shutil.rmtree(_pen, ignore_errors=True)

    # --- integration: --no-dictionary-cache skips the cache entirely -----------
    _ncd = tempfile.mkdtemp(prefix="classprof_ncd_")
    try:
        with open(os.path.join(_ncd, "words.txt"), "w", encoding="utf-8") as f:
            f.write("circumstances implications mat")
        _never_cache = os.path.join(_ncd, "should-not-exist.json")
        rc, out, err = run(["--file", _ncd, "--target-level", "B1", "--no-grammar",
                            "--export", "flashcards", "--dictionary-url", _dict_url,
                            "--dictionary-cache", _never_cache, "--no-dictionary-cache",
                            "--output", os.path.join(_ncd, "decks")])
        check("no-dictionary-cache: rc==0, no cache file written",
              rc == 0 and not os.path.exists(_never_cache))
        with open(os.path.join(_ncd, "decks", "words-preteaching-B1-deck.csv"),
                  encoding="utf-8") as f:
            _nrows = list(_csv.reader(f))
        check("no-dictionary-cache: still enriches from the API",
              any(r[0] == "circumstances"
                  and r[1] == "a fact connected with an event" for r in _nrows))
    finally:
        shutil.rmtree(_ncd, ignore_errors=True)

    # --- integration: enriched decks via the mock API + shared cache -----------
    _enf = tempfile.mkdtemp(prefix="classprof_enf_")
    try:
        with open(os.path.join(_enf, "words.txt"), "w", encoding="utf-8") as f:
            f.write("circumstances implications mat")
        _deck_cache = os.path.join(_enf, "deck-cache.json")
        _before = _DictHandler.requests
        rc, out, err = run(["--file", _enf, "--target-level", "B1", "--no-grammar",
                            "--export", "flashcards", "--dictionary-url", _dict_url,
                            "--dictionary-cache", _deck_cache,
                            "--output", os.path.join(_enf, "decks")])
        _after = _DictHandler.requests
        check("enriched deck rc==0", rc == 0)
        with open(os.path.join(_enf, "decks", "words-preteaching-B1-deck.csv"),
                  encoding="utf-8") as f:
            _drows = list(_csv.reader(f))
        _circ = [r for r in _drows if r[0] == "circumstances"]
        check("enriched deck carries the mock definition",
              bool(_circ) and _circ[0][1] == "a fact connected with an event")
        check("enriched deck: one request per above-target word", _after - _before == 3)
        check("enrich stats on stderr", "2 definitions added, 1 word not found" in err)
        rc2, _, err2 = run(["--file", _enf, "--target-level", "B1", "--no-grammar",
                            "--export", "flashcards", "--dictionary-url", _dict_url,
                            "--dictionary-cache", _deck_cache,
                            "--output", os.path.join(_enf, "decks2")])
        check("repeat deck export answers from cache",
              rc2 == 0 and _DictHandler.requests == _after and "from cache" in err2)
    finally:
        shutil.rmtree(_enf, ignore_errors=True)

    # --- integration: error paths ---------------------------------------------
    rc, _, err = run(["--file", os.path.join(_tmp, "*.nope")])
    check("empty glob rc==1", rc == 1 and "matched no files" in err)
    rc, _, err = run(["--file", _tmp, "--target-level", "Z9"])
    check("bad target level rc==1", rc == 1 and "Invalid --target-level" in err)
    rc, _, err = run(["--file", _tmp, "--targets", "A2,B9"])
    check("bad targets level rc==1", rc == 1 and "Invalid --targets" in err)
    rc, _, err = run(["--file", _tmp, "--min-level", "C2", "--max-level", "A1"])
    check("min above max rc==1", rc == 1 and "--min-level" in err)
    rc, _, err = run(["--file", _tmp, "--sort", "bogus"])
    check("bad sort rc==1", rc == 1 and "Unknown --sort" in err)
    rc, _, err = run(["--file", _tmp, "--format", "bogus"])
    check("bad format rc==1", rc == 1 and "Unknown format" in err)
    rc, _, err = run(["--file", _tmp, "--target-level", "B1", "--targets", "A2"])
    check("target-level + targets rc==1", rc == 1 and "not both" in err)
    rc, _, err = run(["--file", _tmp, "--export", "md"])
    check("export without target rc==1", rc == 1 and "requires --target-level" in err)
    rc, _, err = run(["--file", _tmp, "--target-level", "B1", "--cloze"])
    check("cloze without export rc==1", rc == 1 and "requires --export" in err)
    rc, _, err = run(["--file", _tmp, "--target-level", "B1", "--export", "flashcards",
                      "--cloze"])
    check("cloze with flashcards rc==1", rc == 1 and "--cloze applies" in err)
    rc, _, err = run(["--file", _tmp, "--pre-enrich", "--export", "md"])
    check("pre-enrich + export rc==1", rc == 1 and "can't be combined" in err)
    rc, _, err = run(["--file", _tmp, "--pre-enrich", "--no-dictionary-cache"])
    check("pre-enrich + no-dictionary-cache rc==1",
          rc == 1 and "writes the dictionary cache" in err)
    rc, _, err = run(["--file", _tmp, "--targets", "A2,B1", "--export", "md"])
    check("targets + export md rc==1", rc == 1 and "requires --target-level" in err)
    rc, _, err = run(["--file", _tmp, "--export", "flashcards"])
    check("flashcards without any target rc==1",
          rc == 1 and "needs --target-level" in err)

    # --- integration: no grammar flag ------------------------------------------
    rc, out, _ = run(["--file", _tmp, "--no-grammar"])
    d = json.loads(out)
    check("--no-grammar note", d["grammarError"] == "skipped (--no-grammar)")
    check("--no-grammar rows null grammar", all(r["grammar"] is None for r in d["rows"]))
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

# --- integration: a folder with no analysable text ----------------------------
_only_empty = tempfile.mkdtemp(prefix="classprof_empty_")
try:
    with open(os.path.join(_only_empty, "blank.txt"), "w", encoding="utf-8") as f:
        f.write("   ")
    rc, _, err = run(["--file", _only_empty])
    check("all-unreadable folder rc==1", rc == 1 and "No analysable text" in err)
finally:
    shutil.rmtree(_only_empty, ignore_errors=True)

# --- integration: sample-readings golden contract (mirrors the CI step) --------
_sample = os.path.join(HERE, "sample-readings")
_GRADES = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
if os.path.isdir(_sample):
    files = sorted(f for f in os.listdir(_sample)
                   if not f.startswith(".")
                   and os.path.isfile(os.path.join(_sample, f)))
    rc, out, err = run(["--file", _sample, "--target-level", "B1",
                        "--no-grammar", "--format", "csv"])
    check("sample: csv rc==0", rc == 0)
    rows_s = list(_csv.reader(out.splitlines()))
    check("sample: csv header",
          rows_s[0] == ["file", "total_words", "vocab_typical", "vocab_reached",
                        "grammar_typical", "grammar_reaches", "estimated_level",
                        "above_target_pct", "fits"])
    check("sample: one row per text", len(rows_s) == 1 + len(files))
    check("sample: fits column valid",
          all(r[-1] in ("yes", "no") for r in rows_s[1:]))
    check("sample: every text has words", all(int(r[1]) >= 5 for r in rows_s[1:]))

    rc, out, err = run(["--file", _sample, "--no-grammar"])
    d = json.loads(out)
    check("sample: nothing skipped", d["texts"] == len(files) and d["skipped"] == [])
    check("sample: aggregate equals the sum of the rows",
          sum(r["totalWordCount"] for r in d["rows"]) == d["aggregate"]["totalWordCount"])
    check("sample: folder payload carries the contract schemaVersion",
          d["schemaVersion"] == engine.SCHEMA_VERSION)
    ranks = [_GRADES.get(r["estimatedLevel"], 99) for r in d["rows"]]
    check("sample: ranked by level, A1 first", ranks == sorted(ranks))
    check("sample: spans the A1 to C2 gradient",
          len(ranks) >= 2 and ranks[0] == 0 and ranks[-1] == 5)

    # --schema prints the versioned contract without touching the folder.
    _rc, _out, _err = run(["--schema"])
    check("sample: --schema prints the payload schema",
          _rc == 0 and json.loads(_out) == engine.payload_schema())
    check("sample: --schema is independent of --no-grammar",
          run(["--schema", "--no-grammar"])[0] == 0)

    # Mirror of the CI grammar pass: with spaCy importable in this test
    # interpreter, every row of the sample run carries a real grammar
    # typical/reaches range in the CEFR order.
    if HAVE_GRAMMAR:
        rc, out, err = run(["--file", _sample])
        d = json.loads(out)
        check("sample: grammar-enabled run rc==0", rc == 0)
        check("sample: grammarError null", d["grammarError"] is None)
        check("sample: grammar populated on every row",
              all(r["grammar"] is not None for r in d["rows"]))
        check("sample: grammar bands valid",
              all(r["grammar"]["typical"] in vp.CEFR_ORDER
                  and r["grammar"]["reaches"] in vp.CEFR_ORDER
                  for r in d["rows"]))

        # --comments over the folder: every per-text md handout carries the
        # Rubric comments section (the apply-as-comment reference output).
        _comments_out = tempfile.mkdtemp(prefix="classprof_golden_comments_")
        try:
            rc, out, err = run(["--file", _sample, "--target-level", "B1",
                                "--comments", "--export", "md",
                                "--output", _comments_out])
            check("sample comments: rc==0", rc == 0)
            _handouts = [os.path.join(_comments_out, f)
                         for f in os.listdir(_comments_out)
                         if f.endswith("-preteaching-B1.md")]
            check("sample comments: every per-text handout has both halves",
                  bool(_handouts)
                  and all("## Rubric comments" in open(h, encoding="utf-8").read()
                          and "## Vocabulary comments"
                          in open(h, encoding="utf-8").read()
                          for h in _handouts))
            _summary_path = os.path.join(_comments_out,
                                         "sample-readings-summary-B1.md")
            check("sample comments: summary carries the demand scan",
                  os.path.exists(_summary_path)
                  and "## Demand scan — above B1"
                  in open(_summary_path, encoding="utf-8").read()
                  and "| **Total** |"
                  in open(_summary_path, encoding="utf-8").read())
            # --targets with --comments: one rubric-comment deck per level, so
            # the same construction is a pre-teach card above its own level
            # and a plain rubric card at it.
            _ladder = tempfile.mkdtemp(prefix="classprof_ladder_")
            _ladder_out = tempfile.mkdtemp(prefix="classprof_ladder_out_")
            try:
                _mod = ("If they had studied harder, they would have passed "
                        "the exam. They must have left already.")
                for _nm in ("a.txt", "b.txt"):
                    with open(os.path.join(_ladder, _nm), "w",
                              encoding="utf-8") as f:
                        f.write(_mod)
                rc, out, err = run(["--file", _ladder, "--targets", "A2,B2",
                                    "--comments", "--export", "flashcards",
                                    "--no-enrich", "--output", _ladder_out])
                _lbase = os.path.basename(_ladder) + "-preteaching"
                check("ladder: comments decks written per level",
                      rc == 0
                      and os.path.exists(os.path.join(
                          _ladder_out, f"{_lbase}-A2-comments-deck.csv"))
                      and os.path.exists(os.path.join(
                          _ladder_out, f"{_lbase}-B2-comments-deck.csv")))
                _a2 = list(_csv.reader(open(os.path.join(
                    _ladder_out, f"{_lbase}-A2-comments-deck.csv"),
                    encoding="utf-8")))
                _b2 = list(_csv.reader(open(os.path.join(
                    _ladder_out, f"{_lbase}-B2-comments-deck.csv"),
                    encoding="utf-8")))
                check("ladder: RubricMaker shape with the grammar tag",
                      _a2[0] == ["word", "definition", "example",
                                 "phonetic", "partOfSpeech"]
                      and all(r[4] == "grammar" for r in _a2[1:] + _b2[1:]))
                _mp_a2 = [r for r in _a2[1:] if "Modal + perfect" in r[0]]
                _mp_b2 = [r for r in _b2[1:] if "Modal + perfect" in r[0]]
                check("ladder: same construction pre-teach at A2, rubric at B2",
                      len(_mp_a2) == 1 and len(_mp_b2) == 1
                      and "pre-teach or rewrite" in _mp_a2[0][1]
                      and "Rewrite:" in _mp_a2[0][1]
                      and "pre-teach or rewrite" not in _mp_b2[0][1]
                      and "Uses the" in _mp_b2[0][1])
                check("ladder: one card per construction across the set",
                      "2 of 2 texts" in _mp_a2[0][2])
            finally:
                shutil.rmtree(_ladder, ignore_errors=True)
                shutil.rmtree(_ladder_out, ignore_errors=True)
        finally:
            shutil.rmtree(_comments_out, ignore_errors=True)
    else:
        skipped += 1

    # The export pass of the CI golden check: per-text decks + the combined
    # class-wide deck (named after the source folder) and its level-keyed
    # index, in the documented shapes.
    _golden_out = tempfile.mkdtemp(prefix="classprof_golden_")
    try:
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--export", "flashcards", "--no-enrich", "--output", _golden_out])
        check("sample export: rc==0", rc == 0)
        _stems = [os.path.splitext(f)[0] for f in files]
        _per_text = {f"{s}-preteaching-B1-deck.csv" for s in _stems}
        _combined = "sample-readings-preteaching-B1-deck.csv"
        _index_name = "sample-readings-preteaching-B1-index.md"
        check("sample export: exactly per-text + combined deck + index",
              set(os.listdir(_golden_out))
              == _per_text | {_combined, _index_name})
        with open(os.path.join(_golden_out, _combined), encoding="utf-8") as f:
            _deck_rows = list(_csv.reader(f))
        check("sample export: combined deck has the RubricMaker shape",
              _deck_rows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"]
              and len(_deck_rows) > 1)
        _deck_words = {r[0] for r in _deck_rows[1:]}
        check("sample export: deck words distinct with in-context backs",
              len(_deck_words) == len(_deck_rows) - 1
              and all(r[1] and r[1] == r[2] for r in _deck_rows[1:]))
        with open(os.path.join(_golden_out, _index_name), encoding="utf-8") as f:
            _index_md = f.read()
        check("sample export: index is level-keyed",
              "| Word | Level | Occurrences | Texts |" in _index_md)
        _idx_words = {}
        for _ln in [line for line in _index_md.splitlines()
                    if line.startswith("| ")][1:]:
            _c = [x.strip() for x in _ln.strip("|").split("|")]
            _word, _lvl, _occ, _texts = _c[0], _c[1], _c[2], _c[3]
            _srcs = [t for t in _texts.split(", ") if t]
            check(f"sample export: {_word} level above B1 and real sources",
                  _lvl in ("B2", "C1", "C2")
                  and _occ.isdigit() and int(_occ) >= 1
                  and all(t in files for t in _srcs))
            _idx_words[_word] = _lvl
        check("sample export: index words == deck words", _idx_words.keys() == _deck_words)
    finally:
        shutil.rmtree(_golden_out, ignore_errors=True)

    # The per-level export pass of the CI golden check: --targets A2,B1 writes
    # one combined deck + level-keyed index per level, no per-text decks.
    _golden_targets = tempfile.mkdtemp(prefix="classprof_golden_targets_")
    try:
        rc, out, err = run(["--file", _sample, "--targets", "A2,B1", "--no-grammar",
                            "--export", "flashcards", "--no-enrich", "--output",
                            _golden_targets])
        check("sample targets export: rc==0", rc == 0)
        _gbase = "sample-readings-preteaching"
        check("sample targets export: one deck + index per level, no per-text",
              set(os.listdir(_golden_targets))
              == {f"{_gbase}-{lvl}-deck.csv" for lvl in ("A2", "B1")}
              | {f"{_gbase}-{lvl}-index.md" for lvl in ("A2", "B1")})

        def _gdeck_words(level):
            with open(os.path.join(_golden_targets, f"{_gbase}-{level}-deck.csv"),
                      encoding="utf-8") as f:
                rows = list(_csv.reader(f))
            check(f"sample targets export: {level} deck has the RubricMaker shape",
                  rows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"])
            return {r[0] for r in rows[1:]}

        _ga2_words = _gdeck_words("A2")
        _gb1_words = _gdeck_words("B1")
        check("sample targets export: both decks non-empty", bool(_ga2_words) and bool(_gb1_words))
        check("sample targets export: B1-above words are a subset of A2-above",
              _gb1_words <= _ga2_words)

        def _gindex_words(level, above):
            with open(os.path.join(_golden_targets, f"{_gbase}-{level}-index.md"),
                      encoding="utf-8") as f:
                md = f.read()
            check(f"sample targets export: {level} index is level-keyed",
                  f"# Vocabulary index — above {level}" in md
                  and "| Word | Level | Occurrences | Texts |" in md)
            words = {}
            for ln in [line for line in md.splitlines() if line.startswith("| ")][1:]:
                c = [x.strip() for x in ln.strip("|").split("|")]
                word, lvl, occ, texts = c[0], c[1], c[2], c[3]
                srcs = [t for t in texts.split(", ") if t]
                check(f"sample targets export: {level} {word} above level, real sources",
                      lvl in above and occ.isdigit() and int(occ) >= 1
                      and all(t in files for t in srcs))
                words[word] = lvl
            return words

        check("sample targets export: A2 index == A2 deck",
              _gindex_words("A2", {"B1", "B2", "C1", "C2"}).keys() == _ga2_words)
        check("sample targets export: B1 index == B1 deck",
              _gindex_words("B1", {"B2", "C1", "C2"}).keys() == _gb1_words)
        # --cando on the same run: each level also gets its own Can-Do
        # reference deck, with the demands measured against that level.
        rc, out, err = run(["--file", _sample, "--targets", "A2,B1", "--no-grammar",
                            "--cando", "--export", "flashcards", "--no-enrich",
                            "--output", _golden_targets])
        check("sample targets cando: rc==0", rc == 0)
        check("sample targets cando: one cando deck per level",
              {f"{_gbase}-{lvl}-cando-deck.csv" for lvl in ("A2", "B1")}
              <= set(os.listdir(_golden_targets)))
        for _lvl, _above_bands in (("A2", {"B1", "B2", "C1", "C2"}),
                                   ("B1", {"B2", "C1", "C2"})):
            with open(os.path.join(_golden_targets,
                                   f"{_gbase}-{_lvl}-cando-deck.csv"),
                      encoding="utf-8") as f:
                _cd_rows = list(_csv.reader(f))
            _cd_bands = {r[0].split(" — ")[0] for r in _cd_rows[1:]}
            check(f"sample targets cando: {_lvl} deck has the RubricMaker shape",
                  _cd_rows[0] == ["word", "definition", "example", "phonetic",
                                  "partOfSpeech"]
                  and len(_cd_rows) > 1
                  and _cd_bands == _above_bands
                  and all(r[0].endswith("demand") and r[4] == "cando"
                          and f"above the {_lvl} target" in r[2]
                          for r in _cd_rows[1:]))
    finally:
        shutil.rmtree(_golden_targets, ignore_errors=True)

    # The md-export pass of the CI golden check: per-text handouts plus one
    # set-level summary handout aggregating every text's verdict.
    _golden_md = tempfile.mkdtemp(prefix="classprof_golden_md_")
    try:
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--export", "md", "--output", _golden_md])
        check("sample md export: rc==0", rc == 0)
        _stems = [os.path.splitext(f)[0] for f in files]
        check("sample md export: per-text handouts + one summary",
              set(os.listdir(_golden_md))
              == {f"{s}-preteaching-B1.md" for s in _stems}
              | {"sample-readings-summary-B1.md"})
        with open(os.path.join(_golden_md, "sample-readings-summary-B1.md"),
                  encoding="utf-8") as f:
            _summary_md = f.read()
        check("sample md export: summary names the target and text count",
              f"# Set summary — Target B1 ({len(files)} texts)" in _summary_md)
        check("sample md export: summary aggregates the pooled distribution",
              "Aggregate vocabulary:" in _summary_md and "| Text | Words |" in _summary_md)
        check("sample md export: every text appears in the summary",
              all(f in _summary_md for f in files))
        check("sample md export: both verdict kinds present",
              "pre-teach" in _summary_md and "on level" in _summary_md)
    finally:
        shutil.rmtree(_golden_md, ignore_errors=True)

    # The band-export pass of the CI golden check: one CSV per CEFR band
    # (vocab-<band>.csv, lowercase) with the documented word × occurrences ×
    # texts shape, cross-checked against the run's own pooled aggregate.
    _golden_vocab = tempfile.mkdtemp(prefix="classprof_golden_vocab_")
    try:
        rc, out, err = run(["--file", _sample, "--no-grammar",
                            "--export-vocab", _golden_vocab])
        check("sample vocab export: rc==0", rc == 0)
        _agg = json.loads(out)["aggregate"]
        _band_files = [f"vocab-{lvl.lower().replace(' ', '-')}.csv"
                       for lvl in vp.CEFR_ORDER + ["Off List"]]
        check("sample vocab export: one CSV per band, lowercase",
              set(os.listdir(_golden_vocab)) == set(_band_files))
        _all_words = set()
        for _fname in _band_files:
            with open(os.path.join(_golden_vocab, _fname), encoding="utf-8") as f:
                _rows = list(_csv.reader(f))
            check(f"sample vocab export: {_fname} has the documented shape",
                  _rows[0] == ["word", "occurrences", "texts"] and len(_rows) > 1)
            _words = set()
            for _r in _rows[1:]:
                _occ, _texts = int(_r[1]), int(_r[2])
                check(f"sample vocab export: {_fname} {_r[0]} row valid",
                      _r[0] and _occ >= 1 and 1 <= _texts <= len(files)
                      and _occ >= _texts and _r[0] not in _words)
                _words.add(_r[0])
            check(f"sample vocab export: {_fname} disjoint from other bands",
                  not (_all_words & _words))
            _all_words |= _words
        for _lvl in vp.CEFR_ORDER + ["Off List"]:
            _fname = f"vocab-{_lvl.lower().replace(' ', '-')}.csv"
            with open(os.path.join(_golden_vocab, _fname), encoding="utf-8") as f:
                _n = len(list(_csv.reader(f))) - 1
            check(f"sample vocab export: {_fname} matches the aggregate",
                  _n == _agg["levels"][_lvl]["distinctWordCount"])
    finally:
        shutil.rmtree(_golden_vocab, ignore_errors=True)

    # The interleave pass of the CI golden check: the spaced-introduction
    # schedule across the set — one reading per text, at most the budget of
    # new above-target words per reading, and the md handout's word index
    # matching the run's own schedule payload (csv too).
    _golden_il = tempfile.mkdtemp(prefix="classprof_golden_il_")
    try:
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--interleave", "--new-words-per-reading", "4",
                            "--export", "md", "--output", _golden_il])
        check("sample interleave: rc==0", rc == 0)
        _stems = [os.path.splitext(f)[0] for f in files]
        _reading_files = [f"sample-readings-interleave-B1-reading-{i}.md"
                          for i in range(1, len(files) + 1)]
        check("sample interleave: handouts + summary + schedule + reading handouts",
              set(os.listdir(_golden_il))
              == {f"{s}-preteaching-B1.md" for s in _stems}
              | {"sample-readings-summary-B1.md", "sample-readings-interleave-B1.md"}
              | set(_reading_files))
        _il = json.loads(out)["interleave"]
        check("sample interleave: target and budget in the payload",
              _il["targetLevel"] == "B1" and _il["budget"] == 4)
        check("sample interleave: one reading per text on real files",
              len(_il["readings"]) == len(files)
              and [r["index"] for r in _il["readings"]] == list(range(1, len(files) + 1))
              and all(os.path.basename(r["file"]) in files for r in _il["readings"]))
        _il_idx = {w["word"]: w for w in _il["words"]}
        check("sample interleave: words distinct and strictly above B1",
              len(_il_idx) == len(_il["words"])
              and all(w["level"] in ("B2", "C1", "C2") for w in _il["words"]))
        check("sample interleave: introduction point and appearances sane",
              all(1 <= w["introducedAt"] <= len(files) and w["appearsIn"]
                  and all(1 <= i <= len(files) for i in w["appearsIn"])
                  for w in _il["words"]))
        check("sample interleave: budget respected, intro matches the index",
              all(len(r["introduce"]) <= _il["budget"]
                  and all(d["word"] in _il_idx
                          and _il_idx[d["word"]]["introducedAt"] == r["index"]
                          and _il_idx[d["word"]]["level"] == d["level"]
                          for d in r["introduce"])
                  and all(d["word"] in _il_idx for d in r["due"])
                  for r in _il["readings"]))
        check("sample interleave: at least one word scheduled",
              any(r["introduce"] for r in _il["readings"]))
        with open(os.path.join(_golden_il, "sample-readings-interleave-B1.md"),
                  encoding="utf-8") as f:
            _il_md = f.read()
        check("sample interleave: md schedule shape",
              f"# Vocabulary interleaving — Target B1 ({len(files)} readings, "
              "4 new words/reading)" in _il_md
              and "## Reading 1 — " in _il_md
              and f"## Reading {len(files)} — " in _il_md
              and "**Introduce" in _il_md and "Due for review" in _il_md
              and "## Word index" in _il_md
              and "| Word | Level | Introduced at | Appears in |" in _il_md)
        _il_rows = [ln for ln in _il_md.splitlines() if ln.startswith("| `")]
        check("sample interleave: md word index == payload index",
              len(_il_rows) == len(_il["words"])
              and all(ln.split("|")[2].strip() in ("B2", "C1", "C2")
                      for ln in _il_rows))
        for _i, _r in enumerate(_il["readings"], start=1):
            with open(os.path.join(_golden_il, _reading_files[_i - 1]),
                      encoding="utf-8") as f:
                _rmd = f.read()
            check(f"sample interleave: reading {_i} handout shape",
                  f"# Reading {_i} — {os.path.basename(_r['file'])}" in _rmd
                  and "| Word | Level | Definition |" in _rmd
                  and "## Introduce" in _rmd and "## Review" in _rmd
                  and "## Due for review" in _rmd)
            check(f"sample interleave: reading {_i} introduces its words",
                  all(f"`{d['word']}`" in _rmd and f"| {d['level']} |" in _rmd
                      for d in _r["introduce"]))
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--interleave", "--new-words-per-reading", "4",
                            "--export", "csv", "--output", _golden_il])
        check("sample interleave csv: rc==0", rc == 0)
        with open(os.path.join(_golden_il, "sample-readings-interleave-B1.csv"),
                  encoding="utf-8") as f:
            _il_csv = list(_csv.reader(f))
        check("sample interleave csv: documented shape",
              _il_csv[0] == ["word", "level", "introducedAt", "appearsIn", "deferredFrom"]
              and len(_il_csv) - 1 == len(_il["words"]))
        for _r in _il_csv[1:]:
            _w = _il_idx[_r[0]]
            check(f"sample interleave csv: {_r[0]} row matches the payload",
                  _r[1] == _w["level"] and int(_r[2]) == _w["introducedAt"]
                  and _r[3] == ";".join(str(i) for i in _w["appearsIn"])
                  and (_r[4] == "" or int(_r[4]) == _w.get("deferredFrom")))
    finally:
        shutil.rmtree(_golden_il, ignore_errors=True)

    # The curriculum pass of the CI golden check: --export csv --curriculum
    # writes the folder-level coverage grid — one row per text, one column
    # per required item, with a pass verdict per text.
    _golden_curr = tempfile.mkdtemp(prefix="classprof_golden_curr_")
    try:
        _curr_path = os.path.join(_golden_curr, "unit-checklist.txt")
        with open(_curr_path, "w", encoding="utf-8") as f:
            f.write("[vocabulary]\npurchase\nmat\n\n[grammar]\npassive_present\n")
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--export", "csv", "--curriculum", _curr_path,
                            "--output", _golden_curr])
        check("sample curriculum grid: rc==0", rc == 0)
        _matrix = "sample-readings-curriculum-coverage-B1.csv"
        with open(os.path.join(_golden_curr, _matrix), encoding="utf-8") as f:
            _mrows = list(_csv.reader(f))
        check("sample curriculum grid: header with one column per item",
              _mrows[0] == ["text", "purchase", "mat", "Passive (present)", "pass"])
        check("sample curriculum grid: one row per text with yes/no cells",
              len(_mrows) == 1 + len(files)
              and all(r[0] in files for r in _mrows[1:])
              and all(c in ("yes", "no") for r in _mrows[1:] for c in r[1:]))
        # md run: per-text sections plus the same grid in the set summary.
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--export", "md", "--curriculum", _curr_path,
                            "--output", _golden_curr])
        check("sample curriculum md: rc==0", rc == 0)
        with open(os.path.join(_golden_curr, "sample-readings-summary-B1.md"),
                  encoding="utf-8") as f:
            _cc_summary = f.read()
        check("sample curriculum md: summary carries the coverage matrix",
              "## Curriculum coverage" in _cc_summary
              and "| Text | purchase | mat | Passive (present) | pass |" in _cc_summary
              and all(f in _cc_summary for f in files))
        with open(os.path.join(_golden_curr, "academic-essay-preteaching-B1.md"),
                  encoding="utf-8") as f:
            check("sample curriculum md: per-text handout carries the checklist",
                  "## Curriculum checklist" in f.read())
        # json run: the same grid inside the payload (curriculumCoverage), so
        # scripts can consume the pass/fail matrix without CSV parsing.
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--format", "json", "--curriculum", _curr_path])
        _ccj = json.loads(out)["curriculumCoverage"]
        check("sample curriculum json: grid in the payload",
              rc == 0 and _ccj["items"] == [["vocabulary", "purchase"],
                                             ["vocabulary", "mat"],
                                             ["grammar", "Passive (present)"]]
              and _ccj["textCount"] == len(files)
              and {r["text"] for r in _ccj["rows"]} == set(files)
              and all(len(r["cells"]) == len(_ccj["items"])
                      and isinstance(r["pass"], bool)
                      for r in _ccj["rows"])
              and 0 <= _ccj["passCount"] <= _ccj["textCount"])
    finally:
        shutil.rmtree(_golden_curr, ignore_errors=True)

    # The Can-Do pass of the CI golden check: --cando-diff --export md puts
    # the shared above-target demands into the summary handout, and
    # --cando --export flashcards writes a combined Can-Do reference deck.
    _golden_cando = tempfile.mkdtemp(prefix="classprof_golden_cando_")
    try:
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--cando-diff", "--export", "md", "--output", _golden_cando])
        check("sample cando-diff: rc==0", rc == 0)
        with open(os.path.join(_golden_cando, "sample-readings-summary-B1.md"),
                  encoding="utf-8") as f:
            _cd_summary = f.read()
        check("sample cando-diff: summary carries the demands section",
              "## Can-Do demands across the set" in _cd_summary
              and "| Demand | Level | Can-Do descriptor | Texts |" in _cd_summary
              and all(f in _cd_summary for f in files))
        rc, out, err = run(["--file", _sample, "--target-level", "B1", "--no-grammar",
                            "--cando", "--export", "flashcards", "--no-enrich",
                            "--output", _golden_cando])
        check("sample cando deck: rc==0", rc == 0)
        with open(os.path.join(_golden_cando,
                               "sample-readings-preteaching-B1-cando-deck.csv"),
                  encoding="utf-8") as f:
            _cdrows = list(_csv.reader(f))
        check("sample cando deck: RubrikMaker shape with demand cards",
              _cdrows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"]
              and len(_cdrows) > 1
              and all(r[0].endswith("demand") and r[3] == "" and r[4] == "cando"
                      for r in _cdrows[1:]))
    finally:
        shutil.rmtree(_golden_cando, ignore_errors=True)
else:
    skipped += 1

# --- unit: the plugin skill stays flavour-consistent with the repo copy -----
# Mirrors the CI "Skills stay flavour-consistent + plugin.json commands" step
# for this plugin: the bundled SKILL.md is plugin-flavoured (the `class-profile`
# command on PATH, ${CLAUDE_PLUGIN_ROOT} references), the repo-local copy is
# repo-flavoured (../../../ checkout links), and plugin.json declares the
# command the skill states.
_skill_local = os.path.join(HERE, ".claude", "skills", "class-profile", "SKILL.md")
_skill_plugin = os.path.join(HERE, "plugins", "class-profile", "skills",
                             "class-profile", "SKILL.md")
_plugin_json = os.path.join(HERE, "plugins", "class-profile", ".claude-plugin",
                            "plugin.json")
if all(os.path.isfile(p) for p in (_skill_local, _skill_plugin, _plugin_json)):
    with open(_skill_local, encoding="utf-8") as f:
        _sl = f.read()
    with open(_skill_plugin, encoding="utf-8") as f:
        _sp = f.read()
    check("class-profile plugin copy is plugin-flavoured",
          "`class-profile`" in _sp and "${CLAUDE_PLUGIN_ROOT}" in _sp
          and "../../../" not in _sp)
    check("class-profile repo-local copy is repo-flavoured",
          "../../../" in _sl and "class_profile.py" in _sl)
    check("class-profile copies are deliberately different flavours", _sl != _sp)
    # Whole-token matching: a longer flag like --cando-off must not satisfy
    # the --cando requirement.
    def _has_flag(md, flag):
        return _re.search(_re.escape(flag) + r"(?![-A-Za-z0-9_])", md) is not None

    for _flag in ("--gap-report", "--interleave", "--new-words-per-reading",
                  "--curriculum", "--watch", "--cando", "--cando-diff",
                  "--cando-diff-sort", "--schema", "--comments"):
        check(f"class-profile skill documents {_flag} in both copies",
              _has_flag(_sl, _flag) and _has_flag(_sp, _flag))
    with open(os.path.join(HERE, ".claude", "skills", "text-report", "SKILL.md"),
              encoding="utf-8") as f:
        _tl = f.read()
    with open(os.path.join(HERE, "plugins", "text-report", "skills",
                           "text-report", "SKILL.md"), encoding="utf-8") as f:
        _tp = f.read()
    for _flag in ("--cambridge", "--cando", "--schema", "--comments"):
        check(f"text-report skill documents {_flag} in both copies",
              _has_flag(_tl, _flag) and _has_flag(_tp, _flag))
    _manifest = json.load(open(_plugin_json, encoding="utf-8"))
    check("class-profile plugin.json declares the command",
          [c["name"] for c in _manifest.get("commands", [])] == ["class-profile"])
else:
    skipped += 1

print(f"\n{passed} passed, {failed} failed"
      + (f", {skipped} skipped" if skipped else ""))
sys.exit(1 if failed else 0)
