import threading
import tkinter as tk
from tkinter import messagebox, simpledialog


def _clear(container):
    for child in container.winfo_children(): child.destroy()


def _rrect(cv, x1, y1, x2, y2, r, fill="", outline="", width=1):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
           x1 + r, y1]
    if fill:
        cv.create_polygon(pts, smooth=True, fill=fill, outline="")
    if outline:
        cv.create_polygon(pts, smooth=True, fill="", outline=outline, width=width)


def _pill_button(parent, text, cmd, theme, *, font, variant="accent", pad_x=18, pad_y=9):
    pass
    c = theme
    host_bg = parent.cget("bg")
    if variant == "accent":
        base, hover, fg = c["accent"], c["accent2"], "#ffffff"
    elif variant == "soft":
        base, hover, fg = c["surface_alt"], c["surface_hover"], c["text"]
    else:
        base, hover, fg = host_bg, c["surface_hover"], c["text_dim"]

    tmp = tk.Label(parent, text=text, font=font)
    tw, th = tmp.winfo_reqwidth(), tmp.winfo_reqheight()
    tmp.destroy()
    w, h = tw + pad_x * 2, th + pad_y * 2
    r = h // 2
    cv = tk.Canvas(parent, width=w, height=h, bg=host_bg, highlightthickness=0, cursor="hand2")

    def render(fill):
        cv.delete("all")
        _rrect(cv, 1, 1, w - 1, h - 1, r, fill=fill)
        cv.create_text(w // 2, h // 2, text=text, font=font, fill=fg)

    render(base)
    cv.bind("<Enter>", lambda e: render(hover))
    cv.bind("<Leave>", lambda e: render(base))
    cv.bind("<Button-1>", lambda e: cmd())
    return cv


def _card(parent, theme):
    pass
    return tk.Frame(parent, bg=theme["surface"], padx=24, pady=22,
                     highlightbackground=theme["border"], highlightthickness=1)


def _labeled_entry(parent, theme, label, *, font_label, font_entry, secret=False):
    c = theme
    tk.Label(parent, text=label, font=font_label, bg=theme["surface"],
              fg=c["text_dim"]).pack(anchor="w", pady=(10, 4))
    box = tk.Frame(parent, bg=c["surface_alt"], highlightbackground=c["border"],
                    highlightthickness=1)
    box.pack(fill="x")
    entry = tk.Entry(box, font=font_entry, bd=0, highlightthickness=0,
                      bg=c["surface_alt"], fg=c["text"], insertbackground=c["text"],
                      disabledbackground=c["surface_alt"], disabledforeground=c["text_dim"],
                      show="•" if secret else "")
    entry.pack(fill="x", padx=12, ipady=9)

    def on_focus_in(_e): box.config(highlightbackground=c["accent"])
    def on_focus_out(_e): box.config(highlightbackground=c["border"])
    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)
    return entry


_ROLE_COLORS = {"owner": "#f5c842", "admin": "#ff7a4d", "moderator": "#5aabff"}


