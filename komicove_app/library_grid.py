"""Keep only the visible library rows as items on the scrolling canvas."""
import math


class LibraryGrid:
    def __init__(self, canvas, scrollbar, header, paths, columns, card_width,
                 gap, padding, create_card, release_card):
        self.canvas = canvas
        self.scrollbar = scrollbar
        self.header = header
        self.paths = paths
        self.columns = columns
        self.card_width = card_width
        self.gap = gap
        self.padding = padding
        self.create_card = create_card
        self.release_card = release_card
        self.cards = {}
        self.job = None
        self.closed = False
        first = create_card(paths[0])
        first.frame.update_idletasks()
        self.row_height = first.frame.winfo_reqheight() + gap
        self.cards[0] = (first, self._place(first, 0))
        self.bindings = [(header, header.bind('<Configure>', self._layout, add='+')),
                         (canvas, canvas.bind('<Configure>', self._layout, add='+'))]
        canvas.bind('<Destroy>', lambda event: self.close() if event.widget is canvas else None, add='+')
        canvas.configure(yscrollcommand=self._scrolled, yscrollincrement=28)
        self._layout()

    def _place(self, card, index):
        row, column = divmod(index, self.columns)
        return card.place_on_canvas(self.padding + column * (self.card_width + self.gap),
            self.header.winfo_reqheight() + self.gap + row * self.row_height)

    def _layout(self, event=None):
        if self.closed:
            return
        top = self.header.winfo_reqheight() + self.gap
        height = top + math.ceil(len(self.paths) / self.columns) * self.row_height
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(),
                                            max(height, self.canvas.winfo_height())))
        for index, (card, _) in self.cards.items():
            row, column = divmod(index, self.columns)
            card.place_on_canvas(self.padding + column * (self.card_width + self.gap),
                                 top + row * self.row_height)
        self.schedule()

    def _scrolled(self, first, last):
        self.scrollbar.set(first, last)
        self.schedule()

    def schedule(self):
        if not self.closed and self.job is None:
            self.job = self.canvas.after_idle(self.refresh)

    def refresh(self):
        self.job = None
        if self.closed or not self.canvas.winfo_exists():
            return
        top = self.header.winfo_reqheight() + self.gap
        start = max(0, int((self.canvas.canvasy(0) - top) // self.row_height) - 1)
        end = max(0, int((self.canvas.canvasy(self.canvas.winfo_height()) - top)
                         // self.row_height) + 2)
        wanted = set(range(min(len(self.paths), start * self.columns),
                           min(len(self.paths), end * self.columns)))
        for index in self.cards.keys() - wanted:
            card, item = self.cards.pop(index)
            self.release_card(card, self.paths[index])
            self.canvas.delete(item)
        for index in sorted(wanted - self.cards.keys()):
            card = self.create_card(self.paths[index])
            self.cards[index] = (card, self._place(card, index))

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.job is not None:
            self.canvas.after_cancel(self.job)
            self.job = None
        for widget, binding in self.bindings:
            if widget.winfo_exists():
                widget.unbind('<Configure>', binding)
        for index, (card, item) in self.cards.items():
            self.release_card(card, self.paths[index])
            if self.canvas.winfo_exists():
                self.canvas.delete(item)
        self.cards.clear()
        self.canvas._comic_hit_photo = None
        self.canvas._comic_hit_size = None
        if self.canvas.winfo_exists():
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
