def reading_regions(width, height, manga=False):
    columns = 4 if width > height else 2
    halves = range(columns // 2)
    if manga:
        halves = reversed(list(halves))
    return [(max(0, x / columns - .06), max(0, y / 3 - .06),
             min(1, (x + 1) / columns + .06), min(1, (y + 1) / 3 + .06))
            for half in halves for y in range(3)
            for x in ([half * 2 + 1, half * 2] if manga else [half * 2, half * 2 + 1])]


def detect_regions(image, manga=False):
    small = image.convert('RGB')
    small.thumbnail((320, 480))
    width, height = small.size
    pixels = small.load()
    regions = []

    def split(left, top, right, bottom, depth=0):
        if depth < 5:
            for axis in (0, 1):
                start, end = (top, bottom) if axis == 0 else (left, right)
                span = end - start
                run = best = cut = 0
                low, high = (left, right) if axis == 0 else (top, bottom)
                for pos in range(start + span // 6, end - span // 6):
                    white = sum(min(pixels[q, pos] if axis == 0 else pixels[pos, q]) > 235
                                for q in range(low, high))
                    run = run + 1 if white >= (high - low) * .98 else 0
                    if run > best:
                        best, cut = run, pos - run // 2
                if max(3, span // 100) <= best < span / 4:
                    boxes = ([(left, top, right, cut), (left, cut, right, bottom)] if axis == 0
                             else [(left, top, cut, bottom), (cut, top, right, bottom)])
                    if axis == 1 and manga:
                        boxes.reverse()
                    for box in boxes:
                        split(*box, depth + 1)
                    return
        regions.append((left / width, top / height, right / width, bottom / height))

    split(0, 0, width, height)
    fallback = len(regions) == 1
    return (reading_regions(*image.size, manga) if fallback else regions), fallback
