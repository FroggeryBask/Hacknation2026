"use client";

import { Check, Copy } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";

// One JSON token: a string (a key when ":" follows), a literal or a number.
const TOKEN =
  /("(?:\\u[0-9a-fA-F]{4}|\\[^u]|[^\\"])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;

/** JSON text with keys, strings and literals in design-system colours. */
function highlight(json: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of json.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) out.push(json.slice(last, at));
    const [token, str, colon, literal] = m;
    const cls = str
      ? colon
        ? "text-primary"
        : "text-success"
      : literal
        ? "text-destructive"
        : "text-link";
    out.push(
      <span key={at} className={cls}>
        {str ?? token}
      </span>,
    );
    if (colon) out.push(colon);
    last = at + token.length;
  }
  out.push(json.slice(last));
  return out;
}

/**
 * The generated JSON as it will be imported ("przeglądanie wyjściowej
 * struktury danych (jsona)", task 3.3.IV): formatted, coloured, with copy.
 */
export function JsonView({ data }: { data: unknown }) {
  const text = useMemo(() => JSON.stringify(data, null, 2), [data]);
  const parts = useMemo(() => highlight(text), [text]);
  const [copied, setCopied] = useState(false);
  const lines = text.split("\n").length;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>
          Linie: {lines} · Rozmiar:{" "}
          {Math.max(1, Math.round(text.length / 1024))} KB
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? (
            <Check data-icon="inline-start" aria-hidden />
          ) : (
            <Copy data-icon="inline-start" aria-hidden />
          )}
          {copied ? "Skopiowano" : "Kopiuj JSON"}
        </Button>
      </div>
      <section aria-label="Wygenerowany JSON">
        <pre
          // A scrollable region must be reachable by keyboard (WCAG 2.1.1).
          // biome-ignore lint/a11y/noNoninteractiveTabindex: scroll container
          tabIndex={0}
          className="max-h-[70vh] overflow-auto rounded-lg border bg-card p-4 font-mono text-xs leading-relaxed outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <code>{parts}</code>
        </pre>
      </section>
    </div>
  );
}
