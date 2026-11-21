// Field validators. Names mirror the validator list from
// materialy/ "Reguły techniczne konfiguracji formularzy" (REQUIRED, EMAIL, PESEL, ...).
// Messages follow the voice & tone standard: short, active, no gendered forms.

export type FieldValue = string | string[] | boolean | FileValue[] | undefined;
export type FileValue = { name: string; size: number };
export type Validator = (value: FieldValue) => string | undefined;

export const isEmpty = (v: FieldValue) =>
  v === undefined ||
  v === false ||
  (typeof v === "string" && v.trim() === "") ||
  (Array.isArray(v) && v.length === 0);

const text = (fn: (s: string) => string | undefined): Validator => {
  return (v) => (typeof v === "string" && v.trim() ? fn(v.trim()) : undefined);
};

const digitsChecksum = (s: string, weights: number[]) =>
  weights.reduce((sum, w, i) => sum + w * Number(s[i]), 0);

export const PESEL = text((s) => {
  if (!/^\d{11}$/.test(s)) return "Numer PESEL ma 11 cyfr.";
  const sum = digitsChecksum(s, [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]);
  return (10 - (sum % 10)) % 10 === Number(s[10])
    ? undefined
    : "Numer PESEL jest niepoprawny. Sprawdź cyfry.";
});

export const NIP = text((s) => {
  const d = s.replace(/[-\s]/g, "");
  if (!/^\d{10}$/.test(d)) return "NIP ma 10 cyfr.";
  const sum = digitsChecksum(d, [6, 5, 7, 2, 3, 4, 5, 6, 7]);
  return sum % 11 === Number(d[9])
    ? undefined
    : "NIP jest niepoprawny. Sprawdź cyfry.";
});

export const REGON = text((s) => {
  if (!/^(\d{9}|\d{14})$/.test(s)) return "REGON ma 9 lub 14 cyfr.";
  const w =
    s.length === 9
      ? [8, 9, 2, 3, 4, 5, 6, 7]
      : [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8];
  const check = (digitsChecksum(s, w) % 11) % 10;
  return check === Number(s[s.length - 1])
    ? undefined
    : "REGON jest niepoprawny. Sprawdź cyfry.";
});

export const ZIP_CODE = text((s) =>
  /^\d{2}-\d{3}$/.test(s) ? undefined : "Wpisz kod pocztowy w formacie 00-000.",
);

export const EMAIL = text((s) =>
  /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s)
    ? undefined
    : "Wpisz adres e-mail w formacie nazwa@domena.pl.",
);

export const PHONE = text((s) =>
  /^\+?\d{9,15}$/.test(s.replace(/[\s-]/g, ""))
    ? undefined
    : "Wpisz numer telefonu, np. 600 100 200 lub +48600100200.",
);

export const IBAN_PL = text((s) =>
  /^(PL)?\d{26}$/.test(s.replace(/\s/g, "").toUpperCase())
    ? undefined
    : "Numer rachunku ma 26 cyfr.",
);

export const pattern = (re: RegExp, message: string): Validator =>
  text((s) => (re.test(s) ? undefined : message));

export const minNumber = (min: number, message: string): Validator =>
  text((s) => (Number(s) >= min ? undefined : message));

/** Message for an empty required field, by field kind. */
export const requiredMessage = {
  text: "Uzupełnij to pole.",
  choice: "Wybierz jedną z opcji.",
  multi: "Wybierz co najmniej jedną opcję.",
  date: "Wybierz datę.",
  file: "Dodaj plik.",
  consent: "Oświadczenie jest wymagane.",
} as const;
