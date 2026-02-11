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
import os
import re
import shlex
import subprocess
import shutil
import sys
import webbrowser
from pathlib import Path
from collections import Counter
from typing import Optional


# ── ANSI Colors ──────────────────────────────────────────────────────────────

def _supports_color():
    """Check if terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if sys.platform == "win32":
        return os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM")
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_color()

MAGENTA = "\033[95m" if USE_COLOR else ""
PINK = "\033[35m" if USE_COLOR else ""
CYAN = "\033[96m" if USE_COLOR else ""
YELLOW = "\033[93m" if USE_COLOR else ""
GREEN = "\033[92m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""
R = "\033[0m" if USE_COLOR else ""

# Output directory — lives next to this script
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"


# ── Dependency Check & Auto-Install ──────────────────────────────────────────

def check_and_install_deps():
    """Check for required packages and offer to install them."""
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

    print()
    print(f"  {MAGENTA}{BOLD}📦 First-time setup{R}")
    print()
    print(f"  {PINK}RoboStripper needs a few packages to work:{R}")
    for pkg in missing:
        print(f"    {DIM}•{R} {pkg}")
    print()

    try:
        answer = input(f"  {BOLD}Install them now? [Y/n]{R} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Okay, maybe next time. 👠")
        sys.exit(0)

    if answer not in ('', 'y', 'yes'):
        print(f"\n  {DIM}No worries. Install manually with:{R}")
        print(f"    pip install {' '.join(missing)}")
        sys.exit(1)

    print()
    print(f"  {CYAN}Installing...{R}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing,
            stdout=subprocess.DEVNULL if not sys.stdout.isatty() else None,
        )
    except subprocess.CalledProcessError:
        print(f"\n  {YELLOW}pip install failed. Try running manually:{R}")
        print(f"    pip install {' '.join(missing)}")
        sys.exit(1)

    print(f"  {GREEN}✓ Installed!{R}\n")


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


# Run dependency check before importing
check_and_install_deps()

import fitz  # pymupdf  # noqa: E402

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
    ("standalone_page_num", re.compile(r"^\s*\d{1,4}\s*$"), "line"),
    ("standalone_url", re.compile(r"^\s*https?://\S+\s*$"), "line"),
    ("creative_commons_line", re.compile(r"Creative Commons Attribution.+License"), "line"),
    ("rights_reserved", re.compile(r"^\s*©\s*\d{4}.+All rights reserved\.?\s*$"), "line"),
]


# ── Core Functions ───────────────────────────────────────────────────────────

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


def extract_text(pdf_path: Path) -> list[str]:
    """Extract text from PDF, with OCR fallback for scanned pages."""
    pages = []
    ocr_pages = []

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"    {YELLOW}Error opening {pdf_path}: {e}{R}", file=sys.stderr)
        return []

    total = len(doc)
    for page_num in range(total):
        page = doc[page_num]
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
                    print(f"    {DIM}OCR failed p.{page_num + 1}: {e}{R}", file=sys.stderr)
            elif not TESSERACT_INSTALLED:
                # Silently note — we'll report at the end
                ocr_pages.append(page_num + 1)

        pages.append(text)

    doc.close()

    # Report OCR usage
    if ocr_pages and OCR_AVAILABLE:
        print(f"    {DIM}🔍 Used OCR on {len(ocr_pages)} scanned page{'s' if len(ocr_pages) != 1 else ''}{R}")
    elif ocr_pages and not OCR_AVAILABLE:
        print(f"    {YELLOW}⚠ {len(ocr_pages)} page{'s look' if len(ocr_pages) != 1 else ' looks'} scanned but OCR isn't available{R}")
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


def clean_document(pages: list[str]) -> str:
    """Clean entire document."""
    if not pages:
        return ""

    front_matter_count = detect_front_matter_pages(pages)
    pages = pages[front_matter_count:]
    if not pages:
        return ""

    repeating_lines = detect_repeating_lines(pages)
    cleaned_pages = [clean_page(page, repeating_lines) for page in pages]
    text = '\n\n'.join(cleaned_pages)

    # Fix hyphenation
    text = re.sub(
        r'(\w+)-\n(\w+)',
        lambda m: m.group(1) + m.group(2) if m.group(2)[0].islower() else m.group(0),
        text
    )
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def format_for_tts(text: str, faithful: bool = False) -> str:
    """Format text for TTS-friendly reading."""
    lines = text.split('\n')
    formatted_lines = []

    for line in lines:
        stripped = line.strip()
        is_heading = False
        if stripped and len(stripped) < 100:
            if stripped.isupper() or (stripped[0].isupper() and sum(1 for c in stripped if c.isupper()) > len(stripped) * 0.3):
                if stripped[-1] not in '.!?:;,':
                    is_heading = True

        if is_heading:
            formatted_lines.append('')
            formatted_lines.append(stripped + '.')
            formatted_lines.append('')
        else:
            formatted_lines.append(line)

    text = '\n'.join(formatted_lines)

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
    """If output directory has old files, offer to clean up."""
    if not OUTPUT_DIR.exists():
        return

    txt_files = list(OUTPUT_DIR.glob("*.txt"))
    if not txt_files:
        return

    n = len(txt_files)
    print(f"  {CYAN}📁 Output folder has {n} file{'s' if n != 1 else ''} from before.{R}")

    try:
        answer = input(f"     {BOLD}Clear them out? [y/N]{R} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = 'n'

    if answer in ('y', 'yes'):
        for f in txt_files:
            f.unlink()
        print(f"     {GREEN}✓ Cleared!{R}")
    else:
        print(f"     {DIM}Keeping them. New files will be added alongside.{R}")
    print()


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


def print_banner():
    """Print the welcome banner."""
    print()
    print(f"  {MAGENTA}┌─────────────────────────────────────────────────┐{R}")
    print(f"  {MAGENTA}│{R}  {BOLD}{MAGENTA}👠✨💅  R O B O S T R I P P E R  💅✨👠{R}       {MAGENTA}│{R}")
    print(f"  {MAGENTA}└─────────────────────────────────────────────────┘{R}")
    print()
    print(f"  {PINK}Hey love!{R} I strip the stuff that shouldn't be")
    print(f"  there — copyright stamps, download timestamps,")
    print(f"  platform junk — so RoboBraille reads your articles")
    print(f"  clean. No clutter, no interruptions, just vibes.")
    print()
    print(f"  {DIM}Cleaned files go to:{R} {CYAN}output/{R}")
    print()


def pick_files() -> list[Path]:
    """Prompt user to drag-and-drop PDF files into the terminal."""
    print_banner()

    # Check for old output files
    check_cleanup()

    print(f"  {MAGENTA}─────────────────────────────────────────────────{R}")
    print()
    print(f"  {CYAN}📂 Drag PDFs from Finder into this window,{R}")
    print(f"     then press Enter.")
    print(f"     {DIM}(Multiple files OK — toss them all in.){R}")
    print()

    try:
        raw = input(f"  {BOLD}>{R} ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        sys.exit(0)

    if not raw:
        print(f"  {DIM}Nothing? Okay, I'll be here when you're ready. 👠{R}")
        sys.exit(0)

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

    if not paths:
        print(f"  {YELLOW}No valid PDF files provided.{R}")
        sys.exit(1)

    return paths


def process_file(input_path: Path, output_path: Optional[Path], preview: bool, faithful: bool, verbose: bool) -> Optional[Path]:
    """Process a single PDF file."""
    print(f"  {PINK}💅 Stripping{R} {input_path.name}...")

    pages = extract_text(input_path)
    if not pages:
        print(f"    {YELLOW}No text extracted from {input_path.name}{R}", file=sys.stderr)
        return None

    cleaned_text = clean_document(pages)
    if not cleaned_text:
        print(f"    {YELLOW}No text remaining after cleaning {input_path.name}{R}", file=sys.stderr)
        return None

    formatted_text = format_for_tts(cleaned_text, faithful=faithful)

    if preview:
        print("\n" + "="*80)
        print(formatted_text)
        print("="*80 + "\n")
        return None

    if output_path is None:
        output_dir = get_output_dir()
        output_path = output_dir / (input_path.stem + "_clean.txt")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(formatted_text, encoding='utf-8')
        print(f"     {GREEN}✨ {output_path.name}{R} {DIM}({len(pages)} pages){R}")
        return output_path
    except Exception as e:
        print(f"    {YELLOW}Error writing {output_path}: {e}{R}", file=sys.stderr)
        return None


def print_summary(output_files: list[Path], args):
    """Print results and offer to open RoboBraille."""
    if not output_files:
        return

    n = len(output_files)
    print()
    print(f"  {MAGENTA}┌─────────────────────────────────────────────────┐{R}")
    print(f"  {MAGENTA}│{R}  {GREEN}✨ {n} file{'s' if n != 1 else ' '} stripped clean!{R}                       {MAGENTA}│{R}")
    print(f"  {MAGENTA}└─────────────────────────────────────────────────┘{R}")
    print()
    for f in output_files:
        print(f"    {CYAN}📄{R} {f.name}")
    print()
    print(f"    {DIM}Saved in:{R} {CYAN}{output_files[0].parent}{R}")

    filename = output_files[0].name
    if copy_to_clipboard(filename):
        print(f"\n    {GREEN}📋 \"{filename}\" copied to clipboard{R}")
        print(f"       {DIM}Paste into the search bar in the file picker{R}")

    if not args.no_open and not args.preview:
        print()
        print(f"  {MAGENTA}─────────────────────────────────────────────────{R}")
        print()
        print(f"  {PINK}Next up — upload to RoboBraille:{R}")
        print(f"    {CYAN}1.{R} Click 'Upload' on robobraille.org")
        print(f"    {CYAN}2.{R} Search for the filename ({BOLD}Cmd+V{R} to paste)")
        print(f"    {CYAN}3.{R} Pick a voice & hit convert 🎤")
        print()
        try:
            answer = input(f"  {BOLD}Open RoboBraille? [Y/n]{R} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = 'n'
        if answer in ('', 'y', 'yes'):
            print(f"\n  {MAGENTA}💋 Go get 'em.{R}\n")
            webbrowser.open("https://www.robobraille.org")
        else:
            print(f"\n  {PINK}👠 Standing by. You know where to find me.{R}\n")
    else:
        print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
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

    # Interactive mode
    if args.input is None:
        pdf_files = pick_files()
        n = len(pdf_files)
        print(f"\n  {MAGENTA}👠{R} {n} file{'s' if n != 1 else ''} on the stage. {BOLD}Let's work.{R}\n")
        for pdf_path in pdf_files:
            result = process_file(pdf_path, None, args.preview, args.faithful, args.verbose)
            if result:
                output_files.append(result)

    # Single file
    elif args.input.is_file():
        if args.input.suffix.lower() != '.pdf':
            print(f"  {YELLOW}Error: Not a PDF: {args.input}{R}", file=sys.stderr)
            sys.exit(1)

        output_path = args.output
        if output_path and output_path.is_dir():
            output_path = output_path / (args.input.stem + "_clean.txt")

        result = process_file(args.input, output_path, args.preview, args.faithful, args.verbose)
        if result:
            output_files.append(result)

    # Directory
    elif args.input.is_dir():
        pdf_files = sorted(args.input.glob('*.pdf'))
        if not pdf_files:
            print(f"  {YELLOW}No PDF files found in {args.input}{R}", file=sys.stderr)
            sys.exit(1)

        print(f"  {MAGENTA}👠{R} {len(pdf_files)} files. {BOLD}Let's work.{R}\n")

        output_dir = args.output
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

        for pdf_path in pdf_files:
            out = output_dir / (pdf_path.stem + "_clean.txt") if output_dir else None
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
