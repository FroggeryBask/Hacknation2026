"""LLM step: extracted form content -> FormSpec.

Default: an open-weight model on Eden AI (organizer-provided, OpenAI Chat Completions, team decision 2026-11-21).
AUTOFORMULARZ_LLM_PROVIDER=ollama runs the model locally instead (offline option), with the FormSpec JSON Schema
as `format`, so decoding is constrained to valid JSON of the right shape."""

import base64
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from pydantic import ValidationError

from autoformularz import metrics, progress
from autoformularz.check import TEMPLATE_TITLE
from autoformularz.config import Settings
from autoformularz.document import FILL_LINE, Document
from autoformularz.spec import FormSpec, model_schema

SYSTEM_PROMPT = """\
Jesteś analitykiem, który zamienia papierowe formularze urzędowe na opis formularza elektronicznego (e-usługi).
Zwracasz WYŁĄCZNIE JSON zgodny ze schematem FormSpec.

Część standardowa jest dodawana automatycznie. NIE umieszczaj jej w `pages`:
- dane urzędu/organu (podajesz tylko `authority_name` i `authority_kind`),
- dane wnioskodawcy: imię, nazwisko, PESEL, adres zamieszkania, dane pełnomocnika, dane firmy (NIP, REGON, KRS,
  nazwa, adres siedziby), pełnomocnictwo i opłata skarbowa za pełnomocnictwo (opisujesz je tylko przez `applicant`),
- dane do kontaktu (telefon, e-mail), zgoda na przetwarzanie danych osobowych (RODO), podgląd i podpis.
Pomiń elementy, które mają sens tylko na papierze: „miejscowość i data”, „podpis wnioskodawcy”, pieczątki,
adnotacje urzędu („wypełnia urząd”, „data wpływu”), pouczenia o sposobie wypełniania drukiem.
Bloki z tymi danymi (np. „Imię i nazwisko”, „Nazwa”, „NIP”, „Miejscowość”, „Ulica”, „Nr domu”, „Nr lokalu”,
„Kod pocztowy”, „Numer telefonu”, „Adres e-mail”, „Dane pełnomocnika”, „Instrukcja wypełnienia”, „Podpis”)
NIE są polami w `pages`: dane wnioskodawcy i pełnomocnika opisuje tylko `applicant`, a instrukcje i podpis
dostają rolę w `block_roles` (INSTRUCTION, SKIP). Wyjątek: adres lub dane, które dotyczą przedmiotu sprawy
(np. adres nieruchomości, miejsce utrzymywania psa), są polami w `pages`.

`pages` to strony dotyczące przedmiotu sprawy. Zasady:
- Grupuj pola tematycznie w sekcje. Strona ma krótki tytuł opisujący temat (np. „Informacje o budynku”).
- Każdą stronę, sekcję i pole wpisz tylko raz. Nie powtarzaj stron ani sekcji. Gdy opiszesz wszystkie pola
  formularza, zakończ JSON. Nie każdy blok musi trafić do `pages`: pouczenia, objaśnienia, podstawa prawna i
  klauzula RODO idą tylko do `block_roles`, nigdy jako sekcje ani pola INFO.
- Zachowaj zakres danych z formularza. Nie wymyślaj pól, których nie ma w dokumencie.
- Pole to miejsce do wpisania lub zaznaczenia na druku (kropki, linia, kratka, pusta rubryka) wraz z jego
  etykietą: każda część tej samej linii z własnym miejscem do wpisania to osobne pole, w kolejności z druku.
  Tytuł wniosku i zdanie prośby („Wnoszę o…”, „Proszę o…”) nie są polami. Nie dodawaj pola na to, o co
  wnioskodawca prosi urząd (np. numer lub decyzję, którą urząd dopiero wyda), ani pól, o które druk nie pyta.
- Typ pola: TEXT krótki tekst; LONG_TEXT opis lub uzasadnienie; NUMBER tylko liczby (kwoty, liczby osób);
  DATE daty; SINGLE_CHOICE jedna z kilku opcji (kratki do zaznaczenia jednej odpowiedzi); MULTI_CHOICE wiele
  opcji; SELECT jedna z wielu (>5) opcji; FILE załączniki wymienione w formularzu; INFO stała informacja.
- Etykiety pisz prostym językiem, bez form zależnych od płci, bez dwukropków i wielokropków.
- `required` wpisz w KAŻDYM polu: false dla danych opcjonalnych (np. „jeśli posiada”, „nr lokalu”, „uwagi”) i dla wszystkiego,
  co druk opisuje jako nieobowiązkowe lub do wypełnienia tylko w pewnym przypadku („pola nieobowiązkowe”,
  „wypełnić tylko w przypadku…”, „jeżeli…”, „dotyczy tylko…”), chyba że ten przypadek opisuje `show_if`.
- Stałe kwoty i stawki wydrukowane na druku (np. „38 zł”) nie są polami: wpisz je w `description` pola,
  którego dotyczą.
- Gdy na druku zaznacza się jedną z kilku sytuacji i dla niej podaje datę lub inne dane: pole SINGLE_CHOICE
  z sytuacjami, a dane dla każdej sytuacji jako pola z `show_if` na tej opcji.
- Oświadczenie, które można zaznaczyć albo nie, i które zmienia sprawę (np. ulga, zwolnienie), to pole
  SINGLE_CHOICE z opcjami TAK/NIE, nie `consents`.
- Pola pokazywane warunkowo (np. „jeśli zaznaczono TAK, podaj…”) opisz przez `show_if` z etykietą pola wyboru
  i wartością opcji.
- Gdy dane się powtarzają (kilka osób, pojazdów, działek, zawodów), użyj sekcji z `repeating: true`.
- Gdy dokument zawiera kilka wersji tego samego wniosku (np. kilka rodzajów wniosku z tymi samymi częściami),
  zrób JEDEN formularz: na pierwszej stronie pole SINGLE_CHOICE „Rodzaj wniosku” z opcjami = rodzaje.
  Dokument z jednym wnioskiem nie ma pola „Rodzaj wniosku”.
  Część wspólną opisz raz. Porównaj wersje: KAŻDA sekcja, której nie ma we wszystkich wersjach, musi mieć
  `show_if`. Sekcja tylko dla jednego rodzaju: `show_if` z tą opcją; dla wszystkich rodzajów oprócz jednego:
  `show_if` z tą jedną opcją i `negate: true`. W `blocks` podaj ID z
  pierwszej wersji; bloków kolejnych wersji nie powtarzaj w polach ani w `block_roles`.
- Kraj wybieraj słownikiem `Kraje`. Walidatory: PESEL, NIP, REGON, ZIP_CODE (kod pocztowy), EMAIL.
- Załączniki z listy „do wniosku należy dołączyć” zamień na pola FILE w osobnej sekcji „Załączniki”.
- Oświadczenia, które wnioskodawca potwierdza (np. „oświadczam, że…”), wpisz do `consents` w krótkiej formie
  bez form zależnych od płci („Znam warunki…”, „Dane w formularzu są zgodne z prawdą”).

`applicant`: `entity=true` gdy formularz przewiduje dane firmy/instytucji; `other_person=true` gdy można
działać w imieniu innej osoby (domyślnie tak dla osób fizycznych).
`title`: zaczyna się od „Wniosek”, „Zgłoszenie”, „Deklaracja” lub „Oświadczenie”, bez odwołań do przepisów.
`authority_kind`: „organ”, gdy wniosek jest kierowany do osoby (Wójt, Burmistrz, Prezydent, Starosta).

Bloki: treść formularza dostajesz jako bloki z identyfikatorami, np. `[b12] Imię i nazwisko: ____`.
- Odwołuj się do bloków po ID, nie przepisuj ich treści.
- W polu i sekcji wpisz w `blocks` ID bloków, z których pochodzą (etykieta, opcje).
- `block_roles` wypełnij PRZED `pages`. Podaj rolę TYLKO dla bloków z tekstem do przeniesienia lub pominięcia:
  INSTRUCTION (pouczenie, objaśnienia), LEGAL_BASIS (podstawa prawna), STATEMENT (oświadczenie), GDPR (RODO),
  SKIP (tylko na papierze: podpis, pieczątka, „wypełnia urząd”, miejscowość i data). Nie podawaj ról dla
  etykiet pól, opcji ani tytułów.
- Ciąg kolejnych bloków o tej samej roli podaj JEDNYM wpisem z zakresem: `{"block": "b200", "to": "b260",
  "role": "GDPR"}` (np. cała klauzula RODO albo wszystkie objaśnienia).
- Używaj wyłącznie ID z listy bloków.
"""


