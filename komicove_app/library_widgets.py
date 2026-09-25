from komicove_app.runtime import *
from komicove_app.publishing_views import PublishDialog
from komicove_app import book_metadata

class ComicCard:
    HOVER_STEPS = 10
    HOVER_MS    = 14
    SCALE_MAX   = 1.12

    def __init__(self, parent, path, img_pil, open_cb, root, label_override=None):
        self._path    = path
        self._open_cb = open_cb
        self._root    = root
        self._alpha   = 0.0
        self._anim_id = None
        self._img_pil = img_pil
        self._tk_img  = None

        c    = THEME
        nome = label_override if label_override else Path(path).stem
        if len(nome) > 22: nome = nome[:20] + "…"
        self._nome = nome

        self._cw = CAPA_W + 40
        self._ch = CAPA_H + 40

        self.frame = tk.Frame(parent, bg=c["bg"])
        self.cv = tk.Canvas(self.frame, width=self._cw, height=self._ch,
                            bg=c["bg"], highlightthickness=0)
        self.cv.pack()
        self.lbl = tk.Label(self.frame, text=nome, font=FSMALL,
                            bg=c["bg"], fg=c["text_dim"], wraplength=self._cw)
        self.lbl.pack(pady=(0, 3))

        self._draw(0.0)
        for w in (self.cv, self.lbl):
            w.bind("<Enter>",           self._on_enter)
            w.bind("<Leave>",           self._on_leave)
            w.bind("<Double-Button-1>", lambda e: self._open_cb(self._path))
            w.bind("<Button-1>",        lambda e: self._open_cb(self._path))
            w.bind("<Button-3>",        self._show_context_menu)

    def set_image(self, pil_image):
        self._img_pil = pil_image
        self._draw(self._alpha)

    def _draw(self, alpha: float):
        c  = THEME
        cw, ch = self._cw, self._ch
        cv = self.cv
        cv.delete("all")
        scale  = 1.0 + (self.SCALE_MAX - 1.0) * ease_out(alpha)
        iw, ih = int(CAPA_W * scale), int(CAPA_H * scale)
        px, py = (cw - iw) // 2, (ch - ih) // 2

        s_off = int(4 + alpha * 4)
        s_color = c["border_glow"] if alpha > 0.4 else c["shadow"]
        _rrect(cv, px + s_off, py + s_off, px + iw + s_off - 1, py + ih + s_off - 1, 20, fill=s_color)

        img_to_draw = self._img_pil if self._img_pil is not None else get_placeholder_pil()
        if img_to_draw:
            resized = img_to_draw.resize((iw, ih), Image.BILINEAR)
            if alpha > 0.01:
                overlay = Image.new("RGBA", (iw, ih), (0, 0, 0, int(120 * alpha)))
                resized = Image.alpha_composite(resized.convert("RGBA"), overlay).convert("RGB")
            mask = Image.new("L", (iw, ih), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, iw - 1, ih - 1], radius=CARD_R, fill=255)
            result = Image.new("RGB", (iw, ih),
                               tuple(int(c["surface_alt"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4)))
            result.paste(resized, mask=mask)
            self._tk_img = ImageTk.PhotoImage(result)
            cv.create_image(px, py, anchor="nw", image=self._tk_img)
            if self._img_pil is None:
                cv.create_rectangle(px, py, px+iw, py+ih, fill="", outline=c["border"], width=1)
                cv.create_text(cw//2, ch//2, text="…", font=FSMALL, fill=c["text_muted"])
            if alpha > 0.3 and self._img_pil is not None:
                a_int = int(255 * min(1.0, (alpha - 0.3) / 0.7))
                mx, my = cw // 2, ch // 2 - 10
                cv.create_text(mx, my - 4, text="▶",
                               font=("Segoe UI Symbol", int(22 * scale)),
                               fill=f"#{a_int:02x}{a_int:02x}{a_int:02x}")
                cv.create_text(mx, my + 26, text=self._nome,
                               font=("Segoe UI", 8, "bold"),
                               fill=f"#{a_int:02x}{a_int:02x}{a_int:02x}", width=iw - 16)
        border_col = c["accent2"] if alpha > 0.4 else c["border"]
        bw = 2 if alpha > 0.4 else 1
        _rrect(cv, px, py, px + iw - 1, py + ih - 1, CARD_R, outline=border_col, width=bw)

        status = get_manual_status(self._path)
        if status == "done":
            cv.create_oval(px+4, py+4, px+18, py+18, fill=c["read_badge"], outline="")
            cv.create_text(px+11, py+11, text="✓", font=(_SANS, 7, "bold"), fill=c["read_badge_text"], anchor="center")
        elif status == "reading":
            cv.create_oval(px+4, py+4, px+18, py+18, fill="#1e3a5c", outline="")
            cv.create_text(px+11, py+11, text="▶", font=(_SANS, 6, "bold"), fill="#5aabff", anchor="center")
        if is_favorite(self._path):
            fav_icon = ICONS.get("favorited")
            if fav_icon:
                cv.create_image(px + iw - 14, py + 12, image=fav_icon, anchor="center")
            else:
                cv.create_text(px + iw - 12, py + 12, text="★", font=(_SANS, 11, "bold"),
                               fill="#f5c842", anchor="center")

    def _show_context_menu(self, event):
        path = self._path
        c = THEME
        menu = tk.Menu(self._root, tearoff=0,
                       bg=c["surface"], fg=c["text"],
                       activebackground=c["accent"], activeforeground="#ffffff",
                       relief="flat", borderwidth=1,
                       font=FSMALL)

        fav_label = ui('★  Desfavoritar', '★  Remove favorite') if is_favorite(path) else ui('☆  Favoritar', '☆  Add to favorites')
        def toggle_fav():
            toggle_favorite(path)
            self._draw(self._alpha)
        menu.add_command(label=fav_label, command=toggle_fav)
        menu.add_separator()

        cur = get_manual_status(path)

        def set_reading():
            if cur == "reading":
                set_manual_status(path, None)
            else:
                set_manual_status(path, "reading")
            self._draw(self._alpha)
        reading_label = "▶  Lendo  ✓" if cur == "reading" else "▶  Marcar como Lendo"
        menu.add_command(label=reading_label, command=set_reading)

        def set_done():
            if cur == "done":
                set_manual_status(path, None)
            else:
                set_manual_status(path, "done")
            self._draw(self._alpha)
        done_label = ui('✓  Concluído  ✓', '✓  Completed  ✓') if cur == "done" else ui('✓  Marcar como Concluído', '✓  Mark as Completed')
        menu.add_command(label=done_label, command=set_done)

        menu.add_separator()
        menu.add_command(label=ui('▶  Abrir', '▶  Open'), command=lambda: self._open_cb(path))
        menu.add_command(label=ui('Editar informações', 'Edit information'), command=lambda: book_metadata.edit(self._root, path, get_comic_info(path), self._root._refresh_library))

        menu.add_separator()
        menu.add_command(label=ui('📤  Publicar na comunidade', '📤  Publish to community'), command=lambda: self._publish())

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _publish(self):
        user = getattr(self._root, "current_user", None)
        if not _ACCOUNTS_AVAILABLE or user is None:
            messagebox.showinfo(
                ui('Conta necessária', 'Account required'),
                ui(
                    "Crie uma conta ou entre com uma existente para publicar na comunidade.\n\nUse \"Sair\" na barra lateral se quiser trocar de conta, ou reabra o app e escolha \"Entrar\"/\"Cadastrar\" em vez de convidado.",
                    "Create an account or sign in to publish to the community.\n\nUse \"Sign out\" in the sidebar to switch accounts, or reopen the app and choose \"Sign in\"/\"Sign up\" instead of guest mode.",
                ),
            )
            return
        PublishDialog(self._root, self._path, user)

    def _animate(self, target: float):
        if self._anim_id:
            self._root.after_cancel(self._anim_id); self._anim_id = None
        step = (1.0 / self.HOVER_STEPS) * (1 if target > self._alpha else -1)
        def tick():
            self._alpha += step
            if (step > 0 and self._alpha >= target) or (step < 0 and self._alpha <= target):
                self._alpha = target
                self._draw(self._alpha)
                self.lbl.config(fg=THEME["text"] if target > 0.5 else THEME["text_dim"],
                                font=("Segoe UI", 9, "bold") if target > 0.5 else FSMALL)
                return
            self._draw(self._alpha)
            self._anim_id = self._root.after(self.HOVER_MS, tick)
        tick()

    def _on_enter(self, e): self._animate(1.0)
    def _on_leave(self, e): self._animate(0.0)
    def grid(self, **kwargs): self.frame.grid(**kwargs)


class CollectionCard:
    HOVER_STEPS = 10
    HOVER_MS    = 14
    SCALE_MAX   = 1.08

    def __init__(self, parent, collection: dict, open_cb, detail_cb, rename_cb, root):
        self._collection = collection
        self._open_cb = open_cb
        self._detail_cb = detail_cb
        self._rename_cb = rename_cb
        self._root = root
        self._alpha = 0.0
        self._anim_id = None
        self._tk_imgs = []

        c = THEME
        files = collection["files"]
        name = collection["name"]
        if len(name) > 22: name = name[:20] + "…"
        self._name = name
        self._files = files

        lidas, total, ultima = collection_read_count(files)
        self._lidas, self._total, self._ultima = lidas, total, ultima

        self._capas_pil = []
        for fpath in files[:3]:
            try:
                cf = _cover_cache_path(fpath)
                if os.path.exists(cf):
                    self._capas_pil.append(Image.open(cf).convert("RGB"))
                else:
                    data = extract_cover_only(fpath)
                    img = Image.open(io.BytesIO(data)).convert("RGB")
                    img.thumbnail((CAPA_W, CAPA_H), Image.BILINEAR)
                    self._capas_pil.append(img)
            except:
                self._capas_pil.append(None)

        self._cw = CAPA_W + 60
        self._ch = CAPA_H + 60

        self.frame = tk.Frame(parent, bg=c["bg"])
        self.cv = tk.Canvas(self.frame, width=self._cw, height=self._ch,
                            bg=c["bg"], highlightthickness=0)
        self.cv.pack()
        self.lbl = tk.Label(self.frame, text=self._name, font=FSMALL,
                            bg=c["bg"], fg=c["text_dim"], wraplength=self._cw)
        self.lbl.pack(pady=(0, 1))
        self._prog_frame = tk.Frame(self.frame, bg=c["bg"])
        self._prog_frame.pack(pady=(0, 3))
        self._draw_progress_bar()
        make_pill(self.frame, ui("Renomear", "Rename"),
                  lambda: self._rename_cb(self._collection),
                  variant="soft", font=FTINY, pad_x=10, pad_y=4).pack(pady=(2, 8))
        self._draw(0.0)
        for w in (self.cv, self.lbl):
            w.bind("<Enter>",           self._on_enter)
            w.bind("<Leave>",           self._on_leave)
            w.bind("<Double-Button-1>", lambda e: self._detail_cb(self._collection))
            w.bind("<Button-1>",        lambda e: self._detail_cb(self._collection))
            w.bind("<Button-3>",        self._show_menu)

    def _show_menu(self, event):
        menu = tk.Menu(self.frame, tearoff=False)
        menu.add_command(label=ui("Abrir coleção", "Open collection"),
                         command=lambda: self._detail_cb(self._collection))
        menu.add_command(label=ui("Renomear", "Rename"),
                         command=lambda: self._rename_cb(self._collection))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _draw_progress_bar(self):
        for w in self._prog_frame.winfo_children():
            w.destroy()
        c = THEME
        if self._total == 0: return
        pct = self._lidas / self._total
        bar_w, bar_h = CAPA_W, 4
        cv = tk.Canvas(self._prog_frame, width=bar_w, height=bar_h, bg=c["bg"], highlightthickness=0)
        cv.pack(side="left", padx=(10, 4))
        cv.create_rectangle(0, 0, bar_w, bar_h, fill=c["progress_bg"], outline="")
        filled = int(bar_w * pct)
        if filled > 0:
            cv.create_rectangle(0, 0, filled, bar_h, fill=c["accent"], outline="")
        tk.Label(self._prog_frame, text=f"{self._lidas}/{self._total} {TEXTS[LANG]['read']}",
                 font=FTINY, bg=c["bg"], fg=c["text_dim"]).pack(side="left")

    def _make_stack_image(self, alpha):
        c = THEME
        cw, ch = self._cw, self._ch
        scale = 1.0 + (self.SCALE_MAX - 1.0) * ease_out(alpha)
        iw, ih = int(CAPA_W * scale), int(CAPA_H * scale)
        bg_hex = c["bg"].lstrip("#")
        bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
        canvas_img = Image.new("RGBA", (cw, ch), (*bg_rgb, 255))
        rotations  = [6, -4, 0]
        offsets_x  = [-8, 6, 0]
        offsets_y  = [4, -4, 0]
        shadow_cols = [(0,0,0,80),(0,0,0,60),(0,0,0,120)]
        cx, cy = cw // 2, ch // 2 - 4
        n_capas = len(self._capas_pil)
        layers = min(3, n_capas) if n_capas > 0 else 1
        for i in range(layers - 1, -1, -1):
            pil = self._capas_pil[i] if i < len(self._capas_pil) else None
            rot = rotations[i] * (1 + alpha * 0.3)
            ox, oy = offsets_x[i], offsets_y[i]
            layer = Image.new("RGBA", (iw, ih), (50, 50, 60, 255))
            if pil:
                resized = pil.resize((iw, ih), Image.BILINEAR)
                if i < layers - 1:
                    overlay = Image.new("RGBA", (iw, ih), (0, 0, 0, int(80 * (layers - 1 - i) / layers)))
                    resized = Image.alpha_composite(resized.convert("RGBA"), overlay)
                else:
                    resized = resized.convert("RGBA")
                    if alpha > 0.01:
                        ov = Image.new("RGBA", (iw, ih), (0, 0, 0, int(100 * alpha)))
                        resized = Image.alpha_composite(resized, ov)
                layer = resized
            mask = Image.new("L", (iw, ih), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0,0,iw-1,ih-1], radius=CARD_R, fill=255)
            layer.putalpha(mask)
            if abs(rot) > 0.1:
                layer = layer.rotate(rot, expand=True, resample=Image.BICUBIC)
            lw, lh = layer.size
            px, py = cx - lw // 2 + ox, cy - lh // 2 + oy
            shadow = Image.new("RGBA", (lw+8, lh+8), (0,0,0,0))
            shadow.paste(Image.new("RGBA", (lw, lh), shadow_cols[i]), (4, 4))
            canvas_img.alpha_composite(shadow, (px-4, py-4))
            canvas_img.alpha_composite(layer, (px, py))
        return canvas_img.convert("RGB"), iw, ih, cx, cy

    def _draw(self, alpha):
        c = THEME
        cw, ch = self._cw, self._ch
        cv = self.cv
        cv.delete("all")
        self._tk_imgs.clear()
        stack_img, iw, ih, cx, cy = self._make_stack_image(alpha)
        tk_img = ImageTk.PhotoImage(stack_img)
        self._tk_imgs.append(tk_img)
        cv.create_image(0, 0, anchor="nw", image=tk_img)
        n = self._total
        bx, by = cw - 22, 18
        cv.create_oval(bx-12, by-10, bx+12, by+10, fill=c["accent"], outline="")
        cv.create_text(bx, by, text=f"{n}", font=("Segoe UI", 8, "bold"), fill="#fff", anchor="center")
        if self._lidas > 0:
            cv.create_rectangle(18, by-10, 18+52, by+10, fill=c["read_badge"], outline="")
            cv.create_text(18+26, by, text=f"✓ {self._lidas} {TEXTS[LANG]['read']}",
                           font=("Segoe UI", 7, "bold"), fill=c["read_badge_text"], anchor="center")
        if alpha > 0.3:
            a_int = int(255 * min(1.0, (alpha - 0.3) / 0.7))
            col_hex = f"#{a_int:02x}{a_int:02x}{a_int:02x}"
            scale = 1.0 + (self.SCALE_MAX - 1.0) * ease_out(alpha)
            cv.create_text(cx, cy-6, text="▶", font=("Segoe UI Symbol", int(22*scale)), fill=col_hex)
            cv.create_text(cx, cy+26, text=self._name, font=("Segoe UI", 8, "bold"),
                           fill=col_hex, width=iw-16)

    def _animate(self, target):
        if self._anim_id:
            self._root.after_cancel(self._anim_id); self._anim_id = None
        step = (1.0 / self.HOVER_STEPS) * (1 if target > self._alpha else -1)
        def tick():
            self._alpha += step
            if (step > 0 and self._alpha >= target) or (step < 0 and self._alpha <= target):
                self._alpha = target
                self._draw(self._alpha)
                self.lbl.config(fg=THEME["text"] if target > 0.5 else THEME["text_dim"],
                                font=("Segoe UI", 9, "bold") if target > 0.5 else FSMALL)
                return
            self._draw(self._alpha)
            self._anim_id = self._root.after(self.HOVER_MS, tick)
        tick()

    def _on_enter(self, e): self._animate(1.0)
    def _on_leave(self, e): self._animate(0.0)
    def grid(self, **kwargs): self.frame.grid(**kwargs)


def _serie_name(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r'\s*[\(\[]?\d{4}[\)\]]?\s*', ' ', stem)
    stem = re.sub(r'\s*[#nNvV°º]\.?\s*\d+.*$', '', stem)
    stem = re.sub(r'\s+\d+\s*$', '', stem)
    stem = re.sub(r'\s*[-– - ]\s*.*$', '', stem)
    stem = stem.strip(" ._-")
    return stem if stem else Path(filename).stem


def scan_collections(folder: str) -> dict:
    from komicove_app.archive import SUPPORTED_EXTENSIONS
    exts = SUPPORTED_EXTENSIONS
    result = {"subfolders": [], "series": []}
    if not folder or not os.path.isdir(folder):
        return result

    def _scan_dir(base_path, depth=0):
        collected = []
        try:
            entries = sorted(os.scandir(base_path), key=lambda e: natural_key(e.name))
        except PermissionError:
            return collected
        for entry in entries:
            if not entry.name.startswith(".") and entry.is_dir() and depth < 3:
                sub = _scan_dir(entry.path, depth + 1)
                direct_files = sorted([
                    os.path.join(entry.path, f)
                    for f in os.listdir(entry.path)
                    if f.lower().endswith(exts) and os.path.isfile(os.path.join(entry.path, f))
                ], key=natural_key)
                if direct_files:
                    collected.append({"name": entry.name, "path": entry.path, "files": direct_files})
                collected.extend(sub)
        return collected

    result["subfolders"] = _scan_dir(folder)
    root_files = sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(exts) and os.path.isfile(os.path.join(folder, f))
    ], key=natural_key)
    series_map = {}
    for fpath in root_files:
        key = _serie_name(os.path.basename(fpath))
        series_map.setdefault(key, []).append(fpath)
    for name, files in sorted(series_map.items()):
        if len(files) >= 2:
            result["series"].append({"name": name, "files": sorted(files, key=natural_key)})
    return result


