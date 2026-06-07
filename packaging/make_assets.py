"""Generate the PNG logo assets required by the MSIX AppxManifest.

Produces simple placeholder tiles (a blue rounded square with a "BZ" mark) at
all sizes the manifest references. Run as:

    python make_assets.py <output_assets_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# (filename, width, height) pairs referenced by AppxManifest.xml
ASSETS = [
    ("StoreLogo.png", 50, 50),
    ("Square150x150Logo.png", 150, 150),
    ("Square44x44Logo.png", 44, 44),
    ("SmallTile.png", 71, 71),
    ("Wide310x150Logo.png", 310, 150),
]

BG_COLOR = (30, 120, 220, 255)
TEXT_COLOR = (255, 255, 255, 255)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_tile(path: Path, width: int, height: int) -> None:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(2, min(width, height) // 8)
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=BG_COLOR)

    text = "BZ"
    font = _load_font(max(8, int(min(width, height) * 0.5)))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - tw) / 2 - bbox[0], (height - th) / 2 - bbox[1]),
        text,
        font=font,
        fill=TEXT_COLOR,
    )
    img.save(path, "PNG")


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Assets")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, width, height in ASSETS:
        make_tile(out_dir / name, width, height)
        print(f"[assets] wrote {name} ({width}x{height})")


if __name__ == "__main__":
    main()
