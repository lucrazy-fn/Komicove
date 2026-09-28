"""Account notifications with real read state and source-backed filters."""

from __future__ import annotations

import datetime as dt
import threading
import tkinter as tk
from PIL import Image, ImageTk

from komicove_app.account_views import _notification_copy
from komicove_app.design.fonts import body, caption, heading, section
from komicove_app.design.icons import lucide_icon
from komicove_app.design.spacing import CONTENT_PADDING
from komicove_app.design.styles import KomicoveButton, KomicoveCard, KomicoveInput
from komicove_app.runtime import resource_path
from komicove_app.translations import ui


def filter_notifications(items, query="", group="all"):
    """Filter only fields supplied by the account API."""
    query = query.strip().casefold()
    result = []
    for item in items:
        if group == "unread" and item.get("read_at"):
            continue
        if group == "read" and not item.get("read_at"):
            continue
        if group == "submissions" and item.get("kind") != "publication_decision":
            continue
        if group == "system" and item.get("kind") != "punishment":
            continue
        title, message = _notification_copy(item)
        if query and query not in f"{title} {message}".casefold():
            continue
        result.append(item)
    return result


def _timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone()
        return parsed.strftime("%d/%m/%Y  %H:%M")
    except (TypeError, ValueError, OverflowError):
        return ""


def _count_summary(total, unread):
    return ui(
        f"{total} {'notificação' if total == 1 else 'notificações'} · "
        f"{unread} {'não lida' if unread == 1 else 'não lidas'}",
        f"{total} {'notification' if total == 1 else 'notifications'} · "
        f"{unread} unread",
    )


