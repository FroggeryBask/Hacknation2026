"use client";

import { cn } from "cn";
import {
  Check,
  CircleCheck,
  Download,
  ExternalLink,
  FileText,
  LoaderCircle,
  TriangleAlert,
  Upload,
  X,
} from "lucide-react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { AiIcon } from "@/components/form/ai-icon";
import { CoiFormView } from "@/components/form/coi-form";
import { FieldError, InfoSection } from "@/components/form/fields";
import { FormSection, Stepper } from "@/components/form/layout";
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

// Same list as api/src/autoformularz/upload.py (EXTENSIONS).
const FORMATS = ["pdf", "doc", "docx", "ods", "xlsx", "jpg", "jpeg", "png"];
// Formats a browser can show in a tab; the others would only download.
const PREVIEWABLE = ["pdf", "jpg", "jpeg", "png"];

const STEPS = [
  "Dodaj plik formularza",
  "Tworzymy formularz",
  "Sprawdź formularz utworzony przez AI",
];

type Issue = {
  level: "error" | "warning";
  code: string;
  message: string;
  path: string;
};
type Result = { form: CoiForm; issues: Issue[]; notes: string[] };
/** A pipeline stage, or what the model or the code found in it (api progress.py). */
type Progress = { kind: "stage" | "item"; text: string };
type Job = {
  status: "running" | "done" | "error" | "cancelled";
  steps: Progress[];
  result?: Result;
  error?: { message: string };
};
type State =
  | { step: "idle" }
  | { step: "sending"; steps: Progress[] }
  | { step: "done"; result: Result };

const POLL_MS = 1500;
// Polls that may fail in a row (e.g. a restarting proxy) before the page gives up.
const POLL_RETRIES = 3;

const wait = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });

/** Stages with the items found in each, in the order they came. */
function groupSteps(steps: Progress[]) {
  const out: { stage: string; items: string[] }[] = [];
  for (const s of steps) {
    if (s.kind === "stage") out.push({ stage: s.text, items: [] });
    else if (out.length) out[out.length - 1].items.push(s.text);
  }
  return out;
}

