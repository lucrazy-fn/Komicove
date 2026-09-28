from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, io, os, subprocess, sys, threading, time, uuid
from urllib.parse import urlsplit, urlunsplit
import requests
from PIL import Image, ImageOps
from .storage import APPDATA_DIR, json_load, json_save
from .translations import ui
from .design.fonts import caption, heading
from .design.spacing import CONTENT_PADDING
from .design.styles import KomicoveButton, KomicoveCard, KomicoveEmptyState, KomicoveInput

HISTORY_FILE = os.path.join(APPDATA_DIR, "downloads.json")
COVER_CACHE_DIR = os.path.join(APPDATA_DIR, "download_covers")
_cover_lock = threading.Lock()
_cover_slots = threading.Semaphore(3)
_cover_requested = set()
_cover_finished = set()

@dataclass
class DownloadTask:
    id: str; title: str; url: str; destination: str; token: str | None
    status: str = "queued"; received: int = 0; total: int = 0; error: str | None = None
    created_at: float = 0

class DownloadManager:
    def __init__(self):
        self.tasks = {}
        self._pause, self._cancel = {}, {}
        for row in json_load(HISTORY_FILE, []):
            try:
                task = DownloadTask(**row); self.tasks[task.id] = task
            except TypeError: pass

    def add(self, title, url, destination, token=None, on_done=None):
        task = DownloadTask(uuid.uuid4().hex, title, url, destination, token, created_at=time.time())
        self.tasks[task.id] = task; self._pause[task.id] = threading.Event(); self._cancel[task.id] = threading.Event()
        threading.Thread(target=self._run,args=(task,on_done),daemon=True).start()
        _request_download_cover(task)
        self._save(); return task

    def pause(self, task_id):
        task=self.tasks.get(task_id)
        if task and task.status=="downloading": self._pause[task_id].set(); task.status="paused"; self._save()
    def resume(self, task_id):
        task=self.tasks.get(task_id)
        if task and task.status=="paused": self._pause[task_id].clear(); task.status="downloading"; self._save()
    def cancel(self, task_id):
        if task_id in self._cancel: self._cancel[task_id].set()
    def _save(self):
        json_save(HISTORY_FILE,[{**asdict(x),"token":None} for x in self.tasks.values()][-100:])
    def _run(self, task, on_done):
        temp=task.destination+".part"; task.status="downloading"; self._save()
        try:
            headers={"Authorization":f"Bearer {task.token}"} if task.token else {}
            with requests.get(task.url,headers=headers,stream=True,timeout=300) as response:
                response.raise_for_status(); task.total=int(response.headers.get("content-length") or 0)
                with open(temp,"wb") as target:
                    for chunk in response.iter_content(256*1024):
                        while self._pause[task.id].is_set() and not self._cancel[task.id].is_set(): time.sleep(.15)
                        if self._cancel[task.id].is_set(): task.status="cancelled"; break
                        if chunk: target.write(chunk); task.received += len(chunk)
            if task.status != "cancelled":
                os.replace(temp,task.destination); task.status="completed"
                if not os.path.isfile(_cover_path(task)):
                    _cache_local_cover(task)
        except Exception as exc: task.status="failed"; task.error=str(exc)
        finally:
            if task.status in {"failed","cancelled"} and os.path.exists(temp):
                try: os.remove(temp)
                except OSError: pass
            self._save()
            if on_done: on_done(task)

manager = DownloadManager()


def _cover_path(task):
    name = hashlib.sha256(task.id.encode("utf-8")).hexdigest() + ".webp"
    return os.path.join(COVER_CACHE_DIR, name)


def _store_cover(task, data, *, remote=False):
    """Write a small, atomic thumbnail; use the archive only as an API fallback."""
    with Image.open(io.BytesIO(data)) as source:
        cover = ImageOps.fit(source.convert("RGB"), (196, 264), Image.Resampling.LANCZOS)
    os.makedirs(COVER_CACHE_DIR, exist_ok=True)
    target = _cover_path(task)
    temporary = target + "." + uuid.uuid4().hex + ".tmp"
    try:
        cover.save(temporary, format="WEBP", quality=85)
        with _cover_lock:
            if remote or not os.path.isfile(target):
                os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _cache_local_cover(task):
    if not os.path.isfile(task.destination):
        return False
    try:
        from .archive import extract_cover_only
        _store_cover(task, extract_cover_only(task.destination))
        return True
    except (OSError, ValueError, IndexError, RuntimeError):
        return False


