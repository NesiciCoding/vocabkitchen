#!/usr/bin/env python3
"""Regression guard for grammar_profile.py.

Dependency-free harness (no pytest). Run:  python3 test_grammar_profile.py

Unit checks (level resolution, format handling, JSON shaping, document
extraction, the missing-engine error path) always run. The detector integration
checks need spaCy + en_core_web_sm; when those aren't installed they are skipped
with a printed note, so the suite still passes on a machine without spaCy.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "grammar_profile.py")

import grammar_profile as gp  # noqa: E402

try:
    import spacy  # noqa: F401
    HAVE_SPACY_PKG = True
except ImportError:
    HAVE_SPACY_PKG = False

try:
    _NLP = gp.load_nlp()
    HAVE_SPACY = True
except Exception:
    _NLP = None
    HAVE_SPACY = False

_LEVELS = gp.load_cefrj_levels(os.path.join(HERE, "GrammarProfile"))

passed = failed = skipped = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


def run(args, text=""):
    p = subprocess.run([sys.executable, SCRIPT] + args,
                       input=text, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


# --- unit: coarse level parsing ------------------------------------------------
check("coarse A1.2 -> A1", gp._coarse("A1.2") == "A1")
check("coarse 'B1-C1' -> B1", gp._coarse("B1-C1") == "B1")
check("coarse 'B2.2*' -> B2", gp._coarse("B2.2*") == "B2")
check("coarse blank -> ''", gp._coarse("") == "" and gp._coarse("N/A") == "")

# --- unit: CEFR-J level table --------------------------------------------------
check("levels load non-empty", len(_LEVELS) > 200)
check("present perfect is A2", _LEVELS.get("TA.PRPF.AFF") == "A2")
check("can is A1", _LEVELS.get("MD.can.AFF") == "A1")
check("past passive is A2", _LEVELS.get("PASS.PAST.AFF") == "A2")
check("perfect to-infinitive is C1", _LEVELS.get("TO.to_have_done") == "C1")

# --- unit: every construction resolves to a valid CEFR band --------------------
_all_ok = True
for cid, (name, cat, code, fb) in gp._CONSTRUCTIONS.items():
    lvl = _LEVELS.get(code, fb)
    if lvl not in gp._CEFR_ORDER:
        _all_ok = False
        print(f"  bad level for {cid}: {lvl}")
check("all constructions resolve to a CEFR band", _all_ok)

# --- unit: the grammar gap report's full-set enumeration ----------------------
_at_b1 = gp.constructions_at_level(_LEVELS, "B1")
check("constructions_at_level: B1 set is non-empty", len(_at_b1) > 5)
check("constructions_at_level: every entry named and categorised",
      all(d["name"] and d["category"] for d in _at_b1))
check("constructions_at_level: sorted by category then name",
      [(d["category"], d["name"]) for d in _at_b1]
      == sorted((d["category"], d["name"]) for d in _at_b1))
check("constructions_at_level: bands partition the registry",
      sum(len(gp.constructions_at_level(_LEVELS, lvl))
          for lvl in gp._CEFR_ORDER) == len(gp._CONSTRUCTIONS))

# --- unit: --format resolution -------------------------------------------------
check("format auto+tty -> pretty", gp.resolve_format("auto", True) == "pretty")
check("format auto+pipe -> json", gp.resolve_format("auto", False) == "json")
check("format none+pipe -> json", gp.resolve_format(None, False) == "json")
check("format json overrides tty", gp.resolve_format("json", True) == "json")
check("format pretty overrides pipe", gp.resolve_format("pretty", False) == "pretty")
try:
    gp.resolve_format("bogus", True)
    check("format bogus raises", False)
except ValueError:
    check("format bogus raises", True)

# --- unit: JSON shaping + sort order (-count, then name) -----------------------
_fake_results = {lvl: {} for lvl in gp._CEFR_ORDER}
# Three A2 constructions: two share a count (tie broken by name), one ranks above.
_fake_results["A2"]["b_low"] = {
    "name": "Beta", "category": "Tense & aspect", "level": "A2",
    "count": 1, "examples": []}
_fake_results["A2"]["a_low"] = {
    "name": "Alpha", "category": "Tense & aspect", "level": "A2",
    "count": 1, "examples": []}
_fake_results["A2"]["top"] = {
    "name": "Zeta", "category": "Tense & aspect", "level": "A2",
    "count": 5, "examples": [{"span": "have gone", "sentence": "They have gone."}]}
_fake_meta = {"sentenceCount": 1, "tokenCount": 3, "constructionCount": 7,
              "estimatedLevel": {"typical": "A2", "reaches": "A2"},
              "bandCounts": {lvl: 0 for lvl in gp._CEFR_ORDER}}
_j = gp.results_to_json(_fake_results, _fake_meta)
check("json has top-level counts", _j["sentenceCount"] == 1 and _j["constructionCount"] == 7)
check("json bands all six levels", set(_j["results"]) == set(gp._CEFR_ORDER))
_ids = [c["id"] for c in _j["results"]["A2"]["constructions"]]
check("json sort: higher count first, then name", _ids == ["top", "a_low", "b_low"])
check("json A2 count/distinct", _j["results"]["A2"]["constructionCount"] == 7
      and _j["results"]["A2"]["distinct"] == 3)

# --- unit: missing-engine error path ------------------------------------------
# Two distinct states: spaCy absent -> "pip install spacy"; spaCy present but the
# model absent -> "spacy download". Only assert the message for the true state.
if HAVE_SPACY:
    try:
        gp.load_nlp("definitely_not_a_real_model_xyz")
        check("bad model raises EngineError", False)
    except gp.EngineError as ex:
        check("bad model raises EngineError", "spacy download" in str(ex))
elif not HAVE_SPACY_PKG:
    try:
        gp.load_nlp()
        check("missing spaCy raises EngineError", False)
    except gp.EngineError as ex:
        check("missing spaCy raises EngineError", "pip install spacy" in str(ex))
else:
    # spaCy installed but the model isn't: load_nlp() must point at the download.
    try:
        gp.load_nlp()
        check("missing model raises EngineError", False)
    except gp.EngineError as ex:
        check("missing model raises EngineError", "spacy download" in str(ex))

# --- integration: blank input errors before needing spaCy ----------------------
rc, out, err = run(["--text", "   "])
check("blank input errors rc==1", rc == 1 and "Usage" in err)

# --- integration: document extraction (stdlib only) ----------------------------
_tmp = tempfile.mkdtemp(prefix="grammartest_")
try:
    # Plain .txt goes through the _read_plain fallback; assert it returns content.
    txt = os.path.join(_tmp, "prose.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("The committee analysed the results carefully.")
    check("plain txt returns content",
          gp.extract_text(txt) == "The committee analysed the results carefully.")
    # Unknown extension falls back to plain-text reading too.
    rst = os.path.join(_tmp, "notes.rst")
    with open(rst, "w", encoding="utf-8") as f:
        f.write("Unknown extension prose.")
    check("unknown extension reads as plain", "Unknown extension prose" in gp.extract_text(rst))

    md = os.path.join(_tmp, "doc.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Title\n\nSome **bold** and a [link](https://example.com) plus `code`.")
    text = gp.extract_text(md)
    check("markdown keeps prose", "bold" in text and "link" in text and "code" in text)
    check("markdown drops url host", "example.com" not in text)

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    docx = os.path.join(_tmp, "doc.docx")
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
    check("docx extracts text", "cat sat on the mat" in gp.extract_text(docx))

    empty = os.path.join(_tmp, "empty.txt")
    with open(empty, "w", encoding="utf-8") as f:
        f.write("   \n\t")
    try:
        gp.extract_text(empty)
        check("empty file raises", False)
    except gp.DocumentError as ex:
        check("empty file raises", "No analysable text" in str(ex))

    try:
        gp.extract_text(os.path.join(_tmp, "missing.txt"))
        check("missing file raises", False)
    except gp.DocumentError as ex:
        check("missing file raises", "file not found" in str(ex))
finally:
    shutil.rmtree(_tmp, ignore_errors=True)


# --- integration: detectors (needs spaCy) --------------------------------------
def ids_for(text):
    results, meta = gp.profile(text, _NLP, _LEVELS)
    return {cid for lvl in results for cid in results[lvl]}, results, meta


def detect_check(name, text, expected_id, expected_level=None, forbidden_ids=()):
    global skipped
    if not HAVE_SPACY:
        skipped += 1
        return
    ids, results, _meta = ids_for(text)
    ok = expected_id in ids
    if ok and expected_level is not None:
        ok = expected_id in results[expected_level]
    if ok and forbidden_ids:
        ok = not (ids & set(forbidden_ids))
    check(name, ok)


detect_check("present perfect progressive", "She has been working all day.", "pres_perf_prog", "B2")
detect_check("past passive", "The book was written last year.", "passive_past", "A2")
detect_check("passive with modal", "The work must be finished today.", "passive_modal", "B1")
detect_check("get-passive", "The window got broken.", "get_passive", "B1")
detect_check("modal can", "I can swim well.", "modal_can", "A1")
detect_check("future going to", "I am going to travel next week.", "future_going_to", "A2")
detect_check("have to", "I have to leave now.", "have_to", "A2")
detect_check("used to", "She used to smoke.", "used_to", "B1")
detect_check("third conditional", "If I had known, I would have helped.", "cond_third", "B1")
detect_check("first conditional", "If it rains, we will stay home.", "cond_first", "A2")
detect_check("relative who", "The man who lives here is kind.", "rel_who", "A1")
detect_check("relative which", "The book which I read was long.", "rel_which", "B2")
detect_check("to-infinitive", "I want to learn French.", "to_inf", "A1")
detect_check("passive to-infinitive", "The house needs to be cleaned.", "to_be_done", "B2")
detect_check("comparative -er", "She is taller than him.", "comp_er", "A1")
detect_check("superlative", "This is the biggest house.", "superl_est", "A1")
detect_check("existential there", "There is a book here.", "there_be", "A1")
detect_check("wh-question", "What did you do?", "wh_question", "A1")
detect_check("tag question", "You like tea, don't you?", "tag_question", "B1")
detect_check("imperative", "Sit down.", "imperative", "A1")
detect_check("negative imperative", "Don't touch that.", "neg_imperative", "B1")
detect_check("causative make", "She made me laugh.", "caus_make", "A2")
detect_check("negative-adverbial inversion", "Never have I seen such a thing.", "inversion_neg", "C1")

# Coverage for previously untested constructions, with negative expectations on
# the overlap-prone ones (an over-firing detector would fail these).
detect_check("ought to (not mislabelled modal_can)", "You ought to leave.",
             "ought_to", "B1", forbidden_ids=["modal_can"])
detect_check("had better", "You had better go now.", "had_better", "B2")
detect_check("as ... as", "She is as tall as her brother.", "as_as", "B2")
detect_check("wish clause", "I wish I had a car.", "wish_clause", "B2")
detect_check("non-restrictive relative", "My sister, who is older, sings.",
             "rel_nonrestrictive", "B1")
detect_check("having + PP", "Having finished, she left.", "having_pp", "B2")
detect_check("being + PP", "Being asked twice, he agreed.", "being_pp", "B2")
detect_check("causative have + PP", "I had my hair cut.", "caus_have_pp", "B2")
detect_check("mandative subjunctive", "I suggest that he leave now.",
             "subjunctive_mandative", "C1")
detect_check("embedded wh-clause (not a wh-question)", "I know what you did.",
             "wh_clause", "B1", forbidden_ids=["wh_question"])

# spaCy-dependent property checks: estimatedLevel + no misfire on plain sentence
if HAVE_SPACY:
    ids, results, meta = ids_for("The cat sat on the mat.")
    check("simple sentence -> past simple", "past_simple" in ids)
    check("estimatedLevel present", meta["estimatedLevel"]["typical"] in gp._CEFR_ORDER)
    check("no passive misfire on plain sentence", "passive_past" not in ids)

    # pretty rendering to a non-tty buffer carries no ANSI and shows the header
    buf = io.StringIO()
    results, meta = gp.profile("She has finished the report.", _NLP, _LEVELS)
    gp.render_pretty("essay.txt", results, meta, stream=buf)
    pretty = buf.getvalue()
    check("pretty has header", "Grammar Profile" in pretty)
    check("pretty has source", "essay.txt" in pretty)
    check("pretty non-tty has no ANSI", "\x1b[" not in pretty)

    # end-to-end JSON via the CLI. Guard json.loads so a CLI failure is counted
    # as a FAIL rather than aborting the suite with a JSONDecodeError traceback.
    rc, out, err = run(["--format", "json", "--text", "I can swim."])
    check("cli json rc==0", rc == 0)
    if rc == 0:
        d = json.loads(out)
        check("cli json shape",
              "results" in d and set(d["results"]) == set(gp._CEFR_ORDER))
    else:
        check("cli json shape", False)
        print(f"  cli stderr: {err.strip()}")
else:
    skipped += 1

# --- the shared taxonomy: every construction, levelled exactly like the -----
# --- profiler, in one machine-readable document both tools cite -------------- 
_tax = gp.taxonomy(_LEVELS)
check("taxonomy covers every registered construction",
      len(_tax) == len(gp._CONSTRUCTIONS))
check("taxonomy entries carry id/name/category/level/cefrjCode",
      all(set(e) == {"id", "name", "category", "level", "cefrjCode"}
          for e in _tax))
check("taxonomy levels resolve exactly like the profiler",
      all(e["level"] == _LEVELS.get(e["cefrjCode"],
                                     gp._CONSTRUCTIONS[e["id"]][3])
          for e in _tax))
_ladder2 = ["A1", "A2", "B1", "B2", "C1", "C2"]
check("taxonomy sorted by band ladder then name",
      _tax == sorted(
          _tax,
          key=lambda e: (
              _ladder2.index(e["level"]) if e["level"] in _ladder2 else 99,
              e["name"].lower(),
          )))
_doc = gp.taxonomy_document(_LEVELS)
check("taxonomy document carries source attribution",
      _doc["constructions"] == _tax and "CEFR-J" in _doc["source"])
_checked_in = json.load(open(os.path.join(HERE, "GrammarProfile", "taxonomy.json"),
                             encoding="utf-8"))
check("checked-in taxonomy.json matches taxonomy_document()",
      _checked_in == _doc)
rc, out, err = run(["--taxonomy"])
check("cli --taxonomy prints the shared document without spaCy",
      rc == 0 and json.loads(out) == _doc)
rc2, out2, err2 = run(["--taxonomy", "--grammar-profile",
                       os.path.join(HERE, "no-such-grammar-profile")])
check("cli --taxonomy with a bad grammar profile fails cleanly",
      rc2 == 1 and "Could not read grammar profile" in err2 and out2 == "")

print(f"\n{passed} passed, {failed} failed, {skipped} skipped"
      + ("  (spaCy not installed — detector checks skipped)" if not HAVE_SPACY else ""))
sys.exit(1 if failed else 0)
