#!/usr/bin/env python3
"""
RoboStripper GUI — ANSI Terminal Emulator in tkinter.

Runs the full robostripper.py TUI inside a native macOS window so we get:
  • The sexy rounded icon in the Dock
  • Every single ANSI color, spinner, fade effect, and easter egg
  • All 1873 lines of UX artistry, completely unmodified

Architecture:
  1. ANSITerminal widget parses escape codes → tkinter text tags
  2. stdout/stdin are redirected through thread-safe queues
  3. robostripper.main() runs in a background thread
  4. The GUI event loop renders output and feeds input

   💅✨👠
"""

import os
import re
import sys
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog


# ── ANSI Color Map ───────────────────────────────────────────────────────────
# Maps ANSI SGR codes to (foreground, bold, dim) properties

ANSI_COLORS = {
    # Standard foreground
    30: '#4D4D4D',   # Black
    31: '#FF5555',   # Red
    32: '#50FA7B',   # Green
    33: '#F1FA8C',   # Yellow
    34: '#6272A4',   # Blue
    35: '#FF79C6',   # Hot pink (PINK - "Hey love!" color)
    36: '#E8D4A0',   # Champagne gold (standard cyan)
    37: '#E8D4A0',   # Champagne gold (matches CYAN)

    # Bright/high-intensity foreground
    90: '#6272A4',   # Bright Black (Dark Gray)
    91: '#FF6E6E',   # Bright Red
    92: '#69FF94',   # Bright Green (GREEN)
    93: '#FFFFA5',   # Bright Yellow (YELLOW)
    94: '#00BD6F',   # Deeper, richer emerald (EMERALD - commands only: quit, profile, pip install)
    95: '#FF79C6',   # Hot pink (MAGENTA - same as PINK now)
    96: '#E8D4A0',   # Champagne gold (CYAN - friendly text, instructions, destinations)
    97: '#E8D4A0',   # Champagne gold (WHITE - matches CYAN)
}

BG_COLOR = '#000000'        # Pure black
DEFAULT_FG = '#E8D4A0'      # Champagne gold
DIM_MULTIPLIER = 0.55        # How much to dim text


