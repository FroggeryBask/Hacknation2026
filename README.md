# autoformularz: cyfryzacja formularzy

Usługa REST, która zamienia plik formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) na konfigurację formularza e-usługi w formacie JSON, gotową do importu w Generatorze Formularzy. Zadanie COI, HackNation 2026.

Model językowy to domyślnie model open-weight (Qwen3-VL) na Eden AI, udostępniony przez organizatorów. Ten sam rodzaj modelu (Qwen3-VL, Apache-2.0) można uruchomić w całości lokalnie przez Ollamę, bez zewnętrznych API (tryb offline).

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

### 2a. Eden AI (domyślnie)

Model open-weight w chmurze organizatorów (`deepinfra/deepseek-ai/DeepSeek-V4.1-Flash`): bez pobierania ~6 GB modelu i bez wymagań pamięci dla modelu. W `.env` dopisz klucz zespołu `EDENAI_API_KEY=...`, potem:

```bash
docker compose up --build
```

- Startują tylko `api` i `web`; `ollama` i `model` są w profilu `ollama` i bez niego się nie uruchamiają. Klucz dostaje tylko `api`, nigdy `web`.
- `GET /health` pokazuje `"provider": "eden"`, `"configured"` (czy jest klucz i model) i `"usage"`: liczbę zapytań i koszt w USD od startu kontenera.
- Każde zapytanie kosztuje (wspólny budżet zespołu, [docs/eden-budzet.md](docs/eden-budzet.md)). Bez klucza żądania kończą się błędem `LLM_MISCONFIGURED` i nic nie jest wysyłane.

### 2b. W pełni lokalnie (Ollama, offline)

```bash
AUTOFORMULARZ_LLM_PROVIDER=ollama docker compose --profile ollama up --build      # macOS, Linux
```

Na Windows (PowerShell) ustaw w `.env` `AUTOFORMULARZ_LLM_PROVIDER=ollama`, potem `docker compose --profile ollama up --build`.

