"""Turns an uploaded file into a Document: text blocks with IDs in reading order and/or page images.

Text formats keep reading order (paragraphs and table rows), so the model sees the paper layout.
Scans (JPG/PNG, PDF without a text layer) are cut into pages, read with OCR into the same blocks
(with page numbers) and also passed as pictures to the vision model (OCR does not see empty tick boxes).
.ods is read directly from its XML; only legacy binary .doc is converted with LibreOffice (headless,
separate process). Everything happens in memory or a temp dir.

For now one block = one line of the text below (a paragraph or a whole table row); finer blocks
(cells, options) come later without changing the Document shape."""

import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree

import docx
from openpyxl import load_workbook
from PIL import Image

from autoformularz.document import Document, build
from autoformularz.ocr import Ocr, OcrError, page_lines
from autoformularz.upload import Kind, UploadError

MAX_IMAGE_SIDE = 1600
SCANNED_CHARS_PER_PAGE = 80
MAX_OCR_PAGES = 30  # ~1 s per page; the longest material (form 9) has 16 pages
PDF_RENDER_SCALE = 3  # 216 dpi: enough detail for OCR (images for the model are downscaled anyway)
WINDOWS_SOFFICE = Path("C:/Program Files/LibreOffice/program/soffice.exe")


def _lines(text: str, page: int | None = None) -> list[tuple[str, int | None]]:
    return [(line, page) for line in text.splitlines()]


def extract(
    kind: Kind, data: bytes, *, soffice: str = "soffice", max_pages: int = 6, ocr: Ocr | None = None
) -> Document:
    """`max_pages`: page images passed to the model. `ocr`: None = scans go only as images."""
    match kind:
        case Kind.DOCX:
            return build(_lines(docx_text(data)))
        case Kind.DOC:
            return build(_lines(docx_text(convert(data, "doc", "docx", soffice))))
        case Kind.XLSX:
            return build(_lines(xlsx_text(data)))
        case Kind.ODS:
            return build(_lines(ods_text(data)))
        case Kind.PDF:
            return pdf(data, max_pages, ocr)
        case Kind.JPEG | Kind.PNG:
            return scan(data, max_pages, ocr)
    raise UploadError("UNSUPPORTED_FORMAT", f"Nieobsługiwany format: {kind}.", 415)


A4_RATIO = 2**0.5  # page height / width
CUT_WINDOW = 0.05  # search a blank row within ±5% of a page height around the expected boundary


