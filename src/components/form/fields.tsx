"use client";

import { cn } from "cn";
import {
  ExternalLink,
  FileText,
  Info,
  TriangleAlert,
  Upload,
  X,
} from "lucide-react";
import { type ReactNode, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import {
  Field,
  FieldDescription,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  type FileValue,
  maxChars,
  NUMBER,
  requiredMessage,
  type Validator,
} from "@/lib/form/validators";
import { useField, useFormApi } from "./form-context";

/* ------------------------------------------------------------------ */
/* Shared props and the label / description / error wrapper            */
/* ------------------------------------------------------------------ */

export type BaseFieldProps = {
  /** techName from the JSON config; also the key in form values. */
  name: string;
  label: string;
  description?: ReactNode;
  /** Required fields get a red asterisk (legend above the form); read-only ones none. */
  required?: boolean;
  readOnly?: boolean;
  validators?: Validator[];
  /** defaultValue from the JSON config (e.g. office name, "Polska"). */
  defaultValue?: string;
  className?: string;
};

export function FieldError({ id, error }: { id: string; error?: string }) {
  if (!error) return null;
  return (
    <p
      id={id}
      role="alert"
      className="flex items-start gap-1.5 text-sm font-bold text-destructive"
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      {error}
    </p>
  );
}

/**
 * As the COI visualisation: required fields have no marker, optional ones the
 * suffix "(opcjonalnie)". Read-only fields and fields with a "Brak …" checkbox
 * (the checkbox is how to leave them empty) get no suffix.
 */
function labelText(label: string, required?: boolean, plain?: boolean) {
  return required || plain ? label : `${label} (opcjonalnie)`;
}

/** Vertical field: label, description, control, error (in that order). */
export function FormField({
  name,
  id,
  label,
  description,
  required,
  readOnly,
  plainLabel,
  error,
  className,
  children,
}: {
  name: string;
  id: string;
  label: string;
  description?: ReactNode;
  required?: boolean;
  readOnly?: boolean;
  /** No "(opcjonalnie)": the field has a "Brak …" checkbox. */
  plainLabel?: boolean;
  error?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Field
      data-field={name}
      data-invalid={!!error}
      className={cn("gap-1.5 data-[invalid=true]:text-foreground", className)}
    >
      <FieldLabel htmlFor={id} className="font-normal text-foreground">
        {labelText(label, required, readOnly || plainLabel)}
      </FieldLabel>
      {description && (
        <FieldDescription id={`${id}-desc`}>{description}</FieldDescription>
      )}
      {children}
      <FieldError id={`${id}-err`} error={error} />
    </Field>
  );
}

const describedBy = (
  id: string,
  description?: unknown,
  error?: string,
  counted?: boolean,
) =>
  [description && `${id}-desc`, counted && `${id}-count`, error && `${id}-err`]
    .filter(Boolean)
    .join(" ") || undefined;

/**
 * "12 / 255 znaków" under a field. For free text (limit of 50 or more), the
 * last 10% turns to the warning colour and screen readers hear how many
 * characters are left.
 */
export function CharCount({
  id,
  length,
  max,
}: {
  id: string;
  length: number;
  max: number;
}) {
  const left = max - length;
  // Only free text warns near its limit; a full PESEL or postcode is complete,
  // not a problem.
  const near = max >= 50 && left <= Math.floor(max * 0.1);
  return (
    <p
      id={`${id}-count`}
      className={cn(
        "text-right text-xs text-muted-foreground",
        near && "font-bold text-warning",
      )}
    >
      {length} / {max} znaków
      <span className="sr-only" aria-live="polite">
        {near ? `Zostało znaków: ${left}.` : ""}
      </span>
    </p>
  );
}

/* ------------------------------------------------------------------ */
/* TEXT_FIELD / NUMBER / DATEPICKER                                    */
/* ------------------------------------------------------------------ */

type TextFieldProps = BaseFieldProps & {
  placeholder?: string;
  type?: "text" | "email" | "tel" | "number" | "date";
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  autoComplete?: string;
  maxLength?: number;
  /** "Wyświetl dodatkowy checkbox wyłączający pole", e.g. "Brak nazwy ulicy". */
  noValueLabel?: string;
  min?: string;
};

export function TextField({
  name,
  label,
  description,
  required,
  readOnly,
  validators,
  placeholder,
  type = "text",
  inputMode,
  autoComplete,
  maxLength,
  noValueLabel,
  min,
  defaultValue,
  className,
}: TextFieldProps) {
  const form = useFormApi();
  const noValueKey = `${name}__brak`;
  const noValue = form.values[noValueKey] === true;
  const { id, value, setValue, onBlur, error } = useField<string>(name, {
    required:
      required && !readOnly
        ? type === "date"
          ? requiredMessage.date
          : requiredMessage.text
        : undefined,
    validators: maxLength
      ? [...(validators ?? []), maxChars(maxLength)]
      : validators,
    skip: noValue,
    defaultValue,
  });
  // The counter shows once the field has a value: shown on focus already, it
  // would vanish on blur from an empty field and shift the page under a click.
  const counted = !!maxLength && !readOnly && type !== "date" && !!value;
  const aria = {
    id,
    name,
    "aria-invalid": !!error || undefined,
    "aria-describedby": describedBy(id, description, error, counted),
    "aria-required": required || undefined,
  };

  return (
    <FormField
      name={name}
      id={id}
      label={label}
      description={description}
      required={required}
      readOnly={readOnly}
      plainLabel={!!noValueLabel}
      error={error}
      className={className}
    >
      {readOnly ? (
        <Input
          {...aria}
          readOnly
          placeholder={placeholder}
          value={value ?? ""}
        />
      ) : (
        <InputGroup>
          <InputGroupInput
            {...aria}
            type={type}
            inputMode={inputMode}
            autoComplete={autoComplete}
            maxLength={maxLength}
            min={min}
            placeholder={placeholder}
            disabled={noValue}
            value={value ?? ""}
            onChange={(e) => setValue(e.target.value)}
            onBlur={onBlur}
          />
          {value && type !== "date" && (
            <InputGroupAddon align="inline-end">
              <InputGroupButton
                size="icon-xs"
                aria-label={`Wyczyść pole ${label}`}
                onClick={() => setValue("")}
              >
                <X className="text-primary" />
              </InputGroupButton>
            </InputGroupAddon>
          )}
        </InputGroup>
      )}
      {counted && maxLength && (
        <CharCount id={id} length={(value ?? "").length} max={maxLength} />
      )}
      {noValueLabel && (
        <Field orientation="horizontal" className="gap-2">
          <Checkbox
            id={`${id}-brak`}
            checked={noValue}
            onCheckedChange={(c) => {
              form.setValue(noValueKey, c === true);
              if (c) setValue("");
            }}
          />
          <FieldLabel htmlFor={`${id}-brak`} className="font-normal">
            {noValueLabel}
          </FieldLabel>
        </Field>
      )}
    </FormField>
  );
}

/**
 * Numbers as text with a numeric keyboard: a browser `type="number"` field
 * hides what was typed when it is not a number, so it could not be checked.
 */
export function NumberField(props: Omit<TextFieldProps, "type">) {
  return (
    <TextField
      {...props}
      inputMode="decimal"
      validators={[NUMBER, ...(props.validators ?? [])]}
    />
  );
}

export function DateField(props: Omit<TextFieldProps, "type">) {
  return <TextField {...props} type="date" />;
}

/* ------------------------------------------------------------------ */
/* TEXTAREA                                                            */
/* ------------------------------------------------------------------ */

export function TextareaField({
  name,
  label,
  description,
  required,
  readOnly,
  validators,
  maxLength = 2000,
  className,
}: BaseFieldProps & { maxLength?: number }) {
  const { id, value, setValue, onBlur, error } = useField<string>(name, {
    required: required && !readOnly ? requiredMessage.text : undefined,
    validators: [...(validators ?? []), maxChars(maxLength)],
  });
  return (
    <FormField
      name={name}
      id={id}
      label={label}
      description={description}
      required={required}
      readOnly={readOnly}
      error={error}
      className={className}
    >
      <Textarea
        id={id}
        name={name}
        readOnly={readOnly}
        maxLength={maxLength}
        aria-invalid={!!error || undefined}
        aria-describedby={describedBy(id, description, error, !readOnly)}
        value={value ?? ""}
        onChange={(e) => setValue(e.target.value)}
        onBlur={onBlur}
      />
      {!readOnly && (
        <CharCount id={id} length={(value ?? "").length} max={maxLength} />
      )}
    </FormField>
  );
}

/* ------------------------------------------------------------------ */
/* RADIO / CHECKBOX (choice groups use fieldset + legend)              */
/* ------------------------------------------------------------------ */

type ChoiceProps = BaseFieldProps & { options: string[] };

function ChoiceSet({
  name,
  id,
  label,
  description,
  required,
  error,
  className,
  children,
}: {
  name: string;
  id: string;
  label: string;
  description?: ReactNode;
  required?: boolean;
  error?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <FieldSet
      data-field={name}
      data-invalid={!!error}
      className={cn("gap-3 data-[invalid=true]:text-foreground", className)}
      aria-describedby={describedBy(id, description, error)}
    >
      <FieldLegend variant="label" className="mb-0 font-normal">
        {labelText(label, required)}
      </FieldLegend>
      {description && (
        <FieldDescription id={`${id}-desc`}>{description}</FieldDescription>
      )}
      {children}
      <FieldError id={`${id}-err`} error={error} />
    </FieldSet>
  );
}

export function RadioField({
  name,
  label,
  description,
  required,
  options,
  className,
}: ChoiceProps) {
  const { id, value, setValue, error } = useField<string>(name, {
    required: required ? requiredMessage.choice : undefined,
  });
  return (
    <ChoiceSet
      name={name}
      id={id}
      label={label}
      description={description}
      required={required}
      error={error}
      className={className}
    >
      <RadioGroup
        value={value ?? ""}
        onValueChange={(v) => setValue(String(v))}
        aria-invalid={!!error || undefined}
        className="gap-3"
      >
        {options.map((opt, i) => (
          <Field key={opt} orientation="horizontal" className="gap-2.5">
            <RadioGroupItem value={opt} id={`${id}-${i}`} />
            <FieldLabel htmlFor={`${id}-${i}`} className="font-normal">
              {opt}
            </FieldLabel>
          </Field>
        ))}
      </RadioGroup>
    </ChoiceSet>
  );
}

export function CheckboxField({
  name,
  label,
  description,
  required,
  options,
  className,
}: ChoiceProps) {
  const {
    id,
    value = [],
    setValue,
    error,
  } = useField<string[]>(name, {
    required: required ? requiredMessage.multi : undefined,
  });
  return (
    <ChoiceSet
      name={name}
      id={id}
      label={label}
      description={description}
      required={required}
      error={error}
      className={className}
    >
      <div className="flex flex-col gap-3">
        {options.map((opt, i) => (
          <Field key={opt} orientation="horizontal" className="gap-2.5">
            <Checkbox
              id={`${id}-${i}`}
              checked={value.includes(opt)}
              aria-invalid={!!error || undefined}
              onCheckedChange={(c) =>
                setValue(c ? [...value, opt] : value.filter((v) => v !== opt))
              }
            />
            <FieldLabel htmlFor={`${id}-${i}`} className="font-normal">
              {opt}
            </FieldLabel>
          </Field>
        ))}
      </div>
    </ChoiceSet>
  );
}

/* ------------------------------------------------------------------ */
/* SELECT (searchable automatically above 15 options, per standard)    */
/* ------------------------------------------------------------------ */

export function SelectField({
  name,
  label,
  description,
  required,
  readOnly,
  options,
  searchable,
  defaultValue,
  className,
}: ChoiceProps & { searchable?: boolean }) {
  const { id, value, setValue, error } = useField<string>(name, {
    required: required ? requiredMessage.choice : undefined,
    defaultValue,
  });
  const common = {
    "aria-invalid": !!error || undefined,
    "aria-describedby": describedBy(id, description, error),
  };
  return (
    <FormField
      name={name}
      id={id}
      label={label}
      description={description}
      required={required}
      readOnly={readOnly}
      error={error}
      className={className}
    >
      {readOnly ? (
        <Input id={id} readOnly value={value ?? ""} />
      ) : searchable || options.length > 15 ? (
        <Combobox
          items={options}
          value={value || null}
          onValueChange={(v) => setValue(v ?? "")}
        >
          <ComboboxInput
            id={id}
            placeholder="Wybierz lub wpisz"
            showClear={!!value}
            className="w-full"
            {...common}
          />
          <ComboboxContent>
            <ComboboxEmpty>Brak wyników</ComboboxEmpty>
            <ComboboxList>
              {(item: string) => (
                <ComboboxItem key={item} value={item}>
                  {item}
                </ComboboxItem>
              )}
            </ComboboxList>
          </ComboboxContent>
        </Combobox>
      ) : (
        <Select value={value || null} onValueChange={(v) => setValue(v ?? "")}>
          <SelectTrigger id={id} className="w-full" {...common}>
            <SelectValue placeholder="Wybierz" />
          </SelectTrigger>
          <SelectContent>
            {options.map((opt) => (
              <SelectItem key={opt} value={opt}>
                {opt}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </FormField>
  );
}

/* ------------------------------------------------------------------ */
/* FILE_UPLOADER                                                       */
/* ------------------------------------------------------------------ */

const formatSize = (b: number) =>
  b < 1024 * 1024
    ? `${Math.ceil(b / 1024)} KB`
    : `${(b / 1024 / 1024).toFixed(1)} MB`;

export function FileUploaderField({
  name,
  label,
  description,
  required,
  formats = ["jpg", "pdf", "png", "jpeg"],
  maxSizeMb = 10,
  maxFiles = 1,
  className,
}: BaseFieldProps & {
  formats?: string[];
  maxSizeMb?: number;
  maxFiles?: number;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const form = useFormApi();
  const {
    id,
    value = [],
    setValue,
    error,
  } = useField<FileValue[]>(name, {
    required: required ? requiredMessage.file : undefined,
  });
  const full = value.length >= maxFiles;

  const add = (files: FileList | null) => {
    if (!files) return;
    const ok = Array.from(files).filter((f) => {
      const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
      return (
        formats.some((x) => x.toLowerCase() === ext) &&
        f.size <= maxSizeMb * 1024 * 1024
      );
    });
    if (ok.length < files.length) {
      form.setValue(`${name}__info`, "rejected");
    }
    setValue(
      [...value, ...ok.map((f) => ({ name: f.name, size: f.size }))].slice(
        0,
        maxFiles,
      ),
    );
  };

  const rejected = form.values[`${name}__info`] === "rejected";

  return (
    <FormField
      name={name}
      id={id}
      label={label}
      description={description}
      required={required}
      error={error}
      className={className}
    >
      {/* biome-ignore lint/a11y/noStaticElementInteractions: drop target; the button inside is the keyboard path */}
      <div
        className={cn(
          "flex flex-col gap-4 rounded-sm border border-input p-4 transition-colors",
          error && "border-destructive",
        )}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!full) add(e.dataTransfer.files);
        }}
      >
        {value.length > 0 && (
          <ul className="flex flex-col gap-2">
            {value.map((f) => (
              <li
                key={f.name}
                className="flex items-center gap-2 rounded-sm bg-secondary px-3 py-2 text-sm"
              >
                <FileText className="size-4 text-primary" aria-hidden />
                <span className="flex-1 truncate font-bold">{f.name}</span>
                <span className="text-muted-foreground">
                  {formatSize(f.size)}
                </span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={`Usuń plik ${f.name}`}
                  onClick={() => setValue(value.filter((x) => x !== f))}
                >
                  <X className="text-primary" />
                </Button>
              </li>
            ))}
          </ul>
        )}
        {!full && (
          <Button
            variant="outline"
            className="self-center"
            onClick={() => inputRef.current?.click()}
            aria-describedby={describedBy(id, description, error)}
          >
            <Upload data-icon="inline-start" aria-hidden />
            Dodaj lub przeciągnij plik
          </Button>
        )}
        <input
          ref={inputRef}
          id={id}
          type="file"
          className="sr-only"
          tabIndex={-1}
          multiple={maxFiles > 1}
          accept={formats.map((f) => `.${f}`).join(",")}
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
        {rejected && (
          <p className="text-sm text-destructive">
            Część plików pominięto: zły format lub za duży rozmiar.
          </p>
        )}
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 text-xs [&>dd]:border-b [&>dd]:py-1.5 [&>dd]:font-bold [&>dt]:border-b [&>dt]:py-1.5 [&>dt]:text-muted-foreground">
          <dt>Dopuszczalny format pliku:</dt>
          <dd>{formats.map((f) => `.${f}`).join(", ")}</dd>
          <dt>Maksymalny rozmiar pliku:</dt>
          <dd>{maxSizeMb} MB</dd>
          <dt>Maksymalna liczba plików:</dt>
          <dd>{maxFiles}</dd>
        </dl>
      </div>
    </FormField>
  );
}

/* ------------------------------------------------------------------ */
/* TEXT_BLOCK / INFO_SECTION / external link                           */
/* ------------------------------------------------------------------ */

export function ExternalLinkText({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-baseline gap-1 font-bold text-link underline-offset-4 hover:underline"
    >
      {children}
      <ExternalLink className="size-3.5 self-center" aria-hidden />
      <span className="sr-only">(otwiera się w nowej karcie)</span>
    </a>
  );
}

/** Non-editable text that isn't a description of a single field. */
export function TextBlock({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 text-sm leading-relaxed [&_strong]:font-bold",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Highlighted information (the only content allowed on the FINISH page). */
export function InfoSection({
  title,
  icon,
  children,
}: {
  title?: string;
  /** Replaces the default info icon (decorative, 20px). */
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex gap-3 rounded-sm border-l-4 border-primary bg-info p-4 text-sm text-info-foreground">
      {icon ?? <Info className="mt-0.5 size-5 shrink-0" aria-hidden />}
      <div className="flex flex-col gap-1">
        {title && <p className="font-bold">{title}</p>}
        <div className="leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* CONSENT_SECTION                                                     */
/* ------------------------------------------------------------------ */

export type Consent = { id: string; content: ReactNode; required?: boolean };

function ConsentItem({ name, consent }: { name: string; consent: Consent }) {
  const key = `${name}.${consent.id}`;
  const { id, value, setValue, error } = useField<boolean>(key, {
    required: consent.required ? requiredMessage.consent : undefined,
  });
  return (
    <div data-field={key} className="flex flex-col gap-1.5">
      <Field orientation="horizontal" className="items-start gap-2.5">
        <Checkbox
          id={id}
          checked={value === true}
          onCheckedChange={(c) => setValue(c === true)}
          aria-invalid={!!error || undefined}
          aria-describedby={error ? `${id}-err` : undefined}
          className="mt-0.5"
        />
        <FieldLabel
          htmlFor={id}
          className="block font-normal leading-relaxed text-foreground"
        >
          {consent.content}
          {!consent.required && " (opcjonalnie)"}
        </FieldLabel>
      </Field>
      <div className="pl-7.5">
        <FieldError id={`${id}-err`} error={error} />
      </div>
    </div>
  );
}

export function ConsentSection({
  name,
  consents,
}: {
  name: string;
  consents: Consent[];
}) {
  return (
    <div className="flex flex-col gap-4">
      {consents.map((c) => (
        <ConsentItem key={c.id} name={name} consent={c} />
      ))}
    </div>
  );
}