def _sort_collections(items, mode):
    if mode == "name":
        return sorted(items, key=lambda x: natural_key(x["name"]))
    elif mode == "date":
        def _mtime(item):
            try: return max(os.path.getmtime(f) for f in item["files"])
            except: return 0
        return sorted(items, key=_mtime, reverse=True)
    elif mode == "progress":
        def _pct(item):
            lidas, total, _ = collection_read_count(item["files"])
            return lidas / total if total > 0 else 0
        return sorted(items, key=_pct, reverse=True)
    return items


import xml.etree.ElementTree as ET

def read_comic_info(path: str) -> dict:
    info = {}
    try:
        if not zipfile.is_zipfile(path):
            return info
        with zipfile.ZipFile(path, "r") as z:
            ci_name = next((n for n in z.namelist()
                            if Path(n).name.lower() == "comicinfo.xml"), None)
            if ci_name is None: return info
            root = ET.fromstring(z.read(ci_name))
            tag_map = {"Title":"title","Series":"series","Number":"number","Year":"year",
                       "Writer":"writer","Penciller":"penciller","Inker":"inker",
                       "Colorist":"colorist","Publisher":"publisher","Summary":"summary",
                       "Genre":"genre","PageCount":"page_count","LanguageISO":"language","Web":"web"}
            for xml_tag, key in tag_map.items():
                el = root.find(xml_tag)
                if el is not None and el.text and el.text.strip():
                    info[key] = el.text.strip()
    except Exception:
        pass
    return info


