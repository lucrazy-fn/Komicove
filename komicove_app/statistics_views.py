"""Personal statistics screen built only from locally recorded reading data."""

from __future__ import annotations

import datetime as dt
import os
import tkinter as tk
from pathlib import Path

from komicove_app.design.fonts import body, caption, heading, section
from komicove_app.design.spacing import CONTENT_PADDING
from komicove_app.design.styles import KomicoveButton, _rounded_rect
from komicove_app.design.icons import lucide_icon
from komicove_app.storage import load_progress, personal_statistics
from komicove_app.translations import ui


def statistics_model(stats, progress, *, exists=os.path.isfile, today=None):
    """Normalize real counters and recent file progress for display."""
    started = max(0, int(stats.get("started") or 0))
    completed = max(0, min(started, int(stats.get("completed") or 0)))
    pages = max(0, int(stats.get("pages") or 0))
    seconds = max(0, int(stats.get("seconds") or 0))
    recent = []
    for path, value in progress.items():
        if not isinstance(path, str) or not exists(path):
            continue
        if isinstance(value, dict):
            page, stamp = value.get("page"), value.get("ts")
        else:
            page, stamp = value, 0
        try:
            page = int(page)
            stamp = float(stamp or 0)
        except (TypeError, ValueError):
            continue
        if page < 0:
            continue
        recent.append((stamp, path, page))
    recent.sort(key=lambda item: item[0], reverse=True)
    today = today or dt.date.today()
    daily_source = stats.get("daily") if isinstance(stats.get("daily"), dict) else {}
    daily = []
    for offset in range(13, -1, -1):
        day = today - dt.timedelta(days=offset)
        source = daily_source.get(day.isoformat(), {})
        daily.append({
            "date": day,
            "pages": max(0, int(source.get("pages", 0) or 0)),
            "seconds": max(0, int(source.get("seconds", 0) or 0)),
            "sessions": max(0, int(source.get("sessions", 0) or 0)),
        })
    weekly = []
    for week_index in range(8):
        end = today - dt.timedelta(days=(7 - week_index) * 7)
        start = end - dt.timedelta(days=6)
        pages_in_week = 0
        seconds_in_week = 0
        for day_key, source in daily_source.items():
            try:
                day = dt.date.fromisoformat(day_key)
            except (TypeError, ValueError):
                continue
            if start <= day <= end:
                pages_in_week += max(0, int(source.get("pages", 0) or 0))
                seconds_in_week += max(0, int(source.get("seconds", 0) or 0))
        weekly.append({"start": start, "end": end, "pages": pages_in_week,
                       "seconds": seconds_in_week})
    read_days = set()
    for key, source in daily_source.items():
        try:
            if int(source.get("pages", 0) or 0) > 0 or int(source.get("seconds", 0) or 0) > 0:
                read_days.add(dt.date.fromisoformat(key))
        except (TypeError, ValueError):
            continue
    streak = 0
    cursor = today
    if cursor not in read_days and cursor - dt.timedelta(days=1) in read_days:
        cursor -= dt.timedelta(days=1)
    while cursor in read_days:
        streak += 1
        cursor -= dt.timedelta(days=1)
    genres = sorted(
        ((str(name), max(0, int(value or 0))) for name, value in
         (stats.get("genres") or {}).items()),
        key=lambda item: item[1], reverse=True,
    )[:5]
    return {
        "started": started,
        "completed": completed,
        "pages": pages,
        "seconds": seconds,
        "completion_percent": round(100 * completed / started) if started else 0,
        "recent": recent[:5],
        "daily": daily,
        "weekly": weekly,
        "streak": streak,
        "sessions": max(0, int(stats.get("sessions") or 0)),
        "genres": genres,
    }


