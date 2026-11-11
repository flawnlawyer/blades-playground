#!/usr/bin/env python3
"""make_icon.py — build assets/logo.ico (Windows/macOS app icon) from assets/logo.png.  Needs Pillow."""
from PIL import Image
src = Image.open("assets/logo.png").convert("RGBA")
side = max(src.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))                    # pad to a square, centred
canvas.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
canvas.save("assets/logo.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote assets/logo.ico")