def _cache_remote_cover(task):
    parts = urlsplit(task.url)
    if parts.scheme not in {"http", "https"} or not parts.path.endswith("/content"):
        return
    cover_url = urlunsplit((parts.scheme, parts.netloc,
                            parts.path[:-len("content")] + "cover", parts.query, parts.fragment))
    headers = {"Authorization": f"Bearer {task.token}"} if task.token else {}
    try:
        with requests.get(cover_url, headers=headers, stream=True, timeout=(5, 12)) as response:
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_content(64 * 1024):
                payload.extend(chunk)
                if len(payload) > 8 * 1024 * 1024:
                    return
        _store_cover(task, bytes(payload), remote=True)
    except (OSError, ValueError, requests.RequestException):
        pass


def _request_download_cover(task):
    if os.path.isfile(_cover_path(task)):
        return
    with _cover_lock:
        if task.id in _cover_requested:
            return
        _cover_requested.add(task.id)
    def worker():
        try:
            with _cover_slots:
                if os.path.isfile(task.destination):
                    _cache_local_cover(task)
                _cache_remote_cover(task)
        finally:
            with _cover_lock:
                _cover_finished.add(task.id)
    threading.Thread(target=worker, daemon=True, name="komicove-download-cover").start()

def _visible_downloads(tasks, status_filter, query):
    """Filter actual download history without altering the persisted tasks."""
    query = query.strip().casefold()
    groups = {
        "downloading": {"queued", "downloading", "paused"},
        "completed": {"completed"},
        "failed": {"failed", "cancelled"},
    }
    allowed = groups.get(status_filter)
    return [task for task in reversed(tasks)
            if (allowed is None or task.status in allowed)
            and (not query or query in task.title.casefold())]


def _open_download_location(destination):
    folder = os.path.dirname(os.path.abspath(destination))
    if not os.path.isdir(folder):
        return
    if sys.platform == "win32":
        os.startfile(folder)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])


