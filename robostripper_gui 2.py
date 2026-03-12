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


# ── ANSI Color Map ───────────────────────────────────────────────────────────
# Maps ANSI SGR codes to (foreground, bold, dim) properties

ANSI_COLORS = {
    # Standard foreground
    30: '#4D4D4D',   # Black
    31: '#FF5555',   # Red
    32: '#50FA7B',   # Green
    33: '#F1FA8C',   # Yellow
    34: '#6272A4',   # Blue
    35: '#FF79C6',   # Magenta (PINK in robostripper)
    36: '#8BE9FD',   # Cyan
    37: '#F8F8F2',   # White

    # Bright/high-intensity foreground
    90: '#6272A4',   # Bright Black (Dark Gray)
    91: '#FF6E6E',   # Bright Red
    92: '#69FF94',   # Bright Green (GREEN)
    93: '#FFFFA5',   # Bright Yellow (YELLOW)
    94: '#D6ACFF',   # Bright Blue
    95: '#FF92DF',   # Bright Magenta (MAGENTA)
    96: '#A4FFFF',   # Bright Cyan (CYAN)
    97: '#FFFFFF',   # Bright White (WHITE)
}

BG_COLOR = '#000000'        # Pure black
DEFAULT_FG = '#F8F8F2'      # Warm off-white
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
            fg='#F8F8F2',
            insertbackground='#FF79C6',
            relief=tk.FLAT,
            borderwidth=6,
            highlightthickness=1,
            highlightcolor='#333333',
            highlightbackground='#1a1a1a',
        )

        # Layout
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(4, 12))
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Bind Enter key
        self.input_field.bind('<Return>', self._on_enter)

        # Thread-safe queues
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self._input_ready = threading.Event()

        # ANSI state
        self._ansi_state = ANSIState()
        self._tag_cache = {}

        # Current line buffer for \r handling
        self._current_line_start = None

        # Start output polling
        self._poll_output()

        # Focus the input field
        self.input_field.focus_set()

    def set_font(self, family, size):
        """Set the terminal font."""
        normal_font = tkfont.Font(family=family, size=size, weight='normal')
        bold_font = tkfont.Font(family=family, size=size, weight='bold')
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

    def _on_enter(self, event=None):
        """Handle Enter keypress — send input to the waiting thread."""
        text = self.input_field.get()
        self.input_field.delete(0, tk.END)
        self.input_queue.put(text)
        self._input_ready.set()
        return 'break'

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
                tag = self._get_or_create_tag(self._ansi_state)

                # Track line start for \r handling
                if self._current_line_start is None:
                    self._current_line_start = self.text.index(tk.END + '-1c')

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
        self.output_queue.put(text)

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
        self.root.geometry('820x650')
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

        # Set font — Monaco is the classic macOS terminal font
        for font_name in ['Monaco', 'Menlo', 'SF Mono', 'Courier New']:
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
