# Pipeline: wierny formularz i deterministyczny JSON

Wynik brainstormu zespołu. Cel: z jednego pliku wygenerować e-formularz wierny źródłu (pola, teksty prawne, zależności) i JSON COI, który jest poprawny i powtarzalny (ten sam plik → ten sam JSON).

## Zasada

Wierność źródłu wymaga LLM, a powtarzalność wymaga kodu. Dlatego:
- LLM tylko **klasyfikuje i wskazuje** (role bloków, typy pól, sekcje, warunki). Nie przepisuje tekstu i nie pisze JSON-a COI.
- Wszystko, co da się zrobić regułami, robi kod: ekstrakcja, sprawdzenia, kanonizacja, kompilacja, lint.
- **UI renderuje COI JSON**, nie FormSpec. Podgląd jest widokiem JSON-a, więc formularz i JSON nie mogą się rozjechać.

## Zakres wejścia

- Jedno wywołanie = **jeden plik** („REST API umożliwiający przesłanie pojedynczego pliku będącego blankietem formularza”).
- Batch (rozszerzenie VI) = wiele **osobnych** formularzy przetwarzanych po kolei, bez sklejania plików.
- Kolejność stron w pliku jest poprawna (nie obsługujemy pomieszanych stron).

## Kroki

```
1. upload.py   plik → sprawdzenie nazwy, rozmiaru, MIME (tylko pamięć / temp)
2. extract.py  plik → Document { bloki[id, tekst, strona, typ], kandydaci_na_pola[] }
3. llm.py      Document → FormSpec (ID bloków, role, typy, warunki)
4. check       FormSpec × Document → kotwice, pokrycie pól, pokrycie tekstu, słownik
5. canon       FormSpec → kanoniczny FormSpec
6. compiler.py FormSpec + Document → COI JSON
7. lint.py     COI JSON → błędy i ostrzeżenia
8. UI          COI JSON → formularz (ewaluacja states)
```

### 2. Extract (kod)
- Tekst w kolejności czytania, podzielony na **bloki z ID**: akapit, wiersz, komórka tabeli, opcja `☐`.
- **Kandydaci na pola**: `____`, `......`, `☐`/`□`, puste komórki tabel, pola AcroForm, wzorzec „Etykieta: ___”.
- **Skany** (JPG, PNG, skan w PDF): osobny krok VLM robi tylko transkrypcję do tych samych bloków, bez interpretacji. Dalej pipeline jest taki sam.

### 3. LLM (FormSpec)
Wyjście ograniczone JSON Schemą, `temperature=0`, stały seed, przypięta wersja modelu. Model:
- przypisuje każdemu blokowi rolę: `etykieta_pola`, `opcja`, `pouczenie`, `podstawa_prawna`, `oświadczenie`, `rodo`, `nagłówek`, `pomiń` (np. „miejsce na pieczęć”);
- dla pól podaje typ, wymagalność i sekcję;
- wskazuje potrzebne sekcje predefiniowane (adres, pełnomocnik, opłata skarbowa…);
- podaje proste warunki: `{pokaż_gdy: <pole>, równe: <opcja>}`.

Model **odwołuje się do ID bloków**, nigdy nie przepisuje ich treści.

### 4. Check (kod)
- **Kotwice**: każde ID bloku z FormSpec istnieje w Document. Jeśli nie, to halucynacja i pole jest odrzucane.
- **Pokrycie pól**: każdy kandydat z ekstrakcji ma pole albo jawne `pomiń`.
- **Pokrycie tekstu**: każdy blok ma rolę. Dla nieprzypisanych jest jedna ponowna próba LLM tylko z tymi blokami. Jeśli dalej brak, blok trafia jako `TEXT_BLOCK` do najbliższej sekcji z ostrzeżeniem. **Nic nie znika po cichu.**
- **Słownik typów**: normalizacja etykiet do typów (PESEL, NIP, REGON, kod pocztowy, e-mail, data) i walidatory; rozpoznawanie zestawów pól jako sekcji predefiniowanych (np. ulica/nr/kod/miejscowość = adres).

