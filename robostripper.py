#!/usr/bin/env python3
"""
RoboStripper 👠✨💅
Strips metadata from scholarly PDFs so RoboBraille can read them clean.

Usage:
    python3 robostripper.py                           # interactive mode
    python3 robostripper.py input.pdf                 # single file
    python3 robostripper.py PDFs/                     # batch directory
    python3 robostripper.py input.pdf --preview       # preview output
"""

import argparse
import io
import json
import os
import re
import shlex
import subprocess
import shutil
import sys
import urllib.request
import webbrowser
from pathlib import Path
from collections import Counter
from typing import Optional

VERSION = "1.0.0"  # Manually bump this when releasing updates


# ── Profile System ───────────────────────────────────────────────────────────

PROFILES = {
    "cunty": {
        "name": "Cunty",
        "banner_emoji": "👠✨💅",
        "greeting": "Hey love! I'm your friendly neighborhood RoboStripper",
        "tagline": "🔥 No more interruptions! 🔥",
        "subtitle": "Just good, clean fun.\nLike a spa day but it's homework.",
        "working_emoji": "💅",
        "success_emoji": "✨",
        "error_emoji": "😱😫😭",
        "goodbye": "👠 Standing by. You know where to find me.",
        "go_get_em": "💋 Go get 'em.",
        "first_time": "Oh, it's your first time? 👀",
        "need_packages": "I need a few *packages* to work my magic 😏😘",
        "old_files": "Ew, babe. I found {n} old file{s} in ~/StrippedText/ 😵‍💫",
        "cleanup_prompt": "Want me to send in the {maid} to clean up this {mess} and delete the old files?",
        "cleanup_yes": "✨ All cleaned up! 🧹🧽🧼 Now doesn't that feel better? 😉",
        "cleanup_no": "Sure, babe. Live in your own filth if that's what you want 💅",
    },
    "normie": {
        "name": "NORMIE",
        "banner_emoji": "",
        "greeting": "RoboStripper PDF Processing Utility - Version 1.0.0-stable",
        "tagline": "Document Metadata Extraction and Removal System (DMERS)",
        "subtitle": "Licensed for use under standard academic processing protocols.\nCompliance ID: RS-2024-PROC-1847",
        "working_emoji": "▪",
        "success_emoji": "✓",
        "error_emoji": "X",
        "goodbye": "Session #[AUTO] terminated at [TIMESTAMP]. Please retain this window for your records.\nThank you for using RoboStripper DMERS.",
        "go_get_em": "Processing task queue complete. You may now proceed to the next step.\nPlease allow 2-3 business days for changes to take effect.",
        "first_time": "INITIAL SETUP REQUIRED - Form RS-101",
        "need_packages": "The following system dependencies must be installed before proceeding.\nFailure to install may result in application errors (Code: ERR-DEP-001):",
        "old_files": "NOTICE: System has detected {n} existing file{s} in designated output directory.\nFile retention policy compliance check required.",
        "cleanup_prompt": "Proceed with removal of existing files? (Action cannot be undone)\n     Select option:",
        "cleanup_yes": "✓ File removal operation completed successfully.\n     Reference Code: CLN-{timestamp}\n     Files processed: {n}",
        "cleanup_no": "Operation cancelled. Existing files will be retained in output directory.\n     NOTE: This may affect disk space allocation.",
    }
}

def load_profile() -> str:
    """Load saved profile preference from config file."""
    config_dir = Path.home() / ".robostripper"
    config_file = config_dir / "config.json"

    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
                return config.get("profile", "cunty")
        except Exception:
            pass

    return "cunty"  # Default

def save_profile(profile: str):
    """Save profile preference to config file."""
    config_dir = Path.home() / ".robostripper"
    config_file = config_dir / "config.json"

    config_dir.mkdir(exist_ok=True)

    config = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
        except Exception:
            pass

    config["profile"] = profile

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

CURRENT_PROFILE = load_profile()
P = PROFILES[CURRENT_PROFILE]  # Shorthand for current profile


# ── ANSI Colors ──────────────────────────────────────────────────────────────

