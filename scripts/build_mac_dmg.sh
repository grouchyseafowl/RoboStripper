#!/bin/bash
set -e

echo "🏗️  Building RoboStripper for Mac..."

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist

# Build with PyInstaller (TUI app; opens in Terminal)
echo "📦 Building .app bundle..."
pyinstaller \
    --name "RoboStripper" \
    --console \
    --icon assets/robostripper_icon.icns \
    robostripper.py

# Clean the .app bundle
echo "🧹 Cleaning .app bundle..."
xattr -cr "dist/RoboStripper.app" 2>/dev/null || true
find "dist/RoboStripper.app" -name "._*" -delete 2>/dev/null || true
find "dist/RoboStripper.app" -name ".DS_Store" -delete 2>/dev/null || true

echo "✨ TUI app with sexy icon ready!"

# Create DMG staging area
echo "💿 Creating DMG..."
DMG_DIR="dist/dmg_staging"
mkdir -p "$DMG_DIR"

# Copy app to staging
cp -r "dist/RoboStripper.app" "$DMG_DIR/"

# Create Applications symlink for easy drag-to-install
ln -s /Applications "$DMG_DIR/Applications"

# Create background image directory (will be hidden in DMG)
mkdir -p "$DMG_DIR/.background"
if [ -f "assets/dmg_background.png" ]; then
    cp assets/dmg_background.png "$DMG_DIR/.background/"
    echo "✨ Using custom background"
else
    echo "⚠️  No background image found (assets/dmg_background.png) - using default"
fi

# Hide the background folder
SetFile -a V "$DMG_DIR/.background"

# Create temporary DMG
DMG_TEMP="dist/RoboStripper-temp.dmg"
DMG_FINAL="dist/RoboStripper.dmg"

hdiutil create -volname "RoboStripper" -srcfolder "$DMG_DIR" -ov -format UDRW "$DMG_TEMP"

# Mount it to customize
echo "🎨 Customizing DMG appearance..."
MOUNT_DIR="/Volumes/RoboStripper"
hdiutil attach "$DMG_TEMP" -mountpoint "$MOUNT_DIR"

# Wait for mount
sleep 2

# Use AppleScript to set view options
osascript <<EOF
tell application "Finder"
    tell disk "RoboStripper"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {100, 100, 700, 500}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 128
        set background picture of viewOptions to file ".background:dmg_background.png"
        set shows item info of viewOptions to false
        set shows icon preview of viewOptions to true

        -- Position icons with better spacing
        set position of item "RoboStripper.app" of container window to {150, 180}
        set position of item "Applications" of container window to {450, 180}

        close
        open
        update without registering applications
        delay 3
    end tell
end tell
EOF

# Hide system files in the mounted DMG
SetFile -a V "$MOUNT_DIR/.background" 2>/dev/null || true
SetFile -a V "$MOUNT_DIR/.DS_Store" 2>/dev/null || true
SetFile -a V "$MOUNT_DIR/.fseventsd" 2>/dev/null || true

# Ensure changes are written
sync

# Unmount
hdiutil detach "$MOUNT_DIR"

# Convert to compressed final DMG
echo "📦 Compressing final DMG..."
rm -f "$DMG_FINAL"
hdiutil convert "$DMG_TEMP" -format UDZO -imagekey zlib-level=9 -o "$DMG_FINAL"

# Clean up
rm -f "$DMG_TEMP"
rm -rf "$DMG_DIR"

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 Created files:"
echo "   • dist/RoboStripper.app (standalone app)"
echo "   • dist/RoboStripper.dmg (installer)"
echo ""
echo "🧪 To test the app:"
echo "   open dist/RoboStripper.app"
echo ""
echo "🧪 To test the DMG:"
echo "   open dist/RoboStripper.dmg"
echo ""
echo "💅✨👠"
