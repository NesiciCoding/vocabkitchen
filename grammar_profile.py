#!/usr/bin/env python3
"""EFL-Tools grammar profiler — CEFR grammar analysis for English text.

A companion to ``vocab_profile.py``. Where the vocabulary profiler scores *which
words* a text uses, this tool profiles *which grammatical constructions* it uses
— present perfect, the passive, relative clauses, conditionals, modals, and so
on — and maps each to a CEFR level, so you can see how grammatically demanding a
text is and where its structural range reaches.

Levels come from the **CEFR-J Grammar Profile** (Tono Laboratory, Tokyo
University of Foreign Studies; bundled under ``GrammarProfile/``). Each detector
declares the CEFR-J "shorthand code" it corresponds to, and its level is read
from that dataset at load time (coarsened A1.1 -> A1, etc.), so the mapping is
data-driven and auditable. See ``GRAMMARPROFILE.md`` for provenance and the full
construction-to-code table.

Detection is **rule-based**: deterministic rules run over a spaCy part-of-speech
and dependency parse — there is no LLM in the loop. Because reliable grammar
detection needs real parsing, this tool **requires spaCy** and the small English
model ``en_core_web_sm`` (unlike the dependency-free vocabulary profiler):

    pip install spacy
    python3 -m spacy download en_core_web_sm

Usage:
    python3 grammar_profile.py --text "If I had known, I would have helped."
    python3 grammar_profile.py --file essay.docx
    echo "The results were analysed by the team." | python3 grammar_profile.py

Flags:
    --format          auto | json | pretty  (default: auto — a colour terminal
                      view when stdout is a TTY, JSON when piped/redirected)
    --text            inline text to analyse
    --file            path to a .txt, .md, .docx, or .pdf file to analyse
    --grammar-profile directory holding the CEFR-J grammar-profile CSV
                      (default: the GrammarProfile folder next to this script)
    (stdin)           if neither --text nor --file is given, text is read from stdin

Output: with --format json, a JSON object with sentence/token counts, an
estimated grammatical level, and — grouped by CEFR level — every construction
detected, its count, and example spans. With --format pretty, a colour-coded
terminal view. Pair it with vocab_profile.py for a combined vocabulary + grammar
picture of a text.
"""

import argparse
import csv
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Document text extraction — plain text, Markdown, Word .docx, PDF.
#
# Mirrors vocab_profile.py so the grammar tool reads the same file formats and
# stays a self-contained, independently packageable script. Kept in sync by
# hand; only PDF needs a third-party package (pypdf).
# ---------------------------------------------------------------------------

class DocumentError(Exception):
    """Raised when an input file cannot be read or yields no analysable text."""


def _read_plain(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


_MD_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MD_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_MD_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_MD_LIST_MARKER_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+", re.MULTILINE)
_MD_HR_RE = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_|~~)")


def _read_markdown(path):
    md = _read_plain(path)
    md = _MD_FENCE_RE.sub(" ", md)
    md = _MD_IMAGE_RE.sub(r"\1", md)
    md = _MD_LINK_RE.sub(r"\1", md)
    md = _MD_INLINE_CODE_RE.sub(r"\1", md)
    md = _MD_HTML_TAG_RE.sub(" ", md)
    md = _MD_HR_RE.sub(" ", md)
    md = _MD_HEADING_RE.sub("", md)
    md = _MD_BLOCKQUOTE_RE.sub("", md)
    md = _MD_LIST_MARKER_RE.sub("", md)
    md = _MD_EMPHASIS_RE.sub("", md)
    md = md.replace("|", " ")
    return md


_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _read_docx(path):
    import zipfile
    import xml.etree.ElementTree as ET

    try:
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                root = ET.parse(f).getroot()
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as ex:
        raise DocumentError(f"'{path}' is not a readable .docx file: {ex}")

    paragraphs = []
    for para in root.iter(_DOCX_NS + "p"):
        runs = []
        for node in para.iter():
            tag = node.tag
            if tag == _DOCX_NS + "t" and node.text:
                runs.append(node.text)
            elif tag == _DOCX_NS + "tab":
                runs.append(" ")
            elif tag == _DOCX_NS + "br":
                runs.append("\n")
        paragraphs.append("".join(runs))
    return "\n".join(paragraphs)


def _read_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # older name, same API
        except ImportError:
            raise DocumentError(
                "Reading PDF files needs the optional 'pypdf' package. "
                "Install it with:  pip install pypdf"
            )
    try:
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except DocumentError:
        raise
    except Exception as ex:
        raise DocumentError(f"Could not read PDF '{path}': {ex}")


_EXTRACTORS = {
    ".md": _read_markdown,
    ".markdown": _read_markdown,
    ".docx": _read_docx,
    ".pdf": _read_pdf,
}


def extract_text(path):
    """Read *path* and return its text, dispatching on file extension."""
    if not os.path.exists(path):
        raise DocumentError(f"Could not read file '{path}': file not found.")

    ext = os.path.splitext(path)[1].lower()
    extractor = _EXTRACTORS.get(ext, _read_plain)
    try:
        text = extractor(path)
    except DocumentError:
        raise
    except (IOError, OSError, UnicodeDecodeError) as ex:
        raise DocumentError(f"Could not read file '{path}': {ex}")

    if text is None or text.strip() == "":
        hint = (
            " (a scanned or image-only PDF has no text layer; OCR is not performed)"
            if ext == ".pdf" else ""
        )
        raise DocumentError(f"No analysable text found in '{path}'{hint}.")
    return text


# ---------------------------------------------------------------------------
# spaCy engine loading
# ---------------------------------------------------------------------------

_MODEL = "en_core_web_sm"


class EngineError(Exception):
    """Raised when spaCy or its English model is unavailable."""


