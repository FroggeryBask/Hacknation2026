# Podział pracy (3 osoby)

Stan na `d9138a6`. Działa API: upload → odczyt → LLM (FormSpec) → kompilator → linter, testy na wzorcach 1 i 5, Docker. Design system formularzy jest w `src/components/form`, ale strona główna to nadal ekran Create Next App, a formularze w `/design-system` są pisane ręcznie, a nie renderowane z JSON. Nie ma jeszcze wynikowych JSON-ów dla formularzy 2, 3, 4, 6, 7, 8, 9 ani materiałów do oddania.

## Na czym się skupić (wg kryteriów oceny)

| Kryterium | Waga | Co to dla nas znaczy |
|---|---|---|
| Kompletność | 30% | Poprawne JSON-y dla 2, 3, 4, 6, 7, 8, 9 (zero błędów lintera) i działanie na **nowych plikach na obronie** |
| Intuicyjność | 20% | Formularze zgodne ze standardem projektowania + frontend: upload, podgląd, renderer |
| Jakość kodu | 20% | Testy, `npm run check` na zielono, czytelna architektura |
| Potencjał wdrożeniowy i koszt | 20% | Mały lokalny model, Docker działa „od zera”, uzasadniony wybór sprzętu |
| Oryginalność | 10% | Hybryda AI + deterministyczny kompilator, walidacja reguł, edycja FormSpec |

Priorytety:
1. **Jakość wyniku na lokalnym modelu (Ollama `qwen3-vl:8b`).** Oceniany jest wynik z Dockera, nie z Eden AI.
2. **Odporność na nieznane pliki:** wszystkie formaty (PDF, skan, DOC, DOCX, ODS, XLSX, JPG, PNG) muszą dawać poprawny JSON.
3. **Frontend z rendererem z JSON** (rozszerzenia IV i V): dobrze wygląda na filmie i obronie.
4. **Materiały do oddania** od początku równolegle, nie na ostatnią godzinę.

## Osoba 1: jakość konwersji (backend, AI)

Pliki: `api/src/autoformularz/` (`llm.py`, `spec.py`, `compiler.py`, `lint.py`, `extract.py`).

- Przepuścić formularze 2, 3, 4, 6, 7, 8, 9 przez API, zapisać FormSpec i JSON do `wyniki/`, poprawiać prompt i kompilator, aż linter da 0 błędów. Dalsza praca nad kompilatorem na zapisanych FormSpec (endpoint `/compile`, bez kosztu LLM).
- Testy na każdym formacie wejścia (zwłaszcza skany JPG/PNG i `.doc`/`.ods` przez LibreOffice).
- Rozszerzenie III: warunki `show_if` → jsonata `states`, przepływy między stronami; rozszerzenie I: słowniki (`Kraje`, `TERYT_*`) i dane inicjalne (MLPZ/PESEL).
- Każda zmiana kompilatora z testem w `api/tests/test_compiler.py`.
- Eden AI oszczędnie (budżet 100 €): domyślnie Ollama, `AUTOFORMULARZ_MAX_PDF_PAGES=2–3` w trakcie pracy, bez pętli po wszystkich formularzach.

## Osoba 2: frontend (rozszerzenia IV, V, VI)

Pliki: `src/app/`, `src/components/form` (tylko design system i tokeny z `globals.css`, zob. `docs/design-system.md`).

- Strona główna zamiast ekranu Create Next App: upload pliku → wywołanie `POST /api/v1/forms?details=true` po stronie serwera (`AUTOFORMULARZ_API_URL`, JWT nigdy w przeglądarce) → wynik.
- Podgląd: JSON do pobrania, raport walidacji (`issues`, `notes`), stan ładowania (model działa nawet kilka minut).
- **Renderer e-formularza z JSON COI** (rozszerzenie V): generyczny komponent zamiast ręcznych `src/components/forms/*.tsx`; sprawdzić na wzorcach 1 i 5.
- Edycja FormSpec i ponowne `POST /api/v1/forms/compile` (bez modelu), walidacje pól w rendererze, opcjonalnie batch kilku plików (rozszerzenie VI).

## Osoba 3: dostarczenie i dokumentacja

- **Docker od zera** na czystej maszynie: `docker compose up --build`, pobranie modelu, czas odpowiedzi na CPU i GPU. Wynik decyduje o rozmiarze modelu na obronę.
- Dopytać mentorów COI o otwarte sprawy z `docs/wyjasnienia-materialow.md` (FINISH, sprzęt na obronie, LibreOffice) i aktualizować `docs/decisions.md`.
- Dokumentacja architektury (wymagana obowiązkowo) i README: diagram, uzasadnienie wyborów, koszt wdrożenia.
- Materiały do oddania: tytuł i opis, prezentacja PDF (maks. 10 slajdów), wynikowe JSON-y (od osoby 1), film (maks. 3 min), link do repo.
- Rozszerzenie II: propozycja nowego słownika.
- Próba generalna obrony: nowy, nieznany formularz end-to-end na Dockerze.

## Zasady współpracy

- Każdy na swoim branchu, małe PR-y do `main`; `npm run check` musi przechodzić.
- Kontrakt między osobą 1 a 2: odpowiedź `?details=true` (`form`, `spec`, `issues`, `notes`, `sourceFormat`). Zmiany kontraktu tylko po uzgodnieniu.
- Klucz Eden AI jest wspólny: zanim uruchomisz serię testów przez Eden, daj znać zespołowi.
- Bez atrybucji AI w commitach i PR-ach (reguła zespołu).
