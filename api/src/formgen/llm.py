"""Local LLM step: extracted form content -> FormSpec.

Uses Ollama with the FormSpec JSON Schema as `format`, so decoding is constrained to valid JSON of the
right shape. The model runs locally (task rule: no models available only through external APIs)."""

import base64
import json

import httpx
from pydantic import ValidationError

from formgen.config import Settings
from formgen.extract import Extracted
from formgen.spec import FormSpec

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
"""


class LLMError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def build_user_prompt(ex: Extracted) -> str:
    parts = ["Przeanalizuj formularz i zwróć FormSpec."]
    if ex.text:
        parts.append(
            "Treść formularza (kolejność jak w dokumencie, wiersze tabel jako | komórka |):\n\n" + ex.text
        )
    if ex.images:
        parts.append(f"Formularz jest też na załączonych obrazach ({len(ex.images)}).")
    return "\n\n".join(parts)


def generate_spec(ex: Extracted, settings: Settings) -> FormSpec:
    message: dict = {"role": "user", "content": build_user_prompt(ex)}
    if ex.images:
        message["images"] = [base64.b64encode(img).decode() for img in ex.images]
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, message],
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
    content = r.json().get("message", {}).get("content", "")
    try:
        return FormSpec.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError) as e:
        raise LLMError("LLM_BAD_OUTPUT", "Model zwrócił odpowiedź niezgodną ze schematem.") from e


def llm_status(settings: Settings) -> dict:
    try:
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return {
            "reachable": True,
            "model": settings.llm_model,
            "model_available": settings.llm_model in models,
        }
    except httpx.HTTPError, ValueError, KeyError:
        return {"reachable": False, "model": settings.llm_model, "model_available": False}
