from panel_app.runtime import *
import panel_app.runtime as _runtime

class LangWindow(tk.Toplevel):
    def __init__(self, master, cb):
        super().__init__(master)
        try: self.iconbitmap(resource_path("panel.ico"))
        except Exception as _e: log.debug("silenced: %s", _e)
        self.cb = cb
        self.title("Idioma / Language")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.grab_set()
        W, H = 340, 232
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        tk.Canvas(self, width=W, height=3, bg=THEME["accent"], highlightthickness=0).place(x=0, y=0)
        tk.Label(self, text="◈ PANEL", font=FLOGO, bg=THEME["bg"], fg=THEME["text"]).pack(pady=(24, 2))
        tk.Label(self, text="Idioma / Language", font=FSMALL, bg=THEME["bg"], fg=THEME["text_dim"]).pack(pady=(0, 16))
        for flag, txt, lang in [("🇧🇷", "Português", "pt"), ("🇺🇸", "English", "en")]:
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
        self.title("PANEL - Modo Webtoon")
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
        try: self.iconbitmap(resource_path("panel.ico"))
        except Exception as _e: log.debug("silenced: %s", _e)
        self.title(f"PANEL — {Path(path).stem}")
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

        prefs = load_prefs()
        self._persist_zoom = bool(prefs.get("reader_persist_zoom", True))
        self._auto_fit = bool(prefs.get("reader_auto_fit", True))
        self._manga = prefs.get("manga", False)
        reader_state = load_reader_state(self._content_key)
        self._has_saved_zoom = "zoom" in reader_state
        self._updating_zoom = False
        self._zoom = float(reader_state.get("zoom", self.Z0))
        self._offset = list(reader_state.get("offset", [0, 0]))
        self._double = bool(reader_state.get("double", False))
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

        self._top = tk.Frame(self, bg=c["surface"], height=58)
        self._top.pack(fill="x")
        self._top.pack_propagate(False)
        inner = tk.Frame(self._top, bg=c["surface"])
        inner.pack(fill="both", expand=True, padx=16, pady=9)

        left = tk.Frame(inner, bg=c["surface"])
        left.pack(side="left", fill="y")
        self._mkbtn(left, f"◀  {TEXTS[LANG]['back']}", self._close, accent=True).pack(side="left", padx=(0, 14))

        title_box = tk.Frame(left, bg=c["surface"])
        title_box.pack(side="left", fill="y")
        fname = Path(self._path).stem
        if len(fname) > 48: fname = fname[:45] + "…"
        tk.Label(title_box, text=fname, font=("Segoe UI", 11, "bold"),
                 bg=c["surface"], fg=c["text"], anchor="w").pack(anchor="w")

        right = tk.Frame(inner, bg=c["surface"])
        right.pack(side="right", fill="y")
        self._mkbtn(right, "⛶", self._immersive_toggle).pack(side="right", padx=3)
        self._mkbtn(right, TEXTS[LANG]["fullscreen"], self._fullscreen).pack(side="right", padx=3)
        self._mkbtn(right, "📜  Webtoon", self._open_webtoon).pack(side="right", padx=3)
        self._mkbtn(right, TEXTS[LANG]["fit"], self._fit).pack(side="right", padx=3)
        self._mkbtn(right, "⚙  Preferências", self._reader_preferences).pack(side="right", padx=3)
        self._mkbtn(right, current_theme_label(), self._toggle_theme, icon=ICONS.get("theme")).pack(side="right", padx=3)

        self._bm_btn = self._pill(right, self._bm_label(), self._toggle_bookmark, variant="soft")
        self._bm_btn.pack(side="right", padx=3)

        txt = TEXTS[LANG]["manga_on"] if self._manga else TEXTS[LANG]["manga_off"]
        self._manga_btn = self._pill(right, txt, self._toggle_manga, variant="soft")
        self._manga_btn.pill_set_active(self._manga)
        self._manga_btn.pack(side="right", padx=(3, 10))

        tk.Frame(self, bg=c["accent"], height=2).pack(fill="x")

        self._cv = tk.Canvas(self, bg=c["canvas_bg"], highlightthickness=0, cursor="crosshair")
        self._cv.pack(fill="both", expand=True)

        self._bot = tk.Frame(self, bg=c["surface"], height=66)
        self._bot.pack(fill="x")
        self._bot.pack_propagate(False)
        self._prog_cv = tk.Canvas(self._bot, height=6, bg=c["progress_bg"], highlightthickness=0)
        self._prog_cv.pack(fill="x")
        self._prog_cv.bind("<Button-1>", self._seek_click)
        ib = tk.Frame(self._bot, bg=c["surface"])
        ib.pack(fill="both", expand=True, padx=16, pady=8)

        nf = tk.Frame(ib, bg=c["surface"]); nf.pack(side="left")
        self._nav_btn(nf, "‹" if not ICONS.get("prev") else "", self._prev,
                      icon=ICONS.get("prev")).pack(side="left", padx=(0, 8))
        self._page_lbl = tk.Label(nf, text="", font=("Consolas", 12, "bold"),
                                  bg=c["surface_alt"], fg=c["text"], width=11, padx=10, pady=6)
        self._page_lbl.pack(side="left", padx=2)
        self._nav_btn(nf, "›" if not ICONS.get("next") else "", self._next,
                      icon=ICONS.get("next")).pack(side="left", padx=(8, 0))

        zf = tk.Frame(ib, bg=c["surface"]); zf.pack(side="left", padx=18)
        self._nav_btn(zf, "−" if not ICONS.get("zoom_out") else "", self._zoom_out,
                      icon=ICONS.get("zoom_out")).pack(side="left", padx=3)
        self._zoom_lbl = tk.Label(zf, text="45%", font=("Segoe UI", 9, "bold"),
                                  bg=c["surface"], fg=c["text_dim"], width=5)
        self._zoom_lbl.pack(side="left", padx=4)
        self._nav_btn(zf, "+" if not ICONS.get("zoom_in") else "", self._zoom_in,
                      icon=ICONS.get("zoom_in")).pack(side="left", padx=3)

        self._zvar = tk.DoubleVar(value=self._zoom)
        sl = tk.Scale(ib, from_=self.ZMIN, to=self.ZMAX, resolution=0.05,
                      orient="horizontal", variable=self._zvar, command=self._slider_zoom,
                      bg=c["surface"], fg=c["text_dim"], troughcolor=c["progress_bg"],
                      activebackground=c["accent2"], highlightthickness=0,
                      sliderrelief="flat", length=130, showvalue=False, bd=0)
        sl.pack(side="left", padx=(8, 0))
        self._slider = sl

        self._thumb_btn = self._pill(ib, "⊟  Miniaturas", self._toggle_thumbnails, variant="soft")
        self._thumb_btn.pack(side="right", padx=6)
        self._double_btn = self._pill(ib, "▭▭ Dupla", self._toggle_double, variant="soft")
        self._double_btn.pack(side="right", padx=3)
        self._nav_btn(ib, "↻", self._rotate).pack(side="right", padx=3)
        self._nav_btn(ib, "?", self._show_shortcuts).pack(side="right", padx=3)

        bf = tk.Frame(ib, bg=c["surface"]); bf.pack(side="right", padx=(0, 8))
        tk.Label(bf, text="☀", font=(_SANS, 9), bg=c["surface"], fg=c["text_dim"]).pack(side="left", padx=(0, 2))
        self._bright_var = tk.DoubleVar(value=self._brightness)
        bright_sl = tk.Scale(bf, from_=0.3, to=2.0, resolution=0.05,
                             orient="horizontal", variable=self._bright_var,
                             command=self._slider_brightness,
                             bg=c["surface"], fg=c["text_dim"], troughcolor=c["progress_bg"],
                             activebackground=c["accent2"], highlightthickness=0,
                             sliderrelief="flat", length=90, showvalue=False, bd=0)
        bright_sl.pack(side="left")

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
        self.bind("<b>",      lambda e: self._toggle_bookmark())
        self.bind("<r>",      lambda e: self._rotate())
        self.bind("<question>", lambda e: self._show_shortcuts())
        self.bind("<bracketleft>",  lambda e: self._set_brightness(self._brightness - 0.1))
        self.bind("<bracketright>", lambda e: self._set_brightness(self._brightness + 0.1))

    def _pill(self, parent, text, cmd, *, icon=None, variant="ghost",
              font=FSMALL, pad_x=14, pad_y=8, min_w=0):
        return make_pill(parent, text, cmd, icon=icon, variant=variant,
                         font=font, pad_x=pad_x, pad_y=pad_y, min_w=min_w)

    def _mkbtn(self, parent, text, cmd, accent=False, icon=None):
        return self._pill(parent, text, cmd, icon=icon,
                          variant="accent" if accent else "ghost")

    def _nav_btn(self, parent, text, cmd, icon=None):
        c = THEME
        host_bg = parent.cget("bg")
        size, r = 40, 12
        cv = tk.Canvas(parent, width=size, height=size, bg=host_bg,
                       highlightthickness=0, cursor="hand2", takefocus=0)
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
        n = self._count
        suffix = f" +1" if (self._double and self._idx + 1 < n) else ""
        self._page_lbl.config(text=f"{self._idx+1}{suffix} / {n}")
        self._zoom_lbl.config(text=f"{self._zoom*100:.0f}%")
        if hasattr(self, "_bm_btn") and self._bm_btn.winfo_exists():
            self._bm_btn.pill_set_text(self._bm_label())
            self._bm_btn.pill_set_active(self._idx in get_bookmarks(self._path))
        self.update_idletasks()
        self._update_progress_bar()
        if self._thumb_visible and self._thumb_strip:
            self._thumb_strip.highlight(self._idx)
        self._update_done_btn()

    def _bm_label(self):
        return "★" if self._idx in get_bookmarks(self._path) else "☆"

    def _update_done_btn(self):
        pass
        c = THEME
        on_last = (self._idx >= self._count - 1)
        is_done = get_manual_status(self._path) == "done"
        if on_last:
            if not hasattr(self, "_done_overlay") or not self._done_overlay.winfo_exists():
                self._done_overlay = tk.Frame(self._cv, bg=c["canvas_bg"], highlightthickness=0)
                lbl_txt = "✓  Concluído!" if is_done else "✓  Marcar como Concluído"
                fill = c["read_badge"] if is_done else c["accent"]
                fg   = c["read_badge_text"] if is_done else "#ffffff"
                self._done_pill = make_pill(self._done_overlay, lbl_txt,
                                           self._toggle_done_from_reader,
                                           variant="accent", font=FBTN, pad_x=22, pad_y=11)
                self._done_pill.pack()
                self._done_overlay.place(relx=0.5, rely=0.92, anchor="center")
            else:
                is_done = get_manual_status(self._path) == "done"
                lbl_txt = "✓  Concluído!" if is_done else "✓  Marcar como Concluído"
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
        nxt = self._idx - self._step() if self._manga else self._idx + self._step()
        if nxt >= self._count or nxt < 0:
            if (not self._manga and self._idx + self._step() >= self._count) or \
               (self._manga and self._idx - self._step() < 0):
                self._maybe_next_chapter()
            return
        self._fade_to(nxt)

    def _prev(self):
        prv = self._idx + self._step() if self._manga else self._idx - self._step()
        self._fade_to(prv)

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
        dialog.title("Preferências do leitor")
        dialog.configure(bg=THEME["bg"])
        dialog.resizable(False, False)
        dialog.geometry("520x360")
        dialog.transient(self); dialog.grab_set()
        header=tk.Frame(dialog,bg=THEME["surface"],height=72);header.pack(fill="x");header.pack_propagate(False)
        tk.Label(header,text="⚙  Preferências do leitor",font=FTITLE,
                 bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w",padx=24,pady=(18,0))
        tk.Label(header,text="Personalize como cada página será aberta",font=FSMALL,
                 bg=THEME["surface"],fg=THEME["text_dim"]).pack(anchor="w",padx=26)
        body=tk.Frame(dialog,bg=THEME["bg"]);body.pack(fill="both",expand=True,padx=20,pady=16)
        persist = tk.BooleanVar(value=self._persist_zoom)
        autofit = tk.BooleanVar(value=self._auto_fit)
        for var, title, detail in ((persist, "Persistir zoom e deslocamento", "Mantém escala e posição ao trocar de página."),
                                   (autofit, "Ajustar à tela automaticamente", "Abre cada HQ no melhor encaixe disponível.")):
            card=tk.Frame(body,bg=THEME["surface_alt"],highlightthickness=1,highlightbackground=THEME["border"])
            card.pack(fill="x",pady=5)
            check=tk.Checkbutton(card,text=title,variable=var,anchor="w",font=FBTN,
                bg=THEME["surface_alt"],fg=THEME["text"],selectcolor=THEME["accent"],
                activebackground=THEME["surface_alt"],activeforeground=THEME["text"],
                highlightthickness=0,bd=0)
            check.pack(fill="x",padx=12,pady=(9,0))
            tk.Label(card,text=detail,font=FSMALL,bg=THEME["surface_alt"],fg=THEME["text_dim"]).pack(anchor="w",padx=40,pady=(0,9))
        tk.Label(body,text="Atalho rápido: pressione E para encaixar a página na tela.",font=FSMALL,
                 bg=THEME["bg"],fg=THEME["text_dim"]).pack(anchor="w",pady=(8,0))
        def apply():
            self._persist_zoom = bool(persist.get()); self._auto_fit = bool(autofit.get())
            save_prefs(reader_persist_zoom=self._persist_zoom, reader_auto_fit=self._auto_fit)
            if not self._persist_zoom:
                self._zoom = self.Z0; self._offset = [0, 0]; self._show(reset=False)
            dialog.destroy()
        self._pill(dialog, "Salvar preferências", apply, variant="accent", font=FBTN,
                   pad_x=24, pad_y=10).pack(pady=(4, 18))

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
        self._show(reset=False)

    def _slider_brightness(self, v):
        self._brightness = float(v)
        self._show(reset=False)

    def _show_shortcuts(self):
        c = THEME
        win = tk.Toplevel(self)
        win.title("Atalhos de teclado")
        win.configure(bg=c["surface"])
        win.resizable(False, False)
        win.grab_set()
        W, H = 360, 380
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        tk.Canvas(win, width=W, height=3, bg=c["accent"], highlightthickness=0).place(x=0, y=0)
        tk.Label(win, text="Atalhos de Teclado", font=FBTN, bg=c["surface"],
                 fg=c["text"], pady=14).pack()
        tk.Frame(win, bg=c["border"], height=1).pack(fill="x", padx=16, pady=(0, 8))
        shortcuts = [
            ("← / →", "Página anterior / próxima"),
            ("+ / -", "Zoom in / out"),
            ("Ctrl + scroll", "Zoom no cursor"),
            ("F / F11", "Tela cheia"),
            ("I", "Modo imersivo"),
            ("R", "Girar página"),
            ("B", "Marcar bookmark"),
            ("G", "Mostrar miniaturas"),
            ("T", "Alternar tema"),
            ("[ / ]", "Reduzir / aumentar brilho"),
            ("?", "Esta janela"),
            ("Esc", "Sair da tela cheia"),
        ]
        frame = tk.Frame(win, bg=c["surface"]); frame.pack(padx=24, pady=4, fill="x")
        for key, desc in shortcuts:
            row = tk.Frame(frame, bg=c["surface"]); row.pack(fill="x", pady=3)
            tk.Label(row, text=key, font=(_MONO, 9, "bold"), bg=c["surface_alt"],
                     fg=c["accent"], padx=8, pady=3, relief="flat").pack(side="left")
            tk.Label(row, text=desc, font=FSMALL, bg=c["surface"],
                     fg=c["text_dim"], anchor="w").pack(side="left", padx=10)
        make_pill(win, "Fechar", win.destroy, variant="soft", font=FBTN,
                  pad_x=24, pad_y=10).pack(pady=14)

    def _toggle_double(self):
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
        txt = TEXTS[LANG]["manga_on"] if self._manga else TEXTS[LANG]["manga_off"]
        if hasattr(self, "_manga_btn") and self._manga_btn.winfo_exists():
            self._manga_btn.pill_set_text(txt)
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
            self._thumb_btn.pill_set_text("⊟  Miniaturas")
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
        self._thumb_btn.pill_set_text("⊠  Miniaturas")
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
        save_progress(self._path, self._idx)
        save_reader_state(self._content_key, page=self._idx,
                          zoom=self._zoom if self._persist_zoom else self.Z0,
                          offset=self._offset, double=self._double, manga=self._manga)
        try: self._loader.close()
        except Exception as _e: log.debug("silenced: %s", _e)
        self.destroy()
