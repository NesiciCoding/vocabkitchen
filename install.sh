#!/usr/bin/env bash
#
# VocabKitchen — one-command setup.
#
# Creates a self-contained virtual environment (.venv) next to this script and
# installs everything the profilers need:
#
#   * spaCy + the small English model  (grammar / text-report / class-profile)
#   * pypdf                            (optional PDF input)
#
# The plain vocabulary profiler needs none of this — it runs on stdlib Python 3
# alone — but installing the venv makes every tool, and the TUI, work with no
# further steps. The profiler scripts already auto-detect this .venv and
# re-launch under it, so nothing needs to be "activated" afterwards.
#
# Usage:
#   ./install.sh            # full setup (recommended)
#   ./install.sh --minimal  # skip pypdf (no PDF input)
#
# It is safe to re-run: an existing .venv is reused and packages are upgraded.

set -euo pipefail

# --- locate ourselves, following symlinks ----------------------------------
# When this script is bundled into a plugin it's a symlink back to the repo
# copy; resolve it so .venv is created next to the *real* script — the same
# place the profilers look for it (they resolve their own realpath too).
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    dir="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in
        /*) ;;
        *) SOURCE="$dir/$SOURCE" ;;
    esac
done
HERE="$(cd -P "$(dirname "$SOURCE")" && pwd)"
cd "$HERE"

VENV="$HERE/.venv"
MINIMAL=0
for arg in "$@"; do
    case "$arg" in
        --minimal) MINIMAL=1 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed '/^!/d'
            exit 0 ;;
        *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ok\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

# --- find a usable Python 3 -------------------------------------------------
PY=""
for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
        if "$cand" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 8) else 1)' 2>/dev/null; then
            PY="$cand"
            break
        fi
    fi
done
[ -n "$PY" ] || die "Python 3.8+ is required but was not found.
  Install Python 3 first:
    macOS:  install the Xcode Command Line Tools, or 'brew install python'
    Debian/Ubuntu:  sudo apt install python3 python3-venv
    Fedora:  sudo dnf install python3
    Arch:  sudo pacman -S python"

PY_VER="$("$PY" -c 'import platform; print(platform.python_version())')"
say "Using Python $PY_VER ($("$PY" -c 'import sys; print(sys.executable)'))"

# --- create the virtual environment ----------------------------------------
if [ -d "$VENV" ] && [ -x "$VENV/bin/python" ]; then
    ok "Reusing existing virtual environment (.venv)"
else
    say "Creating virtual environment in .venv"
    if ! "$PY" -m venv "$VENV" 2>/tmp/vk_venv_err; then
        cat /tmp/vk_venv_err >&2 || true
        die "Could not create the virtual environment.
  On Debian/Ubuntu the venv module ships separately — install it with:
    sudo apt install python3-venv
  then re-run ./install.sh"
    fi
    ok "Virtual environment created"
fi

VPY="$VENV/bin/python"
[ -x "$VPY" ] || die "The virtual environment looks broken ($VPY missing). Delete .venv and re-run."

# --- install packages -------------------------------------------------------
say "Upgrading pip"
"$VPY" -m pip install --quiet --upgrade pip || warn "pip self-upgrade failed; continuing with the existing pip"

say "Installing spaCy (this can take a minute)"
if ! "$VPY" -m pip install --quiet spacy; then
    die "Installing spaCy failed.
  spaCy ships compiled wheels that can lag on brand-new Python releases.
  If '$PY_VER' was released very recently, install an earlier Python 3 (e.g.
  3.11 or 3.12) and re-run ./install.sh. The network must also be reachable."
fi
ok "spaCy installed"

say "Downloading the English model (en_core_web_sm)"
if ! "$VPY" -m spacy download en_core_web_sm >/dev/null 2>&1; then
    # Retry once, surfacing the error this time.
    if ! "$VPY" -m spacy download en_core_web_sm; then
        die "Downloading the spaCy English model failed (network problem?).
  Once you have connectivity, finish setup with:
    $VPY -m spacy download en_core_web_sm"
    fi
fi
ok "English model installed"

if [ "$MINIMAL" -eq 0 ]; then
    say "Installing pypdf (PDF input)"
    if "$VPY" -m pip install --quiet pypdf; then
        ok "pypdf installed"
    else
        warn "pypdf failed to install — PDF input will be unavailable, everything else works."
    fi
fi

# --- verify -----------------------------------------------------------------
say "Verifying the installation"
if "$VPY" - <<'PYCHECK'
import sys
try:
    import spacy
    spacy.load("en_core_web_sm")
except Exception as exc:  # noqa: BLE001
    print(f"  grammar engine check failed: {exc}", file=sys.stderr)
    sys.exit(1)
PYCHECK
then
    ok "Grammar engine ready (spaCy + en_core_web_sm)"
else
    die "The grammar engine did not load after install. Try deleting .venv and re-running."
fi

echo
printf '\033[1;32mAll set.\033[0m VocabKitchen is ready to use.\n\n'
if [ -f "$HERE/tui.py" ]; then
    # Running from the repo checkout: the TUI and samples are alongside us.
    cat <<EOF
  Launch the interactive menu (TUI):
      ./vocabkitchen

  …or run a tool directly, e.g.:
      python3 vocab_profile.py --file sample-readings/academic-essay.txt
      python3 text_report.py --file sample-readings/news-report.txt --target-level B1

EOF
else
    # Bundled inside a plugin: no TUI or samples here, just the profiler.
    cat <<EOF
  The profiler command is ready to use — spaCy and the English model are
  installed in .venv, which the tool finds automatically.

EOF
fi
echo "Nothing needs activating — the tools find .venv on their own."
