# Cyfryzacja formularzy: research i proponowane podejście

Źródło prawdy: `materialy/` (w tym `0. Treść zadania i regulamin/`, czyli oficjalne PDF-y z hacknation.pl).

## 1. Zadanie w skrócie

Usługa **REST API**, która przyjmuje **jeden plik** z formularzem urzędowym (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) i zwraca **JSON z konfiguracją e-formularza** w formacie importu COI (`importowanyPlikJsonSchemat`). Wzorce to formularze 1 i 5, które mają gotowe pliki `konfiguracja_form_*.json`. Formularze 2, 3, 4, 6, 7, 8 i 9 są do wygenerowania i podlegają ocenie. Na obronie finaliści dostaną **nowe pliki** do przetworzenia na żywo.

**Obowiązkowo:** REST API, JSON zgodny ze strukturą i ze standardami projektowania, dokumentacja architektury, Docker, README.

**Rozszerzenia (dodatkowe punkty):**
- I: słowniki i dane inicjalne (MLPZ/PESEL),
- II: propozycja nowego słownika,
- III: zależności i dynamiczne stany (jsonata), przepływy między stronami,
- IV: frontend do uploadu i podglądu JSON,
- V: renderer e-formularza z JSON,
- VI: walidacje i UX (batch).

**Ocena:** kompletność 30%, intuicyjność 20%, oryginalność 10%, jakość kodu 20%, potencjał wdrożeniowy z kosztem 20%.

**Do oddania:** opis i tytuł, PDF (maks. 10 slajdów), wynikowe pliki JSON, film (maks. 3 min, link), repozytorium.

## 2. Twarde ograniczenia (kolidują z obecnym stackiem)

| Wymaganie | Konsekwencja |
|---|---|
| Język: **Python 3.14+** lub Java 21+ | Backend w Pythonie, a nie w Next.js. |
| **Zakaz LLM dostępnych tylko przez API**, zakaz zewnętrznych API/MCP/SaaS | Model musi działać lokalnie (open-weight). Supabase i Vercel nie mogą być częścią rozwiązania. |
| Tylko open source, **bez copyleft** (AGPL, GPL) | Odpada **PyMuPDF** (AGPL). LibreOffice (MPL-2.0, słaby copyleft) jako zewnętrzny proces trzeba potwierdzić z mentorem. |
| Docker: oficjalny obraz, przypięta wersja (bez `latest`), użytkownik bez uprawnień root, sekrety w runtime | Obraz `python:3.14-slim`. Alpine z PyTorch/OCR na musl jest problematyczny, więc tę decyzję trzeba uzasadnić w README. |
| Walidacja MIME (zawartość = rozszerzenie), nazwa ≤ 250 znaków bez `; : > < / \ \| ' * % $`, konfigurowalny maks. rozmiar | Warstwa walidacji uploadu. |
| Plik tylko w pamięci lub w katalogu tymczasowym | Brak trwałego zapisu i brak bazy na pliki. |
| Konfiguracja: maks. rozmiar, **JWT**, parametry integracyjne | Endpoint z autoryzacją JWT, konfiguracja przez zmienne środowiskowe. |

Next.js może zostać tylko jako opcjonalny frontend (rozszerzenia IV i V), który rozmawia z naszym API. Nie może wołać chmurowych LLM.

## 3. Czy to „jak KSeF”? Częściowo tak

KSeF przyjmuje fakturę **już ustrukturyzowaną** (XML wg schematu FA), waliduje ją względem XSD i reguł biznesowych, a potem zwraca wynik lub błędy. Trudna część naszego zadania, czyli zrozumienie nieustrukturyzowanego, niejednolitego dokumentu, w KSeF nie występuje. Dlatego KSeF nie rozwiązuje problemu wejścia.

Analogia sprawdza się natomiast po **stronie wyjścia**. Warto z niej wziąć trzy rzeczy:
1. **Sztywny schemat i bramka walidacyjna.** JSON Schema plus linter reguł z „Reguł technicznych” (min. 2 strony, strona `FINISH` bez inputów, każde pole w sekcji, brak zagnieżdżonych sekcji, flow łączy strony). Odpowiedź API zawiera listę naruszeń, podobnie jak raport błędów w KSeF.
2. **Stałe bloki jak nagłówek faktury.** Sekcje predefiniowane w „Standardach” (Urząd/Organ, Podmiot wniosku, Twoje dane z MLPZ, Adres, Dane innej osoby, Dane podmiotu, Pełnomocnictwo, Opłata skarbowa, Dane do kontaktu, Zgoda, Podgląd) generujemy **deterministycznie z szablonów**. AI decyduje tylko, *które* z nich są potrzebne, i projektuje strony „przedmiotu wniosku”.
3. **Tryb asynchroniczny z numerem referencyjnym** (jak sesje KSeF) dla batcha (rozszerzenie VI). To opcja, nie trzon.

