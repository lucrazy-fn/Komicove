"""Tkinter components for the noir redesign.

These are real controls with working callbacks. They do not depend on a
screenshot or on a second UI framework.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from .fonts import body, caption, heading
from .icons import lucide_icon
from .spacing import RADIUS_LARGE, RADIUS_MEDIUM, RADIUS_SMALL


def _rounded_rect(canvas, x1, y1, x2, y2, radius, *, fill, outline=""):
    """Draw a compact rounded rectangle without turning its long sides into a pill."""
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [
        x1 + radius, y1, x1 + radius, y1,
        x2 - radius, y1, x2 - radius, y1,
        x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2,
        x2 - radius, y2, x2 - radius, y2,
        x1 + radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius,
        x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=18,
                                 fill=fill, outline=outline, width=1)


class KomicoveButton(tk.Canvas):
    def __init__(self, parent, text, command, palette, *, kind="secondary", compact=False,
                 min_width=None, fixed_height=None, icon_name=None, enabled=True):
        self.palette = palette
        self.kind = kind
        self.text = text
        self.command = command
        self.icon_name = icon_name
        self.enabled = enabled
        self._pressed = False
        self._icon_image = None
        self._compact = compact
        font = caption(10, bold=True)
        measure = tkfont.Font(family=font[0], size=font[1], weight=font[2])
        icon_space = 25 if icon_name else 0
        base_width = 44 if icon_name and not text else 86
        width = max(min_width or 0, base_width,
                    measure.measure(text) + icon_space + (18 if compact else 38))
        height = fixed_height or (36 if compact else 42)
        super().__init__(
            parent, width=width, height=height, bg=parent.cget("bg"),
            highlightthickness=0, bd=0, cursor="hand2", takefocus=1,
        )
        self._width = width
        self._height = height
        self._draw(False)
        self.bind("<Enter>", lambda _e: self._draw(True))
        self.bind("<Leave>", lambda _e: self._draw(False))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", lambda _e: self._invoke())
        self.bind("<space>", lambda _e: self._invoke())

    def _invoke(self):
        if self.enabled and self.command:
            self.command()

    def _press(self, _event):
        if self.enabled:
            self._pressed = True
            self._draw(True)

    def _release(self, event):
        was_pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x <= self._width and 0 <= event.y <= self._height
        self._draw(inside)
        if was_pressed and inside:
            self._invoke()

    def _draw(self, hover):
        self.delete("all")
        c = self.palette
        w, h = self._width, self._height
        primary = self.kind == "primary"
        success = self.kind == "success"
        danger = self.kind == "danger"
        ghost = self.kind == "ghost"
        if not self.enabled:
            fill, outline, text_color = c["surface_alt"], c["border"], c["text_muted"]
        elif success:
            fill = "#0b9a61" if hover else "#087a4c"
            outline, text_color = "#20d887", "#ffffff"
        elif danger:
            fill = "#ff3045" if hover else "#ed1f36"
            outline, text_color = "#ff5365", "#ffffff"
        elif primary:
            fill = c["btn_hover"] if hover else c["accent"]
            outline, text_color = c["accent2"], "#ffffff"
        elif ghost:
            fill = c["surface_hover"] if hover else c["bg"]
            outline, text_color = c["border"] if hover else c["bg"], c["text"]
        else:
            fill = c["surface_hover"] if hover else c["surface_alt"]
            outline, text_color = c["border_glow"] if hover else c["border"], c["text"]

        emphasized = primary or success or danger
        inset = 3 if emphasized else 1
        if emphasized and self.enabled:
            # Two inexpensive layers reproduce the restrained red halo in the references.
            _rounded_rect(self, 0, 1, w, h - 1, RADIUS_MEDIUM + 1,
                          fill=c["border_glow"] if hover else c["shadow"], outline="")
        _rounded_rect(self, inset, inset, w - inset, h - inset, RADIUS_MEDIUM,
                      fill=fill, outline=outline)

        text_width = tkfont.Font(family=caption(10, bold=True)[0], size=10,
                                 weight="bold").measure(self.text)
        group_width = text_width + (24 if self.icon_name else 0)
        start_x = (w - group_width) / 2
        if self.icon_name:
            state = "white" if emphasized else ("hover" if hover else "normal")
            self._icon_image = lucide_icon(self.icon_name, size=17, state=state,
                                           dark=c["bg"].lower() == "#090b0f")
            if self._icon_image:
                self.create_image(start_x + 8, h // 2, image=self._icon_image)
                start_x += 24
        self.create_text(start_x + text_width / 2, h // 2, text=self.text,
                         font=caption(10, bold=True), fill=text_color)


class KomicoveSidebarItem(tk.Canvas):
    def __init__(self, parent, text, command, palette, *, icon=None, active=False,
                 badge=None, compact=False, width=216, icon_name=None):
        height = 34 if compact else 40
        super().__init__(parent, width=width, height=height, bg=palette["surface"],
                         highlightthickness=0, cursor="hand2", takefocus=1)
        self.palette = palette
        self.text = text
        self.icon = icon
        self.icon_name = icon_name
        self._lucide_image = None
        self.active = active
        self.badge = badge
        self.command = command
        self._width = width
        self._height = height
        self._compact = compact
        self._draw(False)
        self.bind("<Enter>", lambda _e: self._draw(True))
        self.bind("<Leave>", lambda _e: self._draw(False))
        self.bind("<Button-1>", lambda _e: self.command())
        self.bind("<Return>", lambda _e: self.command())
        self.bind("<space>", lambda _e: self.command())

    def _draw(self, hover):
        self.delete("all")
        c = self.palette
        w, h = self._width, self._height
        if self.active or hover:
            fill = c["surface_alt"] if self.active else c["surface_hover"]
            if self.active:
                _rounded_rect(self, 0, 0, w, h, RADIUS_MEDIUM + 1,
                              fill=c["shadow"], outline=c["border_glow"])
            _rounded_rect(self, 2 if self.active else 1, 2 if self.active else 1,
                          w - (2 if self.active else 1), h - (2 if self.active else 1),
                          RADIUS_MEDIUM, fill=fill,
                          outline=c["border_glow"] if self.active else "")
        if self.active:
            self.create_rectangle(1, 4, 4, h - 4, fill=c["accent"], outline="")
        x = 16
        image = self.icon
        if self.icon_name:
            state = "active" if self.active else ("hover" if hover else "normal")
            self._lucide_image = lucide_icon(
                self.icon_name, size=18, state=state,
                dark=c["bg"].lower() == "#090b0f",
            )
            image = self._lucide_image
        if image:
            self.create_image(x, h // 2, image=image, anchor="w")
            x += image.width() + 11
        self.create_text(x, h // 2, text=self.text.strip(), anchor="w",
                         font=body(10, bold=self.active and not self._compact),
                         fill=c["text"] if self.active or hover else c["text_dim"])
        if self.badge:
            value = "99+" if int(self.badge) > 99 else str(self.badge)
            self.create_oval(w - 35, h // 2 - 10, w - 9, h // 2 + 10,
                             fill=c["accent"], outline="")
            self.create_text(w - 22, h // 2, text=value, font=caption(8, bold=True), fill="#ffffff")


class KomicoveInput(tk.Canvas):
    def __init__(self, parent, palette, *, placeholder, value="", on_change=None,
                 width=None):
        self._width = width or 400
        super().__init__(parent, bg=parent.cget("bg"), width=self._width, height=42,
                         highlightthickness=0, bd=0)
        self.palette = palette
        self.placeholder = placeholder
        self.on_change = on_change
        self._job = None
        self._showing_placeholder = not bool(value)
        self._draw_background(False)
        inner = tk.Frame(self, bg=palette["search_bg"])
        self._inner_window_id = self.create_window(
            12, 5, window=inner, anchor="nw", width=self._width - 24, height=32,
        )
        self._search_icon = lucide_icon(
            "search", size=18, state="normal", dark=palette["bg"].lower() == "#090b0f",
        )
        tk.Label(inner, image=self._search_icon, bg=palette["search_bg"],
                 fg=palette["text_dim"]).pack(side="left", padx=(1, 10))
        self.entry = tk.Entry(inner, font=body(10), bg=palette["search_bg"],
                              fg=palette["text_dim"] if self._showing_placeholder else palette["text"],
                              insertbackground=palette["text"], relief="flat", bd=0,
                              highlightthickness=0)
        self.entry.pack(side="left", fill="both", expand=True, pady=4)
        self.clear_button = tk.Label(inner, text="Ctrl + K", font=caption(8),
                                     bg=palette["search_bg"], fg=palette["text_dim"],
                                     cursor="hand2", padx=5)
        self.clear_button.pack(side="right")
        self.clear_button.bind("<Button-1>", lambda _e: self.clear() if self.get() else self.entry.focus_set())
        self.entry.insert(0, placeholder if self._showing_placeholder else value)
        self._update_hint()
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<KeyRelease>", self._changed)
        self.bind("<Configure>", self._resize)
        self.bind("<Destroy>", self._destroyed)

    def _resize(self, event):
        if event.width == self._width:
            return
        self._width = event.width
        self.itemconfigure(self._inner_window_id, width=max(1, self._width - 24))
        self._draw_background(self.entry.focus_get() is self.entry)

    def _draw_background(self, focused):
        if getattr(self, "_background_id", None):
            self.delete(self._background_id)
        border = self.palette["border_glow"] if focused else self.palette["border"]
        self._background_id = _rounded_rect(
            self, 1, 1, self._width - 2, 40, RADIUS_MEDIUM,
            fill=self.palette["search_bg"], outline=border,
        )
        self.tag_lower(self._background_id)

    def _focus_in(self, _event):
        self._draw_background(True)
        if self._showing_placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(fg=self.palette["text"])
            self._showing_placeholder = False

    def _focus_out(self, _event):
        self._draw_background(False)
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.configure(fg=self.palette["text_dim"])
            self._showing_placeholder = True

    def _changed(self, _event):
        self._update_hint()
        if self._job:
            self.after_cancel(self._job)
        if self.on_change:
            self._job = self.after(250, lambda: self.on_change(self.get()))

    def _destroyed(self, event):
        if event.widget is self and self._job:
            self.after_cancel(self._job)
            self._job = None

    def get(self):
        return "" if self._showing_placeholder else self.entry.get()

    def _update_hint(self):
        if self.get():
            self.clear_button.configure(text="×", font=heading(14))
        else:
            self.clear_button.configure(text="Ctrl + K", font=caption(8))

    def clear(self):
        self.entry.delete(0, "end")
        self._showing_placeholder = False
        self._focus_out(None)
        self._update_hint()
        if self.on_change:
            self.on_change("")


class KomicoveCard(tk.Canvas):
    """A reusable card surface with a real rounded outline and live child controls."""

    def __init__(self, parent, palette, *, height=154, radius=RADIUS_LARGE, padding=10,
                 outline=None):
        super().__init__(parent, bg=parent.cget("bg"), height=height, width=420,
                         highlightthickness=0, bd=0)
        self.palette = palette
        self.outline = outline or palette["border"]
        self.radius = radius
        self.padding = padding
        self.card_height = height
        self.content = tk.Frame(self, bg=palette["surface"])
        self._window = self.create_window(padding, padding, window=self.content, anchor="nw",
                                          height=height - 2 * padding)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, event):
        self.delete("card-background")
        height = max(4, event.height)
        shadow = _rounded_rect(self, 3, 4, event.width - 1, height - 1,
                              self.radius, fill=self.palette["shadow"], outline="")
        self.addtag_withtag("card-background", shadow)
        shape = _rounded_rect(self, 1, 1, event.width - 3, height - 3,
                              self.radius, fill=self.palette["surface"],
                              outline=self.outline)
        self.addtag_withtag("card-background", shape)
        # Lower both layers together. Lowering only the surface used to place it
        # behind the offset shadow, which hid the right and bottom borders.
        self.tag_lower("card-background")
        self.itemconfigure(
            self._window,
            width=max(1, event.width - 2 * self.padding),
            height=max(1, height - 2 * self.padding),
        )


class KomicoveEmptyState(tk.Frame):
    def __init__(self, parent, palette, *, title, description, action, action_text,
                 illustration=None, panel=False):
        super().__init__(parent, bg=palette["bg"], highlightthickness=0)
        self._image = illustration
        if panel:
            border = tk.Canvas(self, bg=palette["bg"], highlightthickness=0, bd=0)
            border.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.tk.call("lower", border._w)

            def draw_border(event):
                border.delete("all")
                if event.width < 6 or event.height < 6:
                    return
                _rounded_rect(border, 1, 1, event.width - 2, event.height - 2, 16,
                              fill=palette["bg"], outline=palette["border"])

            self.bind("<Configure>", draw_border)
        content_frame = tk.Frame(self, bg=palette["bg"])
        content_frame.pack(fill="both", expand=True, padx=3 if panel else 0,
                           pady=3 if panel else 0)
        large = illustration is not None
        if illustration is not None:
            tk.Label(content_frame, image=illustration, bg=palette["bg"], bd=0).pack(
                pady=(18 if panel else 0, 6))
        tk.Label(content_frame, text=title, font=heading(25 if large or not panel else 18), bg=palette["bg"],
                 fg=palette["text"]).pack(padx=20, pady=(6, 7))
        tk.Label(content_frame, text=description, font=body(12 if large or not panel else 10), bg=palette["bg"],
                 fg=palette["text_dim"], justify="center", wraplength=680).pack(padx=25)
        KomicoveButton(content_frame, action_text, action, palette, kind="primary",
                       min_width=230 if large or not panel else None,
                       fixed_height=48 if large or not panel else None).pack(pady=(24, 22))
