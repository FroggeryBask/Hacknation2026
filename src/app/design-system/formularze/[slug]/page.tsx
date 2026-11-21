import { notFound } from "next/navigation";
import { Suspense } from "react";
import { NadplataPodatkuForm } from "@/components/forms/nadplata-podatku";
import { NumerPorzadkowyForm } from "@/components/forms/numer-porzadkowy";
import { SwietlicaForm } from "@/components/forms/swietlica";
import { FORMS, type FormSlug } from "../forms";

const COMPONENTS: Record<FormSlug, () => React.JSX.Element> = {
  "numer-porzadkowy": NumerPorzadkowyForm,
  "nadplata-podatku": NadplataPodatkuForm,
  swietlica: SwietlicaForm,
};

export function generateStaticParams() {
  return FORMS.map((f) => ({ slug: f.slug }));
}

export async function generateMetadata({
  params,
}: PageProps<"/design-system/formularze/[slug]">) {
  const { slug } = await params;
  return { title: FORMS.find((f) => f.slug === slug)?.title };
}

async function FormBySlug({
  params,
}: Pick<PageProps<"/design-system/formularze/[slug]">, "params">) {
  const { slug } = await params;
  const Form = COMPONENTS[slug as FormSlug];
  if (!Form) notFound();
  return <Form />;
}

export default function FormPage({
  params,
}: PageProps<"/design-system/formularze/[slug]">) {
  return (
    <Suspense fallback={<div className="flex-1 bg-page" />}>
      <FormBySlug params={params} />
    </Suspense>
  );
}
