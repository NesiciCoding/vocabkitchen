@echo off
REM VocabKitchen launcher for Windows — opens the interactive TUI.
REM Prefers the project's .venv, falls back to the system Python.
setlocal
set "HERE=%~dp0"

if defined GRAMMAR_PROFILE_PYTHON (
    if exist "%GRAMMAR_PROFILE_PYTHON%" (
        "%GRAMMAR_PROFILE_PYTHON%" "%HERE%tui.py" %*
        goto :eof
    )
)
if exist "%HERE%.venv\Scripts\python.exe" (
    "%HERE%.venv\Scripts\python.exe" "%HERE%tui.py" %*
    goto :eof
)
where python >nul 2>&1 && (
    python "%HERE%tui.py" %*
    goto :eof
)
where py >nul 2>&1 && (
    py "%HERE%tui.py" %*
    goto :eof
)
echo Python 3 was not found. Install it, then run install.ps1
exit /b 1
