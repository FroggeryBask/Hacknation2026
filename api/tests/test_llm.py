"""LLM transport (Ollama / Eden AI dev provider). httpx.post is monkeypatched: no network."""

import contextlib
import copy
import json

import httpx
import pytest

from autoformularz import llm, progress
from autoformularz.config import Settings
from autoformularz.document import Document, build
from autoformularz.llm import LLMError, generate_spec, llm_status
from autoformularz.spec import FormSpec, model_schema

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

    @contextlib.contextmanager
    def stream(self, method, url, *, json=None, headers=None, timeout=None):
        """httpx.stream (Ollama): the same queued responses, read line by line."""
        yield self(url, json=json, headers=headers, timeout=timeout)


@pytest.fixture
def post(monkeypatch):
    def install(*responses: httpx.Response) -> Recorder:
        rec = Recorder(*responses)
        monkeypatch.setattr(llm.httpx, "post", rec)
        monkeypatch.setattr(llm.httpx, "stream", rec.stream)
        return rec

    return install


def test_default_provider_is_eden(monkeypatch):
    """Team decision 2026-11-21: Eden AI by default (also delivered), Ollama as the offline option."""
    for name in ("AUTOFORMULARZ_LLM_PROVIDER", "AUTOFORMULARZ_EDEN_MODEL", "AUTOFORMULARZ_LLM_MAX_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)
    assert s.llm_provider == "eden"
    assert s.eden_model == "deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct"  # open-weight, the team's model
    assert s.llm_max_tokens == 12000


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
    assert body["response_format"]["json_schema"]["schema"] == model_schema()
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
    assert [c["json"]["response_format"]["type"] for c in rec.calls] == [
        "json_schema",
        "json_object",
    ]


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
    assert body["format"] == model_schema()
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

    monkeypatch.setattr(llm.httpx, "stream", down)
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), eden())
    errors.append(e.value)
    assert [x.code for x in errors] == [
        "LLM_ERROR",
        "LLM_BAD_OUTPUT",
        "LLM_UNAVAILABLE",
    ]
    for err in errors:
        assert KEY not in err.message and KEY not in str(err)


def test_status_eden_does_not_call_ollama(monkeypatch):
    monkeypatch.setattr(llm.httpx, "get", lambda *a, **k: pytest.fail("Ollama called"))
    status = llm_status(eden())
    assert status == {
        "provider": "eden",
        "model": eden().eden_model,
        "configured": True,
        "usage": llm.eden_usage_total(),
    }
    assert llm_status(eden(eden_api_key=None))["configured"] is False
    assert KEY not in json.dumps(status)


def test_status_ollama_has_provider(monkeypatch):
    monkeypatch.setattr(llm.httpx, "get", lambda *a, **k: httpx.Response(200, json={"models": []}))
    assert llm_status(Settings(_env_file=None, llm_provider="ollama"))["provider"] == "ollama"


def test_dev_provider_warning(caplog):
    llm.warn_if_dev_provider(eden())
    assert "Eden AI" in caplog.text and "kosztuje" in caplog.text
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
    generate_spec(
        doc(text="x"),
        Settings(_env_file=None, llm_provider="ollama", llm_max_tokens=99),
    )
    assert rec.calls[0]["json"]["options"]["num_predict"] == 99
    assert rec.calls[0]["json"]["keep_alive"] == "30m"  # the model stays loaded for the next form


def test_eden_truncated_answer_fails_without_retry(post, monkeypatch):
    """A repetition loop hits max_tokens: no second call (it would loop again), but the cost is recorded."""
    monkeypatch.setattr(llm, "EDEN_USAGE", [])
    looping = {
        "choices": [
            {
                "message": {"content": '{"title": "x", "pages": [{"ti'},
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 4000, "completion_tokens": 8000},
        "cost": 0.0054,
    }
    rec = post(httpx.Response(200, json=looping))
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), eden())
    assert e.value.code == "LLM_TRUNCATED" and len(rec.calls) == 1
    assert llm.EDEN_USAGE[0]["cost"] == 0.0054
    assert e.value.partial == '{"title": "x", "pages": [{"ti'


