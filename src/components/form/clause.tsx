"use client";

import { ExternalLink } from "lucide-react";
import { createContext, type ReactNode, useContext } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

/*
 * The consent links to the information clause (design standard: "zapewnić
 * dostęp do pełnej treści klauzuli informacyjnej", never on the form itself).
 * The compiler cannot know the office's BIP address, so the JSON has the
 * anchor "#klauzula-informacyjna". In the preview the link opens the clause
 * read from the uploaded document (its GDPR blocks); without a document it
 * says where the office publishes it.
 */

/** Lines of the information clause from the source document, if known. */
export const ClauseContext = createContext<string[] | null>(null);

export const isClauseLink = (href: string) => /^#klauzul/i.test(href);

export function ClauseLink({ children }: { children: ReactNode }) {
  const lines = useContext(ClauseContext);
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <button
            type="button"
            className="inline-flex cursor-pointer items-baseline gap-1 rounded-xs font-bold text-link underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        }
      >
        {children}
        <ExternalLink className="size-3.5 self-center" aria-hidden />
        <span className="sr-only">(otwiera okno z treścią klauzuli)</span>
      </AlertDialogTrigger>
      <AlertDialogContent className="max-h-[85vh] sm:max-w-2xl">
        <AlertDialogHeader>
          <AlertDialogTitle>Klauzula informacyjna</AlertDialogTitle>
          <AlertDialogDescription>
            {lines?.length
              ? "Treść z dokumentu źródłowego. W e-usłudze odnośnik prowadzi do klauzuli opublikowanej przez urząd (np. w BIP)."
              : "W e-usłudze odnośnik prowadzi do klauzuli opublikowanej przez urząd (np. w BIP). Dokument źródłowy nie zawierał jej treści."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {!!lines?.length && (
          <div className="flex max-h-[55vh] flex-col gap-1.5 overflow-y-auto rounded-sm border bg-card p-4 text-sm leading-relaxed">
            {lines.map((line, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: static text, lines may repeat
              <p key={i}>{line}</p>
            ))}
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>Zamknij</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

type Block = { id: string; text: string };
type BlockRole = { block: string; to?: string | null; role: string };

const number = (id: string) => (/^b\d+$/.test(id) ? Number(id.slice(1)) : NaN);

/** The clause's lines: blocks the API marked GDPR (`block`..`to` ranges). */
export function clauseLines(
  blocks: Block[] | undefined,
  roles: BlockRole[] | undefined,
): string[] {
  if (!blocks?.length || !roles?.length) return [];
  const ranges = roles
    .filter((r) => r.role === "GDPR")
    .map((r) => [number(r.block), number(r.to ?? r.block)] as const);
  return blocks
    .filter((b) => {
      const n = number(b.id);
      return ranges.some(([from, to]) => n >= from && n <= to);
    })
    .map((b) => b.text.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}
