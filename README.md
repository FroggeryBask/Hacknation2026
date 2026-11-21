# autoformularz: cyfryzacja formularzy

Usługa REST, która zamienia plik formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) na konfigurację formularza e-usługi w formacie JSON, gotową do importu w Generatorze Formularzy. Zadanie COI, HackNation 2026.

Docelowo działa w całości lokalnie: model językowy (Qwen3-VL, Apache-2.0) jest uruchamiany przez Ollama, bez zewnętrznych API. Na czas demo (uzgodnione z mentorami COI) zamiast lokalnego modelu można użyć modelu open-weight z Eden AI udostępnionego przez organizatorów.

## Jak to działa

```
plik ─► walidacja (nazwa, rozmiar, MIME z zawartości) ─► odczyt (tekst w kolejności dokumentu / obrazy stron)
     ─► lokalny model: opis formularza (FormSpec, odpowiedź wymuszona schematem JSON)
     ─► kompilator: JSON w formacie COI (sekcje standardowe, walidatory, słowniki, dane inicjalne, warunki jsonata, przejścia)
     ─► walidator reguł technicznych ─► odpowiedź
```

Model opisuje tylko to, czego dotyczy formularz. Sekcje wspólne dla wszystkich wniosków (urząd, wnioskodawca, adres, pełnomocnictwo, opłata skarbowa, kontakt, zgoda, podgląd) buduje deterministyczny kompilator według standardu projektowania formularzy. Dzięki temu wynik jest powtarzalny i zawsze zgodny ze strukturą importu. **Dokumentacja architektury: [docs/architektura.md](docs/architektura.md)** (komponenty, przepływ, bezpieczeństwo, koszt, licencje). Kroki przetwarzania: [docs/pipeline.md](docs/pipeline.md), decyzje: [docs/decisions.md](docs/decisions.md), research: [docs/research-cyfryzacja-formularzy.md](docs/research-cyfryzacja-formularzy.md).

## Uruchomienie (Docker)

Działa tak samo na Windows, macOS (Intel i Apple Silicon) i Linuksie (x86_64 i ARM64): obrazy bazowe są wieloarchitekturowe, a wszystkie skompilowane zależności mają wersje dla obu architektur. Potrzebny jest Docker Desktop (Windows, macOS) albo Docker Engine z wtyczką Compose **2.24 lub nowszą** (Linux).

### 1. Konfiguracja

Skopiuj plik z przykładowymi ustawieniami:

```bash
cp .env.example .env                 # macOS, Linux
Copy-Item .env.example .env          # Windows (PowerShell)
```

W `.env` ustaw `AUTOFORMULARZ_JWT_SECRET`. Losowy klucz wygenerujesz na każdym systemie samym Dockerem:

