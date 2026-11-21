"""Turns an uploaded file into what the model reads: ordered text and/or page images.

Text formats keep reading order (paragraphs and table rows), so the model sees the paper layout.
Images and scanned PDFs are passed as pictures to the vision model. Legacy .doc/.ods are converted
with LibreOffice (headless, separate process). Everything happens in memory or a temp dir."""

import io
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
from PIL import Image

from autoformularz.upload import Kind, UploadError

MAX_IMAGE_SIDE = 1600
SCANNED_CHARS_PER_PAGE = 80
WINDOWS_SOFFICE = Path("C:/Program Files/LibreOffice/program/soffice.exe")


@dataclass
class Extracted:
    text: str = ""
    images: list[bytes] = field(default_factory=list)  # PNG/JPEG bytes, already downscaled
    notes: list[str] = field(default_factory=list)


def extract(kind: Kind, data: bytes, *, soffice: str = "soffice", max_pages: int = 6) -> Extracted:
    match kind:
        case Kind.DOCX:
            return Extracted(text=docx_text(data))
        case Kind.DOC:
            return Extracted(text=docx_text(convert(data, "doc", "docx", soffice)))
        case Kind.XLSX:
            return Extracted(text=xlsx_text(data))
        case Kind.ODS:
            return Extracted(text=xlsx_text(convert(data, "ods", "xlsx", soffice)))
        case Kind.PDF:
            return pdf(data, max_pages)
        case Kind.JPEG | Kind.PNG:
            return Extracted(images=[downscale(data)])
    raise UploadError("UNSUPPORTED_FORMAT", f"Nieobsługiwany format: {kind}.", 415)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
CHECKBOX_GLYPHS = {"F0A8", "F06F", "F071", "F0FE", "F0FD", "F0A3"}  # Wingdings boxes used as tick fields


def docx_text(data: bytes) -> str:
    """Reads paragraphs, tables AND text boxes in document order (many office forms are built from
    floating text boxes, which python-docx's high-level API skips). VML fallback copies are ignored."""
    body = Document(io.BytesIO(data)).element.body
    lines: list[str] = []
    for el in body:
        if el.tag == f"{W}p":
            lines.extend(_paragraph_lines(el))
        elif el.tag == f"{W}tbl":
            lines.extend(_table_rows(el))
    return "\n".join(_dedupe(lines))


def _own_text(el) -> str:
    """Text of runs that belong to this element, not to nested text boxes."""
    parts = []
    for node in el.iter(f"{W}t", f"{W}sym", f"{W}tab", f"{W}txbxContent", MC_FALLBACK):
        if _inside(node, el, (f"{W}txbxContent", MC_FALLBACK)):
            continue
        if node.tag == f"{W}t":
            parts.append(node.text or "")
        elif node.tag == f"{W}sym" and (node.get(f"{W}char") or "").upper() in CHECKBOX_GLYPHS:
            parts.append("☐ ")
        elif node.tag == f"{W}tab":
            parts.append(" ")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _inside(node, root, tags: tuple[str, ...]) -> bool:
    parent = node.getparent()
    while parent is not None and parent is not root:
        if parent.tag in tags:
            return True
        parent = parent.getparent()
    return False


def _paragraph_lines(p) -> list[str]:
    lines = [t] if (t := _own_text(p)) else []
    for box in p.iter(f"{W}txbxContent"):
        if _inside(box, p, (MC_FALLBACK, f"{W}txbxContent")):
            continue
        for child in box:
            if child.tag == f"{W}p":
                lines.extend(_paragraph_lines(child))
            elif child.tag == f"{W}tbl":
                lines.extend(_table_rows(child))
    return lines


def _table_rows(tbl) -> list[str]:
    rows = []
    for tr in tbl.iterchildren(f"{W}tr"):
        cells: list[str] = []
        for tc in tr.iterchildren(f"{W}tc"):
            parts = []
            for child in tc:
                if child.tag == f"{W}p":
                    parts.extend(_paragraph_lines(child))
                elif child.tag == f"{W}tbl":
                    parts.append(" / ".join(_table_rows(child)))
            text = " ".join(parts).strip()
            if text and (not cells or cells[-1] != text):  # merged cells repeat their text
                cells.append(text)
        if cells:
            rows.append("| " + " | ".join(cells) + " |")
    return rows


def _dedupe(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not out or out[-1] != line:
            out.append(line)
    return out


def xlsx_text(data: bytes) -> str:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        if len(wb.worksheets) > 1:
            lines.append(f"## Arkusz: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def pdf(data: bytes, max_pages: int) -> Extracted:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    texts = [(p.extract_text() or "").strip() for p in reader.pages]
    out = Extracted(text="\n\n".join(t for t in texts if t))
    if len(out.text) < SCANNED_CHARS_PER_PAGE * max(1, len(texts)):
        out.images = render_pdf(data, max_pages)
        out.notes.append("PDF bez warstwy tekstowej: przekazano obrazy stron.")
    if len(reader.pages) > max_pages and out.images:
        out.notes.append(f"Przeanalizowano pierwsze {max_pages} stron z {len(reader.pages)}.")
    return out


def render_pdf(data: bytes, max_pages: int) -> list[bytes]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    images = []
    for i in range(min(len(doc), max_pages)):
        pil = doc[i].render(scale=2).to_pil()
        images.append(_png(pil))
    return images


def downscale(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.load()
    return _png(img)


def _png(img: Image.Image) -> bytes:
    img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def find_soffice(configured: str) -> str | None:
    found = shutil.which(configured)
    if found:
        return found
    return str(WINDOWS_SOFFICE) if WINDOWS_SOFFICE.exists() else None


def convert(data: bytes, src_ext: str, dst_ext: str, soffice: str) -> bytes:
    binary = find_soffice(soffice)
    if not binary:
        raise UploadError(
            "CONVERTER_MISSING",
            f"Format .{src_ext} wymaga LibreOffice, którego nie znaleziono na serwerze.",
            503,
        )
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input.{src_ext}"
        src.write_bytes(data)
        # Separate profile dir: parallel conversions don't fight over the user profile lock.
        profile = Path(tmp, "profile").as_uri()
        cmd = [
            binary,
            f"-env:UserInstallation={profile}",
            "--headless",
            "--convert-to",
            dst_ext,
            "--outdir",
            tmp,
            str(src),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise UploadError("CONVERSION_FAILED", f"Nie udało się odczytać pliku .{src_ext}.", 422) from e
        out = Path(tmp) / f"input.{dst_ext}"
        if not out.exists():
            raise UploadError("CONVERSION_FAILED", f"Nie udało się odczytać pliku .{src_ext}.", 422)
        return out.read_bytes()
