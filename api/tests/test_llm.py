"""LLM transport (Ollama / Eden AI dev provider). httpx.post is monkeypatched: no network."""

import copy
import json

import httpx
import pytest

from autoformularz import llm
from autoformularz.config import Settings
from autoformularz.document import Document, build
from autoformularz.llm import LLMError, generate_spec, llm_status
from autoformularz.spec import FormSpec

KEY = "sk-test-secret-123"
PNG = b"\x89PNG\r\n\x1a\nfake"


def doc(text: str = "", images: list[bytes] | None = None) -> Document:
    return build([(text, None)], images=images or [])


def eden(**kw) -> Settings:
    base = {
        "llm_provider": "eden",
        "eden_api_key": KEY,
        "eden_model": "deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct",
    }
    return Settings(_env_file=None, **(base | kw))


def spec_json(spec: FormSpec) -> str:
    return spec.model_dump_json()


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


class Recorder:
    """Fake httpx.post returning queued responses and remembering the calls."""

    def __init__(self, *responses: httpx.Response):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url, *, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": copy.deepcopy(json), "headers": headers or {}})
        return self.responses.pop(0)


@pytest.fixture
def post(monkeypatch):
    def install(*responses: httpx.Response) -> Recorder:
        rec = Recorder(*responses)
        monkeypatch.setattr(llm.httpx, "post", rec)
        return rec

    return install


def test_default_provider_is_ollama(monkeypatch):
    monkeypatch.delenv("AUTOFORMULARZ_LLM_PROVIDER", raising=False)
    s = Settings(_env_file=None)
    assert s.llm_provider == "ollama"
    assert s.eden_model is None


def test_eden_key_read_from_unprefixed_env(monkeypatch):
    monkeypatch.setenv("EDENAI_API_KEY", KEY)
    assert Settings(_env_file=None).eden_api_key.get_secret_value() == KEY


def test_eden_request_shape(post, nadplata_spec):
    rec = post(completion(spec_json(nadplata_spec)))
    out = generate_spec(doc(text="Wniosek", images=[PNG]), eden())
    assert out == nadplata_spec
    call = rec.calls[0]
    assert call["url"].endswith("/chat/completions")
    assert call["headers"]["Authorization"] == f"Bearer {KEY}"
    body = call["json"]
    assert body["model"] == "deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct"
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == FormSpec.model_json_schema()
    parts = body["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": parts[0]["text"]} and "Wniosek" in parts[0]["text"]
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_eden_text_only_keeps_string_content(post, nadplata_spec):
    rec = post(completion(spec_json(nadplata_spec)))
    generate_spec(doc(text="Wniosek"), eden())
    assert isinstance(rec.calls[0]["json"]["messages"][1]["content"], str)


def test_fenced_json_is_parsed(post, nadplata_spec):
    post(completion(f"```json\n{spec_json(nadplata_spec)}\n```"))
    assert generate_spec(doc(text="x"), eden()) == nadplata_spec


def test_json_schema_rejected_falls_back_to_json_object(post, nadplata_spec):
    rejected = httpx.Response(400, json={"error": "response_format json_schema is not supported"})
    rec = post(rejected, completion(spec_json(nadplata_spec)))
    assert generate_spec(doc(text="x"), eden()) == nadplata_spec
    assert [c["json"]["response_format"]["type"] for c in rec.calls] == ["json_schema", "json_object"]


def test_bad_output_retried_once_then_fails(post):
    rec = post(completion("to nie jest JSON"), completion('{"title": 1}'))
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), eden())
    assert e.value.code == "LLM_BAD_OUTPUT"
    assert len(rec.calls) == 2
    fix = rec.calls[1]["json"]["messages"][-1]
    assert fix["role"] == "user" and "Błąd" in fix["content"]


def test_bad_output_recovers_on_retry(post, nadplata_spec):
    post(completion("{"), completion(spec_json(nadplata_spec)))
    assert generate_spec(doc(text="x"), eden()) == nadplata_spec


def test_ollama_retry_and_payload(post, nadplata_spec):
    ok = httpx.Response(200, json={"message": {"content": spec_json(nadplata_spec)}})
    bad = httpx.Response(200, json={"message": {"content": "{}"}})
    rec = post(bad, ok)
    s = Settings(_env_file=None, llm_provider="ollama")
    assert generate_spec(doc(text="x", images=[PNG]), s) == nadplata_spec
    body = rec.calls[0]["json"]
    assert rec.calls[0]["url"].endswith("/api/chat")
    assert body["format"] == FormSpec.model_json_schema()
    assert body["messages"][1]["images"]
    assert "Authorization" not in rec.calls[0]["headers"]


