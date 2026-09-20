
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import zipfile
import os, sys, io, json, time, threading, hashlib, re, shutil, logging
from pathlib import Path
from collections import deque
from panel_app.translations import ui

from panel_app.storage import (
    APPDATA_DIR as _APPDATA, BOOKMARKS_FILE, COVER_CACHE_DIR, FAVORITES_FILE,
    LIBRARY_CONFIG_FILE, MANUAL_STATUS_FILE, PREFS_FILE, PROGRESS_FILE,
    collection_progress, collection_read_count, export_backup, get_bookmarks,
    get_manual_status, get_progress_page, import_backup, is_favorite,
    json_load as _json_load, json_save as _json_save, load_bookmarks,
    load_favorites, load_manual_status, load_prefs, load_progress, save_prefs,
    save_progress, set_manual_status, toggle_bookmark, toggle_favorite,
    register_change_listener,
    personal_statistics, record_page_read, record_reading_time,
)
from panel_app.account_views import render_notifications, render_profile
from panel_app.sync import build_sync_payload, content_id
from panel_app.reader import (load_state as load_reader_state, save_state as save_reader_state,
    load_manual_panels, save_manual_panels)
from panel_app.downloads import manager as download_manager, render_downloads
from panel_app.community import load_catalog, save_catalog
from panel_app.moderation import can_moderate
from panel_app.auth import role_label

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("panel")
log.setLevel(logging.DEBUG)

try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False

try:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageEnhance
except ImportError:
    print("Pillow não encontrado. Instale com: pip install pillow")
    sys.exit(1)

def resource_path(relative_path):
    try:
        base = sys._MEIPASS
    except AttributeError:


        base = str(Path(__file__).resolve().parent.parent)
    return os.path.join(base, relative_path)