/** Stages one under another; the current one spins, items are listed under their stage. */
function StepLog({ steps }: { steps: Progress[] }) {
  const end = useRef<HTMLDivElement>(null);
  const groups = groupSteps(steps);
  // biome-ignore lint/correctness/useExhaustiveDependencies: follow new steps
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [steps.length]);
  if (!groups.length) return null;
  return (
    <div className="max-h-80 overflow-y-auto rounded-sm border bg-secondary px-3 py-2 text-sm">
      <ol className="flex flex-col gap-2">
        {groups.map((g, i) => {
          const current = i === groups.length - 1;
          return (
            <li key={`${i}-${g.stage}`}>
              <span className="flex items-center gap-2 font-bold">
                {current ? (
                  <LoaderCircle
                    className="size-4 shrink-0 animate-spin text-primary"
                    aria-hidden
                  />
                ) : (
                  <Check className="size-4 shrink-0 text-success" aria-hidden />
                )}
                {g.stage}
              </span>
              {g.items.length > 0 && (
                <ul className="mt-1 flex flex-col gap-0.5 pl-6 text-muted-foreground">
                  {g.items.map((t, j) => (
                    <motion.li
                      // biome-ignore lint/suspicious/noArrayIndexKey: items only append, names may repeat
                      key={j}
                      initial={{ opacity: 0, y: -2 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.15 }}
                    >
                      {t}
                    </motion.li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ol>
      <div ref={end} />
    </div>
  );
}

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

/** File name; for PDF and images a link that opens the file in a new tab. */
function FileName({ file, url }: { file: File; url?: string }) {
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

/**
 * One step of the page. Collapses on exit; takes focus when the step changes,
 * because the control that was focused (e.g. "Utwórz formularz") disappears.
 */
function StepPanel({
  label,
  focus,
  children,
}: {
  label: string;
  focus: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: only on mount
  useEffect(() => {
    if (focus) ref.current?.focus({ preventScroll: true });
  }, []);
  return (
    <motion.div
      ref={ref}
      tabIndex={-1}
      role="group"
      aria-label={label}
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="overflow-hidden outline-none"
    >
      <div className="flex flex-col gap-4">{children}</div>
    </motion.div>
  );
}

export function UploadForm({ maxSizeMb }: { maxSizeMb: number }) {
  const [file, setFile] = useState<File>();
  const [fileUrl, setFileUrl] = useState<string>();
  const [error, setError] = useState<string>();
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<State>({ step: "idle" });
  const [run, setRun] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController>(null);
  // Move focus to the new step only after a user action, not on page load.
  const moved = useRef(false);
  const sending = state.step === "sending";
  const elapsed = useElapsed(sending);
  const step = state.step === "idle" ? 0 : sending ? 1 : 2;

  useEffect(() => {
    if (!file) return setFileUrl(undefined);
    const url = URL.createObjectURL(file);
    setFileUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const goTo = (next: State) => {
    moved.current = true;
    setState(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

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
    goTo({ step: "sending", steps: [] });
    const body = new FormData();
    body.append("file", file);
    const controller = new AbortController();
    abort.current = controller;
    const { signal } = controller;
    let id: string | undefined;
    // Cancelling stops the job on the server too: the model stops writing, no more tokens are paid.
    signal.addEventListener("abort", () => {
      if (id) fetch(`/api/forms/${id}`, { method: "DELETE" }).catch(() => {});
    });
    try {
      const res = await fetch("/api/forms", { method: "POST", body, signal });
      if (!res.ok) throw new Error(await errorMessage(res));
      id = ((await res.json()) as { id: string }).id;
      let failures = 0;
      let job: Job | undefined;
      while (!signal.aborted) {
        await wait(POLL_MS, signal);
        if (signal.aborted) break;
        const poll = await fetch(`/api/forms/${id}`, { signal }).catch(
          () => undefined,
        );
        if (!poll?.ok) {
          if (poll && poll.status < 500)
            throw new Error(await errorMessage(poll));
          if (++failures > POLL_RETRIES)
            throw new Error(
              poll ? await errorMessage(poll) : "Failed to fetch",
            );
          continue;
        }
        failures = 0;
        job = (await poll.json()) as Job;
        const steps = job.steps;
        setState((s) =>
          s.step === "sending" ? { step: "sending", steps } : s,
        );
        if (job.status !== "running") break;
      }
      if (signal.aborted) throw new Error("Anulowano.");
      if (job?.status !== "done" || !job.result)
        throw new Error(
          job?.error?.message ??
            "Nie udało się utworzyć formularza. Spróbuj ponownie.",
        );
      const result = job.result;
      setRun((r) => r + 1);
      goTo({ step: "done", result });
    } catch (e) {
      goTo({ step: "idle" });
      if (controller.signal.aborted) return;
      setError(
        e instanceof Error && e.message !== "Failed to fetch"
          ? e.message
          : "Brak połączenia z serwerem. Spróbuj ponownie.",
      );
    } finally {
      if (abort.current === controller) abort.current = null;
    }
  };

  const cancel = () => abort.current?.abort();

  const reset = () => {
    setFile(undefined);
    setError(undefined);
    goTo({ step: "idle" });
  };

  const result = state.step === "done" ? state.result : undefined;
  const errors = result?.issues.filter((i) => i.level === "error") ?? [];
  const warnings = result?.issues.filter((i) => i.level === "warning") ?? [];
  const stepLabel = (i: number) => `Krok ${i + 1}: ${STEPS[i]}`;

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex flex-1 flex-col bg-page">
        <div className="px-4 py-8 sm:py-12">
          <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
            <h1 className="text-2xl font-bold leading-tight">
              Stwórz e-formularz
            </h1>
            <Stepper
              steps={STEPS}
              current={step}
              label="Kroki tworzenia e-formularza"
            />

            <AnimatePresence mode="wait" initial={false}>
              {step === 0 && (
                <StepPanel
                  key="plik"
                  label={stepLabel(0)}
                  focus={moved.current}
                >
                  <FormSection title="Dodaj plik formularza papierowego">
                    {/* biome-ignore lint/a11y/noStaticElementInteractions: drop target; the button inside is the keyboard path */}
                    {/* biome-ignore lint/a11y/useKeyWithClickEvents: keyboard uses the button, whose click bubbles here */}
                    <div
                      onClick={() => input.current?.click()}
                      className={cn(
                        "flex cursor-pointer flex-col items-center gap-3 rounded-sm border border-dashed border-input px-4 py-8 text-center transition-colors hover:bg-secondary",
                        dragging && "border-primary bg-secondary",
                        error && "border-destructive",
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
                        <FileText
                          className="size-4 shrink-0 text-primary"
                          aria-hidden
                        />
                        <span className="min-w-0 flex-1">
                          <FileName file={file} url={fileUrl} />
                        </span>
                        <span className="text-muted-foreground">
                          {formatSize(file.size)}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon-xs"
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

                  <div className="flex justify-end">
                    <Button onClick={submit}>Utwórz formularz</Button>
                  </div>
                </StepPanel>
              )}

              {step === 1 && file && (
                <StepPanel
                  key="tworzenie"
                  label={stepLabel(1)}
                  focus={moved.current}
                >
                  <FormSection
                    title="Tworzymy formularz"
                    description={<FileName file={file} url={fileUrl} />}
                  >
                    <div className="flex items-center gap-3 text-sm">
                      <LoaderCircle
                        className="size-5 shrink-0 animate-spin text-primary"
                        aria-hidden
                      />
                      <output>
                        {state.step === "sending" && state.steps.length
                          ? `Trwa: ${groupSteps(state.steps).at(-1)?.stage}.`
                          : "Trwa tworzenie formularza."}{" "}
                        Może to potrwać kilka minut.
                        {/* Ticking timer is visual only, so screen readers hear the status once. */}
                        <span
                          className="block text-muted-foreground"
                          aria-hidden
                        >
                          Upłynęło: {elapsedText(elapsed)}
                        </span>
                      </output>
                    </div>
                    {state.step === "sending" && (
                      <StepLog steps={state.steps} />
                    )}
                  </FormSection>
                  <div className="flex justify-end">
                    <AlertDialog>
                      <AlertDialogTrigger
                        render={<Button variant="destructive">Anuluj</Button>}
                      />
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Czy na pewno chcesz anulować?
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            Tworzenie formularza zostanie przerwane, a
                            dotychczasowe postępy zostaną utracone. Plik
                            pozostanie wybrany i możesz spróbować ponownie.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Nie, kontynuuj</AlertDialogCancel>
                          <AlertDialogAction
                            variant="destructive"
                            onClick={cancel}
                          >
                            Tak, anuluj
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </StepPanel>
              )}

              {result && (
                <StepPanel
                  key={`wynik-${run}`}
                  label={stepLabel(2)}
                  focus={moved.current}
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
                    <InfoSection icon={<AiIcon className="mt-0.5" />}>
                      Formularz utworzył model sztucznej inteligencji. Może
                      zawierać błędy. Sprawdź go przed publikacją.
                    </InfoSection>
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
                                {i.level === "error"
                                  ? "Błąd: "
                                  : "Ostrzeżenie: "}
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
                    <div className="flex flex-wrap gap-3">
                      <Button
                        onClick={() => file && download(result.form, file.name)}
                      >
                        <Download data-icon="inline-start" aria-hidden />
                        Pobierz JSON
                      </Button>
                      <Button variant="outline" onClick={reset}>
                        Dodaj inny plik
                      </Button>
                    </div>
                  </FormSection>
                </StepPanel>
              )}
            </AnimatePresence>
          </div>
        </div>

        {result && (
          <motion.div
            key={`podglad-${run}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="flex flex-1 flex-col border-t"
          >
            <p className="mx-auto w-full max-w-2xl px-4 pt-8 text-sm font-bold uppercase tracking-wide text-muted-foreground">
              Podgląd e-formularza
            </p>
            <CoiFormView key={run} form={result.form} abortHref="/" />
          </motion.div>
        )}
      </div>
    </MotionConfig>
  );
}
