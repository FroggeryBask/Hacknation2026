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
from autoformularz.spec import FormSpec

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

`pages` to strony dotyczące przedmiotu sprawy. Zasady:
- Grupuj pola tematycznie w sekcje. Strona ma krótki tytuł opisujący temat (np. „Informacje o budynku”).
- Zachowaj zakres danych z formularza. Nie wymyślaj pól, których nie ma w dokumencie.
- Typ pola: TEXT krótki tekst; LONG_TEXT opis lub uzasadnienie; NUMBER tylko liczby (kwoty, liczby osób);
  DATE daty; SINGLE_CHOICE jedna z kilku opcji (kratki do zaznaczenia jednej odpowiedzi); MULTI_CHOICE wiele
  opcji; SELECT jedna z wielu (>5) opcji; FILE załączniki wymienione w formularzu; INFO stała informacja.
- Etykiety pisz prostym językiem, bez form zależnych od płci, bez dwukropków i wielokropków.
- `required`: false tylko dla danych opcjonalnych (np. „jeśli posiada”, „nr lokalu”, „uwagi”).
- Pola pokazywane warunkowo (np. „jeśli zaznaczono TAK, podaj…”) opisz przez `show_if` z etykietą pola wyboru
  i wartością opcji.
- Gdy dane się powtarzają (kilka osób, pojazdów, działek, zawodów), użyj sekcji z `repeating: true`.
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
- W `block_roles` podaj rolę każdego pozostałego bloku: HEADING (tytuł), INSTRUCTION (pouczenie),
  LEGAL_BASIS (podstawa prawna), STATEMENT (oświadczenie), GDPR (RODO), SKIP (tylko na papierze: podpis,
  pieczątka, „wypełnia urząd”, miejscowość i data). Dla pól i opcji użyj FIELD_LABEL i OPTION.
- Używaj wyłącznie ID z listy bloków.
"""


log = logging.getLogger("autoformularz.llm")

DEV_WARNING = "LLM przez Eden AI: tryb deweloperski, nie do oddania (oddawane rozwiązanie używa Ollamy)."
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


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
        "format": FormSpec.model_json_schema(),
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_ctx": settings.llm_num_ctx},
    }
    try:
        r = httpx.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=settings.llm_timeout_s)
    except httpx.HTTPError as e:
        raise LLMError(
            "LLM_UNAVAILABLE", f"Model językowy jest niedostępny ({settings.ollama_url}).", 503
        ) from e
    if r.status_code != 200:
        raise LLMError("LLM_ERROR", f"Model językowy zwrócił błąd {r.status_code}: {r.text[:300]}")
    return r.json().get("message", {}).get("content", "")


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
        "messages": _eden_messages(messages, images),
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "FormSpec", "schema": FormSpec.model_json_schema()},
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
        content = r.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError("LLM_BAD_OUTPUT", "Model zwrócił odpowiedź w nieoczekiwanym formacie.") from e
    if isinstance(content, list):  # content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
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
        system += "\nSchemat JSON (FormSpec):\n" + json.dumps(
            FormSpec.model_json_schema(), ensure_ascii=False
        )
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


def llm_status(settings: Settings) -> dict:
    if settings.llm_provider == "eden":
        return {
            "provider": "eden",
            "model": settings.eden_model,
            "configured": bool(_key(settings) and settings.eden_model),
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
