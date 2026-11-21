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


def test_reference_differences_are_warnings():
    assert "FINISH_TEXT_BLOCK" in codes(reference(5), "warning")


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
