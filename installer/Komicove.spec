from pathlib import Path
import hashlib
import os
import sys
import importlib.util
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

root = Path(SPECPATH).parent
ai_datas = []
ai_binaries = []
ai_imports = []
translation_datas = []
translation_binaries = []
translation_imports = []
if importlib.util.find_spec('argostranslate') is not None:
    for module in ('argostranslate', 'minisbd', 'ctranslate2', 'sentencepiece'):
        datas, binaries, imports = collect_all(module)
        translation_datas += datas
        translation_binaries += binaries
        translation_imports += imports
sevenzip_binaries = []
sevenzip_datas = []
if sys.platform.startswith('linux'):
    sevenzip = Path(os.environ.get('KOMICOVE_BUNDLED_7ZIP_PATH', ''))
    if not sevenzip.is_file() or not (sevenzip.parent / 'License.txt').is_file():
        raise SystemExit('Run linux/build.sh to include the verified 7-Zip extractor.')
    sevenzip_binaries = [(str(sevenzip), '.')]
    sevenzip_datas = [(str(sevenzip.parent / 'License.txt'), 'licenses/7zip')]
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
    binaries=ai_binaries + translation_binaries + sevenzip_binaries, datas=ai_datas + translation_datas + sevenzip_datas + [(str(root / "Icons"), "Icons"),
    (str(root / "assets_redesign"), "assets_redesign"),
    (str(root / "komicovelogo.png"), "."), (str(root / "Komicove.ico"), "."),
    (str(root / "LICENSE"), ".")], hiddenimports=["PIL._tkinter_finder"] + ai_imports + translation_imports,
    excludes=["pytest", "komicove_backend", "stanza", "spacy", "torch"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Komicove",
          console=sys.platform != "win32", icon=str(root / "Komicove.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="Komicove")
