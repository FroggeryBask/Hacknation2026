"""The whole conversion: validate upload -> extract -> LLM (FormSpec) -> compile -> lint."""

from dataclasses import dataclass, field
from typing import Any

from autoformularz.compiler import compile_form
from autoformularz.config import Settings
from autoformularz.extract import extract
from autoformularz.lint import Issue, lint
from autoformularz.llm import generate_spec
from autoformularz.spec import FormSpec
from autoformularz.upload import validate_upload


@dataclass
class Result:
    form: dict[str, Any]
    spec: FormSpec
    issues: list[Issue]
    notes: list[str] = field(default_factory=list)
    source_format: str | None = None


def from_spec(spec: FormSpec) -> Result:
    form, warnings = compile_form(spec)
    return Result(form=form, spec=spec, issues=lint(form), notes=warnings)


def from_file(name: str | None, data: bytes, settings: Settings, llm=generate_spec) -> Result:
    kind = validate_upload(name, data, int(settings.max_upload_mb * 1_048_576))
    extracted = extract(kind, data, soffice=settings.soffice_bin, max_pages=settings.max_pdf_pages)
    spec = llm(extracted, settings)
    result = from_spec(spec)
    result.notes = extracted.notes + result.notes
    result.source_format = kind.value
    return result
