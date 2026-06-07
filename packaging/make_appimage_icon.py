"""Generate a 256x256 PNG icon for the Linux AppImage."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bobozip.png")
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=32, fill=(30, 120, 220, 255))

    text = "BZ"
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 130)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, font=font, fill="white")

    img.save(out, "PNG")
    print(f"[icon] wrote {out}")


if __name__ == "__main__":
    main()
