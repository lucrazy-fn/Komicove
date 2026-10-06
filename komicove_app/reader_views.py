from komicove_app.runtime import *
import komicove_app.runtime as _runtime
from komicove_app.guided import DetectionCache, reading_regions
from komicove_app.guided_ai import LocalPanelAI
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from komicove_app.panel_editor import PanelEditor
from komicove_app.design.icons import lucide_icon
from komicove_app.design.styles import KomicoveButton, KomicoveCard
from komicove_app.design.spacing import RADIUS_LARGE, RADIUS_MEDIUM, RADIUS_SMALL


def _guided_crop(image, rect, width, height, zoom, sampling):
    """Resize only the visible part of a panel, including at high zoom."""
    iw, ih = image.size
    left, top, right, bottom = rect
    x, y = int(left * iw), int(top * ih)
    right, bottom = max(x + 1, int(right * iw)), max(y + 1, int(bottom * ih))
    scale = min(max(1, width - 24) / (right - x), max(1, height - 24) / (bottom - y)) * zoom
    nw, nh = max(1, int((right - x) * scale)), max(1, int((bottom - y) * scale))
    px, py = (width - nw) // 2, (height - nh) // 2
    vx, vy = max(0, -px), max(0, -py)
    vw, vh = min(nw, width), min(nh, height)
    box = (x + vx * (right - x) / nw, y + vy * (bottom - y) / nh,
           x + (vx + vw) * (right - x) / nw, y + (vy + vh) * (bottom - y) / nh)
    crop = image.resize((vw, vh), sampling, box=box)
    full = Image.new('RGB', (width, height), THEME['canvas_bg'])
    full.paste(crop, (max(0, px), max(0, py)))
    return full, scale


class ReaderSlider(tk.Canvas):
    """Small native slider drawn in the same visual language as the reader."""
    def __init__(self, parent, value, minimum, maximum, command, *, width=124):
        super().__init__(parent, width=width, height=34, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.minimum = minimum
        self.maximum = maximum
        self.command = command
        self.value = max(minimum, min(maximum, float(value)))
        self._width = width
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._move)
        self.bind("<B1-Motion>", self._move)
        self.bind("<Left>", lambda _e: self.set(self.value - (maximum - minimum) / 20, notify=True))
        self.bind("<Right>", lambda _e: self.set(self.value + (maximum - minimum) / 20, notify=True))
        self._draw()

    def _draw(self):
        self.delete("all")
        c = THEME
        left, right, cy = 9, max(10, self.winfo_width() - 9), 17
        ratio = (self.value - self.minimum) / max(.0001, self.maximum - self.minimum)
        x = left + (right - left) * ratio
        self.create_line(left, cy, right, cy, fill=c["progress_bg"], width=5,
                         capstyle="round")
        self.create_line(left, cy, x, cy, fill=c["accent"], width=5,
                         capstyle="round")
        self.create_oval(x - 8, cy - 8, x + 8, cy + 8, fill=c["border_glow"], outline="")
        self.create_oval(x - 5, cy - 5, x + 5, cy + 5, fill=c["accent2"], outline="#ffffff")

    def _move(self, event):
        left, right = 9, max(10, self.winfo_width() - 9)
        ratio = max(0., min(1., (event.x - left) / max(1, right - left)))
        self.set(self.minimum + ratio * (self.maximum - self.minimum), notify=True)

    def set(self, value, notify=False):
        self.value = max(self.minimum, min(self.maximum, float(value)))
        self._draw()
        if notify and self.command:
            self.command(str(self.value))


