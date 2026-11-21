"""Result generator (wyniki/): tested without a model, from a saved FormSpec."""

import json

import pytest
from conftest import material

from autoformularz import results
from autoformularz.config import Settings


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "OUT", tmp_path)
    return tmp_path


def test_best_source_is_docx():
    material("2. */*.docx")
    assert results.source_file(2).suffix == ".docx"
    assert results.source_file(7).suffix.lower() in (".doc", ".pdf")  # form 7 has no .docx file


def test_compile_only_never_calls_the_model(out, monkeypatch):
    monkeypatch.setattr("autoformularz.llm.generate_spec", lambda *a: pytest.fail("model called"))
    line = results.run(2, Settings(_env_file=None), compile_only=True, force=False)
    assert "pominięty" in line and not list(out.iterdir())


def test_saved_spec_gives_identical_files(out, nadplata_spec):
    material("2. */*.docx")
    (out / "02.spec.json").write_text(nadplata_spec.model_dump_json(), encoding="utf-8")
    settings = Settings(_env_file=None)
    results.run(2, settings, compile_only=True, force=False)
    first = {p.name: p.read_bytes() for p in out.iterdir()}
    results.run(2, settings, compile_only=True, force=False)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == first  # deterministic
    report = json.loads((out / "02.report.json").read_text(encoding="utf-8"))
    assert report["model"] == "zapisany FormSpec" and report["errors"] == 0
    assert report["source"].endswith(".docx") and "coverage" in report
    assert json.loads((out / "02.json").read_text(encoding="utf-8"))["tabs"]
