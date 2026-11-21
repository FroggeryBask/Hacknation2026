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
    block: str = Field(description="Block ID from the document, e.g. 'b12'.")
    role: Role


def _blocks():
    return Field(
        default_factory=list,
        description="IDs of the source blocks this element comes from (label, options), e.g. ['b12', 'b13'].",
    )


class Condition(BaseModel):
    """Show the element only when a choice field has (or has not) a given option selected."""

    field: str = Field(description="Label of the controlling choice field (exactly as in this spec).")
    equals: str = Field(description="Option label that must be selected.")
    negate: bool = Field(default=False, description="True = show when the option is NOT selected.")


class FieldSpec(BaseModel):
    label: str
    kind: Kind
    required: bool = True
    description: str | None = Field(default=None, description="Short hint under the field, plain language.")
    options: list[str] = Field(default_factory=list, description="Options for choice fields.")
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
    fields: list[FieldSpec]
    show_if: Condition | None = None
    blocks: list[str] = _blocks()


class PageSpec(BaseModel):
    title: str = Field(description="Short page title describing its topic, e.g. 'Informacje o budynku'.")
    sections: list[SectionSpec]


class ApplicantSpec(BaseModel):
    """Who may file the form. Drives the predefined 'Podmiot wniosku' and related sections."""

    other_person: bool = Field(
        default=True, description="Filing on behalf of another natural person is allowed."
    )
    entity: bool = Field(
        default=False, description="The paper form has company/institution data (NIP, REGON, KRS, name)."
    )
    entity_nip_only: bool = Field(default=False, description="Paper form asks only name + NIP of entity.")


class FormSpec(BaseModel):
    title: str = Field(description="Starts with Wniosek/Zgłoszenie/Deklaracja/Oświadczenie, no legal refs.")
    authority_kind: Literal["urząd", "organ"] = Field(
        default="urząd", description="'organ' when addressed to an official (Wójt, Burmistrz, Prezydent)."
    )
    authority_name: str = Field(description="Office or authority with its unit, e.g. 'Urząd Gminy X'.")
    applicant: ApplicantSpec = Field(default_factory=ApplicantSpec)
    pages: list[PageSpec] = Field(description="Case-specific pages only (subject of the application).")
    consents: list[str] = Field(
        default_factory=list, description="Statements the applicant confirms (besides the GDPR consent)."
    )
    summary: str | None = Field(default=None, description="Optional info on what happens after sending.")
    signed: bool = True
    block_roles: list[BlockRole] = Field(
        default_factory=list,
        # Only text the compiler copies or drops: listing every block overflows the context on big forms.
        description="Only blocks with instructions, legal basis, statements, GDPR text, and SKIP for "
        "paper-only text. Not for field labels, options or headings (blocks without a role are allowed).",
    )

    def referenced_blocks(self) -> set[str]:
        """Block IDs used anywhere in the spec (fields, sections, roles)."""
        refs = {r.block for r in self.block_roles}
        for page in self.pages:
            for section in page.sections:
                refs.update(section.blocks)
                for f in section.fields:
                    refs.update(f.blocks)
        return refs
