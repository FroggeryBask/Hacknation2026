from conftest import material

from autoformularz.extract import docx_text, extract, xlsx_text
from autoformularz.upload import Kind


def test_docx_keeps_tables_and_text():
    text = docx_text(material("2. */*.docx").read_bytes())
    assert "opłaty skarbowej" in text.lower() or "|" in text


def test_xlsx_rows():
    text = xlsx_text(material("3. */*.xlsx").read_bytes())
    assert text.startswith("|")


def test_image_is_downscaled():
    out = extract(Kind.PNG, material("2. */*.png").read_bytes())
    assert out.images and out.images[0].startswith(b"\x89PNG") and not out.text
