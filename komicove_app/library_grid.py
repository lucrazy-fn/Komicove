"""Keep only the visible library rows as items on the scrolling canvas."""
import math
import bisect


class LibraryGrid:
    def __init__(self, canvas, scrollbar, header, paths, columns, card_width,
                 gap, padding, create_card, release_card, sections=()):
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
        self.sections = sections
        self.positions = {}
        self.rows = []
        self.row_tops = []
        self.section_items = []
        self.cards = {}
        self.job = None
        self.closed = False
        first = create_card(paths[0])
        first.frame.update_idletasks()
        self.row_height = first.frame.winfo_reqheight() + gap
        self.cards[0] = (first, self._place(first, 0))
        self.bindings = [(header, header.bind('<Configure>', self._layout, add='+')),
                         (canvas, canvas.bind('<Configure>', self._layout, add='+'))]
        self.destroy_binding = canvas.bind('<Destroy>',
            lambda event: self.close() if event.widget is canvas else None, add='+')
        self.original_scroll_command = canvas.cget('yscrollcommand')
        canvas.configure(yscrollcommand=self._scrolled, yscrollincrement=28)
        self.scroll_command = canvas.cget('yscrollcommand')
        self._layout()

    def _place(self, card, index):
        row, column = divmod(index, self.columns)
        x = self.padding + column * (self.card_width + self.gap)
        y = self.header.winfo_reqheight() + self.gap + row * self.row_height
        if self.sections and index in self.positions:
            x, y = self.positions[index]
        if hasattr(card, 'place_on_canvas'):
            return card.place_on_canvas(x, y)
        item = getattr(card, '_canvas_window', None)
        if item is None:
            item = card._canvas_window = self.canvas.create_window(x, y, window=card.frame, anchor='nw')
        else:
            self.canvas.coords(item, x, y)
        return item

    def _layout(self, event=None):
        if self.closed:
            return
        top = self.header.winfo_reqheight() + self.gap
        height = top + math.ceil(len(self.paths) / self.columns) * self.row_height
        if self.sections:
            self.rows, self.row_tops, self.positions = [], [], {}
            if not self.section_items:
                for _, heading in self.sections:
                    self.section_items.append((self.canvas.create_window(0, 0, window=heading, anchor='nw'),
                        self.canvas.create_line(0, 0, 0, 0, fill=self.canvas.cget('bg'))))
            y = top
            for section, (start, heading) in enumerate(self.sections):
                end = self.sections[section + 1][0] if section + 1 < len(self.sections) else len(self.paths)
                window, separator = self.section_items[section]
                width = max(1, self.canvas.winfo_width() - self.padding * 2)
                self.canvas.itemconfigure(window, width=width)
                self.canvas.coords(window, self.padding, y)
                y += heading.winfo_reqheight() + self.gap
                for first in range(start, end, self.columns):
                    indices = range(first, min(end, first + self.columns))
                    self.rows.append(indices)
                    self.row_tops.append(y)
                    for column, index in enumerate(indices):
                        self.positions[index] = (self.padding + column * (self.card_width + self.gap), y)
                    y += self.row_height
                self.canvas.coords(separator, self.padding, y, self.padding + width, y)
                y += self.gap * 2
            height = y
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(),
                                            max(height, self.canvas.winfo_height())))
        for index, (card, _) in self.cards.items():
            self._place(card, index)
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
        if self.sections:
            first = max(0, bisect.bisect_right(self.row_tops, self.canvas.canvasy(0)) - 2)
            last = bisect.bisect_right(self.row_tops, self.canvas.canvasy(self.canvas.winfo_height())) + 1
            wanted = {index for row in self.rows[first:last] for index in row}
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
            self.canvas.unbind('<Destroy>', self.destroy_binding)
            self.canvas.configure(yscrollcommand=self.original_scroll_command)
            self.canvas.deletecommand(self.scroll_command)