def test_ollama_truncated_answer_fails_without_retry(post):
    rec = post(httpx.Response(200, json={"message": {"content": "{"}, "done_reason": "length"}))
    with pytest.raises(LLMError) as e:
        generate_spec(doc(text="x"), Settings(_env_file=None, llm_provider="ollama"))
    assert e.value.code == "LLM_TRUNCATED" and len(rec.calls) == 1 and e.value.partial == "{"


def test_health_shows_eden_cost_since_start(monkeypatch):
    monkeypatch.setattr(
        llm,
        "EDEN_USAGE",
        [{"promptTokens": 10, "completionTokens": 5, "cost": 0.0021}, {"cost": 0.003}],
    )
    assert llm_status(eden())["usage"] == {"calls": 2, "costUsd": 0.0051}


def paid(content: str, **usage) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": usage})


@pytest.fixture
def hooks(monkeypatch):
    """Fresh hook lists per test (module-level registries)."""
    monkeypatch.setattr(llm, "before_eden_call", [])
    monkeypatch.setattr(llm, "usage_hooks", [])
    return llm


def test_usage_reported_for_every_paid_response(post, hooks, nadplata_spec):
    seen: list[llm.Usage] = []
    hooks.usage_hooks.append(seen.append)
    post(
        paid("{", prompt_tokens=100, completion_tokens=5),
        paid(
            spec_json(nadplata_spec),
            prompt_tokens=120,
            completion_tokens=900,
            total_tokens=1020,
            cost=0.0042,
        ),
    )
    assert generate_spec(doc(text="x"), eden()) == nadplata_spec
    assert [(u.prompt_tokens, u.completion_tokens) for u in seen] == [
        (100, 5),
        (120, 900),
    ]  # retry is paid too
    assert seen[1].total_tokens == 1020 and seen[1].cost == 0.0042 and seen[1].model == eden().eden_model


def test_guard_blocks_call_before_anything_is_sent(post, hooks):
    def over_budget(model: str) -> None:
        raise llm.LLMError("LLM_BUDGET_EXCEEDED", "Limit budżetu Eden AI wyczerpany.", 429)

    hooks.before_eden_call.append(over_budget)
    rec = post()
    with pytest.raises(llm.LLMError) as e:
        generate_spec(doc(text="x"), eden())
    assert e.value.code == "LLM_BUDGET_EXCEEDED" and rec.calls == []


def test_failing_usage_hook_keeps_the_answer(post, hooks, nadplata_spec):
    def broken(_: llm.Usage) -> None:
        raise RuntimeError("tracker down")

    hooks.usage_hooks.append(broken)
    post(paid(spec_json(nadplata_spec), prompt_tokens=1))
    assert generate_spec(doc(text="x"), eden()) == nadplata_spec


def test_ollama_does_not_report_usage(post, hooks, nadplata_spec):
    seen: list = []
    hooks.usage_hooks.append(seen.append)
    hooks.before_eden_call.append(lambda m: pytest.fail("guard is for Eden only"))
    post(httpx.Response(200, json={"message": {"content": spec_json(nadplata_spec)}}))
    generate_spec(doc(text="x"), Settings(_env_file=None, llm_provider="ollama"))
    assert seen == []


# ---------------------------------------------------------------- a cut or looping answer


def looping_answer(times: int = 3) -> str:
    """Form 9 shape: the whole form on one page, then the same sections again, cut mid-field."""
    sections = [
        {
            "title": "Dane wnioskodawcy",
            "fields": [{"label": "Nazwa klubu", "kind": "TEXT", "required": True}],
        },
        {
            "title": "Zgody",
            "fields": [{"label": "Zgoda", "kind": "SINGLE_CHOICE", "required": True, "options": ["Tak"]}],
        },
    ]
    body = ", ".join(json.dumps(s, ensure_ascii=False) for s in sections * times)
    head = '{"title": "Wniosek o stypendium", "authority_name": "Prezydent Miasta", "block_roles": [], '
    return head + '"pages": [{"title": "Wniosek", "sections": [' + body + ', {"title": "Dane wnioskod'


