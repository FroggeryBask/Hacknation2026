"""Check step (docs/pipeline.md, step 4): does the FormSpec stay true to the Document?

Coverage counts and canon (`dedupe`: repeated pages, sections, fields; `drop_standard_sections`: copies of
the predefined applicant/proxy/contact part). Later: dropping fields whose anchors do not exist, a retry
for blocks without a role, TEXT_BLOCK fallback, type normalisation."""

import re
from dataclasses import asdict, dataclass, field

from autoformularz.document import Document
from autoformularz.spec import Condition, FieldSpec, FormSpec, Kind, Role


@dataclass
class Coverage:
    blocks: int = 0  # all text blocks in the source
    referenced: int = 0  # blocks the spec points to (fields, sections, roles)
    unreferenced: list[str] = field(default_factory=list)  # block IDs nobody points to: text may be lost
    candidates: int = 0  # spots to fill in found in the source
    candidates_without_field: list[str] = field(default_factory=list)  # their blocks have no field or SKIP
    unknown_refs: list[str] = field(default_factory=list)  # IDs in the spec that are not in the source

    def as_dict(self) -> dict:
        d = asdict(self)
        return {
            "blocks": d["blocks"],
            "referenced": d["referenced"],
            "unreferenced": d["unreferenced"],
            "candidates": d["candidates"],
            "candidatesWithoutField": d["candidates_without_field"],
            "unknownRefs": d["unknown_refs"],
        }


def coverage(spec: FormSpec, doc: Document) -> Coverage:
    ids = [b.id for b in doc.blocks]
    known = set(ids)
    refs = spec.referenced_blocks()
    in_fields = {r for p in spec.pages for s in p.sections for f in s.fields for r in f.blocks}
    skipped = {block for block, role in spec.roles().items() if role is Role.SKIP}
    handled = in_fields | skipped
    without_field = list(dict.fromkeys(c.block for c in doc.candidates if c.block not in handled))
    return Coverage(
        blocks=len(ids),
        referenced=len(refs & known),
        unreferenced=[i for i in ids if i not in refs],
        candidates=len(doc.candidates),
        candidates_without_field=without_field,
        unknown_refs=sorted(refs - known, key=lambda i: (len(i), i)),
    )


def dedupe(spec: FormSpec) -> tuple[FormSpec, list[str]]:
    """Canon, first rule: drop what a model repeated (a repetition loop writes the same page, section or
    field again and again). Deterministic, keeps the first occurrence and the order:
    - a page with the same title and the same content as an earlier page,
    - a section with the same title and field labels as an earlier section (anywhere in the form),
    - a field with the same label as an earlier field in its section, unless it points to other source
      blocks (another row of a table).
    Returns a new spec and notes about what was dropped."""
    notes: list[str] = []
    seen_pages: set[str] = set()
    seen_sections: set[tuple[str, tuple[str, ...]]] = set()
    pages = []
    for page in spec.pages:
        key = page.model_dump_json()
        if key in seen_pages:
            notes.append(f"Pominięto powtórzoną stronę „{page.title}”.")
            continue
        seen_pages.add(key)
        sections = []
        for section in page.sections:
            labels: list[str] = []
            fields = []
            used: dict[str, set[str]] = {}  # label -> blocks of the fields kept with it
            for f in section.fields:
                # Same label, but other source blocks: another row of a table ("Wysokość opłaty" for each
                # flat size in material 8), not a repetition.
                new_row = f.label in used and f.blocks and not used[f.label] & set(f.blocks)
                if f.label in used and not new_row:
                    notes.append(f"Pominięto powtórzone pole „{f.label}” w sekcji „{section.title}”.")
                    continue
                used.setdefault(f.label, set()).update(f.blocks)
                labels.append(f.label)
                fields.append(f)
            skey = (section.title, tuple(labels))
            if skey in seen_sections:
                notes.append(f"Pominięto powtórzoną sekcję „{section.title}”.")
                continue
            seen_sections.add(skey)
            sections.append(section.model_copy(update={"fields": fields}))
        if sections:
            pages.append(page.model_copy(update={"sections": sections}))
        else:
            notes.append(f"Pominięto stronę „{page.title}” (same powtórzenia).")
    return spec.model_copy(update={"pages": pages}), notes