def _setup_unrar():
    if not HAS_RAR:
        return
    candidates = [
        r"C:\Program Files\WinRAR\UnRAR.exe",
        r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
        shutil.which("unrar"),
        shutil.which("UnRAR"),
        shutil.which("bsdtar"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            rarfile.UNRAR_TOOL = c
            return

_setup_unrar()


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', str(s))]


LANG = "pt"
TEXTS = {
    "en": {
        "library": "Library", "collections": "Collections", "theme": "Theme",
        "fit": "⊞ Fit", "fullscreen": "⛶ Fullscreen",
        "language": "Choose Language", "choose_library_folder": "Choose Library Folder",
        "error": "Error", "back": "← Back",
        "no_comics": "No comics found", "add_folder": "Choose a folder",
        "light": "Light Mode", "dark": "Dark Mode", "folder": "Folder",
        "manga_off": "🇯🇵 Manga OFF", "manga_on": "🇯🇵 Manga ON",
        "no_collections": "No collections found", "issues": "issue", "back_collections": "← Collections",
        "all": "All", "subfolders": "Folders", "series": "Series",
        "sort_name": "Name", "sort_date": "Date", "sort_progress": "Progress",
        "read": "read", "continue_reading": "▶ Continue", "sort_by": "Sort:",
        "unread": "Unread", "search": "Search…", "no_results": "No results for",
        "loading": "Loading…", "continue_section": "Continue Reading",
        "next_issue": "Next issue", "next_chapter_q": "Next issue of the series?",
        "yes": "Yes", "no": "No", "bookmark": "Bookmark", "immersive": "Immersive",
        "rotate": "Rotate", "brightness": "Brightness", "double_page": "Double Page",
        "filter_status": "Status", "f_all": "All", "f_unread": "Unread",
        "f_reading": "Reading", "f_done": "Done",
    },
    "pt": {
        "library": "Biblioteca", "collections": "Coleções", "theme": "Tema",
        "fit": "⊞ Encaixar", "fullscreen": "⛶ Tela Cheia",
        "language": "Escolha o Idioma", "choose_library_folder": "Escolher Pasta",
        "error": "Erro", "back": "← Voltar",
        "no_comics": "Nenhuma história encontrada", "add_folder": "Escolher pasta",
        "light": "Modo Claro", "dark": "Modo Escuro", "folder": "Pasta",
        "manga_off": "🇯🇵 Mangá OFF", "manga_on": "🇯🇵 Mangá ON",
        "no_collections": "Nenhuma coleção encontrada", "issues": "edição", "back_collections": "← Coleções",
        "all": "Todas", "subfolders": "Pastas", "series": "Séries",
        "sort_name": "Nome", "sort_date": "Data", "sort_progress": "Progresso",
        "read": "lidas", "continue_reading": "▶ Continuar", "sort_by": "Ordenar:",
        "unread": "Não lido", "search": "Buscar…", "no_results": "Nenhum resultado para",
        "loading": "Carregando…", "continue_section": "Continuar Lendo",
        "next_issue": "Próxima edição", "next_chapter_q": "Próxima edição da série?",
        "yes": "Sim", "no": "Não", "bookmark": "Marcador", "immersive": "Imersivo",
        "rotate": "Girar", "brightness": "Brilho", "double_page": "Página Dupla",
        "filter_status": "Status", "f_all": "Todos", "f_unread": "Não lidos",
        "f_reading": "Lendo", "f_done": "Concluídos",
    },
}

DARK = {
    "bg": "#0a0a10", "surface": "#15151f", "surface_alt": "#1c1c29",
    "surface_hover": "#26263a", "border": "#2e2e46", "border_glow": "#e2733f",
    "accent": "#df3b3b", "accent2": "#ff7a4d",
    "text": "#f2ede4", "text_dim": "#9089a8", "text_muted": "#403e5c",
    "canvas_bg": "#05050a", "btn_hover": "#2e2e46",
    "progress_bg": "#22222f", "shadow": "#000000", "shadow_light": "#1c1c2c",
    "read_badge": "#234a30", "read_badge_text": "#6ee69a",
    "search_bg": "#1c1c2c",
}
LIGHT = {
    "bg": "#faf8f5", "surface": "#ffffff", "surface_alt": "#f4f1eb",
    "surface_hover": "#ece7de", "border": "#e2dbd0", "border_glow": "#e2733f",
    "accent": "#d6362f", "accent2": "#ff7a4d",
    "text": "#211f1a", "text_dim": "#7d7566", "text_muted": "#d8d2c6",
    "canvas_bg": "#efece5", "btn_hover": "#ece7de",
    "progress_bg": "#e6e0d5", "shadow": "#c4bdae", "shadow_light": "#e2dbd0",
    "read_badge": "#dcf3e2", "read_badge_text": "#1c7a3e",
    "search_bg": "#f4f1eb",
}



from panel_app.themes import DARK as DARK, LIGHT as LIGHT, TEXTS as TEXTS

IS_DARK = True
THEME = DARK.copy()

def toggle_theme():
    global IS_DARK, THEME
    IS_DARK = not IS_DARK
    new = DARK if IS_DARK else LIGHT
    THEME.clear()
    THEME.update(new)

def current_theme_label():
    return TEXTS[LANG]["light"] if IS_DARK else TEXTS[LANG]["dark"]

def apply_scrollbar_style():
    pass
    c = THEME
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Vertical.TScrollbar",
                     background=c["surface_hover"], troughcolor=c["bg"],
                     bordercolor=c["bg"], arrowcolor=c["text_dim"],
                     lightcolor=c["surface_hover"], darkcolor=c["surface_hover"],
                     relief="flat", arrowsize=14, width=12)
    style.map("Vertical.TScrollbar",
              background=[("active", c["accent"]), ("pressed", c["accent"])],
              arrowcolor=[("active", c["text"])])

LIBRARY_FOLDER      = ""

ICON_PATH = Path(resource_path("Icons"))
ICONS = {}

def _generated_icon(kind, size):
    pass
    scale = 4
    w, h = size[0] * scale, size[1] * scale
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    line = max(5, scale * 2)
    ink = (195, 187, 255, 255)
    accent = (124, 92, 255, 255)
    soft = (104, 211, 170, 255)
    def xy(values): return tuple(int(value * scale) for value in values)
    if kind == "discover":
        draw.ellipse(xy((2, 2, 16, 16)), outline=ink, width=line)
        draw.polygon([xy((10.5, 6)), xy((8.5, 11.5)), xy((5.8, 12.3)), xy((7.7, 6.8))], fill=accent)
        draw.ellipse(xy((8, 8, 10, 10)), fill=(255,255,255,255))
    elif kind == "downloads":
        draw.line([xy((9, 2)), xy((9, 11))], fill=accent, width=line)
        draw.polygon([xy((5, 8)), xy((9, 13)), xy((13, 8))], fill=accent)
        draw.rounded_rectangle(xy((2, 12, 16, 16)), radius=scale, outline=ink, width=line)
    elif kind == "profile":
        draw.ellipse(xy((5.5, 2, 12.5, 9)), outline=ink, width=line)
        draw.arc(xy((2, 8, 16, 18)), 190, 350, fill=accent, width=line)
    elif kind == "notifications":
        draw.arc(xy((4, 2, 14, 14)), 185, 355, fill=ink, width=line)
        draw.line([xy((4, 8)),xy((3, 13)),xy((15, 13)),xy((14, 8))],fill=ink,width=line)
        draw.ellipse(xy((7, 14, 11, 17)), fill=accent)
    elif kind == "submissions":
        draw.polygon([xy((2, 9)),xy((16, 2)),xy((11, 16)),xy((8, 11))], outline=ink, fill=(124,92,255,80))
        draw.line([xy((8, 11)),xy((16, 2))],fill=accent,width=line)
    elif kind == "moderation":
        draw.polygon([xy((9, 1)),xy((16, 4)),xy((15, 11)),xy((9, 17)),xy((3, 11)),xy((2, 4))],fill=(124,92,255,90),outline=ink)
        draw.line([xy((5.5, 9)),xy((8, 12)),xy((13, 6))],fill=soft,width=line)
    elif kind == "folder":
        draw.rounded_rectangle(xy((1, 5, 17, 16)),radius=scale,fill=(245,185,76,210),outline=ink,width=line)
        draw.polygon([xy((2, 5)),xy((2, 2)),xy((8, 2)),xy((10, 5))],fill=(245,185,76,230))
    elif kind == "logout":
        draw.rounded_rectangle(xy((2, 2, 10, 16)),radius=scale,outline=ink,width=line)
        draw.line([xy((7, 9)),xy((17, 9))],fill=accent,width=line)
        draw.polygon([xy((13, 5)),xy((17, 9)),xy((13, 13))],fill=accent)
    return image.resize(size, Image.Resampling.LANCZOS)

def load_icons(size=(18, 18)):
    global ICONS
    icon_files = {
        "library": "library.png", "collections": "collections.png",
        "next": "next.png", "open": "open.png", "prev": "prev.png",
        "theme": "theme.png", "language": "language.png",
        "zoom_in": "zoom_in.png", "zoom_out": "zoom_out.png",
        "backup": "backup.png", "restore": "restore.png", "favorited": "favorited.png",
    }
    for name, filename in icon_files.items():
        path = ICON_PATH / filename
        if path.exists():
            try:
                img = Image.open(path).convert("RGBA").resize(size, Image.BILINEAR)
                ICONS[name] = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Erro ao carregar ícone {filename}: {e}")
                ICONS[name] = None
        else:
            ICONS[name] = None
    for name in ("discover", "downloads", "profile", "notifications",
                 "submissions", "moderation", "folder", "logout"):
        try: ICONS[name] = ImageTk.PhotoImage(_generated_icon(name, size))
        except Exception: ICONS[name] = None


import platform
_OS = platform.system()
_SANS = "Segoe UI" if _OS == "Windows" else ("SF Pro Text" if _OS == "Darwin" else "DejaVu Sans")
_MONO = "Consolas" if _OS == "Windows" else ("Menlo" if _OS == "Darwin" else "DejaVu Sans Mono")

FLOGO  = ("Georgia", 19, "bold")
FTITLE = ("Georgia", 21, "bold")
FBTN   = (_SANS, 10, "bold")
FLABEL = (_SANS, 10)
FSMALL = (_SANS, 9)
FTINY  = (_SANS, 8)
FPAGE  = (_MONO, 11, "bold")

CAPA_W, CAPA_H = 160, 220
CARD_R  = 14
GPAD    = 16

FADE_SPEED   = 0.18
EASING_POWER = 4

_PLACEHOLDER_PIL = None

def get_placeholder_pil() -> Image.Image:
    global _PLACEHOLDER_PIL
    if _PLACEHOLDER_PIL is None:
        bg_hex = THEME["surface_alt"].lstrip("#")
        bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
        img = Image.new("RGB", (CAPA_W, CAPA_H), bg_rgb)
        d = ImageDraw.Draw(img)
        cx, cy = CAPA_W // 2, CAPA_H // 2
        d.rectangle([cx-28, cy-36, cx+28, cy+36], outline=(100, 100, 120), width=2)
        d.line([cx, cy-36, cx, cy+36], fill=(80, 80, 100), width=1)
        _PLACEHOLDER_PIL = img
    return _PLACEHOLDER_PIL


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

class ArchiveBackend:
    pass
    def __init__(self, path: str):
        self.path = path
        self.kind = None
        self.names = []
        self._pdf_doc = None
        try:
            self._detect()
        except Exception:
            self.close()
            raise

    def _detect(self):
        suffix = Path(self.path).suffix.lower()
        if zipfile.is_zipfile(self.path):
            self.kind = "zip"
            with zipfile.ZipFile(self.path, "r") as z:
                self.names = sorted(
                    [n for n in z.namelist()
                     if Path(n).suffix.lower() in IMG_EXTS
                     and not Path(n).name.startswith(".")],
                    key=natural_key)
        elif HAS_RAR and rarfile.is_rarfile(self.path):
            self.kind = "rar"
            with rarfile.RarFile(self.path, "r") as r:
                self.names = sorted(
                    [n for n in r.namelist()
                     if Path(n).suffix.lower() in IMG_EXTS
                     and not Path(n).name.startswith(".")],
                    key=natural_key)
        elif HAS_PDF and suffix == ".pdf":
            self.kind = "pdf"
            self._pdf_doc = fitz.open(self.path)
            self.names = [f"page_{i}" for i in range(self._pdf_doc.page_count)]
        else:
            raise ValueError(f"Formato não suportado: {suffix}")

    @property
    def count(self) -> int:
        return len(self.names)

    def read_page(self, idx: int) -> bytes:
        pass
        if not (0 <= idx < self.count):
            raise IndexError(idx)
        if self.kind == "zip":
            with zipfile.ZipFile(self.path, "r") as z:
                return z.read(self.names[idx])
        elif self.kind == "rar":
            with rarfile.RarFile(self.path, "r") as r:
                return r.read(self.names[idx])
        elif self.kind == "pdf":
            page = self._pdf_doc.load_page(idx)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            return pix.tobytes("png")
        raise ValueError("backend inválido")

    def close(self):
        if self._pdf_doc:
            try: self._pdf_doc.close()
            except Exception as _e: log.debug("silenced: %s", _e)
            self._pdf_doc = None


def extract_cover_only(path: str) -> bytes:
    pass
    suffix = Path(path).suffix.lower()
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as z:
            names = sorted([n for n in z.namelist()
                            if Path(n).suffix.lower() in IMG_EXTS
                            and not Path(n).name.startswith(".")], key=natural_key)
            if names:
                return z.read(names[0])
    if HAS_RAR and rarfile.is_rarfile(path):
        with rarfile.RarFile(path, "r") as r:
            names = sorted([n for n in r.namelist()
                            if Path(n).suffix.lower() in IMG_EXTS
                            and not Path(n).name.startswith(".")], key=natural_key)
            if names:
                return r.read(names[0])
    if HAS_PDF and suffix == ".pdf":
        doc = fitz.open(path)
        try:
            if doc.page_count:
                pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                return pix.tobytes("png")
        finally:
            doc.close()
    raise ValueError(f"Formato não suportado: {suffix}")


def pil_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def rounded_image(img: Image.Image, r: int) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img.convert("RGBA"), mask=mask)
    return out


