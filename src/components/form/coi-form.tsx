"use client";

/*
 * Renders a COI e-form JSON with the design system: one `field.type` = one
 * component (docs/design-system.md). SHOW / READ_ONLY states are evaluated with
 * JSONata on every answer; a hidden field is not rendered, so it is not
 * validated, but its answer stays in the form values.
 */

import { AnimatePresence } from "motion/react";
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  type CoiField,
  type CoiForm,
  type CoiQuestion,
  evaluateStates,
  type FieldState,
  fieldMaxLength,
  fieldOptions,
  fieldValidators,
  isPhone,
  isRequired,
  orderedTabs,
  sortQuestions,
  validatorNames,
} from "@/lib/form/coi";
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
} from "./fields";
import { useFormApi } from "./form-context";
import { FormSection, FormShell, RepeatingSection } from "./layout";
import { hasText, RichText } from "./rich-text";

const StatesContext = createContext<Record<string, FieldState> | null>(null);

/** Re-evaluates all states when any answer changes (async: JSONata). */
function useStates(form: CoiForm) {
  const { values } = useFormApi();
  const [states, setStates] = useState<Record<string, FieldState> | null>(null);
  useEffect(() => {
    let current = true;
    evaluateStates(form, values).then((s) => {
      if (current) setStates(s);
    });
    return () => {
      current = false;
    };
  }, [form, values]);
  return states;
}

function CoiPage({
  form,
  questions,
}: {
  form: CoiForm;
  questions: CoiQuestion[];
}) {
  const states = useStates(form);
  return (
    <StatesContext.Provider value={states}>
      <Questions questions={questions} />
    </StatesContext.Provider>
  );
}

function Questions({
  questions,
  prefix,
}: {
  questions?: CoiQuestion[];
  prefix?: string;
}) {
  return (
    <AnimatePresence initial={false}>
      {sortQuestions(questions).map((q) => (
        <Field key={q.field.id} field={q.field} prefix={prefix} />
      ))}
    </AnimatePresence>
  );
}

const description = (html?: string, inline = false): ReactNode =>
  hasText(html) ? <RichText html={html} inline={inline} /> : undefined;

/** Read-only registry field in the preview: the platform fills it after login. */
const EXTERNAL_PLACEHOLDER = "Uzupełni się automatycznie z danych logowania";

/** Input type and keyboard for the kind of data (phone and e-mail keyboards). */
function textKind(f: CoiField) {
  if (validatorNames(f).includes("EMAIL"))
    return { type: "email" as const, autoComplete: "email" };
  if (isPhone(f))
    return {
      type: "tel" as const,
      inputMode: "tel" as const,
      autoComplete: "tel",
    };
  if (["PESEL", "NIP", "REGON"].some((v) => validatorNames(f).includes(v)))
    return { type: "text" as const, inputMode: "numeric" as const };
  if (validatorNames(f).includes("ZIP_CODE"))
    return { type: "text" as const, autoComplete: "postal-code" };
  return { type: "text" as const };
}

/*
 * Address fields as the design standard and the COI visualisation of
 * material 1 show them. The COI import format has no key for these, the
 * e-service platform draws them, so the preview adds them by the field title.
 */

/** "Wyświetl dodatkowy checkbox wyłączający pole" (design standard, address). */
function noValueLabel(f: CoiField): string | undefined {
  const title = f.title.trim().toLowerCase();
  if (title === "ulica") return "Brak nazwy ulicy";
  if (title === "numer lokalu") return "Brak numeru lokalu";
  if (title === "kod pocztowy" && /zagranica/.test(f.techName))
    return "Brak kodu pocztowego";
  return undefined;
}

const isZip = (f: CoiField) => validatorNames(f).includes("ZIP_CODE");

