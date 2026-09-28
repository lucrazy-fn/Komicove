"""Create labeled previews of the untouched redesign references."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    files = sorted(args.source.rglob("*.png"))
    args.output.mkdir(parents=True, exist_ok=True)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 24) if font_path.exists() else ImageFont.load_default()
    cell_width, cell_height, columns, rows = 640, 450, 3, 3
    for offset in range(0, len(files), columns * rows):
        sheet = Image.new("RGB", (cell_width * columns, cell_height * rows), "#202126")
        draw = ImageDraw.Draw(sheet)
        for position, path in enumerate(files[offset:offset + columns * rows]):
            number = offset + position + 1
            x = position % columns * cell_width
            y = position // columns * cell_height
            with Image.open(path) as original:
                thumb = ImageOps.contain(ImageOps.exif_transpose(original).convert("RGB"),
                                         (cell_width - 24, cell_height - 70))
                sheet.paste(thumb, (x + (cell_width - thumb.width) // 2, y + 44))
                label = f"{number:02d}  {original.width}x{original.height}  {path.name.split(',')[-1]}"
            draw.text((x + 12, y + 10), label, fill="white", font=font)
        sheet.save(args.output / f"contact-{offset // (columns * rows) + 1:02d}.jpg",
                   quality=90)
    print(f"{len(files)} references in {len(list(args.output.glob('contact-*.jpg')))} sheets")


if __name__ == "__main__":
    main()
