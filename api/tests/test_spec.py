"""FormSpec: block role ranges (one entry for a run of consecutive blocks)."""

from autoformularz.check import coverage
from autoformularz.document import build
from autoformularz.spec import BlockRole, FormSpec, Role


def test_range_covers_consecutive_blocks():
    assert BlockRole(block="b8", to="b11", role=Role.GDPR).ids() == ["b8", "b9", "b10", "b11"]


def test_single_block_and_bad_ranges_cover_only_the_first_block():
    assert BlockRole(block="b8", role=Role.GDPR).ids() == ["b8"]
    assert BlockRole(block="b8", to="b3", role=Role.GDPR).ids() == ["b8"]  # backwards
    assert BlockRole(block="b8", to="x", role=Role.GDPR).ids() == ["b8"]  # not a block ID


def test_old_specs_without_ranges_still_load():
    spec = FormSpec.model_validate(
        {
            "title": "Wniosek",
            "authority_name": "Urząd",
            "pages": [],
            "block_roles": [{"block": "b1", "role": "SKIP"}],
        }
    )
    assert spec.roles() == {"b1": Role.SKIP}


def test_coverage_counts_every_block_in_a_range():
    doc = build([("Tytuł", None), ("RODO 1", None), ("RODO 2", None), ("Podpis ......", None)])
    spec = FormSpec(
        title="Wniosek",
        authority_name="Urząd",
        pages=[],
        block_roles=[
            BlockRole(block="b2", to="b3", role=Role.GDPR),
            BlockRole(block="b4", role=Role.SKIP),
        ],
    )
    c = coverage(spec, doc)
    assert c.unreferenced == ["b1"] and c.candidates_without_field == [] and c.unknown_refs == []


def test_model_schema_is_stricter_than_saved_specs():
    from autoformularz.spec import MODEL_MAX_ROLES, model_schema

    schema = model_schema()
    assert schema["$defs"]["BlockRole"]["properties"]["role"]["enum"] == [
        "INSTRUCTION",
        "LEGAL_BASIS",
        "STATEMENT",
        "GDPR",
        "SKIP",
    ]
    assert schema["properties"]["block_roles"]["maxItems"] == MODEL_MAX_ROLES
    assert "required" in schema["$defs"]["FieldSpec"]["required"]
    assert FormSpec.model_json_schema()["$defs"]["FieldSpec"]["properties"]["required"]["default"] is True
    # A saved spec with a role the model may no longer give still loads (material 8, first results).
    old = {
        "title": "W",
        "authority_name": "U",
        "pages": [],
        "block_roles": [{"block": "b1", "role": "HEADING"}],
    }
    assert FormSpec.model_validate(old).roles() == {"b1": Role.HEADING}
