#!/usr/bin/env python3
"""VocabKitchen — an interactive terminal menu (TUI) over all the profilers.

A single front door to the four command-line tools:

    * Vocabulary profiler   (vocab_profile.py)   — dependency-free
    * Grammar profiler      (grammar_profile.py)  — needs spaCy
    * Text report           (text_report.py)      — needs spaCy
    * Class profile         (class_profile.py)     — needs spaCy

You pick a tool, fill in a short form (arrow keys to move, Enter to edit or
cycle a value), and choose Run. The TUI builds the command line for you, hands
control to the tool so its native colour output shows in full, then returns to
the menu.

It uses only the Python standard library — no third-party packages — so the TUI
itself never needs installing. When the terminal supports curses you get the
full-screen menu; otherwise it drops to a plain numbered-menu fallback that
works anywhere. The tools it launches still need their own setup for the grammar
side; the "Setup & diagnostics" screen checks that and can run the installer.

Run it with:  ./vocabkitchen      (or:  python3 tui.py)
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))

# --------------------------------------------------------------------------
# Locating a Python that can run the tools (venv-aware, mirrors the scripts).
# --------------------------------------------------------------------------


def engine_python():
    """Return the best interpreter for the tools: the project venv if present.

    Mirrors grammar_profile._find_engine_python so the TUI, the scripts and the
    installer all agree on which interpreter carries spaCy. Falls back to the
    interpreter running the TUI (fine for the dependency-free vocab profiler).
    """
    override = os.environ.get("GRAMMAR_PROFILE_PYTHON")
    candidates = [
        override,
        os.path.join(HERE, ".venv", "bin", "python"),
        os.path.join(HERE, "venv", "bin", "python"),
        os.path.join(HERE, ".venv", "Scripts", "python.exe"),  # Windows
        os.path.join(HERE, "venv", "Scripts", "python.exe"),
    ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            return os.path.abspath(cand)
    return sys.executable


CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

SAMPLE_DIR = os.path.join(HERE, "sample-readings")


def _default_source():
    """A sensible starting file so a first Run produces output immediately."""
    for name in ("academic-essay.txt", "news-report.txt", "starter.txt"):
        p = os.path.join(SAMPLE_DIR, name)
        if os.path.exists(p):
            return p
    return ""


# --------------------------------------------------------------------------
# Tool definitions. Each field becomes one row in the form and maps to argv.
#
# field kinds:
#   source  -> paired with a "mode" field; emits --file VALUE or --text VALUE
#   choice  -> cycle through choices; the sentinel "(default)"/"(none)" emits nothing
#   toggle  -> True emits the flag (store_true)
#   text    -> non-empty emits `flag VALUE`
#   extra   -> raw string, shlex-split and appended verbatim
# --------------------------------------------------------------------------


def _common_source_fields():
    """Return the File/Text input fields shared by the single-text tools."""
    return [
        {"key": "mode", "label": "Input", "kind": "choice",
         "choices": ["File", "Inline text"], "value": "File"},
        {"key": "source", "label": "File / text", "kind": "source",
         "value": _default_source()},
    ]


TOOLS = [
    {
        "id": "vocab",
        "name": "Vocabulary profiler",
        "script": "vocab_profile.py",
        "needs_engine": False,
        "blurb": "CEFR / academic vocabulary level of a text. No setup needed.",
        "fields": _common_source_fields() + [
            {"key": "type", "label": "Word list(s)", "kind": "choice", "flag": "--type",
             "choices": ["all", "cefr", "awl", "nawl", "cefr,awl"], "value": "all"},
            {"key": "format", "label": "Output", "kind": "choice", "flag": "--format",
             "choices": ["pretty", "json"], "value": "pretty"},
            {"key": "extra", "label": "Extra args", "kind": "extra", "value": ""},
        ],
    },
    {
        "id": "grammar",
        "name": "Grammar profiler",
        "script": "grammar_profile.py",
        "needs_engine": True,
        "blurb": "Which grammatical constructions a text uses, by CEFR level.",
        "fields": _common_source_fields() + [
            {"key": "format", "label": "Output", "kind": "choice", "flag": "--format",
             "choices": ["pretty", "json"], "value": "pretty"},
            {"key": "extra", "label": "Extra args", "kind": "extra", "value": ""},
        ],
    },
    {
        "id": "text_report",
        "name": "Text report (vocab + grammar)",
        "script": "text_report.py",
        "needs_engine": True,
        "blurb": "Combined difficulty report: is this one text right for my class?",
        "fields": _common_source_fields() + [
            {"key": "target", "label": "Target level", "kind": "choice", "flag": "--target-level",
             "choices": ["(none)"] + CEFR_LEVELS, "value": "(none)"},
            {"key": "grammar", "label": "Grammar side", "kind": "choice", "flag": "--no-grammar",
             "choices": ["on", "off"], "value": "on", "flag_when": "off"},
            {"key": "export", "label": "Export handout", "kind": "choice", "flag": "--export",
             "choices": ["(none)", "md", "csv", "flashcards"], "value": "(none)"},
            {"key": "suggest", "label": "Suggest simpler words", "kind": "toggle",
             "flag": "--suggest", "value": False},
            {"key": "gap", "label": "Grammar gap report", "kind": "toggle",
             "flag": "--gap-report", "value": False},
            {"key": "format", "label": "Output", "kind": "choice", "flag": "--format",
             "choices": ["pretty", "json"], "value": "pretty"},
            {"key": "extra", "label": "Extra args", "kind": "extra", "value": ""},
        ],
    },
    {
        "id": "class_profile",
        "name": "Class profile (folder of texts)",
        "script": "class_profile.py",
        "needs_engine": True,
        "blurb": "Rank & filter a whole folder of readings for a class level.",
        "fields": [
            {"key": "mode", "label": "Input", "kind": "choice",
             "choices": ["File / folder / glob"], "value": "File / folder / glob"},
            {"key": "source", "label": "Path or glob", "kind": "source",
             "value": SAMPLE_DIR},
            {"key": "target", "label": "Target level", "kind": "choice", "flag": "--target-level",
             "choices": ["(none)"] + CEFR_LEVELS, "value": "(none)"},
            {"key": "max", "label": "Max level filter", "kind": "choice", "flag": "--max-level",
             "choices": ["(none)"] + CEFR_LEVELS, "value": "(none)"},
            {"key": "targets", "label": "Compare levels", "kind": "text", "flag": "--targets",
             "value": "", "hint": "e.g. A2,B1,B2"},
            {"key": "sort", "label": "Sort by", "kind": "choice", "flag": "--sort",
             "choices": ["level", "name", "above"], "value": "level"},
            {"key": "format", "label": "Output", "kind": "choice", "flag": "--format",
             "choices": ["pretty", "json", "csv"], "value": "pretty"},
            {"key": "extra", "label": "Extra args", "kind": "extra", "value": ""},
        ],
    },
]


def build_argv(tool):
    """Translate a tool's current field values into a full argument vector."""
    argv = [engine_python(), os.path.join(HERE, tool["script"])]
    mode = "File"
    for f in tool["fields"]:
        if f["key"] == "mode":
            mode = f["value"]
            continue
        kind = f["kind"]
        val = f["value"]
        if kind == "source":
            if not str(val).strip():
                continue
            flag = "--text" if mode == "Inline text" else "--file"
            argv += [flag, str(val)]
        elif kind == "choice":
            if val in ("(none)", "(default)"):
                continue
            # toggle-style choice (e.g. grammar on/off -> --no-grammar)
            if "flag_when" in f:
                if val == f["flag_when"]:
                    argv.append(f["flag"])
                continue
            argv += [f["flag"], str(val)]
        elif kind == "toggle":
            if val:
                argv.append(f["flag"])
        elif kind == "text":
            if str(val).strip():
                argv += [f["flag"], str(val)]
        elif kind == "extra":
            if str(val).strip():
                argv += shlex.split(str(val))
    return argv