def test_salvage_keeps_the_form_up_to_the_first_repeat():
    spec = llm.salvage(looping_answer())
    assert [s.title for s in spec.pages[0].sections] == ["Dane wnioskodawcy", "Zgody"]
    assert spec.title == "Wniosek o stypendium"


@pytest.mark.parametrize("partial", ["", "{", '{"title": "Wniosek", "pages": [{"title": "A", "sec'])
def test_salvage_gives_up_without_a_complete_section(partial):
    assert llm.salvage(partial) is None


def test_eden_cut_answer_is_salvaged_with_a_note(post, monkeypatch):
    monkeypatch.setattr(llm, "EDEN_USAGE", [])
    body = {"choices": [{"message": {"content": looping_answer()}, "finish_reason": "length"}]}
    rec = post(httpx.Response(200, json=body))
    d = doc(text="x")
    spec = generate_spec(d, eden())
    assert len(spec.pages[0].sections) == 2 and len(rec.calls) == 1  # no second paid call
    assert any("powtarzał sekcje" in n for n in d.notes)


def test_ollama_stops_streaming_when_sections_repeat(post, monkeypatch):
    """Ollama streams the answer: generation stops at the first repeated section, not at the limit."""
    monkeypatch.setattr(llm, "REPEAT_CHECK_CHARS", 50)
    text = looping_answer(times=40)
    pieces = [text[i : i + 40] for i in range(0, len(text), 40)]
    sent: list[str] = []

    def ollama():  # what the model streams; counts how much the client asked for
        for p in pieces:
            sent.append(p)
            yield (json.dumps({"message": {"content": p}, "done": False}) + "\n").encode()

    post(httpx.Response(200, content=ollama()))
    d = doc(text="x")
    spec = generate_spec(d, Settings(_env_file=None, llm_provider="ollama"))
    assert [s.title for s in spec.pages[0].sections] == ["Dane wnioskodawcy", "Zgody"]
    assert len(sent) < len(pieces) // 5  # stopped soon after the first repeat, not at the end
    assert any("powtarzał sekcje" in n for n in d.notes)


def test_ollama_streamed_answer_is_joined(post, nadplata_spec):
    text = spec_json(nadplata_spec)
    lines = [
        json.dumps({"message": {"content": text[i : i + 30]}, "done": False}) for i in range(0, len(text), 30)
    ]
    lines.append(json.dumps({"message": {"content": ""}, "done": True, "done_reason": "stop"}))
    post(httpx.Response(200, content="\n".join(lines).encode()))
    assert generate_spec(doc(text="x"), Settings(_env_file=None, llm_provider="ollama")) == nadplata_spec


def test_one_repeated_section_is_not_a_loop():
    """Form 9's good answer: the same "Opinia" section on the athlete's and the coach's page."""
    opinion = {
        "title": "Opinia klubu",
        "fields": [{"label": "Opinia", "kind": "LONG_TEXT", "required": True}],
    }
    pages = [
        {"title": "Sportowiec", "sections": [{"title": "Dane", "fields": []}, opinion]},
        {
            "title": "Trener",
            "sections": [{"title": "Dane trenera", "fields": []}, opinion, {"title": "Uwagi", "fields": []}],
        },
    ]
    assert llm.first_repeat(pages) is None
    pages[1]["sections"].append({"title": "Uwagi", "fields": []})  # two in a row: the model began again
    assert llm.first_repeat(pages) is None  # "Uwagi" after "Uwagi" alone is still one repeat
    pages[1]["sections"].append({"title": "Dane", "fields": []})
    assert llm.first_repeat(pages) == (1, 3)