log = logging.getLogger("autoformularz.llm")

# Eden AI usage per call ({promptTokens, completionTokens, cost} in USD, as reported by Eden), so the
# shared budget can be tracked (docs/eden-budzet.md). Ollama calls are free and not recorded.
EDEN_USAGE: list[dict] = []

DEV_WARNING = (
    "LLM przez Eden AI: każde zapytanie kosztuje (wspólny budżet, docs/eden-budzet.md). "
    "Tryb offline: AUTOFORMULARZ_LLM_PROVIDER=ollama."
)


@dataclass(frozen=True)
class Usage:
    """Token usage of one paid Eden AI response (OpenAI `usage` object; `cost` if Eden reports it)."""

    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost: float | None = None
    raw: dict = field(default_factory=dict)


# Seams for cost tracking (the team's budget file plugs in here; nothing in this module stores usage):
# - before_eden_call: run before every HTTP call to Eden; raise LLMError to block it (e.g. budget used up),
# - usage_hooks: run after every successful response with its Usage; errors are logged, never raised,
#   so a failing tracker does not throw away an answer that was already paid for.
before_eden_call: list[Callable[[str], None]] = []
usage_hooks: list[Callable[[Usage], None]] = []


def _usage(model: str, body: dict) -> Usage:
    u = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    cost = u.get("cost", body.get("cost"))
    return Usage(
        model=model,
        prompt_tokens=u.get("prompt_tokens"),
        completion_tokens=u.get("completion_tokens"),
        total_tokens=u.get("total_tokens"),
        cost=float(cost) if isinstance(cost, int | float) else None,
        raw=u,
    )


