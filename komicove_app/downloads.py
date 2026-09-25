from __future__ import annotations
from dataclasses import dataclass, asdict
import os, threading, time, uuid
import requests
from .storage import APPDATA_DIR, json_load, json_save
from .translations import ui

HISTORY_FILE = os.path.join(APPDATA_DIR, "downloads.json")

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
        threading.Thread(target=self._run,args=(task,on_done),daemon=True).start(); self._save(); return task

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
            if task.status != "cancelled": os.replace(temp,task.destination); task.status="completed"
        except Exception as exc: task.status="failed"; task.error=str(exc)
        finally:
            if task.status in {"failed","cancelled"} and os.path.exists(temp):
                try: os.remove(temp)
                except OSError: pass
            self._save()
            if on_done: on_done(task)

manager = DownloadManager()

def render_downloads(container, theme, fonts):
    for child in container.winfo_children(): child.destroy()
    import tkinter as tk
    title,body,small=fonts
    tk.Label(container,text="Downloads",font=title,bg=theme["bg"],fg=theme["text"]).pack(anchor="w",padx=30,pady=(28,12))
    area=tk.Frame(container,bg=theme["bg"]); area.pack(fill="both",expand=True,padx=30)
    def refresh():
        for child in area.winfo_children(): child.destroy()
        tasks=list(manager.tasks.values())[::-1]
        if not tasks: tk.Label(area,text=ui("Nenhum download ainda.", "No downloads yet."),font=body,bg=theme["bg"],fg=theme["text_dim"]).pack(pady=40)
        for task in tasks:
            card=tk.Frame(area,bg=theme["surface"],padx=14,pady=10); card.pack(fill="x",pady=5)
            pct=int(task.received*100/task.total) if task.total else 0
            tk.Label(card,text=task.title,font=body,bg=theme["surface"],fg=theme["text"]).pack(anchor="w")
            status={"queued":ui("na fila", "queued"),"downloading":ui("baixando", "downloading"),"paused":ui("pausado", "paused"),"cancelled":ui("cancelado", "cancelled"),"completed":ui("concluído", "completed"),"failed":ui("falhou", "failed")}.get(task.status,task.status)
            tk.Label(card,text=f"{status} · {pct}% · {task.destination}",font=small,bg=theme["surface"],fg=theme["text_dim"]).pack(anchor="w")
            controls=tk.Frame(card,bg=theme["surface"]); controls.pack(anchor="e")
            if task.status=="downloading": tk.Button(controls,text=ui("Pausar", "Pause"),command=lambda i=task.id:manager.pause(i)).pack(side="left")
            if task.status=="paused": tk.Button(controls,text=ui("Continuar", "Resume"),command=lambda i=task.id:manager.resume(i)).pack(side="left")
            if task.status in {"downloading","paused","queued"}: tk.Button(controls,text=ui("Cancelar", "Cancel"),command=lambda i=task.id:manager.cancel(i)).pack(side="left",padx=5)
        try: container.after(700,refresh)
        except tk.TclError: pass
    refresh()
