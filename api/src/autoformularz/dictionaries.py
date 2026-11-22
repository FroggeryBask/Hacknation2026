"""Proposals of new dictionaries (task extension II; material "Słowniki": "zaproponuj jego nazwę, strukturę i
zastosowanie w formularzu"). The platform has Kraje, TERYT and NUMERY_KIERUNKOWE; a field that would be better
fed by a shared list than by hand-written options or free text gets a proposal here.

The COI JSON itself is not changed: a `dictionaryName` the platform does not know would import as an empty
field, so the options stay in the field and the proposal goes next to the form (`?details=true` ->
`dictionaries`, the results report and `wyniki/slowniki.json`). Rules on the field label (normalised, so
wording may vary), no model call:
- a catalogue of dictionaries recognised from the label (degree of kinship, identity document type, breeds of
  dogs considered aggressive, ways of delivery, tax offices, sports disciplines),
- any other choice field with many options (MIN_OPTIONS), named after its label.
"""

import re
from dataclasses import dataclass, field

from autoformularz.presort import fold
from autoformularz.spec import FieldSpec, FormSpec, Kind

CHOICE = {Kind.SELECT, Kind.SINGLE_CHOICE, Kind.MULTI_CHOICE}
MIN_OPTIONS = 8  # a closed list this long is a list of values, not a question with a few answers
FEW_OPTIONS = 4  # a choice with fewer options is its own question, even when its label names a known list
STRUCTURE = [  # the same shape for every proposal: like the platform's lists, a code and a display name
    {
        "name": "kod",
        "type": "string",
        "description": "Stały identyfikator pozycji (wartość zapisywana w odpowiedzi)",
    },
    {"name": "nazwa", "type": "string", "description": "Tekst widoczny na liście"},
]


@dataclass(frozen=True)
class Known:
    name: str
    title: str
    description: str
    label: re.Pattern
    entries: tuple[str, ...] = ()
    source: str = ""  # where the full list comes from when it is too long to write here
    kinds: frozenset[Kind] = frozenset({Kind.TEXT, *CHOICE})


KNOWN = [
    Known(
        "STOPIEN_POKREWIENSTWA",
        "Stopień pokrewieństwa lub powinowactwa",
        "Relacja osoby wskazanej we wniosku do wnioskodawcy.",
        re.compile(r"pokrewienst|powinowact"),
        (
            "małżonek",
            "matka",
            "ojciec",
            "córka",
            "syn",
            "pasierbica",
            "pasierb",
            "siostra",
            "brat",
            "babka",
            "dziadek",
            "wnuczka",
            "wnuk",
            "teściowa",
            "teść",
            "synowa",
            "zięć",
            "inny członek rodziny",
        ),
    ),
    Known(
        "RODZAJ_DOKUMENTU_TOZSAMOSCI",
        "Rodzaj dokumentu tożsamości",
        "Dokument potwierdzający tożsamość osoby bez numeru PESEL. Pole „Rodzaj, seria i numer dokumentu” "
        "warto rozdzielić na listę z tego słownika i pole tekstowe „Seria i numer”.",
        # "Rodzaj dokumentu", "Rodzaj, seria i numer dokumentu potwierdzającego tożsamość" (Z-15)
        re.compile(r"\brodzaj\w*\b[\w ,]{0,20}\bdokument|dokument\w* (potwierdzajac\w* )?tozsamos"),
        (
            "dowód osobisty",
            "paszport",
            "karta pobytu",
            "polski dokument tożsamości cudzoziemca",
            "inny dokument",
        ),
    ),
    Known(
        "RASY_PSOW_AGRESYWNYCH",
        "Rasy psów uznawanych za agresywne",
        "Wykaz z rozporządzenia MSWiA z 28 kwietnia 2003 r. w sprawie wykazu ras psów uznawanych za agresywne; "
        "pole „Rasa psa” na wniosku o zezwolenie na utrzymywanie takiego psa.",
        re.compile(r"\bras\w* psa\b|\bras\w* psow\b"),
        (
            "amerykański pit bull terier",
            "pies z Majorki (Perro de Presa Mallorquin)",
            "buldog amerykański",
            "dog argentyński",
            "pies kanaryjski (Perro de Presa Canario)",
            "tosa inu",
            "rottweiler",
            "akbash dog",
            "anatolian karabash",
            "moskiewski stróżujący",
            "owczarek kaukaski",
        ),
    ),
    Known(
        "SPOSOBY_DORECZENIA",
        "Sposób doręczenia korespondencji",
        "Jak urząd ma przekazać odpowiedź lub decyzję.",
        re.compile(
            r"spos\w* (korespondencji|doreczeni|odbioru)|forma (odbioru|doreczeni)|korespondencj\w* z urzed"
        ),
        ("e-Doręczenia", "skrzynka ePUAP", "poczta tradycyjna", "odbiór osobisty w urzędzie"),
    ),
    Known(
        "URZEDY_SKARBOWE",
        "Urzędy skarbowe",
        "Urząd skarbowy właściwy dla wnioskodawcy.",
        re.compile(r"urzad\w* skarbow"),
        source="Wykaz urzędów skarbowych z kodami (Ministerstwo Finansów, kody urzędów z deklaracji podatkowych).",
    ),
    Known(
        "DYSCYPLINY_SPORTOWE",
        "Dyscypliny sportowe",
        "Dyscyplina uprawiana przez sportowca.",
        re.compile(r"dyscyplin\w* sport|^dyscyplin"),
        source="Wykaz dyscyplin polskich związków sportowych (Ministerstwo Sportu); poniżej pozycje z formularza.",
        kinds=frozenset({Kind.TEXT, *CHOICE}),
    ),
]


