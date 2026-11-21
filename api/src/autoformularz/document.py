"""Document: what `extract.py` reads from a file, shared by the LLM prompt, the checks and the UI.

The source text is split into blocks with stable IDs (b1, b2, ... in reading order). The model refers to
blocks by ID instead of copying their text, so the code can check that every field comes from the file
and that no text is lost (see docs/pipeline.md, "Kontrakt")."""

import re
from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal["paragraph", "table_row", "heading"]
CandidateKind = Literal["blank", "dots", "checkbox", "colon"]


@dataclass
class Block:
    id: str
    text: str
    kind: BlockKind = "paragraph"
    page: int | None = None  # 1-based; None when the format has no pages (DOCX, XLSX)


@dataclass
class FieldCandidate:
    """A spot in the source that looks like a place to fill in."""

    block: str  # Block.id
    kind: CandidateKind
    text: str  # the matched fragment, e.g. "Imię: ____"


@dataclass
class Document:
    blocks: list[Block] = field(default_factory=list)
    candidates: list[FieldCandidate] = field(default_factory=list)
    images: list[bytes] = field(default_factory=list)  # PNG bytes, already downscaled (scans)
    notes: list[str] = field(default_factory=list)
    hint: str = ""  # one line for the model about blocks the code already handled (presort), not in the API

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    def ids(self) -> set[str]:
        return {b.id for b in self.blocks}

    def as_dict(self) -> dict:
        """JSON shape for `?details=true` (images are left out)."""
        return {
            "blocks": [{"id": b.id, "text": b.text, "kind": b.kind, "page": b.page} for b in self.blocks],
            "candidates": [{"block": c.block, "kind": c.kind, "text": c.text} for c in self.candidates],
        }


# Box glyphs used as tick fields: ☐ (DOCX Wingdings mapped in extract.py), □ (form 9), ❑ (form 7 PDF).
_BOX = "☐□❑❒▢◻⬜"

_CANDIDATES: list[tuple[CandidateKind, re.Pattern[str]]] = [
    ("checkbox", re.compile(rf"[{_BOX}]\s*[^{_BOX}|]*")),
    ("blank", re.compile(r"[^_|]{0,60}_{3,}")),
    ("dots", re.compile(r"[^.…|]{0,60}(?:\.{4,}|…{2,})")),
]


def _colon_labels(text: str) -> list[str]:
    """`Label:` with nothing after it, per table cell. A cell may hold several labels in a row
    ("Miejscowość: Kod pocztowy:"): when the cell ends with a colon, every part before a colon is a label.
    A cell with a value after its last colon ("Płeć: ❑ pies", "godz. 10:30") gives none."""
    labels = []
    for cell in text.split("|"):
        cell = cell.strip()
        if not cell.endswith(":"):
            continue
        labels += [
            f"{p.strip()}:" for p in cell[:-1].split(":") if 2 <= len(p.strip()) <= 60 and _has_letter(p)
        ]
    return labels


def _has_letter(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def find_candidates(block: Block) -> list[FieldCandidate]:
    """Spots to fill in: `____`, `......`, `☐ option`, and `Label:` with nothing after it."""
    out: list[FieldCandidate] = []
    for kind, pattern in _CANDIDATES:
        out += [
            FieldCandidate(block.id, kind, m.group(0).strip())
            for m in pattern.finditer(block.text)
            if m.group(0).strip()
        ]
    out += [FieldCandidate(block.id, "colon", label) for label in _colon_labels(block.text)]
    return out


def build(lines: list[tuple[str, int | None]], **kw) -> Document:
    """Blocks from text lines in reading order: (text, page). Table rows are kept as one block."""
    doc = Document(**kw)
    for text, page in lines:
        text = text.strip()
        if not text:
            continue
        kind: BlockKind = (
            "table_row" if text.startswith("|") else "heading" if text.startswith("## ") else "paragraph"
        )
        block = Block(id=f"b{len(doc.blocks) + 1}", text=text, kind=kind, page=page)
        doc.blocks.append(block)
        doc.candidates += find_candidates(block)
    return doc
