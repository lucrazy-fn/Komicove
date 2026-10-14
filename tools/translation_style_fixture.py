"""Authorial page for checking lettering scale on desktop and Android."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageDraw, ImageFont

from komicove_app.comic_translation import TextRegion
from komicove_app.translation_views import draw_translation_overlay


def font(size):
    for name in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    output = Path(__file__).resolve().parents[1] / "build/translation-style"
    output.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (1200, 1700), "#f7f5ef")
    draw = ImageDraw.Draw(page)
    for top, bottom in ((80, 320), (360, 690), (730, 1120), (1160, 1580)):
        draw.rounded_rectangle((90, top, 1110, bottom), radius=80, fill="white")
    draw.text((205, 173), "psst...", font=font(28), fill="#171417")
    draw.text((205, 465), "HELLO THERE", font=font(58), fill="#171417")
    draw.text((205, 840), "STOP!", font=font(112), fill="#171417")
    draw.text((205, 1354), "go", font=font(34), fill="#171417")
    draw.text((300, 1288), "NOW!", font=font(104), fill="#171417")
    specs = (
        ((195, 165, 410, 224), "psst...", "psiu...", (1.0,)),
        ((195, 450, 850, 545), "HELLO THERE", "OLÁ AMIGO", (1.0, 1.0)),
        ((195, 825, 700, 980), "STOP!", "PARE!", (1.0,)),
        ((195, 1275, 760, 1410), "go NOW!", "vá AGORA!", (.6, 1.6)),
    )
    rows = [TextRegion(tuple(value / (1200 if index % 2 == 0 else 1700)
                             for index, value in enumerate(box)), original, 1,
                       translated, word_scales=scales)
            for box, original, translated, scales in specs]
    page.save(output / "original.png")
    draw_translation_overlay(page, rows, (0, 0, page.width, page.height)).save(output / "translated.png")
    with ZipFile(output / "lettering-scale.cbz", "w", ZIP_DEFLATED) as archive:
        content = BytesIO()
        page.save(content, format="PNG")
        archive.writestr("001.png", content.getvalue())
    print(output)


if __name__ == "__main__":
    main()
