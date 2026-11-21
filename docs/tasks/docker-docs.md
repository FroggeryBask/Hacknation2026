# Zadanie (Konrad): Docker od zera, README i dokumentacja architektury

## Cel
Jury uruchamia rozwiązanie u siebie z samego README i `docker compose up --build`, także na CPU
(ustalenie z mentorami). Dokumentacja architektury jest wymaganiem obowiązkowym (treść zadania, 3.2.II).
Branch: `feat/compiler-lint` (razem z kompilatorem i linterem).

## Co mówią materiały
- Treść zadania, „Konteneryzacja”: kompletna konfiguracja Docker, oficjalne obrazy, jawne wersje bez `latest`,
  użytkownik bez uprawnień, tylko potrzebne porty, sekrety w runtime.
- „Dokumentacja”: README z instrukcją budowania obrazu, uruchomienia, opisem konfiguracji i REST API.
- „Biblioteki”: tylko open source bez copyleft; brak zewnętrznych API, MCP, SaaS i LLM dostępnych tylko przez API.
- Mentorzy: LibreOffice tylko przy licencji, która nie wymaga udostępnienia naszego kodu.

## Zakres
1. Start od zera bez wyścigów: model pobiera się dopiero, gdy Ollama odpowiada, API startuje po pobraniu modelu.
2. Pomiar na tej maszynie (CPU, Docker Desktop na WSL2): czas budowania obrazów, pobrania modelu, pierwszej
   i kolejnej odpowiedzi dla formularza, zużycie pamięci. Wynik i wymagania sprzętowe w README.
3. `docs/architektura.md`: komponenty, przepływ danych, kontrakty, bezpieczeństwo, wdrożenie i koszt,
   decyzje, licencje (w tym LibreOffice MPL-2.0 jako osobny proces).
4. README: wymagania sprzętowe, czasy, licencje, odnośnik do architektury.

## Wynik
- `docker compose up --build` na pustym środowisku kończy się działającym API i frontendem bez ręcznych kroków
  poza ustawieniem `AUTOFORMULARZ_JWT_SECRET`.
- Zmierzone czasy i wymagania wpisane w README (z opisem sprzętu, na którym mierzono).
- `docs/architektura.md` gotowe do oddania, z tabelą licencji.
- `npm run check` przechodzi.

## Stan
- Zrobione: kolejność startu w `docker-compose.yml`, `docs/architektura.md`, wymagania i licencje w README.
- Pomiar przerwany na budowaniu obrazów (łącze ok. 100 kB/s). Drugi pomiar (2026-11-21, Ryzen 7 4800H, 16 GB RAM,
  Docker 8 GB): stack z nakładką Eden wstaje w 1 min 45 s (`api` z cache), formularz 2 przez API w kontenerze 80 s,
  formularz 8 122 s, oba 0 błędów lintera, razem 0,008 USD. Ollama w Dockerze na CPU **nie zmierzona** (Docker ma
  7,7 GB, model z kontekstem 24576 zajmuje 9,4 GB; potrzebny `.wslconfig` z `memory=12GB`).
- Ustawione po pomiarze: `llm_num_ctx=24576` (formularz 8: prompt ~9–10 tys. + odpowiedź do 8 tys. > 16384),
  `llm_timeout_s=1800` (8B na CPU kilka tok/s), domyślnie zostaje `qwen3-vl:8b` (30B-A3B potrzebuje ~20 GB RAM,
  opisany w README jako opcja dla maszyn z ≥ 32 GB).
- Demo na Eden AI (uzgodnione z mentorami): nakładka `docker-compose.eden.yml` (bez `ollama` i `model`, klucz tylko
  w `api`). Domyślny `docker-compose.yml` dalej uruchamia model lokalnie. Koszty: `llm.EDEN_USAGE` (Ewelina), suma
  w `GET /health` (`usage`). Żadne zapytanie do Eden nie zostało wysłane (brak klucza).
- Platformy: Windows, macOS (Intel, Apple Silicon), Linux (x86_64, ARM64); polecenia w README dla każdego systemu.
- Do zrobienia przez frontend: `sharp` (LGPL-3.0) w obrazie `web`, patrz `docs/architektura.md`, „Licencje”.

## Ograniczenia
Pomiar jest z jednej maszyny (laptop, i5-11300H, 16 GB RAM, bez użycia GPU w Dockerze). GPU w Dockerze
opisujemy jako opcję, bez pomiaru.
