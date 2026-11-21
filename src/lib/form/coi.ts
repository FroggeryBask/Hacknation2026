// COI e-form JSON (import format from materialy/ "OpisImportowanegoPlikuJSON",
// reference files materialy/1.* and 5.*) and pure helpers for the renderer.

import jsonata from "jsonata";
import {
  EMAIL,
  type FieldValue,
  NIP,
  PESEL,
  pattern,
  REGON,
  type Validator,
  ZIP_CODE,
} from "./validators";

export type CoiState = { type: "SHOW" | "READ_ONLY"; query: string };
export type CoiOption = { id: string; name: string; techName?: string };

export type CoiField = {
  id: string;
  type: string;
  techName: string;
  title: string;
  description?: string;
  options?: CoiOption[];
  /** Validator names; the reference files sometimes have `{}` instead of `[]`. */
  validation?: unknown;
  readOnly?: boolean;
  repeatingSectionGrid?: CoiQuestion[];
  defaultValue?: string | string[];
  defaultValueType?: "EXTERNAL_SYSTEM" | null;
  dictionaryName?: string | null;
  searchEnabled?: boolean | null;
  states?: CoiState[];
  tooltipMessage?: string;
  consentSectionConfig?: {
    consents: { description: string; required?: boolean }[];
  };
};

export type CoiQuestion = {
  x: number;
  y: number;
  rows: number;
  cols: number;
  minItemRows?: number;
  field: CoiField;
};

export type CoiTab = {
  id: string;
  title: string;
  type: "MAIN" | "FINISH";
  questions: CoiQuestion[];
};

export type CoiForm = {
  title: string;
  tabs: CoiTab[];
  flow?: { links: { id: string; source: string; target: string }[] };
};

export type Values = Record<string, FieldValue>;

/* ------------------------------------------------------------------ */
/* Structure                                                           */
/* ------------------------------------------------------------------ */

/** Tabs in flow order (start = tab that is never a target); JSON order as fallback. */
export function orderedTabs(form: CoiForm): CoiTab[] {
  const links = form.flow?.links ?? [];
  const byId = new Map(form.tabs.map((t) => [t.id, t]));
  const next = new Map(links.map((l) => [l.source, l.target]));
  const targets = new Set(links.map((l) => l.target));
  const start = form.tabs.find((t) => !targets.has(t.id) && next.has(t.id));
  if (!start) return form.tabs;
  const out: CoiTab[] = [];
  for (let t: CoiTab | undefined = start; t && !out.includes(t); ) {
    out.push(t);
    t = byId.get(next.get(t.id) ?? "");
  }
  // Tabs outside the flow still get shown, after the flow.
  return [...out, ...form.tabs.filter((t) => !out.includes(t))];
}

/** Grid order: row (y), then column (x). The standard asks for one column. */
export const sortQuestions = (qs: CoiQuestion[] = []) =>
  [...qs].sort((a, b) => a.y - b.y || a.x - b.x);

/** Every field in the form, depth first. */
export function* allFields(qs: CoiQuestion[]): Generator<CoiField> {
  for (const q of qs) {
    yield q.field;
    yield* allFields(q.field.repeatingSectionGrid ?? []);
  }
}

/* ------------------------------------------------------------------ */
/* Validation (names from "Reguły techniczne": REQUIRED, EMAIL, ...)   */
/* ------------------------------------------------------------------ */

const VALIDATORS: Record<string, Validator> = {
  EMAIL,
  PESEL,
  NIP,
  REGON,
  ZIP_CODE,
  EPUAP: pattern(
    /^\/?[\w.-]+\/[\w.-]+$/,
    "Wpisz adres skrytki ePUAP, np. /nazwaUrzedu/SkrytkaESP.",
  ),
  ADE: pattern(
    /^AE:PL-\d{5}-\d{5}-[A-Z]{5}-\d{2}$/i,
    "Wpisz adres do e-Doręczeń w formacie AE:PL-00000-00000-AAAAA-00.",
  ),
  SERIAL_NUMBER_ID_CARD: pattern(
    /^[A-Z]{3}\s?\d{6}$/i,
    "Wpisz serię i numer dowodu, np. ABC123456.",
  ),
};