class _StatisticTile(tk.Canvas):
    def __init__(self, parent, palette, icon, title, value):
        super().__init__(parent, width=250, height=158, bg=palette["bg"],
                         highlightthickness=0, bd=0)
        self.palette, self.icon, self.title, self.value = palette, icon, title, value
        self._icon_image = None
        self.bind("<Configure>", self._paint)

    def _paint(self, event):
        self.delete("all")
        c = self.palette
        width = max(180, event.width)
        _rounded_rect(self, 1, 1, width - 2, 155, 20,
                      fill=c["surface"], outline=c["border_glow"])
        self._icon_image = lucide_icon(
            self.icon, size=25, state="active", dark=c["bg"].lower() == "#090b0f",
        )
        if self._icon_image:
            self.create_image(22, 28, image=self._icon_image, anchor="w")
        self.create_text(22, 70, text=self.title, anchor="w", font=body(11),
                         fill=c["text_dim"], width=width - 40)
        self.create_text(22, 115, text=self.value, anchor="w", font=heading(27),
                         fill=c["text"], width=width - 40)


def _paint_completion(canvas, palette, model):
    width = max(350, canvas.winfo_width())
    canvas.delete("all")
    _rounded_rect(canvas, 1, 1, width - 2, 306, 20,
                  fill=palette["surface"], outline=palette["border"])
    canvas.create_text(25, 29, text=ui("Taxa de conclusão", "Completion rate"),
                       anchor="w", font=section(14), fill=palette["text"])
    canvas.create_text(25, 56, text=ui("Das HQs que você iniciou.", "Of comics you started."),
                       anchor="w", font=caption(10), fill=palette["text_dim"])
    diameter = 152
    left, top = 35, 93
    canvas.create_arc(left, top, left + diameter, top + diameter,
                      start=90, extent=-359.9, style="arc", width=18,
                      outline=palette["progress_bg"])
    if model["completion_percent"]:
        canvas.create_arc(left, top, left + diameter, top + diameter,
                          start=90, extent=-359.9 * model["completion_percent"] / 100,
                          style="arc", width=18, outline=palette["accent"])
    canvas.create_text(left + diameter / 2, top + diameter / 2 - 8,
                       text=f'{model["completion_percent"]}%', font=heading(25),
                       fill=palette["text"])
    canvas.create_text(left + diameter / 2, top + diameter / 2 + 19,
                       text=ui("concluídas", "completed"), font=caption(9),
                       fill=palette["text_dim"])
    label_x = min(width - 180, 229)
    rows = (
        (palette["accent"], ui("Concluídas", "Completed"), model["completed"]),
        (palette["text_dim"], ui("Em andamento", "In progress"),
         model["started"] - model["completed"]),
    )
    for index, (color, title, value) in enumerate(rows):
        y = 139 + index * 45
        canvas.create_oval(label_x, y - 6, label_x + 12, y + 6, fill=color, outline="")
        canvas.create_text(label_x + 23, y, text=f"{value}  {title}", anchor="w",
                           font=body(11), fill=palette["text"])


def _recent_panel(parent, palette, model):
    card = tk.Canvas(parent, width=490, height=308, bg=palette["bg"],
                     highlightthickness=0, bd=0)

    def paint(event):
        card.delete("all")
        width = max(350, event.width)
        _rounded_rect(card, 1, 1, width - 2, 306, 20,
                      fill=palette["surface"], outline=palette["border"])
        card.create_text(25, 29, text=ui("Leituras recentes", "Recent reading"),
                         anchor="w", font=section(14), fill=palette["text"])
        card.create_text(25, 56, text=ui("Seu progresso salvo neste dispositivo.",
                                        "Your progress saved on this device."),
                         anchor="w", font=caption(10), fill=palette["text_dim"])
        if not model["recent"]:
            card.create_text(25, 151,
                             text=ui("Nenhuma leitura recente nesta biblioteca.",
                                     "No recent reading in this library."),
                             anchor="w", font=body(11), fill=palette["text_dim"])
            return
        for index, (stamp, path, page) in enumerate(model["recent"]):
            y = 101 + index * 39
            title = Path(path).stem
            if len(title) > 39:
                title = title[:37] + "…"
            card.create_text(25, y, text=title, anchor="w", font=body(10, bold=True),
                             fill=palette["text"], width=max(145, width - 195))
            detail = ui(f"Pág. {page + 1}", f"Page {page + 1}")
            if stamp:
                try:
                    detail += "  ·  " + dt.datetime.fromtimestamp(stamp).strftime("%d/%m/%Y")
                except (OverflowError, OSError, ValueError):
                    pass
            card.create_text(width - 25, y, text=detail, anchor="e", font=caption(9),
                             fill=palette["text_dim"])
            if index < len(model["recent"]) - 1:
                card.create_line(25, y + 19, width - 25, y + 19,
                                 fill=palette["border"])

    card.bind("<Configure>", paint)
    return card


