from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from komicove_backend.api.app import app
from komicove_backend.api.deps import get_db
from komicove_backend.db import Base


def test_account_can_list_and_revoke_another_real_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with Session.begin() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            registered = client.post(
                "/auth/register",
                headers={"X-Komicove-Device": "Komicove Desktop (Windows)"},
                json={"username": "sessions.user", "password": "senha-segura"},
            ).json()
            primary = registered["token"]
            secondary = client.post(
                "/auth/login",
                headers={"X-Komicove-Device": "Android"},
                json={"username": "sessions.user", "password": "senha-segura"},
            ).json()["token"]
            response = client.get(
                "/account/sessions", headers={"Authorization": f"Bearer {primary}"}
            )
            assert response.status_code == 200
            sessions = response.json()
            assert {item["device_name"] for item in sessions} == {
                "Komicove Desktop (Windows)", "Android",
            }
            other = next(item for item in sessions if not item["current"])
            assert client.delete(
                f"/account/sessions/{other['id']}",
                headers={"Authorization": f"Bearer {primary}"},
            ).status_code == 204
            assert client.get(
                "/auth/me", headers={"Authorization": f"Bearer {secondary}"}
            ).status_code == 401
    finally:
        app.dependency_overrides.clear()
