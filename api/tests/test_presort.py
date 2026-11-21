"""Presort: the code recognises the GDPR clause, paper-only lines and the template's applicant data.

Wording varies between forms (and OCR drops Polish letters), so the cases below use several versions of
the same thing. A block with a place to fill in that belongs to the case itself must always reach the model."""

import json
from pathlib import Path

import pytest
from conftest import material

from autoformularz import pipeline
from autoformularz.config import Settings
from autoformularz.document import build
from autoformularz.extract import extract
from autoformularz.llm import build_user_prompt
from autoformularz.presort import apply, is_paper_only, is_standard_label, presort
from autoformularz.results import source_file
from autoformularz.spec import MAX_ROLES, FormSpec, Role
from autoformularz.upload import validate_upload

WYNIKI = Path(__file__).resolve().parents[2] / "wyniki"


def doc(*lines: str):
    return build([(t, None) for t in lines])


def roles(*lines: str) -> dict[str, str]:
    """Block text -> role given by the code (blocks for the model are left out)."""
    d = doc(*lines)
    p = presort(d)
    by_id = {bid: r.role.value for r in p.roles for bid in r.ids()}
    return {b.text: by_id[b.id] for b in d.blocks if b.id in by_id}


# ---------------------------------------------------------------- GDPR


@pytest.mark.parametrize(
    "start",
    [
        "Zgodnie z art. 13 ust. 1 i 2 rozporządzenia Parlamentu Europejskiego i Rady (UE) 2016/679 z dnia 27 kwietnia 2016 r.",
        "KLAUZULA INFORMACYJNA",
        "Informacja o przetwarzaniu danych osobowych",
        "INFORMACJE DOTYCZĄCE PRZETWARZANIA TWOICH DANYCH OSOBOWYCH",
        "Administratorem Pani/Pana danych osobowych jest Wójt Gminy X.",
        "Klauzula informacyjna RODO",
        "ZGODNIE Z ART. 13 RODO INFORMUJEMY",
        "Administratorem Panstwa danych osobowych jest Burmistrz",  # OCR without Polish letters
    ],
)
def test_gdpr_clause_starts(start):
    r = roles(
        "Wniosek o wydanie zezwolenia",
        start,
        "Pani/Pana dane osobowe przetwarzane będą w celu wydania zezwolenia.",
        "Przysługuje Pani/Panu prawo dostępu do danych oraz ich sprostowania.",
    )
    assert "Wniosek o wydanie zezwolenia" not in r
    assert set(r.values()) == {"GDPR"} and len(r) == 3


def test_gdpr_run_covers_broken_lines_and_stops_at_consent():
    r = roles(
        "Informacja o przetwarzaniu danych osobowych",
        "1. Administratorem Pani/Pana danych osobowych jest Prezydent Miasta Gdyni z siedzibą przy al. Marsz.",
        "Piłsudskiego 52/54, 81-382 Gdynia.",  # a broken line without clause words
        "a) listownie: Al. Marsz. Piłsudskiego 52/54",
        "2. Administrator powołał inspektora ochrony danych.",
        "Wyrażam zgodę na przetwarzanie moich danych osobowych w celu kontaktu.",  # consent: for the model
        "Adres e-mail do kontaktu ………………",
    )
    assert r == {
        "Informacja o przetwarzaniu danych osobowych": "GDPR",
        "1. Administratorem Pani/Pana danych osobowych jest Prezydent Miasta Gdyni z siedzibą przy al. Marsz.": "GDPR",
        "Piłsudskiego 52/54, 81-382 Gdynia.": "GDPR",
        "a) listownie: Al. Marsz. Piłsudskiego 52/54": "GDPR",
        "2. Administrator powołał inspektora ochrony danych.": "GDPR",
    }


def test_text_about_personal_data_outside_a_clause_stays():
    r = roles("Dane osobowe kandydata do stypendium", "Imię ………", "Nazwisko ………", "Data urodzenia ………")
    assert r == {}


# ---------------------------------------------------------------- paper-only lines


