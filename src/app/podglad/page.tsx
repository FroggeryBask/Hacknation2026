import { JsonPreview } from "./json-preview";
import { SAMPLES } from "./samples";

export const metadata = { title: "Podgląd formularza z JSON" };

export default function PodgladPage() {
  return <JsonPreview samples={SAMPLES} />;
}