def _report(usage: Usage) -> None:
    log.info(
        "Eden AI usage: model=%s prompt=%s completion=%s cost=%s",
        usage.model,
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.cost,
    )
    for hook in usage_hooks:
        try:
            hook(usage)
        except Exception:
            log.exception("Usage hook failed")


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMError(Exception):
    def __init__(self, code: str, message: str, status: int = 502, partial: str = ""):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.partial = partial  # the cut answer (LLM_TRUNCATED), to see where the model got stuck


def build_user_prompt(ex: Document) -> str:
    parts = ["Przeanalizuj formularz i zwróć FormSpec."]
    if ex.blocks:
        listing = "\n".join(f"[{b.id}] {FILL_LINE.sub('……', b.text)}" for b in ex.blocks)
        parts.append(
            "Bloki formularza (kolejność jak w dokumencie, wiersze tabel jako | komórka |):\n\n" + listing
        )
    if ex.hint:  # blocks the code already handled (presort): the model does not look for them
        parts.append(ex.hint)
    if ex.images:
        parts.append(f"Formularz jest też na załączonych obrazach ({len(ex.images)}).")
    return "\n\n".join(parts)


def _key(settings: Settings) -> str:
    return settings.eden_api_key.get_secret_value() if settings.eden_api_key else ""


def _b64(img: bytes) -> str:
    return base64.b64encode(img).decode()


def _mime(img: bytes) -> str:
    return "image/jpeg" if img[:3] == b"\xff\xd8\xff" else "image/png"


def _call_ollama(messages: list[dict], images: list[bytes], settings: Settings) -> str:
    msgs = [dict(m) for m in messages]
    if images:
        msgs[1]["images"] = [_b64(img) for img in images]
    payload = {
        "model": settings.llm_model,
        "messages": msgs,
        "format": model_schema(),
        # Streamed so a looping answer can be stopped as soon as it repeats a section (see below).
        "stream": True,
        "think": False,
        "keep_alive": settings.llm_keep_alive,
        "options": {
            "temperature": 0,
            "num_ctx": settings.llm_num_ctx,
            "num_predict": settings.llm_max_tokens,
        },
    }
    answer = Answer()
    done_reason = None
    final: dict = {}
    call = metrics.start_call("ollama", settings.llm_model, msgs, images)
    try:
        with httpx.stream(
            "POST", f"{settings.ollama_url}/api/chat", json=payload, timeout=settings.llm_timeout_s
        ) as r:
            if r.status_code != 200:
                r.read()
                raise LLMError("LLM_ERROR", f"Model językowy zwrócił błąd {r.status_code}: {r.text[:300]}")
            for line in r.iter_lines():
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                done_reason = chunk.get("done_reason") or done_reason
                answer.add((chunk.get("message") or {}).get("content", ""))
                if chunk.get("done"):
                    final = chunk
                    break
    except httpx.HTTPError as e:
        raise LLMError(
            "LLM_UNAVAILABLE", f"Model językowy jest niedostępny ({settings.ollama_url}).", 503
        ) from e
    finally:
        _finish_call(call, answer, done_reason)
        call.prompt_tokens, call.completion_tokens = final.get("prompt_eval_count"), final.get("eval_count")
        call.ollama = {  # Ollama reports nanoseconds
            k.removesuffix("_duration") + "S": round(final[k] / 1e9, 2)
            for k in ("load_duration", "prompt_eval_duration", "eval_duration")
            if isinstance(final.get(k), int | float)
        }
    content = answer.text()
    if done_reason == "length":
        raise truncated(settings, content)
    return content


