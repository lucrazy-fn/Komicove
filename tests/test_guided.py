import unittest
from PIL import Image, ImageDraw
from panel_app.guided import detect_regions, reading_regions


class GuidedTests(unittest.TestCase):
    def test_gutters_and_manga_order(self):
        image = Image.new('RGB', (300, 400), 'black')
        ImageDraw.Draw(image).rectangle((145, 0, 155, 399), fill='white')
        regions, fallback = detect_regions(image)
        reverse, _ = detect_regions(image, manga=True)
        self.assertFalse(fallback)
        self.assertEqual(len(regions), 2)
        self.assertEqual(reverse, list(reversed(regions)))

    def test_fallback_covers_spread(self):
        regions, fallback = detect_regions(Image.new('RGB', (800, 400), 'black'))
        self.assertTrue(fallback)
        self.assertEqual(len(regions), 12)
        for x in range(21):
            for y in range(21):
                self.assertTrue(any(l <= x / 20 <= r and t <= y / 20 <= b
                                    for l, t, r, b in regions))
        self.assertGreater(reading_regions(800, 400, True)[0][0], .5)

    def test_tiny_page(self):
        regions, fallback = detect_regions(Image.new('RGB', (1, 1), 'black'))
        self.assertTrue(fallback)
        self.assertTrue(regions)