def _supports_color():
    """Check if terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if sys.platform == "win32":
        return os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM")
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_color()

MAGENTA = "\033[95m" if USE_COLOR else ""  # Hot pink in GUI - same as PINK
PINK = "\033[35m" if USE_COLOR else ""     # Hot pink in GUI
CYAN = "\033[96m" if USE_COLOR else ""     # Champagne gold in GUI - friendly text, instructions
EMERALD = "\033[94m" if USE_COLOR else ""  # Emerald in GUI - commands only
YELLOW = "\033[93m" if USE_COLOR else ""
GREEN = "\033[92m" if USE_COLOR else ""
WHITE = "\033[97m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""
R = "\033[0m" if USE_COLOR else ""

# Output directory — keep writable for app bundles
SCRIPT_DIR = Path(__file__).resolve().parent
if getattr(sys, 'frozen', False):
    OUTPUT_DIR = Path.home() / "StrippedText"
else:
    OUTPUT_DIR = SCRIPT_DIR / "StrippedText"


# ── Dependency Check & Auto-Install ──────────────────────────────────────────

def check_and_install_deps():
    """Check for required packages and offer to install them."""
    import datetime

    # Skip if running as PyInstaller bundle (dependencies are already bundled)
    if getattr(sys, 'frozen', False):
        return

    missing = []

    try:
        import fitz  # noqa: F401
    except ImportError:
        missing.append("pymupdf")

    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.extend(["pytesseract", "Pillow"])

    if not missing:
        return

    missing = list(dict.fromkeys(missing))

    if CURRENT_PROFILE == "cunty":
        # CUNTY PROFILE: Playful first-time setup
        print()
        print(f"  {BOLD}📦 FIRST-TIMER SETUP 📦{R}")
        print()
        print(f"  {PINK}Oh sweatie, is this your first time? 👀😏{R}")
        print(f"  {DIM}I need a few *packages* to work my ✨magic✨{R}")
        for pkg in missing:
            print(f"    {DIM}•{R} {pkg}{R}")
        print()

        try:
            answer = input(f"  {BOLD}Install now? [Y/n]{R} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {PINK}👠 Maybe next time!{R}\n{R}")
            sys.exit(0)

        if answer not in ('', 'y', 'yes'):
            print(f"\n  {PINK}Whatever, boo 💅 Install manually with:{R}")
            print(f"    {EMERALD}pip install {' '.join(missing)}{R}")
            print()
            sys.exit(1)
    else:
        # NORMIE PROFILE: Bureaucratic dependency installation
        print()
        print(f"  {DIM}══════════════════════════════════════════════════{R}")
        print(f"  INITIAL SETUP REQUIRED - Form RS-101{R}")
        print(f"  {DIM}══════════════════════════════════════════════════{R}")
        print()
        print(f"  {DIM}The following system dependencies must be installed before proceeding.{R}")
        print(f"  {DIM}Failure to install may result in application errors (Code: ERR-DEP-001):{R}")
        print()
        for pkg in missing:
            print(f"    {DIM}▪ {pkg}{R}")
        print()

        try:
            answer = input(f"  Proceed with automated installation? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {DIM}Installation cancelled by user. Session terminated.{R}")
            print(f"  Reference Code: TERM-{datetime.datetime.now().strftime('%H%M%S')}{R}\n{R}")
            sys.exit(0)

        if answer not in ('', 'y', 'yes'):
            print(f"\n  {DIM}User response not valid. Manual installation required:{R}")
            print(f"    pip install {' '.join(missing)}{R}")
            print(f"  Please complete installation and restart application.{R}")
            print()
            sys.exit(1)

    print()

    if CURRENT_PROFILE == "cunty":
        # CUNTY PROFILE: Quick and fun
        print(f"  {CYAN}Installing...{R}")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages"] + missing,
                stdout=subprocess.DEVNULL if not sys.stdout.isatty() else None,
            )
        except subprocess.CalledProcessError:
            print(f"\n  Oh no, babe! {YELLOW}pip install failed 😭 Try running manually:{R}")
            print(f"    pip install {' '.join(missing)}{R}")
            sys.exit(1)

        print(f"  {GREEN}✓ Installed!{R}\n{R}")
    else:
        # NORMIE PROFILE: Bureaucratic installation process
        gray_spinner(0.6, "📋 Initiating package installation protocol...")
        gray_spinner(0.5, "🏢 Connecting to cubicle...")
        gray_spinner(0.8, "🖼️ Adding obligatory personalization to cubicle...")
        gray_spinner(0.5, "📄 Completing paperwork...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages"] + missing,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            print(f"\n  {DIM}ERROR: Package installation failed (Code: ERR-INSTALL-002){R}")
            print(f"  {DIM}Manual installation required:{R}")
            print(f"    pip install {' '.join(missing)}{R}")
            print(f"  {DIM}Please complete installation and restart application.{R}")
            print(f"  Reference Code: ERR-{datetime.datetime.now().strftime('%H%M%S')}{R}")
            sys.exit(1)

        gray_spinner(0.4, "✔️ Completing installation procedures...")
        print(f"  {DIM}✓ Installation completed successfully. 📊{R}")
        print(f"  {DIM}Reference Code: INST-{datetime.datetime.now().strftime('%H%M%S')}{R}\n{R}")


def check_tesseract() -> bool:
    """Check if Tesseract OCR binary is available."""
    try:
        subprocess.run(
            ["tesseract", "--version"],
            capture_output=True, check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


# Run dependency check before importing (skip in GUI mode — GUI handles it in main())
if not os.environ.get('ROBOSTRIPPER_GUI_MODE'):
    check_and_install_deps()

try:
    import fitz  # pymupdf  # noqa: E402
except ImportError:
    fitz = None  # Will be available after check_and_install_deps() in main()

try:
    import pytesseract  # noqa: E402
    from PIL import Image  # noqa: E402
    TESSERACT_INSTALLED = check_tesseract()
    OCR_AVAILABLE = TESSERACT_INSTALLED
except ImportError:
    OCR_AVAILABLE = False
    TESSERACT_INSTALLED = False


# ── Metadata Patterns ────────────────────────────────────────────────────────

METADATA_PATTERNS = [
    # --- JSTOR ---
    ("jstor_download", re.compile(r"This content downloaded from .+"), "line"),
    ("jstor_terms", re.compile(r"All use subject to https?://about\.jstor\.org/terms"), "line"),
    ("jstor_boilerplate", re.compile(r"JSTOR is a not-for-profit service"), "line"),
    ("jstor_stable_url", re.compile(r"Stable URL:\s*https?://"), "line"),
    ("jstor_accessed", re.compile(r"Accessed:\s+\d{2}-\d{2}-\d{4}"), "line"),
    ("jstor_collab", re.compile(r"is collaborating with JSTOR"), "line"),
    ("jstor_linked_refs", re.compile(r"Linked references are available on JSTOR"), "line"),
    ("jstor_your_use", re.compile(r"Your use of the JSTOR archive indicates"), "line"),

    # --- ProQuest Ebook Central ---
    ("proquest_copyright", re.compile(r"Copyright\s*©\s*\d{4}\.\s*.+\.\s*All rights reserved\.?"), "line"),
    ("proquest_page_range", re.compile(r"Ebook pages \d+-\d+\s*\|\s*Printed page \d+ of \d+"), "line"),
    ("proquest_url", re.compile(r"https?://ebookcentral\.proquest\.com/lib/.+"), "line"),
    ("proquest_created", re.compile(r"Created from \w+ on \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"), "line"),
    ("proquest_citation", re.compile(r"^.{10,}\.\s*ProQuest\s*(Ebook Central)?\.?\s*$"), "line"),

    # --- EBSCO ---
    ("ebsco_header", re.compile(r"EBSCO Publishing:\s*eBook Collection.+", re.IGNORECASE), "line"),
    ("ebsco_terms", re.compile(r"All use subject to https?://www\.ebsco\.com/terms-of-use"), "line"),
    ("ebsco_rights", re.compile(r"All rights reserved\.\s*May not be reproduced"), "line"),
    ("ebsco_account", re.compile(r"Account:\s*\w+", re.IGNORECASE), "line"),
    ("ebsco_printed_on", re.compile(r"printed on \d{4}-\d{2}-\d{2}.*via\b", re.IGNORECASE), "line"),
    ("ebsco_copyright_block", re.compile(r"Copyright of .+ is the property of .+"), "line"),
    ("ebsco_content_may_not", re.compile(r"content may not be copied or emailed"), "line"),
    ("ebsco_express_written", re.compile(r"copyright holder's express written permission"), "line"),
    ("ebsco_users_may_print", re.compile(r"users may print, download, or email"), "line"),

    # --- Duke University Press ---
    ("duke_download", re.compile(r"Downloaded from https?://read\.dukeupress\.edu/.+"), "line"),
    ("duke_user", re.compile(r"by [A-Z\s]+ user$"), "line"),
    ("publisher_year_line", re.compile(r"^\d{4}\.\s+.+(?:Press|Books|Publishing|Publishers)\b.+\.\s*$"), "line"),

    # --- Taylor & Francis / journal headers ---
    ("tf_url_footer", re.compile(r"WWW\.TANDFONLINE\.COM/\w+", re.IGNORECASE), "line"),
    ("tf_vol_issue", re.compile(r"^\d{4},\s*VOL\.\s*\d+,\s*NO\.\s*\d+", re.IGNORECASE), "line"),
    ("tf_copyright", re.compile(r"^\s*©\s*\d{4}\s+Taylor\s*&\s*Francis", re.IGNORECASE), "line"),
    ("doi_line", re.compile(r"^\s*https?://doi\.org/.+$"), "line"),
    ("contact_line", re.compile(r"^CONTACT\s+.+@.+$", re.IGNORECASE), "line"),

    # --- eScholarship front matter ---
    ("eschol_powered", re.compile(r"eScholarship\.org\s*/?\s*Powered by the California Digital Library"), "line"),
    ("eschol_permalink", re.compile(r"Permalink:\s*https?://escholarship\.org/.+"), "line"),

    # --- Chicago Unbound ---
    ("chicago_unbound", re.compile(r"This Article is brought to you for free and open access by Chicago Unbound"), "line"),
    ("chicago_follow", re.compile(r"Follow this and additional works at:\s*https?://"), "line"),

    # --- General ---
    ("standalone_url", re.compile(r"^\s*https?://\S+\s*$"), "line"),
    ("creative_commons_line", re.compile(r"Creative Commons Attribution.+License"), "line"),
    ("rights_reserved", re.compile(r"^\s*©\s*\d{4}.+All rights reserved\.?\s*$"), "line"),
]


# ── Core Functions ───────────────────────────────────────────────────────────

def detect_page_numbers(pages: list[str]) -> set[str]:
    """
    Smart page number detection - only remove if numbers appear in consistent
    positions and increment sequentially.
    """
    page_num_candidates = []  # List of (page_index, line_position, number_value)

    for page_idx, page_text in enumerate(pages):
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        if not lines:
            continue

        # Check first 3 and last 3 lines for standalone numbers
        positions_to_check = []
        if len(lines) >= 3:
            positions_to_check.extend([(i, lines[i]) for i in range(min(3, len(lines)))])
            positions_to_check.extend([(len(lines) - i - 1, lines[len(lines) - i - 1]) for i in range(min(3, len(lines)))])

        for line_pos, line in positions_to_check:
            # Check if line is just a number (1-4 digits)
            if re.match(r'^\s*\d{1,4}\s*$', line):
                num_value = int(line.strip())
                page_num_candidates.append((page_idx, line_pos, num_value, line.strip()))

    if len(page_num_candidates) < 3:
        return set()  # Not enough data to confidently identify page numbers

    # Group by line position (e.g., all first lines, all last lines)
    from collections import defaultdict
    by_position = defaultdict(list)
    for page_idx, line_pos, num_value, original in page_num_candidates:
        by_position[line_pos].append((page_idx, num_value, original))

    # Check each position group for sequential numbering
    page_nums_to_remove = set()
    for line_pos, candidates in by_position.items():
        if len(candidates) < 3:
            continue

        # Sort by page index
        candidates.sort()

        # Check if numbers increment (allowing gaps for missing pages)
        sequential_count = 0
        for i in range(len(candidates) - 1):
            page_idx1, num1, orig1 = candidates[i]
            page_idx2, num2, orig2 = candidates[i + 1]

            # Numbers should increase as pages increase
            if num2 > num1 and num2 - num1 <= 5:  # Allow small gaps
                sequential_count += 1

        # If >60% of transitions are sequential, these are page numbers
        if sequential_count >= len(candidates) * 0.6:
            for _, _, original in candidates:
                page_nums_to_remove.add(original)

    return page_nums_to_remove


def detect_repeating_lines(pages: list[str]) -> set[str]:
    """Auto-detect metadata lines that repeat across pages."""
    line_counter = Counter()
    total_pages = len(pages)

    for page_text in pages:
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        if not lines:
            continue

        header_lines = lines[:5]
        footer_lines = lines[-5:] if len(lines) > 5 else []

        seen_this_page = set()
        for line in header_lines + footer_lines:
            normalized = line.lower().strip()
            if normalized and len(normalized) < 200 and normalized not in seen_this_page:
                line_counter[normalized] += 1
                seen_this_page.add(normalized)

    threshold = max(3, int(total_pages * 0.4))
    return {line for line, count in line_counter.items() if count >= threshold}


def detect_front_matter_pages(pages: list[str]) -> int:
    """Detect how many leading pages are front matter to strip."""
    if not pages:
        return 0

    first_page = pages[0].lower()
    front_matter_markers = [
        "jstor is a not-for-profit",
        "escholarship.org",
        "chicago unbound",
        "follow this and additional works",
        "stable url:",
        "recommended citation",
    ]

    if any(m in first_page for m in front_matter_markers) and len(pages[0]) < 500:
        return 1
    return 0


def extract_citation(pdf_path: Path, raw_pages: list[str]) -> dict:
    """
    Extract citation metadata from PDF metadata and first-page text.
    Returns dict with keys: title, author, date, source.
    Values are strings or None. Conservative — prefers no info over wrong info.
    """
    info = {"title": None, "author": None, "date": None, "source": None}

    # Junk PDF metadata values to ignore
    junk = {"untitled", "sometitle", "someauthor", "unknown", "none", "microsoft word"}

    # 1. Try PDF file metadata
    try:
        doc = fitz.open(pdf_path)
        meta = doc.metadata or {}
        doc.close()

        title = (meta.get("title") or "").strip()
        author = (meta.get("author") or "").strip()

        if title and len(title) > 3 and title.lower() not in junk:
            info["title"] = title
        if author and len(author) > 1 and author.lower() not in junk:
            info["author"] = author
    except Exception:
        pass

    if not raw_pages:
        return info

    first_page = raw_pages[0]
    lines = [l.strip() for l in first_page.split('\n') if l.strip()]

    # 2. Try to capture ProQuest citation line (before it's stripped)
    #    Format: "Last, First. Title : Subtitle, Publisher, Year. ProQuest"
    for line in lines:
        if re.search(r'\.\s*ProQuest\s*(Ebook Central)?\.?\s*$', line):
            # Split on ". " to get author and rest — first period-space is author/title boundary
            m = re.match(r'^([^.]+,\s*[^.]+)\.\s+(.+),\s+.+,\s+(\d{4})\.\s*ProQuest', line)
            if m:
                info["author"] = info["author"] or m.group(1).strip()
                info["title"] = info["title"] or m.group(2).strip().rstrip(',')
                info["date"] = info["date"] or m.group(3)
            break

    # 3. Try to extract journal info from T&F / journal headers
    for line in lines:
        # "JOURNAL OF LATINOS AND EDUCATION" style
        if line.isupper() and 15 < len(line) < 100 and "JOURNAL" in line:
            info["source"] = info["source"] or line.strip()
        # "2024, VOL. 23, NO. 2, 474–491"
        m = re.match(r'^(\d{4}),\s*VOL\.\s*(\d+),\s*NO\.\s*(\d+)', line, re.IGNORECASE)
        if m:
            info["date"] = info["date"] or m.group(1)
            if info["source"]:
                info["source"] += f" Vol. {m.group(2)}, No. {m.group(3)}"

    # 4. Try EBSCO/Duke publisher line for source
    for line in lines:
        m = re.match(r'^(\d{4})\.\s+(.+(?:Press|Books|Publishing|Publishers).+)\.\s*$', line)
        if m:
            info["date"] = info["date"] or m.group(1)
            info["source"] = info["source"] or m.group(2).strip()

    # 5. Guess title from first page text ONLY if we have nothing from structured sources.
    #    Very conservative — better to show no title than a wrong one.
    if not info["title"]:
        skip_patterns = [
            r'^(Chapter|Part|Section)\s+\w+',
            r'^OTHER\s+WORKS',
            r'^PUBLISHED\s+BY',
            r'^(Also|See)\s+',
            r'also appears',
            r'^(Edited|Translated|With|Foreword)',
            r'^\d{4}\.',
        ]
        for line in lines[:10]:
            # Must be substantial — short lines are often fragments of multi-line titles
            if len(line) < 20 or re.match(r'^\d+$', line):
                continue
            # Must start with uppercase (skip broken drop-cap lines)
            if line[0].islower():
                continue
            # Skip fragments (trailing comma, semicolon, hyphen)
            if line.rstrip()[-1] in ',;-':
                continue
            if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
                continue
            if any(p.search(line) for _, p, _ in METADATA_PATTERNS):
                continue
            info["title"] = line
            break

    # Author guessing from unstructured text is too unreliable —
    # only use author from PDF metadata or ProQuest citation parsing above.

    return info


def format_citation_header(citation: dict) -> str:
    """
    Format citation info as a TTS-friendly header block.
    Only produces output when we have confident data — at minimum a title
    plus one other field (author, source, or date).
    """
    has_title = bool(citation.get("title"))
    has_author = bool(citation.get("author"))
    has_source = bool(citation.get("source"))
    has_date = bool(citation.get("date"))

    # Require title + at least one other field to avoid showing garbage
    if not has_title or not (has_author or has_source or has_date):
        return ""

    parts = []
    parts.append(citation["title"])
    if has_author:
        parts.append(f"By {citation['author']}")

    source_date = []
    if has_source:
        source_date.append(citation["source"])
    if has_date:
        source_date.append(citation["date"])
    if source_date:
        parts.append(", ".join(source_date))

    header = "\n".join(parts)
    return f"{header}\n\n---\n\n"


def classify_page_blocks(page, body_size: float) -> str:
    """
    Re-assemble a page's text block by block, tagging non-body blocks
    with sentinels so downstream processing can handle them semantically.

    Sentinels inserted:
      [BLOCKQUOTE] ... [/BLOCKQUOTE]  — indented block quote (smaller font)
      [CAPTION] ... [/CAPTION]        — figure/photo caption (smaller font,
                                        typically at page bottom or after image)

    We use font size relative to the established body size to classify:
      - body_size ± 0.5 pt  → normal body text (no tag)
      - smaller by > 1 pt   → candidate for blockquote or caption
      - very small (< 7 pt) → watermark/DRM noise → skip entirely
      - larger / bold       → heading (handled later by format_for_tts)

    Distinguishing blockquotes from captions: captions tend to be short
    (≤ 3 lines), contain photo/illustration cues, or follow image blocks.
    Blockquotes tend to be multi-line prose.
    """
    blocks = page.get_text("dict")["blocks"]
    result_parts = []
    prev_was_image = False
    prev_was_caption = False

    for block in blocks:
        # Image blocks — skip, but flag so the next text block can be
        # identified as a caption
        if block["type"] == 1:
            prev_was_image = True
            continue

        # Gather all spans in this block
        spans = []
        for line in block["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    spans.append(span)

        if not spans:
            prev_was_image = False
            continue

        # Determine dominant font size for this block (median)
        sizes = sorted(span["size"] for span in spans)
        dominant_size = sizes[len(sizes) // 2]

        # Very small = watermark/DRM noise — drop entirely
        if dominant_size < 7.0:
            prev_was_image = False
            continue

        # Get block text the normal way (preserves line structure)
        block_text = "\n".join(
            "".join(span["text"] for span in line["spans"])
            for line in block["lines"]
        ).strip()

        if not block_text:
            prev_was_image = False
            continue

        size_diff = body_size - dominant_size  # positive = smaller than body

        if size_diff > 1.0:
            # Smaller than body text — blockquote or caption
            lines = [l for l in block_text.split('\n') if l.strip()]

            # Caption heuristics:
            #   1. Immediately follows an image block, OR
            #   2. Contains explicit photo/figure cue words
            caption_cues = ('photo by', 'figure', 'image', 'illustration',
                            'courtesy', 'credit', 'photograph')
            any_line_lower = ' '.join(lines).lower()
            looks_like_caption = (
                prev_was_image
                or prev_was_caption   # continuation of a multi-block caption
                or any(cue in any_line_lower for cue in caption_cues)
            )

            if looks_like_caption:
                result_parts.append(f"[CAPTION]{block_text}[/CAPTION]")
                prev_was_caption = True
            else:
                result_parts.append(f"[BLOCKQUOTE]{block_text}[/BLOCKQUOTE]")
                prev_was_caption = False
        else:
            result_parts.append(block_text)
            prev_was_caption = False

        prev_was_image = False

    return "\n\n".join(p for p in result_parts if p.strip())


def detect_body_font_size(doc) -> float:
    """
    Determine the body text font size for a document by finding the most
    common font size across all pages (excluding very small sizes like
    watermarks and very large sizes like headings).
    """
    size_counter = Counter()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"].strip():
                        size = round(span["size"], 1)
                        if 8.0 <= size <= 16.0:  # plausible body text range
                            size_counter[size] += len(span["text"])

    if not size_counter:
        return 12.0  # fallback
    return size_counter.most_common(1)[0][0]


def extract_text(pdf_path: Path) -> list[str]:
    """Extract text from PDF, with OCR fallback for scanned pages."""
    pages = []
    ocr_pages = []

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        if CURRENT_PROFILE == "cunty":
            print(f"    {YELLOW}Oh no, babe! I hit an error opening {pdf_path}: {e}{R} 😱😫😭", file=sys.stderr)
        else:
            print(f"    ⚠️{BOLD} ERROR:{R} ⚠️ {DIM}Failed to open PDF file (Code: ERR-PDF-453GN){R}")
            print(f"    File: {DIM}{pdf_path}{R}")
            print(f"    Description: {DIM}{e}{R}", file=sys.stderr)
        return []

    # Detect body font size once across whole document
    body_size = detect_body_font_size(doc)
    use_font_aware = (body_size > 0)

    total = len(doc)
    for page_num in range(total):
        page = doc[page_num]

        # Font-aware extraction when possible (gives us blockquote/caption tags)
        if use_font_aware:
            try:
                text = classify_page_blocks(page, body_size)
            except Exception:
                text = page.get_text("text")
        else:
            text = page.get_text("text")

        if len(text.strip()) < 50:
            if OCR_AVAILABLE:
                try:
                    pix = page.get_pixmap(dpi=300)
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    text = pytesseract.image_to_string(img)
                    ocr_pages.append(page_num + 1)
                except Exception as e:
                    if CURRENT_PROFILE == "cunty":
                        print(f"    {DIM}{PINK}Oh no, honey!{R}{DIM} OCR failed p.{page_num + 1}: {e}{R} 😱😫😭", file=sys.stderr)
                    else:
                        print(f"    ⚠️{BOLD} WARNING:{R} ⚠️ {DIM}OCR processing failed for page {page_num + 1}{R}")
                        print(f"    Error details: {DIM}{e}{R}", file=sys.stderr)
            elif not TESSERACT_INSTALLED:
                # Silently note — we'll report at the end
                ocr_pages.append(page_num + 1)

        pages.append(text)

    doc.close()

    # Report OCR usage (profile-aware)
    if ocr_pages and OCR_AVAILABLE:
        if CURRENT_PROFILE == "cunty":
            print(f"    {DIM}I used OCR on {len(ocr_pages)} scanned page{'s' if len(ocr_pages) != 1 else ''}{R} 😚🤌{R}")
        else:
            print(f"    NOTICE: {DIM}OCR processing applied to {len(ocr_pages)} page{'s' if len(ocr_pages) != 1 else ''}{R}")
    elif ocr_pages and not OCR_AVAILABLE:
        if CURRENT_PROFILE == "cunty":
            print(f"    {YELLOW}⚠ {len(ocr_pages)} page{'s look' if len(ocr_pages) != 1 else ' looks'} scanned but OCR isn't available{R} 😫😭{R}")
            if not TESSERACT_INSTALLED:
                if sys.platform == "darwin":
                    hint = "brew install tesseract"
                elif sys.platform == "win32":
                    hint = "choco install tesseract"
                else:
                    hint = "sudo apt install tesseract-ocr"
                print(f"    {DIM}To turn on OCR: 😉 {hint}{R}")
        else:
            print(f"    {BOLD}⚠️ WARNING: ⚠️{R} {DIM}{len(ocr_pages)} scanned page{'s' if len(ocr_pages) != 1 else ''} detected.{R}")
            print(f"    {DIM}OCR not available. Text extraction may be incomplete.{R}")
            if not TESSERACT_INSTALLED:
                if sys.platform == "darwin":
                    hint = "brew install tesseract"
                elif sys.platform == "win32":
                    hint = "choco install tesseract"
                else:
                    hint = "sudo apt install tesseract-ocr"
                print(f"    {DIM}To enable OCR: {hint}{R}")

    return pages


def clean_page(text: str, repeating_lines: set[str]) -> str:
    """Clean a single page's text."""
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        matched = False
        for name, pattern, scope in METADATA_PATTERNS:
            if scope == "line" and pattern.search(line):
                matched = True
                break
        if matched:
            continue

        normalized = line.lower().strip()
        if normalized in repeating_lines:
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def reflow_paragraphs(text: str) -> str:
    """
    Join soft line breaks (PDF hard-wrap artifacts) within paragraphs.

    PDF text extraction preserves every line break from the rendered PDF layout,
    so a single paragraph becomes many short lines. We join them into proper
    flowing paragraphs so TTS doesn't pause at every line end.

    Rules for keeping a line break (i.e. it IS a paragraph/section boundary):
      - Blank line (double newline) → always kept
      - Previous line ends with sentence-ending punctuation (.!?:") AND next
        line starts with an uppercase letter → keep (new sentence/paragraph)
      - Line is very short (≤ 4 chars) and looks like a heading or isolated
        fragment → keep as its own line
      - Next line starts with a bullet/dash/number list marker → keep

    Otherwise: join with a space.
    """
    # Split into paragraph blocks first (preserve blank-line boundaries)
    paragraph_blocks = re.split(r'\n{2,}', text)
    reflowed_blocks = []

    for block in paragraph_blocks:
        lines = block.split('\n')
        if len(lines) <= 1:
            reflowed_blocks.append(block)
            continue

        joined = []
        current = lines[0].rstrip()

        for next_line in lines[1:]:
            next_stripped = next_line.strip()

            # Empty line within block — shouldn't happen after split but be safe
            if not next_stripped:
                joined.append(current)
                current = ''
                continue

            # If current line is empty, start fresh
            if not current.strip():
                current = next_stripped
                continue

            cur_stripped = current.rstrip()

            # Decide whether to join or keep as separate line
            keep_break = False

            # Short isolated lines (headings, chapter numbers, captions)
            if len(cur_stripped) <= 6 and cur_stripped[-1:] not in '-,':
                keep_break = True

            # Current ends with sentence-terminating punctuation and next starts uppercase
            elif cur_stripped and cur_stripped[-1] in '.!?"' and next_stripped and next_stripped[0].isupper():
                keep_break = True

            # Next line looks like a list item
            elif re.match(r'^[\-•*\d]+[\.\)]\s', next_stripped):
                keep_break = True

            # Next line starts with an em-dash (block quote / attribution)
            elif next_stripped.startswith('—') or next_stripped.startswith('-'):
                keep_break = True

            # Current line IS an attribution/quote marker (starts with —)
            # The next line is a new paragraph
            elif cur_stripped.startswith('—') and next_stripped and next_stripped[0].isupper():
                keep_break = True

            if keep_break:
                joined.append(current)
                current = next_stripped
            else:
                # Join with a space (handle case where current ends with hyphen)
                if cur_stripped.endswith('-'):
                    current = cur_stripped[:-1] + next_stripped
                else:
                    current = cur_stripped + ' ' + next_stripped

        if current.strip():
            joined.append(current)

        reflowed_blocks.append('\n'.join(joined))

    return '\n\n'.join(reflowed_blocks)


