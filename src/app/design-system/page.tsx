import { ArrowRight, Download, Plus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { FieldDemos } from "./field-demos";
import { FORMS } from "./formularze/forms";

export const metadata = { title: "Design system – Cyfryzacja formularzy" };

const COLORS = [
  ["page", "bg-page", "Tło strony"],
  ["card", "bg-card", "Karta sekcji"],
  ["primary", "bg-primary", "Akcje, focus, linki"],
  ["secondary", "bg-secondary", "Tło akcentu"],
  ["foreground", "bg-foreground", "Tekst"],
  ["muted-foreground", "bg-muted-foreground", "Tekst pomocniczy"],
  ["input", "bg-input", "Obramowanie pól"],
  ["readonly", "bg-readonly", "Pole tylko do odczytu"],
  ["border", "bg-border", "Linie, separatory"],
  ["destructive", "bg-destructive", "Błędy"],
  ["success", "bg-success", "Sukces"],
  ["info", "bg-info", "Sekcja informacyjna"],
] as const;

function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="mt-6 text-xl font-bold">{children}</h2>;
}

export default function DesignSystemPage() {
  return (
    <main className="flex-1 bg-page px-4 py-8 sm:py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
        <header className="flex flex-col gap-2">
          <p className="text-sm font-bold text-primary">Design system</p>
          <h1 className="text-3xl font-bold leading-tight">
            Formularze eUsług
          </h1>
          <p className="text-muted-foreground">
            Tokeny, przyciski, pola i struktura formularza zgodne ze standardem
            projektowania formularzy z materiałów zadania (WCAG 2.1 AA, układ
            jednokolumnowy, sekcje tematyczne). Opis zasad:{" "}
            <code className="font-mono text-sm">docs/design-system.md</code>.
          </p>
        </header>

        <H2>Organizmy: przykładowe formularze</H2>
        <ul className="flex flex-col gap-3">
          {FORMS.map((f) => (
            <li key={f.slug}>
              <Link
                href={`/design-system/formularze/${f.slug}`}
                className="group flex items-center gap-4 rounded-lg bg-card p-5 shadow-[0_1px_3px_rgb(15_40_80/0.08)] outline-none transition-shadow hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <div className="flex flex-1 flex-col gap-1">
                  <span className="font-bold text-link group-hover:underline">
                    {f.title}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {f.note}
                  </span>
                </div>
                <ArrowRight className="size-5 text-primary" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>

        <H2>Kolory (tokeny)</H2>
        <div className="grid grid-cols-2 gap-3 rounded-lg bg-card p-5 sm:grid-cols-3">
          {COLORS.map(([token, cls, use]) => (
            <div key={token} className="flex items-center gap-3">
              <span
                className={`size-10 shrink-0 rounded-sm ring-1 ring-foreground/10 ${cls}`}
              />
              <span className="flex min-w-0 flex-col">
                <code className="truncate font-mono text-xs">{token}</code>
                <span className="text-xs text-muted-foreground">{use}</span>
              </span>
            </div>
          ))}
        </div>

        <H2>Typografia</H2>
        <div className="flex flex-col gap-3 rounded-lg bg-card p-5">
          <p className="text-2xl font-bold">Tytuł formularza · 24 bold</p>
          <p className="text-lg font-bold">Tytuł sekcji · 18 bold</p>
          <p className="text-base">Treść, etykiety pól · 16 regular</p>
          <p className="text-sm text-muted-foreground">
            Opis pola, tekst pomocniczy · 14 regular
          </p>
          <p className="text-xs text-muted-foreground">
            Lato (krój gov.pl), z polskimi znakami: zażółć gęślą jaźń
          </p>
        </div>

        <H2>Przyciski</H2>
        <div className="flex flex-col gap-4 rounded-lg bg-card p-5">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Dalej</Button>
            <Button variant="outline">Wstecz</Button>
            <Button variant="link">Przerwij wypełnianie</Button>
            <Button disabled>Niedostępny</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg">Przejdź do podpisu</Button>
            <Button variant="outline">
              <Plus data-icon="inline-start" aria-hidden />
              Dodaj kolejną pozycję
            </Button>
            <Button variant="secondary">
              <Download data-icon="inline-start" aria-hidden />
              Pobierz JSON
            </Button>
            <Button size="sm" variant="ghost">
              Mały
            </Button>
          </div>
          <ul className="list-disc pl-5 text-sm text-muted-foreground">
            <li>
              Jedna akcja główna (<strong>primary</strong>) na ekran: „Dalej”,
              „Wyślij wniosek”.
            </li>
            <li>
              <strong>outline</strong>: akcje wtórne („Wstecz”, „Dodaj plik”).
            </li>
            <li>
              <strong>link</strong>: wyjście z procesu („Przerwij wypełnianie”).
            </li>
          </ul>
        </div>

        <FieldDemos />
      </div>
    </main>
  );
}
