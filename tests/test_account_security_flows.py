from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from panel_backend.accounts import account_actions
from panel_backend.accounts.models import AccountActionToken, User
from panel_backend.accounts.security import totp_code
from panel_backend.api.app import app
from panel_backend.api.deps import get_db
from panel_backend.db import Base


def test_email_recovery_and_2fa_for_regular_user(monkeypatch):
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); Session=sessionmaker(bind=engine,expire_on_commit=False)
    def override_db():
        with Session.begin() as db: yield db
    app.dependency_overrides[get_db]=override_db
    monkeypatch.setattr(account_actions,"send_account_email",lambda *args:True)
    try:
        with TestClient(app) as client:
            created=client.post("/auth/register",json={"username":"seguro","password":"senha-segura","email":"safe@example.com"}).json()
            token=created["token"]; headers={"Authorization":f"Bearer {token}"}
            with Session.begin() as db:
                verify=db.scalar(select(AccountActionToken).where(AccountActionToken.purpose=="verify_email"))
                # Generate a token through the public helper so the raw value is available to this test.
                user=db.scalar(select(User).where(User.username=="seguro")); raw_verify=account_actions.issue(db,user,"verify_email",30)
            assert client.post("/auth/email/confirm",json={"token":raw_verify}).status_code==200
            assert client.get("/account/profile",headers=headers).json()["email_verified"] is True

            setup=client.post("/account/2fa/setup",headers=headers,json={"current_password":"senha-segura","current_code":None}).json()
            confirmed=client.post("/account/2fa/confirm",headers=headers,json={"code":totp_code(setup["secret"])}).json()
            assert len(confirmed["recovery_codes"])==8
            assert client.post("/auth/login",json={"username":"seguro","password":"senha-segura"}).status_code==401
            assert client.post("/auth/login",json={"username":"seguro","password":"senha-segura","totp_code":totp_code(setup["secret"])}).status_code==200
            recovery=confirmed["recovery_codes"][0]
            assert client.post("/auth/login",json={"username":"seguro","password":"senha-segura","totp_code":recovery}).status_code==200
            assert client.post("/auth/login",json={"username":"seguro","password":"senha-segura","totp_code":recovery}).status_code==401

            assert client.post("/auth/password-recovery/request",json={"identifier":"safe@example.com"}).status_code==200
            with Session.begin() as db:
                user=db.scalar(select(User).where(User.username=="seguro")); raw_reset=account_actions.issue(db,user,"reset_password",30)
            assert client.post("/auth/password-recovery/confirm",json={"token":raw_reset,"new_password":"nova-senha-segura"}).status_code==200
            assert client.post("/auth/login",json={"username":"seguro","password":"nova-senha-segura","totp_code":totp_code(setup["secret"])}).status_code==200
    finally:
        app.dependency_overrides.pop(get_db,None)
