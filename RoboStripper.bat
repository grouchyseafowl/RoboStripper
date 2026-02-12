@echo off
setlocal enabledelayedexpansion
REM ✨ RoboStripper — double-click to run ✨

cd /d "%~dp0"

REM Resize terminal window to fit the banner (35 rows x 80 cols)
mode con: cols=80 lines=35

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
echo   Python is free — think of it like an engine under
echo   the hood. Install it once, never think about it again.
echo.
echo   ⚠️  IMPORTANT: Check "Add Python to PATH" during install!
echo.
echo   ─────────────────────────────────────────────────
echo.
set /p answer="  Open the Python download page? [Y/n] "
echo.

if /i "%answer%"=="n" goto decline
if /i "%answer%"=="no" goto decline

start https://www.python.org/downloads/
echo   💅 Opening python.org...
echo.
echo   Once you've installed Python:
echo     1. Close this window
echo     2. Double-click me again
echo.
echo   💋 See you in a sec!
echo.
pause
exit /b

:decline
echo   👠 No worries. Install Python whenever you're ready,
echo      then come back and double-click me.
echo.
pause
exit /b
