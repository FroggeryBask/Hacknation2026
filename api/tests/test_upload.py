import io
import zipfile

import pytest
from conftest import material

from autoformularz.upload import Kind, UploadError, sniff, validate_filename, validate_upload


def zip_with(*names: str, mimetype: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        if mimetype:
            z.writestr("mimetype", mimetype)
        for n in names:
            z.writestr(n, "x")
    return buf.getvalue()


@pytest.mark.parametrize(
    "data,kind",
    [
        (b"%PDF-1.7 ...", Kind.PDF),
        (b"\x89PNG\r\n\x1a\n....", Kind.PNG),
        (b"\xff\xd8\xff\xe0....", Kind.JPEG),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1....", Kind.DOC),
        (zip_with("[Content_Types].xml", "word/document.xml"), Kind.DOCX),
        (zip_with("[Content_Types].xml", "xl/workbook.xml"), Kind.XLSX),
        (zip_with("content.xml", mimetype="application/vnd.oasis.opendocument.spreadsheet"), Kind.ODS),
        (b"hello", None),
    ],
)
def test_sniff(data, kind):
    assert sniff(data) == kind


@pytest.mark.parametrize(
    "name", ["a;b.pdf", "a:b.pdf", "x<y.pdf", "a/b.pdf", "a\\b.pdf", "it's.pdf", "100%.pdf"]
)
def test_forbidden_chars(name):
    with pytest.raises(UploadError) as e:
        validate_filename(name)
    assert e.value.code == "FILENAME_FORBIDDEN_CHARS"


def test_name_length_and_extension():
    assert validate_filename("Wniosek o zwrot opłaty skarbowej.DOCX") == Kind.DOCX
    with pytest.raises(UploadError, match="250"):
        validate_filename("a" * 247 + ".pdf")
    with pytest.raises(UploadError) as e:
        validate_filename("plik.exe")
    assert e.value.code == "UNSUPPORTED_FORMAT"


def test_content_must_match_extension():
    with pytest.raises(UploadError) as e:
        validate_upload("skan.pdf", b"\x89PNG\r\n\x1a\n....", 1000)
    assert e.value.code == "MIME_MISMATCH"
    assert validate_upload("skan.jpe", b"\xff\xd8\xff\xe0....", 1000) == Kind.JPEG


def test_word_extensions_are_one_format():
    """Task: "DOC (.doc .docx)". A .docx saved as .doc (materials 5 and 7) is read by its content."""
    docx = zip_with("[Content_Types].xml", "word/document.xml")
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1...."
    assert validate_upload("Wniosek.DOC", docx, 1000) == Kind.DOCX
    assert validate_upload("Wniosek.docx", ole, 1000) == Kind.DOC
    with pytest.raises(UploadError) as e:
        validate_upload("Wniosek.doc", b"%PDF-1.7 ...", 1000)
    assert e.value.code == "MIME_MISMATCH"


def test_materials_with_docx_under_doc_name():
    path = material("7. */*.DOC")
    assert validate_upload(path.name, path.read_bytes(), 50 << 20) == Kind.DOCX


def test_size_limit():
    with pytest.raises(UploadError) as e:
        validate_upload("a.pdf", b"%PDF-" + b"0" * 2000, 1000)
    assert e.value.code == "FILE_TOO_LARGE"
