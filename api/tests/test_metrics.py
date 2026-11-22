"""Metrics of a conversion: what was sent, how long each step and model call took, tokens, cost and the
shape of the answer. They compare runs; they never contain the file name or the form text."""

import io
import json
import logging

import httpx
import pytest
from conftest import material
from PIL import Image
from test_llm import KEY, Recorder, completion, doc, eden, spec_json

from autoformularz import llm, metrics, pipeline, results
from autoformularz.config import Settings
from autoformularz.llm import generate_spec
from autoformularz.spec import FormSpec


@pytest.fixture
def post(monkeypatch):
    """Fake httpx (no network), as in test_llm."""

    def install(*responses: httpx.Response) -> Recorder:
        rec = Recorder(*responses)
        monkeypatch.setattr(llm.httpx, "post", rec)
        monkeypatch.setattr(llm.httpx, "stream", rec.stream)
        return rec

    return install


def jpeg(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="JPEG")
    return buf.getvalue()


def test_answer_shape_counts_default_values():
    call = metrics.ModelCall(provider="eden", model="m")
    metrics.answer_shape(call, '{\n  "a": null, "b": [], "c": [ ], "d": false, "e": "null", "f": [1]\n}')
    assert (call.answer_nulls, call.answer_empty_lists, call.answer_false) == (1, 2, 1)
    assert call.answer_whitespace == 4 and call.answer_chars > 0


def test_image_tokens_estimate():
    assert metrics.image_tokens([jpeg(1280, 905)]) == (1280 // 28) * (905 // 28)


def test_eden_call_is_measured(post, nadplata_spec):
    body = json.loads(completion(spec_json(nadplata_spec)).content)
    body["usage"] = {"prompt_tokens": 1200, "completion_tokens": 340}
    body["cost"] = 0.0004
    post(httpx.Response(200, json=body))
    with metrics.collecting() as m:
        generate_spec(doc(text="Wniosek", images=[jpeg(1280, 905)]), eden())
    (call,) = m.calls
    assert call.provider == "eden" and call.prompt_tokens == 1200 and call.completion_tokens == 340
    assert call.cost_usd == 0.0004 and call.images == 1 and call.image_tokens_est > 0
    assert call.prompt_chars > 100 and call.answer_chars == len(spec_json(nadplata_spec))
    d = m.as_dict()
    assert d["completionTokens"] == 340 and d["costUsd"] == 0.0004 and d["modelCalls"] == 1
    assert KEY not in json.dumps(d)


def test_ollama_call_is_measured(post, nadplata_spec):
    final = {
        "message": {"content": spec_json(nadplata_spec)},
        "done": True,
        "prompt_eval_count": 900,
        "eval_count": 410,
        "load_duration": 2_000_000_000,
        "prompt_eval_duration": 3_500_000_000,
        "eval_duration": 40_000_000_000,
    }
    post(httpx.Response(200, json=final))
    with metrics.collecting() as m:
        generate_spec(doc(text="x"), Settings(_env_file=None, llm_provider="ollama"))
    (call,) = m.calls
    assert (call.prompt_tokens, call.completion_tokens) == (900, 410)
    assert call.ollama == {"loadS": 2.0, "prompt_evalS": 3.5, "evalS": 40.0}


def test_conversion_metrics_and_log_line(nadplata_spec, caplog):
    path = material("5. */*nadpłaty podatku.docx")
    with caplog.at_level(logging.INFO, logger="autoformularz.metrics"):
        result = pipeline.from_file(
            path.name, path.read_bytes(), Settings(_env_file=None), llm=lambda d, s: nadplata_spec
        )
    d = result.metrics.as_dict()
    assert (
        d["sourceFormat"] == "docx" and len(d["fileSha"]) == 12 and d["fileBytes"] == len(path.read_bytes())
    )
    assert set(d["steps"]) >= {"check", "extract", "presort", "model", "compile"}
    assert d["blocks"] > d["blocksToModel"] > 0 and d["presort"]  # presort took some blocks
    assert d["fields"] > 0 and d["lintErrors"] == 0
    line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("metrics "))
    assert path.name not in line and "nadpłaty" not in line  # no file name, no form text
    assert json.loads(line.removeprefix("metrics "))["fileSha"] == d["fileSha"]


def test_failed_conversion_is_logged_with_its_error(caplog):
    from autoformularz.llm import LLMError

    def broken(*_):
        raise LLMError("LLM_TRUNCATED", "cut")

    path = material("5. */*nadpłaty podatku.docx")
    with caplog.at_level(logging.INFO, logger="autoformularz.metrics"), pytest.raises(LLMError):
        pipeline.from_file(path.name, path.read_bytes(), Settings(_env_file=None), llm=broken)
    line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("metrics "))
    assert json.loads(line.removeprefix("metrics "))["error"] == "LLM_TRUNCATED"


def test_details_response_has_metrics():
    from autoformularz.main import body

    r = pipeline.from_spec(FormSpec(title="Wniosek", authority_name="U", pages=[]))
    assert body(r, details=True)["metrics"] is None  # /compile: no model call


def test_generator_appends_metrics_and_raw_answer(tmp_path, monkeypatch, nadplata_spec):
    monkeypatch.setattr(results, "OUT", tmp_path)

    def fake_model(document, settings):  # records a call like the real one
        call = metrics.start_call("eden", "m", [{"role": "user", "content": "x"}], [])
        metrics.answer_shape(call, '{"a": null}')
        return nadplata_spec

    monkeypatch.setattr(results.llm, "generate_spec", fake_model)
    results.run(2, Settings(_env_file=None), compile_only=False, force=True)
    results.run(2, Settings(_env_file=None), compile_only=False, force=True)
    rows = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2 and json.loads(rows[0])["form"] == 2
    first = json.loads(rows[0])
    assert first["settings"]["imageSide"] == 1280 and first["calls"][0]["answerNulls"] == 1
    assert (tmp_path / "02.raw.txt").read_text(encoding="utf-8") == '{"a": null}'
    table = results.compare_metrics(tmp_path / "metrics.jsonl")
    assert len(table.splitlines()) == 3  # header + 2 runs


def test_compile_only_writes_no_metrics(tmp_path, monkeypatch, nadplata_spec):
    monkeypatch.setattr(results, "OUT", tmp_path)
    (tmp_path / "02.spec.json").write_text(nadplata_spec.model_dump_json(), encoding="utf-8")
    results.run(2, Settings(_env_file=None), compile_only=True, force=False)
    assert not (tmp_path / "metrics.jsonl").exists()  # reports stay byte-identical, no timings in them
