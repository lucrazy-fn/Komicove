from komicove_app.runtime import *
from komicove_app.archive import ArchiveBackend, SUPPORTED_EXTENSIONS, find_7zip
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
from komicove_app.statistics_views import render_statistics
from komicove_app.notifications_views import render_notifications
from komicove_app.design.fonts import body as design_body, caption as design_caption, heading as design_heading
from komicove_app.design.spacing import CONTENT_PADDING, SIDEBAR_WIDTH
from komicove_app.design.icons import lucide_icon
from komicove_app.design.styles import (
    KomicoveButton, KomicoveCard, KomicoveEmptyState, KomicoveInput,
    KomicoveSidebarItem, _rounded_rect,
)
import webbrowser
import platform, sys, threading
from PIL import ImageOps, ImageEnhance, ImageDraw
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
        self._collection_query = ""
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
        self._session_expiry_handled = False
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
                "statistics": self._open_statistics,
                "submissions": self._open_my_publications,
                "notifications": self._open_notifications,
                "moderation": self._open_moderation,
                "profile": self._open_profile,
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
        self._session_expiry_handled = False
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
            except api_client.ApiAuthError:
                session_store.clear_session()
                self.after(0, lambda: self._finish_expired_session(auth.token))
            except api_client.ApiUnavailableError as exc:
                log.debug("%s: %s", ui('Sincronização da biblioteca indisponível', 'Library sync unavailable'), exc)
            except api_client.ApiServerError as exc:
                log.warning("%s: %s", ui('Falha ao sincronizar a biblioteca', 'Library sync failed'), exc)
            except Exception:
                log.debug(ui('Sincronização da biblioteca indisponível', 'Library sync unavailable'), exc_info=True)
        threading.Thread(target=worker, daemon=True).start()

    def _finish_expired_session(self, token):
        current = self.current_user
        if current is None or getattr(current, "token", None) != token:
            return
        if self._session_expiry_handled:
            return
        self._session_expiry_handled = True
        self.current_user = None
        self._sync_job = None
        if hasattr(self, "_main") and self._main.winfo_exists():
            self._active_tab = "library"
            self._build_shell()
            self._refresh_library()
        messagebox.showwarning(
            ui('Sessão expirada', 'Session expired'),
            ui(
                'Sua sessão expirou. A biblioteca local continua disponível. Entre novamente para sincronizar.',
                'Your session expired. Your local library remains available. Sign in again to sync.',
            ),
            parent=self,
        )

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
            self._open_discovery,
        )

    def _set_notification_count(self, count):
        self._notification_count = max(0, int(count or 0))
        item = getattr(self, "_notifications_nav_item", None)
        if item is not None and item.winfo_exists():
            item.badge = self._notification_count or None
            item._draw(False)

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
        render_downloads(
            self._main, THEME, (FTITLE, FLABEL, FSMALL),
            resource_path=resource_path, on_discover=self._open_discovery,
            on_choose_folder=self._choose_library_folder_from_downloads,
            on_metadata_filters=self._open_library_metadata_filters,
            make_filter=make_pill,
        )

    def _choose_library_folder_from_downloads(self):
        self._go_library()
        self._choose_folder()

    def _open_library_metadata_filters(self):
        self._go_library()
        self._metadata_filters()

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
        self._moderation_generation = getattr(self, "_moderation_generation", 0) + 1
        generation = self._moderation_generation
        for child in self._main.winfo_children():
            child.destroy()
        self._moderation_images = []
        self._moderation_filter = getattr(self, "_moderation_filter", "pending_review")
        self._moderation_query = ""
        self._moderation_items = []
        header = tk.Frame(self._main, bg=THEME["bg"])
        header.pack(fill="x", padx=28, pady=(20, 10))
        tk.Label(header, text=ui('Moderação', 'Moderation'), font=design_heading(29), bg=THEME["bg"],
                 fg=THEME["text"]).pack(side="left")
        search = KomicoveInput(header, THEME,
                               placeholder=ui('Buscar obras, autores…', 'Search titles, authors…'),
                               width=520, on_change=self._moderation_search_changed)
        search.pack(side="left", fill="x", expand=True, padx=(26, 18))
        KomicoveButton(header, ui('Denúncias', 'Reports'), self._render_reports_tab,
                       THEME, kind="secondary", compact=True).pack(side="right")
        KomicoveButton(header, ui('Atualizar', 'Refresh'), self._render_moderation_tab,
                       THEME, kind="secondary", compact=True).pack(side="right", padx=(0, 8))
        if getattr(self.current_user, "role", "user") == "moderator":
            make_pill(header, ui('Usar token de administrador', 'Use administrator token'), self._claim_admin_token,
                      variant="accent", font=FSMALL, pad_x=12, pad_y=7).pack(side="right", padx=8)
        filters = tk.Frame(self._main, bg=THEME["bg"])
        filters.pack(fill="x", padx=28, pady=(2, 10))
        self._moderation_filter_buttons = {}
        counts = {
            "pending_review": sum(item.get("status") == "pending_review" for item in self._moderation_items),
            "approved": sum(item.get("status") == "approved" for item in self._moderation_items),
            "rejected": sum(item.get("status") == "rejected" for item in self._moderation_items),
            "all": len(self._moderation_items),
        }
        for value, pt, en in (
            ("pending_review", "Pendentes", "Pending"),
            ("approved", "Aprovados", "Approved"),
            ("rejected", "Rejeitados", "Rejected"),
            ("all", "Todos", "All"),
        ):
            button = KomicoveButton(
                filters, f"{ui(pt, en)} ({counts[value]})",
                lambda chosen=value: self._set_moderation_filter(chosen),
                THEME, kind="primary" if value == self._moderation_filter else "secondary",
                compact=False, min_width=150,
                icon_name={"pending_review": "refresh-cw", "approved": "check",
                           "rejected": "x", "all": "grid-2x2"}[value],
            )
            button.pack(side="left", padx=(0, 8))
            self._moderation_filter_buttons[value] = button

        self._moderation_status = tk.Label(
            filters, text=ui('Carregando pedidos…', 'Loading requests…'), font=FSMALL,
            bg=THEME["bg"], fg=THEME["text_dim"],
        )
        self._moderation_status.pack(side="right")

        self._moderation_hero = tk.Canvas(self._main, height=216, bg=THEME["bg"],
                                          highlightthickness=0, bd=0)
        self._moderation_hero.pack(fill="x", padx=28, pady=(0, 10))
        self._moderation_hero.bind("<Configure>", lambda _event: self._paint_moderation_hero())

        canvas = tk.Canvas(self._main, bg=THEME["bg"], highlightthickness=0)
        self._moderation_canvas = canvas
        scrollbar = ttk.Scrollbar(self._main, orient="vertical", command=canvas.yview)
        self._moderation_grid = tk.Frame(canvas, bg=THEME["bg"])
        grid_window = canvas.create_window(
            (0, 0), window=self._moderation_grid, anchor="nw"
        )

        def sync_moderation_view(_event=None):
            if not canvas.winfo_exists() or not self._moderation_grid.winfo_exists():
                return
            width = max(1, canvas.winfo_width())
            canvas.itemconfigure(grid_window, width=width)
            self._moderation_grid.update_idletasks()
            content_height = self._moderation_grid.winfo_reqheight()
            viewport_height = max(1, canvas.winfo_height())
            canvas.configure(scrollregion=(0, 0, width, max(content_height, viewport_height)))
            if content_height <= viewport_height:
                canvas.yview_moveto(0)

        self._moderation_grid.bind("<Configure>", sync_moderation_view)
        canvas.bind("<Configure>", sync_moderation_view)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=(20, 0), pady=(0, 12))
        def moderation_wheel(event):
            try:
                if (self._active_tab != "moderation" or not canvas.winfo_exists()
                        or self._moderation_grid.winfo_reqheight() <= canvas.winfo_height()):
                    return
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            except tk.TclError:
                return
        canvas.bind_all("<MouseWheel>", moderation_wheel)

        def worker():
            try:
                outcome = (api_client.moderation_queue(
                    self.current_user.token, include_decided=True
                ), None)
            except Exception as exc:
                outcome = (None, str(exc))
            try:
                self.after(0, lambda: self._moderation_loaded(*outcome, generation=generation))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _moderation_search_changed(self, value):
        self._moderation_query = (value or "").strip().casefold()
        self._render_moderation_results()

    def _set_moderation_filter(self, value):
        self._moderation_filter = value
        self._render_moderation_tab()

    def _paint_moderation_hero(self):
        hero = getattr(self, "_moderation_hero", None)
        if hero is None or not hero.winfo_exists():
            return
        width = max(600, hero.winfo_width())
        hero.delete("all")
        try:
            source = Image.open(resource_path("assets_redesign/banners/library_noir.png")).convert("RGB")
            art = ImageOps.fit(source, (width - 4, 208), Image.LANCZOS).convert("RGBA")
            art = ImageEnhance.Brightness(art).enhance(.46)
            mask = Image.new("L", art.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, art.width - 1, art.height - 1), radius=18, fill=255,
            )
            art.putalpha(mask)
            self._moderation_hero_photo = ImageTk.PhotoImage(art)
            hero.create_image(2, 2, image=self._moderation_hero_photo, anchor="nw")
        except Exception:
            _rounded_rect(hero, 2, 2, width - 2, 210, 18,
                          fill=THEME["surface"], outline="")
        _rounded_rect(hero, 2, 2, width - 2, 210, 18,
                      fill="", outline=THEME["accent"])
        hero.create_text(27, 37, text="›", anchor="w", font=design_heading(31),
                         fill=THEME["accent"])
        hero.create_text(52, 39, text=ui('Revisão de Conteúdo', 'Content Review'),
                         anchor="w", font=design_heading(22), fill=THEME["text"])
        hero.create_text(52, 72,
                         text=ui('Analise as obras enviadas pela comunidade e mantenha\no Komicove seguro e incrível para todos.',
                                 'Review community submissions and keep\nKomicove safe and welcoming for everyone.'),
                         anchor="w", font=design_body(11), fill=THEME["text_dim"])
        items = getattr(self, "_moderation_items", [])
        counts = {
            "pending_review": sum(item.get("status") == "pending_review" for item in items),
            "approved": sum(item.get("status") == "approved" for item in items),
            "rejected": sum(item.get("status") == "rejected" for item in items),
        }
        for index, (status, pt, en) in enumerate((
            ("pending_review", "Pendentes", "Pending"),
            ("approved", "Aprovados", "Approved"),
            ("rejected", "Rejeitados", "Rejected"),
        )):
            x = 48 + index * 145
            hero.create_text(x, 151, text=str(counts[status]), anchor="w",
                             font=design_heading(25),
                             fill=THEME["accent2"] if status != "approved" else "#44d483")
            hero.create_text(x, 181, text=ui(pt, en), anchor="w", font=design_body(10),
                             fill=THEME["text_dim"])
            if index < 2:
                hero.create_line(x + 104, 139, x + 104, 188, fill=THEME["border"])

    def _render_moderation_results(self):
        grid = getattr(self, "_moderation_grid", None)
        if grid is None or not grid.winfo_exists():
            return
        for child in grid.winfo_children():
            child.destroy()
        items = list(getattr(self, "_moderation_items", []))
        selected = getattr(self, "_moderation_filter", "pending_review")
        if selected != "all":
            items = [item for item in items if item.get("status") == selected]
        query = getattr(self, "_moderation_query", "")
        if query:
            items = [item for item in items if query in
                     f"{item.get('title', '')} {item.get('author', '')}".casefold()]
        if not items:
            tk.Label(grid, text=ui('Nenhum pedido neste filtro.', 'No requests in this filter.'),
                     font=FTITLE, bg=THEME["bg"], fg=THEME["text_dim"]).grid(
                         row=0, column=0, padx=40, pady=70)
            return
        for column in range(4):
            grid.grid_columnconfigure(column, weight=1, uniform="moderation")
        for index, item in enumerate(items):
            self._create_moderation_card(item, index // 4, index % 4)
        canvas = getattr(self, "_moderation_canvas", None)
        if canvas is not None and canvas.winfo_exists():
            grid.update_idletasks()
            width = max(1, canvas.winfo_width())
            content_height = grid.winfo_reqheight()
            viewport_height = max(1, canvas.winfo_height())
            canvas.configure(scrollregion=(0, 0, width, max(content_height, viewport_height)))
            canvas.yview_moveto(0)

    def _render_reports_tab(self):
        self._moderation_generation = getattr(self, "_moderation_generation", 0) + 1
        for child in self._main.winfo_children(): child.destroy()
        tk.Label(self._main,text=ui('Denúncias', 'Reports'),font=FTITLE,bg=THEME["bg"],fg=THEME["text"]).pack(anchor="w",padx=28,pady=(24,8))
        status=tk.Label(self._main,text=ui('Carregando…', 'Loading…'),font=FSMALL,bg=THEME["bg"],fg=THEME["text_dim"]);status.pack(anchor="w",padx=28)
        area=tk.Frame(self._main,bg=THEME["bg"]);area.pack(fill="both",expand=True,padx=28,pady=12)
        def worker():
            try: result,error=api_client.admin_reports(self.current_user.token),None
            except Exception as exc: result,error=None,str(exc)
            def done(items,error):
                if not status.winfo_exists() or not area.winfo_exists():
                    return
                status.config(text=error or ui(f"{len(items)} denúncia(s)", f"{len(items)} report(s)"),fg=THEME["accent2"] if error else THEME["text_dim"])
                if error:return
                for item in items:
                    card=tk.Frame(area,bg=THEME["surface"],padx=14,pady=10);card.pack(fill="x",pady=5)
                    tk.Label(card,text=f"{item['target_type']} · {item['reason']} · {item['status']}",font=FLABEL,bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w")
                    tk.Label(card,text=item.get("description") or ui('Sem descrição', 'No description'),font=FSMALL,bg=THEME["surface"],fg=THEME["text_dim"],wraplength=850,justify="left").pack(anchor="w")
            try:
                self.after(0,lambda:done(result,error))
            except (RuntimeError, tk.TclError):
                pass
        threading.Thread(target=worker,daemon=True).start()

    def _moderation_loaded(self, items, error, generation=None):
        if (generation is not None and generation != self._moderation_generation) or self._active_tab != "moderation":
            return
        try:
            if not self._moderation_status.winfo_exists() or not self._moderation_grid.winfo_exists():
                return
        except tk.TclError:
            return
        if error:
            self._moderation_status.config(text=error, fg=THEME["accent2"])
            return
        pending = sum(item.get("status") == "pending_review" for item in items)
        self._moderation_items = list(items)
        self._moderation_status.config(
            text=ui(f"{len(items)} pedido(s) no histórico · {pending} pendente(s)",
                    f"{len(items)} request(s) in history · {pending} pending")
        )
        counts = {
            "pending_review": pending,
            "approved": sum(item.get("status") == "approved" for item in items),
            "rejected": sum(item.get("status") == "rejected" for item in items),
            "all": len(items),
        }
        labels = {
            "pending_review": ui("Pendentes", "Pending"),
            "approved": ui("Aprovados", "Approved"),
            "rejected": ui("Rejeitados", "Rejected"),
            "all": ui("Todos", "All"),
        }
        for key, button in getattr(self, "_moderation_filter_buttons", {}).items():
            button.text = f"{labels[key]} ({counts[key]})"
            button._draw(False)
        self._paint_moderation_hero()
        self._render_moderation_results()

    def _create_moderation_card(self, item, row, column):
        card_shell = KomicoveCard(self._moderation_grid, THEME, height=292,
                                  radius=22, padding=10,
                                  outline=THEME["border"])
        card_shell.configure(width=326)
        card_shell.grid(row=row, column=column, padx=7, pady=7, sticky="nsew")
        card = card_shell.content
        top = tk.Frame(card, bg=THEME["surface"])
        top.pack(fill="both", expand=True)
        cover_box = tk.Frame(top, width=112, height=174, bg=THEME["surface_alt"])
        cover_box.pack(side="left", anchor="n", padx=(0, 12))
        cover_box.pack_propagate(False)
        cover = tk.Label(cover_box,
                         text=ui('Carregando capa…', 'Loading cover…') if item.get("has_file") else ui('Sem arquivo', 'No file'),
                         bg=THEME["surface_alt"], fg=THEME["text_dim"], font=design_caption(8))
        cover.pack(fill="both", expand=True)
        if not item.get("has_file"):
            try:
                placeholder = getattr(self, "_moderation_placeholder_photo", None)
                if placeholder is None:
                    source = Image.open(resource_path(
                        "assets_redesign/placeholders/comic_cover.png")).convert("RGB")
                    source = ImageOps.fit(source, (112, 174), Image.LANCZOS)
                    source = ImageEnhance.Brightness(source).enhance(.38)
                    placeholder = ImageTk.PhotoImage(source)
                    self._moderation_placeholder_photo = placeholder
                cover.configure(image=placeholder, text=ui("ARQUIVO AUSENTE", "FILE MISSING"),
                                compound="center", fg="#ffffff",
                                font=design_caption(8, bold=True))
            except Exception:
                pass
        badge_colors = {
            "pending_review": ("#ffba08", ui("PENDENTE", "PENDING")),
            "approved": ("#20d887", ui("APROVADO", "APPROVED")),
            "rejected": ("#ff3045", ui("REJEITADO", "REJECTED")),
        }
        badge_color, badge_text = badge_colors.get(
            item.get("status"), (THEME["text_dim"], str(item.get("status", ""))))
        badge = tk.Canvas(cover_box, width=88, height=27, bg=THEME["surface_alt"],
                          highlightthickness=0, bd=0)
        _rounded_rect(badge, 1, 1, 87, 26, 9, fill="#10151d", outline=badge_color)
        badge.create_text(44, 14, text=badge_text, font=design_caption(8, bold=True),
                          fill=badge_color)
        badge.place(x=4, y=4)
        details = tk.Frame(top, bg=THEME["surface"])
        details.pack(side="left", fill="both", expand=True)
        menu_icon = lucide_icon("ellipsis-vertical", size=18, state="normal",
                                dark=THEME["bg"].lower() == "#090b0f")
        menu_button = tk.Label(details, image=menu_icon, bg=THEME["surface_alt"],
                               cursor="hand2", padx=5, pady=5)
        menu_button._image = menu_icon
        menu_button.place(relx=1.0, x=-2, y=0, anchor="ne")
        menu_button.bind("<Button-1>", lambda _e, i=item, w=menu_button:
                         self._show_moderation_item_menu(i, w))
        tk.Label(details, text=item.get("title") or ui("Sem título", "Untitled"),
                 font=design_body(11, bold=True), bg=THEME["surface"],
                 fg=THEME["text"], wraplength=155, justify="left").pack(
                     anchor="w", padx=(0, 25), pady=(27, 0))
        tk.Label(details, text=ui(f"Por {item.get('author', '')}", f"By {item.get('author', '')}"),
                 font=design_body(9), bg=THEME["surface"], fg=THEME["text_dim"],
                 wraplength=155, justify="left").pack(anchor="w", pady=(4, 5))
        tags = list(item.get("tags") or [])[:3]
        if tags:
            tag_row = tk.Frame(details, bg=THEME["surface"])
            tag_row.pack(anchor="w", pady=(2, 5))
            for tag in tags:
                tk.Label(tag_row, text=tag, font=design_caption(7), bg=THEME["surface_alt"],
                         fg=THEME["text"], padx=6, pady=3,
                         highlightthickness=1, highlightbackground=THEME["border"]).pack(
                             side="left", padx=(0, 4))
        description = (item.get("description") or item.get("justification") or "").strip()
        if description:
            tk.Label(details, text=description, font=design_caption(8), bg=THEME["surface"],
                     fg=THEME["text_dim"], wraplength=155, justify="left",
                     anchor="nw").pack(fill="x", pady=(5, 0))
        buttons = tk.Frame(card, bg=THEME["surface"])
        buttons.pack(side="bottom", fill="x", pady=(7, 0))
        review = KomicoveButton(
            buttons, ui('Revisar', 'Review'),
            (lambda i=item: self._read_moderation_file(i)) if item.get("has_file") else None,
            THEME, kind="secondary", compact=True, min_width=92, icon_name="eye",
            enabled=bool(item.get("has_file")),
        )
        review.pack(side="left")
        if item.get("has_file"):
            self._load_moderation_cover(item, cover)
        if item.get("status") == "pending_review":
            KomicoveButton(buttons, ui('Aprovar', 'Approve'),
                           lambda i=item: self._moderate_from_tab(i, "approved"),
                           THEME, kind="success", compact=True, min_width=96,
                           icon_name="check", enabled=bool(item.get("has_file"))).pack(
                               side="left", padx=5)
            KomicoveButton(buttons, ui('Rejeitar', 'Reject'),
                           lambda i=item: self._moderate_from_tab(i, "rejected"),
                           THEME, kind="danger", compact=True, min_width=96,
                           icon_name="x").pack(side="left")

    def _show_moderation_item_menu(self, item, widget):
        menu = tk.Menu(self, tearoff=False, bg=THEME["surface_alt"], fg=THEME["text"],
                       activebackground=THEME["surface_hover"], activeforeground=THEME["text"],
                       bd=0, relief="flat")
        if item.get("has_file"):
            menu.add_command(label=ui("Baixar arquivo", "Download file"),
                             command=lambda: self._download_moderation_file(item))
        if item.get("decision_reason"):
            menu.add_command(label=ui("Ver motivo da decisão", "View decision reason"),
                             command=lambda: messagebox.showinfo(
                                 ui("Decisão", "Decision"), item["decision_reason"], parent=self))
        if menu.index("end") is None:
            menu.add_command(label=ui("Sem ações disponíveis", "No actions available"), state="disabled")
        menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def _load_moderation_cover(self, item, label):
        generation = self._moderation_generation
        token = self.current_user.token
        def worker():
            try:
                data = api_client.moderation_cover(token, item["record_id"])
                image = Image.open(io.BytesIO(data)).convert("RGB")
                image = ImageOps.fit(image, (112, 174), Image.LANCZOS)
            except Exception:
                image = None
            try:
                self.after(0, lambda: self._set_moderation_cover(label, image, generation))
            except (RuntimeError, tk.TclError):
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _set_moderation_cover(self, label, image, generation=None):
        if (generation is not None and generation != self._moderation_generation) or self._active_tab != "moderation":
            return
        try:
            if not label.winfo_exists():
                return
            if image is None:
                label.config(text=ui('Capa indisponível', 'Cover unavailable'))
                return
            tk_image = ImageTk.PhotoImage(image)
            label.config(image=tk_image, text="")
            self._moderation_images.append(tk_image)
        except tk.TclError:
            # A navegação pode destruir o rótulo entre a verificação e a atualização.
            return

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
        self._notifications_nav_item = None
        c = THEME
        sidebar_width = SIDEBAR_WIDTH
        self._sb = tk.Frame(self, bg=c["surface"], width=sidebar_width)
        self._sb.pack(side="left", fill="y")
        self._sb.pack_propagate(False)
        lc = tk.Canvas(self._sb, width=sidebar_width, height=116, bg=c["surface"], highlightthickness=0)
        lc.pack(pady=(9, 0))
        try:
            logo_img = Image.open(resource_path("komicovelogo.png")).convert("RGBA")
            logo_img.thumbnail((172, 81), Image.LANCZOS)
            self.logo_tk = ImageTk.PhotoImage(logo_img)
            lc.create_image(sidebar_width // 2, 50, image=self.logo_tk)
        except Exception:
            lc.create_text(sidebar_width // 2, 38, text="◈ Komicove", font=FLOGO, fill=c["text"])
        lc.create_line(17, 112, sidebar_width - 17, 112, fill=c["border"], width=1)

        menu_host = tk.Frame(self._sb, bg=c["surface"])
        menu_host.pack(side="top", fill="both", expand=True)
        menu_canvas = tk.Canvas(
            menu_host, bg=c["surface"], highlightthickness=0, bd=0,
            width=sidebar_width - 5,
        )
        menu_scroll = ttk.Scrollbar(
            menu_host, orient="vertical", command=menu_canvas.yview,
            style="Vertical.TScrollbar",
        )
        self._sidebar_menu = tk.Frame(menu_canvas, bg=c["surface"])
        menu_window = menu_canvas.create_window(
            (0, 0), window=self._sidebar_menu, anchor="nw",
            width=sidebar_width - 7,
        )
        menu_canvas.configure(yscrollcommand=menu_scroll.set)
        menu_canvas.pack(side="left", fill="both", expand=True)
        menu_scroll.pack(side="right", fill="y")

        def update_sidebar_scroll(_event=None):
            try:
                content_height = max(1, self._sidebar_menu.winfo_reqheight())
                viewport_height = max(1, menu_canvas.winfo_height())
                viewport_width = max(1, menu_canvas.winfo_width())
            except tk.TclError:
                return
            # Keep the scroll region anchored at y=0.  Using bbox("all") here
            # allowed transient widget geometry to create an empty strip above
            # the first sidebar item.
            menu_canvas.configure(
                scrollregion=(0, 0, viewport_width, max(content_height, viewport_height))
            )
            if content_height <= viewport_height:
                menu_canvas.yview_moveto(0.0)

        def resize_sidebar_menu(event):
            menu_canvas.itemconfigure(menu_window, width=max(1, event.width))
            menu_canvas.after_idle(update_sidebar_scroll)

        def pointer_is_over_sidebar_menu():
            try:
                pointer_x = self.winfo_pointerx()
                pointer_y = self.winfo_pointery()
                left = menu_canvas.winfo_rootx()
                top = menu_canvas.winfo_rooty()
                right = left + menu_canvas.winfo_width()
                bottom = top + menu_canvas.winfo_height()
            except tk.TclError:
                return False
            return left <= pointer_x < right and top <= pointer_y < bottom

        def scroll_sidebar(steps):
            update_sidebar_scroll()
            content_height = max(1, self._sidebar_menu.winfo_reqheight())
            viewport_height = max(1, menu_canvas.winfo_height())
            if content_height <= viewport_height:
                menu_canvas.yview_moveto(0.0)
                return

            first, last = menu_canvas.yview()
            if steps < 0 and first <= 0.0001:
                menu_canvas.yview_moveto(0.0)
                return
            if steps > 0 and last >= 0.9999:
                menu_canvas.yview_moveto(1.0)
                return

            menu_canvas.yview_scroll(steps, "units")
            first, last = menu_canvas.yview()
            if first < 0.0:
                menu_canvas.yview_moveto(0.0)
            elif last > 1.0:
                menu_canvas.yview_moveto(1.0)

        def sidebar_wheel(event):
            if not pointer_is_over_sidebar_menu():
                return None
            # Windows reports a positive delta for scrolling up and a negative
            # delta for scrolling down.
            scroll_sidebar(-3 if event.delta > 0 else 3)
            return "break"

        def sidebar_linux_wheel(event):
            if not pointer_is_over_sidebar_menu():
                return None
            scroll_sidebar(-3 if event.num == 4 else 3)
            return "break"

        self._sidebar_menu.bind("<Configure>", update_sidebar_scroll)
        menu_canvas.bind("<Configure>", resize_sidebar_menu)
        # Bind on the toplevel instead of bind_all on canvas enter/leave.  The
        # embedded menu frame makes the pointer leave the canvas as soon as it
        # reaches a button, which used to disable sidebar scrolling and let a
        # page-level wheel handler process the same gesture instead.
        self.bind("<MouseWheel>", sidebar_wheel)
        self.bind("<Button-4>", sidebar_linux_wheel)
        self.bind("<Button-5>", sidebar_linux_wheel)

        self._active_tab = getattr(self, "_active_tab", "library")
        self._sidebar_section(ui('NAVEGAÇÃO', 'NAVIGATION'))
        for label, cmd, tab, icon in [
            (TEXTS[LANG]['library'], self._refresh_library, "library", "book-open"),
            (TEXTS[LANG]['collections'], self._show_collections, "collections", "folders"),
        ]:
            active = (self._active_tab == tab)
            self._sidebar_item(label, icon,
                lambda f=cmd, t=tab: (setattr(self, "_active_tab", t), self._build_shell(), f())[-1],
                active=active, font=FBTN, pady=8)
        self._sidebar_item(ui('Descobrir', 'Discover'), "compass",
                           self._open_discovery, active=(self._active_tab == "discovery"), font=FBTN, pady=8)

        self._sidebar_section(ui('ATIVIDADE', 'ACTIVITY'))
        self._sidebar_item("Downloads", "download", self._open_downloads,
                           active=(self._active_tab == "downloads"), font=FLABEL, pady=7)
        self._sidebar_item(ui('Estatísticas', 'Statistics'), "chart-no-axes-column-increasing", self._open_statistics,
                           active=(self._active_tab == "statistics"), font=FLABEL, pady=7)

        if self.current_user is not None:
            self._sidebar_item(ui('Meus envios', 'My submissions'), "upload", self._open_my_publications,
                                active=(self._active_tab == "submissions"), font=FLABEL, pady=7)
            self._notifications_nav_item = self._sidebar_item(
                ui('Notificações', 'Notifications'), "bell",
                self._open_notifications, active=(self._active_tab == "notifications"),
                font=FLABEL, pady=7, badge=self._notification_count or None)
            role = getattr(self.current_user, "role", "user")
            has_moderation_access = can_moderate(self.current_user)
            if has_moderation_access:
                self._sidebar_section(ui('EQUIPE', 'TEAM'))
                self._sidebar_item(ui('Moderação', 'Moderation'), "shield",
                                    self._open_moderation,
                                    active=(self._active_tab == "moderation"), font=FLABEL, pady=7)

        tk.Frame(self._sidebar_menu, bg=c["border"], height=1).pack(fill="x", padx=16, pady=(12, 5))
        self._sidebar_section(ui('PREFERÊNCIAS', 'PREFERENCES'))
        for txt, cmd, icon in [
            (ui('Idioma', 'Language'), self._change_language, "settings"),
            (current_theme_label().strip(), self._toggle_theme, "moon" if IS_DARK else "sun"),
            (TEXTS[LANG]['folder'], self._choose_folder, "folder"),
            ("Backup", self._do_backup, "database-backup"),
            (ui('Restaurar', 'Restore'), self._do_restore, "refresh-cw"),
            (ui('Atualizações', 'Updates'), self._check_updates, "download"),
            (ui('Diagnóstico seguro', 'Safe diagnostics'), self._copy_diagnostics, "shield"),
        ]:
            self._sidebar_item(txt, icon, cmd, font=FSMALL, pady=6)

        if self.current_user is not None:
            self._sidebar_account_card()
        else:
            tk.Label(self._sb, text=ui('Modo convidado', 'Guest mode'), font=FSMALL, bg=c["surface"],
                     fg=c["text_dim"]).pack(side="bottom", anchor="w", padx=20, pady=(8, 14))

        tk.Frame(self._sb, bg=c["border"], width=1).place(relx=1, rely=0, relheight=1, anchor="ne")

        # Every rebuilt screen starts with the first navigation item exactly at
        # the top limit.  The user can then scroll only into the content below.
        def reset_sidebar_to_top():
            update_sidebar_scroll()
            menu_canvas.yview_moveto(0.0)

        menu_canvas.after_idle(reset_sidebar_to_top)

        self._main = tk.Frame(self, bg=c["bg"])
        self._main.pack(side="right", fill="both", expand=True)

    def _check_updates(self):
        dialog=tk.Toplevel(self); dialog.title(ui('Atualizações do Komicove', 'Komicove updates')); dialog.configure(bg=THEME["bg"])
        dialog.geometry("560x420"); dialog.resizable(False,False); dialog.transient(self); grab_when_visible(dialog)
        head=tk.Frame(dialog,bg=THEME["surface"],height=82); head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head,text=ui('✦  Atualizações', '✦  Updates'),font=FTITLE,bg=THEME["surface"],fg=THEME["text"]).pack(anchor="w",padx=24,pady=(18,0))
        tk.Label(head,text=f"Windows/Linux {updater.CURRENT_VERSION}  ·  Android 0.2.0",font=FSMALL,bg=THEME["surface"],fg=THEME["text_dim"]).pack(anchor="w",padx=26)
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
            + "Android: 0.2.0\n"
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
        tk.Label(self._sidebar_menu, text=text, font=design_caption(8, bold=True), bg=THEME["surface"],
                 fg=THEME["text_muted"], anchor="w").pack(fill="x", padx=19, pady=(12, 4))

    def _sidebar_account_card(self):
        c = THEME
        width, height = SIDEBAR_WIDTH - 16, 70
        card = tk.Canvas(
            self._sb, width=width, height=height, bg=c["surface"],
            highlightthickness=0, bd=0, cursor="hand2", takefocus=1,
        )
        card.pack(side="bottom", padx=8, pady=(7, 12))

        # A restrained outer halo, thin accent edge and rounded surface match the
        # floating account card from the redesign reference without a costly blur.
        # Filled nested layers keep the outline continuous on all four sides.
        # Canvas polygon outlines can be clipped on the right and bottom edge.
        _rounded_rect(card, 0, 1, width - 1, height - 1, 15,
                      fill=c["border_glow"], outline="")
        _rounded_rect(card, 2, 3, width - 3, height - 3, 14,
                      fill=c["accent"], outline="")
        _rounded_rect(card, 3, 4, width - 4, height - 4, 13,
                      fill=c["surface_alt"], outline="")
        card.create_oval(10, 12, 54, 56, fill=c["border_glow"], outline="")
        card.create_oval(12, 14, 52, 54, fill=c["accent"], outline="")
        card.create_oval(14, 16, 50, 52, fill=c["surface_alt"], outline="")

        self._profile_icon = lucide_icon(
            "circle-user-round", size=23, state="white", dark=IS_DARK,
        )
        self._logout_icon = lucide_icon(
            "log-out", size=19, state="normal", dark=IS_DARK,
        )
        username = getattr(self.current_user, "username", "local") or "local"
        avatar_path = load_prefs().get(f"profile_avatar_{username}")
        self._sidebar_avatar_photo = None

        def paint_sidebar_avatar(path):
            if not path or not os.path.isfile(path) or not card.winfo_exists():
                return
            try:
                source = Image.open(path).convert("RGBA")
                source = ImageOps.fit(source, (34, 34), Image.LANCZOS)
                mask = Image.new("L", source.size, 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 33, 33), fill=255)
                source.putalpha(mask)
                self._sidebar_avatar_photo = ImageTk.PhotoImage(source)
                card.delete("avatar-image")
                card.create_image(32, 34, image=self._sidebar_avatar_photo,
                                  tags=("profile", "avatar-image"))
            except Exception:
                return

        if self._profile_icon:
            card.create_image(32, 34, image=self._profile_icon,
                              tags=("profile", "avatar-image"))
        paint_sidebar_avatar(avatar_path)

        def sync_sidebar_avatar():
            try:
                payload = api_client.profile_avatar(self.current_user.token)
                avatar_dir = Path(APPDATA_DIR, "profile")
                avatar_dir.mkdir(parents=True, exist_ok=True)
                destination = avatar_dir / f"{username}_avatar.png"
                temporary = destination.with_suffix(".sync")
                temporary.write_bytes(payload)
                with Image.open(temporary) as image:
                    ImageOps.fit(image.convert("RGBA"), (512, 512), Image.LANCZOS).save(
                        destination, "PNG", optimize=True,
                    )
                temporary.unlink(missing_ok=True)
                save_prefs(**{f"profile_avatar_{username}": str(destination)})
                self.after(0, lambda: paint_sidebar_avatar(str(destination)))
            except Exception:
                return

        if not getattr(self, "_avatar_sync_started", False):
            self._avatar_sync_started = True
            threading.Thread(target=sync_sidebar_avatar, daemon=True).start()
        if self._logout_icon:
            card.create_image(width - 20, 34, image=self._logout_icon,
                              tags=("logout",), anchor="center")

        display_name = (
            getattr(self.current_user, "display_name", None)
            or getattr(self.current_user, "username", None)
            or ui('Conta', 'Account')
        )
        card.create_text(65, 27, text=display_name, anchor="w",
                         font=design_body(10, bold=True), fill=c["text"],
                         width=width - 112, tags=("profile",))
        card.create_text(65, 45, text=role_label(self.current_user), anchor="w",
                         font=design_caption(8), fill=c["text_dim"],
                         tags=("profile",))

        card.tag_bind("logout", "<Button-1>",
                      lambda _e: (self._logout(), "break")[1])
        card.tag_bind("logout", "<Enter>", lambda _e: card.config(cursor="hand2"))
        card.tag_bind("profile", "<Button-1>", lambda _e: self._open_profile())
        card.bind("<Button-1>", lambda _e: self._open_profile())
        card.bind("<Return>", lambda _e: self._open_profile())
        card.bind("<space>", lambda _e: self._open_profile())

    def _sidebar_item(self, text, icon, cmd, *, active=False, font=FBTN, pady=11, badge=None):
        item = KomicoveSidebarItem(
            self._sidebar_menu, text, cmd, THEME,
            icon_name=icon if isinstance(icon, str) else None,
            icon=None if isinstance(icon, str) else icon,
            active=active, badge=badge,
            compact=pady <= 6, width=SIDEBAR_WIDTH - 16,
        )
        item.pack(padx=8, pady=1)
        return item

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

        top = tk.Frame(self._main, bg=c["bg"])
        top.pack(fill="x", padx=CONTENT_PADDING, pady=(18, 7))
        title_area = tk.Frame(top, bg=c["bg"], width=170, height=44)
        title_area.pack(side="left", padx=(0, 28))
        title_area.pack_propagate(False)
        tk.Label(title_area, text=TEXTS[LANG]["library"], font=design_heading(27),
                 bg=c["bg"], fg=c["text"]).pack(anchor="w")
        KomicoveButton(top, ui('Pasta', 'Folder'), self._choose_folder,
                       c, kind="primary", icon_name="plus").pack(side="right", padx=(8, 0))
        KomicoveButton(top, ui('Série / Autor', 'Series / Author'), self._metadata_filters,
                       c, compact=True, icon_name="list").pack(side="right", padx=(8, 0))

        self._library_search = KomicoveInput(
            top, c, placeholder=ui('Buscar títulos, autores, gêneros...', 'Search titles, authors, genres...'),
            value=self._search_query, on_change=self._bubble_search_changed,
            width=640,
        )
        self._library_search.pack(side="left", fill="x", expand=True, pady=(2, 0))
        self.bind('<Control-k>', lambda _e: self._library_search.entry.focus_set()
                  if self._active_tab == 'library' and self._library_search.winfo_exists() else None)

        stf = tk.Frame(self._main, bg=c["bg"])
        stf.pack(fill="x", padx=CONTENT_PADDING, pady=(0, 8))
        self._status_btns = {}
        for key, lbl, icon_name in [
                         ("all", TEXTS[LANG]["f_all"], "grid-2x2"),
                         ("unread", TEXTS[LANG]["f_unread"], "book-open"),
                         ("reading", TEXTS[LANG]["f_reading"], "bookmark"),
                         ("done", TEXTS[LANG]["f_done"], "check"),
                         ("favorites", ui('Favoritos', 'Favorites'), "heart")]:
            b = make_pill(stf, lbl, lambda k=key: self._set_status_filter(k),
                          variant="soft", font=design_caption(10), pad_x=17, pad_y=8,
                          active=(self._status_filter == key), icon_name=icon_name)
            b.pack(side="left", padx=(0, 4))
            self._status_btns[key] = b

        tk.Frame(self._main, bg=c["border"], height=1).pack(fill="x", padx=CONTENT_PADDING, pady=(4, 3))

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

        # The reference uses a permanent search field, not a floating bubble.

    def _set_status_filter(self, key):
        self._status_filter = key
        self._populate_library_grid()
        for k, b in self._status_btns.items():
            b.pill_set_active(k == key)

    def _open_statistics(self):
        self._active_tab = "statistics"
        self._build_shell()
        for child in self._main.winfo_children():
            child.destroy()
        render_statistics(self._main, THEME, self._go_library)

    def _bubble_search_changed(self, val):
        self._search_query = val
        self._populate_library_grid()
    def _bubble_search_clear(self):
        self._search_query = ""
        if getattr(self, "_library_search", None):
            self._library_search.clear()
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

        has_active_filter = bool(q or self._status_filter != "all" or any(
            getattr(self, "_metadata_filter_" + field, "") for field in ("series", "writer")
        ))
        if not arquivos and (not continuar or has_active_filter):
            self._show_empty(self._lib_content, no_results=has_active_filter)
            return

        self.update_idletasks()
        avail = self._main.winfo_width() - CONTENT_PADDING * 2
        if avail < 50:
            self.after(200, self._populate_library_grid); return
        card_w = 156 + GPAD
        ncols = max(2, avail // card_w)
        self._last_ncols = ncols

        if continuar and not has_active_filter:
            self._render_library_hero(self._lib_content, continuar[:6])

        section = tk.Frame(self._lib_content, bg=c["bg"])
        section.pack(fill="x", padx=CONTENT_PADDING, pady=(22, 5))
        tk.Label(section,
                 text=ui(f'TODAS AS HQs  ·  {len(arquivos)}', f'ALL COMICS  ·  {len(arquivos)}'),
                 font=design_caption(10, bold=True), bg=c["bg"], fg=c["text"], anchor="w").pack(side="left")
        self._book_sort_controls(section, self._refresh_library, side="right")

        gf = tk.Frame(self._lib_content, bg=c["bg"])
        gf.pack(padx=CONTENT_PADDING - GPAD // 2, pady=(8, GPAD), anchor="nw")
        for placed, path in enumerate(arquivos):
            row, col = placed // ncols, placed % ncols
            card = ComicCard(gf, path, None, self._open, self,
                             label_override=comic_display_title(path), compact=True)
            card.grid(row=row, column=col, padx=GPAD//2, pady=GPAD//2)
            self._card_map[path] = card
            self._wire_card(card, path)

    def _render_library_hero(self, parent, paths):
        c = THEME
        available = max(450, self._main.winfo_width() - CONTENT_PADDING * 2)
        height = 326
        hero = tk.Canvas(parent, bg=c["bg"], width=available, height=height,
                         highlightthickness=0, bd=0)
        hero.pack(fill="x", padx=CONTENT_PADDING, pady=(9, 0))
        try:
            art_width = min(available, max(760, round(available * 0.72)))
            art_left = available - art_width
            with Image.open(resource_path('assets_redesign/banners/library_noir.png')) as source:
                art = ImageOps.fit(source.convert('RGB'), (art_width, height),
                                   method=Image.LANCZOS, centering=(0.52, 0.59))
            art = ImageEnhance.Brightness(art).enhance(0.48).convert('RGBA')
            backdrop = Image.new('RGBA', (available, height), c['bg'])
            backdrop.paste(art, (art_left, 0))
            shade = Image.new('RGBA', (available, height), (0, 0, 0, 0))
            gradient = ImageDraw.Draw(shade)
            fade_end = min(available, art_left + 360)
            for x in range(fade_end):
                opacity = 255 if x < art_left else round(255 * (1 - (x - art_left) / max(1, fade_end - art_left)) ** 1.7)
                gradient.line((x, 0, x, height), fill=(7, 9, 14, opacity))
            art = Image.alpha_composite(backdrop, shade)
            mask = Image.new('L', (available, height), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, available - 1, height - 1),
                                                    radius=24, fill=255)
            rounded = Image.new('RGBA', (available, height), c['bg'])
            rounded.paste(art, (0, 0), mask)
            self._library_hero_photo = ImageTk.PhotoImage(rounded)
            hero.create_image(0, 0, image=self._library_hero_photo, anchor='nw')
        except (OSError, ValueError):
            _runtime._rrect(hero, 1, 1, available - 2, height - 2, 24, fill=c['surface'])
        _runtime._rrect(hero, 1, 1, available - 2, height - 2, 24,
                        outline=c['border'], width=1)
        hero.create_line(2, 19, 2, 72, fill=c['accent'], width=3)
        hero.create_text(24, 29, text='›', font=design_heading(22),
                         fill=c['accent'], anchor='w')
        hero.create_text(43, 28, text=ui('Continuar lendo', 'Continue reading'),
                         font=design_heading(17), fill=c['text'], anchor='w')

        self._hero_index = min(getattr(self, '_hero_index', 0), max(0, len(paths) - 1))
        cover_photos = {}
        hero._cover_photos = cover_photos
        self._library_hero_cover_photos = cover_photos

        def cover_photo(pil):
            width, cover_height = 176, 208
            source = (pil or get_placeholder_pil()).convert('RGBA').resize(
                (width - 4, cover_height - 4), Image.LANCZOS)
            edge = Image.new('RGBA', (width, cover_height), (0, 0, 0, 0))
            ImageDraw.Draw(edge).rounded_rectangle(
                (0, 0, width - 1, cover_height - 1), radius=19,
                fill=c['accent'], outline=c['border_glow'], width=1)
            mask = Image.new('L', source.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, source.width - 1, source.height - 1), radius=17, fill=255)
            edge.paste(source, (2, 2), mask)
            return ImageTk.PhotoImage(edge)

        placeholder = cover_photo(None)
        cover_photos['placeholder'] = placeholder

        def open_context(event, path):
            card = self._card_map.get(path)
            if card is not None:
                card._show_context_menu(event)
                self.after_idle(self._refresh_library)

        def show_cards():
            hero.delete('hero-card')
            cover_photos.clear()
            cover_photos['placeholder'] = placeholder
            for column, path in enumerate(paths[self._hero_index:self._hero_index + 2]):
                x, y = 26 + column * 216, 48
                tag = f'hero-card-{column}'
                image_id = hero.create_image(x, y, image=placeholder, anchor='nw',
                                             tags=('hero-card', tag))
                title = comic_display_title(path)
                if len(title) > 25:
                    title = title[:23] + '…'
                hero.create_text(x, y + 217, text=title, width=176, anchor='nw',
                                 font=design_caption(10, bold=True), fill=c['text'],
                                 tags=('hero-card', tag))
                page = get_progress_page(path)
                status = get_manual_status(path)
                try:
                    total = max(0, int(get_comic_info(path).get('page_count') or 0))
                except (ValueError, TypeError):
                    total = 0
                fraction = 1.0 if status == 'done' else (
                    min(1.0, (page + 1) / total) if page is not None and total else 0.0)
                progress_text = (f'{round(fraction * 100)}%' if total or status == 'done'
                                 else ui(f'Página {page + 1}', f'Page {page + 1}')
                                 if page is not None else ui('Em leitura', 'Reading'))
                bar_y = y + 251
                hero.create_line(x + 2, bar_y, x + 140, bar_y, fill=c['progress_bg'],
                                 width=6, capstyle=tk.ROUND, tags=('hero-card', tag))
                progress_id = hero.create_line(
                    x + 2, bar_y, x + 2 + round(138 * fraction), bar_y,
                    fill=c['accent'] if fraction else c['progress_bg'],
                    width=6, capstyle=tk.ROUND, tags=('hero-card', tag))
                text_id = hero.create_text(x + 176, bar_y, text=progress_text, anchor='e',
                                           font=FTINY, fill=c['text_dim'],
                                           tags=('hero-card', tag))
                hero.tag_bind(tag, '<Button-1>', lambda _e, p=path: self._open(p))
                hero.tag_bind(tag, '<Button-3>', lambda e, p=path: open_context(e, p))

                def loaded(_path, pil, item=image_id, key=tag, cover=path):
                    if not hero.winfo_exists() or not hero.find_withtag(item):
                        return
                    custom_cover = get_comic_info(cover).get('cover')
                    if custom_cover:
                        try:
                            with Image.open(custom_cover) as source:
                                pil = source.convert('RGB')
                        except (OSError, ValueError):
                            pass
                    photo = cover_photo(pil)
                    cover_photos[key] = photo
                    hero.itemconfigure(item, image=photo)

                self._cover_loader.request(path, loaded)

                if page is not None and not total and status != 'done':
                    def count_pages(book=path, current_page=page, line=progress_id,
                                    label=text_id, left=x, top=bar_y):
                        backend = None
                        try:
                            backend = ArchiveBackend(book)
                            count = backend.count
                        except (OSError, ValueError):
                            return
                        finally:
                            if backend is not None:
                                backend.close()
                        if count <= 0:
                            return

                        def update():
                            if not hero.winfo_exists() or not hero.find_withtag(line):
                                return
                            progress = min(1.0, (current_page + 1) / count)
                            hero.coords(line, left + 2, top,
                                        left + 2 + round(138 * progress), top)
                            hero.itemconfigure(line, fill=c['accent'])
                            hero.itemconfigure(label, text=f'{round(progress * 100)}%')

                        try:
                            self.after(0, update)
                        except (RuntimeError, tk.TclError):
                            pass

                    threading.Thread(target=count_pages, daemon=True).start()

        show_cards()
        if len(paths) > 2:
            def move(direction):
                self._hero_index = (self._hero_index + 2 * direction) % len(paths)
                show_cards()

            for x, arrow, direction in ((available - 85, '‹', -1),
                                        (available - 45, '›', 1)):
                button = tk.Canvas(hero, width=34, height=34, bg=c['bg'],
                                   highlightthickness=0, cursor='hand2')
                _runtime._rrect(button, 1, 1, 33, 33, 14,
                                fill=c['surface_alt'], outline=c['border'])
                button.create_text(17, 16, text=arrow, font=design_heading(18),
                                   fill=c['text'])
                button.bind('<Button-1>', lambda _e, step=direction: move(step))
                hero.create_window(x, 13, window=button, anchor='nw')

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
        avail = self._main.winfo_width() - CONTENT_PADDING * 2
        if avail < 50: return
        card_w = 156 + GPAD
        nc = max(2, avail // card_w)
        if nc != self._last_ncols:
            self._populate_library_grid()

    def _show_empty(self, parent, no_results=False):
        c = THEME
        illustration = None
        if not no_results:
            try:
                # During the first render Tk may still report a 1 px content area.
                # Derive a stable fallback from the actual window so the artwork
                # does not randomly alternate between its minimum and full size.
                self.update_idletasks()
                root_width = self.winfo_width()
                if root_width < 600:
                    root_width = self.winfo_screenwidth()
                content_width = max(self._main.winfo_width(), root_width - SIDEBAR_WIDTH)
                art_width = max(620, min(1270, content_width - CONTENT_PADDING * 2 - 50))
                with Image.open(resource_path('assets_redesign/empty_states/library_desktop.png')) as source:
                    art = source.convert('RGBA')
                    art.thumbnail((art_width, 555), Image.LANCZOS)
                illustration = ImageTk.PhotoImage(art)
            except (OSError, ValueError):
                pass
        self._empty_illustration = illustration
        if no_results:
            title = ui('Nenhuma HQ corresponde aos filtros', 'No comics match the filters')
            description = ui('Tente outro termo ou limpe os filtros para ver sua biblioteca.',
                             'Try another search or clear the filters to see your library.')
            action = self._clear_library_filters
            action_text = ui('Limpar filtros', 'Clear filters')
        else:
            title = ui('Sua biblioteca está vazia', 'Your library is empty')
            description = ui('Escolha uma pasta com quadrinhos para começar sua coleção.',
                             'Choose a folder with comics to start your collection.')
            action = self._choose_folder
            action_text = TEXTS[LANG]["add_folder"]
        KomicoveEmptyState(parent, c, title=title, description=description,
                           action=action, action_text=action_text,
                           illustration=illustration, panel=no_results).pack(
                               fill="x", pady=(55 if not no_results else 85, 25),
                               padx=CONTENT_PADDING)

    def _clear_library_filters(self):
        self._status_filter = 'all'
        self._metadata_filter_series = ''
        self._metadata_filter_writer = ''
        self._search_query = ''
        self._refresh_library()

    def _scan(self):
        from komicove_app.archive import SUPPORTED_EXTENSIONS
        exts = SUPPORTED_EXTENSIONS
        if not LIBRARY_FOLDER or not os.path.isdir(LIBRARY_FOLDER):
            return []
        return sorted([os.path.join(LIBRARY_FOLDER, f)
                       for f in os.listdir(LIBRARY_FOLDER)
                       if f.lower().endswith(exts) and os.path.isfile(os.path.join(LIBRARY_FOLDER, f))],
                      key=natural_key)

    def _book_sort_controls(self, parent, refresh, side=None):
        c = THEME
        row = tk.Frame(parent, bg=c["bg"])
        if side:
            row.pack(side=side)
        else:
            row.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(row, text=ui("Ordenar:", "Sort:"), font=FTINY,
                 bg=c["bg"], fg=c["text_dim"]).pack(side="left", padx=(0, 6))
        for key, label, icon_name in (("recent", ui("Recentes", "Recent"), "refresh-cw"),
                                      ("title", ui("Título A-Z", "Title A-Z"), "list"),
                                      ("title_desc", ui("Título Z-A", "Title Z-A"), "list"),
                                      ("series", ui("Série e título", "Series and title"), "library")):
            make_pill(row, label, lambda k=key: self._set_book_sort(k, refresh),
                      variant="soft", font=FTINY, pad_x=10, pad_y=4,
                      active=(self._book_sort == key), icon_name=icon_name).pack(
                          side="left", padx=(0, 4))

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
        hdr = tk.Frame(self._main, bg=c["bg"])
        hdr.pack(fill="x", padx=CONTENT_PADDING, pady=(18, 7))
        title_area = tk.Frame(hdr, bg=c["bg"], width=170, height=44)
        title_area.pack(side="left", padx=(0, 28))
        title_area.pack_propagate(False)
        tk.Label(title_area, text=TEXTS[LANG]["collections"], font=design_heading(27),
                 bg=c["bg"], fg=c["text"]).pack(anchor="w")
        KomicoveButton(hdr, ui('Pasta', 'Folder'), self._choose_folder,
                       c, kind="primary", icon_name="plus").pack(side="right", padx=(8, 0))
        KomicoveButton(hdr, ui('Série / Autor', 'Series / Author'), self._metadata_filters,
                       c, compact=True, icon_name="list").pack(side="right", padx=(8, 0))
        self._collection_search_field = KomicoveInput(
            hdr, c, placeholder=ui('Buscar coleções...', 'Search collections...'),
            value=self._collection_query, on_change=self._set_collection_search,
            width=max(260, min(640, self._main.winfo_width() - 490)),
        )
        self._collection_search_field.pack(side="left", pady=(2, 0))
        self.bind('<Control-k>', lambda _e: self._collection_search_field.entry.focus_set()
                  if self._active_tab == 'collections' and self._collection_search_field.winfo_exists() else None)

        ctrl = tk.Frame(self._main, bg=c["bg"])
        ctrl.pack(fill="x", padx=CONTENT_PADDING, pady=(0, 8))
        tabs = tk.Frame(ctrl, bg=c["bg"]); tabs.pack(side="left")
        self._filter_btns = {}
        for key, label, icon_name in [("all", TEXTS[LANG]["all"], "grid-2x2"),
                                      ("subfolders", TEXTS[LANG]["subfolders"], "folders"),
                                      ("series", TEXTS[LANG]["series"], "library")]:
            btn = make_pill(tabs, label, lambda k=key: self._set_col_filter(k),
                            variant="soft", font=design_caption(10), pad_x=17, pad_y=8,
                            active=(self._col_filter == key), icon_name=icon_name)
            btn.pack(side="left", padx=(0, 5)); self._filter_btns[key] = btn
        srt = tk.Frame(ctrl, bg=c["bg"]); srt.pack(side="right")
        tk.Label(srt, text=TEXTS[LANG]["sort_by"], font=design_caption(10),
                 bg=c["bg"], fg=c["text_dim"]).pack(side="left", padx=(0, 6))
        self._sort_btns = {}
        for key, label, icon_name in [("name", TEXTS[LANG]["sort_name"], "list"),
                                      ("date", TEXTS[LANG]["sort_date"], "refresh-cw"),
                                      ("progress", TEXTS[LANG]["sort_progress"],
                                       "chart-no-axes-column-increasing")]:
            btn = make_pill(srt, label, lambda k=key: self._set_col_sort(k),
                            variant="soft", font=design_caption(10), pad_x=12, pad_y=8,
                            active=(self._col_sort == key), icon_name=icon_name)
            btn.pack(side="left", padx=(0, 3)); self._sort_btns[key] = btn
        tk.Frame(self._main, bg=c["border"], height=1).pack(fill="x", padx=CONTENT_PADDING, pady=(4, 3))
        self._col_scroll_area(self._main)

    def _set_collection_search(self, query):
        self._collection_query = query
        self._col_scroll_area(self._main)

    def _go_library(self):
        self._active_tab = 'library'
        self._build_shell()
        self._refresh_library()

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
        query = self._collection_query.strip().casefold()
        if query:
            for kind in ("subfolders", "series"):
                cols[kind] = [item for item in cols[kind] if query in item["name"].casefold()]
        subfolders = _sort_collections(cols["subfolders"], self._col_sort)
        series = _sort_collections(cols["series"], self._col_sort)
        show_sub = self._col_filter in ("all", "subfolders")
        show_ser = self._col_filter in ("all", "series")

        if not (subfolders and show_sub) and not (series and show_ser):
            illustration = None
            if not query:
                try:
                    self.update_idletasks()
                    root_width = self.winfo_width()
                    if root_width < 600:
                        root_width = self.winfo_screenwidth()
                    content_width = max(self._main.winfo_width(), root_width - SIDEBAR_WIDTH)
                    art_width = max(620, min(1020, content_width - CONTENT_PADDING * 2 - 80))
                    with Image.open(resource_path('assets_redesign/empty_states/collections_desktop.png')) as source:
                        art = source.convert('RGBA')
                        art.thumbnail((art_width, 510), Image.LANCZOS)
                    illustration = ImageTk.PhotoImage(art)
                except (OSError, ValueError):
                    pass
            self._empty_collection_illustration = illustration
            if query:
                title = ui('Nenhuma coleção corresponde à busca', 'No collections match your search')
                description = ui('Tente outro nome ou limpe a busca.', 'Try another name or clear the search.')
                action = lambda: (setattr(self, '_collection_query', ''), self._show_collections())
                action_text = ui('Limpar busca', 'Clear search')
            else:
                title = TEXTS[LANG]['no_collections']
                description = ui('Organize suas histórias em pastas ou séries para facilitar sua leitura.',
                                 'Organize your stories into folders or series to make reading easier.')
                action = self._go_library
                action_text = ui('Ir para biblioteca', 'Go to library')
            KomicoveEmptyState(content, c, title=title, description=description,
                               action=action, action_text=action_text,
                               illustration=illustration, panel=True).pack(
                                   fill='x', padx=CONTENT_PADDING, pady=(10, 24))
            return

        self.update_idletasks()
        avail = self._main.winfo_width() - CONTENT_PADDING * 2
        if avail < 50:
            def retry_when_ready():
                if parent.winfo_exists() and self._active_tab == 'collections':
                    self._col_scroll_area(parent)
            self.after(200, retry_when_ready)
            return
        card_w = 320 + GPAD
        ncols = max(1, avail // card_w)

        def _section(par, title, items):
            heading_row = tk.Frame(par, bg=c["bg"])
            heading_row.pack(fill="x", padx=CONTENT_PADDING, pady=(12, 7))
            tk.Frame(heading_row, bg=c["accent"], width=4).pack(side="left", fill="y", padx=(0, 12))
            tk.Label(heading_row, text=f'›  {title}', font=design_heading(18),
                     bg=c["bg"], fg=c["text"], anchor="w").pack(side="left")
            gf = tk.Frame(par, bg=c["bg"])
            gf.pack(padx=CONTENT_PADDING - GPAD // 2, pady=(0, 12), anchor="nw")
            for i, item in enumerate(items):
                row, col = i // ncols, i % ncols
                card = CollectionCard(gf, item, open_cb=self._open,
                                      detail_cb=self._show_collection_detail,
                                      rename_cb=self._rename_collection, root=self)
                card.grid(row=row, column=col, padx=GPAD//2, pady=GPAD//2)
            tk.Frame(par, bg=c["border"], height=1).pack(fill="x", padx=CONTENT_PADDING, pady=(0, 8))
        if show_sub and subfolders: _section(content, TEXTS[LANG]['subfolders'], subfolders)
        if show_ser and series:     _section(content, TEXTS[LANG]['series'], series)

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
        active = getattr(self, "_active_tab", "library")
        if getattr(self, "_library_search", None) and active == "library":
            self._search_query = self._library_search.get()
        toggle_theme()
        self._sync_shared_settings()
        save_prefs(dark=_runtime.IS_DARK)
        apply_scrollbar_style()
        load_icons()
        self._capa_cache.clear()
        if self._search_bubble:
            self._search_query = self._search_bubble.get_text()
            try: self._search_bubble.destroy()
            except Exception: pass
            self._search_bubble = None
        self._build_shell()
        action = {
            "collections": self._show_collections,
            "discovery": self._open_discovery,
            "downloads": self._open_downloads,
            "statistics": self._open_statistics,
            "submissions": self._open_my_publications,
            "notifications": self._open_notifications,
            "moderation": self._open_moderation,
            "profile": self._open_profile,
        }.get(active, self._refresh_library)
        self.after(100, action)
