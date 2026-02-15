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
import shlex
import sys
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog


# ── Check for drag-and-drop support ──────────────────────────────────────────
def check_gui_dependencies():
    """Check and install tkinterdnd2 for drag-and-drop support."""
    try:
        from tkinterdnd2 import TkinterDnD  # noqa: F401
        return True
    except ImportError:
        print("\n  💅 First time running the GUI? Let me grab one more package for drag-and-drop!")
        print("  Installing tkinterdnd2...")

        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "tkinterdnd2"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("  ✨ Drag-and-drop ready! Launching...\n")
            return True
        except subprocess.CalledProcessError:
            print("  ⚠️  Couldn't install tkinterdnd2. Drag-and-drop won't work, but the attach button will!")
            print("  (You can install it manually with: pip install tkinterdnd2)")
            return False


# Check dependencies on import
DRAG_DROP_AVAILABLE = check_gui_dependencies()

# Import drag-and-drop if available
if DRAG_DROP_AVAILABLE:
    try:
        from tkinterdnd2 import TkinterDnD, DND_FILES
    except ImportError:
        DRAG_DROP_AVAILABLE = False


# ── ANSI Color Map ───────────────────────────────────────────────────────────
# Maps ANSI SGR codes to (foreground, bold, dim) properties

# Cunty mode: vibrant, fabulous colors
ANSI_COLORS_CUNTY = {
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

# Normie mode: corporate grey, muted colors (DMV office vibes)
ANSI_COLORS_NORMIE = {
    # Standard foreground
    30: '#3a3a3a',   # Black -> dark grey
    31: '#8a8a8a',   # Red -> medium grey
    32: '#9a9a9a',   # Green -> light grey
    33: '#888888',   # Yellow -> muted grey
    34: '#6a6a6a',   # Blue -> grey
    35: '#7a7a7a',   # Magenta -> grey (NO PINK!)
    36: '#8a8a8a',   # Cyan -> grey (no champagne!)
    37: '#9a9a9a',   # White -> light grey

    # Bright/high-intensity foreground
    90: '#5a5a5a',   # Bright Black -> slightly lighter grey
    91: '#888888',   # Bright Red -> grey
    92: '#8a8a8a',   # Bright Green -> grey
    93: '#888888',   # Bright Yellow -> grey
    94: '#7a7a7a',   # Bright Blue -> grey (commands still grey)
    95: '#7a7a7a',   # Bright Magenta -> grey
    96: '#8a8a8a',   # Bright Cyan -> grey
    97: '#9a9a9a',   # Bright White -> light grey
}

# Active color map (will be switched dynamically)
ANSI_COLORS = ANSI_COLORS_CUNTY.copy()

# Profile-aware default foreground
DEFAULT_FG_CUNTY = '#E8D4A0'  # Champagne gold
DEFAULT_FG_NORMIE = '#888888'  # Corporate grey
DEFAULT_FG = DEFAULT_FG_CUNTY  # Will be updated dynamically

BG_COLOR = '#000000'        # Pure black
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

        # Create a StringVar to track input field changes
        self._input_var = tk.StringVar()
        self._input_var.trace_add('write', lambda *args: self._on_input_change())

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
            textvariable=self._input_var,
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

        # Track profile changes for dynamic updates
        from pathlib import Path
        self._current_profile = current_profile
        self._profile_config_path = Path.home() / ".robostripper" / "config.json"
        self._profile_mtime = self._profile_config_path.stat().st_mtime if self._profile_config_path.exists() else 0

        # ANSI state
        self._ansi_state = ANSIState()
        self._tag_cache = {}

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

        # Current line buffer for \r handling
        self._current_line_start = None

        # Header background tag for title section - profile-aware
        # Cunty: ultra dark purple, Normie: pure black (soulless)
        header_bg_color = '#1A0B2E' if current_profile == 'cunty' else '#000000'
        self.text.tag_configure('header_bg', background=header_bg_color)
        self.text.tag_lower('header_bg')  # Ensure header_bg is below other tags
        self._in_header = False  # Track if we're still in the header section
        self._header_line_count = 0

        # Load initial colors for current profile
        self._reconfigure_colors_for_profile(current_profile)

        # Start output polling
        self._poll_output()

        # Focus the input field
        self.input_field.focus_set()

    def set_font(self, family, size):
        """Set the terminal font."""
        normal_font = tkfont.Font(family=family, size=size, weight='normal')
        bold_font = tkfont.Font(family=family, size=size, weight='bold')

        # Store base font info for profile switching
        self._base_font_family = family
        self._base_font_size = size

        # Initialize cunty fonts (glamorous!)
        self._init_cunty_fonts(family, size)

        # Initialize normie fonts (soul-crushing!)
        self._init_normie_fonts(family, size)

        # Set active fonts based on current profile
        if self._current_profile == 'cunty':
            self._activate_cunty_fonts()
        else:
            self._activate_normie_fonts()

        self.text.configure(font=normal_font)
        self.input_field.configure(font=normal_font)
        self._normal_font = normal_font
        self._bold_font = bold_font

        # Now that fonts are initialized, apply them to any existing title tags
        # (This handles the case where set_font() is called after __init__)
        self._apply_profile_fonts()

    def _init_cunty_fonts(self, family, size):
        """Initialize glamorous cunty mode fonts."""
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

        # Cunty fonts - glamorous and fabulous!
        self._title_font_cunty = tkfont.Font(family=runway_family, size=size+3, weight='bold')
        self._title_font_r_cunty = tkfont.Font(family=script_family, size=size+7, weight='bold')
        self._title_font_s_cunty = tkfont.Font(family=script_family, size=size+7, weight='bold')

    def _init_normie_fonts(self, family, size):
        """Initialize soul-crushing normie mode fonts."""
        # NORMIE FONTS: Corporate, boring, Arial/Helvetica hell
        normie_fonts = [
            'Arial',                # Peak corporate boredom
            'Helvetica',            # Swiss neutrality (yawn)
            'Helvetica Neue',       # Still boring
            'Geneva',               # Mac system font (meh)
            'MS Sans Serif',        # Windows corporate hell
            'Lucida Grande',        # Default Mac (uninspired)
        ]

        normie_family = family
        for font_name in normie_fonts:
            if font_name in tkfont.families():
                normie_family = font_name
                break

        # Normie fonts - all the same size, all the same boring font
        self._title_font_normie = tkfont.Font(family=normie_family, size=size, weight='normal')
        self._title_font_r_normie = tkfont.Font(family=normie_family, size=size, weight='normal')
        self._title_font_s_normie = tkfont.Font(family=normie_family, size=size, weight='normal')

    def _activate_cunty_fonts(self):
        """Switch to glamorous cunty fonts."""
        self._title_font = self._title_font_cunty
        self._title_font_r = self._title_font_r_cunty
        self._title_font_s = self._title_font_s_cunty

    def _activate_normie_fonts(self):
        """Switch to boring normie fonts."""
        self._title_font = self._title_font_normie
        self._title_font_r = self._title_font_r_normie
        self._title_font_s = self._title_font_s_normie

    def _apply_profile_fonts(self):
        """Apply current profile fonts to all existing title tags."""
        if not hasattr(self, '_title_font'):
            return  # Fonts not initialized yet

        for tag_name in self.text.tag_names():
            if '_title_' not in tag_name:
                continue

            try:
                # Determine char type from tag name
                if tag_name.endswith('_title_R'):
                    new_font = self._title_font_r
                elif tag_name.endswith('_title_S'):
                    new_font = self._title_font_s
                elif tag_name.endswith('_title_normal'):
                    new_font = self._title_font
                else:
                    continue

                # Reconfigure the tag with new font
                self.text.tag_configure(tag_name, font=new_font)
            except Exception:
                pass

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
            # Properly quote paths for shlex.split() in TUI
            quoted_paths = ' '.join(shlex.quote(str(p)) for p in file_paths)

            # Insert file paths into input field
            current = self.input_field.get()
            if current:
                # Append to existing text with space
                self.input_field.insert(tk.END, ' ' + quoted_paths)
            else:
                # Replace empty field
                self.input_field.delete(0, tk.END)
                self.input_field.insert(0, quoted_paths)
            self.input_field.focus_set()

    def _setup_drag_drop(self):
        """Enable drag-and-drop for PDF files on macOS."""
        if not DRAG_DROP_AVAILABLE:
            # Fallback: detect macOS brace format via StringVar trace
            # (already set up in __init__ with self._input_var.trace_add)
            return

        # Register multiple widgets as drop targets so users can drop anywhere!
        self.input_field.drop_target_register(DND_FILES)
        self.text.drop_target_register(DND_FILES)
        self.input_frame.drop_target_register(DND_FILES)

        # Bind the drop event to all drop targets
        self.input_field.dnd_bind('<<Drop>>', self._on_drop)
        self.text.dnd_bind('<<Drop>>', self._on_drop)
        self.input_frame.dnd_bind('<<Drop>>', self._on_drop)

    def _on_drop(self, event):
        """Handle files dropped onto the input field."""
        # event.data contains the file paths
        # On macOS, they come in brace format: {/path/file1.pdf} {/path/file2.pdf}
        files = self._parse_drop_data(event.data)

        if files:
            # Quote all paths properly for TUI's shlex.split()
            quoted_paths = ' '.join(shlex.quote(f) for f in files)

            # Get current content
            current = self.input_field.get()
            if current:
                # Append to existing text with space
                self.input_field.insert(tk.END, ' ' + quoted_paths)
            else:
                # Replace empty field
                self.input_field.delete(0, tk.END)
                self.input_field.insert(0, quoted_paths)

            self.input_field.focus_set()

        # Prevent default handling
        return 'break'

    def _parse_drop_data(self, data):
        """Parse file paths from drop event data.

        On macOS/Linux: {/path/file1.pdf} {/path/file2.pdf}
        On Windows: {C:/path/file1.pdf} {C:/path/file2.pdf}
        """
        # Extract paths from brace format
        brace_pattern = r'\{([^}]+)\}'
        paths = re.findall(brace_pattern, data)

        if not paths:
            # Fallback: try splitting by whitespace
            paths = data.split()

        return [p.strip() for p in paths if p.strip()]

    def _on_input_change(self):
        """Called automatically when input field content changes (via StringVar trace)."""
        # Check for macOS drag-and-drop brace format (fallback for when tkinterdnd2 isn't available)
        if not DRAG_DROP_AVAILABLE:
            content = self.input_field.get()
            if '{' in content and '}' in content:
                # Schedule processing after current event completes
                self.after(1, self._process_dropped_paths)

    def _process_dropped_paths(self):
        """Process paths that were pasted or dragged into the input field.

        Handles two formats:
        1. macOS drag-and-drop: {/path/file1.pdf} {/path with spaces/file2.pdf}
        2. Manual paste: /path/file1.pdf or "/path with spaces/file2.pdf"

        Converts both to shlex-compatible quoted format.
        """
        content = self.input_field.get().strip()
        if not content:
            return

        # Check for macOS brace format: {/path/file.pdf}
        brace_pattern = r'\{([^}]+)\}'
        brace_matches = re.findall(brace_pattern, content)

        if brace_matches:
            # macOS drag-and-drop detected
            paths = brace_matches
        else:
            # Manual paste or typed input
            try:
                paths = shlex.split(content)
            except ValueError:
                paths = content.split()

        # Re-quote all paths properly for TUI's shlex.split()
        quoted_paths = ' '.join(shlex.quote(p) for p in paths)

        # Replace input field with properly quoted paths
        self.input_field.delete(0, tk.END)
        self.input_field.insert(0, quoted_paths)

    def _check_profile_change(self):
        """Check if profile changed and update UI if needed."""
        if not self._profile_config_path.exists():
            return

        try:
            current_mtime = self._profile_config_path.stat().st_mtime
            if current_mtime > self._profile_mtime:
                # Profile changed! Reload it
                self._profile_mtime = current_mtime

                import json
                with open(self._profile_config_path) as f:
                    config = json.load(f)
                    new_profile = config.get("profile", "cunty")

                if new_profile != self._current_profile:
                    self._current_profile = new_profile
                    self._update_button_style(new_profile)
                    self._reconfigure_colors_for_profile(new_profile)
        except Exception:
            pass  # Silent fail if file read error

    def _update_button_style(self, profile):
        """Update attach button styling based on profile."""
        if profile == 'cunty':
            self.attach_button.config(
                text='📎✨',
                bg='#1A0B2E',
                fg='#FF79C6',
                activebackground='#2A1B3E',
                activeforeground='#FF79C6'
            )
        else:  # normie
            self.attach_button.config(
                text='📎',
                bg='#2a2a2a',
                fg='#888888',
                activebackground='#3a3a3a',
                activeforeground='#888888'
            )

    def _reconfigure_colors_for_profile(self, profile):
        """Reconfigure all terminal colors for new profile."""
        global ANSI_COLORS, DEFAULT_FG

        # Switch active color map
        if profile == 'cunty':
            ANSI_COLORS = ANSI_COLORS_CUNTY.copy()
            DEFAULT_FG = DEFAULT_FG_CUNTY
            new_palette = ANSI_COLORS_CUNTY
            old_palette = ANSI_COLORS_NORMIE
        else:  # normie
            ANSI_COLORS = ANSI_COLORS_NORMIE.copy()
            DEFAULT_FG = DEFAULT_FG_NORMIE
            new_palette = ANSI_COLORS_NORMIE
            old_palette = ANSI_COLORS_CUNTY

        # Build color mapping: old_color -> new_color
        color_map = {}
        for code in old_palette:
            if code in new_palette:
                old_color = old_palette[code]
                new_color = new_palette[code]
                color_map[old_color] = new_color
                # Also map dimmed versions
                color_map[dim_color(old_color)] = dim_color(new_color)

        # Reconfigure all existing tags
        for tag_name in self.text.tag_names():
            if not tag_name.startswith('ansi_'):
                continue

            # Get current foreground color
            try:
                current_fg = self.text.tag_cget(tag_name, 'foreground')

                # Map to new color
                new_fg = color_map.get(current_fg, current_fg)

                # Reconfigure tag (this retroactively affects all text using this tag!)
                if new_fg != current_fg:
                    self.text.tag_configure(tag_name, foreground=new_fg)
            except Exception:
                pass  # Skip tags that don't have foreground color

        # Update header background: purple in cunty, black in normie
        header_bg_color = '#1A0B2E' if profile == 'cunty' else '#000000'
        self.text.tag_configure('header_bg', background=header_bg_color)

        # Switch title fonts: glamorous in cunty, boring in normie
        # (Only if fonts have been initialized - set_font() is called after __init__)
        if hasattr(self, '_title_font_cunty') and hasattr(self, '_title_font_normie'):
            if profile == 'cunty':
                self._activate_cunty_fonts()
            else:
                self._activate_normie_fonts()

            # Apply the new fonts to all existing title tags
            self._apply_profile_fonts()

        # Update main text widget's default foreground and cursor
        cursor_color = '#FF79C6' if profile == 'cunty' else '#666666'
        self.text.config(fg=DEFAULT_FG, insertbackground=cursor_color)

        # Update input field cursor and foreground color
        self.input_field.config(insertbackground=cursor_color, fg=DEFAULT_FG)

    def _poll_output(self):
        """Poll the output queue and render text."""
        # Check for profile changes every poll cycle (~60fps is fine for this)
        self._check_profile_change()

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
        global DRAG_DROP_AVAILABLE

        # Use TkinterDnD if available for drag-and-drop support
        if DRAG_DROP_AVAILABLE:
            try:
                self.root = TkinterDnD.Tk()
            except (RuntimeError, Exception) as e:
                # Fall back if tkdnd native library fails to load (common on macOS Python 3.14)
                print(f"  ⚠️  Drag-and-drop unavailable ({e})")
                print("  📎 Using attach button instead!\n")
                self.root = tk.Tk()
                DRAG_DROP_AVAILABLE = False
        else:
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
