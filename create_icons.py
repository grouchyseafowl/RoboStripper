#!/usr/bin/env python3
"""
Script to generate .ico and .icns files from the PNG icon for PyInstaller builds.
"""

from PIL import Image
import sys
import os

def create_ico(png_path, ico_path):
    """Convert PNG to ICO with multiple sizes."""
    img = Image.open(png_path)
    # ICO supports multiple sizes - include common Windows icon sizes
    img.save(ico_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Created {ico_path}")

def create_icns(png_path, icns_path):
    """Convert PNG to ICNS for macOS."""
    # For macOS, we need to create an iconset directory structure
    img = Image.open(png_path)

    # Create temporary iconset directory
    iconset_dir = 'RoboStripper.iconset'
    os.makedirs(iconset_dir, exist_ok=True)

    # Generate required sizes for ICNS
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for size in sizes:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(f'{iconset_dir}/icon_{size}x{size}.png')
        if size <= 512:  # @2x versions
            resized.save(f'{iconset_dir}/icon_{size//2}x{size//2}@2x.png')

    # Convert iconset to icns using macOS iconutil (only available on macOS)
    if sys.platform == 'darwin':
        os.system(f'iconutil -c icns {iconset_dir} -o {icns_path}')
        print(f"Created {icns_path}")
    else:
        print(f"Skipping ICNS creation (macOS only), but iconset directory created at {iconset_dir}")

    # Clean up iconset directory (optional, keep it for Windows builds)
    # import shutil
    # shutil.rmtree(iconset_dir)

if __name__ == '__main__':
    png_file = 'robostripper_icon.png'

    if not os.path.exists(png_file):
        print(f"Error: {png_file} not found!")
        sys.exit(1)

    # Create ICO for Windows
    create_ico(png_file, 'robostripper_icon.ico')

    # Create ICNS for macOS
    create_icns(png_file, 'robostripper_icon.icns')

    print("Icon conversion complete!")
