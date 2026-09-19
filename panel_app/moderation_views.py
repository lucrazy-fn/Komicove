from panel_app.runtime import *
from panel_app.reader_views import ReaderWindow

class ModerationWindow(tk.Toplevel):
    pass

    def __init__(self, master, user):
        super().__init__(master)
        self._user = user
        self._items = []
        self.title("PANEL — Moderação")
        self.geometry("900x560")
        self.minsize(720, 460)
        self.configure(bg=THEME["bg"])
        try: self.iconbitmap(resource_path("panel.ico"))
        except Exception as _e: log.debug("silenced: %s", _e)

        header = tk.Frame(self, bg=THEME["bg"])
        header.pack(fill="x", padx=20, pady=(18, 10))
        tk.Label(header, text="Pedidos de publicação", font=FTITLE,
                 bg=THEME["bg"], fg=THEME["text"]).pack(side="left")
        make_pill(header, "Atualizar", self._refresh, variant="ghost",
                  font=FBTN, pad_x=14, pad_y=7).pack(side="right")

        body = tk.Frame(self, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=20)
        self._list = tk.Listbox(
            body, width=38, bg=THEME["surface"], fg=THEME["text"],
            selectbackground=THEME["accent"], selectforeground="#ffffff",
            bd=0, highlightthickness=1, highlightbackground=THEME["border"],
            font=FSMALL,
        )
        self._list.pack(side="left", fill="both", expand=False)
        self._list.bind("<<ListboxSelect>>", self._show_selected)

        right = tk.Frame(body, bg=THEME["surface"])
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._detail = tk.Text(
            right, bg=THEME["surface"], fg=THEME["text"], font=FSMALL,
            wrap="word", bd=0, padx=16, pady=14, state="disabled",
        )
        self._detail.pack(fill="both", expand=True)

        actions = tk.Frame(self, bg=THEME["bg"])
        actions.pack(fill="x", padx=20, pady=14)
        self._status = tk.Label(actions, text="", font=FTINY,
                                bg=THEME["bg"], fg=THEME["text_dim"])
        self._status.pack(side="left")
        make_pill(actions, "Rejeitar", lambda: self._decide("rejected"),
                  variant="ghost", font=FBTN, pad_x=16, pad_y=8).pack(side="right")
        make_pill(actions, "Aprovar", lambda: self._decide("approved"),
                  variant="accent", font=FBTN, pad_x=16, pad_y=8).pack(side="right", padx=8)
        self._refresh()

    def _run(self, operation, callback):
        self._status.config(text="Carregando…", fg=THEME["text_dim"])

        def worker():
            try:
                outcome = (operation(), None)
            except (api_client.ApiAuthError, api_client.ApiServerError) as exc:
                outcome = (None, str(exc))
            except api_client.ApiUnavailableError:
                outcome = (None, "Servidor indisponível.")
            except Exception:
                log.exception("Falha na tela de moderação")
                outcome = (None, "Não foi possível concluir a operação.")
            try: self.after(0, lambda: callback(*outcome))
            except tk.TclError: pass

        threading.Thread(target=worker, daemon=True).start()

    def _refresh(self):
        self._run(lambda: api_client.moderation_queue(self._user.token), self._loaded)

    def _loaded(self, items, error):
        if error:
            self._status.config(text=error, fg=THEME["accent2"])
            return
        self._items = items
        self._list.delete(0, "end")
        for item in items:
            self._list.insert("end", f"{item['title']} — @{item['uploader_username']}")
        self._status.config(text=f"{len(items)} pedido(s) pendente(s)", fg=THEME["text_dim"])
        if items:
            self._list.selection_set(0)
            self._show_selected()
        else:
            self._set_detail("Nenhum pedido aguardando revisão.")

    def _selected(self):
        selection = self._list.curselection()
        return self._items[selection[0]] if selection else None

    def _show_selected(self, _event=None):
        item = self._selected()
        if not item:
            return
        self._set_detail(
            f"Título: {item['title']}\n"
            f"Autor: {item['author']}\n"
            f"Enviado por: @{item['uploader_username']}\n"
            f"Risco: {item['risk_level']}\n"
            f"Confiança automática: {item['confidence']:.0%}\n\n"
            f"Análise interna:\n{item['justification']}"
        )

    def _set_detail(self, text):
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")

    def _decide(self, decision):
        item = self._selected()
        if not item:
            messagebox.showinfo("Moderação", "Selecione um pedido primeiro.", parent=self)
            return
        verb = "aprovar" if decision == "approved" else "rejeitar"
        reason = simpledialog.askstring(
            "Motivo da decisão", f"Explique por que deseja {verb} esta publicação:",
            parent=self,
        )
        if not reason or len(reason.strip()) < 3:
            return
        self._run(
            lambda: api_client.moderate(
                self._user.token, item["record_id"], decision, reason.strip()
            ),
            lambda _result, error: self._decision_finished(error),
        )

    def _decision_finished(self, error):
        if error:
            self._status.config(text=error, fg=THEME["accent2"])
            return
        self._refresh()