# ---------------------------------------------------------------- streamed answers and progress


def sse(content: str, size: int = 7, **usage) -> httpx.Response:
    """An Eden answer streamed as Server-Sent Events, `size` characters per chunk, usage in the last one."""
    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": content[i : i + size]}}]})
        for i in range(0, len(content), size)
    ]
    lines.append("data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
    if usage:
        lines.append("data: " + json.dumps({"choices": [], "usage": usage, "cost": usage.get("cost")}))
    lines.append("data: [DONE]")
    return httpx.Response(
        200, text="\n\n".join(lines) + "\n\n", headers={"content-type": "text/event-stream"}
    )


def test_eden_streams_and_records_usage(post, nadplata_spec, monkeypatch):
    monkeypatch.setattr(llm, "EDEN_USAGE", [])
    rec = post(sse(spec_json(nadplata_spec), prompt_tokens=50, completion_tokens=20, cost=0.001))
    assert generate_spec(doc(text="x"), eden()) == nadplata_spec
    sent = rec.calls[0]["json"]
    assert sent["stream"] is True and sent["stream_options"] == {"include_usage": True}
    assert llm.EDEN_USAGE == [{"promptTokens": 50, "completionTokens": 20, "cost": 0.001}]


def test_progress_lists_names_as_the_model_writes(post, nadplata_spec):
    steps: list[tuple[str, str]] = []
    post(sse(spec_json(nadplata_spec), size=3))
    with progress.reporting(lambda kind, text: steps.append((kind, text))):
        generate_spec(doc(text="x"), eden())
    items = [t for k, t in steps if k == "item"]
    assert ("stage", "Model opisuje formularz") in steps
    assert items[0] == f"Tytuł: {nadplata_spec.title}"
    page, section = nadplata_spec.pages[0], nadplata_spec.pages[0].sections[0]
    assert items[1:3] == [f"Strona: {page.title}", f"Sekcja: {section.title}"]
    assert f"Pole: {section.fields[0].label}" in items
    fields = sum(len(s.fields) for p in nadplata_spec.pages for s in p.sections)
    assert sum(t.startswith("Pole: ") for t in items) == fields


def test_outline_reads_escapes_and_nested_titles():
    steps: list[str] = []
    text = json.dumps(
        {
            "title": 'Wniosek "A"',
            "applicant": {"title": "nie"},
            "pages": [{"title": "S1", "sections": [{"title": "Sek", "fields": [{"label": "Łódź\\x"}]}]}],
        },
        ensure_ascii=True,
    )
    with progress.reporting(lambda kind, t: steps.append(t)):
        outline = llm.Outline()
        for ch in text:
            outline.feed(ch)
    assert steps == ['Tytuł: Wniosek "A"', "Strona: S1", "Sekcja: Sek", "Pole: Łódź\\x"]


def test_eden_looping_stream_stops_early(post, nadplata_spec):
    """The same check as for Ollama: a stream that starts writing its sections again is cut (fewer tokens)."""
    page = nadplata_spec.pages[0].model_dump(mode="json")
    twice = {**page, "sections": page["sections"] * 2 + page["sections"] * 50}
    head = nadplata_spec.model_dump(mode="json") | {"pages": [twice]}
    rec = post(sse(json.dumps(head, ensure_ascii=False), size=50))
    spec = generate_spec(doc(text="x"), eden())
    assert len(rec.calls) == 1 and spec.pages[0].sections == nadplata_spec.pages[0].sections


def test_cancel_stops_the_stream(post, nadplata_spec):
    class Stop(Exception):
        pass

    def sink(kind: str, _: str) -> None:
        if kind == "item":
            raise Stop

    post(sse(spec_json(nadplata_spec)))
    with progress.reporting(sink), pytest.raises(Stop):
        generate_spec(doc(text="x"), eden())
