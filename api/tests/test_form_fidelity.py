"""Rules that keep the e-form to what the paper form asks (material 1 against its reference JSON): footnotes,
the letter-style header, fields without a source, renamed or shorter copies of a section, and a model
stuck repeating one field. All run without a model."""

import json

from conftest import material

from autoformularz.check import dedupe, drop_paper_only_fields
from autoformularz.document import build
from autoformularz.extract import docx_text, extract
from autoformularz.llm import Answer, LLMError, field_loop, salvage
from autoformularz.presort import apply, drop_ungrounded, presort
from autoformularz.spec import FieldSpec, FormSpec, Kind, PageSpec, Role, SectionSpec
from autoformularz.upload import validate_upload

# Material 1 as a PDF reads it: two-column header, the request, footnote marks and two footnotes.
FORM_1 = [
    "………………………………",
    "(data)",
    "Wnioskodawca: Adresat:",
    "………………………………….",
    "(imię i nazwisko/nazwa wnioskodawcy)                                   Wójt Gminy Elbląg",
    "…………………………............. ul. Browarna 85",
    "…………………………………. 82-300 Elbląg",
    "(adres)",
    "………………………………….",
    "(nr telefonu/adres e-mail)1)",
    "WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO",
    "Wnoszę o ustalenie numeru porządkowego budynkowi zlokalizowanemu",
    "w miejscowości……………….……………… przy ulicy1)……………….…………………",
    "nr ewidencyjny działki ……………w obrębie ………………………….……………………",
    "…………………………",
    "(podpis wnioskodawcy)2)",
    "1 ) Dane nieobowiązkowe.",
    "2 ) Podpis własnoręczny, a w przypadku składania wniosku w postaci elektronicznej: kwalifikowany podpis",
    "podpis osobisty albo podpis zaufany.",
]


def ids(d, *texts):
    by_text = {b.text: b.id for b in d.blocks}
    return [by_text[t] for t in texts]


def field(label, blocks, kind=Kind.TEXT, required=True, options=()):
    return FieldSpec(label=label, kind=kind, required=required, blocks=list(blocks), options=list(options))


def spec_of(*sections, title="Wniosek o ustalenie numeru porządkowego"):
    return FormSpec(
        title=title,
        authority_kind="organ",
        authority_name="Wójt Gminy Elbląg",
        pages=[PageSpec(title="Informacje o budynku", sections=list(sections))],
    )


def labels(spec):
    return [f.label for p in spec.pages for s in p.sections for f in s.fields]


# ---------------------------------------------------------------- presort


def test_footnotes_and_signature_lines_never_reach_the_model():
    d = build([(t, None) for t in FORM_1])
    p = presort(d)
    seen = {b.text for b in p.model_doc.blocks}
    for gone in FORM_1[14:]:  # signature line and label, both footnotes with the continuation line
        assert gone not in seen
    assert "(data)" not in seen
    assert "nr ewidencyjny działki ……………w obrębie ………………………….……………………" in seen


def test_header_columns_show_only_the_addressee_and_tell_a_company_may_apply():
    d = build([(t, None) for t in FORM_1])
    p = presort(d)
    texts = {b.text for b in p.model_doc.blocks}
    assert {"Wójt Gminy Elbląg", "ul. Browarna 85", "82-300 Elbląg"} <= texts
    assert p.entity  # "nazwa wnioskodawcy"


def test_optional_footnote_marks_only_the_marked_field():
    d = build([(t, None) for t in FORM_1])
    p = presort(d)
    town_street, plot = ids(d, FORM_1[12], FORM_1[13])
    model = spec_of(
        SectionSpec(
            title="Lokalizacja budynku",
            fields=[
                field("Miejscowość", [town_street], required=False),
                field("Ulica", [town_street], required=False),
                field("Numer ewidencyjny działki", [plot], required=False),
                field("Obręb", [plot], required=False),
            ],
        )
    )
    out = apply(model, p)
    required = {f.label: f.required for f in out.pages[0].sections[0].fields}
    assert required == {"Miejscowość": True, "Ulica": False, "Numer ewidencyjny działki": True, "Obręb": True}


def test_spreadsheet_marks_are_read_per_cell():
    rows = [
        "| WNIOSEK O USTALENIE NUMERU |",
        "| w miejscowości | przy ulicy1) |",
        "| 1) Dane nieobowiązkowe. |",
    ]
    p = presort(build([(t, None) for t in rows]))
    assert list(p.optional.values()) == [["przy ulicy"]]