def join_continued_blocks(text: str) -> str:
    """
    Merge paragraph blocks that are mid-sentence continuations.

    PDF text is extracted block-by-block, and sentences often span two blocks
    (e.g. split at a page break or column boundary). reflow_paragraphs handles
    soft-wrapped lines within a block, but leaves double-newline block boundaries
    intact. This function merges across those boundaries when the previous block
    clearly doesn't end a sentence.

    A block is a continuation if:
      - The previous block doesn't end with sentence-terminating punctuation
        (.  !  ?  :  "  \u201d) AND the current block starts with a lowercase letter.
    """
    SENTENCE_END = set('.!?:"\u201d')
    blocks = re.split(r'\n\n+', text)
    result = []
    for block in blocks:
        if not result:
            result.append(block)
            continue
        prev = result[-1].rstrip()
        curr = block.lstrip()
        if prev and curr and prev[-1] not in SENTENCE_END and curr[0].islower():
            result[-1] = prev + ' ' + curr
        else:
            result.append(block)
    return '\n\n'.join(result)


def strip_inline_footnote_numbers(text: str) -> str:
    """
    Remove footnote/endnote reference numbers from PDF-extracted text.

    Two forms appear in PDF extractions:
    1. Standalone line: a line containing only a small integer (not a year,
       not surrounded by blank lines on both sides).
    2. Trailing inline: a number glued to the end of a word with no space,
       e.g. "Cook-Lynn1" or "earth."3  — superscript refs baked into the line.
    """
    lines = text.split('\n')
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # A line that is ONLY a small number (1-3 digits, ≤ 999)
        if re.match(r'^\d{1,3}$', stripped):
            num = int(stripped)
            # Don't remove if it's a plausible year (1700-2100)
            if 1700 <= num <= 2100:
                result.append(line)
                continue
            # Don't remove if surrounded by blank lines (could be a section number)
            prev_blank = (i == 0) or (not lines[i - 1].strip())
            next_blank = (i == len(lines) - 1) or (not lines[i + 1].strip())
            if prev_blank and next_blank:
                result.append(line)
                continue
            # Otherwise it's a footnote ref — drop it
            continue
        # Remove trailing inline footnote refs: word/punct immediately followed
        # by 1-3 digits at end of line, e.g. "Cook-Lynn1" → "Cook-Lynn"
        # or "earth."3 → "earth."
        # Include curly quotes (U+2018/19, U+201C/D) — PDFs use these before
        # sanitize_for_tts has run, so we need them here too.
        line = re.sub(r'([a-zA-Z"\'.\!\?\u2018\u2019\u201c\u201d])\d{1,3}(\s*)$', r'\1\2', line)
        result.append(line)
    return '\n'.join(result)