@pytest.mark.parametrize(
    "text",
    [
        "(czytelny podpis wnioskodawcy)",
        "/podpis/",
        "……………………………… /podpis/",
        "/ podpis Wnioskodawcy/",
        "Podpis i pieczątka wnioskodawcy",
        "Podpis i pieczatka wnioskodawcy",  # OCR
        "podpis wnioskodawcy lub osoby upoważnionej",
        "Data Podpis rodzica/opiekuna prawnego",
        "76. Data wypełnienia 77. Podpis składającego deklarację / osoby reprezentującej",
        "78. Podpis współmałżonka (wypełnić tylko w przypadku zaznaczenia poz. B 1.1.2)",
        "81. Podpis i pieczęć przyjmującego deklarację",
        "(miejscowość i data)",
        "Młynary, dnia…………………….",
        "……………………….dnia………………………",
        "Miejsce na pieczęć Urzędu",
        "/wypełnia organ/",
        "WYPEŁNIA URZĄD",
        "79. Data wpływu do organu 80. Uwagi",
        "WYPEŁNIJ WIELKIMI LITERAMI.",
        "Wypełniaj kolorem czarnym lub niebieskim.",
        "Wniosek należy wypełnić czytelnie, drukowanymi literami.",
        "Pola wyboru oznaczaj",
        "1. Instrukcja wypełnienia dokumentu",
        "strona 1/2",
        "Strona 2 z 3",
        "1/6",
    ],
)
def test_paper_only(text):
    assert is_paper_only(text)


@pytest.mark.parametrize(
    "text",
    [
        "Data urodzenia",
        "Data uiszczenia opłaty",
        "Data wypełnienia",  # may be a date field of the case: the model decides
        "Data",
        "Uwagi",
        "Zaświadczenie potrzebne jest celem przedłożenia w ………………",
        "Okres wynajmu od ……… do ………",
        "Dane osobowe podopiecznego trenera",
    ],
)
def test_not_paper_only(text):
    assert not is_paper_only(text)


def test_split_instruction_line_goes_whole():
    r = roles(
        "1. Instrukcja wypełnienia dokumentu",
        "1.",
        "WYPEŁNIJ WIELKIMI LITERAMI.",
        "2.",
        "Pola wyboru oznaczaj",
        "lub",
        ".",
        "3.",
        "Wypełniaj kolorem czarnym lub niebieskim.",
        "3. Informacje o opłacie",
    )
    assert len(r) == 9 and set(r.values()) == {"SKIP"}


def test_line_to_fill_in_above_a_signature_stays():
    r = roles("Zaświadczenie potrzebne jest celem przedłożenia w", "………………………………………", "……… /podpis/")
    assert r == {"……… /podpis/": "SKIP"}


# ---------------------------------------------------------------- applicant / proxy / contact


@pytest.mark.parametrize(
    "label",
    [
        "Nazwa /Imię i nazwisko",
        "(imię i nazwisko wnioskodawcy)",
        "/ adres /",
        "nr telefonu i e-mail",
        "3. PESEL 4. NIP/REGON (dot. tylko osób prawnych)",
        "| Ulica: | Nr domu: | Nr lokalu: |",
        "Imię ……………………",
        "Telefon kontaktowy (opcjonalnie) ……",
        "PESEL *………………",
        "adres zamieszkania/siedziba firmy",
        "Adres poczty elektronicznej",
        "Nazwisko i imie",  # OCR
    ],
)
def test_standard_labels(label):
    assert is_standard_label(label)


@pytest.mark.parametrize(
    "label",
    ["Nazwa klubu sportowego", "Adres nieruchomości", "Numer działki", "Rasa psa", "Data urodzenia", "Kwota"],
)
def test_case_labels(label):
    assert not is_standard_label(label)


def test_applicant_section_with_subsections():
    r = roles(
        "2. Dane wnioskodawcy",
        "2.1. Dane identyfikacyjne",
        "Nazwa /Imię i nazwisko",
        "NIP",
        "2.2. Adres siedziby lub miejsca zamieszkania wnioskodawcy",
        "Miejscowość",
        "Kod pocztowy",
        "-",
        "2.3. Dane kontaktowe wnioskodawcy (dane kontaktowe nie są obowiązkowe,",
        "ale ułatwią kontakt)",
        "Numer telefonu",
        "2.4. Dane pełnomocnika",
        "Imię i nazwisko",
        "3. Informacje o opłacie skarbowej",
        "Kwota opłaty",
    )
    assert "3. Informacje o opłacie skarbowej" not in r and "Kwota opłaty" not in r
    assert r["2. Dane wnioskodawcy"] == "HEADING" and r["NIP"] == "FIELD_LABEL" and len(r) == 13


def test_section_ends_at_case_data():
    """A section about the applicant ends at the first block that is not template data."""
    r = roles("1. Wnioskodawca", "Klub sportowy", "Imię ………", "Nazwisko ………", "2. Dane sportowca", "Imię ………")
    assert r == {}