def ease_out(t):  return 1 - pow(1 - t, EASING_POWER)
def ease_in_out(t):
    if t < 0.5: return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2
def lerp(a, b, t): return a + (b - a) * t


class SmartPageLoader:
    pass
    WINDOW = 4

    def __init__(self, path: str):
        self.backend = ArchiveBackend(path)
        self._cache = {}
        self._lock = threading.Lock()
        self._prefetching = set()

    @property
    def count(self):
        return self.backend.count

    @property
    def names(self):
        return self.backend.names

    @property
    def entries(self):
        return self.backend.names

    def get_pil(self, idx: int) -> Image.Image:
        with self._lock:
            if idx in self._cache:
                return self._cache[idx]
        img = pil_from_bytes(self.backend.read_page(idx))
        with self._lock:
            self._cache[idx] = img
            self._trim(idx)
        return img

    def _trim(self, center: int):
        keep = set(range(center - self.WINDOW, center + self.WINDOW + 1))
        for k in list(self._cache.keys()):
            if k not in keep:
                del self._cache[k]

    def prefetch(self, idx: int):
        pass
        if not (0 <= idx < self.count):
            return
        with self._lock:
            if idx in self._cache or idx in self._prefetching:
                return
            self._prefetching.add(idx)

        def work():
            try:
                img = pil_from_bytes(self.backend.read_page(idx))
                with self._lock:
                    self._cache[idx] = img
            except Exception as e:
                print("prefetch err:", e)
            finally:
                with self._lock:
                    self._prefetching.discard(idx)

        threading.Thread(target=work, daemon=True).start()

    def get_thumbnail_pil(self, idx, tw, th):
        cache_file = _cover_cache_path(self.backend.path)
        if idx == 0 and os.path.exists(cache_file):
            try:
                img = Image.open(cache_file).convert("RGB")
                img.thumbnail((tw, th), Image.BILINEAR)
                return img
            except Exception:
                pass
        img = pil_from_bytes(self.backend.read_page(idx)).convert("RGB")
        img.thumbnail((tw, th), Image.BILINEAR)
        return img

    def close(self):
        self.backend.close()
        with self._lock:
            self._cache.clear()



