"use client";

/*
 * Predefined sections from materialy/ "Standardy i dobre praktyki projektowania
 * formularzy" (section 2: Budowa formularza). Labels, descriptions and SHOW
 * logic follow the standard and the reference eUsługa screens 1:1.
 */

import type { ReactNode } from "react";
import {
  EMAIL,
  NIP,
  PESEL,
  PHONE,
  pattern,
  REGON,
  ZIP_CODE,
} from "@/lib/form/validators";
import {
  type Consent,
  ConsentSection,
  ExternalLinkText,
  FileUploaderField,
  InfoSection,
  RadioField,
  SelectField,
  TextBlock,
  TextField,
} from "./fields";
import { useWatch } from "./form-context";
import { FormSection } from "./layout";

/* Dictionaries (subset). Full ones: materialy/ "Hacknation - Słowniki". */
export const KRAJE = [
  "Polska",
  "Austria",
  "Belgia",
  "Czechy",
  "Dania",
  "Estonia",
  "Finlandia",
  "Francja",
  "Hiszpania",
  "Holandia",
  "Irlandia",
  "Litwa",
  "Łotwa",
  "Niemcy",
  "Norwegia",
  "Portugalia",
  "Słowacja",
  "Szwecja",
  "Ukraina",
  "Wielka Brytania",
  "Włochy",
];

export const WOJEWODZTWA = [
  "dolnośląskie",
  "kujawsko-pomorskie",
  "lubelskie",
  "lubuskie",
  "łódzkie",
  "małopolskie",
  "mazowieckie",
  "opolskie",
  "podkarpackie",
  "podlaskie",
  "pomorskie",
  "śląskie",
  "świętokrzyskie",
  "warmińsko-mazurskie",
  "wielkopolskie",
  "zachodniopomorskie",
];

export const SUBJECT = {
  self: "Swoim",
  other: "Innej osoby",
  entity: "Osoby prawnej lub jednostki organizacyjnej",
} as const;
export const ROLE = { proxy: "Pełnomocnik", rep: "Reprezentant" } as const;

/* ------------------------------------------------------------------ */

export function OfficeSection({
  value,
  organ,
}: {
  /** Office (and department) or authority name; read-only. */
  value: string;
  /** Addressed to an authority (e.g. "Wójt") rather than an office. */
  organ?: boolean;
}) {
  return (
    <FormSection
      title={
        organ
          ? "Organ, do którego jest składany wniosek"
          : "Urząd, do którego jest składany wniosek"
      }
    >
      <TextField
        name={organ ? "nazwa_organu" : "nazwa_urzedu"}
        label={organ ? "Nazwa organu" : "Nazwa urzędu"}
        defaultValue={value}
        readOnly
      />
    </FormSection>
  );
}

export function SubjectSection({
  options = [SUBJECT.self, SUBJECT.other, SUBJECT.entity],
}: {
  /** Adjust to who may file this form (see standard: "Podmiot wniosku"). */
  options?: string[];
}) {
  const subject = useWatch("w_czyim_imieniu");
  return (
    <FormSection title="Podmiot wniosku">
      <RadioField
        name="w_czyim_imieniu"
        label="Wybierz, w czyim imieniu wnioskujesz"
        options={options}
        required
      />
      {subject === SUBJECT.entity && (
        <RadioField
          name="jako_kto"
          label="Wybierz, jako kto wnioskujesz"
          options={[ROLE.proxy, ROLE.rep]}
          required
        />
      )}
    </FormSection>
  );
}

export function YourDataSection({ withPesel }: { withPesel?: boolean }) {
  return (
    <FormSection title="Twoje dane">
      <TextField name="imie" label="Imię" readOnly required />
      <TextField name="nazwisko" label="Nazwisko" readOnly required />
      {withPesel && (
        <TextField name="pesel" label="Numer PESEL" readOnly required />
      )}
    </FormSection>
  );
}

/** One schema for every address (residence, registered office, mailing). */
export function AddressSection({
  prefix,
  title,
}: {
  prefix: string;
  title: string;
}) {
  const country = useWatch(`${prefix}.kraj`);
  const pl = country === "Polska";
  const n = (f: string) => `${prefix}.${f}`;
  return (
    <FormSection title={title}>
      <SelectField
        name={n("kraj")}
        label="Kraj"
        options={KRAJE}
        defaultValue="Polska"
        searchable
        required
      />
      {pl ? (
        <>
          <SelectField
            name={n("wojewodztwo")}
            label="Województwo"
            options={WOJEWODZTWA}
            required
          />
          <TextField
            name={n("kod_pocztowy")}
            label="Kod pocztowy"
            placeholder="__-___"
            inputMode="numeric"
            maxLength={6}
            autoComplete="postal-code"
            validators={[ZIP_CODE]}
            required
          />
          <TextField
            name={n("ulica")}
            label="Ulica"
            placeholder="Np. Polna, aleja Leśna, plac Lipowy, skwer Słoneczny"
            noValueLabel="Brak nazwy ulicy"
            required
          />
        </>
      ) : country ? (
        <>
          <TextField name={n("miejscowosc")} label="Miejscowość" required />
          <TextField
            name={n("kod_pocztowy")}
            label="Kod pocztowy"
            noValueLabel="Brak kodu pocztowego"
            required
          />
          <TextField
            name={n("ulica")}
            label="Ulica"
            noValueLabel="Brak nazwy ulicy"
            required
          />
        </>
      ) : null}
      {country && (
        <>
          <TextField name={n("numer_budynku")} label="Numer budynku" required />
          <TextField
            name={n("numer_lokalu")}
            label="Numer lokalu"
            noValueLabel="Brak numeru lokalu"
            required
          />
        </>
      )}
    </FormSection>
  );
}

