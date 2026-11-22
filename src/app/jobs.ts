// Conversion jobs seen from the browser: one file through the Next route /api/forms (API jobs,
// api/src/autoformularz/jobs.py) and a queue for several files (task 3.3.VI, batch processing).
import type { CoiForm } from "@/lib/form/coi";

export type Issue = {
  level: "error" | "warning";
  code: string;
  message: string;
  path: string;
};
export type Result = {
  form: CoiForm;
  issues: Issue[];
  notes: string[];
  // `?details=true`: source blocks and the model's spec (roles mark the GDPR clause).
  document?: { blocks: { id: string; text: string }[] };
  spec?: {
    block_roles?: { block: string; to?: string | null; role: string }[];
  };
};
/** A pipeline stage, or what the model or the code found in it (api progress.py). */
export type Progress = { kind: "stage" | "item"; text: string };
type Job = {
  status: "running" | "done" | "error" | "cancelled";
  steps: Progress[];
  result?: Result;
  error?: { message: string };
};

const POLL_MS = 1500;
// Polls that may fail in a row (e.g. a restarting proxy) before the page gives up.
const POLL_RETRIES = 3;
// The API runs at most 4 jobs at once (MAX_RUNNING in jobs.py) and answers 429 BUSY beyond that:
// the file waits and is sent again instead of failing, for at most BUSY_MAX_WAIT_MS.
const BUSY_RETRY_MS = 5000;
const BUSY_MAX_WAIT_MS = 10 * 60 * 1000;
const QUEUED: Progress[] = [
  { kind: "stage", text: "Czekamy w kolejce: serwer przetwarza inne pliki" },
];

/** The stage the job is in now. */
export const currentStage = (steps: Progress[]) =>
  steps.filter((s) => s.kind === "stage").at(-1)?.text;

export const OFFLINE = "Brak połączenia z serwerem. Spróbuj ponownie.";
export const CANCELLED = "Anulowano.";

export const wait = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });

/** Message from the API (`{error: {message}}`) or FastAPI (`{detail}`). */
async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const msg = body?.error?.message ?? body?.detail;
    if (typeof msg === "string") return msg;
  } catch {}
  return `Nie udało się utworzyć formularza (błąd ${res.status}). Spróbuj ponownie.`;
}

/** What to tell the user about a failed job (runJob throws messages written for the user). */
export const failureText = (e: unknown) =>
  e instanceof Error ? e.message : OFFLINE;

/**
 * Sends one file as a job and polls its steps until it ends. Returns the result or throws an Error
 * whose message is for the user. Aborting `signal` cancels the job on the server too: the model
 * stops writing and no more tokens are paid for.
 */
export async function runJob(
  file: File,
  signal: AbortSignal,
  onSteps: (steps: Progress[]) => void,
): Promise<Result> {
  let id: string | undefined;
  const cancel = () => {
    if (id) fetch(`/api/forms/${id}`, { method: "DELETE" }).catch(() => {});
  };
  signal.addEventListener("abort", cancel);
  try {
    const since = Date.now();
    while (!id) {
      const body = new FormData();
      body.append("file", file);
      // No `signal` here: a POST cut off mid-way may still start the job on the API, and only its
      // answer gives the id to cancel it with. A cancel during the upload sends DELETE right after.
      const res = await fetch("/api/forms", { method: "POST", body }).catch(
        () => {
          throw new Error(OFFLINE);
        },
      );
      if (res.status === 429) {
        if (Date.now() - since > BUSY_MAX_WAIT_MS)
          throw new Error(
            "Serwer jest zajęty innymi plikami. Spróbuj ponownie później.",
          );
        onSteps(QUEUED);
        await wait(BUSY_RETRY_MS, signal);
        if (signal.aborted) throw new Error(CANCELLED);
        continue;
      }
      if (!res.ok) throw new Error(await errorMessage(res));
      id = ((await res.json()) as { id: string }).id;
      if (signal.aborted) {
        cancel();
        throw new Error(CANCELLED);
      }
    }
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
          throw new Error(poll ? await errorMessage(poll) : OFFLINE);
        continue;
      }
      failures = 0;
      job = (await poll.json()) as Job;
      onSteps(job.steps);
      if (job.status !== "running") break;
    }
    if (signal.aborted) throw new Error(CANCELLED);
    if (job?.status !== "done" || !job.result)
      throw new Error(
        job?.error?.message ??
          "Nie udało się utworzyć formularza. Spróbuj ponownie.",
      );
    return job.result;
  } finally {
    // A finished job needs no DELETE when the page is cancelled later.
    signal.removeEventListener("abort", cancel);
  }
}

/**
 * Runs `task(i)` for each index in order, at most `limit` at a time. Stops taking new indexes
 * once `signal` aborts; the ones not started are left to the caller. `task` must not throw.
 */
export async function runQueue(
  indexes: number[],
  limit: number,
  signal: AbortSignal,
  task: (i: number) => Promise<void>,
): Promise<void> {
  let next = 0;
  const worker = async () => {
    while (!signal.aborted && next < indexes.length)
      await task(indexes[next++]);
  };
  await Promise.all(
    Array.from({ length: Math.min(limit, indexes.length) }, worker),
  );
}
