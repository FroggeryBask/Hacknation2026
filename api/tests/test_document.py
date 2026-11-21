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
    assert "[b1] Imię: ……" in prompt and "[b2] Podpis" in prompt  # the line to fill in, shortened


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


def test_table_rows_with_the_same_label_are_not_repetitions():
    """Material 8: "Wysokość miesięcznej opłaty" once per flat size, each from its own row of the table."""
    from autoformularz.check import dedupe

    f = lambda label, *blocks: FieldSpec(label=label, kind=Kind.NUMBER, blocks=list(blocks))  # noqa: E731
    rows = [f("Liczba do 45 m²", "b1"), f("Wysokość opłaty", "b2"), f("Liczba ponad 45 m²", "b3")]
    rows += [f("Wysokość opłaty", "b4"), f("Wysokość opłaty", "b4")]  # the last one is a real repetition
    spec = FormSpec(
        title="Deklaracja",
        authority_name="Urząd",
        pages=[PageSpec(title="Opłata", sections=[SectionSpec(title="Obliczenie", fields=rows)])],
    )
    clean, notes = dedupe(spec)
    assert [x.blocks for x in clean.pages[0].sections[0].fields] == [["b1"], ["b2"], ["b3"], ["b4"]]
    assert len(notes) == 1


def test_applicant_section_keeps_its_other_questions():
    """Material 8: who files the declaration (owner, tenant, …) stays; name, PESEL, NIP/REGON go to the
    predefined part. An applicant address with a plot number keeps only the plot number."""
    from autoformularz.check import drop_standard_sections

    f = lambda label, kind=Kind.TEXT: FieldSpec(label=label, kind=kind)  # noqa: E731
    who = SectionSpec(
        title="Dane identyfikacyjne składającego deklarację",
        fields=[
            f("Składający deklarację", Kind.SINGLE_CHOICE),
            f("Nazwisko, imię / Nazwa pełna"),
            f("PESEL"),
            f("NIP/REGON"),
        ],
    )
    address = SectionSpec(
        title="Adres zamieszkania / siedziby",
        fields=[
            f("Kraj"),
            f("Miejscowość"),
            f("Ulica"),
            f("Numer nieruchomości/domu"),
            f("Kod pocztowy"),
            f("Numer/y działki/działek"),
        ],
    )
    proxy = SectionSpec(  # one standard field among proxy data: stays whole
        title="Dane pełnomocnika klubu",
        fields=[f("Imię pełnomocnika"), f("Nazwisko pełnomocnika"), f("Seria i numer dowodu osobistego")],
    )
    spec = FormSpec(
        title="Deklaracja",
        authority_name="Urząd",
        pages=[PageSpec(title="Dane", sections=[who, address, proxy])],
    )
    clean, notes = drop_standard_sections(spec)
    kept = {s.title: [x.label for x in s.fields] for s in clean.pages[0].sections}
    assert kept == {
        "Dane identyfikacyjne składającego deklarację": ["Składający deklarację"],
        "Adres zamieszkania / siedziby": ["Numer/y działki/działek"],
        "Dane pełnomocnika klubu": [
            "Imię pełnomocnika",
            "Nazwisko pełnomocnika",
            "Seria i numer dowodu osobistego",
        ],
    }
    assert clean.applicant.entity  # NIP/REGON was asked
    assert len(notes) == 3


