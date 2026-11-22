"""FormSpec: the small intermediate model the LLM fills in.

The LLM never writes the target JSON directly (1-2k lines with UUIDs and jsonata). It only describes
WHAT the form asks for; `compiler.py` deterministically turns this into the COI import format,
adding the predefined sections from the design standard."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Kind(StrEnum):
    TEXT = "TEXT"  # short single-line text -> TEXT_FIELD
    LONG_TEXT = "LONG_TEXT"  # description, justification -> TEXTAREA
    NUMBER = "NUMBER"  # numbers only (amounts, counts) -> NUMBER
    DATE = "DATE"  # -> DATEPICKER
    SINGLE_CHOICE = "SINGLE_CHOICE"  # one of <=5 options -> RADIO
    MULTI_CHOICE = "MULTI_CHOICE"  # one or more options -> CHECKBOX
    SELECT = "SELECT"  # one of >5 options or a dictionary -> SELECT
    FILE = "FILE"  # attachment -> FILE_UPLOADER
    INFO = "INFO"  # static explanation, no input -> TEXT_BLOCK


# Initial data sources ("Dane inicjalne" material): SOURCE.attribute
Prefill = Literal[
    "PESEL.pesel",
    "PESEL.name",
    "PESEL.surname",
    "PESEL.birthDate",
    "PESEL.citizenship",
    "PESEL.motherName",
    "PESEL.birthPlace",
    "PESEL.motherSurname",
    "PESEL.sex",
    "PESEL.fatherName",
    "PESEL.secondName",
    "PESEL.birthCountry",
    "PESEL.foreignBirthUSC",
    "PESEL.familyName",
    "PESEL.fatherSurname",
    "PESEL.maritalStatus",
    "PESEL_ADDRESS.permanentAddressVoivodeship",
    "PESEL_ADDRESS.permanentAddressDistrict",
    "PESEL_ADDRESS.permanentAddressCommunity",
    "PESEL_ADDRESS.permanentAddressPlace",
    "PESEL_ADDRESS.permanentAddressStreetType",
    "PESEL_ADDRESS.permanentAddressStreet",
    "PESEL_ADDRESS.permanentAddressPostalCode",
    "PESEL_ADDRESS.permanentAddressHouseNumber",
    "PESEL_ADDRESS.permanentAddressApartmentNumber",
    "MLPZ.name",
    "MLPZ.secondName",
    "MLPZ.surname",
    "MLPZ.pesel",
    "MLPZ.phoneNumber",
    "MLPZ.email",
    "MLPZ.country",
    "MLPZ.voivodeship",
    "MLPZ.district",
    "MLPZ.community",
    "MLPZ.place",
    "MLPZ.postCode",
    "MLPZ.street",
    "MLPZ.building",
    "MLPZ.apartment",
    "MLPZ.institutionName",
    "MLPZ.descriptiveOrganizationName",
]

Validator = Literal["PESEL", "NIP", "REGON", "ZIP_CODE", "EMAIL", "EPUAP", "ADE", "SERIAL_NUMBER_ID_CARD"]

# Predefined dictionaries ("Słowniki" material + names used in the reference JSON)
Dictionary = Literal["Kraje", "TERYT_4G_DOWODOWY", "NUMERY_KIERUNKOWE"]


class Role(StrEnum):
    """What a source block is (docs/pipeline.md, step 3). The model classifies, the code copies text."""

    FIELD_LABEL = "FIELD_LABEL"  # label of something to fill in
    OPTION = "OPTION"  # one option of a choice field (☐ …)
    HEADING = "HEADING"  # section or page title
    INSTRUCTION = "INSTRUCTION"  # pouczenie: how to fill in, what happens next
    LEGAL_BASIS = "LEGAL_BASIS"  # podstawa prawna (act, article)
    STATEMENT = "STATEMENT"  # oświadczenie the applicant confirms
    GDPR = "GDPR"  # RODO / personal data clause
    SKIP = "SKIP"  # paper-only: signature, stamp, "wypełnia urząd", date and place


class BlockRole(BaseModel):
    """A role for one block, or for a run of consecutive blocks `block`..`to` (e.g. a whole GDPR clause):
    one entry instead of one per line keeps the answer short on forms with long instructions."""

    block: str = Field(description="Block ID from the document, e.g. 'b12' (first block of the run).")
    to: str | None = Field(
        default=None, description="Last block of a run of consecutive blocks with the same role, e.g. 'b40'."
    )
    role: Role

    def ids(self) -> list[str]:
        """Block IDs covered, in order. IDs are `b<number>` in reading order (document.py); an unreadable
        or backwards range covers only `block`."""
        first, last = _number(self.block), _number(self.to) if self.to else None
        if first is None or last is None or last < first:
            return [self.block]
        return [f"b{i}" for i in range(first, min(last, first + MAX_RUN) + 1)]


MAX_RUN = 2000  # a range never covers more blocks than a real form has


def _number(block_id: str) -> int | None:
    return int(block_id[1:]) if block_id[:1] == "b" and block_id[1:].isdigit() else None


def _blocks():
    return Field(
        default_factory=list,
        max_length=MAX_REFS,
        description="IDs of the source blocks this element comes from (label, options), e.g. ['b12', 'b13'].",
    )


class Condition(BaseModel):
    """Show the element only when a choice field has (or has not) a given option selected."""

    field: str = Field(description="Label of the controlling choice field (exactly as in this spec).")
    equals: str = Field(description="Option label that must be selected.")
    negate: bool = Field(default=False, description="True = show when the option is NOT selected.")


# Upper bounds in the JSON Schema (maxItems). Generous for real forms (the largest material, form 9, merges
# three applications), but they stop a model stuck in a repetition loop when the provider enforces the schema.
MAX_PAGES, MAX_SECTIONS, MAX_FIELDS, MAX_OPTIONS, MAX_REFS, MAX_ROLES = 10, 15, 40, 40, 30, 120


class FieldSpec(BaseModel):
    label: str
    kind: Kind
    required: bool = True
    description: str | None = Field(default=None, description="Short hint under the field, plain language.")
    options: list[str] = Field(
        default_factory=list, max_length=MAX_OPTIONS, description="Options for choice fields."
    )
    dictionary: Dictionary | None = None
    prefill: Prefill | None = Field(default=None, description="Registry value shown read-only.")
    validators: list[Validator] = Field(default_factory=list)
    show_if: Condition | None = None
    allowed_formats: list[str] = Field(default_factory=list, description="FILE only, e.g. ['pdf','jpg'].")
    max_files: int | None = Field(default=None, description="FILE only.")
    blocks: list[str] = _blocks()


class SectionSpec(BaseModel):
    title: str
    repeating: bool = Field(default=False, description="True for repeated items (people, vehicles, plots).")
    description: str | None = None
    fields: list[FieldSpec] = Field(max_length=MAX_FIELDS)
    show_if: Condition | None = None
    blocks: list[str] = _blocks()


class PageSpec(BaseModel):
    title: str = Field(description="Short page title describing its topic, e.g. 'Informacje o budynku'.")
    sections: list[SectionSpec] = Field(max_length=MAX_SECTIONS)


class ApplicantSpec(BaseModel):
    """Who may file the form. Drives the predefined 'Podmiot wniosku' and related sections."""

    other_person: bool = Field(
        default=True, description="Filing on behalf of another natural person is allowed."
    )
    entity: bool = Field(
        default=False, description="The paper form has company/institution data (NIP, REGON, KRS, name)."
    )
    entity_nip_only: bool = Field(default=False, description="Paper form asks only name + NIP of entity.")
    # Set by the code (presort: the paper mentions PESEL outside the GDPR clause), not by the model. The
    # COI references follow the paper: material 1 (no PESEL on paper) has none, its visualisation too;
    # material 5 (PESEL on paper) has it. Default True keeps saved specs as they were.
    pesel: bool = Field(default=True, description="The paper form asks for a PESEL.")


class FormSpec(BaseModel):
    title: str = Field(description="Starts with Wniosek/Zgłoszenie/Deklaracja/Oświadczenie, no legal refs.")
    authority_kind: Literal["urząd", "organ"] = Field(
        default="urząd", description="'organ' when addressed to an official (Wójt, Burmistrz, Prezydent)."
    )
    authority_name: str = Field(description="Office or authority with its unit, e.g. 'Urząd Gminy X'.")
    applicant: ApplicantSpec = Field(default_factory=ApplicantSpec)
    # Before `pages`: the model first sets aside instructions, legal text and GDPR (as ranges), then
    # describes fields. With roles last it turned every line of long instructions into a section (form 8).
    block_roles: list[BlockRole] = Field(
        default_factory=list,
        max_length=MAX_ROLES,  # saved specs; the model gets the tighter MODEL_MAX_ROLES (model_schema)
        # Only text the compiler copies or drops: listing every block overflows the context on big forms.
        description="Only blocks with instructions, legal basis, statements, GDPR text, and SKIP for "
        "paper-only text; consecutive blocks with the same role as one range (block..to). Not for field "
        "labels, options or headings (blocks without a role are allowed).",
    )
    # Before `pages` too: the model writes the statements first. Written after the pages, they were lost
    # whenever the model kept adding sections (forms 2, 3, 4, 6: "Podpis", "Data", "Podpis", …) and the
    # answer was cut, and the model then turned them into TAK/NIE fields instead.
    consents: list[str] = Field(
        default_factory=list, description="Statements the applicant confirms (besides the GDPR consent)."
    )
    summary: str | None = Field(default=None, description="Optional info on what happens after sending.")
    signed: bool = True
    pages: list[PageSpec] = Field(
        max_length=MAX_PAGES,
        description="Case-specific pages only (subject of the application), each page once.",
    )

    def roles(self) -> dict[str, Role]:
        """Role of each block, ranges expanded. A later entry wins for a block listed twice."""
        return {block: r.role for r in self.block_roles for block in r.ids()}

    def referenced_blocks(self) -> set[str]:
        """Block IDs used anywhere in the spec (fields, sections, roles)."""
        refs = set(self.roles())
        for page in self.pages:
            for section in page.sections:
                refs.update(section.blocks)
                for f in section.fields:
                    refs.update(f.blocks)
        return refs


# Roles the model may give (the others exist for code and old specs). With FIELD_LABEL/HEADING/OPTION
# allowed, the model on material 8 spent 77 of 120 entries on them and ran out of tokens before the pages.
MODEL_ROLES = [Role.INSTRUCTION, Role.LEGAL_BASIS, Role.STATEMENT, Role.GDPR, Role.SKIP]
MODEL_MAX_ROLES = 40  # with ranges a whole form fits; forces one entry per run of blocks


def model_schema() -> dict:
    """JSON Schema sent to the model (Ollama `format`, Eden `json_schema`). Both providers enforce it, so
    rules that must hold go here, not only in the prompt. Stricter than `FormSpec` itself, which still
    loads saved specs:
    - `block_roles[].role` only from MODEL_ROLES, at most MODEL_MAX_ROLES entries,
    - `required` must be written for every field (with a default the model never wrote it, so every field
      came out required, even ones the paper marks as optional)."""
    schema = FormSpec.model_json_schema()
    defs = schema["$defs"]
    defs["BlockRole"]["properties"]["role"] = {"enum": [r.value for r in MODEL_ROLES], "type": "string"}
    schema["properties"]["block_roles"]["maxItems"] = MODEL_MAX_ROLES
    field = defs["FieldSpec"]
    field["required"] = [*field.get("required", []), "required"]
    field["properties"]["required"].pop("default", None)
    defs["ApplicantSpec"]["properties"].pop("pesel", None)  # the code decides (presort)
    for obj in (schema, *defs.values()):
        _only_non_defaults(obj)
    defs["ApplicantSpec"]["minProperties"] = 1  # an empty "applicant": {} is the default: leave it out
    return schema


def _only_non_defaults(obj: dict) -> None:
    """An optional key may be written only with a value that differs from its default; otherwise it is left
    out (Pydantic fills the default when reading). A default value is output time and cost for nothing:
    the saved specs are ~45% default values (null, [], false) when every key is written.
    - `null` is not allowed (description, dictionary, prefill, show_if, max_files, to, summary),
    - a list needs at least one item (options, validators, allowed_formats, blocks, consents, block_roles),
    - a flag can only be written as the non-default value (repeating, negate, entity: true; signed,
      other_person: false), a string with a default only as another value (authority_kind: "organ")."""
    required = set(obj.get("required", []))
    for name, prop in (obj.get("properties") or {}).items():
        if name in required:
            continue
        default = prop.pop("default", None)
        if "anyOf" in prop:
            options = [o for o in prop["anyOf"] if o.get("type") != "null"]
            if len(options) == 1:
                prop.pop("anyOf")
                prop.update(options[0])
            else:
                prop["anyOf"] = options
        if prop.get("type") == "array":
            prop["minItems"] = max(prop.get("minItems", 0), 1)
        elif prop.get("type") == "boolean" and isinstance(default, bool):
            prop["enum"] = [not default]
        elif isinstance(default, str) and "enum" in prop:
            prop["enum"] = [v for v in prop["enum"] if v != default]
        elif isinstance(default, str) and "$ref" in prop:
            pass  # an enum class by reference: kept as is (not used for optional keys today)