_COMIC_INFO_CACHE = {}

def get_comic_info(path):
    if path not in _COMIC_INFO_CACHE:
        _COMIC_INFO_CACHE[path] = read_comic_info(path)
    return {**_COMIC_INFO_CACHE.get(path, {}), **book_metadata.get(path)}

def comic_display_title(path):
    info = get_comic_info(path)
    if book_metadata.get(path).get('title'): return info['title']
    if info.get("series") and info.get("number"):
        return f"{info['series']} #{info['number']}"
    if info.get("title"): return info["title"]
    if info.get("series"): return info["series"]
    return Path(path).stem


def sort_comics(paths, mode, progress=None):
    """Order library and collection cards without changing files on disk."""
    paths = list(paths)

    def title_key(value):
        return [(0, int(part)) if part.isdigit() else (1, part.casefold())
                for part in re.split(r"(\d+)", str(value))]

    if mode == "recent":
        progress = progress if progress is not None else load_progress()

        def recent_key(path):
            entry = progress.get(path, {})
            timestamp = entry.get("ts", 0) if isinstance(entry, dict) else 0
            try:
                timestamp = max(float(timestamp or 0), os.path.getmtime(path))
            except OSError:
                timestamp = float(timestamp or 0)
            return timestamp

        return sorted(paths, key=recent_key, reverse=True)
    if mode == "series":
        def series_key(path):
            info = get_comic_info(path)
            series = info.get("series") or _serie_name(Path(path).name)
            return title_key(series), title_key(comic_display_title(path))

        return sorted(paths, key=series_key)
    return sorted(paths, key=lambda path: title_key(comic_display_title(path)),
                  reverse=(mode == "title_desc"))


