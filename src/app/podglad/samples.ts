// Reference JSONs straight from materialy/ (source of truth, not copies).
import type { CoiForm } from "@/lib/form/coi";
import numerPorzadkowy from "../../../materialy/1. Wniosek o ustalenie numeru porządkowego nieruchomości - materiał referencyjny dla Uczestników do zadania/konfiguracja_form_wniosekOUstalenieNumeruPorządkowegoNieruchomości (1).json";
import nadplata from "../../../materialy/5. Wniosek o stwierdzenie nadpłaty podatku - materiał referencyjny dla Uczestników do zadania/konfiguracja_form_wniosekOStwierdzenieNadpłatyPodatkuHacknation (2).json";

export const SAMPLES: { slug: string; label: string; form: CoiForm }[] = [
  {
    slug: "numer-porzadkowy",
    label: "Wzór 1: numer porządkowy nieruchomości",
    form: numerPorzadkowy as CoiForm,
  },
  {
    slug: "nadplata-podatku",
    label: "Wzór 5: nadpłata podatku",
    form: nadplata as CoiForm,
  },
];
