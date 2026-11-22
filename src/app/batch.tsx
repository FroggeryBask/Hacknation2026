"use client";

// Several files at once (task 3.3.VI, batch processing): one row per file with its status, and
// the preview and download of each created form.
import { cn } from "cn";
import {
  Ban,
  CircleCheck,
  CircleX,
  Clock,
  LoaderCircle,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { FileName, formatSize } from "./files";
import { currentStage, type Progress, type Result } from "./jobs";
import { checksText, DownloadButton, download, useChecks } from "./result";

export type Item = {
  file: File;
  status: "queued" | "running" | "done" | "error" | "cancelled";
  steps: Progress[];
  result?: Result;
  error?: string;
};

export const isPending = (it: Item) =>
  it.status === "queued" || it.status === "running";

function StatusIcon({
  status,
  checks: { errors, findings },
}: {
  status: Item["status"];
  checks: ReturnType<typeof useChecks>;
}) {
  const cls = "mt-0.5 size-4 shrink-0";
  switch (status) {
    case "queued":
      return <Clock className={cn(cls, "text-muted-foreground")} aria-hidden />;
    case "running":
      return (
        <LoaderCircle
          className={cn(cls, "animate-spin text-primary")}
          aria-hidden
        />
      );
    case "error":
      return <CircleX className={cn(cls, "text-destructive")} aria-hidden />;
    case "cancelled":
      return <Ban className={cn(cls, "text-muted-foreground")} aria-hidden />;
    case "done":
      if (errors.length)
        return (
          <TriangleAlert className={cn(cls, "text-destructive")} aria-hidden />
        );
      if (findings.length)
        return <ShieldAlert className={cn(cls, "text-warning")} aria-hidden />;
      return <CircleCheck className={cn(cls, "text-success")} aria-hidden />;
  }
}

function Row({
  item,
  url,
  selected,
  onSelect,
}: {
  item: Item;
  url?: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const checks = useChecks(item.result);
  const { result } = item;
  const status = {
    queued: "W kolejce",
    running: `${currentStage(item.steps) ?? "Wysyłanie pliku"}…`,
    done: result ? `${result.form.title} · ${checksText(checks)}` : "",
    error: item.error ?? "Nie udało się utworzyć formularza.",
    cancelled: "Anulowano",
  }[item.status];
  return (
    <li
      className={cn(
        "flex flex-col gap-2 rounded-sm border px-3 py-2 text-sm",
        selected && "border-primary bg-secondary",
      )}
    >
      <div className="flex items-start gap-2">
        <StatusIcon status={item.status} checks={checks} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <FileName file={item.file} url={url} />
          <span
            className={cn(
              "text-muted-foreground",
              item.status === "error" && "text-destructive",
            )}
          >
            {status}
          </span>
        </div>
        <span className="shrink-0 text-muted-foreground">
          {formatSize(item.file.size)}
        </span>
      </div>
      {result && (
        <div className="flex flex-wrap gap-2 pl-6">
          <Button
            variant={selected ? "default" : "outline"}
            size="sm"
            aria-pressed={selected}
            onClick={onSelect}
          >
            Sprawdź i podejrzyj
            <span className="sr-only"> formularz z pliku {item.file.name}</span>
          </Button>
          <DownloadButton
            variant="outline"
            size="sm"
            findings={checks.findings.length}
            onDownload={() => download(result.form, item.file.name)}
          >
            Pobierz JSON
            <span className="sr-only">
              {" "}
              formularza z pliku {item.file.name}
            </span>
          </DownloadButton>
        </div>
      )}
    </li>
  );
}

/** One row per file: status, current stage while it runs, checks and actions once done. */
export function BatchList({
  items,
  urls,
  selected,
  onSelect,
}: {
  items: Item[];
  urls: string[];
  selected?: number;
  onSelect: (i: number) => void;
}) {
  return (
    <ul className="flex flex-col gap-2" aria-label="Pliki formularzy">
      {items.map((it, i) => (
        <Row
          // biome-ignore lint/suspicious/noArrayIndexKey: the list is fixed while it is shown
          key={i}
          item={it}
          url={urls[i]}
          selected={selected === i}
          onSelect={() => onSelect(i)}
        />
      ))}
    </ul>
  );
}

/** "Gotowe: 3 z 5 · Nieudane: 1", for the section header and screen readers. */
export function batchSummary(items: Item[]) {
  const count = (s: Item["status"]) =>
    items.filter((it) => it.status === s).length;
  const failed = count("error");
  const cancelled = count("cancelled");
  return [
    `Gotowe: ${count("done")} z ${items.length}`,
    failed && `Nieudane: ${failed}`,
    cancelled && `Anulowane: ${cancelled}`,
  ]
    .filter(Boolean)
    .join(" · ");
}