@pytest.mark.parametrize("kw", [{"eden_api_key": None}, {"eden_api_key": ""}, {"eden_model": None}])
def test_eden_missing_config(post, kw):
    rec = post()
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), eden(**kw))
    assert e.value.code == "LLM_MISCONFIGURED" and e.value.status == 500
    assert rec.calls == []


def test_key_never_in_errors(post, monkeypatch):
    errors: list[LLMError] = []
    echo = httpx.Response(401, text=f"invalid token Bearer {KEY}")
    for responses in ([echo], [completion("nope"), completion("nope")]):
        post(*responses)
        with pytest.raises(LLMError) as e:
            generate_spec(doc(text="x"), eden())
        errors.append(e.value)

    def down(*_, **__):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(llm.httpx, "post", down)
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), eden())
    errors.append(e.value)
    assert [x.code for x in errors] == ["LLM_ERROR", "LLM_BAD_OUTPUT", "LLM_UNAVAILABLE"]
    for err in errors:
        assert KEY not in err.message and KEY not in str(err)


def test_status_eden_does_not_call_ollama(monkeypatch):
    monkeypatch.setattr(llm.httpx, "get", lambda *a, **k: pytest.fail("Ollama called"))
    status = llm_status(eden())
    assert status == {"provider": "eden", "model": eden().eden_model, "configured": True}
    assert llm_status(eden(eden_api_key=None))["configured"] is False
    assert KEY not in json.dumps(status)


def test_status_ollama_has_provider(monkeypatch):
    monkeypatch.setattr(llm.httpx, "get", lambda *a, **k: httpx.Response(200, json={"models": []}))
    assert llm_status(Settings(_env_file=None))["provider"] == "ollama"


def test_dev_provider_warning(caplog):
    llm.warn_if_dev_provider(eden())
    assert "nie do oddania" in caplog.text
    caplog.clear()
    llm.warn_if_dev_provider(Settings(_env_file=None, llm_provider="ollama"))
    assert caplog.text == ""


def test_eden_usage_is_recorded(post, nadplata_spec, monkeypatch):
    monkeypatch.setattr(llm, "EDEN_USAGE", [])
    body = {
        "choices": [{"message": {"role": "assistant", "content": spec_json(nadplata_spec)}}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 300},
        "cost": 0.00036,
    }
    post(httpx.Response(200, json=body))
    generate_spec(doc(text="Wniosek"), eden())
    assert llm.EDEN_USAGE == [{"promptTokens": 1200, "completionTokens": 300, "cost": 0.00036}]


def test_answer_length_is_capped(post, nadplata_spec):
    rec = post(completion(spec_json(nadplata_spec)))
    generate_spec(doc(text="x"), eden(llm_max_tokens=1234))
    assert rec.calls[0]["json"]["max_tokens"] == 1234
    rec = post(httpx.Response(200, json={"message": {"content": spec_json(nadplata_spec)}}))
    generate_spec(doc(text="x"), Settings(_env_file=None, llm_provider="ollama", llm_max_tokens=99))
    assert rec.calls[0]["json"]["options"]["num_predict"] == 99


def test_eden_truncated_answer_fails_without_retry(post, monkeypatch):
    """A repetition loop hits max_tokens: no second call (it would loop again), but the cost is recorded."""
    monkeypatch.setattr(llm, "EDEN_USAGE", [])
    looping = {
        "choices": [{"message": {"content": '{"title": "x", "pages": [{"ti'}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 4000, "completion_tokens": 8000},
        "cost": 0.0054,
    }
    rec = post(httpx.Response(200, json=looping))
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), eden())
    assert e.value.code == "LLM_TRUNCATED" and len(rec.calls) == 1
    assert llm.EDEN_USAGE[0]["cost"] == 0.0054


def test_ollama_truncated_answer_fails_without_retry(post):
    rec = post(httpx.Response(200, json={"message": {"content": "{"}, "done_reason": "length"}))
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), Settings(_env_file=None, llm_provider="ollama"))
    assert e.value.code == "LLM_TRUNCATED" and len(rec.calls) == 1