def _find_engine_python():
    """Locate a Python interpreter that likely has spaCy, if not this one.

    Looks at ``$GRAMMAR_PROFILE_PYTHON`` then a ``.venv`` sitting next to the
    *real* script (symlinks resolved, so this finds the repo-root venv even when
    the script is loaded through the plugin's symlink). Returns a path or None.
    """
    override = os.environ.get("GRAMMAR_PROFILE_PYTHON")
    real_dir = os.path.dirname(os.path.realpath(__file__))
    candidates = [
        override,
        os.path.join(real_dir, ".venv", "bin", "python"),
        os.path.join(real_dir, "venv", "bin", "python"),
    ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            # abspath, NOT realpath: a venv's bin/python is a symlink to the base
            # interpreter, and only the unresolved venv path activates its
            # site-packages. Resolving it would defeat the whole point.
            return os.path.abspath(cand)
    return None


def _maybe_reexec_in_venv():
    """Re-launch under a spaCy-capable venv if the current interpreter lacks it.

    On externally-managed systems (e.g. Arch, PEP 668) spaCy is usually installed
    into a virtual environment rather than the system Python. If this interpreter
    can't import spaCy but a sibling ``.venv`` can, transparently re-exec there so
    ``python3 grammar_profile.py`` and the plugin wrapper both work without the
    user having to activate anything. Guarded against loops and no-ops.
    """
    import importlib.util
    if importlib.util.find_spec("spacy") is not None:
        return  # this interpreter already has spaCy
    if os.environ.get("_GRAMMAR_PROFILE_REEXEC"):
        return  # already re-exec'd once; don't loop
    py = _find_engine_python()
    if not py or os.path.abspath(py) == os.path.abspath(sys.executable):
        return
    env = dict(os.environ, _GRAMMAR_PROFILE_REEXEC="1")
    try:
        os.execve(py, [py, os.path.abspath(__file__)] + sys.argv[1:], env)
    except OSError:
        return  # fall through to the normal EngineError with install guidance


def load_nlp(model=_MODEL):
    """Load the spaCy pipeline, or raise EngineError with install guidance."""
    try:
        import spacy
    except ImportError:
        raise EngineError(
            "The grammar profiler needs spaCy, which is not installed.\n"
            "Install it with:\n"
            "    pip install spacy\n"
            "    python3 -m spacy download en_core_web_sm"
        )
    try:
        return spacy.load(model)
    except OSError:
        raise EngineError(
            f"The spaCy English model '{model}' is not installed.\n"
            "Install it with:\n"
            f"    python3 -m spacy download {model}"
        )


# ---------------------------------------------------------------------------
# CEFR level resolution from the bundled CEFR-J Grammar Profile
# ---------------------------------------------------------------------------

_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
_LEVEL_INDEX = {lvl: i for i, lvl in enumerate(_CEFR_ORDER)}
_COARSE_RE = re.compile(r"([ABC][12])")


def _coarse(value):
    """A1.2 -> A1, 'B1-C1' -> B1, blank/N/A -> ''. Takes the first CEFR band."""
    m = _COARSE_RE.match((value or "").strip())
    return m.group(1) if m else ""


def load_cefrj_levels(base_dir):
    """Map every CEFR-J shorthand code to its coarse CEFR level.

    Prefers the 'CEFR-J Level' column, falling back to the cross-referenced
    'Core Inventory' then 'EGP' columns when CEFR-J itself is blank.
    """
    path = os.path.join(base_dir, "cefrj-grammar-profile.csv")
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as ex:
        raise EngineError(f"Could not read grammar profile '{path}': {ex}")

    levels = {}
    for r in rows:
        code = (r.get("Shorthand Code") or "").strip()
        if not code:
            continue
        lvl = (_coarse(r.get("CEFR-J Level"))
               or _coarse(r.get("Core Inventory"))
               or _coarse(r.get("EGP")))
        if lvl:
            levels[code] = lvl
    return levels


# ---------------------------------------------------------------------------
# Construction registry
#
# Each construction: id -> (name, category, cefrj_code, fallback_level). The
# level shown is read from the CEFR-J profile for `cefrj_code`; `fallback` is used
# only when the code is blank/absent in the source or when no single CEFR-J code
# fits (e.g. `had better`, whose code carries no level, and the generic adverbial
# clause / relative-whom/whose, which have no dedicated code).
# ---------------------------------------------------------------------------

# id: (display name, category, CEFR-J shorthand code, fallback level)
_CONSTRUCTIONS = {
    # --- Tense & aspect -----------------------------------------------------
    "pres_simple_be":  ("Present simple (be)", "Tense & aspect", "TA.PRESENT.be.AFF", "A1"),
    "pres_simple":     ("Present simple", "Tense & aspect", "TA.PRESENT.do.AFF", "A1"),
    "past_simple_be":  ("Past simple (be)", "Tense & aspect", "TA.PAST.be.AFF", "A1"),
    "past_simple":     ("Past simple", "Tense & aspect", "TA.PAST.do.AFF", "A1"),
    "pres_prog":       ("Present progressive", "Tense & aspect", "TA.PRPRG.AFF", "A1"),
    "past_prog":       ("Past progressive", "Tense & aspect", "TA.PASTPRG.AFF", "A2"),
    "pres_perf":       ("Present perfect", "Tense & aspect", "TA.PRPF.AFF", "A2"),
    "past_perf":       ("Past perfect", "Tense & aspect", "TA.PASTPF.AFF", "B1"),
    "pres_perf_prog":  ("Present perfect progressive", "Tense & aspect", "TA.PRPFPRG.AFF", "B2"),
    "past_perf_prog":  ("Past perfect progressive", "Tense & aspect", "TA.PASTPFPRG.AFF", "B2"),
    "future_will":     ("Future (will)", "Tense & aspect", "TA.FUT.AFF", "A2"),
    # --- Modality -----------------------------------------------------------
    "future_going_to": ("Future (be going to)", "Modality", "MD.be_going_to.AFF", "A2"),
    "modal_can":       ("Modal: can", "Modality", "MD.can.AFF", "A1"),
    "modal_could":     ("Modal: could", "Modality", "MD.could.AFF", "B1"),
    "modal_may":       ("Modal: may", "Modality", "MD.may.AFF", "B1"),
    "modal_might":     ("Modal: might", "Modality", "MD.might.AFF", "B1"),
    "modal_must":      ("Modal: must", "Modality", "MD.must.AFF", "B1"),
    "modal_shall":     ("Modal: shall", "Modality", "MD.shall.AFF", "A2"),
    "modal_should":    ("Modal: should", "Modality", "MD.should.AFF", "A2"),
    "modal_would":     ("Modal: would", "Modality", "MD.would.AFF", "A2"),
    "modal_perfect":   ("Modal + perfect (e.g. would have done)", "Modality", "MD.MD_PF.AFF", "B2"),
    "modal_progressive": ("Modal + progressive (e.g. must be doing)", "Modality", "MD.MD_PRG.AFF", "B2"),
    "have_to":         ("have to (obligation)", "Modality", "MD.have_to.AFF", "A2"),
    "used_to":         ("used to (past habit)", "Modality", "MD.used_to.AFF", "B1"),
    "be_able_to":      ("be able to (ability)", "Modality", "MD.be_able_to.AFF", "B1"),
    "ought_to":        ("ought to", "Modality", "MD.ought_to.AFF", "B1"),
    "had_better":      ("had better", "Modality", "MD.had_better.AFF", "B2"),
    # --- Voice --------------------------------------------------------------
    "passive_present": ("Passive (present)", "Voice", "PASS.PRESENT", "A1"),
    "passive_past":    ("Passive (past)", "Voice", "PASS.PAST.AFF", "A2"),
    "passive_perfect": ("Passive (perfect)", "Voice", "PASS.PRSPF.AFF", "B2"),
    "passive_progressive": ("Passive (progressive)", "Voice", "PASS.PRSPRG.AFF", "B2"),
    "passive_modal":   ("Passive (with modal)", "Voice", "PASS.MD.AFF", "B1"),
    "get_passive":     ("get-passive", "Voice", "PASS.get_VN", "B1"),
    # --- Non-finite ---------------------------------------------------------
    "to_inf":          ("to-infinitive (to do)", "Non-finite", "TO.to_do", "A1"),
    "not_to_inf":      ("negative to-infinitive (not to do)", "Non-finite", "TO.not_to_do", "B1"),
    "to_be_done":      ("passive to-infinitive (to be done)", "Non-finite", "TO.to_be_done", "B2"),
    "to_have_done":    ("perfect to-infinitive (to have done)", "Non-finite", "TO.to_have_done", "C1"),
    "ving":            ("-ing form (gerund/participle)", "Non-finite", "VG", "A1"),
    "having_pp":       ("having + past participle", "Non-finite", "VG.having_VN", "B2"),
    "being_pp":        ("being + past participle", "Non-finite", "VG.being_VN", "B2"),
    # --- Comparison ---------------------------------------------------------
    "comp_er":         ("Comparative (-er)", "Comparison", "COMP.JJR.RBR.er", "A1"),
    "comp_more":       ("Comparative (more + adj/adv)", "Comparison", "COMP.JJR.RBR.more", "A2"),
    "superl_est":      ("Superlative (-est)", "Comparison", "COMP.JJS.RBS.est", "A1"),
    "superl_most":     ("Superlative (most + adj/adv)", "Comparison", "COMP.JJS.RBS.most", "A2"),
    "as_as":           ("Comparison of equality (as ... as)", "Comparison", "COMP.EQ.as_as", "B2"),
    # --- Relative clauses ---------------------------------------------------
    "rel_who":         ("Relative clause: who", "Relative clause", "PREL.who", "A1"),
    "rel_that":        ("Relative clause: that", "Relative clause", "PREL.that", "A1"),
    "rel_which":       ("Relative clause: which", "Relative clause", "PREL.which", "B2"),
    # The CEFR-J PREL family has no 'whom'/'whose' code, so these use a documented
    # fallback rather than borrowing the interrogative INT.whom (a different item).
    "rel_whom":        ("Relative clause: whom", "Relative clause", "", "B2"),
    "rel_whose":       ("Relative clause: whose", "Relative clause", "", "B1"),
    "rel_nonrestrictive": ("Non-restrictive relative clause", "Relative clause", "PREL.NR", "B1"),
    # --- Subordination ------------------------------------------------------
    "that_clause":     ("that-clause complement", "Subordination", "CL.that.OBJ", "A2"),
    "wh_clause":       ("Embedded wh- / question clause", "Subordination", "CL.WH.OBJ", "B1"),
    # Generic adverbial clause: no single CEFR-J code fits every subordinator, so
    # the base uses a documented fallback; 'when'/'as' override it with their real
    # CEFR-J codes via _SUBORDINATOR_CODE.
    "adv_clause":      ("Adverbial (subordinate) clause", "Subordination", "", "A2"),
    # --- Questions ----------------------------------------------------------
    "wh_question":     ("Wh- question", "Questions", "INT.what", "A1"),
    "yesno_question":  ("Yes/no question (inversion)", "Questions", "TA.PRESENT.be.INT.AFF", "A1"),
    "tag_question":    ("Tag question", "Questions", "TAG.AFF", "B1"),
    # --- Existential --------------------------------------------------------
    "there_be":        ("Existential there + be", "Existential", "EX.there.AFF", "A1"),
    # --- Imperative & mood --------------------------------------------------
    "imperative":      ("Imperative", "Imperative & mood", "IMP.V.AFF", "A1"),
    "neg_imperative":  ("Negative imperative", "Imperative & mood", "IMP.V.NEG", "B1"),
    "lets":            ("let's ...", "Imperative & mood", "IMP.let's_V.AFF", "A1"),
    # --- Conditionals -------------------------------------------------------
    "cond_first":      ("First conditional", "Conditionals", "CL.if", "A2"),
    "cond_second":     ("Second conditional", "Conditionals", "SUBJ.PAST.AFF", "B1"),
    "cond_third":      ("Third conditional", "Conditionals", "SUBJ.PASTPF.AFF", "B1"),
    "wish_clause":     ("wish + past (unreal)", "Conditionals", "SUBJ.wish_PAST", "B2"),
    # --- Causative ----------------------------------------------------------
    "caus_make":       ("Causative (make/let/have + inf)", "Causative", "CAUS.have.let.make", "A2"),
    "caus_have_pp":    ("Causative (have/get + past participle)", "Causative", "CAUS.have.get_NP_VN", "B2"),
    "caus_ask_tell":   ("ask/tell + object + to-infinitive", "Causative", "CAUS.ask.tell_NP_to_do", "B1"),
    # --- Inversion ----------------------------------------------------------
    "inversion_neg":   ("Negative-adverbial inversion", "Inversion", "INV.never.etc", "C1"),
    "subjunctive_mandative": ("Mandative subjunctive (suggest that he go)", "Inversion", "SUBJ.PRS.AFF", "C1"),
}


# Which CEFR-J code supplies each core modal's level.
_MODAL_ID = {
    "can": "modal_can", "could": "modal_could", "may": "modal_may",
    "might": "modal_might", "must": "modal_must", "shall": "modal_shall",
    "should": "modal_should", "would": "modal_would",
}
_MODAL_LEMMAS = set(_MODAL_ID) | {"will"}
_WH_WORDS = {"what", "when", "where", "why", "who", "whom", "which", "whose", "how"}
_WH_QUESTION_CODE = {
    "what": "INT.what", "when": "INT.when", "where": "INT.where", "why": "INT.why",
    "who": "INT.who", "whom": "INT.whom", "which": "INT.which", "whose": "INT.whose",
    "how": "INT.how",
}
# Subordinating conjunctions that introduce an adverbial clause. 'if'/'unless' are
# intentionally excluded: conditional clauses are reported by _conditionals so they
# aren't also counted as generic adverbial clauses.
_SUBORDINATORS = frozenset({
    "when", "as", "because", "although", "though", "while", "since", "until",
    "before", "after", "whereas", "whenever", "wherever",
})
# Only subordinators with a genuinely corresponding CEFR-J code override the
# generic adv_clause level; the rest fall back to the adv_clause base level rather
# than borrowing an unrelated construction's code.
_SUBORDINATOR_CODE = {
    "when": "CL.when",
    "as": "CL.as",
}


# ---------------------------------------------------------------------------
# Detection — rule-based, over the spaCy parse
# ---------------------------------------------------------------------------

# A detection: (construction_id, example_span_text). Sentence text is attached
# by profile().

_PREDICATE_DEPS = {"ROOT", "ccomp", "xcomp", "advcl", "relcl", "conj",
                   "acl", "pcomp", "csubj", "csubjpass", "parataxis"}
_FINITE_TAGS = {"VBZ", "VBP", "VBD", "MD"}


def _auxes(tok):
    """Auxiliary children of *tok*, in text order."""
    return sorted((c for c in tok.children if c.dep_ in ("aux", "auxpass")),
                  key=lambda t: t.i)


def _group_span(tok, extra=()):
    """Minimal span covering a verb group: its auxiliaries, negation and head."""
    idxs = [tok.i] + [a.i for a in _auxes(tok)]
    idxs += [c.i for c in tok.children if c.dep_ == "neg"]
    idxs += [t.i for t in extra]
    lo, hi = min(idxs), max(idxs)
    return tok.doc[lo:hi + 1]


def _is_finite_group(tok):
    """True if the verb group headed by *tok* is finite (a real clause predicate)."""
    if tok.tag_ in _FINITE_TAGS:
        return True
    return any(a.tag_ in _FINITE_TAGS for a in _auxes(tok))


def _analyze_verb_group(V):
    """Classify one finite verb group into a single tense/aspect/voice/modal id.

    Returns (construction_id, span) or None.
    """
    auxes = _auxes(V)
    aux_lemmas = [a.lemma_.lower() for a in auxes]
    modal = next((a for a in auxes if a.tag_ == "MD"), None)
    modal_lemma = modal.lemma_.lower() if modal else None
    has_have = "have" in aux_lemmas
    has_be = "be" in aux_lemmas
    passive = any(c.dep_ == "auxpass" for c in V.children) and V.tag_ == "VBN"
    progressive = V.tag_ == "VBG" and has_be

    finite = auxes[0] if auxes else V
    is_past = ("Past" in finite.morph.get("Tense")) or finite.tag_ == "VBD"
    span = _group_span(V)

    # Existential 'there is/are/was' is reported by _existential, not as a
    # plain present/past simple — skip it here to avoid double-counting.
    if V.lemma_.lower() == "be" and any(c.dep_ == "expl" for c in V.children):
        return None

    # --- passive voice (takes precedence; one label per group) --------------
    if passive:
        if any(c.dep_ == "auxpass" and c.lemma_.lower() == "get" for c in V.children):
            return "get_passive", span
        if modal:
            return "passive_modal", span
        if has_have:
            return "passive_perfect", span
        if any(a.lemma_.lower() == "be" and a.tag_ == "VBG" for a in auxes):
            return "passive_progressive", span
        return ("passive_past", span) if is_past else ("passive_present", span)

    # --- modal groups -------------------------------------------------------
    if modal_lemma and modal_lemma != "will":
        if has_have:
            return "modal_perfect", span
        if progressive:
            return "modal_progressive", span
        # Only the eight core modals map to a construction. spaCy also tags
        # ought/need/dare as MD; return None for those rather than mislabelling
        # them "Modal: can" (they're handled elsewhere or intentionally skipped).
        cid = _MODAL_ID.get(modal_lemma)
        return (cid, span) if cid else None
    if modal_lemma == "will":
        # will + have + done / will + be + doing collapse to future here.
        return "future_will", span

    # --- perfect / progressive combinations ---------------------------------
    if has_have and progressive:
        return ("past_perf_prog", span) if is_past else ("pres_perf_prog", span)
    if has_have and V.tag_ == "VBN":
        return ("past_perf", span) if is_past else ("pres_perf", span)
    if progressive:
        return ("past_prog", span) if is_past else ("pres_prog", span)

    # --- simple tenses ------------------------------------------------------
    is_be_main = V.lemma_.lower() == "be" and not auxes
    if is_be_main:
        return ("past_simple_be", span) if V.tag_ == "VBD" else ("pres_simple_be", span)
    if V.pos_ in ("VERB", "AUX"):
        if V.tag_ == "VBD":
            return "past_simple", span
        if V.tag_ in ("VBZ", "VBP"):
            return "pres_simple", span
    return None


def _multiword_verbs(sent, covered):
    """Detect fixed modal/future phrases; record their head verb in *covered*."""
    found = []
    toks = list(sent)
    for i, t in enumerate(toks):
        lemma = t.lemma_.lower()
        low = t.lower_

        # be going to + VERB
        if lemma == "go" and t.tag_ == "VBG":
            nxt = t.nbor(1) if t.i + 1 < len(t.doc) else None
            if nxt is not None and nxt.lower_ == "to":
                # 'to' is usually the aux of the following bare-infinitive verb.
                target = next((c for c in t.doc[nxt.i:min(nxt.i + 4, len(t.doc))]
                               if c.tag_ == "VB"), None)
                if target is not None:
                    covered.add(t.i)
                    covered.add(target.i)
                    found.append(("future_going_to", t.doc[t.i:target.i + 1]))
                    continue

        # have/has/had to + VERB
        if lemma == "have" and t.i + 1 < len(t.doc) and t.nbor(1).lower_ == "to":
            target = next((c for c in t.doc[t.i:min(t.i + 4, len(t.doc))]
                           if c.tag_ == "VB"), None)
            if target is not None:
                covered.add(t.i)
                covered.add(target.i)
                found.append(("have_to", t.doc[t.i:target.i + 1]))
                continue

        # used to + VERB
        if low == "used" and t.i + 1 < len(t.doc) and t.nbor(1).lower_ == "to":
            target = next((c for c in t.doc[t.i:min(t.i + 4, len(t.doc))]
                           if c.tag_ == "VB"), None)
            if target is not None:
                covered.add(t.i)
                covered.add(target.i)
                found.append(("used_to", t.doc[t.i:target.i + 1]))
                continue

        # be able to + VERB
        if low == "able" and t.i + 1 < len(t.doc) and t.nbor(1).lower_ == "to":
            found.append(("be_able_to", t.doc[max(sent.start, t.i - 1):min(t.i + 3, len(t.doc))]))
            target = next((c for c in t.doc[t.i:min(t.i + 4, len(t.doc))]
                           if c.tag_ == "VB"), None)
            if target is not None:
                covered.add(target.i)
            continue

        # ought to + VERB
        if low == "ought" and t.i + 1 < len(t.doc) and t.nbor(1).lower_ == "to":
            found.append(("ought_to", t.doc[t.i:min(t.i + 3, len(t.doc))]))
            target = next((c for c in t.doc[t.i:min(t.i + 4, len(t.doc))]
                           if c.tag_ == "VB"), None)
            if target is not None:
                covered.add(target.i)
            continue

        # had better + VERB
        if low == "better" and t.i > 0 and t.nbor(-1).lower_ in ("had", "'d"):
            found.append(("had_better", t.doc[t.i - 1:min(t.i + 2, len(t.doc))]))
            continue

    return found


def _nonfinite(sent, covered=frozenset()):
    """to-infinitives, gerunds/participles, having/being + PP.

    *covered* holds token indices whose verb group is already reported by a
    fixed phrase (be going to / have to / used to / be able to), so their
    ``to VERB`` isn't also double-counted as a plain to-infinitive.
    """
    found = []
    for t in sent:
        # to-infinitive: 'to' (TO) governing a bare verb group.
        if t.tag_ == "TO" and t.head.pos_ in ("VERB", "AUX") and t.head.i not in covered:
            H = t.head
            haux = [a.lemma_.lower() for a in _auxes(H)]
            span = t.doc[t.i:H.i + 1] if H.i >= t.i else t.doc[H.i:t.i + 1]
            if H.tag_ == "VBN" and "be" in haux:
                found.append(("to_be_done", span))
            elif H.tag_ == "VBN" and "have" in haux:
                found.append(("to_have_done", span))
            elif H.tag_ == "VB":
                prev = H.doc[t.i - 1] if t.i > 0 else None
                if prev is not None and prev.lower_ in ("not", "never"):
                    found.append(("not_to_inf", H.doc[t.i - 1:H.i + 1]))
                else:
                    found.append(("to_inf", span))
        # having / being + past participle. spaCy usually parses the participle
        # (VBN) as the head with 'having'/'being' as its VBG auxiliary, so detect
        # from the participle side; also handle the reverse (VBN as a child).
        # Match on the surface form: spaCy lemmatizes 'being' -> 'be' but keeps
        # 'having' -> 'having', so the word form is the reliable key.
        if t.tag_ == "VBN":
            aux = next((a for a in _auxes(t)
                        if a.tag_ == "VBG" and a.lower_ in ("having", "being")), None)
            if aux is not None:
                cid = "having_pp" if aux.lower_ == "having" else "being_pp"
                lo, hi = min(aux.i, t.i), max(aux.i, t.i)
                found.append((cid, t.doc[lo:hi + 1]))
        elif t.tag_ == "VBG" and t.lower_ in ("having", "being"):
            pp = next((c for c in t.children if c.tag_ == "VBN"), None)
            if pp is not None:
                cid = "having_pp" if t.lower_ == "having" else "being_pp"
                found.append((cid, t.doc[t.i:pp.i + 1]))
        # bare gerund / participle used nominally or in a participial phrase
        if t.tag_ == "VBG" and t.lemma_.lower() not in ("be", "have") \
                and not any(a.lemma_ == "be" for a in _auxes(t)) \
                and t.dep_ in ("nsubj", "nsubjpass", "dobj", "pobj", "csubj",
                               "acl", "advcl", "pcomp", "conj", "ROOT", "xcomp"):
            found.append(("ving", sent.doc[t.i:t.i + 1]))
    return found


def _comparatives(sent):
    found = []
    for t in sent:
        if t.tag_ in ("JJR", "RBR"):
            if t.lower_ in ("more", "less"):
                found.append(("comp_more", sent.doc[t.i:t.i + 1]))
            else:
                found.append(("comp_er", sent.doc[t.i:t.i + 1]))
        elif t.tag_ in ("JJS", "RBS"):
            if t.lower_ in ("most", "least"):
                found.append(("superl_most", sent.doc[t.i:t.i + 1]))
            else:
                found.append(("superl_est", sent.doc[t.i:t.i + 1]))
    # as ... as
    as_positions = [t.i for t in sent if t.lower_ == "as"]
    if len(as_positions) >= 2:
        found.append(("as_as", sent.doc[as_positions[0]:as_positions[1] + 1]))
    return found


def _relatives(sent):
    """Relative clauses, keyed by relativizer, with non-restrictive detection."""
    found = []
    for t in sent:
        if t.dep_ != "relcl":
            continue
        # Find the relativizer inside the clause subtree.
        rel = None
        for d in t.subtree:
            if d.tag_ in ("WDT", "WP", "WP$") or (d.lower_ == "that" and d.i < t.i):
                rel = d
                break
        head_noun = t.head
        # Non-restrictive: a comma sits right before the relative clause.
        start = rel.i if rel is not None else t.i
        prev = sent.doc[start - 1] if start > 0 else None
        nonrestrictive = prev is not None and prev.text == ","
        span = sent.doc[head_noun.i:t.i + 1] if t.i >= head_noun.i else sent.doc[t.i:head_noun.i + 1]
        if nonrestrictive:
            found.append(("rel_nonrestrictive", span))
            continue
        word = rel.lower_ if rel is not None else "that"
        cid = {"who": "rel_who", "which": "rel_which", "whom": "rel_whom",
               "whose": "rel_whose", "that": "rel_that"}.get(word, "rel_that")
        found.append((cid, span))
    return found


def _clauses(sent):
    """that-complement, embedded wh-clause, adverbial subordinate clause."""
    found = []
    for t in sent:
        # that-clause complement: verb with a ccomp introduced by 'that'
        if t.dep_ == "ccomp":
            mark = next((c for c in t.children if c.dep_ == "mark" and c.lower_ == "that"), None)
            if mark is not None:
                found.append(("that_clause", sent.doc[mark.i:t.i + 1]))
        # embedded wh-clause (indirect question): ccomp/advcl headed under a wh-word.
        # Skip the sentence-initial wh-word, which _questions already reports.
        if t.dep_ in ("ccomp", "advcl", "acl", "dobj", "pcomp"):
            wh = next((c for c in t.children if c.tag_ in ("WDT", "WP", "WP$", "WRB")
                       and c.lower_ in _WH_WORDS), None)
            if wh is not None and wh.i != sent.start:
                found.append(("wh_clause", sent.doc[wh.i:t.i + 1]))
        # adverbial clause: advcl with a subordinating conjunction marker. Only
        # 'when'/'as' carry a real CEFR-J code override; others fall back to the
        # adv_clause base level (code_override None).
        if t.dep_ == "advcl":
            mark = next((c for c in t.children if c.dep_ == "mark"), None)
            if mark is not None and mark.lower_ in _SUBORDINATORS:
                found.append(("adv_clause", sent.doc[mark.i:t.i + 1],
                              _SUBORDINATOR_CODE.get(mark.lower_)))
    return found


def _questions(sent):
    found = []
    toks = [t for t in sent if not t.is_space]
    if not toks:
        return found
    # Use the space-filtered tokens: spaCy can emit a trailing SPACE token when a
    # sentence ends with a newline, which would hide the question mark.
    is_question = toks[-1].text == "?"
    first = toks[0]
    # Wh-question
    if is_question and first.lower_ in _WH_WORDS:
        found.append(("wh_question", sent.doc[first.i:first.i + 1],
                      _WH_QUESTION_CODE.get(first.lower_, "INT.what")))
    elif is_question and first.tag_ in ("MD", "VBZ", "VBP", "VBD") \
            and first.dep_ in ("aux", "auxpass", "ROOT"):
        found.append(("yesno_question", sent.doc[first.i:first.i + 1]))
    # Tag question: ..., aux (n't) pron ?
    if is_question and len(toks) >= 4:
        tail = toks[-4:]
        if tail[0].text == "," and tail[1].tag_ in ("MD", "VBZ", "VBP", "VBD") \
                and tail[2].pos_ == "PRON":
            found.append(("tag_question", sent.doc[tail[0].i:tail[-1].i + 1]))
        elif toks[-2].pos_ == "PRON" and any(x.tag_ in ("MD", "VBZ", "VBP", "VBD")
                                             for x in toks[-4:-1]) \
                and any(x.text == "," for x in toks[-5:-2]):
            found.append(("tag_question", sent.doc[toks[-4].i:toks[-1].i + 1]))
    return found


def _existential(sent):
    found = []
    for t in sent:
        if t.dep_ == "expl" and t.lower_ == "there":
            found.append(("there_be", sent.doc[t.i:min(t.head.i + 1, len(sent.doc))]
                          if t.head.i >= t.i else sent.doc[t.i:t.i + 2]))
    return found


def _imperative(sent):
    found = []
    toks = [t for t in sent if not t.is_space and not t.is_punct]
    if not toks:
        return found
    root = next((t for t in sent if t.dep_ == "ROOT"), None)
    if root is None:
        return found
    has_subj = any(c.dep_ in ("nsubj", "nsubjpass", "expl") for c in root.children)
    first = toks[0]
    # let's
    if first.lower_ in ("let", "let's", "lets") and (first.lower_ != "let"
            or (len(toks) > 1 and toks[1].lower_ in ("us", "'s"))):
        found.append(("lets", sent.doc[first.i:min(first.i + 2, len(sent.doc))]))
        return found
    # negative imperative: Don't / Never + base verb, no subject
    if first.lower_ in ("do", "don't", "never") and root.tag_ == "VB" and not has_subj:
        found.append(("neg_imperative", sent.doc[first.i:root.i + 1]))
        return found
    # affirmative imperative: ROOT is a base-form verb, no subject, sentence-initial
    if root.tag_ == "VB" and not has_subj and root.i <= first.i + 1 \
            and root.lemma_.lower() not in ("let",):
        found.append(("imperative", sent.doc[root.i:root.i + 1]))
    return found


def _conditionals(sent):
    found = []
    if_tok = next((t for t in sent if t.lemma_.lower() == "if" and t.dep_ == "mark"), None)
    wish_tok = next((t for t in sent if t.lemma_.lower() == "wish"), None)
    if wish_tok is not None:
        # wish + past clause
        comp = next((c for c in wish_tok.children if c.dep_ == "ccomp"), None)
        if comp is not None:
            found.append(("wish_clause", sent.doc[wish_tok.i:comp.i + 1]
                          if comp.i >= wish_tok.i else sent.doc[comp.i:wish_tok.i + 1]))
    if if_tok is not None:
        if_head = if_tok.head  # verb of the if-clause
        if_auxes = [a.lemma_.lower() for a in _auxes(if_head)]
        if_past = ("Past" in if_head.morph.get("Tense")) or if_head.tag_ == "VBD" \
            or "had" in [a.lower_ for a in _auxes(if_head)]
        main = if_head.head if if_head.dep_ == "advcl" else None
        main_modal = None
        main_have = False
        if main is not None:
            for a in _auxes(main):
                if a.tag_ == "MD":
                    main_modal = a.lemma_.lower()
                if a.lemma_.lower() == "have":
                    main_have = True
        # Third: if + had + PP ... would/could have PP
        if "have" in if_auxes and if_head.tag_ == "VBN" and main_have:
            found.append(("cond_third", sent.doc[if_tok.i:if_head.i + 1]))
        elif if_past and main_modal in ("would", "could", "might"):
            found.append(("cond_second", sent.doc[if_tok.i:if_head.i + 1]))
        else:
            found.append(("cond_first", sent.doc[if_tok.i:if_head.i + 1]))
    return found


def _causatives(sent):
    found = []
    for t in sent:
        lemma = t.lemma_.lower()
        # make/let/have + NP + bare infinitive. The causee shows up as the
        # embedded verb's own subject ("made [me] laugh"), so require that.
        if lemma in ("make", "let", "have"):
            inf = next((c for c in t.children if c.dep_ in ("ccomp", "xcomp")
                        and c.tag_ == "VB"), None)
            if inf is not None and any(g.dep_ == "nsubj" for g in inf.children):
                found.append(("caus_make", sent.doc[t.i:inf.i + 1]))
        # have/get + NP + past participle
        if lemma in ("have", "get"):
            pp = next((c for c in t.children if c.dep_ in ("ccomp", "xcomp", "oprd")
                       and c.tag_ == "VBN"), None)
            if pp is not None:
                found.append(("caus_have_pp", sent.doc[t.i:pp.i + 1]))
        # ask/tell + object + to-infinitive (the object is a genuine dobj, which
        # separates "told [him] to wait" from plain "want to learn").
        if lemma in ("ask", "tell", "want", "advise", "order", "persuade"):
            xcomp = next((c for c in t.children if c.dep_ == "xcomp"
                          and any(a.tag_ == "TO" for a in c.children)), None)
            obj = next((c for c in t.children if c.dep_ == "dobj"), None)
            if xcomp is not None and obj is not None:
                found.append(("caus_ask_tell", sent.doc[t.i:xcomp.i + 1]))
    return found


_INVERSION_TRIGGERS = {"never", "hardly", "seldom", "rarely", "little",
                       "scarcely", "nor", "neither", "barely"}


def _inversion(sent):
    found = []
    toks = [t for t in sent if not t.is_space]
    if not toks:
        return found
    first = toks[0]
    if first.lower_ in _INVERSION_TRIGGERS and len(toks) > 2 \
            and toks[1].tag_ in ("MD", "VB", "VBZ", "VBP", "VBD", "VBN") \
            and toks[1].dep_ in ("aux", "auxpass"):
        found.append(("inversion_neg", sent.doc[first.i:toks[2].i + 1]))
    # "No sooner ... than", "Not until ..."
    if first.lower_ == "no" and len(toks) > 1 and toks[1].lower_ == "sooner":
        found.append(("inversion_neg", sent.doc[first.i:toks[1].i + 1]))
    return found


_MANDATIVE_VERBS = {"suggest", "demand", "insist", "recommend", "require",
                    "propose", "order", "request", "ask", "advise"}


def _subjunctive(sent):
    found = []
    for t in sent:
        if t.lemma_.lower() in _MANDATIVE_VERBS:
            comp = next((c for c in t.children if c.dep_ == "ccomp"), None)
            if comp is None:
                continue
            has_that = any(c.dep_ == "mark" and c.lower_ == "that" for c in comp.children)
            if not has_that:
                continue
            # Base-form verb as the complement predicate. spaCy usually tags the
            # mandative base form VBP, so also accept an uninflected verb under a
            # 3rd-person-singular subject ("he leave", not "he leaves").
            subj = next((c for c in comp.children if c.dep_ == "nsubj"), None)
            uninflected = comp.text.lower() == comp.lemma_.lower()
            third_sing = subj is not None and "Sing" in subj.morph.get("Number") \
                and "3" in subj.morph.get("Person")
            if comp.tag_ == "VB" or (comp.tag_ == "VBP" and uninflected and third_sing):
                found.append(("subjunctive_mandative",
                              sent.doc[t.i:comp.i + 1] if comp.i >= t.i
                              else sent.doc[comp.i:t.i + 1]))
    return found


def analyze_sentence(sent):
    """Return a list of (construction_id, span_text) for one sentence."""
    raw = []
    covered = set()
    raw += _multiword_verbs(sent, covered)
    for tok in sent:
        if tok.i in covered:
            continue
        if tok.pos_ in ("VERB", "AUX") and tok.dep_ in _PREDICATE_DEPS \
                and _is_finite_group(tok):
            r = _analyze_verb_group(tok)
            if r is not None:
                raw.append(r)
    raw += _nonfinite(sent, covered)
    for fn in (_comparatives, _relatives, _clauses, _questions,
               _existential, _imperative, _conditionals, _causatives,
               _inversion, _subjunctive):
        raw += fn(sent)

    # Normalise: each item is (cid, span[, code_override]).
    out = []
    for item in raw:
        cid = item[0]
        span = item[1]
        code_override = item[2] if len(item) > 2 else None
        span_text = span.text if hasattr(span, "text") else str(span)
        out.append((cid, span_text.strip(), code_override))
    return out


# ---------------------------------------------------------------------------
# Profiling — aggregate detections into a level-banded result
# ---------------------------------------------------------------------------

def constructions_at_level(cefrj_levels, level):
    """Every registered construction whose band is exactly *level*.

    The canonical set for the grammar gap report: the target-level
    constructions a text should be introducing. Levels resolve like the
    profiler's (``cefrj_levels.get(code, fallback)``); entries are sorted by
    category then name.
    """
    out = []
    for cid, (name, category, code, fallback) in _CONSTRUCTIONS.items():
        if cefrj_levels.get(code, fallback) == level:
            out.append({"name": name, "category": category})
    out.sort(key=lambda d: (d["category"], d["name"]))
    return out


def profile(text, nlp, cefrj_levels):
    """Analyse *text* and return (results_by_level, meta).

    results_by_level: {level: {cid: {"name","category","count","examples"}}}
    meta: dict with sentenceCount, tokenCount, constructionCount, estimatedLevel.
    """
    doc = nlp(text)
    sentences = [s for s in doc.sents if s.text.strip()]
    token_count = sum(1 for t in doc if not (t.is_space or t.is_punct))

    # cid -> {name, category, level, count, examples:[(span, sentence)]}
    agg = {}
    for sent in sentences:
        sent_text = sent.text.strip()
        for cid, span_text, code_override in analyze_sentence(sent):
            spec = _CONSTRUCTIONS.get(cid)
            if spec is None:
                continue
            name, category, code, fallback = spec
            code = code_override or code
            level = cefrj_levels.get(code, fallback)
            entry = agg.get(cid)
            if entry is None:
                entry = {"name": name, "category": category, "level": level,
                         "count": 0, "examples": []}
                agg[cid] = entry
            entry["count"] += 1
            if len(entry["examples"]) < 3:
                entry["examples"].append({"span": span_text, "sentence": sent_text})

    # Band by level.
    results = {lvl: {} for lvl in _CEFR_ORDER}
    for cid, entry in agg.items():
        results[entry["level"]][cid] = entry

    construction_count = sum(e["count"] for e in agg.values())

    # Estimated level: `typical` = busiest band (ties -> lower); `reaches` =
    # highest band with any construction.
    band_counts = {lvl: sum(e["count"] for e in results[lvl].values())
                   for lvl in _CEFR_ORDER}
    if construction_count == 0:
        typical = reaches = "—"
    else:
        typical = max(_CEFR_ORDER, key=lambda lvl: (band_counts[lvl], -_LEVEL_INDEX[lvl]))
        reaches = next((lvl for lvl in reversed(_CEFR_ORDER) if band_counts[lvl] > 0), typical)

    meta = {
        "sentenceCount": len(sentences),
        "tokenCount": token_count,
        "constructionCount": construction_count,
        "estimatedLevel": {"typical": typical, "reaches": reaches},
        "bandCounts": band_counts,
    }
    return results, meta


def results_to_json(results, meta):
    """Shape the profile into the JSON payload described in the module docstring."""
    out_results = {}
    for lvl in _CEFR_ORDER:
        entries = results[lvl]
        constructions = [
            {
                "id": cid,
                "name": e["name"],
                "category": e["category"],
                "count": e["count"],
                "examples": e["examples"],
            }
            for cid, e in sorted(entries.items(),
                                 key=lambda kv: (-kv[1]["count"], kv[1]["name"]))
        ]
        out_results[lvl] = {
            "constructionCount": sum(e["count"] for e in entries.values()),
            "distinct": len(entries),
            "constructions": constructions,
        }
    return {
        "sentenceCount": meta["sentenceCount"],
        "tokenCount": meta["tokenCount"],
        "constructionCount": meta["constructionCount"],
        "estimatedLevel": meta["estimatedLevel"],
        "results": out_results,
    }


# ---------------------------------------------------------------------------
# Pretty terminal rendering (shares the vocab profiler's CEFR palette)
# ---------------------------------------------------------------------------

_LEVEL_RGB = {
    "A1": (0, 153, 204),
    "A2": (0, 187, 0),
    "B1": (255, 153, 0),
    "B2": (179, 0, 0),
    "C1": (215, 51, 255),
    "C2": (219, 112, 147),
}
_DIM_RGB = (136, 136, 136)


def _use_colour(stream):
    return stream.isatty() and os.environ.get("NO_COLOR") is None


def _paint(rgb, text, enabled):
    if not enabled:
        return text
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


def _bold(text, enabled):
    return f"\x1b[1m{text}\x1b[0m" if enabled else text


def _distribution_bar(band_counts, total, width, colour):
    segments, legend = [], []
    for lvl in _CEFR_ORDER:
        c = band_counts.get(lvl, 0)
        if c == 0:
            continue
        cells = round(c / total * width) if total else 0
        if cells:
            segments.append(_paint(_LEVEL_RGB[lvl], "█" * cells, colour))
        pct = round(c / total * 100) if total else 0
        legend.append(_paint(_LEVEL_RGB[lvl], "■", colour) + f" {lvl} {pct}%")
    return "".join(segments), "   ".join(legend)


def render_pretty(source_label, results, meta, stream=None):
    stream = stream or sys.stdout
    colour = _use_colour(stream)
    try:
        import shutil
        width = min(shutil.get_terminal_size((80, 20)).columns, 100)
    except Exception:
        width = 80

    out = []
    out.append(_bold("Grammar Profile", colour))
    if source_label:
        out.append(_paint(_DIM_RGB, f"Source: {source_label}", colour))
    out.append("")

    total = meta["constructionCount"]
    typical = meta["estimatedLevel"]["typical"]
    reaches = meta["estimatedLevel"]["reaches"]
    out.append(f"{_bold('Sentences:', colour)} {meta['sentenceCount']}   "
               f"{_bold('Words:', colour)} {meta['tokenCount']}   "
               f"{_bold('Constructions:', colour)} {total}")

    if total == 0:
        out.append("")
        out.append(_paint(_DIM_RGB, "No grammatical constructions were detected.", colour))
        stream.write("\n".join(out) + "\n")
        return

    out.append(
        f"{_bold('Typical:', colour)} {_paint(_LEVEL_RGB.get(typical, _DIM_RGB), typical, colour)}"
        f"   {_bold('Reaches:', colour)} {_paint(_LEVEL_RGB.get(reaches, _DIM_RGB), reaches, colour)}"
    )
    out.append("")

    bar, legend = _distribution_bar(meta["bandCounts"], total, min(width, 64), colour)
    out.append(bar)
    out.append(legend)
    out.append("")

    for lvl in _CEFR_ORDER:
        entries = results[lvl]
        if not entries:
            continue
        rgb = _LEVEL_RGB[lvl]
        band_total = sum(e["count"] for e in entries.values())
        out.append(_paint(rgb, _bold(lvl, colour), colour)
                   + _paint(_DIM_RGB, f"  {len(entries)} constructions · {band_total} uses", colour))
        for cid, e in sorted(entries.items(), key=lambda kv: (-kv[1]["count"], kv[1]["name"])):
            label = f"{e['name']}" + (f" ×{e['count']}" if e["count"] > 1 else "")
            out.append("  " + _paint(rgb, "•", colour) + " " + label)
            if e["examples"]:
                ex = e["examples"][0]["span"]
                if ex:
                    out.append(_paint(_DIM_RGB, f"      “{ex}”", colour))
        out.append("")

    stream.write("\n".join(out) + "\n")


def resolve_format(explicit, is_tty):
    """Resolve --format: explicit value wins, else auto by TTY (pretty) vs pipe (json)."""
    if explicit in (None, "", "auto"):
        return "pretty" if is_tty else "json"
    value = explicit.strip().lower()
    if value == "json":
        return "json"
    if value in ("pretty", "text"):
        return "pretty"
    raise ValueError(f"Unknown format '{explicit}'. Valid formats: auto, json, pretty.")


def main(argv=None):
    _maybe_reexec_in_venv()
    parser = argparse.ArgumentParser(add_help=True, description="EFL-Tools grammar profiler")
    parser.add_argument("--format", default="auto")
    parser.add_argument("--text", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--grammar-profile", dest="grammar_profile", default=None)
    parser.add_argument("positional", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        out_format = resolve_format(args.format, sys.stdout.isatty())
    except ValueError as ex:
        sys.stderr.write(str(ex) + "\n")
        return 1

    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = args.grammar_profile or os.path.join(script_dir, "GrammarProfile")

    source_label = None
    text = args.text
    if text is None and args.file:
        try:
            text = extract_text(args.file)
            source_label = os.path.basename(args.file)
        except DocumentError as ex:
            sys.stderr.write(str(ex) + "\n")
            return 1
    if text is None and args.positional:
        text = args.positional[0]
    if text is None and not sys.stdin.isatty():
        text = sys.stdin.read()

    if text is None or text.strip() == "":
        sys.stderr.write(
            'Usage: grammar_profile.py [--format auto|json|pretty] '
            '[--text "..." | --file path{.txt|.md|.docx|.pdf} | < stdin]\n'
        )
        return 1

    try:
        cefrj_levels = load_cefrj_levels(base_dir)
        nlp = load_nlp()
    except EngineError as ex:
        sys.stderr.write(str(ex) + "\n")
        return 1

    # spaCy's parser caps input at nlp.max_length (default 1,000,000 chars) to
    # bound memory; beyond it, nlp(text) raises ValueError. Fail cleanly instead.
    if len(text) > nlp.max_length:
        sys.stderr.write(
            f"Input is too long for the parser ({len(text):,} characters; the "
            f"limit is {nlp.max_length:,}). Split it into smaller pieces (e.g. by "
            "chapter or section) and profile each separately.\n"
        )
        return 1

    results, meta = profile(text, nlp, cefrj_levels)

    if out_format == "pretty":
        render_pretty(source_label, results, meta)
    else:
        print(json.dumps(results_to_json(results, meta), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
