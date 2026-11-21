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
  /** Optional fields get the "(opcjonalnie)" suffix; required ones get no marker. */
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

function labelText(label: string, required?: boolean, readOnly?: boolean) {
  return required || readOnly ? label : `${label} (opcjonalnie)`;
}

/** Vertical field: label, description, control, error (in that order). */
export function FormField({
  name,
  id,
  label,
  description,
  required,
  readOnly,
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
        {labelText(label, required, readOnly)}
      </FieldLabel>
      {description && (
        <FieldDescription id={`${id}-desc`}>{description}</FieldDescription>
      )}
      {children}
      <FieldError id={`${id}-err`} error={error} />
    </Field>
  );
}

const describedBy = (id: string, description?: unknown, error?: string) =>
  [description && `${id}-desc`, error && `${id}-err`]
    .filter(Boolean)
    .join(" ") || undefined;

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
  const { id, value, setValue, error } = useField<string>(name, {
    required:
      required && !readOnly
        ? type === "date"
          ? requiredMessage.date
          : requiredMessage.text
        : undefined,
    validators,
    skip: noValue,
    defaultValue,
  });
  const aria = {
    id,
    name,
    "aria-invalid": !!error || undefined,
    "aria-describedby": describedBy(id, description, error),
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
      error={error}
      className={className}
    >
      {readOnly ? (
        <Input {...aria} readOnly value={value ?? ""} />
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

export function NumberField(props: Omit<TextFieldProps, "type">) {
  return <TextField {...props} type="number" inputMode="numeric" />;
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
  const { id, value, setValue, error } = useField<string>(name, {
    required: required ? requiredMessage.text : undefined,
    validators,
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
        aria-describedby={describedBy(id, description, error)}
        value={value ?? ""}
        onChange={(e) => setValue(e.target.value)}
      />
      <p className="text-right text-xs text-muted-foreground">
        {(value ?? "").length} / {maxLength} znaków
      </p>
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
