"use client";

import { cn } from "cn";
import { Check, FileText, LoaderCircle, Upload, X } from "lucide-react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { AiIcon } from "@/components/form/ai-icon";
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
import { scanForm } from "@/lib/form/safety";
import { BatchList, batchSummary, type Item, isPending } from "./batch";
import { checkFile, FileName, FORMATS, formatSize, sameFile } from "./files";
import {
  currentStage,
  failureText,
  type Progress,
  type Result,
  runJob,
  runQueue,
} from "./jobs";
import {
  checksText,
  DownloadButton,
  download,
  downloadZip,
  ResultChecks,
  ResultPreview,
  useChecks,
} from "./result";

const STEPS = [
  "Dodaj plik formularza",
  "Generowanie formularza",
  "Weryfikacja formularza",
];
const STEPS_MANY = [
  "Dodaj pliki formularzy",
  "Generowanie formularzy",
  "Weryfikacja formularzy",
];
// Several files at once (task 3.3.VI, batch). Each file costs one model call; the API runs at most
// 4 jobs for all users (jobs.py MAX_RUNNING), so one page takes 2 and leaves room for others.
const MAX_FILES = 20;
const BATCH_CONCURRENCY = 2;

type State =
  | { step: "idle" }
  | { step: "sending"; steps: Progress[] }
  | { step: "done"; result: Result }
  | { step: "batch"; items: Item[] };

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