# --------------------------------------------------------------------------
# Engine diagnostics (shared by curses + fallback UIs).
# --------------------------------------------------------------------------


def check_engine():
    """Probe the venv/engine. Returns a dict of human-readable status strings."""
    py = engine_python()
    status = {"python": py, "spacy": None, "model": None, "pypdf": None}
    probe = (
        "import json,sys\n"
        "r={}\n"
        "try:\n"
        "    import spacy; r['spacy']=getattr(spacy,'__version__','yes')\n"
        "except Exception as e: r['spacy']=None\n"
        "try:\n"
        "    import spacy; spacy.load('en_core_web_sm'); r['model']=True\n"
        "except Exception: r['model']=False\n"
        "try:\n"
        "    import pypdf; r['pypdf']=getattr(pypdf,'__version__','yes')\n"
        "except Exception: r['pypdf']=None\n"
        "print(json.dumps(r))\n"
    )
    try:
        out = subprocess.run([py, "-c", probe], capture_output=True, text=True, timeout=60)
        import json
        data = json.loads(out.stdout.strip() or "{}")
        status.update(data)
    except Exception:  # noqa: BLE001
        pass
    return status


def engine_ready(status=None):
    """Return True when spaCy and the English model are both available."""
    status = status or check_engine()
    return bool(status.get("spacy")) and bool(status.get("model"))


