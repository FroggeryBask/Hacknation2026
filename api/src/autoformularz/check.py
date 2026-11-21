"""Check step (docs/pipeline.md, step 4): does the FormSpec stay true to the Document?

First version: coverage counts only. Later: dropping fields whose anchors don't exist, a retry for
blocks without a role, TEXT_BLOCK fallback, type normalisation."""

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
