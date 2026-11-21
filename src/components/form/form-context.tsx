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
 * current page's fields are checked on "Dalej".
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
};

const FormContext = createContext<FormApi | null>(null);

export function useForm(initial: Values = {}): FormApi {
  const [values, setValues] = useState<Values>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const registry = useRef(new Map<string, () => Rule>());
  const valuesRef = useRef(values);
  valuesRef.current = values;

  const setValue = useCallback((name: string, value: FieldValue) => {
    setValues((v) => ({ ...v, [name]: value }));
    setErrors((e) => {
      if (!e[name]) return e;
      const { [name]: _, ...rest } = e;
      return rest;
    });
  }, []);

  const register = useCallback((name: string, getRule: () => Rule) => {
    registry.current.set(name, getRule);
    return () => {
      registry.current.delete(name);
    };
  }, []);

  const validate = useCallback(() => {
    const next: Record<string, string> = {};
    for (const [name, getRule] of registry.current) {
      const { required, validators = [] } = getRule();
      const value = valuesRef.current[name];
      const error = isEmpty(value)
        ? required
        : validators.map((v) => v(value)).find(Boolean);
      if (error) next[name] = error;
    }
    setErrors(next);
    const first = Object.keys(next)[0];
    if (first) {
      document
        .querySelector<HTMLElement>(`[data-field="${CSS.escape(first)}"]`)
        ?.querySelector<HTMLElement>("input, textarea, button")
        ?.focus();
    }
    return !first;
  }, []);

  return useMemo(
    () => ({ values, errors, setValue, register, validate }),
    [values, errors, setValue, register, validate],
  );
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
    error: form.errors[name],
  };
}