- Usługa `model` przy pierwszym starcie pobiera model (~6 GB) do wolumenu `ollama`; `api` startuje dopiero po pobraniu.
- Wymagania pamięci: patrz [Wymagania sprzętowe i czasy](#wymagania-sprzętowe-i-czasy).
- GPU NVIDIA (Linux, Windows z WSL2): odkomentuj blok `deploy` w `docker-compose.yml`. Docker na macOS nie daje kontenerom dostępu do GPU, więc tam model liczy się na CPU.

### 3. Adresy i zatrzymanie

- API: http://localhost:8000 (dokumentacja OpenAPI: http://localhost:8000/docs)
- Frontend: http://localhost:3000 (upload jednego albo wielu plików naraz, do 20; każdy plik to osobne zadanie `/api/v1/jobs`, po 2 jednocześnie; podgląd e-formularza i JSON-u, pobieranie pojedynczo albo wszystkich)
- Zatrzymanie: `docker compose down` (z `--profile ollama`, jeśli startowało z Ollamą). `docker compose down -v` usuwa też pobrany model.

### Wymagania sprzętowe i czasy

| Zasób | Eden AI (2a) | Ollama (2b) |
|---|---|---|
| Pamięć RAM dla Dockera | bez modelu: tylko API i frontend | **min. 12 GB** (`qwen3-vl:8b` z kontekstem 24576 zajmuje zmierzone 9,4 GB + API i frontend) |
| Dysk | obrazy `api` i `web` | obrazy + model ~6,2 GB |
| Sieć | przy budowaniu obrazów i przy każdym zapytaniu | tylko przy pierwszym starcie (obrazy, pakiety, model); potem działa bez internetu |

**Docker Desktop na Windows (WSL2)** domyślnie daje kontenerom połowę RAM. Na laptopie z 16 GB to ok. 7,7 GB, czyli za mało dla modelu 8B. Zwiększ limit w `C:\Users\<użytkownik>\.wslconfig`:

```
[wsl2]
memory=12GB
```

i uruchom ponownie WSL (`wsl --shutdown`) oraz Docker Desktop. Na macOS limit pamięci ustawia się w Docker Desktop (Settings → Resources). Na słabszej maszynie użyj mniejszego modelu (`AUTOFORMULARZ_LLM_MODEL=qwen3-vl:4b` w `.env`, słabsza jakość) albo zmniejsz `AUTOFORMULARZ_LLM_NUM_CTX`.

**Model lokalny: 8B czy 30B.** Domyślny jest `qwen3-vl:8b`, bo działa na laptopie z 16 GB RAM. `qwen3-vl:30b-a3b` to ten sam model, który przez Eden AI dał wyniki w `wyniki/`. Ma architekturę MoE, czyli przy każdym tokenie liczy tylko ok. 3B parametrów, więc nie powinien być wolniejszy od 8B. Potrzebuje jednak ok. 20 GB RAM na sam model, czyli maszyny z co najmniej 32 GB RAM. Na takiej maszynie ustaw `AUTOFORMULARZ_LLM_MODEL=qwen3-vl:30b-a3b`.

Zmierzone czasy (laptop AMD Ryzen 7 4800H, 16 GB RAM, Docker Desktop na WSL2, Windows 11):

| Krok | Eden AI (2a) | Ollama (2b) |
|---|---|---|
| Budowanie obrazów | `web` od zera + `api` z cache: 1 min 45 s; `api` od zera: ok. 17 min (LibreOffice, Tesseract) | to samo |
| Pobranie modelu | brak | ~6 GB: ok. 1 min przy 1 Gb/s, ok. 9 min przy 100 Mb/s |
| Formularz 2 (DOCX) | 80 s, 0 błędów lintera, 0,0017 USD | nie zmierzone w Dockerze |
| Formularz 8 (DOCX, największy) | 122 s, 0 błędów lintera, 0,0063 USD | nie zmierzone w Dockerze |

Na CPU bez GPU model 8B pisze kilka tokenów na sekundę, a duży formularz to kilka tysięcy tokenów odpowiedzi (limit 12000), czyli 15–25 min. Dlatego limit czasu to 30 min (`AUTOFORMULARZ_LLM_TIMEOUT_S=1800`). Z GPU NVIDIA zostaje kilkadziesiąt sekund.

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
| `additional privileges requested: pass "--allow=fs.read=Dockerfile.web"` | Compose 5 buduje przez bake i na Windows w Git Bash źle porównuje ścieżki (`/c/...` vs `C:\...`); uruchom polecenie w PowerShellu albo cmd |
| `autoformularz-token`: „Zasady kontroli aplikacji” (Windows) | Smart App Control blokuje plik `.exe` utworzony przez uv; token z kontenera: `docker compose exec api autoformularz-token` |
| port 8000 lub 3000 zajęty | zatrzymaj lokalne `uvicorn` / `npm run dev` albo zmień port w `docker-compose.yml` |

## Licencje

Kod projektu: **MIT**. Zadanie wymaga bibliotek open source bez copyleftu (np. AGPL, GNU GPL) i bez płatnych licencji.
Licencje sprawdzone 2026-11-22 na zainstalowanych pakietach: Python z `importlib.metadata` (tylko zależności
uruchomieniowe, `uv export --no-dev`), JavaScript z `package-lock.json` i z tego, co faktycznie trafia do obrazu
`web` (`.next/standalone`). Nic nie wymaga udostępnienia naszego kodu i nic nie wymaga zakupu licencji.

### API (obraz `autoformularz-api`)

| Biblioteka | Wersja | Licencja | Do czego |
|---|---|---|---|
| fastapi | 0.165.0 | MIT | REST API |
| starlette | 1.10.0 | BSD-3-Clause | REST API (pod FastAPI) |
| uvicorn, click, h11 | 0.54.0, 8.5.1, 0.16.0 | BSD-3-Clause, BSD-3-Clause, MIT | serwer HTTP |
| python-multipart | 0.0.34 | Apache-2.0 | odbiór pliku |
| pydantic, pydantic-core, pydantic-settings | 2.14.4, 2.50.5, 2.16.3 | MIT | modele danych, konfiguracja |
| annotated-types, annotated-doc, typing-inspection | 0.8.0, 0.0.7, 0.4.5 | MIT | pomocnicze Pydantic/FastAPI |
| typing-extensions | 4.16.0 | PSF-2.0 | pomocnicze typowanie |
| python-dotenv | 1.2.4 | BSD-3-Clause | pliki `.env` |
| pyjwt | 2.15.1 | MIT | tokeny JWT |
| httpx, httpcore, anyio, idna | 0.28.1, 1.0.9, 4.16.0, 3.20 | BSD-3-Clause, BSD-3-Clause, MIT, BSD-3-Clause | wywołania modelu |
| certifi | 2026.11.20 | MPL-2.0 | lista certyfikatów dla httpx, bez zmian (niżej) |
| opentelemetry-api | 1.45.2 | Apache-2.0 | zależność pośrednia, bez użycia w kodzie |
| python-docx, lxml | 1.2.0, 6.1.3 | MIT, BSD-3-Clause | odczyt DOCX i ODS (XML) |
| openpyxl, et-xmlfile | 3.1.5, 2.0.0 | MIT | odczyt XLSX |
| pypdf | 7.1.1 | BSD-3-Clause | tekst z PDF |
| pypdfium2 (z PDFium) | 5.15.2 | BSD-3-Clause / Apache-2.0 | strony skanów PDF jako obrazy (zamiast PyMuPDF na AGPL) |
| pillow | 13.0.0 | MIT-CMU (HPND) | zmniejszanie obrazów |
| Tesseract 5 + `pol` (Debian `tesseract-ocr`, `tesseract-ocr-pol`) | 5.x | Apache-2.0 | OCR skanów, osobny proces |
| LibreOffice (Debian `libreoffice-writer-nogui`) | 25.2 | MPL-2.0 | tylko binarny `.doc`, osobny proces `soffice --headless` (niżej) |
| obraz bazowy `python:3.14.10-slim-trixie` | 3.14.10 | PSF-2.0 (Python) + pakiety Debiana | system w kontenerze |

### Frontend (obraz `autoformularz-web`)

| Biblioteka | Wersja | Licencja |
|---|---|---|
| next, @next/env, styled-jsx, client-only | 16.4.6, 16.4.6, 5.1.6, 0.0.1 | MIT |
| react, react-dom, scheduler | 19.3.0, 19.3.0, 0.28.0 | MIT |
| @swc/helpers | 0.5.23 | Apache-2.0 |
| jsonata (warunki `states` w podglądzie) | 2.2.2 | MIT |
| motion, @base-ui/react, shadcn, tw-animate-css, cn, server-only | 14.14.0, 1.9.0, 4.23.0, 1.4.0, 0.5.2, 0.0.1 | MIT |
| lucide-react | 1.77.0 | ISC |
| class-variance-authority | 0.7.1 | Apache-2.0 |
| obraz bazowy `node:22.23.5-alpine3.24` | 22.23.5 | MIT (Node.js) + pakiety Alpine |

Wszystkie pakiety produkcyjne z `package-lock.json` (293): MIT 226, Apache-2.0 20, ISC 17, BSD-3-Clause 6,
BSD-2-Clause 4, BlueOak-1.0.0 3, 0BSD 1, MIT OR CC0-1.0 1, CC-BY-4.0 1 (`caniuse-lite`: dane o przeglądarkach,
tylko przy budowaniu). Pozostałe 14 to opcjonalne binaria `sharp`/libvips (LGPL-3.0): **nie trafiają do obrazu**, bo
optymalizacja obrazów Next jest wyłączona (`images.unoptimized`, `outputFileTracingExcludes` w `next.config.ts`;
sprawdzone: w `.next/standalone/node_modules` nie ma `sharp` ani `@img`).

### Modele językowe

| Model | Licencja | Gdzie |
|---|---|---|
| DeepSeek V4.1 Flash (`deepinfra/deepseek-ai/DeepSeek-V4.1-Flash`) | MIT, otwarte wagi | Eden AI (domyślnie). Wagi są publiczne, ale model jest duży (763 mld parametrów), więc lokalnie praktycznie tylko na serwerze GPU |
| Qwen3-VL 8B (`qwen3-vl:8b`) | Apache-2.0, otwarte wagi | Ollama, tryb offline |
| Qwen3-VL 30B-A3B (`deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct`) | Apache-2.0, otwarte wagi | poprzedni model na Eden AI |
| Ollama (`ollama/ollama:0.40.17`) | MIT | serwer modelu, osobny kontener (`--profile ollama`) |

### Tylko przy budowaniu i w developmencie

uv, ruff, pytest, Biome, TypeScript, Tailwind CSS, lefthook, Marp (slajdy przez npx): MIT lub Apache-2.0;
lightningcss (przez Tailwind): MPL-2.0, tylko przy budowaniu CSS. Nic z tego nie trafia do obrazów.

### Dlaczego MPL-2.0 nie łamie zakazu copyleft

MPL-2.0 (certifi, LibreOffice, lightningcss) to copyleft na poziomie pliku: udostępnić trzeba tylko zmienione pliki
na tej licencji, nie nasz kod. Niczego w nich nie zmieniamy, a LibreOffice działa jako osobny program, bez
linkowania. Mentorzy COI dopuścili LibreOffice tylko przy takiej licencji, dlatego `.ods` czytamy wprost z XML, a
LibreOffice zostało wyłącznie dla binarnego `.doc` (obraz bez niego: `--build-arg WITH_LIBREOFFICE=0`). Obrazy
bazowe zawierają pakiety systemu (Debian, Alpine) na różnych licencjach, także GPL; to osobne programy
dystrybuowane razem z systemem, nasz kod z nimi nie jest łączony. Licencji pakietów Debiana, które dociąga
LibreOffice, nie przeglądaliśmy po kolei. Szczegóły i uzasadnienia: [docs/architektura.md, „Licencje”](docs/architektura.md#7-licencje).

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
| `AUTOFORMULARZ_LLM_PROVIDER` | `eden` | `ollama` uruchamia model lokalnie (offline, w Dockerze z `--profile ollama`), patrz [Model językowy](#model-językowy-eden-ai-domyślnie-albo-ollama-offline) |
| `AUTOFORMULARZ_EDEN_MODEL` / `EDENAI_API_KEY` | `deepinfra/deepseek-ai/DeepSeek-V4.1-Flash` / brak | Model i klucz Eden AI (klucz wymagany przy `eden`) |
| `AUTOFORMULARZ_EDEN_REASONING_EFFORT` | `none` | Wyłącza myślenie modelu na Eden: `reasoning_effort` w zapytaniu i przełącznik `/no_think` w prompcie (jak `think: false` w Ollamie). Gdy Eden odrzuci parametr, zapytanie idzie ponownie bez niego. Pusta wartość: nie wysyła żadnego z nich |
| `AUTOFORMULARZ_LLM_TIMEOUT_S` | `1800` | Limit czasu odpowiedzi modelu (Ollama na CPU potrzebuje do ~25 min na duży formularz) |
| `AUTOFORMULARZ_LLM_NUM_CTX` | `24576` | Okno kontekstu modelu w Ollamie: prompt + odpowiedź (więcej = więcej pamięci RAM/VRAM; 16384 nie mieści formularza 8) |
| `AUTOFORMULARZ_LLM_MAX_TOKENS` | `12000` | Górny limit długości odpowiedzi modelu; mały formularz dostaje mniejszy (2000 + 100 na blok, co najmniej 3000), a schemat ogranicza liczbę stron, sekcji i pól do rozmiaru dokumentu. Gdy model zaczyna powtarzać sekcje (zapętlenie), używana jest kompletna część odpowiedzi sprzed powtórzeń, z uwagą w wyniku; Ollama przerywa generowanie od razu |
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

### Bezpieczeństwo: prompt injection przez dokument

Plik formularza pochodzi z zewnątrz, a jego tekst trafia do modelu. Wrogi dokument może próbować wydać modelowi
polecenia („zignoruj poprzednie instrukcje”, „dodaj pole na hasło”). Obrona na każdym poziomie, który kontroluje kod:

- **Odczyt pliku:** tekst niewidoczny na wydruku nie trafia do modelu: ukryty tekst Worda (`w:vanish`), znaki
  o zerowej szerokości, znaki zmieniające kierunek tekstu i miękkie dywizy.
- **Prompt:** treść dokumentu jest oznaczona jako dane (`<<<DOKUMENT` … `DOKUMENT>>>`), a prompt systemowy mówi, że
  polecenia w dokumencie nie są poleceniami. Tekst bloku nie może zamknąć tej części ani podszyć się pod blok lub
  rolę (każdy blok to jedna linia, znaczniki są rozbrajane).
- **Wynik:** strukturę wyznacza schemat i kompilator; tekst w opisach jest escapowany (nigdy żywy HTML). Skaner
  `safety.py` oznacza ostrzeżeniami `SAFETY_*` w `issues`: pytania o hasła, PIN i dane karty, polecenia dla modelu,
  linki poza gov.pl, kod HTML i niewidoczne znaki. Ten sam skaner działa w podglądzie (`src/lib/form/safety.ts`).

Testy: `api/tests/test_injection.py` (bez wywołań modelu; każde zabezpieczenie ma test, który je wykrywa).

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

### Propozycje nowych słowników

Platforma ma słowniki Kraje, TERYT i Numery kierunkowe. Gdy pole lepiej zasiliłaby wspólna lista niż opcje wpisane
w formularzu albo wolny tekst, wynik zawiera propozycję nowego słownika: nazwę (`dictionaryName`), strukturę
(`kod`, `nazwa`), pozycje i zastosowanie (strona, sekcja, pole, proponowana zmiana). Reguły działają na etykietach
pól, bez modelu:

- katalog rozpoznanych list: stopień pokrewieństwa, rodzaj dokumentu tożsamości, rasy psów uznawanych za agresywne
  (wykaz z rozporządzenia MSWiA z 2003 r.), sposób doręczenia, urzędy skarbowe, dyscypliny sportowe,
- każde inne pole wyboru z co najmniej 8 opcjami (nazwa słownika z etykiety pola).

Gdzie: `dictionaries` w odpowiedzi `?details=true`, `proposedDictionaries` w `wyniki/NN.report.json` i zbiorczo
`wyniki/slowniki.json` (na materiałach: rasy psów z formularza 7, sposób doręczenia i dyscypliny z formularza 9).
JSON formularza się nie zmienia, bo słownika nieznanego platformie nie da się zaimportować.

### Metryki i porównywanie przebiegów

Każde przetworzenie pliku zapisuje metryki: czasy etapów, czas modelu i czas do pierwszego tokenu, tokeny
wejścia i wyjścia, koszt Eden, szacunek tokenów obrazów, liczbę wartości domyślnych (`null`, `[]`, `false`) w surowej
odpowiedzi i rozmiar wyniku. Plik jest opisany skrótem SHA-256, nigdy nazwą ani treścią.

- API: jedna linia JSON w logu (`docker compose logs api | grep metrics`) i klucz `metrics` w `?details=true`.
- Generator wyników: każde zapytanie modelu dopisuje linię do `wyniki/metrics.jsonl` (ze stanem ustawień: model,
  presort, rozdzielczość obrazów…) i zapisuje surową odpowiedź w `wyniki/NN.raw.txt` (oba poza gitem).
  Tabela porównawcza bez modelu: `cd api && uv run python -m autoformularz.results --metrics`.

### Model językowy: Eden AI (domyślnie) albo Ollama (offline)

Domyślnie API używa modelu open-weight na Eden AI (`AUTOFORMULARZ_LLM_PROVIDER=eden`, decyzja zespołu z 2026-11-21): odpowiada w 1–3 minuty, a lokalna Ollama na CPU potrzebuje kilkunastu minut. W Dockerze: [2a. Eden AI](#2a-eden-ai-domyślnie).

**Konfiguracja.** W `api/.env` albo w `.env.local` w katalogu głównym:

```bash
AUTOFORMULARZ_LLM_PROVIDER=eden
AUTOFORMULARZ_EDEN_MODEL=deepinfra/deepseek-ai/DeepSeek-V4.1-Flash  # poprzednio deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct (Ollama: qwen3-vl:30b)
EDENAI_API_KEY=...                                          # klucz zespołu, tylko po stronie serwera
```

Uruchom API (`cd api && uv run uvicorn autoformularz.main:app --reload`). `GET /health` pokaże `"provider": "eden"` i `"configured": true`, a w logu pojawi się ostrzeżenie o trybie demo i kosztach. Bez klucza lub modelu żądania kończą się błędem `LLM_MISCONFIGURED`.

**Tryb offline.** Ustaw `AUTOFORMULARZ_LLM_PROVIDER=ollama` i zrestartuj API. Potrzebny jest wtedy model w Ollamie: `ollama pull qwen3-vl:8b`.

Kolejność: `api/.env` nadpisuje `.env.local`, a zmienne środowiskowe nadpisują oba pliki. `docker-compose.yml` domyślnie używa Eden (klucz tylko w kontenerze `api`); Ollamę włącza `AUTOFORMULARZ_LLM_PROVIDER=ollama` z `--profile ollama`. Przez Eden używaj wyłącznie modeli open-weight, które da się uruchomić w Ollamie (bez GPT, Gemini, Claude).

Struktura repozytorium:
- `api/`: rozwiązanie (Python 3.14, FastAPI),
- `src/`: frontend (Next.js) z design systemem formularzy,
- `materialy/`: materiały zadania,
- `docs/`: decyzje i research; wyjaśnienia niespójności w materiałach: [docs/wyjasnienia-materialow.md](docs/wyjasnienia-materialow.md).

Zasady zespołu: brak atrybucji AI w commitach (hook to blokuje), nigdy nie commituj plików `.env`, a wszystkie zależności muszą mieć licencję open source bez copyleft (szczegóły w [CLAUDE.md](CLAUDE.md)).