def clean_document(pages: list[str]) -> str:
    """Clean entire document."""
    if not pages:
        return ""

    front_matter_count = detect_front_matter_pages(pages)
    pages = pages[front_matter_count:]
    if not pages:
        return ""

    # Detect both repeating metadata lines and sequential page numbers
    repeating_lines = detect_repeating_lines(pages)
    page_numbers = detect_page_numbers(pages)
    lines_to_remove = repeating_lines | page_numbers  # Combine both sets

    cleaned_pages = [clean_page(page, lines_to_remove) for page in pages]
    text = '\n\n'.join(cleaned_pages)

    # Fix hyphenation across line breaks (must happen before reflow).
    # PRESERVE the hyphen when joining — compound words like "thirty-two",
    # "scorched-earth", "well-known" should keep their hyphens.
    # Soft-hyphen PDF artifacts like "comple-\ntion" become "comple-tion",
    # which TTS handles better than "Thirtytwo" or "scorchedearth".
    text = re.sub(
        r'(\w+)-\n(\w+)',
        lambda m: m.group(1) + '-' + m.group(2) if m.group(2)[0].islower() else m.group(0),
        text
    )

    # Fix possessives split by PDF glyph separation: "Vaughn' s" → "Vaughn's"
    text = re.sub(r"(\w+)'\s+s\b", r"\1's", text)

    # Remove inline footnote reference numbers
    text = strip_inline_footnote_numbers(text)

    # Reflow soft line breaks into proper paragraphs (within blocks)
    text = reflow_paragraphs(text)

    # Merge mid-sentence continuations that span PDF block boundaries
    text = join_continued_blocks(text)

    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def sanitize_for_tts(text: str) -> str:
    """
    Replace characters and sequences that RoboBraille misreads or vocalizes
    poorly. This runs on the raw extracted text before any other formatting.

    Known RoboBraille issues:
      - Em dash (U+2014) → read aloud as the letter "A" (Latin-1 artifact)
      - En dash (U+2013) → similar misread
      - Long sequences of dashes (———) → garbled output
      - Non-breaking space (U+00A0) → may cause word-join artifacts
      - Curly quotes (U+2018/19, U+201C/D) → sometimes misread
      - Ellipsis character (U+2026) → sometimes skipped
      - Bullet (U+2022) → sometimes skipped
    """
    # Remove decorative separator lines BEFORE character substitution
    # (so "————————" gets removed before the — chars are turned into " - ")
    text = re.sub(r'^\s*[\u2014\u2013\u2015\-_=]{3,}\s*$', '', text, flags=re.MULTILINE)

    replacements = [
        # Em dash: replace with " - " so it reads naturally as a pause/dash
        ('\u2014', ' - '),
        # En dash: replace with " to " when between numbers, else " - "
        # (simple blanket replacement is fine for TTS)
        ('\u2013', ' - '),
        # Non-breaking space → regular space
        ('\u00a0', ' '),
        # Curly/smart quotes → straight quotes
        ('\u2018', "'"),
        ('\u2019', "'"),
        ('\u201c', '"'),
        ('\u201d', '"'),
        # Ellipsis character → three dots with spaces so TTS pauses
        ('\u2026', '...'),
        # Bullet → dash (most TTS reads dash fine)
        ('\u2022', '-'),
        # Horizontal bar (U+2015)
        ('\u2015', ' - '),
        # Figure dash (U+2012)
        ('\u2012', '-'),
    ]
    for char, repl in replacements:
        text = text.replace(char, repl)

    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)

    return text


def format_for_tts(text: str, faithful: bool = False) -> str:
    """
    Format text for TTS-friendly reading.

    Handles:
      - Sanitizing characters RoboBraille misreads (em dashes, curly quotes, etc.)
      - [BLOCKQUOTE]...[/BLOCKQUOTE] sentinels → "Quote: ... End quote."
      - [CAPTION]...[/CAPTION] sentinels → removed entirely
      - Standalone chapter numbers → "Chapter N."
      - ALL-CAPS section headings → "New section. Heading."
      - Abbreviation expansion (et al., ibid., etc.)
    """
    # Sanitize problematic characters first
    text = sanitize_for_tts(text)

    # ── Block quotes ──────────────────────────────────────────────────────────
    # First, merge consecutive [BLOCKQUOTE] blocks (e.g. quote body + attribution
    # that the PDF stored as separate text blocks at the same smaller font size).
    text = re.sub(
        r'\[/BLOCKQUOTE\]\s*\[BLOCKQUOTE\]',
        '\n',
        text
    )

    # Now replace each [BLOCKQUOTE]...[/BLOCKQUOTE] with spoken framing.
    def format_blockquote(m):
        content = m.group(1).strip()
        # Detect attribution line: starts with em-dash or " - " pattern,
        # typically the last line of the block.
        lines = content.split('\n')
        body_lines = []
        attribution = None
        for line in lines:
            s = line.strip()
            if s.startswith('\u2014') or re.match(r'^[\- ]+[A-Z]', s):
                attribution = re.sub(r'^[\u2014\- ]+', '', s).strip()
                attribution = re.sub(r'\d{1,3}$', '', attribution).strip()  # strip trailing footnote ref
            else:
                body_lines.append(line)
        body = ' '.join(l.strip() for l in body_lines if l.strip())
        # Strip any trailing inline footnote ref from the quote body
        body = re.sub(r'([a-zA-Z"\'\.\!\?])\d{1,3}\s*$', r'\1', body).strip()
        result = f"Quote: {body} End quote."
        if attribution:
            result += f" {attribution}."
        return f"\n\n{result}\n\n"

    text = re.sub(
        r'\[BLOCKQUOTE\](.*?)\[/BLOCKQUOTE\]',
        format_blockquote,
        text,
        flags=re.DOTALL
    )

    # ── Captions → remove ────────────────────────────────────────────────────
    text = re.sub(r'\[CAPTION\].*?\[/CAPTION\]', '', text, flags=re.DOTALL)

    # ── Chapter numbers and section headings ─────────────────────────────────
    lines = text.split('\n')
    formatted_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Standalone chapter number: a line that is just a number (1-2 digits),
        # surrounded by blank lines, not a year.
        if re.match(r'^\d{1,2}$', stripped):
            num = int(stripped)
            prev_blank = (i == 0) or not lines[i - 1].strip()
            next_blank = (i == len(lines) - 1) or not lines[i + 1].strip()
            if prev_blank and next_blank and num < 100:
                formatted_lines.append('')
                formatted_lines.append(f"Chapter {num}.")
                formatted_lines.append('')
                i += 1
                continue

        # Section heading: ALL CAPS line (or majority uppercase), short, no
        # terminal sentence punctuation. Add "New section." before it.
        is_heading = False
        if stripped and len(stripped) < 80:
            upper_ratio = sum(1 for c in stripped if c.isupper()) / max(len(stripped), 1)
            if (stripped.isupper() or upper_ratio > 0.6) and stripped[-1] not in '.!?:;,':
                # Make sure it's not just an acronym mid-sentence
                if len(stripped.split()) >= 1 and len(stripped) > 2:
                    is_heading = True

        if is_heading:
            # Title-case the heading so it sounds natural when read aloud
            # (avoids TTS reading each letter of "ORIGINS" as O-R-I-G-I-N-S
            # on some engines, and is more pleasant regardless)
            readable = stripped.title()
            formatted_lines.append('')
            formatted_lines.append(f"New section. {readable}.")
            formatted_lines.append('')
        else:
            formatted_lines.append(line)
        i += 1

    text = '\n'.join(formatted_lines)

    # ── Abbreviation expansion ────────────────────────────────────────────────
    if not faithful:
        for pattern, replacement in [
            (r'\bet al\.', 'and others'),
            (r'\bibid\.', 'same source'),
            (r'\bcf\.', 'compare'),
            (r'\be\.g\.', 'for example'),
            (r'\bi\.e\.', 'that is'),
            (r'\bp\.\s*(\d+)', r'page \1'),
            (r'\bpp\.\s*(\d+)', r'pages \1'),
        ]:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Output Directory ─────────────────────────────────────────────────────────

def get_output_dir() -> Path:
    """Get or create the output directory."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR


def check_cleanup() -> None:
    """If output directory has old files, offer to clean up (profile-aware)."""
    import datetime

    if not OUTPUT_DIR.exists():
        return

    txt_files = list(OUTPUT_DIR.glob("*.txt"))
    if not txt_files:
        return

    n = len(txt_files)

    if CURRENT_PROFILE == "cunty":
        # CUNTY PROFILE: Playful cleanup prompt
        print(f"  {BOLD}Ew, babe. I found {n} old file{'s' if n != 1 else ''} in ~/StrippedText/ 😵‍💫{R}")
        try:
            answer = input(f"     Want me to send in the {CYAN}{BOLD}maid{R} to clean up this {MAGENTA}dirty mess{R} and delete the old files? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = 'n'

        if answer in ('y', 'yes'):
            for f in txt_files:
                f.unlink()
            print(f"     {GREEN}✨ All cleaned up! 🧹🧽🧼 Now doesn't that feel better? 😉{R}")
        else:
            print(f"     {PINK}Sure, babe. Live in your own filth if that's what you want 💅{R}")
    else:
        # NORMIE PROFILE: Bureaucratic file cleanup notice
        print(f"  {BOLD}⚠️ NOTICE: ⚠️{R}{DIM} System has detected {n} existing file{'s' if n != 1 else ''} in designated{R}")
        print(f"  {DIM}output directory. File retention policy compliance check required. 📋{R}")
        print()
        try:
            answer = input(f"  Proceed with removal of existing files? (Action cannot be undone) [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = 'n'

        if answer in ('y', 'yes'):
            print()
            gray_spinner(0.5, "📄 Initiating file deletion protocol...")
            gray_spinner(0.5, "🟥 Processing red tape requirements...")
            gray_spinner(0.8, "⏳ Completing paperwork...")
            for f in txt_files:
                f.unlink()
            print(f"  {DIM}✔️ File removal operation completed successfully. 📉{R}")
            ref_code = f"CLN-{datetime.datetime.now().strftime('%H%M%S')}"
            print(f"  {DIM}Reference Code: {ref_code} 🏢{R}")
            print(f"  {DIM}Files processed: {n}{R}")
        else:
            print()
            print(f"  ⏳ Operation cancelled{DIM}. Existing files will be retained in output directory.{R}")
            print(f"  NOTE: {DIM}This may affect disk space allocation. 📊{R}")

    print()

    # After user responds to cleanup, clear screen
    # This removes the cleanup prompt and prepares for main menu
    if txt_files:  # Only if cleanup prompt was shown
        clear_screen()


# ── UI Functions ─────────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard."""
    try:
        if sys.platform == "darwin":
            subprocess.run(['pbcopy'], input=text.encode(), check=True)
        elif sys.platform == "win32":
            subprocess.run(['clip'], input=text.encode(), check=True)
        else:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def resize_terminal():
    """Resize terminal window based on current profile."""
    if CURRENT_PROFILE == "cunty":
        # Cunty profile: 80 columns x 35 rows
        cols, rows = 80, 35
    else:
        # Normie profile: 100 columns x 60 rows (wider for bureaucratic text)
        cols, rows = 100, 60

    # Try to resize terminal (works on most terminals)
    try:
        # ANSI escape sequence for terminal resize
        print(f'\033[8;{rows};{cols}t', end='', flush=True)
    except Exception:
        pass  # Silent fail if terminal doesn't support resizing


