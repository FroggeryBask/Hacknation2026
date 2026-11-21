"use client";

// Organism: "Wniosek o stwierdzenie nadpłaty podatku"
// Source: materialy/5. ... (reference JSON + eUsługa visualisation).

import {
  FileUploaderField,
  NumberField,
  RadioField,
  TextareaField,
  TextField,
} from "@/components/form/fields";
import { useWatch } from "@/components/form/form-context";
import { FormSection, FormShell } from "@/components/form/layout";
import {
  ApplicantSections,
  ConsentsSection,
  ContactSection,
  PreviewSection,
} from "@/components/form/sections";
import { IBAN_PL, minNumber } from "@/lib/form/validators";
import { MLPZ_DEMO } from "./mlpz";

const OFFSET = "Zaliczyć na poczet przyszłego zobowiązania podatkowego";
const REFUND = "Zwrócić przelewem na rachunek bankowy";

function OverpaymentPage() {
  const settle = useWatch("rozliczenie");
  return (
    <>
      <FormSection title="Informacje o nadpłacie">
        <TextField
          name="podatek"
          label="Podatek, którego dotyczy nadpłata"
          required
        />
        <NumberField
          name="kwota"
          label="Kwota"
          description="Podaj kwotę w złotych, np. 120,50."
          validators={[minNumber(0.01, "Kwota musi być większa od zera.")]}
          required
        />
        <TextareaField
          name="uzasadnienie"
          label="Uzasadnienie"
          description="Uzasadnij dlaczego Twoim zdaniem powstała nadpłata i z czego wynika jej wysokość."
          required
        />
      </FormSection>
      <FormSection title="Rozliczenie nadpłaty">
        <RadioField
          name="rozliczenie"
          label="Wybierz, co mamy zrobić z nadpłatą"
          options={[OFFSET, REFUND]}
          required
        />
        {settle === OFFSET && (
          <TextField name="nazwa_podatku" label="Nazwa podatku" required />
        )}
        {settle === REFUND && (
          <TextField
            name="numer_rachunku"
            label="Numer rachunku"
            inputMode="numeric"
            placeholder="00 0000 0000 0000 0000 0000 0000"
            validators={[IBAN_PL]}
            required
          />
        )}
      </FormSection>
      <FormSection
        title="Korekta deklaracji"
        description="Załącz poprawioną deklarację podatkową, z której wynika prawidłowa, niższa wysokość zobowiązania podatkowego, a w konsekwencji nadpłata."
      >
        <FileUploaderField
          name="korekta_deklaracji"
          label="Plik deklaracji podatkowej"
          required
        />
      </FormSection>
    </>
  );
}

export function NadplataPodatkuForm() {
  return (
    <FormShell
      title="Wniosek o stwierdzenie nadpłaty podatku"
      initialValues={MLPZ_DEMO}
      pages={[
        {
          title: "Dane",
          type: "MAIN",
          content: (
            <ApplicantSections office="Urząd Gminy Ulan-Majorat" withPesel />
          ),
        },
        {
          title: "Informacje o nadpłacie",
          type: "MAIN",
          content: <OverpaymentPage />,
        },
        {
          title: "Kontakt i zgody",
          type: "MAIN",
          content: (
            <>
              <ContactSection />
              <ConsentsSection />
            </>
          ),
        },
        {
          title: "Strona końcowa",
          type: "FINISH",
          content: <PreviewSection />,
        },
      ]}
    />
  );
}
