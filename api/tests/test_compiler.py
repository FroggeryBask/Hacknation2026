import re

from conftest import reference

from autoformularz.compiler import compile_form, slug
from autoformularz.lint import lint
from autoformularz.spec import Condition, FieldSpec, FormSpec, Kind, PageSpec, SectionSpec


def sections(form: dict, tab: str) -> dict[str, dict]:
    t = next(t for t in form["tabs"] if t["title"] == tab)
    return {q["field"]["techName"]: q["field"] for q in t["questions"]}


def children(section: dict) -> dict[str, dict]:
    return {c["field"]["techName"]: c["field"] for c in section["repeatingSectionGrid"]}


def norm(query: str) -> str:
    return re.sub(r"\s+", "", query)


def test_slug():
    assert slug("Podatek, którego dotyczy nadpłata") == "podatek_ktorego_dotyczy_nadplata"
    assert slug("Łódź – ŻÓŁW") == "lodz_zolw"


def test_matches_reference_structure(nadplata_spec):
    ref = reference(5)
    form, warnings = compile_form(nadplata_spec)
    assert warnings == []
    assert [t["title"] for t in form["tabs"]] == [t["title"] for t in ref["tabs"]]
    assert [t["type"] for t in form["tabs"]] == [t["type"] for t in ref["tabs"]]

    ours, theirs = sections(form, "Dane"), sections(ref, "Dane")
    # Same predefined sections as the reference (organ/urząd naming follows authority_kind).
    assert set(theirs) <= set(ours)
    # Same visibility rules for the applicant-dependent sections.
    for tech in ("dane_podmiotu", "adres_siedziby", "dane_innej_osoby", "oplata_skarbowa_pelnomocnictwo_2"):
        assert norm(ours[tech]["states"][0]["query"]) == norm(theirs[tech]["states"][0]["query"]), tech


def test_case_page_and_conditions(nadplata_spec):
    form, _ = compile_form(nadplata_spec)
    page = sections(form, "Informacje o nadpłacie")
    fields = children(page["rozliczenie_nadplaty"])
    assert fields["wybierz_co_mamy_zrobic_z_nadplata"]["type"] == "RADIO"
    query = fields["numer_rachunku"]["states"][0]["query"]
    assert query == (
        "(\"Zwrot na rachunek bankowy\" in tabs['Informacje o nadpłacie' in title]"
        ".questions['rozliczenie_nadplaty' in field.techName].field.repeatingSectionGrid"
        "['wybierz_co_mamy_zrobic_z_nadplata' in field.techName].field.__userAnswer)"
    )
    assert children(page["informacje_o_nadplacie"])["kwota"]["type"] == "NUMBER"


def test_output_passes_lint(nadplata_spec):
    form, _ = compile_form(nadplata_spec)
    errors = [i for i in lint(form) if i.level == "error"]
    assert errors == []


def test_deterministic_ids(nadplata_spec):
    a, _ = compile_form(nadplata_spec)
    b, _ = compile_form(nadplata_spec)
    assert a == b


def test_minimal_form_self_only():
    spec = FormSpec(
        title="Wniosek o wydanie zaświadczenia",
        authority_kind="organ",
        authority_name="Wójt Gminy X",
        applicant={"other_person": False, "entity": False},
        pages=[
            PageSpec(
                title="Zaświadczenie",
                sections=[
                    SectionSpec(
                        title="Zakres zaświadczenia",
                        fields=[FieldSpec(label="Cel wydania zaświadczenia", kind=Kind.TEXT)],
                    )
                ],
            )
        ],
        consents=["Dane w formularzu są zgodne z prawdą"],
    )
    form, _ = compile_form(spec)
    data = sections(form, "Dane")
    assert "podmiot_wniosku" not in data and "pelnomocnictwo" not in data
    assert "organ_do_ktorego_jest_skladany_wniosek" in data
    consent = children(sections(form, "Kontakt i zgody")["zgoda_wyrazenie"])["zgoda"]
    assert len(consent["consentSectionConfig"]["consents"]) == 2
    assert [i for i in lint(form) if i.level == "error"] == []


def test_auto_validators_and_dictionaries():
    spec = FormSpec(
        title="Wniosek testowy",
        authority_name="Urząd",
        pages=[
            PageSpec(
                title="Dane dziecka",
                sections=[
                    SectionSpec(
                        title="Dziecko",
                        repeating=True,
                        fields=[
                            FieldSpec(label="Numer PESEL dziecka", kind=Kind.TEXT),
                            FieldSpec(label="Obywatelstwo", kind=Kind.TEXT),
                            FieldSpec(
                                label="Czy dziecko jest niepełnosprawne",
                                kind=Kind.SINGLE_CHOICE,
                                options=["Tak", "Nie"],
                            ),
                            FieldSpec(
                                label="Orzeczenie",
                                kind=Kind.FILE,
                                required=False,
                                show_if=Condition(field="Czy dziecko jest niepełnosprawne", equals="Tak"),
                            ),
                        ],
                    )
                ],
            )
        ],
    )
    form, _ = compile_form(spec)
    child = sections(form, "Dane dziecka")["dziecko"]
    assert child["type"] == "REPEATING_SECTION"
    f = children(child)
    assert f["numer_pesel_dziecka"]["validation"] == ["REQUIRED", "PESEL"]
    assert f["obywatelstwo"]["type"] == "SELECT" and f["obywatelstwo"]["dictionaryName"] == "Kraje"
    assert "$repeatingSectionIndex" in f["orzeczenie"]["states"][0]["query"]
    assert f["orzeczenie"]["validation"] == []