@dataclass
class Proposal:
    name: str
    title: str
    description: str
    entries: list[str]
    source: str = ""
    usage: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "dictionaryName": self.name,
            "title": self.title,
            "description": self.description,
            "structure": STRUCTURE,
            "fieldTypes": ["SELECT", "RADIO", "CHECKBOX"],
            "entries": [{"kod": code(e), "nazwa": e} for e in self.entries],
            "source": self.source or None,
            "usage": self.usage,
        }


def code(text: str) -> str:
    """Upper-case ASCII code, as the platform's dictionary names (TERYT_4G_DOWODOWY)."""
    return re.sub(r"[^A-Z0-9]+", "_", fold(text).upper()).strip("_")[:60]


def _known(f: FieldSpec) -> Known | None:
    label = fold(f.label)
    return next((k for k in KNOWN if f.kind in k.kinds and k.label.search(label)), None)


def propose(spec: FormSpec) -> list[Proposal]:
    """Dictionaries this form would use, each once with every field it fits (page, section, field)."""
    found: dict[str, Proposal] = {}
    for page in spec.pages:
        for section in page.sections:
            for f in section.fields:
                if f.dictionary:
                    continue  # already fed by a platform dictionary
                known = _known(f)
                if known and f.kind in CHOICE and len(f.options) < FEW_OPTIONS:
                    known = None  # "Rodzaj dyscypliny: zespołowa / indywidualna" is another question
                if known:
                    p = found.setdefault(
                        known.name,
                        Proposal(
                            known.name, known.title, known.description, list(known.entries), known.source
                        ),
                    )
                elif f.kind in CHOICE and len(f.options) >= MIN_OPTIONS:
                    name = code(f.label)
                    p = found.setdefault(
                        name,
                        Proposal(name, f.label, f"Lista wartości pola „{f.label}” jako wspólny słownik.", []),
                    )
                else:
                    continue
                # A list without fixed entries (generic, or known only by its source) is filled from the form's
                # options; a fixed list keeps its own entries ("Poczta tradycyjna – adres klubu" is one form's).
                if not (known and known.entries):
                    for option in f.options:
                        if fold(option) not in {fold(e) for e in p.entries}:
                            p.entries.append(option)
                p.usage.append(
                    {
                        "page": page.title,
                        "section": section.title,
                        "field": f.label,
                        "fieldType": f.kind.value,
                        "change": (
                            f"pole listy rozwijanej z dictionaryName „{p.name}” zamiast "
                            + ("pola tekstowego" if f.kind == Kind.TEXT else "opcji wpisanych w polu")
                        ),
                    }
                )
    return list(found.values())