export function OtherPersonSection({ withPesel }: { withPesel?: boolean }) {
  return (
    <FormSection title="Dane innej osoby">
      <TextField name="inna_osoba.imie" label="Imię" required />
      <TextField name="inna_osoba.nazwisko" label="Nazwisko" required />
      {withPesel && (
        <TextField
          name="inna_osoba.pesel"
          label="Numer PESEL"
          inputMode="numeric"
          maxLength={11}
          validators={[PESEL]}
          required
        />
      )}
    </FormSection>
  );
}

export function EntitySection() {
  return (
    <FormSection title="Dane podmiotu">
      <TextField name="podmiot.nazwa" label="Nazwa" required />
      <TextField
        name="podmiot.nip"
        label="NIP"
        inputMode="numeric"
        validators={[NIP]}
        required
      />
      <TextField
        name="podmiot.regon"
        label="REGON"
        inputMode="numeric"
        validators={[REGON]}
        required
      />
      <TextField
        name="podmiot.krs"
        label="Numer KRS"
        inputMode="numeric"
        maxLength={10}
        validators={[pattern(/^\d{10}$/, "Wpisz 10 cyfr.")]}
      />
    </FormSection>
  );
}

export function PowerOfAttorneySection() {
  return (
    <FormSection
      title="Pełnomocnictwo"
      description="Dodaj dokument potwierdzający, że jesteś pełnomocnikiem."
    >
      <FileUploaderField
        name="pelnomocnictwo_plik"
        label="Plik dokumentu z pełnomocnictwem"
        formats={[
          "jpg",
          "pdf",
          "xml",
          "PAdES",
          "png",
          "jpeg",
          "CAdES",
          "XAdES",
        ]}
        required
      />
    </FormSection>
  );
}

function StampDutyInfo({ whose }: { whose: "person" | "entity" }) {
  return (
    <TextBlock>
      <p>
        Opłata skarbowa za pełnomocnictwo wynosi <strong>17 zł</strong>.
      </p>
      <p>
        Przelej ją na konto urzędu miasta lub gminy właściwego dla{" "}
        {whose === "person"
          ? "adresu zamieszkania osoby, która udzieliła pełnomocnictwa"
          : "adresu siedziby podmiotu, który udzielił pełnomocnictwa"}
        . Jeśli adres nie jest w Polsce, opłatę przelej na konto{" "}
        <ExternalLinkText href="https://um.warszawa.pl">
          Urzędu Miasta Stołecznego Warszawy – Centrum Obsługi Podatnika
        </ExternalLinkText>
      </p>
      <p>
        Dodaj plik z potwierdzeniem przelewu. Znajdziesz go na stronie lub w
        aplikacji swojego banku.
      </p>
    </TextBlock>
  );
}

/** Version 1: acting for another person (may be exempt, so ask first). */
export function StampDutySection() {
  const needed = useWatch("oplata_wymagana");
  return (
    <FormSection
      title="Opłata skarbowa"
      description={
        <p>
          Nie musisz płacić za złożenie pełnomocnictwa wystawionego przez
          najbliższą rodzinę: małżonka, dzieci, rodziców, dziadków, wnuków,
          rodzeństwo. Więcej informacji na stronie{" "}
          <ExternalLinkText href="https://www.biznes.gov.pl">
            biznes.gov.pl
          </ExternalLinkText>
        </p>
      }
    >
      <RadioField
        name="oplata_wymagana"
        label="Czy złożenie pełnomocnictwa wymaga opłaty skarbowej?"
        options={["Tak", "Nie"]}
        required
      />
      {needed === "Tak" && (
        <>
          <StampDutyInfo whose="person" />
          <FileUploaderField
            name="oplata_potwierdzenie"
            label="Plik z potwierdzeniem przelewu"
            formats={["pdf"]}
            required
          />
        </>
      )}
    </FormSection>
  );
}

