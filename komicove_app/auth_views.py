from komicove_app.runtime import *
from PIL import ImageOps
from komicove_app.design.fonts import heading as design_heading

class AuthWindow(tk.Toplevel):
    W, H = 1280, 760
    CARD_W = 500

    def __init__(self, master, cb):
        super().__init__(master)
        set_app_icon(self)
        self.cb = cb
        self.title("Komicove")
        self.configure(bg=THEME["bg"])
        self.resizable(True, True)
        self.minsize(920, 620)
        grab_when_visible(self)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(sw, self.W), min(sh, self.H)
        self.geometry(f"{width}x{height}+{(sw-width)//2}+{(sh-height)//2}")

        self._mode = "login"
        self._status_text = ""
        self._status_error = False
        self._entries = {}
        self._fullscreen = False
        self._auth_in_progress = False
        self._needs_totp = False
        self._background_source = None
        self._background_photo = None
        self._logo_photo = None
        self._field_icons = []
        self._last_size = None
        self._resize_job = None

        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)
        self.bind("<Configure>", self._on_configure)

        self._build()
        try:
            self.state("zoomed")
        except tk.TclError:
            pass



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
        factor = min(W / self.W, H / self.H)
        return max(0.82, min(factor, 1.32))

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

        f_logo = self._sf(FLOGO, scale)
        f_btn = self._sf(FBTN, scale)
        f_label = self._sf(FLABEL, scale)
        f_tiny = self._sf(FTINY, scale)
        f_entry = self._sf(FSMALL, scale)

        registering = self._mode == "register"
        card_w = round(self.CARD_W * scale)
        card_y = (max(round(12 * scale), round(H * .035)) if registering
                  else max(round(18 * scale), round(H * .095)))
        base_card_h = round((690 if registering else 650 + 58 * int(self._needs_totp)) * scale)
        card_h = min(base_card_h, H - card_y - round(14 * scale))
        card_x = max(round(W * .552), W - card_w - round(150 * scale))
        center_x = card_x + card_w / 2
        field_h = round((42 if registering else 48) * scale)
        field_spacing = round((8 if registering else 11) * scale)
        field_y = card_y + round((245 if registering else 263) * scale)
        field_count = 5 if registering else 2 + int(self._needs_totp)
        field_y_end = field_y + field_count * field_h + (field_count - 1) * field_spacing
        status_y = field_y_end + round((11 if registering else 16) * scale)
        if registering:
            forgot_y = status_y
            btn_y = status_y + round(31 * scale)
            switch_y = btn_y + round(47 * scale)
        else:
            forgot_y = field_y_end + round(20 * scale)
            btn_y = forgot_y + round(54 * scale)
            switch_y = btn_y + round(59 * scale)
        divider_y = switch_y + round(52 * scale)
        guest_y = (switch_y + round(45 * scale) if registering
                   else divider_y + round(45 * scale))

        cv = tk.Canvas(self, width=W, height=H, bg=c["bg"], highlightthickness=0)
        cv.pack(fill="both", expand=True)
        self._cv = cv


        try:
            if self._background_source is None:
                self._background_source = Image.open(
                    resource_path("assets_redesign/backgrounds/auth_reference_background.png")
                ).convert("RGB")
            background = ImageOps.fit(self._background_source, (W, H), Image.LANCZOS)
            background = ImageEnhance.Brightness(background).enhance(.90)
            self._background_photo = ImageTk.PhotoImage(background)
            cv.create_image(0, 0, image=self._background_photo, anchor="nw")
        except Exception:
            log.debug("Auth background unavailable", exc_info=True)
        cv.create_rectangle(0, 0, W, H, fill="#05080c", stipple="gray25", outline="")

        card_radius = round(18 * scale)
        _rrect(cv, card_x + 7, card_y + 9, card_x + card_w + 7, card_y + card_h + 9,
               card_radius, fill=c["shadow"])
        _rrect(cv, card_x, card_y, card_x + card_w, card_y + card_h,
               card_radius, fill=c["surface"], outline=c["border"])

        try:
            logo = Image.open(resource_path("komicovelogo.png")).convert("RGBA")
            if logo.getbbox():
                logo = logo.crop(logo.getbbox())
            logo.thumbnail((round((155 if registering else 185) * scale),
                            round((94 if registering else 120) * scale)), Image.LANCZOS)
            self._logo_photo = ImageTk.PhotoImage(logo)
            cv.create_image(center_x, card_y + round((85 if registering else 90) * scale),
                            image=self._logo_photo)
        except Exception:
            cv.create_text(center_x, card_y + round(67 * scale), text="Komicove",
                           font=f_logo, fill=c["text"])
        heading_text = (ui('Bem-vindo ao Komicove', 'Welcome to Komicove')
                        if self._mode == "login" else ui('Crie sua conta', 'Create your account'))
        cv.create_text(center_x, card_y + round((175 if registering else 195) * scale),
                       text=heading_text,
                       font=design_heading(max(22, round(24 * scale))), fill=c["text"])
        cv.create_text(center_x, card_y + round((207 if registering else 226) * scale),
                       text=ui('Sua biblioteca de quadrinhos, sempre com você.',
                               'Your comic library, always with you.'),
                       font=f_label, fill=c["text_dim"])


        field_pad = round(24 * scale)
        field_x0 = card_x + field_pad
        field_w = card_w - field_pad * 2
        y = field_y
        self._entries.clear()
        self._field_icons.clear()
        if self._mode == "register":
            y = self._add_field(cv, "username", "user", ui('Usuário', 'Username'), field_x0, y, field_w, field_h, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "display_name", "user", ui('Nome de exibição', 'Display name'), field_x0, y, field_w, field_h, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "email", "mail", ui('E-mail', 'Email'), field_x0, y, field_w, field_h, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "password", "lock", ui('Senha (mín. 8 caracteres)', 'Password (8 characters minimum)'), field_x0, y, field_w, field_h, secret=True, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "confirm_password", "lock", ui('Confirmar senha', 'Confirm password'), field_x0, y, field_w, field_h, secret=True, scale=scale, font=f_entry)
        else:
            y = self._add_field(cv, "username", "user", ui('Usuário ou e-mail', 'Username or email'), field_x0, y, field_w, field_h, scale=scale, font=f_entry) + field_spacing
            y = self._add_field(cv, "password", "lock", ui('Senha', 'Password'), field_x0, y, field_w, field_h, secret=True, scale=scale, font=f_entry)
            if self._needs_totp:
                y += field_spacing
                y = self._add_field(cv, "totp", "lock", ui('Código 2FA', '2FA code'), field_x0, y, field_w, field_h, scale=scale, font=f_entry)
        self._restore_values(saved_values)


        self._status_item = cv.create_text(
            center_x, status_y, text=self._status_text, font=f_tiny,
            fill=(c["accent2"] if self._status_error else c["text_dim"]),
            width=card_w - round(40*scale), justify="center",
        )


        btn_label = ui('Entrar', 'Sign in') if self._mode == "login" else ui('Criar conta', 'Create account')
        btn = make_pill(cv, btn_label,
                         self._do_login if self._mode == "login" else self._do_register,
                         variant="accent", font=f_btn,
                         pad_x=round(20*scale), pad_y=round(11*scale), min_w=field_w,
                         icon_name="log-out" if self._mode == "login" else "user")
        cv.create_window(center_x, btn_y, window=btn)


        switch_text = (ui('Criar conta', 'Create account') if self._mode == "login"
                       else ui('Já tenho conta', 'I already have an account'))
        switch_button = make_pill(
            cv, switch_text,
            lambda: self._switch_mode("register" if self._mode == "login" else "login"),
            variant="ghost", font=f_btn, pad_x=round(20 * scale),
            pad_y=round(10 * scale), min_w=field_w, icon_name="user",
        )
        cv.create_window(center_x, switch_y, window=switch_button)

        if self._mode == "login":
            forgot=cv.create_text(field_x0 + field_w,forgot_y,text=ui('Esqueci minha senha','Forgot my password'),
                                  anchor="e",
                                  font=f_tiny,fill=c['accent2'])
            cv.tag_bind(forgot,"<Button-1>",lambda e:self._recover_password())
            cv.tag_bind(forgot,"<Enter>",lambda e:cv.config(cursor='hand2'))
            cv.tag_bind(forgot,"<Leave>",lambda e:cv.config(cursor=''))


        if self._mode == "login":
            line_pad = round(26 * scale)
            cv.create_line(field_x0, divider_y, center_x - line_pad, divider_y,
                           fill=c["border"])
            cv.create_line(center_x + line_pad, divider_y, field_x0 + field_w, divider_y,
                           fill=c["border"])
            cv.create_text(center_x, divider_y, text=ui('ou', 'or'), font=f_tiny,
                           fill=c["text_dim"])

        guest_button = make_pill(
            cv, ui('Entrar como convidado', 'Continue as guest'), self._continue_guest,
            variant="ghost", font=f_label, pad_x=round(17 * scale),
            pad_y=round(8 * scale), icon_name="user",
        )
        cv.create_window(center_x, guest_y, window=guest_button)

        if not _ACCOUNTS_AVAILABLE:
            self._set_status(ui('Contas indisponíveis no momento: use o modo convidado.', 'Accounts are currently unavailable: use guest mode.'), error=True)

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
            if name in ("password", "confirm_password"):
                entry.config(show="•")

    def _add_field(self, cv, name, icon_kind, placeholder, x, y, w, h, secret=False, scale=1.0, font=None):
        c = THEME
        font = font or FSMALL
        icon_off = round(22 * scale)
        icon_size = round(18 * scale)
        entry_x = round(40 * scale)
        radius = round(16 * scale)

        field_shape = _rrect(cv, x, y, x+w, y+h, radius,
                             fill=c["surface_alt"], outline=c["border"], width=1)
        _draw_field_icon(cv, icon_kind, x + icon_off, y + h/2, icon_size, c["text_dim"])

        entry = tk.Entry(cv, font=font, bd=0, highlightthickness=0,
                          bg=c["surface_alt"], fg=c["text_dim"],
                          insertbackground=c["text"])
        entry.insert(0, placeholder)
        entry_w = w - entry_x - round((36 if secret else 6) * scale)
        cv.create_window(x + entry_x, y + h/2, window=entry, anchor="w",
                          width=entry_w, height=max(1, h - round(14 * scale)))
        if secret:
            eye = lucide_icon("eye", size=max(16, round(18 * scale)), state="normal",
                              dark=IS_DARK)
            eye_off = lucide_icon("eye-off", size=max(16, round(18 * scale)),
                                  state="normal", dark=IS_DARK)
            self._field_icons.extend(image for image in (eye, eye_off) if image is not None)
            reveal = cv.create_image(x + w - round(20 * scale), y + h / 2,
                                     image=eye_off)

            def toggle_secret(_event, ent=entry, marker=reveal):
                visible = bool(ent.cget("show"))
                ent.config(show="" if visible else "•")
                cv.itemconfig(marker, image=eye if visible else eye_off)

            cv.tag_bind(reveal, "<Button-1>", toggle_secret)
            cv.tag_bind(reveal, "<Enter>", lambda _event: cv.config(cursor="hand2"))
            cv.tag_bind(reveal, "<Leave>", lambda _event: cv.config(cursor=""))

        def on_focus_in(_e, ent=entry, ph=placeholder, sec=secret):
            cv.itemconfig(field_shape, outline=c["accent"])
            if ent.get() == ph:
                ent.delete(0, "end")
                ent.config(fg=c["text"])
                if sec:
                    ent.config(show="•")

        def on_focus_out(_e, ent=entry, ph=placeholder):
            cv.itemconfig(field_shape, outline=c["border"])
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
        if self._field_value("password") != self._field_value("confirm_password"):
            self._set_status(ui('As senhas não coincidem.', 'Passwords do not match.'), error=True)
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
        display_name = self._field_value("display_name") if with_email else None
        if with_email and (not email or not display_name):
            self._set_status(ui('Preencha nome de exibição e e-mail.',
                                'Enter a display name and email.'), error=True)
            return
        self._auth_in_progress = True
        self._set_status(ui('Conectando…', 'Connecting…'))

        def worker():
            try:
                if with_email:
                    auth = api_fn(username, password, email, display_name)
                else:
                    totp = self._field_value("totp") if "totp" in self._entries else None
                    auth = api_fn(username, password, totp or None)
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
            if self._mode == "login" and "2FA" in error.upper() and not self._needs_totp:
                self._needs_totp = True
                self._status_text = ui('Digite o código do autenticador para continuar.',
                                       'Enter your authenticator code to continue.')
                self._status_error = False
                self._build()
                return
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