def test_made_up_fields_are_dropped_and_real_ones_kept():
    d = build([(t, None) for t in FORM_1])
    p = presort(d)
    request, town_street, plot, line = ids(d, FORM_1[11], FORM_1[12], FORM_1[13], FORM_1[14])
    model = spec_of(
        SectionSpec(
            title="Dane budynku",
            fields=[
                field("Miejscowość", [town_street]),
                field("Ulica", [town_street]),
                field("Numer budynku", [town_street]),  # a third field on a line with two places
                field("Numer ewidencyjny działki", [plot]),
                field("Obręb", [plot]),
                field("Kod pocztowy", [line]),  # the signature line
            ],
        ),
        SectionSpec(title="Załączniki", fields=[field("Załączniki", [request], kind=Kind.FILE)]),
        SectionSpec(
            title="Rodzaj",
            fields=[
                field(
                    "Rodzaj wniosku", [request], Kind.SINGLE_CHOICE, options=["Ustalenie numeru porządkowego"]
                )
            ],
        ),
    )
    out = apply(model, p)
    out, _ = drop_paper_only_fields(out)
    assert labels(out) == ["Miejscowość", "Ulica", "Numer ewidencyjny działki", "Obręb"]


def test_grounding_keeps_short_labels_and_bare_lines():
    texts = {"b1": "NIP", "b2": "/ adres /", "b3": "……………………………"}
    pages = [
        PageSpec(
            title="Dane",
            sections=[
                SectionSpec(
                    title="Dane",
                    fields=[
                        field("NIP", ["b1"]),
                        field("Adres", ["b2"]),
                        field("Adres do korespondencji", ["b3"]),
                    ],
                )
            ],
        )
    ]
    assert len(drop_ungrounded(pages, texts)[0].sections[0].fields) == 3


# ---------------------------------------------------------------- canon


def test_renamed_and_shorter_copies_of_a_section_are_dropped():
    a = [field("Miejscowość", ["b13"]), field("Ulica", ["b13"]), field("Obręb", ["b14"])]
    spec = spec_of(
        SectionSpec(title="Lokalizacja budynku", fields=a),
        SectionSpec(title="Informacje o budynku", fields=a),
        SectionSpec(title="Dane o budynku", fields=a[2:]),
        SectionSpec(title="Inna", fields=[field("Ulica", ["b40"])]),  # same label, other source: kept
    )
    out, notes = dedupe(spec)
    assert [s.title for s in out.pages[0].sections] == ["Lokalizacja budynku", "Inna"]
    assert len(notes) == 2


def test_field_restating_the_title_is_dropped():
    spec = spec_of(
        SectionSpec(
            title="Informacje", fields=[field("Wniosek o ustalenie numeru porządkowego budynku", ["b1"])]
        )
    )
    out, notes = drop_paper_only_fields(spec)
    assert not out.pages and notes


# ---------------------------------------------------------------- model stuck on one field

HEAD = '{"title": "Wniosek", "authority_kind": "organ", "authority_name": "Wójt", "block_roles": [], "pages": [{"title": "Budynek", "sections": [{"title": "Lokalizacja", "fields": ['


def answer_field(label, blocks):
    return json.dumps(
        {"label": label, "kind": "TEXT", "required": True, "blocks": blocks}, ensure_ascii=False
    )


def test_a_field_loop_stops_the_stream_and_keeps_each_field_once():
    good = [answer_field("Miejscowość", ["b13"]), answer_field("Obręb", ["b14"])]
    text = HEAD + ", ".join(good + [answer_field("Numer porządkowy", ["b15"])] * 20)
    answer = Answer()
    stopped = None
    try:
        for i in range(0, len(text), 50):
            answer.add(text[i : i + 50])
    except LLMError as e:
        stopped = e
    assert stopped is not None and answer.size < len(text) / 2
    spec = salvage(stopped.partial)
    assert labels(spec) == ["Miejscowość", "Obręb", "Numer porządkowy"]


def test_table_rows_with_one_label_are_not_a_loop():
    rows = [answer_field("Wysokość opłaty", [f"b{i}"]) for i in range(30, 40)]
    assert field_loop(HEAD + ", ".join(rows)) is None


# ---------------------------------------------------------------- DOCX footnotes


