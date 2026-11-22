"""OCR for scans. Tests that run Tesseract are skipped when it (or the Polish model) is not installed."""

import io
import subprocess

import pytest
from conftest import material
from PIL import Image

from autoformularz.config import Settings
from autoformularz.extract import extract, split_pages
from autoformularz.ocr import Ocr, ocr_from, tsv_lines
from autoformularz.upload import Kind

TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t95\tWniosek\n"
    "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t95\to\n"
    "5\t1\t1\t1\t1\t3\t0\t0\t10\t10\t95\tzwrot\n"
    "5\t1\t1\t1\t2\t1\t0\t0\t10\t10\t40\t|\n"
    "5\t1\t2\t1\t1\t1\t0\t0\t10\t10\t90\tImię:\n"
    '5\t1\t2\t1\t1\t2\t0\t0\t10\t10\t90\t"Jan\n'
)


def test_tsv_lines_groups_words_and_drops_noise():
    # a line of only "|" (box border) is dropped; a lone quote char does not break parsing
    assert tsv_lines(TSV) == ["Wniosek o zwrot", 'Imię: "Jan']


@pytest.fixture(scope="module")
def ocr() -> Ocr:
    s = Settings()
    found = ocr_from(s.ocr_bin, s.ocr_lang, s.tessdata_dir)
    if not found:
        pytest.skip("brak Tesseracta")
    cmd = [found.binary, "--list-langs"] + (
        ["--tessdata-dir", found.tessdata_dir] if found.tessdata_dir else []
    )
    if "pol" not in subprocess.run(cmd, capture_output=True, text=True).stdout.split():
        pytest.skip("brak polskiego modelu Tesseracta (pol.traineddata)")
    return found


def test_scan_gets_blocks_with_pages(ocr):
    doc = extract(Kind.PNG, material("2. */*.png").read_bytes(), ocr=ocr)
    text = doc.text.lower()
    assert "wniosek o zwrot opłaty skarbowej" in text
    assert "art. 9 ustawy z dnia 16 listopada 2006" in text  # legal text kept word for word
    assert {b.page for b in doc.blocks} == {1, 2}  # stacked scan: two pages
    assert len(doc.images) == 2 and not doc.notes


def test_ocr_is_deterministic(ocr):
    data = material("3. */*.png").read_bytes()
    first, second = extract(Kind.PNG, data, ocr=ocr), extract(Kind.PNG, data, ocr=ocr)
    assert first.as_dict() == second.as_dict() and first.blocks


def test_scanned_pdf_uses_ocr(ocr):
    pages = split_pages(Image.open(material("2. */*.png")))
    buf = io.BytesIO()
    pages[0].convert("RGB").save(
        buf, format="PDF", save_all=True, append_images=[p.convert("RGB") for p in pages[1:]]
    )
    doc = extract(Kind.PDF, buf.getvalue(), ocr=ocr)
    assert doc.notes[0] == "PDF bez warstwy tekstowej (skan)."
    assert "wniosek o zwrot opłaty skarbowej" in doc.text.lower()
    assert {b.page for b in doc.blocks} == {1, 2} and len(doc.images) == 2


def test_broken_tesseract_falls_back_to_images(tmp_path):
    fake = Ocr(binary=str(tmp_path / "missing-tesseract"))
    doc = extract(Kind.PNG, material("3. */*.png").read_bytes(), ocr=fake)
    assert not doc.blocks and doc.images
    assert doc.notes == ["OCR nie powiódł się: skan przekazano modelowi tylko jako obraz."]


def test_sparse_pass_restores_words_after_a_dotted_leader():
    """--psm 4 drops what follows a long dotted line ("w miejscowości …… przy ulicy"): the sparse pass's
    words come back into the same row, after a place to fill in, in left-to-right order."""
    from autoformularz.ocr import FILL, Row, merge_sparse, row_text

    main = [Row([(100, "w"), (130, "miejscowości")], 500, 540, 400)]
    sparse = [Row([(900, "przy"), (980, "ulicy")], 505, 538, 1100)]
    out = merge_sparse(main, sparse)
    assert [row_text(r) for r in out] == [f"w miejscowości {FILL} przy ulicy"]


def test_sparse_pass_adds_missing_rows_in_place_and_skips_known_text():
    from autoformularz.ocr import Row, merge_sparse, row_text

    main = [Row([(10, "Imię")], 100, 130, 200), Row([(10, "Adres")], 300, 330, 200)]
    sparse = [
        Row([(10, "Imię")], 100, 130, 200),  # already read
        Row([(10, "Nazwisko")], 200, 230, 200),  # dropped by the column pass: goes between the two
        Row([(10, "|")], 400, 410, 20),  # a box border read as text
    ]
    assert [row_text(r) for r in merge_sparse(main, sparse)] == ["Imię", "Nazwisko", "Adres"]


def test_sparse_pass_does_not_double_a_row_read_differently():
    from autoformularz.ocr import Row, merge_sparse, row_text

    main = [Row([(10, "art."), (60, "6m"), (100, "ust."), (150, "1a")], 100, 130, 300)]
    sparse = [Row([(10, "art."), (60, "6m"), (100, "ust."), (150, "lai")], 100, 130, 300)]
    assert [row_text(r) for r in merge_sparse(main, sparse)] == ["art. 6m ust. 1a"]
