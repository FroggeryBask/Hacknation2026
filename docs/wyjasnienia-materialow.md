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

## Do potwierdzenia

### Strona FINISH: INFO_SECTION czy TEXT_BLOCK
- Reguła: `Materiały do zadania dla Uczestników/Reguły techniczne konfiguracji formularzy i pól na formularzu - materiał do zadania obligatoryjnego  (2).docx`: na stronie `finish` „może być dodane wyłącznie pole typu sekcja informacyjna INFO_SECTION”.
- Przykłady mają tam `SECTION` z `TEXT_BLOCK`: przykład 1 (FINISH linia 1609, TEXT_BLOCK 1633), przykład 5 (FINISH 1720, TEXT_BLOCK 1744).
- Wstępnie: robimy jak w przykładach, bo formularze często muszą zawierać na końcu informacje prawne i podstawę prawną (ustawę).

### `repetingSectionGrid` czy `repeatingSectionGrid`
- Literówka tylko w schemacie `Materiały do zadania dla Uczestników/importowanyPlikJsonSchemat (1).json:85` i w `OpisImportowanegoPlikuJSON (1).docx`. Przykłady 1 i 5 oraz „Reguły techniczne…” używają `repeatingSectionGrid`.
- Wstępnie: trzymamy się przykładów (`repeatingSectionGrid`).

### Sprzęt na obronie
- Materiały nie mówią, czy obrona jest na CPU czy GPU, czy model ma być w obrazie czy jako volume, ani czy jest internet. Od tego zależy rozmiar modelu.

### Eden AI a zakaz LLM przez API
- Treść zadania (s. 3): „rozwiązanie nie może używać modeli LLM dostępnych wyłącznie przez API (ale można ich używać do pisania/testowania/projektowania kodu)”. Eden AI to API, więc w oddawanym rozwiązaniu tylko lokalny model (Ollama); Eden wyłącznie do pracy/testów.