def test_spouse_and_case_people_stay():
    r = roles("B.2 DANE IDENTYFIKACYJNE WSPÓŁMAŁŻONKA", "5. Nazwisko, imię", "7. PESEL")
    assert r == {}
    r = roles("Dane osobowe kandydatki/kandydata do wyróżnienia", "Imię ………", "Nazwisko ………")
    assert r == {}


def test_letter_header_and_entity_hint():
    d = doc(
        "Ulan-Majorat, dnia……",
        "Wnioskodawca:",
        "………………",
        "Nazwisko i imię/Nazwa firmy",
        "………………",
        "adres zamieszkania/siedziba firmy",
        "PESEL *………",
        "NIP * ………",
        "Urząd Gminy",
        "Ulan-Majorat",
        "Wniosek o stwierdzenie nadpłaty podatku",
        "Kwota nadpłaty ………",
    )
    p = presort(d)
    left = [b.text for b in p.model_doc.blocks]
    assert left == [
        "Urząd Gminy",
        "Ulan-Majorat",
        "Wniosek o stwierdzenie nadpłaty podatku",
        "Kwota nadpłaty ………",
    ]
    assert p.entity and p.nip_only  # like reference form 5 (entity_nip_only)


# ---------------------------------------------------------------- the step in the pipeline


def test_prompt_leaves_out_recognised_blocks_and_says_so():
    d = doc(
        "Wniosek o zwrot opłaty",
        "Kwota ………",
        "Klauzula informacyjna",
        "Administratorem Pani/Pana danych osobowych jest Wójt.",
        "(czytelny podpis wnioskodawcy)",
    )
    p = presort(d)
    prompt = build_user_prompt(p.model_doc)
    assert (
        "[b2] Kwota" in prompt
        and "Administratorem" not in prompt
        and "podpis" not in prompt.split("Kod już")[0]
    )
    assert "klauzula RODO" in prompt and "podpisy" in prompt


def test_apply_adds_code_roles_and_code_wins(nadplata_spec):
    from autoformularz.spec import BlockRole

    d = doc("Wniosek", "Klauzula informacyjna", "Administratorem danych osobowych jest Wójt.", "Kwota ………")
    p = presort(d)
    model = nadplata_spec.model_copy(
        update={
            "block_roles": [
                BlockRole(block="b2", role=Role.INSTRUCTION),
                BlockRole(block="b4", role=Role.SKIP),
            ]
        }
    )
    out = apply(model, p)
    assert out.roles() == {"b2": Role.GDPR, "b3": Role.GDPR, "b4": Role.SKIP}


def test_presort_off_sends_the_whole_document():
    d = doc("Wniosek", "Klauzula informacyjna", "(czytelny podpis wnioskodawcy)")
    seen = {}

    def fake(document, _):
        seen["n"] = len(document.blocks)
        return FormSpec(title="Wniosek", authority_name="Urząd", pages=[])

    pipeline.ask_model(d, Settings(_env_file=None, presort=False), fake)
    assert seen["n"] == 3
    pipeline.ask_model(d, Settings(_env_file=None), fake)
    assert seen["n"] == 1


@pytest.mark.parametrize("ext", ["docx", "pdf", "xlsx"])
def test_big_forms_shrink_and_roles_fit(ext):
    path = material(f"8. */*.{ext}")
    data = path.read_bytes()
    d = extract(validate_upload(path.name, data, 50 << 20), data)
    p = presort(d)
    assert p.counts.get("GDPR", 0) >= 25  # the information clause of form 8
    assert len(build_user_prompt(p.model_doc)) < 0.8 * len(build_user_prompt(d))
    assert len(p.roles) <= 40  # ranges: far below MAX_ROLES even with the model's own roles
    assert len(p.roles) < MAX_ROLES


@pytest.mark.parametrize("n", [2, 3, 4, 6, 7, 8, 9])
def test_saved_results_keep_their_case_fields(n):
    """No block the code removes was used by a field of a saved, checked result (after canon)."""
    spec_path = WYNIKI / f"{n:02d}.spec.json"
    if not spec_path.exists():
        pytest.skip("no saved result")
    src = source_file(n)
    data = src.read_bytes()
    try:
        d = extract(validate_upload(src.name, data, 50 << 20), data)
    except Exception as e:  # .doc needs LibreOffice
        pytest.skip(str(e))
    removed = {bid for r in presort(d).roles for bid in r.ids()}
    spec = pipeline.from_spec(FormSpec.model_validate(json.loads(spec_path.read_text(encoding="utf-8")))).spec
    used = {bid for page in spec.pages for s in page.sections for f in s.fields for bid in f.blocks}
    assert not used & removed


