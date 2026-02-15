# 🚀 Release Checklist (Stopgap TUI)

Use this for every GitHub Release so users can download and double‑click without using the terminal.

## ✅ Files to upload to the Release

- `RoboStripper.zip` (contains the TUI + launchers)
  - Must include:
    - `robostripper.py`
    - `RoboStripper.command` (Mac)
    - `RoboStripper.bat` (Windows)
    - `RoboStripper.sh` (Linux)
    - `assets/`

## ✅ README should say

- “Download `RoboStripper.zip` → unzip → double‑click launcher.”
- “No terminal needed.”

## ✅ Quick smoke test (optional but recommended)

- **Mac**: Double‑click `RoboStripper.command`
- **Windows**: Double‑click `RoboStripper.bat`
- **Linux**: Double‑click `RoboStripper.sh`

If Python isn’t installed, each launcher should open python.org with instructions.
