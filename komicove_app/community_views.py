from komicove_app.runtime import *
from komicove_app.reader_views import ReaderWindow

class CommunityWindow(tk.Toplevel):
    pass

    STATUS_LABELS = {
        "approved": ("Aprovada", "Approved"),
        "pending_review": ("Em análise", "Under review"),
        "rejected": ("Rejeitada", "Rejected"),
    }

    @classmethod
    def status_label(cls, status):
        labels = cls.STATUS_LABELS.get(status)
        return ui(*labels) if labels else status

    def __init__(self, master, user=None, mine=False):
        super().__init__(master)
        self._user = user
        self._mine = mine
        self._items = []
        self._cover_tk = None
        title = ui('Meus envios', 'My submissions') if mine else ui('Descobrir', 'Discover')
        self.title(f"Komicove: {title}")
        self.geometry("860x540")
        self.minsize(700, 440)
        self.configure(bg=THEME["bg"])
        set_app_icon(self)

        header = tk.Frame(self, bg=THEME["bg"])
        header.pack(fill="x", padx=20, pady=(18, 10))
        tk.Label(header, text=title, font=FTITLE, bg=THEME["bg"],
                 fg=THEME["text"]).pack(side="left")
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
        self._list.pack(side="left", fill="both")
        self._list.bind("<<ListboxSelect>>", self._show_selected)
        right = tk.Frame(body, bg=THEME["surface"])
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._cover = tk.Label(
            right, text=ui('Selecione uma obra', 'Select a work'), bg=THEME["surface_alt"],
            fg=THEME["text_dim"], font=FTINY, width=22, height=12,
        )
        self._cover.pack(side="left", padx=14, pady=14)
        detail_side = tk.Frame(right, bg=THEME["surface"])
        detail_side.pack(side="left", fill="both", expand=True)
        self._detail = tk.Text(
            detail_side, bg=THEME["surface"], fg=THEME["text"], font=FSMALL,
            wrap="word", bd=0, padx=18, pady=15, state="disabled",
        )
        self._detail.pack(fill="both", expand=True)
        actions = tk.Frame(detail_side, bg=THEME["surface"])
        actions.pack(fill="x", padx=12, pady=12)
        make_pill(actions, ui('Baixar', 'Download'), self._download_selected, variant="ghost",
                  font=FBTN, pad_x=16, pad_y=8).pack(side="left", padx=8)
        if self._user is not None and not self._mine:
            make_pill(actions, ui('Denunciar', 'Report'), self._report_selected, variant="ghost",
                      font=FBTN, pad_x=16, pad_y=8).pack(side="left")
        self._status = tk.Label(self, text="", font=FTINY, bg=THEME["bg"],
                                fg=THEME["text_dim"])
        self._status.pack(fill="x", padx=20, pady=14)
        self._refresh()

    def _refresh(self):
        self._status.config(text=ui('Carregando…', 'Loading…'), fg=THEME["text_dim"])

        def worker():
            try:
                items = (api_client.my_publications(self._user.token)
                         if self._mine else api_client.discovery())
                outcome = (items, None)
            except (api_client.ApiAuthError, api_client.ApiServerError) as exc:
                outcome = (None, str(exc))
            except api_client.ApiUnavailableError:
                cached, saved_at = load_catalog()
                outcome = (cached, None) if cached and not self._mine else (None, ui('Servidor indisponível.', 'Server unavailable.'))
            except Exception:
                log.exception(ui('Falha ao carregar comunidade', 'Could not load community'))
                outcome = (None, ui('Não foi possível carregar os dados.', 'Could not load the data.'))
            try: self.after(0, lambda: self._loaded(*outcome))
            except tk.TclError: pass

        threading.Thread(target=worker, daemon=True).start()

    def _loaded(self, items, error):
        if error:
            self._status.config(text=error, fg=THEME["accent2"])
            return
        self._items = items
        if not self._mine:
            save_catalog(items)
        self._list.delete(0, "end")
        for item in items:
            suffix = (f": {self.status_label(item['status'])}"
                      if self._mine else f": {item['author']}")
            self._list.insert("end", item["title"] + suffix)
        noun = ui("envio(s)", "submission(s)") if self._mine else ui('obra(s)', 'work(s)')
        self._status.config(text=f"{len(items)} {noun}", fg=THEME["text_dim"])
        if items:
            self._list.selection_set(0)
            self._show_selected()
        else:
            self._set_detail(ui('Nenhum item encontrado.', 'No items found.'))

    def _show_selected(self, _event=None):
        selected = self._list.curselection()
        if not selected:
            return
        item = self._items[selected[0]]
        lines = [
            ui(f"Título: {item['title']}", f"Title: {item['title']}"),
            ui(f"Autor: {item['author']}", f"Author: {item['author']}"),
            ui(f"Tags: {', '.join(item.get('tags', [])) or 'Nenhuma'}", f"Tags: {', '.join(item.get('tags', [])) or 'None'}"),
        ]
        if item.get("series_title"):
            lines.insert(1, ui(f"Série: {item['series_title']} · Capítulo {item.get('chapter_number') or '?'}",
                               f"Series: {item['series_title']} · Chapter {item.get('chapter_number') or '?'}"))
        if self._mine:
            lines.extend([
                f"Status: {self.status_label(item['status'])}",
                ui(f"Risco da triagem: {item['risk_level']}", f"Screening risk: {item['risk_level']}"),
            ])
            if item.get("decision_reason"):
                lines.append(ui(f"Motivo da decisão: {item['decision_reason']}", f"Decision reason: {item['decision_reason']}"))
        lines.extend(["", item.get("description") or ui('Sem descrição.', 'No description.')])
        if not item.get("has_file"):
            lines.extend(["", ui('O arquivo desta publicação ainda não foi enviado.', 'The file for this submission has not been uploaded yet.')])
        self._set_detail("\n".join(lines))
        self._load_cover(item)

    def _selected_item(self):
        selected = self._list.curselection()
        return self._items[selected[0]] if selected else None

    def _token(self):
        return self._user.token if self._user else None

    def _report_selected(self):
        item=self._selected_item()
        if not item:return
        reason=simpledialog.askstring(ui('Denunciar obra', 'Report comic'),ui('Motivo (copyright, illegal, harassment, spam ou other):', 'Reason (copyright, illegal, harassment, spam, or other):'),parent=self)
        if not reason:return
        reason=reason.strip().lower()
        if reason not in {"copyright","illegal","harassment","spam","other"}:
            messagebox.showerror(ui('Denúncia', 'Report'),ui('Motivo inválido.', 'Invalid reason.'),parent=self);return
        description=simpledialog.askstring(ui('Denunciar obra', 'Report comic'),ui('Descreva o problema:', 'Describe the problem:'),parent=self) or ""
        def worker():
            try: api_client.create_report(self._user.token,"publication",item["publication_id"],reason,description); error=None
            except Exception as exc:error=str(exc)
            self.after(0,lambda:messagebox.showerror(ui('Denúncia', 'Report'),error,parent=self) if error else messagebox.showinfo(ui('Denúncia', 'Report'),ui('Denúncia enviada para a moderação.', 'Report sent to moderation.'),parent=self))
        threading.Thread(target=worker,daemon=True).start()

    def _load_cover(self, item):
        self._cover.config(image="", text=ui('Carregando capa…', 'Loading cover…'))
        self._cover_tk = None
        if not item.get("has_file"):
            self._cover.config(text=ui('Sem arquivo', 'No file'))
            return
        publication_id = item["publication_id"]
        token = self._token()

        def worker():
            try:
                data = api_client.publication_cover(publication_id, token)
                image = Image.open(io.BytesIO(data)).convert("RGB")
                image.thumbnail((220, 320), Image.LANCZOS)
                outcome = (image, None)
            except Exception as exc:
                outcome = (None, str(exc))
            try: self.after(0, lambda: self._cover_loaded(*outcome))
            except tk.TclError: pass
        threading.Thread(target=worker, daemon=True).start()

    def _cover_loaded(self, image, error):
        if error:
            self._cover.config(text=ui('Capa indisponível', 'Cover unavailable'))
            return
        self._cover_tk = ImageTk.PhotoImage(image)
        self._cover.config(image=self._cover_tk, text="", width=image.width, height=image.height)

    def _read_selected(self):
        item = self._selected_item()
        if not item or not item.get("has_file"):
            messagebox.showinfo(ui('Comunidade', 'Community'), ui('Esta publicação ainda não possui arquivo.', 'This submission does not have a file yet.'), parent=self)
            return
        folder = os.path.join(_APPDATA, "community_cache")
        os.makedirs(folder, exist_ok=True)
        extension = Path(item.get("original_filename") or ".cbz").suffix or ".cbz"
        destination = os.path.join(folder, item["publication_id"] + extension)
        self._download_item(item, destination, open_after=True)

    def _download_selected(self):
        item = self._selected_item()
        if not item or not item.get("has_file"):
            messagebox.showinfo(ui('Comunidade', 'Community'), ui('Esta publicação ainda não possui arquivo.', 'This submission does not have a file yet.'), parent=self)
            return
        destination = filedialog.asksaveasfilename(
            parent=self, initialfile=item.get("original_filename") or "quadrinho.cbz"
        )
        if destination:
            self._download_item(item, destination, open_after=False)

    def _download_item(self, item, destination, open_after):
        self._status.config(text=ui('Baixando arquivo…', 'Downloading file…'), fg=THEME["text_dim"])
        token = self._token()
        url = f"{api_client.BASE_URL}/publications/{item['publication_id']}/content"
        def done(task):
            error = task.error or (ui('Download cancelado.', 'Download cancelled.') if task.status == "cancelled" else None)
            try: self.after(0, lambda: self._download_finished(destination, open_after, error))
            except tk.TclError: pass
        download_manager.add(item.get("title") or ui('Quadrinho', 'Comic'), url, destination, token, done)

    def _download_finished(self, destination, open_after, error):
        if error:
            self._status.config(text=error, fg=THEME["accent2"])
            return
        self._status.config(text=ui('Download concluído.', 'Download completed.'), fg=THEME["text_dim"])
        if open_after:
            try:
                loader = SmartPageLoader(destination)
                ReaderWindow(self, destination, loader)
            except Exception as exc:
                messagebox.showerror(ui('Leitura', 'Reading'), ui(f"Não foi possível abrir: {exc}", f"Could not open: {exc}"), parent=self)

    def _set_detail(self, text):
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")


