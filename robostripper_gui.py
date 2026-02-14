#!/usr/bin/env python3
"""
RoboStripper GUI wrapper - gives us that sexy icon in the Dock! 💅✨👠
"""

import tkinter as tk
from tkinter import scrolledtext
import sys
import threading
import queue
from robostripper import main as robostripper_main

class RoboStripperGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("👠✨💅 RoboStripper 💅✨👠")
        self.root.geometry("900x600")

        # Set dark theme colors - cyberpunk vibes
        bg_color = "#1a1a1a"
        text_color = "#ff69b4"  # Hot pink
        input_color = "#ffb6c1"  # Light pink

        self.root.configure(bg=bg_color)

        # Create output area (like a terminal)
        self.output = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            width=100,
            height=30,
            bg=bg_color,
            fg=text_color,
            insertbackground=input_color,
            font=("Monaco", 12),
            relief=tk.FLAT,
            borderwidth=10
        )
        self.output.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Create input area
        input_frame = tk.Frame(self.root, bg=bg_color)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(input_frame, text="❯ ", bg=bg_color, fg=input_color, font=("Monaco", 12)).pack(side=tk.LEFT)

        self.input_field = tk.Entry(
            input_frame,
            bg="#2a2a2a",
            fg=input_color,
            insertbackground=input_color,
            font=("Monaco", 12),
            relief=tk.FLAT,
            borderwidth=5
        )
        self.input_field.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.input_field.bind("<Return>", self.handle_input)

        # Queue for thread-safe communication
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()

        # Redirect stdout/stdin
        sys.stdout = StdoutRedirector(self.output_queue)
        sys.stdin = StdinRedirector(self.input_queue)

        # Start output processor
        self.process_output()

        # Start RoboStripper in a thread
        self.robostripper_thread = threading.Thread(target=robostripper_main, daemon=True)
        self.robostripper_thread.start()

    def handle_input(self, event):
        """Handle user input"""
        user_input = self.input_field.get()
        self.output.insert(tk.END, f"❯ {user_input}\n", "user_input")
        self.output.see(tk.END)
        self.input_queue.put(user_input)
        self.input_field.delete(0, tk.END)

    def process_output(self):
        """Process output from RoboStripper"""
        try:
            while True:
                line = self.output_queue.get_nowait()
                self.output.insert(tk.END, line)
                self.output.see(tk.END)
        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(50, self.process_output)

    def run(self):
        """Start the GUI"""
        self.root.mainloop()

class StdoutRedirector:
    """Redirects stdout to the GUI"""
    def __init__(self, output_queue):
        self.output_queue = output_queue

    def write(self, text):
        self.output_queue.put(text)

    def flush(self):
        pass

class StdinRedirector:
    """Redirects stdin from the GUI"""
    def __init__(self, input_queue):
        self.input_queue = input_queue

    def readline(self):
        return self.input_queue.get() + "\n"

if __name__ == "__main__":
    app = RoboStripperGUI()
    app.run()
