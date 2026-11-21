# Zadanie: wspólny kontrakt Document i FormSpec (pierwszy wspólny PR)

## Cel
Odblokować równoległą pracę według [pipeline.md](../pipeline.md) i [podzial-pracy.md](../podzial-pracy.md).
Ewelina (extract, check, canon), Konrad (spec, prompt, kompilator) i Gabrysia (UI) potrzebują tych samych
struktur danych, zanim zaczną je wypełniać. Ten PR ustala kształt tych struktur i daje działającą, prostą
implementację, żeby nikt nie czekał na cudzą pracę.

## Zakres
1. Typy `Document`, `Block`, `FieldCandidate` w `api/src/autoformularz/document.py` (krok 2 z pipeline.md).
2. `extract.py` zwraca `Document`: na razie jeden blok na wiersz obecnego tekstu (ID `b1`, `b2`, … w kolejności
   czytania), typ bloku, numer strony dla PDF i proste wykrywanie kandydatów na pola (`____`, `......`, `☐`,
   „Etykieta:” bez wartości). Skany nadal idą jako obrazy, bez bloków (transkrypcja VLM to osobne zadanie).
3. FormSpec odwołuje się do ID bloków: `FieldSpec.blocks`, `SectionSpec.blocks`, role bloków
   `FormSpec.block_roles` (krok 3). Pola mają wartości domyślne, więc stare FormSpec dalej działają.
4. Prompt pokazuje bloki z ID (`[b12] …`) i prosi o odwołania do nich zamiast przepisywania tekstu.
5. `?details=true` dostaje `document` (bloki i kandydaci) i `coverage` (wstępne pokrycie: bloki i kandydaci
   bez odwołania, odwołania do nieistniejących bloków).

Poza zakresem: prawdziwe bloki z komórek tabel i opcji, transkrypcja skanów, pełne kroki check i canon,
kompilator biorący tekst z bloków. Kompilator w tym PR się nie zmienia.

## Wynik
- Te same pliki dają ten sam JSON COI co wcześniej (kompilator bez zmian, testy wzorców zielone).
- `POST /api/v1/forms?details=true` zwraca dodatkowo `document` i `coverage` w opisanym niżej kształcie.
- Kontrakt opisany w `pipeline.md` (sekcja „Kontrakt”), decyzja w `decisions.md`.
- Testy: kształt `Document` dla DOCX, XLSX, PDF i obrazu, kandydaci na pola, prompt z ID bloków,
  pokrycie, odpowiedź `?details=true`. `npm run check` przechodzi.

## Kto co dalej podmienia
- Ewelina: lepszy podział na bloki (komórki, opcje), skany → bloki, pełne check i canon (nowy plik `check.py`).
- Konrad: kompilator bierze tekst prawny z bloków według `block_roles`, strojenie promptu.
- Gabrysia: widok źródła i formularza na podstawie `document.blocks`, `FieldSpec.blocks` i `coverage`.
