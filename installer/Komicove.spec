from pathlib import Path
import sys

root = Path(SPECPATH).parent
a = Analysis([str(root / "installer" / "desktop_entry.py")], pathex=[str(root)],
    binaries=[], datas=[(str(root / "Icons"), "Icons"),
    (str(root / "komicovelogo.png"), "."), (str(root / "Komicove.ico"), "."),
    (str(root / "LICENSE"), ".")], hiddenimports=["PIL._tkinter_finder"],
    excludes=["pytest", "komicove_backend"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Komicove",
          console=sys.platform != "win32", icon=str(root / "Komicove.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="Komicove")
