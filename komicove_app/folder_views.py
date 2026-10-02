"""Phase 02 monitored-folder table, using the existing desktop components."""
import os
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from datetime import datetime
from PIL import Image, ImageTk
from .design.styles import KomicoveButton, KomicoveCard, KomicoveInput
from .design.fonts import heading, body, caption
from .design.icons import lucide_icon
from .translations import ui


def _structure(folders):
    return [(key, row["name"], row["path"], row.get("cover")) for key, row in folders.items()]


def _clear_summary_binding(window):
    owner = getattr(window, "_folder_summary_owner", None)
    binding = getattr(window, "_folder_summary_binding", None)
    window._folder_summary_owner = None
    window._folder_summary_binding = None
    if owner is not None and binding:
        try:
            if owner.winfo_exists():
                owner.unbind("<Configure>", binding)
        except tk.TclError:
            # Tk may already have deleted the command when the shell was rebuilt.
            pass


def toggle_folder(window, key, palette):
    row = window._folder_index.snapshot()["folders"].get(key)
    if row is None:
        return
    window._folder_index.configure(key, enabled=not row["enabled"])
    window._folder_watcher.refresh()
    update_folders(window, palette)


def update_folders(window, palette):
    folders = window._folder_index.snapshot()["folders"]
    canvas = getattr(window, "_folder_canvas", None)
    if (canvas is None or not canvas.winfo_exists()
            or getattr(window, "_folder_host", None) is not window._main
            or _structure(folders) != getattr(window, "_folder_structure", None)):
        render_folders(window, palette)
        return
    for key, update in window._folder_row_updates.items():
        update(folders[key])
    window._folder_update_summary()


def _draw_status(badge, folder, c):
    state = folder["status"] if folder["enabled"] else "paused"
    status, color = {"updated": (ui("Atualizada", "Up to date"), "#35d58b"),
                     "checking": (ui("Verificando...", "Checking..."), "#f6c453"),
                     "unavailable": (ui("Pasta indisponível", "Folder unavailable"), "#ff5665"),
                     "paused": (ui("Pausada", "Paused"), c["text_dim"])}[state]
    if folder["new"] and state == "updated":
        status, color = ui(f'{folder["new"]} nova(s) HQ(s)', f'{folder["new"]} new comic(s)'), "#56a9ff"
    if getattr(badge, "_status", None) == (status, color):
        return
    badge._status = status, color
    badge.delete("all")
    rgb = [int(color[n:n+2], 16) for n in (1, 3, 5)]
    tint = "#"+"".join(f"{round(channel*.3):02x}" for channel in rgb)
    badge.create_oval(1, 1, 33, 33, fill=c["surface_alt"], outline=tint)
    badge.create_oval(137, 1, 169, 33, fill=c["surface_alt"], outline=tint)
    badge.create_rectangle(17, 1, 153, 33, fill=c["surface_alt"], outline="")
    badge.create_line(17, 1, 153, 1, fill=tint)
    badge.create_line(17, 33, 153, 33, fill=tint)
    badge.create_oval(10, 12, 20, 22, fill=color, outline="")
    badge.create_text(28, 17, text=status, font=caption(9), anchor="w", fill=color)


