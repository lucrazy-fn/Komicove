from pathlib import Path
import hashlib
import os
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs

root = Path(SPECPATH).parent
ai_datas = []
ai_binaries = []
ai_imports = []
if os.environ.get('KOMICOVE_BUILD_WITH_AI', '1') != '0':
    model = root / 'local_models' / 'inkwell.onnx'
    if not model.is_file() or model.stat().st_size != 12256396:
        raise SystemExit('Full build requires local_models/inkwell.onnx. See docs/COMPLETE_BUILDS.md.')
    if hashlib.sha256(model.read_bytes()).hexdigest() != 'f240e1296efd048126b26ea4ffeddc97d7c3aa667a37e3127c2afc6d5e9b9578':
        raise SystemExit('Inkwell model checksum mismatch.')
    import numpy
    import onnxruntime
    ai_datas = [(str(model), 'local_models'), (str(root / 'installer' / 'inkwell'), 'local_models')]
    ai_binaries = collect_dynamic_libs('onnxruntime')
    ai_imports = ['numpy', 'onnxruntime']
a = Analysis([str(root / "installer" / "desktop_entry.py")], pathex=[str(root)],
    binaries=ai_binaries, datas=ai_datas + [(str(root / "Icons"), "Icons"),
    (str(root / "assets_redesign"), "assets_redesign"),
    (str(root / "komicovelogo.png"), "."), (str(root / "Komicove.ico"), "."),
    (str(root / "LICENSE"), ".")], hiddenimports=["PIL._tkinter_finder"] + ai_imports,
    excludes=["pytest", "komicove_backend"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Komicove",
          console=sys.platform != "win32", icon=str(root / "Komicove.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="Komicove")