# ---------------------------------------------------------------- clause shapes, spreadsheets, form 8


def test_gdpr_hole_inside_one_clause_is_filled():
    """Form 8: legal bases and ePUAP lines without clause words between two parts of the clause."""
    r = roles(
        "Informacja o przetwarzaniu danych osobowych",
        "3. Będziemy przetwarzać Pani/Pana dane osobowe na podstawie art. 6 ust. 1 lit. c RODO w",
        "związku z przepisami ustawy z dnia 13 września 1996r. o utrzymaniu czystości i porządku w gminach,",
        "ustawy z dnia 8 marca 1990r. o samorządzie gminnym oraz uchwały nr XIV/478/19 Rady Miasta",
        "komunalnymi ze zmianami.",
        "W przypadku przekazania niniejszej deklaracji za pomocą środków komunikacji elektronicznej (ePUAP)",
        "usług drogą elektroniczną oraz przepisami ustawy z dnia 18 listopada 2020 r. o doręczeniach",
        "elektronicznych.",
        "kontaktu na podstawie Pani/Pana zgody (art. 6 ust. 1 lit. a RODO).",
        "4. Odbiorcami Pana/Pani danych osobowych mogą być:",
    )
    assert len(r) == 10 and set(r.values()) == {"GDPR"}


def test_gdpr_hole_with_a_case_question_stays():
    r = roles(
        "Klauzula informacyjna",
        "Administratorem danych osobowych jest Wójt.",
        "Wyrażam zgodę na kontakt telefoniczny.",
        "Telefon ………",
        "Administrator powołał inspektora ochrony danych.",
    )
    assert "Wyrażam zgodę na kontakt telefoniczny." not in r and "Telefon ………" not in r


def test_numbered_clause_section_ends_at_next_section():
    """Form 9: "4. Klauzula informacyjna" with points a), b) without clause words, then "5. Zgody"."""
    r = roles(
        "4. Klauzula informacyjna",
        "Informacje na temat ochrony danych osobowych stosowanych przez administratora danych:",
        "a) klub sportowy – znajdują się na jego stronie internetowej;",
        "b) Prezydent Miasta – znajdują się na stronie podmiotowej BIP.",
        "5. Zgody",
        "5.1. Zgoda kandydata pełnoletniego do stypendium",
    )
    assert len(r) == 4 and "5. Zgody" not in r


def test_spreadsheet_rows_read_like_docx():
    """ODS/XLSX: one-cell rows "| 2. Dane wnioskodawcy |" and a "-" separator cell."""
    r = roles(
        "| Wniosek o zwrot opłaty skarbowej |",
        "| 2. Dane wnioskodawcy |",
        "| 2.1. Dane identyfikacyjne |",
        "| Nazwa /Imię i nazwisko |",
        "| NIP |",
        "| Nr domu | Nr lokalu | Kod pocztowy | - |",
        "| 2.3. Dane kontaktowe wnioskodawcy (dane kontaktowe nie są obowiązkowe, ale ułatwią kontakt w sprawie wniosku) |",
        "| Numer telefonu |",
        "| 3. Informacje o opłacie skarbowej |",
        "| Wysokość opłaty |",
    )
    assert r["| 2. Dane wnioskodawcy |"] == "HEADING" and r["| Numer telefonu |"] == "FIELD_LABEL"
    assert "| 3. Informacje o opłacie skarbowej |" not in r and "| Wysokość opłaty |" not in r


