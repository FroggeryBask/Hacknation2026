"use client";

import { cn } from "cn";
import { Check, Plus, Trash2, TriangleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { FormProvider, focusField, useForm, useFormApi } from "./form-context";

/* ------------------------------------------------------------------ */
/* SECTION: white card with title and optional description             */
/* ------------------------------------------------------------------ */

export function FormSection({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.section
      layout="position"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className={cn(
        "flex flex-col gap-5 rounded-lg bg-card p-5 shadow-[0_1px_3px_rgb(15_40_80/0.08)] sm:p-6",
        className,
      )}
    >
      <header className="flex flex-col gap-2">
        <h2 className="text-lg font-bold leading-snug">{title}</h2>
        {description && (
          <div className="text-sm leading-relaxed [&_p+p]:mt-1">
            {description}
          </div>
        )}
      </header>
      {children}
    </motion.section>
  );
}

/* ------------------------------------------------------------------ */
/* REPEATING_SECTION: same fields for many people / plots / vehicles   */
/* ------------------------------------------------------------------ */

export function RepeatingSection({
  name,
  title,
  itemTitle,
  description,
  addLabel = "Dodaj kolejną pozycję",
  max = 10,
  children,
}: {
  name: string;
  title: string;
  itemTitle: (index: number) => string;
  description?: ReactNode;
  addLabel?: string;
  max?: number;
  /** Render fields for item `index`; prefix field names with `${name}[${index}]`. */
  children: (prefix: string, index: number) => ReactNode;
}) {
  const [keys, setKeys] = useState([0]);
  const [next, setNext] = useState(1);
  return (
    <FormSection title={title} description={description}>
      {keys.map((k, i) => (
        <fieldset
          key={k}
          className="flex flex-col gap-5 border-t pt-5 first-of-type:border-t-0 first-of-type:pt-0"
        >
          <div className="flex items-center justify-between gap-2">
            <legend className="font-bold">{itemTitle(i)}</legend>
            {keys.length > 1 && (
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive"
                onClick={() => setKeys(keys.filter((x) => x !== k))}
              >
                <Trash2 data-icon="inline-start" aria-hidden />
                Usuń
              </Button>
            )}
          </div>
          {children(`${name}[${k}]`, i)}
        </fieldset>
      ))}
      {keys.length < max && (
        <Button
          variant="outline"
          className="self-start"
          onClick={() => {
            setKeys([...keys, next]);
            setNext(next + 1);
          }}
        >
          <Plus data-icon="inline-start" aria-hidden />
          {addLabel}
        </Button>
      )}
    </FormSection>
  );
}

/**
 * Navigation buttons keep the focus where it is on mouse down. Otherwise the
 * field being left checks itself (an error message appears, the character
 * counter goes) and the page shifts between mouse down and up, so the click
 * lands next to the button and is lost. The click still runs: "Dalej" checks
 * the whole page anyway. Keyboard use is unchanged.
 */
const keepFocus = (e: React.MouseEvent) => e.preventDefault();

/* ------------------------------------------------------------------ */
/* Stepper (page navigation)                                           */
/* ------------------------------------------------------------------ */

export function Stepper({
  steps,
  current,
  label = "Kroki formularza",
  onSelect,
  canSelect,
}: {
  steps: string[];
  current: number;
  label?: string;
  /** Makes steps buttons that open them. */
  onSelect?: (index: number) => void;
  /** Which steps can be opened (default: all); the others stay plain text. */
  canSelect?: (index: number) => boolean;
}) {
  return (
    <nav aria-label={label}>
      <p className="mb-2 text-sm text-muted-foreground sm:hidden">
        Krok {current + 1} z {steps.length}: {steps[current]}
      </p>
      <ol className="flex gap-1.5 sm:gap-2">
        {steps.map((s, i) => {
          const done = i < current;
          const active = i === current;
          const body = (
            <>
              <span
                className={cn(
                  "h-1 rounded-full bg-border",
                  (done || active) && "bg-primary",
                )}
              />
              <span
                className={cn(
                  "hidden items-start gap-1.5 text-xs leading-snug sm:flex",
                  active
                    ? "font-bold text-foreground"
                    : "text-muted-foreground",
                )}
              >
                {done ? (
                  <Check
                    className="size-3.5 shrink-0 text-primary"
                    aria-hidden
                  />
                ) : (
                  <span aria-hidden>{i + 1}.</span>
                )}
                {/* Wrap, don't truncate: cut-off step names hide information. */}
                <span className="min-w-0 break-words">{s}</span>
                {done && <span className="sr-only">(ukończony)</span>}
              </span>
            </>
          );
          return (
            <li
              key={s}
              aria-current={active ? "step" : undefined}
              className="flex min-w-0 flex-1"
            >
              {onSelect && (canSelect?.(i) ?? true) ? (
                <button
                  type="button"
                  onMouseDown={keepFocus}
                  onClick={() => onSelect(i)}
                  aria-label={`Krok ${i + 1}: ${s}`}
                  className="group flex min-w-0 flex-1 cursor-pointer flex-col gap-2 rounded-xs pb-1 text-left outline-none hover:[&>span:last-child]:underline focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {body}
                </button>
              ) : (
                <div className="flex min-w-0 flex-1 flex-col gap-2">{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* Bottom navigation: Wstecz | Dalej                                  */
/* ------------------------------------------------------------------ */

export function FormNav({
  onBack,
  onNext,
  nextLabel = "Dalej",
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
}) {
  return (
    <div className="flex items-center justify-end gap-3 pt-2">
      <div className="flex gap-3">
        {onBack && (
          <Button variant="outline" onMouseDown={keepFocus} onClick={onBack}>
            Wstecz
          </Button>
        )}
        <Button onMouseDown={keepFocus} onClick={onNext}>
          {nextLabel}
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Error summary after a page check (pattern of gov.pl / GOV.UK forms) */
/* ------------------------------------------------------------------ */

/** The visible label of a field, without the "(opcjonalnie)" suffix. */
function fieldLabel(name: string): string {
  const el = document.querySelector(`[data-field="${CSS.escape(name)}"]`);
  const text = el?.querySelector("label, legend")?.textContent?.trim();
  return text?.replace(/\s*\(opcjonalnie\)$/, "") || name;
}

/** Field names in the order they appear on the page. */
function inPageOrder(names: string[]): string[] {
  const at = (n: string) =>
    document.querySelector(`[data-field="${CSS.escape(n)}"]`);
  return [...names].sort((a, b) => {
    const x = at(a);
    const y = at(b);
    if (!x || !y) return 0;
    return x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING
      ? -1
      : 1;
  });
}

/**
 * Shown when "Dalej" finds errors: a list with links to the fields (focus
 * moves here, so screen readers read it). Follows the live errors: fixing a
 * field removes its line, and when all are fixed it says so.
 */
export function ErrorSummary({ errors }: { errors: Record<string, string> }) {
  const box = useRef<HTMLElement | null>(null);
  const keep = (el: HTMLElement | null) => {
    box.current = el;
  };
  const names = inPageOrder(Object.keys(errors));
  const count = names.length;
  // Focus once, when the summary appears (each check mounts a new one).
  useEffect(() => {
    box.current?.focus();
    box.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, []);

  if (!count) {
    return (
      <output
        ref={keep}
        tabIndex={-1}
        className="flex items-start gap-2 rounded-lg border border-success bg-card p-4 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
        Wszystkie błędy na tej stronie są poprawione. Możesz przejść dalej.
      </output>
    );
  }
  return (
    <div
      ref={keep}
      tabIndex={-1}
      role="alert"
      aria-labelledby="error-summary-title"
      className="flex flex-col gap-2 rounded-lg border-2 border-destructive bg-card p-4 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <h2
        id="error-summary-title"
        className="flex items-center gap-2 font-bold text-destructive"
      >
        <TriangleAlert className="size-4 shrink-0" aria-hidden />
        {count === 1
          ? "Popraw 1 błąd na tej stronie"
          : `Popraw błędy na tej stronie: ${count}`}
      </h2>
      <ul className="flex flex-col gap-1 text-sm">
        {names.map((name) => (
          <li key={name}>
            <button
              type="button"
              onClick={() => focusField(name)}
              className="cursor-pointer text-left text-primary underline underline-offset-2 outline-none hover:no-underline focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {fieldLabel(name)}: {errors[name]}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Form shell: title + stepper + pages (tabs MAIN... + FINISH)         */
/* ------------------------------------------------------------------ */

export type FormPage = {
  /** Tab title from the JSON config. */
  title: string;
  type: "MAIN" | "FINISH";
  content: ReactNode;
};

function PagedForm({
  title,
  pages,
  submitLabel,
  freeNavigation,
}: {
  title: string;
  pages: FormPage[];
  submitLabel: string;
  freeNavigation?: boolean;
}) {
  const form = useFormApi();
  const [page, setPage] = useState(0);
  const [sent, setSent] = useState(false);
  // Failed "Dalej" checks on this page (each one shows the summary again).
  const [checks, setChecks] = useState(0);
  // Furthest page reached with "Dalej": the stepper opens only pages up to it,
  // so a page can't be skipped before the ones before it are correct.
  const [reached, setReached] = useState(0);
  const last = page === pages.length - 1;

  const go = (to: number) => {
    setPage(to);
    setChecks(0);
    // Preview: errors of the page left behind are not shown on the next one.
    if (freeNavigation) form.clearErrors();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  /** Like the e-service: "Dalej" stays on the page while it has errors. */
  const next = () => {
    if (form.check().length) {
      setChecks((n) => n + 1);
      return;
    }
    if (last) setSent(true);
    else {
      setReached((r) => Math.max(r, page + 1));
      go(page + 1);
    }
  };

  if (sent) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-lg bg-card p-8 text-center">
        <span className="grid size-12 place-items-center rounded-full bg-success text-success-foreground">
          <Check className="size-6" aria-hidden />
        </span>
        <h2 className="text-xl font-bold">Wniosek jest gotowy do podpisu</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          To wersja demonstracyjna. W eUsłudze w tym miejscu wybierasz sposób
          podpisu i wysyłasz wniosek do urzędu.
        </p>
        <Button
          variant="outline"
          onClick={() => {
            setSent(false);
            go(0);
          }}
        >
          Wróć do początku
        </Button>
      </div>
    );
  }

  return (
    <form
      noValidate
      onSubmit={(e) => e.preventDefault()}
      className="flex flex-col gap-4"
      aria-labelledby="form-title"
    >
      <h1 id="form-title" className="text-2xl font-bold leading-tight">
        {title}
      </h1>
      <Stepper
        steps={pages.map((p) => p.title)}
        current={page}
        onSelect={freeNavigation ? go : undefined}
        canSelect={(i) => i <= reached}
      />
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.div
          key={page}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
          transition={{ duration: 0.2 }}
          className="flex flex-col gap-4"
        >
          {checks > 0 && <ErrorSummary key={checks} errors={form.errors} />}
          <AnimatePresence initial={false}>
            {pages[page].content}
          </AnimatePresence>
        </motion.div>
      </AnimatePresence>
      <FormNav
        onBack={page > 0 ? () => go(page - 1) : undefined}
        nextLabel={last ? submitLabel : "Dalej"}
        onNext={next}
      />
    </form>
  );
}

export function FormShell({
  title,
  pages,
  submitLabel = "Przejdź do podpisu",
  initialValues,
  freeNavigation,
}: {
  title: string;
  pages: FormPage[];
  submitLabel?: string;
  initialValues?: Parameters<typeof useForm>[0];
  /** The stepper opens pages already reached (back and forth); "Dalej" checks the page first. */
  freeNavigation?: boolean;
}) {
  const form = useForm(initialValues);
  return (
    <div className="min-h-full flex-1 bg-page px-4 py-8 sm:py-12">
      <div className="mx-auto w-full max-w-2xl">
        <FormProvider form={form}>
          <PagedForm
            title={title}
            pages={pages}
            submitLabel={submitLabel}
            freeNavigation={freeNavigation}
          />
        </FormProvider>
      </div>
    </div>
  );
}
