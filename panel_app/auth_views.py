from panel_app.runtime import *

class AuthWindow(tk.Toplevel):
    pass
    W, H = 400, 660
    CARD_W = 320

    def __init__(self, master, cb):
        super().__init__(master)
        try: self.iconbitmap(resource_path("panel.ico"))
        except Exception as _e: log.debug("silenced: %s", _e)
        self.cb = cb
        self.title("PANEL")
        self.configure(bg=THEME["bg"])
        self.resizable(True, True)
        self.minsize(self.W, self.H)
        self.grab_set()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")

        self._mode = "login"
        self._status_text = ""
        self._status_error = False
        self._entries = {}
        self._fullscreen = False
        self._auth_in_progress = False
        self._last_size = None
        self._resize_job = None

        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)
        self.bind("<Configure>", self._on_configure)

        self._build()



    def _current_size(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return self.W, self.H
        return w, h

    def _on_configure(self, event):
        if event.widget is not self:
            return
        size = (event.width, event.height)
        if size == self._last_size:
            return
        self._last_size = size
        if self._resize_job:
            self.after_cancel(self._resize_job)


        self._resize_job = self.after(120, self._build)

    def _toggle_fullscreen(self, event=None):
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)

    def _exit_fullscreen(self, event=None):
        if self._fullscreen:
            self._fullscreen = False
            self.attributes("-fullscreen", False)



    def _scale_factor(self, W, H):
        pass
        factor = min(W / self.W, H / self.H)
        return max(1.0, min(factor, 1.6))

    @staticmethod
    def _sf(font, scale):
        family, size, *rest = font
        return (family, max(1, round(size * scale)), *rest)

    def _build(self):
        self._resize_job = None
        saved_values = self._capture_values()
        for w in self.winfo_children():
            w.destroy()
        c = THEME
        W, H = self._current_size()
        scale = self._scale_factor(W, H)

        f_logo  = self._sf(FLOGO, scale)
        f_btn   = self._sf(FBTN, scale)
        f_label = self._sf(FLABEL, scale)
        f_tiny  = self._sf(FTINY, scale)
        f_entry = self._sf(FSMALL, scale)

        card_w = round(self.CARD_W * scale)
        card_x = (W - card_w) // 2
        card_y = round(92 * scale)


        tab_pad = round(16 * scale)
        tab_h = round(38 * scale)
        tab_y0, tab_y1 = card_y + round(16 * scale), card_y + round(54 * scale)
        ax, ay, ar = W // 2, tab_y1 + round(44 * scale), round(30 * scale)
        field_y = ay + ar + round(24 * scale)
        field_h = round(42 * scale)
        field_spacing = round(12 * scale)



        n_fields = 3
        field_y_end = field_y + n_fields * field_h + (n_fields - 1) * field_spacing
        status_y = field_y_end + round(20 * scale)
        btn_y = status_y + round(32 * scale)
        switch_y = btn_y + round(30 * scale)
        forgot_y = switch_y + round(24 * scale)
        card_bottom = forgot_y + round(22 * scale) if self._mode == "login" else switch_y + round(20 * scale)
        card_h = card_bottom - card_y
        guest_y = card_y + card_h + round(34 * scale)

        cv = tk.Canvas(self, width=W, height=H, bg=c["bg"], highlightthickness=0)
        cv.pack(fill="both", expand=True)
        self._cv = cv


        cv.create_text(W//2, round(40*scale), text="◈ PANEL", font=f_logo, fill=c["text"])
        cv.create_text(W//2, round(64*scale), text=ui('Sua biblioteca de quadrinhos', 'Your comic library'), font=f_tiny, fill=c["text_dim"])
        cv.create_text(W - 14, H - 14, text=ui('F11 tela cheia', 'F11 fullscreen'), font=FTINY, fill=c["text_dim"], anchor="se")

        card_radius = round(22 * scale)
        _rrect(cv, card_x+4, card_y+6, card_x+card_w+4, card_y+card_h+6, card_radius, fill=c["shadow_light"])
        _rrect(cv, card_x, card_y, card_x+card_w, card_y+card_h, card_radius, fill=c["surface"])


        tab_x0, tab_x1 = card_x + tab_pad, card_x + card_w - tab_pad
        _rrect(cv, tab_x0, tab_y0, tab_x1, tab_y1, (tab_y1-tab_y0)//2, fill=c["surface_alt"])
        half_w = (tab_x1 - tab_x0) / 2
        active_x0 = tab_x0 if self._mode == "login" else tab_x0 + half_w
        _rrect(cv, active_x0 + 2, tab_y0 + 2, active_x0 + half_w - 2, tab_y1 - 2,
               (tab_y1-tab_y0)//2 - 2, fill=c["accent"])

        login_tag = cv.create_rectangle(tab_x0, tab_y0, tab_x0+half_w, tab_y1, outline="", fill="")
        register_tag = cv.create_rectangle(tab_x0+half_w, tab_y0, tab_x1, tab_y1, outline="", fill="")
        cv.create_text(tab_x0 + half_w/2, (tab_y0+tab_y1)/2, text=ui('Entrar', 'Sign in'), font=f_btn,
                        fill="#ffffff" if self._mode == "login" else c["text_dim"])
        cv.create_text(tab_x0 + half_w*1.5, (tab_y0+tab_y1)/2, text=ui('Cadastrar', 'Sign up'), font=f_btn,
                        fill="#ffffff" if self._mode == "register" else c["text_dim"])
        cv.tag_bind(login_tag, "<Button-1>", lambda e: self._switch_mode("login"))
        cv.tag_bind(register_tag, "<Button-1>", lambda e: self._switch_mode("register"))


        cv.create_oval(ax-ar, ay-ar, ax+ar, ay+ar, fill=c["surface_alt"], outline=c["border"])
        _draw_field_icon(cv, "user", ax, ay+3, ar*1.3, c["text_dim"])


        field_pad = round(24 * scale)
        field_x0 = card_x + field_pad
        field_w = card_w - field_pad * 2
        y = field_y
        self._entries.clear()
        if self._mode == "register":
            y = self._add_field(cv, "username", "user", ui('Usuário', 'Username'), field_x0, y, field_w, field_h, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "email", "mail", ui('E-mail (opcional)', 'Email (optional)'), field_x0, y, field_w, field_h, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "password", "lock", ui('Senha (mín. 8 caracteres)', 'Password (8 characters minimum)'), field_x0, y, field_w, field_h, secret=True, scale=scale, font=f_entry)
        else:
            y = self._add_field(cv, "username", "user", ui('Usuário', 'Username'), field_x0, y, field_w, field_h, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "password", "lock", ui('Senha', 'Password'), field_x0, y, field_w, field_h, secret=True, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "totp", "lock", ui('Código 2FA (se ativado)', '2FA code (if enabled)'), field_x0, y, field_w, field_h, scale=scale, font=f_entry)
        self._restore_values(saved_values)


        self._status_item = cv.create_text(
            W//2, status_y, text=self._status_text, font=f_tiny,
            fill=(c["accent2"] if self._status_error else c["text_dim"]),
            width=card_w - round(40*scale), justify="center",
        )


        btn_label = ui('Entrar', 'Sign in') if self._mode == "login" else ui('Criar conta', 'Create account')
        btn = make_pill(cv, btn_label,
                         self._do_login if self._mode == "login" else self._do_register,
                         variant="accent", font=f_btn,
                         pad_x=round(20*scale), pad_y=round(9*scale), min_w=field_w)
        cv.create_window(W//2, btn_y, window=btn)


        if self._mode == "login":
            cv.create_text(W//2, switch_y, text=ui('Não tem conta?  Cadastre-se', 'No account yet?  Sign up'),
                            font=f_tiny, fill=c["text_dim"])
        else:
            cv.create_text(W//2, switch_y, text=ui('Já tem conta?  Entrar', 'Already have an account?  Sign in'),
                            font=f_tiny, fill=c["text_dim"])
        link_tag = cv.create_rectangle(card_x, switch_y-10, card_x+card_w, switch_y+10, outline="", fill="")
        cv.tag_bind(link_tag, "<Button-1>",
                    lambda e: self._switch_mode("register" if self._mode == "login" else "login"))

        if self._mode == "login":
            forgot=cv.create_text(W//2,forgot_y,text=ui('Esqueci minha senha','Forgot my password'),
                                  font=f_tiny,fill=c['accent2'])
            cv.tag_bind(forgot,"<Button-1>",lambda e:self._recover_password())
            cv.tag_bind(forgot,"<Enter>",lambda e:cv.config(cursor='hand2'))
            cv.tag_bind(forgot,"<Leave>",lambda e:cv.config(cursor=''))


        guest = cv.create_text(W//2, guest_y, text=ui('Continuar como convidado', 'Continue as guest'),
                                font=f_label, fill=c["text_dim"])
        cv.tag_bind(guest, "<Button-1>", lambda e: self._continue_guest())
        cv.tag_bind(guest, "<Enter>", lambda e: cv.itemconfig(guest, fill=c["text"]))
        cv.tag_bind(guest, "<Leave>", lambda e: cv.itemconfig(guest, fill=c["text_dim"]))
        for tag in (guest, login_tag, register_tag, link_tag):
            cv.tag_bind(tag, "<Enter>", lambda e, t=tag: cv.config(cursor="hand2"))
            cv.tag_bind(tag, "<Leave>", lambda e: cv.config(cursor=""))

        if not _ACCOUNTS_AVAILABLE:
            self._set_status(ui('Contas indisponíveis no momento — use o modo convidado.', 'Accounts are currently unavailable — use guest mode.'), error=True)

    def _capture_values(self):
        pass
        saved = {}
        for name, (entry, ph) in getattr(self, "_entries", {}).items():
            try:
                val = entry.get()
            except tk.TclError:
                continue
            if val != ph:
                saved[name] = val
        return saved

    def _restore_values(self, saved):
        for name, val in saved.items():
            if name not in self._entries or not val:
                continue
            entry, _ph = self._entries[name]
            entry.delete(0, "end")
            entry.insert(0, val)
            entry.config(fg=THEME["text"])
            if name == "password":
                entry.config(show="•")

    def _add_field(self, cv, name, icon_kind, placeholder, x, y, w, h, secret=False, scale=1.0, font=None):
        c = THEME
        font = font or FSMALL
        icon_off = round(22 * scale)
        icon_size = round(18 * scale)
        entry_x = round(40 * scale)
        radius = round(12 * scale)

        _rrect(cv, x, y, x+w, y+h, radius, fill=c["surface_alt"])
        _draw_field_icon(cv, icon_kind, x + icon_off, y + h/2, icon_size, c["text_dim"])

        entry = tk.Entry(cv, font=font, bd=0, highlightthickness=0,
                          bg=c["surface_alt"], fg=c["text_dim"],
                          insertbackground=c["text"])
        entry.insert(0, placeholder)
        entry_w = w - entry_x - round(6 * scale)
        cv.create_window(x + entry_x, y + h/2, window=entry, anchor="w",
                          width=entry_w, height=max(1, h - round(14 * scale)))

        def on_focus_in(_e, ent=entry, ph=placeholder, sec=secret):
            if ent.get() == ph:
                ent.delete(0, "end")
                ent.config(fg=c["text"])
                if sec:
                    ent.config(show="•")

        def on_focus_out(_e, ent=entry, ph=placeholder):
            if not ent.get():
                ent.config(fg=c["text_dim"], show="")
                ent.insert(0, ph)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        self._entries[name] = (entry, placeholder)
        return y + h

    def _field_value(self, name):
        entry, placeholder = self._entries[name]
        v = entry.get()
        return "" if v == placeholder else v.strip() if name != "password" else v

    def _set_status(self, text, error=False):
        self._status_text, self._status_error = text, error
        if hasattr(self, "_cv") and self._status_item:
            self._cv.itemconfig(self._status_item, text=text,
                                 fill=(THEME["accent2"] if error else THEME["text_dim"]))



    def _switch_mode(self, mode):
        if mode == self._mode:
            return
        self._mode = mode
        self._status_text = ""
        self._build()

    def _do_login(self):
        if not _ACCOUNTS_AVAILABLE:
            self._set_status(ui('Contas indisponíveis no momento.', 'Accounts are currently unavailable.'), error=True)
            return
        self._authenticate(api_client.login)

    def _do_register(self):
        if not _ACCOUNTS_AVAILABLE:
            self._set_status(ui('Contas indisponíveis no momento.', 'Accounts are currently unavailable.'), error=True)
            return
        self._authenticate(api_client.register, with_email=True)

    def _authenticate(self, api_fn, with_email=False):
        if self._auth_in_progress:
            return
        username = self._field_value("username")
        password = self._field_value("password")
        if not username or not password:
            self._set_status(ui('Preencha usuário e senha.', 'Enter your username and password.'), error=True)
            return
        email = (self._field_value("email") or None) if with_email else None
        self._auth_in_progress = True
        self._set_status(ui('Conectando…', 'Connecting…'))

        def worker():
            try:
                auth = api_fn(username, password, email) if with_email else api_fn(username, password,self._field_value("totp") or None)
                result = (auth, None)
            except api_client.ApiAuthError as exc:
                result = (None, str(exc))
            except api_client.ApiUnavailableError:
                result = (None, ui('Sem conexão com o servidor. Tente o modo convidado.', 'Could not connect to the server. Try guest mode.'))
            except api_client.ApiServerError as exc:
                result = (None, str(exc))
            except Exception:
                log.exception(ui('Falha inesperada durante autenticação', 'Unexpected authentication error'))
                result = (None, ui('Não foi possível entrar agora.', 'Could not sign in right now.'))
            try:
                self.after(0, lambda: self._finish_auth(*result))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _finish_auth(self, auth, error):
        self._auth_in_progress = False
        if error:
            self._set_status(error, error=True)
            return
        session_store.save_session(session_store.LocalSession(
            token=auth.token, user_id=auth.user_id,
            username=auth.username, display_name=auth.display_name,
            is_moderator=getattr(auth, "is_moderator", False),
            role=getattr(auth, "role", "user"),
        ))
        self.destroy()
        self.cb(auth)

    def _continue_guest(self):
        self.destroy()
        self.cb(None)

    def _recover_password(self):
        identifier=simpledialog.askstring(ui('Recuperar senha','Recover password'),
            ui('Informe o usuário ou e-mail da conta:','Enter the account username or email:'),parent=self)
        if not identifier:return
        try: api_client.request_password_recovery(identifier)
        except Exception as exc: messagebox.showerror(ui('Recuperar senha','Recover password'),str(exc),parent=self); return
        code=simpledialog.askstring(ui('Recuperar senha','Recover password'),
            ui('Se a conta existir, você receberá um código por e-mail. Cole-o aqui:','If the account exists, you will receive a code by email. Paste it here:'),parent=self)
        if not code:return
        password=simpledialog.askstring(ui('Nova senha','New password'),
            ui('Digite a nova senha (mínimo de 8 caracteres):','Enter the new password (8 characters minimum):'),show='•',parent=self)
        if not password:return
        try:
            api_client.confirm_password_recovery(code,password)
            messagebox.showinfo(ui('Recuperar senha','Recover password'),ui('Senha alterada. Agora você já pode entrar.','Password changed. You can now sign in.'),parent=self)
        except Exception as exc: messagebox.showerror(ui('Recuperar senha','Recover password'),str(exc),parent=self)