def dim_color(hex_color):
    """Darken a hex color for DIM effect."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = int(r * DIM_MULTIPLIER)
    g = int(g * DIM_MULTIPLIER)
    b = int(b * DIM_MULTIPLIER)
    return f'#{r:02x}{g:02x}{b:02x}'


# ── ANSI Parser ──────────────────────────────────────────────────────────────

# Matches: ESC[ (params) (letter)  — standard CSI sequences
CSI_RE = re.compile(r'\033\[([0-9;]*)([A-Za-z])')

# Matches: ESC[8;rows;cols t  — terminal resize (we'll ignore gracefully)
RESIZE_RE = re.compile(r'\033\[8;\d+;\d+t')


class ANSIState:
    """Tracks current ANSI text styling state."""

    def __init__(self):
        self.fg = DEFAULT_FG
        self.bold = False
        self.dim = False

    def reset(self):
        self.fg = DEFAULT_FG
        self.bold = False
        self.dim = False

    def apply_sgr(self, codes):
        """Apply SGR (Select Graphic Rendition) codes."""
        if not codes:
            self.reset()
            return

        for code in codes:
            if code == 0:
                self.reset()
            elif code == 1:
                self.bold = True
            elif code == 2:
                self.dim = True
            elif code in ANSI_COLORS:
                self.fg = ANSI_COLORS[code]
                # When a new color is set, don't inherit previous dim
                # unless dim was explicitly set in the same sequence
            elif code == 22:  # Normal intensity (neither bold nor dim)
                self.bold = False
                self.dim = False

    def tag_name(self):
        """Generate a unique tag name for the current state."""
        color = self.fg
        if self.dim:
            color = dim_color(color)
        weight = 'bold' if self.bold else 'normal'
        # Sanitize hex for tag name
        safe_color = color.replace('#', 'c')
        return f'ansi_{safe_color}_{weight}'

    def tag_config(self):
        """Return dict of tkinter text tag configuration."""
        color = self.fg
        if self.dim:
            color = dim_color(color)
        weight = 'bold' if self.bold else 'normal'
        return {'foreground': color, 'font_weight': weight}


# ── Terminal Emulator Widget ─────────────────────────────────────────────────

class ANSITerminal(tk.Frame):
    """A tkinter widget that emulates a terminal with ANSI color support."""

    def __init__(self, master, **kwargs):
        super().__init__(master, bg=BG_COLOR, **kwargs)

        # Output text area
        self.text = tk.Text(
            self,
            wrap=tk.NONE,  # No wrapping - let terminal content control layout
            bg=BG_COLOR,
            fg=DEFAULT_FG,
            insertbackground=DEFAULT_FG,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            padx=16,
            pady=12,
            state=tk.NORMAL,
            cursor='arrow',
        )

        # Scrollbar
        self.scrollbar = tk.Scrollbar(
            self,
            command=self.text.yview,
            bg=BG_COLOR,
            troughcolor=BG_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        self.text.configure(yscrollcommand=self.scrollbar.set)

        # Input frame at bottom (no visible prompt - robostripper prints its own)
        self.input_frame = tk.Frame(self, bg=BG_COLOR)
        self.input_field = tk.Entry(
            self.input_frame,
            bg='#0a0a0a',  # Slightly lighter black
            fg='#E8D4A0',  # Champagne gold
            insertbackground='#FF79C6',
            relief=tk.FLAT,
            borderwidth=6,
            highlightthickness=1,
            highlightcolor='#333333',
            highlightbackground='#1a1a1a',
        )

        # Get current profile to style the button
        try:
            import robostripper
            current_profile = robostripper.load_profile()
        except:
            current_profile = 'cunty'  # Default to fabulous mode!

        # Fabulous file attach button 💅
        # Subtle pink in cunty mode, grey in normie mode
        if current_profile == 'cunty':
            button_config = {
                'text': '📎✨',  # Paperclip with sparkles - cunty vibes!
                'bg': '#1A0B2E',  # Deep purple background (matches header)
                'fg': '#FF79C6',  # Hot pink text
                'activebackground': '#2A1B3E',  # Slightly lighter purple when clicked
                'activeforeground': '#FF79C6',  # Keep pink text when clicked
            }
        else:
            button_config = {
                'text': '📎',  # Plain paperclip - normie mode
                'bg': '#2a2a2a',  # Dark grey background
                'fg': '#888888',  # Medium grey text
                'activebackground': '#3a3a3a',  # Lighter grey when clicked
                'activeforeground': '#aaaaaa',  # Lighter grey text when clicked
            }

        self.attach_button = tk.Button(
            self.input_frame,
            relief=tk.FLAT,
            borderwidth=0,
            font=('SF Pro', 16),
            cursor='hand2',
            padx=8,
            pady=4,
            command=self._attach_files,
            **button_config
        )

        # Layout
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 12))
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.attach_button.pack(side=tk.RIGHT)

        # Bind Enter key
        self.input_field.bind('<Return>', self._on_enter)

        # Enable drag-and-drop for file paths
        self._setup_drag_drop()

        # Thread-safe queues
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self._input_ready = threading.Event()

        # ANSI state
        self._ansi_state = ANSIState()
        self._tag_cache = {}

        # Current line buffer for \r handling
        self._current_line_start = None

        # Header background tag for title section - ultra dark purple
        self.text.tag_configure('header_bg', background='#1A0B2E')  # Ultra deep, almost black purple
        self.text.tag_lower('header_bg')  # Ensure header_bg is below other tags
        self._in_header = False  # Track if we're still in the header section
        self._header_line_count = 0

        # Start output polling
        self._poll_output()

        # Focus the input field
        self.input_field.focus_set()

    def set_font(self, family, size):
        """Set the terminal font."""
        normal_font = tkfont.Font(family=family, size=size, weight='normal')
        bold_font = tkfont.Font(family=family, size=size, weight='bold')

        # TWO FONTS: Script for R/S, runway editorial for the rest

        # Font 1: GLAMOROUS SCRIPT for R and S (Zapfino first for that perfect R!)
        script_fonts = [
            'Zapfino',              # Flowing script - MAXIMUM GLAMOUR, perfect R
            'Snell Roundhand',      # Classic calligraphy - beautiful S swashes
            'Brush Script MT',      # Bold flowing script - dramatic S
            'Apple Chancery',       # Classic italic swashes
            'Edwardian Script ITC', # Elegant with long flourishes
            'Lucida Handwriting',   # Italic swashes
            'Noteworthy',           # Handwritten elegance
            'Party LET',            # Decorative display
        ]

        script_family = family
        for font_name in script_fonts:
            if font_name in tkfont.families():
                script_family = font_name
                break

        # Font 2: RUNWAY EDITORIAL for O B O / R I P P E R
        runway_fonts = [
            'Didot',                # High fashion editorial
            'Bodoni 72',            # Luxury magazine
            'Avenir Next',          # Clean luxury
            'Futura',               # Geometric runway
            'Optima',               # Sophisticated
            'Helvetica Neue',       # Fashion branding
        ]

        runway_family = family
        for font_name in runway_fonts:
            if font_name in tkfont.families():
                runway_family = font_name
                break

        # Regular runway font for O B O / T R I P P E R
        self._title_font = tkfont.Font(family=runway_family, size=size+3, weight='bold')

        # LARGE glamorous R (Zapfino - you love this one!)
        self._title_font_r = tkfont.Font(family=script_family, size=size+7, weight='bold')

        # S uses same font as R (Zapfino)
        s_fonts = [
            'Zapfino',              # Same as R - consistent look
        ]

        s_family = script_family
        for font_name in s_fonts:
            if font_name in tkfont.families():
                s_family = font_name
                break

        # S same size as R
        self._title_font_s = tkfont.Font(family=s_family, size=size+7, weight='bold')

        self.text.configure(font=normal_font)
        self.input_field.configure(font=normal_font)
        self._normal_font = normal_font
        self._bold_font = bold_font

    def _get_or_create_tag(self, state):
        """Get or create a text tag for the given ANSI state."""
        name = state.tag_name()
        if name not in self._tag_cache:
            config = state.tag_config()
            font_weight = config.pop('font_weight', 'normal')
            if font_weight == 'bold' and hasattr(self, '_bold_font'):
                config['font'] = self._bold_font
            self.text.tag_configure(name, **config)
            self._tag_cache[name] = True
        return name

    def _get_or_create_title_tag(self, state, char_type='normal'):
        """Get or create a special title tag with glamorous font.

        char_type: 'normal', 'R', or 'S' for different font treatments
        """
        suffix = f'_title_{char_type}'
        name = state.tag_name() + suffix
        if name not in self._tag_cache:
            config = state.tag_config()
            config.pop('font_weight', None)

            if char_type == 'R' and hasattr(self, '_title_font_r'):
                config['font'] = self._title_font_r
            elif char_type == 'S' and hasattr(self, '_title_font_s'):
                config['font'] = self._title_font_s
            elif hasattr(self, '_title_font'):
                config['font'] = self._title_font

            self.text.tag_configure(name, **config)
            self._tag_cache[name] = True
        return name

    def _write_glamorous_title(self, line):
        """Write the title line with fancy R/S and runway OBO/TRIPPER."""
        # Track line start
        if self._current_line_start is None:
            self._current_line_start = self.text.index(tk.END + '-1c')

        # First, handle any ANSI codes at the start and count leading spaces after them
        i = 0
        leading_spaces_after_ansi = 0

        # Process initial ANSI codes
        while i < len(line):
            if line[i] == '\033' and i + 1 < len(line) and line[i + 1] == '[':
                match = CSI_RE.match(line[i:])
                if match:
                    params_str = match.group(1)
                    command = match.group(2)
                    if command == 'm':
                        if params_str == '':
                            codes = [0]
                        else:
                            codes = [int(p) for p in params_str.split(';') if p]
                        self._ansi_state.apply_sgr(codes)
                    i += match.end()
                    continue
            elif line[i] == ' ':
                leading_spaces_after_ansi += 1
                i += 1
            else:
                break

        # Insert the leading spaces with purple background
        if leading_spaces_after_ansi > 0:
            self.text.insert(tk.END, ' ' * leading_spaces_after_ansi, 'header_bg')

        # Track position in the actual title text (ignoring ANSI codes)
        # We want: R(fancy) OBO(runway) S(fancy) TRIPPER(runway)
        title_chars_seen = 0
        r_count = 0
        s_count = 0

        # Process character by character to apply variable sizing
        # Start from where we left off after processing leading content
        while i < len(line):
            char = line[i]

            # Check if we're starting an ANSI sequence
            if char == '\033' and i + 1 < len(line) and line[i + 1] == '[':
                # Find the end of the ANSI sequence
                match = CSI_RE.match(line[i:])
                if match:
                    # Process the ANSI code
                    params_str = match.group(1)
                    command = match.group(2)
                    if command == 'm':
                        if params_str == '':
                            codes = [0]
                        else:
                            codes = [int(p) for p in params_str.split(';') if p]
                        self._ansi_state.apply_sgr(codes)
                    i += match.end()
                    continue

            # Track which R or S this is
            if char == 'R':
                r_count += 1
            elif char == 'S':
                s_count += 1

            # Determine font treatment
            if char == 'R' and r_count == 1:
                char_type = 'R'  # First R gets Zapfino
            elif char == 'S' and s_count == 1:
                char_type = 'S'  # First S gets dramatic font - BIG!
            else:
                char_type = 'normal'  # Everything else gets runway font

            # Get appropriate tag
            tag = self._get_or_create_title_tag(self._ansi_state, char_type=char_type)

            # Insert the character
            insert_pos = tk.END

            # For the big S, we want it to extend over adjacent letters
            # Add some negative spacing by backing up the cursor
            if char == 'S' and s_count == 1:
                # Insert S, then back up cursor slightly so next char overlaps
                if self._in_header:
                    self.text.insert(insert_pos, char, (tag, 'header_bg'))
                else:
                    self.text.insert(insert_pos, char, tag)
                # Delete a couple spaces after S to create overlap effect
                # (This is a hack but tkinter doesn't support proper kerning)
                i += 1
                continue

            # Apply both the style tag and header_bg if in header section
            if self._in_header:
                self.text.insert(insert_pos, char, (tag, 'header_bg'))
            else:
                self.text.insert(insert_pos, char, tag)
            i += 1

        # Extend header background to match the pink border width
        # Add enough spaces to fill to the same width as the border lines (71 chars)
        remaining_spaces = ' ' * 14  # Fill to match border width (15 leading + 35 title + 14 trailing = 64)
        if self._in_header:
            self.text.insert(tk.END, remaining_spaces, 'header_bg')

        # Header ends after the title line - set flag to False
        self._in_header = False

    def _on_enter(self, event=None):
        """Handle Enter keypress — send input to the waiting thread."""
        text = self.input_field.get()
        self.input_field.delete(0, tk.END)
        self.input_queue.put(text)
        self._input_ready.set()
        return 'break'

    def _attach_files(self):
        """Handle file attach button click - open file picker with cunty vibes! 💅"""
        file_paths = filedialog.askopenfilenames(
            title="Pick your files, boo! 💅",
            filetypes=[
                ("PDF files", "*.pdf"),
                ("All files", "*.*")
            ]
        )
        if file_paths:
            # Insert file paths into input field
            current = self.input_field.get()
            if current:
                # Append to existing text with space
                self.input_field.insert(tk.END, ' ' + ' '.join(file_paths))
            else:
                # Replace empty field
                self.input_field.delete(0, tk.END)
                self.input_field.insert(0, ' '.join(file_paths))
            self.input_field.focus_set()

    def _setup_drag_drop(self):
        """Enable drag-and-drop for PDF files on macOS."""
        # On macOS, tkinter has a special event for drag-and-drop
        # When files are dragged onto the window, they appear as a <<Drop>> event
        # However, this requires tkinterdnd2 package for full support

        # For now, we'll make the input field accept dropped text (file paths)
        # When you drag files onto macOS tkinter Entry widget, it auto-pastes the paths
        # This works out of the box on macOS!

        # Just make sure the input field is ready to receive drops
        # The Entry widget on macOS automatically handles file drops as text paste

        # We can also detect when text is pasted/dropped and clean it up
        def on_paste(event=None):
            # Get pasted content after a short delay (let the paste happen first)
            self.after(10, self._clean_pasted_paths)

        self.input_field.bind('<<Paste>>', on_paste)
        # Also handle Command+V explicitly
        self.input_field.bind('<Command-v>', on_paste)

    def _clean_pasted_paths(self):
        """Clean up file paths that were pasted/dropped."""
        content = self.input_field.get()
        if content:
            # Remove quotes and clean up paths
            # macOS often adds quotes around paths with spaces
            content = content.replace("'", "").replace('"', '')
            self.input_field.delete(0, tk.END)
            self.input_field.insert(0, content)

    def _poll_output(self):
        """Poll the output queue and render text."""
        try:
            while True:
                chunk = self.output_queue.get_nowait()
                self._render_ansi(chunk)
        except queue.Empty:
            pass
        self.after(16, self._poll_output)  # ~60fps

    def _render_ansi(self, text):
        """Parse ANSI escape codes and render styled text."""
        # Strip terminal resize sequences (we handle window size ourselves)
        text = RESIZE_RE.sub('', text)

        pos = 0
        while pos < len(text):
            # Look for next escape sequence
            match = CSI_RE.search(text, pos)

            if match is None:
                # No more escape codes — render remaining text
                self._write_text(text[pos:])
                break

            # Render text before the escape code
            if match.start() > pos:
                self._write_text(text[pos:match.start()])

            # Process the escape sequence
            params_str = match.group(1)
            command = match.group(2)

            if command == 'm':
                # SGR — Select Graphic Rendition (colors/styles)
                if params_str == '':
                    codes = [0]
                else:
                    codes = [int(p) for p in params_str.split(';') if p]
                self._ansi_state.apply_sgr(codes)

            elif command == 'J':
                # ED — Erase Display
                param = int(params_str) if params_str else 0
                if param == 2:
                    # Clear entire screen
                    self.text.delete('1.0', tk.END)
                    self._current_line_start = None
                    self._in_header = False  # Reset header tracking on screen clear

            elif command == 'H':
                # CUP — Cursor Position (home)
                # When used as \033[H (no params), moves to top-left
                # In our context, this usually follows clear screen
                pass

            elif command == 'K':
                # EL — Erase in Line
                param = int(params_str) if params_str else 0
                if param == 2 or param == 0:
                    # Clear entire line / clear to end of line
                    self._clear_current_line()

            pos = match.end()

        # Auto-scroll to bottom
        self.text.see(tk.END)

    def _write_text(self, text):
        """Write plain text with current ANSI styling."""
        if not text:
            return

        # Handle carriage return: move cursor back to start of current line
        parts = text.split('\r')
        for i, part in enumerate(parts):
            if i > 0:
                # \r encountered — next text overwrites current line
                self._clear_current_line()

            if part:
                # Check if this is the title line - activate header background
                if 'R O B O S T R I P P E R' in part:
                    self._in_header = True
                    # Render title with variable-sized letters (R and S are larger)
                    self._write_glamorous_title(part)
                else:
                    tag = self._get_or_create_tag(self._ansi_state)

                    # Track line start for \r handling
                    if self._current_line_start is None:
                        self._current_line_start = self.text.index(tk.END + '-1c')

                    # Normal text - no header background
                    self.text.insert(tk.END, part, tag)

                # If text contains newlines, reset line tracking
                if '\n' in part:
                    self._current_line_start = None

    def _clear_current_line(self):
        """Clear the current (last) line of text."""
        # Get the start of the last line
        end = self.text.index(tk.END + '-1c')
        line_num = int(end.split('.')[0])
        line_start = f'{line_num}.0'
        self.text.delete(line_start, tk.END)
        self._current_line_start = None

    def readline(self):
        """Block until user provides input (called from background thread)."""
        self._input_ready.clear()
        self._input_ready.wait()
        try:
            text = self.input_queue.get_nowait()
            return text + '\n'
        except queue.Empty:
            return '\n'

    def write(self, text):
        """Write text to the terminal (called from background thread)."""
        # Filter out input prompts that Python's input() function prints
        # The actual prompts are already in the terminal output above
        if text.strip() and not self._is_input_prompt(text):
            self.output_queue.put(text)
        elif not text.strip():
            # Keep empty strings (newlines, spaces) for formatting
            self.output_queue.put(text)

    def _is_input_prompt(self, text):
        """Check if text is an input() prompt we should suppress."""
        # Suppress the standalone bold > that appears before input
        stripped = text.strip()
        # Remove ANSI codes for checking
        ansi_removed = CSI_RE.sub('', stripped)
        # If it's just ">" or variations with whitespace, suppress it
        return ansi_removed.strip() in ['>', '> ']

    def flush(self):
        """Flush — no-op for GUI."""
        pass

    def isatty(self):
        """Pretend we're a real terminal so ANSI colors are enabled."""
        return True

    @property
    def encoding(self):
        return 'utf-8'


