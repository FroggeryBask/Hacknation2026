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
- Pomiar przerwany na budowaniu obrazów (łącze ok. 100 kB/s): czasy odpowiedzi modelu w Dockerze **do zmierzenia**
  na szybszym łączu i z limitem RAM dla Dockera ≥ 10 GB.
- Demo na Eden AI (uzgodnione z mentorami): nakładka `docker-compose.eden.yml` (bez `ollama` i `model`, klucz tylko
  w `api`). Domyślny `docker-compose.yml` dalej uruchamia model lokalnie. Koszty: `llm.EDEN_USAGE` (Ewelina), suma
  w `GET /health` (`usage`). Żadne zapytanie do Eden nie zostało wysłane (brak klucza).
- Platformy: Windows, macOS (Intel, Apple Silicon), Linux (x86_64, ARM64); polecenia w README dla każdego systemu.
- Do zrobienia przez frontend: `sharp` (LGPL-3.0) w obrazie `web`, patrz `docs/architektura.md`, „Licencje”.

## Ograniczenia
Pomiar jest z jednej maszyny (laptop, i5-11300H, 16 GB RAM, bez użycia GPU w Dockerze). GPU w Dockerze
opisujemy jako opcję, bez pomiaru.
