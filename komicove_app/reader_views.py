from komicove_app.runtime import *
import komicove_app.runtime as _runtime
from komicove_app.guided import detect_regions
from komicove_app.panel_editor import PanelEditor
from komicove_app.design.icons import lucide_icon
from komicove_app.design.styles import KomicoveButton, KomicoveCard
from komicove_app.design.spacing import RADIUS_LARGE, RADIUS_MEDIUM, RADIUS_SMALL


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


class WebtoonViewer(tk.Toplevel):
    def __init__(self, parent, loader: SmartPageLoader, width=800, height=900):
        super().__init__(parent)
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


class ReaderWindow(tk.Toplevel):
    ZSTEP = 0.15
    ZMIN  = 0.1
    ZMAX  = 5.0
    Z0    = 0.45

    def __init__(self, master, path, loader: SmartPageLoader, on_finish=None):
        super().__init__(master)
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
        self._slider    = None
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
        self._regions = []
        self._region_index = 0
        self._guide_last = False
        self._guide_overview = False
        self._guide_saved = None
        self._guide_written = None
        self._read_started = time.monotonic()
        self._persist_zoom = bool(prefs.get("reader_persist_zoom", True))
        self._auto_fit = bool(prefs.get("reader_auto_fit", True))
        self._manga = prefs.get("manga", False)
        reader_state = load_reader_state(self._content_key)
        self._guide_saved = (reader_state.get("guided_page", -1), reader_state.get("guided_panel", 0))
        self._has_saved_zoom = "zoom" in reader_state
        self._updating_zoom = False
        self._zoom = float(reader_state.get("zoom", self.Z0))
        self._offset = list(reader_state.get("offset", [0, 0]))
        self._double = bool(reader_state.get("double", False))
        if self._guided:
            self._double = False
        self._manga = bool(reader_state.get("manga", self._manga))

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
        tk.Label(title_box, text=fname, font=("Segoe UI", 14, "bold"),
                 bg=c["surface"], fg=c["text"], anchor="w").pack(anchor="w")
        tk.Label(title_box, text=ui('Leitor', 'Reader'), font=("Segoe UI", 8),
                 bg=c["surface"], fg=c["text_dim"], anchor="w").pack(anchor="w", pady=(1, 0))

        right = tk.Frame(inner, bg=c["surface"])
        right.pack(side="right", fill="y")
        self._mkbtn(right, ui('Tela cheia', 'Fullscreen'), self._fullscreen,
                    icon_name="maximize").pack(side="right", padx=3)
        self._mkbtn(right, "Webtoon", self._open_webtoon, icon_name="columns-2").pack(side="right", padx=3)
        self._overview_btn = self._mkbtn(
            right,
            ui('Página inteira', 'Full page') if self._guided else ui('Encaixar', 'Fit'),
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

        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")

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
        controls = tk.Frame(ib, bg=c["surface"])
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

        self._zvar = tk.DoubleVar(value=self._zoom)
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
        self._bright_var = tk.DoubleVar(value=self._brightness)
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
        pass
        img = self._loader.get_pil(idx)
        if self._rotation:
            img = img.rotate(-self._rotation, expand=True, resample=Image.BICUBIC)
        if abs(self._brightness - 1.0) > 0.01:
            img = ImageEnhance.Brightness(img.convert("RGB")).enhance(self._brightness).convert("RGBA")
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
        img = self._compose_pages()
        iw, ih = img.size
        record_page_read(
            self._content_key, self._idx, self._count,
            path=self._path, metadata=self._statistics_metadata,
        )

        if self._guided:
            key = (self._idx, self._rotation, self._double, self._manga)
            if key != self._guide_key:
                manual=load_manual_panels(self._content_key,self._idx)
                if manual:
                    self._regions=[tuple(r) for r in manual]; self._guide_fallback=False
                else:
                    self._regions, self._guide_fallback = detect_regions(img, self._manga)
                self._region_index = len(self._regions) - 1 if self._guide_last else 0
                if self._guide_saved and self._guide_saved[0] == self._idx and not self._guide_last:
                    self._region_index = max(0, min(int(self._guide_saved[1]), len(self._regions) - 1))
                self._guide_saved = None
                self._guide_last = False
                self._guide_key = key
            rect = self._regions[self._region_index]
            if self._guide_motion and self._guide_motion[:2] == (self._guide_key, self._region_index) and not self._guide_overview:
                rect = self._guide_motion[2]
            left, top, right, bottom = rect
            x, y = int(left * iw), int(top * ih)
            crop = img.copy() if self._guide_overview else img.crop((x, y, max(x + 1, int(right * iw)), max(y + 1, int(bottom * ih))))
            scale = min(max(1, cw - 24) / crop.width, max(1, ch - 24) / crop.height)
            crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
            full = Image.new("RGB", (cw, ch), THEME["canvas_bg"])
            full.paste(crop.convert("RGB"), ((cw - crop.width) // 2, (ch - crop.height) // 2))
            if self._guide_overview:
                ox, oy = (cw - crop.width) // 2, (ch - crop.height) // 2
                ImageDraw.Draw(full).rectangle((ox + left * crop.width, oy + top * crop.height,
                                                ox + right * crop.width, oy + bottom * crop.height),
                                               outline=THEME["accent"], width=3)
            if alpha < 1:
                full = Image.blend(Image.new("RGB", full.size, THEME["canvas_bg"]), full, alpha)
            self._tk_img = ImageTk.PhotoImage(full)
            self._cv.delete("all")
            self._cv.create_image(0, 0, anchor="nw", image=self._tk_img)
            self._hud()
            self._save_guided_position()
            return

        if reset:
            self._zoom = self.Z0
            self._offset = [0, 0]

        nw = max(1, int(iw * self._zoom))
        nh = max(1, int(ih * self._zoom))
        resized = img.resize((nw, nh), Image.BILINEAR)

        bg_rgb = (7, 7, 14) if IS_DARK else (232, 228, 222)
        full = Image.new("RGB", (cw, ch), bg_rgb)
        px = cw // 2 + int(self._offset[0]) - nw // 2
        py = ch // 2 + int(self._offset[1]) - nh // 2
        full.paste(resized.convert("RGB"), (px, py))

        if alpha < 1.0:
            full = Image.blend(Image.new("RGB", (cw, ch), bg_rgb), full, alpha)

        self._tk_img = ImageTk.PhotoImage(full)
        self._cv.delete("all")
        self._cv.create_image(0, 0, anchor="nw", image=self._tk_img)
        self._hud()

    def _fade_to(self, new_idx):
        if self._fading: return
        new_idx = max(0, min(new_idx, self._count - 1))
        if new_idx == self._idx: return
        self._fading = True
        start = time.perf_counter()
        self._loader.get_pil(new_idx)

        def animate():
            elapsed = time.perf_counter() - start
            prog = min(elapsed / FADE_SPEED, 1.0)
            if prog < 0.5:
                self._show(reset=False, alpha=1.0 - ease_out(prog))
            elif prog < 1.0:
                if not hasattr(animate, "swapped"):
                    self._idx = new_idx
                    save_progress(self._path, self._idx)
                    animate.swapped = True
                    self._prefetch_neighbors()
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
        if self._double:
            messagebox.showinfo(ui('Editor de quadros','Panel editor'),
                ui('Desative a página dupla para editar esta página.','Turn off double-page mode to edit this page.'),parent=self)
            return
        image=self._compose_pages()
        automatic,_=detect_regions(image,self._manga)
        current=load_manual_panels(self._content_key,self._idx) or automatic
        def saved(regions):
            save_manual_panels(self._content_key,self._idx,regions)
            self._guide_key=None; self._regions=list(regions); self._region_index=0
            self._show(reset=False)
        PanelEditor(self,image,current,automatic,saved)

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
        if hasattr(self, "_overview_btn"):
            self._overview_btn.pill_set_text(
                (ui('Voltar ao quadro', 'Return to panel') if self._guide_overview
                 else ui('Página inteira', 'Full page'))
                if self._guided else ui('Encaixar', 'Fit')
            )
        n = self._count
        suffix = f" +1" if (self._double and self._idx + 1 < n) else ""
        self._page_lbl.config(text=f"{self._idx+1}{suffix} / {n}")
        if self._guided and self._regions:
            label = "Trecho" if self._guide_fallback else ui('Quadro', 'Panel')
            self._page_lbl.config(text=f"{self._idx+1}/{n}\n{label} {self._region_index+1}/{len(self._regions)}", width=13, font=("Consolas", 10, "bold"))
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
        if self._fading:
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
        started = time.monotonic()
        def frame():
            self._guide_animation = None
            if not self._guided or not self._animate_guided or self._guide_overview or self._guide_key != key or self._region_index != index:
                self._guide_motion = None
                return
            progress = min(1., (time.monotonic() - started) / .24)
            eased = progress * progress * (3 - 2 * progress)
            self._guide_motion = (key, index, tuple(a + (b - a) * eased for a, b in zip(previous, target)))
            if progress >= 1:
                self._guide_motion = None
            self._show(reset=False)
            if progress < 1:
                self._guide_animation = self.after(20, frame)
        frame()

    def _maybe_next_chapter(self):
        if not self._on_finish:
            return
        if messagebox.askyesno(TEXTS[LANG]["next_issue"],
                               TEXTS[LANG]["next_chapter_q"]):
            self._on_finish(self._path)
            self.destroy()

    def _seek_click(self, e):
        pw = self._prog_cv.winfo_width() or 1
        frac = max(0.0, min(1.0, e.x / pw))
        self._fade_to(int(frac * (self._count - 1)))

    def _set_zoom(self, z):
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
        if self._auto_fit and not self._has_saved_zoom:
            self._fit()
        else:
            self._show(reset=False)

    def _reader_preferences(self):
        dialog = tk.Toplevel(self)
        dialog.title(ui('Preferências do leitor', 'Reader preferences'))
        dialog.configure(bg=THEME["bg"])
        dialog.resizable(False, False)
        W, H = 720, 650
        dialog.geometry(f"{W}x{H}+{max(0, self.winfo_rootx() + (self.winfo_width()-W)//2)}+{max(0, self.winfo_rooty() + (self.winfo_height()-H)//2)}")
        dialog.transient(self); grab_when_visible(dialog)
        header=tk.Frame(dialog,bg=THEME["surface"],height=88);header.pack(fill="x");header.pack_propagate(False)
        heading_box = tk.Frame(header, bg=THEME["surface"]); heading_box.pack(side="left", padx=28, pady=17)
        tk.Label(heading_box,text=ui('Preferências do leitor', 'Reader preferences'),font=("Segoe UI", 20, "bold"),
                 bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w")
        tk.Label(heading_box,text=ui('Personalize a leitura e a navegação', 'Customize reading and navigation'),font=FSMALL,
                 bg=THEME["surface"],fg=THEME["text_dim"]).pack(anchor="w", pady=(3,0))
        KomicoveButton(header, ui('Fechar', 'Close'), dialog.destroy, THEME, kind="secondary",
                       compact=True, icon_name="x").pack(side="right", padx=24)
        body=tk.Frame(dialog,bg=THEME["bg"]);body.pack(fill="both",expand=True,padx=24,pady=18)
        persist = tk.BooleanVar(value=self._persist_zoom)
        autofit = tk.BooleanVar(value=self._auto_fit)
        guided = tk.BooleanVar(value=self._guided)
        animated = tk.BooleanVar(value=self._animate_guided)
        manga = tk.BooleanVar(value=self._manga)
        double = tk.BooleanVar(value=self._double)
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

        def option(parent, var, title, detail):
            shell = KomicoveCard(parent, THEME, height=78, radius=RADIUS_MEDIUM, padding=10)
            shell.pack(fill="x", pady=5)
            ReaderSwitch(shell.content, var).pack(side="right", padx=(8, 2))
            labels = tk.Frame(shell.content, bg=THEME["surface"]); labels.pack(side="left", fill="both", expand=True)
            tk.Label(labels, text=title, font=FBTN, bg=THEME["surface"], fg=THEME["text"]).pack(anchor="w")
            tk.Label(labels, text=detail, font=("Segoe UI", 8), bg=THEME["surface"],
                     fg=THEME["text_dim"], wraplength=230, justify="left").pack(anchor="w", pady=(3, 0))

        section(left, ui('Visualização', 'Viewing'), "scan")
        option(left, autofit, ui('Encaixe automático', 'Automatic fit'),
               ui('Ajusta cada página à área disponível.', 'Fits every page to the available area.'))
        option(left, persist, ui('Persistir zoom e posição', 'Keep zoom and position'),
               ui('Mantém o enquadramento ao trocar de página.', 'Keeps framing while changing pages.'))
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
            self._persist_zoom = bool(persist.get()); self._auto_fit = bool(autofit.get())
            save_prefs(reader_persist_zoom=self._persist_zoom, reader_auto_fit=self._auto_fit)
            self._guided = bool(guided.get())
            save_prefs(reader_guided=self._guided)
            self._manga = bool(manga.get())
            self._double = bool(double.get()) and not self._guided
            save_prefs(manga=self._manga)
            self._guide_overview = False
            if self._guided:
                self._double = False
            if not self._persist_zoom:
                self._zoom = self.Z0; self._offset = [0, 0]; self._show(reset=False)
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
            self._offset[0] += dx
            self._offset[1] += dy
            self._drag = (e.x, e.y)
            self._cv.move("all", dx, dy)
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
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    def _immersive_toggle(self):
        self._immersive = not self._immersive
        if self._immersive:
            self._top.pack_forget()
            self._bot.pack_forget()
            self.attributes("-fullscreen", True)
        else:
            self.attributes("-fullscreen", False)
            self._top.pack(fill="x", before=self._cv)
            self._bot.pack(fill="x")
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
        if not self._thumb_frame.winfo_ismapped():
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
        self._save_guided_position()
        save_progress(self._path, self._idx)
        save_reader_state(self._content_key, page=self._idx,
                          zoom=self._zoom if self._persist_zoom else self.Z0,
                          offset=self._offset, double=self._double, manga=self._manga)
        record_reading_time(
            self._content_key, time.monotonic()-self._read_started,
            path=self._path, metadata=self._statistics_metadata,
        )
        try: self._loader.close()
        except Exception as _e: log.debug("silenced: %s", _e)
        self.destroy()