# ==========================================================================
# curses front-end
# ==========================================================================


def run_curses():
    """Run the full-screen curses app via curses.wrapper."""
    import curses

    def _wrapped(stdscr):
        """curses.wrapper entry point: build the App and run its loop."""
        return App(stdscr).loop()

    return curses.wrapper(_wrapped)


class App:
    """The full-screen curses application: menus, forms, and running tools."""
    def __init__(self, stdscr):
        """Set up curses state and colour pairs for the given screen."""
        import curses

        self.curses = curses
        self.stdscr = stdscr
        curses.curs_set(0)
        stdscr.keypad(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)     # title
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)  # selection
            curses.init_pair(3, curses.COLOR_YELLOW, -1)   # hint / warning
            curses.init_pair(4, curses.COLOR_GREEN, -1)    # ok

    # -- drawing helpers ----------------------------------------------------

    def _addstr(self, y, x, text, attr=0):
        """Write text at (y, x), clipped to the screen; ignore overflow errors."""
        curses = self.curses
        h, w = self.stdscr.getmaxyx()
        if y < 0 or y >= h:
            return
        text = text[: max(0, w - x - 1)]
        try:
            self.stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def _header(self, subtitle=""):
        """Draw the title bar with an optional subtitle."""
        curses = self.curses
        self._addstr(0, 2, "VocabKitchen", curses.color_pair(1) | curses.A_BOLD)
        if subtitle:
            self._addstr(0, 16, "· " + subtitle, curses.A_DIM)
        h, w = self.stdscr.getmaxyx()
        self._addstr(1, 2, "─" * (w - 4), curses.A_DIM)

    def _footer(self, keys):
        """Draw the key-hint line along the bottom of the screen."""
        h, _ = self.stdscr.getmaxyx()
        self._addstr(h - 1, 2, keys, self.curses.A_DIM)

    # -- generic vertical menu ---------------------------------------------

    def menu(self, subtitle, items, footer="↑/↓ move · Enter select · q back"):
        """items: list of (label, help). Returns index, or None on q/Esc."""
        curses = self.curses
        idx = 0
        while True:
            self.stdscr.erase()
            self._header(subtitle)
            top = 3
            for i, (label, help_) in enumerate(items):
                attr = curses.color_pair(2) if i == idx else 0
                self._addstr(top + i, 4, f" {label} ".ljust(38), attr)
                if help_ and i == idx:
                    self._addstr(top + i, 44, help_, curses.A_DIM)
            self._footer(footer)
            self.stdscr.refresh()

            ch = self.stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(items)
            elif ch in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(items)
            elif ch in (curses.KEY_ENTER, 10, 13, ord(" ")):
                return idx
            elif ch in (ord("q"), 27):
                return None

    # -- text line editor ---------------------------------------------------

    def edit_line(self, prompt, initial=""):
        """Inline single-line editor; return the text, or None if cancelled."""
        curses = self.curses
        curses.curs_set(1)
        buf = list(str(initial))
        pos = len(buf)
        h, w = self.stdscr.getmaxyx()
        y = h - 2
        try:
            while True:
                self._addstr(y, 2, " " * (w - 4))
                label = prompt + ": "
                self._addstr(y, 2, label, curses.A_BOLD)
                field_x = 2 + len(label)
                shown = "".join(buf)
                self._addstr(y, field_x, shown[: max(0, w - field_x - 1)])
                self.stdscr.move(y, min(field_x + pos, w - 2))
                self.stdscr.refresh()

                ch = self.stdscr.getch()
                if ch in (curses.KEY_ENTER, 10, 13):
                    return "".join(buf)
                if ch == 27:  # Esc cancels
                    return None
                if ch in (curses.KEY_BACKSPACE, 127, 8):
                    if pos > 0:
                        del buf[pos - 1]
                        pos -= 1
                elif ch == curses.KEY_DC:
                    if pos < len(buf):
                        del buf[pos]
                elif ch == curses.KEY_LEFT:
                    pos = max(0, pos - 1)
                elif ch == curses.KEY_RIGHT:
                    pos = min(len(buf), pos + 1)
                elif ch == curses.KEY_HOME:
                    pos = 0
                elif ch == curses.KEY_END:
                    pos = len(buf)
                elif 32 <= ch < 127:
                    buf.insert(pos, chr(ch))
                    pos += 1
        finally:
            curses.curs_set(0)

    # -- suspend curses, run a subprocess, resume --------------------------

    def run_tool(self, argv):
        """Suspend curses, run argv with inherited stdio, then resume the menu."""
        curses = self.curses
        curses.def_prog_mode()
        curses.endwin()
        os.system("clear" if os.name != "nt" else "cls")
        # Show a readable command: "python3" for the interpreter, relative paths.
        parts = ["python3"] + [
            shlex.quote(a.replace(HERE + os.sep, "")) for a in argv[1:]
        ]
        sys.stdout.write("\033[1;36m$ %s\033[0m\n\n" % " ".join(parts))
        sys.stdout.flush()
        rc = None
        try:
            rc = subprocess.call(argv, cwd=HERE)
        except KeyboardInterrupt:
            rc = 130
        except Exception as exc:  # noqa: BLE001
            sys.stdout.write("\n\033[1;31mCould not run the tool: %s\033[0m\n" % exc)
        tail = "\n\033[2m── done (exit %s) · press Enter to return to the menu ──\033[0m" % rc
        sys.stdout.write(tail)
        sys.stdout.flush()
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        curses.reset_prog_mode()
        self.stdscr.refresh()

    # -- a tool's form ------------------------------------------------------

    def tool_form(self, tool):
        """Show a tool's editable form and run it on demand."""
        curses = self.curses
        fields = tool["fields"]
        idx = 0
        # rows = fields... plus a final "Run" action row
        while True:
            self.stdscr.erase()
            self._header(tool["name"])
            self._addstr(2, 4, tool["blurb"], curses.A_DIM)

            if tool["needs_engine"]:
                st = getattr(self, "_engine_status_cache", None)
                if st is None:
                    st = self._engine_status_cache = check_engine()
                if not engine_ready(st):
                    self._addstr(3, 4, "⚠ Grammar engine not ready — see Setup & diagnostics "
                                       "(this tool will show install steps).",
                                 curses.color_pair(3))

            top = 5
            for i, f in enumerate(fields):
                attr = curses.color_pair(2) if i == idx else 0
                label = f["label"].rjust(18)
                val = self._field_display(f)
                self._addstr(top + i, 4, label + " : ", attr | curses.A_BOLD if i == idx else 0)
                self._addstr(top + i, 4 + 21, val, attr)
                if i == idx and f.get("hint"):
                    self._addstr(top + i, 4 + 21 + max(20, len(val) + 2), f["hint"], curses.A_DIM)

            run_row = top + len(fields) + 1
            run_attr = curses.color_pair(2) if idx == len(fields) else curses.color_pair(4)
            self._addstr(run_row, 4, "  ▶ Run  ", run_attr | curses.A_BOLD)
            self._addstr(run_row, 20, "(builds and runs the command below)", curses.A_DIM)

            # preview
            argv = build_argv(tool)
            preview = " ".join(shlex.quote(a) for a in argv[1:])  # drop interpreter
            preview = preview.replace(os.path.join(HERE, tool["script"]), tool["script"])
            self._addstr(run_row + 2, 4, "command:", curses.A_DIM)
            self._addstr(run_row + 3, 4, preview, curses.color_pair(1))

            self._footer("↑/↓ move · Enter edit/cycle · ←/→ cycle · r Run · q back")
            self.stdscr.refresh()

            ch = self.stdscr.getch()
            n = len(fields) + 1  # +1 for Run row
            if ch in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % n
            elif ch in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % n
            elif ch in (ord("q"), 27):
                return
            elif ch in (ord("r"), ord("R")):
                self.run_tool(build_argv(tool))
            elif ch in (curses.KEY_ENTER, 10, 13, ord(" ")):
                if idx == len(fields):
                    self.run_tool(build_argv(tool))
                else:
                    self._activate_field(fields[idx], forward=True)
            elif ch == curses.KEY_RIGHT:
                if idx < len(fields):
                    self._cycle_field(fields[idx], +1)
            elif ch == curses.KEY_LEFT:
                if idx < len(fields):
                    self._cycle_field(fields[idx], -1)

    def _field_display(self, f):
        """Return the display string for a form field's current value."""
        if f["kind"] == "toggle":
            return "[x] yes" if f["value"] else "[ ] no"
        val = str(f["value"])
        if f["kind"] == "source" and not val:
            return "(stdin — type text when you Run, or set a value)"
        if f["kind"] in ("choice",):
            return "< %s >" % val
        return val if val else "(empty)"

    def _cycle_field(self, f, direction):
        """Advance a choice/toggle field by the given direction (+1/-1)."""
        if f["kind"] == "choice":
            ch = f["choices"]
            i = ch.index(f["value"]) if f["value"] in ch else 0
            f["value"] = ch[(i + direction) % len(ch)]
        elif f["kind"] == "toggle":
            f["value"] = not f["value"]

    def _activate_field(self, f, forward=True):
        """Edit or cycle the focused field, depending on its kind."""
        kind = f["kind"]
        if kind == "choice":
            self._cycle_field(f, +1)
        elif kind == "toggle":
            f["value"] = not f["value"]
        elif kind in ("source", "text", "extra"):
            new = self.edit_line("Edit " + f["label"], f["value"])
            if new is not None:
                f["value"] = new

    # -- setup / doctor screen ---------------------------------------------

    def doctor(self):
        """Setup & diagnostics screen: show engine status and offer the installer."""
        curses = self.curses
        while True:
            status = check_engine()
            self._engine_status_cache = status  # refresh cache used by forms
            self.stdscr.erase()
            self._header("Setup & diagnostics")
            rows = [
                ("Interpreter", status["python"], True),
                ("Python venv (.venv)",
                 "present" if os.path.exists(os.path.join(HERE, ".venv")) else "not created",
                 os.path.exists(os.path.join(HERE, ".venv"))),
                ("spaCy", status["spacy"] or "not installed", bool(status["spacy"])),
                ("English model (en_core_web_sm)",
                 "installed" if status["model"] else "not installed", bool(status["model"])),
                ("pypdf (PDF input, optional)",
                 status["pypdf"] or "not installed",
                 # 3-state: installed (✓), or absent-but-optional (○, not ✗).
                 True if status["pypdf"] else None),
            ]
            top = 3
            for i, (label, val, ok) in enumerate(rows):
                if ok is None:          # optional dependency, not installed
                    mark, color = "○", curses.A_DIM
                elif ok:
                    mark, color = "✓", curses.color_pair(4) | curses.A_BOLD
                else:
                    mark, color = "✗", curses.color_pair(3) | curses.A_BOLD
                self._addstr(top + i, 4, mark, color)
                self._addstr(top + i, 6, label.ljust(34), curses.A_BOLD)
                self._addstr(top + i, 42, str(val), curses.A_DIM)

            ready = engine_ready(status)
            msg_row = top + len(rows) + 1
            if ready:
                self._addstr(msg_row, 4, "Everything the grammar tools need is installed.",
                             curses.color_pair(4))
            else:
                self._addstr(msg_row, 4, "The grammar tools need spaCy + the model. "
                                         "Run the installer below.", curses.color_pair(3))

            installer_name = "install.ps1" if os.name == "nt" else "install.sh"
            actions = [
                ("Run installer (%s)" % installer_name,
                 "creates .venv and installs everything"),
                ("Re-check now", "re-run these diagnostics"),
                ("Validate word lists", "build_wordlists.py --check"),
                ("Back", ""),
            ]
            abase = msg_row + 2
            sel = self._inline_menu(abase, actions)
            if sel is None or sel == 3:
                return
            if sel == 0:
                self._run_installer()
            elif sel == 1:
                continue
            elif sel == 2:
                self.run_tool([engine_python(),
                               os.path.join(HERE, "build_wordlists.py"), "--check"])

    def _inline_menu(self, base_y, actions):
        """A small blocking menu drawn starting at base_y. Returns index or None."""
        curses = self.curses
        idx = 0
        while True:
            for i, (label, help_) in enumerate(actions):
                attr = curses.color_pair(2) if i == idx else 0
                self._addstr(base_y + i, 4, (" " + label + " ").ljust(34), attr)
                if i == idx and help_:
                    self._addstr(base_y + i, 40, help_, curses.A_DIM)
            self._footer("↑/↓ move · Enter select · q back")
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(actions)
            elif ch in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(actions)
            elif ch in (curses.KEY_ENTER, 10, 13, ord(" ")):
                return idx
            elif ch in (ord("q"), 27):
                return None

    def _flash(self, msg):
        """Show a one-line notice on the footer and wait for a keypress."""
        curses = self.curses
        h, w = self.stdscr.getmaxyx()
        self._addstr(h - 2, 2, (msg + "   (press a key)")[: max(0, w - 4)],
                     curses.color_pair(3) | curses.A_BOLD)
        self.stdscr.refresh()
        self.stdscr.getch()

    def _run_installer(self):
        """Run the platform installer, or report why it can't be run."""
        argv, err = installer_invocation()
        if err:
            self._flash(err)
            return
        self.run_tool(argv)
        self._engine_status_cache = None  # force refresh

    # -- top-level loop -----------------------------------------------------

    def loop(self):
        """Run the top-level menu until the user quits."""
        while True:
            items = [(t["name"], t["blurb"]) for t in TOOLS]
            items.append(("Setup & diagnostics", "check/install the grammar engine"))
            items.append(("Quit", ""))
            sel = self.menu("main menu", items,
                            footer="↑/↓ move · Enter select · q quit")
            if sel is None or sel == len(items) - 1:
                return
            if sel == len(TOOLS):
                self.doctor()
            else:
                self.tool_form(TOOLS[sel])


