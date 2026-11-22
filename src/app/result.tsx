"use client";

// A created form: its checks (rules, notes, safety scan), download and preview. Shared by the
// single-file flow and the list of several files (upload-form.tsx, batch.tsx).
import { cn } from "cn";
import {
  CircleCheck,
  Download,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { motion } from "motion/react";
import { type ReactNode, useMemo, useState } from "react";
import { ClauseContext, clauseLines } from "@/components/form/clause";
import { CoiFormView } from "@/components/form/coi-form";
import { InfoSection } from "@/components/form/fields";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import type { CoiForm } from "@/lib/form/coi";
import { type Finding, scanForm } from "@/lib/form/safety";
import { uniqueNames, zip } from "@/lib/zip";
import type { Result } from "./jobs";
import { JsonView } from "./json-view";

/** Rule errors and warnings, and content the model may have copied from a hostile document. */
export function useChecks(result: Result | undefined) {
  const findings = useMemo(
    () => (result ? scanForm(result.form) : []),
    [result],
  );
  const errors = result?.issues.filter((i) => i.level === "error") ?? [];
  // SAFETY_* warnings are the API's copy of the same scan (for other clients): shown once, in `findings`.
  const warnings =
    result?.issues.filter(
      (i) => i.level === "warning" && !i.code.startsWith("SAFETY_"),
    ) ?? [];
  return { findings, errors, warnings };
}

/** "Błędy: 0 · Ostrzeżenia: 2 · Treść do sprawdzenia: 1" */
export function checksText({
  errors,
  warnings,
  findings,
}: ReturnType<typeof useChecks>) {
  return `Błędy: ${errors.length} · Ostrzeżenia: ${warnings.length}${
    findings.length > 0 ? ` · Treść do sprawdzenia: ${findings.length}` : ""
  }`;
}

const formJson = (form: CoiForm) => JSON.stringify(form, null, 2);

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  // Firefox and Safari may read the blob after click() returns.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Saves the form JSON under the source file's name. */
export function download(form: CoiForm, sourceName: string) {
  const [name] = uniqueNames([sourceName], "json");
  save(new Blob([formJson(form)], { type: "application/json" }), name);
}

/** Saves the forms of several files as one ZIP, each JSON named after its source file. */
export function downloadZip(forms: { form: CoiForm; sourceName: string }[]) {
  const names = uniqueNames(
    forms.map((f) => f.sourceName),
    "json",
  );
  save(
    zip(forms.map((f, i) => ({ name: names[i], text: formJson(f.form) }))),
    "formularze.zip",
  );
}

/** Findings of the safety scan: what and where, to check before publishing. */
function Findings({ findings }: { findings: Finding[] }) {
  return (
    <section
      aria-labelledby="findings-title"
      className="flex flex-col gap-2 rounded-lg border-2 border-warning p-4"
    >
      <h3
        id="findings-title"
        className="flex items-center gap-2 text-sm font-bold"
      >
        <ShieldAlert className="size-4 shrink-0 text-warning" aria-hidden />
        Treść do sprawdzenia: {findings.length}
      </h3>
      <p className="text-sm text-muted-foreground">
        Te fragmenty nie wyglądają na zwykłą treść formularza urzędowego. Mogą
        pochodzić z dokumentu, który próbuje wpłynąć na model AI (prompt
        injection), albo z błędu modelu.
      </p>
      <ul className="flex flex-col gap-2 text-sm">
        {findings.map((f) => (
          <li key={`${f.code}-${f.where}-${f.message}`}>
            {f.message}
            <span className="block text-muted-foreground">{f.where}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Rule issues, notes and safety findings of one result. */
export function ResultChecks({ result }: { result: Result }) {
  const { findings, errors, warnings } = useChecks(result);
  return (
    <>
      {errors.length + warnings.length > 0 ? (
        <ul className="flex flex-col gap-2 text-sm">
          {[...errors, ...warnings].map((i) => (
            <li
              key={`${i.code}-${i.path}-${i.message}`}
              className={cn(
                "flex items-start gap-2",
                i.level === "error" && "text-destructive",
              )}
            >
              <TriangleAlert
                className={cn(
                  "mt-0.5 size-4 shrink-0",
                  i.level === "warning" && "text-warning",
                )}
                aria-hidden
              />
              <span>
                <span className="sr-only">
                  {i.level === "error" ? "Błąd: " : "Ostrzeżenie: "}
                </span>
                {i.message}
                {i.path && (
                  <span className="text-muted-foreground"> ({i.path})</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="flex items-center gap-2 text-sm">
          <CircleCheck className="size-4 text-success" aria-hidden />
          JSON spełnia reguły techniczne.
        </p>
      )}
      {result.notes.length > 0 && (
        <InfoSection title="Uwagi">
          <ul className="list-disc pl-4">
            {result.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </InfoSection>
      )}
      {findings.length > 0 && <Findings findings={findings} />}
    </>
  );
}

/**
 * "Pobierz JSON". When the safety scan found something, asks first: the content may come from a
 * document that tries to steer the model.
 */
export function DownloadButton({
  findings,
  onDownload,
  variant = "default",
  size = "default",
  children = "Pobierz JSON",
}: {
  findings: number;
  onDownload: () => void;
  variant?: "default" | "outline";
  size?: "default" | "sm";
  children?: ReactNode;
}) {
  const button = (
    <Button
      variant={variant}
      size={size}
      onClick={findings > 0 ? undefined : onDownload}
    >
      <Download data-icon="inline-start" aria-hidden />
      {children}
    </Button>
  );
  if (findings === 0) return button;
  return (
    <AlertDialog>
      <AlertDialogTrigger render={button} />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Formularz zawiera treść do sprawdzenia
          </AlertDialogTitle>
          <AlertDialogDescription>
            Znaleźliśmy miejsca do sprawdzenia: {findings}. Mogą pochodzić z
            dokumentu źródłowego, który próbuje wpłynąć na model AI. Sprawdź je
            przed publikacją formularza.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Wróć i sprawdź</AlertDialogCancel>
          <AlertDialogAction onClick={onDownload}>
            Pobierz mimo to
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** The created e-form rendered from its JSON, or the JSON itself. */
export function ResultPreview({ result }: { result: Result }) {
  const [view, setView] = useState<"form" | "json">("form");
  // The information clause cut from the document: shown behind the consent's link.
  const clause = useMemo(
    () => clauseLines(result.document?.blocks, result.spec?.block_roles),
    [result],
  );
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.25 }}
      className="flex flex-1 flex-col border-t"
    >
      <fieldset className="mx-auto flex w-full max-w-2xl gap-2 px-4 pt-8">
        <legend className="sr-only">Widok wyniku</legend>
        <Button
          variant={view === "form" ? "default" : "outline"}
          size="sm"
          aria-pressed={view === "form"}
          onClick={() => setView("form")}
        >
          Podgląd e-formularza
        </Button>
        <Button
          variant={view === "json" ? "default" : "outline"}
          size="sm"
          aria-pressed={view === "json"}
          onClick={() => setView("json")}
        >
          JSON
        </Button>
      </fieldset>
      {view === "form" ? (
        <ClauseContext.Provider value={clause}>
          <CoiFormView form={result.form} />
        </ClauseContext.Provider>
      ) : (
        <div className="mx-auto w-full max-w-2xl px-4 py-6">
          <JsonView data={result.form} />
        </div>
      )}
    </motion.div>
  );
}