REPEAT_CHECK_CHARS = 400  # how often a streamed answer is checked for a repeated section (~100 tokens)


def truncated(settings: Settings, partial: str = "") -> LLMError:
    """The answer hit `llm_max_tokens`: almost always a repetition loop. No retry: it would loop again
    and double the cost. The cut answer is kept on the error (`partial`) for diagnosis."""
    return LLMError(
        "LLM_TRUNCATED",
        f"Odpowiedź modelu przekroczyła {settings.llm_max_tokens} tokenów (prawdopodobnie zapętlenie).",
        partial=partial,
    )


class Outline:
    """Reads a streamed FormSpec and reports the form title and the page, section and field names as soon
    as each one is complete (progress, shown in the UI while the model writes). A small JSON scanner: it
    only tracks strings, keys and which key opened each array or object."""

    NAMES = {
        ((), "title"): "Tytuł",
        (("pages",), "title"): "Strona",
        (("pages", "sections"), "title"): "Sekcja",
        (("pages", "sections", "fields"), "label"): "Pole",
    }

    def __init__(self) -> None:
        self.stack: list[str | None] = []  # key whose value each open container is (None in arrays)
        self.key: str | None = None  # last key read in the innermost object
        self.pending: str | None = None  # a complete string: a key if ":" follows, else a value
        self.raw: list[str] | None = None  # the string being read (None outside strings)
        self.escape = False

    def feed(self, piece: str) -> None:
        for ch in piece:
            if self.raw is not None:
                if self.escape:
                    self.escape = False
                elif ch == "\\":
                    self.escape = True
                elif ch == '"':
                    try:
                        self.pending = json.loads('"' + "".join(self.raw) + '"')
                    except ValueError:
                        self.pending = ""
                    self.raw = None
                    continue
                self.raw.append(ch)
            elif ch == '"':
                self.raw = []
            elif ch == ":":
                self.key, self.pending = self.pending, None
            elif ch in ",}]":
                if self.pending is not None:
                    self._value(self.pending)
                    self.pending = None
                if ch != ",":
                    if self.stack:
                        self.stack.pop()
                    self.key = None
            elif ch in "{[":
                self.stack.append(self.key)
                self.key = None

    def _value(self, value: str) -> None:
        path = tuple(k for k in self.stack if k is not None)
        if (name := self.NAMES.get((path, self.key or ""))) and value.strip():
            progress.item(f"{name}: {value.strip()}")