def test_unknown_condition_is_dropped_with_warning():
    spec = FormSpec(
        title="Wniosek testowy",
        authority_name="Urząd",
        pages=[
            PageSpec(
                title="Sprawa",
                sections=[
                    SectionSpec(
                        title="Sprawa",
                        fields=[
                            FieldSpec(
                                label="Opis",
                                kind=Kind.LONG_TEXT,
                                show_if=Condition(field="Nie ma", equals="Tak"),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    form, warnings = compile_form(spec)
    assert warnings and "Nie ma" in warnings[0]
    assert children(sections(form, "Sprawa")["sprawa"])["opis"]["states"] == []


def _finish_texts(form: dict) -> dict[str, str]:
    """techName of each finish-page section -> HTML of its first field."""
    finish = form["tabs"][-1]
    return {
        qn["field"]["techName"]: qn["field"]["repeatingSectionGrid"][0]["field"]["description"]
        for qn in finish["questions"]
    }


def test_legal_text_copied_verbatim_from_blocks(nadplata_spec):
    from autoformularz.document import build
    from autoformularz.lint import lint
    from autoformularz.spec import BlockRole, Role

    doc = build(
        [
            ("Wniosek o stwierdzenie nadpłaty", None),
            ("| Podstawa prawna: | art. 75 § 1 Ordynacji podatkowej |", None),
            ("Wniosek rozpatruje się w terminie 30 dni.", None),
            ("Oświadczam, że podane dane są prawdziwe.", None),
            ("Administratorem danych jest Wójt Gminy.", None),
            ("Podpis wnioskodawcy ............", None),
        ]
    )
    roles = {
        "b2": Role.LEGAL_BASIS,
        "b3": Role.INSTRUCTION,
        "b4": Role.STATEMENT,
        "b5": Role.GDPR,
        "b6": Role.SKIP,
    }
    spec = nadplata_spec.model_copy(
        update={"block_roles": [BlockRole(block=k, role=v) for k, v in roles.items()]}
    )
    form, _ = compile_form(spec, doc)
    texts = _finish_texts(form)
    assert list(texts) == ["pouczenie", "podstawa_prawna", "podglad_uzupelnionego_wniosku"]
    assert "art. 75 § 1 Ordynacji podatkowej" in texts["podstawa_prawna"]  # table markup removed, text kept
    assert "|" not in texts["podstawa_prawna"]
    assert "Wniosek rozpatruje się w terminie 30 dni." in texts["pouczenie"]
    everything = str(form)
    assert "Administratorem danych" not in everything  # GDPR clause is linked, not placed on the form
    assert "Oświadczam, że podane" not in everything  # statements come from `consents`, not verbatim
    assert "Podpis wnioskodawcy" not in everything
    assert not [i for i in lint(form) if i.level == "error"]


def test_without_document_output_is_unchanged(nadplata_spec):
    from autoformularz.document import build
    from autoformularz.spec import BlockRole, Role

    spec = nadplata_spec.model_copy(update={"block_roles": [BlockRole(block="b1", role=Role.LEGAL_BASIS)]})
    assert compile_form(spec)[0] == compile_form(nadplata_spec)[0]
    assert compile_form(nadplata_spec, build([("art. 1", None)]))[0] == compile_form(nadplata_spec)[0]


def test_instruction_range_copies_every_block_in_it(nadplata_spec):
    from autoformularz.document import build
    from autoformularz.spec import BlockRole, Role

    doc = build([("Objaśnienia:", None), ("1. Pierwsze.", None), ("2. Drugie.", None), ("Koniec", None)])
    spec = nadplata_spec.model_copy(
        update={"block_roles": [BlockRole(block="b1", to="b3", role=Role.INSTRUCTION)]}
    )
    texts = _finish_texts(compile_form(spec, doc)[0])
    assert all(t in texts["pouczenie"] for t in ("Objaśnienia:", "1. Pierwsze.", "2. Drugie."))
    assert "Koniec" not in texts["pouczenie"]


def _choice_spec(equals: str) -> FormSpec:
    return FormSpec(
        title="Wniosek testowy",
        authority_name="Urząd",
        pages=[
            PageSpec(
                title="Sprawa",
                sections=[
                    SectionSpec(
                        title="Sprawa",
                        fields=[
                            FieldSpec(label="Dyscyplina", kind=Kind.SINGLE_CHOICE, options=["hokej", "Inna"]),
                            FieldSpec(
                                label="Inna dyscyplina",
                                kind=Kind.TEXT,
                                show_if=Condition(field="Dyscyplina", equals=equals),
                            ),
                        ],
                    )
                ],
            )
        ],
    )


def test_condition_option_matched_regardless_of_case():
    form, warnings = compile_form(_choice_spec("INNA"))
    query = children(sections(form, "Sprawa")["sprawa"])["inna_dyscyplina"]["states"][0]["query"]
    assert '"Inna"' in query and not warnings
    assert not [i for i in lint(form) if i.level == "error"]


def test_condition_on_missing_option_is_dropped_with_warning():
    # Material 9: the model pointed to "Inna dyscyplina", which was not among the options (lint error).
    form, warnings = compile_form(_choice_spec("Inna dyscyplina"))
    assert children(sections(form, "Sprawa")["sprawa"])["inna_dyscyplina"]["states"] == []
    assert warnings and "Inna dyscyplina" in warnings[0]
    assert not [i for i in lint(form) if i.level == "error"]
