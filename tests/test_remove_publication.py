from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from komicove_backend.api.app import app
from komicove_backend.api.deps import get_db
from komicove_backend.db import Base


def test_only_uploader_can_remove_publication():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def database():
        with sessions.begin() as db:
            yield db
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            def register(name):
                response = client.post("/auth/register", json={"username": name, "password": "senha-segura-123"})
                assert response.status_code == 201
                return {"Authorization": "Bearer " + response.json()["token"]}
            owner, other = register("uploader"), register("otherreader")
            response = client.post("/publications", headers=owner, json={
                "title": "Minha obra", "author": "Autor", "description": "Original",
                "tags": [], "file_reference": "original.cbz", "authorship_declared": True,
                "authorization_declared": False,
            })
            assert response.status_code == 201, response.text
            publication_id = response.json()["publication_id"]
            url = f"/publications/{publication_id}"
            assert client.delete(url).status_code == 401
            assert client.delete(url, headers=other).status_code == 404
            assert len(client.get("/publications/mine", headers=owner).json()) == 1
            assert client.delete(url, headers=owner).status_code == 204
            assert client.get("/publications/mine", headers=owner).json() == []
            assert client.get(url + "/content", headers=owner).status_code == 404
            assert client.delete(url, headers=owner).status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
