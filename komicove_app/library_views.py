from komicove_app.runtime import *
from komicove_app.archive import SUPPORTED_EXTENSIONS, find_7zip
import komicove_app.runtime as _runtime
import komicove_app.auth_views as _auth_views
import komicove_app.reader_views as _reader_views
import komicove_app.community_views as _community_views
import komicove_app.publishing_views as _publishing_views
import komicove_app.moderation_views as _moderation_views
import komicove_app.library_widgets as _library_widgets
from komicove_app.auth_views import AuthWindow
from komicove_app.reader_views import LangWindow, ReaderWindow
from komicove_app.publishing_views import PublishDialog
from komicove_app.community_views import CommunityTab, CommunityWindow
from komicove_app.moderation_views import ModerationWindow
from komicove_app.library_widgets import *
from komicove_app import updater
import webbrowser
import platform, sys
from urllib.parse import urlparse

class LibraryWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        set_app_icon(self)
        self.withdraw()
        self.title("Komicove")
        self.configure(bg=THEME["bg"])
        apply_scrollbar_style()

        self._capa_cache   = {}
        self._resize_job   = None
        self._last_ncols   = 0
        self._col_filter   = "all"
        self._col_sort     = "name"
        self._book_sort    = load_prefs().get("book_sort", "title")
        if self._book_sort not in ("recent", "title", "title_desc", "series"):
            self._book_sort = "title"
        self._status_filter= "all"
        self._search_query = ""
        self._card_map     = {}
        self._cover_loader = None
        self._search_bubble= None
        self._meta_tooltip = None
        self._sync_job = None
        register_change_listener(self._schedule_sync)
        self._notification_count = 0

        self.current_user = None
        load_icons()
        load_library_config()
        self._sync_shared_settings()
        prefs = load_prefs()
        if prefs.get("lang"):
            self.after(10, self._show_auth)
        else:
            LangWindow(self, self._language_ready)

    def _language_ready(self):
        self._sync_shared_settings()
        self._show_auth()

    def _change_language(self):
        def changed():
            self._sync_shared_settings()
            self._build_shell()
            active = getattr(self, "_active_tab", "library")
            action = {
                "collections": self._show_collections,
                "discovery": self._open_discovery,
                "downloads": self._open_downloads,
                "submissions": self._open_my_publications,
                "notifications": self._open_notifications,
                "moderation": self._open_moderation,
            }.get(active, self._refresh_library)
            action()
        LangWindow(self, changed)

    def _sync_shared_settings(self):
        pass
        global LIBRARY_FOLDER, LANG, IS_DARK
        LIBRARY_FOLDER = _runtime.LIBRARY_FOLDER
        LANG = _runtime.LANG
        IS_DARK = _runtime.IS_DARK
        for module in (_auth_views, _reader_views, _community_views,
                       _publishing_views, _moderation_views, _library_widgets):
            module.LANG = LANG
            module.IS_DARK = IS_DARK

    def _show_auth(self):

        existing = session_store.load_session() if _ACCOUNTS_AVAILABLE else None
        if existing:
            def validate():
                try:
                    user = api_client.get_current_user(existing.token)
                    outcome = (user, True)
                except api_client.ApiUnavailableError:

                    outcome = (existing, True)
                except Exception:
                    session_store.clear_session()
                    outcome = (None, False)
                self.after(0, lambda: self._finish_saved_session(*outcome))

            threading.Thread(target=validate, daemon=True).start()
        else:
            AuthWindow(self, self._on_auth_done)

    def _finish_saved_session(self, user, usable):
        if usable:
            self.current_user = user
            if user is not None:
                self._sync_library_state(user)
            self._start()
        else:
            AuthWindow(self, self._on_auth_done)

    def _on_auth_done(self, auth):




        self.current_user = auth
        if auth is not None:
            self._sync_library_state(auth)
        self._start()

    def _sync_library_state(self, auth):
        def worker():
            try:
                progress, favorites = load_progress(), set(load_favorites())
                payload, paths_by_id = build_sync_payload(progress, favorites)
                merged = api_client.sync_library_state(auth.token, payload)
                changed = False
                for item in merged:
                    path = paths_by_id.get(item["item_key"])
                    if not path: continue
                    local = progress.get(path, {})
                    local_stamp = local.get("ts", 0) if isinstance(local, dict) else 0
                    remote_stamp = float(item.get("client_updated_at") or 0)
                    if item.get("page") is not None and remote_stamp > local_stamp:
                        progress[path] = {"page": item["page"], "ts": remote_stamp}; changed = True
                    if remote_stamp >= local_stamp:
                        if item.get("favorite"): favorites.add(path)
                        else: favorites.discard(path)
                        changed = True
                if changed:
                    _json_save(PROGRESS_FILE, progress); _json_save(FAVORITES_FILE, sorted(favorites))
            except Exception:
                log.debug(ui('Sincronização da biblioteca indisponível', 'Library sync unavailable'), exc_info=True)
        threading.Thread(target=worker, daemon=True).start()

    def _schedule_sync(self, _kind=None, _path=None):
        if self.current_user is None:return
        if self._sync_job is not None:
            try:self.after_cancel(self._sync_job)
            except Exception:pass
        self._sync_job=self.after(1500,lambda:self._sync_library_state(self.current_user))

    def _open_profile(self):
        self._active_tab = "profile"
        self._build_shell()
        render_profile(
            self._main, self, self.current_user, api_client, THEME,
            (FTITLE, FLABEL, FSMALL), self._profile_updated,
        )

    def _profile_updated(self, data):
        self.current_user.display_name = data.get("display_name") or self.current_user.display_name
        if hasattr(self.current_user, "email"):
            self.current_user.email = data.get("email")

    def _open_notifications(self):
        self._active_tab = "notifications"
        self._build_shell()
        render_notifications(
            self._main, self, self.current_user, api_client, THEME,
            (FTITLE, FLABEL, FSMALL), self._set_notification_count,
        )

    def _set_notification_count(self, count):
        self._notification_count = max(0, int(count or 0))

    def _refresh_notification_count(self):
        if self.current_user is None:
            return
        def worker():
            try:
                items = api_client.notifications(self.current_user.token)
                count = sum(not item.get("read_at") for item in items)
            except Exception:
                return
            self.after(0, lambda: self._set_notification_count(count))
        threading.Thread(target=worker, daemon=True).start()

    def _open_downloads(self):
        self._active_tab = "downloads"
        self._build_shell()
        render_downloads(self._main, THEME, (FTITLE, FLABEL, FSMALL))

    def _logout(self):
        if _ACCOUNTS_AVAILABLE and self.current_user is not None:
            token = getattr(self.current_user, "token", None)
            if token:
                try:
                    api_client.logout(token)
                except Exception as _e:
                    log.debug("silenced: %s", _e)
            session_store.clear_session()
        self.current_user = None



        AuthWindow(self, self._on_auth_done)

    def _open_moderation(self):
        if self.current_user is None:
            messagebox.showinfo(ui('Moderação', 'Moderation'), ui('Entre em uma conta para continuar.', 'Sign in to continue.'))
            return
        role = getattr(self.current_user, "role", "user")
        if can_moderate(self.current_user):
            self._active_tab = "moderation"
            self._build_shell()
            self._render_moderation_tab()
            return

        messagebox.showerror(ui('Moderação', 'Moderation'), ui('Sua conta não possui acesso à moderação.', 'Your account does not have moderation access.'), parent=self)
        return

    def _claim_admin_token(self):
        if getattr(self.current_user, "role", "user") != "moderator":
            return
        setup_token = simpledialog.askstring(
            ui('Ativar administrador', 'Enable administrator role'),
            ui('Digite o token de administrador:', 'Enter the administrator token:'), parent=self, show="•",
        )
        if not setup_token:
            return

        def worker():
            try:
                promoted = api_client.claim_admin(
                    self.current_user.token, setup_token.strip()
                )
                outcome = (promoted, None)
            except (api_client.ApiAuthError, api_client.ApiServerError) as exc:
                outcome = (None, str(exc))
            except api_client.ApiUnavailableError:
                outcome = (None, ui('Servidor indisponível.', 'Server unavailable.'))
            except Exception:
                log.exception(ui('Falha ao ativar administrador', 'Could not enable administrator role'))
                outcome = (None, ui('Não foi possível ativar o cargo de administrador.', 'Could not enable the administrator role.'))
            self.after(0, lambda: self._finish_moderator_claim(*outcome))

        threading.Thread(target=worker, daemon=True).start()

    def _open_discovery(self):
        self._active_tab="discovery";self._build_shell()
        CommunityTab(self._main,self,user=self.current_user,mine=False)

    def _open_my_publications(self):
        if self.current_user is not None:
            self._active_tab="submissions";self._build_shell()
            CommunityTab(self._main,self,user=self.current_user,mine=True)

    def _finish_moderator_claim(self, promoted, error):
        if error:
            messagebox.showerror(ui('Administrador', 'Administrator'), error, parent=self)
            return
        self.current_user = promoted
        session_store.save_session(session_store.LocalSession(
            token=promoted.token, user_id=promoted.user_id,
            username=promoted.username, display_name=promoted.display_name,
            is_moderator=True,
            role=getattr(promoted, "role", "admin"),
        ))
        self._build_shell()
        self._active_tab = "moderation"
        self._build_shell()
        self._render_moderation_tab()

    def _render_moderation_tab(self):
        for child in self._main.winfo_children():
            child.destroy()
        self._moderation_images = []
        header = tk.Frame(self._main, bg=THEME["bg"])
        header.pack(fill="x", padx=28, pady=(24, 12))
        tk.Label(header, text=ui('Moderação', 'Moderation'), font=FTITLE, bg=THEME["bg"],
                 fg=THEME["text"]).pack(side="left")
        make_pill(header, ui('Atualizar', 'Refresh'), self._render_moderation_tab,
                  variant="ghost", font=FBTN, pad_x=14, pad_y=7).pack(side="right")
        make_pill(header, ui('Denúncias', 'Reports'), self._render_reports_tab,
                  variant="ghost", font=FBTN, pad_x=14, pad_y=7).pack(side="right", padx=8)
        if getattr(self.current_user, "role", "user") == "moderator":
            make_pill(header, ui('Usar token de administrador', 'Use administrator token'), self._claim_admin_token,
                      variant="accent", font=FSMALL, pad_x=12, pad_y=7).pack(side="right", padx=8)
        self._moderation_status = tk.Label(
            self._main, text=ui('Carregando pedidos…', 'Loading requests…'), font=FSMALL,
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._moderation_status.pack(anchor="w", padx=28)

        canvas = tk.Canvas(self._main, bg=THEME["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._main, orient="vertical", command=canvas.yview)
        self._moderation_grid = tk.Frame(canvas, bg=THEME["bg"])
        self._moderation_grid.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._moderation_grid, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=(20, 0), pady=12)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        def worker():
            try:
                outcome = (api_client.moderation_queue(
                    self.current_user.token, include_decided=True
                ), None)
            except Exception as exc:
                outcome = (None, str(exc))
            self.after(0, lambda: self._moderation_loaded(*outcome))

        threading.Thread(target=worker, daemon=True).start()

    def _render_reports_tab(self):
        for child in self._main.winfo_children(): child.destroy()
        tk.Label(self._main,text=ui('Denúncias', 'Reports'),font=FTITLE,bg=THEME["bg"],fg=THEME["text"]).pack(anchor="w",padx=28,pady=(24,8))
        status=tk.Label(self._main,text=ui('Carregando…', 'Loading…'),font=FSMALL,bg=THEME["bg"],fg=THEME["text_dim"]);status.pack(anchor="w",padx=28)
        area=tk.Frame(self._main,bg=THEME["bg"]);area.pack(fill="both",expand=True,padx=28,pady=12)
        def worker():
            try: result,error=api_client.admin_reports(self.current_user.token),None
            except Exception as exc: result,error=None,str(exc)
            def done(items,error):
                status.config(text=error or ui(f"{len(items)} denúncia(s)", f"{len(items)} report(s)"),fg=THEME["accent2"] if error else THEME["text_dim"])
                if error:return
                for item in items:
                    card=tk.Frame(area,bg=THEME["surface"],padx=14,pady=10);card.pack(fill="x",pady=5)
                    tk.Label(card,text=f"{item['target_type']} · {item['reason']} · {item['status']}",font=FLABEL,bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w")
                    tk.Label(card,text=item.get("description") or ui('Sem descrição', 'No description'),font=FSMALL,bg=THEME["surface"],fg=THEME["text_dim"],wraplength=850,justify="left").pack(anchor="w")
            self.after(0,lambda:done(result,error))
        threading.Thread(target=worker,daemon=True).start()

    def _moderation_loaded(self, items, error):
        if error:
            self._moderation_status.config(text=error, fg=THEME["accent2"])
            return
        pending = sum(item.get("status") == "pending_review" for item in items)
        self._moderation_status.config(
            text=ui(f"{len(items)} pedido(s) no histórico · {pending} pendente(s)",
                    f"{len(items)} request(s) in history · {pending} pending")
        )
        if not items:
            tk.Label(self._moderation_grid, text=ui('Nenhum pedido pendente.', 'No pending requests.'), font=FTITLE,
                     bg=THEME["bg"], fg=THEME["text_dim"]).grid(row=0, column=0, padx=40, pady=70)
            return
        for index, item in enumerate(items):
            self._create_moderation_card(item, index // 4, index % 4)

    def _create_moderation_card(self, item, row, column):
        card = tk.Frame(self._moderation_grid, bg=THEME["surface"], width=220, height=390)
        card.grid(row=row, column=column, padx=9, pady=9, sticky="n")
        card.grid_propagate(False)
        cover_box = tk.Frame(card, width=190, height=220, bg=THEME["surface_alt"])
        cover_box.pack(padx=10, pady=(10, 7))
        cover_box.pack_propagate(False)
        cover = tk.Label(cover_box,
                         text=ui('Carregando capa…', 'Loading cover…') if item.get("has_file") else ui('Sem arquivo', 'No file'),
                         bg=THEME["surface_alt"], fg=THEME["text_dim"], font=FTINY)
        cover.pack(fill="both", expand=True)
        tk.Label(card, text=item["title"], font=FBTN, bg=THEME["surface"],
                 fg=THEME["text"], wraplength=195).pack(padx=10)
        status_labels = {"pending_review": ui('Pendente', 'Pending'), "approved": ui('Aprovado', 'Approved'), "rejected": ui('Rejeitado', 'Rejected')}
        tk.Label(card, text=f"{item['author']} · {status_labels.get(item.get('status'), item.get('status'))}", font=FTINY,
                 bg=THEME["surface"], fg=THEME["text_dim"], wraplength=195).pack(padx=10, pady=3)
        buttons = tk.Frame(card, bg=THEME["surface"])
        buttons.pack(side="bottom", fill="x", padx=8, pady=8)
        if item.get("has_file"):
            make_pill(buttons, ui('Ler', 'Read'), lambda i=item: self._read_moderation_file(i),
                      variant="ghost", font=FTINY, pad_x=8, pad_y=5).pack(side="left")
            make_pill(buttons, ui('Baixar', 'Download'), lambda i=item: self._download_moderation_file(i),
                      variant="ghost", font=FTINY, pad_x=8, pad_y=5).pack(side="left", padx=3)
            self._load_moderation_cover(item, cover)
        if item.get("status") == "pending_review":
            make_pill(buttons, "✓", lambda i=item: self._moderate_from_tab(i, "approved"),
                      variant="accent", font=FTINY, pad_x=8, pad_y=5).pack(side="right")
            make_pill(buttons, "✕", lambda i=item: self._moderate_from_tab(i, "rejected"),
                      variant="ghost", font=FTINY, pad_x=8, pad_y=5).pack(side="right", padx=3)

    def _load_moderation_cover(self, item, label):
        def worker():
            try:
                data = api_client.moderation_cover(self.current_user.token, item["record_id"])
                image = Image.open(io.BytesIO(data)).convert("RGB")
                image.thumbnail((190, 220), Image.LANCZOS)
                self.after(0, lambda: self._set_moderation_cover(label, image))
            except Exception:
                self.after(0, lambda: label.config(text=ui('Capa indisponível', 'Cover unavailable')))
        threading.Thread(target=worker, daemon=True).start()

    def _set_moderation_cover(self, label, image):
        tk_image = ImageTk.PhotoImage(image)
        self._moderation_images.append(tk_image)
        label.config(image=tk_image, text="")

    def _moderation_cache_path(self, item):
        folder = os.path.join(_APPDATA, "moderation_cache")
        os.makedirs(folder, exist_ok=True)
        extension = Path(item.get("original_filename") or ".cbz").suffix or ".cbz"
        return os.path.join(folder, item["record_id"] + extension)

    def _read_moderation_file(self, item):
        destination = self._moderation_cache_path(item)
        self._download_for_action(item, destination, open_after=True)

    def _download_moderation_file(self, item):
        destination = filedialog.asksaveasfilename(
            parent=self, initialfile=item.get("original_filename") or "quadrinho.cbz"
        )
        if destination:
            self._download_for_action(item, destination, open_after=False)

    def _download_for_action(self, item, destination, open_after):
        self._moderation_status.config(text=ui('Baixando arquivo…', 'Downloading file…'))
        def worker():
            try:
                api_client.download_moderation_file(
                    self.current_user.token, item["record_id"], destination
                )
                outcome = None
            except Exception as exc:
                outcome = str(exc)
            self.after(0, lambda: self._download_finished(destination, open_after, outcome))
        threading.Thread(target=worker, daemon=True).start()

    def _download_finished(self, destination, open_after, error):
        if error:
            self._moderation_status.config(text=error, fg=THEME["accent2"])
            return
        self._moderation_status.config(text=ui('Download concluído.', 'Download completed.'), fg=THEME["text_dim"])
        if open_after:
            try:
                loader = SmartPageLoader(destination)
                ReaderWindow(self, destination, loader)
            except Exception as exc:
                messagebox.showerror(ui('Leitura', 'Reading'), ui(f"Não foi possível abrir o arquivo: {exc}", f"Could not open the file: {exc}"), parent=self)

    def _moderate_from_tab(self, item, decision):
        verb = ui("aprovar", "approve") if decision == "approved" else ui("rejeitar", "reject")
        reason = simpledialog.askstring(
            ui('Motivo da decisão', 'Decision reason'),
            ui(f"Explique por que deseja {verb} esta publicação:", f"Explain why you want to {verb} this submission:"), parent=self
        )
        if not reason or len(reason.strip()) < 3:
            return
        def worker():
            try:
                api_client.moderate(
                    self.current_user.token, item["record_id"], decision, reason.strip()
                )
                error = None
            except Exception as exc:
                error = str(exc)
            self.after(0, lambda: self._moderation_decided(error))
        threading.Thread(target=worker, daemon=True).start()

    def _moderation_decided(self, error):
        if error:
            messagebox.showerror(ui('Moderação', 'Moderation'), error, parent=self)
        else:
            self._render_moderation_tab()

    def _start(self):
        maximize_window(self)
        self.deiconify()
        self._cover_loader = CoverLoader(self, self._capa_cache)
        self._meta_tooltip = MetaTooltip(self)
        self._build_shell()
        self.after(200, self._refresh_library)
        self.after(250, self._refresh_notification_count)
        self.after(1200, self._check_updates_background)

    def _check_updates_background(self):
        if getattr(self, "_update_check_started", False): return
        self._update_check_started = True
        def worker():
            try: result = updater.check()
            except Exception: result = None
            if result: self.after(0, lambda: self._show_update_notice(result))
        threading.Thread(target=worker, daemon=True).start()

    def _release_notes(self, data):
        if _runtime.LANG == "en":
            return "A new Komicove release is available with reader fixes and stability improvements. Open the download page to read the complete release notes."
        return (data.get("notes") or ui('Sem notas publicadas.', 'No release notes published.')).strip()

    def _show_update_notice(self, data):
        if getattr(self, "_update_notice", None) and self._update_notice.winfo_exists(): return
        dialog=tk.Toplevel(self); self._update_notice=dialog
        dialog.title(ui('Atualização disponível', 'Update available')); dialog.configure(bg=THEME["bg"]); dialog.resizable(False,False)
        dialog.transient(self); dialog.attributes("-topmost", True)
        card=tk.Frame(dialog,bg=THEME["surface"],highlightthickness=1,highlightbackground=THEME["accent"]); card.pack(padx=2,pady=2)
        tk.Label(card,text=ui(f"Komicove {data['version']} disponível 🎉", f"Komicove {data['version']} available 🎉"),font=FTITLE,bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w",padx=22,pady=(18,4))
        notes=self._release_notes(data)
        summary=notes.split("\n\n",1)[0][:220]
        tk.Label(card,text=summary,font=FSMALL,bg=THEME["surface"],fg=THEME["text_dim"],wraplength=390,justify="left").pack(anchor="w",padx=22,pady=(0,14))
        actions=tk.Frame(card,bg=THEME["surface"]);actions.pack(fill="x",padx=18,pady=(0,16))
        make_pill(actions,ui("Depois", "Later"),dialog.destroy,variant="soft",font=FSMALL).pack(side="right")
        make_pill(actions,ui('Baixar', 'Download'),lambda:webbrowser.open(updater.safe_url(data.get("url"))),variant="accent",font=FSMALL).pack(side="right",padx=7)
        make_pill(actions,ui('Ver novidades', "See what's new"),lambda:self._open_update_details(data),variant="ghost",font=FSMALL).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW",dialog.destroy)

    def _open_update_details(self, data):
        if getattr(self, "_update_notice", None) and self._update_notice.winfo_exists(): self._update_notice.destroy()
        self._check_updates()

    def _build_shell(self):
        for w in self.winfo_children():
            w.destroy()
        c = THEME
        sidebar_width = 232
        self._sb = tk.Frame(self, bg=c["surface"], width=sidebar_width)
        self._sb.pack(side="left", fill="y")
        self._sb.pack_propagate(False)
        lc = tk.Canvas(self._sb, width=sidebar_width, height=92, bg=c["surface"], highlightthickness=0)
        lc.pack(pady=(8, 0))
        try:
            logo_img = Image.open(resource_path("komicovelogo.png")).convert("RGBA")
            logo_img.thumbnail((168, 76), Image.LANCZOS)
            self.logo_tk = ImageTk.PhotoImage(logo_img)
            lc.create_image(sidebar_width // 2, 42, image=self.logo_tk)
        except Exception:
            lc.create_text(sidebar_width // 2, 38, text="◈ Komicove", font=FLOGO, fill=c["text"])
        lc.create_line(20, 88, sidebar_width - 20, 88, fill=c["border"], width=1)

        self._active_tab = getattr(self, "_active_tab", "library")
        self._sidebar_section(ui('NAVEGAÇÃO', 'NAVIGATION'))
        for label, cmd, tab, icon in [
            (TEXTS[LANG]['library'], self._refresh_library, "library", ICONS.get("library")),
            (TEXTS[LANG]['collections'], self._show_collections, "collections", ICONS.get("collections")),
        ]:
            active = (self._active_tab == tab)
            self._sidebar_item(label, icon,
                lambda f=cmd, t=tab: (setattr(self, "_active_tab", t), self._build_shell(), f())[-1],
                active=active, font=FBTN, pady=8)
        self._sidebar_item(ui('Descobrir', 'Discover'), ICONS.get("discover"),
                           self._open_discovery, active=(self._active_tab == "discovery"), font=FBTN, pady=8)

        self._sidebar_section(ui('ATIVIDADE', 'ACTIVITY'))
        self._sidebar_item("Downloads", ICONS.get("downloads"), self._open_downloads,
                           active=(self._active_tab == "downloads"), font=FLABEL, pady=7)
        self._sidebar_item(ui('Estatísticas', 'Statistics'), ICONS.get("library"), self._open_statistics,
                           active=(self._active_tab == "statistics"), font=FLABEL, pady=7)

        if self.current_user is not None:
            self._sidebar_item(ui('Meus envios', 'My submissions'), ICONS.get("submissions"), self._open_my_publications,
                                active=(self._active_tab == "submissions"), font=FLABEL, pady=7)
            self._sidebar_item(ui('Notificações', 'Notifications'), ICONS.get("notifications"), self._open_notifications,
                                active=(self._active_tab == "notifications"), font=FLABEL, pady=7,
                                badge=self._notification_count or None)
            role = getattr(self.current_user, "role", "user")
            has_moderation_access = can_moderate(self.current_user)
            if has_moderation_access:
                self._sidebar_section(ui('EQUIPE', 'TEAM'))
                self._sidebar_item(ui('Moderação', 'Moderation'), ICONS.get("moderation"),
                                    self._open_moderation,
                                    active=(self._active_tab == "moderation"), font=FLABEL, pady=7)

        tk.Frame(self._sb, bg=c["surface"]).pack(fill="both", expand=True)
        self._sidebar_section(ui('PREFERÊNCIAS', 'PREFERENCES'))
        for txt, cmd, icon in [
            (ui('Idioma', 'Language'), self._change_language, ICONS.get("language")),
            (current_theme_label().strip(), self._toggle_theme, ICONS.get("theme")),
            (TEXTS[LANG]['folder'], self._choose_folder, ICONS.get("folder")),
            ("Backup", self._do_backup, ICONS.get("backup")),
            (ui('Restaurar', 'Restore'), self._do_restore, ICONS.get("restore")),
            (ui('Atualizações', 'Updates'), self._check_updates, ICONS.get("downloads")),
            (ui('Diagnóstico seguro', 'Safe diagnostics'), self._copy_diagnostics, ICONS.get("notifications")),
        ]:
            self._sidebar_item(txt, icon, cmd, font=FSMALL, pady=6)

        if self.current_user is not None:
            self._sidebar_account_card()
        else:
            tk.Label(self._sb, text=ui('Modo convidado', 'Guest mode'), font=FSMALL, bg=c["surface"],
                     fg=c["text_dim"]).pack(anchor="w", padx=20, pady=(8, 14))

        tk.Frame(self._sb, bg=c["border"], width=1).place(relx=1, rely=0, relheight=1, anchor="ne")

        self._main = tk.Frame(self, bg=c["bg"])
        self._main.pack(side="right", fill="both", expand=True)

    def _check_updates(self):
        dialog=tk.Toplevel(self); dialog.title(ui('Atualizações do Komicove', 'Komicove updates')); dialog.configure(bg=THEME["bg"])
        dialog.geometry("560x420"); dialog.resizable(False,False); dialog.transient(self); grab_when_visible(dialog)
        head=tk.Frame(dialog,bg=THEME["surface"],height=82); head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head,text=ui('✦  Atualizações', '✦  Updates'),font=FTITLE,bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w",padx=24,pady=(18,0))
        tk.Label(head,text=f"Windows/Linux {updater.CURRENT_VERSION}  ·  Android 0.1.0",font=FSMALL,bg=THEME["surface"],fg=THEME["text_dim"]).pack(anchor="w",padx=26)
        status=tk.Label(dialog,text=ui('Verificando versões…', 'Checking versions…'),font=FLABEL,bg=THEME["bg"],fg=THEME["text_dim"]); status.pack(anchor="w",padx=24,pady=(20,8))
        notes=tk.Text(dialog,height=11,bg=THEME["surface_alt"],fg=THEME["text"],insertbackground=THEME["text"],relief="flat",wrap="word",font=FSMALL)
        notes.pack(fill="both",expand=True,padx=24,pady=4); notes.configure(state="disabled")
        actions=tk.Frame(dialog,bg=THEME["bg"]); actions.pack(fill="x",padx=24,pady=16)
        make_pill(actions,ui('Fechar', 'Close'),dialog.destroy,variant="soft",font=FSMALL).pack(side="right")
        def worker():
            try: data=updater.check(); error=None
            except Exception as exc: data=None; error=exc
            def done():
                if not dialog.winfo_exists(): return
                if error:
                    status.config(text=ui('Não foi possível verificar agora. A leitura local continua disponível.', 'Could not check right now. Local reading remains available.'),fg=THEME["accent2"]); return
                if not data:
                    status.config(text=ui('Você já está usando a versão mais recente.', 'You are already using the latest version.'),fg=THEME["read_badge_text"]); return
                status.config(text=ui(f"Nova versão disponível: {data['version']}", f"New version available: {data['version']}"),fg=THEME["read_badge_text"])
                notes.configure(state="normal"); notes.insert("1.0",self._release_notes(data)); notes.configure(state="disabled")
                make_pill(actions,ui('Abrir downloads', 'Open downloads'),lambda:webbrowser.open(updater.safe_url(data.get("url"))),variant="accent",font=FSMALL).pack(side="right",padx=8)
            self.after(0,done)
        threading.Thread(target=worker,daemon=True).start()

    def _copy_diagnostics(self):
        api_url = getattr(api_client, "BASE_URL", "")
        parsed = urlparse(api_url)
        api_host = parsed.netloc or ui('não configurada', 'not configured')
        report = ui(
            "Komicove: Diagnóstico seguro\n",
            "Komicove: Safe diagnostics\n",
        ) + (
            f"Windows: {updater.CURRENT_VERSION}\n"
            + "Android: 0.1.0\n"
            +
            ui(f"Sistema: {platform.system()} {platform.release()} ({platform.machine()})\n",
               f"System: {platform.system()} {platform.release()} ({platform.machine()})\n")
            + f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n"
            + f"API: {api_host}\n"
            + f"7-Zip: {ui('disponível', 'available') if find_7zip() else ui('não encontrado', 'not found')}\n"
            + f"PDF: {ui('disponível', 'available') if HAS_PDF else ui('indisponível', 'unavailable')}\n"
            + f"RAR: {ui('disponível', 'available') if HAS_RAR else ui('indisponível', 'unavailable')}\n"
            +
            ui("\nNenhum token, senha, caminho local ou conteúdo de quadrinhos foi incluído.",
               "\nNo token, password, local path, or comic content was included.")
        )
        self.clipboard_clear(); self.clipboard_append(report); self.update()
        messagebox.showinfo(ui('Diagnóstico seguro', 'Safe diagnostics'), ui('Relatório copiado para a área de transferência.\n\nCole-o na issue sem adicionar tokens ou senhas.', 'Report copied to the clipboard.\n\nPaste it into the issue without adding tokens or passwords.'), parent=self)

    def _sidebar_section(self, text):
        tk.Label(self._sb, text=text, font=(_SANS, 8, "bold"), bg=THEME["surface"],
                 fg=THEME["text_dim"], anchor="w").pack(fill="x", padx=20, pady=(9, 3))

    def _sidebar_account_card(self):
        c = THEME
        card = tk.Frame(self._sb, bg=c["surface_alt"], cursor="hand2")
        card.pack(fill="x", padx=10, pady=(8, 12))
        avatar = tk.Label(card, image=ICONS.get("profile"),
                          bg=c["accent"], fg="#ffffff", width=30, height=30)
        avatar.pack(side="left", padx=(10, 8), pady=10)
        info = tk.Frame(card, bg=c["surface_alt"]); info.pack(side="left", fill="x", expand=True)
        name_label = tk.Label(info, text=getattr(self.current_user, "display_name", ui('Conta', 'Account')), font=FSMALL,
                              bg=c["surface_alt"], fg=c["text"], anchor="w")
        name_label.pack(fill="x")
        role_text = tk.Label(info, text=role_label(self.current_user), font=FTINY,
                             bg=c["surface_alt"], fg=c["text_dim"], anchor="w")
        role_text.pack(fill="x")
        logout = tk.Label(card, image=ICONS.get("logout"), bg=c["surface_alt"],
                          cursor="hand2", padx=9)
        logout.pack(side="right", fill="y")
        logout.bind("<Button-1>", lambda _e: self._logout())
        for widget in (card, avatar, info, name_label, role_text):
            widget.bind("<Button-1>", lambda _e: self._open_profile())

    def _sidebar_item(self, text, icon, cmd, *, active=False, font=FBTN, pady=11, badge=None):
        c = THEME
        W = 216
        tmp = tk.Label(self._sb, text=text, font=font)
        th = tmp.winfo_reqheight(); tmp.destroy()
        ih = icon.height() if icon else 0
        H = max(th, ih) + pady * 2
        r = 11
        cv = tk.Canvas(self._sb, width=W, height=H, bg=c["surface"],
                       highlightthickness=0, cursor="hand2", takefocus=0)
        cv.pack(padx=6, pady=2)
        def render(hover):
            cv.delete("all")
            if active:
                _rrect(cv, 1, 2, W - 1, H - 2, r, fill=c["surface_alt"])
                _rrect(cv, 2, H // 2 - 10, 5, H // 2 + 10, 2, fill=c["accent"])
                fg = c["text"]
            elif hover:
                _rrect(cv, 1, 2, W - 1, H - 2, r, fill=c["surface_hover"]); fg = c["text"]
            else:
                fg = c["text_dim"]
            x = 16
            if icon:
                cv.create_image(x, H // 2, image=icon, anchor="w"); x += icon.width() + 8
            cv.create_text(x, H // 2, text=text.strip(), font=font, fill=fg, anchor="w")
            if badge:
                badge_text = "99+" if int(badge) > 99 else str(badge)
                bx = W - 20
                _rrect(cv, bx - 14, H // 2 - 10, bx + 14, H // 2 + 10, 10,
                       fill=c["accent"])
                cv.create_text(bx, H // 2, text=badge_text, font=FTINY, fill="#ffffff")
        render(False)
        def hover(entered):
            if active:return

            animate_color(cv,"background",cv.cget("background"),c["surface_hover"] if entered else c["surface"])
        cv.bind("<Enter>", lambda e:hover(True))
        cv.bind("<Leave>", lambda e:hover(False))
        cv.bind("<Button-1>", lambda e: cmd())
        return cv

    def _refresh_library(self):
        c = THEME
        self._card_map.clear()
        if self._cover_loader: self._cover_loader.clear_queue()
        if self._search_bubble:
            try: self._search_bubble.destroy()
            except Exception as _e: log.debug("silenced: %s", _e)
            self._search_bubble = None
        try: self._main.unbind("<Configure>")
        except Exception as _e: log.debug("silenced: %s", _e)
        for w in self._main.winfo_children():
            w.destroy()

        hdr = tk.Frame(self._main, bg=c["bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(hdr, text=TEXTS[LANG]["library"], font=FTITLE, bg=c["bg"], fg=c["text"]).pack(side="left")
        if LIBRARY_FOLDER:
            short = LIBRARY_FOLDER
            if len(short) > 40: short = "…" + short[-37:]
            tk.Label(hdr, text=short, font=FTINY, bg=c["bg"], fg=c["text_muted"]).pack(side="left", padx=10, pady=(6,0))
        make_pill(hdr, ui('+  Pasta', '+  Folder'), self._choose_folder, variant="accent", font=FSMALL).pack(side="right")
        make_pill(hdr, ui('Série / Autor', 'Series / Author'), self._metadata_filters, variant="soft", font=FSMALL).pack(side="right", padx=6)

        stf = tk.Frame(self._main, bg=c["bg"]); stf.pack(fill="x", padx=20, pady=(0, 4))
        tk.Label(stf, text=f"{TEXTS[LANG]['filter_status']}:", font=FTINY,
                 bg=c["bg"], fg=c["text_dim"]).pack(side="left", padx=(0, 6))
        self._status_btns = {}
        for key, lbl in [("all", TEXTS[LANG]["f_all"]), ("unread", TEXTS[LANG]["f_unread"]),
                         ("reading", TEXTS[LANG]["f_reading"]), ("done", TEXTS[LANG]["f_done"]),
                         ("favorites", ui('★ Favoritos', '★ Favorites'))]:
            b = make_pill(stf, lbl, lambda k=key: self._set_status_filter(k),
                          variant="soft", font=FTINY, pad_x=12, pad_y=5,
                          active=(self._status_filter == key))
            b.pack(side="left", padx=(0, 4))
            self._status_btns[key] = b

        self._book_sort_controls(self._main, self._refresh_library)

        tk.Frame(self._main, bg=c["border"], height=1).pack(fill="x", padx=20, pady=(0, 4))

        sf = tk.Frame(self._main, bg=c["bg"]); sf.pack(fill="both", expand=True)
        self._lib_canvas = tk.Canvas(sf, bg=c["bg"], highlightthickness=0)
        self._lib_canvas.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(sf, orient="vertical", command=self._lib_canvas.yview)
        sb.pack(side="right", fill="y")
        self._lib_canvas.configure(yscrollcommand=sb.set)
        self._lib_content = tk.Frame(self._lib_canvas, bg=c["bg"])
        self._lib_win_id = self._lib_canvas.create_window((0, 0), window=self._lib_content, anchor="nw")

        def _update_scroll(e=None):
            self._lib_canvas.configure(scrollregion=(0, 0, self._lib_canvas.winfo_width(),
                max(self._lib_canvas.winfo_height(), self._lib_content.winfo_height())))
        self._lib_content.bind("<Configure>", _update_scroll)
        self._lib_canvas.bind("<Configure>", lambda e: (
            self._lib_canvas.itemconfig(self._lib_win_id, width=e.width), _update_scroll()))
        def _on_wheel(e): self._lib_canvas.yview_scroll(-int(e.delta/120), "units")
        self._lib_canvas.bind("<Enter>", lambda e: self._lib_canvas.bind_all("<MouseWheel>", _on_wheel))
        self._lib_canvas.bind("<Leave>", lambda e: self._lib_canvas.unbind_all("<MouseWheel>"))

        self._populate_library_grid()

        def _on_resize(e):
            if self._resize_job: self.after_cancel(self._resize_job)
            self._resize_job = self.after(350, self._check_ncols)
        self._main.bind("<Configure>", _on_resize)

        self._search_bubble = SearchBubble(self._main, self._bubble_search_changed,
                                           self._bubble_search_clear, self)
        if self._search_query:
            self._search_bubble.set_text(self._search_query)

    def _set_status_filter(self, key):
        self._status_filter = key
        self._populate_library_grid()
        for k, b in self._status_btns.items():
            b.pill_set_active(k == key)

    def _open_statistics(self):
        self._active_tab="statistics"; self._build_shell()
        for w in self._main.winfo_children(): w.destroy()
        data=personal_statistics(); c=THEME
        tk.Label(self._main,text=ui('Estatísticas pessoais','Personal statistics'),font=FTITLE,
                 bg=c['bg'],fg=c['text']).pack(anchor='w',padx=30,pady=(28,6))
        tk.Label(self._main,text=ui('Os dados ficam somente neste dispositivo.','Your data stays on this device.'),
                 font=FSMALL,bg=c['bg'],fg=c['text_dim']).pack(anchor='w',padx=30,pady=(0,24))
        row=tk.Frame(self._main,bg=c['bg']); row.pack(fill='x',padx=24)
        hours=data['seconds']//3600; minutes=(data['seconds']%3600)//60
        cards=[(ui('HQs concluídas','Completed comics'),data['completed']),
               (ui('Páginas lidas','Pages read'),data['pages']),
               (ui('Tempo de leitura','Reading time'),f"{hours}h {minutes:02d}min"),
               (ui('HQs iniciadas','Started comics'),data['started'])]
        for title,value in cards:
            card=tk.Frame(row,bg=c['surface'],highlightthickness=1,highlightbackground=c['border'])
            card.pack(side='left',fill='x',expand=True,padx=7)
            tk.Label(card,text=str(value),font=("Segoe UI",26,"bold"),bg=c['surface'],fg=c['accent']).pack(pady=(22,5))
            tk.Label(card,text=title,font=FBTN,bg=c['surface'],fg=c['text']).pack(pady=(0,22))

    def _bubble_search_changed(self, val):
        self._search_query = val
        self._populate_library_grid()
    def _bubble_search_clear(self):
        self._search_query = ""
        self._populate_library_grid()

    def _status_of(self, path):
        ms = get_manual_status(path)
        if ms in ("reading", "done"):
            return ms
        page = get_progress_page(path)
        if page is None: return "unread"
        try:
            be = ArchiveBackend(path)
            total = be.count
            be.close()
        except Exception as _e:
            log.debug("silenced: %s", _e)
            total = 0
        if total and page >= total - 1: return "done"
        return "reading"

    def _metadata_filters(self):
        dialog = tk.Toplevel(self)
        dialog.title(ui('Filtrar biblioteca', 'Filter library'))
        dialog.configure(bg=THEME["bg"])
        fields = {}
        files = self._scan()
        for key, label in [("series", ui('Série', 'Series')), ("writer", ui('Autor', 'Author'))]:
            tk.Label(dialog, text=label, bg=THEME["bg"], fg=THEME["text"]).pack(padx=20, pady=(12, 4))
            choices = sorted({get_comic_info(path).get(key, "") for path in files} - {""})
            entry = ttk.Combobox(dialog, values=[""] + choices, state="readonly", width=40)
            entry.set(getattr(self, "_metadata_filter_" + key, ""))
            entry.pack(padx=20, pady=4)
            fields[key] = entry
        def apply(clear=False):
            for key, entry in fields.items():
                setattr(self, "_metadata_filter_" + key, "" if clear else entry.get())
            dialog.destroy()
            self._populate_library_grid()
        tk.Button(dialog, text=ui('Aplicar filtros', 'Apply filters'), command=apply).pack(pady=12)
        tk.Button(dialog, text=ui('Limpar filtros', 'Clear filters'), command=lambda: apply(True)).pack(pady=(0, 12))

    def _populate_library_grid(self):
        c = THEME
        for w in self._lib_content.winfo_children():
            w.destroy()
        self._card_map.clear()

        arquivos = self._scan()

        for field in ("series", "writer"):
            selected = getattr(self, "_metadata_filter_" + field, "")
            if selected:
                arquivos = [path for path in arquivos if get_comic_info(path).get(field, "") == selected]

        prog = load_progress()
        continuar = []
        for p in arquivos:
            entry = prog.get(p)
            if entry is not None:
                ts = entry.get("ts", 0) if isinstance(entry, dict) else 0
                continuar.append((ts, p))
        continuar.sort(reverse=True)
        continuar = [p for _, p in continuar[:6]]

        q = self._search_query.strip().lower()
        if q:
            def _match(p):
                if q in Path(p).stem.lower(): return True
                info = get_comic_info(p)
                return any(q in info.get(f, "").lower()
                           for f in ("title", "series", "writer", "publisher", "genre"))
            arquivos = [p for p in arquivos if _match(p)]

        if self._status_filter == "favorites":
            arquivos = [p for p in arquivos if is_favorite(p)]
        elif self._status_filter != "all":
            arquivos = [p for p in arquivos if self._status_of(p) == self._status_filter]

        arquivos = sort_comics(arquivos, self._book_sort, prog)

        if not arquivos and not continuar:
            self._show_empty(self._lib_content, no_results=bool(q))
            return

        self.update_idletasks()
        avail = self._main.winfo_width() - 44
        if avail < 50:
            self.after(200, self._populate_library_grid); return
        card_w = CAPA_W + 24 + GPAD * 2
        ncols = max(2, avail // card_w)
        self._last_ncols = ncols

        if continuar and not q and self._status_filter == "all":
            tk.Label(self._lib_content, text=f"▶  {TEXTS[LANG]['continue_section']}",
                     font=FBTN, bg=c["bg"], fg=c["text_dim"], anchor="w").pack(
                fill="x", padx=GPAD+4, pady=(8, 2))
            cg = tk.Frame(self._lib_content, bg=c["bg"]); cg.pack(padx=GPAD, anchor="nw")
            for i, path in enumerate(continuar):
                card = ComicCard(cg, path, None, self._open, self,
                                 label_override=comic_display_title(path))
                card.grid(row=0, column=i, padx=GPAD//2, pady=GPAD//2)
                self._wire_card(card, path)
            tk.Frame(self._lib_content, bg=c["border"], height=1).pack(fill="x", padx=GPAD, pady=8)

        gf = tk.Frame(self._lib_content, bg=c["bg"])
        gf.pack(padx=GPAD, pady=GPAD, anchor="nw")
        for placed, path in enumerate(arquivos):
            row, col = placed // ncols, placed % ncols
            card = ComicCard(gf, path, None, self._open, self,
                             label_override=comic_display_title(path))
            card.grid(row=row, column=col, padx=GPAD//2, pady=GPAD//2)
            self._card_map[path] = card
            self._wire_card(card, path)

    def _wire_card(self, card, path):
        custom_cover = get_comic_info(path).get('cover')
        if self._meta_tooltip:
            tt = self._meta_tooltip
            card.cv.bind("<Enter>",  lambda e, p=path, w=card.cv: tt.show(w, p), add="+")
            card.cv.bind("<Leave>",  lambda e: tt.hide(), add="+")
            card.lbl.bind("<Enter>", lambda e, p=path, w=card.cv: tt.show(w, p), add="+")
            card.lbl.bind("<Leave>", lambda e: tt.hide(), add="+")
        def _on_loaded(p, pil, _card=card):
            if custom_cover:
                try:
                    with Image.open(custom_cover) as source:
                        pil = source.convert('RGB')
                except (OSError, ValueError): pass
            try: _card.set_image(pil)
            except Exception: pass
        self._cover_loader.request(path, _on_loaded)

    def _check_ncols(self):
        self._resize_job = None
        avail = self._main.winfo_width() - 44
        if avail < 50: return
        card_w = CAPA_W + 24 + GPAD * 2
        nc = max(2, avail // card_w)
        if nc != self._last_ncols:
            self._populate_library_grid()

    def _show_empty(self, parent, no_results=False):
        c = THEME
        f = tk.Frame(parent, bg=c["bg"]); f.pack(pady=80)
        if no_results:
            tk.Label(f, text="🔍", font=("Segoe UI Emoji", 42), bg=c["bg"], fg=c["text_muted"]).pack(pady=(20, 6))
            tk.Label(f, text=f'{TEXTS[LANG]["no_results"]} "{self._search_query}"',
                     font=FLABEL, bg=c["bg"], fg=c["text_dim"]).pack()
            make_pill(f, ui('✕  Limpar busca', '✕  Clear search'), self._bubble_search_clear,
                      variant="soft", font=FBTN, pad_x=18, pad_y=9).pack(pady=12)
        else:
            tk.Label(f, text="📚", font=("Segoe UI Emoji", 42), bg=c["bg"], fg=c["text_muted"]).pack(pady=(20, 6))
            tk.Label(f, text=TEXTS[LANG]["no_comics"], font=FLABEL, bg=c["bg"], fg=c["text_dim"]).pack()
            make_pill(f, TEXTS[LANG]["add_folder"], self._choose_folder,
                      variant="accent", font=FBTN, pad_x=22, pad_y=11).pack(pady=16)

    def _scan(self):
        from komicove_app.archive import SUPPORTED_EXTENSIONS
        exts = SUPPORTED_EXTENSIONS
        if not LIBRARY_FOLDER or not os.path.isdir(LIBRARY_FOLDER):
            return []
        return sorted([os.path.join(LIBRARY_FOLDER, f)
                       for f in os.listdir(LIBRARY_FOLDER)
                       if f.lower().endswith(exts) and os.path.isfile(os.path.join(LIBRARY_FOLDER, f))],
                      key=natural_key)

    def _book_sort_controls(self, parent, refresh):
        c = THEME
        row = tk.Frame(parent, bg=c["bg"])
        row.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(row, text=ui("Ordenar:", "Sort:"), font=FTINY,
                 bg=c["bg"], fg=c["text_dim"]).pack(side="left", padx=(0, 6))
        for key, label in (("recent", ui("Recentes", "Recent")),
                           ("title", ui("Título A-Z", "Title A-Z")),
                           ("title_desc", ui("Título Z-A", "Title Z-A")),
                           ("series", ui("Série e título", "Series and title"))):
            make_pill(row, label, lambda k=key: self._set_book_sort(k, refresh),
                      variant="soft", font=FTINY, pad_x=10, pad_y=4,
                      active=(self._book_sort == key)).pack(side="left", padx=(0, 4))

    def _set_book_sort(self, mode, refresh):
        self._book_sort = mode
        save_prefs(book_sort=mode)
        refresh()

    def _open(self, path, sibling_list=None):
        try:
            loader = SmartPageLoader(path)
        except Exception as e:
            messagebox.showerror(TEXTS[LANG]["error"], str(e)); return
        if loader.count == 0:
            messagebox.showerror(TEXTS[LANG]["error"], ui('Sem imagens.', 'No images.')); return

        if sibling_list is None:
            sibling_list = self._siblings_of(path)

        def on_finish(cur_path):
            try:
                i = sibling_list.index(cur_path)
                if i + 1 < len(sibling_list):
                    self._open(sibling_list[i + 1], sibling_list)
            except (ValueError, IndexError):
                pass

        has_next = False
        try:
            i = sibling_list.index(path)
            has_next = (i + 1 < len(sibling_list))
        except ValueError:
            pass

        ReaderWindow(self, path, loader, on_finish=on_finish if has_next else None)

    def _siblings_of(self, path):
        pass
        folder = os.path.dirname(path)
        same_dir = self._scan() if folder == LIBRARY_FOLDER else sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith(SUPPORTED_EXTENSIONS)
            and os.path.isfile(os.path.join(folder, f))], key=natural_key)
        if folder == LIBRARY_FOLDER:
            key = _serie_name(os.path.basename(path))
            serie = sorted([p for p in same_dir
                            if _serie_name(os.path.basename(p)) == key], key=natural_key)
            if len(serie) >= 2:
                return serie
        return same_dir

    def _do_backup(self):
        path = filedialog.asksaveasfilename(
            title=ui('Exportar backup', 'Export backup'), defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="komicove_backup.json")
        if path:
            try:
                export_backup(path)
                messagebox.showinfo("Backup", ui(f"Backup salvo em:\n{path}", f"Backup saved to:\n{path}"))
            except Exception as e:
                messagebox.showerror(TEXTS[LANG]["error"], str(e))

    def _do_restore(self):
        path = filedialog.askopenfilename(
            title=ui('Importar backup', 'Import backup'), filetypes=[("JSON", "*.json")])
        if path:
            try:
                import_backup(path)
                messagebox.showinfo(ui('Restaurar', 'Restore'), ui('Backup importado com sucesso!', 'Backup imported successfully!'))
                self._refresh_library()
            except Exception as e:
                messagebox.showerror(TEXTS[LANG]["error"], str(e))

    def _choose_folder(self):
        p = filedialog.askdirectory(title=TEXTS[LANG]["choose_library_folder"],
                                    initialdir=LIBRARY_FOLDER if LIBRARY_FOLDER else None)
        if p:
            save_library_config(p)
            self._sync_shared_settings()
            self._capa_cache.clear()
            _COMIC_INFO_CACHE.clear()
            self._search_query = ""
            self._refresh_library()

    def _show_collections(self):
        if self._search_bubble:
            try: self._search_bubble.destroy()
            except Exception as _e: log.debug("silenced: %s", _e)
            self._search_bubble = None
        c = THEME
        try: self._main.unbind("<Configure>")
        except Exception as _e: log.debug("silenced: %s", _e)
        for w in self._main.winfo_children():
            w.destroy()
        hdr = tk.Frame(self._main, bg=c["bg"]); hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text=TEXTS[LANG]["collections"], font=FTITLE, bg=c["bg"], fg=c["text"]).pack(side="left")
        ctrl = tk.Frame(self._main, bg=c["bg"]); ctrl.pack(fill="x", padx=20, pady=(8, 0))
        tabs = tk.Frame(ctrl, bg=c["bg"]); tabs.pack(side="left")
        self._filter_btns = {}
        for key, label in [("all", TEXTS[LANG]["all"]), ("subfolders", TEXTS[LANG]["subfolders"]),
                           ("series", TEXTS[LANG]["series"])]:
            btn = make_pill(tabs, label, lambda k=key: self._set_col_filter(k),
                            variant="soft", font=FSMALL, pad_x=14, pad_y=6,
                            active=(self._col_filter == key))
            btn.pack(side="left", padx=(0, 5)); self._filter_btns[key] = btn
        srt = tk.Frame(ctrl, bg=c["bg"]); srt.pack(side="right")
        tk.Label(srt, text=TEXTS[LANG]["sort_by"], font=FTINY, bg=c["bg"], fg=c["text_dim"]).pack(side="left", padx=(0, 6))
        self._sort_btns = {}
        for key, label in [("name", TEXTS[LANG]["sort_name"]), ("date", TEXTS[LANG]["sort_date"]),
                           ("progress", TEXTS[LANG]["sort_progress"])]:
            btn = make_pill(srt, label, lambda k=key: self._set_col_sort(k),
                            variant="soft", font=FTINY, pad_x=10, pad_y=6,
                            active=(self._col_sort == key))
            btn.pack(side="left", padx=(0, 3)); self._sort_btns[key] = btn
        tk.Frame(self._main, bg=c["border"], height=1).pack(fill="x", padx=20, pady=(8, 4))
        self._col_scroll_area(self._main)

    def _col_scroll_area(self, parent):
        c = THEME
        if hasattr(self, "_col_sf") and self._col_sf.winfo_exists():
            self._col_sf.destroy()
        sf = tk.Frame(parent, bg=c["bg"]); sf.pack(fill="both", expand=True); self._col_sf = sf
        cv = tk.Canvas(sf, bg=c["bg"], highlightthickness=0); cv.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(sf, orient="vertical", command=cv.yview); sb.pack(side="right", fill="y")
        cv.configure(yscrollcommand=sb.set)
        content = tk.Frame(cv, bg=c["bg"])
        wid = cv.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(wid, width=e.width))
        def _on_wheel(e): cv.yview_scroll(-int(e.delta / 120), "units")
        cv.bind("<Enter>", lambda e: cv.bind_all("<MouseWheel>", _on_wheel))
        cv.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))

        cols = scan_collections(LIBRARY_FOLDER)
        aliases = load_prefs().get("collection_aliases", {})
        for kind in ("subfolders", "series"):
            for item in cols[kind]:
                source = item["path"] if kind == "subfolders" else item["name"]
                item["alias_key"] = f"{kind}:{source}"
                item["name"] = aliases.get(item["alias_key"], item["name"])
        subfolders = _sort_collections(cols["subfolders"], self._col_sort)
        series = _sort_collections(cols["series"], self._col_sort)
        show_sub = self._col_filter in ("all", "subfolders")
        show_ser = self._col_filter in ("all", "series")

        if not (subfolders and show_sub) and not (series and show_ser):
            f = tk.Frame(content, bg=c["bg"]); f.pack(pady=80)
            tk.Label(f, text="🗂️", font=("Segoe UI Emoji", 42), bg=c["bg"], fg=c["text_muted"]).pack(pady=(20, 6))
            tk.Label(f, text=TEXTS[LANG]["no_collections"], font=FLABEL, bg=c["bg"], fg=c["text_dim"]).pack()
            return

        self.update_idletasks()
        avail = self._main.winfo_width() - 44
        if avail < 50:
            self.after(200, lambda: self._col_scroll_area(parent)); return
        card_w = CAPA_W + 60 + GPAD * 2
        ncols = max(2, avail // card_w)

        def _section(par, title, items):
            tk.Label(par, text=title, font=FBTN, bg=c["bg"], fg=c["text_dim"],
                     anchor="w", padx=4).pack(fill="x", padx=GPAD, pady=(12, 4))
            tk.Frame(par, bg=c["border"], height=1).pack(fill="x", padx=GPAD, pady=(0, 6))
            gf = tk.Frame(par, bg=c["bg"]); gf.pack(padx=GPAD, pady=(0, GPAD), anchor="nw")
            for i, item in enumerate(items):
                row, col = i // ncols, i % ncols
                card = CollectionCard(gf, item, open_cb=self._open,
                                      detail_cb=self._show_collection_detail,
                                      rename_cb=self._rename_collection, root=self)
                card.grid(row=row, column=col, padx=GPAD//2, pady=GPAD//2)
        if show_sub and subfolders: _section(content, f"📁  {TEXTS[LANG]['subfolders']}", subfolders)
        if show_ser and series:     _section(content, f"📚  {TEXTS[LANG]['series']}", series)

    def _set_col_filter(self, key): self._col_filter = key; self._show_collections()
    def _set_col_sort(self, key):   self._col_sort = key; self._show_collections()

    def _rename_collection(self, collection, *, show_detail=False):
        name = simpledialog.askstring(
            ui("Renomear coleção", "Rename collection"),
            ui("Novo nome exibido da coleção:", "New displayed collection name:"),
            initialvalue=collection["name"], parent=self)
        if name is None:
            return
        name = name.strip()
        if not name or len(name) > 80:
            messagebox.showwarning(
                ui("Nome inválido", "Invalid name"),
                ui("Use um nome de 1 a 80 caracteres.", "Use a name with 1 to 80 characters."),
                parent=self)
            return
        aliases = load_prefs().get("collection_aliases", {})
        aliases[collection["alias_key"]] = name
        save_prefs(collection_aliases=aliases)
        collection["name"] = name
        if show_detail:
            self._show_collection_detail(collection)
        else:
            self._show_collections()

    def _show_collection_detail(self, collection):
        c = THEME
        try: self._main.unbind("<Configure>")
        except Exception as _e: log.debug("silenced: %s", _e)
        for w in self._main.winfo_children():
            w.destroy()
        files = sort_comics(collection["files"], self._book_sort)
        lidas, total, ultima = collection_read_count(files)

        hdr = tk.Frame(self._main, bg=c["bg"]); hdr.pack(fill="x", padx=20, pady=(16, 6))
        make_pill(hdr, f"◀  {TEXTS[LANG]['back_collections']}", self._show_collections,
                  variant="soft", font=FSMALL).pack(side="left", padx=(0, 14))
        tk.Label(hdr, text=collection["name"], font=FTITLE, bg=c["bg"], fg=c["text"]).pack(side="left")
        n = len(files)
        tk.Label(hdr, text=f"{n} {TEXTS[LANG]['issues']}{'s' if n != 1 else ''}",
                 font=FTINY, bg=c["bg"], fg=c["text_muted"]).pack(side="left", padx=10, pady=(6, 0))
        make_pill(hdr, ui("Renomear", "Rename"),
                  lambda: self._rename_collection(collection, show_detail=True),
                  variant="soft", font=FSMALL).pack(side="right", padx=(6, 0))
        if ultima:
            make_pill(hdr, f"▶  {TEXTS[LANG]['continue_reading']}",
                      lambda: self._open(ultima, files), variant="accent", font=FSMALL).pack(side="right")

        prog_row = tk.Frame(self._main, bg=c["bg"]); prog_row.pack(fill="x", padx=20, pady=(0, 4))
        if total > 0:
            pct = lidas / total
            bar_w_full, bar_h = 300, 8
            pbar = tk.Canvas(prog_row, width=bar_w_full, height=bar_h, bg=c["bg"], highlightthickness=0)
            pbar.pack(side="left", pady=4)
            r = bar_h // 2
            _rrect(pbar, 0, 0, bar_w_full, bar_h, r, fill=c["progress_bg"])
            filled = int(bar_w_full * pct)
            if filled > r * 2: _rrect(pbar, 0, 0, filled, bar_h, r, fill=c["accent"])
            elif filled > 0: pbar.create_oval(0, 0, bar_h, bar_h, fill=c["accent"], outline="")
            tk.Label(prog_row, text=f"  {lidas}/{total} {TEXTS[LANG]['read']}  ({int(pct*100)}%)",
                     font=FTINY, bg=c["bg"], fg=c["text_dim"]).pack(side="left", padx=6)

        self._book_sort_controls(self._main, lambda: self._show_collection_detail(collection))

        tk.Frame(self._main, bg=c["border"], height=1).pack(fill="x", padx=20, pady=(0, 4))
        sf = tk.Frame(self._main, bg=c["bg"]); sf.pack(fill="both", expand=True)
        cvd = tk.Canvas(sf, bg=c["bg"], highlightthickness=0); cvd.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(sf, orient="vertical", command=cvd.yview); sb2.pack(side="right", fill="y")
        cvd.configure(yscrollcommand=sb2.set)
        content = tk.Frame(cvd, bg=c["bg"])
        wid = cvd.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: cvd.configure(scrollregion=cvd.bbox("all")))
        cvd.bind("<Configure>", lambda e: cvd.itemconfig(wid, width=e.width))
        def _on_wheel(e): cvd.yview_scroll(-int(e.delta / 120), "units")
        cvd.bind("<Enter>", lambda e: cvd.bind_all("<MouseWheel>", _on_wheel))
        cvd.bind("<Leave>", lambda e: cvd.unbind_all("<MouseWheel>"))

        self.update_idletasks()
        avail = self._main.winfo_width() - 44
        card_w = CAPA_W + 24 + GPAD * 2
        ncols = max(2, avail // card_w)
        gf = tk.Frame(content, bg=c["bg"]); gf.pack(padx=GPAD, pady=GPAD, anchor="nw")
        prog = load_progress()
        for i, fpath in enumerate(files):
            row, col = i // ncols, i % ncols
            info = get_comic_info(fpath)
            stem = Path(fpath).stem
            if info.get("number"):
                label = f"#{info['number']}"
                if info.get("title"): label += f": {info['title']}"
            elif info.get("title"): label = info["title"]
            else: label = stem
            if len(label) > 22: label = label[:20] + "…"
            page = get_progress_page(fpath)
            if page is not None and page > 0: label = f"✓ {label}"
            card = ComicCard(gf, fpath, None,
                             lambda p, fl=files: self._open(p, fl), self, label_override=label)
            card.grid(row=row, column=col, padx=GPAD//2, pady=GPAD//2)
            if self._meta_tooltip:
                tt = self._meta_tooltip
                card.cv.bind("<Enter>", lambda e, p=fpath, w=card.cv: tt.show(w, p), add="+")
                card.cv.bind("<Leave>", lambda e: tt.hide(), add="+")
            if page is not None and page > 0:
                tk.Frame(card.frame, bg=c["read_badge_text"], width=6, height=6).place(
                    relx=0.5, rely=1.0, anchor="s", y=-2)
            def _on_loaded(p, pil, _card=card):
                try: _card.set_image(pil)
                except Exception as _e: log.debug("silenced: %s", _e)
            self._cover_loader.request(fpath, _on_loaded)

    def _toggle_theme(self):
        toggle_theme()
        self._sync_shared_settings()
        save_prefs(dark=_runtime.IS_DARK)
        apply_scrollbar_style()
        self._capa_cache.clear()
        if self._search_bubble:
            self._search_query = self._search_bubble.get_text()
            try: self._search_bubble.destroy()
            except Exception: pass
            self._search_bubble = None
        self._build_shell()
        self.after(200, self._refresh_library)