Przynależność pola do formularza sprawdzamy kotwicą w źródle, nie słownikiem „typ sprawy → pola” (takiego źródła nie ma w materiałach). Wyjątek: pola z szablonów sekcji predefiniowanych, które dokłada kompilator.

### 5. Canon (kod)
- Kolejność według pozycji bloków w dokumencie, a nie według kolejności z odpowiedzi modelu.
- Znormalizowane etykiety (spacje, dwukropki), techNames z etykiet.
- ID elementów: UUIDv5 z tytułu i techName (nie z indeksu), żeby jedno dodatkowe pole nie zmieniało ID wszystkich pól pod nim.

### 6. Compiler (kod)
- Sekcje predefiniowane z szablonów (te same techNames i zapytania co w referencji).
- **Tekst wklejany dosłownie** z bloków (za flagą `AUTOFORMULARZ_COPY_SOURCE_TEXT`, domyślnie wyłączone: na zapisanych wynikach model oznaczał jako pouczenie lub podstawę prawną papierowe instrukcje, treść prośby i RODO): pouczenia (`INSTRUCTION`) i podstawa prawna (`LEGAL_BASIS`) jako `TEXT_BLOCK` na stronie końcowej (sekcje „Pouczenie” i „Podstawa prawna”, przed podglądem). Według standardu **nie** kopiujemy oświadczeń (mają być krótkie i neutralne płciowo, więc pisze je model w `consents`) ani klauzuli RODO (tylko odnośnik, „zasadą jest niezamieszczanie takich treści na formularzu”).
- Warunki → `states` z zapytaniem jsonata w kształcie z referencji (`{"type": "SHOW", "query": "(\"…\" in tabs[…].questions[…].field.__userAnswer)"}`). Model nigdy nie pisze jsonaty.
- Strony i flow.

### 7. Lint (kod)
Obecne reguły z „Reguł technicznych”, a do tego:
- warunek wskazuje istniejące pole i opcję (`STATE_UNKNOWN_OPTION`), brak cykli (`STATE_CYCLE`), pole sterujące jest wyżej na ekranie (`STATE_FORWARD_REF`, ostrzeżenie; kolejność z `y`/`x` siatki, nie z tablicy JSON);
- liczniki pokrycia tekstu i pól w odpowiedzi `?details=true`.

### 8. UI
- Renderer z COI JSON; `states` ewaluowane przy każdej odpowiedzi, a pola ukryte istnieją, ale się nie pokazują (np. „nie mam dzieci” ukrywa „liczbę dzieci”).
- Widok obok siebie: bloki źródła i formularz, z podświetleniem, skąd jest każde pole i każdy tekst prawny.
- Licznik pokrycia i lista nieprzypisanych bloków.
- Ręczna korekta FormSpec → `/api/v1/forms/compile` → nowy JSON (deterministycznie, bez modelu).

## Zmiany względem obecnego kodu
- `extract.py` zwraca bloki z ID i kandydatów na pola zamiast samego tekstu.
- `spec.py`: FormSpec odwołuje się do ID bloków i ma pole warunku.
- Nowe kroki check i canon (mogą być funkcjami w istniejących modułach).
- Kompilator bierze tekst z Document, nie z FormSpec.
- Kontrakt `?details=true` dostaje `document.blocks` i `coverage`.

## Kontrakt

Ustalony w PR „document-contract” ([zadanie](tasks/document-contract.md)). Zmiany tylko po uzgodnieniu
(Ewelina ↔ Konrad: `Document`, Konrad ↔ Gabrysia: `?details=true`).

**`Document`** (`api/src/autoformularz/document.py`, wynik `extract.py`):
- `blocks`: `{id, text, kind, page}`. `id` = `b1`, `b2`, … w kolejności czytania. `kind` = `paragraph`,
  `table_row` (cały wiersz tabeli jako `| a | b |`), `heading`. `page` od 1 dla PDF, `null` dla DOCX/XLSX.