def scan(data: bytes, max_pages: int, ocr: Ocr | None = None) -> Document:
    """Image scan -> one image per page. Multi-page forms often come as ONE tall image with the pages
    stacked (materials 1, 2, 6-9: up to 16 pages, 1654x37424 px); downscaled as a whole it would be an
    unreadable strip, so it is cut into pages first."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # Pillow refuses decompression bombs (> MAX_IMAGE_PIXELS) here
    except (OSError, Image.DecompressionBombError) as e:  # UnidentifiedImageError is an OSError
        raise UploadError("UNREADABLE_IMAGE", "Nie udało się odczytać obrazu.", 422) from e
    pages = split_pages(img.convert("L"))  # grayscale: 1/3 of the memory, OCR reads gray anyway
    return scanned_pages(iter(pages), len(pages), max_pages, ocr)


def scanned_pages(pages: Iterator[Image.Image], total: int, max_pages: int, ocr: Ocr | None) -> Document:
    """Page images -> Document: OCR blocks for the first MAX_OCR_PAGES pages + the first `max_pages`
    images for the vision model. Pages are consumed one at a time, so a long PDF is never held in
    memory at full resolution."""
    lines: list[tuple[str, int | None]] = []
    images: list[bytes] = []
    notes: list[str] = []
    ocr_ok = ocr is not None
    if ocr is None:
        notes.append("OCR niedostępny: skan przekazano modelowi tylko jako obraz.")
    needed = max(max_pages, MAX_OCR_PAGES if ocr else 0)
    for n, page in enumerate(pages, 1):
        if n > needed:
            break
        if n <= max_pages:
            images.append(_png(page))
        if ocr is not None and ocr_ok and n <= MAX_OCR_PAGES:
            try:
                lines += [(line, n) for line in page_lines(page, ocr)]
            except OcrError:
                ocr_ok, lines = False, []
                notes.append("OCR nie powiódł się: skan przekazano modelowi tylko jako obraz.")
    if ocr_ok and total > MAX_OCR_PAGES:
        notes.append(f"OCR objął pierwsze {MAX_OCR_PAGES} stron z {total}.")
    if total > max_pages:
        notes.append(f"Modelowi przekazano obrazy pierwszych {max_pages} stron z {total}.")
    return build(lines, images=images, notes=notes)


def split_pages(img: Image.Image) -> list[Image.Image]:
    """Cuts a tall image of stacked A4 pages at the blankest row near each expected page boundary.
    Deterministic: depends only on pixel values. A single page (or landscape) is returned as is."""
    w, h = img.size
    n = round(h / (w * A4_RATIO))
    if n <= 1:
        return [img]
    # One brightness value per row (box filter = exact row mean), no extra dependencies.
    rows = img.convert("L").resize((1, h), Image.Resampling.BOX).tobytes()
    page_h = h / n
    window = max(1, round(page_h * CUT_WINDOW))
    cuts = [0]
    for i in range(1, n):
        target = round(i * page_h)
        lo, hi = max(cuts[-1] + 1, target - window), min(h - 1, target + window)
        # brightest row; ties -> closest to the expected boundary, then the upper one
        cuts.append(max(range(lo, hi + 1), key=lambda y: (rows[y], -abs(y - target), -y)))
    cuts.append(h)
    return [img.crop((0, top, w, bottom)) for top, bottom in pairwise(cuts)]


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
CHECKBOX_GLYPHS = {"F0A8", "F06F", "F071", "F0FE", "F0FD", "F0A3"}  # Wingdings boxes used as tick fields


@dataclass
class Placed:
    """Text of a text box anchored to the PAGE: its position on the page in EMU (top-left) and height."""

    text: str
    x: int
    y: int
    height: int


def docx_text(data: bytes) -> str:
    """Reads paragraphs, tables AND text boxes in document order (many office forms are built from
    floating text boxes, which python-docx's high-level API skips). VML fallback copies are ignored.

    A PDF converted to DOCX may put every word in its own text box anchored to the page (material 8:
    651 boxes). Such boxes that follow each other at the same height are joined into one line, left to
    right (`_join_placed`), so the model gets lines of text instead of single words."""
    body = docx.Document(io.BytesIO(data)).element.body
    items: list[str | Placed] = []
    for el in body:
        if el.tag == f"{W}p":
            items.extend(_paragraph_lines(el))
        elif el.tag == f"{W}tbl":
            items.extend(_table_rows(el))
    return "\n".join(_dedupe(_join_placed(items)))


def _join_placed(items: list[str | Placed]) -> list[str]:
    """Consecutive page-anchored boxes whose tops differ by at most half the first box's height form one
    line, ordered by x. Deterministic: depends only on the order and positions in the file."""
    out: list[str] = []
    line: list[Placed] = []

    def flush() -> None:
        if line:
            out.append(" ".join(p.text for p in sorted(line, key=lambda p: p.x)))
            line.clear()

    for item in items:
        if isinstance(item, str):
            flush()
            out.append(item)
        elif line and abs(item.y - line[0].y) <= line[0].height // 2:
            line.append(item)
        else:
            flush()
            line.append(item)
    flush()
    return out


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


def _paragraph_lines(p) -> list[str | Placed]:
    lines: list[str | Placed] = [t] if (t := _own_text(p)) else []
    for box in p.iter(f"{W}txbxContent"):
        if _inside(box, p, (MC_FALLBACK, f"{W}txbxContent")):
            continue
        inner: list[str | Placed] = []
        for child in box:
            if child.tag == f"{W}p":
                inner.extend(_paragraph_lines(child))
            elif child.tag == f"{W}tbl":
                inner.extend(_table_rows(child))
        if (pos := _page_position(box)) and inner and all(isinstance(i, str) for i in inner):
            lines.append(Placed(" ".join(str(i) for i in inner), *pos))
        else:
            lines.extend(inner)
    return lines


def _page_position(box) -> tuple[int, int, int] | None:
    """(x, y, height) in EMU of the box's anchor when it is positioned relative to the page, else None."""
    anchor = box.getparent()
    while anchor is not None and anchor.tag != f"{WP}anchor":
        anchor = anchor.getparent()
    if anchor is None:
        return None
    h, v, extent = anchor.find(f"{WP}positionH"), anchor.find(f"{WP}positionV"), anchor.find(f"{WP}extent")
    if h is None or v is None or extent is None or v.get("relativeFrom") != "page":
        return None
    x, y = h.find(f"{WP}posOffset"), v.find(f"{WP}posOffset")
    try:
        return int(x.text), int(y.text), int(extent.get("cy"))  # type: ignore[union-attr]
    except AttributeError, TypeError, ValueError:  # missing offset (e.g. align="center")
        return None


def _text_lines(items: list[str | Placed]) -> list[str]:
    return [i if isinstance(i, str) else i.text for i in items]


def _table_rows(tbl) -> list[str]:
    rows = []
    for tr in tbl.iterchildren(f"{W}tr"):
        cells: list[str] = []
        for tc in tr.iterchildren(f"{W}tc"):
            parts = []
            for child in tc:
                if child.tag == f"{W}p":
                    parts.extend(_text_lines(_paragraph_lines(child)))
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


ODS_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
ODS_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
ODS_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"


def ods_text(data: bytes) -> str:
    """Reads an OpenDocument spreadsheet directly from its XML (a ZIP like .xlsx), in the same shape as
    `xlsx_text`: no LibreOffice needed. Covered cells (merged areas) are empty; repeated empty
    rows/columns (an ODS sheet declares ~1M of them) are never expanded."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ElementTree.fromstring(z.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as e:
        raise UploadError("CONVERSION_FAILED", "Nie udało się odczytać pliku .ods.", 422) from e
    tables = root.findall(f"{ODS_OFFICE}body/{ODS_OFFICE}spreadsheet/{ODS_TABLE}table")
    lines: list[str] = []
    for table in tables:
        if len(tables) > 1:
            lines.append(f"## Arkusz: {table.get(f'{ODS_TABLE}name', '')}")
        for row in table.iter(f"{ODS_TABLE}table-row"):
            cells = [t for cell in row if cell.tag == f"{ODS_TABLE}table-cell" if (t := _ods_cell(cell))]
            if cells:
                lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _ods_cell(cell) -> str:
    """Cell text as displayed: paragraphs joined with spaces, <text:s c="n"/> = n spaces, whitespace
    collapsed (like DOCX and XLSX)."""
    parts: list[str] = []

    def walk(el) -> None:
        if el.text:
            parts.append(el.text)
        for child in el:
            if child.tag == f"{ODS_TEXT}s":
                parts.append(" " * int(child.get(f"{ODS_TEXT}c", "1")))
            elif child.tag in (f"{ODS_TEXT}tab", f"{ODS_TEXT}line-break"):
                parts.append(" ")
            else:
                walk(child)
            if child.tail:
                parts.append(child.tail)

    for p in cell.iter(f"{ODS_TEXT}p"):
        walk(p)
        parts.append(" ")
    return " ".join("".join(parts).split())


def xlsx_text(data: bytes) -> str:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        if len(wb.worksheets) > 1:
            lines.append(f"## Arkusz: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            # Whitespace collapsed like in DOCX: a multi-line cell stays inside its row (one block per row).
            cells = [" ".join(str(c).split()) for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def pdf(data: bytes, max_pages: int, ocr: Ocr | None = None) -> Document:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    texts = [(p.extract_text() or "").strip() for p in reader.pages]
    if sum(len(t) for t in texts) >= SCANNED_CHARS_PER_PAGE * max(1, len(texts)):
        return build([line for page, t in enumerate(texts, 1) for line in _lines(t, page)])
    # Scanned PDF: same path as image scans, rendered lazily page by page.
    out = scanned_pages(render_pdf(data), len(reader.pages), max_pages, ocr)
    out.notes.insert(0, "PDF bez warstwy tekstowej (skan).")
    return out


def render_pdf(data: bytes) -> Iterator[Image.Image]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    for page in doc:
        yield page.render(scale=PDF_RENDER_SCALE, grayscale=True).to_pil()


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
