"""The whole conversion: validate upload -> extract -> LLM (FormSpec) -> check -> compile -> lint."""

from dataclasses import dataclass, field
from typing import Any

from autoformularz.check import Coverage, coverage, dedupe, drop_standard_sections
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


def from_spec(spec: FormSpec) -> Result:
    # Canon: a model's repetitions and copies of the predefined part never reach the form.
    spec, repeated = dedupe(spec)
    spec, standard = drop_standard_sections(spec)
    form, warnings = compile_form(spec)
    return Result(form=form, spec=spec, issues=lint(form), notes=repeated + standard + warnings)


def from_file(name: str | None, data: bytes, settings: Settings, llm=generate_spec) -> Result:
    kind = validate_upload(name, data, int(settings.max_upload_mb * 1_048_576))
    ocr = ocr_from(settings.ocr_bin, settings.ocr_lang, settings.tessdata_dir)
    document = extract(kind, data, soffice=settings.soffice_bin, max_pages=settings.max_pdf_pages, ocr=ocr)
    spec = llm(document, settings)
    result = from_spec(spec)
    result.notes = document.notes + result.notes
    result.source_format = kind.value
    result.document = document
    result.coverage = coverage(spec, document)
    return result
