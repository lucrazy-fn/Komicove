from .translations import ui

ROLE_LABELS={"user":("Usuário","User"),"moderator":("Moderador","Moderator"),"admin":("Administrador","Administrator"),"owner":("Dono","Owner")}
def role_label(user):
    portuguese, english = ROLE_LABELS.get(getattr(user,"role","user"), ROLE_LABELS["user"])
    return ui(portuguese, english)
