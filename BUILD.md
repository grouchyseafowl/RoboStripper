# 🏗️ Building RoboStripper

## Building for Mac (Fancy DMG)

### Prerequisites
- Python 3.12+
- PyInstaller: `pip install pyinstaller`
- All dependencies: `pip install pymupdf pytesseract Pillow`

### Build Steps

1. **Generate the DMG background** (only needed once):
   ```bash
   python3 scripts/create_dmg_background.py
   ```

2. **Build the DMG**:
   ```bash
   ./scripts/build_mac_dmg.sh
   ```

This creates:
- `dist/RoboStripper.app` - Standalone application (TUI, opens in Terminal)
- `dist/RoboStripper.dmg` - Professional installer (176MB)

### What the Build Does

1. ✅ Builds .app bundle with PyInstaller (TUI)
2. ✅ Cleans extended attributes
3. ✅ Ad-hoc code signs the app (prevents "damaged" error)
4. ✅ Creates professional DMG with:
   - Custom background image (👠✨💅)
   - Positioned icons
   - Applications folder symlink
   - Custom window size/layout

### Testing

Test the standalone app:
```bash
open dist/RoboStripper.app
```

Test the DMG installer:
```bash
open dist/RoboStripper.dmg
```

### Distributing

Upload to GitHub Releases:
1. Test both the .app and .dmg locally
2. Upload `dist/RoboStripper.dmg` to a GitHub Release
3. Users download, mount, and drag to Applications

### About Code Signing

The build uses **ad-hoc code signing** (`codesign -s -`), which:
- ✅ Prevents the "damaged" error when opening locally-built apps
- ✅ Is free (no Apple Developer account needed)
- ⚠️ Still shows Gatekeeper warnings on first launch
- ℹ️ Users can bypass: Right-click → Open → Open

For **full code signing** (no warnings):
- Requires Apple Developer account ($99/year)
- Replace `codesign -s -` with `codesign -s "Developer ID Application: Your Name"`

## Building for Windows

Use GitHub Actions (`.github/workflows/build.yml`) or build locally:

```bash
pyinstaller --name "RoboStripper" --onefile --console --icon assets/robostripper_icon.ico robostripper.py
```

Creates: `dist/RoboStripper.exe`

---

💅✨👠
