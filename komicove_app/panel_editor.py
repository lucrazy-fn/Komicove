from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from concurrent.futures import ThreadPoolExecutor

from PIL import ImageTk

from komicove_app.design.spacing import RADIUS_LARGE, RADIUS_MEDIUM, RADIUS_SMALL
from komicove_app.design.styles import KomicoveButton, KomicoveCard
from komicove_app.runtime import THEME, grab_when_visible, maximize_window, set_app_icon
from komicove_app.translations import ui


class PanelEditor(tk.Toplevel):
    """Visual editor that preserves the existing normalized panel data."""

    def __init__(self, master, image, regions, auto_regions, on_save, on_redetect=None, detection_cancel=None):
        super().__init__(master)
        set_app_icon(self)
        self.title(ui("Editor manual de quadros", "Manual panel editor"))
        self.configure(bg=THEME["canvas_bg"])
        self.geometry("1280x820")
        self.minsize(980, 680)
        self.image = image.convert("RGB")
        self.regions = [list(region) for region in regions]
        self.auto_regions = [list(region) for region in auto_regions]
        self.on_save = on_save
        self.on_redetect = on_redetect
        self._detection_cancel = detection_cancel
        self._detector = ThreadPoolExecutor(max_workers=1,thread_name_prefix="panel-editor")
        self._detecting = False
        self._detect_poll = None
        self.bind('<Destroy>',self._dispose,add='+')
        self.selected = None
        self.action = None
        self.start = None
        self.original = None
        self._photo = None
        self._thumb_photo = None
        self._tool = "select"
        self._build()
        self.transient(master)
        grab_when_visible(self)
        self.after(40, lambda: maximize_window(self))

    def _build(self):
        c = THEME
        top = tk.Frame(self, bg=c["surface"], height=72)
        top.pack(fill="x"); top.pack_propagate(False)
        KomicoveButton(top, ui("Voltar", "Back"), self.destroy, c, kind="primary",
                       icon_name="arrow-left", min_width=128).pack(side="left", padx=(26, 18), pady=13)
        tk.Frame(top, width=1, bg=c["border"]).pack(side="left", fill="y", pady=14, padx=(0, 18))
        heading = tk.Frame(top, bg=c["surface"]); heading.pack(side="left", pady=11)
        tk.Label(heading, text=ui("Editor de quadros", "Panel editor"),
                 font=("Segoe UI", 16, "bold"), bg=c["surface"], fg=c["text"]).pack(anchor="w")
        tk.Label(heading, text=ui("Crie, ajuste e organize a ordem da leitura guiada",
                                  "Create, adjust and organize guided reading order"),
                 font=("Segoe UI", 8), bg=c["surface"], fg=c["text_dim"]).pack(anchor="w")
        KomicoveButton(top, ui("Redetectar", "Redetect"), self._reset, c,
                       kind="secondary", icon_name="scan-search").pack(side="right", padx=26, pady=13)

        workspace = tk.Frame(self, bg=c["canvas_bg"])
        workspace.pack(fill="both", expand=True)
        left = tk.Frame(workspace, bg=c["surface"], width=116)
        left.pack(side="left", fill="y"); left.pack_propagate(False)
        tk.Label(left, text=ui("PÁGINA", "PAGE"), font=("Segoe UI", 8, "bold"),
                 bg=c["surface"], fg=c["text_dim"]).pack(pady=(18, 10))
        thumb = self.image.copy(); thumb.thumbnail((82, 118))
        self._thumb_photo = ImageTk.PhotoImage(thumb)
        thumb_cv = tk.Canvas(left, width=94, height=132, bg=c["surface"], highlightthickness=0)
        thumb_cv.pack()
        self._rounded_rect(thumb_cv, 1, 1, 93, 131, RADIUS_SMALL,
                           fill=c["border_glow"], outline=c["accent"])
        thumb_cv.create_image(47, 66, image=self._thumb_photo)
        tk.Label(left, text="1", font=("Segoe UI", 9, "bold"), bg=c["surface"],
                 fg=c["accent2"]).pack(pady=(5, 0))

        right = tk.Frame(workspace, bg=c["surface"], width=292)
        right.pack(side="right", fill="y"); right.pack_propagate(False)
        self._build_inspector(right)

        center = tk.Frame(workspace, bg=c["canvas_bg"])
        center.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(center, bg=c["canvas_bg"], highlightthickness=0, cursor="crosshair")
        self.cv.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        self.cv.bind("<Configure>", lambda _e: self._draw())
        self.cv.bind("<Button-1>", self._down)
        self.cv.bind("<B1-Motion>", self._move)
        self.cv.bind("<ButtonRelease-1>", self._up)

        bottom = tk.Frame(center, bg=c["canvas_bg"], height=78)
        bottom.pack(fill="x", padx=12, pady=(5, 26)); bottom.pack_propagate(False)
        tools = KomicoveCard(bottom, c, height=68, radius=RADIUS_LARGE, padding=8)
        tools.pack(fill="x")
        self._build_toolbar(tools.content)
        self.bind("<Delete>", lambda _e: self._delete())
        self.bind("<Control-d>", lambda _e: self._duplicate())
        self.bind("<Control-s>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

    @staticmethod
    def _rounded_rect(canvas, x1, y1, x2, y2, radius, *, fill, outline="", width=1):
        radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
        points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                  x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                  x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
        canvas.create_polygon(points, smooth=True, splinesteps=18, fill=fill,
                              outline=outline, width=width)

    def _build_toolbar(self, parent):
        c = THEME
        actions = [
            (ui("Selecionar", "Select"), lambda: self._set_tool("select"), "primary", "mouse-pointer-2"),
            (ui("Adicionar", "Add"), lambda: self._set_tool("add"), "secondary", "square-plus"),
            (ui("Duplicar", "Duplicate"), self._duplicate, "secondary", "copy"),
            (ui("Excluir", "Delete"), self._delete, "danger", "trash-2"),
            (ui("Para trás", "Move back"), lambda: self._order(-1), "secondary", "arrow-left"),
            (ui("Para frente", "Move forward"), lambda: self._order(1), "secondary", "arrow-right"),
        ]
        for index, (text, command, kind, icon) in enumerate(actions):
            if index == 4:
                tk.Frame(parent, width=1, bg=c["border"]).pack(side="left", fill="y", padx=9, pady=4)
            KomicoveButton(parent, text, command, c, kind=kind, compact=True,
                           icon_name=icon).pack(side="left", padx=3)
        KomicoveButton(parent, ui("Salvar layout", "Save layout"), self._save, c,
                       kind="primary", compact=True, icon_name="save",
                       min_width=154).pack(side="right", padx=3)

    def _build_inspector(self, parent):
        c = THEME
        tk.Label(parent, text=ui("Propriedades", "Properties"), font=("Segoe UI", 15, "bold"),
                 bg=c["surface"], fg=c["text"]).pack(anchor="w", padx=20, pady=(20, 2))
        tk.Label(parent, text=ui("Ajuste o quadro selecionado", "Adjust the selected panel"),
                 font=("Segoe UI", 8), bg=c["surface"], fg=c["text_dim"]).pack(anchor="w", padx=20)
        tk.Frame(parent, height=1, bg=c["border"]).pack(fill="x", padx=20, pady=16)

        selected = KomicoveCard(parent, c, height=86, radius=RADIUS_MEDIUM, padding=12)
        selected.pack(fill="x", padx=16)
        self._selected_title = tk.Label(selected.content, text=ui("Nenhum quadro", "No panel selected"),
                                        font=("Segoe UI", 11, "bold"), bg=c["surface"], fg=c["text"])
        self._selected_title.pack(anchor="w")
        self._selected_detail = tk.Label(selected.content, text=ui("Clique em um quadro para editar.",
                                                                    "Click a panel to edit it."),
                                         font=("Segoe UI", 8), bg=c["surface"], fg=c["text_dim"])
        self._selected_detail.pack(anchor="w", pady=(5, 0))

        tk.Label(parent, text=ui("POSIÇÃO E TAMANHO", "POSITION AND SIZE"),
                 font=("Segoe UI", 8, "bold"), bg=c["surface"], fg=c["text_dim"]).pack(anchor="w", padx=20, pady=(22, 8))
        values = KomicoveCard(parent, c, height=154, radius=RADIUS_MEDIUM, padding=12)
        values.pack(fill="x", padx=16)
        self._value_labels = {}
        for index, key in enumerate(("X", "Y", "W", "H")):
            cell = tk.Frame(values.content, bg=c["surface_alt"])
            cell.grid(row=index // 2, column=index % 2, padx=4, pady=4, sticky="nsew")
            values.content.grid_columnconfigure(index % 2, weight=1)
            tk.Label(cell, text=key, font=("Segoe UI", 8, "bold"), bg=c["surface_alt"],
                     fg=c["text_dim"]).pack(anchor="w", padx=9, pady=(6, 0))
            label = tk.Label(cell, text="0%", font=("Consolas", 10, "bold"), bg=c["surface_alt"],
                             fg=c["text"])
            label.pack(anchor="w", padx=9, pady=(0, 6))
            self._value_labels[key] = label

        tk.Label(parent, text=ui("ORDEM DE LEITURA", "READING ORDER"),
                 font=("Segoe UI", 8, "bold"), bg=c["surface"], fg=c["text_dim"]).pack(anchor="w", padx=20, pady=(22, 8))
        order_card = KomicoveCard(parent, c, height=92, radius=RADIUS_MEDIUM, padding=12)
        order_card.pack(fill="x", padx=16)
        tk.Label(order_card.content, text=ui("A ordem dos números define a sequência.",
                                             "Panel numbers define the sequence."),
                 font=("Segoe UI", 8), bg=c["surface"], fg=c["text_dim"],
                 wraplength=220, justify="left").pack(anchor="w")
        buttons = tk.Frame(order_card.content, bg=c["surface"]); buttons.pack(anchor="w", pady=(7, 0))
        KomicoveButton(buttons, ui("Anterior", "Earlier"), lambda: self._order(-1), c,
                       kind="secondary", compact=True, icon_name="arrow-left").pack(side="left", padx=(0, 5))
        KomicoveButton(buttons, ui("Próximo", "Later"), lambda: self._order(1), c,
                       kind="secondary", compact=True, icon_name="arrow-right").pack(side="left")

    def _set_tool(self, name):
        self._tool = name
        self.cv.config(cursor="crosshair" if name == "add" else "fleur")

    def _geometry(self):
        width = max(1, self.cv.winfo_width()); height = max(1, self.cv.winfo_height())
        scale = min((width - 38) / self.image.width, (height - 38) / self.image.height)
        image_width = int(self.image.width * scale); image_height = int(self.image.height * scale)
        return (width - image_width) // 2, (height - image_height) // 2, image_width, image_height

    def _draw(self):
        if not hasattr(self, "cv") or not self.cv.winfo_exists(): return
        c = THEME; self.cv.delete("all")
        offset_x, offset_y, image_width, image_height = self._geometry()
        preview = self.image.resize((image_width, image_height)); self._photo = ImageTk.PhotoImage(preview)
        self.cv.create_rectangle(offset_x - 7, offset_y - 7, offset_x + image_width + 7,
                                 offset_y + image_height + 7, fill=c["shadow"], outline=c["border"])
        self.cv.create_image(offset_x, offset_y, anchor="nw", image=self._photo)
        centers = []
        for index, (left, top, right, bottom) in enumerate(self.regions):
            box = (offset_x + left * image_width, offset_y + top * image_height,
                   offset_x + right * image_width, offset_y + bottom * image_height)
            selected = index == self.selected; color = c["accent2"] if selected else c["accent"]
            if selected:
                self.cv.create_rectangle(box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3,
                                         outline=c["border_glow"], width=5)
            self.cv.create_rectangle(*box, outline=color, width=3 if selected else 2)
            centers.append(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))
            self.cv.create_oval(box[0] + 7, box[1] + 7, box[0] + 33, box[1] + 33,
                                fill=c["accent"], outline="#ffffff" if selected else c["accent2"])
            self.cv.create_text(box[0] + 20, box[1] + 20, text=str(index + 1),
                                fill="#ffffff", font=("Segoe UI", 9, "bold"))
            if selected:
                for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
                    self.cv.create_rectangle(x - 7, y - 7, x + 7, y + 7,
                                             fill="#ffffff", outline=c["accent"], width=3)
        for first, second in zip(centers, centers[1:]):
            self.cv.create_line(first[0], first[1], second[0], second[1],
                                fill=c["accent2"], width=2, dash=(5, 5), arrow="last")
        self._refresh_inspector()

    def _refresh_inspector(self):
        if not hasattr(self, "_selected_title"): return
        if self.selected is None or not (0 <= self.selected < len(self.regions)):
            self._selected_title.config(text=ui("Nenhum quadro", "No panel selected"))
            self._selected_detail.config(text=ui("Clique em um quadro para editar.", "Click a panel to edit it."))
            values = (0, 0, 0, 0)
        else:
            left, top, right, bottom = self.regions[self.selected]
            self._selected_title.config(text=ui(f"Quadro {self.selected + 1}", f"Panel {self.selected + 1}"))
            self._selected_detail.config(text=ui(f"{len(self.regions)} quadros nesta página",
                                                  f"{len(self.regions)} panels on this page"))
            values = (left, top, right - left, bottom - top)
        for key, value in zip(("X", "Y", "W", "H"), values):
            self._value_labels[key].config(text=f"{value * 100:.1f}%")

    def _norm(self, x, y):
        offset_x, offset_y, image_width, image_height = self._geometry()
        return max(0, min(1, (x - offset_x) / image_width)), max(0, min(1, (y - offset_y) / image_height))

    def _down(self, event):
        x, y = self._norm(event.x, event.y); self.start = (x, y); self.action = "new"; self.selected = None
        if self._tool != "add":
            for index in range(len(self.regions) - 1, -1, -1):
                left, top, right, bottom = self.regions[index]
                if left <= x <= right and top <= y <= bottom:
                    self.selected = index; self.action = "move"; self.original = list(self.regions[index])
                    corners = [(left, top, "tl"), (right, top, "tr"), (left, bottom, "bl"), (right, bottom, "br")]
                    nearest = min(corners, key=lambda point: (point[0] - x) ** 2 + (point[1] - y) ** 2)
                    if abs(nearest[0] - x) < .035 and abs(nearest[1] - y) < .035: self.action = nearest[2]
                    break
        self._draw()

    def _move(self, event):
        x, y = self._norm(event.x, event.y); start_x, start_y = self.start
        if self.action == "new":
            self.regions.append([min(start_x, x), min(start_y, y), max(start_x, x), max(start_y, y)])
            self.selected = len(self.regions) - 1; self.action = "new-active"
        elif self.action == "new-active":
            self.regions[self.selected] = [min(start_x, x), min(start_y, y), max(start_x, x), max(start_y, y)]
        elif self.selected is not None:
            left, top, right, bottom = self.original
            if self.action == "move":
                dx, dy = x - start_x, y - start_y; dx = max(-left, min(1 - right, dx)); dy = max(-top, min(1 - bottom, dy))
                self.regions[self.selected] = [left + dx, top + dy, right + dx, bottom + dy]
            else:
                if "l" in self.action: left = min(x, right - .02)
                if "r" in self.action: right = max(x, left + .02)
                if "t" in self.action: top = min(y, bottom - .02)
                if "b" in self.action: bottom = max(y, top + .02)
                self.regions[self.selected] = [left, top, right, bottom]
        self._draw()

    def _up(self, _event):
        self.action = None
        self.regions = [region for region in self.regions if region[2] - region[0] >= .02 and region[3] - region[1] >= .02]
        if self.selected is not None: self.selected = min(self.selected, len(self.regions) - 1) if self.regions else None
        self._tool = "select"; self.cv.config(cursor="fleur"); self._draw()

    def _delete(self):
        if self.selected is not None: self.regions.pop(self.selected); self.selected = None; self._draw()

    def _duplicate(self):
        if self.selected is None: return
        left, top, right, bottom = self.regions[self.selected]; width, height = right - left, bottom - top
        dx = min(.025, max(0., 1 - right)); dy = min(.025, max(0., 1 - bottom))
        self.regions.insert(self.selected + 1, [left + dx, top + dy, min(1., left + dx + width), min(1., top + dy + height)])
        self.selected += 1; self._draw()

    def _order(self, direction):
        if self.selected is None: return
        target = max(0, min(len(self.regions) - 1, self.selected + direction))
        self.regions[self.selected], self.regions[target] = self.regions[target], self.regions[self.selected]
        self.selected = target; self._draw()

    def _reset(self):
        if self._detecting:
            return
        self._detecting=True
        if self.on_redetect is None:
            from komicove_app.guided import detect_result
            image=self.image
            self.on_redetect=lambda: detect_result(image).regions
        future=self._detector.submit(self.on_redetect)
        def finish():
            self._detect_poll=None
            if not future.done():
                self._detect_poll=self.after(30,finish)
                return
            self._detecting=False
            try:
                self.auto_regions=[list(region) for region in future.result()]
            except Exception:
                messagebox.showerror(ui('Redetectar','Redetect'),ui('Não foi possível detectar os quadros.','Could not detect panels.'),parent=self)
                return
            self.regions=[list(region) for region in self.auto_regions]
            self.selected=None
            self._draw()
        self._detect_poll=self.after(30,finish)

    def _dispose(self,event):
        if event.widget is self:
            if self._detection_cancel is not None:
                self._detection_cancel.set()
            if self._detect_poll:
                self.after_cancel(self._detect_poll)
            self._detector.shutdown(wait=False,cancel_futures=True)

    def _save(self):
        if self._detecting:
            return
        if not self.regions:
            messagebox.showwarning(ui("Editor de quadros", "Panel editor"), ui("Crie pelo menos um quadro.", "Create at least one panel."), parent=self)
            return
        self.on_save([tuple(region) for region in self.regions]); self.destroy()