class Answer:
    """A model answer read piece by piece: reports its outline and stops a looping answer early."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.size = self.checked = 0
        self.outline = Outline()
        self.started = time.perf_counter()
        self.first_at: float | None = None  # when the first piece arrived (metrics: time to first token)

    def text(self) -> str:
        return "".join(self.parts)

    def add(self, piece: str) -> None:
        if not piece:
            return
        if self.first_at is None:
            self.first_at = time.perf_counter()
        self.parts.append(piece)
        self.size += len(piece)
        self.outline.feed(piece)
        progress.tick()  # a cancelled job stops here: leaving the stream closes it and the model stops
        # The model began writing the form again (form 9: once per version of the request): stop now
        # instead of at llm_max_tokens. Leaving the stream closes the connection and the model stops
        # generating; the complete part is used (generate_spec -> salvage). On form 9 this halves the
        # answer; a healthy answer never repeats a whole section, so it is never cut.
        if self.size - self.checked >= REPEAT_CHECK_CHARS:
            self.checked = self.size
            text = self.text()
            found = _complete_pages(text)
            if found and first_repeat(found[1]):
                log.warning("Model started repeating sections: stopped after %d characters.", self.size)
                raise LLMError("LLM_TRUNCATED", "Model zaczął powtarzać sekcje.", partial=text)
            # The form's own sections are done and the model goes on with the template's ("Dane
            # kontaktowe", "Podpis", "Data", "Podpis", …): stop, nothing after them belongs to the form.
            if found and template_tail(found[1]) >= TEMPLATE_TAIL:
                log.warning(
                    "Model started writing template sections: stopped after %d characters.", self.size
                )
                raise LLMError("LLM_TRUNCATED", "Model zaczął dopisywać części szablonu.", partial=text)
            # A loop inside one section: the same field again and again (form 1: "Numer porządkowy" 22
            # times). The section never closes, so the check above never sees it.
            if field_loop(text) is not None:
                log.warning("Model started repeating fields: stopped after %d characters.", self.size)
                raise LLMError("LLM_TRUNCATED", "Model zaczął powtarzać pola.", partial=text)


NO_THINK = "/no_think"  # Qwen3 soft switch: hybrid models skip reasoning; Instruct models ignore it


def thinking_off(settings: Settings) -> bool:
    return settings.eden_reasoning_effort.strip().lower() in ("none", "disable")


def _eden_messages(messages: list[dict], images: list[bytes], no_think: bool = False) -> list[dict]:
    msgs = [dict(m) for m in messages]
    if no_think:  # at the end of the last user message, where Qwen3 reads the switch
        last = max(i for i, m in enumerate(msgs) if m["role"] == "user")
        msgs[last]["content"] = f"{msgs[last]['content']}\n\n{NO_THINK}"
    if images:
        msgs[1]["content"] = [{"type": "text", "text": msgs[1]["content"]}] + [
            {"type": "image_url", "image_url": {"url": f"data:{_mime(img)};base64,{_b64(img)}"}}
            for img in images
        ]
    return msgs


def _call_eden(messages: list[dict], images: list[bytes], settings: Settings) -> str:
    key = _key(settings)
    if not key or not settings.eden_model:
        raise LLMError(
            "LLM_MISCONFIGURED",
            "Dostawca eden wymaga zmiennych EDENAI_API_KEY i AUTOFORMULARZ_EDEN_MODEL.",
            500,
        )
    url = f"{settings.eden_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.eden_model,
        "temperature": 0,
        "max_tokens": settings.llm_max_tokens,
        "messages": _eden_messages(messages, images, no_think=thinking_off(settings)),
        "stream": True,
        "stream_options": {"include_usage": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "FormSpec", "schema": model_schema()},
        },
    }
    if settings.eden_reasoning_effort.strip():
        payload["reasoning_effort"] = settings.eden_reasoning_effort.strip()

    def post() -> tuple[httpx.Response, dict | None, Answer]:
        """One call. Streamed (SSE) so progress shows and a looping answer stops early; the body is None
        when the provider answered with plain JSON instead (then read as before)."""
        for guard in before_eden_call:
            guard(settings.eden_model)
        answer = Answer()
        call = metrics.start_call("eden", settings.eden_model or "", payload["messages"], images)
        sse: dict | None = None
        try:
            with httpx.stream(
                "POST",
                url,
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
                timeout=settings.llm_timeout_s,
            ) as r:
                if r.status_code != 200 or "text/event-stream" not in r.headers.get("content-type", ""):
                    r.read()
                    if r.status_code != 200:
                        call.finish_reason = f"http {r.status_code}"
                    return r, None, answer
                sse = _read_sse(r, answer)
                return r, sse, answer
        except httpx.HTTPError as e:
            log.warning("Eden AI call failed: %s: %s", type(e).__name__, e)
            raise LLMError("LLM_UNAVAILABLE", "Model językowy jest niedostępny (Eden AI).", 503) from e
        finally:
            _finish_call(call, answer, (sse or {}).get("finish_reason") or call.finish_reason)
            if sse:
                _eden_call_usage(call, sse)

    r, body, answer = post()
    if 400 <= r.status_code < 500 and "reasoning" in r.text.lower() and "reasoning_effort" in payload:
        # Eden documents that a parameter the model does not list "may be dropped, ignored, or refused".
        # Refused: the same call without it (the /no_think switch stays in the prompt).
        payload.pop("reasoning_effort")
        r, body, answer = post()
    if 400 <= r.status_code < 500 and "response_format" in r.text:
        # Some providers behind Eden reject json_schema; the schema is in the prompt and Pydantic validates.
        payload["response_format"] = {"type": "json_object"}
        r, body, answer = post()
    if r.status_code != 200:
        snippet = r.text[:300].replace(key, "***")
        raise LLMError("LLM_ERROR", f"Model językowy zwrócił błąd {r.status_code}: {snippet}")
    if body is None:
        try:
            body = r.json()
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            _record(settings.eden_model, body if isinstance(body, dict) else {})
            raise LLMError("LLM_BAD_OUTPUT", "Model zwrócił odpowiedź w nieoczekiwanym formacie.") from e
        if isinstance(content, list):  # content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        content = content or ""
        answer.outline.feed(content)
        finish = choice.get("finish_reason")
        if (m := metrics.current()) is not None and m.calls:  # plain JSON answer: fill the call's record
            metrics.answer_shape(m.calls[-1], content)
            m.calls[-1].finish_reason = finish
            _eden_call_usage(m.calls[-1], body)
    else:
        content, finish = answer.text(), body.get("finish_reason")
    _record(settings.eden_model, body)
    if finish == "length":
        raise truncated(settings, content)
    return content


def _read_sse(r: httpx.Response, answer: Answer) -> dict:
    """A streamed Chat Completions answer: the text goes to `answer`; returns the finish reason and the
    usage and cost sent in the last chunks (`stream_options.include_usage`)."""
    out: dict = {}
    for line in r.iter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except ValueError:
            continue
        if not isinstance(chunk, dict):
            continue
        if isinstance(chunk.get("usage"), dict) and chunk["usage"]:
            out["usage"] = chunk["usage"]
        if "cost" in chunk:
            out["cost"] = chunk["cost"]
        for choice in chunk.get("choices") or []:
            piece = (choice.get("delta") or {}).get("content") or ""
            if isinstance(piece, list):
                piece = "".join(p.get("text", "") for p in piece if isinstance(p, dict))
            answer.add(piece)
            out["finish_reason"] = choice.get("finish_reason") or out.get("finish_reason")
    if "usage" not in out:
        log.warning("Eden AI sent no usage in the stream: this call's cost is not recorded.")
    return out


def _finish_call(call: metrics.ModelCall, answer: Answer, finish: str | None) -> None:
    """Fill a call's metrics from the streamed answer (also when it was stopped or failed)."""
    call.seconds = time.perf_counter() - answer.started
    if answer.first_at is not None:
        call.first_token_s = answer.first_at - answer.started
    call.finish_reason = finish
    metrics.answer_shape(call, answer.text())


