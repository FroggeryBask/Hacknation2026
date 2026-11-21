"""Check step (docs/pipeline.md, step 4): does the FormSpec stay true to the Document?

Coverage counts and canon (`dedupe`: repeated pages, sections, fields; `drop_standard_sections`: copies of
the predefined applicant/proxy/contact part). Later: dropping fields whose anchors do not exist, a retry
for blocks without a role, TEXT_BLOCK fallback, type normalisation."""

import re
from dataclasses import asdict, dataclass, field

from autoformularz.document import Document
from autoformularz.spec import FormSpec, Role


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
    skipped = {r.block for r in spec.block_roles if r.role is Role.SKIP}
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
    - a field with the same label as an earlier field in its section.
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
            for f in section.fields:
                if f.label in labels:
                    notes.append(f"Pominięto powtórzone pole „{f.label}” w sekcji „{section.title}”.")
                    continue
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


# Section titles of the predefined part that the compiler always adds from the design standard (applicant,
# proxy, contact). A model sometimes copies them from the paper form anyway; they would appear twice.
STANDARD_SECTION = re.compile(
    r"wnioskodawc|pełnomocni|dane kontaktowe|dane do kontaktu|podpis", re.IGNORECASE
)


ENTITY_ID = re.compile(r"\b(NIP|REGON|KRS)\b")


def drop_standard_sections(spec: FormSpec) -> tuple[FormSpec, list[str]]:
    """Canon, second rule: sections about the applicant, proxy or contact data are left to the compiler's
    predefined sections. Deterministic (by page and section title); a page left empty is dropped too.

    What they asked for still matters: NIP/REGON/KRS among the applicant's fields means the applicant may be
    a company or institution, so `applicant.entity` is set (and `entity_nip_only` when only NIP is asked,
    like reference form 5), whatever the model said."""
    notes: list[str] = []
    pages = []
    dropped_labels: list[str] = []
    for page in spec.pages:
        if STANDARD_SECTION.search(page.title):
            notes.append(f"Strona „{page.title}” jest w części standardowej formularza (pominięta).")
            dropped_labels += [f.label for s in page.sections for f in s.fields]
            continue
        sections = []
        for section in page.sections:
            if STANDARD_SECTION.search(section.title):
                notes.append(f"Sekcja „{section.title}” jest w części standardowej formularza (pominięta).")
                dropped_labels += [f.label for f in section.fields]
            else:
                sections.append(section)
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