def clear_screen():
    """Clear the terminal screen using ANSI codes."""
    print("\033[2J\033[H", end="", flush=True)


def clear_and_show_header():
    """Clear screen and redisplay banner (without fluorescent joke)."""
    clear_screen()
    print_banner(first_time=False)


def print_banner(first_time=True, header_only=False):
    """Print the welcome banner (profile-aware).

    Args:
        first_time: If True, show fluorescent lighting joke in normie mode.
                   If False, skip the joke and show banner directly.
        header_only: If True, only show title/border, skip all content.
    """
    global P, CURRENT_PROFILE
    P = PROFILES[CURRENT_PROFILE]  # Refresh in case profile changed

    # Resize terminal to fit banner
    resize_terminal()

    if CURRENT_PROFILE == "cunty":
        # ═══════════════════════════════════════════════════════════
        # CUNTY PROFILE BANNER: Colorful, playful, fabulous
        # ═══════════════════════════════════════════════════════════
        # Elegant high-femme title treatment with borders
        print(f"{MAGENTA}{'─' * 71}{R}")
        print(f"{BOLD}{MAGENTA}              👠✨💅  R O B O S T R I P P E R  💅✨👠 {R}")
        print(f"{MAGENTA}{'─' * 71}{R}")
        print("")

        # Skip content if header_only mode
        if header_only:
            return

        # Show full content
        print(f"         {PINK}Hey love!{R} {DIM}I'm your friendly neighborhood {R}{WHITE}RoboStripper!{R}")
        print("")
        print(f"  {DIM}I strip {R}{PINK}metadata{R}{DIM} from your PDFs so{R} {CYAN}RoboBraille{R} {DIM}and{R} {CYAN}screen readers{R} {R}")
        print(f"  {DIM}can read to you without interruptions on every page 🤩👌💯{R}")
        print("")
        print(f"                           {MAGENTA}· · · ✦ · · ·{R}")
        print("")
        print(f"                         {WHITE}What is{R} {PINK}metadata{R}?")
        print()
        print(f"  {DIM}That's the junk publishers slap on the top and bottom of every page:{R}")
        print(f"  {DIM}copyright stamps, URLs, timestamps, journal/book titles, and page{R}")
        print(f"  {DIM}numbers 😒😤{R}")
        print()
        print(f"                           {MAGENTA}· · · ✦ · · ·{R}")
        print()
        print(f"               {MAGENTA}🔥🔥🔥 No more interruptions! 🔥🔥🔥{R}")
        print()
        print(f"  {DIM}Just good, clean fun. Like a spa day but its homework 🥂🍾🏖️😎{R}")
        print("")
        print(f"  {DIM}Stripped files go to: {R}{CYAN}~/StrippedText/{R}")
        print(f"  {DIM}Upload the stripped files to: {R}{CYAN}robobraille.org{R}")
        print()
        print(f"  {DIM}To quit, type: {R}{EMERALD}quit{R}")

    else:
        # ═══════════════════════════════════════════════════════════
        # NORMIE PROFILE BANNER: DMV office energy - soul-crushing
        # ═══════════════════════════════════════════════════════════
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = f"RS{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Narrower banner for normie mode (50 columns to match separator lines)
        print(f"  ┌──────────────────────────────────────────────────┐")
        print(f"  │                                                  │")
        print(f"  │  🏢 👔 📁 R O B O S T R I P P E R  v{VERSION} 📁 👔 🏢  │")
        print(f"  │                                                  │")
        print(f"  │   Document Metadata Extraction and Removal       │")
        print(f"  │                                                  │")
        print(f"  └──────────────────────────────────────────────────┘")
        print("")
        print(f"  Session ID: {DIM}{session_id}{R}")
        print(f"  Timestamp:  {DIM}{timestamp}{R}")
        print(f"  Status:     {BOLD}{DIM}ACTIVE 🟢{R}")
        print("")
        print(f"  {DIM}──────────────────────────────────────────────────{R}")
        print("")

        # Skip content if header_only mode
        if header_only:
            return

        # Only show fluorescent lighting joke on first banner display
        if first_time:
            print(f"  Sorry, I can't concentrate without more fluorescent lighting.")
            print()
            gray_spinner(4.5, "📋 Submitting Form FL-001: Request for Fluorescent Lighting Adjustment...")
            gray_spinner(5.0, "⏳ Awaiting approval from Lighting Adjustment Supervisor...")
            gray_spinner(6.0, "🏢 Escalating to Lighting Adjustment Supervisor's Supervisor...")
            gray_spinner(5.5, "📊 Consulting corporate lighting policy manual (1,847 pages)...")
            gray_spinner(5.0, "💡 Adjusting fluorescent lighting levels by 0.003%...")
            gray_spinner(4.0, "📄 Completing mandatory post-adjustment documentation...")
            print()
            print(f"  {WHITE}Whew, much better. Ready when you are. Hit Enter to continue.{R}")
            # Pause after the fluorescent lighting joke so user can see nothing changed
            try:
                input(f"  {DIM}Press Enter to continue...{R}")
            except (EOFError, KeyboardInterrupt):
                pass

            # Clear screen and reprint the exact same banner (the joke!)
            print("\033[2J\033[H", end="")

            # Reprint banner after the joke (same narrow banner)
            print(f"  ┌──────────────────────────────────────────────────┐")
            print(f"  │                                                  │")
            print(f"  │  🏢 👔 📁 R O B O S T R I P P E R  v{VERSION} 📁 👔 🏢  │")
            print(f"  │                                                  │")
            print(f"  │   Document Metadata Extraction and Removal       │")
            print(f"  │                                                  │")
            print(f"  └──────────────────────────────────────────────────┘")
            print("")
            print(f"  Session ID: {DIM}{session_id}{R}")
            print(f"  Timestamp:  {DIM}{timestamp}{R}")
            print(f"  Status:     {BOLD}ACTIVE {R}")
            print("")
            print(f"  {DIM}──────────────────────────────────────────────────{R}")
            print("")

        # Main content (always shown)
        print(f"  {DIM}Despite my name, there will be no innuendo or silliness whatsoever.{R}")
        print()
        print(f"  NOTICE: {DIM}This application processes PDF documents to remove extraneous header and footer{R}")
        print(f"  {DIM}information for using {R}RoboBraille {DIM}and {R}screen readers{DIM}.{R}")
        print(f"  Compliance ID: {DIM}RS-2024-PROC-1847{R}")
        print(f"  License Type: {DIM}Standard Academic Use{R}")
        print("")
        print()
        print(f"  {WHITE}SYSTEM CONFIGURATION{R}")
        print(f"  {DIM}─────────────────────────────────────────────────────────────────────────────────────────{R}")
        print(f"    📄 Output Directory:    {DIM}StrippedText/{R}")
        print(f"    📊 Target Platform:     {DIM}robobraille.org{R}")
        print(f"    ✔️  Supported Formats:   {DIM}PDF (Portable Document Format){R}")
        print(f"    ⏳ Processing Mode:     {DIM}Normal{R}")
        print(f"    🟥 Exit Command:        {DIM}'{R}{BOLD}quit{DIM}' (red tape requires approval){R}")
        print("")
        print(f"  {WHITE}DISCLAIMER: {DIM}By using this software, you acknowledge that you have read and agree to the{R}")
        print(f"  {DIM}terms and conditions of having your soul stored in the void of despair, never to experience{R}")
        print(f"  {DIM}joy or color again. Consult your IT administrator for additional guidance.{R}")
        print()


    # Profile switcher option
    if CURRENT_PROFILE == "cunty":
        # CUNTY PROFILE: Playful hint about switching
        print(f'  {DIM}Type {R}{EMERALD}profile{R}{DIM} to input: "Help! This UX is {R}{EMERALD}*too cunty*{R}{DIM} for me!"{R}')
    else:
        # NORMIE PROFILE: Bureaucratic hint with form number
        print()
        print(f"  {WHITE}ADVANCED CONFIGURATION OPTIONS {DIM}(Form RS-CONFIG-002):{R}")
        print(f"  {DIM}─────────────────────────────────────────────────────────────────────────────────────────{R}")
        print(f"    ▪ Toggle UX Profile: {DIM}To reintroduce personality, input:'{BOLD}{WHITE}profile{R}{DIM}' (NOT RECOMMENDED){R}")
        print(f"    ▪ Processing time: {DIM}Shorter than usual{R}")
        print(f"    ▪ Approval required: {DIM}Minimal{R}")

    print()

    # In normie mode, scroll to top to show the banner (in GUI)
    if CURRENT_PROFILE == "normie":
        # Use ANSI code to move cursor to home position (top-left)
        # This signals the GUI to scroll to top
        print("\033[H", end="", flush=True)


def gray_spinner(duration: float, message: str = ""):
    """Show a gray, soul-crushing spinner for NORMIE mode delays.

    Prints message, waits for duration, then prints completion.
    No in-place animation to avoid GUI text wrapping issues.
    """
    import time
    import sys

    # Print the task message (persistent) with immediate flush
    print(f"  {DIM}⠿ {message}{R}", flush=True)
    sys.stdout.flush()  # Force immediate output in GUI

    # Wait for the duration (simulating work being done)
    time.sleep(duration)

    # Print completion with immediate flush
    print(f"  {DIM}  ✓ Complete{R}", flush=True)
    sys.stdout.flush()  # Force immediate output in GUI


def gray_spinner_with_task(task_func, message: str = ""):
    """Run a task in background while showing gray spinner (no added delay!)."""
    import time
    import threading

    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Run task in background thread
    result = [None]
    exception = [None]

    def run_task():
        try:
            result[0] = task_func()
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=run_task)
    thread.start()

    # Show spinner while task runs
    i = 0
    while thread.is_alive():
        char = spinner_chars[i % len(spinner_chars)]
        # Clear line, then print spinner
        print(f"\033[2K\r  {DIM}{char} {message}{R}", end="", flush=True)
        time.sleep(0.1)
        i += 1

    thread.join()

    # Clear spinner and show completion
    print(f"\033[2K\r  {DIM}✓ {message}{R}")

    # Re-raise exception if task failed
    if exception[0]:
        raise exception[0]

    return result[0]


def fade_to_boring():
    """Full-screen fade: drain color from entire interface when switching to normie."""
    import time
    import datetime

    # Gradual color fade through multiple full-screen frames
    frames = [
        ("\033[95m", "● Draining color from interface...", 1.5),
        ("\033[35m", "● Removing joy from user experience...", 1.5),
        ("\033[2m\033[95m", "● Extracting enthusiasm from system...", 1.2),
        ("\033[2m\033[35m", "● Neutralizing personality components...", 1.8),
        ("\033[90m", "● Converting to bleh mode...", 1.5),
        ("\033[2m\033[90m", "● Launching faceless bureaucracies...", 1.8),
        ("\033[2m", "● Initializing soul extraction protocol...", 2.0),
        ("\033[2m\033[90m", "● Finalizing transformation to void...", 1.5),
    ]

    for color, message, delay in frames:
        print("\033[2J\033[H", end="", flush=True)
        print("\n" * 10)
        print(f"  {color}{message}{R}", flush=True)
        time.sleep(delay)

    # Final completion screen
    print("\033[2J\033[H", end="", flush=True)
    print("\n" * 8)
    print(f"  Welcome, fellow coworker. Let's do paperwork until 5 PM. 🏢 👔 📁{R}")
    print(f"  ✓ NORMIE mode activated.{R}")
    print(f"  ✓ Soul successfully extracted and archived.{R}")
    print(f"  Reference Code: VOID-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{R}")
    print()

    # Pause so user can absorb the soul-crushing transition
    try:
        input(f"\033[2m  Press Enter to continue...{R}")
    except (EOFError, KeyboardInterrupt):
        pass