def _chart_card(parent, palette, title, subtitle, painter, *, height=270):
    card = tk.Canvas(parent, height=height, bg=palette["bg"], highlightthickness=0, bd=0)

    def paint(event):
        card.delete("all")
        width = max(360, event.width)
        _rounded_rect(card, 1, 1, width - 2, height - 2, 20,
                      fill=palette["surface"], outline=palette["border"])
        card.create_text(25, 28, text=title, anchor="w", font=section(14),
                         fill=palette["text"])
        card.create_text(25, 54, text=subtitle, anchor="w", font=caption(9),
                         fill=palette["text_dim"])
        painter(card, palette, width, height)

    card.bind("<Configure>", paint)
    return card


def _paint_weekly_chart(canvas, palette, width, height, model):
    values = [item["pages"] for item in model["weekly"]]
    left, right, top, bottom = 48, width - 20, 91, height - 34
    maximum = max(values + [1])
    for line in range(4):
        y = top + (bottom - top) * line / 3
        canvas.create_line(left, y, right, y, fill=palette["border"], dash=(3, 4))
        value = round(maximum * (3 - line) / 3)
        canvas.create_text(left - 9, y, text=str(value), anchor="e",
                           font=caption(8), fill=palette["text_dim"])
    points = []
    step = (right - left) / max(1, len(values) - 1)
    for index, value in enumerate(values):
        x = left + index * step
        y = bottom - value / maximum * (bottom - top)
        points.extend((x, y))
        canvas.create_text(x, bottom + 18, text=ui(f"Sem {index + 1}", f"W{index + 1}"),
                           font=caption(8), fill=palette["text_dim"])
    if any(values):
        polygon = [left, bottom, *points, right, bottom]
        canvas.create_polygon(polygon, fill=palette.get("accent_dark", "#431018"), outline="")
    if len(points) >= 4:
        canvas.create_line(*points, fill=palette["accent"], width=3, smooth=True)
    for index, value in enumerate(values):
        x = left + index * step
        y = bottom - value / maximum * (bottom - top)
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4,
                           fill=palette["accent2"], outline=palette["accent"])
    if not any(values):
        canvas.create_text((left + right) / 2, (top + bottom) / 2,
                           text=ui("Continue lendo para gerar sua atividade.",
                                   "Keep reading to generate your activity."),
                           font=body(10), fill=palette["text_dim"])


def _paint_daily_chart(canvas, palette, width, height, model):
    values = [item["pages"] for item in model["daily"]]
    left, right, top, bottom = 48, width - 18, 91, height - 34
    maximum = max(values + [1])
    for line in range(4):
        y = top + (bottom - top) * line / 3
        canvas.create_line(left, y, right, y, fill=palette["border"], dash=(3, 4))
        canvas.create_text(left - 9, y, text=str(round(maximum * (3 - line) / 3)),
                           anchor="e", font=caption(8), fill=palette["text_dim"])
    slot = (right - left) / max(1, len(values))
    bar_width = max(4, min(20, slot * .56))
    for index, item in enumerate(model["daily"]):
        x = left + slot * (index + .5)
        bar_top = bottom - item["pages"] / maximum * (bottom - top)
        canvas.create_rectangle(x - bar_width / 2, bar_top, x + bar_width / 2, bottom,
                                fill=palette["accent"], outline="")
        canvas.create_text(x, bottom + 18, text=item["date"].strftime("%d/%m"),
                           font=caption(7), fill=palette["text_dim"])
    if not any(values):
        canvas.create_text((left + right) / 2, (top + bottom) / 2,
                           text=ui("Nenhuma página registrada nos últimos 14 dias.",
                                   "No pages recorded in the last 14 days."),
                           font=body(10), fill=palette["text_dim"])