def _role_badge(parent, theme, role):
    pass
    c = theme
    color = _ROLE_COLORS.get(role, c["text_dim"])
    label = (role or "user").title()
    font = ("Segoe UI", 8, "bold")
    tmp = tk.Label(parent, text=label, font=font)
    tw = tmp.winfo_reqwidth()
    tmp.destroy()
    h = 22
    r = h / 2
    w = tw + 20
    cv = tk.Canvas(parent, width=w, height=h, bg=parent.cget("bg"), highlightthickness=0)
    cv.create_arc(0, 0, h, h, start=90, extent=180, style="arc", outline=color, width=1)
    cv.create_arc(w - h, 0, w, h, start=270, extent=180, style="arc", outline=color, width=1)
    cv.create_line(r, 1, w - r, 1, fill=color, width=1)
    cv.create_line(r, h - 1, w - r, h - 1, fill=color, width=1)
    cv.create_text(w // 2, h // 2, text=label, font=font, fill=color)
    return cv


def render_profile(container, root, user, api, theme, fonts, on_updated):
    _clear(container); title, body, small = fonts
    c = theme

    header = tk.Frame(container, bg=c["bg"])
    header.pack(fill="x", padx=30, pady=(28, 16))

    av_size = 60
    av = tk.Canvas(header, width=av_size, height=av_size, bg=c["bg"], highlightthickness=0)
    av.pack(side="left")
    nome_atual = getattr(user, "display_name", None) or getattr(user, "username", "") or "?"
    initial = (nome_atual.strip()[:1] or "?").upper()
    av.create_oval(2, 2, av_size - 2, av_size - 2, fill=c["surface_alt"], outline=c["border"], width=2)
    av.create_text(av_size // 2, av_size // 2, text=initial, font=(title[0], 20, "bold"), fill=c["accent2"])

    name_box = tk.Frame(header, bg=c["bg"])
    name_box.pack(side="left", padx=(14, 0), anchor="w")
    tk.Label(name_box, text=nome_atual, font=title, bg=c["bg"], fg=c["text"]).pack(anchor="w")
    sub = tk.Frame(name_box, bg=c["bg"]); sub.pack(anchor="w", pady=(2, 0))
    tk.Label(sub, text=f"@{getattr(user, 'username', '')}", font=small,
              bg=c["bg"], fg=c["text_dim"]).pack(side="left")
    role_holder = tk.Frame(sub, bg=c["bg"]); role_holder.pack(side="left", padx=(8, 0))
    _role_badge(role_holder, theme, getattr(user, "role", "user")).pack()

    status = tk.Label(container, text="Carregando…", font=small, bg=c["bg"], fg=c["text_dim"])
    status.pack(anchor="w", padx=30)

    if getattr(user, "role", "user") == "user":
        def use_setup_token():
            secret = simpledialog.askstring(
                "Ativar cargo", "Cole o token de configuração do servidor:",
                parent=root, show="•",
            )
            if not secret:
                return
            try:
                promoted = api.claim_moderator(user.token, secret.strip())
                user.role = promoted.role
                user.is_moderator = True
                status.config(text="Cargo ativado. Reabra o app para atualizar o menu.", fg=c["read_badge_text"])
                on_updated(promoted)
            except Exception as exc:
                messagebox.showerror("Ativar cargo", str(exc), parent=root)
        _pill_button(container, "Tenho um token de cargo", use_setup_token, theme, font=small, variant="ghost").pack(anchor="w", padx=30, pady=(8, 0))

    form = _card(container, theme)
    form.pack(fill="x", padx=30, pady=(14, 18))
    tk.Label(form, text="Informações", font=body, bg=c["surface"], fg=c["text"]).pack(anchor="w")

    fields = {}
    for key, label in [("username", "Usuário"), ("display_name", "Nome de exibição"), ("email", "E-mail")]:
        fields[key] = _labeled_entry(form, theme, label, font_label=small, font_entry=body)
    fields["username"].config(state="disabled")

    def loaded(data, error=None):
        if error: status.config(text=error, fg=c["accent2"]); return
        for key in fields:
            fields[key].config(state="normal")
            fields[key].delete(0, "end")
            fields[key].insert(0, data.get(key) or "")
        fields["username"].config(state="disabled")
        for w in role_holder.winfo_children(): w.destroy()
        _role_badge(role_holder, theme, data.get("role", "user")).pack()
        status.config(text="")

    def fetch():
        try: result = (api.get_profile(user.token), None)
        except Exception as exc: result = (None, str(exc))
        root.after(0, lambda: loaded(*result))
    threading.Thread(target=fetch, daemon=True).start()

    def save():
        status.config(text="Salvando…", fg=c["text_dim"])
        def work():
            try:
                result = (api.update_profile(
                    user.token, fields["display_name"].get().strip(),
                    fields["email"].get().strip() or None), None)
            except Exception as exc:
                result = (None, str(exc))
            def done(data, error):
                if error: status.config(text=error, fg=c["accent2"]); return
                status.config(text="Perfil atualizado.", fg=c["read_badge_text"])
                on_updated(data)
            root.after(0, lambda: done(*result))
        threading.Thread(target=work, daemon=True).start()

    btn_row = tk.Frame(form, bg=c["surface"]); btn_row.pack(fill="x", pady=(18, 0))
    _pill_button(btn_row, "Salvar alterações", save, theme, font=body, variant="accent").pack(side="right")

    security = _card(container, theme)
    security.pack(fill="x", padx=30, pady=(0, 18))
    tk.Label(security, text="Segurança", font=body, bg=c["surface"], fg=c["text"]).pack(anchor="w")
    old = _labeled_entry(security, theme, "Senha atual", font_label=small, font_entry=body, secret=True)
    new = _labeled_entry(security, theme, "Nova senha", font_label=small, font_entry=body, secret=True)

    def change_password():
        if len(new.get()) < 8:
            messagebox.showerror("Segurança", "A nova senha precisa ter ao menos 8 caracteres.", parent=root)
            return
        def work():
            try:
                api.change_password(user.token, old.get(), new.get()); error = None
            except Exception as exc:
                error = str(exc)
            def done():
                if error: messagebox.showerror("Segurança", error, parent=root)
                else: messagebox.showinfo("Segurança", "Senha alterada. Entre novamente no próximo acesso.", parent=root)
            root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    sec_btn_row = tk.Frame(security, bg=c["surface"]); sec_btn_row.pack(fill="x", pady=(18, 0))
    _pill_button(sec_btn_row, "Trocar senha", change_password, theme, font=body, variant="accent").pack(side="right")

    if getattr(user, "role", "user") in {"admin", "owner"}:
        def enable_2fa():
            password = simpledialog.askstring("Configurar 2FA", "Confirme sua senha atual:", show="*", parent=root)
            if not password: return
            previous_code = simpledialog.askstring("Configurar 2FA",
                "Código do autenticador atual (deixe vazio na primeira ativação):", parent=root)
            if previous_code is None: return
            def work():
                try: setup, error = api.setup_2fa(user.token, password, previous_code or None), None
                except Exception as exc: setup, error = None, str(exc)
                def show(setup, error):
                    if error: messagebox.showerror("2FA", error, parent=root); return
                    code = simpledialog.askstring(
                        "Ativar 2FA",
                        f"Adicione este segredo ao autenticador:\n\n{setup['secret']}\n\nDigite o código gerado:",
                        parent=root)
                    if not code: return
                    try:
                        api.confirm_2fa(user.token, code)
                        messagebox.showinfo("2FA", "Autenticação em duas etapas ativada.", parent=root)
                    except Exception as exc:
                        messagebox.showerror("2FA", str(exc), parent=root)
                root.after(0, lambda: show(setup, error))
            threading.Thread(target=work, daemon=True).start()
        _pill_button(sec_btn_row, "Configurar 2FA", enable_2fa, theme, font=small, variant="soft").pack(
            side="right", padx=(0, 10))


def render_notifications(container, root, user, api, theme, fonts, on_count):
    _clear(container); title, body, small = fonts
    head = tk.Frame(container, bg=theme["bg"]); head.pack(fill="x", padx=30, pady=(28, 10))
    tk.Label(head, text="Notificações", font=title, bg=theme["bg"], fg=theme["text"]).pack(side="left")
    status = tk.Label(container, text="Carregando…", font=small, bg=theme["bg"], fg=theme["text_dim"])
    status.pack(anchor="w", padx=30)
    canvas = tk.Canvas(container, bg=theme["bg"], highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=30, pady=12)
    content = tk.Frame(canvas, bg=theme["bg"])
    window = canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(window, width=e.width))
    content.bind("<Configure>", lambda e: canvas.config(scrollregion=canvas.bbox("all")))

    def loaded(items, error=None):
        status.config(text=error or f"{sum(not x.get('read_at') for x in items)} não lida(s)",
                      fg=theme["accent2"] if error else theme["text_dim"])
        if error: return
        on_count(sum(not x.get("read_at") for x in items))
        if not items:
            tk.Label(content, text="Nenhuma notificação.", font=body, bg=theme["bg"],
                      fg=theme["text_dim"]).pack(pady=50)
            return
        for item in items:
            unread = not item.get("read_at")
            card = tk.Frame(content, bg=theme["surface_alt"] if unread else theme["surface"],
                             padx=16, pady=12,
                             highlightbackground=theme["accent"] if unread else theme["border"],
                             highlightthickness=1)
            card.pack(fill="x", pady=5)
            tk.Label(card, text=item["title"], font=body, bg=card["bg"], fg=theme["text"]).pack(anchor="w")
            tk.Label(card, text=item["message"], font=small, bg=card["bg"], fg=theme["text_dim"],
                      wraplength=760, justify="left").pack(anchor="w")
            if unread:
                threading.Thread(target=lambda i=item: api.mark_notification_read(user.token, i["id"]),
                                  daemon=True).start()
        on_count(0)

    def fetch():
        try: result = (api.notifications(user.token), None)
        except Exception as exc: result = (None, str(exc))
        root.after(0, lambda: loaded(*result))
    threading.Thread(target=fetch, daemon=True).start()