def _eden_call_usage(call: metrics.ModelCall, body: dict) -> None:
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    call.prompt_tokens = usage.get("prompt_tokens")
    call.completion_tokens = usage.get("completion_tokens")
    cost = body.get("cost", usage.get("cost", usage.get("estimated_cost")))
    call.cost_usd = float(cost) if isinstance(cost, int | float) else None


def _record(model: str, body: dict) -> None:
    """Usage and cost of one paid response: log, hooks and EDEN_USAGE (/health)."""
    _report(_usage(model, body))
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    EDEN_USAGE.append(
        {
            "promptTokens": usage.get("prompt_tokens", 0),
            "completionTokens": usage.get("completion_tokens", 0),
            "cost": body.get("cost", usage.get("estimated_cost", 0.0)) or 0.0,
        }
    )


def parse_spec(content: str) -> FormSpec:
    text = content.strip()
    if m := _FENCE.match(text):
        text = m.group(1)
    return FormSpec.model_validate(json.loads(text))


# ---------------------------------------------------------------- a cut or looping answer

_DECODER = json.JSONDecoder()
_PAGES = re.compile(r'"pages"\s*:\s*\[')
_SECTIONS = re.compile(r'"sections"\s*:\s*\[')
_TITLE = re.compile(r'"title"\s*:\s*("(?:[^"\\]|\\.)*")')


def _items(text: str, pos: int) -> tuple[list, int, bool]:
    """Complete JSON values of an array from `pos` (after its "["): (values, end, array closed)."""
    out: list = []
    while True:
        while pos < len(text) and text[pos] in " \n\r\t,":
            pos += 1
        if pos >= len(text) or text[pos] == "]":
            return out, pos, pos < len(text)
        try:
            value, pos = _DECODER.raw_decode(text, pos)
        except json.JSONDecodeError:
            return out, pos, False
        out.append(value)