/** Names like "REQUIRED"; accepts plain strings or `{ type }` / `{ name }` objects. */
export const validatorNames = (f: CoiField): string[] =>
  Array.isArray(f.validation)
    ? f.validation.flatMap((v) =>
        typeof v === "string" ? v : (v?.type ?? v?.name ?? []),
      )
    : [];

export const isRequired = (f: CoiField) =>
  validatorNames(f).includes("REQUIRED");

export const fieldValidators = (f: CoiField) =>
  validatorNames(f).flatMap((v) => VALIDATORS[v] ?? []);

/* ------------------------------------------------------------------ */
/* Options: own options or a dictionary (materialy/ "Słowniki")        */
/* ------------------------------------------------------------------ */

export const KRAJE = [
  "Polska",
  "Austria",
  "Belgia",
  "Bułgaria",
  "Chorwacja",
  "Cypr",
  "Czechy",
  "Dania",
  "Estonia",
  "Finlandia",
  "Francja",
  "Grecja",
  "Hiszpania",
  "Holandia",
  "Irlandia",
  "Litwa",
  "Luksemburg",
  "Łotwa",
  "Malta",
  "Niemcy",
  "Norwegia",
  "Portugalia",
  "Rumunia",
  "Słowacja",
  "Słowenia",
  "Szwajcaria",
  "Szwecja",
  "Ukraina",
  "Węgry",
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

/** Demo subsets; TERYT_* trees start at województwo (powiat/gmina not loaded). */
const DICTIONARIES: Record<string, string[]> = {
  Kraje: KRAJE,
  TERYT_DOWODOWY: WOJEWODZTWA,
  TERYT_4G_DOWODOWY: WOJEWODZTWA,
  Województwo: WOJEWODZTWA,
};

export function fieldOptions(f: CoiField): string[] {
  if (f.options?.length) return f.options.map((o) => o.name);
  return (f.dictionaryName && DICTIONARIES[f.dictionaryName]) || [];
}

/* ------------------------------------------------------------------ */
/* Initial values: defaultValue and EXTERNAL_SYSTEM (MLPZ) data        */
/* ------------------------------------------------------------------ */

/** Demo stand-in for the logged-in user's registry data (materialy/ "Dane inicjalne"). */
export const MLPZ_DEMO: Record<string, string> = {
  name: "JAN",
  secondName: "",
  surname: "KOWALSKI",
  pesel: "44051401359",
  email: "jan.kowalski@example.pl",
  phoneNumber: "+48600100200",
  country: "Polska",
  voivodeship: "mazowieckie",
  district: "warszawski zachodni",
  community: "Łomianki",
  place: "Łomianki",
  street: "Warszawska",
  building: "12",
  apartment: "4",
  postCode: "05-092",
};

export function fieldDefault(f: CoiField): FieldValue {
  const d = f.defaultValue;
  if (d === undefined || d === null) return undefined;
  if (f.defaultValueType === "EXTERNAL_SYSTEM" && typeof d === "string") {
    // "MLPZ.surname", "PESEL.surname": source system + key.
    return MLPZ_DEMO[d.replace(/^[A-Z]+\./, "")] || undefined;
  }
  if (Array.isArray(d)) {
    if (!d.length) return undefined;
    return f.type === "CHECKBOX" ? d : d[0];
  }
  return d;
}

/** Initial values for the whole form (repeating sections are filled per item). */
export function initialValues(form: CoiForm): Values {
  const out: Values = {};
  const walk = (qs: CoiQuestion[]) => {
    for (const { field } of qs) {
      if (field.type === "REPEATING_SECTION") continue;
      const v = fieldDefault(field);
      if (v !== undefined) out[field.techName] = v;
      walk(field.repeatingSectionGrid ?? []);
    }
  };
  for (const t of form.tabs) walk(t.questions);
  return out;
}

/* ------------------------------------------------------------------ */
/* Dynamic states (SHOW / READ_ONLY): real JSONata on the form JSON     */
/* with __userAnswer injected, as in "Reguły techniczne"               */
/* ------------------------------------------------------------------ */

/** Keys of repeating items present in values, e.g. "osoby[0]" → 0, in add order. */
export function repeatingKeys(values: Values, section: string): number[] {
  const re = new RegExp(
    `^${section.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\[(\\d+)\\]\\.`,
  );
  const keys = new Set<number>();
  for (const k of Object.keys(values)) {
    const m = re.exec(k);
    if (m) keys.add(Number(m[1]));
  }
  return [...keys].sort((a, b) => a - b);
}

/** Copy of the form where every field carries its `__userAnswer`. */
export function answerDocument(form: CoiForm, values: Values) {
  const withAnswers = (qs: CoiQuestion[] = []): unknown[] =>
    qs.map((q) => {
      const f = q.field;
      if (f.type === "REPEATING_SECTION") {
        const items = repeatingKeys(values, f.techName).map((k) =>
          [...allFields(f.repeatingSectionGrid ?? [])].map((c) => ({
            fieldTechName: c.techName,
            answers: values[`${f.techName}[${k}].${c.techName}`],
          })),
        );
        return {
          ...q,
          field: {
            ...f,
            repeatingSectionGrid: withAnswers(f.repeatingSectionGrid),
            __userAnswer: items,
          },
        };
      }
      return {
        ...q,
        field: {
          ...f,
          repeatingSectionGrid: withAnswers(f.repeatingSectionGrid),
          __userAnswer: values[f.techName],
        },
      };
    });
  return {
    ...form,
    tabs: form.tabs.map((t) => ({ ...t, questions: withAnswers(t.questions) })),
  };
}

export type FieldState = { show: boolean; readOnly: boolean };

const compiled = new Map<string, ReturnType<typeof jsonata> | null>();
function compile(query: string) {
  if (!compiled.has(query)) {
    try {
      compiled.set(query, jsonata(query));
    } catch {
      compiled.set(query, null); // invalid query: treated as false
    }
  }
  return compiled.get(query) ?? null;
}

async function truthy(
  query: string,
  doc: unknown,
  bindings?: Record<string, unknown>,
) {
  const expr = compile(query);
  if (!expr) return false;
  try {
    return Boolean(await expr.evaluate(doc, bindings));
  } catch {
    return false;
  }
}

/** One state per field with `states`; key = value key (techName or `sekcja[k].techName`). */
export async function evaluateStates(
  form: CoiForm,
  values: Values,
): Promise<Record<string, FieldState>> {
  const doc = answerDocument(form, values);
  const out: Record<string, FieldState> = {};
  const jobs: Promise<void>[] = [];

  const evalField = (
    f: CoiField,
    key: string,
    bindings?: Record<string, unknown>,
  ) => {
    const states = f.states ?? [];
    if (!states.length) return;
    jobs.push(
      (async () => {
        const results = await Promise.all(
          states.map(
            async (s) =>
              [s.type, await truthy(s.query, doc, bindings)] as const,
          ),
        );
        const of = (type: string) => results.filter(([t]) => t === type);
        out[key] = {
          show: of("SHOW").every(([, ok]) => ok),
          readOnly: of("READ_ONLY").some(([, ok]) => ok),
        };
      })(),
    );
  };

  const walk = (qs: CoiQuestion[], prefix?: string, index?: number) => {
    for (const { field } of qs) {
      const key = prefix ? `${prefix}.${field.techName}` : field.techName;
      const bindings =
        index === undefined ? undefined : { repeatingSectionIndex: index };
      evalField(field, key, bindings);
      if (field.type === "REPEATING_SECTION") {
        repeatingKeys(values, field.techName).forEach((k, i) => {
          walk(field.repeatingSectionGrid ?? [], `${field.techName}[${k}]`, i);
        });
      } else {
        walk(field.repeatingSectionGrid ?? [], prefix, index);
      }
    }
  };
  for (const t of form.tabs) walk(t.questions);
  await Promise.all(jobs);
  return out;
}
