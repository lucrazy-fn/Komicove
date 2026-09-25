import ast
import pathlib
import re

from komicove_app import runtime
from komicove_app.translations import ui


PORTUGUESE_UI = re.compile(
    r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]|\b(?:não|nenhum|página|leitura|publicação|senha|"
    r"conta|salvar|escolher|arquivo|pasta|atualização|denúncia|série|título|autor|"
    r"capítulo|abrir|voltar|falha|erro|concluído|aprovar|rejeitar|enviar|remover|"
    r"biblioteca|coleções|comunidade|moderação|notificação|diagnóstico|preferências|"
    r"cancelar|fechar|próximo|anterior)\b",
    re.IGNORECASE,
)


def test_explicit_language_selection_covers_reported_labels(monkeypatch):
    monkeypatch.setattr(runtime, "LANG", "en")
    pairs = [
        ("Descobrir", "Discover"), ("Meus envios", "My submissions"),
        ("Notificações", "Notifications"), ("Moderação", "Moderation"),
        ("Denúncias", "Reports"), ("Atualizar", "Refresh"),
        ("Remover envio", "Remove submission"), ("Série / Autor", "Series / Author"),
        ("Diagnóstico seguro", "Safe diagnostics"),
    ]
    for portuguese, english in pairs:
        assert ui(portuguese, english) == english


def test_desktop_widget_literals_use_explicit_ui_choice():
    root = pathlib.Path(__file__).parents[1] / "komicove_app"
    sinks = {
        "Label", "Button", "Checkbutton", "Radiobutton", "title", "showerror",
        "showinfo", "showwarning", "askyesno", "askstring", "create_text",
        "make_pill", "_mkbtn", "_sidebar_item",
    }
    untranslated = []
    for path in root.glob("*.py"):
        if path.name == "translations.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if not PORTUGUESE_UI.search(node.value):
                continue
            current, wrapped, visible = node, False, False
            for _ in range(10):
                current = parents.get(current)
                if current is None:
                    break
                if isinstance(current, ast.Call):
                    name = (current.func.attr if isinstance(current.func, ast.Attribute)
                            else current.func.id if isinstance(current.func, ast.Name) else "")
                    if name == "ui":
                        wrapped = True
                        break
                    if name in sinks:
                        visible = True
            if visible and not wrapped:
                untranslated.append(f"{path.name}:{node.lineno}: {node.value!r}")
    assert not untranslated, "Desktop UI without explicit language choice:\n" + "\n".join(untranslated)


def test_android_uses_explicit_translation_at_component_boundaries():
    root = pathlib.Path(__file__).parents[1] / "android" / "app" / "src" / "main" / "java" / "com" / "lucrazy" / "komicove"
    i18n = (root / "I18n.java").read_text(encoding="utf-8")
    ui_source = (root / "Ui.java").read_text(encoding="utf-8")
    dialog_source = (root / "PanelDialog.java").read_text(encoding="utf-8")
    assert "static void localize" not in i18n
    assert "I18n.t(c,s)" in ui_source
    assert "I18n.t(context" in dialog_source
    for label in ("Descobrir quadrinhos", "Meus envios", "Notificações", "Moderação",
                  "Remover envio", "Diagnóstico seguro", "Preferências do leitor"):
        assert f'put("{label}",' in i18n
