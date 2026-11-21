"use client";

// Organism: "Wniosek o ustalenie numeru porządkowego nieruchomości"
// Source: materialy/1. ... (reference JSON + eUsługa visualisation).

import { TextField } from "@/components/form/fields";
import { FormSection, FormShell } from "@/components/form/layout";
import {
  ApplicantSections,
  ConsentsSection,
  ContactSection,
  PreviewSection,
} from "@/components/form/sections";
import { MLPZ_DEMO } from "./mlpz";

function BuildingPage() {
  return (
    <FormSection title="Lokalizacja budynku">
      <TextField name="budynek.miejscowosc" label="Miejscowość" required />
      <TextField
        name="budynek.ulica"
        label="Ulica"
        noValueLabel="Brak nazwy ulicy"
        required
      />
      <TextField
        name="budynek.numer_dzialki"
        label="Numer ewidencyjny działki"
        description="Znajdziesz go w wypisie z rejestru gruntów lub na mapie geoportal.gov.pl."
        required
      />
      <TextField name="budynek.obreb" label="Obręb" required />
    </FormSection>
  );
}

export function NumerPorzadkowyForm() {
  return (
    <FormShell
      title="Wniosek o ustalenie numeru porządkowego nieruchomości"
      initialValues={MLPZ_DEMO}
      pages={[
        {
          title: "Dane",
          type: "MAIN",
          content: <ApplicantSections office="Wójt Gminy Elbląg" organ />,
        },
        {
          title: "Informacje o budynku",
          type: "MAIN",
          content: <BuildingPage />,
        },
        {
          title: "Kontakt z urzędem",
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
          content: <PreviewSection signed={false} />,
        },
      ]}
      submitLabel="Wyślij wniosek"
    />
  );
}
