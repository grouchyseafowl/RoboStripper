# 👠✨💅 RoboStripper 💅✨👠

**Strip metadata from scholarly PDFs for clean RoboBraille audio conversion**

Removes repetitive headers, footers, copyright stamps, download timestamps, and platform URLs that clutter academic PDFs — so RoboBraille can read your PDFs aloud without interruptions.

---

## 📥 Download

### Stopgap TUI (All OS) — Double‑Click Launchers (No Terminal Needed)

This is the fastest path while the GUI is being cleaned up. It runs the **TUI**.

1. Go to [**Releases**](../../releases/latest)
2. Download `RoboStripper.zip`
3. Unzip it anywhere (Desktop is fine)
4. Double‑click the launcher for your OS:
   - **Mac**: `RoboStripper.command`
   - **Windows**: `RoboStripper.bat`
   - **Linux**: `RoboStripper.sh`

If you don’t have Python installed, the launcher will open python.org and walk you through it.

---

### For Mac Users

1. Go to [**Releases**](../../releases/latest)
2. Download **`RoboStripper`** (the file without .exe)
3. Move it to your Applications folder or Desktop
4. Double-click to run
   - If you get a security warning: Right-click → Open → Open anyway

### For Windows Users

1. Go to [**Releases**](../../releases/latest)
2. Download **`RoboStripper.exe`**
3. Move it to a folder you like (Desktop works great)
4. Double-click to run
   - If Windows Defender blocks it: Click "More info" → "Run anyway"

### Any OS (requires Python 3 installation) 

1. clone this repo and run directly:
```bash
git clone https://github.com/[your-username]/RoboStripper.git
```

2a. Double click any of the launchers:
   - Linux: RoboStripper.sh
   - Mac: RoboStripper.command 
   - Windows: RoboStripper.bat

2b. Or run the python script directly (if Python 3 already installed)
```bash
cd RoboStripper
python3 robostripper.py
```

3. RoboStripper will walk you through installing any needed dependencies

---

## ✨ How to Use

1. **Launch RoboStripper** (double-click the app, exe, or launcher, or run the Python script)

2. **Drag in your PDF files** when prompted, then press Enter

3. **Find cleaned files** in the `StrippedText/` folder
   - Original: `Our_History_Is_the_Future.pdf`
   - Cleaned: `Our_History_Is_the_Future_clean.txt`

4. **Upload to RoboBraille**
   - The filename is already on your clipboard
   - Go to [robobraille.org](https://www.robobraille.org)
   - Click Upload → Paste filename (Cmd+V / Ctrl+V) → Select file
   - Pick a voice & convert 🎤

---

## 💖 What It Does

**Strips away:**
- Repeating headers and footers on every page
- Copyright notices and terms of use
- Download timestamps and IP addresses
- Database URLs and access codes
- Journal metadata (ISSN, DOI, publication info)
- Page numbers (standalone)

**Keeps:**
- Body text (paragraphs, quotes, poetry)
- Abstracts
- Section headings and chapter titles
- Footnote content
- Citation headers (title, author, source) for orientation

**Smart features:**
- Auto-detects metadata patterns across platforms
- OCR support for scanned PDFs
- Fixes hyphenation across line breaks
- Formats text for natural TTS reading

---

## 🛠️ Supported Platforms

RoboStripper recognizes and removes metadata from:

- **JSTOR** — download stamps, stable URLs, terms of use
- **ProQuest Ebook Central** — copyright headers, page ranges, created-from timestamps
- **EBSCO** — eBook Collection watermarks, terms URLs
- **Taylor & Francis** — journal headers, DOI footers, contact info
- **Duke University Press** — download footers, user stamps
- **eScholarship** — UC permalinks, powered-by footers
- **Chicago Unbound** — recommended citations, brought-to-you text
- Plus general patterns found in other academic sources

---

## 🆘 Troubleshooting

### "Python is not installed" (Mac/Windows launchers)
The app will guide you! It'll open python.org where you can download it.

### "Permission denied" or "Can't be opened" (Mac)
Right-click the app → **Open** → Click **Open** in the dialog. macOS will remember your choice.

### "Windows protected your PC" (Windows)
Click **More info** → **Run anyway**. This happens because the app isn't code-signed (that costs $$).

### OCR not working
Make sure Tesseract is installed:
- **Mac**: `brew install tesseract`
- **Windows**: Download from [tesseract-ocr](https://github.com/UB-Mannheim/tesseract/wiki)
- **Linux**: `sudo apt install tesseract-ocr`

### Still stuck?
[Open an issue](../../issues) with:
- Your operating system (Mac/Windows/Linux)
- The error message you're seeing
- A sample PDF if possible (or just the platform name like "JSTOR")

---

## 🔄 Updates

RoboStripper checks for updates when you open it.

- **Python users**: Auto-updates with one click
- **App/exe users**: Opens the download page for the latest version

To disable update checks, run with: `robostripper.py --no-update` (coming soon)

---

## 📜 License

MIT License — use it, modify it, share it!

---

Made with 💅 for faculty and students who need readings made accessible or just like being read aloud to by robots. 