def test_docx_footnotes_get_numbers_and_text():
    data = material("1. */Wniosek o ustalenie numeru porządkowego nieruchomości.docx").read_bytes()
    text = docx_text(data)
    assert "(nr telefonu/adres e-mail)1)" in text
    assert "1) Dane nieobowiązkowe." in text
    assert "2) Podpis własnoręczny" in text


def test_docx_without_footnotes_reads_as_before():
    data = material("2. */Wniosek o zwrot opłaty skarbowej.docx").read_bytes()
    text = docx_text(data)
    assert text and not text.splitlines()[-1].startswith("1)")


def test_material_1_reads_the_same_in_every_text_format():
    found = {}
    for ext in ("pdf", "docx", "doc", "ods", "xlsx"):
        name = f"Wniosek o ustalenie numeru porządkowego nieruchomości.{ext}"
        data = material(f"1. */{name}").read_bytes()
        p = presort(extract(validate_upload(name, data, 50 * 2**20), data))
        found[ext] = (p.entity, tuple(sorted(w for words in p.optional.values() for w in words)))
        skipped = {b for r in p.roles if r.role is Role.SKIP for b in r.ids()}
        assert skipped, ext
    assert set(found.values()) == {(True, ("adres e mail", "przy ulicy"))}, found


def test_pesel_only_when_the_paper_asks():
    for pattern, asks in (
        ("1. */*porządkowego nieruchomości.pdf", False),
        ("5. */*nadpłaty podatku.PDF", True),
    ):
        path = material(pattern)
        data = path.read_bytes()
        p = presort(extract(validate_upload(path.name, data, 50 * 2**20), data))
        assert p.pesel is asks, pattern


# ---------------------------------------------------------------- template tail, statements first


def test_statements_come_before_pages_in_the_model_schema():
    from autoformularz.spec import model_schema

    keys = list(model_schema()["properties"])
    assert keys.index("consents") < keys.index("pages")


def test_template_sections_after_the_form_stop_the_stream():
    def section(title, label):
        return json.dumps({"title": title, "fields": [{"label": label, "kind": "TEXT", "required": True}]})

    own = [section("Opłata skarbowa", "Kwota"), section("Uzasadnienie", "Uzasadnienie")]
    # Long enough to pass a check point (every REPEAT_CHECK_CHARS characters) after the tail began.
    tail = [
        section(t, f"{t} wnioskodawcy")
        for t in ("Dane kontaktowe", "Podpis", "Data", "Podgląd", "Podpis", "Data")
    ] * 3
    head = '{"title": "Wniosek", "authority_kind": "organ", "authority_name": "Wójt", "consents": ["Znam regulamin"], "pages": [{"title": "Opłata", "sections": ['
    text = head + ", ".join(own + tail) + "]}]}"
    answer = Answer()
    stopped = None
    try:
        for i in range(0, len(text), 40):
            answer.add(text[i : i + 40])
    except LLMError as e:
        stopped = e
    assert stopped is not None
    spec = salvage(stopped.partial)
    assert spec.consents == ["Znam regulamin"]
    out, _ = drop_paper_only_fields(spec)
    titles = [s.title for p in out.pages for s in p.sections]
    assert titles[:2] == ["Opłata skarbowa", "Uzasadnienie"] and "Podpis" not in titles


def test_scan_of_material_1_keeps_street_and_precinct():
    """OCR's second (sparse) pass restores the words after dotted leaders, as the PDF reads them."""
    import subprocess

    import pytest

    from autoformularz.config import Settings
    from autoformularz.ocr import ocr_from

    s = Settings()
    ocr = ocr_from(s.ocr_bin, s.ocr_lang, s.tessdata_dir)
    if ocr is None:
        pytest.skip("brak Tesseracta")
    langs = [ocr.binary, "--list-langs"] + (["--tessdata-dir", ocr.tessdata_dir] if ocr.tessdata_dir else [])
    if "pol" not in subprocess.run(langs, capture_output=True, text=True).stdout.split():
        pytest.skip("brak polskiego modelu Tesseracta (pol.traineddata)")
    path = material("1. */Wniosek o ustalenie numeru porządkowego nieruchomości.jpg")
    data = path.read_bytes()
    p = presort(extract(validate_upload(path.name, data, 50 * 2**20), data, ocr=ocr))
    seen = " ".join(b.text for b in p.model_doc.blocks)
    assert "przy ulicy" in seen and "w obrębie" in seen
    assert p.entity
    assert ["przy ulicy"] in p.optional.values()  # OCR's quote for the raised "1)"
