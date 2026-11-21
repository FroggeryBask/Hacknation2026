"use client";

import { cn } from "cn";
import { Check, Plus, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { type ReactNode, useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormProvider, useForm, useFormApi } from "./form-context";

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

/* ------------------------------------------------------------------ */
/* Stepper (page navigation)                                           */
/* ------------------------------------------------------------------ */

export function Stepper({
  steps,
  current,
  label = "Kroki formularza",
}: {
  steps: string[];
  current: number;
  label?: string;
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
          return (
            <li
              key={s}
              aria-current={active ? "step" : undefined}
              className="flex min-w-0 flex-1 flex-col gap-2"
            >
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
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* Bottom navigation: Przerwij wypełnianie | Wstecz | Dalej            */
/* ------------------------------------------------------------------ */

export function FormNav({
  onBack,
  onNext,
  nextLabel = "Dalej",
  abortHref = "/design-system",
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  abortHref?: string;
}) {
  return (
    <div className="flex flex-wrap-reverse items-center justify-between gap-3 pt-2">
      <Link href={abortHref} className={buttonVariants({ variant: "link" })}>
        Przerwij wypełnianie
      </Link>
      <div className="flex gap-3">
        {onBack && (
          <Button variant="outline" onClick={onBack}>
            Wstecz
          </Button>
        )}
        <Button onClick={onNext}>{nextLabel}</Button>
      </div>
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
  abortHref,
}: {
  title: string;
  pages: FormPage[];
  submitLabel: string;
  abortHref?: string;
}) {
  const form = useFormApi();
  const [page, setPage] = useState(0);
  const [sent, setSent] = useState(false);
  const last = page === pages.length - 1;

  const go = (to: number) => {
    setPage(to);
    window.scrollTo({ top: 0, behavior: "smooth" });
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
      <Stepper steps={pages.map((p) => p.title)} current={page} />
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.div
          key={page}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
          transition={{ duration: 0.2 }}
          className="flex flex-col gap-4"
        >
          <AnimatePresence initial={false}>
            {pages[page].content}
          </AnimatePresence>
        </motion.div>
      </AnimatePresence>
      <FormNav
        abortHref={abortHref}
        onBack={page > 0 ? () => go(page - 1) : undefined}
        nextLabel={last ? submitLabel : "Dalej"}
        onNext={() => {
          if (!form.validate()) return;
          if (last) setSent(true);
          else go(page + 1);
        }}
      />
    </form>
  );
}

export function FormShell({
  title,
  pages,
  submitLabel = "Przejdź do podpisu",
  initialValues,
  abortHref,
}: {
  title: string;
  pages: FormPage[];
  submitLabel?: string;
  initialValues?: Parameters<typeof useForm>[0];
  abortHref?: string;
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
            abortHref={abortHref}
          />
        </FormProvider>
      </div>
    </div>
  );
}