class MetaTooltip:
    def __init__(self, root):
        self._root = root
        self._win = None
        self._after = None

    def show(self, widget, path):
        info = get_comic_info(path)
        if not info: return
        self._cancel()
        self._after = self._root.after(600, lambda: self._create(widget, path, info))

    def hide(self):
        self._cancel()
        if self._win:
            try: self._win.destroy()
            except Exception as _e: log.debug("silenced: %s", _e)
            self._win = None

    def _cancel(self):
        if self._after:
            self._root.after_cancel(self._after); self._after = None

    def _create(self, widget, path, info):
        if self._win:
            try: self._win.destroy()
            except Exception as _e: log.debug("silenced: %s", _e)
        c = THEME
        self._win = tk.Toplevel(self._root)
        self._win.overrideredirect(True)
        self._win.configure(bg=c["surface"])
        tk.Canvas(self._win, height=2, bg=c["accent"], highlightthickness=0).pack(fill="x")
        frame = tk.Frame(self._win, bg=c["surface"], padx=12, pady=8); frame.pack()
        tk.Label(frame, text=comic_display_title(path), font=FBTN,
                 bg=c["surface"], fg=c["text"], wraplength=220).pack(anchor="w")
        tk.Frame(frame, bg=c["border"], height=1).pack(fill="x", pady=(4, 6))
        for key, label in [("series",ui('Série', 'Series')),("number","Nº"),("year",ui('Ano', 'Year')),
                           ("writer",ui('Roteiro', 'Writer')),("penciller",ui('Desenho', 'Artist')),
                           ("publisher",ui('Editora', 'Publisher')),("genre",ui('Gênero', 'Genre'))]:
            val = info.get(key, "")
            if val:
                row = tk.Frame(frame, bg=c["surface"]); row.pack(fill="x", pady=1)
                tk.Label(row, text=f"{label}:", font=FTINY, bg=c["surface"],
                         fg=c["text_dim"], width=8, anchor="e").pack(side="left")
                tk.Label(row, text=val, font=FTINY, bg=c["surface"], fg=c["text"],
                         anchor="w", wraplength=150).pack(side="left", padx=(4, 0))
        if info.get("summary"):
            tk.Frame(frame, bg=c["border"], height=1).pack(fill="x", pady=(6, 4))
            tk.Label(frame, text=info["summary"], font=FTINY, bg=c["surface"],
                     fg=c["text_dim"], wraplength=220, justify="left").pack(anchor="w")
        self._win.update_idletasks()
        wx = widget.winfo_rootx() + widget.winfo_width() + 6
        wy = widget.winfo_rooty()
        sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
        tw, th = self._win.winfo_width(), self._win.winfo_height()
        if wx + tw > sw - 10: wx = widget.winfo_rootx() - tw - 6
        if wy + th > sh - 10: wy = sh - th - 10
        self._win.geometry(f"+{wx}+{wy}")
        self._win.configure(highlightbackground=c["border"], highlightthickness=1)

