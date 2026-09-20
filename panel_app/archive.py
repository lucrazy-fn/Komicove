from __future__ import annotations
import io, os, re, threading, zipfile, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from .translations import ui
try:
    import rarfile
except ImportError: rarfile=None
try:
    try: import pymupdf as fitz
    except ImportError: import fitz
except ImportError: fitz=None

IMG_EXTS={".jpg",".jpeg",".png",".webp",".gif",".bmp"}
SUPPORTED_EXTENSIONS=(".cbz", ".cbr", ".zip", ".rar", ".pdf", ".7z", ".cb7", ".tar", ".cbt", ".epub")

def find_7zip():
    candidates = [os.environ.get("PANEL_7ZIP_PATH"), shutil.which("7z"), shutil.which("7zz"),
                  r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"]
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)

def run_7zip(executable, arguments):
    try:
        result = subprocess.run([executable, *arguments], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        raise ValueError(ui("O 7-Zip demorou demais para abrir o arquivo.", "7-Zip took too long to open the file.")) from exc
    if result.returncode != 0:
        raise ValueError(ui("O 7-Zip não conseguiu ler o arquivo. Verifique se está íntegro e sem senha.", "7-Zip could not read the file. Make sure it is intact and not password-protected."))
    return result.stdout
def natural_key(value): return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',str(value))]
class ArchiveBackend:
    def __init__(self,path): self.path=path; self.kind=None; self.names=[]; self._pdf_doc=None; self._detect()
    def _detect(self):
        self._seven_zip = find_7zip()
        suffix=Path(self.path).suffix.lower()
        if suffix == '.epub':
            from .epub import image_pages
            self.kind = 'zip'
            with zipfile.ZipFile(self.path) as source:
                self.names = image_pages(source)
        elif zipfile.is_zipfile(self.path):
            self.kind="zip"
            with zipfile.ZipFile(self.path) as source: self.names=sorted([n for n in source.namelist() if Path(n).suffix.lower() in IMG_EXTS and not Path(n).name.startswith('.')],key=natural_key)
        elif self._seven_zip and suffix in {".rar", ".cbr", ".7z", ".cb7", ".tar", ".cbt"}:
            self.kind="7zip"
            listing=run_7zip(self._seven_zip,["l","-slt","-ba","-sccUTF-8","--",str(Path(self.path).resolve())]).decode("utf-8")
            self.names=sorted([line[7:] for line in listing.splitlines() if line.startswith("Path = ")
                and Path(line[7:]).suffix.lower() in IMG_EXTS and not Path(line[7:]).name.startswith(".")],key=natural_key)
        elif rarfile and rarfile.is_rarfile(self.path):
            self.kind="rar"
            with rarfile.RarFile(self.path) as source: self.names=sorted([n for n in source.namelist() if Path(n).suffix.lower() in IMG_EXTS and not Path(n).name.startswith('.')],key=natural_key)
        elif fitz and suffix==".pdf": self.kind="pdf"; self._pdf_doc=fitz.open(self.path); self.names=[f"page_{i}" for i in range(self._pdf_doc.page_count)]
        elif suffix in {".7z", ".cb7", ".tar", ".cbt"}:
            raise ValueError(ui("Instale o 7-Zip ou configure PANEL_7ZIP_PATH com o caminho do 7z.exe.", "Install 7-Zip or set PANEL_7ZIP_PATH to the 7z executable."))
        else: raise ValueError(ui(f"Formato não suportado: {suffix}", f"Unsupported format: {suffix}"))
    @property
    def count(self): return len(self.names)
    def read_page(self,index):
        if not 0<=index<self.count: raise IndexError(index)
        if self.kind=="zip":
            with zipfile.ZipFile(self.path) as source:return source.read(self.names[index])
        if self.kind=="rar":
            with rarfile.RarFile(self.path) as source:return source.read(self.names[index])
        if self.kind=="7zip":
            return run_7zip(self._seven_zip,["x","-so","-spd","--",str(Path(self.path).resolve()),self.names[index]])
        page=self._pdf_doc.load_page(index); return page.get_pixmap(matrix=fitz.Matrix(2,2)).tobytes("png")
    def close(self):
        if self._pdf_doc: self._pdf_doc.close(); self._pdf_doc=None
def extract_cover_only(path):
    backend=ArchiveBackend(path)
    try:
        if backend.count == 0:
            raise ValueError(ui("O arquivo não contém páginas de imagem reconhecidas.", "The file does not contain recognized image pages."))
        return backend.read_page(0)
    finally:backend.close()
def pil_from_bytes(data): return Image.open(io.BytesIO(data)).convert("RGBA")
def rounded_image(image,radius):
    mask=Image.new("L",image.size,0); ImageDraw.Draw(mask).rounded_rectangle([0,0,image.width-1,image.height-1],radius=radius,fill=255)
    out=Image.new("RGBA",image.size); out.paste(image.convert("RGBA"),mask=mask); return out
class SmartPageLoader:
    WINDOW=4
    def __init__(self,path): self.backend=ArchiveBackend(path); self._cache={}; self._lock=threading.Lock(); self._prefetching=set()
    @property
    def count(self):return self.backend.count
    @property
    def names(self):return self.backend.names
    @property
    def entries(self):return self.backend.names
    def get_pil(self,index):
        with self._lock:
            if index in self._cache:return self._cache[index]
        image=pil_from_bytes(self.backend.read_page(index))
        with self._lock:
            self._cache[index]=image
            for key in list(self._cache):
                if abs(key-index)>self.WINDOW:self._cache.pop(key,None)
        return image
    def prefetch(self,index):
        if not 0<=index<self.count:return
        with self._lock:
            if index in self._cache or index in self._prefetching:return
            self._prefetching.add(index)
        def work():
            try:self.get_pil(index)
            finally:
                with self._lock:self._prefetching.discard(index)
        threading.Thread(target=work,daemon=True).start()
    def get_thumbnail_pil(self,index,width,height):
        image=self.get_pil(index).convert("RGB"); image.thumbnail((width,height),Image.BILINEAR); return image
    def close(self):self.backend.close(); self._cache.clear()