def switch_profile():
    """Switch between cunty and normie profiles with sass."""
    global CURRENT_PROFILE, P
    import time

    if CURRENT_PROFILE == "cunty":
        # ═══════════════════════════════════════════════════════════
        # CUNTY → NORMIE: Draining the fun away
        # ═══════════════════════════════════════════════════════════
        print()
        print(f"  {PINK}Gurl, sex work IS work 💅{R}")
        print(f"  Whatever. You do you, {BOLD}normie{R}.{R}")

        print()

        # Fade effect - colors drain away
        fade_to_boring()
        print()

        CURRENT_PROFILE = "normie"
        save_profile("normie")
        resize_terminal()  # Widen window for normie mode

    else:
        # ═══════════════════════════════════════════════════════════
        # NORMIE → CUNTY: Color and life rushing back in!
        # ═══════════════════════════════════════════════════════════
        print()
        print()
        print(f"  {BOLD}FINALLY.{R} Thank {BOLD}god 💅{R}")
        print()

        # Reverse fade - colors rushing back in (full screen transition)
        frames = [
            ("\033[2m\033[90m", "● Restoring color and personality...", 0.8),
            ("\033[2m", "● Reactivating joy protocols...", 0.8),
            ("\033[90m", "● Color emergence detected...", 0.7),
            ("\033[2m\033[35m", "● Personality restoration in progress...", 0.9),
            ("\033[35m", "● Enthusiasm levels rising...", 0.7),
            ("\033[2m\033[95m", "● Fabulous mode initializing...", 0.8),
            ("\033[95m", "● Maximum color achieved...", 0.7),
            ("\033[95m\033[1m", "● ✨ GLAMOUR RESTORED ✨", 1.0),
        ]

        for color, message, delay in frames:
            print("\033[2J\033[H", end="", flush=True)
            print("\n" * 10)
            print(f"  {color}{message}{R}", flush=True)
            time.sleep(delay)

        # Final celebration
        print("\033[2J\033[H", end="", flush=True)
        print("\n" * 10)
        print(f"  {MAGENTA}✨ Welcome back, babe! 💅{R}")
        print()

        # Pause so user can enjoy the moment
        try:
            input(f"  {DIM}Press Enter to continue...{R}")
        except (EOFError, KeyboardInterrupt):
            pass
        print()

        CURRENT_PROFILE = "cunty"
        save_profile("cunty")
        resize_terminal()  # Shrink window back for cunty mode

    P = PROFILES[CURRENT_PROFILE]

    # Clear screen and reprint banner
    # Show fluorescent joke if we just switched TO normie mode
    print("\033[2J\033[H", end="", flush=True)  # ANSI clear screen
    time.sleep(0.05)  # Brief pause to ensure clear completes
    show_fluorescent_joke = (CURRENT_PROFILE == "normie")
    print_banner(first_time=show_fluorescent_joke)


