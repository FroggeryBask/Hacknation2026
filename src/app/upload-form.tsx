"use client";

import { cn } from "cn";
import {
  CircleCheck,
  Download,
  FileText,
  LoaderCircle,
  TriangleAlert,
  Upload,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { CoiFormView } from "@/components/form/coi-form";
import { FieldError, InfoSection } from "@/components/form/fields";
import { FormSection } from "@/components/form/layout";
import { Button } from "@/components/ui/button";
import type { CoiForm } from "@/lib/form/coi";

// Same list as api/src/autoformularz/upload.py (EXTENSIONS).
const FORMATS = ["pdf", "doc", "docx", "ods", "xlsx", "jpg", "jpeg", "png"];

type Issue = {
  level: "error" | "warning";
  code: string;
  message: string;
  path: string;
};
type Result = { form: CoiForm; issues: Issue[]; notes: string[] };
type State =
  | { step: "idle" }
  | { step: "sending" }
  | { step: "done"; result: Result };

const formatSize = (b: number) =>
  b < 1024 * 1024
    ? `${Math.max(1, Math.round(b / 1024))} KB`
    : `${(b / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;

const extension = (name: string) =>
  name.includes(".") ? (name.split(".").pop()?.toLowerCase() ?? "") : "";

function checkFile(f: File, maxSizeMb: number): string | undefined {
  if (!FORMATS.includes(extension(f.name)))
    return "Ten format pliku nie jest obsługiwany. Wybierz plik PDF, DOC, DOCX, ODS, XLSX, JPG lub PNG.";
  if (f.size === 0) return "Plik jest pusty.";
  if (f.size > maxSizeMb * 1024 * 1024)
    return `Plik jest za duży. Maksymalny rozmiar: ${maxSizeMb} MB.`;
}

/** Message from the API (`{error: {message}}`) or FastAPI (`{detail}`). */
async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const msg = body?.error?.message ?? body?.detail;
    if (typeof msg === "string") return msg;
  } catch {}
  return `Nie udało się utworzyć formularza (błąd ${res.status}). Spróbuj ponownie.`;
}

function download(form: CoiForm, sourceName: string) {
  const base = sourceName.replace(/\.[^.]+$/, "") || "formularz";
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(form, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `${base}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function useElapsed(running: boolean) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    setSeconds(0);
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [running]);
  return seconds;
}

const elapsedText = (s: number) =>
  s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;