/** Ticking timer, visual only, so screen readers hear the status once. */
function Elapsed({ seconds }: { seconds: number }) {
  return (
    <span className="block text-muted-foreground" aria-hidden>
      Upłynęło: {elapsedText(seconds)}
    </span>
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

/** A destructive button that asks before it acts. */
function ConfirmButton({
  label,
  title,
  description,
  cancel,
  confirm,
  onConfirm,
}: {
  label: string;
  title: string;
  description: string;
  cancel: string;
  confirm: string;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={<Button variant="destructive">{label}</Button>}
      />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancel}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={onConfirm}>
            {confirm}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function UploadForm({ maxSizeMb }: { maxSizeMb: number }) {
  const [files, setFiles] = useState<File[]>([]);
  const [objectUrls, setObjectUrls] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<State>({ step: "idle" });
  const [run, setRun] = useState(0);
  // The file whose form is shown below the list (several files).
  const [selected, setSelected] = useState<number>();
  const input = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController>(null);
  // Move focus to the new step only after a user action, not on page load.
  const moved = useRef(false);
  const many = files.length > 1;
  const steps = many ? STEPS_MANY : STEPS;
  const sending = state.step === "sending";
  const items = state.step === "batch" ? state.items : [];
  const batchRunning = items.some(isPending);
  const elapsed = useElapsed(sending || batchRunning);
  const step = state.step === "idle" ? 0 : sending || batchRunning ? 1 : 2;
  // The links are made after a render with the new files: until then a row would open another file.
  const urls = objectUrls.length === files.length ? objectUrls : [];

  useEffect(() => {
    const list = files.map((f) => URL.createObjectURL(f));
    setObjectUrls(list);
    return () => {
      for (const u of list) URL.revokeObjectURL(u);
    };
  }, [files]);

  // Leaving the page stops its jobs: the model stops writing, no more tokens are paid.
  useEffect(() => () => abort.current?.abort(), []);

  const goTo = (next: State) => {
    moved.current = true;
    setState(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const add = (picked: File[]) => {
    if (!picked.length) return;
    setState({ step: "idle" });
    const problems: string[] = [];
    const next = [...files];
    // With several files the message says which one.
    const named = files.length + picked.length > 1;
    for (const f of picked) {
      const problem = checkFile(f, maxSizeMb);
      if (problem) problems.push(named ? `${f.name}: ${problem}` : problem);
      else if (!next.some((g) => sameFile(f, g))) next.push(f);
    }
    if (next.length > MAX_FILES)
      problems.push(
        `Możesz dodać najwyżej ${MAX_FILES} plików naraz. Pominięto: ${next
          .splice(MAX_FILES)
          .map((f) => f.name)
          .join(", ")}.`,
      );
    setErrors(problems);
    setFiles(next);
  };

  const remove = (i: number) => {
    setErrors([]);
    setFiles((fs) => fs.filter((_, j) => j !== i));
  };

  const reset = () => {
    setFiles([]);
    setErrors([]);
    setSelected(undefined);
    goTo({ step: "idle" });
  };

  /** Starts a new controller for the page's jobs; the cancel button aborts it. */
  const control = () => {
    const controller = new AbortController();
    abort.current = controller;
    return controller;
  };
  const release = (controller: AbortController) => {
    if (abort.current === controller) abort.current = null;
  };

  const submitOne = async (file: File) => {
    goTo({ step: "sending", steps: [] });
    const controller = control();
    try {
      const result = await runJob(file, controller.signal, (steps) =>
        setState((s) =>
          s.step === "sending" ? { step: "sending", steps } : s,
        ),
      );
      setRun((r) => r + 1);
      goTo({ step: "done", result });
    } catch (e) {
      goTo({ step: "idle" });
      if (!controller.signal.aborted) setErrors([failureText(e)]);
    } finally {
      release(controller);
    }
  };

  /** Runs (or runs again) the files at `indexes` of the batch, BATCH_CONCURRENCY at a time. */
  const runBatch = async (list: File[], indexes: number[]) => {
    const controller = control();
    const { signal } = controller;
    const update = (pick: (it: Item, i: number) => Partial<Item> | undefined) =>
      setState((s) =>
        s.step === "batch"
          ? {
              ...s,
              items: s.items.map((it, i) => {
                const patch = pick(it, i);
                return patch ? { ...it, ...patch } : it;
              }),
            }
          : s,
      );
    const one = (i: number, patch: Partial<Item>) =>
      update((_, j) => (j === i ? patch : undefined));
    const again = new Set(indexes);
    update((_, i) =>
      again.has(i)
        ? { status: "queued", steps: [], result: undefined, error: undefined }
        : undefined,
    );
    await runQueue(indexes, BATCH_CONCURRENCY, signal, async (i) => {
      one(i, { status: "running" });
      try {
        const result = await runJob(list[i], signal, (steps) =>
          one(i, { steps }),
        );
        one(i, { status: "done", result });
      } catch (e) {
        one(
          i,
          signal.aborted
            ? { status: "cancelled" }
            : { status: "error", error: failureText(e) },
        );
      }
    });
    // Files the queue had not started when it was cancelled.
    if (signal.aborted)
      update((it) =>
        it.status === "queued" ? { status: "cancelled" } : undefined,
      );
    release(controller);
  };

  const submit = () => {
    if (!files.length) {
      setErrors(["Wybierz plik formularza."]);
      return;
    }
    setErrors([]);
    if (files.length === 1) return submitOne(files[0]);
    setRun((r) => r + 1);
    setSelected(undefined);
    goTo({
      step: "batch",
      items: files.map((file) => ({ file, status: "queued", steps: [] })),
    });
    return runBatch(
      files,
      files.map((_, i) => i),
    );
  };

  const cancel = () => abort.current?.abort();

  const result =
    state.step === "done"
      ? state.result
      : selected !== undefined
        ? items[selected]?.result
        : undefined;
  const checks = useChecks(result);
  const finished = items.filter((it) => it.status === "done");
  const retry = items.flatMap((it, i) =>
    it.status === "error" || it.status === "cancelled" ? [i] : [],
  );
  const findingsTotal = useMemo(
    () =>
      batchRunning
        ? 0
        : items.reduce(
            (n, it) => n + (it.result ? scanForm(it.result.form).length : 0),
            0,
          ),
    [items, batchRunning],
  );
  const downloadAll = () =>
    downloadZip(
      finished.flatMap((it) =>
        it.result ? [{ form: it.result.form, sourceName: it.file.name }] : [],
      ),
    );
  const stepLabel = (i: number) => `Krok ${i + 1}: ${steps[i]}`;
  const submitLabel = many
    ? `Utwórz formularze (${files.length})`
    : "Utwórz formularz";
  const selectedName =
    selected !== undefined ? items[selected]?.file.name : undefined;

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex flex-1 flex-col bg-page">
        <div className="px-4 py-8 sm:py-12">
          <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
            <h1 className="text-2xl font-bold leading-tight">
              Stwórz e-formularz
            </h1>
            <Stepper
              steps={steps}
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
                        errors.length > 0 && "border-destructive",
                      )}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDragging(true);
                      }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setDragging(false);
                        add([...e.dataTransfer.files]);
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
                        aria-describedby={
                          errors.length
                            ? errors.map((_, i) => `plik-err-${i}`).join(" ")
                            : undefined
                        }
                      >
                        Wybierz pliki z dysku
                      </Button>
                      <input
                        ref={input}
                        id="plik"
                        type="file"
                        multiple
                        className="sr-only"
                        tabIndex={-1}
                        accept={FORMATS.map((f) => `.${f}`).join(",")}
                        onChange={(e) => {
                          add([...(e.target.files ?? [])]);
                          e.target.value = "";
                        }}
                      />
                    </div>

                    {files.length > 0 && (
                      <ul
                        className="flex flex-col gap-2"
                        aria-label="Wybrane pliki"
                      >
                        {files.map((f, i) => (
                          <li
                            key={`${f.name}-${f.size}-${f.lastModified}`}
                            className="flex items-center gap-2 rounded-sm bg-secondary px-3 py-2 text-sm"
                          >
                            <FileText
                              className="size-4 shrink-0 text-primary"
                              aria-hidden
                            />
                            <span className="min-w-0 flex-1">
                              <FileName file={f} url={urls[i]} />
                            </span>
                            <span className="text-muted-foreground">
                              {formatSize(f.size)}
                            </span>
                            <Button
                              variant="ghost"
                              size="icon-xs"
                              aria-label={`Usuń plik ${f.name}`}
                              onClick={() => remove(i)}
                            >
                              <X className="text-primary" />
                            </Button>
                          </li>
                        ))}
                      </ul>
                    )}

                    {errors.map((e, i) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: two files may have the same name and problem
                      <FieldError key={i} id={`plik-err-${i}`} error={e} />
                    ))}

                    <InfoSection>
                      Możesz dodać kilka plików naraz (najwyżej {MAX_FILES}). Po
                      kliknięciu „{submitLabel}” każdy plik przeanalizuje model
                      sztucznej inteligencji, po {BATCH_CONCURRENCY}{" "}
                      jednocześnie. Może to potrwać kilka minut.
                    </InfoSection>
                  </FormSection>

                  <div className="flex justify-end">
                    <Button onClick={submit}>{submitLabel}</Button>
                  </div>
                </StepPanel>
              )}

              {sending && files[0] && (
                <StepPanel
                  key="tworzenie"
                  label={stepLabel(1)}
                  focus={moved.current}
                >
                  <FormSection
                    title="Generowanie formularza"
                    description={<FileName file={files[0]} url={urls[0]} />}
                  >
                    <div className="flex items-center gap-3 text-sm">
                      <LoaderCircle
                        className="size-5 shrink-0 animate-spin text-primary"
                        aria-hidden
                      />
                      <output>
                        {state.steps.length
                          ? `Trwa: ${currentStage(state.steps)}.`
                          : "Trwa tworzenie formularza."}{" "}
                        Może to potrwać kilka minut.
                        <Elapsed seconds={elapsed} />
                      </output>
                    </div>
                    <StepLog steps={state.steps} />
                  </FormSection>
                  <div className="flex justify-end">
                    <ConfirmButton
                      label="Anuluj"
                      title="Czy na pewno chcesz anulować?"
                      description="Tworzenie formularza zostanie przerwane, a dotychczasowe postępy zostaną utracone. Plik pozostanie wybrany i możesz spróbować ponownie."
                      cancel="Nie, kontynuuj"
                      confirm="Tak, anuluj"
                      onConfirm={cancel}
                    />
                  </div>
                </StepPanel>
              )}

              {state.step === "done" && files[0] && (
                <StepPanel
                  key={`wynik-${run}`}
                  label={stepLabel(2)}
                  focus={moved.current}
                >
                  <FormSection
                    title="Formularz jest gotowy"
                    description={
                      <p>
                        <span className="font-bold">
                          {state.result.form.title}
                        </span>
                        {" · "}
                        {checksText(checks)}
                      </p>
                    }
                  >
                    <InfoSection icon={<AiIcon className="mt-0.5" />}>
                      Formularz utworzył model sztucznej inteligencji. Może
                      zawierać błędy. Sprawdź go przed publikacją.
                    </InfoSection>
                    <ResultChecks result={state.result} />
                    <div className="flex flex-wrap gap-3">
                      <DownloadButton
                        findings={checks.findings.length}
                        onDownload={() =>
                          download(state.result.form, files[0].name)
                        }
                      />
                      <ConfirmButton
                        label="Przeanalizuj inny formularz"
                        title="Czy na pewno chcesz przeanalizować inny formularz?"
                        description="Utworzony formularz i jego podgląd zostaną utracone. Jeśli chcesz go zachować, najpierw pobierz JSON."
                        cancel="Nie, wróć"
                        confirm="Tak, przeanalizuj inny"
                        onConfirm={reset}
                      />
                    </div>
                  </FormSection>
                </StepPanel>
              )}

              {state.step === "batch" && (
                <StepPanel
                  key={`partia-${run}`}
                  label={stepLabel(step)}
                  focus={moved.current}
                >
                  <FormSection
                    title={
                      batchRunning
                        ? "Tworzymy formularze"
                        : finished.length
                          ? "Formularze są gotowe"
                          : "Nie udało się utworzyć formularzy"
                    }
                    description={
                      <output className="block">
                        {batchSummary(items)}
                        {batchRunning && <Elapsed seconds={elapsed} />}
                      </output>
                    }
                  >
                    {finished.length > 0 && (
                      <InfoSection icon={<AiIcon className="mt-0.5" />}>
                        Formularze utworzył model sztucznej inteligencji. Mogą
                        zawierać błędy. Sprawdź każdy przed publikacją.
                      </InfoSection>
                    )}
                    <BatchList
                      items={items}
                      urls={urls}
                      selected={selected}
                      onSelect={setSelected}
                    />
                  </FormSection>

                  {result && selectedName && (
                    <FormSection
                      title={`Sprawdź formularz: ${result.form.title}`}
                      description={
                        <p>
                          {selectedName} · {checksText(checks)}
                        </p>
                      }
                    >
                      <ResultChecks result={result} />
                    </FormSection>
                  )}

                  <div className="flex flex-wrap justify-end gap-3">
                    {batchRunning ? (
                      <ConfirmButton
                        label="Anuluj"
                        title="Czy na pewno chcesz anulować?"
                        description="Tworzenie formularzy, które jeszcze trwa lub czeka w kolejce, zostanie przerwane. Gotowe formularze zostaną zachowane."
                        cancel="Nie, kontynuuj"
                        confirm="Tak, anuluj"
                        onConfirm={cancel}
                      />
                    ) : (
                      <>
                        {retry.length > 0 && (
                          <Button
                            variant="outline"
                            onClick={() => runBatch(files, retry)}
                          >
                            Ponów nieudane ({retry.length})
                          </Button>
                        )}
                        {finished.length > 1 && (
                          <DownloadButton
                            findings={findingsTotal}
                            onDownload={downloadAll}
                          >
                            Pobierz wszystkie w ZIP ({finished.length})
                          </DownloadButton>
                        )}
                        <ConfirmButton
                          label="Przeanalizuj inne formularze"
                          title="Czy na pewno chcesz przeanalizować inne formularze?"
                          description="Utworzone formularze i ich podgląd zostaną utracone. Jeśli chcesz je zachować, najpierw pobierz pliki JSON."
                          cancel="Nie, wróć"
                          confirm="Tak, przeanalizuj inne"
                          onConfirm={reset}
                        />
                      </>
                    )}
                  </div>
                </StepPanel>
              )}
            </AnimatePresence>
          </div>
        </div>

        {result && (
          <ResultPreview key={`podglad-${run}-${selected}`} result={result} />
        )}
      </div>
    </MotionConfig>
  );
}
