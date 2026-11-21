# Zadanie (Konrad): kompilator i linter na kontrakcie Document

## Cel
Pierwszy krok Konrada po PR „document-contract” ([podział pracy](../podzial-pracy.md)): kompilator korzysta
z bloków źródła tam, gdzie standard pozwala przenieść tekst, a linter pilnuje warunków i ustalenia z mentorami.
Branch: `feat/compiler-lint`. Docker od zera i dokumentacja architektury to osobne zadanie.

## Co mówią materiały (na tym opiera się zakres)
- Standard, „Oświadczenie”: oświadczenia i zgody mają być „krótkie, jednoznaczne”, „neutralne językowo”.
  **Nie kopiujemy ich dosłownie**: zostają w `consents` w formie od modelu.
- Standard, klauzula informacyjna: „zasadą jest niezamieszczanie takich treści na formularzu”, tylko odnośnik.
  **Bloków RODO nie przenosimy**: zostaje sekcja zgód z linkiem do klauzuli.
- Standard, „Podsumowanie i podgląd”: na ostatniej stronie bloki tekstu z informacjami dla użytkownika.
  Mentorzy: na stronie końcowej wolno `INFO_SECTION` i `TEXT_BLOCK`.
- Schemat importu: `flow.links` ma tylko `source` i `target`, bez warunków. Dynamika (rozszerzenie III) jest
  więc w `states` sekcji i pól, nie w przejściach między stronami.

## Zakres
1. Linter: usunąć ostrzeżenie `FINISH_TEXT_BLOCK` (ustalenie z mentorami).
2. Linter: warunki w `states`:
   - opcja z warunku istnieje w polu sterującym (`STATE_UNKNOWN_OPTION`, błąd; pomijane dla pól ze słownikiem),
   - pole nie zależy od samego siebie i nie ma cykli zależności (`STATE_CYCLE`, błąd),
   - pole sterujące jest przed polem zależnym (`STATE_FORWARD_REF`, ostrzeżenie).
3. Kompilator: bloki z rolą `LEGAL_BASIS` i `INSTRUCTION` trafiają **dosłownie** na stronę końcową jako
   `TEXT_BLOCK` w sekcjach „Pouczenie” i „Podstawa prawna” (przed podglądem), w kolejności z dokumentu.
   `STATEMENT`, `GDPR` i `SKIP` nie są kopiowane (patrz wyżej). Bez dokumentu (np. `/compile`) wynik bez zmian.
4. Pipeline przekazuje `Document` do kompilatora.

## Wynik
- Wzorce 1 i 5 dalej bez błędów lintera, testy porównania ze wzorcem zielone.
- Nowe testy: każda nowa reguła lintera (błąd wykryty, wzorce czyste), tekst prawny dosłownie z bloków,
  role pomijane zgodnie ze standardem, brak zmian bez dokumentu.
- `decisions.md`: linia o stronie końcowej poprawiona, nowa linia o tym, które role kopiujemy.
- `npm run check` przechodzi.

## Poza zakresem
Docker od zera i pomiary czasu, README i dokumentacja architektury, strojenie promptu na formularzach 2–9.
