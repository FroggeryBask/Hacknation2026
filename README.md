# AutoFormularz: cyfryzacja formularzy

Usługa REST, która zamienia plik formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) na konfigurację
formularza e-usługi w formacie JSON, gotową do importu w systemie docelowym COI. Zadanie COI „Cyfryzacja
formularzy”, HackNation 2026.

Model językowy to model o otwartych wagach. Domyślnie działa na Eden AI, udostępnionym przez organizatorów
(`deepinfra/deepseek-ai/DeepSeek-V4.1-Flash`, MIT). W trybie offline działa w całości lokalnie przez Ollamę
(`qwen3-vl:8b`, Apache-2.0), bez żadnego zewnętrznego API.

## Zawartość repozytorium

| Ścieżka | Co zawiera |
|---|---|
| `api/` | rozwiązanie: REST API (Python 3.14, FastAPI), testy, `Dockerfile` |
| `src/`, `Dockerfile.web` | frontend (Next.js): wgranie jednego lub wielu plików, podgląd e-formularza z JSON-u, podgląd JSON-u |
| `docker-compose.yml`, `.env.example` | uruchomienie całości w Dockerze i przykładowa konfiguracja |
| `wyniki/` | wynikowe pliki JSON dla materiałów 1–9 (`NN.json`), raporty (`NN.report.json`) i propozycje słowników (`slowniki.json`), [Wyniki](#wyniki) |
| `docs/architektura.md` | **dokumentacja architektury** (komponenty, przepływ, bezpieczeństwo, koszt, zgodność z wymaganiami, licencje) |
| `docs/pipeline.md`, `docs/decisions.md` | kroki przetwarzania i decyzje projektowe z uzasadnieniem |
| `docs/prezentacja.pdf` | prezentacja projektu (źródło: `docs/prezentacja.md`, Marp) |
| `docs/wyjasnienia-materialow.md`, `docs/research-cyfryzacja-formularzy.md` | ustalenia z mentorami i research |
| `materialy/` | materiały zadania (źródło prawdy dla formatu i reguł) |
| `wczesniej.md` | co powstało przed hackathonem |

## Jak to działa

```
plik ─► walidacja (nazwa, rozmiar, MIME z zawartości) ─► odczyt (bloki tekstu w kolejności dokumentu, OCR skanów, obrazy stron)
     ─► presort: kod rozpoznaje RODO, linie tylko na papier i dane wnioskodawcy (nie idą do modelu)
     ─► model: krótki opis formularza (FormSpec, odpowiedź wymuszona schematem JSON, wskazuje bloki źródła)
     ─► kanon i kompilator: JSON w formacie COI (sekcje ze standardu, walidatory, słowniki, dane inicjalne,
        warunki jsonata, przejścia, podstawa prawna i pouczenia dosłownie ze źródła)
     ─► walidator reguł technicznych i skaner bezpieczeństwa ─► odpowiedź
```

Model opisuje tylko to, czego dotyczy formularz. Sekcje wspólne dla wszystkich wniosków (urząd, podmiot wniosku,
wnioskodawca, adres, pełnomocnictwo, opłata skarbowa, kontakt, zgody, podgląd) buduje deterministyczny kompilator
według standardu projektowania formularzy. Dzięki temu wynik jest powtarzalny i zawsze zgodny ze strukturą importu.
Szczegóły: [docs/architektura.md](docs/architektura.md).

## Szybki start

```bash
cp .env.example .env          # Windows (PowerShell): Copy-Item .env.example .env
# w .env: AUTOFORMULARZ_JWT_SECRET=<losowy klucz> i EDENAI_API_KEY=<klucz Eden AI>
docker compose up --build
```

API: http://localhost:8000 (OpenAPI: http://localhost:8000/docs), frontend: http://localhost:3000. Token do API:
`docker compose exec api autoformularz-token`. Tryb offline bez Eden AI: [Uruchomienie lokalnie (Ollama)](#2b-w-pełni-lokalnie-ollama-offline), ten sam model
DeepSeek na własnym serwerze: [2c](#2c-ten-sam-model-co-na-eden-ai-ale-na-własnym-serwerze-deepseek-v41-flash).

## Budowanie obrazu Docker

Potrzebny jest Docker Desktop (Windows, macOS) albo Docker Engine z wtyczką Compose **2.24 lub nowszą** (Linux).
Obrazy działają na x86_64 i ARM64 (także Apple Silicon).

Oba obrazy naraz (API i frontend), z `docker-compose.yml`:

```bash
docker compose build
```

Każdy obraz osobno:

```bash
docker build -t autoformularz-api:0.1.0 ./api                                       # API z LibreOffice (pliki .doc)
docker build -t autoformularz-api:0.1.0-slim --build-arg WITH_LIBREOFFICE=0 ./api   # API bez LibreOffice (mniejszy, bez binarnego .doc)
docker build -t autoformularz-web:0.1.0 -f Dockerfile.web .                         # frontend (opcjonalny)
```

| Wymaganie z zadania | Jak jest spełnione |
|---|---|
| oficjalne obrazy bazowe, jawne wersje, bez `latest` | `python:3.14.10-slim-trixie`, `node:22.23.5-alpine3.24`, `ollama/ollama:0.40.17`; nasze obrazy mają tag `0.1.0` |
| lekka dystrybucja | frontend na Alpine; API na Debian slim, bo LibreOffice i biblioteki PDF/obrazów są budowane dla glibc |
| proces na użytkowniku z ograniczonymi uprawnieniami | API: użytkownik systemowy `app`, frontend: `node` |
| tylko potrzebne porty | API `8000`, frontend `3000` (Ollama w profilu `ollama` nie wystawia portu na zewnątrz) |
| sekrety tylko przy uruchomieniu | `AUTOFORMULARZ_JWT_SECRET` i `EDENAI_API_KEY` z `.env` lub `-e` przy starcie, nigdy w obrazie; klucz Eden dostaje tylko `api` |

Czas budowania (laptop AMD Ryzen 7 4800H, 16 GB RAM, WSL2): `web` od zera ok. 1 min 45 s, `api` od zera ok. 17 min
(LibreOffice i Tesseract), potem z cache kilka sekund.

## Uruchomienie aplikacji

### 1. Konfiguracja

```bash
cp .env.example .env                 # macOS, Linux
Copy-Item .env.example .env          # Windows (PowerShell)
```

W `.env` ustaw `AUTOFORMULARZ_JWT_SECRET`. Losowy klucz wygenerujesz samym Dockerem:

```bash
docker run --rm python:3.14.10-slim-trixie python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Zapisz `.env` jako UTF-8 bez BOM (domyślnie tak robią VS Code i Notatnik w Windows 11). Wszystkie ustawienia:
[Konfiguracja](#konfiguracja).

### 2a. Eden AI (domyślnie)

W `.env` dopisz klucz `EDENAI_API_KEY=...`, potem:

```bash
docker compose up --build
```

- Startują tylko `api` i `web`; `ollama` i `model` są w profilu `ollama` i bez niego się nie uruchamiają.
- `GET /health` pokazuje `"provider": "eden"`, `"configured"` (czy jest klucz i model) i `"usage"`: liczbę zapytań
  i koszt w USD od startu kontenera.
- Każde zapytanie do modelu kosztuje (na materiałach poniżej 0,005 USD za formularz). Bez klucza żądania kończą się
  błędem `LLM_MISCONFIGURED` i nic nie jest wysyłane.

### 2b. W pełni lokalnie (Ollama, offline)

```bash
AUTOFORMULARZ_LLM_PROVIDER=ollama docker compose --profile ollama up --build      # macOS, Linux
```

Na Windows (PowerShell) ustaw w `.env` `AUTOFORMULARZ_LLM_PROVIDER=ollama`, potem `docker compose --profile ollama up --build`.

- Usługa `model` przy pierwszym starcie pobiera model `qwen3-vl:8b` (~6 GB) do wolumenu `ollama`; `api` startuje
  dopiero po pobraniu. Potem wszystko działa bez internetu.
- GPU NVIDIA (Linux, Windows z WSL2): odkomentuj blok `deploy` w `docker-compose.yml`. Docker na macOS nie daje
  kontenerom dostępu do GPU, więc tam model liczy się na CPU.

### 2c. Ten sam model co na Eden AI, ale na własnym serwerze (DeepSeek V4.1 Flash)

DeepSeek V4.1 Flash ma otwarte wagi (MIT, `deepseek-ai/DeepSeek-V4.1-Flash-1017` na Hugging Face), więc da się go
uruchomić u siebie i przestać korzystać z Eden AI. Kod się nie zmienia. Dostawca `eden` to zwykły klient API
zgodnego z OpenAI (`POST {AUTOFORMULARZ_EDEN_BASE_URL}/chat/completions`, odpowiedź strumieniowana, schemat
`json_schema`), więc wystarczy wskazać mu własny serwer zamiast `api.edenai.run`.

1. **Serwer modelu.** To duży model MoE, więc potrzebny jest serwer z kilkoma GPU, nie laptop (wymagania pamięci
   podaje karta modelu). Model wystawia serwer zgodny z OpenAI API, np. [vLLM](https://github.com/vllm-project/vllm)
   albo [SGLang](https://github.com/sgl-project/sglang) (oba Apache-2.0), jeśli dana wersja obsługuje ten model.
   Przykład dla vLLM:

   ```bash
   vllm serve deepseek-ai/DeepSeek-V4.1-Flash-1017 --served-model-name deepseek-v4.1-flash \
     --api-key <dowolny-klucz> --tensor-parallel-size <liczba GPU> --port 8001
   ```

2. **Konfiguracja API** w `.env`. Nazwy zmiennych mają przedrostek `EDEN`, ale działają z każdym serwerem
   zgodnym z OpenAI:

   ```bash
   AUTOFORMULARZ_LLM_PROVIDER=eden                              # klient API zgodnego z OpenAI
   AUTOFORMULARZ_EDEN_BASE_URL=http://<adres-serwera>:8001/v1   # zamiast https://api.edenai.run/v3
   AUTOFORMULARZ_EDEN_MODEL=deepseek-v4.1-flash                 # nazwa z --served-model-name
   EDENAI_API_KEY=<dowolny-klucz>                               # ten sam co w --api-key
   ```

   `AUTOFORMULARZ_EDEN_REASONING_EFFORT=none` może zostać. Gdy serwer odrzuci `reasoning_effort` albo
   `json_schema`, API samo ponawia zapytanie bez tego parametru albo z `json_object`; schemat i tak jest w prompcie,
   a odpowiedź sprawdza Pydantic. Jeśli serwer stoi na tym samym komputerze co Docker, adres to
   `http://host.docker.internal:8001/v1`. Docker Desktop (Windows, macOS) zna ten adres sam; na Linuksie usługa `api`
   potrzebuje dodatkowo `extra_hosts: ["host.docker.internal:host-gateway"]`.

3. **Start:** `docker compose up --build`, jak w wariancie 2a. `GET /health` pokaże `"provider": "eden"`
   i `"configured": true`. Koszt w `usage` wyniesie 0, bo własny serwer nie zwraca ceny.

Wyniki powinny być bardzo zbliżone do tych z Eden AI, bo to ten sam model z tym samym promptem i schematem (mogą
się różnić, jeśli serwer używa innej kwantyzacji wag). Nie testowaliśmy tego na własnym serwerze (nie mamy sprzętu dla tego modelu); na Eden AI ta sama ścieżka kodu działa
na wszystkich materiałach. Na zwykłym komputerze bez GPU zostaje wariant 2b (Ollama z `qwen3-vl:8b`).

### 3. Adresy, token i zatrzymanie

- API: http://localhost:8000, dokumentacja OpenAPI: http://localhost:8000/docs
- Frontend: http://localhost:3000. Do 20 plików naraz, każdy jako osobne zadanie `/api/v1/jobs`, po 2 jednocześnie.
  Na każdy plik: podgląd e-formularza i JSON-u, błędy reguł, wynik skanu bezpieczeństwa. Pobieranie JSON-u
  pojedynczo albo wszystkich w jednym ZIP-ie.
- Token JWT do API (ważny 8 h): `docker compose exec api autoformularz-token`
- Zatrzymanie: `docker compose down` (z `--profile ollama`, jeśli startowało z Ollamą). `docker compose down -v` usuwa
  też pobrany model.

Samo API bez Compose (np. z Ollamą zainstalowaną na komputerze):

```bash
docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway \
  -e AUTOFORMULARZ_JWT_SECRET=... -e AUTOFORMULARZ_LLM_PROVIDER=ollama \
  -e AUTOFORMULARZ_OLLAMA_URL=http://host.docker.internal:11434 autoformularz-api:0.1.0
```

`--add-host` jest potrzebne na Linuksie (Docker Desktop na Windows i macOS zna `host.docker.internal` sam). Z Eden AI
zamiast dwóch ostatnich zmiennych podaj `-e EDENAI_API_KEY=...`.

### Wymagania sprzętowe i czasy

| Zasób | Eden AI (2a) | Ollama (2b) |
|---|---|---|
| Pamięć RAM dla Dockera | bez modelu: tylko API i frontend | **min. 12 GB** (`qwen3-vl:8b` z kontekstem 24576 zajmuje zmierzone 9,4 GB + API i frontend) |
| Dysk | obrazy `api` i `web` | obrazy + model ~6,2 GB |
| Sieć | przy budowaniu obrazów i przy każdym zapytaniu | tylko przy pierwszym starcie (obrazy, pakiety, model) |
| Czas na formularz | 3–24 s odpowiedzi modelu na materiałach 1–9 (DeepSeek V4.1 Flash) | na CPU 15–25 min dla dużego formularza, z GPU NVIDIA kilkadziesiąt sekund |

**Docker Desktop na Windows (WSL2)** domyślnie daje kontenerom połowę RAM. Na laptopie z 16 GB to ok. 7,7 GB, czyli
za mało dla modelu 8B. Zwiększ limit w `C:\Users\<użytkownik>\.wslconfig`:

```
[wsl2]
memory=12GB
```

i uruchom ponownie WSL (`wsl --shutdown`) oraz Docker Desktop. Na macOS limit pamięci ustawia się w Docker Desktop
(Settings → Resources). Na słabszej maszynie użyj mniejszego modelu (`AUTOFORMULARZ_LLM_MODEL=qwen3-vl:4b`, słabsza
jakość) albo zmniejsz `AUTOFORMULARZ_LLM_NUM_CTX`. Na maszynie z co najmniej 32 GB RAM lepsze wyniki da
`qwen3-vl:30b-a3b` (MoE, ok. 3B aktywnych parametrów na token, ok. 20 GB na sam model).

Na CPU model 8B pisze kilka tokenów na sekundę, a duży formularz to kilka tysięcy tokenów odpowiedzi, dlatego limit
czasu to 30 min (`AUTOFORMULARZ_LLM_TIMEOUT_S=1800`).

### Gdy coś nie działa

| Objaw | Przyczyna i rozwiązanie |
|---|---|
| `429 Too Many Requests` przy budowaniu | limit pobrań z Docker Hub bez logowania; `docker login` (darmowe konto) albo odczekaj |
| `failed to connect to the docker API` | Docker Desktop nie jest uruchomiony |
| `depends_on` / `!reset` w błędzie Compose | za stara wtyczka Compose; potrzebna 2.24+ (`docker compose version`) |
| `/health`: `"configured": false` (Eden) | brak `EDENAI_API_KEY` w `.env` albo kontener uruchomiony przed jego dopisaniem (`docker compose up -d` ponownie) |
| kontener `ollama` kończy się bez błędu, model się nie ładuje | za mało pamięci dla Dockera, patrz wyżej |
| `additional privileges requested: pass "--allow=fs.read=Dockerfile.web"` | Compose 5 buduje przez bake i na Windows w Git Bash źle porównuje ścieżki (`/c/...` vs `C:\...`); uruchom polecenie w PowerShellu albo cmd |
| `LLM_UNAVAILABLE`, w logu `No address associated with hostname` | DNS sieci lokalnej źle odpowiada na zapytanie IPv6 o `api.edenai.run` (Docker Desktop). API pyta najpierw o IPv4 i ponawia połączenie (1, 2, 4, 8 s); jeśli błąd wraca, zmień DNS karty sieciowej i uruchom ponownie Docker Desktop |
| port 8000 lub 3000 zajęty | zatrzymaj lokalne `uvicorn` / `npm run dev` albo zmień port w `docker-compose.yml` |

## Konfiguracja

Zmienne środowiskowe API (prefiks `AUTOFORMULARZ_`, plus `EDENAI_API_KEY`), czytane przy starcie z `.env`
lub ze środowiska. Przykład z komentarzami: [.env.example](.env.example). Sekrety (JWT, klucz Eden) podawaj tylko
przy uruchomieniu.

**Plik i uwierzytelnianie**

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `AUTOFORMULARZ_MAX_UPLOAD_MB` | `20` | Maksymalny rozmiar przesyłanego pliku (MB); większy plik: `413 FILE_TOO_LARGE` |
| `AUTOFORMULARZ_JWT_SECRET` | brak (wymagany) | **Sekret.** Klucz do weryfikacji podpisu tokenów JWT |
| `AUTOFORMULARZ_JWT_ALGORITHM` | `HS256` | Algorytm podpisu tokenu |
| `AUTOFORMULARZ_JWT_AUDIENCE` | brak | Wymagane pole `aud` tokenu (puste: nie sprawdzane) |
| `AUTOFORMULARZ_AUTH_ENABLED` | `true` | `false` wyłącza JWT (tylko do lokalnego developmentu) |
| `AUTOFORMULARZ_CORS_ORIGINS` | `http://localhost:3000` | Dozwolone adresy frontendu (po przecinku) |

**Model językowy**

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `AUTOFORMULARZ_LLM_PROVIDER` | `eden` | `eden` (Eden AI) albo `ollama` (lokalnie, offline) |
| `EDENAI_API_KEY` | brak | **Sekret.** Klucz Eden AI, wymagany przy `eden`; trafia tylko do kontenera `api` |
| `AUTOFORMULARZ_EDEN_MODEL` | `deepinfra/deepseek-ai/DeepSeek-V4.1-Flash` | Model na Eden AI (tylko modele o otwartych wagach) |
| `AUTOFORMULARZ_EDEN_BASE_URL` | `https://api.edenai.run/v3` | Adres API Eden AI albo własnego serwera zgodnego z OpenAI, np. vLLM z DeepSeekiem ([2c](#2c-ten-sam-model-co-na-eden-ai-ale-na-własnym-serwerze-deepseek-v41-flash)) |
| `AUTOFORMULARZ_EDEN_REASONING_EFFORT` | `none` | Wyłącza „myślenie” modelu na Eden (`reasoning_effort`; dla Qwen też `/no_think`). Pusta wartość: nie wysyła nic |
| `AUTOFORMULARZ_OLLAMA_URL` | `http://localhost:11434` | Adres serwera Ollama (w Compose: `http://ollama:11434`) |
| `AUTOFORMULARZ_LLM_MODEL` | `qwen3-vl:8b` | Model w Ollamie (model wizyjny: czyta też skany) |
| `AUTOFORMULARZ_LLM_TIMEOUT_S` | `1800` | Limit czasu odpowiedzi modelu w sekundach |
| `AUTOFORMULARZ_LLM_NUM_CTX` | `24576` | Okno kontekstu w Ollamie (prompt + odpowiedź); więcej = więcej RAM |
| `AUTOFORMULARZ_LLM_MAX_TOKENS` | `12000` | Górny limit długości odpowiedzi; mały dokument dostaje mniejszy (2000 + 100 na blok, min. 3000), a schemat ogranicza liczbę stron, sekcji i pól do rozmiaru dokumentu. Zapętloną odpowiedź kod zatrzymuje i używa jej kompletnej części |
| `AUTOFORMULARZ_LLM_KEEP_ALIVE` | `30m` | Jak długo Ollama trzyma model w pamięci po zapytaniu |
| `AUTOFORMULARZ_LLM_SAMPLES` | `1` | Ile odpowiedzi modelu na plik; kod wybiera najlepszą (najmniej błędów reguł, najmniej pominiętych pól) i uzupełnia ją z pozostałych. N zapytań = N razy koszt i czas |
| `AUTOFORMULARZ_LLM_TEMPERATURE` / `AUTOFORMULARZ_LLM_SAMPLE_TEMPERATURE` | `0.0` / `0.4` | Temperatura pierwszej odpowiedzi i kolejnych (przy `LLM_SAMPLES` > 1) |

**Odczyt plików i wynik**

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `AUTOFORMULARZ_MAX_PDF_PAGES` | `6` | Ile stron skanu przekazać modelowi jako obrazy (OCR czyta wszystkie, do 30) |
| `AUTOFORMULARZ_OCR_BIN` / `AUTOFORMULARZ_OCR_LANG` | `tesseract` / `pol` | OCR skanów (Tesseract, jest w obrazie). Bez niego skan trafia do modelu tylko jako obraz |
| `AUTOFORMULARZ_TESSDATA_DIR` | brak | Katalog z `pol.traineddata`, jeśli nie ma go w domyślnym `tessdata` |
| `AUTOFORMULARZ_SOFFICE_BIN` | `soffice` | LibreOffice, tylko dla binarnych `.doc` (`.docx`, `.ods`, `.xlsx` są czytane bez niego) |
| `AUTOFORMULARZ_PRESORT` | `true` | Kod rozpoznaje klauzulę RODO, linie tylko na papier i dane wnioskodawcy przed modelem (krótszy prompt, mniej błędów) |
| `AUTOFORMULARZ_COPY_SOURCE_TEXT` | `true` | Pouczenia dosłownie ze źródła na stronie końcowej (kod zostawia tylko punkty o opłatach, terminach, obowiązkach i skutkach). Podstawa prawna jest dodawana zawsze, też sprawdzana w kodzie |

**Frontend** (tylko po stronie serwera Next.js): `AUTOFORMULARZ_API_URL` (adres API, w Compose `http://api:8000`)
i `AUTOFORMULARZ_JWT_SECRET` (frontend podpisuje nim krótkie tokeny do API; sekret nie trafia do przeglądarki).

## REST API

Opis interaktywny (OpenAPI/Swagger): http://localhost:8000/docs.

### Uwierzytelnianie

Endpointy `/api/v1/*` wymagają nagłówka `Authorization: Bearer <JWT>`. Token jest podpisany kluczem
`AUTOFORMULARZ_JWT_SECRET` (`HS256`), musi mieć `exp`, a gdy ustawiono `AUTOFORMULARZ_JWT_AUDIENCE`, także `aud`.
Token testowy: `docker compose exec api autoformularz-token [godziny]` (lokalnie: `cd api && uv run autoformularz-token`).

### Endpointy

| Metoda i ścieżka | Wejście | Odpowiedź |
|---|---|---|
| `POST /api/v1/forms` | `multipart/form-data`, pole `file`: jeden plik formularza | `200`: JSON konfiguracji formularza gotowy do importu. Nagłówki `X-Autoformularz-Errors` i `X-Autoformularz-Warnings`: liczba błędów i ostrzeżeń reguł technicznych |
| `POST /api/v1/forms?details=true` | jak wyżej | `200`: `{form, spec, issues, notes, sourceFormat, document, coverage, metrics, dictionaries}` (niżej) |
| `POST /api/v1/jobs` (`?details=true`) | jak `/forms` | `202`: `{id}`; to samo przetwarzanie w tle (dla długich plików i wielu plików naraz). Najwyżej 4 zadania jednocześnie, inaczej `429 BUSY` |
| `GET /api/v1/jobs/{id}` | | `200`: `{id, status, steps, result?, error?}`; `status`: `running`, `done`, `error`, `cancelled`; `steps`: postęp (etapy, potem tytuł, strony, sekcje i pola z odpowiedzi modelu); `result`: to samo co `/forms`. Zadanie znika 15 min po ostatniej zmianie |
| `DELETE /api/v1/jobs/{id}` | | `204`: anuluje zadanie (model przestaje pisać) |
| `POST /api/v1/forms/compile` (`?details=true`) | body: FormSpec (JSON) | `200`: formularz zbudowany bez modelu, np. po ręcznej korekcie opisu |
| `POST /api/v1/forms/validate` | body: JSON formularza | `200`: `{valid, issues}` według reguł technicznych |
| `GET /api/v1/spec/schema` | | `200`: schemat JSON opisu pośredniego (FormSpec) |
| `GET /health` (bez tokenu) | | `200`: `{status, llm}`: dostawca i model, czy skonfigurowany, zużycie Eden od startu |

Pola odpowiedzi `?details=true`:

| Pole | Zawartość |
|---|---|
| `form` | JSON formularza do importu (to samo co bez `details`) |
| `spec` | opis pośredni FormSpec, który zwrócił model (po poprawkach kodu) |
| `issues` | `[{level, code, message, path}]`: błędy i ostrzeżenia reguł technicznych oraz ostrzeżenia `SAFETY_*` skanera bezpieczeństwa |
| `notes` | uwagi z przetwarzania (np. co kod usunął lub połączył i dlaczego) |
| `sourceFormat` | rozpoznany format pliku |
| `document` | bloki tekstu źródła z identyfikatorami i wykryte miejsca do wypełnienia |
| `coverage` | pokrycie źródła: które miejsca do wypełnienia nie mają pola |
| `metrics` | czasy etapów, tokeny i koszt modelu, rozmiar wyniku |
| `dictionaries` | propozycje nowych słowników (nazwa, struktura, pozycje, pola, w których użyć) |

### Walidacja pliku

| Reguła | Szczegóły |
|---|---|
| format | `.pdf`, `.doc`, `.docx`, `.ods`, `.xlsx`, `.jpg`, `.jpeg`, `.png`; typ MIME sprawdzany z zawartości pliku (sygnatura), musi pasować do rozszerzenia. `.doc` i `.docx` to jeden format „DOC”: o sposobie odczytu decyduje zawartość |
| nazwa | najwyżej 250 znaków, bez znaków `; : > < / \ \| ' * % $` |
| rozmiar | najwyżej `AUTOFORMULARZ_MAX_UPLOAD_MB` |
| przechowywanie | plik tylko w pamięci (binarny `.doc`: w katalogu tymczasowym na czas konwersji); nic nie jest zapisywane |

### Błędy

Postać: `{"error": {"code": "...", "message": "..."}}` (komunikat po polsku); błędy uwierzytelniania mają standardową
postać FastAPI `{"detail": "..."}`.

| Status | Kod | Kiedy |
|---|---|---|
| `401` | | brak tokenu albo token nieprawidłowy lub wygasły |
| `500` | | `AUTOFORMULARZ_JWT_SECRET` nie jest ustawiony (przy włączonym JWT) |
| `404` | `JOB_NOT_FOUND` | nie ma takiego zadania (mogło wygasnąć) |
| `413` | `FILE_TOO_LARGE` | plik większy niż `AUTOFORMULARZ_MAX_UPLOAD_MB` |
| `415` | `UNSUPPORTED_FORMAT`, `MIME_MISMATCH`, `UNSUPPORTED_CONTENT` | nieobsługiwany format albo zawartość niezgodna z rozszerzeniem |
| `422` | `FILENAME_TOO_LONG`, `FILENAME_FORBIDDEN_CHARS`, `FILENAME_MISSING`, `FILE_EMPTY` | zła nazwa albo pusty plik |
| `422` | `CONVERSION_FAILED`, `UNREADABLE_IMAGE` | pliku nie da się odczytać |
| `429` | `BUSY` | serwer przetwarza już 4 zadania; ponów za chwilę |
| `500` | `LLM_MISCONFIGURED` | `eden` bez `EDENAI_API_KEY` lub modelu |
| `502` | `LLM_ERROR`, `LLM_BAD_OUTPUT`, `LLM_TRUNCATED` | model zwrócił błąd, odpowiedź niezgodną ze schematem albo przerwaną bez użytecznej części |
| `503` | `LLM_UNAVAILABLE`, `CONVERTER_MISSING` | model niedostępny albo brak LibreOffice dla `.doc` |

### Przykład

```bash
TOKEN=$(docker compose exec -T api autoformularz-token)
curl -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.pdf" http://localhost:8000/api/v1/forms -o wniosek.json
curl -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.pdf" "http://localhost:8000/api/v1/forms?details=true"
```

PowerShell:

```powershell
$token = docker compose exec -T api autoformularz-token
curl.exe -H "Authorization: Bearer $token" -F "file=@wniosek.pdf" http://localhost:8000/api/v1/forms -o wniosek.json
```

## Wyniki

`wyniki/NN.json` to wynikowe pliki JSON dla materiałów 1–9. Każdy to jedno zwykłe wywołanie usługi bez żadnej
poprawki: materiał wysłany raz do `POST /api/v1/forms?details=true` w obrazie Docker z ustawieniami domyślnymi
(Eden AI, DeepSeek V4.1 Flash, jedna odpowiedź modelu na plik), za każdym razem w innym formacie. `NN.json` to
formularz do importu, `NN.report.json` to plik źródłowy, czas, koszt, uwagi, raport reguł, propozycje słowników
i metryki, `slowniki.json` zbiera propozycje słowników. Przebieg z 2026-11-22:

| Materiał | Format | Czas | Koszt (USD) | Strony | Sekcje / pola z formularza | Błędy reguł |
|---|---|---|---|---|---|---|
| 1. Numer porządkowy nieruchomości | XLSX | 3,2 s | 0,0003 | 4 | 1 / 4 | 0 |
| 2. Zwrot opłaty skarbowej | PDF | 4,8 s | 0,0007 | 5 | 4 / 9 | 0 |
| 3. Wydanie zaświadczenia | JPG (skan) | 5,3 s | 0,0006 | 4 | 2 / 6 | 0 |
| 4. Wynajęcie świetlicy | ODS | 4,2 s | 0,0006 | 4 | 2 / 7 | 0 |
| 5. Stwierdzenie nadpłaty podatku | DOC | 4,2 s | 0,0006 | 4 | 3 / 9 | 0 |
| 6. Zajęcie pasa drogowego | XLSX | 8,2 s | 0,0012 | 5 | 5 / 19 | 0 |
| 7. Psy ras uznawanych za agresywne | PNG (skan) | 11,7 s | 0,0010 | 4 | 2 / 10 | 0 |
| 8. Deklaracja opłaty za odpady | ODS | 18,9 s | 0,0037 | 6 | 11 / 54 | 0 |
| 9. Stypendium, nagroda, wyróżnienie | DOCX | 14,1 s | 0,0026 | 7 | 10 / 34 | 0 |

Razem 0,011 USD. Czas to całe żądanie (odczyt, OCR skanów, model, kompilacja, walidacja). Strony liczą też
predefiniowane („Dane”, „Kontakt i zgody”, „Strona końcowa”), a sekcje i pola tylko te, które model opisał
z formularza (sekcje standardowe dodaje kompilator). Skaner bezpieczeństwa nie zgłosił nic w żadnym wyniku.
Propozycje słowników: rasy psów (7) i dyscypliny sportowe (9).

## Dowód spełnienia wymagań

`api/tests/test_wymagania.py` zawiera 13 testów. Każdy odpowiada jednemu punktowi treści zadania i jest nazwany
jego numerem. Testy nie wołają modelu ani sieci: sprawdzają materiały COI, wyniki powyżej i kod usługi, więc
trwają kilka sekund i nic nie kosztują.

```bash
npm run proof    # albo: cd api && uv run pytest tests/test_wymagania.py -v
```

### Test wszystkich wymagań na żywo

```bash
npm run proof:live:all
```

Ta komenda najpierw przetwarza usługą z prawdziwym modelem wszystkie 9 materiałów, z tych samych plików
i w tych samych formatach co `wyniki/`. Wyniki zapisuje w katalogu tymczasowym i na nich, zamiast na
zapisanych plikach, uruchamia te same 13 testów. Trwa kilkadziesiąt sekund, bo przetwarza kilka plików
(3 naraz). Potrzebuje `EDENAI_API_KEY` w `.env` i kosztuje ok. 0,01 USD. Przebieg z 2026-11-22: 13/13
w 40 s.

Test na żywo (`api/tests/test_na_zywo.py`) wysyła dowolny plik przez całą usługę z prawdziwym modelem, tak
jak przy sprawdzaniu na nowych plikach (pkt 6 zadania). Sprawdza klucze jak w referencjach COI, 0 błędów reguł,
stronę o sprawie, odwołania tylko do fragmentów dokumentu i czysty skan bezpieczeństwa, a potem wypisuje
podsumowanie i ścieżkę wynikowego JSON. Jedno wywołanie modelu (materiał 1: ok. 3 s, 0,0002 USD); bez opcji
`--na-zywo` jest pomijany.

```bash
npm run proof:live                                   # materiał 1
npm run proof:live -- --plik "ścieżka/do/wniosku.pdf"  # dowolny plik
```

Pozostałe testy w `api/tests/` (ok. 240) sprawdzają szczegóły każdego etapu.

## Co jeszcze robi rozwiązanie

Rozszerzenia z punktu 3.3 treści zadania:

- **Słowniki i dane inicjalne:** kraje, TERYT i numery kierunkowe przez `dictionaryName`; dane wnioskodawcy, adres
  i kontakt wstępnie wypełnione z danych logowania (`EXTERNAL_SYSTEM`), z możliwością edycji.
- **Nowe słowniki:** gdy pole lepiej zasiliłaby wspólna lista niż opcje wpisane w formularz albo wolny tekst, wynik
  zawiera propozycję słownika: nazwę, strukturę (`kod`, `nazwa`), pozycje i zastosowanie (strona, sekcja, pole).
  Reguły działają na etykietach pól, bez modelu: katalog list (stopień pokrewieństwa, rodzaj dokumentu tożsamości,
  rasy psów uznawanych za agresywne, sposób doręczenia, urzędy skarbowe, dyscypliny sportowe) i każde inne pole
  wyboru z co najmniej 8 opcjami. Propozycje są w `dictionaries` (`?details=true`) i w `wyniki/slowniki.json`; JSON
  formularza się nie zmienia, bo słownika nieznanego platformie nie da się zaimportować.
- **Zależności:** pola, sekcje i strony pokazywane warunkowo (`states` w jsonata), np. dane innej osoby tylko przy
  „Innej osoby”, sekcje jednego rodzaju wniosku tylko po jego wyborze.
- **Frontend:** wgranie plików (także wielu naraz), podgląd e-formularza zbudowanego z JSON-u (z działającymi
  warunkami i walidacją), podgląd JSON-u, pobranie wyniku.
- **Walidacja pól:** PESEL, NIP, REGON, kod pocztowy, e-mail, telefon, liczby; limity długości pól i licznik znaków.
- **Podstawa prawna i pouczenia** dosłownie ze źródła, na stronie końcowej, sprawdzane w kodzie (nigdy klauzula RODO,
  odwołania do pozycji na papierze ani podpowiedzi do pól).

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
| DeepSeek V4.1 Flash (`deepinfra/deepseek-ai/DeepSeek-V4.1-Flash`) | MIT, otwarte wagi | Eden AI (domyślnie). Wagi są publiczne; to duży model MoE, więc lokalnie praktycznie tylko na serwerze GPU |
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

## Development

Wymagane: Node.js 22+, [uv](https://docs.astral.sh/uv/), Tesseract z językiem polskim (OCR skanów; Windows:
`winget install UB-Mannheim.TesseractOCR`, potem `pol.traineddata` z
[tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) do katalogu z `AUTOFORMULARZ_TESSDATA_DIR`) i
LibreOffice (tylko binarne `.doc`). [Ollama](https://ollama.com) jest potrzebna tylko w trybie offline.

| Plik | Kto go czyta | Do czego |
|---|---|---|
| `.env.local` (katalog główny) | `npm run dev` i API uruchomione z `api/` | praca lokalna: jeden plik dla frontendu i API |
| `.env` (katalog główny) | `docker compose` | Docker |
| `api/.env` | API uruchomione z `api/` | opcjonalnie: nadpisuje `.env.local` |

Kolejność: `api/.env` nadpisuje `.env.local`, a zmienne środowiskowe nadpisują oba pliki. Pliki `.env*` są poza
gitem (oprócz `.env.example`).

1. Zależności: `npm install` oraz `cd api && uv sync`.
2. Konfiguracja: `cp .env.example .env.local`; ustaw `EDENAI_API_KEY` (albo `AUTOFORMULARZ_LLM_PROVIDER=ollama`
   i `ollama pull qwen3-vl:8b`). `AUTOFORMULARZ_AUTH_ENABLED=false` pozwala testować API bez tokenów.
3. API **z katalogu `api/`**: `uv run uvicorn autoformularz.main:app --reload` (http://localhost:8000/docs).
4. Frontend z katalogu głównego: `npm run dev` (http://localhost:3000).

| Polecenie | Co robi |
|---|---|
| `npm run check` | Biome, TypeScript, ruff i pytest (API i skrypty); uruchamia się też przed pushem |
| `cd api && uv run pytest` | testy API, w tym porównanie z referencyjnymi JSON-ami COI (materiały 1 i 5) |
| `cd api && uv run python -m autoformularz.results` | generuje `wyniki/` dla formularzy 2–9 z materiałów (`--only 2 3`, `--compile`: bez modelu, z zapisanych FormSpec) |
| `npm run smoke [url]` | sprawdza, czy kluczowe strony frontendu odpowiadają |
| `npm run slides` | buduje `docs/prezentacja.pdf` z `docs/prezentacja.md` |

Każde przetworzenie zapisuje metryki (czasy etapów, tokeny, koszt, rozmiar wyniku) jako jedną linię JSON w logu
(`docker compose logs api | grep metrics`) i w `metrics` odpowiedzi `?details=true`. Plik jest opisany skrótem
SHA-256, nigdy nazwą ani treścią.

Zasady zespołu: przez Eden AI tylko modele o otwartych wagach, które da się uruchomić lokalnie; zależności open
source bez copyleftu (licencja przy każdej w `api/pyproject.toml`); brak atrybucji AI w commitach (hook to
blokuje); nigdy nie commituj plików `.env`.