def test_address_and_contact_subsections_of_form_8():
    r = roles(
        "B.2 DANE IDENTYFIKACYJNE WSPÓŁMAŁŻONKA (wypełnić tylko w przypadku zaznaczenia kratki)",
        "6 . Adres zamieszkania",
        "B.3 ADRES ZAMIESZKANIA / SIEDZIBY",
        "8. Kraj 9. Województwo 10. Gmina",
        "13. Numer",
        "nieruchomości/domu",  # a label broken over two lines
        "14. Numer lokalu 15. Kod pocztowy",
        "16. Numer/y działki/działek (wypełnić jeżeli nieruchomość nie ma urzędowo nadanego adresu)",
        "B.4 ADRES DO KORESPONDENCJI (wypełnić tylko w przypadku kiedy jest inny niż w poz. B.3)",
        "17. Kraj 18. Województwo 19. Gmina",
        "F. DANE DO KONTAKTU (pola nieobowiązkowe)",
        "70. Nr tel./fax 71. Adres e-mail",
        "72. Wyrażam zgodę na otrzymywanie korespondencji za pośrednictwem adresu poczty elektronicznej",
    )
    assert r == {
        "B.3 ADRES ZAMIESZKANIA / SIEDZIBY": "HEADING",
        "8. Kraj 9. Województwo 10. Gmina": "FIELD_LABEL",
        "13. Numer": "FIELD_LABEL",
        "nieruchomości/domu": "FIELD_LABEL",
        "14. Numer lokalu 15. Kod pocztowy": "FIELD_LABEL",
        "F. DANE DO KONTAKTU (pola nieobowiązkowe)": "HEADING",
        "70. Nr tel./fax 71. Adres e-mail": "FIELD_LABEL",
    }  # spouse, plot number, correspondence address and the e-mail consent stay with the model


def test_case_address_heading_stays():
    assert roles("Adres nieruchomości", "Miejscowość", "Ulica") == {}
    assert roles("Osoba do kontaktu w sprawie najmu", "Telefon") == {}


def test_prompt_shortens_lines_to_fill_in():
    d = doc("Imię " + "…" * 300, "Kwota ____________ zł", "Uwagi: . . . . . . . .", "Kwota 1.50 zł")
    prompt = build_user_prompt(d)
    assert "[b1] Imię ……" in prompt and "[b2] Kwota …… zł" in prompt and "[b3] Uwagi: ……" in prompt
    assert "Kwota 1.50 zł" in prompt and len(prompt) < 300
    assert d.blocks[0].text.endswith("…" * 300)  # the Document keeps the source text


@pytest.mark.parametrize("ext", ["docx", "pdf"])  # the spreadsheet has no dotted lines
def test_form_9_prompt_shrinks(ext):
    path = material(f"9. */*.{ext}")
    data = path.read_bytes()
    d = extract(validate_upload(path.name, data, 50 << 20), data)
    raw = "\n".join(f"[{b.id}] {b.text}" for b in d.blocks)
    assert len(build_user_prompt(presort(d).model_doc)) < 0.7 * len(raw)


def test_apply_keeps_model_range_around_code_blocks(nadplata_spec):
    """The model saw b1, b2, b5 (b3-b4 taken by the code) and wrote one range b1..b5."""
    from autoformularz.spec import BlockRole

    d = doc(
        "Pouczenie",
        "Należy dołączyć dowód wpłaty.",
        "Klauzula informacyjna",
        "Administratorem danych osobowych jest Wójt.",
        "Termin rozpatrzenia: 30 dni.",
    )
    p = presort(d)
    assert [b.id for b in p.model_doc.blocks] == ["b1", "b2", "b5"]
    model = nadplata_spec.model_copy(
        update={"block_roles": [BlockRole(block="b1", to="b5", role=Role.INSTRUCTION)]}
    )
    out = apply(model, p)
    assert out.roles() == {
        "b1": Role.INSTRUCTION,
        "b2": Role.INSTRUCTION,
        "b3": Role.GDPR,
        "b4": Role.GDPR,
        "b5": Role.INSTRUCTION,
    }


# ---------------------------------------------------------------- repeated versions (form 9)


VERSION = [
    "1. Wnioskodawca",
    "Klub sportowy",
    "Imię ………………",
    "Nazwisko ………………",
    "Nazwa klubu sportowego ………",
    "Do wniosku należy dołączyć odpis z KRS.",
    "2. Dane kandydata",
]


def test_repeated_version_is_shortened_to_a_note():
    d = doc(
        "Wniosek o przyznanie stypendium",
        *VERSION,
        "Data urodzenia ………",
        "Wniosek o przyznanie nagrody",
        *VERSION,
    )
    p = presort(d)
    texts = [b.text for b in p.model_doc.blocks]
    assert texts[-1].startswith("1. Wnioskodawca (dalej bloki b12–b17 takie same jak b3–b8, pominięte)")
    assert len(texts) == 11 and "Wniosek o przyznanie nagrody" in texts
    assert "takie same jak" in build_user_prompt(p.model_doc) and "opisz ją raz" in build_user_prompt(
        p.model_doc
    )
    assert d.blocks[10].text == "1. Wnioskodawca"  # the Document keeps the source text