```bash
docker run --rm python:3.14.10-slim-trixie python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Zapisz `.env` jako UTF-8 bez BOM (domyślnie tak robią VS Code i Notatnik w Windows 11).

### 2a. Demo z Eden AI (na czas hackatonu)

Model open-weight w chmurze organizatorów (`deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct`): bez pobierania ~6 GB modelu i bez wymagań pamięci dla modelu. W `.env` dopisz klucz zespołu `EDENAI_API_KEY=...`, potem:

```bash
docker compose -f docker-compose.yml -f docker-compose.eden.yml up --build
```

- Startują tylko `api` i `web`; nakładka `docker-compose.eden.yml` wyłącza `ollama` i `model`. Klucz dostaje tylko `api`, nigdy `web`.
- `GET /health` pokazuje `"provider": "eden"`, `"configured"` (czy jest klucz i model) i `"usage"`: liczbę zapytań i koszt w USD od startu kontenera.
- Każde zapytanie kosztuje (wspólny budżet zespołu, [docs/eden-budzet.md](docs/eden-budzet.md)). Bez klucza żądania kończą się błędem `LLM_MISCONFIGURED` i nic nie jest wysyłane.

### 2b. W pełni lokalnie (Ollama, wersja docelowa)

```bash
docker compose up --build
```

- Usługa `model` przy pierwszym starcie pobiera model (~6 GB) do wolumenu `ollama`; `api` startuje dopiero po pobraniu.
- Wymagania pamięci: patrz [Wymagania sprzętowe i czasy](#wymagania-sprzętowe-i-czasy).
- GPU NVIDIA (Linux, Windows z WSL2): odkomentuj blok `deploy` w `docker-compose.yml`. Docker na macOS nie daje kontenerom dostępu do GPU, więc tam model liczy się na CPU.

### 3. Adresy i zatrzymanie

- API: http://localhost:8000 (dokumentacja OpenAPI: http://localhost:8000/docs)
- Frontend: http://localhost:3000
- Zatrzymanie: `docker compose down` (z tymi samymi `-f`, jeśli startowało z Eden). `docker compose down -v` usuwa też pobrany model.

### Wymagania sprzętowe i czasy

| Zasób | Eden AI (2a) | Ollama (2b) |
|---|---|---|
| Pamięć RAM dla Dockera | bez modelu: tylko API i frontend | **min. 10 GB, zalecane 12 GB** (`qwen3-vl:8b` ~6,2 GB + kontekst 16k ~2,3 GB + API i frontend) |
| Dysk | obrazy `api` i `web` | obrazy + model ~6,2 GB |
| Sieć | przy budowaniu obrazów i przy każdym zapytaniu | tylko przy pierwszym starcie (obrazy, pakiety, model); potem działa bez internetu |

**Docker Desktop na Windows (WSL2)** domyślnie daje kontenerom połowę RAM. Na laptopie z 16 GB to ok. 7,6 GB, czyli za mało dla modelu 8B. Zwiększ limit w `C:\Users\<użytkownik>\.wslconfig`:

```
[wsl2]
memory=12GB
```

i uruchom ponownie WSL (`wsl --shutdown`) oraz Docker Desktop. Na macOS limit pamięci ustawia się w Docker Desktop (Settings → Resources). Na słabszej maszynie użyj mniejszego modelu (`AUTOFORMULARZ_LLM_MODEL=qwen3-vl:4b` w `.env`, słabsza jakość) albo zmniejsz `AUTOFORMULARZ_LLM_NUM_CTX`.

Czas pierwszego startu zależy głównie od łącza: sam model to ~6 GB (ok. 1 min przy 1 Gb/s, ok. 9 min przy 100 Mb/s). Pomiar od zera na laptopie (i5-11300H, 16 GB RAM, Docker Desktop na WSL2) przerwaliśmy na etapie budowania obrazów: przy łączu ok. 100 kB/s sama instalacja LibreOffice trwała ponad 13 minut. **Czasy odpowiedzi modelu w Dockerze nie są jeszcze zmierzone.**

### Budowanie obrazów osobno

```bash
docker build -t autoformularz-api:0.1.0 ./api                               # z LibreOffice (obsługa .doc)
docker build -t autoformularz-api:0.1.0-slim --build-arg WITH_LIBREOFFICE=0 ./api
docker build -t autoformularz-web:0.1.0 -f Dockerfile.web .
docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway \
  -e AUTOFORMULARZ_JWT_SECRET=... -e AUTOFORMULARZ_OLLAMA_URL=http://host.docker.internal:11434 autoformularz-api:0.1.0
