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
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "class_profile.py")

import class_profile as cp  # noqa: E402
import vocab_profile as vp  # noqa: E402
import grammar_profile as gp  # noqa: E402

try:
    _NLP = gp.load_nlp()
    _CEFRJ = gp.load_cefrj_levels(os.path.join(HERE, "GrammarProfile"))
    HAVE_GRAMMAR = True
except Exception:
    _NLP = _CEFRJ = None
    HAVE_GRAMMAR = False

_BASE = os.path.join(HERE, "WordLists")
_LEVELS = [(name, vp.load_wordlist(_BASE, rel)) for name, rel in vp.PROFILERS["cefr"]]

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
           '<w:p><w:r><w:t>{"The cat sat on the mat."}</w:t></w:r></w:p></w:body></w:document>')
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
    names = [os.path.basename(f) for f in cp.discover_files(_tmp)]
    check("discover skips the tool's own export artifacts",
          "easy-preteaching-B1.md" not in names
          and "essays-summary-B1.md" not in names
          and "hard.txt" in names)
    check("is_export_artifact recognises decks and indexes",
          cp.is_export_artifact("essays-preteaching-B1-deck.csv")
          and cp.is_export_artifact("essays-preteaching-B1-index.md")
          and cp.is_export_artifact("class-summary-C2.md")
          and not cp.is_export_artifact("lesson-notes.md")
          and not cp.is_export_artifact("handout-summary.docx"))
    os.remove(os.path.join(_tmp, "easy-preteaching-B1.md"))
    os.remove(os.path.join(_tmp, "essays-summary-B1.md"))

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

    # --- unit: row building (vocab only; no grammar engine needed) -------------
    row, ordered, _ctx = cp.build_row(_EASY, "easy.txt", _LEVELS, None, None, False, "B1")
    check("row easy typical A1", row["vocabulary"]["typical"] == "A1")
    check("row easy coverage A1", row["vocabulary"]["coverage"] == "A1")
    check("row grammar None without engine", row["grammar"] is None)
    check("row estimated A1", row["estimatedLevel"] == "A1")
    check("row aboveTargetPercent numeric",
          isinstance(row["aboveTargetPercent"], int) and 0 <= row["aboveTargetPercent"] <= 100)
    check("row easy fits B1 target", row["fits"] is True)
    check("row ctx carries the text", _ctx["text"] == _EASY)

    row2, _o2, _c2 = cp.build_row(_HARD, "hard.txt", _LEVELS, None, None, False, "B1")
    check("row hard estimated C2", row2["estimatedLevel"] == "C2")
    check("row hard does not fit B1", row2["fits"] is False)

    row3, _o3, _c3 = cp.build_row(_EASY, "x.txt", _LEVELS, None, None, False, None)
    check("row without target: above/fits null",
          row3["aboveTargetPercent"] is None and row3["fits"] is None)

    # --- unit: multiple targets side by side ----------------------------------
    rowm, _om, _cm = cp.build_row(_EASY, "easy.txt", _LEVELS, None, None, False,
                                  ["A2", "B1"])
    check("multi-target: per-target map populated",
          set(rowm["targets"]) == {"A2", "B1"})
    check("multi-target: easy fits A2 and B1",
          rowm["targets"]["A2"]["fits"] is True and rowm["targets"]["B1"]["fits"] is True)
    check("multi-target: singular fields null",
          rowm["aboveTargetPercent"] is None and rowm["fits"] is None)
    rowm2, _om2, _cm2 = cp.build_row(_HARD, "hard.txt", _LEVELS, None, None, False,
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
    check("export payload above-target words have context",
          all(d.get("context") for d in payload["aboveTarget"]["words"]))
    check("export payload above-target nonempty", payload["aboveTarget"]["wordCount"] >= 1)

    # --- unit: folder vocabulary + combined deck ------------------------------
    prof_a = cp.build_row(_EASY, "a", _LEVELS, None, None, False, None)
    prof_b = cp.build_row(_HARD, "b", _LEVELS, None, None, False, None)
    vocab = cp.folder_vocabulary([prof_a, prof_b])
    check("folder_vocabulary distinct across texts",
          {"the", "cat", "circumstances", "chlorophyll"} <= set(vocab))
    check("folder_vocabulary sorted", vocab == sorted(vocab))

    payloads = [cp.export_payload(r, o, c, "B1") for r, o, c in
                (cp.build_row(_EASY, "a", _LEVELS, None, None, False, "B1"),
                 cp.build_row(_HARD, "b", _LEVELS, None, None, False, "B1"))]
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
    for _r, _o, _c in (cp.build_row(_EASY, "a", _LEVELS, None, None, False, None),
                       cp.build_row(_HARD, "b", _LEVELS, None, None, False, None)):
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
    _prof = [cp.build_row(t, label, _LEVELS, None, None, False, "B1")
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

    rows = []
    for label, text in [("b", _EASY), ("a", _HARD)]:
        _r, _o, _c = cp.build_row(text, label, _LEVELS, None, None, False, None)
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

    # --- integration: --help renders without argparse formatting errors --------
    rc, out, err = run(["--help"])
    # %%above escapes argparse's %-interpolation; the rendered help shows the
    # literal label, not the interpolated args dict.
    check("cli --help exits 0 and renders every flag",
          rc == 0 and "--targets" in out and "fits/%above verdict" in out
          and "option_strings" not in out)

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
    ranks = [_GRADES.get(r["estimatedLevel"], 99) for r in d["rows"]]
    check("sample: ranked by level, A1 first", ranks == sorted(ranks))
    check("sample: spans the A1 to C2 gradient",
          len(ranks) >= 2 and ranks[0] == 0 and ranks[-1] == 5)

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
    _manifest = json.load(open(_plugin_json, encoding="utf-8"))
    check("class-profile plugin.json declares the command",
          [c["name"] for c in _manifest.get("commands", [])] == ["class-profile"])
else:
    skipped += 1

print(f"\n{passed} passed, {failed} failed"
      + (f", {skipped} skipped" if skipped else ""))
sys.exit(1 if failed else 0)
