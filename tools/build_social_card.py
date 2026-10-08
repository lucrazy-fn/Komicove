from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUTPUT = DOCS / "assets" / "social-card.png"
WIDTH, HEIGHT = 1200, 630


def font(name: str, size: int):
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


canvas = Image.new("RGB", (WIDTH, HEIGHT), "#101013")
pixels = canvas.load()
for y in range(HEIGHT):
    for x in range(WIDTH):
        edge = max(0.0, 1 - (((x - 900) / 640) ** 2 + ((y - 120) / 480) ** 2))
        pixels[x, y] = (
            int(16 + 46 * edge),
            int(16 + 8 * edge),
            int(19 + 14 * edge),
        )

glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow)
glow_draw.ellipse((650, -190, 1320, 500), fill=(255, 67, 83, 72))
glow = glow.filter(ImageFilter.GaussianBlur(95))
canvas = Image.alpha_composite(canvas.convert("RGBA"), glow)
draw = ImageDraw.Draw(canvas)

logo = Image.open(DOCS / "assets" / "logo.png").convert("RGBA")
logo.thumbnail((205, 95), Image.Resampling.LANCZOS)
canvas.alpha_composite(logo, (62, 54))

eyebrow_font = font("arialbd.ttf", 21)
headline_font = font("arialbd.ttf", 49)
meta_font = font("arial.ttf", 23)
draw.text((66, 178), "KOMICOVE 0.2.1.1", font=eyebrow_font, fill="#ff848c")
draw.text((62, 222), "YOUR COMICS.", font=headline_font, fill="#f4f0ec")
draw.text((62, 281), "YOUR UNIVERSE.", font=headline_font, fill="#ff515b")
draw.rounded_rectangle((64, 407, 446, 458), radius=25, fill="#211d23", outline="#443940", width=2)
draw.text((89, 420), "WINDOWS  ·  LINUX  ·  ANDROID", font=eyebrow_font, fill="#d7d0d5")
draw.text((65, 501), "Open source comic reader", font=meta_font, fill="#aea7b0")
draw.text((65, 537), "Local files. Offline reading. No account.", font=meta_font, fill="#aea7b0")

screenshot = Image.open(DOCS / "screenshots" / "desktop-biblioteca.png").convert("RGB")
screenshot = ImageOps.fit(screenshot, (700, 420), method=Image.Resampling.LANCZOS, centering=(0.55, 0.47))
shot_mask = Image.new("L", screenshot.size, 0)
ImageDraw.Draw(shot_mask).rounded_rectangle((0, 0, screenshot.width - 1, screenshot.height - 1), radius=22, fill=255)
shot = screenshot.convert("RGBA")
shot.putalpha(shot_mask)

shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
shadow_draw = ImageDraw.Draw(shadow)
shadow_draw.rounded_rectangle((506, 122, 1194, 566), radius=26, fill=(0, 0, 0, 180))
shadow = shadow.filter(ImageFilter.GaussianBlur(26))
canvas = Image.alpha_composite(canvas, shadow)
canvas.alpha_composite(shot, (500, 99))
draw = ImageDraw.Draw(canvas)
draw.rounded_rectangle((500, 99, 1199, 518), radius=22, outline="#74616d", width=2)
draw.rectangle((500, 484, 1199, 518), fill="#19181d")
draw.text((526, 491), "YOUR COLLECTION. YOUR NEXT CHAPTER.", font=eyebrow_font, fill="#ffc3c7")

canvas.convert("RGB").save(OUTPUT, "PNG", optimize=True)
print(f"Created {OUTPUT} ({WIDTH}x{HEIGHT})")
