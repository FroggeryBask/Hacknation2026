# Plan: Ewelina (wejście, sprawdzenia, wyniki)

Zakres z [podzial-pracy.md](podzial-pracy.md), kroki 2, 4 i 5 z [pipeline.md](pipeline.md). Zasada: **wszystko, co da się zrobić kodem, robi kod** (ten sam plik → ten sam wynik). Model tylko klasyfikuje bloki.

## Co wyszło z przeglądu materiałów (stan `357f7cf`)

| Problem | Skutek | Priorytet |
|---|---|---|
| Skany JPG/PNG to **wszystkie strony sklejone w jeden pionowy obraz** (formularz 1: 1654×4678 = 2 strony, 8: 1654×14034 = 6 stron, 9: 1654×37424 = 16 stron). `downscale` zmniejsza dłuższy bok do 1600 px. | Formularz 9 trafia do modelu jako pasek ~70×1600 px, formularz 1 jako ~565×1600 px. Model nie ma czego przeczytać. | **krytyczny** |
| `.DOC` formularzy 5 i 7 to w środku plik DOCX. `upload.py` odrzuca je jako `MIME_MISMATCH`. | 2 z 9 formularzy w tym formacie nie przechodzą; na obronie może być tak samo. Treść zadania traktuje `.doc` i `.docx` jako jeden typ „DOC”. | **wysoki** |
| Skany idą wyłącznie do modelu wizyjnego (brak OCR). | Wynik niedeterministyczny, wolny (lokalnie model działa w 82% na CPU), a tekst prawny nie może być „wklejony dosłownie”, bo nie mamy tekstu. | **wysoki** |
| PDF: `pypdf` miesza kolejność (formularz 7: sekcja B przed A). | Zła kolejność bloków i pól. | średni |
| `.ods` przez LibreOffice. | Zbędna zależność (ustalenie z mentorami: uważać na licencje). | średni |

## Zadania w kolejności

### 1. Szybkie poprawki (≈1 h)
- **Cięcie wysokich obrazów na strony:** liczba stron `n = round(h / (w·√2))`, cięcie w najjaśniejszym (pustym) wierszu w pobliżu granicy. Każda strona osobno → OCR i ewentualnie model. Test na formularzach 1, 8, 9.
- **`.doc` z zawartością DOCX:** akceptować (rozszerzenie z grupy DOC, zawartość DOCX → `Kind.DOCX`). Test na formularzach 5 i 7.

### 2. Kontrakt Document (≈2–3 h, **odblokowuje Konrada**)
Ustalić z Konradem i zaimplementować w `extract.py`:

```python
Block(id="b001", page=1, kind="paragraph|row|cell|option|heading", text="...", table=(t, r, c) | None)
Candidate(block_id="b014", kind="dots|underscores|checkbox|empty_cell|label_colon")
Document(blocks=[...], candidates=[...], images=[...], notes=[...], source="docx|pdf|ocr|...")
```

- ID nadawane po kolei w kolejności czytania → deterministyczne.
- Do modelu idzie tekst z prefiksami: `[b014] Rasa psa: .....`. Model zwraca tylko ID.
- Kandydaci na pola z wyrażeń regularnych: `\.{5,}`, `_{3,}`, `☐□❑`, glify Wingdings (już w `extract.py`), puste komórki tabel, „Etykieta:” na końcu bloku.
- Źródła: DOCX (już jest kolejność + pola tekstowe), XLSX/ODS (komórki), PDF z tekstem (kolejność z pozycji na stronie: `pypdfium2` daje współrzędne znaków, sortowanie góra→dół, lewo→prawo), skany (OCR, pkt 3).

### 3. OCR deterministyczny dla skanów (≈2–3 h)
- **Tesseract** (Apache-2.0) z danymi `pol`, wywoływany jako osobny proces (`tesseract obraz - -l pol tsv`), więc bez nowej biblioteki Pythona. Wynik TSV ma podział na bloki, akapity i linie ze współrzędnymi → wprost `Block`.
- Docker: `apt-get install tesseract-ocr tesseract-ocr-pol` (Debian, Apache-2.0). Windows lokalnie: instalator UB Mannheim. Do `decisions.md` i README.
- Model wizyjny zostaje tylko jako dodatek (obraz strony obok tekstu z OCR), nie jedyne źródło.
- Skan w PDF: `render_pdf` → ten sam OCR.

### 4. `.ods` bez LibreOffice (≈1 h)
- ODS to ZIP z `content.xml`: `table:table-row` / `table:table-cell`, `table:number-columns-repeated`, `table:covered-table-cell`. Czytać jak XLSX.
- LibreOffice zostaje tylko dla binarnego `.doc`.

### 5. Check i canon (≈2 h, po kontrakcie FormSpec od Konrada)
Czyste funkcje, bez modelu:
- **Kotwice:** każde ID z FormSpec istnieje w Document; inaczej pole odrzucone z ostrzeżeniem.
- **Pokrycie pól:** każdy kandydat ma pole albo rolę `pomiń`.
- **Pokrycie tekstu:** każdy blok ma rolę; nieprzypisane → `TEXT_BLOCK` z ostrzeżeniem (nic nie znika po cichu).
- **Canon:** kolejność wg pozycji bloków, normalizacja etykiet (spacje, dwukropki, kropki), techName z etykiety.
- Liczniki `coverage` do odpowiedzi `?details=true` (kontrakt z Gabrysią).

### 6. Wyniki i testy migawkowe (≈2–3 h, wieczorem)
- Skrypt generujący `wyniki/<nr>.json` + `wyniki/<nr>.spec.json` dla formularzy 2, 3, 4, 6, 7, 8, 9 z najlepszego źródła (DOCX > PDF > skan).
- **Zamrożone FormSpec** w testach: kompilator i linter testowane bez modelu (szybko, za darmo, deterministycznie).
- Test powtarzalności: ten sam plik kilka razy → identyczny Document; ten sam FormSpec → identyczny JSON.
- Ollama: `temperature=0` już jest; dodać stały `seed` w `options` (uzgodnić z Konradem, to `llm.py`).

### 7. Nowy słownik, rozszerzenie II (≈1 h)
- Kandydat: **rasy psów uznawanych za agresywne** (formularz 7, pole „Rasa psa”), lista z rozporządzenia MSWiA z 28.04.2003 – sprawdzić aktualny tekst przed użyciem. Format jak słowniki z materiałów.
- Inne kandydaty do przejrzenia: rodzaj robót w pasie drogowym (6), sposób gromadzenia odpadów (8).

### 8. Oddanie (rano 22.11, przed 11:00)
- Opis i tytuł, wyniki JSON, link do repo i filmu → Hacktribe.
- Pytania do mentorów: cache po hashu pliku, pole „(jeśli dotyczy)” bez pytania sterującego.

## Eden AI a Ollama

- Kod po stronie Eweliny (ekstrakcja, OCR, check, canon) **w ogóle nie używa modelu**: testy na plikach z `materialy/`, za darmo.
- Model potrzebny tylko do kroku 6 (wyniki) i wspólnych testów z Konradem.