/** A short "Np. …" hint is the field's placeholder ("Np. Polna, Aleja Leśna…"). */
function exampleHint(f: CoiField): string | undefined {
  const text = (f.description ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return /^Np\.\s/.test(text) && text.length <= 80 ? text : undefined;
}

const firstValue = (v: CoiField["defaultValue"]) =>
  (Array.isArray(v) ? v[0] : v) || undefined;

function Field({ field: f, prefix }: { field: CoiField; prefix?: string }) {
  const states = useContext(StatesContext);
  const name = prefix ? `${prefix}.${f.techName}` : f.techName;
  const state = states?.[name];
  // Conditional fields stay hidden until their condition is known to be true.
  if (f.states?.length && !state?.show) return null;

  const external = f.defaultValueType === "EXTERNAL_SYSTEM";
  const readOnly = f.readOnly || state?.readOnly;
  const common = {
    name,
    label: f.title,
    description: description(f.description, true),
    required: isRequired(f),
    readOnly,
    validators: fieldValidators(f),
    // A value written in the JSON (office name, "Polska") is shown as is;
    // registry data (MLPZ, PESEL) is filled in by the platform, not by us.
    defaultValue: external ? undefined : firstValue(f.defaultValue),
  };

  switch (f.type) {
    case "SECTION":
      return (
        <FormSection title={f.title} description={description(f.description)}>
          <Questions questions={f.repeatingSectionGrid} prefix={prefix} />
        </FormSection>
      );
    case "REPEATING_SECTION":
      return (
        <RepeatingSection
          name={name}
          title={f.title}
          description={description(f.description)}
          itemTitle={(i) => `${f.title} ${i + 1}`}
        >
          {(itemPrefix) => (
            <Questions questions={f.repeatingSectionGrid} prefix={itemPrefix} />
          )}
        </RepeatingSection>
      );
    case "TEXT_FIELD": {
      const example = exampleHint(f);
      return (
        <TextField
          {...common}
          description={example ? undefined : common.description}
          maxLength={fieldMaxLength(f)}
          {...textKind(f)}
          placeholder={
            external && readOnly
              ? EXTERNAL_PLACEHOLDER
              : (example ?? (isZip(f) ? "__-___" : undefined))
          }
          noValueLabel={readOnly ? undefined : noValueLabel(f)}
        />
      );
    }
    case "NUMBER":
      return <NumberField {...common} maxLength={fieldMaxLength(f)} />;
    case "DATEPICKER":
      return <DateField {...common} />;
    case "TEXTAREA":
      return <TextareaField {...common} maxLength={fieldMaxLength(f)} />;
    case "RADIO":
      return <RadioField {...common} options={fieldOptions(f)} />;
    case "CHECKBOX": {
      const options = fieldOptions(f);
      // A lone checkbox (no options) is a single yes/no statement.
      return (
        <CheckboxField
          {...common}
          options={options.length ? options : ["Tak"]}
        />
      );
    }
    case "SELECT":
      return (
        <SelectField
          {...common}
          options={fieldOptions(f)}
          searchable={!!f.searchEnabled}
        />
      );
    case "FILE_UPLOADER":
      return <FileUploaderField {...common} />;
    case "TEXT_BLOCK":
      return (
        <TextBlock>
          <RichText html={f.description} />
        </TextBlock>
      );
    case "INFO_SECTION":
      return (
        <InfoSection title={f.title || undefined}>
          <RichText html={f.description} />
        </InfoSection>
      );
    case "CONSENT_SECTION":
      return (
        <ConsentSection
          name={name}
          consents={(f.consentSectionConfig?.consents ?? []).map((c, i) => ({
            id: `zgoda_${i + 1}`,
            content: <RichText html={c.description} inline />,
            required: c.required,
          }))}
        />
      );
    default:
      return (
        <InfoSection title={`Nieobsługiwany typ pola: ${f.type}`}>
          {f.title || f.techName}
        </InfoSection>
      );
  }
}

/**
 * E-form built from COI JSON: tabs in flow order, FINISH last. Values written
 * in the JSON (office name, "Polska") are shown; registry data
 * (EXTERNAL_SYSTEM: MLPZ, PESEL) comes from the e-service platform, so a
 * read-only field of that kind says where its value comes from. "Dalej" checks
 * the page; the stepper opens pages already reached.
 */
export function CoiFormView({ form }: { form: CoiForm }) {
  const pages = useMemo(
    () =>
      orderedTabs(form).map((tab) => ({
        title: tab.title,
        type: tab.type,
        content: <CoiPage key={tab.id} form={form} questions={tab.questions} />,
      })),
    [form],
  );
  return <FormShell title={form.title} pages={pages} freeNavigation />;
}
