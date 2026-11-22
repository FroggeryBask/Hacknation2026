"""Proposals of new dictionaries (task extension II): name, structure and use in the form, next to the JSON."""

import json

from autoformularz import results
from autoformularz.config import Settings
from autoformularz.dictionaries import STRUCTURE, propose
from autoformularz.pipeline import from_spec
from autoformularz.spec import FieldSpec, FormSpec, Kind, PageSpec, SectionSpec


def form(*fields: FieldSpec) -> FormSpec:
    return FormSpec(
        title="Wniosek o zasiłek opiekuńczy",
        authority_name="ZUS",
        pages=[PageSpec(title="Dane osoby", sections=[SectionSpec(title="Osoba", fields=list(fields))])],
    )


def text(label: str) -> FieldSpec:
    return FieldSpec(label=label, kind=Kind.TEXT, required=True)


def choice(label: str, options: list[str], kind: Kind = Kind.SINGLE_CHOICE) -> FieldSpec:
    return FieldSpec(label=label, kind=kind, required=True, options=options)


def test_known_dictionaries_from_labels():
    """Z-15: "Stopień pokrewieństwa" and the identity document are free text on paper: shared lists fit."""
    found = {
        p.name: p
        for p in propose(form(text("Stopień pokrewieństwa"), text("Rodzaj, seria i numer dokumentu")))
    }
    assert set(found) == {"STOPIEN_POKREWIENSTWA", "RODZAJ_DOKUMENTU_TOZSAMOSCI"}
    d = found["STOPIEN_POKREWIENSTWA"].as_dict()
    assert d["structure"] == STRUCTURE and {"kod": "CORKA", "nazwa": "córka"} in d["entries"]
    assert d["usage"] == [
        {
            "page": "Dane osoby",
            "section": "Osoba",
            "field": "Stopień pokrewieństwa",
            "fieldType": "TEXT",
            "change": "pole listy rozwijanej z dictionaryName „STOPIEN_POKREWIENSTWA” zamiast pola tekstowego",
        }
    ]


def test_long_option_list_becomes_a_dictionary_named_after_its_label():
    options = [f"Rodzaj odpadu {i}" for i in range(9)]
    (p,) = propose(form(choice("Frakcja odpadów", options, Kind.MULTI_CHOICE)))
    assert p.name == "FRAKCJA_ODPADOW" and p.entries == options


def test_short_questions_and_platform_dictionaries_get_no_proposal():
    fields = [
        choice("Rodzaj dyscypliny sportowej", ["zespołowa", "indywidualna"]),  # a question, not the list
        choice("Płeć", ["kobieta", "mężczyzna"]),
        FieldSpec(label="Kraj", kind=Kind.SELECT, required=True, dictionary="Kraje"),
    ]
    assert propose(form(*fields)) == []


def test_fixed_list_keeps_its_entries_and_a_source_list_takes_the_forms():
    delivery = choice(
        "Preferowany sposób korespondencji z urzędem", ["Poczta - adres klubu", "ePUAP", "x", "y"]
    )
    sports = choice("Dyscypliny sportowe", ["hokej", "karate", "judo", "boks"], Kind.MULTI_CHOICE)
    found = {p.name: p for p in propose(form(delivery, sports))}
    assert "Poczta - adres klubu" not in found["SPOSOBY_DORECZENIA"].entries  # one form's variant
    assert found["DYSCYPLINY_SPORTOWE"].entries == ["hokej", "karate", "judo", "boks"]
    assert found["DYSCYPLINY_SPORTOWE"].as_dict()["source"]


def test_json_is_unchanged_and_details_list_the_proposals():
    """An unknown dictionaryName would import as an empty field: the options stay in the JSON."""
    from autoformularz.main import body

    result = from_spec(
        form(choice("Dyscypliny sportowe", ["hokej", "karate", "judo", "boks"], Kind.MULTI_CHOICE))
    )
    assert "DYSCYPLINY_SPORTOWE" not in json.dumps(result.form) and "karate" in json.dumps(
        result.form, ensure_ascii=False
    )
    assert body(result, details=True)["dictionaries"][0]["dictionaryName"] == "DYSCYPLINY_SPORTOWE"


def test_generator_merges_proposals_of_all_forms(tmp_path, monkeypatch, nadplata_spec):
    monkeypatch.setattr(results, "OUT", tmp_path)
    for n, label in ((2, "Stopień pokrewieństwa"), (3, "Stopień pokrewieństwa wnioskodawcy")):
        spec = form(text(label))
        (tmp_path / f"{n:02d}.spec.json").write_text(spec.model_dump_json(), encoding="utf-8")
        results.run(n, Settings(_env_file=None), compile_only=True, force=False)
    assert results.write_dictionaries() == 1
    (d,) = json.loads((tmp_path / "slowniki.json").read_text(encoding="utf-8"))
    assert d["dictionaryName"] == "STOPIEN_POKREWIENSTWA" and [u["form"] for u in d["usage"]] == [2, 3]
