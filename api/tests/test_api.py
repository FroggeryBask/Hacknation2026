import threading
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


def test_pipeline_passes_document_to_compiler(nadplata_spec):
    from autoformularz.spec import BlockRole, Role

    path = material("5. */*nadpłaty podatku.docx")
    seen = {}

    def fake_llm(doc, _):  # the first block the model sees (presort already took the paper-only ones)
        seen["first"] = doc.blocks[0]
        return nadplata_spec.model_copy(
            update={"block_roles": [BlockRole(block=doc.blocks[0].id, role=Role.LEGAL_BASIS)]}
        )

    settings = Settings(_env_file=None, copy_source_text=True)
    result = pipeline.from_file(path.name, path.read_bytes(), settings, llm=fake_llm)
    finish = result.form["tabs"][-1]["questions"]
    legal = [q["field"] for q in finish if q["field"]["techName"] == "podstawa_prawna"]
    from autoformularz.compiler import _plain

    assert legal, "LEGAL_BASIS block should become a finish-page section"
    text_block = legal[0]["repeatingSectionGrid"][0]["field"]["description"]
    assert _plain(seen["first"])[:20] in text_block
    assert result.document is not None and result.coverage is not None


def test_source_text_copy_is_off_by_default(nadplata_spec):
    """Saved results showed unreliable block roles (paper instructions, GDPR as legal basis): off by default."""
    from autoformularz.spec import BlockRole, Role

    path = material("5. */*nadpłaty podatku.docx")
    spec = nadplata_spec.model_copy(update={"block_roles": [BlockRole(block="b1", role=Role.LEGAL_BASIS)]})
    settings = Settings(_env_file=None)
    assert settings.copy_source_text is False
    result = pipeline.from_file(path.name, path.read_bytes(), settings, llm=lambda doc, _: spec)
    finish = [q["field"]["techName"] for q in result.form["tabs"][-1]["questions"]]
    assert "podstawa_prawna" not in finish and "pouczenie" not in finish
    assert result.document is not None  # ?details=true still shows the source blocks


def test_schema_endpoint_matches_what_compile_accepts(client):
    """UI contract: the editor validates against this schema and sends the spec to /compile. The stricter
    model schema (max 40 roles, no FIELD_LABEL/HEADING) would reject saved specs such as wyniki/02, 07, 09."""
    import json
    from pathlib import Path

    from autoformularz.spec import FormSpec, model_schema

    schema = client.get("/api/v1/spec/schema").json()
    assert schema == FormSpec.model_json_schema() and schema != model_schema()
    for path in sorted((Path(__file__).resolve().parents[2] / "wyniki").glob("*.spec.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        r = client.post("/api/v1/forms/compile", headers=auth(), json=spec)
        assert r.status_code == 200, path.name


def wait_for(client, job_id: str) -> dict:
    for _ in range(200):
        r = client.get(f"/api/v1/jobs/{job_id}", headers=auth())
        assert r.status_code == 200, r.text
        if (view := r.json())["status"] != "running":
            return view
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_job_reports_steps_and_result(client):
    path = material("5. */*nadpłaty podatku.docx")
    r = client.post(
        "/api/v1/jobs?details=true", headers=auth(), files={"file": (path.name, path.read_bytes())}
    )
    assert r.status_code == 202, r.text
    view = wait_for(client, r.json()["id"])
    assert view["status"] == "done", view
    assert set(view["result"]["form"]) == {"title", "tabs", "flow"}
    stages = [s["text"] for s in view["steps"] if s["kind"] == "stage"]
    assert stages[0] == "Sprawdzanie pliku" and stages[-1] == "Sprawdzanie reguł technicznych"
    assert view["steps"][-1]["text"].startswith("Błędy: 0")


def test_job_rejects_a_bad_file_right_away(client):
    r = client.post("/api/v1/jobs", headers=auth(), files={"file": ("a.exe", b"MZ")})
    assert r.status_code >= 400 and r.status_code < 500 and "error" in r.json()


def test_job_needs_jwt_and_unknown_id_is_404(client):
    assert client.get("/api/v1/jobs/x").status_code == 401
    assert client.get("/api/v1/jobs/nope", headers=auth()).json()["error"]["code"] == "JOB_NOT_FOUND"
    assert client.delete("/api/v1/jobs/nope", headers=auth()).status_code == 404


def test_cancelled_job_stops_at_next_step(client, monkeypatch):
    from autoformularz import jobs, progress

    gate = threading.Event()

    def slow(name, data, s):
        progress.stage("start")
        gate.wait(5)
        progress.stage("after cancel")
        raise AssertionError("not stopped")

    monkeypatch.setattr(pipeline, "from_file", slow)
    path = material("5. */*nadpłaty podatku.docx")
    job_id = client.post(
        "/api/v1/jobs", headers=auth(), files={"file": (path.name, path.read_bytes())}
    ).json()["id"]
    assert client.delete(f"/api/v1/jobs/{job_id}", headers=auth()).status_code == 204
    gate.set()
    view = wait_for(client, job_id)
    assert view["status"] == "cancelled"
    assert "after cancel" not in [s["text"] for s in view["steps"]]
    assert jobs.get(job_id) is not None


def test_file_name_limit_is_250_characters_end_to_end(client):
    """Task: the name may have at most 250 characters (counted as characters, so Polish letters count once)."""
    path = material("5. */*nadpłaty podatku.docx")
    data = path.read_bytes()
    ok = "ś" * 245 + ".docx"  # 250 characters, 495 bytes in UTF-8
    r = client.post("/api/v1/forms", headers=auth(), files={"file": (ok, data)})
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/forms", headers=auth(), files={"file": ("ś" + ok, data)})
    assert r.status_code == 422 and r.json()["error"]["code"] == "FILENAME_TOO_LONG"
