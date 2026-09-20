from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from PIL import ImageTk

from panel_app.translations import ui


class PanelEditor(tk.Toplevel):
    def __init__(self, master, image, regions, auto_regions, on_save):
        super().__init__(master)
        self.title(ui("Editor manual de quadros", "Manual panel editor"))
        self.configure(bg="#101018")
        self.geometry("980x760")
        self.minsize(720, 560)
        self.image=image.convert("RGB"); self.regions=[list(r) for r in regions]
        self.auto_regions=[list(r) for r in auto_regions]; self.on_save=on_save
        self.selected=None; self.action=None; self.start=None; self._photo=None
        bar=tk.Frame(self,bg="#181823"); bar.pack(fill="x")
        tk.Label(bar,text=ui("Arraste no vazio para criar. Arraste um quadro ou seus cantos para ajustar.",
            "Drag empty space to create. Drag a panel or its corners to adjust."),bg="#181823",fg="#ddd").pack(side="left",padx=14,pady=10)
        for text,cmd in [(ui("Excluir","Delete"),self._delete),(ui("◀ Ordem","◀ Order"),lambda:self._order(-1)),
                         (ui("Ordem ▶","Order ▶"),lambda:self._order(1)),(ui("Redetectar","Redetect"),self._reset),
                         (ui("Salvar","Save"),self._save)]:
            tk.Button(bar,text=text,command=cmd,bg="#e52b32" if cmd==self._save else "#252536",
                      fg="white",relief="flat",padx=12,pady=7).pack(side="right",padx=4,pady=6)
        self.cv=tk.Canvas(self,bg="#07070e",highlightthickness=0); self.cv.pack(fill="both",expand=True)
        self.cv.bind("<Configure>",lambda e:self._draw())
        self.cv.bind("<Button-1>",self._down); self.cv.bind("<B1-Motion>",self._move); self.cv.bind("<ButtonRelease-1>",self._up)
        self.bind("<Delete>",lambda e:self._delete()); self.transient(master); self.grab_set()

    def _geometry(self):
        w=max(1,self.cv.winfo_width()); h=max(1,self.cv.winfo_height())
        scale=min((w-30)/self.image.width,(h-30)/self.image.height)
        iw,ih=int(self.image.width*scale),int(self.image.height*scale)
        return (w-iw)//2,(h-ih)//2,iw,ih

    def _draw(self):
        self.cv.delete("all"); ox,oy,iw,ih=self._geometry()
        preview=self.image.resize((iw,ih)); self._photo=ImageTk.PhotoImage(preview)
        self.cv.create_image(ox,oy,anchor="nw",image=self._photo)
        for i,(l,t,r,b) in enumerate(self.regions):
            box=(ox+l*iw,oy+t*ih,ox+r*iw,oy+b*ih); selected=i==self.selected
            self.cv.create_rectangle(*box,outline="#ff3545" if selected else "#52d6ff",width=4 if selected else 2)
            self.cv.create_text(box[0]+8,box[1]+8,text=str(i+1),anchor="nw",fill="white",font=("Segoe UI",11,"bold"))
            if selected:
                for x,y in ((box[0],box[1]),(box[2],box[1]),(box[0],box[3]),(box[2],box[3])):
                    self.cv.create_rectangle(x-6,y-6,x+6,y+6,fill="#ff3545",outline="white")

    def _norm(self,x,y):
        ox,oy,iw,ih=self._geometry(); return max(0,min(1,(x-ox)/iw)),max(0,min(1,(y-oy)/ih))
    def _down(self,e):
        x,y=self._norm(e.x,e.y); self.start=(x,y); self.action="new"; self.selected=None
        for i in range(len(self.regions)-1,-1,-1):
            l,t,r,b=self.regions[i]
            if l<=x<=r and t<=y<=b:
                self.selected=i; self.action="move"; self.original=list(self.regions[i])
                margin=.035
                corners=[(l,t,"tl"),(r,t,"tr"),(l,b,"bl"),(r,b,"br")]
                nearest=min(corners,key=lambda p:(p[0]-x)**2+(p[1]-y)**2)
                if abs(nearest[0]-x)<margin and abs(nearest[1]-y)<margin: self.action=nearest[2]
                break
        self._draw()
    def _move(self,e):
        x,y=self._norm(e.x,e.y); sx,sy=self.start
        if self.action=="new":
            rect=[min(sx,x),min(sy,y),max(sx,x),max(sy,y)]
            if self.selected is None: self.regions.append(rect); self.selected=len(self.regions)-1
            else: self.regions[self.selected]=rect
            self.action="new-active"
        elif self.action=="new-active":
            self.regions[self.selected]=[min(sx,x),min(sy,y),max(sx,x),max(sy,y)]
        elif self.selected is not None:
            l,t,r,b=self.original
            if self.action=="move":
                dx,dy=x-sx,y-sy; dx=max(-l,min(1-r,dx)); dy=max(-t,min(1-b,dy)); self.regions[self.selected]=[l+dx,t+dy,r+dx,b+dy]
            else:
                if "l" in self.action: l=min(x,r-.02)
                if "r" in self.action: r=max(x,l+.02)
                if "t" in self.action: t=min(y,b-.02)
                if "b" in self.action: b=max(y,t+.02)
                self.regions[self.selected]=[l,t,r,b]
        self._draw()
    def _up(self,e):
        self.action=None
        self.regions=[r for r in self.regions if r[2]-r[0]>=.02 and r[3]-r[1]>=.02]
        if self.selected is not None: self.selected=min(self.selected,len(self.regions)-1) if self.regions else None
        self._draw()
    def _delete(self):
        if self.selected is not None: self.regions.pop(self.selected); self.selected=None; self._draw()
    def _order(self,d):
        if self.selected is None:return
        target=max(0,min(len(self.regions)-1,self.selected+d))
        self.regions[self.selected],self.regions[target]=self.regions[target],self.regions[self.selected]; self.selected=target; self._draw()
    def _reset(self): self.regions=[list(r) for r in self.auto_regions]; self.selected=None; self._draw()
    def _save(self):
        if not self.regions:
            messagebox.showwarning(ui("Editor de quadros","Panel editor"),ui("Crie pelo menos um quadro.","Create at least one panel."),parent=self); return
        self.on_save([tuple(r) for r in self.regions]); self.destroy()