from panel_app.archive import (
    ArchiveBackend as ArchiveBackend,
    SmartPageLoader as SmartPageLoader,
    extract_cover_only as extract_cover_only,
    pil_from_bytes as pil_from_bytes,
    rounded_image as rounded_image,
)


def load_library_config():
    global LIBRARY_FOLDER, LANG, IS_DARK, THEME
    cfg = _json_load(LIBRARY_CONFIG_FILE, {})
    if "library_folder" in cfg and os.path.isdir(cfg["library_folder"]):
        LIBRARY_FOLDER = cfg["library_folder"]
    prefs = load_prefs()
    if prefs.get("lang") in ("pt", "en"):
        LANG = prefs["lang"]
    if "dark" in prefs:
        IS_DARK = prefs["dark"]
        THEME.clear()
        THEME.update(DARK if IS_DARK else LIGHT)

def save_library_config(path):
    global LIBRARY_FOLDER
    LIBRARY_FOLDER = path
    _json_save(LIBRARY_CONFIG_FILE, {"library_folder": path})


def _cover_cache_path(comic_path: str) -> str:
    try:
        mtime = os.path.getmtime(comic_path)
    except OSError:
        mtime = 0
    theme_id = "dark" if IS_DARK else "light"
    key = f"{comic_path}|{mtime}|{CAPA_W}x{CAPA_H}|{theme_id}"
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(COVER_CACHE_DIR, f"{h}.webp")