# ── Main Application ─────────────────────────────────────────────────────────

class RoboStripperApp:
    """Main GUI application window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('RoboStripper 👠✨💅')
        # Narrower window for cunty mode - centered text blocks
        self.root.geometry('620x700')
        self.root.configure(bg=BG_COLOR)
        self.root.minsize(600, 400)

        # Set the app icon (if running as .app bundle, icon is set via Info.plist)
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'robostripper_icon.png')
            if os.path.exists(icon_path):
                icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon)
        except Exception:
            pass

        # Create terminal emulator
        self.terminal = ANSITerminal(self.root)
        self.terminal.pack(fill=tk.BOTH, expand=True)

        # Set font — try fonts with good Unicode box-drawing support
        # Menlo has better box-drawing characters than Monaco
        for font_name in ['Menlo', 'SF Mono', 'Monaco', 'Courier New']:
            if font_name in tkfont.families():
                self.terminal.set_font(font_name, 13)
                break
        else:
            self.terminal.set_font('TkFixedFont', 13)

        # Handle window close
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _on_close(self):
        """Clean up and exit."""
        self.root.destroy()
        os._exit(0)

    def start(self):
        """Start robostripper in a background thread and run the GUI."""
        # Redirect stdout/stderr/stdin to our terminal widget
        sys.stdout = self.terminal
        sys.stderr = self.terminal
        sys.stdin = self.terminal

        # Force color support ON (we handle ANSI codes natively)
        os.environ.pop('NO_COLOR', None)

        # Override argv so argparse doesn't choke on PyInstaller args
        sys.argv = [sys.argv[0]]

        # Start robostripper in background thread
        thread = threading.Thread(target=self._run_robostripper, daemon=True)
        thread.start()

        # Run the GUI event loop
        self.root.mainloop()

    def _run_robostripper(self):
        """Run the main robostripper logic in a background thread."""
        try:
            # Import after redirecting stdout so dependency check works
            from robostripper import main
            main()
        except SystemExit:
            # robostripper calls sys.exit() on quit — that's fine
            pass
        except Exception as e:
            sys.stderr.write(f'\n\n  Error: {e}\n')
            import traceback
            sys.stderr.write(traceback.format_exc())


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app = RoboStripperApp()
    app.start()