class CommunityTab(tk.Frame):
    pass
    STATUS_LABELS = CommunityWindow.STATUS_LABELS
    def status_label(self, status):
        return CommunityWindow.status_label(status)
    def __init__(self, master, root, user=None, mine=False):
        super().__init__(master,bg=THEME["bg"])
        self.root,self.user,self.mine=root,user,mine
        self.images=[];self.items=[]
        self.pack(fill="both",expand=True)
        head=tk.Frame(self,bg=THEME["bg"]);head.pack(fill="x",padx=24,pady=(18,8))
        tk.Label(head,text=ui('Meus envios', 'My submissions') if mine else ui('Descobrir', 'Discover'),font=FTITLE,bg=THEME["bg"],fg=THEME["text"]).pack(side="left")
        make_pill(head,ui('Atualizar', 'Refresh'),self.refresh,variant="ghost",font=FBTN,pad_x=14,pad_y=7).pack(side="right")
        self.status=tk.Label(self,text=ui('Carregando…', 'Loading…'),font=FSMALL,bg=THEME["bg"],fg=THEME["text_dim"]);self.status.pack(anchor="w",padx=24)
        self.canvas=tk.Canvas(self,bg=THEME["bg"],highlightthickness=0)
        bar=ttk.Scrollbar(self,orient="vertical",command=self.canvas.yview)
        self.grid_frame=tk.Frame(self.canvas,bg=THEME["bg"])
        self.window=self.canvas.create_window((0,0),window=self.grid_frame,anchor="nw")
        self.grid_frame.bind("<Configure>",lambda _e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",lambda e:(self.canvas.itemconfigure(self.window,width=e.width),self._arrange()))
        self.canvas.configure(yscrollcommand=bar.set);bar.pack(side="right",fill="y");self.canvas.pack(fill="both",expand=True,padx=(18,0),pady=10)
        self.refresh()
    def refresh(self):
        self.status.config(text=ui('Carregando…', 'Loading…'),fg=THEME["text_dim"])
        def work():
            try:
                rows=api_client.my_publications(self.user.token) if self.mine else api_client.discovery(); result=(rows,None)
            except api_client.ApiUnavailableError:
                cached,_=load_catalog();result=(cached,None) if cached and not self.mine else (None,ui('Servidor indisponível.', 'Server unavailable.'))
            except Exception as exc:result=(None,str(exc))
            self.root.after(0,lambda:self._loaded(*result))
        threading.Thread(target=work,daemon=True).start()
    def _loaded(self,items,error):
        if not self.winfo_exists():return
        if error:self.status.config(text=error,fg=THEME["accent2"]);return
        self.items=items or []
        if not self.mine:save_catalog(self.items)
        for child in self.grid_frame.winfo_children():child.destroy()
        self.images=[];self.cards=[]
        noun = ui("envio(s)", "submission(s)") if self.mine else ui("obra(s)", "work(s)")
        self.status.config(text=f"{len(self.items)} {noun}",fg=THEME["text_dim"])
        if not self.items:
            tk.Label(self.grid_frame,text=ui('Nenhum item encontrado.', 'No items found.'),font=FLABEL,bg=THEME["bg"],fg=THEME["text_dim"]).grid(row=0,column=0,padx=30,pady=60);return
        for item in self.items:self.cards.append(self._card(item))
        self._arrange()
    def _arrange(self):
        if not getattr(self,"cards",None):return
        cols=max(1,self.canvas.winfo_width()//210)
        for i,card in enumerate(self.cards):card.grid(row=i//cols,column=i%cols,padx=10,pady=10,sticky="n")
    def _card(self,item):
        card=tk.Frame(self.grid_frame,bg=THEME["surface"],width=184,height=400 if self.mine else 370,highlightthickness=1,highlightbackground=THEME["border"]);card.pack_propagate(False)
        animate_color(card,"highlightbackground",THEME["bg"],THEME["border"],duration=300)
        card.bind("<Enter>",lambda e:animate_color(card,"highlightbackground",card.cget("highlightbackground"),THEME["accent"]))
        card.bind("<Leave>",lambda e:animate_color(card,"highlightbackground",card.cget("highlightbackground"),THEME["border"]))
        cover_box=tk.Frame(card,width=160,height=220,bg=THEME["surface_alt"])
        cover_box.pack(padx=11,pady=(11,7));cover_box.pack_propagate(False)
        cover=tk.Label(cover_box,text=ui('Carregando capa…', 'Loading cover…') if item.get("has_file") else ui('Arquivo indisponível', 'File unavailable'),font=FTINY,bg=THEME["surface_alt"],fg=THEME["text_dim"],wraplength=145);cover.pack(fill="both",expand=True)
        tk.Label(card,text=item.get("title") or ui('Sem título', 'Untitled'),font=FBTN,bg=THEME["surface"],fg=THEME["text"],wraplength=160).pack(padx=8)
        meta=self.status_label(item.get("status")) if self.mine else item.get("author",ui('Autor desconhecido', 'Unknown author'))
        tk.Label(card,text=meta,font=FTINY,bg=THEME["surface"],fg=THEME["text_dim"],wraplength=160).pack(padx=8,pady=2)
        if self.mine:
            make_pill(card,ui('Remover envio', 'Remove submission'),lambda i=item:self._remove(i),variant="ghost",font=FSMALL,pad_x=10,pad_y=5).pack(side="bottom",pady=(0,8))
        if item.get("has_file"):
            make_pill(card,ui('Baixar', 'Download'),lambda i=item:self._download(i),variant="accent",font=FSMALL,pad_x=12,pad_y=6).pack(side="bottom",pady=9)
            self._load_cover(item,cover)
        return card
    def _remove(self,item):
        if getattr(self,"_removing",False):return
        comic_title = item.get("title", ui("Quadrinho", "Comic"))
        question = ui(
            f"Remover ‘{comic_title}’ da comunidade?\n\nO arquivo da sua biblioteca não será apagado. Para publicar novamente, será necessário um novo envio.",
            f"Remove ‘{comic_title}’ from the community?\n\nThe file in your library will not be deleted. To publish it again, create a new submission.",
        )
        if not messagebox.askyesno(ui('Remover envio', 'Remove submission'), question, parent=self.root):return
        self._removing=True
        self.status.config(text=ui('Removendo envio…', 'Removing submission…'))
        def work():
            try:
                api_client.remove_publication(self.user.token,item["publication_id"])
                error=None
            except Exception as exc:error=str(exc)
            def done():
                if not self.winfo_exists():return
                self._removing=False
                if error:self.status.config(text=error,fg=THEME["accent2"])
                else:
                    cached,_=load_catalog()
                    save_catalog([row for row in (cached or []) if row.get("publication_id")!=item["publication_id"]])
                    self.refresh()
            self.root.after(0,done)
        threading.Thread(target=work,daemon=True).start()
    def _load_cover(self,item,label):
        token=self.user.token if self.user else None
        def work():
            try:
                data=api_client.publication_cover(item["publication_id"],token);image=Image.open(io.BytesIO(data)).convert("RGB");image.thumbnail((160,220),Image.LANCZOS);error=None
            except Exception as exc:image,error=None,str(exc)
            def done(image,error):
                if not label.winfo_exists():return
                if error:label.config(text=ui('Capa indisponível', 'Cover unavailable'));return
                photo=ImageTk.PhotoImage(image);self.images.append(photo);label.config(image=photo,text="")
            self.root.after(0,lambda:done(image,error))
        threading.Thread(target=work,daemon=True).start()
    def _download(self,item):
        destination=filedialog.asksaveasfilename(parent=self.root,initialfile=item.get("original_filename") or "quadrinho.cbz")
        if not destination:return
        self.status.config(text=ui('Download adicionado à central.', 'Download added to the download center.'))
        url=f"{api_client.BASE_URL}/publications/{item['publication_id']}/content"
        download_manager.add(item.get("title") or ui('Quadrinho', 'Comic'),url,destination,self.user.token if self.user else None)