/** Version 2: proxy of a legal entity (fee always applies). */
export function StampDutyEntitySection() {
  return (
    <FormSection title="Opłata skarbowa za pełnomocnictwo">
      <StampDutyInfo whose="entity" />
      <FileUploaderField
        name="oplata_potwierdzenie"
        label="Plik z potwierdzeniem przelewu"
        formats={["pdf"]}
        required
      />
    </FormSection>
  );
}

export function RepresentativeProofSection() {
  return (
    <FormSection
      title="Potwierdzenie, że jesteś reprezentantem"
      description="Dołącz aktualny odpis danych z Krajowego Rejestru Sądowego lub innego rejestru. Odpis powinien potwierdzać, że jesteś reprezentantem podmiotu lub instytucji."
    >
      <FileUploaderField
        name="reprezentant_odpis"
        label="Plik z odpisem danych"
        maxFiles={3}
        required
      />
    </FormSection>
  );
}

/**
 * The whole "who is applying" block of page 1, with the dynamic states from
 * the reference visualisations (Swoim / Innej osoby / Osoby prawnej → role).
 */
export function ApplicantSections({
  office,
  organ,
  subjects,
  withPesel,
}: {
  office: string;
  organ?: boolean;
  subjects?: string[];
  withPesel?: boolean;
}) {
  const subject = useWatch("w_czyim_imieniu");
  const role = useWatch("jako_kto");
  return (
    <>
      <OfficeSection value={office} organ={organ} />
      <SubjectSection options={subjects} />
      <YourDataSection withPesel={withPesel} />
      <AddressSection prefix="adres_zamieszkania" title="Adres zamieszkania" />
      {subject === SUBJECT.other && (
        <>
          <OtherPersonSection />
          <AddressSection
            prefix="adres_innej_osoby"
            title="Adres zamieszkania innej osoby"
          />
          <PowerOfAttorneySection />
          <StampDutySection />
        </>
      )}
      {subject === SUBJECT.entity && (
        <>
          <EntitySection />
          <AddressSection prefix="adres_siedziby" title="Adres siedziby" />
          {role === ROLE.proxy && (
            <>
              <PowerOfAttorneySection />
              <StampDutyEntitySection />
            </>
          )}
          {role === ROLE.rep && <RepresentativeProofSection />}
        </>
      )}
    </>
  );
}

export function ContactSection() {
  return (
    <FormSection
      title="Dane do kontaktu"
      description={
        <>
          <p>
            Wpisanie danych do kontaktu może przyspieszyć załatwienie sprawy.
            Urzędnik będzie mógł skontaktować się z Tobą w przypadku pytań lub
            wątpliwości.
          </p>
          <p>
            Jeśli widzisz uzupełnione dane, sprawdź, czy są poprawne. Możesz je
            zmienić lub usunąć.
          </p>
        </>
      }
    >
      <TextField
        name="telefon"
        label="Numer telefonu"
        type="tel"
        autoComplete="tel"
        validators={[PHONE]}
      />
      <TextField
        name="email"
        label="Adres e-mail"
        type="email"
        autoComplete="email"
        validators={[EMAIL]}
      />
    </FormSection>
  );
}

export const RODO_CONSENT: Consent = {
  id: "rodo",
  required: true,
  content: (
    <>
      Wyrażam zgodę na przetwarzanie moich danych osobowych zgodnie z{" "}
      <ExternalLinkText href="https://www.gov.pl/web/gov/klauzula-informacyjna">
        klauzulą informacyjną
      </ExternalLinkText>
    </>
  ),
};

/** "Oświadczenie" if statements only, "Zgody i oświadczenia" if mixed. */
export function ConsentsSection({
  title = "Zgoda",
  consents = [RODO_CONSENT],
}: {
  title?: string;
  consents?: Consent[];
}) {
  return (
    <FormSection title={title}>
      <ConsentSection name="zgody" consents={consents} />
    </FormSection>
  );
}

/** FINISH page: no inputs, only info (Podsumowanie) and preview text. */
export function PreviewSection({
  signed = true,
  summary,
}: {
  signed?: boolean;
  summary?: ReactNode;
}) {
  return (
    <>
      {summary && (
        <FormSection title="Podsumowanie">
          <TextBlock>{summary}</TextBlock>
        </FormSection>
      )}
      <FormSection title="Podgląd uzupełnionego wniosku">
        <InfoSection>
          {signed
            ? "Zanim przejdziesz do wyboru sposobu podpisu, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, wróć do edycji."
            : "Zanim wyślesz formularz, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, wróć do edycji."}
        </InfoSection>
        <div className="grid min-h-40 place-items-center rounded-sm border border-dashed border-input bg-muted p-6 text-center text-sm text-muted-foreground">
          Tu pojawi się wizualizacja dokumentu (wzór z CRWDE).
        </div>
      </FormSection>
    </>
  );
}
