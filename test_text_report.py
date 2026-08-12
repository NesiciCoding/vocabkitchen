#!/usr/bin/env python3
"""Regression guard for text_report.py — the unified difficulty report.

Dependency-free harness (no pytest). Run:  python3 test_text_report.py

Unit checks (readability, coverage figure, above-target lists, verdict, blend,
JSON shape, pretty rendering, error paths) always run. Checks that need spaCy
for the grammar side are skipped when it isn't installed, like
test_grammar_profile.py. The CLI is exercised through subprocess, which —
like the tool itself — re-launches under a sibling .venv when the invoking
interpreter lacks spaCy, so the grammar side of the CLI runs where available.
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
SCRIPT = os.path.join(HERE, "text_report.py")

import text_report as tr  # noqa: E402
import vocab_profile as vp  # noqa: E402
import grammar_profile as gp  # noqa: E402

try:
    _NLP = gp.load_nlp()
    HAVE_GRAMMAR = True
except Exception:
    _NLP = None
    HAVE_GRAMMAR = False

_BASE = os.path.join(HERE, "WordLists")
_LEVELS = [(name, vp.load_wordlist(_BASE, rel)) for name, rel in vp.PROFILERS["cefr"]]

_CAT = "The cat sat on the mat."
_ACADEMIC = ("If I had known about the circumstances, I would have helped them "
             "analyse the implications. The results were analysed by the "
             "committee and the findings were published in a reputable journal.")

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


# --- unit: the venv re-exec is skipped in vocabulary-only modes -------------
_saved_argv = list(sys.argv)
try:
    sys.argv = ["text_report.py", "--no-grammar"]
    tr._maybe_reexec_in_venv()  # must return; never exec's with --no-grammar
    sys.argv = ["text_report.py", "--pre-enrich"]
    tr._maybe_reexec_in_venv()  # ...and with --pre-enrich
    check("re-exec skipped for vocab-only modes", True)
except Exception as _ex:
    check("re-exec skipped for vocab-only modes", False, str(_ex))
finally:
    sys.argv = _saved_argv

# --- unit: syllable heuristic -------------------------------------------------
check("syllables cat -> 1", tr.count_syllables("cat") == 1)
check("syllables the -> 1", tr.count_syllables("the") == 1)
check("syllables analysis -> 4", tr.count_syllables("analysis") == 4)
check("syllables running -> 2", tr.count_syllables("running") == 2)
check("syllables walked -> 1", tr.count_syllables("walked") == 1)
check("syllables table -> 2", tr.count_syllables("table") == 2)
check("syllables wanted keeps 2", tr.count_syllables("wanted") == 2)

# --- unit: sentence count -----------------------------------------------------
check("sentences 3", tr.count_sentences("One. Two! Three?") == 3)
check("sentences without punctuation -> 1", tr.count_sentences("Hello world") == 1)
check("sentences empty -> 1", tr.count_sentences("") == 1)

# --- unit: readability (frozen values for the cat sentence) -------------------
_read = tr.compute_readability(_CAT, 6)
check("readability fre frozen", _read["fleschReadingEase"] == 116.1,
      detail=f"got {_read['fleschReadingEase']}, expected 116.1")
check("readability fk frozen", _read["fleschKincaidGrade"] == -1.4)
check("readability description", _read["description"] == "very easy")
check("readability wordless -> None", tr.compute_readability("!!!", 0) is None)

# --- unit: coverage figure ----------------------------------------------------
_ordered, _total = vp.profile(_CAT, _LEVELS)
_cov = tr.coverage_figure(_ordered, "B1")
check("coverage pct 83", _cov["knownPercent"] == 83)
check("coverage counts", _cov["knownWords"] == 5 and _cov["recognisedWords"] == 6)
check("coverage sentence", "A B1 learner will already know ~83%" in _cov["sentence"])
check("coverage C2 -> 100", tr.coverage_figure(_ordered, "C2")["knownPercent"] == 100)

# --- unit: words above target -------------------------------------------------
_above = tr.words_above_target(_ordered, "B1")
check("mat above B1", _above == [{"word": "mat", "level": "C1", "occurrences": 1}],
      detail=f"got {_above}")
check("nothing above C2", tr.words_above_target(_ordered, "C2") == [])

# --- unit: verdict ------------------------------------------------------------
check("verdict on level", tr.build_verdict([], [], True) == "on level")
check("verdict on level no grammar", tr.build_verdict([], [], False) == "on level")
check("verdict words+structures",
      tr.build_verdict([{"level": "C1"}], [{"level": "B2"}], True)
      == "reaches C1 — pre-teach 1 word, 1 structure")
check("verdict plural",
      tr.build_verdict([{"level": "B2"}, {"level": "C1"}], [], True)
      == "reaches C1 — pre-teach 2 words")
check("verdict structures only",
      tr.build_verdict([], [{"level": "B2"}], True)
      == "reaches B2 — pre-teach 1 structure")
check("verdict omits zero-clause",
      tr.build_verdict([{"level": "B2"}], [], True)
      == "reaches B2 — pre-teach 1 word")
check("verdict without grammar",
      tr.build_verdict([{"level": "B2"}], [], False)
      == "reaches B2 — pre-teach 1 word")

# --- unit: blended estimated level --------------------------------------------
check("blend coverage wins", tr.blend_level("B2", "A1") == "B2")
check("blend grammar wins", tr.blend_level("A2", "B1") == "B1")
check("blend vocab only", tr.blend_level("A2", None) == "A2")
check("blend grammar only", tr.blend_level(None, "B1") == "B1")
check("blend dash skipped", tr.blend_level("—", "B1") == "B1")
check("blend none", tr.blend_level(None, None) is None)

# --- in-process analyze (no grammar -> deterministic degraded path) ------------
_p = tr.analyze(_CAT, target_level="B1", with_grammar=False)
check("analyze total", _p["totalWordCount"] == 6)
check("analyze verdict", _p["verdict"] == "reaches C1 — pre-teach 1 word")
check("analyze blended from coverage only", _p["estimatedLevel"] == "C1")
check("analyze coverage", _p["coverage"]["knownPercent"] == 83)
check("analyze aboveTarget", _p["aboveTarget"]["wordCount"] == 1
      and _p["aboveTarget"]["maxLevel"] == "C1"
      and _p["aboveTarget"]["structureCount"] == 0)
check("analyze grammar skipped note", _p["grammar"] is None
      and _p["grammarError"] == "skipped (--no-grammar)")
check("analyze readability on", _p["readability"] is not None)
check("analyze vocab shape superset",
      set(_p["vocabulary"]["results"]) == {"A1", "A2", "B1", "B2", "C1", "C2", "Off List"})
_p2 = tr.analyze(_CAT, with_grammar=False)
check("analyze no target -> no verdict", _p2["verdict"] is None
      and _p2["coverage"] is None and _p2["aboveTarget"] is None)

# --- unit: simpler-synonym suggestions (--suggest) ----------------------------
_syns = tr.load_synonyms(os.path.join(_BASE, "synonyms.csv"))
check("synonyms loaded from the bundled list", len(_syns) > 20)
check("synonyms entry shape", _syns.get("purchase") == {"word": "buy", "level": "A1"})
check("synonyms missing file is empty",
      tr.load_synonyms(os.path.join(_BASE, "does-not-exist.csv")) == {})

_ps = tr.analyze("We purchase fresh bread daily.", target_level="A2",
                 with_grammar=False, suggest=True)
_pw = next(d for d in _ps["aboveTarget"]["words"] if d["word"] == "purchase")
check("suggest annotates the above-target word",
      _pw.get("suggestion") == {"word": "buy", "level": "A1"})
_pn = tr.analyze("We purchase fresh bread daily.", target_level="A2",
                 with_grammar=False)
_pwn = next(d for d in _pn["aboveTarget"]["words"] if d["word"] == "purchase")
check("no --suggest -> no suggestion key", "suggestion" not in _pwn)

_md_sugg = tr.export_markdown(_ps)
check("md with suggestions gains the Simpler column",
      "| Word | Level | Occurrences | Simpler alternative | Example |" in _md_sugg
      and "| buy (A1) |" in _md_sugg)
_md_plain = tr.export_markdown(_pn)
check("md without suggestions keeps the old shape",
      "| Word | Level | Occurrences | Example |" in _md_plain
      and "Simpler alternative" not in _md_plain)
_buf3 = io.StringIO()
tr.render_pretty(_ps, "p.txt", stream=_buf3)
check("pretty shows the suggestion arrow",
      "purchase (B2) → buy (A1)" in _buf3.getvalue())
rc, out, err = run(["--target-level", "A2", "--no-grammar", "--suggest",
                    "--text", "We purchase fresh bread daily."])
_ds = json.loads(out)
_dw = next(w for w in _ds["aboveTarget"]["words"] if w["word"] == "purchase")
check("cli --suggest carries the suggestion",
      rc == 0 and _dw["suggestion"] == {"word": "buy", "level": "A1"})
rc, _, err = run(["--suggest", "--text", "hi"])
check("cli --suggest without target rc==1",
      rc == 1 and "--suggest requires --target-level" in err)

# --- unit: grammar gap report (--gap-report) ----------------------------------
_gcefrj = gp.load_cefrj_levels(os.path.join(HERE, "GrammarProfile"))
_full_b1 = gp.constructions_at_level(_gcefrj, "B1")
check("constructions_at_level: B1 set is non-empty", len(_full_b1) > 10)
check("constructions_at_level: sorted by category then name",
      [(d["category"], d["name"]) for d in _full_b1]
      == sorted((d["category"], d["name"]) for d in _full_b1))
_gap_empty = tr.grammar_gap_report({}, _gcefrj, "B1")
check("gap report with nothing used lists the whole set",
      _gap_empty["missingCount"] == _gap_empty["total"] > 10
      and _gap_empty["targetLevel"] == "B1"
      and all(m["name"] and m["category"] for m in _gap_empty["missing"]))
_name1 = _full_b1[0]["name"]
_gap_used = tr.grammar_gap_report(
    {"B1": {"x": {"name": _name1}}}, _gcefrj, "B1")
check("gap report excludes used constructions",
      _gap_used["missingCount"] == _gap_used["total"] - 1
      and _name1 not in [m["name"] for m in _gap_used["missing"]])

_pgap = tr.analyze(_CAT, target_level="B1", with_grammar=False, gap_report=True)
check("gap report degrades gracefully without grammar",
      _pgap["grammarGap"] is None and _pgap["grammarGapError"] is not None)
_fake_gap = dict(_pgap)
_fake_gap["grammarGap"] = {
    "targetLevel": "B1", "total": 19, "missingCount": 2,
    "missing": [{"name": "Second conditional", "category": "Conditional"},
                 {"name": "Modal: may", "category": "Modality"}]}
_md_gap = tr.export_markdown(_fake_gap)
check("md with a gap gains the introduce section",
      "## Constructions to introduce at B1 (2 of 19 not used)" in _md_gap
      and "Second conditional" in _md_gap and "Modality" in _md_gap)
check("md without a gap has no introduce section",
      "Constructions to introduce" not in tr.export_markdown(_pgap))
_bufg = io.StringIO()
tr.render_pretty(_fake_gap, "g.txt", stream=_bufg)
check("pretty shows the gap section",
      "Gap report — B1 constructions not used (2 of 19)" in _bufg.getvalue()
      and "Second conditional" in _bufg.getvalue())

rc, _, err = run(["--gap-report", "--text", _CAT])
check("cli --gap-report without target rc==1",
      rc == 1 and "--gap-report requires --target-level" in err)
rc, _, err = run(["--gap-report", "--target-level", "B1", "--no-grammar",
                  "--text", _CAT])
check("cli --gap-report with --no-grammar rc==1",
      rc == 1 and "--gap-report needs the grammar side" in err)
rc, out, err = run(["--gap-report", "--target-level", "B1", "--text", _CAT])
_dg = json.loads(out)
if _dg["grammarGap"] is not None:
    check("cli gap report shape",
          _dg["grammarGap"]["targetLevel"] == "B1"
          and 0 <= _dg["grammarGap"]["missingCount"] <= _dg["grammarGap"]["total"])
else:
    check("cli gap report degraded gracefully", _dg["grammarGapError"] is not None)

# --- unit: curriculum checklist (--curriculum) --------------------------------
_curr_dir = tempfile.mkdtemp(prefix="tr_curriculum_")
_curr_path = os.path.join(_curr_dir, "unit3.txt")
with open(_curr_path, "w", encoding="utf-8") as f:
    f.write("# Unit 3 checklist\n"
            "; bare lines before any section header count as vocabulary\n"
            "mat\n"
            "[vocabulary]\npurchase\ncircumstances\n\n"
            "[grammar]\nsecond conditional\ncond_second\npast perfect\n")


def _raises_curriculum(fn):
    try:
        fn()
    except tr.CurriculumError:
        return True
    return False


_curr = tr.load_curriculum(_curr_path)
check("curriculum: both sections parsed",
      _curr["vocabulary"] == ["mat", "purchase", "circumstances"]
      and _curr["grammar"] == ["second conditional", "cond_second", "past perfect"])
check("curriculum: missing file raises CurriculumError",
      _raises_curriculum(lambda: tr.load_curriculum(
          os.path.join(_curr_dir, "nope.txt"))))
with open(os.path.join(_curr_dir, "bad.txt"), "w", encoding="utf-8") as f:
    f.write("[unknown]\nx\n")
check("curriculum: unknown section raises CurriculumError",
      _raises_curriculum(lambda: tr.load_curriculum(
          os.path.join(_curr_dir, "bad.txt"))))
with open(os.path.join(_curr_dir, "typo.txt"), "w", encoding="utf-8") as f:
    f.write("[grammer]\npast simple\n")
try:
    tr.load_curriculum(os.path.join(_curr_dir, "typo.txt"))
    _typo_msg = ""
except tr.CurriculumError as ex:
    _typo_msg = str(ex)
check("curriculum: typo'd header suggests the fix",
      "unknown curriculum section on line 1" in _typo_msg
      and "Did you mean [grammar]?" in _typo_msg)
with open(os.path.join(_curr_dir, "mal.txt"), "w", encoding="utf-8") as f:
    f.write("[vocabulary] words\n")
check("curriculum: header with trailing text is malformed",
      _raises_curriculum(lambda: tr.load_curriculum(
          os.path.join(_curr_dir, "mal.txt"))))
with open(os.path.join(_curr_dir, "empty.txt"), "w", encoding="utf-8") as f:
    f.write("[vocabulary]\ncat\n\n[grammar]\n")
_sect, _warns = tr.validate_curriculum(os.path.join(_curr_dir, "empty.txt"))
check("curriculum: validate returns sections + warnings",
      _sect == {"vocabulary": ["cat"], "grammar": []}
      and _warns == ["curriculum section [grammar] is empty — nothing required from it"])
check("curriculum: clean file has no warnings",
      tr.validate_curriculum(_curr_path)[1] == [])

check("curriculum resolver: by construction id",
      tr._resolve_construction("cond_second")[0] == "cond_second")
check("curriculum resolver: by display name (case-insensitive)",
      tr._resolve_construction("Second Conditional")
      == ("cond_second", "Second conditional", "Conditionals"))
check("curriculum resolver: exact name wins over its substring",
      tr._resolve_construction("past perfect") == ("past_perf", "Past perfect", "Tense & aspect"))
check("curriculum resolver: unambiguous substring",
      tr._resolve_construction("gerund") is not None)
check("curriculum resolver: ambiguous stays unresolved",
      tr._resolve_construction("passive") is None)
check("curriculum resolver: unknown stays unresolved",
      tr._resolve_construction("floob") is None)

_c_ordered, _ = vp.profile("We must purchase the equipment. Circumstances matter.", _LEVELS)
_fake_gres = {"B1": {"cond_second": {"name": "Second conditional",
                                      "category": "Conditionals",
                                      "count": 1, "examples": []}}}
_cr = tr.curriculum_report(
    "We must purchase the equipment. Circumstances matter.",
    {"vocabulary": ["purchase", "mat"],
     "grammar": ["second conditional", "Passive (present)"]},
    ordered=_c_ordered, gresults=_fake_gres)
check("curriculum report: vocabulary presence + band",
      [(d["word"], d["present"], d["level"]) for d in _cr["vocabulary"]]
      == [("purchase", True, "B2"), ("mat", False, None)])
check("curriculum report: grammar presence and pass verdict",
      [(d["name"], d["present"]) for d in _cr["grammar"]]
      == [("Second conditional", True), ("Passive (present)", False)]
      and _cr["pass"] is False
      and _cr["missing"] == ["mat", "Passive (present)"])
_cr_all = tr.curriculum_report(
    "We must purchase the equipment. Circumstances matter.",
    {"vocabulary": ["purchase", "circumstances"],
     "grammar": ["second conditional"]},
    ordered=_c_ordered, gresults=_fake_gres)
check("curriculum report: all covered -> pass",
      _cr_all["pass"] is True and _cr_all["missing"] == [])
_cr_nog = tr.curriculum_report("mat", {"vocabulary": ["purchase"],
                                        "grammar": ["second conditional"]},
                               ordered=_c_ordered, gresults=None)
check("curriculum report: no grammar results -> grammar unchecked",
      _cr_nog["grammar"][0]["present"] is False)

_pc = tr.analyze("We must purchase the equipment.", target_level="B1",
                 with_grammar=False, curriculum=_curr)
check("analyze carries the curriculum checklist",
      _pc["curriculum"] is not None
      and _pc["curriculum"]["grammarAvailable"] is False
      and _pc["curriculumError"] is not None)
_pc2 = tr.analyze("The cat sat on the mat.", with_grammar=False,
                   curriculum=_curr)
check("curriculum works without --target-level",
      _pc2["curriculum"] is not None)
_bufc = io.StringIO()
tr.render_pretty(_pc, "c.txt", stream=_bufc)
check("pretty shows the curriculum checklist",
      "Curriculum checklist" in _bufc.getvalue())
_md_curr = tr.export_markdown(_pc)
check("md gains the curriculum checklist section",
      "## Curriculum checklist" in _md_curr
      and "| Item | Kind | Status | Level |" in _md_curr)
check("md without curriculum has no checklist section",
      "Curriculum checklist" not in tr.export_markdown(_p2))
rc, out, err = run(["--curriculum", _curr_path, "--text",
                    "We must purchase the equipment. Circumstances matter."])
_dc = json.loads(out)
check("cli --curriculum carries the checklist",
      rc == 0 and _dc["curriculum"] is not None
      and _dc["curriculum"]["pass"] is False
      and any(d["word"] == "purchase" and d["present"] is True
              for d in _dc["curriculum"]["vocabulary"]))
rc, _, err = run(["--curriculum", os.path.join(_curr_dir, "nope.txt"),
                  "--text", "hi"])
check("cli --curriculum missing file rc==1",
      rc == 1 and "curriculum file not found" in err)

# --- unit: watch mode (--watch, the edit -> re-check loop) --------------------
_wf = os.path.join(_curr_dir, "watch.txt")
with open(_wf, "w", encoding="utf-8") as f:
    f.write("v1")
_s1 = tr._file_snapshot(_wf)
time.sleep(0.02)
with open(_wf, "w", encoding="utf-8") as f:
    f.write("v2 with more words")
_s2 = tr._file_snapshot(_wf)
check("watch: snapshot detects a change",
      _s1 is not None and _s2 is not None and _s1 != _s2)
check("watch: snapshot of a missing file is None",
      tr._file_snapshot(os.path.join(_curr_dir, "gone.txt")) is None)
_watch_runs = []


def _watch_cb():
    _watch_runs.append(tr._file_snapshot(_wf))


_tw = threading.Thread(target=lambda: tr.watch_file(_wf, 0.01, _watch_cb,
                                                    timeout=2), daemon=True)
_tw.start()
time.sleep(0.1)
with open(_wf, "w", encoding="utf-8") as f:
    f.write("v3 changed again")
time.sleep(0.1)
os.remove(_wf)
_tw.join(3)
check("watch: re-runs on change and stops when the file disappears",
      len(_watch_runs) >= 1)
rc, _, err = run(["--watch", "--text", "hi"])
check("cli --watch requires --file",
      rc == 1 and "--watch re-profiles a file on save" in err)
rc, _, err = run(["--watch", "--pre-enrich", "--file", _wf, "--text", "hi"])
check("cli --watch rejects --pre-enrich",
      rc == 1 and "--watch and --pre-enrich don't combine" in err)

# --- unit: Cambridge English exam mapping (--cambridge) -----------------------
check("cambridge: B1 maps to Preliminary",
      tr.cambridge_for("B1") == "B1 Preliminary (PET)")
check("cambridge: A1 is below the exam ladder", tr.cambridge_for("A1") is None)
check("cambridge: unknown band is None", tr.cambridge_for("XX") is None)
_pcm = tr.analyze("We purchase fresh bread daily.", with_grammar=False,
                   cambridge=True)
_cm = _pcm["cambridge"]
check("analyze carries the cambridge mapping",
      _cm["vocabulary"]["reaches"] == "B2 First (FCE)"
      and _cm["estimated"] == "B2 First (FCE)"
      and _cm["grammar"] == {"typical": None, "reaches": None})
check("analyze without --cambridge has no mapping",
      tr.analyze("We purchase fresh bread daily.", with_grammar=False)
      .get("cambridge") is None)
_bufcm = io.StringIO()
tr.render_pretty(_pcm, "cm.txt", stream=_bufcm)
check("pretty shows the Cambridge English block",
      "Cambridge English" in _bufcm.getvalue()
      and "B2 First (FCE)" in _bufcm.getvalue())
_md_cm = tr.export_markdown(_pcm)
check("md gains the Cambridge English mapping section",
      "## Cambridge English mapping" in _md_cm
      and "| Vocabulary reaches (B2) | B2 First (FCE) |" in _md_cm)
check("md without --cambridge has no mapping section",
      "Cambridge English" not in tr.export_markdown(
          tr.analyze("We purchase fresh bread daily.", with_grammar=False)))
rc, out, err = run(["--cambridge", "--text", "We purchase fresh bread daily.",
                    "--no-grammar"])
_dcm = json.loads(out)
check("cli --cambridge carries the mapping",
      rc == 0 and _dcm["cambridge"]["vocabulary"]["reaches"]
      == "B2 First (FCE)")

# --- unit: CEFR Can-Do framing (--cando) -------------------------------------
check("cando: B2 has a descriptor",
      tr.cando_for("B2") is not None and "complex text" in tr.cando_for("B2"))
check("cando: all six bands have descriptors",
      all(tr.cando_for(b) for b in ("A1", "A2", "B1", "B2", "C1", "C2")))
check("cando: unknown band is None", tr.cando_for("XX") is None)
_pcd = tr.analyze("We purchase fresh bread daily.", with_grammar=False,
                   cando=True)
_cd = _pcd["cando"]
check("analyze carries the can-do mapping",
      _cd["vocabulary"]["reaches"] == tr.cando_for("B2")
      and _cd["estimated"] == tr.cando_for("B2")
      and _cd["grammar"] == {"typical": None, "reaches": None})
check("analyze without --cando has no mapping",
      tr.analyze("We purchase fresh bread daily.", with_grammar=False)
      .get("cando") is None)
_bufcd = io.StringIO()
tr.render_pretty(_pcd, "cd.txt", stream=_bufcd)
check("pretty shows the Can-Do block",
      "Can-Do (CEFR global scale)" in _bufcd.getvalue()
      and "complex text on both concrete and abstract topics"
      in _bufcd.getvalue())
_md_cd = tr.export_markdown(_pcd)
check("md gains the Can-Do descriptors section",
      "## Can-Do descriptors" in _md_cd
      and "| Demand level | Can-Do descriptor (CEFR global scale) |" in _md_cd
      and "| Estimated level (B2) |" in _md_cd)
check("md without --cando has no Can-Do section",
      "Can-Do" not in tr.export_markdown(
          tr.analyze("We purchase fresh bread daily.", with_grammar=False)))
rc, out, err = run(["--cando", "--text", "We purchase fresh bread daily.",
                    "--no-grammar"])
_dcd = json.loads(out)
check("cli --cando carries the mapping",
      rc == 0 and _dcd["cando"]["vocabulary"]["reaches"] == tr.cando_for("B2"))

# --- unit: Can-Do diff against a target level (--cando + --target-level) -----
_dc = tr.analyze("We purchase fresh bread daily.", target_level="A2",
                 with_grammar=False, cando=True)["cando"]
check("cando with target carries the aboveTarget diff",
      _dc["targetLevel"] == "A2"
      and [e["band"] for e in _dc["aboveTarget"]["vocabulary"]] == ["B1", "B2"]
      and _dc["aboveTarget"]["grammar"] == []
      and [e["band"] for e in _dc["aboveTarget"]["estimated"]] == ["B1", "B2"])
check("cando at-or-below target diff is empty",
      tr.analyze("I am a student.", target_level="B1", with_grammar=False,
                 cando=True)["cando"]["aboveTarget"]
      == {"vocabulary": [], "grammar": [], "estimated": []})
check("cando without a target has no diff",
      "aboveTarget" not in tr.analyze("I am a student.", with_grammar=False,
                                       cando=True)["cando"])
_dcmd = tr.export_markdown(tr.analyze("We purchase fresh bread daily.",
                                      target_level="A2", with_grammar=False,
                                      cando=True))
check("md renders the above-target Can-Do section",
      "### Above the A2 target" in _dcmd
      and "| Vocabulary | B2 |" in _dcmd
      and "pre-teach or rewrite" in _dcmd)
_bufdc = io.StringIO()
tr.render_pretty(tr.analyze("We purchase fresh bread daily.",
                            target_level="A2", with_grammar=False, cando=True),
                 "dc.txt", stream=_bufdc)
check("pretty renders the above-target Can-Do block",
      "above the A2 target" in _bufdc.getvalue()
      and "pre-teach or rewrite" in _bufdc.getvalue())

# --- unit: Can-Do reference deck (--cando --export flashcards) ---------------
_cd_deck = tr.export_cando_deck(
    tr.analyze("We purchase fresh bread daily.", target_level="A2",
               with_grammar=False, cando=True))
_cd_rows = list(_csv.reader(_cd_deck.splitlines()))
check("cando deck: RubricMaker shape with demand cards",
      _cd_rows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"]
      and {r[0] for r in _cd_rows[1:]} == {"B1 — vocabulary demand",
                                            "B2 — vocabulary demand",
                                            "B1 — estimated demand",
                                            "B2 — estimated demand"}
      and all(r[3] == "" and r[4] == "cando" for r in _cd_rows[1:])
      and any("above the A2 target" in r[2] for r in _cd_rows[1:]))
check("cando deck: none without --cando",
      tr.export_cando_deck(tr.analyze("I am a student.", with_grammar=False))
      is None)
check("cando deck path derives from the word deck",
      tr.cando_deck_path("essay-preteaching-B1-deck.csv")
      == "essay-preteaching-B1-cando-deck.csv"
      and tr.cando_deck_path("out.csv") == "out-cando-deck.csv")
# The companion deck is actually written by the CLI next to the word deck.
_cd_cli = tempfile.mkdtemp(prefix="tr_cando_deck_")
rc, out, err = run(["--cando", "--no-grammar", "--target-level", "A2",
                    "--file", os.path.join(HERE, "sample-readings/news-report.txt"),
                    "--export", "flashcards", "--no-enrich", "--output",
                    os.path.join(_cd_cli, "news-deck.csv")])
_has_deck = os.path.isfile(os.path.join(_cd_cli, "news-cando-deck.csv"))
if _has_deck:
    with open(os.path.join(_cd_cli, "news-cando-deck.csv"), encoding="utf-8") as f:
        _deck_rows = list(_csv.reader(f))
check("cli --cando --export flashcards writes the companion deck",
      rc == 0 and _has_deck and _deck_rows[0][0] == "word"
      and all(r[4] == "cando" for r in _deck_rows[1:]))
shutil.rmtree(_cd_cli, ignore_errors=True)

# --- unit: cached definitions (no-network lookups for handouts) ---------------
_cache_path = os.path.join(_curr_dir, "dict-cache.json")
with open(_cache_path, "w", encoding="utf-8") as f:
    json.dump({"version": tr._CACHE_VERSION,
               "entries": {tr._DICT_API: {
                   "purchase": {"definition": "to buy something",
                                 "phonetic": "/p/", "partOfSpeech": "verb"},
                   "miss": None}}}, f)
_defs = tr.cached_definitions(_cache_path)
check("cached_definitions returns real definitions only",
      _defs == {"purchase": "to buy something"})
check("cached_definitions of a missing cache is empty",
      tr.cached_definitions(os.path.join(_curr_dir, "nope.json")) == {})

# --- in-process analyze with grammar (needs spaCy) ----------------------------
if HAVE_GRAMMAR:
    _pg = tr.analyze(_CAT, target_level="B1", with_grammar=True)
    check("analyze grammar attached", _pg["grammar"] is not None
          and _pg["grammar"]["constructionCount"] >= 1)
    check("analyze no B1-exceeding structures in cat text",
          _pg["aboveTarget"]["structures"] == [])
    _pac = tr.analyze(_ACADEMIC, target_level="B1", with_grammar=True)
    _structs = _pac["aboveTarget"]["structures"]
    check("academic: 3 words above B1", _pac["aboveTarget"]["wordCount"] == 3)
    check("academic: B2 structure above B1",
          len(_structs) == 1 and _structs[0]["level"] == "B2"
          and _structs[0]["name"].startswith("Modal + perfect"))
    check("academic verdict",
          _pac["verdict"] == "reaches B2 — pre-teach 3 words, 1 structure")
    # The OLP-EN-CEFRJ merge classified previously off-list function words
    # (i, a), so the 90%-coverage band sits at B1 and the blend follows it.
    check("academic blended B1", _pac["estimatedLevel"] == "B1")
    check("academic grammar reaches B2",
          _pac["grammar"]["estimatedLevel"]["reaches"] == "B2")
else:
    skipped += 1

# --- unit: pretty rendering (in-process, non-tty stream, no grammar) ----------
_buf = io.StringIO()
tr.render_pretty(_p, "essay.txt", stream=_buf)
_pretty = _buf.getvalue()
check("pretty header", "Text Report" in _pretty)
check("pretty source", "essay.txt" in _pretty)
check("pretty vocab labels", "Typical:" in _pretty and "90% coverage:" in _pretty)
check("pretty target + coverage", "Target: B1" in _pretty and "~83%" in _pretty)
check("pretty verdict", "Verdict:" in _pretty and "reaches C1" in _pretty)
check("pretty readability", "Flesch–Kincaid" in _pretty and "Flesch Reading Ease" in _pretty)
check("pretty grammar-skip note", "skipped (--no-grammar)" in _pretty)
check("pretty non-tty has no ANSI", "\x1b[" not in _pretty)

# --- integration: CLI end-to-end ----------------------------------------------
rc, out, err = run(["--target-level", "b1", "--text", _CAT])
check("cli rc==0", rc == 0)
d = json.loads(out)
check("cli total", d["totalWordCount"] == 6)
check("cli target normalised", d["targetLevel"] == "B1")
check("cli coverage", d["coverage"]["knownPercent"] == 83)
check("cli verdict", d["verdict"].startswith("reaches C1 — pre-teach 1 word"))
check("cli readability present", d["readability"] is not None)
if d["grammar"] is not None:
    check("cli grammar section present", d["grammar"]["constructionCount"] >= 1)
else:
    skipped += 1

# --- integration: grammar degrades cleanly on request -------------------------
rc, out, err = run(["--no-grammar", "--target-level", "B1", "--text", _CAT])
d2 = json.loads(out)
check("cli --no-grammar", d2["grammar"] is None
      and d2["grammarError"] == "skipped (--no-grammar)"
      and d2["verdict"] == "reaches C1 — pre-teach 1 word")

# --- integration: academic text via CLI (grammar side where available) --------
rc, out, err = run(["--target-level", "B1", "--text", _ACADEMIC])
check("cli academic rc==0", rc == 0)
d3 = json.loads(out)
check("cli academic words above", d3["aboveTarget"]["wordCount"] == 3)
check("cli academic blended", d3["estimatedLevel"] == "B1")
if d3["grammar"] is not None:
    check("cli academic structure above",
          len(d3["aboveTarget"]["structures"]) == 1
          and d3["aboveTarget"]["structures"][0]["level"] == "B2")
else:
    skipped += 1

# --- integration: --no-readability / pretty / errors --------------------------
rc, out, err = run(["--no-readability", "--text", _CAT])
check("cli --no-readability", rc == 0 and json.loads(out)["readability"] is None)

rc, out, err = run(["--format", "pretty", "--target-level", "B1", "--text", _CAT])
check("cli pretty rc==0", rc == 0)
check("cli pretty verdict line", "Verdict:" in out and "pre-teach" in out)
check("cli pretty no ANSI (piped)", "\x1b[" not in out)

rc, out, err = run(["--target-level", "Z9", "--text", "hi"])
check("cli bad target rc==1", rc == 1 and "Invalid target level" in err)
rc, out, err = run(["--text", "   "])
check("cli blank input rc==1", rc == 1 and "Usage" in err)
rc, out, err = run(["--file", os.path.join(HERE, "definitely-missing.txt")])
check("cli missing file rc==1", rc == 1 and "Could not read file" in err)
rc, out, err = run(["--format", "bogus", "--text", "hi"])
check("cli bad format rc==1", rc == 1 and "Unknown format" in err)

# --- integration: --file input ------------------------------------------------
_tmp = tempfile.mkdtemp(prefix="textreport_")
try:
    essay = os.path.join(_tmp, "essay.txt")
    with open(essay, "w", encoding="utf-8") as f:
        f.write(_CAT)
    rc, out, err = run(["--target-level", "B1", "--file", essay])
    check("cli --file rc==0", rc == 0)
    df = json.loads(out)
    check("cli --file matches --text", df["totalWordCount"] == 6
          and df["verdict"].startswith("reaches C1"))

    empty = os.path.join(_tmp, "empty.txt")
    with open(empty, "w", encoding="utf-8") as f:
        f.write("   \n\t")
    rc, out, err = run(["--file", empty])
    check("cli empty file rc==1", rc == 1 and "No analysable" in err)
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

# --- unit: word contexts -----------------------------------------------------
_ctx = tr.word_contexts(_ACADEMIC, ["circumstances", "implications", "analyse"])
check("context found for each word",
      set(_ctx) == {"circumstances", "implications", "analyse"})
check("context is a full sentence", _ctx["circumstances"].startswith("If I had known"))
check("context case-insensitive", "analyse" in _ctx["analyse"])
check("context missing word absent", "zzz" not in tr.word_contexts(_ACADEMIC, ["zzz"]))

# --- unit: export path -------------------------------------------------------
check("export default next to file",
      tr.export_path("/tmp/x/essay.docx", None, "B1", "md")
      == "/tmp/x/essay-preteaching-B1.md")
check("export default cwd for text",
      tr.export_path(None, None, "B1", "csv") == "preteaching-B1.csv")
check("export output override",
      tr.export_path("/tmp/x/essay.docx", "handout.md", "B1", "md") == "handout.md")

# --- unit: exports (in-process, no grammar -> deterministic) -----------------
_px = tr.analyze(_ACADEMIC, target_level="B1", with_grammar=False)
_rows = list(_csv.reader(tr.export_csv(_px).splitlines()))
check("csv header",
      _rows[0] == ["type", "item", "level", "count", "category", "example"])
check("csv word row with context",
      _rows[1][:5] == ["word", "circumstances", "B2", "1", ""]
      and _rows[1][5].startswith("If I had known about the circumstances"))
check("csv quoting handles commas",
      len(_rows) == 4 and all(len(r) == 6 for r in _rows))
_md = tr.export_markdown(_px)
check("md title + verdict",
      "# Pre-teaching list — Target B1" in _md
      and "**Verdict:** reaches B2 — pre-teach 3 words" in _md)
check("md words table", "## Words above B1 (3)" in _md
      and "| circumstances | B2 | 1 | If I had known" in _md)
check("md no structures section (grammar skipped)", "## Structures above B1" not in _md)
check("md on-level handout",
      "nothing to pre-teach" in tr.export_markdown(
          tr.analyze("Hello world.", target_level="C2", with_grammar=False)))
if HAVE_GRAMMAR:
    _pxg = tr.analyze(_ACADEMIC, target_level="B1", with_grammar=True)
    _srows = [r for r in _csv.reader(tr.export_csv(_pxg).splitlines())
              if r[0] == "structure"]
    check("csv structure rows from grammar", len(_srows) == 1
          and _srows[0][1].startswith("Modal + perfect")
          and _srows[0][2] == "B2" and _srows[0][3] == "1"
          and _srows[0][4] and _srows[0][5])
    _mdg = tr.export_markdown(_pxg)
    check("md structures table", "## Structures above B1 (1)" in _mdg
          and "Modal + perfect" in _mdg)
else:
    skipped += 1

# --- integration: --export via CLI -------------------------------------------
_tmp2 = tempfile.mkdtemp(prefix="textreport_export_")
try:
    essay = os.path.join(_tmp2, "essay.txt")
    with open(essay, "w", encoding="utf-8") as f:
        f.write(_ACADEMIC)
    rc, out, err = run(["--target-level", "B1", "--file", essay,
                        "--export", "md", "--no-grammar"])
    md_path = os.path.join(_tmp2, "essay-preteaching-B1.md")
    check("cli export md default path", rc == 0 and os.path.exists(md_path))
    with open(md_path, encoding="utf-8") as f:
        md_body = f.read()
    check("cli export md content", "## Words above B1" in md_body
          and "circumstances" in md_body)
    check("cli export note on stderr", "Wrote pre-teaching list" in err)

    out_path = os.path.join(_tmp2, "handout.csv")
    rc, out, err = run(["--target-level", "B1", "--file", essay,
                        "--export", "csv", "--output", out_path,
                        "--no-grammar"])
    check("cli export csv --output", rc == 0 and os.path.exists(out_path))
    with open(out_path, encoding="utf-8") as f:
        rows2 = list(_csv.reader(f))
    check("cli export csv rows", len(rows2) == 4  # header + 3 words
          and rows2[1][:3] == ["word", "circumstances", "B2"])

    json_path = os.path.join(_tmp2, "json-export.md")
    rc, out, err = run(["--target-level", "B1", "--text", _CAT,
                        "--export", "md", "--output", json_path,
                        "--no-grammar"])
    check("cli json stdout stays parseable with export",
          rc == 0 and json.loads(out)["verdict"].startswith("reaches C1")
          and os.path.exists(json_path)
          and "Wrote pre-teaching list" not in out)

    rc, out, err = run(["--export", "md", "--text", _CAT])
    check("cli export without target errors",
          rc == 1 and "requires --target-level" in err)
    rc, out, err = run(["--target-level", "B1", "--export", "xlsx", "--text", _CAT])
    check("cli bad export format", rc != 0 and "invalid choice" in err)
finally:
    shutil.rmtree(_tmp2, ignore_errors=True)

# --- unit: cloze gap blanking (RubricMaker fill-the-gap syntax) --------------
check("blank_gap first occurrence",
      tr.blank_gap("the cat and the cat", "cat") == "the {{cat}} and the cat")
check("blank_gap case-insensitive",
      tr.blank_gap("The cat sat.", "cat") == "The {{cat}} sat.")
check("blank_gap multi-word span",
      tr.blank_gap("I would have helped them.", "would have helped")
      == "I {{would have helped}} them.")
check("blank_gap escapes regex metachars",
      tr.blank_gap("foo a+b bar", "a+b") == "foo {{a+b}} bar")
check("blank_gap not found unchanged",
      tr.blank_gap("hello world", "zzz") == "hello world")
check("blank_gap empty", tr.blank_gap("", "x") == "")

# --- unit: cloze exports -----------------------------------------------------
_pzc = tr.analyze(_ACADEMIC, target_level="B1", with_grammar=False)
_mdc = tr.export_markdown(_pzc, cloze=True)
check("cloze md blanks word",
      "{{circumstances}}" in _mdc and "had known about the {{circumstances}}" in _mdc)
check("cloze md worksheet note", "Worksheet mode" in _mdc and "fill-the-gap" in _mdc)
check("plain md has no gaps", "{{" not in tr.export_markdown(_pzc))
_csc = tr.export_csv(_pzc, cloze=True)
check("cloze csv blanks word", "about the {{circumstances}}" in _csc)
check("plain csv has no gaps", "{{" not in tr.export_csv(_pzc))
if HAVE_GRAMMAR:
    _pxgc = tr.analyze(_ACADEMIC, target_level="B1", with_grammar=True)
    _mdgc = tr.export_markdown(_pxgc, cloze=True)
    check("cloze md blanks structure span",
          "I {{would have helped}} them" in _mdgc
          and "would have helped" not in _mdgc.split("I ")[1].split("them")[0])
else:
    skipped += 1

# --- unit: RubricMaker flashcard-deck export ---------------------------------
_deck, _deck_stats = tr.export_flashcards(_pzc, enrich=False)
_drows = list(_csv.reader(_deck.splitlines()))
check("deck header exact RubricMaker shape",
      _drows[0] == ["word", "definition", "example", "phonetic", "partOfSpeech"])
check("deck rows have non-empty front+back",
      all(len(r) == 5 and r[0] and r[1] for r in _drows[1:]))
check("deck is words only (no structure rows)",
      all(r[0] in {"circumstances", "implications", "known"} for r in _drows[1:]))
check("deck enrich=False is a no-op",
      _deck_stats == {"enriched": 0, "missed": 0, "offline": False, "cached": 0})
# Replicate RubricMaker's cardsFromRows header-skip + drop rules (flashcardImport.ts)
_hfront = _re.compile(r"^(front|term|word|question|phrase)$", _re.I)
_hback = _re.compile(r"^(back|definition|translation|answer|meaning)$", _re.I)
_cards = []
for i, row in enumerate(_drows):
    front, back = row[0], row[1]
    if not front or not back:
        continue
    if i == 0 and (_hfront.match(front) or _hback.match(back)):
        continue
    _cards.append((front, back, row[2], row[3], row[4]))
check("deck imports as RubricMaker cards",
      len(_cards) == 3 and _cards[0][0] == "circumstances"
      and _cards[0][1].startswith("If I had known about the circumstances"))
check("deck default path has -deck suffix",
      tr.export_path("/tmp/x/essay.docx", None, "B1", "flashcards")
      == "/tmp/x/essay-preteaching-B1-deck.csv")

# --- integration: cloze + flashcards via CLI ---------------------------------
_tmp3 = tempfile.mkdtemp(prefix="textreport_cloze_")
try:
    essay = os.path.join(_tmp3, "essay.txt")
    with open(essay, "w", encoding="utf-8") as f:
        f.write(_ACADEMIC)
    rc, out, err = run(["--target-level", "B1", "--file", essay,
                        "--export", "md", "--cloze", "--no-grammar"])
    cloze_path = os.path.join(_tmp3, "essay-preteaching-B1.md")
    check("cli cloze md written", rc == 0 and os.path.exists(cloze_path))
    with open(cloze_path, encoding="utf-8") as f:
        cloze_body = f.read()
    check("cli cloze md gaps", "{{circumstances}}" in cloze_body
          and "Worksheet mode" in cloze_body)

    rc, out, err = run(["--target-level", "B1", "--file", essay,
                        "--export", "flashcards", "--no-grammar", "--no-enrich"])
    deck_path = os.path.join(_tmp3, "essay-preteaching-B1-deck.csv")
    check("cli deck written at -deck path", rc == 0 and os.path.exists(deck_path))
    with open(deck_path, encoding="utf-8") as f:
        deck_rows = list(_csv.reader(f))
    check("cli deck header", deck_rows[0][0] == "word"
          and deck_rows[0][1] == "definition")
    check("cli deck cards", len(deck_rows) == 4)

    rc, out, err = run(["--cloze", "--text", _CAT])
    check("cli cloze without export errors",
          rc == 1 and "requires --export" in err)
    rc, out, err = run(["--target-level", "B1", "--cloze", "--export", "flashcards",
                        "--text", _CAT])
    check("cli cloze + flashcards errors",
          rc == 1 and "applies to the md/csv exports" in err)
finally:
    shutil.rmtree(_tmp3, ignore_errors=True)

# --- unit: Free Dictionary API enrichment ------------------------------------
check("dict parser valid entry",
      tr.parse_dictionary_entry([{"word": "x", "phonetic": "/p/",
                                 "phonetics": [{"text": "/p/"}],
                                 "meanings": [{"partOfSpeech": "noun",
                                               "definitions": [{"definition": "a def"}]}]}]) ==
      {"definition": "a def", "phonetic": "/p/", "partOfSpeech": "noun"})
check("dict parser phonetic from phonetics[]",
      tr.parse_dictionary_entry([{"word": "x",
                                 "phonetics": [{"text": "/alt/"}],
                                 "meanings": [{"partOfSpeech": "verb",
                                               "definitions": [{"definition": "d"}]}]}]) ==
      {"definition": "d", "phonetic": "/alt/", "partOfSpeech": "verb"})
check("dict parser missing definition -> None",
      tr.parse_dictionary_entry([{"word": "x",
                                 "meanings": [{"partOfSpeech": "noun"}]}]) ==
      {"definition": None, "phonetic": None, "partOfSpeech": "noun"})
check("dict parser junk payload -> None",
      tr.parse_dictionary_entry([]) is None and tr.parse_dictionary_entry(None) is None
      and tr.parse_dictionary_entry({"not": "an array"}) is None)

# Real HTTP path against a local server — hermetic, no external network.
class _DictHandler(http.server.BaseHTTPRequestHandler):
    _lock = threading.Lock()
    requests = 0

    def do_GET(self):
        with _DictHandler._lock:
            _DictHandler.requests += 1
        word = self.path.rsplit("/", 1)[-1]
        if word == "rate-limited":
            self.send_response(429)
            self.end_headers()
            return
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
try:
    _hit = tr.lookup_dictionary("circumstances", base_url=_dict_url)
    check("lookup http returns parsed entry",
          _hit == {"definition": "a fact connected with an event",
                   "phonetic": "/s/", "partOfSpeech": "noun"})
    check("lookup http 404 -> None",
          tr.lookup_dictionary("known", base_url=_dict_url) is None)
    try:
        tr.lookup_dictionary("x", base_url="http://127.0.0.1:1", timeout=3)
        check("lookup refused raises network error", False)
    except tr._DictNetworkError:
        check("lookup refused raises network error", True)
    try:
        tr.lookup_dictionary("rate-limited", base_url=_dict_url)
        check("lookup 429 raises network error", False)
    except tr._DictNetworkError:
        check("lookup 429 raises network error", True)
    _c429_dir = tempfile.mkdtemp(prefix="textreport_429_")
    try:
        _c429 = os.path.join(_c429_dir, "c.json")
        _s429 = tr.pre_enrich_words(["rate-limited"], base_url=_dict_url,
                                    cache_path=_c429, delay=0)
        _cached_429 = {}
        if os.path.exists(_c429):
            with open(_c429, encoding="utf-8") as f:
                _cached_429 = json.load(f)
        check("lookup 429 is not cached as a miss",
              _s429["offline"] and "rate-limited" not in json.dumps(_cached_429))
    finally:
        shutil.rmtree(_c429_dir, ignore_errors=True)

    # --- enriched deck export (stubbed lookup) ------------------------------
    _FAKE = {
        "circumstances": {"definition": "a real definition",
                          "phonetic": "/s/", "partOfSpeech": "noun"},
        "implications": {"definition": "likely consequences",
                          "phonetic": None, "partOfSpeech": "noun"},
        "known": None,
    }

    def _fake_lookup(word):
        return _FAKE.get(word)

    _deck2, _stats2 = tr.export_flashcards(_pzc, enrich=True, lookup=_fake_lookup)
    _d2rows = list(_csv.reader(_deck2.splitlines()))
    _c2 = [r for r in _d2rows if r[0] == "circumstances"][0]
    check("enriched deck: definition is the back", _c2[1] == "a real definition")
    check("enriched deck: context moved to example", _c2[2].startswith("If I had known"))
    check("enriched deck: phonetic filled", _c2[3] == "/s/")
    check("enriched deck: pos filled", _c2[4] == "noun")
    check("enriched deck: miss keeps context back",
          [r for r in _d2rows if r[0] == "known"][0][1].startswith("If I had known"))
    check("enriched deck: stats track hits and misses",
          _stats2 == {"enriched": 2, "missed": 1, "offline": False, "cached": 0})

    def _offline_lookup(word):
        raise tr._DictNetworkError("offline")

    _deck3, _stats3 = tr.export_flashcards(_pzc, enrich=True, lookup=_offline_lookup)
    _d3rows = list(_csv.reader(_deck3.splitlines()))
    check("enriched deck: offline falls back to context",
          all(r[1].startswith("If I had known") for r in _d3rows[1:])
          and _stats3 == {"enriched": 0, "missed": 0, "offline": True, "cached": 0})

    _deck4, _s4 = tr.export_flashcards(
        _pzc, enrich=False, level_index={"known": {"level": "B2", "pos": "adjective"}})
    check("deck pos falls back to OLP index",
          [r for r in _csv.reader(_deck4.splitlines()) if r[0] == "known"][0][4] == "adjective")

    # --- cache: repeat exports skip the network ------------------------------
    _ctmp = tempfile.mkdtemp(prefix="textreport_cache_")
    try:
        _cache_file = os.path.join(_ctmp, "dictionary.json")
        _calls = []

        def _counting_lookup(word):
            _calls.append(word)
            return _FAKE.get(word)

        _d5, _s5 = tr.export_flashcards(_pzc, enrich=True, lookup=_counting_lookup,
                                        cache_path=_cache_file)
        _calls.clear()
        _d6, _s6 = tr.export_flashcards(_pzc, enrich=True, lookup=_counting_lookup,
                                        cache_path=_cache_file)
        check("cache: first run fetches the API",
              _s5 == {"enriched": 2, "missed": 1, "offline": False, "cached": 0})
        check("cache: second run makes no requests",
              _calls == []
              and _s6 == {"enriched": 2, "missed": 1, "offline": False, "cached": 3})
        check("cache: hits and misses both cached",
              _s6["cached"] == 3 and _s6["missed"] == 1)
        with open(_cache_file, encoding="utf-8") as _cf:
            _cache_payload = json.load(_cf)
        check("cache: file written with version",
              os.path.exists(_cache_file) and _cache_payload["version"] == 1)
        check("cache: default path is user-level",
              tr.default_dictionary_cache_path().endswith(
                  os.path.join("vocabkitchen", "dictionary.json")))
    finally:
        shutil.rmtree(_ctmp, ignore_errors=True)

    # --- pre-enrich: prime the cache in one polite pass ----------------------
    _ptmp = tempfile.mkdtemp(prefix="textreport_preenrich_")
    try:
        _pcache = os.path.join(_ptmp, "dictionary.json")
        _pcalls = []

        def _plookup(word):
            _pcalls.append(word)
            return _FAKE.get(word)

        _ps1 = tr.pre_enrich_words(
            ["circumstances", "implications", "known", "circumstances"],
            lookup=_plookup, cache_path=_pcache, delay=0)
        _pcalls.clear()
        _ps2 = tr.pre_enrich_words(
            ["circumstances", "implications", "known"],
            lookup=_plookup, cache_path=_pcache, delay=0)
        check("pre-enrich: first pass fetches distinct words",
              _ps1 == {"requested": 4, "skipped": 1, "looked_up": 3,
                       "found": 2, "missed": 1, "offline": False})
        check("pre-enrich: second pass is cache-only",
              _pcalls == [] and _ps2["looked_up"] == 0 and _ps2["skipped"] == 3)

        def _plookup_offline(word):
            raise tr._DictNetworkError("offline")

        _ps3 = tr.pre_enrich_words(
            ["circumstances", "implications"], lookup=_plookup_offline,
            cache_path=os.path.join(_ptmp, "offline.json"), delay=0)
        check("pre-enrich: offline stops the pass",
              _ps3["offline"] and _ps3["looked_up"] == 0 and _ps3["missed"] == 0)

        def _fresh(w):
            return {"definition": "d", "phonetic": None, "partOfSpeech": None}

        check("pre-enrich: limit caps new lookups",
              tr.pre_enrich_words(["fresh1", "fresh2", "fresh3"], lookup=_fresh,
                                  cache_path=os.path.join(_ptmp, "d3.json"),
                                  delay=0, limit=2)["looked_up"] == 2)
        _prog = []
        _ps5 = tr.pre_enrich_words(
            ["w%02d" % i for i in range(30)], lookup=_fresh,
            cache_path=os.path.join(_ptmp, "d4.json"), delay=0,
            on_progress=lambda s: _prog.append(s))
        check("pre-enrich: progress callback fires every 25",
              len(_prog) == 1 and _ps5["looked_up"] == 30 and _ps5["found"] == 30)
    finally:
        shutil.rmtree(_ptmp, ignore_errors=True)

    # CLI: enriched deck through --dictionary-url against the local server.
    _tmpd = tempfile.mkdtemp(prefix="textreport_enrich_")
    try:
        rc, out, err = run(["--target-level", "B1", "--text", _ACADEMIC,
                            "--export", "flashcards", "--dictionary-url", _dict_url,
                            "--no-grammar", "--no-dictionary-cache",
                            "--output", os.path.join(_tmpd, "deck.csv")])
        _rows = list(_csv.reader(open(os.path.join(_tmpd, "deck.csv"), encoding="utf-8")))
        _circ = [r for r in _rows if r[0] == "circumstances"]
        check("cli enriched deck has real definition",
              rc == 0 and _circ and _circ[0][1] == "a fact connected with an event")
        check("cli enrich stats on stderr", "2 definitions added, 1 word not found" in err)

        # Repeat export with a cache file: first run requests, second doesn't.
        _cache_file = os.path.join(_tmpd, "dict-cache.json")
        _before = _DictHandler.requests
        rc1, _, err1 = run(["--target-level", "B1", "--text", _ACADEMIC,
                            "--export", "flashcards", "--dictionary-url", _dict_url,
                            "--dictionary-cache", _cache_file, "--no-grammar",
                            "--output", os.path.join(_tmpd, "deck1.csv")])
        _after_first = _DictHandler.requests
        rc2, _, err2 = run(["--target-level", "B1", "--text", _ACADEMIC,
                            "--export", "flashcards", "--dictionary-url", _dict_url,
                            "--dictionary-cache", _cache_file, "--no-grammar",
                            "--output", os.path.join(_tmpd, "deck2.csv")])
        check("cli cache: first run requests the API",
              rc1 == 0 and _after_first > _before and "from cache" not in err1)
        check("cli cache: second run makes no requests",
              rc2 == 0 and _DictHandler.requests == _after_first
              and "from cache" in err2)

        # Batch pre-enrichment: prime the cache from a word list in one pass.
        _pre = os.path.join(_tmpd, "pre-cache.json")
        _before = _DictHandler.requests
        rc3, out3, err3 = run(["--pre-enrich", "--text",
                               "circumstances implications zzqnotaword",
                               "--dictionary-url", _dict_url,
                               "--dictionary-cache", _pre, "--delay", "0"])
        _after_pre = _DictHandler.requests
        rc4, out4, err4 = run(["--pre-enrich", "--text",
                               "circumstances implications zzqnotaword",
                               "--dictionary-url", _dict_url,
                               "--dictionary-cache", _pre, "--delay", "0"])
        check("cli pre-enrich: first pass primes the cache",
              rc3 == 0 and out3 == "" and _after_pre - _before == 3
              and "Pre-enriched 3 words (2 found, 1 not found)" in err3)
        check("cli pre-enrich: second pass makes no requests",
              rc4 == 0 and _DictHandler.requests == _after_pre
              and "3 of 3 already cached" in err4)
        rc5, _, err5 = run(["--pre-enrich", "--export", "md", "--text", _CAT])
        check("cli pre-enrich + export errors",
              rc5 == 1 and "can't be combined with --export" in err5)
    finally:
        shutil.rmtree(_tmpd, ignore_errors=True)
finally:
    _dict_server.shutdown()

print(f"\n{passed} passed, {failed} failed, {skipped} skipped"
      + ("  (spaCy not installed — grammar checks skipped)" if not HAVE_GRAMMAR else ""))
sys.exit(1 if failed else 0)
