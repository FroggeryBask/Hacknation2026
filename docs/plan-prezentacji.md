# Plan prezentacji (maks. 10 slajdów)

1. **Tytuł:** „Papierowy wniosek → e-formularz”.
2. **Problem i cel:** urzędnik przepisuje wniosek ręcznie, a każdy urząd robi to po swojemu. Cel: dostajemy plik, oddajemy JSON gotowy do importu do COI.
3. **Jak to działa:**
   - Plik (8 formatów) → `POST /api/v1/forms` → JSON → e-formularz
   - Etapy: odczyt → presort → model → sprawdzenie → kompilator → linter
   - Model tylko klasyfikuje bloki i wypełnia mały FormSpec, a JSON COI buduje kod.
4. **Przed modelem i po modelu:**
   - Presort: kod sam rozpoznaje klauzulę RODO i elementy potrzebne tylko na papierze (podpis, data, „wypełnia urząd”, stopki). Rozpoznaje też dane wnioskodawcy z szablonu, przypisy i powtórzone wersje wniosku. Nie wysyła ich do modelu, więc prompt jest krótszy o 30–80% i tańszy.
   - Po modelu: przypis „dane nieobowiązkowe” decyduje o polach opcjonalnych. Pola zmyślone, czyli bez miejsca na papierze, są usuwane.
   - Zgody i oświadczenia model pisze przed stronami, więc nie giną, gdy odpowiedź zostanie ucięta.
5. **Budowanie JSON dla COI (kompilator, bez modelu):**
   - Część standardowa z szablonów: urząd, wnioskodawca, adres, pełnomocnik, opłata skarbowa, kontakt, zgody i podgląd, z tymi samymi techName i zapytaniami co we wzorach COI.
   - Warunki pokazywania pól w JSONata (`states`), także dla sekcji powtarzalnych i kilku wersji jednego wniosku (formularz 9).
   - Walidacja: pola wymagane oraz PESEL, NIP, REGON, kod pocztowy i e-mail, rozpoznawane także po etykietach.
   - Kanon: usuwa duplikaty sekcji, sekcje szablonu, wybory z jedną opcją i pola powtarzające tytuł.
   - Stabilne identyfikatory (UUIDv5): ten sam plik daje ten sam JSON.
   - Format pilnowany testami, które porównują wynik ze wzorcami COI.
6. **Kontrola jakości:**
   - Pokrycie: które bloki dokumentu trafiły do formularza.
   - Skan bezpieczeństwa wygenerowanego formularza: prośby o hasła, PIN, kody SMS i dane karty; linki spoza gov.pl albo bez HTTPS; tekst skierowany do modelu (prompt injection, PL i EN); ukryte znaki, HTML i skrypty; bardzo długie etykiety. Skan tylko ostrzega i nigdy nie zmienia JSON-a.
7. **Interfejs (demo):** zrzuty postępu na żywo oraz formularza z sekcją warunkową i błędem walidacji.
   - Dynamiczne, warunkowe formularze z walidacją
   - Postęp na żywo; anulowanie zatrzymuje model i oszczędza tokeny
   - Prosty interfejs, który chroni przed utratą postępów
   - Link do klauzuli informacyjnej przy zgodzie
   - Dostępność (a11y)
8. **Zamknięty system:**
   - Docker, jedno polecenie; oficjalne obrazy, przypięte wersje, użytkownik bez roota
   - Jedyne zewnętrzne AI to Eden AI (od organizatorów, tylko modele open-weight); opcja offline na lokalnej Ollamie
   - Zależności open source bez copyleftu
   - Pliki tylko w pamięci, bez bazy danych i bez zapisu
9. **Kompletność i wyniki:** 7/7 formularzy, 0 błędów lintera, punkty I–VI z zadania, czas na formularz.
10. **Jakość kodu, co dalej, zespół i linki:** liczba testów (273 testy API), `npm run check`, dokumentacja decyzji; imiona, linki do repozytorium i filmu.

Później, być może: informacje o ustawach.

## Do poprawienia w `docs/prezentacja.md`
- „Lokalny model 8B” (podtytuł, slajd o wdrożeniu): domyślnie Eden AI z DeepSeek V4.1 Flash, Ollama (qwen3-vl:8b) jako opcja offline.
- „Tekst prawny dosłownie ze źródła”: opcja domyślnie wyłączona (`AUTOFORMULARZ_COPY_SOURCE_TEXT=false`).
- „Każdy blok ma pole, tekst albo jawne pomiń”: zastąpić slajdem o pokryciu.