export function UploadForm({ maxSizeMb }: { maxSizeMb: number }) {
  const [file, setFile] = useState<File>();
  const [error, setError] = useState<string>();
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<State>({ step: "idle" });
  const [run, setRun] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const preview = useRef<HTMLDivElement>(null);
  const sending = state.step === "sending";
  const elapsed = useElapsed(sending);

  const pick = (f?: File) => {
    if (!f) return;
    setState({ step: "idle" });
    const problem = checkFile(f, maxSizeMb);
    setError(problem);
    setFile(problem ? undefined : f);
  };

  const submit = async () => {
    if (!file) {
      setError("Wybierz plik formularza.");
      return;
    }
    setError(undefined);
    setState({ step: "sending" });
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch("/api/forms", { method: "POST", body });
      if (!res.ok) throw new Error(await errorMessage(res));
      const result = (await res.json()) as Result;
      setRun((r) => r + 1);
      setState({ step: "done", result });
      requestAnimationFrame(() =>
        preview.current?.scrollIntoView({ behavior: "smooth" }),
      );
    } catch (e) {
      setState({ step: "idle" });
      setError(
        e instanceof Error && e.message !== "Failed to fetch"
          ? e.message
          : "Brak połączenia z serwerem. Spróbuj ponownie.",
      );
    }
  };

  const reset = () => {
    setFile(undefined);
    setError(undefined);
    setState({ step: "idle" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const result = state.step === "done" ? state.result : undefined;
  const errors = result?.issues.filter((i) => i.level === "error") ?? [];
  const warnings = result?.issues.filter((i) => i.level === "warning") ?? [];

  return (
    <div className="flex flex-1 flex-col bg-page">
      <div className="px-4 py-8 sm:py-12">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
          <header className="flex flex-col gap-2">
            <h1 className="text-2xl font-bold leading-tight">
              Stwórz e-formularz
            </h1>
          </header>

          <FormSection title="Dodaj plik formularza papierowego">
            {/* biome-ignore lint/a11y/noStaticElementInteractions: drop target; the button inside is the keyboard path */}
            {/* biome-ignore lint/a11y/useKeyWithClickEvents: keyboard uses the button, whose click bubbles here */}
            <div
              onClick={() => input.current?.click()}
              className={cn(
                "flex cursor-pointer flex-col items-center gap-3 rounded-sm border border-dashed border-input px-4 py-8 text-center transition-colors hover:bg-secondary",
                dragging && "border-primary bg-secondary",
                error && "border-destructive",
                sending && "pointer-events-none opacity-60",
              )}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                pick(e.dataTransfer.files[0]);
              }}
            >
              <span className="grid size-12 place-items-center rounded-full bg-secondary text-primary">
                <Upload className="size-6" aria-hidden />
              </span>
              <p className="flex flex-col gap-3 text-sm">
                <span className="font-bold text-primary">
                  Przeciągnij plik tutaj
                </span>
                albo
              </p>
              <Button
                variant="outline"
                disabled={sending}
                aria-describedby={error ? "plik-err" : undefined}
              >
                Wybierz plik z dysku
              </Button>
              <input
                ref={input}
                id="plik"
                type="file"
                className="sr-only"
                tabIndex={-1}
                accept={FORMATS.map((f) => `.${f}`).join(",")}
                onChange={(e) => {
                  pick(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </div>

            {file && (
              <div className="flex items-center gap-2 rounded-sm bg-secondary px-3 py-2 text-sm">
                <FileText className="size-4 text-primary" aria-hidden />
                <span className="flex-1 truncate font-bold">{file.name}</span>
                <span className="text-muted-foreground">
                  {formatSize(file.size)}
                </span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  disabled={sending}
                  aria-label={`Usuń plik ${file.name}`}
                  onClick={reset}
                >
                  <X className="text-primary" />
                </Button>
              </div>
            )}

            <FieldError id="plik-err" error={error} />

            <InfoSection>
              Po kliknięciu „Utwórz formularz” plik przeanalizuje model
              sztucznej inteligencji. Może to potrwać kilka minut.
            </InfoSection>
          </FormSection>

          <div className="flex flex-wrap items-center justify-end gap-3">
            <output className="text-sm text-muted-foreground">
              {sending && (
                <>
                  Trwa tworzenie formularza
                  {/* Ticking timer is visual only, so screen readers hear the status once. */}
                  <span aria-hidden>: {elapsedText(elapsed)}</span>
                </>
              )}
            </output>
            {result ? (
              <Button variant="outline" onClick={reset}>
                Dodaj inny plik
              </Button>
            ) : (
              <Button onClick={submit} disabled={sending}>
                {sending && (
                  <LoaderCircle
                    data-icon="inline-start"
                    className="animate-spin"
                    aria-hidden
                  />
                )}
                {sending ? "Tworzę formularz" : "Utwórz formularz"}
              </Button>
            )}
          </div>

          <AnimatePresence>
            {result && (
              <motion.div
                key={`wynik-${run}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <FormSection
                  title="Formularz jest gotowy"
                  description={
                    <p>
                      <span className="font-bold">{result.form.title}</span>
                      {" · "}
                      Błędy: {errors.length} · Ostrzeżenia: {warnings.length}
                    </p>
                  }
                >
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
                              <span className="text-muted-foreground">
                                {" "}
                                ({i.path})
                              </span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="flex items-center gap-2 text-sm">
                      <CircleCheck
                        className="size-4 text-success"
                        aria-hidden
                      />
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
                  <Button
                    className="self-start"
                    onClick={() => file && download(result.form, file.name)}
                  >
                    <Download data-icon="inline-start" aria-hidden />
                    Pobierz JSON
                  </Button>
                </FormSection>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {result && (
        <div ref={preview} className="flex flex-1 flex-col border-t">
          <p className="mx-auto w-full max-w-2xl px-4 pt-8 text-sm font-bold uppercase tracking-wide text-muted-foreground">
            Podgląd e-formularza
          </p>
          <CoiFormView key={run} form={result.form} abortHref="/" />
        </div>
      )}
    </div>
  );
}
