@echo off
setlocal enabledelayedexpansion
REM ✨ RoboStripper — double-click to run ✨

cd /d "%~dp0"

REM Offer to clean up other OS launchers
set "HAS_OTHERS=0"
if exist "START HERE — Mac.command" set "HAS_OTHERS=1"
if exist "START HERE — Linux.sh" set "HAS_OTHERS=1"

if "%HAS_OTHERS%"=="1" (
    echo.
    echo   👀 I see launcher files for other operating systems.
    echo      Since you're on Windows, want me to remove them?
    echo.
    set /p cleanup="  Delete other launchers? [y/N] "
    echo.
    if /i "!cleanup!"=="y" (
        if exist "START HERE — Mac.command" del "START HERE — Mac.command"
        if exist "START HERE — Linux.sh" del "START HERE — Linux.sh"
        echo   ✨ Cleaned up. Just you and me now.
        echo.
    )
)

where python >nul 2>nul
if %errorlevel%==0 (
    python robostripper.py
    echo.
    pause
    exit /b
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    python3 robostripper.py
    echo.
    pause
    exit /b
)

REM No Python found — styled install prompt
echo.
echo   ┌─────────────────────────────────────────────────┐
echo   │  👠✨💅  R O B O S T R I P P E R  💅✨👠       │
echo   └─────────────────────────────────────────────────┘
echo.
echo   Hey love! Before I can work my magic, I need
echo   Python installed on your computer.
echo.
echo   Python is a free programming language — think of
echo   it like an engine under the hood. You install it
echo   once and never think about it again.
echo.
echo   IMPORTANT: During install, check the box that says
echo   "Add Python to PATH" — this lets me find it.
echo.
echo   ─────────────────────────────────────────────────
echo.
set /p answer="  Open the Python download page? [Y/n] "
echo.

if /i "%answer%"=="n" goto decline
if /i "%answer%"=="no" goto decline

start https://www.python.org/downloads/
echo   ✨ Opening python.org...
echo.
echo   Once you've installed it:
echo     1. Close this window
echo     2. Double-click me again
echo.
echo   💋 See you in a sec.
echo.
pause
exit /b

:decline
echo   👠 No worries. Install Python whenever you're ready,
echo      then double-click me again.
echo.
pause
exit /b