class ReaderSwitch(tk.Canvas):
    def __init__(self, parent, variable, *, command=None):
        super().__init__(parent, width=48, height=26, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.variable = variable
        self.command = command
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        self._draw()
        if self.command:
            self.command()

    def _draw(self):
        self.delete("all")
        on = bool(self.variable.get())
        fill = THEME["accent"] if on else THEME["surface_hover"]
        outline = THEME["accent2"] if on else THEME["border"]
        _rrect(self, 1, 1, 47, 25, 13, fill=fill, outline=outline, width=1)
        x = 35 if on else 13
        if on:
            self.create_oval(x - 10, 3, x + 10, 23, fill=THEME["border_glow"], outline="")
        self.create_oval(x - 8, 5, x + 8, 21, fill="#ffffff", outline="")

class LangWindow(tk.Toplevel):
    def __init__(self, master, cb):
        super().__init__(master)
        set_app_icon(self)
        self.cb = cb
        self.title(ui('Idioma / Language', 'Language'))
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        grab_when_visible(self)
        W, H = 340, 232
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        tk.Canvas(self, width=W, height=3, bg=THEME["accent"], highlightthickness=0).place(x=0, y=0)
        tk.Label(self, text="◈ Komicove", font=FLOGO, bg=THEME["bg"], fg=THEME["text"]).pack(pady=(24, 2))
        tk.Label(self, text=ui('Idioma / Language', 'Language'), font=FSMALL, bg=THEME["bg"], fg=THEME["text_dim"]).pack(pady=(0, 16))
        for flag, txt, lang in [("🇧🇷", ui('Português', 'Portuguese'), "pt"), ("🇺🇸", "English", "en")]:
            make_pill(self, f"{flag}   {txt}", lambda l=lang: self._pick(l),
                      variant="soft", font=FBTN, pad_x=20, pad_y=10, min_w=W-100).pack(pady=5)

    def _pick(self, lang):
        global LANG
        LANG = lang
        _runtime.LANG = lang
        save_prefs(lang=lang)
        self.destroy()
        self.cb()

class ThumbnailStrip(tk.Frame):
    def __init__(self, parent, bg_color="#1e1e1e", on_click=None, **kwargs):
        super().__init__(parent, bg=bg_color, **kwargs)
        self._on_click = on_click
        self._bg = bg_color
        self.canvas = tk.Canvas(self, height=110, highlightthickness=0, bg=bg_color)
        self.canvas.pack(side="top", fill="x", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg_color)
        self.win_id = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self._buttons = {}

    def _wheel(self, e):
        self.canvas.xview_scroll(int(-1 * (e.delta / 120)), "units")

    def add_thumbnail(self, tk_img, page_index):
        btn = tk.Button(self.inner, image=tk_img,
                        command=lambda: self._on_click and self._on_click(page_index),
                        bg="#2d2d2d", activebackground="#5a5a5a",
                        relief="flat", borderwidth=0, cursor="hand2",
                        highlightthickness=0)
        btn.image = tk_img
        btn.pack(side="left", padx=4, pady=8)
        self._buttons[page_index] = btn

    def highlight(self, idx):
        for i, b in self._buttons.items():
            if b.winfo_exists():
                b.config(highlightthickness=2 if i == idx else 0,
                         highlightbackground=THEME["accent"],
                         highlightcolor=THEME["accent"])

    def scroll_to(self, idx, total):
        if total <= 0:
            return
        self.canvas.update_idletasks()
        try:
            self.canvas.xview_moveto(max(0.0, (idx / total) - 0.1))
        except Exception:
            pass


class WebtoonContent:
    def __init__(self, parent, loader: SmartPageLoader, width=800, height=900):
        super().__init__(parent)
        if not getattr(self,'_embedded',False):
            self.title(ui('Komicove - Modo Webtoon', 'Komicove - Webtoon Mode'))
            self.geometry(f"{width}x{height}")
        bg = THEME["canvas_bg"]
        self.configure(bg=bg)
        self._loader = loader
        self._tw = width - 40
        self._labels = {}
        self._loaded = set()
        self._placeholders = {}

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self.canvas.create_window((width // 2, 0), window=self.inner, anchor="n")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        self._build_placeholders(bg)
        self.after(60, self._check_visible)
        if not getattr(self, '_embedded', False):
            self.bind('<F11>', lambda _e: self._fullscreen())
            self.bind('<Escape>', lambda _e: self._escape())

    def _fullscreen(self):
        host = self.winfo_toplevel()
        host.attributes('-fullscreen', not host.attributes('-fullscreen'))
        self._apply_fullscreen_layout()

    def _apply_fullscreen_layout(self):
        if self.winfo_toplevel().attributes('-fullscreen'):
            self.scrollbar.pack_forget()
            if hasattr(self, '_bar'): self._bar.pack_forget()
        else:
            self.scrollbar.pack(side='right', fill='y')
            if hasattr(self, '_bar'): self._bar.pack(fill='x', before=self.canvas)

    def _escape(self):
        if self.winfo_toplevel().attributes('-fullscreen'):
            self._fullscreen()
        else:
            self.destroy()

    def _build_placeholders(self, bg=None):
        if bg is None:
            bg = THEME["canvas_bg"]
        ph_text = THEME["text_muted"]
        est_h = int(self._tw * 1.4)
        for idx in range(self._loader.count):
            lbl = tk.Label(self.inner, bg=bg, text=f"··· {idx+1} ···",
                           fg=ph_text, height=int(est_h / 18))
            lbl.pack(side="top", fill="x", pady=0)
            self._labels[idx] = lbl

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self.after(40, self._check_visible)

    def _check_visible(self):
        pass
        if not self.winfo_exists():
            return
        top = self.canvas.canvasy(0)
        bot = top + self.canvas.winfo_height()
        margin = self.canvas.winfo_height()
        for idx, lbl in self._labels.items():
            if idx in self._loaded or not lbl.winfo_exists():
                continue
            ly = lbl.winfo_y()
            lh = lbl.winfo_height()
            if (ly + lh) >= (top - margin) and ly <= (bot + margin):
                self._load_page(idx)

    def _load_page(self, idx):
        self._loaded.add(idx)
        def work():
            try:
                pil = self._loader.get_pil(idx).convert("RGB")
                pil.thumbnail((self._tw, 99999), Image.LANCZOS)
                def apply():
                    if not self.winfo_exists():
                        return
                    tk_img = ImageTk.PhotoImage(pil)
                    lbl = self._labels.get(idx)
                    if lbl and lbl.winfo_exists():
                        lbl.config(image=tk_img, text="", height=0)
                        lbl.image = tk_img
                self.after(0, apply)
            except Exception as e:
                print("webtoon load err:", e)
        threading.Thread(target=work, daemon=True).start()


class WebtoonViewer(WebtoonContent,tk.Toplevel):
    pass


class ReaderContent:
    ZSTEP = 0.15
    ZMIN  = 0.1
    ZMAX  = 5.0
    Z0    = 0.45

    def __init__(self, master, path, loader: SmartPageLoader, on_finish=None):
        super().__init__(master)
        if not getattr(self,'_embedded',False):
            set_app_icon(self)
            self.title(f"Komicove: {Path(path).stem}")
        self.configure(bg=THEME["bg"])

        self._path      = path
        self._loader    = loader
        self._on_finish = on_finish
        self._idx       = 0
        self._zoom      = self.Z0
        self._offset    = [0, 0]
        self._drag      = None
        self._tk_img    = None
        self._rotation  = 0
        self._brightness = 1.0
        self._double    = False
        self._immersive = False
        self._fading    = False
        self._page_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='reader-page')
        self._slider    = None
        self._owned_tk_variables = []
        try: self._content_key = content_id(path)
        except OSError: self._content_key = os.path.normcase(os.path.abspath(path))
        try:
            from komicove_app.library_widgets import get_comic_info
            self._statistics_metadata = get_comic_info(path)
        except Exception:
            self._statistics_metadata = {}

        prefs = load_prefs()
        self._animate_guided = bool(prefs.get("reader_animate_guided", True))
        self._guide_motion = None
        self._guide_animation = None
        self._guided = bool(prefs.get("reader_guided", False))
        self._guide_key = None
        self._guide_cache = DetectionCache(ai=LocalPanelAI.available())
        self._guide_result = None
        self._guide_manual = False
        self._guide_fallback = False
        self._guide_pending = False
        self._detection_future = None
        self._detection_cancel = Event()
        self._detection_poll = None
        self._detection_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="guided")
        self._editor_future = None
        self._editor_poll = None
        self._editor_cancel = Event()
        self.bind("<Destroy>", self._dispose_detection, add="+")
        self._regions = []
        self._region_index = 0
        self._guide_last = False
        self._guide_overview = False
        self._guide_saved = None
        self._guide_written = None
        self._read_started = time.monotonic()
        self._persist_zoom = bool(prefs.get("reader_persist_zoom", True))
        self._persist_position = bool(prefs.get("reader_persist_position", self._persist_zoom))
        self._auto_fit = bool(prefs.get("reader_auto_fit", True))
        self._manga = prefs.get("manga", False)
        reader_state = load_reader_state(self._content_key)
        self._guide_saved = (reader_state.get("guided_page", -1), reader_state.get("guided_panel", 0))
        self._has_saved_zoom = self._persist_zoom and "zoom" in reader_state
        self._viewport_page = None
        self._restored_position = self._persist_position and "offset" in reader_state
        self._updating_zoom = False
        self._zoom = float(reader_state.get("zoom", self.Z0))
        self._offset = list(reader_state.get("offset", [0, 0]))
        self._double = bool(reader_state.get("double", False))
        if self._guided:
            self._double = False
        self._manga = bool(reader_state.get("manga", self._manga))

        if not getattr(self,'_embedded',False):
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h = min(1280, sw-60), min(860, sh-60)
            self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            self.minsize(800, 600)
            self.protocol("WM_DELETE_WINDOW", self._close)

        p = get_progress_page(path)
        if p is not None and 0 <= p < loader.count:
            self._idx = p

        self._thumb_strip = None
        self._thumb_visible = False

        self._build()
        self.after(80, self._initial_render)
        self._prefetch_neighbors()

    @property
    def _count(self):
        return self._loader.count

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        c = THEME

        self._top = tk.Frame(self, bg=c["surface"], height=72)
        self._top.pack(fill="x")
        self._top.pack_propagate(False)
        inner = tk.Frame(self._top, bg=c["surface"])
        inner.pack(fill="both", expand=True, padx=28, pady=13)

        left = tk.Frame(inner, bg=c["surface"])
        left.pack(side="left", fill="y")
        self._pill(left, ui('Voltar', 'Back'), self._close, icon_name="arrow-left",
                   variant="accent", font=FBTN, pad_x=22, pad_y=10, min_w=134).pack(side="left", padx=(0, 22))

        tk.Frame(left, width=1, bg=c["border"]).pack(side="left", fill="y", padx=(0, 22))

        title_box = tk.Frame(left, bg=c["surface"])
        title_box.pack(side="left", fill="y")
        fname = Path(self._path).stem
        if len(fname) > 48: fname = fname[:45] + "…"
        self._reader_title=fname
        self._reader_title_label=tk.Label(title_box,text=fname,font=("Segoe UI",14,"bold"),bg=c["surface"],fg=c["text"],anchor="w")
        self._reader_title_label.pack(anchor="w")
        tk.Label(title_box, text=ui('Leitor', 'Reader'), font=("Segoe UI", 8),
                 bg=c["surface"], fg=c["text_dim"], anchor="w").pack(anchor="w", pady=(1, 0))

        right = tk.Frame(inner, bg=c["surface"])
        self._standard_reader_actions=right
        right.pack(side="right", fill="y")
        self._mkbtn(right, ui('Tela cheia', 'Fullscreen'), self._fullscreen,
                    icon_name="maximize").pack(side="right", padx=3)
        self._mkbtn(right, "Webtoon", self._open_webtoon, icon_name="columns-2").pack(side="right", padx=3)
        self._overview_btn = self._mkbtn(
            right,
            ui('Se localizar', 'Find your place') if self._guided else ui('Encaixar', 'Fit'),
            self._toggle_overview, icon_name="scan",
        )
        self._overview_btn.pack(side="right", padx=3)
        self._mkbtn(right, ui('Preferências', 'Preferences'), self._reader_preferences,
                    icon_name="sliders-horizontal").pack(side="right", padx=3)
        self._mkbtn(right, ui('Editar quadros', 'Edit panels'), self._edit_panels,
                    icon_name="pencil").pack(side="right", padx=3)
        self._mkbtn(right, ui('Modo claro', 'Light mode') if IS_DARK else ui('Modo escuro', 'Dark mode'), self._toggle_theme,
                    icon_name="moon" if IS_DARK else "sun").pack(side="right", padx=3)

        self._bm_btn = self._pill(right, self._bm_label(), self._toggle_bookmark,
                                  icon_name="bookmark", variant="soft")
        self._bm_btn.pack(side="right", padx=3)

        self._guided_reader_actions = tk.Frame(inner, bg=c["surface"])
        guide_row = tk.Frame(self._guided_reader_actions, bg=c["surface"])
        guide_row.pack(anchor="e")
        guide_palette=dict(c,border=c['accent'],border_glow=c['accent2'],surface_alt='#171118',surface_hover='#26161e')
        self._guided_heading=KomicoveButton(guide_row,ui('Se localizar','Find your place'),self._toggle_overview,guide_palette,compact=True,icon_name='book-open')
        self._guide_status = tk.Label(guide_row, font=("Segoe UI", 9), bg=c["surface"], fg=c["text_dim"])
        self._guided_header_items=[self._guided_heading,self._guide_status,
            self._mkbtn(guide_row,ui('Redetectar','Redetect'),self._redetect_panels,icon_name='refresh-cw'),
            self._mkbtn(guide_row,ui('Editar quadros','Edit panels'),self._edit_panels,icon_name='pencil'),
            self._mkbtn(guide_row,ui('Sair','Exit'),self._toggle_guided,icon_name='maximize')]

        self._header_divider = tk.Frame(self, bg=c["border"], height=1)
        self._header_divider.pack(fill="x")

        self._cv = tk.Canvas(self, bg=c["canvas_bg"], highlightthickness=0, cursor="crosshair")
        self._cv.pack(fill="both", expand=True)

        self._bot = tk.Frame(self, bg=c["canvas_bg"], height=94)
        self._bot.pack(fill="x")
        self._bot.pack_propagate(False)
        bot_card = KomicoveCard(self._bot, c, height=82, radius=RADIUS_LARGE, padding=7)
        bot_card.pack(fill="x", padx=28, pady=(4, 8))
        ib = bot_card.content
        self._prog_cv = tk.Canvas(ib, height=5, bg=c["surface"], highlightthickness=0)
        self._prog_cv.pack(fill="x", padx=8)
        self._prog_cv.bind("<Button-1>", self._seek_click)
        self._guided_zoom=1.
        self._guide_render_scale=1.
        controls = tk.Frame(ib, bg=c["surface"])
        self._normal_reader_controls=controls
        controls.pack(fill="both", expand=True, padx=7, pady=(4, 0))

        nf = tk.Frame(controls, bg=c["surface"]); nf.pack(side="left")
        self._nav_btn(nf, "", self._prev,
                      icon=lucide_icon("chevron-left", size=22, state="normal", dark=IS_DARK), size=48).pack(side="left", padx=(0, 7))
        self._page_lbl = tk.Label(nf, text="", font=("Consolas", 12, "bold"),
                                  bg=c["surface_alt"], fg=c["text"], width=11, padx=10, pady=8,
                                  cursor="hand2")
        self._page_lbl.pack(side="left", padx=2)
        self._page_lbl.bind("<Button-1>", lambda _e: self._show_page_picker())
        self._nav_btn(nf, "", self._next,
                      icon=lucide_icon("chevron-right", size=22, state="normal", dark=IS_DARK), size=48).pack(side="left", padx=(7, 0))

        zf = tk.Frame(controls, bg=c["surface"]); zf.pack(side="left", padx=16)
        self._nav_btn(zf, "", self._zoom_out,
                      icon=lucide_icon("zoom-out", size=19, state="normal", dark=IS_DARK)).pack(side="left", padx=3)
        self._zoom_lbl = tk.Label(zf, text="45%", font=("Segoe UI", 9, "bold"),
                                  bg=c["surface"], fg=c["text_dim"], width=5)
        self._zoom_lbl.pack(side="left", padx=4)
        self._nav_btn(zf, "", self._zoom_in,
                      icon=lucide_icon("zoom-in", size=19, state="normal", dark=IS_DARK)).pack(side="left", padx=3)

        self._zvar = self._own_variable(tk.DoubleVar(master=self,value=self._zoom))
        sl = ReaderSlider(controls, self._zoom, self.ZMIN, self.ZMAX,
                          self._slider_zoom, width=126)
        sl.pack(side="left", padx=(2, 10))
        self._slider = sl

        self._thumb_btn = self._pill(controls, ui('Páginas', 'Pages'), self._show_page_picker,
                                     icon_name="layout-grid", variant="soft")
        self._thumb_btn.pack(side="right", padx=4)
        self._double_btn = self._pill(controls, ui('Dupla', 'Double page'), self._toggle_double,
                                      icon_name="book-open", variant="soft")
        self._double_btn.pack(side="right", padx=3)
        self._pill(controls, ui('Marcadores', 'Bookmarks'), self._show_bookmarks,
                   icon_name="bookmark", variant="soft").pack(side="right", padx=3)
        self._nav_btn(controls, "", self._rotate,
                      icon=lucide_icon("rotate-cw", size=19, state="normal", dark=IS_DARK)).pack(side="right", padx=3)
        self._nav_btn(controls, "", self._show_shortcuts,
                      icon=lucide_icon("circle-help", size=19, state="normal", dark=IS_DARK)).pack(side="right", padx=3)

        bf = tk.Frame(controls, bg=c["surface"]); bf.pack(side="right", padx=(0, 7))
        bright_icon = lucide_icon("sun", size=17, state="normal", dark=IS_DARK)
        bright_label = tk.Label(bf, image=bright_icon, bg=c["surface"])
        bright_label.image = bright_icon
        bright_label.pack(side="left", padx=(0, 2))
        self._bright_var = self._own_variable(tk.DoubleVar(master=self,value=self._brightness))
        bright_sl = ReaderSlider(bf, self._brightness, 0.3, 2.0,
                                 self._slider_brightness, width=88)
        bright_sl.pack(side="left")
        self._brightness_slider = bright_sl

        self._guided_btn = self._pill(controls, ui('Guiada', 'Guided'), self._toggle_guided,
                                      icon_name="focus", variant="soft")
        self._guided_btn.pill_set_active(self._guided)
        self._guided_btn.pack(side="right", padx=3)

        txt = ui('Mangá', 'Manga')
        self._manga_btn = self._pill(controls, txt, self._toggle_manga,
                                     icon_name="book-open-check", variant="soft")
        self._manga_btn.pill_set_active(self._manga)
        self._manga_btn.pack(side="right", padx=3)

        self._guided_footer=tk.Frame(ib,bg=c["surface"])
        guide_controls=self._guided_footer
        self._nav_btn(guide_controls,"",self._prev,
            icon=lucide_icon("chevron-left",size=22,dark=IS_DARK),size=44).pack(side="left",padx=5)
        self._guided_page_lbl=tk.Label(guide_controls,font=("Consolas",11,"bold"),bg=c["surface_alt"],fg=c["text"],width=10,pady=8,cursor="hand2")
        self._guided_page_lbl.pack(side="left",padx=4)
        self._guided_page_lbl.bind("<Button-1>",lambda e:self._show_page_picker())
        self._nav_btn(guide_controls,"",self._next,
            icon=lucide_icon("chevron-right",size=22,dark=IS_DARK),size=44).pack(side="left",padx=5)
        self._nav_btn(guide_controls,"",lambda:self._set_guided_zoom(self._guided_zoom/1.15),
            icon=lucide_icon("zoom-out",size=19,dark=IS_DARK)).pack(side="left",padx=(14,4))
        self._guided_zoom_lbl=tk.Label(guide_controls,font=("Segoe UI",10),bg=c["surface"],fg=c["text_dim"],width=5)
        self._guided_zoom_lbl.pack(side="left",padx=4)
        self._nav_btn(guide_controls,"",lambda:self._set_guided_zoom(self._guided_zoom*1.15),
            icon=lucide_icon("zoom-in",size=19,dark=IS_DARK)).pack(side="left",padx=4)
        self._guided_slider=ReaderSlider(guide_controls,1.,.5,4.,self._set_guided_zoom,width=180)
        self._guided_slider.pack(side="left",padx=14)
        self._nav_btn(guide_controls,"",self._show_page_picker,
            icon=lucide_icon("layout-grid",size=19,dark=IS_DARK)).pack(side="right",padx=5)
        self._nav_btn(guide_controls,"",self._toggle_overview,
            icon=lucide_icon("scan",size=19,dark=IS_DARK)).pack(side="right",padx=5)
        self._guide_mode_label=KomicoveButton(guide_controls,ui('Modo aproximado','Approximate mode'),self._edit_panels,guide_palette,compact=True,icon_name='focus')

        self._thumb_frame = tk.Frame(self, bg=c["surface"], height=120)
        self._thumb_frame.pack_propagate(False)

        self._cv.bind("<ButtonPress-1>",  self._drag_start)
        self._cv.bind("<B1-Motion>",      self._drag_move)
        self._cv.bind("<ButtonRelease-1>",self._drag_end)
        self._cv.bind("<MouseWheel>",     self._wheel)
        self._cv.bind("<Configure>",      lambda e: self.after(80, lambda: self._show(reset=False)))
        self.bind("<Left>",   lambda e: self._prev())
        self.bind("<Right>",  lambda e: self._next())
        self.bind("<Prior>",  lambda e: self._prev())
        self.bind("<Next>",   lambda e: self._next())
        self.bind("<equal>",  lambda e: self._zoom_in())
        self.bind("<minus>",  lambda e: self._zoom_out())
        self.bind("<f>",      lambda e: self._fullscreen())
        self.bind("<e>",      lambda e: self._fit())
        self.bind("<E>",      lambda e: self._fit())
        self.bind("<F11>",    lambda e: self._fullscreen())
        self.bind("<i>",      lambda e: self._immersive_toggle())
        self.bind("<Escape>", lambda e: self._escape())
        self.bind("<t>",      lambda e: self._toggle_theme())
        self.bind("<g>",      lambda e: self._toggle_thumbnails())
        self.bind("<l>",      self._toggle_guided)
        self.bind("<L>",      self._toggle_guided)
        self.bind("<v>",      self._toggle_overview)
        self.bind("<V>",      self._toggle_overview)
        self.bind("<b>",      lambda e: self._toggle_bookmark())
        self.bind("<r>",      lambda e: self._rotate())
        self.bind("<question>", lambda e: self._show_shortcuts())
        self.bind("<F1>", lambda e: self._show_shortcuts())
        self.bind("<Home>", lambda e: self._fade_to(0))
        self.bind("<End>", lambda e: self._fade_to(max(0, self._count - 1)))
        self.bind("<Control-g>", lambda e: self._show_page_picker())
        self.bind("<Control-e>", lambda e: self._edit_panels())
        self.bind("<Control-comma>", lambda e: self._reader_preferences())
        self.bind("<space>", lambda e: self._next())
        self.bind("<bracketleft>",  lambda e: self._set_brightness(self._brightness - 0.1))
        self.bind("<bracketright>", lambda e: self._set_brightness(self._brightness + 0.1))
        if self._immersive:
            self._apply_immersive_layout()

    def _pill(self, parent, text, cmd, *, icon=None, icon_name=None, variant="ghost",
              font=FSMALL, pad_x=14, pad_y=8, min_w=0):
        return make_pill(parent, text, cmd, icon=icon, icon_name=icon_name, variant=variant,
                         font=font, pad_x=pad_x, pad_y=pad_y, min_w=min_w)

    def _mkbtn(self, parent, text, cmd, accent=False, icon=None, icon_name=None):
        return self._pill(parent, text, cmd, icon=icon, icon_name=icon_name,
                          variant="accent" if accent else "ghost")

    def _nav_btn(self, parent, text, cmd, icon=None, size=40):
        c = THEME
        host_bg = parent.cget("bg")
        r = 12
        cv = tk.Canvas(parent, width=size, height=size, bg=host_bg,
                       highlightthickness=0, cursor="hand2", takefocus=1)
        def render(fill, fg, outline):
            cv.delete("all")
            _rrect(cv, 1, 1, size - 1, size - 1, r, fill=fill)
            if outline: _rrect(cv, 1, 1, size - 2, size - 2, r, outline=outline, width=1)
            if icon: cv.create_image(size // 2, size // 2, image=icon)
            if text: cv.create_text(size // 2, size // 2, text=text,
                                    font=("Segoe UI", 13, "bold"), fill=fg)
        render(c["surface_alt"], c["text"], c["border"])
        cv.bind("<Enter>", lambda e: render(c["accent"], "#fff", c["accent"]))
        cv.bind("<Leave>", lambda e: render(c["surface_alt"], c["text"], c["border"]))
        cv.bind("<Button-1>", lambda e: cmd())
        cv.bind("<Return>", lambda e: cmd())
        cv.bind("<space>", lambda e: cmd())
        cv.bind("<FocusIn>", lambda e: render(c["surface_alt"], c["text"], c["accent"]))
        cv.bind("<FocusOut>", lambda e: render(c["surface_alt"], c["text"], c["border"]))
        return cv

    def _processed_pil(self, idx):
        key = (idx, self._rotation, self._brightness)
        if getattr(self, '_processed_key', None) == key:
            return self._processed_image
        img = self._loader.get_pil(idx)
        if self._rotation:
            img = img.rotate(-self._rotation, expand=True, resample=Image.BICUBIC)
        if abs(self._brightness - 1.0) > 0.01:
            img = ImageEnhance.Brightness(img.convert("RGB")).enhance(self._brightness).convert("RGBA")
        self._processed_key, self._processed_image = key, img
        return img

    def _compose_pages(self):
        pass
        base = self._processed_pil(self._idx)
        if not self._double:
            return base
        if self._idx == 0:
            return base
        nxt_idx = self._idx + 1
        if nxt_idx >= self._count:
            return base
        nxt = self._processed_pil(nxt_idx)
        h = max(base.height, nxt.height)
        left, rightimg = (nxt, base) if self._manga else (base, nxt)
        combo = Image.new("RGBA", (left.width + rightimg.width, h), (0, 0, 0, 0))
        combo.paste(left, (0, (h - left.height) // 2))
        combo.paste(rightimg, (left.width, (h - rightimg.height) // 2))
        return combo

    def _show(self, reset=True, alpha=1.0):
        cw = self._cv.winfo_width() or 800
        ch = self._cv.winfo_height() or 600
        frame_key = (self._idx, cw, ch, self._rotation, self._brightness,
                     self._double, self._manga, self._guided, self._zoom,
                     tuple(self._offset), self._guide_key, self._region_index,
                     self._guide_overview, self._guided_zoom, self._guide_motion,
                     tuple(self._regions), self._guide_pending, self._guide_fallback)
        if not reset and self._fading and alpha < 1.0 and getattr(self, '_rendered_key', None) == frame_key:
            self._present_frame(self._rendered_frame, alpha)
            return
        img = self._compose_pages()
        iw, ih = img.size
        if not self._guide_motion:
            record_page_read(
                self._content_key, self._idx, self._count,
                path=self._path, metadata=self._statistics_metadata,
            )

        if self._guided:
            key = (self._idx, self._rotation, self._double, self._manga)
            if key != self._guide_key:
                manual=load_manual_panels(self._content_key,self._idx)
                if manual:
                    self._guide_pending=False
                    self._regions=[tuple(r) for r in manual]; self._guide_fallback=False
                    self._guide_manual=True
                    self._guide_result=None
                else:
                    self._guide_manual=False
                    self._guide_fallback=True
                    self._regions=reading_regions(iw, ih, self._manga)
                    self._request_detection(key)
                self._region_index = len(self._regions) - 1 if self._guide_last else 0
                if self._guide_saved and self._guide_saved[0] == self._idx and not self._guide_last:
                    self._region_index = max(0, min(int(self._guide_saved[1]), len(self._regions) - 1))
                self._guide_saved = None
                self._guide_last = False
                self._guide_key = key
            rect = self._regions[self._region_index]
            if self._guide_motion and self._guide_motion[:2] == (self._guide_key, self._region_index) and not self._guide_overview:
                rect = self._guide_motion[2]
            if not self._guide_overview:
                source = getattr(self, '_guide_preview', None) if self._guide_motion else None
                source = source if source is not None else img
                sampling = Image.Resampling.BILINEAR if self._guide_motion else Image.Resampling.LANCZOS
                full, scale = _guided_crop(source, rect, cw, ch, self._guided_zoom, sampling)
                self._guide_render_scale = scale * source.width / iw
                self._rendered_key, self._rendered_frame = frame_key, full
                self._present_frame(full, alpha)
                if not self._guide_motion:
                    self._hud()
                    self._save_guided_position()
                return
            left, top, right, bottom = rect
            x, y = int(left * iw), int(top * ih)
            bounds=(x,y,max(x+1,int(right*iw)),max(y+1,int(bottom*ih)))
            # resize creates the output; whole-page crops need no full-size copy.
            crop = img if self._guide_overview or bounds==(0,0,iw,ih) else img.crop(bounds)
            scale = min(max(1, cw - 24) / crop.width, max(1, ch - 24) / crop.height)*self._guided_zoom
            self._guide_render_scale=scale
            sampling = Image.Resampling.BILINEAR if self._guide_motion else Image.Resampling.LANCZOS
            crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), sampling)
            full = Image.new("RGB", (cw, ch), THEME["canvas_bg"])
            full.paste(crop.convert("RGB"), ((cw - crop.width) // 2, (ch - crop.height) // 2))
            if self._guide_overview:
                ox, oy = (cw - crop.width) // 2, (ch - crop.height) // 2
                bounds=(ox+left*crop.width,oy+top*crop.height,ox+right*crop.width,oy+bottom*crop.height)
                overlay=Image.new("RGBA",full.size)
                draw=ImageDraw.Draw(overlay)
                for padding,opacity in ((7,20),(4,38),(2,70)):
                    draw.rectangle(tuple(v+(-padding if i<2 else padding) for i,v in enumerate(bounds)),outline=(255,40,65,opacity),width=2)
                draw.rectangle(bounds,outline=THEME["accent"],width=3)
                full=Image.alpha_composite(full.convert("RGBA"),overlay).convert("RGB")
            self._rendered_key, self._rendered_frame = frame_key, full
            self._present_frame(full, alpha)
            if not self._guide_motion:
                self._hud()
                self._save_guided_position()
            return

        first_page = self._viewport_page is None
        changed_page = not first_page and self._viewport_page != self._idx
        if first_page or changed_page or reset:
            old_zoom = self._zoom
            if reset or (changed_page and not self._persist_zoom) or (first_page and not self._has_saved_zoom):
                self._zoom = min((cw - 24) / iw, (ch - 24) / ih) * .95 if self._auto_fit else self.Z0
            keep_position = self._persist_position and (changed_page or (first_page and self._restored_position)) and not reset
            if keep_position:
                ratio = self._zoom / old_zoom if old_zoom else 1
                self._offset = [v * ratio for v in self._offset]
            else:
                self._offset = [(-1 if self._manga else 1) * max(0, (iw * self._zoom - cw) / 2),
                                max(0, (ih * self._zoom - ch) / 2)]
            self._viewport_page = self._idx
        # Clamp retained framing when the next page has different dimensions.
        mx, my = max(0, (iw * self._zoom - cw) / 2), max(0, (ih * self._zoom - ch) / 2)
        self._offset = [max(-mx, min(mx, self._offset[0])), max(-my, min(my, self._offset[1]))]
        self._pan_bounds = (mx, my)

        nw = max(1, int(iw * self._zoom))
        nh = max(1, int(ih * self._zoom))
        resized = img.resize((nw, nh), Image.BILINEAR)

        bg_rgb = (7, 7, 14) if IS_DARK else (232, 228, 222)
        full = Image.new("RGB", (cw, ch), bg_rgb)
        px = cw // 2 + int(self._offset[0]) - nw // 2
        py = ch // 2 + int(self._offset[1]) - nh // 2
        full.paste(resized.convert("RGB"), (px, py))

        self._rendered_key, self._rendered_frame = frame_key, full
        self._present_frame(full, alpha)
        self._hud()

    def _present_frame(self, full, alpha=1.0):
        if alpha < 1.0:
            background = THEME['canvas_bg'] if self._guided else ((7, 7, 14) if IS_DARK else (232, 228, 222))
            full = Image.blend(Image.new('RGB', full.size, background), full, alpha)
        self._tk_img = ImageTk.PhotoImage(full)
        item = getattr(self, '_canvas_image', None)
        if item is not None and self._cv.type(item):
            self._cv.itemconfigure(item, image=self._tk_img)
            self._cv.coords(item, 0, 0)
        else:
            self._canvas_image = self._cv.create_image(0, 0, anchor='nw', image=self._tk_img)

    def _fade_to(self, new_idx):
        if self._fading: return
        new_idx = max(0, min(new_idx, self._count - 1))
        if new_idx == self._idx: return
        self._fading = True
        future = self._page_executor.submit(self._loader.get_pil, new_idx)
        start = None

        def animate():
            nonlocal start
            if not future.done():
                self.after(16, animate)
                return
            if start is None:
                try:
                    future.result()
                except Exception:
                    self._fading = False
                    log.exception('Page loading failed')
                    return
                start = time.perf_counter()
            elapsed = time.perf_counter() - start
            prog = min(elapsed / FADE_SPEED, 1.0)
            # Loading/rendering can skip the entire second half of the fade.
            # Commit the page even when the next frame is already the last.
            if prog >= 0.5 and not hasattr(animate, "swapped"):
                self._idx = new_idx
                save_progress(self._path, self._idx)
                animate.swapped = True
                self._prefetch_neighbors()
            if prog < 0.5:
                self._show(reset=False, alpha=1.0 - ease_out(prog * 2))
            elif prog < 1.0:
                self._show(reset=False, alpha=ease_out((prog - 0.5) * 2))
            else:
                self._show(reset=False)
                self._fading = False
                return
            self.after(16, animate)
        animate()

    def _prefetch_neighbors(self):
        self._loader.prefetch(self._idx + 1)
        self._loader.prefetch(self._idx + 2)
        self._loader.prefetch(self._idx - 1)

    def _edit_panels(self):
        if self._editor_future is not None:
            return
        if self._double:
            messagebox.showinfo(ui('Editor de quadros','Panel editor'),
                ui('Desative a página dupla para editar esta página.','Turn off double-page mode to edit this page.'),parent=self)
            return
        page=self._idx
        key=(page,self._rotation,False,self._manga)
        preview=self._compose_pages()
        loader,cache,manga,rotation=self._loader,self._guide_cache,self._manga,self._rotation
        cancel=self._editor_cancel=Event()
        def detect(force=False):
            original=loader.get_pil(page)
            rotated=original.rotate(-rotation,expand=True,resample=Image.Resampling.BICUBIC) if rotation else None
            try:
                return cache.detect(key,rotated if rotated is not None else original,manga,force,cancel).regions
            finally:
                if rotated is not None:
                    rotated.close()
        def saved(regions):
            save_manual_panels(self._content_key,page,regions)
            if self._idx==page:
                self._guide_key=None; self._regions=list(regions); self._region_index=0
                self._show(reset=False)
        future=self._detection_executor.submit(detect)
        self._editor_future=future
        def finish():
            self._editor_poll=None
            if not future.done():
                self._editor_poll=self.after(30,finish)
                return
            self._editor_future=None
            if cancel.is_set():
                return
            try:
                automatic=list(future.result())
            except Exception:
                messagebox.showerror(ui('Editor de quadros','Panel editor'),
                    ui('Não foi possível detectar os quadros.','Could not detect panels.'),parent=self)
                return
            # Keep this editor anchored to its original page if the reader moved.
            current=load_manual_panels(self._content_key,page) or automatic
            PanelEditor(self,preview,current,automatic,saved,
                        on_redetect=lambda: detect(True),detection_cancel=cancel)
        self._editor_poll=self.after(30,finish)

    def _request_detection(self, key, force=False):
        self._detection_cancel.set()
        self._detection_cancel=Event()
        cancel=self._detection_cancel
        if self._detection_future:
            self._detection_future.cancel()
        if self._detection_poll:
            self.after_cancel(self._detection_poll)
        self._guide_pending=True
        page,rotation,_,manga=key
        # Detect original colors, not the user's brightness/theme transformation.
        loader,cache=self._loader,self._guide_cache
        def analyze():
            image=loader.get_pil(page)
            rotated=image.rotate(-rotation,expand=True,resample=Image.Resampling.BICUBIC) if rotation else None
            try:
                return cache.detect(key,rotated if rotated is not None else image,manga,force,cancel)
            finally:
                if rotated is not None:
                    rotated.close()
        future=self._detection_executor.submit(analyze)
        self._detection_future=future
        def poll():
            self._detection_poll=None
            if future is not self._detection_future:
                return
            if not future.done():
                self._detection_poll=self.after(30,poll)
                return
            self._guide_pending=False
            if key != self._guide_key:
                return
            try:
                result=future.result()
            except Exception:
                log.exception("Guided detection failed")
                self._hud()
                return
            self._guide_result=result
            if not load_manual_panels(self._content_key,page):
                self._regions=list(result.regions)
                self._guide_fallback=result.fallback
                self._region_index=min(self._region_index,len(self._regions)-1)
            elif force:
                messagebox.showinfo(ui('Redetectar','Redetect'),
                    ui('Detecção atualizada. Seus quadros manuais foram preservados. Use Editar quadros para aplicar a detecção.',
                       'Detection updated. Your manual panels were preserved. Use Edit panels to apply the detection.'),parent=self)
            if self._guided:
                self._show(reset=False)
        self._detection_poll=self.after(30,poll)

    def _redetect_panels(self):
        if self._fading:
            return
        self._request_detection((self._idx,self._rotation,self._double,self._manga),force=True)
        self._hud()

    def _dispose_detection(self,event):
        if event.widget is not self:
            return
        self._detection_cancel.set()
        self._editor_cancel.set()
        if self._editor_poll:
            self.after_cancel(self._editor_poll)
        if self._editor_future:
            self._editor_future.cancel()
        self._tk_img=None
        self._rendered_frame = None
        self._processed_image = None
        self._guide_preview = None
        self._page_executor.shutdown(wait=False, cancel_futures=True)
        if self._detection_poll:
            self.after_cancel(self._detection_poll)
        if self._detection_future:
            self._detection_future.cancel()
        self._detection_executor.shutdown(wait=False,cancel_futures=True)
        self._guide_cache.close()
        # Tk variables can participate in cycles with button callbacks. Delete
        # their Tcl resources here, on the UI thread, instead of letting a
        # background archive/AI allocation trigger their finalizers later.
        for variable in self._owned_tk_variables:
            try:variable.__del__()
            except tk.TclError:pass
            finally:
                variable._tk=None
                variable._root=None
        self._owned_tk_variables.clear()

    def _own_variable(self,variable):
        self._owned_tk_variables.append(variable)
        return variable

    def _update_progress_bar(self):
        if not hasattr(self, "_prog_cv") or not self._prog_cv.winfo_exists():
            return
        n = self._count
        if n == 0: return
        pw = self._prog_cv.winfo_width() or 400
        h = 6
        filled = int(pw * (self._idx + 1) / n)
        self._prog_cv.delete("all")
        self._prog_cv.create_rectangle(0, 0, pw, h, fill=THEME["progress_bg"], outline="")
        if filled > 0:
            self._prog_cv.create_rectangle(0, 0, filled, h, fill=THEME["accent"], outline="")
            self._prog_cv.create_rectangle(0, 0, filled, 2, fill=THEME["accent2"], outline="")
            self._prog_cv.create_oval(filled-4, -1, filled+4, h+1,
                                      fill=THEME["accent2"], outline="")
        for bm in get_bookmarks(self._path):
            bx = int(pw * (bm + 0.5) / n)
            self._prog_cv.create_rectangle(bx-1, 0, bx+1, h, fill="#ffd24a", outline="")

    def _hud(self):
        compact=self.winfo_width()<1100
        self._top.config(height=104 if self._guided and compact else 72)
        title=self._reader_title
        if self._guided and len(title)>(16 if compact else 25):
            title=title[:13 if compact else 22]+'…'
        self._reader_title_label.config(text=title)
        for col,item in enumerate(self._guided_header_items):
            item.grid_forget()
            if compact:
                item.grid(row=0 if col<2 else 1,column=0 if col==0 else 1 if col==1 else col-2,
                          columnspan=2 if col==1 else 1,padx=3,pady=3,sticky='ew')
            else:
                item.grid(row=0,column=col,padx=3,pady=3)
        if self._guided:
            self._normal_reader_controls.pack_forget()
            self._guided_footer.pack(fill="both",expand=True,padx=7,pady=(4,0))
            self._standard_reader_actions.pack_forget()
            self._guided_reader_actions.pack(side="right",fill="y")
            if self._guide_pending:
                label=ui('Detectando…','Detecting…')
            elif self._guide_manual:
                label=ui('Quadros manuais','Manual panels')
            else:
                label=ui('Modo aproximado','Approximate mode') if self._guide_fallback else ui('Detecção automática','Automatic detection')
                if self._guide_result and self._guide_result.method.startswith('ai_'):
                    label=ui('IA local · Aproximado','Local AI · Approximate') if self._guide_fallback else ui('IA local','Local AI')
                if self._guide_result:
                    label+=f" · {self._guide_result.confidence:.0%}"
            self._guide_status.config(text=label,fg=THEME['accent'] if self._guide_fallback else '#39c68c')
            if self._guide_fallback and not self._guide_pending:
                self._guide_mode_label.pack(side="right",padx=6)
            else:
                self._guide_mode_label.pack_forget()
        else:
            self._guided_footer.pack_forget()
            self._normal_reader_controls.pack(fill="both",expand=True,padx=7,pady=(4,0))
            self._guided_reader_actions.pack_forget()
            self._standard_reader_actions.pack(side="right",fill="y")
            self._guide_mode_label.pack_forget()
        self._guided_page_lbl.config(text=f"{self._idx+1} / {self._count}")
        self._guided_zoom_lbl.config(text=f"{self._guide_render_scale*100:.0f}%")
        self._guided_heading.set_text(ui('Voltar ao quadro', 'Return to panel') if self._guide_overview else ui('Se localizar', 'Find your place'))
        if hasattr(self, "_overview_btn"):
            self._overview_btn.pill_set_text(
                (ui('Voltar ao quadro', 'Return to panel') if self._guide_overview
                 else ui('Se localizar', 'Find your place'))
                if self._guided else ui('Encaixar', 'Fit')
            )
        n = self._count
        suffix = f" +1" if (self._double and self._idx + 1 < n) else ""
        self._page_lbl.config(text=f"{self._idx+1}{suffix} / {n}")
        if self._guided and self._regions:
            label = ui('Aprox.','Approx.') if self._guide_fallback else ui('Quadro', 'Panel')
            if self._guide_manual:
                label=ui('Manual','Manual')
            score=f" · {self._guide_result.confidence:.0%}" if self._guide_result and not self._guide_manual else ""
            if self._guide_pending:
                label=ui('Detectando','Detecting')
            self._page_lbl.config(text=f"{self._idx+1}/{n}{score}\n{label} {self._region_index+1}/{len(self._regions)}", width=13, font=("Consolas", 9, "bold"))
        else:
            self._page_lbl.config(width=11)
        self._zoom_lbl.config(text=f"{self._zoom*100:.0f}%")
        if hasattr(self, "_bm_btn") and self._bm_btn.winfo_exists():
            self._bm_btn.pill_set_text(self._bm_label())
            self._bm_btn.pill_set_active(self._idx in get_bookmarks(self._path))
        if hasattr(self, "_guided_btn") and self._guided_btn.winfo_exists():
            self._guided_btn.pill_set_active(self._guided)
        self.update_idletasks()
        self._update_progress_bar()
        if self._thumb_visible and self._thumb_strip:
            self._thumb_strip.highlight(self._idx)
        self._update_done_btn()

    def _bm_label(self):
        return ui("Marcador", "Bookmark")

    def _update_done_btn(self):
        pass
        c = THEME
        on_last = (self._idx >= self._count - 1)
        is_done = get_manual_status(self._path) == "done"
        if on_last:
            if not hasattr(self, "_done_overlay") or not self._done_overlay.winfo_exists():
                self._done_overlay = tk.Frame(self._cv, bg=c["canvas_bg"], highlightthickness=0)
                lbl_txt = ui('Concluído', 'Completed') if is_done else ui('Marcar como concluído', 'Mark as completed')
                fill = c["read_badge"] if is_done else c["accent"]
                fg   = c["read_badge_text"] if is_done else "#ffffff"
                self._done_pill = make_pill(self._done_overlay, lbl_txt,
                                           self._toggle_done_from_reader,
                                           icon_name="check", variant="accent", font=FBTN, pad_x=22, pad_y=11)
                self._done_pill.pack()
                self._done_overlay.place(relx=0.5, rely=0.92, anchor="center")
            else:
                is_done = get_manual_status(self._path) == "done"
                lbl_txt = ui('Concluído', 'Completed') if is_done else ui('Marcar como concluído', 'Mark as completed')
                if hasattr(getattr(self, "_done_pill", None), "pill_set_text"):
                    self._done_pill.pill_set_text(lbl_txt)
        else:
            if hasattr(self, "_done_overlay"):
                try: self._done_overlay.place_forget()
                except Exception as _e: log.debug("silenced: %s", _e)

    def _toggle_done_from_reader(self):
        cur = get_manual_status(self._path)
        set_manual_status(self._path, None if cur == "done" else "done")
        self._update_done_btn()

    def _step(self):
        return 2 if self._double else 1

    def _next(self):
        if self._guided:
            self._guided_move(1)
            return
        nxt = self._idx - self._step() if self._manga else self._idx + self._step()
        if nxt >= self._count or nxt < 0:
            if (not self._manga and self._idx + self._step() >= self._count) or \
               (self._manga and self._idx - self._step() < 0):
                self._maybe_next_chapter()
            return
        self._fade_to(nxt)

    def _prev(self):
        if self._guided:
            self._guided_move(-1)
            return
        prv = self._idx + self._step() if self._manga else self._idx - self._step()
        self._fade_to(prv)

    def _save_guided_position(self):
        if not self._guided or not self._regions:
            return
        position = (self._idx, self._region_index)
        if position != self._guide_written:
            save_progress(self._path, self._idx)
            save_reader_state(self._content_key, guided_page=self._idx, guided_panel=self._region_index)
            self._guide_written = position

    def _toggle_overview(self, event=None):
        if self._fading:
            return "break"
        if self._guided:
            self._guide_overview = not self._guide_overview
            self._show(reset=False)
        else:
            self._fit()
        return "break"

    def _toggle_guided(self, event=None):
        if self._fading:
            return "break"
        self._guided = not self._guided
        self._guide_overview = False
        self._guide_last = False
        if self._guided:
            self._double = False
            if hasattr(self._double_btn, "pill_set_active"):
                self._double_btn.pill_set_active(False)
        save_prefs(reader_guided=self._guided)
        self._show(reset=False)
        return "break"

    def _guided_move(self, direction):
        if self._fading or self._guide_pending:
            return
        target = self._region_index + direction
        if 0 <= target < len(self._regions):
            previous = self._regions[self._region_index]
            if self._guide_motion and self._guide_motion[0] == self._guide_key:
                previous = self._guide_motion[2]
            self._region_index = target
            self._animate_region(previous)
        elif 0 <= self._idx + direction < self._count:
            self._guide_last = direction < 0
            self._fade_to(self._idx + direction)
        elif direction > 0:
            self._maybe_next_chapter()

    def _animate_region(self, previous):
        if self._guide_animation:
            self.after_cancel(self._guide_animation)
            self._guide_animation = None
        self._guide_motion = None
        if not self._animate_guided or self._guide_overview:
            self._show(reset=False)
            return
        key, index = self._guide_key, self._region_index
        target = self._regions[index]
        image = self._compose_pages()
        preview_key = (key, self._brightness, self._cv.winfo_width(), self._cv.winfo_height())
        future = None
        if getattr(self, '_guide_preview_key', None) != preview_key:
            limit = min(2048, max(1024, int(max(preview_key[-2:]) * 1.25)))
            def prepare():
                preview = image.copy()
                preview.thumbnail((limit, limit), Image.Resampling.BILINEAR)
                return preview.convert('RGB')
            future = self._page_executor.submit(prepare)
        started = None
        def frame():
            nonlocal started, future
            self._guide_animation = None
            if not self._guided or not self._animate_guided or self._guide_overview or self._guide_key != key or self._region_index != index:
                self._guide_motion = None
                return
            if future is not None:
                if not future.done():
                    self._guide_animation = self.after(8, frame)
                    return
                try:
                    self._guide_preview = future.result()
                    self._guide_preview_key = preview_key
                except Exception:
                    self._guide_motion = None
                    self._show(reset=False)
                    return
                future = None
            frame_started = time.monotonic()
            if started is None:
                started = frame_started
            progress = min(1., (time.monotonic() - started) / .24)
            eased = progress * progress * (3 - 2 * progress)
            self._guide_motion = (key, index, tuple(a + (b - a) * eased for a, b in zip(previous, target)))
            if progress >= 1:
                self._guide_motion = None
            self._show(reset=False)
            if progress < 1:
                delay = max(1, round(16 - (time.monotonic() - frame_started) * 1000))
                self._guide_animation = self.after(delay, frame)
        frame()

    def _maybe_next_chapter(self):
        if not self._on_finish:
            return
        if messagebox.askyesno(TEXTS[LANG]["next_issue"],
                               TEXTS[LANG]["next_chapter_q"]):
            path,callback=self._path,self._on_finish
            self._close()
            callback(path)

    def _seek_click(self, e):
        pw = self._prog_cv.winfo_width() or 1
        frac = max(0.0, min(1.0, e.x / pw))
        self._fade_to(int(frac * (self._count - 1)))

    def _set_guided_zoom(self,value):
        self._guided_zoom=max(.5,min(4.,float(value)))
        self._guided_slider.set(self._guided_zoom)
        self._show(reset=False)

    def _set_zoom(self, z):
        if self._guided:
            self._set_guided_zoom(self._guided_zoom*(1.15 if z>self._zoom else 1/1.15))
            return
        self._zoom = max(self.ZMIN, min(self.ZMAX, z))
        if hasattr(self, "_slider") and self._slider:
            self._slider.set(self._zoom)
        self._show(reset=False)
    def _zoom_in(self):  self._set_zoom(self._zoom + self.ZSTEP)
    def _zoom_out(self): self._set_zoom(self._zoom - self.ZSTEP)
    def _slider_zoom(self, v):
        if not self._updating_zoom:
            self._set_zoom(float(v))

    def _initial_render(self):
        self._show(reset=False)

    def _reader_preferences(self):
        dialog = tk.Toplevel(self)
        dialog.title(ui('Preferências do leitor', 'Reader preferences'))
        dialog.configure(bg=THEME["bg"])
        dialog.resizable(False, False)
        W, H = 900, 760
        dialog.geometry(f"{W}x{H}+{max(0, self.winfo_rootx() + (self.winfo_width()-W)//2)}+{max(0, self.winfo_rooty() + (self.winfo_height()-H)//2)}")
        dialog.transient(self); grab_when_visible(dialog)
        header=tk.Frame(dialog,bg=THEME["surface"],height=104);header.pack(fill="x");header.pack_propagate(False)
        heading_box = tk.Frame(header, bg=THEME["surface"]); heading_box.pack(side="left", padx=28, pady=17)
        tk.Label(heading_box,text=ui('Preferências do leitor', 'Reader preferences'),font=("Segoe UI", 20, "bold"),
                 bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w")
        tk.Label(heading_box,text=ui('Personalize a leitura e a navegação', 'Customize reading and navigation'),font=FSMALL,
                 bg=THEME["surface"],fg=THEME["text_dim"]).pack(anchor="w", pady=(3,0))
        KomicoveButton(header, ui('Fechar', 'Close'), dialog.destroy, THEME, kind="secondary",
                       compact=True, icon_name="x").pack(side="right", padx=24)
        body=tk.Frame(dialog,bg=THEME["bg"]);body.pack(fill="both",expand=True,padx=24,pady=18)
        persist = self._own_variable(tk.BooleanVar(master=self,value=self._persist_zoom))
        position = self._own_variable(tk.BooleanVar(master=self,value=self._persist_position))
        autofit = self._own_variable(tk.BooleanVar(master=self,value=self._auto_fit))
        guided = self._own_variable(tk.BooleanVar(master=self,value=self._guided))
        animated = self._own_variable(tk.BooleanVar(master=self,value=self._animate_guided))
        manga = self._own_variable(tk.BooleanVar(master=self,value=self._manga))
        double = self._own_variable(tk.BooleanVar(master=self,value=self._double))
        columns = tk.Frame(body, bg=THEME["bg"]); columns.pack(fill="both", expand=True)
        columns.grid_columnconfigure(0, weight=1, uniform="reader-preferences")
        columns.grid_columnconfigure(1, weight=1, uniform="reader-preferences")
        columns.grid_rowconfigure(0, weight=1)
        left = tk.Frame(columns, bg=THEME["bg"]); left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        right = tk.Frame(columns, bg=THEME["bg"]); right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        def section(parent, label, icon_name):
            row = tk.Frame(parent, bg=THEME["bg"]); row.pack(fill="x", pady=(2, 8))
            icon = lucide_icon(icon_name, size=19, state="active", dark=IS_DARK)
            icon_label = tk.Label(row, image=icon, bg=THEME["bg"]); icon_label.image = icon
            icon_label.pack(side="left", padx=(2, 8))
            tk.Label(row, text=label, font=("Segoe UI", 11, "bold"), bg=THEME["bg"],
                     fg=THEME["text"]).pack(side="left")

        def option(parent, var, title, detail, icon_name=None):
            shell = KomicoveCard(parent, THEME, height=78, radius=RADIUS_MEDIUM, padding=10)
            shell.pack(fill="x", pady=5)
            ReaderSwitch(shell.content, var).pack(side="right", padx=(8, 2))
            if icon_name:
                icon = lucide_icon(icon_name, size=28, state="active", dark=IS_DARK)
                badge = tk.Label(shell.content, image=icon, bg=THEME["surface"])
                badge.image = icon
                badge.pack(side="left", padx=(2, 12))
            labels = tk.Frame(shell.content, bg=THEME["surface"]); labels.pack(side="left", fill="both", expand=True)
            tk.Label(labels, text=title, font=FBTN, bg=THEME["surface"], fg=THEME["text"]).pack(anchor="w")
            tk.Label(labels, text=detail, font=("Segoe UI", 8), bg=THEME["surface"],
                     fg=THEME["text_dim"], wraplength=230, justify="left").pack(anchor="w", pady=(3, 0))

        section(left, ui('Visualização', 'Viewing'), "scan")
        option(left, persist, ui('Manter nível de zoom', 'Keep zoom level'),
               ui('Mantém o nível de zoom ao trocar de página.', 'Keeps the zoom level when changing pages.'), 'zoom-in')
        option(left, position, ui('Manter posição', 'Keep position'),
               ui('Mantém a área visualizada ao trocar de página.', 'Keeps the viewed area when changing pages.'), 'focus')
        option(left, autofit, ui('Ajustar página automaticamente', 'Automatically fit page'),
               ui('Redimensiona a página para o melhor enquadramento.', 'Resizes the page for the best fit.'), 'scan')
        option(left, double, ui('Página dupla', 'Double page'),
               ui('Exibe duas páginas lado a lado.', 'Shows two pages side by side.'))
        option(left, manga, ui('Ordem mangá', 'Manga order'),
               ui('Inverte a direção de navegação.', 'Reverses the navigation direction.'))
        section(right, ui('Leitura guiada', 'Guided reading'), "focus")
        option(right, guided, ui('Ativar leitura guiada', 'Enable guided reading'),
               ui('Avança pelos quadros detectados da página.', 'Moves through detected panels on the page.'))
        option(right, animated, ui('Transições suaves', 'Smooth transitions'),
               ui('Anima a passagem entre quadros.', 'Animates movement between panels.'))

        tip = KomicoveCard(right, THEME, height=96, radius=RADIUS_MEDIUM, padding=12)
        tip.pack(fill="x", pady=(12, 0))
        tk.Label(tip.content, text=ui('Atalhos rápidos', 'Quick shortcuts'), font=FBTN,
                 bg=THEME["surface"], fg=THEME["text"]).pack(anchor="w")
        tk.Label(tip.content,
                 text=ui('E: encaixar  |  V: página inteira  |  L: leitura guiada',
                         'E: fit  |  V: full page  |  L: guided reading'),
                 font=FSMALL, bg=THEME["surface"], fg=THEME["text_dim"],
                 wraplength=270, justify="left").pack(anchor="w", pady=(7, 0))
        def apply():
            if self._guide_animation:
                self.after_cancel(self._guide_animation)
                self._guide_animation = None
            self._guide_motion = None
            self._animate_guided = bool(animated.get())
            save_prefs(reader_animate_guided=self._animate_guided)
            self._persist_zoom = bool(persist.get()); self._persist_position = bool(position.get()); self._auto_fit = bool(autofit.get())
            save_prefs(reader_persist_zoom=self._persist_zoom, reader_persist_position=self._persist_position, reader_auto_fit=self._auto_fit)
            self._guided = bool(guided.get())
            save_prefs(reader_guided=self._guided)
            self._manga = bool(manga.get())
            self._double = bool(double.get()) and not self._guided
            save_prefs(manga=self._manga)
            self._guide_overview = False
            if self._guided:
                self._double = False
            dialog.destroy()
            self._show(reset=False)
        footer = tk.Frame(dialog, bg=THEME["surface"]); footer.pack(fill="x", side="bottom")
        KomicoveButton(footer, ui('Salvar preferências', 'Save preferences'), apply, THEME,
                       kind="primary", min_width=210, fixed_height=46,
                       icon_name="check").pack(side="right", padx=24, pady=14)

    def _fit(self):
        cw = self._cv.winfo_width() or 800
        ch = self._cv.winfo_height() or 600
        img = self._compose_pages()
        self._zoom = min(cw / img.width, ch / img.height) * 0.95
        self._offset = [0, 0]
        self._show(reset=False)

    def _drag_start(self, e):
        self._drag = (e.x, e.y); self._cv.config(cursor="fleur")
    def _drag_move(self, e):
        if self._drag:
            dx = e.x - self._drag[0]
            dy = e.y - self._drag[1]
            old_x, old_y = self._offset
            mx, my = getattr(self, '_pan_bounds', (0, 0))
            self._offset = [max(-mx, min(mx, old_x + dx)),
                            max(-my, min(my, old_y + dy))]
            self._drag = (e.x, e.y)
            item = getattr(self, '_canvas_image', None)
            if item is not None:
                self._cv.move(item, self._offset[0] - old_x, self._offset[1] - old_y)
    def _drag_end(self, e):
        self._drag = None; self._cv.config(cursor="crosshair")
        self._show(reset=False)

    def _wheel(self, e):
        d = e.delta / 120 if e.delta else 0
        if e.state & 0x4:
            old_zoom = self._zoom
            new_zoom = max(self.ZMIN, min(self.ZMAX, self._zoom + d * self.ZSTEP))
            if new_zoom != old_zoom:
                cw = self._cv.winfo_width() or 800
                ch = self._cv.winfo_height() or 600
                mx = e.x - cw // 2
                my = e.y - ch // 2
                ratio = new_zoom / old_zoom
                self._offset[0] = mx - (mx - self._offset[0]) * ratio
                self._offset[1] = my - (my - self._offset[1]) * ratio
                self._zoom = new_zoom
                self._show(reset=False)
        else:
            (self._prev if d > 0 else self._next)()

    def _rotate(self):
        self._rotation = (self._rotation + 90) % 360
        self._show(reset=True)

    def _set_brightness(self, val):
        self._brightness = max(0.1, min(3.0, round(val, 2)))
        if hasattr(self, "_bright_var"):
            self._bright_var.set(self._brightness)
        if hasattr(self, "_brightness_slider"):
            self._brightness_slider.set(self._brightness)
        self._show(reset=False)

    def _slider_brightness(self, v):
        self._brightness = float(v)
        self._show(reset=False)

    def _dialog_geometry(self, window, width, height):
        x = max(0, self.winfo_rootx() + (self.winfo_width() - width) // 2)
        y = max(0, self.winfo_rooty() + (self.winfo_height() - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _show_page_picker(self):
        import queue

        c = THEME
        win = tk.Toplevel(self)
        win.title(ui('Selecionar página', 'Select page'))
        win.configure(bg=c["bg"])
        win.minsize(720, 520)
        self._dialog_geometry(win, 980, 700)
        win.transient(self); grab_when_visible(win)
        alive = {"value": True}
        photos = []

        def close():
            alive["value"] = False
            if win.winfo_exists():
                win.destroy()

        header = tk.Frame(win, bg=c["surface"], height=82)
        header.pack(fill="x"); header.pack_propagate(False)
        title_box = tk.Frame(header, bg=c["surface"]); title_box.pack(side="left", padx=28, pady=14)
        tk.Label(title_box, text=ui('Selecionar página', 'Select page'), font=("Segoe UI", 20, "bold"),
                 bg=c["surface"], fg=c["text"]).pack(anchor="w")
        tk.Label(title_box, text=ui(f'{self._count} páginas', f'{self._count} pages'), font=FSMALL,
                 bg=c["surface"], fg=c["text_dim"]).pack(anchor="w", pady=(2, 0))
        KomicoveButton(header, ui('Fechar', 'Close'), close, c, kind="secondary",
                       compact=True, icon_name="x").pack(side="right", padx=24)

        canvas = tk.Canvas(win, bg=c["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        grid = tk.Frame(canvas, bg=c["bg"])
        window_id = canvas.create_window((0, 0), window=grid, anchor="nw")
        grid.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        def go(index):
            self._fade_to(index)
            if win.winfo_exists():
                win.destroy()

        cards = []
        columns = 7
        for i in range(self._count):
            holder = tk.Frame(grid, bg=c["bg"])
            holder.grid(row=i // columns, column=i % columns, padx=9, pady=10, sticky="n")
            card = tk.Canvas(holder, width=112, height=154, bg=c["bg"],
                             highlightthickness=0, cursor="hand2")
            card.pack()
            selected = i == self._idx
            if selected:
                _rrect(card, 0, 0, 112, 154, RADIUS_MEDIUM,
                       fill=c["border_glow"], outline=c["accent2"], width=2)
            _rrect(card, 3, 3, 109, 151, RADIUS_SMALL,
                   fill=c["surface_alt"], outline=c["accent"] if selected else c["border"], width=2 if selected else 1)
            card.create_text(56, 76, text=ui('Carregando', 'Loading'), font=("Segoe UI", 8),
                             fill=c["text_dim"], tags="loading")
            card.bind("<Button-1>", lambda _e, idx=i: go(idx))
            tk.Label(holder, text=ui(f'Página {i+1}', f'Page {i+1}'), font=FSMALL,
                     bg=c["bg"], fg=c["accent2"] if selected else c["text_dim"]).pack(pady=(4, 0))
            cards.append(card)

        pending = queue.Queue()

        def apply_pending():
            if not alive["value"]:
                return
            while True:
                try:
                    index, pil = pending.get_nowait()
                except queue.Empty:
                    break
                target = cards[index]
                try:
                    visible = win.winfo_exists() and target.winfo_exists()
                except tk.TclError:
                    visible = False
                if not visible:
                    continue
                photo = ImageTk.PhotoImage(pil)
                photos.append(photo)
                target.delete("loading")
                target.create_image(56, 77, image=photo)
            if alive["value"]:
                win.after(45, apply_pending)

        def load_thumbnails():
            for index, card in enumerate(cards):
                if not alive["value"]:
                    return
                try:
                    pil = self._loader.get_thumbnail_pil(index, 96, 136).convert("RGB")
                except Exception:
                    continue
                pending.put((index, pil))
        threading.Thread(target=load_thumbnails, daemon=True).start()
        win.after(45, apply_pending)

        win.protocol("WM_DELETE_WINDOW", close)

    def _show_bookmarks(self):
        c = THEME
        win = tk.Toplevel(self)
        win.title(ui('Marcadores', 'Bookmarks'))
        win.configure(bg=c["bg"])
        self._dialog_geometry(win, 620, 560)
        win.transient(self); grab_when_visible(win)

        header = tk.Frame(win, bg=c["surface"], height=86)
        header.pack(fill="x"); header.pack_propagate(False)
        title_box = tk.Frame(header, bg=c["surface"]); title_box.pack(side="left", padx=26, pady=15)
        tk.Label(title_box, text=ui('Marcadores', 'Bookmarks'), font=("Segoe UI", 20, "bold"),
                 bg=c["surface"], fg=c["text"]).pack(anchor="w")
        tk.Label(title_box, text=ui('Acesse rapidamente suas páginas salvas', 'Quickly open your saved pages'),
                 font=FSMALL, bg=c["surface"], fg=c["text_dim"]).pack(anchor="w")
        KomicoveButton(header, ui('Fechar', 'Close'), win.destroy, c, kind="secondary",
                       compact=True, icon_name="x").pack(side="right", padx=22)
        body = tk.Frame(win, bg=c["bg"]); body.pack(fill="both", expand=True, padx=24, pady=20)

        def render():
            for child in body.winfo_children(): child.destroy()
            pages = sorted(get_bookmarks(self._path))
            if not pages:
                icon = lucide_icon("bookmark", size=38, state="active", dark=IS_DARK)
                label = tk.Label(body, image=icon, bg=c["bg"]); label.image = icon
                label.pack(pady=(72, 12))
                tk.Label(body, text=ui('Nenhum marcador ainda', 'No bookmarks yet'),
                         font=("Segoe UI", 16, "bold"), bg=c["bg"], fg=c["text"]).pack()
                tk.Label(body, text=ui('Use o botão Marcador enquanto estiver lendo.',
                                       'Use the Bookmark button while reading.'),
                         font=FSMALL, bg=c["bg"], fg=c["text_dim"]).pack(pady=(6, 0))
                return
            for page in pages:
                card = KomicoveCard(body, c, height=72, radius=RADIUS_MEDIUM, padding=9)
                card.pack(fill="x", pady=5)
                icon = lucide_icon("bookmark-check", size=22, state="active", dark=IS_DARK)
                il = tk.Label(card.content, image=icon, bg=c["surface"]); il.image = icon
                il.pack(side="left", padx=(4, 12))
                labels = tk.Frame(card.content, bg=c["surface"]); labels.pack(side="left", fill="both", expand=True)
                tk.Label(labels, text=ui(f'Página {page+1}', f'Page {page+1}'), font=FBTN,
                         bg=c["surface"], fg=c["text"]).pack(anchor="w")
                tk.Label(labels, text=f'{page+1} / {self._count}', font=FSMALL,
                         bg=c["surface"], fg=c["text_dim"]).pack(anchor="w")
                def remove(p=page):
                    toggle_bookmark(self._path, p); self._hud(); render()
                KomicoveButton(card.content, ui('Remover', 'Remove'), remove, c,
                               kind="secondary", compact=True, icon_name="trash-2").pack(side="right", padx=4)
                def visit(p=page):
                    self._fade_to(p); win.destroy()
                KomicoveButton(card.content, ui('Ir para', 'Go to'), visit, c,
                               kind="primary", compact=True, icon_name="arrow-right").pack(side="right", padx=4)
        render()

    def _show_shortcuts(self):
        c = THEME
        win = tk.Toplevel(self)
        win.title(ui('Atalhos de teclado', 'Keyboard shortcuts'))
        win.configure(bg=c["bg"])
        win.resizable(False, False)
        grab_when_visible(win)
        W, H = 1080, 650
        self._dialog_geometry(win, W, H)
        shell = KomicoveCard(win, c, height=610, radius=RADIUS_LARGE, padding=22)
        shell.pack(fill="both", expand=True, padx=22, pady=20)
        header = tk.Frame(shell.content, bg=c["surface"]); header.pack(fill="x")
        accent = tk.Frame(header, width=5, height=58, bg=c["accent"]); accent.pack(side="left", fill="y", padx=(0, 16))
        accent.pack_propagate(False)
        labels = tk.Frame(header, bg=c["surface"]); labels.pack(side="left", fill="x", expand=True)
        tk.Label(labels, text=ui('Atalhos de teclado', 'Keyboard shortcuts'), font=("Segoe UI", 21, "bold"),
                 bg=c["surface"], fg=c["text"]).pack(anchor="w")
        tk.Label(labels, text=ui('Acesse as principais funções do Komicove com atalhos rápidos.',
                                 'Access the main Komicove features with quick shortcuts.'),
                 font=FSMALL, bg=c["surface"], fg=c["text_dim"]).pack(anchor="w", pady=(3,0))
        KomicoveButton(header, "", win.destroy, c, kind="secondary", compact=True,
                       min_width=46, icon_name="x").pack(side="right")

        categories = [
            (ui('Navegação', 'Navigation'), 'book-open', [
                (ui('Página anterior', 'Previous page'), 'Left'),
                (ui('Próxima página', 'Next page'), 'Right'),
                (ui('Primeira página', 'First page'), 'Home'),
                (ui('Última página', 'Last page'), 'End'),
            ]),
            (ui('Visualização', 'Viewing'), 'search', [
                (ui('Aumentar zoom', 'Zoom in'), '+'),
                (ui('Diminuir zoom', 'Zoom out'), '-'),
                (ui('Zoom no cursor', 'Zoom at pointer'), 'Ctrl + scroll'),
                (ui('Tela cheia', 'Fullscreen'), 'F11'),
            ]),
            (ui('Leitura', 'Reading'), 'scan', [
                (ui('Modo imersivo', 'Immersive mode'), 'I'),
                (ui('Miniaturas', 'Thumbnails'), 'G'),
                (ui('Leitura guiada', 'Guided reading'), 'L'),
                (ui('Adicionar marcador', 'Add bookmark'), 'B'),
            ]),
            (ui('Página', 'Page'), 'rotate-cw', [
                (ui('Girar página', 'Rotate page'), 'R'),
                (ui('Reduzir brilho', 'Decrease brightness'), '['),
                (ui('Aumentar brilho', 'Increase brightness'), ']'),
                (ui('Editar quadros', 'Edit panels'), 'Ctrl + E'),
            ]),
            (ui('Geral', 'General'), 'settings', [
                (ui('Alternar tema', 'Toggle theme'), 'T'),
                (ui('Abrir ajuda', 'Open help'), 'F1'),
                (ui('Abrir preferências', 'Open preferences'), 'Ctrl + ,'),
                (ui('Sair da tela cheia', 'Exit fullscreen'), 'Esc'),
            ]),
        ]
        grid = tk.Frame(shell.content, bg=c["surface"]); grid.pack(fill="both", expand=True, pady=(18, 8))
        for index, (title, icon_name, shortcuts) in enumerate(categories):
            column = index % 3; row_index = index // 3
            card = KomicoveCard(grid, c, height=204, radius=RADIUS_MEDIUM, padding=12)
            card.grid(row=row_index, column=column, sticky="nsew", padx=7, pady=7)
            grid.grid_columnconfigure(column, weight=1, uniform="shortcuts")
            icon = lucide_icon(icon_name, size=22, state="active", dark=IS_DARK)
            head = tk.Frame(card.content, bg=c["surface"]); head.pack(fill="x", pady=(0, 7))
            il = tk.Label(head, image=icon, bg=c["surface"]); il.image = icon; il.pack(side="left", padx=(0, 9))
            tk.Label(head, text=title, font=("Segoe UI", 12, "bold"), bg=c["surface"], fg=c["text"]).pack(side="left")
            for description, key in shortcuts:
                line = tk.Frame(card.content, bg=c["surface"]); line.pack(fill="x", pady=4)
                tk.Label(line, text=description, font=FSMALL, bg=c["surface"], fg=c["text_dim"]).pack(side="left")
                tk.Label(line, text=key, font=(_MONO, 8, "bold"), bg=c["surface_alt"],
                         fg=c["text"], padx=8, pady=3).pack(side="right")
        KomicoveButton(shell.content, ui('Entendi', 'Got it'), win.destroy, c, kind="primary",
                       min_width=220, fixed_height=46, icon_name="check").pack(pady=(4, 0))

    def _toggle_double(self):
        if self._guided:
            messagebox.showinfo(ui('Leitura guiada', 'Guided reading'), ui('Desative a leitura guiada nas Preferências para usar página dupla.', 'Disable guided reading in Preferences to use double-page mode.'))
            return
        self._double = not self._double
        if hasattr(self._double_btn, "pill_set_active"):
            self._double_btn.pill_set_active(self._double)
        self._show(reset=True)

    def _fullscreen(self):
        self._immersive_toggle()

    def _apply_immersive_layout(self):
        if self._immersive:
            for widget in (self._top, self._header_divider, self._bot, self._thumb_frame):
                widget.pack_forget()
        else:
            self._top.pack(fill="x", before=self._cv)
            self._header_divider.pack(fill="x", before=self._cv)
            self._bot.pack(fill="x")
            if self._thumb_visible:
                self._thumb_frame.pack(fill="x", before=self._bot)

    def _immersive_toggle(self):
        self._immersive = not self._immersive
        self.attributes("-fullscreen", self._immersive)
        self._apply_immersive_layout()
        self.after(60, lambda: self._show(reset=False))

    def _escape(self):
        if self.attributes("-fullscreen"):
            if self._immersive: self._immersive_toggle()
            else: self.attributes("-fullscreen", False)

    def _toggle_bookmark(self):
        toggle_bookmark(self._path, self._idx)
        self._hud()

    def _toggle_manga(self, e=None):
        self._manga = not self._manga
        save_prefs(manga=self._manga)
        if hasattr(self, "_manga_btn") and self._manga_btn.winfo_exists():
            self._manga_btn.pill_set_text(ui('Mangá', 'Manga'))
            self._manga_btn.pill_set_active(self._manga)

    def _toggle_theme(self):
        toggle_theme()
        save_prefs(dark=_runtime.IS_DARK)
        idx, zoom, offset = self._idx, self._zoom, self._offset[:]
        brightness = self._brightness
        tv = self._thumb_visible
        self._build()
        self._idx, self._zoom, self._offset = idx, zoom, offset
        self._brightness = brightness
        if hasattr(self, "_bright_var"): self._bright_var.set(brightness)
        if self._slider: self._zvar.set(zoom)
        if tv: self.after(120, self._open_thumbnails)
        self.after(80, lambda: self._show(reset=False))

    def _open_webtoon(self):
        WebtoonViewer(self, self._loader,
                      width=self.winfo_width(), height=self.winfo_height())

    def _toggle_thumbnails(self):
        if self._thumb_visible:
            self._thumb_visible = False
            self._thumb_btn.pill_set_text(ui('Páginas', 'Pages'))
            self._thumb_btn.pill_set_active(False)
            self._thumb_frame.pack_forget()
            for w in self._thumb_frame.winfo_children():
                try: w.destroy()
                except Exception as _e: log.debug("silenced: %s", _e)
            self._thumb_strip = None
        else:
            self._open_thumbnails()

    def _open_thumbnails(self):
        self._thumb_visible = True
        self._thumb_btn.pill_set_text(ui('Páginas', 'Pages'))
        self._thumb_btn.pill_set_active(True)
        for w in self._thumb_frame.winfo_children():
            try: w.destroy()
            except Exception as _e: log.debug("silenced: %s", _e)
        self._thumb_strip = ThumbnailStrip(self._thumb_frame, bg_color=THEME["surface"],
                                           on_click=self._fade_to)
        self._thumb_strip.pack(fill="both", expand=True)
        if not self._immersive and not self._thumb_frame.winfo_ismapped():
            self._thumb_frame.pack(fill="x", before=self._bot)
        threading.Thread(target=self._load_thumbs_bg, daemon=True).start()

    def _load_thumbs_bg(self):
        TW, TH = 60, 84
        for i in range(self._count):
            try:
                pil = self._loader.get_thumbnail_pil(i, TW, TH)
                def add(idx=i, p=pil):
                    if self._thumb_strip and self._thumb_strip.winfo_exists():
                        tk_img = ImageTk.PhotoImage(p)
                        self._thumb_strip.add_thumbnail(tk_img, idx)
                        self._thumb_strip.highlight(self._idx)
                self.after(0, add)
            except Exception:
                pass

    def _close(self):
        if getattr(self,'_closing',False):
            return
        self._closing=True
        self._save_guided_position()
        save_progress(self._path, self._idx)
        save_reader_state(self._content_key, page=self._idx,
                          zoom=self._zoom,
                          offset=self._offset, double=self._double, manga=self._manga)
        record_reading_time(
            self._content_key, time.monotonic()-self._read_started,
            path=self._path, metadata=self._statistics_metadata,
        )
        try: self._loader.close()
        except Exception as _e: log.debug("silenced: %s", _e)
        self.destroy()


class ReaderWindow(ReaderContent,tk.Toplevel):
    """Standalone reader retained for tooling and external hosts."""


class EmbeddedReader(ReaderContent,tk.Frame):
    """Same reader controls, hosted by the existing desktop window."""
    _embedded=True

    def __init__(self,master,path,loader,on_finish=None,on_close=None):
        self._host=master.winfo_toplevel()
        self._return=None
        self._host_bindings={}
        self._scheduled=set()
        self._destroyed=False
        self._previous_title=self._host.title()
        self._previous_fullscreen=self._host.attributes('-fullscreen')
        self._previous_minimum=self._host.minsize()
        super().__init__(master,path,loader,on_finish)
        self._return=on_close
        self._host.title(f'Komicove: {Path(path).stem}')
        self._host.minsize(max(800,self._previous_minimum[0]),max(600,self._previous_minimum[1]))

    def attributes(self,*args):
        return self._host.attributes(*args)

    def bind(self,sequence=None,func=None,add=None):
        if func is None or sequence in ('<Destroy>','<Configure>'):
            return super().bind(sequence,func,add)
        previous=self._host_bindings.pop(sequence,None)
        if previous:
            self._host.unbind(sequence,previous)
        def dispatch(event):
            if not self._destroyed and self.winfo_ismapped():
                func(event)
                return 'break'
        identifier=self._host.bind(sequence,dispatch,add='+')
        self._host_bindings[sequence]=identifier
        return identifier

    def after(self,ms,func=None,*args):
        if self._destroyed:
            return None
        if func is None:
            return tk.Misc.after(self,ms)
        identifier=None
        def invoke():
            self._scheduled.discard(identifier)
            if not self._destroyed:
                func(*args)
        identifier=tk.Misc.after(self,ms,invoke)
        self._scheduled.add(identifier)
        return identifier

    def after_cancel(self,identifier):
        self._scheduled.discard(identifier)
        return tk.Misc.after_cancel(self,identifier)

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed=True
        webtoon=getattr(self,'_webtoon',None)
        if webtoon is not None:
            webtoon.destroy()
        for identifier in list(self._scheduled):
            self.after_cancel(identifier)
        for sequence,identifier in self._host_bindings.items():
            self._host.unbind(sequence,identifier)
        self._host_bindings.clear()
        self._host.attributes('-fullscreen',self._previous_fullscreen)
        self._host.title(self._previous_title)
        self._host.minsize(*self._previous_minimum)
        super().destroy()
        if self._return:
            callback,self._return=self._return,None
            callback()

    def _open_webtoon(self):
        if getattr(self,'_webtoon',None) is not None:
            return
        def back():
            self._webtoon=None
            if not self._destroyed:
                self.pack(fill='both',expand=True)
                self.focus_set()
                self.after(80,lambda:self._show(reset=False))
        self._webtoon=EmbeddedWebtoon(self.master,self._loader,
            width=self.winfo_width(),height=self.winfo_height(),on_close=back)
        self.pack_forget()
        self._webtoon.pack(fill='both',expand=True)


class EmbeddedWebtoon(WebtoonContent,tk.Frame):
    _embedded=True
    after=EmbeddedReader.after
    after_cancel=EmbeddedReader.after_cancel

    def __init__(self,master,loader,width,height,on_close):
        self._scheduled=set();self._destroyed=False
        self._return=on_close
        self._host=master.winfo_toplevel();self._escape_binding=None
        self._previous_fullscreen=self._host.attributes('-fullscreen')
        super().__init__(master,loader,width,height)
        bar=tk.Frame(self,bg=THEME['surface'])
        self._bar=bar
        bar.pack(fill='x',before=self.canvas)
        make_pill(bar,ui('Voltar','Back'),self.destroy,icon_name='arrow-left',
                  variant='accent',font=FBTN,pad_x=22,pad_y=10).pack(side='left',padx=28,pady=13)
        self._host=self.winfo_toplevel()
        self._escape_binding=self._host.bind('<Escape>',lambda _e:(self._escape(),'break')[-1],add='+')
        self._fullscreen_binding=self._host.bind('<F11>',lambda _e:(self._fullscreen(),'break')[-1],add='+')
        self._apply_fullscreen_layout()

    def destroy(self):
        if self._destroyed:return
        self._destroyed=True
        for identifier in list(self._scheduled):self.after_cancel(identifier)
        if self._escape_binding:self._host.unbind('<Escape>',self._escape_binding)
        if self._fullscreen_binding:self._host.unbind('<F11>',self._fullscreen_binding)
        self._host.attributes('-fullscreen',self._previous_fullscreen)
        self.unbind_all('<MouseWheel>')
        super().destroy()
        callback,self._return=self._return,None
        if callback:callback()