```

`--add-host` jest potrzebne na Linuksie (Docker Desktop na Windows i macOS zna `host.docker.internal` sam). Obrazy bazują na oficjalnych obrazach z przypiętą wersją (`python:3.14.10-slim-trixie`, `node:22.23.5-alpine3.24`, `ollama/ollama:0.40.17`). Procesy `api` i `web` działają na użytkowniku bez uprawnień administratora, a sekrety są podawane dopiero przy uruchomieniu.

### Gdy coś nie działa

| Objaw | Przyczyna i rozwiązanie |
|---|---|
| `429 Too Many Requests` przy budowaniu | limit pobrań z Docker Hub bez logowania; `docker login` (darmowe konto) albo odczekaj |
| `failed to connect to the docker API` | Docker Desktop nie jest uruchomiony |
| `depends_on` / `!reset` w błędzie Compose | za stara wtyczka Compose; potrzebna 2.24+ (`docker compose version`) |
| `/health`: `"configured": false` (Eden) | brak `EDENAI_API_KEY` w `.env` albo kontener uruchomiony przed jego dopisaniem (`docker compose ... up -d` ponownie) |
| kontener `ollama` kończy się bez błędu, model się nie ładuje | za mało pamięci dla Dockera, patrz wyżej |
| port 8000 lub 3000 zajęty | zatrzymaj lokalne `uvicorn` / `npm run dev` albo zmień port w `docker-compose.yml` |

## Licencje

Kod projektu: MIT. Wszystkie zależności są open source i nie wymagają udostępnienia naszego kodu: biblioteki MIT, BSD, Apache-2.0, ISC; model Qwen3-VL i Tesseract na Apache-2.0; Ollama na MIT. LibreOffice (MPL-2.0) działa jako osobny proces tylko do konwersji .doc, bez linkowania i bez zmian. Pełna tabela i uzasadnienie: [docs/architektura.md, „Licencje”](docs/architektura.md#7-licencje).

## Konfiguracja

Zmienne środowiskowe API (prefiks `AUTOFORMULARZ_`). Pełna lista z wartościami domyślnymi jest w [.env.example](.env.example).

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `AUTOFORMULARZ_JWT_SECRET` | brak (wymagany) | Klucz HS256 do weryfikacji tokenów JWT |
| `AUTOFORMULARZ_AUTH_ENABLED` | `true` | `false` wyłącza JWT (tylko do lokalnego developmentu) |
| `AUTOFORMULARZ_JWT_ALGORITHM` / `AUTOFORMULARZ_JWT_AUDIENCE` | `HS256` / brak | Parametry weryfikacji tokenu |
| `AUTOFORMULARZ_MAX_UPLOAD_MB` | `20` | Maksymalny rozmiar pliku |
| `AUTOFORMULARZ_OLLAMA_URL` | `http://localhost:11434` | Adres serwera modelu |
| `AUTOFORMULARZ_LLM_MODEL` | `qwen3-vl:8b` | Model (dowolny model wizyjny z Ollama) |
| `AUTOFORMULARZ_LLM_PROVIDER` | `ollama` | `eden` włącza Eden AI (lokalnie albo w Dockerze przez `docker-compose.eden.yml`, patrz [Model językowy](#model-językowy-ollama-domyślnie-albo-eden-ai-opcjonalnie)) |
| `AUTOFORMULARZ_EDEN_MODEL` / `EDENAI_API_KEY` | brak | Model i klucz Eden AI, potrzebne tylko przy `eden` |
| `AUTOFORMULARZ_LLM_TIMEOUT_S` | `600` | Limit czasu odpowiedzi modelu |
| `AUTOFORMULARZ_LLM_NUM_CTX` | `16384` | Okno kontekstu modelu w Ollamie (więcej = więcej pamięci RAM/VRAM) |
| `AUTOFORMULARZ_LLM_MAX_TOKENS` | `8000` | Maksymalna długość odpowiedzi modelu; dłuższa (zwykle zapętlenie) kończy się błędem `LLM_TRUNCATED` bez ponawiania |
| `AUTOFORMULARZ_MAX_PDF_PAGES` | `6` | Ile stron skanu (PDF lub obraz) przekazać modelowi jako obrazy; OCR czyta wszystkie strony (do 30) |
| `AUTOFORMULARZ_SOFFICE_BIN` | `soffice` | Ścieżka do LibreOffice (pliki .doc; .ods jest czytany bez niego) |
| `AUTOFORMULARZ_OCR_BIN` / `AUTOFORMULARZ_OCR_LANG` | `tesseract` / `pol` | OCR skanów (Tesseract, w obrazie Docker). Bez niego skan trafia do modelu tylko jako obraz |
| `AUTOFORMULARZ_TESSDATA_DIR` | brak | Katalog z `pol.traineddata`, jeśli nie ma go w domyślnym `tessdata` (np. instalator na Windows) |
| `AUTOFORMULARZ_COPY_SOURCE_TEXT` | `false` | Kopiuje pouczenia i podstawę prawną dosłownie ze źródła na stronę końcową (wyłączone, dopóki role bloków od modelu nie są wiarygodne) |
| `AUTOFORMULARZ_CORS_ORIGINS` | `http://localhost:3000` | Dozwolone adresy frontendu |

## REST API

Wszystkie endpointy `/api/v1/*` wymagają nagłówka `Authorization: Bearer <JWT>`. Token testowy: `cd api && uv run autoformularz-token`.

| Metoda i ścieżka | Opis |
|---|---|
| `POST /api/v1/forms` | `multipart/form-data`, pole `file`: jeden plik formularza. Zwraca JSON formularza gotowy do importu. Nagłówki `X-Autoformularz-Errors` i `X-Autoformularz-Warnings` podają wynik walidacji reguł. |
| `POST /api/v1/forms?details=true` | Jak wyżej, ale zwraca `{form, spec, issues, notes, sourceFormat}`: formularz, opis pośredni, raport walidacji i uwagi. |
| `POST /api/v1/forms/compile` | Body: FormSpec (JSON). Buduje formularz bez modelu, np. po ręcznej korekcie opisu. |
| `POST /api/v1/forms/validate` | Body: JSON formularza. Zwraca `{valid, issues}` według reguł technicznych. |
| `GET /api/v1/spec/schema` | Schemat JSON opisu pośredniego (FormSpec). |
| `GET /health` | Stan usługi i dostępność modelu (bez autoryzacji). |

Przykład:

```bash
TOKEN=$(cd api && uv run autoformularz-token)
curl -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.pdf" http://localhost:8000/api/v1/forms -o wniosek.json
```

Błędy mają postać `{"error": {"code": "...", "message": "..."}}`:

| Kod | Kiedy |
|---|---|
| `401` | Brak tokenu albo token jest nieprawidłowy lub wygasły |
| `413 FILE_TOO_LARGE` | Plik jest większy niż `AUTOFORMULARZ_MAX_UPLOAD_MB` |
| `415 UNSUPPORTED_FORMAT`, `MIME_MISMATCH`, `UNSUPPORTED_CONTENT` | Zły format lub zawartość niezgodna z rozszerzeniem |
| `422 FILENAME_*` | Nazwa dłuższa niż 250 znaków albo zawiera `; : > < / \ \| ' * % $` |
| `503 LLM_UNAVAILABLE`, `CONVERTER_MISSING` | Brak modelu albo brak LibreOffice |
| `500 LLM_MISCONFIGURED` | `AUTOFORMULARZ_LLM_PROVIDER=eden` bez `EDENAI_API_KEY` lub `AUTOFORMULARZ_EDEN_MODEL` (tylko dev) |

## Development

Wymagane: Node.js 22+, [uv](https://docs.astral.sh/uv/), LibreOffice (do plików .doc) i Tesseract z językiem polskim (OCR skanów; Windows: `winget install UB-Mannheim.TesseractOCR`, potem `pol.traineddata` z [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) do katalogu z `AUTOFORMULARZ_TESSDATA_DIR`). [Ollama](https://ollama.com) jest potrzebna tylko wtedy, gdy nie używasz Eden AI.

#### Pliki konfiguracyjne

| Plik | Kto go czyta | Do czego |
|---|---|---|
| `.env.local` (katalog główny) | `npm run dev` i API uruchomione z `api/` | praca lokalna: jeden plik dla frontendu i API |
| `.env` (katalog główny) | `docker compose` | Docker: wystarczy `AUTOFORMULARZ_JWT_SECRET` |
| `api/.env` | API uruchomione z `api/` | opcjonalnie: nadpisuje `.env.local`, trzymaj tam tylko świadome nadpisania |

Pliki `.env*` są poza gitem (oprócz `.env.example`). Nie commituj ich.

#### Uruchomienie lokalne

1. Zainstaluj zależności:
   ```bash
   npm install
   cd api && uv sync && cd ..
   ```
2. Skopiuj konfigurację: `cp .env.example .env.local`. W `.env.local` ustaw `AUTOFORMULARZ_AUTH_ENABLED=false`, żeby testować bez tokenów.
3. Wybierz model:
   - **Ollama (domyślnie):** `ollama pull qwen3-vl:8b` i zostaw `AUTOFORMULARZ_LLM_PROVIDER=ollama`;
   - **Eden AI (szybciej):** w `.env.local` ustaw `AUTOFORMULARZ_LLM_PROVIDER=eden`, `AUTOFORMULARZ_EDEN_MODEL` i `EDENAI_API_KEY` (patrz [Model językowy](#model-językowy-ollama-domyślnie-albo-eden-ai-opcjonalnie)).
4. Uruchom API **z katalogu `api/`** (ścieżka `../.env.local` jest liczona od bieżącego katalogu):
   ```bash
   cd api && uv run uvicorn autoformularz.main:app --reload   # http://localhost:8000/docs
   ```
5. Sprawdź stan: `curl http://localhost:8000/health`. Pole `llm.provider` pokazuje, który model jest używany.
6. Opcjonalnie uruchom frontend (w drugim terminalu, z katalogu głównego): `npm run dev` (http://localhost:3000).
7. Wyślij formularz:
   ```bash
   curl -i -F "file=@materialy/<katalog>/<plik>.docx" "http://localhost:8000/api/v1/forms?details=true"
   ```
   Przy włączonym JWT dodaj `-H "Authorization: Bearer $(cd api && uv run autoformularz-token)"`. Nagłówek `X-Autoformularz-Errors: 0` oznacza, że wynik przeszedł walidację reguł.

| Polecenie | Co robi |
|---|---|
| `npm run check` | Biome, TypeScript, ruff i pytest (API i skrypty). Uruchamia się też przed każdym pushem. |
| `cd api && uv run pytest` | Testy API, w tym porównanie z referencyjnymi JSON-ami COI |
| `npm run smoke [url]` | Sprawdza, czy kluczowe strony frontendu odpowiadają |
| `npx shadcn@latest add <name>` | Dodaje komponent UI |

### Model językowy: Ollama (domyślnie) albo Eden AI (opcjonalnie)

Domyślnie API używa lokalnego modelu przez Ollamę (`AUTOFORMULARZ_LLM_PROVIDER=ollama`). Tak działa oddawane rozwiązanie i nie trzeba nic ustawiać.

Na czas hackatonu można włączyć Eden AI: model open-weight w chmurze organizatorów odpowiada w kilka sekund, a lokalna Ollama na CPU potrzebuje kilku minut. Tryb do pracy lokalnej i do demo (uzgodnione z mentorami COI). W Dockerze: [2a. Demo z Eden AI](#2a-demo-z-eden-ai-na-czas-hackatonu).

**Włączenie.** Dopisz do `api/.env` albo do `.env.local` w katalogu głównym:

```bash
AUTOFORMULARZ_LLM_PROVIDER=eden
AUTOFORMULARZ_EDEN_MODEL=deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct  # odpowiednik w Ollamie: qwen3-vl:30b
EDENAI_API_KEY=...                                          # klucz zespołu, tylko po stronie serwera
```

Uruchom API (`cd api && uv run uvicorn autoformularz.main:app --reload`). `GET /health` pokaże `"provider": "eden"` i `"configured": true`, a w logu pojawi się ostrzeżenie o trybie demo i kosztach. Bez klucza lub modelu żądania kończą się błędem `LLM_MISCONFIGURED`.

**Wyłączenie.** Usuń `AUTOFORMULARZ_LLM_PROVIDER` albo ustaw go na `ollama` i zrestartuj API. Potrzebny jest wtedy model w Ollamie: `ollama pull qwen3-vl:8b`.

Kolejność: `api/.env` nadpisuje `.env.local`, a zmienne środowiskowe nadpisują oba pliki. Sam `docker-compose.yml` wymusza Ollamę (`AUTOFORMULARZ_LLM_PROVIDER=ollama` i pusty `EDENAI_API_KEY`); Eden w Dockerze włącza tylko jawna nakładka `docker-compose.eden.yml`. Przez Eden używaj wyłącznie modeli open-weight, które da się uruchomić w Ollamie (bez GPT, Gemini, Claude).

Struktura repozytorium:
- `api/`: rozwiązanie (Python 3.14, FastAPI),
- `src/`: frontend (Next.js) z design systemem formularzy,
- `materialy/`: materiały zadania,
- `docs/`: decyzje i research; wyjaśnienia niespójności w materiałach: [docs/wyjasnienia-materialow.md](docs/wyjasnienia-materialow.md).

Zasady zespołu: brak atrybucji AI w commitach (hook to blokuje), nigdy nie commituj plików `.env`, a wszystkie zależności muszą mieć licencję open source bez copyleft (szczegóły w [CLAUDE.md](CLAUDE.md)).
