<#
    EFL-Tools — one-command setup for Windows (PowerShell).

    Mirrors install.sh: creates a .venv next to this script and installs
    spaCy + the English model (+ pypdf for PDF input, and windows-curses so the
    full-screen TUI works). Re-runnable; an existing .venv is reused.

    Usage:
        powershell -ExecutionPolicy Bypass -File .\install.ps1
        powershell -ExecutionPolicy Bypass -File .\install.ps1 -Minimal
#>
param([switch]$Minimal)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here
$Venv = Join-Path $Here ".venv"

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  ok $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !! $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "Error: $m" -ForegroundColor Red; exit 1 }

# --- find Python 3.8+ ---
$Py = $null
foreach ($cand in @("python", "python3", "py")) {
    $exe = (Get-Command $cand -ErrorAction SilentlyContinue)
    if ($exe) {
        try {
            & $cand -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,8) else 1)"
            if ($LASTEXITCODE -eq 0) { $Py = $cand; break }
        } catch { }
    }
}
if (-not $Py) {
    Die "Python 3.8+ is required. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then re-run this script."
}
$PyVer = (& $Py -c "import platform; print(platform.python_version())")
Say "Using Python $PyVer"

# --- venv ---
$VPy = Join-Path $Venv "Scripts\python.exe"
if (Test-Path $VPy) {
    Ok "Reusing existing virtual environment (.venv)"
} else {
    Say "Creating virtual environment in .venv"
    & $Py -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Die "Could not create the virtual environment." }
    Ok "Virtual environment created"
}
if (-not (Test-Path $VPy)) { Die "The virtual environment looks broken. Delete .venv and re-run." }

# --- packages ---
Say "Upgrading pip"
& $VPy -m pip install --quiet --upgrade pip

Say "Installing spaCy (this can take a minute)"
& $VPy -m pip install --quiet spacy
if ($LASTEXITCODE -ne 0) { Die "Installing spaCy failed. If your Python is brand-new, install 3.11/3.12 and re-run. A network connection is required." }
Ok "spaCy installed"

Say "Downloading the English model (en_core_web_sm)"
& $VPy -m spacy download en_core_web_sm
if ($LASTEXITCODE -ne 0) { Die "Downloading the spaCy model failed (network problem?). Finish later with: .venv\Scripts\python.exe -m spacy download en_core_web_sm" }
Ok "English model installed"

Say "Installing windows-curses (for the full-screen menu)"
& $VPy -m pip install --quiet windows-curses
if ($LASTEXITCODE -eq 0) { Ok "windows-curses installed" } else { Warn "windows-curses failed — the TUI will use its simple text menu instead." }

if (-not $Minimal) {
    Say "Installing pypdf (PDF input)"
    & $VPy -m pip install --quiet pypdf
    if ($LASTEXITCODE -eq 0) { Ok "pypdf installed" } else { Warn "pypdf failed — PDF input unavailable, everything else works." }
}

# --- verify ---
Say "Verifying the installation"
& $VPy -c "import spacy; spacy.load('en_core_web_sm')"
if ($LASTEXITCODE -ne 0) { Die "The grammar engine did not load. Delete .venv and re-run." }
Ok "Grammar engine ready (spaCy + en_core_web_sm)"

Write-Host ""
Write-Host "All set. EFL-Tools is ready." -ForegroundColor Green
Write-Host "  Launch the interactive menu:  .\efl-tools.cmd"
Write-Host "  …or:  .venv\Scripts\python.exe tui.py"
