"""Evaluate comic OCR against a small, manually reviewed local manifest."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from komicove_app.comic_translation import TranslationError, recognize


def coverage(detected, expected):
    left = max(detected[0], expected[0])
    top = max(detected[1], expected[1])
    right = min(detected[2], expected[2])
    bottom = min(detected[3], expected[3])
    intersection = max(0, right-left) * max(0, bottom-top)
    expected_area = (expected[2]-expected[0]) * (expected[3]-expected[1])
    detected_area = (detected[2]-detected[0]) * (detected[3]-detected[1])
    return intersection / max(min(expected_area, detected_area), 1e-9)


def evaluate(manifest):
    root = Path(manifest).resolve().parent
    source = json.loads(Path(manifest).read_text(encoding="utf-8"))
    report = []
    for page in source["pages"]:
        image_path = Path(page["image"])
        if not image_path.is_absolute():
            image_path = root / image_path
        started = time.perf_counter()
        error = None
        try:
            rows = recognize(Image.open(image_path), page.get("language", "eng"),
                             page.get("manga", False))
        except TranslationError as exc:
            rows = []
            error = exc.code
        expected = [entry for entry in page["regions"] if entry.get("translate", True)]
        matches = []
        claimed = set()
        for entry in expected:
            ranked = sorted(((coverage(row.box, entry["box"]), index, row)
                             for index, row in enumerate(rows)), reverse=True,
                            key=lambda item: item[0])
            best = ranked[0] if ranked else (0, -1, None)
            if best[0] >= .35:
                claimed.add(best[1])
            matches.append({"expected": entry.get("text", ""),
                            "type": entry.get("type", "dialogue"),
                            "orientation": entry.get("orientation", "horizontal"),
                            "coverage": round(best[0], 3),
                            "recognized": best[2].original if best[2] else "",
                            "detected_box": ([round(value, 4) for value in best[2].box]
                                             if best[2] else None)})
        false_positive = [row.original for index, row in enumerate(rows)
                          if index not in claimed and not row.uncertain]
        report.append({"page": page["id"], "seconds": round(time.perf_counter()-started, 3),
                       "error": error,
                       "expected": len(expected),
                       "detected": sum(match["coverage"] >= .35 for match in matches),
                       "false_positive": false_positive, "matches": matches})
    totals = {"expected": sum(row["expected"] for row in report),
              "detected": sum(row["detected"] for row in report),
              "false_positive": sum(len(row["false_positive"]) for row in report),
              "seconds": round(sum(row["seconds"] for row in report), 3)}
    totals["recall"] = round(totals["detected"] / max(1, totals["expected"]), 4)
    totals["false_positive_rate"] = round(
        totals["false_positive"] / max(1, totals["detected"] + totals["false_positive"]), 4)
    return {"summary": totals, "pages": report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = evaluate(args.manifest)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    sys.stdout.buffer.write(rendered.encode("utf-8") + b"\n")
