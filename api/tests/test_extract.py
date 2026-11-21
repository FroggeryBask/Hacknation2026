import io

import pytest
from conftest import material
from PIL import Image, ImageDraw

from autoformularz.extract import MAX_IMAGE_SIDE, docx_text, extract, split_pages, xlsx_text
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
    assert len(out.images) == 2 and out.notes == ["Przeanalizowano pierwsze 2 stron z 6."]