# The predefined part (applicant, proxy, contact) is always added by the compiler from the design standard.
# A model sometimes copies it from the paper form anyway; it would then appear twice. A section is such a
# copy only when BOTH its title (or its page title) is about the applicant/proxy/contact AND its fields are
# personal, address or contact data or paper-only items. "Oświadczenia wnioskodawcy" (statements) or
# "Miejsce utrzymywania psa" (subject data) stay. A contact section counts only under a generic title:
# "Osoba do kontaktu w sprawie najmu" is subject data, not the applicant's contact.
STANDARD_TITLE = re.compile(
    r"wnioskodawc|pełnomocni|składając|^\s*(dane kontaktowe|dane do kontaktu|kontakt)\s*$"
    r"|^\s*adres (zamieszkania|siedziby)(\s*/\s*(zamieszkania|siedziby))?\s*$",
    re.IGNORECASE,
)
STANDARD_LABEL = re.compile(
    r"^(imię|imiona|nazwisko|imię i nazwisko|nazwisko imię|nazwisko i imię|nazwa|nazwa firmy|nazwa pełna|"
    r"pełna nazwa|pesel|nip|regon|krs|numer krs|"
    r"seria i numer dowodu.*|numer dowodu.*|obywatelstwo|"
    r"adres|adres zamieszkania|adres siedziby|adres do korespondencji|"
    r"miejscowość|ulica|nr domu|numer domu|numer nieruchomości|nr lokalu|numer lokalu|kod pocztowy|poczta|"
    r"gmina|powiat|województwo|kraj|telefon|nr telefonu|numer telefonu|telefon kontaktowy|nr tel|nr fax|"
    r"fax|e-mail|adres e-mail|email|"
    r"adres poczty elektronicznej|adres skrzynki epuap|podpis|data|miejscowość i data|data i podpis)$"
)
STANDARD_SHARE = 0.8
PARTIAL_SHARE = 0.5


def _norm(label: str) -> str:
    """Lowercase, brackets and punctuation removed, spaces collapsed."""
    text = re.sub(r"[()\[\]:;.,*]", " ", label.lower())
    return " ".join(text.split())


def is_standard_label(label: str) -> bool:
    """Personal, address or contact data, or a paper-only item. Alternatives count when every part is
    standard: "Imię i nazwisko lub nazwa firmy", "Adres zamieszkania/siedziby"."""
    parts = [p.strip() for p in re.split(r"/| lub | albo ", _norm(label)) if p.strip()]
    # A short alternative borrows the first word: "adres zamieszkania/siedziby" -> "adres siedziby".
    expanded: list[str] = []
    for part in parts:
        short = expanded and not STANDARD_LABEL.match(part)
        expanded.append(f"{expanded[0].split()[0]} {part}" if short else part)
    return bool(parts) and all(STANDARD_LABEL.match(p) for p in expanded)


def _about_applicant(section, page_title: str) -> bool:
    return bool(STANDARD_TITLE.search(section.title) or STANDARD_TITLE.search(page_title))


def _standard_share(section) -> float:
    return (
        sum(is_standard_label(f.label) for f in section.fields) / len(section.fields) if section.fields else 0
    )


def _is_standard(section, page_title: str) -> bool:
    return _about_applicant(section, page_title) and _standard_share(section) >= STANDARD_SHARE


def _is_mostly_standard(section) -> bool:
    """Its OWN title is about the applicant and at least half of its fields are standard: the other fields
    are extra questions about the applicant. A proxy section with one ID number among other data, or a
    club's data on an applicant page, stays whole (cutting a field there leaves half a person)."""
    return bool(STANDARD_TITLE.search(section.title)) and _standard_share(section) >= PARTIAL_SHARE


ENTITY_ID = re.compile(r"\b(NIP|REGON|KRS)\b")


