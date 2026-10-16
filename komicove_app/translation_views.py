"""Reader-attached OCR and translation controls for the desktop app."""

import json
from io import BytesIO
from pathlib import Path
from statistics import median
from collections import deque
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor, CancelledError
from threading import Event
from queue import SimpleQueue, Empty
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk
from komicove_app.runtime import resource_path

from komicove_app.comic_translation import (
    TranslationError, recognize, local_translate, translate_remote, test_connection,
    read_cache, write_cache, read_ocr_cache, write_ocr_cache,
    apply_corrections, save_correction, clear_cache,
    load_key, save_key, tesseract_available, local_translation_available, detect_source,
    local_model_offer, local_model_download_size, install_local_offer,
    remove_local_model, rotate_regions, previous_page_context, export_cbz_copy,
    glossary_exact_match,
    PROVIDER_MODELS, PROVIDER_KEY_URLS, VISION_MODELS, auto_translation_candidate,
)
from komicove_app.storage import load_prefs, save_prefs
from komicove_app.translations import ui


class TranslationDialog(tk.Toplevel):
    def __init__(self, reader):
        super().__init__(reader)
        self.reader = reader
        self.title(ui("Tradução experimental", "Experimental translation"))
        self.geometry("1120x720")
        self.minsize(820, 540)
        self.configure(bg="#111014")
        self.transient(reader.winfo_toplevel())
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="comic-translation")
        self.preview_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="comic-preview")
        self.preview_updates = SimpleQueue()
        self.preview_ticket = 0
        self.preview_future = None
        self.preview_after = None
        self.preview_photo = None
        self.preview_zoom = 1.0
        self.preview_image_box = None
        self.preview_layout = None
        self.preview_press = None
        self.cancel = Event()
        self.future = None
        self.updates = SimpleQueue()
        self.model_offers = SimpleQueue()
        self.model_progress = SimpleQueue()
        self.export_progress = SimpleQueue()
        self.page = reader._idx
        self.regions = []
        self.regions_rotation = reader._rotation
        prefs = load_prefs()
        stored_source = prefs.get("translation_source", "auto")
        self.source = tk.StringVar(value="pt-BR" if stored_source == "pt" else stored_source)
        stored_target = prefs.get("translation_target", "pt-BR")
        self.target = tk.StringVar(value="pt-BR" if stored_target == "pt" else stored_target)
        self.ocr_language = tk.StringVar(value=prefs.get("translation_ocr", "eng"))
        self.provider = tk.StringVar(value=prefs.get("translation_provider", "local"))
        self.mode = tk.StringVar(value="local" if self.provider.get() == "local" else "remote")
        if self.mode.get() == "local" and not local_translation_available():
            self.mode.set("remote")
        self.model = tk.StringVar(value=prefs.get("translation_model", ""))
        self.custom = tk.StringVar(value=prefs.get("translation_endpoint", ""))
        if not self.model.get():
            self.model.set(PROVIDER_MODELS.get(self.provider.get(), ""))
        self.glossary = tk.StringVar(value=prefs.get("translation_glossary", "{}"))
        try:
            parsed = json.loads(self.glossary.get())
            self.glossary_terms = parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            self.glossary_terms = {}
        self.term_original = tk.StringVar()
        self.term_translation = tk.StringVar()
        self.show_advanced = tk.BooleanVar(value=False)
        self.scope = tk.StringVar(value="page")
        self.view = tk.StringVar(value=prefs.get("translation_view", "original"))
        self.consent = tk.BooleanVar(value=False)
        self.vision = tk.BooleanVar(value=bool(prefs.get("translation_vision", False)))
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_preview()
        self._queue_preview()
        self._load_page_cache()

    def _label(self, parent, label):
        widget = tk.Label(parent, text=label, bg=parent.cget("bg"), fg="#d7cfd4",
                          anchor="w", justify="left", font=("Segoe UI", 10))
        widget.pack(fill="x", padx=14, pady=(8, 3))
        widget.bind("<Configure>", lambda event: widget.configure(wraplength=max(100, event.width - 8)))
        return widget

    def _entry(self, parent, variable, *, secret=False):
        entry = tk.Entry(parent, textvariable=variable, show="*" if secret else "",
                         bg="#292329", fg="#fff", insertbackground="#fff", relief="flat",
                         font=("Segoe UI", 11))
        entry.pack(fill="x", padx=14, ipady=7)
        return entry

    def _button(self, parent, label, command):
        button = tk.Button(parent, text=label, command=command, bg="#38232a", fg="#fff",
                           activebackground="#a92238", activeforeground="#fff", relief="flat",
                           font=("Segoe UI", 10))
        button.pack(side="left", padx=4, pady=6, ipadx=9, ipady=7)
        return button

    def _language_menu(self, parent, variable, *, automatic=False):
        languages = [("auto", ui("Detectar automaticamente", "Detect automatically")),
                     ("pt-BR", ui("Português (Brasil)", "Portuguese (Brazil)")),
                     ("pt-PT", ui("Português (Portugal)", "Portuguese (Portugal)")),
                     ("en", ui("Inglês", "English")),
                     ("es", ui("Espanhol", "Spanish")), ("fr", ui("Francês", "French")),
                     ("de", ui("Alemão", "German")), ("it", ui("Italiano", "Italian")),
                     ("ja", ui("Japonês", "Japanese")), ("zh", ui("Chinês", "Chinese")),
                     ("ko", ui("Coreano", "Korean"))]
        if not automatic:
            languages = languages[1:]
        names = dict(languages)
        shown = tk.StringVar(value=names.get(variable.get(), variable.get()))
        picker = tk.OptionMenu(parent, shown, *names.values(),
                               command=lambda name: variable.set(next(code for code, label in languages if label == name)))
        picker.configure(bg="#242026", fg="#fff", activebackground="#38232a",
                         activeforeground="#fff", highlightthickness=0, relief="flat",
                         anchor="w", font=("Segoe UI", 10))
        picker["menu"].configure(bg="#242026", fg="#fff", activebackground="#a92238")
        picker.pack(fill="x", padx=14, ipady=3)
        variable.trace_add("write", lambda *_: shown.set(names.get(variable.get(), variable.get())))
        return picker

    def _build(self):
        panes = tk.PanedWindow(self, orient="horizontal", bg="#31252b", sashwidth=6,
                               borderwidth=0, relief="flat")
        panes.pack(fill="both", expand=True)
        controls = tk.Frame(panes, bg="#111014", width=420)
        preview_area = tk.Frame(panes, bg="#111014")
        panes.add(controls, minsize=350)
        panes.add(preview_area, minsize=360)
        fixed_actions = tk.Frame(controls, bg="#201a1f", padx=10, pady=8)
        fixed_actions.pack(side="bottom", fill="x")
        canvas = tk.Canvas(controls, bg="#111014", highlightthickness=0)
        scrollbar = tk.Scrollbar(controls, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg="#111014")
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"))
        tk.Label(preview_area, text=ui("Prévia da página", "Page preview"),
                 font=("Segoe UI", 17, "bold"), bg="#111014", fg="#fff",
                 anchor="w").pack(fill="x", padx=18, pady=(17, 3))
        tk.Label(preview_area, text=ui("Amplie e arraste para conferir os detalhes.", "Zoom and drag to inspect details."),
                 bg="#111014", fg="#ada6ad", anchor="w").pack(fill="x", padx=18)
        self.preview_mode_row = tk.Frame(preview_area, bg="#111014")
        self.preview_mode_row.pack(fill="x", padx=14, pady=(10, 8))
        zoom_controls = tk.Frame(preview_area, bg="#111014")
        zoom_controls.pack(fill="x", padx=14, pady=(0, 8))
        self._button(zoom_controls, "−", lambda: self._zoom_preview(.75))
        self.preview_zoom_label = tk.Label(zoom_controls, text="100%", bg="#111014", fg="#fff",
                                           font=("Segoe UI", 10))
        self.preview_zoom_label.pack(side="left", padx=7)
        self._button(zoom_controls, "+", lambda: self._zoom_preview(1.5))
        self._button(zoom_controls, ui("Encaixar", "Fit"), lambda: self._zoom_preview(1, reset=True))
        self._button(zoom_controls, ui("Exportar CBZ", "Export CBZ"), self._export)
        self.preview_canvas = tk.Canvas(preview_area, bg="#08090b", highlightthickness=1,
                                        highlightbackground="#3c353a")
        self.preview_canvas.pack(fill="both", expand=True, padx=18, pady=(0, 9))
        self.preview_canvas.bind("<Configure>", lambda _event: self._queue_preview())
        self.preview_canvas.bind("<ButtonPress-1>", self._preview_mouse_down)
        self.preview_canvas.bind("<B1-Motion>", self._preview_mouse_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._preview_mouse_up)
        self.preview_canvas.bind("<MouseWheel>", lambda event: self._zoom_preview(1.25 if event.delta > 0 else .8))
        self.preview_canvas.bind("<Button-4>", lambda _event: self._zoom_preview(1.25))
        self.preview_canvas.bind("<Button-5>", lambda _event: self._zoom_preview(.8))
        self.preview_caption = tk.Label(preview_area,
                                        text=ui("Traduza a página para ver o resultado aqui.",
                                                "Translate this page to see the result here."),
                                        bg="#242026", fg="#e8e3e5", font=("Segoe UI", 11),
                                        anchor="w", justify="left", wraplength=500, padx=14, pady=12)
        self.preview_caption.pack(fill="x", padx=18, pady=(0, 16))
        tk.Label(body, text=ui("Tradução experimental", "Experimental translation"),
                 font=("Segoe UI", 20, "bold"), bg="#111014", fg="#fff").pack(anchor="w", padx=18, pady=(15, 2))
        tk.Label(body, text=ui("Experimental, em melhoria contínua.",
                               "Experimental, with ongoing improvements."),
                 font=("Segoe UI", 10), bg="#111014", fg="#b9afb5").pack(anchor="w", padx=18, pady=(0, 12))
        settings_card = tk.Frame(body, bg="#1e1a1f", pady=10)
        settings_card.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(settings_card, text=ui("Como traduzir", "How to translate"),
                 font=("Segoe UI", 13, "bold"), bg="#1e1a1f", fg="#fff").pack(anchor="w", padx=14, pady=(0, 5))
        upper = tk.Frame(settings_card, bg="#1e1a1f")
        upper.pack(fill="x")
        left, right = (tk.Frame(upper, bg="#1e1a1f") for _ in range(2))
        left.pack(fill="x")
        right.pack(fill="x")
        self._label(left, ui("Idioma original", "Original language"))
        self._language_menu(left, self.source, automatic=True)
        self._label(right, ui("Idioma de destino", "Target language"))
        self._language_menu(right, self.target)
        modes = tk.Frame(settings_card, bg="#1e1a1f"); modes.pack(fill="x", padx=10, pady=(13, 4))
        self.mode_row = modes
        for value, pt, en in (("local", "IA local", "Local AI"), ("remote", "Minha IA", "My AI")):
            tk.Radiobutton(modes, text=ui(pt, en), value=value, variable=self.mode,
                           command=self._mode_changed, bg="#1e1a1f", fg="#fff",
                           selectcolor="#38232a", activebackground="#1e1a1f",
                           activeforeground="#fff", font=("Segoe UI", 11),
                           state="normal" if value != "local" or local_translation_available() else "disabled").pack(side="left", padx=4)
        self.local_options = tk.Frame(settings_card, bg="#1e1a1f")
        if local_translation_available():
            self._label(self.local_options, ui("Usa os quadros da leitura guiada e reconhece o texto no aparelho. Se faltar um idioma, mostraremos o tamanho antes de baixar.",
                                               "Uses guided reading panels and recognizes text on this device. If a language is missing, its download size appears first."))
        else:
            self._label(self.local_options, ui("IA local indisponível nesta instalação.",
                                               "Local AI is unavailable in this installation."))
        self.remote_options = tk.Frame(settings_card, bg="#1e1a1f")
        self._label(self.remote_options, ui("1. Escolha o serviço", "1. Choose a service"))
        provider_row = tk.Frame(self.remote_options, bg="#1e1a1f"); provider_row.pack(fill="x", padx=14)
        providers = {"openai": "OpenAI", "anthropic": "Anthropic", "xai": "xAI",
                     "groq": "Groq", "openrouter": "OpenRouter", "gemini": "Gemini",
                     "compatible": ui("Outro serviço compatível", "Other compatible service")}
        if self.provider.get() == "local":
            self.provider.set("openai")
            if not self.model.get():
                self.model.set(PROVIDER_MODELS["openai"])
        shown_provider = tk.StringVar(value=providers.get(self.provider.get(), "OpenAI"))
        provider_picker = tk.OptionMenu(provider_row, shown_provider, *providers.values(),
            command=lambda selected: (self.provider.set(next(key for key, value in providers.items()
                                                             if value == selected)), self._provider_changed()))
        provider_picker.configure(bg="#292329", fg="#fff", activebackground="#38232a",
                                  activeforeground="#fff", highlightthickness=0, relief="flat",
                                  font=("Segoe UI", 10))
        provider_picker["menu"].configure(bg="#292329", fg="#fff", activebackground="#a92238")
        provider_picker.pack(side="left", fill="x", expand=True)
        self.provider.trace_add("write", lambda *_: shown_provider.set(providers.get(self.provider.get(), "OpenAI")))
        self._button(provider_row, ui("2. Obter chave oficial", "2. Get official key"), self._open_key_page)
        self._label(self.remote_options, ui("3. Cole a chave API", "3. Paste the API key"))
        self.key = tk.StringVar()
        self._entry(self.remote_options, self.key, secret=True)
        row = tk.Frame(self.remote_options, bg="#1e1a1f"); row.pack(fill="x", padx=10)
        self._button(row, ui("Guardar chave", "Save key"), self._save_key)
        self._button(row, ui("4. Testar conexão (pode cobrar)", "4. Test connection (may cost)"), self._test)
        self._label(self.remote_options, ui("A API pode cobrar por uso. Assinatura de chat não inclui acesso à API. Verifique chave, saldo e modelo se o teste falhar.",
                                             "API usage may cost money. A chat subscription does not include API access. Check the key, balance and model if the test fails."))
        self._label(self.remote_options, ui("Enviamos texto detectado, idiomas, glossário e diálogos próximos. Se você marcar imagem, enviamos também uma versão reduzida da página; isso pode custar mais.",
                                             "We send detected text, languages, glossary and nearby dialogue. If you select image, we also send a reduced page image; this may cost more."))
        tk.Checkbutton(self.remote_options, text=ui("Enviar imagem quando o modelo aceitar", "Send image when the model supports it"),
                       variable=self.vision, bg="#1e1a1f", fg="#fff", selectcolor="#38232a",
                       activebackground="#1e1a1f", activeforeground="#fff").pack(anchor="w", padx=14)
        tk.Checkbutton(self.remote_options, text=ui("Autorizo enviar esses dados", "I allow sending this data"),
                       variable=self.consent, bg="#1e1a1f", fg="#fff", selectcolor="#38232a",
                       activebackground="#1e1a1f", activeforeground="#fff").pack(anchor="w", padx=14)
        self.glossary_options = tk.Frame(body, bg="#111014")
        term_row = tk.Frame(self.glossary_options, bg="#111014"); term_row.pack(fill="x", padx=14)
        self._label(term_row, ui("Original", "Original")); self._entry(term_row, self.term_original)
        self._label(term_row, ui("Tradução", "Translation")); self._entry(term_row, self.term_translation)
        buttons = tk.Frame(self.glossary_options, bg="#111014"); buttons.pack(fill="x", padx=10)
        self._button(buttons, ui("Adicionar / editar", "Add / edit"), self._add_term)
        self._button(buttons, ui("Remover", "Remove"), self._remove_term)
        self.glossary_list = tk.Listbox(self.glossary_options, bg="#242026", fg="#fff", selectbackground="#a92238", height=3)
        self.glossary_list.pack(fill="x", padx=14)
        self.glossary_list.bind("<<ListboxSelect>>", self._select_term)
        self._refresh_terms()
        self.advanced_options = tk.Frame(body, bg="#111014")
        self.remote_advanced = tk.Frame(self.advanced_options, bg="#111014")
        self._label(self.remote_advanced, ui("Modelo API", "API model")); self._entry(self.remote_advanced, self.model)
        self._label(self.remote_advanced, ui("Endereço HTTPS personalizado", "Custom HTTPS address")); self._entry(self.remote_advanced, self.custom)
        self.local_advanced = tk.Frame(self.advanced_options, bg="#111014")
        self._button(self.local_advanced, ui("Remover idioma baixado", "Remove downloaded language"), self._remove_model)
        advanced_toggle = tk.Checkbutton(body, text=ui("Opções avançadas", "Advanced options"), variable=self.show_advanced,
                       command=self._toggle_advanced, bg="#111014", fg="#fff", selectcolor="#38232a",
                       activebackground="#111014", activeforeground="#fff")
        self._mode_changed()
        scope_toggle = tk.Button(body, text=ui("Página atual · alterar escopo", "Current page · change scope"),
                                 command=self._toggle_scope, bg="#242026", fg="#fff", relief="flat")
        scope_toggle.pack(fill="x", padx=14, pady=(10, 4), ipady=6)
        self.scope_toggle = scope_toggle
        scopes = tk.Frame(body, bg="#111014")
        self.scope_options = scopes
        for index, (value, pt, en) in enumerate((("region", "Região selecionada", "Selected region"),
                              ("panel", "Quadro atual", "Current panel"),
                              ("page", "Página atual", "Current page"), ("book", "HQ inteira", "Whole comic"))):
            tk.Radiobutton(scopes, text=ui(pt, en), value=value, variable=self.scope,
                           command=self._scope_changed,
                           bg="#111014", fg="#fff", selectcolor="#38232a",
                           activebackground="#111014", activeforeground="#fff").grid(row=index // 2,
                                                                                       column=index % 2, sticky="w", padx=4)
        actions = tk.Frame(fixed_actions, bg="#201a1f"); actions.pack(fill="x")
        translate_button = self._button(actions, ui("Traduzir", "Translate"), lambda: self._start(True))
        translate_button.configure(bg="#bd263f", font=("Segoe UI", 12, "bold"))
        self._button(actions, ui("Cancelar", "Cancel"), self.cancel.set)
        self._button(actions, ui("Voltar", "Back"), self.close)
        glossary_toggle = tk.Button(body, text=ui("Glossário", "Glossary"), command=self._toggle_glossary,
                                    bg="#38232a", fg="#fff", relief="flat")
        glossary_toggle.pack(anchor="w", padx=14, pady=4, ipadx=7, ipady=5)
        self.glossary_toggle = glossary_toggle
        advanced_toggle.pack(anchor="w", padx=14)
        self.advanced_toggle = advanced_toggle
        modes = self.preview_mode_row
        for value, pt, en in (("original", "Original", "Original"),
                              ("overlay", "Sobreposição", "Overlay"),
                              ("compare", "Comparar", "Compare")):
            tk.Radiobutton(modes, text=ui(pt, en), value=value, variable=self.view,
                           command=self._set_view, bg="#111014", fg="#fff", selectcolor="#38232a",
                           activebackground="#111014", activeforeground="#fff").pack(side="left", padx=4)
        self.status = tk.Label(fixed_actions, text="", bg="#201a1f", fg="#e8e3e5", anchor="w")
        self.status.pack(fill="x", padx=4)
        review_toggle = tk.Button(body, text=ui("Revisar texto e correções", "Review text and corrections"),
                                  command=self._toggle_review, bg="#242026", fg="#fff", relief="flat")
        review_toggle.pack(fill="x", padx=14, pady=(8, 4), ipady=6)
        self.review_toggle = review_toggle
        review = tk.Frame(body, bg="#111014")
        self.review_options = review
        detect_row = tk.Frame(review, bg="#111014"); detect_row.pack(fill="x", padx=10)
        self._button(detect_row, ui("Detectar texto", "Detect text"), lambda: self._start(False))
        self.list = tk.Listbox(review, bg="#242026", fg="#fff", selectbackground="#a92238", height=6)
        self.list.pack(fill="both", expand=True, padx=14, pady=4)
        self.list.bind("<<ListboxSelect>>", self._select)
        self._label(review, ui("Original / correção", "Original / correction"))
        self.original = tk.Text(review, bg="#242026", fg="#fff", insertbackground="#fff", relief="flat",
                                height=3, wrap="word")
        self.original.pack(fill="x", padx=14, ipady=5)
        self._label(review, ui("Tradução completa / correção", "Full translation / correction"))
        self.translated = tk.Text(review, bg="#242026", fg="#fff", insertbackground="#fff", relief="flat",
                                  height=4, wrap="word")
        self.translated.pack(fill="x", padx=14, ipady=5)
        footer = tk.Frame(review, bg="#111014"); footer.pack(fill="x", padx=10)
        self._button(footer, ui("Salvar correções", "Save corrections"), self._save_correction)

    def _toggle_scope(self):
        if self.scope_options.winfo_manager():
            self.scope_options.pack_forget()
        else:
            self.scope_options.pack(after=self.scope_toggle, fill="x", padx=10)

    def _scope_changed(self):
        labels = {"region": ui("Região selecionada", "Selected region"),
                  "panel": ui("Quadro atual", "Current panel"),
                  "page": ui("Página atual", "Current page"),
                  "book": ui("HQ inteira", "Whole comic")}
        self.scope_toggle.config(text=labels[self.scope.get()] + " · " + ui("alterar escopo", "change scope"))

    def _toggle_review(self):
        if self.review_options.winfo_manager():
            self.review_options.pack_forget()
        else:
            self.review_options.pack(after=self.review_toggle, fill="x")

    def _queue_preview(self):
        if self.preview_after is not None:
            self.after_cancel(self.preview_after)
        self.preview_after = self.after(130, self._start_preview)

    def _zoom_preview(self, factor, *, reset=False):
        self.preview_zoom = 1.0 if reset else min(4.0, max(1.0, self.preview_zoom * factor))
        self.preview_zoom_label.config(text=f"{self.preview_zoom * 100:.0f}%")
        self._queue_preview()

    def _preview_mouse_down(self, event):
        self.preview_press = (event.x, event.y)
        self.preview_canvas.scan_mark(event.x, event.y)

    def _preview_mouse_drag(self, event):
        self.preview_canvas.scan_dragto(event.x, event.y, gain=1)

    def _preview_mouse_up(self, event):
        if not self.preview_press or not self.preview_image_box or not self.regions:
            return
        if abs(event.x - self.preview_press[0]) + abs(event.y - self.preview_press[1]) > 6:
            return
        x0, y0, width, height = self.preview_image_box
        x = (self.preview_canvas.canvasx(event.x) - x0) / max(1, width)
        y = (self.preview_canvas.canvasy(event.y) - y0) / max(1, height)
        if self.preview_layout:
            page_width, page_height, image_width, image_height, gap, heading = self.preview_layout
            x *= image_width
            y *= image_height
            if x >= page_width + gap:
                x -= page_width + gap
            if not (0 <= x <= page_width and heading <= y <= heading + page_height):
                return
            x /= page_width
            y = (y - heading) / page_height
        for index, region in enumerate(self.regions):
            left, top, right, bottom = region.box
            if left <= x <= right and top <= y <= bottom:
                self.list.selection_clear(0, tk.END)
                self.list.selection_set(index)
                self._select()
                break

    def _start_preview(self):
        self.preview_after = None
        self._sync_rotation()
        width, height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        if width < 80 or height < 80:
            return
        self.preview_ticket += 1
        ticket = self.preview_ticket
        if self.preview_future and not self.preview_future.running():
            self.preview_future.cancel()
        selected = self.list.curselection()
        index = selected[0] if selected else None
        rows = list(self.regions or [])
        self.preview_future = self.preview_executor.submit(
            self._render_preview, ticket, width, height, self.preview_zoom, self.view.get(), rows, index,
            self.reader._rotation)

    def _render_preview(self, ticket, width, height, zoom, view, rows, index, rotation):
        try:
            page = self._image(self.page, rotation).convert("RGB")
            page.thumbnail((1200, 1200) if view == "compare" else (1800, 1800),
                           Image.Resampling.LANCZOS)
            page_width, page_height = page.size
            gap, heading = (12, 30) if view == "compare" else (0, 0)
            if view == "compare":
                result = draw_translation_overlay(page, rows, (0, 0, page.width, page.height)) if rows else page.copy()
                compared = Image.new("RGB", (page_width * 2 + gap, page_height + heading), "#201a1f")
                compared.paste(page, (0, heading))
                compared.paste(result, (page_width + gap, heading))
                labels = ImageDraw.Draw(compared)
                font = _comic_font("Original Traduzido", 18)
                labels.text((8, 4), ui("Original", "Original"), font=font, fill="#fff")
                labels.text((page_width + gap + 8, 4), ui("Traduzido", "Translated"), font=font, fill="#fff")
                page = compared
            elif view == "overlay" and rows:
                page = draw_translation_overlay(page, rows, (0, 0, page.width, page.height))
            if index is not None and index < len(rows):
                l, t, r, b = rows[index].box
                for offset in ((0, page_width + gap) if view == "compare" else (0,)):
                    ImageDraw.Draw(page).rectangle((int(offset + l * page_width), int(heading + t * page_height),
                                                    int(offset + r * page_width), int(heading + b * page_height)),
                                                   outline="#ed3047", width=max(2, page_width // 500))
            layout = (page_width, page_height, page.width, page.height, gap, heading)
            page.thumbnail((max(1, int((width - 18) * zoom)),
                            max(1, int((height - 18) * zoom))), Image.Resampling.LANCZOS)
            self.preview_updates.put((ticket, page, layout))
        except (OSError, ValueError):
            self.preview_updates.put((ticket, None, None))

    def _poll_preview(self):
        if not self.winfo_exists():
            return
        while True:
            try:
                ticket, page, layout = self.preview_updates.get_nowait()
            except Empty:
                break
            if ticket != self.preview_ticket:
                continue
            self.preview_canvas.delete("all")
            if page is None:
                self.preview_caption.config(text=ui("Não foi possível abrir a prévia.",
                                                    "Could not open the preview."))
                continue
            self.preview_photo = ImageTk.PhotoImage(page, master=self.preview_canvas)
            self.preview_layout = layout
            canvas_width, canvas_height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
            origin_x = max(0, (canvas_width - page.width) // 2)
            origin_y = max(0, (canvas_height - page.height) // 2)
            self.preview_image_box = (origin_x, origin_y, page.width, page.height)
            self.preview_canvas.create_image(origin_x, origin_y,
                                             anchor="nw", image=self.preview_photo)
            self.preview_canvas.configure(scrollregion=(0, 0, max(canvas_width, page.width),
                                                        max(canvas_height, page.height)))
        self.after(120, self._poll_preview)

    def _update_preview_caption(self):
        selected = self.list.curselection()
        if selected and self.regions and selected[0] < len(self.regions):
            region = self.regions[selected[0]]
            self.preview_caption.config(text=f"{region.original}\n{region.translated or '…'}")
        else:
            self.preview_caption.config(text=ui("Escolha um trecho para ver original e tradução.",
                                                "Select an excerpt to see its original and translation."))

    def _mode_changed(self):
        self.local_options.pack_forget()
        self.remote_options.pack_forget()
        self.local_advanced.pack_forget()
        self.remote_advanced.pack_forget()
        options = self.local_options if self.mode.get() == "local" else self.remote_options
        options.pack(after=self.mode_row, fill="x")
        advanced = self.local_advanced if self.mode.get() == "local" else self.remote_advanced
        advanced.pack(fill="x")

    def _toggle_advanced(self):
        if self.show_advanced.get():
            self.advanced_options.pack(after=self.advanced_toggle, fill="x")
        else:
            self.advanced_options.pack_forget()

    def _toggle_glossary(self):
        if self.glossary_options.winfo_manager():
            self.glossary_options.pack_forget()
        else:
            self.glossary_options.pack(after=self.glossary_toggle, fill="x")

    def _provider_changed(self):
        suggested = PROVIDER_MODELS.get(self.provider.get(), "")
        if not self.model.get() or self.model.get() in PROVIDER_MODELS.values():
            self.model.set(suggested)
        self.custom.set("")

    def _open_key_page(self):
        url = PROVIDER_KEY_URLS.get(self.provider.get())
        if url:
            webbrowser.open(url)
        else:
            self.show_advanced.set(True)
            self._toggle_advanced()
            self.status.config(text=ui("Informe o endereço do serviço e obtenha a chave no site oficial dele.",
                                       "Enter the service address and get a key from its official site."))

    def _refresh_terms(self):
        self.glossary_list.delete(0, tk.END)
        for original, translation in self.glossary_terms.items():
            self.glossary_list.insert(tk.END, f"{original}  →  {translation}")
        self.glossary.set(json.dumps(self.glossary_terms, ensure_ascii=False, sort_keys=True))

    def _select_term(self, _event=None):
        if not self.glossary_list.curselection():
            return
        original = list(self.glossary_terms)[self.glossary_list.curselection()[0]]
        self.term_original.set(original)
        self.term_translation.set(self.glossary_terms[original])

    def _add_term(self):
        original, translation = self.term_original.get().strip(), self.term_translation.get().strip()
        if not original or not translation:
            self.status.config(text=ui("Preencha os dois campos do glossário.", "Fill both glossary fields."))
            return
        selected = self.glossary_list.curselection()
        previous = list(self.glossary_terms)[selected[0]] if selected else None
        if any(term.casefold() == original.casefold() and term != previous for term in self.glossary_terms):
            self.status.config(text=ui("Esse termo já existe.", "That term already exists."))
            return
        if previous and previous != original:
            del self.glossary_terms[previous]
        self.glossary_terms[original] = translation
        self._refresh_terms()
        self._settings()
        self.term_original.set(""); self.term_translation.set("")

    def _remove_term(self):
        selected = self.glossary_list.curselection()
        if not selected:
            return
        del self.glossary_terms[list(self.glossary_terms)[selected[0]]]
        self._refresh_terms()
        self._settings()
        self.term_original.set(""); self.term_translation.set("")

    def _settings(self):
        provider = "local" if self.mode.get() == "local" else self.provider.get().strip().lower()
        vision = bool(self.vision.get() and self.model.get().strip() in VISION_MODELS.get(provider, ()))
        self.ocr_language.set({"pt": "por", "pt-BR": "por", "pt-PT": "por",
                               "en": "eng", "es": "spa", "fr": "fra",
                               "de": "deu", "it": "ita", "ja": "jpn", "zh": "chi_sim",
                               "ko": "kor"}.get(self.source.get().strip(), "eng"))
        values = dict(translation_source=self.source.get().strip(),
                      translation_target=self.target.get().strip(),
                      translation_ocr=self.ocr_language.get().strip(),
                      translation_provider=provider,
                      translation_model=self.model.get().strip(),
                      translation_endpoint=self.custom.get().strip(),
                      translation_glossary=self.glossary.get().strip(),
                      translation_vision=vision,
                      translation_view=self.view.get())
        save_prefs(**values)
        return values

    def _set_view(self):
        self._sync_rotation()
        self._settings()
        self.reader._translation_view = self.view.get()
        self.reader._show(reset=False)
        self._queue_preview()

    def _save_key(self):
        try:
            if not self.key.get().strip():
                self.status.config(text=ui("Cole uma chave antes de guardar.", "Paste a key before saving."))
                return
            save_key(self.provider.get().strip().lower(), self.key.get().strip())
            self.key.set("")
            self.status.config(text=ui("Chave guardada no sistema.", "Key saved in the system."))
        except TranslationError as exc:
            self._error(exc)

    def _test(self):
        if self.future and not self.future.done():
            return
        provider = self.provider.get().strip().lower()
        try:
            key = self.key.get().strip() or load_key(provider)
        except TranslationError as exc:
            self._error(exc); return
        self.status.config(text=ui("Testando conexão...", "Testing connection..."))
        self.future = self.executor.submit(test_connection, provider, self.model.get().strip(),
                                           key, self.custom.get().strip())
        self._poll(lambda _: self.status.config(text=ui("Conexão confirmada.", "Connection confirmed.")))

    def _clear(self):
        if self.future and not self.future.done():
            return
        self.future = self.executor.submit(clear_cache)
        self._poll(lambda _: self.status.config(text=ui("Cache limpo. Correções manuais preservadas.", "Cache cleared. Manual corrections kept.")))

    def _remove_model(self):
        if self.future and not self.future.done():
            return
        source = self.source.get().strip()
        target = self.target.get().strip()
        if source == "auto":
            self._error(TranslationError("local_source_required")); return
        self.future = self.executor.submit(remove_local_model, source, target)
        self._poll(lambda _: self.status.config(text=ui("Modelo removido.", "Model removed.")))

    def _image(self, page, rotation=None):
        image = self.reader._loader.get_pil(page).copy()
        rotation = self.reader._rotation if rotation is None else rotation
        if rotation:
            image = image.rotate(-rotation, expand=True)
        return image

    def _load_page_cache(self):
        settings = self._settings()
        rotation = self.reader._rotation
        def read():
            try:
                image = self._image(self.page, rotation)
                glossary = json.loads(settings["translation_glossary"] or "{}")
                arguments = (settings["translation_source"], settings["translation_target"],
                             settings["translation_provider"], settings["translation_model"],
                             settings["translation_endpoint"], glossary,
                             settings["translation_ocr"], self.reader._manga,
                             settings["translation_vision"])
                rows = read_cache(self.reader._content_key, self.page, image, *arguments,
                                  turns=rotation // 90)
                if rows is None and rotation:
                    original = self.reader._loader.get_pil(self.page).copy()
                    rows = read_cache(self.reader._content_key, self.page, original, *arguments)
                    if rows is not None:
                        rows = rotate_regions(rows, rotation // 90)
                return rows
            except (OSError, ValueError):
                return None
        self.future = self.executor.submit(read)
        self._poll(lambda rows: self._show_regions(rows, rotation) if rows is not None else None)

    def _start(self, translate):
        if self.future and not self.future.done():
            return
        settings = self._settings()
        provider = settings["translation_provider"]
        try:
            glossary = json.loads(settings["translation_glossary"] or "{}")
            if not isinstance(glossary, dict):
                raise ValueError()
        except ValueError:
            self._error(TranslationError("invalid_glossary")); return
        if not tesseract_available():
            self._error(TranslationError("ocr_unavailable")); return
        if translate and provider == "local" and not local_translation_available():
            self._error(TranslationError("local_translation_unavailable")); return
        if translate and provider != "local" and not self.consent.get():
            self._error(TranslationError("remote_consent_required")); return
        try:
            key = (self.key.get().strip() or load_key(provider)) if translate and provider != "local" else ""
        except TranslationError as exc:
            self._error(exc); return
        if self.scope.get() == "book" and provider != "local":
            if not messagebox.askyesno(ui("Confirmar custo", "Confirm cost"),
                                       ui("Traduzir a HQ inteira pode gerar cobranças da API. Continuar?",
                                          "Translating the whole comic may incur API charges. Continue?"), parent=self):
                return
        if self.scope.get() == "region" and not self.list.curselection():
            self._error(TranslationError("select_region")); return
        if self.scope.get() == "panel" and not self.reader._guided:
            self._error(TranslationError("guided_required")); return
        self._sync_rotation()
        selected = self.regions[self.list.curselection()[0]].box if self.list.curselection() else None
        scope = self.scope.get()
        panel = self.reader._regions[self.reader._region_index] if scope == "panel" and self.reader._regions else None
        manga = self.reader._manga
        pages = [self.page] if scope != "book" else [self.page] + [p for p in range(self.reader._count) if p != self.page]
        self.cancel.clear()
        self.status.config(text=ui("Processando...", "Processing..."))
        self.future = self.executor.submit(self._work, pages, selected, scope, panel, manga,
                                           self.reader._rotation, translate, settings, glossary, key)
        self._poll(lambda _: self.status.config(text=ui("Concluído.", "Done.")))

    def _export(self):
        if self.future and not self.future.done():
            return
        if not messagebox.askyesno(ui("Exportar cópia", "Export copy"),
                ui("As páginas já traduzidas serão incluídas. Páginas sem resultado permanecem originais. Nenhuma tradução paga será iniciada. Continuar?",
                   "Completed translated pages will be included. Pages without a result stay original. No paid translation starts. Continue?"), parent=self):
            return
        original = Path(self.reader._path)
        destination = filedialog.asksaveasfilename(parent=self, defaultextension=".cbz",
            filetypes=[("Comic Book ZIP", "*.cbz")],
            initialfile=original.stem + "-traduzido.cbz")
        if not destination:
            return
        settings = self._settings()
        try:
            glossary = json.loads(settings["translation_glossary"] or "{}")
            if not isinstance(glossary, dict):
                raise ValueError()
        except ValueError:
            self._error(TranslationError("invalid_glossary")); return
        self.cancel.clear()
        self.status.config(text=ui("Preparando cópia CBZ...", "Preparing CBZ copy..."))
        self.future = self.executor.submit(self._work_export, destination, settings, glossary,
                                           self.reader._rotation)
        self._poll(lambda replaced: self.status.config(
            text=ui(f"Cópia salva: {replaced} páginas traduzidas.",
                    f"Copy saved: {replaced} translated pages.")))

    def _work_export(self, destination, settings, glossary, rotation):
        archive = self.reader._loader.backend
        def render(index, data):
            image = Image.open(BytesIO(data))
            source = image.convert("RGBA")
            args = (self.reader._content_key, index, source,
                    settings["translation_source"], settings["translation_target"],
                    settings["translation_provider"], settings["translation_model"])
            options = (settings["translation_endpoint"], glossary,
                       settings["translation_ocr"], self.reader._manga,
                       settings["translation_vision"])
            regions = read_cache(*args, *options)
            if regions is None and rotation:
                turned = source.rotate(-rotation, expand=True)
                regions = read_cache(self.reader._content_key, index, turned, *args[3:],
                                     *options, turns=rotation // 90)
                if regions is not None:
                    regions = rotate_regions(regions, -rotation // 90)
            if not regions or not any(row.translated for row in regions):
                return None
            result = draw_translation_overlay(source, regions, (0, 0, source.width, source.height))
            output = BytesIO()
            format_name = image.format or "PNG"
            if format_name == "JPEG":
                result.save(output, format="JPEG", quality=95, subsampling=0)
            else:
                result.save(output, format=format_name)
            return output.getvalue()
        return export_cbz_copy(archive, destination, render, self.cancel,
                               lambda done, total, replaced: self.export_progress.put((done, total, replaced)))

    def _work(self, pages, selected, scope, panel, manga, rotation, translate, settings, glossary, key):
        prepared_pairs = set()
        for number, page in enumerate(pages, 1):
            if self.cancel.is_set():
                raise CancelledError()
            image = self._image(page, rotation)
            args = (self.reader._content_key, page, image, settings["translation_source"],
                    settings["translation_target"], settings["translation_provider"],
                    settings["translation_model"])
            regions = read_cache(*args, settings["translation_endpoint"], glossary,
                                 settings["translation_ocr"], manga, settings["translation_vision"],
                                 turns=rotation // 90)
            if regions is None and rotation:
                original = self.reader._loader.get_pil(page).copy()
                base_args = (self.reader._content_key, page, original,
                             settings["translation_source"], settings["translation_target"],
                             settings["translation_provider"], settings["translation_model"])
                base = read_cache(*base_args, settings["translation_endpoint"], glossary,
                                  settings["translation_ocr"], manga, settings["translation_vision"])
                if base is not None:
                    regions = rotate_regions(base, rotation // 90)
            if regions is None:
                regions = read_ocr_cache(self.reader._content_key, page, image,
                                         settings["translation_ocr"], manga)
                if regions is None:
                    regions = recognize(image, settings["translation_ocr"], manga, self.cancel)
                    write_ocr_cache(self.reader._content_key, page, image,
                                    settings["translation_ocr"], manga, regions)
            apply_corrections(self.reader._content_key, page, regions, rotation // 90)
            chosen = regions
            if page == self.page and scope == "region" and selected is not None:
                from komicove_app.comic_translation import _overlap
                chosen = [max(regions, key=lambda region: _overlap(region.box, selected))] if regions else []
                if chosen and _overlap(chosen[0].box, selected) < .2:
                    chosen = []
            elif page == self.page and scope == "panel" and panel is not None:
                from komicove_app.comic_translation import _overlap
                chosen = [region for region in regions if _overlap(region.box, panel) > 0]
            if translate and chosen:
                pending = [region for region in chosen if auto_translation_candidate(region)
                           and not region.manual_translation
                           and not region.translated and not region.translation_attempted]
                if pending:
                    if settings["translation_provider"] == "local":
                        for region in pending:
                            exact = glossary_exact_match(region.original, glossary)
                            if exact is not None:
                                region.translated = exact
                                region.translation_attempted = True
                        pending = [region for region in pending if not region.translation_attempted]
                        if not pending:
                            write_cache(*args, regions, settings["translation_endpoint"], glossary,
                                        settings["translation_ocr"], manga, settings["translation_vision"])
                            self.updates.put((page, regions, number, len(pages), rotation))
                            continue
                        source = settings["translation_source"]
                        if source == "auto":
                            source = detect_source(" ".join(r.original for r in regions
                                                      if auto_translation_candidate(r)))
                        pair = (source, settings["translation_target"])
                        if source != pair[1] and pair not in prepared_pairs:
                            offer = local_model_offer(*pair)
                            if any(offer):
                                size = local_model_download_size(offer)
                                ready = Event()
                                decision = []
                                self.model_offers.put((pair, offer, size, ready, decision))
                                while not ready.wait(.1):
                                    if self.cancel.is_set():
                                        raise CancelledError()
                                if not decision or not decision[0]:
                                    raise CancelledError()
                                install_local_offer(offer, self.cancel,
                                    lambda step, count, received, length: self.model_progress.put(
                                        (step, count, received, length)))
                            prepared_pairs.add(pair)
                        for region in pending:
                            if self.cancel.is_set():
                                raise CancelledError()
                            # Argos cannot guarantee line boundaries after translation.
                            # Each result belongs to exactly one OCR region.
                            value = (region.original if source == pair[1] else
                                     local_translate(region.original, source, pair[1]))
                            region.translated = value.strip()
                            region.translation_attempted = True
                    else:
                        for start in range(0, len(pending), 12):
                            if self.cancel.is_set():
                                raise CancelledError()
                            batch = pending[start:start+12]
                            first, last = regions.index(batch[0]), regions.index(batch[-1])
                            nearby = previous_page_context(self.reader._content_key, page)
                            nearby += [row.original for row in regions[max(0, first-4):min(len(regions), last+5)]
                                       if row not in batch and auto_translation_candidate(row)]
                            nearby = nearby[-8:]
                            translate_remote(batch, settings["translation_source"],
                                             settings["translation_target"],
                                             provider=settings["translation_provider"], model=settings["translation_model"],
                                             key=key, custom=settings["translation_endpoint"], glossary=glossary,
                                             context=nearby,
                                             image=image if settings["translation_vision"] else None)
                            write_cache(*args, regions, settings["translation_endpoint"], glossary,
                                        settings["translation_ocr"], manga, settings["translation_vision"])
            write_cache(*args, regions, settings["translation_endpoint"], glossary,
                        settings["translation_ocr"], manga, settings["translation_vision"])
            self.updates.put((page, regions, number, len(pages), rotation))

    def _poll(self, done):
        if not self.winfo_exists():
            return
        while True:
            try:
                pair, offer, size, ready, decision = self.model_offers.get_nowait()
            except Empty:
                break
            amount = f"{size / 1048576:.1f} MB" if size else ui("tamanho não informado", "size not provided")
            decision.append(messagebox.askyesno(ui("Baixar idioma", "Download language"),
                ui(f"Para traduzir {pair[0]} para {pair[1]} sem API, baixe os componentes locais ({amount}). Continuar?",
                   f"To translate {pair[0]} to {pair[1]} without an API, download local components ({amount}). Continue?"), parent=self))
            ready.set()
        while True:
            try:
                step, count, received, length = self.model_progress.get_nowait()
            except Empty:
                break
            progress = f"{received * 100 // length}%" if length else f"{received // 1048576} MB"
            self.status.config(text=ui(f"Baixando componente {step}/{count}: {progress}",
                                       f"Downloading component {step}/{count}: {progress}"))
        while True:
            try:
                done_count, total_count, replaced = self.export_progress.get_nowait()
            except Empty:
                break
            self.status.config(text=ui(f"Exportando {done_count}/{total_count}, {replaced} traduzidas",
                                       f"Exporting {done_count}/{total_count}, {replaced} translated"))
        while True:
            try:
                page, rows, number, total, rotation = self.updates.get_nowait()
            except Empty:
                break
            self._publish_page(page, rows, rotation)
            self.status.config(text=f"{number} / {total}")
        if self.future and not self.future.done():
            self.after(100, lambda: self._poll(done)); return
        try:
            value = self.future.result()
            done(value)
        except CancelledError:
            self.status.config(text=ui("Cancelado. Páginas concluídas preservadas.",
                                       "Cancelled. Completed pages kept."))
        except TranslationError as exc:
            self._error(exc)
        except Exception:
            self._error(TranslationError("processing_failed"))

    def _sync_rotation(self):
        turns = (self.reader._rotation - self.regions_rotation) % 360 // 90
        if turns and self.regions:
            self.regions = rotate_regions(self.regions, turns)
        self.regions_rotation = self.reader._rotation

    def _show_regions(self, rows, rotation=None):
        self.regions = rows
        self.regions_rotation = self.reader._rotation if rotation is None else rotation
        self._sync_rotation()
        self.list.delete(0, tk.END)
        for region in self.regions:
            marker = "? " if region.uncertain else ""
            self.list.insert(tk.END, marker + region.original[:90])
        if self.regions:
            self.list.selection_set(0)
            self._select()
        self.reader._translation_regions = self.regions
        self.reader._translation_page = self.page
        self.reader._translation_view = self.view.get()
        self.reader._show(reset=False)
        self._update_preview_caption()
        self._queue_preview()

    def _publish_page(self, page, rows, rotation):
        if page == self.page and self.winfo_exists():
            self._show_regions(rows, rotation)
        elif page == self.reader._idx:
            if self.reader._rotation != rotation:
                rows = rotate_regions(rows, (self.reader._rotation - rotation) % 360 // 90)
            self.reader._apply_translation_rows(page, rows)

    def _select(self, _event=None):
        if not self.list.curselection():
            return
        region = self.regions[self.list.curselection()[0]]
        self.original.delete("1.0", tk.END); self.original.insert("1.0", region.original)
        self.translated.delete("1.0", tk.END); self.translated.insert("1.0", region.translated)
        self._update_preview_caption()
        self._queue_preview()

    def _save_correction(self):
        if not self.list.curselection():
            return
        self._sync_rotation()
        index = self.list.curselection()[0]
        region = self.regions[index]
        original, translated = self.original.get("1.0", "end-1c"), self.translated.get("1.0", "end-1c")
        old_translation = region.translated
        if original != region.original:
            region.original = original; region.manual_original = True
            if not region.manual_translation:
                region.translated = ""
                region.translation_attempted = False
        if translated != old_translation:
            region.translated = translated; region.manual_translation = True
            region.translation_attempted = True
        save_correction(self.reader._content_key, self.page, region,
                        self.regions_rotation // 90)
        self._show_regions(self.regions)
        self.list.selection_set(index)
        self._select()
        self.status.config(text=ui("Correção salva.", "Correction saved."))

    def _error(self, exc):
        labels = {
            "ocr_unavailable": ("Instale Tesseract OCR para usar OCR local.", "Install Tesseract OCR for local OCR."),
            "ocr_language_or_model_unavailable": ("Pacote OCR indisponível.", "OCR language pack unavailable."),
            "ocr_timeout": ("O reconhecimento demorou demais nesta página. Tente selecionar uma região menor.", "Text recognition took too long on this page. Try selecting a smaller region."),
            "local_translation_unavailable": ("Instale Argos Translate para tradução offline.", "Install Argos Translate for offline translation."),
            "local_model_unavailable": ("Modelo local para este par não está instalado.", "Local model for this pair is not installed."),
            "local_model_invalid": ("Arquivo de modelo local inválido.", "Invalid local model file."),
            "local_source_required": ("Escolha a origem para tradução local.", "Choose the source for local translation."),
            "remote_consent_required": ("Autorize o envio antes de traduzir remotamente.", "Allow data transfer before remote translation."),
            "select_region": ("Selecione uma região na lista.", "Select a region in the list."),
            "guided_required": ("Ative a leitura guiada para traduzir o quadro.", "Enable guided reading to translate a panel."),
            "invalid_glossary": ("Glossário JSON inválido.", "Invalid JSON glossary."),
            "authentication": ("Autenticação recusada. Verifique a chave API.", "Authentication failed. Check the API key."),
            "quota_or_rate_limit": ("Quota ou limite de chamadas atingido.", "Quota or rate limit reached."),
            "timeout": ("Tempo de resposta esgotado.", "Request timed out."),
            "model_or_request_incompatible": ("Modelo ou solicitação incompatível.", "Incompatible model or request."),
            "key_or_model_missing": ("Informe chave API e modelo.", "Enter an API key and model."),
            "invalid_endpoint": ("Endpoint HTTPS inválido.", "Invalid HTTPS endpoint."),
            "network": ("Falha de rede. Verifique a conexão.", "Network failure. Check the connection."),
            "provider_unavailable": ("Provedor indisponível.", "Provider unavailable."),
            "invalid_provider_response": ("Resposta inválida do provedor.", "Invalid provider response."),
            "secure_storage_unavailable": ("Armazenamento seguro indisponível neste sistema.", "Secure storage is unavailable on this system."),
            "invalid_export_path": ("Escolha um novo arquivo CBZ, separado da HQ original.", "Choose a new CBZ file, separate from the original comic."),
        }
        pt, en = labels.get(exc.code, ("Não foi possível processar.", "Could not process."))
        self.status.config(text=ui(pt, en))

    def close(self):
        self.cancel.set()
        if self.preview_after is not None:
            self.after_cancel(self.preview_after)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.preview_executor.shutdown(wait=True, cancel_futures=True)
        self.destroy()


def _source_font_size(image, box, translated, angle=0, scales=()):
    """Estimate lettering height from ink components inside the OCR line."""
    crop = image.crop(tuple(box)).convert("L")
    if abs(angle) > 60:
        crop = crop.rotate(-90 if angle > 0 else 90, expand=True)
    scale = min(1.0, 550 / max(crop.size))
    if scale < 1:
        crop.thumbnail((550, 550))
    width, height = crop.size
    if width < 3 or height < 3:
        return max(8, min(90, height))
    values = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())
    background = median(values[::max(1, len(values) // 2000)])
    dark = background >= 128
    ink = bytearray((value < background - 42 if dark else value > background + 42)
                    for value in values)
    seen = bytearray(len(ink))
    heights = []
    for start in range(len(ink)):
        if not ink[start] or seen[start]:
            continue
        seen[start] = 1
        queue = deque([start])
        left = right = start % width
        top = bottom = start // width
        area = 0
        while queue:
            index = queue.popleft()
            x, y = index % width, index // width
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
            area += 1
            for next_index in (index-1 if x else -1, index+1 if x+1 < width else -1,
                               index-width if y else -1, index+width if y+1 < height else -1):
                if next_index >= 0 and ink[next_index] and not seen[next_index]:
                    seen[next_index] = 1
                    queue.append(next_index)
        component_height = bottom-top+1
        if 3 <= component_height <= height*.9 and right-left+1 <= width*.42 and area >= 4:
            heights.append(component_height)
    ink_height = max(heights) / scale if heights else max(6, box[3]-box[1])*.75
    words = translated.split() or ["Aa"]
    peak = max(scales, default=1.0)
    reference_height = 1
    for index, word in enumerate(words):
        source = min(len(scales)-1, max(0, round((index+.5)*len(scales)/len(words)-.5))) if scales else 0
        ratio = scales[source] / peak if scales else 1.0
        bounds = _comic_font(word, max(8, round(40*ratio))).getbbox(word)
        reference_height = max(reference_height, bounds[3]-bounds[1])
    return max(8, min(150, round(40 * ink_height * (1.15 if ink_height < 30 else 1) / reference_height)))


def _styled_layout(draw, value, base_size, scales, width, height):
    words = value.split()
    if not words:
        return None
    scale_peak = max(scales, default=1.0)
    for size in range(base_size, 9, -1):
        for spacing in (1.0, .85, .7):
            lines = []
            current = []
            current_width = 0.0
            for index, word in enumerate(words):
                source_index = min(len(scales)-1, max(0, round((index+.5)*len(scales)/len(words)-.5))) if scales else 0
                ratio = (scales[source_index] / scale_peak) ** 1.15 if scales else 1.0
                font = _comic_font(word, max(8, round(size*ratio)))
                word_width = draw.textlength(word, font=font)
                gap = draw.textlength(" ", font=font)*spacing if current else 0
                if current and current_width + gap + word_width > width:
                    lines.append((current, current_width))
                    current, current_width, gap = [], 0.0, 0
                current.append((word, font, gap, word_width))
                current_width += gap + word_width
            if current:
                lines.append((current, current_width))
            heights = [max(font.getbbox(word)[3]-font.getbbox(word)[1]
                           for word, font, _, _ in line) + max(2, size//12)
                       for line, _ in lines]
            if all(line_width <= width for _, line_width in lines) and sum(heights) <= height:
                return lines, heights
    return None


def _paint_styled_lines(draw, lines, heights, width, height, ink):
    y = max(0, (height-sum(heights))/2)
    for (line, line_width), line_height in zip(lines, heights):
        x = max(0, (width-line_width)/2)
        for word, font, gap, word_width in line:
            x += gap
            bounds = font.getbbox(word)
            glyph_height = bounds[3]-bounds[1]
            draw.text((x, y+line_height-glyph_height), word, font=font, fill=ink,
                      anchor="lt")
            x += word_width
        y += line_height


def draw_translation_overlay(frame, regions, transform, panel=None):
    """Paint a disposable preview only; the comic image and OCR boxes stay intact."""
    from komicove_app.comic_translation import _overlap
    x0, y0, width, height = transform
    result = frame.convert("RGB")
    draw = ImageDraw.Draw(result)
    for region in regions:
        if not region.translated or panel is not None and _overlap(region.box, panel) <= 0:
            continue
        l, t, r, b = region.box
        box = [max(0, int(x0 + l * width)), max(0, int(y0 + t * height)),
               min(frame.width, int(x0 + r * width)),
               min(frame.height, int(y0 + b * height))]
        if box[2] - box[0] < 24 or box[3] - box[1] < 12:
            continue
        angle = region.angle if abs(region.angle) > 5 else 0
        vertical = abs(angle) % 180 == 90
        natural_width = box[3]-box[1] if vertical else box[2]-box[0]
        axis_start, axis_end = (box[1], box[3]) if vertical else (box[0], box[2])
        cross_start, cross_end = (box[0], box[2]) if vertical else (box[1], box[3])
        page_extent = frame.height if vertical else frame.width
        axis_center = (axis_start+axis_end)/2
        width_room = min(natural_width*1.65, 2*min(axis_center, page_extent-axis_center))
        for neighbor in regions:
            if neighbor is region:
                continue
            nl, nt, nr, nb = neighbor.box
            other = (y0+nt*height, y0+nb*height) if vertical else (x0+nl*width, x0+nr*width)
            other_cross = (x0+nl*width, x0+nr*width) if vertical else (y0+nt*height, y0+nb*height)
            if other_cross[1] <= cross_start or other_cross[0] >= cross_end:
                continue
            if other[1] <= axis_start:
                width_room = min(width_room, natural_width+2*(axis_start-other[1]))
            elif other[0] >= axis_end:
                width_room = min(width_room, natural_width+2*(other[0]-axis_end))
        if width_room > natural_width + 4:
            samples = []
            extra = (width_room-natural_width)/2
            for across in range(max(0, int(cross_start)), min(frame.width if vertical else frame.height,
                                                           int(cross_end)), 4):
                for along in range(max(0, int(axis_start-extra)),
                                   min(page_extent, int(axis_end+extra)), 4):
                    if axis_start <= along < axis_end:
                        continue
                    x, y = (across, along) if vertical else (along, across)
                    samples.append(sum(result.getpixel((x, y)))/3)
            if samples:
                middle = median(samples)
                if sum(abs(value-middle)>28 for value in samples) > len(samples)*.04:
                    width_room = natural_width
        layout_width = max(natural_width, round(width_room))
        line_height = box[2]-box[0] if vertical else box[3]-box[1]
        layout_height = max(12, round(line_height))
        original_size = _source_font_size(frame, box, region.original, angle,
                                          region.word_scales)
        target_size = _source_font_size(frame, box, region.translated, angle,
                                        region.word_scales)
        source_size = round((original_size + target_size) / 2)
        layout = _styled_layout(draw, region.translated, source_size,
                                region.word_scales, layout_width-2, layout_height)
        if layout is None:
            _draw_translation_label(draw, result, box, region.translated, region.angle)
            continue
        light_background = _clean_text_pixels(result, box)
        if light_background is None:
            _draw_translation_label(draw, result, box, region.translated, region.angle)
            continue
        lines, heights = layout
        ink = (20, 17, 22) if light_background else (250, 248, 243)
        if angle:
            tile = Image.new("RGBA", (layout_width, layout_height))
            tile_draw = ImageDraw.Draw(tile)
            _paint_styled_lines(tile_draw, lines, heights, layout_width,
                                layout_height, (*ink, 255))
            turned = tile.rotate(-angle, expand=True)
            result.paste(turned, (int((box[0]+box[2]-turned.width)/2),
                                  int((box[1]+box[3]-turned.height)/2)), turned)
        else:
            mask = Image.new("L", (layout_width, layout_height))
            _paint_styled_lines(ImageDraw.Draw(mask), lines, heights,
                                layout_width, layout_height, 255)
            paint = Image.new("RGB", (layout_width, layout_height), ink)
            result.paste(paint, (round((box[0]+box[2]-layout_width)/2),
                                 round((box[1]+box[3]-layout_height)/2)), mask)
    return result


def _draw_translation_label(draw, image, box, value, angle=0):
    """Keep lettering visible when cleaning its background would damage artwork."""
    canvas_size = image.size
    size = max(14, min(28, int((box[3] - box[1]) / 3), int(min(canvas_size) * .025)))
    font = _comic_font(value, size)
    width = min(max(size * 7, box[2] - box[0]), max(30, canvas_size[0] - 8))
    words = value.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if current and draw.textlength(candidate, font=font) > width - 12:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    line_height = int(size * 1.25)
    if len(lines) > 4 or len(lines) * line_height + 8 > (box[3] - box[1]) * 1.1:
        lines = [ui("Ver tradução completa em Revisar", "Open Review for full translation")]
    height = max(size + 8, len(lines) * line_height + 8)
    left = min(max(4, box[0]), canvas_size[0] - width - 4)
    top = box[3] + 2 if box[3] + height + 2 <= canvas_size[1] else max(4, box[1] - height - 2)
    if abs(angle) < 5:
        for candidate in (box[3] + 8, box[3] + height + 16,
                          box[1] - height - 8):
            if candidate < 4 or candidate + height >= canvas_size[1] - 4:
                continue
            text_width = max(draw.textlength(line, font=font) for line in lines)
            text_left = int(box[0] + (box[2] - box[0] - text_width) / 2)
            text_left = max(4, min(text_left, canvas_size[0] - width - 4))
            samples = []
            for y in range(int(candidate), int(candidate + height), 4):
                for x in range(text_left, min(canvas_size[0], int(text_left + text_width + 8)), 4):
                    samples.append(image.getpixel((x, y)))
            if samples and median(sum(pixel)/3 for pixel in samples) > 205 and \
                    sum(1 for pixel in samples if min(pixel) < 100) / len(samples) < .015:
                for index, line in enumerate(lines):
                    draw.text((text_left, candidate + index * line_height), line,
                              font=font, fill=(119, 31, 47))
                return
    draw.rounded_rectangle((left, top, left + width, top + height), radius=5, fill=(26, 22, 28))
    for index, line in enumerate(lines):
        draw.text((left + 6, top + 3 + index * line_height), line, font=font, fill=(255, 251, 247))


def _clean_text_pixels(image, box):
    """Rebuild lettering pixels only when the surrounding color is stable."""
    l, t, r, b = box
    margin = max(10, min(22, round((b-t)*.35)))
    outer = (max(0, l-margin-8), max(0, t-margin-8),
             min(image.width, r+margin+8), min(image.height, b+margin+8))
    crop = image.crop(outer)
    ox, oy = l-outer[0], t-outer[1]
    inner = (max(0, ox-margin), max(0, oy-margin),
             min(crop.width, ox+r-l+margin), min(crop.height, oy+b-t+margin))
    ring = []
    ring_colors = []
    pixels = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            if inner[0] <= x < inner[2] and inner[1] <= y < inner[3]:
                continue
            if x % 2 == 0 and y % 2 == 0:
                ring.append(sum(pixels[x, y]) / 3)
                ring_colors.append(pixels[x, y])
    if len(ring) < 8:
        return None
    background = median(ring)
    core_colors = [pixels[x, y] for y in range(max(0, oy), min(crop.height, oy+b-t), 2)
                   for x in range(max(0, ox), min(crop.width, ox+r-l), 2)]
    core = [sum(pixel) / 3 for pixel in core_colors]
    core_background = median(core) if core else 0
    uniform_light_core = (core_background > 220 and
                          median(abs(value-core_background) for value in core) < 18 and
                          sum(value > 180 for value in core) >= len(core) * .68)
    if median(abs(value-background) for value in ring) > 22:
        if not uniform_light_core:
            return None
        background = core_background
        ring_colors = core_colors
    background_color = tuple(int(median(sample[channel] for sample in ring_colors))
                             for channel in range(3))
    if any(median(abs(sample[channel] - background_color[channel])
                  for sample in ring_colors) > 22 for channel in range(3)):
        return None
    polarity = -1 if background >= 120 else 1
    interior = [pixels[x, y] for y in range(oy, min(crop.height, oy+b-t), 2)
                for x in range(ox, min(crop.width, ox+r-l), 2)
                if abs(sum(pixels[x, y])/3-background) < 28]
    if len(interior) >= 12:
        background_color = tuple(int(median(sample[channel] for sample in interior))
                                 for channel in range(3))
    mask = Image.new("L", crop.size)
    mask_pixels = mask.load()
    count = 0
    threshold = 12 if median(abs(value-background) for value in ring) < 8 else 26
    candidates = bytearray(crop.width * crop.height)
    for y in range(inner[1], inner[3]):
        for x in range(inner[0], inner[2]):
            delta = sum(pixels[x, y]) / 3 - background
            if polarity * delta > threshold:
                candidates[y * crop.width + x] = 1
    seen = bytearray(len(candidates))
    for y in range(inner[1], inner[3]):
        for x in range(inner[0], inner[2]):
            start = y * crop.width + x
            if not candidates[start] or seen[start]:
                continue
            seen[start] = 1
            queue = deque([start])
            component = []
            left = right = x
            top = bottom = y
            touches_edge = False
            while queue:
                pixel = queue.popleft()
                px, py = pixel % crop.width, pixel // crop.width
                component.append(pixel)
                left, right = min(left, px), max(right, px)
                top, bottom = min(top, py), max(bottom, py)
                touches_edge |= (px in (inner[0], inner[2]-1) or
                                 py in (inner[1], inner[3]-1))
                for neighbor in (pixel-1 if px > inner[0] else -1,
                                 pixel+1 if px+1 < inner[2] else -1,
                                 pixel-crop.width if py > inner[1] else -1,
                                 pixel+crop.width if py+1 < inner[3] else -1):
                    if neighbor >= 0 and candidates[neighbor] and not seen[neighbor]:
                        seen[neighbor] = 1
                        queue.append(neighbor)
            if touches_edge or right-left+1 > (r-l)*.6 or bottom-top+1 > (b-t)*1.5:
                continue
            for pixel in component:
                mask_pixels[pixel % crop.width, pixel // crop.width] = 255
            count += len(component)
    if count < 2 or count > (r-l)*(b-t)*.45:
        return None
    mask = mask.filter(ImageFilter.MaxFilter(9))
    replacement = Image.new("RGB", crop.size, background_color)
    crop.paste(replacement, (0, 0), mask)
    image.paste(crop, outer[:2])
    return background >= 120


def _comic_font(value, size):
    if any(ord(char) > 0x2e80 for char in value):
        candidates = ("C:/Windows/Fonts/msgothic.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                      "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")
    elif any(ord(char) > 0x024f for char in value):
        candidates = ("DejaVuSans.ttf",)
    else:
        candidates = (resource_path("assets_redesign/fonts/ComicNeue-Regular.ttf"), "DejaVuSans.ttf")
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()