class NotificationsView(tk.Frame):
    def __init__(self, parent, root, user, api, palette, on_count, on_discover=None):
        super().__init__(parent, bg=palette["bg"])
        self.root, self.user, self.api = root, user, api
        self.palette, self.on_count = palette, on_count
        self.on_discover = on_discover
        self.items = []
        self.group = "all"
        self.query = ""
        self.status_text = ui("Carregando notificações...", "Loading notifications...")
        self._build()
        if user is None:
            self._set_status(ui("Entre na sua conta para ver as notificações.",
                                "Sign in to see notifications."))
        else:
            self.refresh()

    def _build(self):
        c = self.palette
        header = tk.Frame(self, bg=c["bg"])
        header.pack(fill="x", padx=CONTENT_PADDING, pady=(22, 8))
        tk.Label(header, text=ui("Notificações", "Notifications"), font=heading(25),
                 bg=c["bg"], fg=c["text"]).pack(side="left")
        KomicoveButton(header, ui("Atualizar", "Refresh"), self.refresh, c,
                       compact=True, icon_name="refresh-cw").pack(side="right")

        search_row = tk.Frame(self, bg=c["bg"])
        search_row.pack(fill="x", padx=CONTENT_PADDING, pady=(4, 9))
        self.search = KomicoveInput(
            search_row, c,
            placeholder=ui("Buscar notificações...", "Search notifications..."),
            on_change=self._search_changed, width=610,
        )
        self.search.pack(side="left")

        self.filters = tk.Frame(self, bg=c["bg"])
        self.filters.pack(fill="x", padx=CONTENT_PADDING, pady=(4, 11))
        self._draw_filters()
        self.status = tk.Label(self, text=self.status_text, font=caption(10),
                               bg=c["bg"], fg=c["text_dim"], anchor="w")
        self.status.pack(fill="x", padx=CONTENT_PADDING, pady=(0, 9))
        tk.Frame(self, height=1, bg=c["border"]).pack(fill="x", padx=CONTENT_PADDING)

        self.canvas = tk.Canvas(self, bg=c["bg"], highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, bg=c["bg"])
        window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda _e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self._render_items()

    def _set_status(self, text, *, error=False):
        self.status_text = text
        if self.winfo_exists():
            self.status.configure(text=text, fg=self.palette["accent2"] if error
                                  else self.palette["text_dim"])

    def _draw_filters(self):
        for child in self.filters.winfo_children():
            child.destroy()
        options = (
            ("all", ui("Todas", "All"), "grid-2x2"),
            ("unread", ui("Não lidas", "Unread"), "bell"),
            ("read", ui("Lidas", "Read"), "check"),
            ("submissions", ui("Meus envios", "My submissions"), "upload"),
            ("system", ui("Sistema", "System"), "shield"),
        )
        for key, label, icon_name in options:
            KomicoveButton(self.filters, label, lambda group=key: self._select(group),
                           self.palette, kind="primary" if key == self.group else "secondary",
                           compact=True, icon_name=icon_name).pack(side="left", padx=(0, 8))

    def _select(self, group):
        self.group = group
        self._draw_filters()
        self._render_items()

    def _search_changed(self, value):
        self.query = value
        self._render_items()

    def refresh(self):
        if self.user is None:
            return
        self._set_status(ui("Carregando notificações...", "Loading notifications..."))

        def worker():
            try:
                outcome = (self.api.notifications(self.user.token), None)
            except Exception as exc:
                outcome = (None, str(exc))
            try:
                self.root.after(0, lambda: self._loaded(*outcome))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _loaded(self, items, error):
        if not self.winfo_exists():
            return
        if error:
            self._set_status(ui("Não foi possível carregar as notificações: ",
                                "Could not load notifications: ") + error, error=True)
            return
        self.items = list(items or [])
        unread = sum(not item.get("read_at") for item in self.items)
        self.on_count(unread)
        self._set_status(_count_summary(len(self.items), unread))
        self._render_items()

    def _mark_read(self, item):
        if self.user is None or item.get("read_at"):
            return
        notification_id = item.get("id")
        if not notification_id:
            return

        def worker():
            try:
                self.api.mark_notification_read(self.user.token, notification_id)
                error = None
            except Exception as exc:
                error = str(exc)
            try:
                self.root.after(0, lambda: self._marked(item, error))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _marked(self, item, error):
        if not self.winfo_exists():
            return
        if error:
            self._set_status(ui("Não foi possível marcar como lida: ",
                                "Could not mark as read: ") + error, error=True)
            return
        item["read_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        unread = sum(not row.get("read_at") for row in self.items)
        self.on_count(unread)
        self._set_status(_count_summary(len(self.items), unread))
        self._render_items()

    def _render_items(self):
        for child in self.content.winfo_children():
            child.destroy()
        self._card_icons = []
        c = self.palette
        rows = filter_notifications(self.items, self.query, self.group)
        if not rows:
            self._render_empty()
            return
        for item in rows:
            self._render_card(item)

    def _clear_filters(self):
        self.group = "all"
        self.query = ""
        self.search.clear()
        self._draw_filters()
        self._render_items()

    def _render_empty(self):
        c = self.palette
        panel = KomicoveCard(self.content, c, height=648, radius=22, padding=18)
        panel.pack(fill="x", padx=CONTENT_PADDING, pady=(20, 15))
        self._empty_art_tk = None
        try:
            with Image.open(resource_path(
                    "assets_redesign/empty_states/notifications_illustration.png")) as source:
                image = source.convert("RGBA")
                image.thumbnail((1080, 405), Image.LANCZOS)
            self._empty_art_tk = ImageTk.PhotoImage(image)
        except (OSError, ValueError):
            pass
        art = tk.Canvas(panel.content, height=405, bg=c["surface"],
                        highlightthickness=0, bd=0)
        art.pack(fill="x")
        art.bind("<Configure>", lambda event: self._paint_empty_art(art, event.width))
        filtered = bool(self.items)
        tk.Label(panel.content,
                 text=(ui("Nenhum resultado encontrado", "No results found") if filtered
                       else ui("Nenhuma notificação", "No notifications")),
                 font=heading(24), bg=c["surface"], fg=c["text"]).pack(pady=(3, 8))
        tk.Label(panel.content,
                 text=(ui("Tente outra busca ou filtro.", "Try another search or filter.")
                       if filtered else ui("Você está em dia! As novidades da sua conta aparecerão aqui.",
                                            "You're up to date! Updates about your account will appear here.")),
                 font=body(11), bg=c["surface"], fg=c["text_dim"],
                 wraplength=630, justify="center").pack(pady=(0, 20))
        if filtered:
            action = self._clear_filters
            label = ui("Limpar filtros", "Clear filters")
        else:
            action = self.on_discover
            label = ui("Explorar quadrinhos", "Explore comics")
        if action is not None:
            KomicoveButton(panel.content, label, action, c, min_width=205,
                           icon_name="search" if filtered else "compass").pack()

    def _paint_empty_art(self, art, width):
        art.delete("all")
        if self._empty_art_tk is not None:
            art.create_image(width // 2, 202, image=self._empty_art_tk)
            return
        c = self.palette
        cx = max(220, width // 2)
        art.create_oval(cx - 142, 78, cx + 142, 362,
                        fill=c["border_glow"], outline="")
        art.create_oval(cx - 122, 98, cx + 122, 342,
                        fill=c["accent"], outline="")
        for index, height in enumerate((103, 147, 126, 172, 116, 153, 100, 139, 117)):
            left = cx - 300 + index * 75
            top = 377 - height
            art.create_rectangle(left, top, left + 55, 377,
                                 fill=c["canvas_bg"], outline=c["border"])
            for x in range(left + 11, left + 50, 17):
                for y in range(top + 15, 366, 24):
                    art.create_rectangle(x, y, x + 5, y + 7,
                                         fill=c["border_glow"], outline="")
        art.create_oval(cx - 96, 167, cx + 96, 359,
                        fill=c["surface_alt"], outline=c["text_dim"], width=3)
        art.create_arc(cx - 69, 180, cx + 69, 330, start=0, extent=180,
                       style="arc", outline=c["text"], width=8)
        art.create_line(cx - 68, 251, cx - 81, 318, cx + 81, 318,
                        cx + 68, 251, fill=c["text"], width=8, smooth=True)
        art.create_oval(cx - 13, 328, cx + 13, 354,
                        fill=c["accent"], outline="")

    def _render_card(self, item):
        c = self.palette
        unread = not item.get("read_at")
        card = KomicoveCard(self.content, c, height=118, radius=19, padding=12,
                            outline=c["border_glow"] if unread else c["border"])
        card.pack(fill="x", padx=CONTENT_PADDING, pady=6)
        pane = card.content
        icon = tk.Canvas(pane, width=76, height=76, bg=c["surface"],
                         highlightthickness=0, bd=0)
        icon.pack(side="left", padx=(5, 17))
        icon.create_oval(6, 6, 70, 70, outline=c["accent"] if unread else c["border"],
                         width=2)
        icon_name = "upload" if item.get("kind") == "publication_decision" else "shield"
        icon_image = lucide_icon(icon_name, size=25,
                                 state="active" if unread else "normal")
        if icon_image is not None:
            self._card_icons.append(icon_image)
            icon.create_image(38, 38, image=icon_image)
        text = tk.Frame(pane, bg=c["surface"])
        text.pack(side="left", fill="both", expand=True, pady=5)
        kind = item.get("kind")
        category = (ui("MEUS ENVIOS", "MY SUBMISSIONS") if kind == "publication_decision"
                    else ui("SISTEMA", "SYSTEM"))
        tk.Label(text, text=category, font=caption(8, bold=True),
                 bg=c["surface"], fg=c["accent2"]).pack(anchor="w")
        title, message = _notification_copy(item)
        tk.Label(text, text=title, font=section(14), bg=c["surface"],
                 fg=c["text"]).pack(anchor="w", pady=(3, 0))
        tk.Label(text, text=message, font=body(10), bg=c["surface"],
                 fg=c["text_dim"], anchor="w", justify="left",
                 wraplength=790).pack(anchor="w", fill="x", pady=(3, 0))
        aside = tk.Frame(pane, bg=c["surface"])
        aside.pack(side="right", fill="y", padx=(12, 5), pady=4)
        tk.Label(aside, text=_timestamp(item.get("created_at")), font=caption(9),
                 bg=c["surface"], fg=c["text_dim"]).pack(anchor="e")
        if unread:
            KomicoveButton(aside, ui("Marcar como lida", "Mark as read"),
                           lambda row=item: self._mark_read(row), c,
                           compact=True, icon_name="check").pack(anchor="e", pady=(13, 0))


def render_notifications(parent, root, user, api, palette, _fonts, on_count,
                         on_discover=None):
    for child in parent.winfo_children():
        child.destroy()
    view = NotificationsView(parent, root, user, api, palette, on_count, on_discover)
    view.pack(fill="both", expand=True)
    return view
