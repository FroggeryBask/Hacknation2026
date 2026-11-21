export const FORMS = [
  {
    slug: "numer-porzadkowy",
    title: "Wniosek o ustalenie numeru porządkowego nieruchomości",
    note: "Odwzorowanie referencyjnego JSON i eUsługi (materiał 1)",
  },
  {
    slug: "nadplata-podatku",
    title: "Wniosek o stwierdzenie nadpłaty podatku",
    note: "Odwzorowanie referencyjnego JSON i eUsługi (materiał 5)",
  },
  {
    slug: "swietlica",
    title: "Wniosek o wynajęcie lub użyczenie świetlicy wiejskiej",
    note: "Zaprojektowany z formularza papierowego wg standardu (materiał 4)",
  },
] as const;

export type FormSlug = (typeof FORMS)[number]["slug"];
