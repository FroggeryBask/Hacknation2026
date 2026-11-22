// Uploaded files in the browser: the same checks as the API before sending, name and size display.
import { ExternalLink } from "lucide-react";

// Same list as api/src/autoformularz/upload.py (EXTENSIONS).
export const FORMATS = [
  "pdf",
  "doc",
  "docx",
  "ods",
  "xlsx",
  "jpg",
  "jpeg",
  "png",
];
// Formats a browser can show in a tab; the others would only download.
const PREVIEWABLE = ["pdf", "jpg", "jpeg", "png"];

export const formatSize = (b: number) =>
  b < 1024 * 1024
    ? `${Math.max(1, Math.round(b / 1024))} KB`
    : `${(b / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;

const extension = (name: string) =>
  name.includes(".") ? (name.split(".").pop()?.toLowerCase() ?? "") : "";

// Task, "Walidacja nazwy pliku" (same rules as api/src/autoformularz/upload.py).
const MAX_NAME_LENGTH = 250;
const FORBIDDEN_CHARS = [
  ";",
  ":",
  ">",
  "<",
  "/",
  "\\",
  "|",
  "'",
  "*",
  "%",
  "$",
];

export function checkFile(f: File, maxSizeMb: number): string | undefined {
  if (f.name.length > MAX_NAME_LENGTH)
    return `Nazwa pliku jest za długa (${f.name.length} znaków). Może mieć najwyżej ${MAX_NAME_LENGTH} znaków. Zmień nazwę pliku i dodaj go ponownie.`;
  const bad = FORBIDDEN_CHARS.filter((c) => f.name.includes(c));
  if (bad.length)
    return `Nazwa pliku zawiera niedozwolone znaki: ${bad.join(" ")}. Zmień nazwę pliku i dodaj go ponownie.`;
  if (!FORMATS.includes(extension(f.name)))
    return "Ten format pliku nie jest obsługiwany. Wybierz plik PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.";
  if (f.size === 0) return "Plik jest pusty.";
  if (f.size > maxSizeMb * 1024 * 1024)
    return `Plik jest za duży. Maksymalny rozmiar: ${maxSizeMb} MB.`;
}

/** The same file picked twice (same name, size and date) is added once. */
export const sameFile = (a: File, b: File) =>
  a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;

/** File name; for PDF and images a link that opens the file in a new tab. */
export function FileName({ file, url }: { file: File; url?: string }) {
  if (!url || !PREVIEWABLE.includes(extension(file.name)))
    return <span className="block truncate font-bold">{file.name}</span>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      title="Otwórz podgląd pliku w nowej karcie"
      className="group inline-flex max-w-full items-center gap-1 rounded-xs font-bold text-link underline underline-offset-4 outline-none hover:decoration-2 focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <span className="truncate">{file.name}</span>
      {/* Shown on hover and keyboard focus; always on touch screens (no hover). */}
      <ExternalLink
        className="size-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 [@media(hover:none)]:opacity-100"
        aria-hidden
      />
      <span className="sr-only">(podgląd otwiera się w nowej karcie)</span>
    </a>
  );
}