def _which(cmd):
    """Return the resolved path to an executable on PATH, or None."""
    from shutil import which
    return which(cmd)


def installer_invocation():
    """Pick the platform's installer and a runner for it.

    Returns ``(argv, None)`` ready to run, or ``(None, message)`` when the
    installer or a suitable interpreter is missing — so callers can report the
    problem instead of crashing on a missing shell.
    """
    if os.name == "nt":
        installer = os.path.join(HERE, "install.ps1")
        if not os.path.exists(installer):
            return None, "install.ps1 not found in %s" % HERE
        runner = _which("pwsh") or _which("powershell")
        if not runner:
            return None, ("PowerShell (pwsh/powershell) was not found — "
                          "run install.ps1 by hand.")
        return [runner, "-ExecutionPolicy", "Bypass", "-File", installer], None
    installer = os.path.join(HERE, "install.sh")
    if not os.path.exists(installer):
        return None, "install.sh not found in %s" % HERE
    runner = _which("bash") or _which("sh")
    if not runner:
        return None, "No POSIX shell (bash/sh) was found — run install.sh by hand."
    return [runner, installer], None


# ==========================================================================
# Plain-text fallback (no curses / non-interactive terminal)
# ==========================================================================


def run_fallback():
    """Plain numbered-menu loop used when curses is unavailable."""
    print("VocabKitchen — text menu (curses unavailable; using the simple menu)\n")
    while True:
        print("Choose a tool:")
        for i, t in enumerate(TOOLS, 1):
            flag = "" if not t["needs_engine"] else "  (needs spaCy)"
            print("  %d) %s%s" % (i, t["name"], flag))
        print("  d) Setup & diagnostics")
        print("  q) Quit")
        choice = _ask("> ").strip().lower()
        if choice in ("q", "quit", "exit", ""):
            return
        if choice == "d":
            _fallback_doctor()
            continue
        if not choice.isdigit() or not (1 <= int(choice) <= len(TOOLS)):
            print("  ? please enter a number, d, or q\n")
            continue
        _fallback_tool(TOOLS[int(choice) - 1])