def render_folders(window, palette):
    c = palette
    previous = getattr(window, "_folder_canvas", None)
    scroll = previous.yview()[0] if previous is not None and previous.winfo_exists() else 0
    _clear_summary_binding(window)
    window._folder_structure = None
    window._folder_row_updates = {}
    for child in window._main.winfo_children():
        child.destroy()
    top = tk.Frame(window._main, bg=c["bg"])
    top.pack(fill="x", padx=28, pady=(18, 14))
    KomicoveButton(top, ui("Pasta", "Folder"), window._add_monitored_folder,
                   c, kind="primary", icon_name="plus").pack(side="right", padx=(12, 0))
    def metadata():
        window._refresh_library()
        window._metadata_filters()
    KomicoveButton(top, ui("Série / Autor", "Series / Author"), metadata,
                   c, icon_name="list").pack(side="right", padx=(12, 0))
    def global_search(query):
        window._search_query = query
        window._refresh_library()
    KomicoveInput(top, c, placeholder=ui("Buscar títulos, autores, gêneros...", "Search titles, authors, genres..."),
                  value=window._search_query, on_change=global_search).pack(
                      side="left", fill="x", expand=True)
    tk.Label(window._main, text=ui("Pastas da biblioteca", "Library folders"),
             bg=c["bg"], fg=c["text"], font=heading(28)).pack(anchor="w", padx=28, pady=(8, 4))
    tk.Label(window._main, text=ui("O Komicove detecta automaticamente novas HQs nestas pastas.",
             "Komicove automatically detects new comics in these folders."),
             bg=c["bg"], fg=c["text_dim"], font=body(11)).pack(anchor="w", padx=28)
    actions = tk.Frame(window._main, bg=c["bg"])
    actions.pack(fill="x", padx=28, pady=(22, 18))
    KomicoveButton(actions, ui("Voltar à biblioteca", "Back to library"), window._refresh_library,
                  c, icon_name="arrow-left").pack(side="left", padx=(0, 14))
    KomicoveButton(actions, ui("Adicionar pasta", "Add folder"), window._add_monitored_folder,
                  c, kind="primary", icon_name="plus").pack(side="left", padx=(0, 14))
    KomicoveButton(actions, ui("Atualizar todas", "Refresh all"), window._rescan_folders,
                  c, icon_name="refresh-cw").pack(side="left")
    window._folder_summary = None
    window._folder_summary_report = None
    def update_summary():
        report = getattr(window, "_folder_report", None)
        if report == window._folder_summary_report:
            return
        window._folder_summary_report = report
        if window._folder_summary is not None and window._folder_summary.winfo_exists():
            window._folder_summary.destroy()
        _clear_summary_binding(window)
        if not report:
            return
        summary_palette = {**c, "surface": "#071c16"}
        summary = KomicoveCard(window._main, summary_palette, height=88, padding=12, radius=12, outline="#087945")
        window._folder_summary = summary
        def position(_event=None):
            if summary.winfo_exists():
                small = window._main.winfo_width() < 1180
                width = min(480, max(240, window._main.winfo_width()-56))
                if small:
                    summary.place(relx=1, rely=1, x=-28, y=-24, anchor="se", width=width)
                else:
                    summary.place(relx=1, rely=0, x=-28, y=76, anchor="ne", width=width)
        window._folder_summary_binding = window._main.bind("<Configure>", position, add="+")
        window._folder_summary_owner = window._main
        position()
        text = ui(f'{report["added"]} novas HQs adicionadas.\n{report["duplicates"]} já estavam na biblioteca.',
                  f'{report["added"]} new comics added.\n{report["duplicates"]} were already in the library.')
        if report.get("invalid"):
            text += ui(f'\n{report["invalid"]} arquivo(s) pendente(s) ou inválido(s).',
                       f'\n{report["invalid"]} pending or invalid file(s).')
        tk.Label(summary.content, text=text, font=body(10), justify="left", bg=summary_palette["surface"],
                 fg="#35d58b").pack(side="left")
        def dismiss():
            window._folder_report = None
            _clear_summary_binding(window)
            summary.destroy()
        KomicoveButton(summary.content, "", dismiss, c, compact=True, icon_name="x").pack(side="right")
    window._folder_update_summary = update_summary
    update_summary()
    area = tk.Frame(window._main, bg=c["bg"])
    area.pack(fill="both", expand=True, padx=28, pady=(0, 24))
    canvas = tk.Canvas(area, bg=c["bg"], highlightthickness=0)
    area.rowconfigure(0, weight=1)
    area.columnconfigure(0, weight=1)
    canvas.grid(row=0, column=0, sticky="nsew")
    window._folder_canvas = canvas
    window._folder_host = window._main
    def destroyed(event):
        if event.widget is canvas and getattr(window, "_folder_canvas", None) is canvas:
            _clear_summary_binding(window)
            window._folder_canvas = None
            window._folder_structure = None
            window._folder_row_updates = {}
    canvas.bind("<Destroy>", destroyed)
    scrollbar = ttk.Scrollbar(area, command=canvas.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    horizontal = ttk.Scrollbar(area, orient="horizontal", command=canvas.xview)
    def xscroll(first, last):
        horizontal.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            horizontal.grid_remove()
        else:
            horizontal.grid(row=1, column=0, sticky="ew")
    canvas.configure(xscrollcommand=xscroll)
    canvas.configure(yscrollcommand=scrollbar.set)
    content = tk.Frame(canvas, bg=c["bg"])
    item = canvas.create_window(0, 0, anchor="nw", window=content)
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=max(1060, e.width)))
    content.bind("<Configure>", lambda e: canvas.configure(scrollregion=(0, 0, max(1060, canvas.winfo_width()),
                                                        max(canvas.winfo_height(), content.winfo_reqheight()))))
    def wheel(event):
        if content.winfo_reqheight() > canvas.winfo_height():
            canvas.yview_scroll(-1 if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0 else 1, "units")
        return "break"
    def bind_wheel(widget):
        for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(event, wheel, add="+")
        for child in widget.winfo_children():
            bind_wheel(child)
    def fill_table():
        for child in content.winfo_children():
            child.destroy()
        folders = window._folder_index.snapshot()["folders"]
        window._folder_structure = _structure(folders)
        window._folder_row_updates = {}
        window._folder_toggle_buttons = {}
        table = KomicoveCard(content, c, height=108 + 112 * len(folders), padding=12, radius=12)
        table.pack(fill="x")
        table_content = table.content
        def fit_table(_event=None):
            # Header/font sizes depend on Windows scaling. Never clip the last
            # folder by estimating the total height from the number of rows.
            height = table_content.winfo_reqheight() + 2 * table.padding
            if height > 2 * table.padding and int(table.cget("height")) != height:
                table.card_height = height
                table.configure(height=height)
        table_content.bind("<Configure>", fit_table, add="+")
        tk.Label(table_content, text=ui(f"Pastas monitoradas ({len(folders)})", f"Monitored folders ({len(folders)})"),
                 font=heading(14), bg=c["surface"], fg=c["text"]).pack(anchor="w", pady=(10, 18), padx=12)
        labels = [ui("Pasta", "Folder"), "HQs", ui("Última verificação", "Last checked"),
                  ui("Estado", "Status"), ui("Ações", "Actions")]
        header = tk.Frame(table_content, bg=c["surface_alt"])
        header.pack(fill="x")
        for i, label in enumerate(labels):
            header.columnconfigure(i, weight=(5, 1, 2, 2, 2)[i], uniform="columns")
            tk.Label(header, text=label, font=body(9), bg=c["surface_alt"],
                     fg=c["text_dim"]).grid(row=0, column=i, sticky="w", padx=16, pady=16)
        query = getattr(window, "_folder_query", "").casefold()
        for key, folder in folders.items():
            if query and query not in (folder["name"] + folder["path"]).casefold():
                continue
            row = tk.Frame(table_content, bg=c["surface"], height=108)
            row.pack(fill="x", pady=1)
            row.rowconfigure(0, minsize=108, weight=1)
            for i in range(5):
                row.columnconfigure(i, weight=(5, 1, 2, 2, 2)[i], uniform="columns")
            identity = tk.Frame(row, bg=c["surface"])
            identity.grid(row=0, column=0, sticky="nsew", padx=12, pady=10)
            image = lucide_icon("folder", size=36, dark=c["bg"] == "#090b0f")
            paths = [b["path"] for b in window._folder_index.snapshot()["books"].values()
                     if any(s["folder"] == key for s in b["sources"].values())]
            if folder.get("cover") and os.path.isfile(folder["cover"]):
                with Image.open(folder["cover"]) as cover:
                    image = ImageTk.PhotoImage(cover.copy())
            elif paths:
                from .runtime import _cover_cache_path
                cached = _cover_cache_path(paths[0])
                if os.path.isfile(cached):
                    try:
                        with Image.open(cached) as cover:
                            small = cover.copy()
                            small.thumbnail((68, 82))
                            image = ImageTk.PhotoImage(small)
                    except OSError:
                        pass
            picture = tk.Label(identity, image=image, bg=c["surface_alt"], width=72, height=86)
            picture.image = image
            picture.pack(side="left", padx=(0, 14))
            text = tk.Frame(identity, bg=c["surface"])
            text.pack(side="left", fill="x", expand=True)
            tk.Label(text, text=folder["name"], bg=c["surface"], fg=c["text"], font=body(11, bold=True),
                     anchor="w").pack(fill="x", pady=(15, 4))
            tk.Label(text, text=folder["path"], bg=c["surface"], fg=c["text_dim"], font=body(9),
                     anchor="w", wraplength=290).pack(fill="x")
            stamp = datetime.fromtimestamp(folder["checked"]).strftime("%d/%m/%Y %H:%M") if folder["checked"] else "—"
            count_label = tk.Label(row, text=str(folder["count"])+"\n"+ui("HQs", "comics"), font=body(10), bg=c["surface"], fg=c["text"])
            count_label.grid(row=0, column=1)
            date_label = tk.Label(row, text=stamp, font=body(9), bg=c["surface"], fg=c["text_dim"])
            date_label.grid(row=0, column=2)
            state_box = tk.Frame(row, bg=c["surface"])
            state_box.grid(row=0, column=3)
            badge = tk.Canvas(state_box, width=170, height=34, bg=c["surface"], highlightthickness=0)
            badge.pack()
            toggle = KomicoveButton(state_box, ui("Desativar", "Disable") if folder["enabled"] else ui("Ativar", "Enable"),
                lambda k=key: toggle_folder(window, k, c), c, compact=True, fixed_height=30, min_width=100)
            toggle.pack(pady=(4, 0))
            window._folder_toggle_buttons[key] = toggle
            def update(record, number=count_label, date=date_label, status=badge, control=toggle):
                count = str(record["count"])+"\n"+ui("HQs", "comics")
                stamp = datetime.fromtimestamp(record["checked"]).strftime("%d/%m/%Y %H:%M") if record["checked"] else "—"
                if number.cget("text") != count:
                    number.configure(text=count)
                if date.cget("text") != stamp:
                    date.configure(text=stamp)
                _draw_status(status, record, c)
                label = ui("Desativar", "Disable") if record["enabled"] else ui("Ativar", "Enable")
                if control.text != label:
                    control.text = label
                    control._draw(False)
            window._folder_row_updates[key] = update
            update(folder)
            buttons = tk.Frame(row, bg=c["surface"])
            buttons.grid(row=0, column=4, sticky="e")
            KomicoveButton(buttons, ui("Atualizar", "Refresh"), lambda k=key: window._rescan_folders(k),
                          c, compact=True, icon_name="refresh-cw").pack(side="left")
            def menu(k=key):
                f = window._folder_index.snapshot()["folders"][k]
                popup = tk.Menu(window, tearoff=False, bg=c["surface"], fg=c["text"])
                def rename():
                    name = simpledialog.askstring(ui("Renomear", "Rename"), ui("Nome da pasta", "Folder name"),
                                                  initialvalue=f["name"], parent=window)
                    if name:
                        window._folder_index.configure(k, name=name)
                        fill_table()
                popup.add_command(label=ui("Renomear", "Rename"), command=rename)
                def toggle():
                    toggle_folder(window, k, c)
                popup.add_command(label=ui("Desativar", "Disable") if f["enabled"] else ui("Ativar", "Enable"), command=toggle)
                def remove():
                    if messagebox.askyesno("Komicove", ui("Parar de monitorar? Os arquivos e o progresso serão mantidos.",
                                                       "Stop monitoring? Files and progress will be kept."), parent=window):
                        window._folder_index.configure(k, remove=True)
                        fill_table()
                popup.add_command(label=ui("Remover pasta", "Remove folder"), command=remove)
                try:
                    popup.tk_popup(window.winfo_pointerx(), window.winfo_pointery())
                finally:
                    popup.grab_release()
            KomicoveButton(buttons, "", menu, c, compact=True, icon_name="ellipsis-vertical").pack(side="left", padx=(6, 0))
            tk.Frame(table_content, bg=c["border"], height=1).pack(fill="x", padx=8)
        bind_wheel(content)
    fill_table()
    bind_wheel(canvas)
    window.after_idle(lambda: canvas.yview_moveto(scroll) if canvas.winfo_exists() else None)
