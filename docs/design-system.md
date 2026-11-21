# Design system: formularze eUsług

Podgląd na żywo: `/design-system` (tokeny, przyciski, wszystkie pola) i `/design-system/formularze/*` (3 przykładowe formularze).
Źródło zasad: `materialy/Materiały do zadania dla Uczestników/HackNation - Standardy i dobre praktyki projektowania formularzy.pdf` oraz zrzuty eUsługi (wizualizacje `.docx`).

## Warstwy (atomic design)

| Warstwa | Gdzie | Co |
|---|---|---|
| Tokeny | `src/app/globals.css` | kolory (`page`, `primary`, `input`, `readonly`, `destructive`, `info`...), radius, font Lato |
| Atomy | `src/components/ui/*` | shadcn (Base UI), dostrojone do 40px pól, radius 4px |
| Molekuły | `src/components/form/fields.tsx` | jedno pole = jeden `field.type` z JSON |
| Struktura | `src/components/form/layout.tsx` | `FormSection`, `RepeatingSection`, `Stepper`, `FormNav`, `FormShell` |
| Sekcje predefiniowane | `src/components/form/sections.tsx` | sekcje ze standardu + logika SHOW |
| Organizmy | `src/components/forms/*` | gotowe formularze |

## Mapowanie typów z JSON na komponenty

| `field.type` | Komponent |
|---|---|
| `SECTION` | `FormSection` |
| `REPEATING_SECTION` | `RepeatingSection` |
| `TEXT_FIELD` | `TextField` (`readOnly`, `noValueLabel` = checkbox „Brak …”, `validators`) |
| `NUMBER` | `NumberField` |
| `DATEPICKER` | `DateField` |
| `TEXTAREA` | `TextareaField` |
| `RADIO` | `RadioField` |
| `CHECKBOX` | `CheckboxField` |
| `SELECT` | `SelectField` (powyżej 15 opcji lub `searchable` dostaje wyszukiwarkę) |
| `FILE_UPLOADER` | `FileUploaderField` (`formats`, `maxSizeMb`, `maxFiles`) |
| `TEXT_BLOCK` | `TextBlock` |
| `INFO_SECTION` | `InfoSection` (na stronie `FINISH` dozwolone razem z `TEXT_BLOCK`, ustalenie z mentorami) |
| `CONSENT_SECTION` | `ConsentSection` (nigdy luźne checkboxy na zgody) |
| tab `MAIN` / `FINISH` | `FormPage` w `FormShell` |

Walidatory (`src/lib/form/validators.ts`) mają nazwy z reguł technicznych: `PESEL`, `NIP`, `REGON`, `ZIP_CODE`, `EMAIL` (+ `PHONE`, `IBAN_PL`, `pattern`).

## Zasady (skrót ze standardu)

- Jedna kolumna, pola pogrupowane w sekcje tematyczne (białe karty na tle `page`).
- Kolejność stron: dane stron → sprawa → kontakt i oświadczenia → podsumowanie i podgląd (`FINISH`, bez pól).
- Pola wymagane są bez znacznika. Opcjonalne mają dopisek „(opcjonalnie)”.
- Dane z rejestru (MLPZ/PESEL) pokazuj jako `readOnly` (szare tło, bez ramki).
- Pokazuj tylko potrzebne pola: warunek SHOW = renderowanie warunkowe (`useWatch`). Ukryte pole nie jest walidowane.
- Błąd pojawia się pod polem: ikona i czerwony tekst, krótko, w stronie czynnej („Uzupełnij to pole.”). Fokus przechodzi na pierwsze błędne pole.
- Przyciski: jedna akcja `primary` na ekran („Dalej”, „Wyślij wniosek”), `outline` dla akcji wtórnych („Wstecz”, „Dodaj plik”), `link` do wyjścia („Przerwij wypełnianie”).
- Linki zewnętrzne: `ExternalLinkText` (ikona, bez kropki na końcu).
- Język: bez form zależnych od płci, krótkie zdania („Znam warunki…”, a nie „Zapoznałem/am się…”).
- WCAG 2.1 AA: kontrast tokenów jest sprawdzony, każde pole ma etykietę, a grupy wyboru mają `fieldset` i `legend`.

## Renderer z COI JSON

`<CoiFormView form={json} />` (`src/components/form/coi-form.tsx`) renderuje dowolny JSON w formacie importu COI: zakładki w kolejności `flow`, pola przez mapowanie z tabeli wyżej. Podgląd: `/podglad` (wzory 1 i 5 z `materialy/` + wczytanie własnego pliku, także odpowiedzi `?details=true`).

- `states` (`SHOW`, `READ_ONLY`): JSONata na kopii JSON-a z `__userAnswer` (`src/lib/form/coi.ts`), liczone po każdej zmianie odpowiedzi. Ukryte pole nie jest renderowane ani walidowane, ale jego odpowiedź zostaje.
- `validation`: `REQUIRED` + walidatory z reguł technicznych (`PESEL`, `NIP`, `REGON`, `ZIP_CODE`, `EMAIL`, `EPUAP`, `ADE`, `SERIAL_NUMBER_ID_CARD`). Toleruje `{}` zamiast `[]` (wzór 1).
- `defaultValue` + `EXTERNAL_SYSTEM` (`MLPZ.*`, `PESEL.*`): dane demo `MLPZ_DEMO`.
- `dictionaryName`: `Kraje`, `TERYT_*` (na razie lista województw, bez powiatu i gminy).

## Nowy formularz (ręcznie)

```tsx
<FormShell title="Wniosek o …" initialValues={daneZRejestru} pages={[
  { title: "Dane", type: "MAIN", content: <ApplicantSections office="Urząd Gminy X" /> },
  { title: "…", type: "MAIN", content: <MojaStrona /> },
  { title: "Kontakt i zgody", type: "MAIN", content: <><ContactSection /><ConsentsSection /></> },
  { title: "Strona końcowa", type: "FINISH", content: <PreviewSection /> },
]} />
```
