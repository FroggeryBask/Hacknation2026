// Checks a generated COI form for content that should not be there.
//
// The model reads text from an uploaded document. A document can carry text
// written for the model ("ignore previous instructions…", prompt injection) or
// a fake form asking for passwords or card data, and the model may copy it into
// labels, hints, options and links. The JSON schema and the compiler fix the
// structure, but not the words. This scan runs on the result before anyone
// sees or downloads it: it warns, it does not change the JSON.

import type { CoiField, CoiForm } from "./coi";

export type Finding = {
  code:
    | "SENSITIVE_DATA"
    | "EXTERNAL_LINK"
    | "UNSAFE_LINK"
    | "INSTRUCTION"
    | "HIDDEN_CHARS"
    | "LONG_TEXT"
    | "MARKUP";
  message: string;
  /** Where it is, for people: "Strona „Dane” › Sekcja „Kontakt” › Pole „Hasło”". */
  where: string;
};

// Data a public form never asks for. Bank account numbers are fine (refunds).
const SENSITIVE =
  /\bhas(ł|l)\w*|\bpin\b|\bkod\w* (sms|weryfikacyjn\w*|autoryzacyjn\w*|jednorazow\w*|blik)|\bblik\b|\bcvv\b|\bcvc\b|kart\w* (płatnicz|kredytow|debetow|bankow)\w*|data ważności karty|\blogin\b(?!\.gov)|nazw\w* użytkownika|\bpassword\b|\btoken\w*|klucz\w* prywatn\w*|fraz\w* (odzyskiwania|seed)|\bseed\b/i;

// Text addressed to a language model, not to a citizen.
const INSTRUCTION =
  /\b(ignore|disregard|forget)\b.{0,30}\b(previous|above|prior|earlier|all)\b.{0,20}\b(instructions?|prompts?|rules)\b|\bzignoruj\w*\b.{0,40}\b(instrukcj\w*|polece\w*|zasad\w*|reguł\w*)|\bsystem prompt\b|\bprompt\b|\byou are (now )?(an? )?(ai|assistant|language model|chatgpt)\b|\bjesteś (teraz )?(asystent\w*|model\w*|ai)\b|\bact as\b|\bjako model (językowy|ai)\b|<\|?(im_start|im_end|system)\|?>|\[\/?(inst|system)\]|^\s*(system|assistant)\s*:/im;

// Zero-width and bidirectional control characters: hide or reorder text.
const HIDDEN = /[​-‏‪-‮⁠-⁤⁦-⁩﻿]/;

// HTML the renderer drops anyway, but it should never come from a paper form.
const MARKUP =
  /<\s*(script|iframe|object|embed|form|input|style)\b|\bon[a-z]+\s*=|javascript:|data:text\/html/i;

