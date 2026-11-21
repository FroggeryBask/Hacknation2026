"use client";

// Organism: "Wniosek o wynajęcie lub użyczenie świetlicy wiejskiej"
// Source: materialy/4. ... (paper form, Gmina Płoskinia). No reference JSON:
// designed from the paper form with the standard's rules:
// - only natural-person data on paper → subject options "Swoim" / "Innej osoby"
// - "wynajęcie/użyczenie* (niepotrzebne skreślić)" → radio
// - "zapoznałem/am się..." → gender-neutral statements in a consent section

import {
  DateField,
  FileUploaderField,
  NumberField,
  RadioField,
  TextField,
} from "@/components/form/fields";
import { useWatch } from "@/components/form/form-context";
import { FormSection, FormShell } from "@/components/form/layout";
import {
  ApplicantSections,
  ConsentsSection,
  ContactSection,
  PreviewSection,
  RODO_CONSENT,
  SUBJECT,
} from "@/components/form/sections";
import type { Validator } from "@/lib/form/validators";
import { minNumber } from "@/lib/form/validators";
import { MLPZ_DEMO } from "./mlpz";

const OTHER_RESPONSIBLE = "Inna osoba pełnoletnia";

function BookingPage() {
  const from = useWatch("termin_od");
  const responsible = useWatch("odpowiedzialny");
  const today = new Date().toISOString().slice(0, 10);
  const notBeforeToday: Validator = (v) =>
    typeof v === "string" && v < today
      ? "Wybierz dzisiejszą lub późniejszą datę."
      : undefined;
  const afterFrom: Validator = (v) =>
    typeof v === "string" && from && v < from
      ? "Data zakończenia nie może być wcześniejsza niż data rozpoczęcia."
      : undefined;

  return (
    <>
      <FormSection title="Rezerwacja świetlicy">
        <RadioField
          name="rodzaj"
          label="Wybierz, o co wnioskujesz"
          options={["Wynajęcie świetlicy", "Użyczenie świetlicy"]}
          description="Użyczenie jest bezpłatne. Zasady opisuje regulamin korzystania ze świetlic wiejskich."
          required
        />
        <TextField
          name="swietlica_miejscowosc"
          label="Miejscowość, w której jest świetlica"
          required
        />
        <DateField
          name="termin_od"
          label="Termin od"
          min={today}
          validators={[notBeforeToday]}
          required
        />
        <DateField
          name="termin_do"
          label="Termin do"
          min={from || today}
          validators={[notBeforeToday, afterFrom]}
          required
        />
      </FormSection>
      <FormSection title="Wydarzenie">
        <TextField
          name="cel"
          label="Cel wynajęcia świetlicy"
          description="Rodzaj uroczystości, np. wesele, urodziny, zabawa."
          required
        />
        <NumberField
          name="liczba_uczestnikow"
          label="Przewidywana liczba uczestników"
          validators={[minNumber(1, "Wpisz liczbę większą od zera.")]}
          required
        />
      </FormSection>
      <FormSection
        title="Osoba odpowiedzialna za porządek i bezpieczeństwo"
        description="Osoba odpowiedzialna musi być pełnoletnia."
      >
        <RadioField
          name="odpowiedzialny"
          label="Wybierz, kto odpowiada za porządek i bezpieczeństwo"
          options={["Ja", OTHER_RESPONSIBLE]}
          required
        />
        {responsible === OTHER_RESPONSIBLE && (
          <>
            <TextField name="odpowiedzialny.imie" label="Imię" required />
            <TextField
              name="odpowiedzialny.nazwisko"
              label="Nazwisko"
              required
            />
            <FileUploaderField
              name="odpowiedzialny.zgoda"
              label="Zgoda i oświadczenie osoby odpowiedzialnej"
              description="Dodaj skan lub zdjęcie zgody tej osoby wraz z jej oświadczeniem o warunkach korzystania ze świetlicy."
              required
            />
          </>
        )}
      </FormSection>
    </>
  );
}

const STATEMENTS = [
  {
    id: "warunki",
    required: true,
    content: "Znam warunki wynajmu i użyczenia świetlicy wiejskiej.",
  },
  {
    id: "porzadek",
    required: true,
    content:
      "W czasie korzystania ze świetlicy odpowiadam za ład i porządek w świetlicy oraz na terenie przy świetlicy.",
  },
  {
    id: "przepisy",
    required: true,
    content:
      "W czasie wydarzenia przestrzegam przepisów sanitarnych, BHP i przeciwpożarowych.",
  },
  {
    id: "mienie",
    required: true,
    content:
      "W czasie korzystania ze świetlicy ponoszę pełną odpowiedzialność za powierzone mienie.",
  },
  RODO_CONSENT,
];

export function SwietlicaForm() {
  return (
    <FormShell
      title="Wniosek o wynajęcie lub użyczenie świetlicy wiejskiej"
      initialValues={MLPZ_DEMO}
      pages={[
        {
          title: "Dane",
          type: "MAIN",
          content: (
            <ApplicantSections
              office="Wójt Gminy Płoskinia"
              organ
              subjects={[SUBJECT.self, SUBJECT.other]}
            />
          ),
        },
        { title: "Rezerwacja", type: "MAIN", content: <BookingPage /> },
        {
          title: "Kontakt i oświadczenia",
          type: "MAIN",
          content: (
            <>
              <ContactSection />
              <ConsentsSection
                title="Zgody i oświadczenia"
                consents={STATEMENTS}
              />
            </>
          ),
        },
        {
          title: "Strona końcowa",
          type: "FINISH",
          content: (
            <PreviewSection
              summary={
                <p>
                  Urząd sprawdzi, czy świetlica jest wolna w wybranym terminie,
                  i skontaktuje się z Tobą. Przy wynajmie otrzymasz informację o
                  opłacie i umowę do podpisania.
                </p>
              }
            />
          ),
        },
      ]}
    />
  );
}
