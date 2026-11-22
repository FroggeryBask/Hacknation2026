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


def _optional_props(schema):
    for obj in (schema, *schema["$defs"].values()):
        required = set(obj.get("required", []))
        for name, prop in (obj.get("properties") or {}).items():
            if name not in required:
                yield name, prop


def test_model_schema_allows_no_default_values():
    """The model leaves defaults out instead of writing them: no null, no [], no default flag value."""
    import json

    from autoformularz.spec import model_schema

    schema = model_schema()
    assert '"null"' not in json.dumps(schema)
    for name, prop in _optional_props(schema):
        assert "default" not in prop, name
        if prop.get("type") == "array":
            assert prop["minItems"] >= 1, name
        if prop.get("type") == "boolean":
            assert len(prop["enum"]) == 1, name
    assert schema["properties"]["authority_kind"]["enum"] == ["organ"]
    assert schema["properties"]["signed"]["enum"] == [False]
    assert schema["$defs"]["SectionSpec"]["properties"]["repeating"]["enum"] == [True]
    assert "required" in schema["$defs"]["FieldSpec"]["required"]  # still written for every field


def test_left_out_defaults_read_back_the_same(nadplata_spec):
    """Every saved result, written without its default values, reads back identical: leaving them out
    loses nothing."""
    import glob
    from pathlib import Path

    from autoformularz.spec import FormSpec

    root = Path(__file__).resolve().parents[2] / "wyniki"
    specs = [
        FormSpec.model_validate_json(Path(p).read_text(encoding="utf-8"))
        for p in glob.glob(str(root / "*.spec.json"))
    ]
    for spec in [nadplata_spec, *specs]:
        lean = spec.model_dump(mode="json", exclude_defaults=True)
        assert FormSpec.model_validate(lean) == spec