def test_broken_conditions_are_removed_and_fields_become_optional():
    from autoformularz.check import drop_broken_conditions
    from autoformularz.spec import Condition

    choice = FieldSpec(label="Dyscyplina", kind=Kind.SINGLE_CHOICE, options=["hokej", "Inna"])
    ok = FieldSpec(label="Jaka", kind=Kind.TEXT, show_if=Condition(field="dyscyplina", equals="INNA"))
    bad_option = FieldSpec(label="Opis", kind=Kind.TEXT, show_if=Condition(field="Dyscyplina", equals="Brak"))
    guarded = SectionSpec(
        title="Adres do korespondencji",
        show_if=Condition(field="Nie ma takiego pola", equals="TAK"),
        fields=[FieldSpec(label="Ulica", kind=Kind.TEXT)],
    )
    spec = FormSpec(
        title="Wniosek",
        authority_name="Urząd",
        pages=[
            PageSpec(title="S", sections=[SectionSpec(title="A", fields=[choice, ok, bad_option]), guarded])
        ],
    )
    clean, notes = drop_broken_conditions(spec)
    a, b = clean.pages[0].sections
    assert a.fields[1] == ok  # a working condition (case ignored, like the compiler) is kept
    assert a.fields[2].show_if is None and a.fields[2].required is False
    assert b.show_if is None and b.fields[0].required is False
    assert len(notes) == 2
    assert drop_broken_conditions(clean) == (clean, [])


def test_printed_amounts_become_info():
    from autoformularz.check import printed_amounts_as_info

    rate = FieldSpec(label="Stawka opłaty", kind=Kind.TEXT, description="38 zł")
    relief = FieldSpec(label="Stawka zwolnienia", kind=Kind.TEXT, description="- 15 zł 00 gr")
    count = FieldSpec(label="Liczba gospodarstw", kind=Kind.NUMBER, description="Wpisz liczbę")
    spec = FormSpec(
        title="Deklaracja",
        authority_name="Urząd",
        pages=[PageSpec(title="Opłata", sections=[SectionSpec(title="E.1", fields=[count, rate, relief])])],
    )
    clean, notes = printed_amounts_as_info(spec)
    out = clean.pages[0].sections[0].fields
    assert out[0] == count
    assert (out[1].kind, out[1].description) == (Kind.INFO, "Stawka opłaty: 38 zł")
    assert (out[2].kind, out[2].description) == (Kind.INFO, "Stawka zwolnienia: - 15 zł 00 gr")
    assert len(notes) == 2


KINDS = ["Stypendium", "Nagroda", "Wyróżnienie"]


def kinds_spec(*sections):
    choice = FieldSpec(label="Rodzaj wniosku", kind=Kind.SINGLE_CHOICE, options=KINDS)
    first = PageSpec(title="Rodzaj", sections=[SectionSpec(title="Rodzaj", fields=[choice])])
    return FormSpec(
        title="Wniosek",
        authority_name="Urząd",
        pages=[first, PageSpec(title="Dane", sections=list(sections))],
    )


def shown_for(spec, title):
    s = next(x for p in spec.pages for x in p.sections if x.title == title)
    if s.show_if is None:
        return set(KINDS)
    return set(KINDS) - {s.show_if.equals} if s.show_if.negate else {s.show_if.equals}


def test_dedupe_merges_conditions_of_copies():
    """Form 9: "Dyscypliny sportowe" once per kind of request; keeping the first copy left the other kinds
    without it (the "Nagroda" form was empty)."""
    from autoformularz.check import dedupe
    from autoformularz.spec import Condition

    def copy(title, kind):
        return SectionSpec(
            title=title,
            fields=[FieldSpec(label="Dyscyplina", kind=Kind.TEXT)],
            show_if=Condition(field="Rodzaj wniosku", equals=kind),
        )

    clean, _ = dedupe(kinds_spec(copy("Dyscypliny", "Stypendium"), copy("Dyscypliny", "Nagroda")))
    assert shown_for(clean, "Dyscypliny") == {"Stypendium", "Nagroda"}  # Wyróżnienie excluded: negate
    clean, _ = dedupe(kinds_spec(*(copy("Dyscypliny", k) for k in KINDS)))
    assert clean.pages[1].sections[0].show_if is None  # all kinds: always shown
    always = SectionSpec(title="Dyscypliny", fields=[FieldSpec(label="Dyscyplina", kind=Kind.TEXT)])
    clean, _ = dedupe(kinds_spec(copy("Dyscypliny", "Nagroda"), always))
    assert clean.pages[1].sections[0].show_if is None