def _genres_panel(parent, palette, model):
    height = 308
    card = tk.Canvas(parent, height=height, bg=palette["bg"], highlightthickness=0, bd=0)

    def paint(event):
        card.delete("all")
        width = max(350, event.width)
        _rounded_rect(card, 1, 1, width - 2, height - 2, 20,
                      fill=palette["surface"], outline=palette["border"])
        card.create_text(25, 29, text=ui("Gêneros mais lidos", "Most-read genres"),
                         anchor="w", font=section(14), fill=palette["text"])
        card.create_text(25, 56, text=ui("Com base nas páginas lidas.",
                                        "Based on pages read."),
                         anchor="w", font=caption(9), fill=palette["text_dim"])
        genres = model["genres"]
        if not genres:
            card.create_text(25, 151,
                             text=ui("Adicione gêneros às HQs para ver esta distribuição.",
                                     "Add genres to comics to see this distribution."),
                             anchor="w", font=body(10), fill=palette["text_dim"])
            return
        maximum = max(value for _name, value in genres) or 1
        total = sum(value for _name, value in genres) or 1
        for index, (name, value) in enumerate(genres):
            y = 96 + index * 40
            card.create_text(25, y, text=name, anchor="w", font=body(10),
                             fill=palette["text"])
            bar_left, bar_right = min(165, width * .32), width - 103
            card.create_rectangle(bar_left, y - 6, bar_right, y + 6,
                                  fill=palette["progress_bg"], outline="")
            card.create_rectangle(bar_left, y - 6,
                                  bar_left + (bar_right - bar_left) * value / maximum,
                                  y + 6, fill=palette["accent"], outline="")
            card.create_text(width - 84, y, text=f"{value}", anchor="w",
                             font=caption(9), fill=palette["text"])
            card.create_text(width - 22, y, text=f"{round(value * 100 / total)}%",
                             anchor="e", font=caption(9), fill=palette["text_dim"])

    card.bind("<Configure>", paint)
    return card


