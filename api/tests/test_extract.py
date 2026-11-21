import io
import zipfile

import pytest
from conftest import material
from PIL import Image, ImageDraw

from autoformularz.extract import (
    MAX_IMAGE_SIDE,
    convert,
    docx_text,
    extract,
    find_soffice,
    ods_text,
    split_pages,
    xlsx_text,
)
from autoformularz.upload import Kind, UploadError


def test_docx_keeps_tables_and_text():
    text = docx_text(material("2. */*.docx").read_bytes())
    assert "opłaty skarbowej" in text.lower() or "|" in text


def test_xlsx_rows():
    text = xlsx_text(material("3. */*.xlsx").read_bytes())
    assert text.startswith("|")


def test_image_is_downscaled():
    out = extract(Kind.PNG, material("2. */*.png").read_bytes())
    assert out.images and out.images[0].startswith(b"\x89PNG") and not out.text


def stacked(pages: int, w: int = 200) -> Image.Image:
    """White A4-ratio pages stacked vertically, each with a black "text" bar in the middle."""
    h = round(w * 2**0.5)
    img = Image.new("RGB", (w, h * pages), "white")
    draw = ImageDraw.Draw(img)
    for i in range(pages):
        top = i * h + h // 4
        draw.rectangle((10, top, w - 10, top + h // 2), fill="black")
    return img


def test_single_page_is_not_cut():
    assert len(split_pages(stacked(1))) == 1
    assert len(split_pages(Image.new("RGB", (300, 200), "white"))) == 1  # landscape


@pytest.mark.parametrize("pages", [2, 6, 16])
def test_stacked_pages_are_cut_in_blank_rows(pages):
    img = stacked(pages)
    parts = split_pages(img)
    assert len(parts) == pages
    assert sum(p.size[1] for p in parts) == img.size[1]  # nothing lost or duplicated
    for p in parts:  # every cut is in white space: each part keeps one whole black bar
        top_row = p.crop((0, 0, p.size[0], 1)).convert("L").getextrema()
        assert top_row == (255, 255)


def test_split_is_deterministic():
    img = stacked(6)
    assert [p.tobytes() for p in split_pages(img)] == [p.tobytes() for p in split_pages(img)]


@pytest.mark.parametrize(("pattern", "pages"), [("1. */*.png", 2), ("8. */*.png", 6), ("3. */*.png", 1)])
def test_material_scans_are_split_into_readable_pages(pattern, pages):
    out = extract(Kind.PNG, material(pattern).read_bytes(), max_pages=20)
    assert len(out.images) == pages
    for png in out.images:  # each page keeps A4 proportions after downscaling (not a thin strip)
        w, h = Image.open(io.BytesIO(png)).size
        assert max(w, h) <= MAX_IMAGE_SIDE and 1.3 < h / w < 1.5


def test_broken_image_is_a_clean_error():
    with pytest.raises(UploadError) as e:
        extract(Kind.PNG, b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    assert e.value.code == "UNREADABLE_IMAGE" and e.value.status == 422


def test_scan_page_limit_adds_note():
    out = extract(Kind.PNG, material("8. */*.png").read_bytes(), max_pages=2)
    assert len(out.images) == 2
    assert out.notes == [
        "OCR niedostępny: skan przekazano modelowi tylko jako obraz.",
        "Modelowi przekazano obrazy pierwszych 2 stron z 6.",
    ]


ODS_HEAD = (
    '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet>'
)


def ods(tables: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr(
            "content.xml", ODS_HEAD + tables + "</office:spreadsheet></office:body></office:document-content>"
        )
    return buf.getvalue()


def test_ods_cells_spaces_merges_and_repeats():
    data = ods(
        '<table:table table:name="A">'
        '<table:table-row><table:table-cell table:number-columns-spanned="2"><text:p>Imię<text:s text:c="3"/>i'
        "</text:p><text:p>nazwisko</text:p></table:table-cell><table:covered-table-cell/>"
        "<table:table-cell><text:p>……</text:p></table:table-cell>"
        '<table:table-cell table:number-columns-repeated="16380"/></table:table-row>'
        '<table:table-row table:number-rows-repeated="1048570"><table:table-cell/></table:table-row>'
        "</table:table>"
    )
    assert ods_text(data) == "| Imię i nazwisko | …… |"


def test_ods_sheets_get_headings():
    sheet = '<table:table table:name="{}"><table:table-row><table:table-cell><text:p>x</text:p></table:table-cell></table:table-row></table:table>'
    assert ods_text(ods(sheet.format("A") + sheet.format("B"))) == "## Arkusz: A\n| x |\n## Arkusz: B\n| x |"


def test_broken_ods_is_a_clean_error():
    with pytest.raises(UploadError) as e:
        ods_text(b"PK\x03\x04 not a zip")
    assert e.value.code == "CONVERSION_FAILED"


def test_ods_material_reads_without_libreoffice():
    doc = extract(Kind.ODS, material("3. */*.ods").read_bytes(), soffice="no-such-binary")
    assert doc.blocks[0].text == "| Młynary, dnia……………………. |"


@pytest.mark.parametrize("n", [3, 9])  # simplest and largest; all 9 matched when written
def test_ods_matches_libreoffice_conversion(n):
    """Native reader gives exactly what the old LibreOffice path (ods -> xlsx -> xlsx_text) gave."""
    if not find_soffice("soffice"):
        pytest.skip("brak LibreOffice")
    data = material(f"{n}. */*.[oO][dD][sS]").read_bytes()
    assert ods_text(data) == xlsx_text(convert(data, "ods", "xlsx", "soffice"))


def _docx_with_boxes(boxes: list[tuple[str, int, int, str]]) -> bytes:
    """DOCX whose body is one paragraph of floating text boxes: (text, x, y, relativeFrom) in EMU."""
    import docx
    from docx.oxml import parse_xml

    ns = (
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
    )
    runs = "".join(
        f'<w:r><w:drawing><wp:anchor><wp:positionH relativeFrom="{rel}"><wp:posOffset>{x}</wp:posOffset>'
        f'</wp:positionH><wp:positionV relativeFrom="{rel}"><wp:posOffset>{y}</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="500000" cy="130000"/><a:graphic><a:graphicData><wps:wsp><wps:txbx><w:txbxContent>'
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:txbxContent></wps:txbx></wps:wsp></a:graphicData>"
        f"</a:graphic></wp:anchor></w:drawing></w:r>"
        for text, x, y, rel in boxes
    )
    d = docx.Document()
    d.element.body.insert(0, parse_xml(f"<w:p {ns}>{runs}</w:p>"))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_page_anchored_word_boxes_join_into_lines_left_to_right():
    # A PDF converted to DOCX: one box per word, slightly uneven tops, not in x order within a line.
    data = _docx_with_boxes(
        [
            ("Oświadczam,", 100_000, 5_000_000, "page"),
            ("nieruchomość", 900_000, 5_004_000, "page"),
            ("że", 500_000, 4_998_000, "page"),
            ("Druga", 100_000, 5_200_000, "page"),
            ("linia", 400_000, 5_200_000, "page"),
        ]
    )
    assert docx_text(data).splitlines()[:2] == ["Oświadczam, że nieruchomość", "Druga linia"]


def test_paragraph_anchored_boxes_stay_separate():
    # Positions relative to a paragraph (material 2) say nothing about lines on the page.
    data = _docx_with_boxes([("Imię", 100, 0, "paragraph"), ("Nazwisko", 900, 0, "paragraph")])
    assert docx_text(data).splitlines()[:2] == ["Imię", "Nazwisko"]


def test_material_8_reads_lines_not_single_words():
    lines = docx_text(material("8. */*.docx").read_bytes()).splitlines()
    assert len(lines) < 400  # 631 single-word lines before
    assert "43. Stawka opłaty od" in lines
    assert any(line.startswith("Oświadczam, że nieruchomość wyposażona jest w przydomowy") for line in lines)