def _complete_pages(text: str) -> tuple[int, list[dict]] | None:
    """Where `pages` starts and its complete content so far: whole pages, plus the whole sections of a
    page still being written (models put a whole form on one page too)."""
    m = _PAGES.search(text)
    if not m:
        return None
    pages, pos, closed = _items(text, m.end())
    if not closed:
        s, t = _SECTIONS.search(text, pos), _TITLE.search(text, pos)
        if s and t and t.start() < s.start():
            sections, _, _ = _items(text, s.end())
            if sections:
                pages.append({"title": json.loads(t.group(1)), "sections": sections})
    return m.start(), [p for p in pages if isinstance(p, dict) and isinstance(p.get("sections"), list)]


def _section_key(section: dict) -> tuple:
    """How the canon (check.dedupe) tells a repeated section: same title and field labels."""
    fields = section.get("fields") if isinstance(section.get("fields"), list) else []
    return section.get("title"), tuple(f.get("label") for f in fields if isinstance(f, dict))


# A loop writes several sections it already wrote one after another. A single repeated section is normal:
# form 9's good answer has "Opinia macierzystego klubu sportowego" on the athlete's and the coach's page
# (the canon keeps one). The looping answer repeated 4 in a row.
LOOP_SECTIONS = 2


def first_repeat(pages: list[dict]) -> tuple[int, int] | None:
    """(page, section) where the model began writing the form again: the first of LOOP_SECTIONS
    consecutive sections it already wrote (same title and fields)."""
    seen: set[tuple] = set()
    run: list[tuple[int, int]] = []
    for pi, page in enumerate(pages):
        for si, section in enumerate(page["sections"]):
            if not isinstance(section, dict):
                continue
            key = _section_key(section)
            run = [*run, (pi, si)] if key in seen else []
            if len(run) >= LOOP_SECTIONS:
                return run[0]
            seen.add(key)
    return None


TEMPLATE_TAIL = 2


def template_tail(pages: list[dict]) -> int:
    """How many of the last complete sections in a row are template or paper-only sections
    (check.TEMPLATE_TITLE), after at least one section of the form's own."""
    titles = [str(s.get("title") or "") for p in pages for s in p["sections"] if isinstance(s, dict)]
    for run, title in enumerate(reversed(titles)):
        if not TEMPLATE_TITLE.match(title):
            return run
    return 0  # only template sections: nothing of the form's own yet


# A field (label and source blocks) written this many times in the open section is a loop. A real section
# repeats a label at most twice in a row of a table, and those rows point to other blocks; three is never
# seen on the materials.
FIELD_LOOP = 3
_FIELDS = re.compile(r'"fields"\s*:\s*\[')


def field_loop(text: str) -> int | None:
    """Where to cut an answer stuck in one section: the end of the last field before the first label
    written for the FIELD_LOOP-th time in the open `fields` array (so the section keeps each field once).
    None when the open section has no such repeat."""
    m = next(reversed(list(_FIELDS.finditer(text))), None)  # the open section is the last one
    if m is None:
        return None
    pos, ends, labels = m.end(), [], []
    while True:
        while pos < len(text) and text[pos] in " \n\r\t,":
            pos += 1
        if pos >= len(text) or text[pos] == "]":
            return None  # closed (the section check handles it) or nothing more yet
        try:
            value, pos = _DECODER.raw_decode(text, pos)
        except json.JSONDecodeError:
            return None
        # Same label AND same source blocks: table rows share a label but point to other blocks (form 8).
        label = (value.get("label"), str(value.get("blocks"))) if isinstance(value, dict) else None
        labels.append(label)
        ends.append(pos)
        if label is not None and labels.count(label) >= FIELD_LOOP:
            first_repeat_at = next(i for i, x in enumerate(labels) if labels[:i].count(x) >= 1)
            return ends[first_repeat_at - 1] if first_repeat_at else m.end()


def close_json(text: str) -> str:
    """Closes every open string, array and object of a cut JSON text (a trailing comma is dropped)."""
    stack: list[str] = []
    in_string = escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            stack.append("]" if ch == "[" else "}")
        elif ch in "]}" and stack:
            stack.pop()
    out = text + ('"' if in_string else "")
    out = out.rstrip().rstrip(",")
    return out + "".join(reversed(stack))


