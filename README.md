# autoformularz: cyfryzacja formularzy

Usługa REST, która zamienia plik formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) na konfigurację formularza e-usługi w formacie JSON, gotową do importu w Generatorze Formularzy. Zadanie COI, HackNation 2026.

Działa w całości lokalnie: model językowy (Qwen3-VL, Apache-2.0) jest uruchamiany przez Ollama. Rozwiązanie nie korzysta z zewnętrznych API.

## Jak to działa

```
plik ─► walidacja (nazwa, rozmiar, MIME z zawartości) ─► odczyt (tekst w kolejności dokumentu / obrazy stron)
     ─► lokalny model: opis formularza (FormSpec, odpowiedź wymuszona schematem JSON)
     ─► kompilator: JSON w formacie COI (sekcje standardowe, walidatory, słowniki, dane inicjalne, warunki jsonata, przejścia)
     ─► walidator reguł technicznych ─► odpowiedź
```

Model opisuje tylko to, czego dotyczy formularz. Sekcje wspólne dla wszystkich wniosków (urząd, wnioskodawca, adres, pełnomocnictwo, opłata skarbowa, kontakt, zgoda, podgląd) buduje deterministyczny kompilator według standardu projektowania formularzy. Dzięki temu wynik jest powtarzalny i zawsze zgodny ze strukturą importu. Szczegóły: [docs/research-cyfryzacja-formularzy.md](docs/research-cyfryzacja-formularzy.md) i [docs/decisions.md](docs/decisions.md).

## Uruchomienie (Docker)

Wymagany Docker z Compose. Do szybkiego działania modelu zalecana karta graficzna NVIDIA. Na samym procesorze model też działa, ale wolniej.

```bash
cp .env.example .env
# w .env ustaw AUTOFORMULARZ_JWT_SECRET, np.: python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

- API: http://localhost:8000 (dokumentacja OpenAPI: http://localhost:8000/docs)
- Frontend: http://localhost:3000
- Usługa `model` przy pierwszym starcie pobiera model (~6 GB) do wolumenu `ollama`.
- GPU: odkomentuj blok `deploy` w `docker-compose.yml`.

### Budowanie obrazów osobno

```bash
docker build -t autoformularz-api:0.1.0 ./api                               # z LibreOffice (obsługa .doc i .ods)
docker build -t autoformularz-api:0.1.0-slim --build-arg WITH_LIBREOFFICE=0 ./api
docker build -t autoformularz-web:0.1.0 -f Dockerfile.web .
docker run --rm -p 8000:8000 -e AUTOFORMULARZ_JWT_SECRET=... -e AUTOFORMULARZ_OLLAMA_URL=http://host.docker.internal:11434 autoformularz-api:0.1.0
```

Obrazy bazują na oficjalnych obrazach z przypiętą wersją (`python:3.14.10-slim-trixie`, `node:22.23.5-alpine3.24`, `ollama/ollama:0.40.17`). Procesy działają na użytkowniku bez uprawnień administratora, a sekrety są podawane dopiero przy uruchomieniu.

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
| `AUTOFORMULARZ_LLM_PROVIDER` | `ollama` | `eden` włącza Eden AI, tylko lokalnie (patrz [Model językowy](#model-językowy-ollama-domyślnie-albo-eden-ai-opcjonalnie)) |
| `AUTOFORMULARZ_EDEN_MODEL` / `EDENAI_API_KEY` | brak | Model i klucz Eden AI, potrzebne tylko przy `eden` |
| `AUTOFORMULARZ_LLM_TIMEOUT_S` | `600` | Limit czasu odpowiedzi modelu |
| `AUTOFORMULARZ_MAX_PDF_PAGES` | `6` | Ile stron skanu (PDF lub obraz) przekazać modelowi jako obrazy; OCR czyta wszystkie strony (do 30) |
| `AUTOFORMULARZ_SOFFICE_BIN` | `soffice` | Ścieżka do LibreOffice (pliki .doc i .ods) |
| `AUTOFORMULARZ_OCR_BIN` / `AUTOFORMULARZ_OCR_LANG` | `tesseract` / `pol` | OCR skanów (Tesseract, w obrazie Docker). Bez niego skan trafia do modelu tylko jako obraz |
| `AUTOFORMULARZ_TESSDATA_DIR` | brak | Katalog z `pol.traineddata`, jeśli nie ma go w domyślnym `tessdata` (np. instalator na Windows) |
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

Wymagane: Node.js 22+, [uv](https://docs.astral.sh/uv/), LibreOffice (do plików .doc i .ods) i Tesseract z językiem polskim (OCR skanów; Windows: `winget install UB-Mannheim.TesseractOCR`, potem `pol.traineddata` z [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) do katalogu z `AUTOFORMULARZ_TESSDATA_DIR`). [Ollama](https://ollama.com) jest potrzebna tylko wtedy, gdy nie używasz Eden AI.

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

Na czas hackatonu można włączyć Eden AI: model open-weight w chmurze organizatorów odpowiada w kilka sekund, a lokalna Ollama na CPU potrzebuje kilku minut. To tylko tryb do pracy lokalnej.

**Włączenie.** Dopisz do `api/.env` albo do `.env.local` w katalogu głównym:

```bash
AUTOFORMULARZ_LLM_PROVIDER=eden
AUTOFORMULARZ_EDEN_MODEL=deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct  # odpowiednik w Ollamie: qwen3-vl:30b
EDENAI_API_KEY=...                                          # klucz zespołu, tylko po stronie serwera
```

Uruchom API (`cd api && uv run uvicorn autoformularz.main:app --reload`). `GET /health` pokaże `"provider": "eden"` i `"configured": true`, a w logu pojawi się ostrzeżenie o trybie deweloperskim. Bez klucza lub modelu żądania kończą się błędem `LLM_MISCONFIGURED`.

**Wyłączenie.** Usuń `AUTOFORMULARZ_LLM_PROVIDER` albo ustaw go na `ollama` i zrestartuj API. Potrzebny jest wtedy model w Ollamie: `ollama pull qwen3-vl:8b`.

Kolejność: `api/.env` nadpisuje `.env.local`, a zmienne środowiskowe nadpisują oba pliki. `docker compose` zawsze wymusza Ollamę (`AUTOFORMULARZ_LLM_PROVIDER=ollama` i pusty `EDENAI_API_KEY`), więc Eden nie trafi do oddawanego rozwiązania. Przez Eden używaj wyłącznie modeli open-weight, które da się uruchomić w Ollamie (bez GPT, Gemini, Claude).

Struktura repozytorium:
- `api/`: rozwiązanie (Python 3.14, FastAPI),
- `src/`: frontend (Next.js) z design systemem formularzy,
- `materialy/`: materiały zadania,
- `docs/`: decyzje i research; wyjaśnienia niespójności w materiałach: [docs/wyjasnienia-materialow.md](docs/wyjasnienia-materialow.md).

Zasady zespołu: brak atrybucji AI w commitach (hook to blokuje), nigdy nie commituj plików `.env`, a wszystkie zależności muszą mieć licencję open source bez copyleft (szczegóły w [CLAUDE.md](CLAUDE.md)).
