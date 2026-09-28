"""Rasterize the bundled official Lucide SVG sources for Tkinter.

This is a development/build helper.  Komicove loads only the generated PNGs
at runtime, so CairoSVG is not a user-facing application dependency.
"""

from __future__ import annotations

import io
from pathlib import Path

import cairosvg
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets_redesign" / "icons"
OUTPUT = SOURCE / "generated"
SIZE = 64

PALETTES = {
    "dark-normal": "#a1adba",
    "dark-hover": "#f5f6f8",
    "dark-active": "#ff4b55",
    "light-normal": "#53606c",
    "light-hover": "#1a2028",
    "light-active": "#cf2633",
    "white": "#ffffff",
}


def render_svg(source: Path, color: str) -> Image.Image:
    svg = source.read_text(encoding="utf-8").replace("currentColor", color)
    png = cairosvg.svg2png(
        bytestring=svg.encode("utf-8"), output_width=SIZE, output_height=SIZE,
    )
    return Image.open(io.BytesIO(png)).convert("RGBA")


def active_glow(icon: Image.Image) -> Image.Image:
    alpha = icon.getchannel("A")
    halo = Image.new("RGBA", icon.size, (255, 42, 57, 0))
    halo.putalpha(alpha.filter(ImageFilter.GaussianBlur(5)).point(lambda a: int(a * 0.45)))
    return Image.alpha_composite(halo, icon)


def main() -> None:
    sources = sorted(SOURCE.glob("*.svg"))
    if not sources:
        raise SystemExit("No Lucide SVG sources were found.")
    for variant, color in PALETTES.items():
        target = OUTPUT / variant
        target.mkdir(parents=True, exist_ok=True)
        for source in sources:
            image = render_svg(source, color)
            if variant.endswith("active"):
                image = active_glow(image)
            image.save(target / f"{source.stem}.png", optimize=True)
    print(f"Generated {len(sources) * len(PALETTES)} local Lucide PNG assets.")


if __name__ == "__main__":
    main()
