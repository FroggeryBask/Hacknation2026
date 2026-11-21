"""LLM step: extracted form content -> FormSpec.

Default: local Ollama with the FormSpec JSON Schema as `format`, so decoding is constrained to valid JSON of
the right shape (task rule: no models available only through external APIs). For local development only,
AUTOFORMULARZ_LLM_PROVIDER=eden sends the same prompt to an open-weight model on Eden AI (OpenAI Chat Completions);
docker-compose forces Ollama for the delivered solution."""

import base64
import json
import logging
import re

import httpx
from pydantic import ValidationError

from autoformularz.config import Settings
from autoformularz.document import Document
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
    "LLM przez Eden AI: tryb demo i deweloperski (uzgodniony z mentorami COI); każde zapytanie kosztuje. "
    "Domyślnie rozwiązanie używa lokalnej Ollamy."
)
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMError(Exception):
    def __init__(self, code: str, message: str, status: int = 502, partial: str = ""):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.partial = partial  # the cut answer (LLM_TRUNCATED), to see where the model got stuck


def build_user_prompt(ex: Document) -> str:
    parts = ["Przeanalizuj formularz i zwróć FormSpec."]
    if ex.blocks:
        listing = "\n".join(f"[{b.id}] {b.text}" for b in ex.blocks)
        parts.append(
            "Bloki formularza (kolejność jak w dokumencie, wiersze tabel jako | komórka |):\n\n" + listing
        )
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
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_ctx": settings.llm_num_ctx,
            "num_predict": settings.llm_max_tokens,
        },
    }
    try:
        r = httpx.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=settings.llm_timeout_s)
    except httpx.HTTPError as e:
        raise LLMError(
            "LLM_UNAVAILABLE", f"Model językowy jest niedostępny ({settings.ollama_url}).", 503
        ) from e
    if r.status_code != 200:
        raise LLMError("LLM_ERROR", f"Model językowy zwrócił błąd {r.status_code}: {r.text[:300]}")
    body = r.json()
    content = body.get("message", {}).get("content", "")
    if body.get("done_reason") == "length":
        raise truncated(settings, content)
    return content


def truncated(settings: Settings, partial: str = "") -> LLMError:
    """The answer hit `llm_max_tokens`: almost always a repetition loop. No retry: it would loop again
    and double the cost. The cut answer is kept on the error (`partial`) for diagnosis."""
    return LLMError(
        "LLM_TRUNCATED",
        f"Odpowiedź modelu przekroczyła {settings.llm_max_tokens} tokenów (prawdopodobnie zapętlenie).",
        partial=partial,
    )


def _eden_messages(messages: list[dict], images: list[bytes]) -> list[dict]:
    msgs = [dict(m) for m in messages]
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
        "messages": _eden_messages(messages, images),
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "FormSpec", "schema": model_schema()},
        },
    }

    def post() -> httpx.Response:
        try:
            return httpx.post(
                url, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=settings.llm_timeout_s
            )
        except httpx.HTTPError as e:
            raise LLMError("LLM_UNAVAILABLE", "Model językowy jest niedostępny (Eden AI).", 503) from e

    r = post()
    if 400 <= r.status_code < 500 and "response_format" in r.text:
        # Some providers behind Eden reject json_schema; the schema is in the prompt and Pydantic validates.
        payload["response_format"] = {"type": "json_object"}
        r = post()
    if r.status_code != 200:
        snippet = r.text[:300].replace(key, "***")
        raise LLMError("LLM_ERROR", f"Model językowy zwrócił błąd {r.status_code}: {snippet}")
    try:
        body = r.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError("LLM_BAD_OUTPUT", "Model zwrócił odpowiedź w nieoczekiwanym formacie.") from e
    usage = body.get("usage") or {}
    EDEN_USAGE.append(
        {
            "promptTokens": usage.get("prompt_tokens", 0),
            "completionTokens": usage.get("completion_tokens", 0),
            "cost": body.get("cost", usage.get("estimated_cost", 0.0)) or 0.0,
        }
    )
    if isinstance(content, list):  # content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if body["choices"][0].get("finish_reason") == "length":
        raise truncated(settings, content or "")
    return content or ""


def parse_spec(content: str) -> FormSpec:
    text = content.strip()
    if m := _FENCE.match(text):
        text = m.group(1)
    return FormSpec.model_validate(json.loads(text))


def generate_spec(ex: Document, settings: Settings) -> FormSpec:
    eden = settings.llm_provider == "eden"
    call = _call_eden if eden else _call_ollama
    system = SYSTEM_PROMPT
    if eden:  # json_schema may be dropped by the provider, so the schema also goes in the prompt
        system += "\nSchemat JSON (FormSpec):\n" + json.dumps(model_schema(), ensure_ascii=False)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": build_user_prompt(ex)}]
    content = call(messages, ex.images, settings)
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
