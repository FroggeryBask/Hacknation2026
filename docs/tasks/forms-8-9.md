# Zadanie (Ewelina): wyniki dla formularzy 8 i 9

Branch: `feat/forms-8-9`. Przejęte od Konrada (komentarz w PR #6 bez odpowiedzi, PR #8 dotyczył kompilatora i lintera).

Stan: **wszystkie 7 formularzy do oddania (2, 3, 4, 6, 7, 8, 9) w `wyniki/`, 0 błędów lintera.** Formularz 9 dobry.
Formularz 8 poprawny formalnie, ale logika warunków nie zgadza się z drukiem (patrz „Formularz 8: przegląd z
drukiem”).

## Diagnoza (bez modelu, `extract` na materiałach)

| Formularz | Źródło | Bloki | Przyczyna `LLM_TRUNCATED` |
|---|---|---|---|
| 8 (deklaracja odpadowa) | DOCX | 631 (397 krótszych niż 15 znaków) | DOCX skonwertowany z PDF: **każde słowo to osobne pole tekstowe** zakotwiczone do strony (`wp:anchor`, `positionV relativeFrom="page"`). Model dostaje `[b139] Oświadczam,` `[b140] że` … i musi dać rolę każdemu słowu RODO i pouczeń. |
| 9 (stypendium, nagroda, wyróżnienie) | DOCX | 267, czytelne | Trzy prawie identyczne wnioski w jednym pliku (`Połączenie 3 wniosków w 1` w nazwie materiału). Model opisuje każdy osobno, więc odpowiedź jest trzy razy dłuższa. |

Inne formaty tych samych formularzy: 8 PDF 337 bloków, XLSX/ODS 178; 9 PDF 402, XLSX/ODS 247.

Na obronie dostaniemy **nowe pliki** (treść zadania, pkt 6), więc poprawki muszą być ogólne: żadnych reguł pod
konkretny formularz, żadnego ręcznego poprawiania specu ani wyników.

## Co zostało zrobione

### Extract
- **DOCX: pola tekstowe zakotwiczone do strony składane w linie.** Kolejne pola `relativeFrom="page"` o tej samej
  wysokości (różnica Y ≤ połowa wysokości pola) to jedna linia, słowa w kolejności X. Formularz 8: 651 pól →
  318 linii, żadne słowo nie zginęło. Pola zakotwiczone do akapitu (formularz 2) bez zmian; pozostałe DOCX
  z materiałów czytają się bajt w bajt jak wcześniej.

### FormSpec i schemat dla modelu
- **Role jako zakresy:** `BlockRole` ma opcjonalne `to` (ostatni blok ciągu), `spec.roles()` rozwija zakresy.
  Wstecznie zgodne: stare spec bez `to` się wczytują.
- `block_roles` w schemacie **przed** `pages`: model najpierw odkłada pouczenia/RODO, potem opisuje pola.
- **`model_schema()`**: schemat wysyłany do modelu jest ostrzejszy niż `FormSpec` (który dalej wczytuje stare
  spec). Eden i Ollama **wymuszają schemat** (model wypisał dokładnie `maxItems` ról), więc reguły, które muszą
  zadziałać, idą do schematu, nie tylko do promptu:
  - `block_roles[].role` tylko INSTRUCTION, LEGAL_BASIS, STATEMENT, GDPR, SKIP; najwyżej 40 wpisów
    (wcześniej model wpisał 77 ról FIELD_LABEL/HEADING/OPTION ze 120 i zabrakło tokenów na strony),
  - `required` obowiązkowe w każdym polu (z wartością domyślną `true` model nigdy go nie pisał, więc każde pole
    wychodziło jako wymagane).

### Prompt (reguły ogólne)
- Kilka wersji tego samego wniosku = jeden formularz z polem „Rodzaj wniosku” i `show_if` na sekcjach, których
  nie ma we wszystkich wersjach (rozszerzenie III).
- Pouczenia, objaśnienia, podstawa prawna i RODO tylko w `block_roles` (zakresami), nigdy jako sekcje/pola INFO.
- `required` false dla „pola nieobowiązkowe”, „wypełnić tylko…”, „jeżeli…”, „dotyczy tylko…”.
- Stałe kwoty z druku do `description`; wybór jednej z sytuacji = SINGLE_CHOICE + pola z `show_if`;
  oświadczenie zmieniające sprawę = TAK/NIE, nie `consents`.

### Canon (`check.py`, bez modelu; działa dla nowych plików; wyniki 2–7 bez zmian)
- Sekcja o wnioskodawcy/składającym: wypadają tylko pola z części standardowej, reszta zostaje
  („Składający deklarację: właściciel / najemca …”, „Numer działki”). Częściowo tylko gdy własny tytuł sekcji
  dotyczy wnioskodawcy i co najmniej połowa pól jest standardowa (sekcja pełnomocnika z jednym numerem
  dowodu zostaje cała). Tytuły: dodane „składający”, „Adres zamieszkania / siedziby”.
- `dedupe`: powtórzona etykieta z innymi blokami źródła to kolejny wiersz tabeli, nie zapętlenie.
- `drop_broken_conditions`: warunek na nieistniejącym polu lub opcji jest usuwany, a pola, których dotyczył,
  są nieobowiązkowe (8: „Adres do korespondencji” był wymagany od każdego; 9: „Inna dyscyplina”).
- `printed_amounts_as_info`: pole, którego opis to sama kwota z druku („38 zł”), staje się informacją INFO.
- Kompilator: opcja w warunku dopasowana bez wielkości liter.

### Generator wyników
- Ucięta odpowiedź (`LLM_TRUNCATED`) zapisuje się do `wyniki/NN.truncated.txt` (w `.gitignore`).

## Wynik (Eden, Qwen3-VL 30B-A3B, 6 zapytań, 0,0358 USD)

| Seria | Zmiana | 8 | 9 |
|---|---|---|---|
| 1 | odczyt DOCX + prompt wariantów | ucięty: z każdej linii objaśnień osobna sekcja | **0 błędów, warunki na stronie trenera, 2 zgody → w `wyniki/`** |
| 2 | + zakresy ról, role przed `pages` | 0 błędów, ale model zignorował zakresy (role HEADING b12–b130) | bez warunków na sekcjach wariantów, 8 zgód (gorszy) |
| 3 | + reguły pól nieobowiązkowych w prompcie | ucięty: 120 ról, z czego 77 zakazanych | – |
| 4 | + `model_schema()` | **0 błędów, 34 role (zakresy), `required` zróżnicowane → w `wyniki/`** | – |

## Formularz 8: przegląd z drukiem (stan w `wyniki/`)

Dobrze: A organ (Prezydent Miasta Gdyni); B.1/B.3 dane i adres składającego → część standardowa, firma
rozpoznana (NIP/REGON), działka nieobowiązkowa; D.1, D.2 (nieobowiązkowe); D.3 rodzaj nieruchomości; E.3
warunkowo po TAK w poz. 34; E.1/E.2/E.4 tabele kompletne, stawki jako informacje; F kontakt → część
standardowa, zgoda na e-mail nieobowiązkowa; H/I podpis i adnotacja urzędu pominięte.

Źle:

| Pozycja | Druk | U nas | Waga |
|---|---|---|---|
| B.1 poz. 1 | trzeba zaznaczyć, kto składa | nieobowiązkowe | średnia |
| B.1 opcja 6 | „inny podmiot (należy podać jaki)” | brak pola „jaki” | średnia |
| **B.2 współmałżonek** | tylko przy **opcji 2** „współwłaściciel (wspólność majątkowa)” | warunek na **opcji 1** | **wysoka** |
| B.4 adres do korespondencji | tylko gdy inny niż B.3 | zawsze widoczny (nieobowiązkowy) | niska |
| **C okoliczności** | **jedna** z 4 okoliczności + data | 4 osobne daty, wszystkie nieobowiązkowe | **wysoka** |
| D.3 poz. 34 TAK/NIE | trzeba zaznaczyć | nieobowiązkowe | niska |
| **D.4 kompostownik** | kratka, tylko domy jednorodzinne | zgoda w `consents` (potwierdza każdy) | **wysoka** |
| **E.1 / E.2** | E.2 tylko przy kompostowniku (poz. 35), E.1 pozostali | obie zawsze widoczne | **wysoka** |
| G załączniki | dołącza się załącznik A/B, pełnomocnictwo | TAK/NIE zamiast pól FILE | średnia |

**Dlaczego kod tego nie poprawi:** to rozumienie druku (która kratka czym steruje, co jest alternatywą).
Kod widzi tylko FormSpec. Reguły oparte na tekście bloków odpadają, bo model przypisuje polom bloki
z przesunięciem (np. „Kraj” → b30, choć „8. Kraj 9. Województwo 10. Gmina” to jeden blok b31; „Kod pocztowy” →
nagłówek B.4).

## Formularz 9: drobne braki
- „Inna dyscyplina” zawsze widoczna (nieobowiązkowa): model dał warunek na opcji, której nie ma na liście.
- Dyscypliny jako dwa pola wielokrotnego wyboru (rodzaj + lista).
- Model nie użył zakresów ról (seria 1 była przed `model_schema()`).

## Co się nie udało
- Prompt sam nie wystarcza: model 30B ignorował zakazy (role HEADING) i reguły (daty okoliczności, kompostownik).
  Zadziałało dopiero wymuszenie w schemacie.
- Model jest niedeterministyczny między seriami mimo `temperature=0` (9: seria 2 gorsza od 1).
- Ponowne próby dla 8 to loteria: 2 z 4 ucięte.

## Sugestie (kolejność)
1. **Prompt: ogólne reguły zależności** (bez nazw z formularza 8): „wypełnić tylko w przypadku zaznaczenia
   poz. X” → `show_if` na tej opcji; „dotyczy wyłącznie …” → `show_if` na sekcji; „do deklaracji należy dołączyć
   / załącznik” → pole FILE; opcja „inne (podać jakie)” → pole tekstowe z `show_if`. 1–2 próby (~0,012 USD).
2. **Mocniejszy model do wyników** (wymaga zgody zespołu, `docs/eden-budzet.md`: „nie zmieniaj modelu bez
   uzgodnienia”): `Qwen3.6-35B-A3B` (nowszy, ta sama rodzina, MoE ~3B aktywnych, jest w Ollamie `qwen3.6:35b-a3b`
   ~24 GB i na Eden). Porównać na formularzu 8 (~0,006 USD/próba).
3. Jeśli dalej źle: oddać obecną wersję i opisać ograniczenia w materiałach (uczciwie dla jury).
4. Kod (możliwe, niski priorytet): pola INFO/FILE dla „Załącznik …” z TAK/NIE; `required` dla pól SINGLE_CHOICE
   bez warunku (wybór zwykle trzeba zaznaczyć) – do sprawdzenia na 2–7, czy nie psuje.

## Model w Dockerze (research, do testu przy Dockerze)
- `qwen3-vl:30b-a3b` to **MoE z ~3B aktywnych parametrów**: generuje szybciej niż „mały” `qwen3-vl:8b` (u
  dostawców ~53 vs ~37 tok/s), na CPU prawdopodobnie też (nie zmierzone), ale potrzebuje ~20 GB RAM (8B: ~6 GB).
  Wyniki w `wyniki/` są z 30B-A3B, więc ten model w Dockerze usunąłby rozjazd „wyniki z 30B, Docker z 8B”.
- Kandydaci dostępni i na Eden, i w Ollamie: `qwen3.6:35b-a3b` (~24 GB), `gemma4:26b` (MoE ~4B aktywnych,
  Apache-2.0; na Eden bardzo tani), `gemma4:e4b` (mały, na słaby sprzęt bez GPU).
- Do zmierzenia przy teście Dockera (formularz 2, potem 8/9): czas i jakość `qwen3-vl:8b` vs
  `qwen3-vl:30b-a3b` (i ewentualnie `gemma4:26b`). Zmiana modelu to tylko `AUTOFORMULARZ_LLM_MODEL` + README.

## Ryzyka dla Dockera (Ollama)
Załatwione w `feat/docker`: `num_ctx=24576`, `timeout=1800`, model 8B domyślnie (docs/tasks/docker-docs.md).

- `llm_num_ctx=16384` obejmuje prompt i odpowiedź. Formularze 8/9: ~9–10 tys. tokenów promptu + 6–8 tys.
  odpowiedzi ≈ granica okna. Podnieść np. do 24576 (koszt: ~1–2 GB RAM).
- `llm_timeout_s=600`: model 8B na CPU ~5–10 tok/s, czyli 6 tys. tokenów to 10–20 min. Duże formularze na CPU
  nie zdążą. Zmierzyć, podnieść limit, w README podać realny czas na CPU i zalecić GPU.
- `llm_max_tokens=8000` zostaje: udany formularz 8 to ~7 tys. tokenów; limit chroni przed kosztem zapętlenia.

## Poza zakresem
Kolejność czytania w PDF (osobne zadanie), słownik ras psów, materiały do Hacktribe.
