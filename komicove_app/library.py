from pathlib import Path
from komicove_app.archive import SUPPORTED_EXTENSIONS
def scan(folder):
    root=Path(folder)
    return sorted((str(p) for p in root.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS),key=str.casefold)
