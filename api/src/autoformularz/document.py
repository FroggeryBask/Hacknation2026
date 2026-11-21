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


_CANDIDATES: list[tuple[CandidateKind, re.Pattern[str]]] = [
    ("checkbox", re.compile(r"[☐□]\s*[^☐□|]*")),
    ("blank", re.compile(r"[^_|]{0,60}_{3,}")),
    ("dots", re.compile(r"[^.…|]{0,60}(?:\.{4,}|…{2,})")),
    ("colon", re.compile(r"[^:|]{2,60}:\s*(?=\||$)")),
]


def find_candidates(block: Block) -> list[FieldCandidate]:
    """Spots to fill in: `____`, `......`, `☐ option`, and `Label:` with nothing after it."""
    out: list[FieldCandidate] = []
    for kind, pattern in _CANDIDATES:
        out += [
            FieldCandidate(block.id, kind, m.group(0).strip())
            for m in pattern.finditer(block.text)
            if m.group(0).strip()
        ]
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
