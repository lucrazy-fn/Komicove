import io
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from komicove_backend.api.app import app
from komicove_backend.api.deps import get_db
from komicove_backend.db import Base


def test_register_publish_discover_and_moderate(monkeypatch, tmp_path):
    monkeypatch.setenv("PANEL_MODERATOR_SETUP_TOKEN", "token-de-configuracao-seguro")
    monkeypatch.setenv("PANEL_STORAGE_DIR", str(tmp_path / "storage"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
                json={"username": "Leitor.Teste", "password": "senha-segura"},
            )
            assert registered.status_code == 201
            token = registered.json()["token"]

            current = client.get(
                "/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert current.status_code == 200
            assert current.json()["username"] == "leitor.teste"
            assert current.json()["is_moderator"] is False

            profile = client.patch(
                "/account/profile", headers={"Authorization": f"Bearer {token}"},
                json={"display_name": "Leitor Atualizado", "email": "leitor@example.com"},
            )
            assert profile.status_code == 200
            assert profile.json()["display_name"] == "Leitor Atualizado"
            synced = client.put(
                "/account/library-state", headers={"Authorization": f"Bearer {token}"},
                json={"items": [{"item_key": "comic.cbz", "page": 7, "favorite": True}]},
            )
            assert synced.status_code == 200
            assert synced.json()[0]["favorite"] is True

            forbidden = client.get(
                "/moderation/queue", headers={"Authorization": f"Bearer {token}"}
            )
            assert forbidden.status_code == 403
            forbidden_generation = client.post(
                "/api/moderator-tokens",
                headers={"Authorization": f"Bearer {token}"},
                json={"max_uses": 1, "valid_hours": 24},
            )
            assert forbidden_generation.status_code == 403

            promoted = client.post(
                "/auth/claim-moderator",
                headers={"Authorization": f"Bearer {token}"},
                json={"setup_token": "token-de-configuracao-seguro"},
            )
            assert promoted.status_code == 200
            assert promoted.json()["is_moderator"] is True
            assert promoted.json()["role"] == "owner"

            invite_response = client.post(
                "/api/moderator-tokens",
                headers={"Authorization": f"Bearer {token}"},
                json={"max_uses": 1, "valid_hours": 24},
            )
            assert invite_response.status_code == 200
            invite_secret = invite_response.json()["secret"]
            assert invite_secret.startswith("pnl_admin_")

            invited_user = client.post(
                "/auth/register",
                json={"username": "convidado.mod", "password": "senha-segura"},
            ).json()
            invited_id = invited_user["user"]["id"]
            ordinary_claim = client.post(
                "/auth/claim-moderator",
                headers={"Authorization": f"Bearer {invited_user['token']}"},
                json={"setup_token": invite_secret},
            )
            assert ordinary_claim.status_code == 403
            made_moderator = client.patch(
                f"/api/moderators/users/{invited_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"action": "set_role", "role": "moderator"},
            )
            assert made_moderator.status_code == 200
            invited_claim = client.post(
                "/auth/claim-moderator",
                headers={"Authorization": f"Bearer {invited_user['token']}"},
                json={"setup_token": invite_secret},
            )
            assert invited_claim.status_code == 200
            assert invited_claim.json()["is_moderator"] is True
            assert invited_claim.json()["role"] == "admin"

            third_user = client.post(
                "/auth/register",
                json={"username": "sem.convite", "password": "senha-segura"},
            ).json()
            exhausted = client.post(
                "/auth/claim-moderator",
                headers={"Authorization": f"Bearer {third_user['token']}"},
                json={"setup_token": invite_secret},
            )
            assert exhausted.status_code == 403

            users = client.get(
                "/api/moderators/users",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert users.status_code == 200
            assert next(u["role"] for u in users.json() if u["username"] == "convidado.mod") == "admin"

            self_action = client.patch(
                f"/api/moderators/users/{promoted.json()['id']}",
                headers={"Authorization": f"Bearer {token}"},
                json={"action": "set_role", "role": "user"},
            )
            assert self_action.status_code == 409

            suspended = client.patch(
                f"/api/moderators/users/{invited_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"action": "suspend", "duration_hours": 24, "reason": "teste"},
            )
            assert suspended.status_code == 200
            assert suspended.json()["punishment_reason"] == "teste"
            invalidated = client.get(
                "/auth/me", headers={"Authorization": f"Bearer {invited_user['token']}"}
            )
            assert invalidated.status_code == 401

            cleared = client.patch(
                f"/api/moderators/users/{invited_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"action": "clear_punishment"},
            )
            assert cleared.status_code == 200
            assert cleared.json()["suspended_until"] is None

            dashboard = client.get(
                "/api/moderators/dashboard",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert dashboard.status_code == 200
            assert dashboard.json()["total_users"] == 3

            detail = client.get(
                f"/api/moderators/users/{invited_id}/detail",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert detail.status_code == 200
            assert detail.json()["user"]["username"] == "convidado.mod"

            audit_rows = client.get(
                "/api/moderators/audit",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert audit_rows.status_code == 200
            assert "user_suspended" in {row["action"] for row in audit_rows.json()}

            publication = client.post(
                "/publications",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "title": "Minha obra original",
                    "author": "Pessoa Autora",
                    "description": "Uma história independente.",
                    "tags": ["Independente", "independente", "Aventura"],
                    "file_reference": "C:/quadrinhos/original.cbz",
                    "authorship_declared": True,
                },
            )
            assert publication.status_code == 201
            assert publication.json()["status"] == "pending_review"
            publication_id = publication.json()["publication_id"]

            image_buffer = io.BytesIO()
            Image.new("RGB", (80, 120), "red").save(image_buffer, "JPEG")
            comic_buffer = io.BytesIO()
            with zipfile.ZipFile(comic_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("001.jpg", image_buffer.getvalue())
            uploaded = client.put(
                f"/publications/{publication_id}/file",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("original.cbz", comic_buffer.getvalue(), "application/zip")},
            )
            assert uploaded.status_code == 200
            assert uploaded.json()["size_bytes"] > 0
            assert client.get(f"/publications/{publication_id}/cover").status_code == 403
            owner_cover = client.get(
                f"/publications/{publication_id}/cover",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert owner_cover.status_code == 200
            assert owner_cover.headers["content-type"] == "image/jpeg"

            discovery = client.get("/publications/discovery")
            assert discovery.status_code == 200
            assert discovery.json() == []

            my_items = client.get(
                "/publications/mine", headers={"Authorization": f"Bearer {token}"}
            )
            assert my_items.status_code == 200
            assert [item["status"] for item in my_items.json()] == ["pending_review"]

            queue = client.get(
                "/moderation/queue", headers={"Authorization": f"Bearer {token}"}
            )
            assert queue.status_code == 200
            assert len(queue.json()) == 1
            assert queue.json()[0]["has_file"] is True
            record_id = queue.json()[0]["record_id"]
            assert client.get(
                f"/moderation/{record_id}/cover",
                headers={"Authorization": f"Bearer {token}"},
            ).headers["content-type"] == "image/jpeg"
            downloaded = client.get(
                f"/moderation/{record_id}/file",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert downloaded.status_code == 200
            assert downloaded.content == comic_buffer.getvalue()

            decision = client.post(
                f"/moderation/{record_id}/decision",
                headers={"Authorization": f"Bearer {token}"},
                json={"decision": "approved", "reason": "Autoria comprovada."},
            )
            assert decision.status_code == 200
            notices = client.get(
                "/account/notifications", headers={"Authorization": f"Bearer {token}"}
            )
            assert notices.status_code == 200
            assert notices.json()[0]["kind"] == "publication_decision"
            assert client.get(
                "/moderation/queue", headers={"Authorization": f"Bearer {token}"}
            ).json() == []
            history = client.get(
                "/moderation/queue?include_decided=true",
                headers={"Authorization": f"Bearer {token}"},
            ).json()
            assert len(history) == 1
            assert history[0]["status"] == "approved"
            assert history[0]["decision_reason"] == "Autoria comprovada."

            reviewed = client.get(
                "/publications/mine", headers={"Authorization": f"Bearer {token}"}
            ).json()[0]
            assert reviewed["status"] == "approved"
            assert reviewed["decision_reason"] == "Autoria comprovada."

            discovered = client.get("/publications/discovery").json()
            assert [item["title"] for item in discovered] == ["Minha obra original"]
            assert discovered[0]["tags"] == ["Independente", "Aventura"]
            assert discovered[0]["has_file"] is True
            public_file = client.get(f"/publications/{publication_id}/content")
            assert public_file.status_code == 200
            assert public_file.content == comic_buffer.getvalue()
    finally:
        app.dependency_overrides.clear()