def render_downloads(container, theme, fonts, *, resource_path, on_discover,
                     on_choose_folder, on_metadata_filters, make_filter):
    import tkinter as tk
    from PIL import Image, ImageTk

    for child in container.winfo_children():
        child.destroy()
    container.update_idletasks()
    _, body_font, small_font = fonts
    selected = {"status": "all", "query": "", "snapshot": None}

    header = tk.Frame(container, bg=theme["bg"])
    header.pack(fill="x", padx=CONTENT_PADDING, pady=(18, 7))
    tk.Label(header, text="Downloads", font=heading(27), bg=theme["bg"],
             fg=theme["text"]).pack(side="left", padx=(0, 28))
    KomicoveButton(header, ui("Pasta", "Folder"), on_choose_folder,
                   theme, kind="primary", icon_name="plus").pack(side="right", padx=(8, 0))
    KomicoveButton(header, ui("Série / Autor", "Series / Author"),
                   on_metadata_filters, theme, compact=True, icon_name="list").pack(
                       side="right", padx=(8, 0))
    search = KomicoveInput(
        header, theme,
        placeholder=ui("Buscar títulos...", "Search titles..."),
        on_change=lambda query: (selected.__setitem__("query", query), refresh(force=True)),
        width=max(260, min(640, container.winfo_width() - 490)),
    )
    search.pack(side="left", pady=(2, 0))

    filters = tk.Frame(container, bg=theme["bg"])
    filters.pack(fill="x", padx=CONTENT_PADDING, pady=(0, 8))
    chips = tk.Frame(filters, bg=theme["bg"])
    chips.pack(side="left")

    def set_filter(value):
        selected["status"] = value
        draw_filters()
        refresh(force=True)

    def draw_filters():
        for child in chips.winfo_children():
            child.destroy()
        labels = [
            ("all", ui("Todos", "All"), "grid-2x2"),
            ("downloading", ui("Baixando", "Downloading"), "download"),
            ("completed", ui("Concluídos", "Completed"), "check"),
            ("failed", ui("Erro", "Error"), "x"),
        ]
        for value, label, icon_name in labels:
            make_filter(chips, label, lambda value=value: set_filter(value),
                        variant="soft", font=caption(10), pad_x=17, pad_y=8,
                        active=selected["status"] == value, icon_name=icon_name).pack(
                            side="left", padx=(0, 5))

    draw_filters()
    tk.Frame(container, bg=theme["border"], height=1).pack(
        fill="x", padx=CONTENT_PADDING, pady=(4, 3))
    viewport = tk.Frame(container, bg=theme["bg"])
    viewport.pack(fill="both", expand=True)
    canvas = tk.Canvas(viewport, bg=theme["bg"], highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar = tk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=scrollbar.set)
    area = tk.Frame(canvas, bg=theme["bg"])
    window = canvas.create_window((0, 0), window=area, anchor="nw")
    area.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfig(window, width=event.width))

    def refresh(*, force=False):
        if not container.winfo_exists():
            return
        all_tasks = list(manager.tasks.values())
        tasks = _visible_downloads(all_tasks, selected["status"], selected["query"])
        for task in tasks:
            _request_download_cover(task)
        snapshot = (selected["status"], selected["query"],
                    tuple((task.id, task.status, task.received, task.total, task.error,
                           os.path.isfile(_cover_path(task)), task.id in _cover_finished)
                          for task in tasks))
        if force or snapshot != selected["snapshot"]:
            selected["snapshot"] = snapshot
            for child in area.winfo_children():
                child.destroy()
            if not tasks:
                illustration = None
                if not all_tasks and not selected["query"] and selected["status"] == "all":
                    try:
                        container.update_idletasks()
                        width = max(400, min(950, container.winfo_width() - CONTENT_PADDING * 2 - 80))
                        with Image.open(resource_path("assets_redesign/empty_states/downloads_desktop.png")) as source:
                            art = source.convert("RGBA")
                            art.thumbnail((width, 480), Image.Resampling.LANCZOS)
                        illustration = ImageTk.PhotoImage(art)
                    except (OSError, ValueError):
                        pass
                if all_tasks or selected["query"] or selected["status"] != "all":
                    empty_title = ui("Nenhum download encontrado", "No downloads found")
                    description = ui("Tente outro termo ou filtro.", "Try another search or filter.")
                    empty_action = lambda: (set_filter("all"), search.clear())
                    empty_action_text = ui("Limpar filtros", "Clear filters")
                else:
                    empty_title = ui("Nenhum download ativo", "No active downloads")
                    description = ui(
                        "Seus downloads aparecerão aqui. Explore novos títulos em Descobrir.",
                        "Your downloads will appear here. Explore new titles in Discover.",
                    )
                    empty_action = on_discover
                    empty_action_text = ui("Ir para Descobrir", "Go to Discover")
                empty = KomicoveEmptyState(
                    area, theme, title=empty_title, description=description,
                    action=empty_action, action_text=empty_action_text,
                    illustration=illustration, panel=True,
                )
                empty.pack(fill="x", padx=CONTENT_PADDING, pady=(10, 24))
            else:
                for task in tasks:
                    card = KomicoveCard(area, theme, height=154, radius=16, padding=10)
                    card.pack(fill="x", padx=CONTENT_PADDING, pady=(10, 2))
                    cover_path = _cover_path(task)
                    cover_photo = None
                    if os.path.isfile(cover_path):
                        try:
                            with Image.open(cover_path) as source:
                                cover = source.convert("RGB").resize((98, 132), Image.Resampling.LANCZOS)
                            cover_photo = ImageTk.PhotoImage(cover)
                        except (OSError, ValueError):
                            pass
                    if cover_photo is not None:
                        cover_label = tk.Label(card.content, image=cover_photo,
                                               bg=theme["surface"], bd=0)
                        cover_label.image = cover_photo
                    else:
                        missing = task.id in _cover_finished
                        cover_text = (ui("Capa\nindisponível", "Cover\nunavailable") if missing
                                      else ui("Carregando\ncapa...", "Loading\ncover..."))
                        cover_label = tk.Label(card.content, text=cover_text,
                                               font=small_font, bg=theme["surface_alt"],
                                               fg=theme["text_dim"], width=13, height=8,
                                               justify="center")
                    cover_label.pack(side="left", padx=(0, 20))
                    content = tk.Frame(card.content, bg=theme["surface"])
                    content.pack(side="left", fill="both", expand=True, pady=5)
                    top = tk.Frame(content, bg=theme["surface"])
                    top.pack(fill="x")
                    tk.Label(top, text=task.title, font=body_font, bg=theme["surface"],
                             fg=theme["text"], anchor="w").pack(side="left", fill="x", expand=True)
                    status = {
                        "queued": ui("Na fila", "Queued"),
                        "downloading": ui("Baixando", "Downloading"),
                        "paused": ui("Pausado", "Paused"),
                        "cancelled": ui("Cancelado", "Cancelled"),
                        "completed": ui("Concluído", "Completed"),
                        "failed": ui("Falhou", "Failed"),
                    }.get(task.status, task.status)
                    status_color = (theme["read_badge_text"] if task.status == "completed" else
                                    theme["accent"] if task.status == "failed" else theme["text_dim"])
                    tk.Label(top, text=status, font=small_font, bg=theme["surface"],
                             fg=status_color).pack(side="right")
                    pct = min(100, int(task.received * 100 / task.total)) if task.total else 0
                    filename = os.path.basename(task.destination)
                    tk.Label(content, text=filename,
                             font=small_font, bg=theme["surface"], fg=theme["text_dim"],
                             anchor="w").pack(fill="x", pady=(8, 13))
                    bar = tk.Frame(content, bg=theme["surface"])
                    bar.pack(fill="x")
                    progress = tk.Canvas(bar, height=6, bg=theme["surface"], highlightthickness=0)
                    progress.pack(side="left", fill="x", expand=True)
                    tk.Label(bar, text=f"{pct}%", font=small_font, bg=theme["surface"],
                             fg=theme["text_dim"]).pack(side="right", padx=(12, 0))
                    progress.bind("<Configure>", lambda event, value=pct, widget=progress: (
                        widget.delete("all"),
                        widget.create_rectangle(0, 0, event.width, 6,
                                                fill=theme["progress_bg"], outline=""),
                        widget.create_rectangle(0, 0, event.width * value / 100, 6,
                                                fill=theme["accent"], outline="")))
                    if task.error:
                        tk.Label(content, text=task.error, font=small_font, bg=theme["surface"],
                                 fg=theme["text_dim"], anchor="w", wraplength=780
                                 ).pack(fill="x", pady=(8, 0))
                    actions = tk.Frame(content, bg=theme["surface"])
                    actions.pack(anchor="e", pady=(10, 0))
                    if task.status == "downloading":
                        KomicoveButton(actions, ui("Pausar", "Pause"),
                                       lambda key=task.id: manager.pause(key), theme,
                                       compact=True).pack(side="left", padx=(0, 6))
                    if task.status == "paused":
                        KomicoveButton(actions, ui("Continuar", "Resume"),
                                       lambda key=task.id: manager.resume(key), theme,
                                       compact=True).pack(side="left", padx=(0, 6))
                    if task.status in {"queued", "downloading", "paused"}:
                        KomicoveButton(actions, ui("Cancelar", "Cancel"),
                                       lambda key=task.id: manager.cancel(key), theme,
                                       compact=True).pack(side="left")
                    if task.status == "completed" and os.path.isfile(task.destination):
                        KomicoveButton(actions, ui("Abrir pasta", "Open folder"),
                                       lambda path=task.destination: _open_download_location(path),
                                       theme, compact=True).pack(side="left")
    def poll():
        if not container.winfo_exists():
            return
        refresh()
        container.after(700, poll)

    refresh(force=True)
    container.after(700, poll)
