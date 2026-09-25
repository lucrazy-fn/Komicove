from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from komicove_backend.accounts.service import authenticate, get_user_by_token, logout, register_user
from komicove_backend.db import Base


def test_register_login_validate_and_logout():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session.begin() as db:
        registered = register_user(db, username="leitor", password="senha-segura")
        user_id = registered.user.id

    with Session.begin() as db:
        logged_in = authenticate(db, username="leitor", password="senha-segura")
        token = logged_in.token

    with Session.begin() as db:
        assert get_user_by_token(db, token).id == user_id
        logout(db, token)

    with Session.begin() as db:
        assert get_user_by_token(db, token) is None