def make_pill(parent, text, cmd, *, icon=None, variant="ghost",
              font=FSMALL, pad_x=14, pad_y=8, min_w=0, active=False):
    c = THEME
    host_bg = parent.cget("bg")
    if variant == "accent":
        base_fill, hover_fill = c["accent"], c["accent2"]
        base_fg, hover_fg = "#ffffff", "#ffffff"
        base_outline = ""
    elif variant == "soft":
        base_fill, hover_fill = c["surface_alt"], c["surface_hover"]
        base_fg, hover_fg = c["text"], c["text"]
        base_outline = c["border"]
    else:
        base_fill, hover_fill = host_bg, c["surface_hover"]
        base_fg, hover_fg = c["text_dim"], c["text"]
        base_outline = c["border"]

    tmp = tk.Label(parent, text=text, font=font)
    tmp_w = tmp.winfo_reqwidth(); tmp_h = tmp.winfo_reqheight()
    tmp.destroy()
    icon_w = (icon.width() + 8) if icon else 0
    w = max(min_w, tmp_w + icon_w + pad_x * 2)
    h = tmp_h + pad_y * 2
    r = h // 2

    cv = tk.Canvas(parent, width=w, height=h, bg=host_bg,
                   highlightthickness=0, cursor="hand2", takefocus=0)
    cv._pill_text = text
    cv._pill_active = bool(active)
    cv._motion_job = None
    cv._motion_fill = base_fill

    def animate(fill, fg, outline):
        if cv._motion_job is not None:
            cv.after_cancel(cv._motion_job)
        start = cv.winfo_rgb(cv._motion_fill)
        target = cv.winfo_rgb(fill)
        def step(frame=1):
            if not cv.winfo_exists():return
            amount = 1 - (1 - frame / 8) ** 3
            color = "#" + "".join(f"{round((a + (b-a)*amount)/257):02x}" for a,b in zip(start,target))
            cv._motion_fill = color
            render(color, fg, outline)
            cv._motion_job = cv.after(16, lambda: step(frame+1)) if frame < 8 else None
        step()

    def render(fill, fg, outline):
        cv.delete("all")
        _rrect(cv, 1, 1, w - 1, h - 1, r, fill=fill)
        if outline:
            _rrect(cv, 1, 1, w - 2, h - 2, r, outline=outline, width=1)
        if icon:
            ix = pad_x + icon.width() // 2
            cv.create_image(ix, h // 2, image=icon)
            cv.create_text(ix + icon.width() // 2 + 6, h // 2,
                           text=cv._pill_text, font=font, fill=fg, anchor="w")
        else:
            cv.create_text(w // 2, h // 2, text=cv._pill_text, font=font, fill=fg)

    def _normal():
        if cv._motion_job is not None:
            cv.after_cancel(cv._motion_job)
            cv._motion_job = None
        if cv._pill_active and variant != "accent":
            cv._motion_fill = c["accent"]
            render(c["accent"], "#ffffff", c["accent"])
        else:
            cv._motion_fill = base_fill
            render(base_fill, base_fg, base_outline)

    def set_text(t):
        cv._pill_text = t
        _normal()

    def set_active(flag):
        cv._pill_active = bool(flag)
        _normal()

    cv.pill_set_text = set_text
    cv.pill_set_active = set_active
    _normal()
    cv.bind("<Enter>", lambda e: (None if cv._pill_active and variant != "accent"
                                  else animate(hover_fill, hover_fg,
                                              hover_fill if variant != "ghost" else c["border_glow"])))
    cv.bind("<Leave>", lambda e: _normal() if cv._pill_active else animate(base_fill, base_fg, base_outline))
    cv.bind("<Button-1>", lambda e: cmd())
    def cancel_motion(event):
        if event.widget is cv and cv._motion_job is not None:
            cv.after_cancel(cv._motion_job)
            cv._motion_job = None
    cv.bind("<Destroy>", cancel_motion, add="+")
    return cv


def animate_color(widget, option, start, end, duration=160):
    pass
    jobs = getattr(widget, "_color_jobs", None)
    if jobs is None:
        jobs = widget._color_jobs = {}
        def cleanup(event):
            if event.widget is widget:
                for job in list(jobs.values()):
                    widget.after_cancel(job)
                jobs.clear()
        widget.bind("<Destroy>", cleanup, add="+")
    if option in jobs:
        widget.after_cancel(jobs.pop(option))
    rgb1, rgb2 = widget.winfo_rgb(start), widget.winfo_rgb(end)
    frames = max(1, duration // 16)
    def step(frame=0):
        if not widget.winfo_exists():return
        progress = 1 - (1 - frame / frames) ** 3
        color = "#" + "".join(f"{round((a+(b-a)*progress)/257):02x}" for a,b in zip(rgb1,rgb2))
        widget.configure(**{option:color})
        if frame < frames:
            jobs[option] = widget.after(16, lambda:step(frame+1))
        else:jobs.pop(option,None)
    step()


class CoverLoader:
    def __init__(self, root: tk.Tk, cache: dict):
        self._root = root
        self._cache = cache
        self._queue = deque()
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def request(self, path, callback):
        if path in self._cache:
            self._root.after(0, lambda: callback(path, self._cache[path]))
            return
        with self._lock:
            if not any(p == path for p, _ in self._queue):
                self._queue.append((path, callback))

    def clear_queue(self):
        with self._lock:
            self._queue.clear()

    def stop(self):
        self._running = False

    def _worker(self):
        while self._running:
            item = None
            with self._lock:
                if self._queue:
                    item = self._queue.popleft()
            if item:
                path, callback = item
                pil = self._load(path)
                self._cache[path] = pil
                if self._root.winfo_exists():
                    self._root.after(0, lambda p=path, i=pil, cb=callback: cb(p, i))
            else:
                time.sleep(0.02)

    def _load(self, path):
        cache_file = _cover_cache_path(path)
        if os.path.exists(cache_file):
            try:
                return Image.open(cache_file).convert("RGB")
            except Exception:
                pass
        try:
            data = extract_cover_only(path)
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail((CAPA_W, CAPA_H), Image.BILINEAR)
            bg_hex = THEME["surface_alt"].lstrip("#")
            bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
            bg = Image.new("RGB", (CAPA_W, CAPA_H), bg_rgb)
            px = (CAPA_W - img.width) // 2
            py = (CAPA_H - img.height) // 2
            bg.paste(img, (px, py))
            mask_img = Image.new("L", (CAPA_W, CAPA_H), 0)
            ImageDraw.Draw(mask_img).rounded_rectangle(
                [0, 0, CAPA_W-1, CAPA_H-1], radius=CARD_R, fill=255)
            result = Image.new("RGB", (CAPA_W, CAPA_H), bg_rgb)
            result.paste(bg, mask=mask_img)
            try:
                result.save(cache_file, "WEBP", quality=85)
            except Exception:
                pass
            return result
        except Exception as e:
            log.warning("Não foi possível carregar a capa de %s: %s", path, e)
            return None


try:
    from panel_client import api_client, session_store
    _ACCOUNTS_AVAILABLE = True
except ImportError:


    _ACCOUNTS_AVAILABLE = False


def _draw_field_icon(cv, kind, cx, cy, s, color):
    pass
    if kind == "user":
        cv.create_oval(cx - s*0.26, cy - s*0.5, cx + s*0.26, cy - s*0.04,
                        outline=color, width=1.6)
        cv.create_arc(cx - s*0.5, cy - s*0.05, cx + s*0.5, cy + s*0.75,
                       start=0, extent=180, style="arc", outline=color, width=1.6)
    elif kind == "mail":
        cv.create_rectangle(cx - s*0.5, cy - s*0.32, cx + s*0.5, cy + s*0.32,
                             outline=color, width=1.6)
        cv.create_line(cx - s*0.5, cy - s*0.3, cx, cy + s*0.08, cx + s*0.5, cy - s*0.3,
                        fill=color, width=1.6)
    elif kind == "lock":
        cv.create_rectangle(cx - s*0.38, cy - s*0.02, cx + s*0.38, cy + s*0.48,
                             outline=color, width=1.6)
        cv.create_arc(cx - s*0.26, cy - s*0.5, cx + s*0.26, cy + s*0.02,
                       start=0, extent=180, style="arc", outline=color, width=1.6)


def _rrect(cv, x1, y1, x2, y2, r, fill="", outline="", width=1):
    pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
           x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1, x1+r,y1]
    if fill:
        cv.create_polygon(pts, smooth=True, fill=fill, outline="")
    if outline:
        cv.create_polygon(pts, smooth=True, fill="", outline=outline, width=width)



__all__ = [name for name in globals() if not name.startswith("__")]
