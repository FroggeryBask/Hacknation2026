"use client";

import {
  CheckboxField,
  ConsentSection,
  DateField,
  FileUploaderField,
  InfoSection,
  NumberField,
  RadioField,
  SelectField,
  TextareaField,
  TextBlock,
  TextField,
} from "@/components/form/fields";
import { FormProvider, useForm } from "@/components/form/form-context";
import {
  FormNav,
  FormSection,
  RepeatingSection,
  Stepper,
} from "@/components/form/layout";
import {
  AddressSection,
  KRAJE,
  RODO_CONSENT,
  WOJEWODZTWA,
} from "@/components/form/sections";
import { Button } from "@/components/ui/button";
import { EMAIL, PESEL } from "@/lib/form/validators";

function Demo({ type, children }: { type: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <code className="self-start rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-xs text-secondary-foreground">
        {type}
      </code>
      {children}
    </div>
  );
}

export function FieldDemos() {
  const form = useForm({
    tylko_odczyt: "Urząd Gminy Ulan-Majorat",
    blad_email: "jan.kowalski@",
  });
  return (
    <FormProvider form={form}>
      <div className="flex flex-col gap-4">
        <FormSection
          title="Pola (molekuły)"
          description="Każde pole odpowiada typowi komponentu z reguł technicznych (field.type w JSON). Pola wymagane nie mają znacznika, opcjonalne mają dopisek „(opcjonalnie)”."
        >
          <Demo type="TEXT_FIELD">
            <TextField
              name="demo_text"
              label="Imię"
              placeholder="Np. Anna"
              required
            />
          </Demo>
          <Demo type="TEXT_FIELD · readOnly (dane z rejestru)">
            <TextField name="tylko_odczyt" label="Nazwa urzędu" readOnly />
          </Demo>
          <Demo type="TEXT_FIELD · checkbox wyłączający pole">
            <TextField
              name="demo_ulica"
              label="Ulica"
              placeholder="Np. Polna, aleja Leśna, plac Lipowy, skwer Słoneczny"
              noValueLabel="Brak nazwy ulicy"
              required
            />
          </Demo>
          <Demo type="TEXT_FIELD · walidator PESEL">
            <TextField
              name="demo_pesel"
              label="Numer PESEL"
              inputMode="numeric"
              maxLength={11}
              validators={[PESEL]}
              required
            />
          </Demo>
          <Demo type="TEXT_FIELD · opcjonalne + EMAIL">
            <TextField
              name="blad_email"
              label="Adres e-mail"
              type="email"
              validators={[EMAIL]}
            />
          </Demo>
          <Demo type="NUMBER">
            <NumberField name="demo_number" label="Kwota" required />
          </Demo>
          <Demo type="DATEPICKER">
            <DateField name="demo_date" label="Termin od" required />
          </Demo>
          <Demo type="TEXTAREA">
            <TextareaField
              name="demo_textarea"
              label="Uzasadnienie"
              description="Uzasadnij, dlaczego Twoim zdaniem powstała nadpłata."
              required
            />
          </Demo>
          <Demo type="RADIO">
            <RadioField
              name="demo_radio"
              label="Wybierz, w czyim imieniu wnioskujesz"
              options={[
                "Swoim",
                "Innej osoby",
                "Osoby prawnej lub jednostki organizacyjnej",
              ]}
              required
            />
          </Demo>
          <Demo type="CHECKBOX">
            <CheckboxField
              name="demo_checkbox"
              label="Wybierz wyposażenie"
              options={["Kuchnia", "Nagłośnienie", "Stoły i krzesła"]}
            />
          </Demo>
          <Demo type="SELECT (≤ 15 opcji)">
            <SelectField
              name="demo_select"
              label="Województwo"
              options={WOJEWODZTWA.slice(0, 8)}
              required
            />
          </Demo>
          <Demo type="SELECT z wyszukiwarką (> 15 opcji)">
            <SelectField
              name="demo_combobox"
              label="Kraj"
              options={KRAJE}
              required
            />
          </Demo>
          <Demo type="FILE_UPLOADER">
            <FileUploaderField
              name="demo_file"
              label="Plik z potwierdzeniem przelewu"
              formats={["pdf"]}
              required
            />
          </Demo>
          <Demo type="TEXT_BLOCK">
            <TextBlock>
              <p>
                Opłata skarbowa za pełnomocnictwo wynosi <strong>17 zł</strong>.
              </p>
            </TextBlock>
          </Demo>
          <Demo type="INFO_SECTION">
            <InfoSection title="Ważne">
              Zanim wyślesz formularz, sprawdź dane na podglądzie.
            </InfoSection>
          </Demo>
          <Demo type="CONSENT_SECTION">
            <ConsentSection name="demo_zgody" consents={[RODO_CONSENT]} />
          </Demo>
          <Button
            variant="outline"
            className="self-start"
            onClick={() => form.validate()}
          >
            Sprawdź walidację wszystkich pól
          </Button>
        </FormSection>

        <h2 className="mt-6 text-xl font-bold">Struktura</h2>
        <Demo type="Stepper (nawigacja po stronach)">
          <Stepper
            steps={["Dane", "Informacje o nadpłacie", "Kontakt", "Podgląd"]}
            current={1}
          />
        </Demo>
        <Demo type="SECTION · sekcja predefiniowana „Adres”">
          <AddressSection prefix="demo_adres" title="Adres zamieszkania" />
        </Demo>
        <Demo type="REPEATING_SECTION">
          <RepeatingSection
            name="dzialki"
            title="Działki"
            itemTitle={(i) => `Działka ${i + 1}`}
            addLabel="Dodaj kolejną działkę"
          >
            {(p) => (
              <>
                <TextField
                  name={`${p}.numer`}
                  label="Numer ewidencyjny działki"
                  required
                />
                <TextField name={`${p}.obreb`} label="Obręb" required />
              </>
            )}
          </RepeatingSection>
        </Demo>
        <Demo type="Nawigacja formularza">
          <FormNav onBack={() => {}} onNext={() => {}} />
        </Demo>
      </div>
    </FormProvider>
  );
}
