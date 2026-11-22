import json
from pathlib import Path

import pytest

from autoformularz.spec import ApplicantSpec, Condition, FieldSpec, FormSpec, Kind, PageSpec, SectionSpec

MATERIALS = Path(__file__).resolve().parents[2] / "materialy"


def material(pattern: str) -> Path:
    found = sorted(MATERIALS.glob(pattern))
    if not found:
        pytest.skip(f"brak materiału {pattern}")
    return found[0]


def reference(n: int) -> dict:
    return json.loads(material(f"{n}. */konfiguracja_form_*.json").read_text(encoding="utf-8"))


@pytest.fixture
def nadplata_spec() -> FormSpec:
    """Hand-written FormSpec for reference form 5 (what the model should produce)."""
    choice = "Wybierz, co mamy zrobić z nadpłatą"
    return FormSpec(
        title="Wniosek o stwierdzenie nadpłaty podatku",
        authority_name="Urząd Gminy Ulan-Majorat",
        applicant=ApplicantSpec(other_person=True, entity=True, entity_nip_only=True),
        pages=[
            PageSpec(
                title="Informacje o nadpłacie",
                sections=[
                    SectionSpec(
                        title="Informacje o nadpłacie",
                        fields=[
                            FieldSpec(label="Podatek, którego dotyczy nadpłata", kind=Kind.TEXT),
                            FieldSpec(label="Kwota", kind=Kind.NUMBER),
                            FieldSpec(label="Uzasadnienie", kind=Kind.LONG_TEXT),
                        ],
                    ),
                    SectionSpec(
                        title="Rozliczenie nadpłaty",
                        fields=[
                            FieldSpec(
                                label=choice,
                                kind=Kind.SINGLE_CHOICE,
                                options=["Zwrot na rachunek bankowy", "Zaliczenie na poczet podatku"],
                            ),
                            FieldSpec(
                                label="Nazwa podatku",
                                kind=Kind.TEXT,
                                show_if=Condition(field=choice, equals="Zaliczenie na poczet podatku"),
                            ),
                            FieldSpec(
                                label="Numer rachunku",
                                kind=Kind.TEXT,
                                show_if=Condition(field=choice, equals="Zwrot na rachunek bankowy"),
                            ),
                        ],
                    ),
                    SectionSpec(
                        title="Korekta deklaracji",
                        fields=[FieldSpec(label="Plik deklaracji podatkowej", kind=Kind.FILE)],
                    ),
                ],
            )
        ],
    )


def pytest_addoption(parser):
    """Test na żywo (tests/test_na_zywo.py): prawdziwy model, płatne wywołanie. Bez tych opcji jest pomijany."""
    parser.addoption("--na-zywo", action="store_true", help="uruchom test z prawdziwym modelem")
    parser.addoption("--plik", default=None, help="plik formularza do testu na żywo (domyślnie materiał 1)")
    parser.addoption(
        "--na-zywo-wszystko",
        action="store_true",
        help="test_wymagania.py na świeżych wynikach: 9 materiałów przez model (płatne), nie na wyniki/",
    )
