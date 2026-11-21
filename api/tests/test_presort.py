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