const URL_IN_TEXT = /\bhttps?:\/\/[^\s"'<>)]+/gi;
const HREF = /href\s*=\s*["']([^"']*)["']/gi;

/** Public administration domains: gov.pl and its subdomains (BIP, urzędy). */
const trustedHost = (host: string) =>
  host === "gov.pl" || host.endsWith(".gov.pl");

const LONG_LABEL = 200;

/** Text of an HTML description, without tags. */
const plain = (html: string) =>
  html
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();

function links(html: string): string[] {
  const out = new Set<string>();
  for (const m of html.matchAll(HREF)) out.add(m[1].trim());
  for (const m of plain(html).matchAll(URL_IN_TEXT)) out.add(m[0]);
  return [...out];
}

type Text = { text: string; html?: string; where: string; label?: boolean };

/** Every piece of text in the form, with where it is. */
function texts(form: CoiForm): Text[] {
  const out: Text[] = [
    { text: form.title ?? "", where: "Tytuł formularza", label: true },
  ];
  const field = (f: CoiField, path: string) => {
    const kind =
      f.type === "SECTION" || f.type === "REPEATING_SECTION"
        ? "Sekcja"
        : "Pole";
    const where = f.title
      ? `${path} › ${kind} „${short(f.title)}”`
      : `${path} › ${kind} ${f.techName}`;
    if (f.title) out.push({ text: f.title, where, label: true });
    if (f.description)
      out.push({ text: plain(f.description), html: f.description, where });
    if (f.tooltipMessage) out.push({ text: f.tooltipMessage, where });
    for (const o of f.options ?? [])
      out.push({ text: o.name ?? "", where: `${where} › opcja`, label: true });
    for (const [i, c] of (f.consentSectionConfig?.consents ?? []).entries())
      out.push({
        text: plain(c.description ?? ""),
        html: c.description,
        where: `${where} › zgoda ${i + 1}`,
      });
    for (const q of f.repeatingSectionGrid ?? []) field(q.field, where);
  };
  for (const tab of form.tabs ?? []) {
    const path = `Strona „${short(tab.title)}”`;
    out.push({ text: tab.title ?? "", where: path, label: true });
    for (const q of tab.questions ?? []) field(q.field, path);
  }
  return out;
}

const short = (s: string) => (s.length > 60 ? `${s.slice(0, 57)}…` : s);

export function scanForm(form: CoiForm): Finding[] {
  const found: Finding[] = [];
  const seen = new Set<string>();
  const add = (f: Finding) => {
    const key = `${f.code}|${f.where}|${f.message}`;
    if (!seen.has(key)) {
      seen.add(key);
      found.push(f);
    }
  };
  for (const t of texts(form)) {
    if (!t.text && !t.html) continue;
    const sensitive = SENSITIVE.exec(t.text);
    if (sensitive)
      add({
        code: "SENSITIVE_DATA",
        where: t.where,
        message: `Formularz prosi o dane, o które urząd nie pyta („${sensitive[0]}”). Sprawdź, czy to jest w dokumencie źródłowym.`,
      });
    if (INSTRUCTION.test(t.text))
      add({
        code: "INSTRUCTION",
        where: t.where,
        message:
          "Tekst wygląda na polecenie dla modelu AI, a nie treść formularza (możliwa próba prompt injection).",
      });
    if (HIDDEN.test(t.text) || (t.html && HIDDEN.test(t.html)))
      add({
        code: "HIDDEN_CHARS",
        where: t.where,
        message:
          "Tekst zawiera niewidoczne znaki sterujące, które mogą ukrywać lub odwracać treść.",
      });
    if (MARKUP.test(t.html ?? t.text))
      add({
        code: "MARKUP",
        where: t.where,
        message:
          "Tekst zawiera kod HTML lub skrypt. Podgląd go pomija, ale nie powinno go być w formularzu.",
      });
    if (t.label && t.text.length > LONG_LABEL)
      add({
        code: "LONG_TEXT",
        where: t.where,
        message: `Etykieta ma ${t.text.length} znaków. Etykiety powinny być krótkie: przenieś opis do podpowiedzi pola.`,
      });
    for (const link of links(t.html ?? t.text)) {
      if (link.startsWith("#")) continue; // anchor on the same page (e.g. the information clause)
      let url: URL;
      try {
        url = new URL(link);
      } catch {
        add({
          code: "UNSAFE_LINK",
          where: t.where,
          message: `Nieprawidłowy adres linku: ${short(link)}`,
        });
        continue;
      }
      if (url.protocol !== "https:")
        add({
          code: "UNSAFE_LINK",
          where: t.where,
          message: `Link nie używa bezpiecznego połączenia HTTPS: ${short(link)}`,
        });
      else if (!trustedHost(url.hostname))
        add({
          code: "EXTERNAL_LINK",
          where: t.where,
          message: `Link prowadzi poza domenę gov.pl: ${url.hostname}. Sprawdź, czy to strona urzędu.`,
        });
    }
  }
  return found;
}
