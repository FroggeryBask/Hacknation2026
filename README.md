# formgen: cyfryzacja formularzy

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
# w .env ustaw FORMGEN_JWT_SECRET, np.: python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

- API: http://localhost:8000 (dokumentacja OpenAPI: http://localhost:8000/docs)
- Frontend: http://localhost:3000
- Usługa `model` przy pierwszym starcie pobiera model (~6 GB) do wolumenu `ollama`.
- GPU: odkomentuj blok `deploy` w `docker-compose.yml`.

### Budowanie obrazów osobno

```bash
docker build -t formgen-api:0.1.0 ./api                               # z LibreOffice (obsługa .doc i .ods)
docker build -t formgen-api:0.1.0-slim --build-arg WITH_LIBREOFFICE=0 ./api
docker build -t formgen-web:0.1.0 -f Dockerfile.web .
docker run --rm -p 8000:8000 -e FORMGEN_JWT_SECRET=... -e FORMGEN_OLLAMA_URL=http://host.docker.internal:11434 formgen-api:0.1.0
```

Obrazy bazują na oficjalnych obrazach z przypiętą wersją (`python:3.14.10-slim-trixie`, `node:22.23.5-alpine3.24`, `ollama/ollama:0.40.17`). Procesy działają na użytkowniku bez uprawnień administratora, a sekrety są podawane dopiero przy uruchomieniu.

## Konfiguracja

Zmienne środowiskowe API (prefiks `FORMGEN_`). Pełna lista z wartościami domyślnymi jest w [.env.example](.env.example).

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `FORMGEN_JWT_SECRET` | brak (wymagany) | Klucz HS256 do weryfikacji tokenów JWT |
| `FORMGEN_AUTH_ENABLED` | `true` | `false` wyłącza JWT (tylko do lokalnego developmentu) |
| `FORMGEN_JWT_ALGORITHM` / `FORMGEN_JWT_AUDIENCE` | `HS256` / brak | Parametry weryfikacji tokenu |
| `FORMGEN_MAX_UPLOAD_MB` | `20` | Maksymalny rozmiar pliku |
| `FORMGEN_OLLAMA_URL` | `http://localhost:11434` | Adres serwera modelu |
| `FORMGEN_LLM_MODEL` | `qwen3-vl:8b` | Model (dowolny model wizyjny z Ollama) |
| `FORMGEN_LLM_TIMEOUT_S` | `600` | Limit czasu odpowiedzi modelu |
| `FORMGEN_MAX_PDF_PAGES` | `6` | Ile stron zeskanowanego PDF przekazać modelowi |
| `FORMGEN_SOFFICE_BIN` | `soffice` | Ścieżka do LibreOffice (pliki .doc i .ods) |
| `FORMGEN_CORS_ORIGINS` | `http://localhost:3000` | Dozwolone adresy frontendu |

## REST API

Wszystkie endpointy `/api/v1/*` wymagają nagłówka `Authorization: Bearer <JWT>`. Token testowy: `cd api && uv run formgen-token`.

| Metoda i ścieżka | Opis |
|---|---|
| `POST /api/v1/forms` | `multipart/form-data`, pole `file`: jeden plik formularza. Zwraca JSON formularza gotowy do importu. Nagłówki `X-Formgen-Errors` i `X-Formgen-Warnings` podają wynik walidacji reguł. |
| `POST /api/v1/forms?details=true` | Jak wyżej, ale zwraca `{form, spec, issues, notes, sourceFormat}`: formularz, opis pośredni, raport walidacji i uwagi. |
| `POST /api/v1/forms/compile` | Body: FormSpec (JSON). Buduje formularz bez modelu, np. po ręcznej korekcie opisu. |
| `POST /api/v1/forms/validate` | Body: JSON formularza. Zwraca `{valid, issues}` według reguł technicznych. |
| `GET /api/v1/spec/schema` | Schemat JSON opisu pośredniego (FormSpec). |
| `GET /health` | Stan usługi i dostępność modelu (bez autoryzacji). |

Przykład:

```bash
TOKEN=$(cd api && uv run formgen-token)
curl -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.pdf" http://localhost:8000/api/v1/forms -o wniosek.json
```

Błędy mają postać `{"error": {"code": "...", "message": "..."}}`:

| Kod | Kiedy |
|---|---|
| `401` | Brak tokenu albo token jest nieprawidłowy lub wygasły |
| `413 FILE_TOO_LARGE` | Plik jest większy niż `FORMGEN_MAX_UPLOAD_MB` |
| `415 UNSUPPORTED_FORMAT`, `MIME_MISMATCH`, `UNSUPPORTED_CONTENT` | Zły format lub zawartość niezgodna z rozszerzeniem |
| `422 FILENAME_*` | Nazwa dłuższa niż 250 znaków albo zawiera `; : > < / \ \| ' * % $` |
| `503 LLM_UNAVAILABLE`, `CONVERTER_MISSING` | Brak modelu albo brak LibreOffice |

## Development

Wymagane: Node.js 22+, [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com) i LibreOffice (do plików .doc i .ods).

```bash
npm install
cp .env.example .env.local          # frontend
cp .env.example api/.env            # API (FORMGEN_AUTH_ENABLED=false do testów lokalnych)
ollama pull qwen3-vl:8b
cd api && uv sync && uv run uvicorn formgen.main:app --reload   # http://localhost:8000/docs
npm run dev                                                      # http://localhost:3000
```

| Polecenie | Co robi |
|---|---|
| `npm run check` | Biome, TypeScript, ruff i pytest (API i skrypty). Uruchamia się też przed każdym pushem. |
| `cd api && uv run pytest` | Testy API, w tym porównanie z referencyjnymi JSON-ami COI |
| `npm run smoke [url]` | Sprawdza, czy kluczowe strony frontendu odpowiadają |
| `npx shadcn@latest add <name>` | Dodaje komponent UI |

Struktura repozytorium:
- `api/`: rozwiązanie (Python 3.14, FastAPI),
- `src/`: frontend (Next.js) z design systemem formularzy,
- `materialy/`: materiały zadania,
- `docs/`: decyzje i research.

Zasady zespołu: brak atrybucji AI w commitach (hook to blokuje), nigdy nie commituj plików `.env`, a wszystkie zależności muszą mieć licencję open source bez copyleft (szczegóły w [CLAUDE.md](CLAUDE.md)).