class SearchBubble:
    BUBBLE_SIZE  = 46
    BUBBLE_ANIM  = 12
    BUBBLE_MS    = 12
    EXPAND_WIDTH = 220
    PAD_RIGHT    = 18
    PAD_BOTTOM   = 18

    def __init__(self, parent, on_change, on_clear, root):
        self._parent = parent
        self._on_change = on_change
        self._on_clear = on_clear
        self._root = root
        self._expanded = False
        self._anim_id = None
        self._anim_t = 0.0
        self._search_job = None

        c = THEME
        BS = self.BUBBLE_SIZE
        self._frame = tk.Frame(parent, bg=c["bg"])
        self._cv = tk.Canvas(self._frame, height=BS, bg=c["bg"], highlightthickness=0)
        self._cv.pack(fill="x")
        self._var = tk.StringVar()
        self._entry = tk.Entry(self._frame, textvariable=self._var, font=FLABEL,
                               bg=c["accent"], fg="#ffffff", insertbackground="#ffffff",
                               relief="flat", highlightthickness=0, bd=0)
        self._clear_btn = tk.Label(self._frame, text="✕", font=("Segoe UI", 9),
                                   bg=c["accent"], fg="#ffffff", cursor="hand2", padx=4)
        self._cv.bind("<Enter>", lambda e: self._open())
        self._cv.bind("<Button-1>", lambda e: self._open())
        self._frame.bind("<Leave>", self._on_frame_leave)
        self._cv.bind("<Leave>", self._on_frame_leave)
        self._clear_btn.bind("<Button-1>", lambda e: self._do_clear())
        self._var.trace_add("write", self._on_text_change)
        self._entry.bind("<Escape>", lambda e: self._close())
        self._entry.bind("<Return>", lambda e: self._close())
        parent.bind("<Configure>", lambda e: self._reposition())
        self._draw_bubble(0.0)
        self.reposition_after = parent.after(100, self._reposition)

    def _reposition(self):
        pw, ph = self._parent.winfo_width(), self._parent.winfo_height()
        if pw < 10 or ph < 10: return
        target_w = self._target_width()
        x = pw - target_w - self.PAD_RIGHT
        y = ph - self.BUBBLE_SIZE - self.PAD_BOTTOM
        self._frame.place(in_=self._parent, x=x, y=y, width=target_w, height=self.BUBBLE_SIZE)

    def _target_width(self):
        t = ease_out(self._anim_t)
        return int(self.BUBBLE_SIZE + (self.EXPAND_WIDTH - self.BUBBLE_SIZE) * t)

    def _draw_bubble(self, t):
        BS = self.BUBBLE_SIZE
        w = self._target_width()
        r = BS // 2
        self._cv.config(width=w, height=BS)
        self._cv.delete("all")
        acc = THEME["accent"]
        border_glow = THEME["border_glow"]
        self._cv.create_oval(3, 3, BS+1, BS+1, fill=THEME["shadow"], outline="")
        self._cv.create_oval(0, 0, BS, BS, fill=acc, outline="")
        if t > 0.01:
            self._cv.create_rectangle(r, 0, w - r, BS, fill=acc, outline="")
            self._cv.create_oval(w - BS, 0, w, BS, fill=acc, outline="")
            outline_w = 2
            self._cv.create_arc(0, 0, BS, BS, start=90, extent=180,
                                style="arc", outline=border_glow, width=outline_w)
            self._cv.create_line(r, 0, w - r, 0, fill=border_glow, width=outline_w)
            self._cv.create_line(r, BS, w - r, BS, fill=border_glow, width=outline_w)
            self._cv.create_arc(w - BS, 0, w, BS, start=270, extent=180,
                                style="arc", outline=border_glow, width=outline_w)
        else:
            self._cv.create_oval(1, 1, BS - 1, BS - 1, fill=acc, outline=border_glow, width=2)
        self._cv.create_text(w - r, r, text="⌕", font=(_SANS, 15),
                             fill="#ffffff", anchor="center")
        if t > 0.15:
            entry_w = max(0, w - BS - 24)
            self._entry.place(in_=self._cv, x=10, y=8, width=entry_w, height=BS - 16)
            if t > 0.6 and self._var.get():
                self._clear_btn.place(in_=self._cv, x=w - BS - 20, y=12, width=18, height=BS - 24)
            else:
                self._clear_btn.place_forget()
        else:
            self._entry.place_forget()
            self._clear_btn.place_forget()

    def _animate_to(self, target):
        if self._anim_id:
            self._root.after_cancel(self._anim_id)
        step = (1.0 / self.BUBBLE_ANIM) * (1 if target > self._anim_t else -1)
        def tick():
            self._anim_t += step
            done = False
            if step > 0 and self._anim_t >= target: self._anim_t = target; done = True
            elif step < 0 and self._anim_t <= target: self._anim_t = target; done = True
            self._draw_bubble(self._anim_t); self._reposition()
            if not done:
                self._anim_id = self._root.after(self.BUBBLE_MS, tick)
            else:
                self._anim_id = None
                if target > 0.5: self._entry.focus_set()
        tick()

    def _open(self):
        if self._anim_t < 0.9:
            self._expanded = True
            self._animate_to(1.0)

    def _close(self):
        self._expanded = False
        self._entry.place_forget()
        self._animate_to(0.0)
        self._root.focus_set()

    def _on_frame_leave(self, e):
        if not self._var.get() and self._expanded:
            wx, wy = self._frame.winfo_rootx(), self._frame.winfo_rooty()
            ww, wh = self._frame.winfo_width(), self._frame.winfo_height()
            mx, my = self._frame.winfo_pointerx(), self._frame.winfo_pointery()
            if not (wx <= mx <= wx + ww and wy <= my <= wy + wh):
                self._close()

    def _on_text_change(self, *args):
        val = self._var.get()
        if self._search_job: self._root.after_cancel(self._search_job)
        self._search_job = self._root.after(280, lambda: self._on_change(val))
        self._draw_bubble(self._anim_t)

    def _do_clear(self):
        self._var.set(""); self._on_clear(); self._entry.focus_set()

    def update_theme(self):
        c = THEME
        self._entry.config(bg=c["accent"], fg="#ffffff", insertbackground="#ffffff")
        self._clear_btn.config(bg=c["accent"])
        self._frame.config(bg=c["bg"]); self._cv.config(bg=c["bg"])
        self._draw_bubble(self._anim_t)

    def set_text(self, text): self._var.set(text)
    def get_text(self): return self._var.get()
    def destroy(self):
        try: self._frame.destroy()
        except Exception as _e: log.debug("silenced: %s", _e)



__all__ = [name for name in globals() if not name.startswith("__")]