- `candidates`: `{block, kind, text}`, miejsca do wypełnienia. `kind` = `blank` (`____`), `dots` (`......`),
  `checkbox` (`☐ opcja`), `colon` („Etykieta:” bez wartości).
- `images`: obrazy stron skanów (nie trafiają do odpowiedzi API). Skany nie mają jeszcze bloków.

**FormSpec** (`spec.py`), pola z wartościami domyślnymi, więc stare FormSpec są poprawne:
- `FieldSpec.blocks`, `SectionSpec.blocks`: ID bloków, z których pochodzi element (etykieta, opcje).
- `FormSpec.block_roles` (w schemacie przed `pages`): `{block, to?, role}`, `to` = ostatni blok ciągu kolejnych
  bloków o tej samej roli (np. cała klauzula RODO jednym wpisem); `spec.roles()` rozwija zakresy. Rola = `FIELD_LABEL`, `OPTION`, `HEADING`, `INSTRUCTION`
  (pouczenie), `LEGAL_BASIS` (podstawa prawna), `STATEMENT` (oświadczenie), `GDPR` (RODO), `SKIP` (tylko na papierze).
  Model podaje role **tylko** dla `INSTRUCTION`, `LEGAL_BASIS`, `STATEMENT`, `GDPR` i `SKIP`. Role dla wszystkich
  bloków nie mieszczą się w oknie modelu: formularz 8 (DOCX) ma 631 bloków, czyli ok. 8 tys. tokenów samych ról
  przy `num_ctx=16384`. Pozostałe role są dozwolone, ale nie wymagane. Bloki bez roli to nie błąd: trafiają do
  `coverage.unreferenced`, a krok check zamieni je później na `TEXT_BLOCK` z ostrzeżeniem.

**`?details=true`** dostaje dwa klucze (`null` dla `/compile`, bo nie ma pliku źródłowego):
```json
"document": {"blocks": [{"id": "b1", "text": "…", "kind": "paragraph", "page": null}],
             "candidates": [{"block": "b7", "kind": "blank", "text": "Imię: ____"}]},
"coverage": {"blocks": 63, "referenced": 58, "unreferenced": ["b4"], "candidates": 12,
             "candidatesWithoutField": ["b31"], "unknownRefs": []}
```
- `unreferenced`: bloki bez pola, sekcji ani roli (tytuły i zwykły tekst; do sprawdzenia, czy nic nie znika).
- `candidatesWithoutField`: bloki z kandydatem na pole bez pola i bez `SKIP`.
- `unknownRefs`: ID z FormSpec, których nie ma w dokumencie (halucynacje).

Pierwsza wersja: jeden blok na wiersz tekstu, kandydaci z wzorców w tekście (formularze z pól tekstowych
bez `____`, np. nr 2, nie mają jeszcze kandydatów). Kompilator jeszcze nie korzysta z bloków.

## Weryfikacja
- Testy migawkowe na formularzach z `materialy/`: każdy uruchomiony kilka razy, JSON-y identyczne.
- Pokrycie i precyzja pól względem ręcznie spisanej listy pól dla każdego formularza.
- Lint z zerem błędów.

## Otwarte decyzje
- Pole „…(jeśli dotyczy)” bez pytania sterującego w źródle: (a) pole opcjonalne, zawsze widoczne (wierne źródłu) czy (b) kompilator dokłada pytanie Tak/Nie z warunkiem (lepszy UX, ale dodaje coś spoza pliku). Najpierw sprawdzić „Standardy i dobre praktyki”, potem zapytać mentorów.
- Cache wyników w pamięci po hashu pliku: potwierdzić z mentorami, że nie łamie zakazu przechowywania plików.
- Głosowanie z kilku przebiegów LLM i podział na wywołania per sekcja: dopiero jeśli testy migawkowe pokażą rozrzut.