Wniosek: KSeF jest dobrym wzorcem dla walidacji i kontraktu, ale samo AI musi zrobić „ekstrakcję i projektowanie”.

## 4. Proponowana architektura (hybryda: AI + kompilator deterministyczny)

```
upload ─► walidacja (MIME/nazwa/rozmiar/JWT)
       ─► konwersja: .doc/.ods → LibreOffice headless → docx/xlsx/pdf
       ─► ekstrakcja: Docling (tekst, tabele, layout; OCR dla skanów) + render stron do PNG
       ─► LLM lokalny (Ollama, JSON-schema constrained) → pośredni model „FormSpec”
             (strony → sekcje → pola: etykieta, rodzaj danych, wymagalność, opcje, warunki)
       ─► KOMPILATOR (czysty Python, bez AI) FormSpec → JSON COI:
             sekcje predefiniowane z szablonów, UUID, techName (slug), x/y/rows/cols,
             walidatory z heurystyk (PESEL/NIP/REGON/kod/email), mapowanie MLPZ/PESEL,
             słowniki (Kraje, TERYT_*), jsonata `states` z szablonów zapytań, flow.links
       ─► LINTER (JSON Schema + reguły) → jeśli błędy: naprawa (deterministyczna lub 1 retry LLM)
       ─► odpowiedź: { form: <JSON COI>, warnings: [...] }
```

**Dlaczego tak:**
- Mały lokalny model nie wygeneruje niezawodnie 1700 linii JSON z UUID-ami i jsonatą. Za to dobrze wypełni krótki FormSpec.
- Resztę robi kod, który jest testowalny (jakość kodu 20%), tani (koszt 20%) i powtarzalny na obronie.
- Lekcja z podobnych wdrożeń (Health Samurai: PDF → FHIR Questionnaire): długi JSON z LLM się „sypie” (ucięcia, duplikaty), więc lepiej generować krótko i składać kodem, a na końcu walidować i zostawić człowieka w pętli.

**Kandydaci technologiczni (licencje do potwierdzenia przy wyborze):**
- Parsowanie: **Docling** (MIT, deklaruje Python 3.14; PDF, DOCX, XLSX, obrazy, OCR przez RapidOCR/Tesseract/EasyOCR). `pdfplumber` (MIT) jako alternatywa. **Nie PyMuPDF.**
- LLM/VLM lokalnie: **Qwen3-VL** (Apache 2.0, 2B–235B, mocny w OCR i dokumentach); wariant 4B lub 8B ze względu na koszt. Alternatywa: Mistral/Pixtral 12B (Apache 2.0). Polski trzeba przetestować na naszych formularzach. Unikać modeli z licencją „community” (Llama, Gemma), bo nie są to licencje OSI.
- Serwowanie: **Ollama** (MIT, parametr `format` z JSON Schema = constrained decoding) albo llama.cpp z gramatyką.
- API: FastAPI + Pydantic (MIT), PyJWT (MIT), `filetype` lub `python-magic` do MIME.
- Jsonata (walidacja wygenerowanych `states`): sprawdzić licencję biblioteki Pythona przed użyciem.

## 5. Niespójności w materiałach (dopytać mentorów COI)

1. Schemat ma klucz `repetingSectionGrid` (literówka), a przykładowe JSON-y używają `repeatingSectionGrid`, i to także dla zwykłych sekcji `SECTION`. **Trzymamy się przykładów.**
2. Reguły mówią, że na stronie `FINISH` może być wyłącznie `INFO_SECTION`, a przykłady mają tam `TEXT_BLOCK` (`podglad_1`).
3. Dokument „Słowniki” podaje Województwo/Powiat/Gmina/Miejscowość, a przykłady i „Standardy” używają `TERYT_4G_DOWODOWY` / `TERYT_DOWODOWY`.
4. Numeracja rozszerzeń: w kryteriach „Punkt V = Walidacje pól”, a w 3.3 V to wizualizacja, a VI to walidacje.
5. Twoje dane: „Standardy” wskazują MLPZ, a przykład 5 używa `PESEL.*`.
6. Czy LibreOffice (MPL-2.0) jako zewnętrzne narzędzie konwersji jest akceptowalny?
7. Na jakim sprzęcie jest obrona (CPU czy GPU)? Od tego zależy rozmiar modelu.

## Źródła
- Treść zadania i regulaminy: `materialy/0. Treść zadania i regulamin/` (z https://hacknation.pl/zadania)
- Health Samurai, „From paper form to FHIR”: https://www.health-samurai.io/articles/from-paper-form-to-fhir
- Docling na PyPI: https://pypi.org/project/docling/2.94.0/
- Ollama, structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Przegląd VLM do dokumentów: https://www.llamaindex.ai/insights/best-vision-language-models, https://dev.to/jovan_chan_9500711396d4e6/open-source-vision-language-models-2026-which-to-self-host-3b77
