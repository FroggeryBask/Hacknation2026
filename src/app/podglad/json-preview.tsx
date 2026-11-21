"use client";

import { FileJson } from "lucide-react";
import { useRef, useState } from "react";
import { CoiFormView } from "@/components/form/coi-form";
import { Button } from "@/components/ui/button";
import type { CoiForm } from "@/lib/form/coi";

type Sample = { slug: string; label: string; form: CoiForm };

const isCoiForm = (x: unknown): x is CoiForm =>
  !!x &&
  typeof x === "object" &&
  Array.isArray((x as CoiForm).tabs) &&
  typeof (x as CoiForm).title === "string";

export function JsonPreview({ samples }: { samples: Sample[] }) {
  const [current, setCurrent] = useState({
    key: samples[0].slug,
    form: samples[0].form,
  });
  const [error, setError] = useState<string>();
  const input = useRef<HTMLInputElement>(null);
  const loads = useRef(0);

  const load = async (file?: File) => {
    if (!file) return;
    try {
      const json = JSON.parse(await file.text());
      // Accept the plain COI JSON or the `?details=true` response ({ form, ... }).
      const form = isCoiForm(json) ? json : json?.form;
      if (!isCoiForm(form)) throw new Error();
      // New key on every load: re-loading the same file starts a fresh form.
      setCurrent({ key: `plik-${++loads.current}`, form });
      setError(undefined);
    } catch {
      setError("To nie jest plik JSON formularza (brak title lub tabs).");
    }
  };

  return (
    <div className="flex flex-1 flex-col bg-page">
      <div className="border-b bg-card px-4 py-3">
        <div className="mx-auto flex w-full max-w-2xl flex-wrap items-center gap-2">
          <span className="mr-1 text-sm font-bold">Podgląd z JSON:</span>
          {samples.map((s) => (
            <Button
              key={s.slug}
              size="sm"
              variant={current.key === s.slug ? "default" : "outline"}
              onClick={() => {
                setCurrent({ key: s.slug, form: s.form });
                setError(undefined);
              }}
            >
              {s.label}
            </Button>
          ))}
          <Button
            size="sm"
            variant="outline"
            onClick={() => input.current?.click()}
          >
            <FileJson data-icon="inline-start" aria-hidden />
            Wczytaj plik JSON
          </Button>
          <input
            ref={input}
            type="file"
            accept=".json,application/json"
            className="sr-only"
            tabIndex={-1}
            onChange={(e) => {
              load(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          {error && (
            <p role="alert" className="w-full text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
      </div>
      <CoiFormView key={current.key} form={current.form} abortHref="/podglad" />
    </div>
  );
}
