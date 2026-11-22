"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  type FieldValue,
  isEmpty,
  type Validator,
} from "@/lib/form/validators";

/*
 * Minimal form state. Fields register themselves while mounted, so a field
 * hidden by a SHOW condition (not rendered) is never validated, and only the
 * current page's fields are checked on "Dalej" / "Sprawdź poprawność".
 *
 * When errors show (design standard: "weryfikuj poprawność danych już na
 * etapie ich wprowadzania", WCAG 3.3.1):
 * - leaving a field checks it: the format (PESEL, NIP, kod pocztowy…), and an
 *   empty required field once it had a value (cleared); a field never filled
 *   is not reported on blur (tabbing through), only on "Dalej",
 * - a field that shows an error is checked again on every change, so the
 *   message disappears as soon as the value is right,
 * - "Dalej" checks every mounted field of the page (empty required ones too).
 */

type Values = Record<string, FieldValue>;
type Rule = { required?: string; validators?: Validator[] };

type FormApi = {
  values: Values;
  errors: Record<string, string>;
  setValue: (name: string, value: FieldValue) => void;
  register: (name: string, getRule: () => Rule) => () => void;
  /** Validates all mounted fields. Focuses the first invalid one. */
  validate: () => boolean;
  /** Validates all mounted fields and returns the errors (no focus change). */
  check: () => FieldError[];
  /** Checks one field on blur; a field never filled is left alone. */
  validateField: (name: string) => void;
  clearErrors: () => void;
};

export type FieldError = { name: string; message: string };

const FormContext = createContext<FormApi | null>(null);

export function useForm(initial: Values = {}): FormApi {
  const [values, setValues] = useState<Values>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const registry = useRef(new Map<string, () => Rule>());
  // Fields that had a value at some point: leaving one empty is an error.
  const filled = useRef(new Set<string>());
  const valuesRef = useRef(values);
  valuesRef.current = values;

  /** The field's error for a value: required first, then its validators. */
  const errorOf = useCallback(
    (name: string, value: FieldValue): string | undefined => {
      const getRule = registry.current.get(name);
      if (!getRule) return undefined;
      const { required, validators = [] } = getRule();
      return isEmpty(value)
        ? required
        : validators.map((v) => v(value)).find(Boolean);
    },
    [],
  );

  const setValue = useCallback(
    (name: string, value: FieldValue) => {
      setValues((v) => ({ ...v, [name]: value }));
      if (!isEmpty(value)) filled.current.add(name);
      // A shown error follows the value: it updates or goes away while typing.
      setErrors((e) => {
        if (!e[name]) return e;
        const message = errorOf(name, value);
        if (message === e[name]) return e;
        const { [name]: _, ...rest } = e;
        return message ? { ...rest, [name]: message } : rest;
      });
    },
    [errorOf],
  );

  const validateField = useCallback(
    (name: string) => {
      const value = valuesRef.current[name];
      if (isEmpty(value) && !filled.current.has(name)) return;
      const message = errorOf(name, value);
      setErrors((e) => {
        if (message === e[name]) return e;
        const { [name]: _, ...rest } = e;
        return message ? { ...rest, [name]: message } : rest;
      });
    },
    [errorOf],
  );

  const clearErrors = useCallback(() => setErrors({}), []);

  const register = useCallback((name: string, getRule: () => Rule) => {
    registry.current.set(name, getRule);
    return () => {
      registry.current.delete(name);
    };
  }, []);

  const check = useCallback(() => {
    const found: FieldError[] = [];
    for (const name of registry.current.keys()) {
      const message = errorOf(name, valuesRef.current[name]);
      if (message) found.push({ name, message });
    }
    setErrors(Object.fromEntries(found.map((e) => [e.name, e.message])));
    return found;
  }, [errorOf]);

  const validate = useCallback(() => {
    const first = check()[0];
    if (first) focusField(first.name);
    return !first;
  }, [check]);

  return useMemo(
    () => ({
      values,
      errors,
      setValue,
      register,
      validate,
      check,
      validateField,
      clearErrors,
    }),
    [
      values,
      errors,
      setValue,
      register,
      validate,
      check,
      validateField,
      clearErrors,
    ],
  );
}

/** Focuses the control of a field (its `data-field` wrapper). */
export function focusField(name: string) {
  document
    .querySelector<HTMLElement>(`[data-field="${CSS.escape(name)}"]`)
    ?.querySelector<HTMLElement>("input:not([type=hidden]), textarea, button")
    ?.focus();
}

export function FormProvider({
  form,
  children,
}: {
  form: FormApi;
  children: ReactNode;
}) {
  return <FormContext.Provider value={form}>{children}</FormContext.Provider>;
}

export function useFormApi() {
  const form = useContext(FormContext);
  if (!form) throw new Error("Form fields must be inside <FormProvider>");
  return form;
}

/** Watch another field's value (for SHOW conditions). */
export function useWatch<T extends FieldValue = string>(name: string) {
  return useFormApi().values[name] as T | undefined;
}

export function useField<T extends FieldValue>(
  name: string,
  rule: Rule & { skip?: boolean; defaultValue?: T } = {},
) {
  const form = useFormApi();
  const id = useId();
  const ruleRef = useRef(rule);
  ruleRef.current = rule;

  useEffect(
    () =>
      form.register(name, () => (ruleRef.current.skip ? {} : ruleRef.current)),
    [form.register, name],
  );

  // defaultValue from the JSON config: applied once when the field first mounts.
  const initial = rule.defaultValue;
  const hasValue = form.values[name] !== undefined;
  useEffect(() => {
    if (!hasValue && initial !== undefined) form.setValue(name, initial);
  }, [form.setValue, name, initial, hasValue]);

  return {
    id,
    value: form.values[name] as T | undefined,
    setValue: (v: T | undefined) => form.setValue(name, v),
    /** Format check when the user leaves the field (empty is not an error yet). */
    onBlur: () => form.validateField(name),
    error: form.errors[name],
  };
}