def _fallback_tool(tool):
    """Prompt for a tool's fields in plain text, then run it."""
    print("\n== %s ==" % tool["name"])
    print(tool["blurb"])
    if tool["needs_engine"] and not engine_ready():
        installer = "install.ps1" if os.name == "nt" else "./install.sh"
        print("\n⚠ This tool needs spaCy + en_core_web_sm, which are not installed.")
        print("  Run:  %s   (or choose 'd' from the menu)\n" % installer)
    # Ask each editable field, keeping defaults on blank input.
    for f in tool["fields"]:
        if f["key"] == "mode" and len(f.get("choices", [])) < 2:
            continue
        if f["kind"] == "toggle":
            ans = _ask("%s? [y/N]: " % f["label"]).strip().lower()
            f["value"] = ans in ("y", "yes")
            continue
        if f["kind"] == "choice":
            ans = _ask("%s %s [%s]: " % (f["label"], f["choices"], f["value"])).strip()
            if ans:
                f["value"] = ans
            continue
        cur = f["value"] or "(empty)"
        ans = _ask("%s [%s]: " % (f["label"], cur)).strip()
        if ans:
            f["value"] = ans
    argv = build_argv(tool)
    pretty = " ".join(shlex.quote(a) for a in argv[1:])
    print("\n$ python3 %s\n" % pretty.replace(os.path.join(HERE, tool["script"]), tool["script"]))
    try:
        subprocess.call(argv, cwd=HERE)
    except Exception as exc:  # noqa: BLE001
        print("Could not run the tool: %s" % exc)
    _ask("\n(press Enter to continue) ")
    print()


