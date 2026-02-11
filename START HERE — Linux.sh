#!/bin/bash
# ✨ RoboStripper — run to launch ✨

cd "$(dirname "$0")"

# Offer to clean up other OS launchers
OTHER_LAUNCHERS=()
[ -f "START HERE — Mac.command" ] && OTHER_LAUNCHERS+=("START HERE — Mac.command")
[ -f "START HERE — Windows.bat" ] && OTHER_LAUNCHERS+=("START HERE — Windows.bat")

if [ ${#OTHER_LAUNCHERS[@]} -gt 0 ]; then
    echo ""
    echo "  👀 I see launcher files for other operating systems."
    echo "     Since you're on Linux, want me to remove them?"
    echo ""
    read -p "  Delete other launchers? [y/N] " cleanup
    echo ""
    if [[ "$cleanup" =~ ^[yY] ]]; then
        for f in "${OTHER_LAUNCHERS[@]}"; do
            rm -f "$f"
        done
        echo "  ✨ Cleaned up. Just you and me now."
        echo ""
    fi
fi

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
echo "  Python is a free programming language — think of"
echo "  it like an engine under the hood. You install it"
echo "  once and never think about it again."
echo ""
echo "  To install, open a terminal and run:"
echo "    sudo apt install python3 python3-pip"
echo ""
echo "  ─────────────────────────────────────────────────"
echo ""
read -p "  Open the Python download page instead? [Y/n] " answer
echo ""

case "$answer" in
    [nN]*)
        echo "  👠 No worries. Install Python whenever you're ready,"
        echo "     then double-click me again."
        echo ""
        read -p "  Press Enter to close..."
        exit 0
        ;;
    *)
        xdg-open "https://www.python.org/downloads/" 2>/dev/null || echo "  Visit: https://www.python.org/downloads/"
        echo "  ✨ Opening python.org..."
        echo ""
        echo "  Once you've installed it:"
        echo "    1. Close this window"
        echo "    2. Double-click me again"
        echo ""
        echo "  💋 See you in a sec."
        echo ""
        read -p "  Press Enter to close..."
        exit 0
        ;;
esac
