from panel_app.runtime import *

class PublishDialog(tk.Toplevel):
    pass
    W, H = 440, 650

    def __init__(self, master, path, user):
        super().__init__(master)
        try: self.iconbitmap(resource_path("panel.ico"))
        except Exception as _e: log.debug("silenced: %s", _e)
        self._path = path
        self._user = user
        self._submit_in_progress = False
        self.title(ui('Publicar na comunidade', 'Publish to community'))
        self.configure(bg=THEME["bg"])
        self.resizable(True, True)
        self.minsize(440, 420)
        self.grab_set()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        height = min(780, sh - 100)
        self.geometry(f"520x{height}+{max(0,(sw-520)//2)}+{max(0,(sh-height)//2)}")

        c = THEME
        pad = dict(padx=28)
        footer = tk.Frame(self, bg=c["bg"])
        footer.pack(side="bottom", fill="x")
        canvas = tk.Canvas(self, bg=c["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        form = tk.Frame(canvas, bg=c["bg"])
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        tk.Label(form, text=ui('Publicar na comunidade', 'Publish to community'), font=FTITLE,
                 bg=c["bg"], fg=c["text"]).pack(pady=(22, 2), **pad)
        tk.Label(form, text=os.path.basename(path), font=FTINY,
                 bg=c["bg"], fg=c["text_dim"]).pack(pady=(0, 14), **pad)

        def field(label_text):
            tk.Label(form, text=label_text, font=FTINY, bg=c["bg"], fg=c["text_dim"],
                      anchor="w").pack(fill="x", pady=(8, 2), **pad)
            e = tk.Entry(form, font=FSMALL, bg=c["surface_alt"], fg=c["text"],
                         bd=0, highlightthickness=1, highlightbackground=c["border"],
                         highlightcolor=c["accent"], insertbackground=c["text"])
            e.pack(fill="x", ipady=6, **pad)
            return e

        self._title_e = field(ui('Título', 'Title'))
        self._title_e.insert(0, Path(path).stem)
        self._author_e = field(ui('Autor', 'Author'))
        self._series_e = field(ui('Série (opcional)', 'Series (optional)'))
        self._chapter_e = field(ui('Número do capítulo (opcional)', 'Chapter number (optional)'))
        self._tags_e = field(ui('Tags (separadas por vírgula)', 'Tags (comma-separated)'))
        self._license_e = field(ui('Licença (opcional — ex: CC-BY-4.0, Domínio Público)', 'License (optional — e.g. CC-BY-4.0, Public Domain)'))

        tk.Label(form, text=ui('Descrição', 'Description'), font=FTINY, bg=c["bg"], fg=c["text_dim"],
                  anchor="w").pack(fill="x", pady=(8, 2), **pad)
        self._desc_txt = tk.Text(form, font=FSMALL, bg=c["surface_alt"], fg=c["text"],
                                   bd=0, highlightthickness=1, highlightbackground=c["border"],
                                   highlightcolor=c["accent"], insertbackground=c["text"],
                                   height=3, wrap="word")
        self._desc_txt.pack(fill="x", **pad)

        self._authorship_var = tk.BooleanVar(value=False)
        self._authorization_var = tk.BooleanVar(value=False)
        chk_kwargs = dict(bg=c["bg"], fg=c["text"], selectcolor=c["surface_alt"],
                           activebackground=c["bg"], activeforeground=c["text"],
                           font=FTINY, anchor="w", relief="flat", bd=0,
                           highlightthickness=0)
        tk.Checkbutton(form, text=ui('Sou o autor original desta obra', 'I am the original author of this work'),
                        variable=self._authorship_var, **chk_kwargs).pack(fill="x", pady=(12, 0), **pad)
        tk.Checkbutton(form, text=ui('Tenho autorização do autor para publicar', "I have the author's permission to publish"),
                        variable=self._authorization_var, **chk_kwargs).pack(fill="x", **pad)

        self._status = tk.Label(footer, text="", font=FTINY, bg=c["bg"], fg=c["text_dim"],
                                  wraplength=self.W-56, justify="center")
        self._status.pack(pady=(10, 0), **pad)

        btn_row = tk.Frame(footer, bg=c["bg"])
        btn_row.pack(pady=16, **pad, fill="x")
        make_pill(btn_row, ui('Cancelar', 'Cancel'), self.destroy,
                  variant="ghost", font=FBTN, pad_x=18, pad_y=9).pack(side="left")
        make_pill(btn_row, ui('Enviar para moderação', 'Submit for moderation'), self._submit,
                  variant="accent", font=FBTN, pad_x=18, pad_y=9).pack(side="right")
        self._fade_job = None
        self.bind("<Destroy>", self._cancel_fade, add="+")
        self._fade_in()

    def _fade_in(self, frame=0):
        try:
            self.attributes("-alpha", 0.6 + 0.4 * (1 - (1-frame/8)**3))
            self._fade_job = self.after(16, lambda: self._fade_in(frame+1)) if frame < 8 else None
        except tk.TclError:

            self._fade_job = None

    def _cancel_fade(self, event):
        if event.widget is self and self._fade_job is not None:
            self.after_cancel(self._fade_job)
            self._fade_job = None

    def _submit(self):
        if self._submit_in_progress:
            return
        title = self._title_e.get().strip()
        author = self._author_e.get().strip()
        if not title or not author:
            self._status.config(text=ui('Preencha ao menos título e autor.', 'Enter at least a title and author.'), fg=THEME["accent2"])
            return
        if not self._authorship_var.get() and not self._authorization_var.get():
            self._status.config(
                text=ui(
                    "Marque que você é o autor ou tem autorização — publicações sem isso têm risco maior de ficar em revisão.",
                    "Confirm that you are the author or have permission — submissions without this have a higher chance of being held for review.",
                ),
                fg=THEME["accent2"])
            return

        tags = [t.strip() for t in self._tags_e.get().split(",") if t.strip()]
        description = self._desc_txt.get("1.0", "end").strip()
        license_ = self._license_e.get().strip() or None
        series_title = self._series_e.get().strip() or None
        try: chapter_number = int(self._chapter_e.get()) if self._chapter_e.get().strip() else None
        except ValueError:
            self._status.config(text=ui('O número do capítulo precisa ser inteiro.', 'The chapter number must be an integer.'),fg=THEME["accent2"]); return
        authorship_declared = self._authorship_var.get()
        authorization_declared = self._authorization_var.get()

        self._submit_in_progress = True
        self._status.config(text=ui('Enviando para moderação…', 'Submitting for moderation…'), fg=THEME["text_dim"])

        def worker():
            try:
                response = api_client.submit_publication(
                    self._user.token, title=title, author=author, description=description,
                    tags=tags, file_reference=self._path,
                    authorship_declared=authorship_declared,
                    authorization_declared=authorization_declared, license=license_,
                    series_title=series_title, chapter_number=chapter_number,
                )
                api_client.upload_publication_file(
                    self._user.token, response.publication_id, self._path
                )
                outcome = (response, None)
            except api_client.ApiAuthError as exc:
                outcome = (None, str(exc))
            except api_client.ApiUnavailableError:
                outcome = (None, ui('Sem conexão com o servidor. Tente novamente mais tarde.', 'Could not connect to the server. Try again later.'))
            except api_client.ApiServerError as exc:
                outcome = (None, str(exc))
            except Exception:
                log.exception(ui('Falha inesperada durante publicação', 'Unexpected publishing error'))
                outcome = (None, ui('Não foi possível enviar a publicação agora.', 'Could not submit the publication now.'))
            try:
                self.after(0, lambda: self._finish_submit(*outcome))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _finish_submit(self, result, error):
        self._submit_in_progress = False
        if error:
            self._status.config(text=error, fg=THEME["accent2"])
            return
        messagebox.showinfo(ui('Publicação enviada', 'Submission sent'), result.public_message)
        self.destroy()