def pick_files(show_initial_banner=True, is_first_launch=True) -> list[Path]:
    """Prompt user to drag-and-drop PDF files into the terminal.

    Args:
        show_initial_banner: If False, skip the initial banner (e.g., after profile switch)
        is_first_launch: If True, show fluorescent joke in normie mode after cleanup
    """
    # Show banner for first time (or after profile switch)
    if show_initial_banner:
        print_banner(first_time=is_first_launch)
        check_cleanup()

    # Loop until we get valid files
    while True:

        if CURRENT_PROFILE == "cunty":
            # CUNTY PROFILE: Fun and friendly
            print(f"                           {MAGENTA}· · · ✦ · · ·{R}")
            print()
            print(f"      {EMERALD}Drag and drop{R} {WHITE}those files right here in my window, boo{R} 😘")
            print(f"          {WHITE}Then press {R}{EMERALD}Enter{R} {WHITE}and I'll take care of the rest {R}")
            print()
            print(f"  {DIM}Multiple files? No problem. I can take care of as many as you{R}")
            print(f"  {DIM}want. All at the same time{R}")
        else:
            # NORMIE PROFILE: DMV-style bureaucratic prompt
            print()
            print(f"  STEP 1: FILE INPUT{R}")
            print(f"  {DIM}─────────────────────────────────────────────────────────────────────────────────────────{R}")
            print(f"  {DIM}Please provide the full file path(s) to PDF document(s) requiring metadata extraction.{R}")
            print(f"  {DIM}Multiple files may be submitted simultaneously.{R}")
            print(f"")
            print(f"  {WHITE}INSTRUCTIONS:{R}")
            print(f"    {DIM}1. {R}Drag file(s){DIM} from system file browser into this terminal window{R}")
            print(f"    {DIM}2. {R}Press ENTER/RETURN key {DIM}to confirm submission{R}")
            print(f"  {R}")
            print(f"  NOTE: {DIM}Submitted files must be PDF format. Other formats will be rejected and returned to{R}")
            print(f"  {DIM}sender. Average processing time: 30 seconds to 8 weeks per file, subject to system load.{R}")
            print()
            print(f"  NOTICE: ⚠️ {DIM}EXPECT DELAYS ⚠️{R}")

        print()

        if CURRENT_PROFILE == "cunty":
            # CUNTY PROFILE: Fun and friendly
            try:
                raw = input(f"  {BOLD}>{R} ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n  {PINK}💋 Catch you later, boo!{R}\n{R}")
                sys.exit(0)
        else:
            # NORMIE PROFILE: DMV-style bureaucratic prompt
            try:
                raw = input(f"  {BOLD}>{R} ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n  Exiting. Goodbye.\n{R}")
                sys.exit(0)

        # Handle empty input - loop back instead of exiting
        if not raw:
            if CURRENT_PROFILE == "cunty":
                print(f"\n  {MAGENTA}No file? Try again, babe.{R}\n")
                try:
                    input(f"  {DIM}Press Enter to continue...{R}")
                except (EOFError, KeyboardInterrupt):
                    pass
            else:
                print(f"\n  {YELLOW}⚠️ ERROR: ⚠️ {R}{DIM}No input detected. Please provide a valid file path or command.{R}\n")
                try:
                    input(f"  {DIM}Press Enter to continue...{R}")
                except (EOFError, KeyboardInterrupt):
                    pass

            # Clear screen and show banner again (without fluorescent joke)
            print("\033[2J\033[H", end="")
            print_banner(first_time=False)
            continue  # Loop back to prompt

        # Check for quit command
        if raw.lower() in ('quit', 'exit', 'q'):
            print(f"\n  {P['goodbye']}\n{R}")
            if os.environ.get('ROBOSTRIPPER_GUI_MODE'):
                os._exit(0)  # Terminate entire process including GUI
            else:
                sys.exit(0)  # Normal exit for TUI

        # Check for profile switch command
        if raw.lower() == 'profile':
            if CURRENT_PROFILE == "cunty":
                # ═══════════════════════════════════════════════════════════
                # CUNTY PROFILE: User wants to switch to normie
                # ═══════════════════════════════════════════════════════════
                print("\033[2J\033[H", end="")
                print(f"                           {MAGENTA}· · · ✦ · · ·{R}")
                print(f"  {MAGENTA}CHANGE PROFILE?{R}")
                print(f"                           {MAGENTA}· · · ✦ · · ·{R}")
                print()
                print(f"  {CYAN}❝ Help! This UX is {R}{EMERALD}*too cunty*{R}{CYAN} for me.{R}")
                print(f"    {CYAN}Can't you be more professional? ❞{R}")
                new_profile_name = f"{BOLD}{DIM}NORMIE{R}"
            else:  # normie
                # ═══════════════════════════════════════════════════════════
                # NORMIE PROFILE: User wants to switch to cunty
                # ═══════════════════════════════════════════════════════════
                print(f"  {DIM}─────────────────────────────────────────────────────────────────────{R}")
                print(f"  CHANGE PROFILE")
                print(f"  {DIM}─────────────────────────────────────────────────────────────────────{R}")            
                print()
                print(f"  ❝ Gurl, can't you have a little more *personality* here? ❞{R}")
                new_profile_name = f"{BOLD}{MAGENTA}CUNTY{R}"

            print()
            try:
                answer = input(f"  {BOLD}Switch to {new_profile_name} mode? [Y/n]{R} ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = 'n'

            if answer in ('', 'y', 'yes'):
                switch_profile()
                return pick_files(show_initial_banner=False)  # Skip banner - already shown by switch animation
            else:
                print(f"\n  {DIM}Keeping current profile.{R}\n")
                # Clear screen and show banner again (without fluorescent joke)
                print("\033[2J\033[H", end="")
                print_banner(first_time=False)
                continue  # Loop back to prompt

        # Try to parse file paths
        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = [p.strip() for p in raw.replace("' '", "'\n'").replace('" "', '"\n"').split('\n')]
            parts = [p.strip("'\"") for p in parts]

        paths = []
        for p in parts:
            path = Path(p)
            if path.is_file() and path.suffix.lower() == '.pdf':
                paths.append(path)
            elif path.is_file():
                print(f"    {DIM}Skipping non-PDF: {path.name}{R}")
            else:
                print(f"    {YELLOW}Not found: {p}{R}")

        # If no valid paths found, show error and loop back
        if not paths:
            if CURRENT_PROFILE == "cunty":
                print(f"\n  {YELLOW}Hmm, I didn't find any valid PDF files there, babe. 😕 Try again?{R}\n")
            else:
                print(f"\n  {YELLOW}⚠️ ERROR: No valid PDF files provided. Please check file paths and try again.{R}\n")

            # Clear screen and show banner again (without fluorescent joke)
            print("\033[2J\033[H", end="")
            print_banner(first_time=False)
            continue  # Loop back to prompt

        # Valid files found - return them!
        return paths


def process_file(input_path: Path, output_path: Optional[Path], preview: bool, faithful: bool, verbose: bool) -> Optional[Path]:
    """Process a single PDF file."""
    import time
    import datetime

    if CURRENT_PROFILE == "cunty":
        # CUNTY PROFILE: Fun and quick
        print(f"  {BOLD}{PINK}💅 Stripping {R}{R}your docs... {input_path.name}{R}")
        pages = extract_text(input_path)
    else:
        # NORMIE PROFILE: Soul-crushing bureaucratic process
        print(f"  ─────────────────────────────────────────────────────────────────────{R}")
        print(f" {BOLD}PROCESSING REQUEST{R}")
        print(f"  File: {DIM}{input_path.name}{R}")
        print(f"  Timestamp: {DIM}{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{R}")
        print(f"  Status: {DIM}QUEUED ⏳{R}")
        print()
        print(f"  Please wait while your request is processed... 👔{R}")
        print()
        gray_spinner(0.5, "📄 Validating file format...")
        gray_spinner(0.3, "🏢 Allocating system resources...")
        gray_spinner(0.2, "📉 Enhancing work-appropriate grayscales...")
        gray_spinner(0.5, "📁 Submitting paperwork...")


        # Run actual extraction with spinner (no extra delay!)
        pages = gray_spinner_with_task(
            lambda: extract_text(input_path),
            "📝 Extracting text from PDF document..."
        )
    if not pages:
        if CURRENT_PROFILE == "cunty":
            print(f"    ⚠️ {YELLOW}No text extracted from {input_path.name}{R} ⚠️", file=sys.stderr)
        else:
            print(f"    {BOLD}⚠️ ERROR: {R}⚠️{DIM}Text extraction failed (Code: ERR-EXTRACT-001){R}")
            print(f"    File: {DIM}{input_path.name}{R}", file=sys.stderr)
        return None

    # Extract citation info from raw pages BEFORE cleaning
    if CURRENT_PROFILE == "normie":
        citation = gray_spinner_with_task(
            lambda: extract_citation(input_path, pages),
            "📋 Extracting citation metadata..."
        )
    else:
        citation = extract_citation(input_path, pages)

    citation_header = format_citation_header(citation)

    # Clean the document
    if CURRENT_PROFILE == "normie":
        cleaned_text = gray_spinner_with_task(
            lambda: clean_document(pages),
            "📊 Removing metadata and cleaning document..."
        )
    else:
        cleaned_text = clean_document(pages)
    if not cleaned_text:
        if CURRENT_PROFILE == "cunty":
            print(f"    {YELLOW}No text remaining after cleaning {input_path.name}{R}", file=sys.stderr)
        else:
            print(f"    {DIM}ERROR: Document cleaning resulted in empty output (Code: ERR-CLEAN-001){R}")
            print(f"    {DIM}File: {input_path.name}{R}", file=sys.stderr)
        return None

    formatted_text = format_for_tts(cleaned_text, faithful=faithful)

    # Prepend citation header (sanitize special chars in title/author too)
    if citation_header:
        formatted_text = sanitize_for_tts(citation_header) + formatted_text

    if preview:
        print("\n" + "="*80)
        print(formatted_text)
        print("="*80 + "\n")
        return None

    if output_path is None:
        output_dir = get_output_dir()
        output_path = output_dir / (input_path.stem + "_stripped.txt")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(formatted_text, encoding='utf-8')

        if CURRENT_PROFILE == "cunty":
            # CUNTY PROFILE: Celebratory!
            print(f"     {GREEN}✨ {output_path.name}{R} {DIM}({len(pages)} pages){R}")
        else:
            # NORMIE PROFILE: Bureaucratic confirmation
            print()
            gray_spinner(0.6, "⏳ Processing metadata extraction...")
            gray_spinner(0.6, "📄 Generating output file...")
            gray_spinner(0.6, "📝 Finalizing document...")
            gray_spinner(0.5, "🟥 Applying red tape protocols...")
            gray_spinner(0.4, "📊 Compiling statistical reports...")
            gray_spinner(0.4, "📊 Readjusting fluorescent lights...")
            print()
            print(f"  ✔️ PROCESSING COMPLETE 😩💥📉{R}")
            print(f"  Output: {DIM}{output_path.name}{R}")
            print(f"  Pages processed: {DIM}{len(pages)}{R}")
            print(f"  Status: {DIM}SUCCESSFUL (satisfactory completion achieved){R}")
            ref_code = f"PROC-{datetime.datetime.now().strftime('%H%M%S')}"
            print(f"  Reference: {DIM}{ref_code} 🏢{R}")
            print(f"  {DIM}Please retain this reference number for your records.{R}")
            print(f"  {DIM}It serves as a unique identifier with no purpose whatsoever.{R}")

            print()

        return output_path
    except Exception as e:
        if CURRENT_PROFILE == "cunty":
            print(f"    Oh no, babe, I hit an {YELLOW}error! {DIM}Writing {output_path}: {e} failed{R}", file=sys.stderr)
        else:
            print(f"    ⚠️ {BOLD}ERROR: ⚠️{R} {DIM}File write operation failed (Code: ERR-WRITE-001){R}")
            print(f"    Output path: {DIM}{output_path}{R}")
            print(f"    Details: {DIM}{e}{R}", file=sys.stderr)
        return None


def print_summary(output_files: list[Path], args):
    """Print results and offer to open RoboBraille (profile-aware)."""
    import datetime
    if not output_files:
        return

    n = len(output_files)
    print()

    if CURRENT_PROFILE == "cunty":
        # CUNTY PROFILE: Celebratory summary
        print(f"  {MAGENTA}┌─────────────────────────────────────────────────┐{R}")
        print(f"  {MAGENTA}│{R}  {GREEN}✨ {n} file{'s' if n != 1 else ' '} stripped clean!{R}                     {MAGENTA}│{R}")
        print(f"  {MAGENTA}└─────────────────────────────────────────────────┘{R}")
        print()
        for f in output_files:
            print(f"    {CYAN}📄{R} {f.name}{R}")
        print()
        print(f"    {DIM}Saved in:{R} {CYAN}{output_files[0].parent}{R}")
    else:
        # NORMIE PROFILE: Soul-crushing bureaucratic summary
        print(f"  {DIM}══════════════════════════════════════════════════{R}")
        print(f"  📊 BATCH PROCESSING SUMMARY 📋{R}")
        print(f"  {DIM}══════════════════════════════════════════════════{R}")
        print()
        print(f"  Session completed: {DIM}{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ⏳{R}")
        print(f"  Total files processed:{DIM} {n} 📄{R}")
        print(f"  Employee engagement: {DIM}23% 📉{R}")
        print(f"  Fluorescent lighting: {DIM}Adequate 💡{R}")
        print(f"  Output directory: {DIM}{output_files[0].parent} 🏢{R}")
        print()
        print(f"  FILES GENERATED: 📝{R}")
        for i, f in enumerate(output_files, 1):
            print(f"    ✔️ {i}. {DIM}{f.name}{R}")
        print()
        print(f"  🟥 IMPORTANT NOTICE (Red Tape Alert):{R}")
        print(f"  {DIM}All output files have been saved to the designated output directory.{R}")
        print(f"  {DIM}Please verify file integrity before proceeding to next steps.{R}")
        print(f"  {DIM}Files must be retained for a minimum of 30 calendar days for{R}")
        print(f"  {DIM}compliance purposes. Failure to comply may result in processing{R}")
        print(f"  {DIM}delays for future requests. 👔{R}")
        print()

    filename = output_files[0].name

    if CURRENT_PROFILE == "cunty":
        # CUNTY PROFILE: Helpful and friendly
        if copy_to_clipboard(filename):
            print(f"\n    {GREEN}📋 \"{filename}\" copied to clipboard{R}")
            print(f"    {DIM}Paste into the search bar in RoboBraille's file picker{R}")

        if not args.no_open and not args.preview:
            print()
            print(f"  {MAGENTA}─────────────────────────────────────────────────{R}")
            print()
            print(f"  {PINK}Next up — upload to RoboBraille:{R}")
            print(f"    {CYAN}1.{R} Click 'Upload' on robobraille.org{R}")
            print(f"    {CYAN}2.{R} Search for the filename ({BOLD}Cmd+V{R} to paste){R}")
            print(f"    {CYAN}3.{R} Pick a voice & hit convert 🎤{R}")
            print()
            try:
                answer = input(f"  {BOLD}Open RoboBraille? [Y/n]{R} ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = 'n'
            if answer in ('', 'y', 'yes'):
                print(f"\n  {MAGENTA}💋 Go get 'em.{R}\n{R}")
                webbrowser.open("https://www.robobraille.org")
            else:
                print(f"\n  {PINK}👠 Standing by. You know where to find me.{R}\n{R}")
    else:
        # NORMIE PROFILE: Soulless bureaucratic next steps
        if copy_to_clipboard(filename):
            print(f"  ✓ First filename copied to system clipboard: {filename}{R}")
            print(f"    (For use in file selection dialogs){R}")
            print()

        if not args.no_open and not args.preview:
            print(f"  {DIM}─────────────────────────────────────────────────────────────────────{R}")
            print(f"  NEXT STEPS - EXTERNAL PROCESSING REQUIRED{R}")
            print(f"  {DIM}─────────────────────────────────────────────────────────────────────{R}")
            print()
            print(f"  {DIM}To complete the document processing workflow, you must now submit{R}")
            print(f"  {DIM}the generated output file(s) to the RoboBraille platform for audio{R}")
            print(f"  {DIM}conversion. Please follow the steps below:{R}")
            print()
            print(f"  STEP 1: {DIM}Navigate to https://www.robobraille.org{R}")
            print(f"  STEP 2: {DIM}Locate and click the 'Upload' button{R}")
            print(f"  STEP 3: {DIM}In the file selection dialog, paste the filename{R}")
            print(f"          {DIM}(Use keyboard shortcut: Cmd+V on Mac, Ctrl+V on Windows){R}")
            print(f"  STEP 4: {DIM}Select desired voice and audio format parameters{R}")
            print(f"  STEP 5: {DIM}Initiate conversion process{R}")
            print()
            print(f"  NOTE: {DIM}Average processing time on RoboBraille platform: 3-7 minutes{R}")
            print(f"  {DIM}per document, subject to server load and queue length.{R}")
            print()
            try:
                answer = input(f"  Launch RoboBraille website in default browser? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = 'n'
            if answer in ('', 'y', 'yes'):
                print()
                print(f"  ✓ Opening https://www.robobraille.org in browser...{R}")
                print(f"  Please proceed with upload process as outlined above.{R}")
                print()
                webbrowser.open("https://www.robobraille.org")
            else:
                print()
                print(f"  ✓ Browser launch cancelled.{R}")
                print(f"  You may manually navigate to https://www.robobraille.org{R}")
                print(f"  at your inconvenience.{R}")
                print()
        else:
            print()


# ── Auto-update ──────────────────────────────────────────────────────────────

def check_version_tag_sync():
    """
    Development safety check: warn if VERSION in code doesn't match latest git tag.
    Only runs when NOT frozen (not in .app/.exe builds) and git repo exists.
    """
    # Skip if running as binary
    if getattr(sys, 'frozen', False):
        return

    # Skip if not in a git repo
    if not (SCRIPT_DIR / '.git').exists():
        return

    try:
        # Get latest git tag
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=2
        )

        if result.returncode == 0:
            latest_tag = result.stdout.strip().lstrip('v')
            if latest_tag and latest_tag != VERSION:
                print()
                print(f"  {YELLOW}⚠️  Version mismatch detected:{R}")
                print(f"    {DIM}Git tag:{R}     {BOLD}{latest_tag}{R}")
                print(f"    {DIM}CODE VERSION:{R} {BOLD}{VERSION}{R}")
                print(f"  {DIM}Did you forget to bump VERSION after tagging?{R}")
                print()

    except Exception:
        # Silent fail - this is just a development helper
        pass


def check_for_updates(github_user: str = "june-alice-blue", repo: str = "RoboStripper"):
    """
    Check GitHub releases for updates. Non-blocking, silent on errors.
    If newer version found:
      - Python script users: offer to auto-download and replace
      - Binary (.app/.exe) users: open download page
    """
    try:
        url = f"https://api.github.com/repos/{github_user}/{repo}/releases/latest"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")

        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())

        latest_version = data.get("tag_name", "").lstrip("v")
        release_url = data.get("html_url", "")
        release_notes = data.get("body", "")

        if not latest_version:
            return

        # Compare versions (simple string comparison works for semver)
        if latest_version > VERSION:
            if CURRENT_PROFILE == "cunty":
                # CUNTY PROFILE: Exciting update notification
                print()
                print(f"  {MAGENTA}┌─────────────────────────────────────────────────┐{R}")
                print(f"  {MAGENTA}│{R}  {PINK}✨ Update available!{R} ✨                           {MAGENTA}│{R}")
                print(f"  {MAGENTA}└─────────────────────────────────────────────────┘{R}")
                print()
                print(f"    {DIM}Current version:{R} {BOLD}{VERSION}{R}")
                print(f"    {DIM}Latest version:{R}  {GREEN}{BOLD}{latest_version}{R}")

                # Show release notes if available (first line only)
                if release_notes:
                    first_line = release_notes.split('\n')[0].strip()
                    if first_line and len(first_line) < 60:
                        print(f"    {DIM}What's new:{R} {first_line}{R}")
                print()
            else:
                # NORMIE PROFILE: Bureaucratic update notification
                import datetime
                session_id = f"UPD-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
                print()
                print(f"  📊 SOFTWARE UPDATE NOTIFICATION{R}")
                print(f"  {DIM}─────────────────────────────────────────────────────────────────────{R}")
                print(f"  Session ID: {DIM}{session_id}{R}")
                print(f"  Form: {DIM}UPDATE-CHECK-001{R}")
                print()
                print(f"  {DIM}A mandatory software update has been detected in the central{R}")
                print(f"  {DIM}repository. Your current installation version does not match{R}")
                print(f"  {DIM}the most recent release available for download.{R}")
                print()
                print(f"  Current installation version: {VERSION}{R}")
                print(f"  Available version:            {latest_version}{R}")
                print()

                # Show release notes if available
                if release_notes:
                    first_line = release_notes.split('\n')[0].strip()
                    if first_line and len(first_line) < 80:
                        print(f"  Update description: {DIM}{first_line}{R}")
                        print()

                print(f"  {DIM}⏳ Please note: Continuing with an outdated version may result{R}")
                print(f"  {DIM}in suboptimal performance and/or feature incompatibility.{R}")
                print()

            is_frozen = getattr(sys, 'frozen', False)

            if is_frozen:
                # Running as .app or .exe — can't auto-update, open download page
                if CURRENT_PROFILE == "cunty":
                    try:
                        answer = input(f"  {BOLD}Open the download page? [Y/n]{R} ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        answer = 'n'

                    if answer in ('', 'y', 'yes'):
                        webbrowser.open(release_url)
                        print(f"\n  {GREEN}We have updates! Download the latest version, boo 💋{R}\n{R}")
                    else:
                        print(f"\n  {PINK}Noted. Carrying on with {VERSION}{R} 💅\n{R}")
                else:
                    # NORMIE PROFILE
                    try:
                        answer = input(f"  Download updated version from website? [Y/n] ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        answer = 'n'

                    if answer in ('', 'y', 'yes'):
                        gray_spinner(0.4, "Preparing to launch browser...")
                        webbrowser.open(release_url)
                        print()
                        print(f"  ✔️ Browser launched. Please download the installation package{R}")
                        print(f"  from the releases page and follow standard installation{R}")
                        print(f"  procedures for your operating system.{R}")
                        print()
                    else:
                        print()
                        print(f"  ✔️ Acknowledged. Continuing with current version {VERSION}.{R}")
                        print(f"  You may update at a later time by re-running this check.{R}")
                        print()

            else:
                # Running as Python script — can auto-update
                if CURRENT_PROFILE == "cunty":
                    try:
                        answer = input(f"  {BOLD}Auto-update now? [Y/n]{R} ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        answer = 'n'
                else:
                    # NORMIE PROFILE
                    try:
                        answer = input(f"  Install update automatically? [Y/n] ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        answer = 'n'

                if answer in ('', 'y', 'yes'):
                    if CURRENT_PROFILE == "normie":
                        gray_spinner(0.5, "📄 Initiating download from remote repository...")

                    # Download new robostripper.py
                    script_url = f"https://github.com/{github_user}/{repo}/releases/download/v{latest_version}/robostripper.py"

                    # Try release asset first, fall back to raw from repo
                    try:
                        req = urllib.request.Request(script_url)
                        with urllib.request.urlopen(req, timeout=10) as response:
                            new_script = response.read()
                    except Exception:
                        # Fall back to downloading from main branch
                        raw_url = f"https://raw.githubusercontent.com/{github_user}/{repo}/v{latest_version}/robostripper.py"
                        req = urllib.request.Request(raw_url)
                        with urllib.request.urlopen(req, timeout=10) as response:
                            new_script = response.read()

                    if CURRENT_PROFILE == "normie":
                        gray_spinner(0.3, "📝 Verifying file integrity...")
                        gray_spinner(0.4, "💾 Creating backup of current version...")

                    # Backup current version
                    script_path = Path(__file__).resolve()
                    backup_path = script_path.with_suffix('.py.backup')
                    shutil.copy2(script_path, backup_path)

                    if CURRENT_PROFILE == "normie":
                        gray_spinner(0.5, "📊 Installing updated version...")

                    # Write new version
                    script_path.write_bytes(new_script)

                    if CURRENT_PROFILE == "cunty":
                        print(f"\n  {GREEN}✓ Updated to {latest_version}!{R}")
                        print(f"  {DIM}Backup saved:{R} {backup_path.name}{R}")
                        print(f"\n  👠 {PINK}Restart RoboStripper to use the new version 👠{R}\n{R}")
                    else:
                        # NORMIE PROFILE
                        print()
                        print(f"  ✔️ UPDATE INSTALLATION COMPLETED 😩📑💥📉{R}")
                        print()
                        print(f"  Updated version: {latest_version}{R}")
                        print(f"  Backup file:     {backup_path.name}{R}")
                        print()
                        print(f"  {DIM}⏳ IMPORTANT: You must now restart this application to{R}")
                        print(f"  {DIM}activate the updated version. Failure to restart may{R}")
                        print(f"  {DIM}result in continued use of the outdated software.{R}")
                        print()
                        print(f"  Please close this window and launch the application again. 🏢{R}")
                        print()

                    # Exit so user restarts with new version
                    sys.exit(0)
                else:
                    if CURRENT_PROFILE == "cunty":
                        print(f"\n  {PINK}Noted. Carrying on with {VERSION}{R} 💅\n{R}")
                    else:
                        # NORMIE PROFILE
                        print()
                        print(f"  ✔️ Update declined. Continuing with version {VERSION}.{R}")
                        print(f"  {DIM}You may update at a later time by manually checking for updates.{R}")
                        print()

    except Exception:
        # Silently fail — don't interrupt workflow if no internet, API down, etc.
        pass


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # In GUI mode, dep check was deferred from import time to here
    # (so stdin/stdout are already redirected to the terminal widget)
    global fitz, OCR_AVAILABLE, TESSERACT_INSTALLED
    if os.environ.get('ROBOSTRIPPER_GUI_MODE'):
        check_and_install_deps()
        # Re-import deps that may have just been installed
        if fitz is None:
            import fitz  # noqa: F811
        try:
            import pytesseract  # noqa: F811
            from PIL import Image  # noqa: F811
            TESSERACT_INSTALLED = check_tesseract()
            OCR_AVAILABLE = TESSERACT_INSTALLED
        except ImportError:
            OCR_AVAILABLE = False
            TESSERACT_INSTALLED = False

    parser = argparse.ArgumentParser(
        description="RoboStripper 👠✨💅 — strip metadata from scholarly PDFs for RoboBraille",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                               # interactive mode
  %(prog)s input.pdf                     # single file
  %(prog)s PDFs/                         # batch directory
  %(prog)s input.pdf --preview           # preview to stdout
  %(prog)s --clean                       # clear output folder
        """
    )

    parser.add_argument('input', nargs='?', type=Path, default=None,
                        help='PDF file or directory (interactive mode if omitted)')
    parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    parser.add_argument('--preview', action='store_true', help='Print cleaned text to stdout')
    parser.add_argument('--faithful', action='store_true', help='Skip TTS abbreviation replacements')
    parser.add_argument('--no-open', action='store_true', help='Skip RoboBraille prompt')
    parser.add_argument('--clean', action='store_true', help='Clear the output folder and exit')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed progress')

    args = parser.parse_args()

    # Development safety check: warn if VERSION and git tags are out of sync
    check_version_tag_sync()

    # Check for updates (non-blocking, silent on errors)
    check_for_updates()

    # --clean: wipe output folder and exit
    if args.clean:
        if OUTPUT_DIR.exists():
            txt_files = list(OUTPUT_DIR.glob("*.txt"))
            if txt_files:
                for f in txt_files:
                    f.unlink()
                print(f"  {GREEN}✓ Cleared {len(txt_files)} file{'s' if len(txt_files) != 1 else ''} from {OUTPUT_DIR.name}/{R}")
            else:
                print(f"  {DIM}Output folder is already empty.{R}")
        else:
            print(f"  {DIM}Nothing to clean — output folder doesn't exist yet.{R}")
        return

    output_files = []

    # Interactive mode - loop back to menu after processing
    if args.input is None:
        first_iteration = True
        while True:
            # Pick files (show initial banner only on first iteration)
            pdf_files = pick_files(show_initial_banner=first_iteration, is_first_launch=first_iteration)
            first_iteration = False  # Subsequent iterations skip initial banner setup

            # Clear screen for clean processing view
            clear_screen()

            # Show minimal header for context
            if CURRENT_PROFILE == "cunty":
                print(f"{MAGENTA}{'─' * 71}{R}")
                print(f"{BOLD}{MAGENTA}              👠✨💅  R O B O S T R I P P E R  💅✨👠 {R}")
                print(f"{MAGENTA}{'─' * 71}{R}")
            else:
                print(f"  ┌───────────────────────────────────────────────────────────────────────────────────────┐")
                print(f"  │               {BOLD}🏢 👔 📁 R O B O S T R I P P E R  v{VERSION} 📁 👔 🏢{R}                       │")
                print(f"  └───────────────────────────────────────────────────────────────────────────────────────┘")

            n = len(pdf_files)
            print(f"\n  {MAGENTA}👠{R} {n} file{'s' if n != 1 else ''} on the stage. {BOLD}Let's work.{R} 👠\n{R}")

            output_files = []
            for pdf_path in pdf_files:
                result = process_file(pdf_path, None, args.preview, args.faithful, args.verbose)
                if result:
                    output_files.append(result)

            # Show summary
            print_summary(output_files, args)

            # Prompt to continue or quit
            print()
            if CURRENT_PROFILE == "cunty":
                print(f"  {MAGENTA}· · · ✦ · · ·{R}")
            else:
                print(f"  {DIM}─────────────────────────────────────────────────{R}")
            print()

            try:
                response = input(f"  {DIM}Press Enter to continue (or type 'quit')...{R} ").strip().lower()
                if response in ('quit', 'exit', 'q'):
                    print(f"\n  {P['goodbye']}\n{R}")
                    if os.environ.get('ROBOSTRIPPER_GUI_MODE'):
                        os._exit(0)  # Close GUI window
                    else:
                        sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                print(f"\n  {P['goodbye']}\n{R}")
                if os.environ.get('ROBOSTRIPPER_GUI_MODE'):
                    os._exit(0)
                else:
                    sys.exit(0)

            # Clear screen and return to main menu
            clear_and_show_header()

    # Single file
    elif args.input.is_file():
        if args.input.suffix.lower() != '.pdf':
            print(f"  {YELLOW}Error: Not a PDF: {args.input}{R}", file=sys.stderr)
            sys.exit(1)

        output_path = args.output
        if output_path and output_path.is_dir():
            output_path = output_path / (args.input.stem + "_stripped.txt")

        result = process_file(args.input, output_path, args.preview, args.faithful, args.verbose)
        if result:
            output_files.append(result)

    # Directory
    elif args.input.is_dir():
        pdf_files = sorted(args.input.glob('*.pdf'))
        if not pdf_files:
            print(f"  {YELLOW}No PDF files found in {args.input}{R}", file=sys.stderr)
            sys.exit(1)

        print(f"  {MAGENTA}👠{R} {len(pdf_files)} files. {BOLD}Let's work.{R}\n{R}")

        output_dir = args.output
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

        for pdf_path in pdf_files:
            out = output_dir / (pdf_path.stem + "_stripped.txt") if output_dir else None
            result = process_file(pdf_path, out, args.preview, args.faithful, args.verbose)
            if result:
                output_files.append(result)

    else:
        if not args.input.exists():
            print(f"  {YELLOW}Error: Path not found: {args.input}{R}", file=sys.stderr)
        else:
            print(f"  {YELLOW}Error: Not a file or directory: {args.input}{R}", file=sys.stderr)
        sys.exit(1)

    print_summary(output_files, args)


if __name__ == '__main__':
    main()
