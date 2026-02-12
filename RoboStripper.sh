#!/bin/bash
# ✨ RoboStripper — run to launch ✨

cd "$(dirname "$0")"

# Resize terminal window to fit the banner (35 rows x 80 cols)
printf '\e[8;35;80t'

# Check for Python
if command -v python3 &>/dev/null; then
    python3 robostripper.py
    echo ""
    read -p "  Press Enter to close..."
    exit 0
fi

if command -v python &>/dev/null; then
    python robostripper.py
    echo ""
    read -p "  Press Enter to close..."
    exit 0
fi

# No Python found — styled install prompt
echo ""
echo "  ┌─────────────────────────────────────────────────┐"
echo "  │  👠✨💅  R O B O S T R I P P E R  💅✨👠       │"
echo "  └─────────────────────────────────────────────────┘"
echo ""
echo "  Hey love! Before I can work my magic, I need"
echo "  Python installed on your computer."
echo ""
echo "  Python is free — think of it like an engine under"
echo "  the hood. Install it once, never think about it again."
echo ""
echo "  Quick install (Debian/Ubuntu):"
echo "    sudo apt install python3 python3-pip"
echo ""
echo "  ─────────────────────────────────────────────────"
echo ""
read -p "  Open the Python download page instead? [Y/n] " answer
echo ""

case "$answer" in
    [nN]*)
        echo "  👠 No worries. Install Python whenever you're ready,"
        echo "     then come back and run me again."
        echo ""
        read -p "  Press Enter to close..."
        exit 0
        ;;
    *)
        xdg-open "https://www.python.org/downloads/" 2>/dev/null || echo "  Visit: https://www.python.org/downloads/"
        echo "  💅 Opening python.org..."
        echo ""
        echo "  Once you've installed Python:"
        echo "    1. Close this window"
        echo "    2. Run me again"
        echo ""
        echo "  💋 See you in a sec!"
        echo ""
        read -p "  Press Enter to close..."
        exit 0
        ;;
esac
