import copy

import pytest
from conftest import reference

from autoformularz.compiler import compile_form
from autoformularz.lint import lint


def codes(form: dict, level: str = "error") -> set[str]:
    return {i.code for i in lint(form) if i.level == level}


@pytest.mark.parametrize("n", [1, 5])
def test_reference_files_have_no_errors(n):
    assert codes(reference(n)) == set()


def test_finish_text_block_is_allowed():
    """Mentors: the finish page may hold INFO_SECTION and TEXT_BLOCK (reference 5 uses TEXT_BLOCK)."""
    issues = {i.code for i in lint(reference(5))}
    assert "FINISH_TEXT_BLOCK" not in issues and "FINISH_HAS_INPUT" not in issues


def test_editable_prefill_is_not_a_warning(nadplata_spec):
    """Address and contact are prefilled from login data but stay editable, as in the references."""
    form, _ = compile_form(nadplata_spec)
    assert "PREFILL_EDITABLE" not in codes(form, "warning")


def test_detects_broken_rules(nadplata_spec):
    form, _ = compile_form(nadplata_spec)
    broken = copy.deepcopy(form)
    broken["tabs"] = broken["tabs"][-1:]  # only the FINISH page
    assert "TABS_MIN" in codes(broken)

    broken = copy.deepcopy(form)
    finish_section = broken["tabs"][-1]["questions"][0]["field"]
    finish_section["repeatingSectionGrid"][0]["field"]["type"] = "TEXT_FIELD"
    assert "FINISH_HAS_INPUT" in codes(broken)

    broken = copy.deepcopy(form)
    section = broken["tabs"][0]["questions"][0]["field"]
    section["repeatingSectionGrid"].append({"field": copy.deepcopy(section)})
    assert "NESTED_SECTION" in codes(broken)

    broken = copy.deepcopy(form)
    broken["flow"]["links"] = broken["flow"]["links"][1:]
    assert "FLOW_DEAD_END" in codes(broken)

    broken = copy.deepcopy(form)
    first = broken["tabs"][1]["questions"][1]["field"]["repeatingSectionGrid"][1]["field"]
    first["states"] = [
        {"type": "SHOW", "query": "(\"X\" in tabs['Dane' in title].questions['nie_ma' in field.techName])"}
    ]
    assert "STATE_UNKNOWN_FIELD" in codes(broken)


def _find(form: dict, tech: str) -> tuple[dict, dict]:
    """(grid item, field) for a field techName in a compiled form."""
    for tab in form["tabs"]:
        for qn in tab["questions"]:
            for item in qn["field"].get("repeatingSectionGrid") or []:
                if item["field"]["techName"] == tech:
                    return item, item["field"]
    raise KeyError(tech)


@pytest.fixture
def conditional_form(nadplata_spec) -> dict:
    """Reference form 5 compiled: 'nazwa_podatku' is shown when the choice field has a given option."""
    form, _ = compile_form(nadplata_spec)
    assert _find(form, "nazwa_podatku")[1]["states"]
    return form


def test_compiled_conditions_are_clean(conditional_form):
    issues = {i.code for i in lint(conditional_form)}
    assert not issues & {"STATE_UNKNOWN_OPTION", "STATE_CYCLE", "STATE_FORWARD_REF"}


def test_unknown_option(conditional_form):
    _, f = _find(conditional_form, "nazwa_podatku")
    f["states"][0]["query"] = f["states"][0]["query"].replace("Zaliczenie na poczet podatku", "Nie ma takiej")
    assert "STATE_UNKNOWN_OPTION" in codes(conditional_form)


def test_cycle(conditional_form):
    _, dependent = _find(conditional_form, "nazwa_podatku")
    _, controlling = _find(conditional_form, "wybierz_co_mamy_zrobic_z_nadplata")
    controlling["states"] = [
        {
            "type": "SHOW",
            "query": dependent["states"][0]["query"].replace(
                "wybierz_co_mamy_zrobic_z_nadplata", "nazwa_podatku"
            ),
        }
    ]
    assert "STATE_CYCLE" in codes(conditional_form)


def test_forward_reference_uses_screen_position(conditional_form):
    dep_item, _ = _find(conditional_form, "nazwa_podatku")
    ctl_item, _ = _find(conditional_form, "wybierz_co_mamy_zrobic_z_nadplata")
    dep_item["y"], ctl_item["y"] = ctl_item["y"], dep_item["y"]  # controlling field now below
    assert "STATE_FORWARD_REF" in codes(conditional_form, "warning")
    assert "STATE_FORWARD_REF" not in codes(conditional_form)  # a warning, not an error