def render_statistics(parent, palette, on_library):
    model = statistics_model(personal_statistics(), load_progress())
    canvas = tk.Canvas(parent, bg=palette["bg"], highlightthickness=0, bd=0)
    scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    content = tk.Frame(canvas, bg=palette["bg"])
    window_id = canvas.create_window((0, 0), window=content, anchor="nw")
    content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)

    def pointer_is_inside():
        try:
            x, y = canvas.winfo_pointerxy()
            left, top = canvas.winfo_rootx(), canvas.winfo_rooty()
            return (left <= x < left + canvas.winfo_width()
                    and top <= y < top + canvas.winfo_height())
        except tk.TclError:
            return False

    def scroll_windows(event):
        if pointer_is_inside() and event.delta:
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"
        return None

    def scroll_linux(event):
        if pointer_is_inside():
            canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
            return "break"
        return None

    scroll_binding_ids = {
        "<MouseWheel>": canvas.bind_all("<MouseWheel>", scroll_windows, add="+"),
        "<Button-4>": canvas.bind_all("<Button-4>", scroll_linux, add="+"),
        "<Button-5>": canvas.bind_all("<Button-5>", scroll_linux, add="+"),
    }

    def release_scroll_bindings(event):
        if event.widget is canvas:
            try:
                for sequence, binding_id in scroll_binding_ids.items():
                    canvas.unbind_class("all", sequence, binding_id)
            except tk.TclError:
                pass

    canvas.bind("<Destroy>", release_scroll_bindings, add="+")

    heading_row = tk.Frame(content, bg=palette["bg"])
    heading_row.pack(fill="x", padx=CONTENT_PADDING, pady=(22, 8))
    tk.Label(heading_row, text=ui("Estatísticas", "Statistics"), font=heading(25),
             bg=palette["bg"], fg=palette["text"]).pack(side="left")
    KomicoveButton(heading_row, ui("Biblioteca", "Library"), on_library,
                   palette, compact=True, icon_name="library").pack(side="right")

    intro = tk.Frame(content, bg=palette["bg"])
    intro.pack(fill="x", padx=CONTENT_PADDING, pady=(6, 18))
    intro_icon = lucide_icon("chart-no-axes-column-increasing", size=27, state="active",
                             dark=palette["bg"].lower() == "#090b0f")
    icon_label = tk.Label(intro, image=intro_icon, bg=palette["bg"], bd=0)
    icon_label.image = intro_icon
    icon_label.pack(side="left", padx=(0, 9))
    text = tk.Frame(intro, bg=palette["bg"])
    text.pack(side="left")
    tk.Label(text, text=ui("Estatísticas pessoais", "Personal statistics"),
             font=heading(18), bg=palette["bg"], fg=palette["text"]).pack(anchor="w")
    tk.Label(text, text=ui("Acompanhe sua leitura. Os dados ficam neste dispositivo.",
                           "Follow your reading. The data stays on this device."),
             font=body(10), bg=palette["bg"], fg=palette["text_dim"]).pack(anchor="w")

    metrics = tk.Frame(content, bg=palette["bg"])
    metrics.pack(fill="x", padx=CONTENT_PADDING - 7)
    for column in range(4):
        metrics.grid_columnconfigure(column, weight=1, uniform="statistics")
    hours, minutes = divmod(model["seconds"] // 60, 60)
    values = (
        ("book-open", ui("HQs concluídas", "Completed comics"), str(model["completed"])),
        ("list", ui("Páginas lidas", "Pages read"),
         ui(f'{model["pages"]:,}'.replace(",", "."), f'{model["pages"]:,}')),
        ("rotate-cw", ui("Tempo de leitura", "Reading time"), f"{hours}h {minutes:02d}min"),
        ("library", ui("HQs iniciadas", "Started comics"), str(model["started"])),
    )
    for column, (icon, title, value) in enumerate(values):
        _StatisticTile(metrics, palette, icon, title, value).grid(
            row=0, column=column, sticky="ew", padx=7)

    charts = tk.Frame(content, bg=palette["bg"])
    charts.pack(fill="x", padx=CONTENT_PADDING - 7, pady=(16, 0))
    charts.grid_columnconfigure(0, weight=1, uniform="statistics-chart")
    charts.grid_columnconfigure(1, weight=1, uniform="statistics-chart")
    _chart_card(
        charts, palette, ui("Atividade de leitura por semana", "Weekly reading activity"),
        ui("Páginas lidas nas últimas 8 semanas.", "Pages read over the last 8 weeks."),
        lambda cv, pal, width, height: _paint_weekly_chart(cv, pal, width, height, model),
    ).grid(row=0, column=0, sticky="ew", padx=7)
    _chart_card(
        charts, palette, ui("Páginas lidas por dia", "Pages read per day"),
        ui("Últimos 14 dias.", "Last 14 days."),
        lambda cv, pal, width, height: _paint_daily_chart(cv, pal, width, height, model),
    ).grid(row=0, column=1, sticky="ew", padx=7)

    panels = tk.Frame(content, bg=palette["bg"])
    panels.pack(fill="x", padx=CONTENT_PADDING - 7, pady=(16, 0))
    panels.grid_columnconfigure(0, weight=1, uniform="statistics-panel")
    panels.grid_columnconfigure(1, weight=1, uniform="statistics-panel")
    completion = tk.Canvas(panels, width=490, height=308, bg=palette["bg"],
                           highlightthickness=0, bd=0)
    completion.grid(row=0, column=0, sticky="ew", padx=7)
    completion.bind("<Configure>", lambda _event: _paint_completion(completion, palette, model))
    _genres_panel(panels, palette, model).grid(row=0, column=1, sticky="ew", padx=7)

    recent = tk.Frame(content, bg=palette["bg"])
    recent.pack(fill="x", padx=CONTENT_PADDING, pady=(16, 25))
    _recent_panel(recent, palette, model).pack(fill="x")
    return canvas
