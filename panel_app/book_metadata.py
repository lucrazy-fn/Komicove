import os
from .storage import APPDATA_DIR, json_load, json_save

FILE = os.path.join(APPDATA_DIR, 'book_metadata.json')


def get(path):
    return dict(json_load(FILE, {}).get(os.path.abspath(path), {}))


def save(path, values):
    data = json_load(FILE, {})
    data[os.path.abspath(path)] = {key: str(value).strip() for key, value in values.items()
                                 if key in {'title', 'writer', 'series', 'number', 'cover'}}
    if not json_save(FILE, data):
        raise OSError('Não foi possível salvar as informações da HQ.')


def edit(parent, path, original, refresh):
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from PIL import Image
    from .runtime import THEME, FLABEL
    values = {**original, **get(path)}
    dialog = tk.Toplevel(parent)
    dialog.title('Editar informações da HQ')
    dialog.configure(bg=THEME['bg'])
    dialog.geometry('480x490')
    entries = {}
    for key, title in [('title', 'Título'), ('writer', 'Autor'), ('series', 'Série'), ('number', 'Número da edição')]:
        tk.Label(dialog, text=title, bg=THEME['bg'], fg=THEME['text'], font=FLABEL).pack(anchor='w', padx=20, pady=(12, 3))
        entry = tk.Entry(dialog, font=FLABEL)
        entry.insert(0, values.get(key, ''))
        entry.pack(fill='x', padx=20)
        entries[key] = entry
    cover = [values.get('cover', '')]
    def choose():
        selected = filedialog.askopenfilename(parent=dialog, filetypes=[('Imagens', '*.png *.jpg *.jpeg *.webp')])
        if selected:
            cover[0] = selected
            cover_button.configure(text='Capa selecionada')
    cover_button = tk.Button(dialog, text='Escolher capa', command=choose)
    cover_button.pack(pady=14)
    def commit():
        try:
            new = {key: entry.get() for key, entry in entries.items()}
            if cover[0]:
                import hashlib
                folder = os.path.join(APPDATA_DIR, 'custom_covers')
                os.makedirs(folder, exist_ok=True)
                dest = os.path.join(folder, hashlib.sha256(os.path.abspath(path).encode()).hexdigest() + '.png')
                with Image.open(cover[0]) as source:
                    image = source.convert('RGB')
                    image.thumbnail((800, 1200))
                    image.save(dest)
                new['cover'] = dest
            save(path, new)
        except Exception as error:
            messagebox.showerror('Não foi possível salvar', str(error), parent=dialog)
            return
        dialog.destroy()
        refresh()
    tk.Button(dialog, text='Salvar informações', command=commit).pack(pady=8)
    tk.Label(dialog, text='O arquivo original não será alterado.', bg=THEME['bg'], fg=THEME['text_dim']).pack()
