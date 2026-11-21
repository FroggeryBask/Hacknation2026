"""Document contract (docs/pipeline.md, "Kontrakt"): blocks with IDs, field candidates, coverage."""

from conftest import material

from autoformularz.check import coverage
from autoformularz.document import Block, build, find_candidates
from autoformularz.extract import extract
from autoformularz.llm import build_user_prompt
from autoformularz.spec import BlockRole, FieldSpec, FormSpec, Kind, PageSpec, Role, SectionSpec
from autoformularz.upload import Kind as FileKind


def test_blocks_have_sequential_ids_and_kinds():
    doc = build([("Wniosek o zwrot", None), ("", None), ("| Imię | ____ |", None), ("## Arkusz: A", None)])
    assert [(b.id, b.kind) for b in doc.blocks] == [
        ("b1", "paragraph"),
        ("b2", "table_row"),
        ("b3", "heading"),
    ]
    assert doc.ids() == {"b1", "b2", "b3"}


def test_candidates():
    kinds = lambda text: [c.kind for c in find_candidates(Block("b1", text))]  # noqa: E731
    assert kinds("Imię i nazwisko: ________") == ["blank"]
    assert kinds("Adres .............") == ["dots"]
    assert kinds("☐ tak ☐ nie") == ["checkbox", "checkbox"]
    assert kinds("Płeć: ❑ pies ❑ suka") == ["checkbox", "checkbox"]  # form 7 PDF
    assert kinds("| Numer PESEL: | |") == ["colon"]
    assert kinds("Wniosek o wydanie zaświadczenia") == []


def test_docx_document_matches_text_lines():
    doc = extract(FileKind.DOCX, material("2. */*.docx").read_bytes())
    assert doc.blocks and not doc.images
    assert all(b.page is None for b in doc.blocks)
    assert doc.blocks[0].id == "b1" and doc.blocks[-1].id == f"b{len(doc.blocks)}"
    assert {c.block for c in doc.candidates} <= doc.ids()


def test_xlsx_rows_are_table_blocks():
    doc = extract(FileKind.XLSX, material("3. */*.xlsx").read_bytes())
    assert doc.blocks and all(b.kind in ("table_row", "heading") for b in doc.blocks)


def test_pdf_blocks_have_pages():
    doc = extract(FileKind.PDF, material("2. */*.pdf").read_bytes())
    if doc.blocks:  # text layer present
        assert doc.blocks[0].page == 1 and all(b.page for b in doc.blocks)


def test_image_has_no_blocks():
    doc = extract(FileKind.PNG, material("2. */*.png").read_bytes())
    assert doc.images and not doc.blocks and doc.as_dict() == {"blocks": [], "candidates": []}


def test_prompt_lists_block_ids():
    prompt = build_user_prompt(build([("Imię: ____", None), ("Podpis", None)]))
    assert "[b1] Imię: ____" in prompt and "[b2] Podpis" in prompt


def test_old_specs_still_valid(nadplata_spec):
    assert nadplata_spec.block_roles == [] and nadplata_spec.referenced_blocks() == set()
    assert "blocks" in FormSpec.model_json_schema()["$defs"]["FieldSpec"]["properties"]


def test_coverage():
    doc = build([("Wniosek", None), ("Imię: ____", None), ("Uwagi: ____", None), ("Podpis ......", None)])
    spec = FormSpec(
        title="Wniosek",
        authority_name="Urząd Gminy X",
        pages=[
            PageSpec(
                title="Dane",
                sections=[
                    SectionSpec(
                        title="Dane", fields=[FieldSpec(label="Imię", kind=Kind.TEXT, blocks=["b2", "b9"])]
                    )
                ],
            )
        ],
        block_roles=[BlockRole(block="b1", role=Role.HEADING), BlockRole(block="b4", role=Role.SKIP)],
    )
    c = coverage(spec, doc)
    assert (c.blocks, c.referenced, c.candidates) == (4, 3, 3)
    assert c.unreferenced == ["b3"]
    assert c.candidates_without_field == ["b3"]
    assert c.unknown_refs == ["b9"]
    assert c.as_dict()["candidatesWithoutField"] == ["b3"]


def test_prompt_asks_roles_only_for_text_to_copy():
    """Roles for every block overflow the model context on big forms (form 8: 631 blocks)."""
    from autoformularz.llm import SYSTEM_PROMPT

    assert "TYLKO dla bloków" in SYSTEM_PROMPT
    assert "każdego pozostałego bloku" not in SYSTEM_PROMPT
    assert "Not for field labels" in FormSpec.model_json_schema()["properties"]["block_roles"]["description"]
