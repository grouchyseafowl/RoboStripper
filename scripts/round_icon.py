#!/usr/bin/env python3
"""
Adds rounded corners to the RoboStripper icon for a modern macOS look
"""

from PIL import Image, ImageDraw
import os

def add_rounded_corners(image, radius):
    """Add rounded corners to an image"""
    # Create a mask for rounded corners
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)

    # Draw rounded rectangle
    draw.rounded_rectangle([(0, 0), image.size], radius=radius, fill=255)

    # Apply mask to image
    output = Image.new('RGBA', image.size, (0, 0, 0, 0))
    output.paste(image, (0, 0))
    output.putalpha(mask)

    return output

# Read the original icon
icon_path = 'assets/robostripper_icon.png'
if not os.path.exists(icon_path):
    print(f"❌ Icon not found: {icon_path}")
    exit(1)

icon = Image.open(icon_path).convert('RGBA')
print(f"📏 Original icon size: {icon.size}")

# macOS icon corner radius is typically ~22.37% of the icon size
# For standard app icons, this creates the characteristic rounded square look
radius = int(icon.size[0] * 0.2237)

# Add rounded corners
rounded_icon = add_rounded_corners(icon, radius)

# Save the rounded version
output_path = 'assets/robostripper_icon_rounded.png'
rounded_icon.save(output_path, 'PNG')

print(f"✅ Rounded icon created: {output_path}")
print(f"   Corner radius: {radius}px")
print("   💅✨👠")

# Also update the .iconset for macOS
iconset_dir = 'RoboStripper.iconset'
if os.path.exists(iconset_dir):
    print(f"\n🔄 Updating iconset with rounded corners...")
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for size in sizes:
        rounded_resized = rounded_icon.resize((size, size), Image.Resampling.LANCZOS)
        rounded_resized.save(f"{iconset_dir}/icon_{size}x{size}.png")
        if size <= 512:  # @2x versions
            rounded_resized_2x = rounded_icon.resize((size * 2, size * 2), Image.Resampling.LANCZOS)
            rounded_resized_2x.save(f"{iconset_dir}/icon_{size}x{size}@2x.png")
    print("✅ Iconset updated!")