def test_short_repeats_and_dotted_lines_stay():
    """Form 8: 2-4 lines repeated between rate tables E.1 and E.2 are separate fields."""
    rows = ["lokale mieszkalne o powierzchni użytkowej", "do 50 m2", "38 zł"]
    d = doc("E.1 Stawki", *rows, "E.2 Stawki ze zwolnieniem", *rows)
    assert len(presort(d).model_doc.blocks) == 8
    dots = ["……………………"] * 7
    d = doc("Opis osiągnięć", *dots, "Uwagi", *dots)
    assert len(presort(d).model_doc.blocks) == 16


def test_form_9_repeats_collapse_form_8_does_not():
    for n, shrinks in ((9, True), (8, False)):
        path = material(f"{n}. */*.docx")
        data = path.read_bytes()
        p = presort(extract(validate_upload(path.name, data, 50 << 20), data))
        assert bool(p.counts.get("REPEAT")) is shrinks


def test_presort_stays_fast_on_big_unknown_documents():
    """A page of empty table rows or the same label 3000 times: every row equals every other one."""
    import time

    for lines in (["| | | |", "……………………"] * 1500, ["Imię ……"] * 3000):
        start = time.perf_counter()
        presort(doc(*lines))
        assert time.perf_counter() - start < 2


def test_clause_written_in_capitals_is_not_cut_at_every_line():
    """Some forms are all in capitals: a clause line is not a section heading."""
    lines = [
        "INFORMACJA O PRZETWARZANIU DANYCH OSOBOWYCH",
        "3. BĘDZIEMY PRZETWARZAĆ PANI/PANA DANE OSOBOWE NA PODSTAWIE ART. 6 UST. 1 LIT. C RODO W",
        "ZWIĄZKU Z PRZEPISAMI USTAWY Z DNIA 13 WRZEŚNIA 1996R. O UTRZYMANIU CZYSTOŚCI I PORZĄDKU W GMINACH,",
        "KOMUNALNYMI ZE ZMIANAMI.",
        "W PRZYPADKU PRZEKAZANIA DEKLARACJI ZA POMOCĄ ŚRODKÓW KOMUNIKACJI ELEKTRONICZNEJ (EPUAP)",
        "KONTAKTU NA PODSTAWIE PANI/PANA ZGODY (ART. 6 UST. 1 LIT. A RODO).",
        "G. INFORMACJA O ZAŁĄCZNIKACH",
    ]
    r = roles(*lines)
    assert len(r) == 6 and "G. INFORMACJA O ZAŁĄCZNIKACH" not in r


def test_section_of_a_repeated_part_is_shown_for_every_version(nadplata_spec):
    """Form 9: the club's data is in all three versions; the model saw it once (the other copies were
    shortened) and showed it only for the scholarship."""
    from autoformularz.spec import Condition, FieldSpec, Kind, PageSpec, SectionSpec

    kinds = ["Wniosek o przyznanie stypendium", "Wniosek o przyznanie nagrody"]
    d = doc(
        "Rodzaje wniosków:",
        *kinds,
        kinds[0],
        *VERSION,
        "Data urodzenia ………",
        kinds[1],
        *VERSION,
        "Kwota nagrody ………",
    )
    p = presort(d)
    assert p.repeats  # the second VERSION was shortened
    choice = FieldSpec(label="Rodzaj wniosku", kind=Kind.SINGLE_CHOICE, options=kinds)
    club = SectionSpec(
        title="Dane klubu",
        fields=[FieldSpec(label="Nazwa klubu", kind=Kind.TEXT, blocks=["b9"])],
        show_if=Condition(field="Rodzaj wniosku", equals=kinds[0]),
    )
    prize = SectionSpec(
        title="Nagroda",
        fields=[FieldSpec(label="Kwota", kind=Kind.NUMBER, blocks=["b21"])],
        show_if=Condition(field="Rodzaj wniosku", equals=kinds[1]),
    )
    spec = nadplata_spec.model_copy(
        update={
            "pages": [
                PageSpec(
                    title="Wniosek", sections=[SectionSpec(title="Rodzaj", fields=[choice]), club, prize]
                )
            ]
        }
    )
    out = apply(spec, p)
    sections = {s.title: s for s in out.pages[0].sections}
    assert sections["Dane klubu"].show_if is None  # in both versions: always shown
    assert sections["Nagroda"].show_if == prize.show_if  # only in the second version: unchanged
