import time

import jwt
import pytest
from conftest import material
from fastapi.testclient import TestClient

from autoformularz import pipeline
from autoformularz.config import Settings, get_settings
from autoformularz.main import app

SECRET = "test-secret-with-at-least-32-bytes!!"


@pytest.fixture
def client(monkeypatch, nadplata_spec):
    settings = Settings(auth_enabled=True, jwt_secret=SECRET)
    app.dependency_overrides[get_settings] = lambda: settings
    real = pipeline.from_file
    monkeypatch.setattr(
        pipeline, "from_file", lambda name, data, s: real(name, data, s, llm=lambda ex, _: nadplata_spec)
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def token(**claims) -> str:
    return jwt.encode({"sub": "urzednik", "exp": int(time.time()) + 60, **claims}, SECRET, algorithm="HS256")


def auth() -> dict:
    return {"Authorization": f"Bearer {token()}"}


def test_requires_jwt(client):
    assert client.post("/api/v1/forms/validate", json={}).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.post("/api/v1/forms/validate", json={}, headers=bad).status_code == 401


def test_convert_docx_returns_importable_json(client):
    path = material("5. */*nadpłaty podatku.docx")
    r = client.post("/api/v1/forms", headers=auth(), files={"file": (path.name, path.read_bytes())})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"title", "tabs", "flow"}
    assert r.headers["X-Autoformularz-Errors"] == "0"


def test_convert_details(client):
    path = material("5. */*nadpłaty podatku.docx")
    r = client.post(
        "/api/v1/forms?details=true", headers=auth(), files={"file": (path.name, path.read_bytes())}
    )
    body = r.json()
    assert body["sourceFormat"] == "docx" and body["spec"]["title"] and "issues" in body
    blocks = body["document"]["blocks"]
    assert blocks and set(blocks[0]) == {"id", "text", "kind", "page"}
    assert set(body["coverage"]) == {
        "blocks",
        "referenced",
        "unreferenced",
        "candidates",
        "candidatesWithoutField",
        "unknownRefs",
    }
    assert body["coverage"]["blocks"] == len(blocks)


def test_compile_details_has_no_document(client, nadplata_spec):
    r = client.post(
        "/api/v1/forms/compile?details=true", headers=auth(), json=nadplata_spec.model_dump(mode="json")
    )
    assert r.json()["document"] is None and r.json()["coverage"] is None


def test_rejects_mismatched_file(client):
    r = client.post("/api/v1/forms", headers=auth(), files={"file": ("a.pdf", b"\x89PNG\r\n\x1a\nxxxx")})
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "MIME_MISMATCH"


def test_compile_and_schema(client, nadplata_spec):
    r = client.post("/api/v1/forms/compile", headers=auth(), json=nadplata_spec.model_dump(mode="json"))
    assert r.status_code == 200 and r.json()["tabs"]
    assert "properties" in client.get("/api/v1/spec/schema").json()
