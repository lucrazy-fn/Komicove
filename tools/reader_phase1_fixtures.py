"""Generate synthetic large comics for USB reader tests; no user comics are read."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import zipfile
import zlib

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=False)
pages = root / "pages"
pages.mkdir()
width, height = 1280, 2048
size = width * height * 3
header = struct.pack("<2sIHHIIIIHHIIIIII", b"BM", size + 54, 0, 0, 54, 40,
                     width, height, 1, 24, 0, size, 0, 0, 0, 0)
for index in range(16):
    (pages / f"page{index:04d}.bmp").write_bytes(header + os.urandom(size))
def rar4_block(kind, flags, payload):
    body = struct.pack("<BHH", kind, flags, len(payload) + 7) + payload
    return struct.pack("<H", zlib.crc32(body) & 0xffff) + body

# WinRAR 7 no longer writes RAR4. Emit standard stored RAR4 records for this fixture.
with (root / "large-rar4.cbr").open("xb") as archive:
    archive.write(b"Rar!\x1a\x07\x00")
    archive.write(rar4_block(0x73, 0, bytes(6)))
    for page in sorted(pages.iterdir()):
        data = page.read_bytes()
        name = page.name.encode("ascii")
        fields = struct.pack("<IIBIIBBHI", len(data), len(data), 2,
                             zlib.crc32(data), 0, 20, 0x30, len(name), 0x20)
        archive.write(rar4_block(0x74, 0x8000, fields + name))
        archive.write(data)
    archive.write(rar4_block(0x7b, 0x4000, b""))
with tarfile.open(root / "large.cbt", "w", format=tarfile.USTAR_FORMAT) as archive:
    for page in sorted(pages.iterdir()):
        archive.add(page, arcname=page.name)
with zipfile.ZipFile(root / "large.cbz", "w", compression=zipfile.ZIP_STORED) as archive:
    for page in sorted(pages.iterdir()):
        archive.write(page, page.name)
rar = Path(r"C:\Program Files\WinRAR\Rar.exe")
seven = Path(r"C:\Program Files\7-Zip\7z.exe")
commands = [
    [str(rar), "a", "-ma5", "-m1", "-s-", "-ep1", str(root / "large-rar5.rar"), str(pages / "*.bmp")],
    [str(rar), "a", "-ma5", "-m1", "-s", "-ep1", str(root / "solid-rar5.rar"), str(pages / "*.bmp")],
    [str(seven), "a", "-t7z", "-mx=1", "-ms=off", str(root / "large.cb7"), str(pages / "*.bmp")],
    [str(seven), "a", "-t7z", "-mx=1", "-ms=on", str(root / "solid.7z"), str(pages / "*.bmp")],
]
for command in commands:
    subprocess.run(command, check=True, capture_output=True)
subprocess.run([str(seven), "t", str(root / "large-rar4.cbr")], check=True, capture_output=True)
for archive in root.iterdir():
    if archive.is_file():
        print(archive.name, archive.stat().st_size)
