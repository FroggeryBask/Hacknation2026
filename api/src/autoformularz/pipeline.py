"""The whole conversion: validate upload -> extract -> LLM (FormSpec) -> check -> compile -> lint."""

from dataclasses import dataclass, field
from typing import Any

from autoformularz import llm as llm_module
from autoformularz import presort as presort_step
from autoformularz.check import (
    Coverage,
    coverage,
    dedupe,
    drop_broken_conditions,
    drop_standard_sections,
    printed_amounts_as_info,
)
from autoformularz.compiler import compile_form
from autoformularz.config import Settings
from autoformularz.document import Document
from autoformularz.extract import extract
from autoformularz.lint import Issue, lint
from autoformularz.llm import generate_spec
from autoformularz.ocr import ocr_from
from autoformularz.spec import FormSpec
from autoformularz.upload import validate_upload


@dataclass
class Result:
    form: dict[str, Any]
    spec: FormSpec
    issues: list[Issue]
    notes: list[str] = field(default_factory=list)
    source_format: str | None = None
    document: Document | None = None  # None for /compile (no source file)
    coverage: Coverage | None = None


def from_spec(spec: FormSpec, document: Document | None = None) -> Result:
    """Canon, then compile. `document` (the source file) adds verbatim legal text; None for /compile."""
    # Canon: a model's repetitions and copies of the predefined part never reach the form.
    spec, repeated = dedupe(spec)
    spec, standard = drop_standard_sections(spec)
    spec, amounts = printed_amounts_as_info(spec)
    spec, conditions = drop_broken_conditions(spec)  # last: the rules above may drop a controlling field
    form, warnings = compile_form(spec, document)
    return Result(
        form=form, spec=spec, issues=lint(form), notes=repeated + standard + amounts + conditions + warnings
    )


def ask_model(document: Document, settings: Settings, llm=None) -> FormSpec:
    """The model's FormSpec. With presort on, blocks the code recognised (GDPR clause, paper-only lines,
    the template's applicant data) are left out of the prompt and their roles are added afterwards.
    `llm` defaults to `llm_module.generate_spec`, looked up at call time (tests replace it)."""
    call = llm or llm_module.generate_spec
    if not settings.presort:
        return call(document, settings)
    pre = presort_step.presort(document)
    return presort_step.apply(call(pre.model_doc, settings), pre)


def from_file(name: str | None, data: bytes, settings: Settings, llm=generate_spec) -> Result:
    kind = validate_upload(name, data, int(settings.max_upload_mb * 1_048_576))
    ocr = ocr_from(settings.ocr_bin, settings.ocr_lang, settings.tessdata_dir)
    document = extract(kind, data, soffice=settings.soffice_bin, max_pages=settings.max_pdf_pages, ocr=ocr)
    spec = ask_model(document, settings, llm)
    result = from_spec(spec, document if settings.copy_source_text else None)
    result.notes = document.notes + result.notes
    result.source_format = kind.value
    result.document = document
    result.coverage = coverage(spec, document)
    return result