def drop_standard_sections(spec: FormSpec) -> tuple[FormSpec, list[str]]:
    """Canon, second rule: copies of the predefined applicant/proxy/contact part are left to the compiler
    (see `_is_standard`). Deterministic; a page left empty is dropped too. A section about the applicant
    that also asks something else ("Składający deklarację: właściciel / najemca / …" next to name and PESEL)
    keeps only the other fields.

    What they asked for still matters: NIP/REGON/KRS among the applicant's fields means the applicant may be
    a company or institution, so `applicant.entity` is set (and `entity_nip_only` when only NIP is asked,
    like reference form 5), whatever the model said."""
    notes: list[str] = []
    pages = []
    dropped_labels: list[str] = []
    for page in spec.pages:
        sections = []
        for section in page.sections:
            if not (_is_standard(section, page.title) or _is_mostly_standard(section)):
                sections.append(section)
                continue
            standard = [f.label for f in section.fields if is_standard_label(f.label)]
            keep = [f for f in section.fields if not is_standard_label(f.label)]
            dropped_labels += standard
            if keep:  # e.g. "Numer działki" next to the applicant's address (material 8)
                notes.append(
                    f"Z sekcji „{section.title}” pominięto pola z części standardowej: {', '.join(standard)}."
                )
                sections.append(section.model_copy(update={"fields": keep}))
            else:
                notes.append(f"Sekcja „{section.title}” jest w części standardowej formularza (pominięta).")
        if sections:
            pages.append(page.model_copy(update={"sections": sections}))
    update: dict = {"pages": pages}
    ids = {m.group(1) for label in dropped_labels for m in ENTITY_ID.finditer(label)}
    if ids and not spec.applicant.entity:
        nip_only = ids == {"NIP"}
        update["applicant"] = spec.applicant.model_copy(update={"entity": True, "entity_nip_only": nip_only})
        notes.append(
            f"Formularz pyta o {', '.join(sorted(ids))} wnioskodawcy: wnioskodawcą może być firma lub instytucja."
        )
    return spec.model_copy(update=update), notes


def _key(text: str) -> str:
    """How the compiler matches condition targets: case and spacing ignored."""
    return " ".join(text.split()).lower()


def drop_broken_conditions(spec: FormSpec) -> tuple[FormSpec, list[str]]:
    """Canon, third rule (after the others, which may drop fields): a `show_if` pointing to a field that is
    not in the spec, or to an option that field does not have, would never work. The condition is removed
    and the fields it guarded become optional: shown always, but never blocking the form (material 8:
    "Adres do korespondencji" pointed to a missing field and was required for everyone)."""
    options = {
        _key(f.label): [_key(o) for o in f.options] for p in spec.pages for s in p.sections for f in s.fields
    }
    notes: list[str] = []

    def broken(c: Condition | None, where: str) -> bool:
        if c is None:
            return False
        opts = options.get(_key(c.field))
        if opts is None:
            notes.append(
                f"„{where}”: warunek na nieistniejącym polu „{c.field}” usunięty, pola nieobowiązkowe."
            )
            return True
        if opts and _key(c.equals) not in opts:
            notes.append(
                f"„{where}”: warunek na nieistniejącej opcji „{c.equals}” usunięty, pola nieobowiązkowe."
            )
            return True
        return False

    def unguarded(f: FieldSpec, *, broken_here: bool) -> FieldSpec:
        return f.model_copy(update={"required": False, "show_if": None if broken_here else f.show_if})

    pages = []
    for page in spec.pages:
        sections = []
        for s in page.sections:
            section_broken = broken(s.show_if, s.title)
            fields: list[FieldSpec] = []
            for f in s.fields:
                field_broken = broken(f.show_if, f.label)
                fields.append(unguarded(f, broken_here=field_broken) if field_broken or section_broken else f)
            update: dict = {"fields": fields}
            if section_broken:
                update["show_if"] = None
            sections.append(s.model_copy(update=update))
        pages.append(page.model_copy(update={"sections": sections}))
    return spec.model_copy(update={"pages": pages}), notes


# A sum of money and nothing else: "38 zł", "- 15 zł 00 gr", "1 250,50 zł".
PRINTED_AMOUNT = re.compile(r"^\s*-?\s*\d[\d\s]*(,\d+)?\s*zł(\s*\d+\s*gr)?\s*$", re.IGNORECASE)


def printed_amounts_as_info(spec: FormSpec) -> tuple[FormSpec, list[str]]:
    """Canon, fourth rule: a field whose description is only an amount printed on the paper ("Stawka
    opłaty: 38 zł" in material 8) is a constant, not something to type in. It becomes an INFO text block
    "<label>: <amount>"."""
    notes: list[str] = []

    def fix(f: FieldSpec) -> FieldSpec:
        if (
            f.kind not in (Kind.TEXT, Kind.NUMBER)
            or not f.description
            or not PRINTED_AMOUNT.match(f.description)
        ):
            return f
        notes.append(f"„{f.label}” to stała kwota z druku ({f.description.strip()}): informacja, nie pole.")
        text = f"{f.label}: {' '.join(f.description.split())}"
        return f.model_copy(
            update={"kind": Kind.INFO, "description": text, "required": False, "validators": []}
        )

    pages = [
        p.model_copy(
            update={
                "sections": [s.model_copy(update={"fields": [fix(f) for f in s.fields]}) for s in p.sections]
            }
        )
        for p in spec.pages
    ]
    return spec.model_copy(update={"pages": pages}), notes
