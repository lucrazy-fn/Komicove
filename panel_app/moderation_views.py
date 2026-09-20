from panel_app.runtime import *
from panel_app.reader_views import ReaderWindow

class ModerationWindow(tk.Toplevel):
    pass

    def __init__(self, master, user):
        super().__init__(master)
        self._user = user
        self._items = []
        self.title(ui("PANEL — Moderação", "PANEL — Moderation"))
        self.geometry("900x560")
        self.minsize(720, 460)
        self.configure(bg=THEME["bg"])
        try: self.iconbitmap(resource_path("panel.ico"))
        except Exception as _e: log.debug("silenced: %s", _e)

        header = tk.Frame(self, bg=THEME["bg"])
        header.pack(fill="x", padx=20, pady=(18, 10))
        tk.Label(header, text=ui('Pedidos de publicação', 'Publication requests'), font=FTITLE,
                 bg=THEME["bg"], fg=THEME["text"]).pack(side="left")
        make_pill(header, ui('Atualizar', 'Refresh'), self._refresh, variant="ghost",
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
        make_pill(actions, ui('Rejeitar', 'Reject'), lambda: self._decide("rejected"),
                  variant="ghost", font=FBTN, pad_x=16, pad_y=8).pack(side="right")
        make_pill(actions, ui('Aprovar', 'Approve'), lambda: self._decide("approved"),
                  variant="accent", font=FBTN, pad_x=16, pad_y=8).pack(side="right", padx=8)
        self._refresh()

    def _run(self, operation, callback):
        self._status.config(text=ui('Carregando…', 'Loading…'), fg=THEME["text_dim"])

        def worker():
            try:
                outcome = (operation(), None)
            except (api_client.ApiAuthError, api_client.ApiServerError) as exc:
                outcome = (None, str(exc))
            except api_client.ApiUnavailableError:
                outcome = (None, ui('Servidor indisponível.', 'Server unavailable.'))
            except Exception:
                log.exception(ui('Falha na tela de moderação', 'Moderation screen error'))
                outcome = (None, ui('Não foi possível concluir a operação.', 'Could not complete the operation.'))
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
        self._status.config(text=ui(f"{len(items)} pedido(s) pendente(s)", f"{len(items)} pending request(s)"), fg=THEME["text_dim"])
        if items:
            self._list.selection_set(0)
            self._show_selected()
        else:
            self._set_detail(ui('Nenhum pedido aguardando revisão.', 'No requests awaiting review.'))

    def _selected(self):
        selection = self._list.curselection()
        return self._items[selection[0]] if selection else None

    def _show_selected(self, _event=None):
        item = self._selected()
        if not item:
            return
        self._set_detail(ui(
            f"Título: {item['title']}\nAutor: {item['author']}\nEnviado por: @{item['uploader_username']}\nRisco: {item['risk_level']}\nConfiança automática: {item['confidence']:.0%}\n\nAnálise interna:\n{item['justification']}",
            f"Title: {item['title']}\nAuthor: {item['author']}\nSubmitted by: @{item['uploader_username']}\nRisk: {item['risk_level']}\nAutomatic confidence: {item['confidence']:.0%}\n\nInternal analysis:\n{item['justification']}",
        ))

    def _set_detail(self, text):
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")

    def _decide(self, decision):
        item = self._selected()
        if not item:
            messagebox.showinfo(ui('Moderação', 'Moderation'), ui('Selecione um pedido primeiro.', 'Select a request first.'), parent=self)
            return
        verb = ui("aprovar", "approve") if decision == "approved" else ui("rejeitar", "reject")
        reason = simpledialog.askstring(
            ui('Motivo da decisão', 'Decision reason'),
            ui(f"Explique por que deseja {verb} esta publicação:", f"Explain why you want to {verb} this submission:"),
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