def salvage(partial: str) -> FormSpec | None:
    """A FormSpec from an answer cut at the limit or stopped in a loop: everything before `pages`, then the
    complete pages and sections up to the first repeated section. When the model got stuck repeating fields
    inside one section, the answer is cut before the repeats and closed, so that section is kept.
    None when too little is left (no pages, invalid head). On the materials the model wrote form 9 well
    once, then began it again per version of the request."""
    if (cut := field_loop(partial)) is not None:
        try:
            return FormSpec.model_validate(json.loads(close_json(partial[:cut])))
        except json.JSONDecodeError, ValidationError:
            pass
    found = _complete_pages(partial)
    if not found:
        return None
    start, pages = found
    if cut := first_repeat(pages):
        pi, si = cut
        pages = [*pages[:pi], {**pages[pi], "sections": pages[pi]["sections"][:si]}]
    pages = [p for p in pages if p["sections"]]
    if not pages:
        return None
    head = partial[:start].rstrip().rstrip(",")
    text = (
        head
        + (", " if head.strip() != "{" else "")
        + '"pages": '
        + json.dumps(pages, ensure_ascii=False)
        + "}"
    )
    try:
        return FormSpec.model_validate(json.loads(text))
    except json.JSONDecodeError, ValidationError:
        return None


def generate_spec(ex: Document, settings: Settings) -> FormSpec:
    eden = settings.llm_provider == "eden"
    call = _call_eden if eden else _call_ollama
    system = SYSTEM_PROMPT
    if eden:  # json_schema may be dropped by the provider, so the schema also goes in the prompt
        system += "\nSchemat JSON (FormSpec):\n" + json.dumps(model_schema(), ensure_ascii=False)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": build_user_prompt(ex)}]
    progress.stage("Model opisuje formularz")
    try:
        content = call(messages, ex.images, settings)
    except LLMError as e:
        if e.code != "LLM_TRUNCATED" or not (spec := salvage(e.partial)):
            raise
        log.warning("Model answer cut at the limit (repetition); kept its complete part.")
        ex.notes.append(  # same list as the source Document's notes: shown with the result
            "Model powtarzał sekcje i przekroczył limit odpowiedzi: użyto kompletnej części odpowiedzi "
            "sprzed powtórzeń. Sprawdź, czy formularz ma wszystkie sekcje."
        )
        return spec
    try:
        return parse_spec(content)
    except (json.JSONDecodeError, ValidationError) as e:
        error = str(e)[:1000]
    retry = [
        *messages,
        {"role": "assistant", "content": content[:4000]},
        {
            "role": "user",
            "content": f"Odpowiedź nie jest poprawnym JSON zgodnym ze schematem FormSpec. Błąd:\n{error}\n\n"
            "Zwróć poprawiony JSON, bez komentarzy.",
        },
    ]
    progress.stage("Model poprawia odpowiedź")
    content = call(retry, ex.images, settings)
    try:
        return parse_spec(content)
    except (json.JSONDecodeError, ValidationError) as e:
        raise LLMError("LLM_BAD_OUTPUT", "Model zwrócił odpowiedź niezgodną ze schematem.") from e


def warn_if_dev_provider(settings: Settings) -> None:
    if settings.llm_provider == "eden":
        log.warning(DEV_WARNING)


def eden_usage_total() -> dict:
    """Eden AI calls and cost since this process started (shared budget, docs/eden-budzet.md)."""
    return {
        "calls": len(EDEN_USAGE),
        "costUsd": round(sum(float(c.get("cost") or 0) for c in EDEN_USAGE), 6),
    }


def llm_status(settings: Settings) -> dict:
    if settings.llm_provider == "eden":
        return {
            "provider": "eden",
            "model": settings.eden_model,
            "configured": bool(_key(settings) and settings.eden_model),
            "usage": eden_usage_total(),
        }
    try:
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return {
            "provider": "ollama",
            "reachable": True,
            "model": settings.llm_model,
            "model_available": settings.llm_model in models,
        }
    except httpx.HTTPError, ValueError, KeyError:
        return {
            "provider": "ollama",
            "reachable": False,
            "model": settings.llm_model,
            "model_available": False,
        }
