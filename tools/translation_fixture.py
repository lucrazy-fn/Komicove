"""Generate original comic pages for OCR and guided-reading validation."""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for path in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def page(title, manga=False):
    image = Image.new("RGB", (1200, 1600), "#f7f5ef")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 1160, 760), outline="#1b1b1b", width=12)
    draw.rectangle((40, 795, 1160, 1560), outline="#1b1b1b", width=12)
    draw.ellipse((135, 100, 900, 340), fill="white", outline="black", width=5)
    draw.text((210, 160), title, fill="black", font=font(70))
    draw.rectangle((150, 925, 1030, 1060), fill="white", outline="black", width=5)
    draw.text((205, 955), "THE STORY CONTINUES", fill="black", font=font(45))
    tilted = Image.new("RGBA", (500, 110), (0, 0, 0, 0))
    ImageDraw.Draw(tilted).text((15, 10), "RUN!", fill="black", font=font(75))
    tilted = tilted.rotate(12, expand=True)
    image.paste(tilted, (400, 1180), tilted)
    if manga:
        vertical = Image.new("RGBA", (500, 110), (0, 0, 0, 0))
        ImageDraw.Draw(vertical).text((10, 15), "DANGER", fill="black", font=font(70))
        vertical = vertical.rotate(90, expand=True)
        image.paste(vertical, (930, 160), vertical)
    return image


def main():
    output = Path(__file__).resolve().parents[1] / "build" / "translation-fixtures"
    output.mkdir(parents=True, exist_ok=True)
    pages = [page("HELLO, HERO!"), page("AMANHÃ COMEÇA"), page("MANGA PAGE", True)]
    with ZipFile(output / "authorial-ocr.cbz", "w", ZIP_DEFLATED) as archive:
        for index, image in enumerate(pages, 1):
            data = BytesIO()
            image.save(data, format="PNG")
            archive.writestr(f"{index:03}.png", data.getvalue())
    print(output / "authorial-ocr.cbz")


if __name__ == "__main__":
    main()