def _fallback_doctor():
    """Plain-text setup diagnostics with an option to run the installer."""
    st = check_engine()
    print("\n== Setup & diagnostics ==")
    print("  interpreter : %s" % st["python"])
    print("  spaCy       : %s" % (st["spacy"] or "not installed"))
    print("  model       : %s" % ("installed" if st["model"] else "not installed"))
    print("  pypdf       : %s" % (st["pypdf"] or "not installed"))
    if engine_ready(st):
        print("  -> grammar tools are ready.\n")
    else:
        installer = "install.ps1" if os.name == "nt" else "install.sh"
        print("  -> grammar tools need setup. Run %s" % installer)
        if _ask("  Run the installer now? [y/N]: ").strip().lower() in ("y", "yes"):
            argv, err = installer_invocation()
            if err:
                print("  " + err)
            else:
                subprocess.call(argv, cwd=HERE)
    print()


def _ask(prompt):
    """Prompt for a line of input; return 'q' on EOF/Ctrl-C so callers exit."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


# ==========================================================================


def main():
    """Entry point: pick the curses UI or the plain-text fallback."""
    # A non-interactive stdin/stdout can't drive a menu — say so plainly.
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        print("The VocabKitchen TUI needs an interactive terminal.\n"
              "Run it directly:  ./vocabkitchen   (or  python3 tui.py)\n"
              "Or call a tool non-interactively, e.g.:\n"
              "  python3 vocab_profile.py --file sample-readings/starter.txt",
              file=sys.stderr)
        return 1
    try:
        import curses  # noqa: F401
    except Exception:  # noqa: BLE001
        run_fallback()
        return 0
    try:
        run_curses()
    except Exception as exc:  # noqa: BLE001
        # Never crash into a traceback in front of the user; degrade gracefully.
        sys.stderr.write("The full-screen menu could not start (%s).\n"
                         "Falling back to the simple text menu.\n\n" % exc)
        run_fallback()
    return 0


if __name__ == "__main__":
    sys.exit(main())
