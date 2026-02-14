#!/usr/bin/env python3
"""
Creates a HIGH FEMME CYBORG SLUT background for the DMG installer 💅✨🤖
"""

from PIL import Image, ImageDraw, ImageFont
import os

# DMG window size
WIDTH = 600
HEIGHT = 400

# Create image with dark cyberpunk gradient
img = Image.new('RGB', (WIDTH, HEIGHT), '#0A0A0A')
draw = ImageDraw.Draw(img)

# Cyberpunk gradient - dark purple to black
for y in range(HEIGHT):
    # Purple-pink gradient from top
    progress = y / HEIGHT
    r = int(15 + progress * 10)
    g = int(5 + progress * 5)
    b = int(25 + progress * 15)
    color = (r, g, b)
    draw.line([(0, y), (WIDTH, y)], fill=color)

# Add some neon accent lines for that cyborg aesthetic
overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
overlay_draw = ImageDraw.Draw(overlay)

# Horizontal accent lines (like scan lines)
for y in range(0, HEIGHT, 4):
    alpha = 8 if y % 8 == 0 else 3
    overlay_draw.line([(0, y), (WIDTH, y)], fill=(255, 105, 180, alpha))

# Diagonal accent line (neon pink)
for i in range(3):
    overlay_draw.line([(0, 80 + i), (WIDTH, 120 + i)], fill=(255, 20, 147, 25))

img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
draw = ImageDraw.Draw(img)

# Try to use SF Pro with italic for that SLEEK look
font_path = None
for path in [
    '/System/Library/Fonts/SF-Pro-Display-Bold.otf',
    '/System/Library/Fonts/SF-Pro.ttf',
    '/Library/Fonts/SF-Pro-Display-Bold.otf',
    '/System/Library/Fonts/Helvetica.ttc',
]:
    if os.path.exists(path):
        font_path = path
        break

try:
    if font_path:
        font_main = ImageFont.truetype(font_path, 24)
        font_emoji = ImageFont.truetype('/System/Library/Fonts/Apple Color Emoji.ttc', 52)
    else:
        font_main = ImageFont.load_default()
        font_emoji = ImageFont.load_default()
except:
    font_main = ImageFont.load_default()
    font_emoji = ImageFont.load_default()

# Main text with GRADIENT effect (cyberpunk pink to white)
instruction = "Drag to Applications to install"

# Calculate text position
bbox = draw.textbbox((0, 0), instruction, font=font_main)
text_width = bbox[2] - bbox[0]
text_x = (WIDTH - text_width) // 2
text_y = 30

# Create gradient text effect
gradient_img = Image.new('RGBA', (text_width, 40), (0, 0, 0, 0))
gradient_draw = ImageDraw.Draw(gradient_img)

# Draw text multiple times for glow effect
for offset in [(2, 2), (1, 1), (0, 0)]:
    alpha = 100 if offset != (0, 0) else 255
    color = (255, 20, 147, alpha) if offset != (0, 0) else (255, 105, 180, 255)
    gradient_draw.text(offset, instruction, fill=color, font=font_main)

# Add white highlight
gradient_draw.text((0, 0), instruction, fill=(255, 255, 255, 180), font=font_main)

# Paste gradient text
img.paste(gradient_img, (text_x, text_y), gradient_img)

# CYBERPUNK EMOJI footer with GLOW
footer_emojis = "👠 ✨ 💅"
try:
    bbox = draw.textbbox((0, 0), footer_emojis, font=font_emoji)
    text_width = bbox[2] - bbox[0]
    emoji_x = (WIDTH - text_width) // 2
    emoji_y = HEIGHT - 75

    # Neon glow effect
    for offset in range(8, 0, -2):
        alpha = int(30 - offset * 3)
        draw.text((emoji_x + offset//2, emoji_y + offset//2), footer_emojis,
                 fill=(255, 20, 147, alpha), font=font_emoji)

    # Main emoji
    draw.text((emoji_x, emoji_y), footer_emojis, fill='#FF1493', font=font_emoji)

except Exception as e:
    # Fallback text
    fallback = "✨ RoboStripper ✨"
    try:
        font_fallback = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
        bbox = draw.textbbox((0, 0), fallback, font=font_fallback)
        text_width = bbox[2] - bbox[0]
        text_x = (WIDTH - text_width) // 2

        # Glow
        draw.text((text_x + 2, HEIGHT - 42), fallback, fill=(255, 20, 147, 100), font=font_fallback)
        # Main
        draw.text((text_x, HEIGHT - 40), fallback, fill='#FF69B4', font=font_fallback)
    except:
        pass

# Save
output_path = 'assets/dmg_background.png'
os.makedirs('assets', exist_ok=True)
img.save(output_path, 'PNG')

print(f"✅ HIGH FEMME CYBORG SLUT DMG background created: {output_path}")
print(f"   Size: {WIDTH}x{HEIGHT}")
print("   💅✨🤖👠")
