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
  fieldOptions,
  fieldValidators,
  initialValues,
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

function Field({ field: f, prefix }: { field: CoiField; prefix?: string }) {
  const states = useContext(StatesContext);
  const name = prefix ? `${prefix}.${f.techName}` : f.techName;
  const state = states?.[name];
  // Conditional fields stay hidden until their condition is known to be true.
  if (f.states?.length && !state?.show) return null;

  const common = {
    name,
    label: f.title,
    description: description(f.description, true),
    required: isRequired(f),
    readOnly: f.readOnly || state?.readOnly,
    validators: fieldValidators(f),
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
    case "TEXT_FIELD":
      return (
        <TextField
          {...common}
          type={validatorNames(f).includes("EMAIL") ? "email" : "text"}
        />
      );
    case "NUMBER":
      return <NumberField {...common} />;
    case "DATEPICKER":
      return <DateField {...common} />;
    case "TEXTAREA":
      return <TextareaField {...common} />;
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

/** Fillable e-form built from COI JSON: tabs in flow order, FINISH last. */
export function CoiFormView({
  form,
  abortHref,
}: {
  form: CoiForm;
  abortHref?: string;
}) {
  const values = useMemo(() => initialValues(form), [form]);
  const pages = useMemo(
    () =>
      orderedTabs(form).map((tab) => ({
        title: tab.title,
        type: tab.type,
        content: <CoiPage key={tab.id} form={form} questions={tab.questions} />,
      })),
    [form],
  );
  return (
    <FormShell
      title={form.title}
      pages={pages}
      initialValues={values}
      abortHref={abortHref}
    />
  );
}
