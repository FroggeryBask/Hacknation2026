# Podział pracy: Ewelina, Konrad, Gabrysia

Stan na `b965fab`. Działa API: upload → odczyt → LLM (FormSpec) → kompilator → linter, testy na wzorcach 1 i 5, Docker. Docelowy pipeline jest opisany w [pipeline.md](pipeline.md) (bloki z ID, kroki check i canon, UI renderuje COI JSON). Design system formularzy jest w `src/components/form`, ale strona główna to nadal ekran Create Next App, a formularze w `/design-system` są pisane ręcznie. Nie ma jeszcze wynikowych JSON-ów dla formularzy 2, 3, 4, 6, 7, 8, 9 ani materiałów do oddania.

**Termin: kod i materiały na Hacktribe do 22.11.2026, 11:00.** Po terminie zmiany się nie liczą.

## Ustalenia z mentorami COI (szczegóły: [wyjasnienia-materialow.md](wyjasnienia-materialow.md))

- Kod wgrywamy na Hacktribe, więc rozwiązanie musi ruszyć u kogoś innego z samego README i `docker compose up --build`, także na CPU.
- Na stronie końcowej wolno `INFO_SECTION` i `TEXT_BLOCK`.
- LibreOffice tylko przy licencji, która nie wymaga udostępnienia naszego kodu: trzeba uważać.
- Punktowane są i walidacje pól, i wizualizacja formularza.

## Na czym się skupić (wg kryteriów oceny)

| Kryterium | Waga | Co to dla nas znaczy |
|---|---|---|
| Kompletność | 30% | Poprawne JSON-y dla 2, 3, 4, 6, 7, 8, 9 (zero błędów lintera), rozszerzenia I–V, działanie na nowych plikach |
| Intuicyjność | 20% | Formularze zgodne ze standardem projektowania, frontend: upload, podgląd, renderer |
| Jakość kodu | 20% | Testy, `npm run check` na zielono, czytelna architektura |
| Potencjał wdrożeniowy i koszt | 20% | Mały lokalny model, Docker działa „od zera”, jasne README |
| Oryginalność | 10% | Hybryda AI + deterministyczny kompilator, kotwice w źródle, pokrycie tekstu, edycja FormSpec |

Priorytety:
1. **Jakość wyniku na lokalnym modelu (Ollama `qwen3-vl:8b`).** Oceniany jest wynik z Dockera, nie z Eden AI.
2. **Odporność na nieznane pliki:** wszystkie formaty (PDF, skan, DOC, DOCX, ODS, XLSX, JPG, PNG).
3. **Frontend z rendererem i walidacjami** (rozszerzenia IV, V, VI).
4. **Materiały do oddania** równolegle od początku, nie na ostatnią godzinę.

## Ewelina: wejście, sprawdzenia i wyniki

Pliki: `api/src/autoformularz/extract.py`, `upload.py`, nowe kroki check i canon, `api/tests/`.

- `extract.py` zwraca Document: bloki z ID (akapit, wiersz, komórka, opcja `☐`) i kandydatów na pola (`____`, `......`, `☐`, puste komórki, „Etykieta: ___”) – krok 2 z pipeline.md.
- Skany (JPG, PNG, skan w PDF): transkrypcja VLM do tych samych bloków.
- `.ods` czytany bezpośrednio z XML (bez LibreOffice); LibreOffice zostaje tylko dla `.doc`.
- Kroki check (kotwice, pokrycie pól i tekstu) i canon (kolejność wg dokumentu, techNames, UUIDv5) – kroki 4 i 5.
- **Wynikowe JSON-y** dla 2, 3, 4, 6, 7, 8, 9 w `wyniki/` + testy migawkowe (kilka przebiegów = ten sam JSON).
- Rozszerzenie II: propozycja nowego słownika.
- Kontakt z mentorami, opis i tytuł projektu, **wgranie wszystkiego na Hacktribe**.

## Konrad: model, kompilator, linter i Docker

Pliki: `api/src/autoformularz/llm.py`, `spec.py`, `compiler.py`, `lint.py`, `api/Dockerfile`, `docker-compose.yml`, `README.md`.

- `spec.py` i prompt: FormSpec odwołuje się do ID bloków, ma role bloków i warunki `{pokaż_gdy, równe}` – krok 3.
- Kompilator: tekst prawny dosłownie z bloków, warunki → jsonata `states`, flow stron, słowniki (`Kraje`, `TERYT_*`) i dane inicjalne (MLPZ/PESEL) – rozszerzenia I i III.
- Linter: usunąć ostrzeżenie o `TEXT_BLOCK` na stronie końcowej (ustalenie z mentorami), dodać sprawdzanie warunków (istniejące pole i opcja, brak cykli) i liczniki pokrycia w `?details=true`.
- Każda zmiana kompilatora z testem w `api/tests/test_compiler.py`.
- **Docker od zera** na czystej maszynie (CPU, opcjonalnie GPU): czas pobrania modelu i odpowiedzi, wymagania w README.
- README i **dokumentacja architektury** (obowiązkowa), w tym licencje (LibreOffice MPL-2.0 jako osobny proces).

## Gabrysia: frontend, prezentacja i film

Pliki: `src/app/`, `src/components/form` (tylko design system i tokeny z `globals.css`, zob. [design-system.md](design-system.md)).

- Strona główna: upload pliku → `POST /api/v1/forms?details=true` po stronie serwera (`AUTOFORMULARZ_API_URL`, JWT nigdy w przeglądarce) → wynik, stan ładowania (model działa nawet kilka minut), JSON do pobrania – rozszerzenie IV.
- **Renderer e-formularza z COI JSON** z ewaluacją `states` (pola ukryte istnieją, ale się nie pokazują) zamiast ręcznych `src/components/forms/*.tsx`; sprawdzić na wzorcach 1 i 5 – wizualizacja.
- **Walidacje pól** w rendererze (PESEL, NIP, REGON, kod pocztowy, e-mail, wymagalność) – punktowane osobno.
- Widok obok siebie: bloki źródła i formularz, pokrycie, lista nieprzypisanych bloków, raport lintera.
- Ręczna korekta FormSpec → `/api/v1/forms/compile`; opcjonalnie batch kilku plików (rozszerzenie VI).
- **Prezentacja PDF** (maks. 10 slajdów) i **film** (maks. 3 min, link) na podstawie działającego UI.

## Wspólnie

- Próba generalna: nowy, nieznany formularz end-to-end na Dockerze, najpóźniej kilka godzin przed terminem.
- Pitch na obronie: 5 min prezentacji + 5 min pytań.

## Zasady współpracy

- Każdy na swoim branchu, małe PR-y do `main`; `npm run check` musi przechodzić.
- Kontrakt Ewelina ↔ Konrad: struktura Document (bloki z ID, kandydaci na pola). Kontrakt Konrad ↔ Gabrysia: odpowiedź `?details=true` (`form`, `spec`, `issues`, `notes`, `sourceFormat`, a docelowo `document.blocks` i `coverage`). Zmiany kontraktu tylko po uzgodnieniu.
- Klucz Eden AI jest wspólny (budżet 100 €): domyślnie Ollama, `AUTOFORMULARZ_MAX_PDF_PAGES=2–3` w trakcie pracy, bez pętli po wszystkich formularzach; przed serią testów przez Eden daj znać zespołowi.
- Bez atrybucji AI w commitach i PR-ach (reguła zespołu).
