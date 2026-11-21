"""Document contract (docs/pipeline.md, "Kontrakt"): blocks with IDs, field candidates, coverage."""

import pytest
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
    texts = lambda text: [c.text for c in find_candidates(Block("b1", text))]  # noqa: E731
    assert texts("Miejscowość: Kod pocztowy:") == ["Miejscowość:", "Kod pocztowy:"]  # form 7
    assert texts("| Nr domu: Nr lokalu: | Ulica: |") == ["Nr domu:", "Nr lokalu:", "Ulica:"]
    assert kinds("Płeć: ❑ pies ❑ suka") == ["checkbox", "checkbox"]  # value after colon: not a label
    assert kinds("Godziny pracy 8:00") == [] and kinds("1:") == []
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


def test_dedupe_drops_a_models_repetitions(nadplata_spec):
    """Form 2 on Eden repeated the page 'Dane wnioskodawcy' 5 times and 'Miejscowość' 10 times."""
    from autoformularz.check import dedupe

    f = lambda label: FieldSpec(label=label, kind=Kind.TEXT)  # noqa: E731
    address = SectionSpec(title="Adres", fields=[f("Miejscowość"), f("Ulica"), f("Miejscowość")])
    page = PageSpec(title="Dane wnioskodawcy", sections=[address])
    other = PageSpec(title="Opłata", sections=[SectionSpec(title="Opłata", fields=[f("Kwota")]), address])
    spec = FormSpec(title="Wniosek", authority_name="Urząd", pages=[page, page, other, page])
    clean, notes = dedupe(spec)
    assert [p.title for p in clean.pages] == ["Dane wnioskodawcy", "Opłata"]
    assert [x.label for x in clean.pages[0].sections[0].fields] == ["Miejscowość", "Ulica"]
    assert [s.title for s in clean.pages[1].sections] == ["Opłata"]  # repeated section dropped
    assert notes[0] == "Pominięto powtórzone pole „Miejscowość” w sekcji „Adres”."
    assert "Pominięto powtórzoną stronę „Dane wnioskodawcy”." in notes
    assert dedupe(nadplata_spec) == (nadplata_spec, [])  # a correct spec is left as it is


def test_schema_bounds_lists():
    schema = FormSpec.model_json_schema()
    assert schema["properties"]["pages"]["maxItems"] == 10
    assert schema["$defs"]["SectionSpec"]["properties"]["fields"]["maxItems"] == 40


def test_standard_sections_are_left_to_the_compiler(nadplata_spec):
    """Form 2 on Eden: the model copied 'Dane pełnomocnika' etc. although the compiler adds them.
    A section goes only when its title is about the applicant/proxy/contact AND its fields are personal,
    address or contact data; statements or subject data with such words in the title stay."""
    from autoformularz.check import drop_standard_sections

    def sec(title, *labels):
        return SectionSpec(title=title, fields=[FieldSpec(label=x, kind=Kind.TEXT) for x in labels])

    address = ("Miejscowość", "Ulica", "Nr domu", "Kod pocztowy")
    statements = sec("Oświadczenia wnioskodawcy", "Psy nie będą wykorzystywane do polowań")
    spec = FormSpec(
        title="Wniosek",
        authority_name="Urząd",
        pages=[
            PageSpec(
                title="Dane wnioskodawcy",
                sections=[
                    sec("Dane identyfikacyjne", "Nazwa / Imię i nazwisko", "NIP"),
                    sec("Dane pełnomocnika", *address),
                ],
            ),
            PageSpec(
                title="Pies",
                sections=[
                    sec(
                        "Miejsce utrzymywania psa", *address
                    ),  # subject data: title is not about the applicant
                    sec("Dane kontaktowe wnioskodawcy", "Telefon", "Adres e-mail"),
                    statements,
                    sec("Dane wnioskodawcy", "Imię i nazwisko", "Opis doświadczenia w hodowli psów"),  # 50%
                    sec("Osoba do kontaktu w sprawie najmu", "Imię i nazwisko", "Telefon"),  # subject data
                ],
            ),
        ],
    )
    clean, notes = drop_standard_sections(spec)
    assert [(p.title, [s.title for s in p.sections]) for p in clean.pages] == [
        (
            "Pies",
            [
                "Miejsce utrzymywania psa",
                "Oświadczenia wnioskodawcy",
                "Dane wnioskodawcy",
                "Osoba do kontaktu w sprawie najmu",
            ],
        )
    ]
    assert notes[0] == "Sekcja „Dane identyfikacyjne” jest w części standardowej formularza (pominięta)."
    assert drop_standard_sections(nadplata_spec) == (nadplata_spec, [])


@pytest.mark.parametrize(
    ("label", "standard"),
    [
        ("Imię i nazwisko lub nazwa firmy", True),  # form 6
        ("Adres zamieszkania/siedziby", True),  # form 6
        ("Adres poczty elektronicznej", True),
        ("Nr lokalu", True),
        ("PESEL", True),
        ("Telefon:", True),
        ("Rasa psa", False),
        ("Data urodzenia psa", False),
        ("Adres miejsca utrzymywania psa", False),
        ("Imię i nazwisko poprzedniego właściciela psa", False),
    ],
)
def test_standard_labels(label, standard):
    from autoformularz.check import is_standard_label

    assert is_standard_label(label) is standard


def test_applicant_ids_mean_a_company_may_apply():
    """Form 2: 'Nazwa / Imię i nazwisko' + NIP in the applicant section, model said entity=false."""
    from autoformularz.check import drop_standard_sections

    def spec_with(*labels):
        fields = [FieldSpec(label=label, kind=Kind.TEXT) for label in labels]
        page = PageSpec(
            title="Dane wnioskodawcy", sections=[SectionSpec(title="Dane identyfikacyjne", fields=fields)]
        )
        rest = PageSpec(
            title="Opłata",
            sections=[SectionSpec(title="Opłata", fields=[FieldSpec(label="Kwota", kind=Kind.NUMBER)])],
        )
        return FormSpec(title="Wniosek", authority_name="Urząd", pages=[page, rest])

    clean, notes = drop_standard_sections(spec_with("Nazwa / Imię i nazwisko", "NIP"))
    assert (clean.applicant.entity, clean.applicant.entity_nip_only) == (True, True)
    assert notes[-1] == "Formularz pyta o NIP wnioskodawcy: wnioskodawcą może być firma lub instytucja."
    clean, _ = drop_standard_sections(spec_with("Nazwa", "NIP", "REGON", "Numer KRS"))
    assert (clean.applicant.entity, clean.applicant.entity_nip_only) == (True, False)
    clean, _ = drop_standard_sections(spec_with("Imię i nazwisko", "PESEL"))
    assert clean.applicant.entity is False
