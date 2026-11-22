# Wyjaśnienia niespójności w materiałach

Niespójności znalezione w `materialy/` i ustalenia zespołu (po rozmowie z mentorami COI). Ścieżki względem `materialy/`.

## Ustalone

### Słowniki
- Problem: `Materiały do zadania dla Uczestników/Hacknation - Słowniki  (1).docx` podaje nazwy opisowe (Województwo, Powiat, Gmina, Miejscowość, Kraje, Numery kierunkowe). Przykładowe JSON-y używają `dictionaryName`: `TERYT_4G_DOWODOWY`, `TERYT_DOWODOWY`, `Kraje` (przykład 1: linie 288, 389, 660, 778, 1029, 1052; przykład 5: 311, 412, 645, 765, 1017, 1041). „Standardy…” też piszą `TERYT_4G_DOWODOWY`.
- Ustalenie: możemy korzystać z dowolnych słowników, a w razie potrzeby tworzyć własne. W praktyce powinny wystarczyć te dostarczone (nazwy jak w przykładach).

### MLPZ
- MLPZ = moduł logowania profilem zaufanym. W materiałach to źródło danych inicjalnych „Dane zalogowanego użytkownika” (`Materiały do zadania dla Uczestników/Dane inicjalne - materialy dodatkowe do zadania rozszerzającego (2).pdf`).
- Dostępne źródła: `PESEL` (Rejestr PESEL), `PESEL_ADDRESS` (dane zameldowania), `MLPZ` (profil zalogowanego). Pole zasilane: `"readOnly": true`, `"defaultValue": "<ŹRÓDŁO>.<atrybut>"`, `"defaultValueType": "EXTERNAL_SYSTEM"`.
- Przykład 1 bierze imię i nazwisko z `MLPZ.*` (bez pola PESEL, bo druk o niego nie pyta). Przykład 5 bierze imię, nazwisko i PESEL z `PESEL.*` (druk wymaga PESEL). Oba źródła są poprawne.

### Stack: bez Supabase i Vercel
- Treść zadania (`COI - Pełna treść zadania konkursowego.pdf`, s. 3 „Wymagania techniczne”) zakazuje zależności typu zewnętrzne API / SaaS, a s. 5 „Konteneryzacja” wymaga Dockera.
- Ustalenie: usuwamy Supabase i Vercel, wszystko działa w kontenerach Docker.

### Strona FINISH: INFO_SECTION czy TEXT_BLOCK
- Problem: „Reguły techniczne…” (`Materiały do zadania dla Uczestników/Reguły techniczne konfiguracji formularzy i pól na formularzu - materiał do zadania obligatoryjnego  (2).docx`) dopuszczają na stronie `finish` „wyłącznie pole typu sekcja informacyjna INFO_SECTION”. „Standardy…” (rozdz. „Podsumowanie i podgląd”) każą tam dać „pole typu blok tekstu”, a przykłady 1 i 5 mają `SECTION` z `TEXT_BLOCK` (przykład 1: FINISH linia 1609, TEXT_BLOCK 1633; przykład 5: FINISH 1720, TEXT_BLOCK 1744).
- Ustalenie (mentorzy COI): **można obydwu**. Linter nie powinien zgłaszać `TEXT_BLOCK` na stronie końcowej. Pola do wprowadzania danych na tej stronie nadal są zabronione.

### `repetingSectionGrid` czy `repeatingSectionGrid`
- Literówka tylko w schemacie `Materiały do zadania dla Uczestników/importowanyPlikJsonSchemat (1).json:85` i w `OpisImportowanegoPlikuJSON (1).docx`. Przykłady 1 i 5 oraz „Reguły techniczne…” (przykład zapytania jsonata) używają `repeatingSectionGrid`.
- Ustalenie: `repeatingSectionGrid`.

### Uruchomienie rozwiązania do oceny
- Ustalenie (mentorzy COI): kod wgrywamy na platformę Hacktribe (termin: 22.11.2026, 11:00, regulamin HackNation §4 pkt 3).
- Konsekwencja: rozwiązanie musi uruchomić się u kogoś innego, bez naszej pomocy, z samego README i `docker compose up --build`. README musi jasno podawać wymagania (RAM, dysk, czas pobrania modelu ~6 GB, GPU opcjonalne) i działać na samym CPU.

### Eden AI a zakaz LLM przez API
- Treść zadania (s. 3): „rozwiązanie nie może używać modeli LLM dostępnych wyłącznie przez API (ale można ich używać do pisania/testowania/projektowania kodu)”.
- Ustalenie (decyzja zespołu 2026-11-21): Eden AI organizatorów może działać także w oddawanym rozwiązaniu (domyślnie), ale tylko z modelami o otwartych wagach, które da się uruchomić lokalnie. Tryb w pełni lokalny (Ollama, `--profile ollama`) zostaje i nie potrzebuje żadnego zewnętrznego API.

### LibreOffice (konwersja .doc i .ods)
- Po co: `.doc` (stary binarny format Worda) nie ma sensownego parsera w Pythonie na licencji innej niż copyleft, więc konwertujemy go do `.docx` przez LibreOffice uruchamiane jako osobny proces. `.ods` czytamy bez LibreOffice, wprost z XML.
- Ustalenie (mentorzy COI): dopuszczalne tylko przy licencji, która nie wymaga udostępnienia naszego kodu. **Trzeba uważać.**
- Stan: LibreOffice ma licencję MPL-2.0 (słaby copyleft, obowiązek publikacji dotyczy tylko zmienionych plików samego LibreOffice). Nie modyfikujemy go ani nie linkujemy, tylko wywołujemy binarkę, więc naszego kodu to nie obejmuje. Zrobione: `.ods` jest czytany z XML, LibreOffice zostało tylko dla `.doc` (obraz bez niego: `--build-arg WITH_LIBREOFFICE=0`), licencje opisane w README.

### Numeracja rozszerzeń
- Problem: w pkt 3.3 treści zadania V to wizualizacja, VI to walidacje, a w kryteriach oceny „Punkt V (Walidacje pól)”.
- Ustalenie (mentorzy COI): punktowane są **i walidacja, i wizualizacja**.

## Do potwierdzenia
- Otwarte decyzje z [pipeline.md](pipeline.md): pole „(jeśli dotyczy)” bez pytania sterującego oraz cache wyników w pamięci po hashu pliku.
