"""The whole conversion: validate upload -> extract -> LLM (FormSpec) -> check -> compile -> lint."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from autoformularz import llm as llm_module
from autoformularz import metrics, progress
from autoformularz import presort as presort_step
from autoformularz.check import (
    Coverage,
    coverage,
    dedupe,
    drop_broken_conditions,
    drop_paper_only_fields,
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
from autoformularz.upload import UploadError, validate_upload

log = logging.getLogger("autoformularz.metrics")


@dataclass
class Result:
    form: dict[str, Any]
    spec: FormSpec
    issues: list[Issue]
    notes: list[str] = field(default_factory=list)
    source_format: str | None = None
    document: Document | None = None  # None for /compile (no source file)
    coverage: Coverage | None = None
    metrics: metrics.Metrics | None = None  # None for /compile (no model call)


def from_spec(spec: FormSpec, document: Document | None = None) -> Result:
    """Canon, then compile. `document` (the source file) adds verbatim legal text; None for /compile."""
    # Canon: a model's repetitions and copies of the predefined part never reach the form.
    progress.stage("Budowanie formularza JSON")
    spec, repeated = dedupe(spec)
    spec, standard = drop_standard_sections(spec)
    spec, amounts = printed_amounts_as_info(spec)
    spec, paper = drop_paper_only_fields(spec)
    spec, conditions = drop_broken_conditions(spec)  # last: the rules above may drop a controlling field
    form, warnings = compile_form(spec, document)
    progress.stage("Sprawdzanie reguł technicznych")
    issues = lint(form)
    errors = sum(i.level == "error" for i in issues)
    progress.item(f"Błędy: {errors}, ostrzeżenia: {len(issues) - errors}")
    return Result(
        form=form,
        spec=spec,
        issues=issues,
        notes=repeated + standard + amounts + paper + conditions + warnings,
    )


def ask_model(document: Document, settings: Settings, llm=None) -> FormSpec:
    """The model's FormSpec. With presort on, blocks the code recognised (GDPR clause, paper-only lines,
    the template's applicant data) are left out of the prompt and their roles are added afterwards.
    `llm` defaults to `llm_module.generate_spec`, looked up at call time (tests replace it)."""
    call = llm or llm_module.generate_spec
    m = metrics.current()
    if m is not None:
        m.blocks, m.candidates = len(document.blocks), len(document.candidates)
    if not settings.presort:
        with metrics.step("model"):
            return call(document, settings)
    progress.stage("Rozpoznawanie części standardowej")
    with metrics.step("presort"):
        pre = presort_step.presort(document)
    if m is not None:
        m.presort, m.blocks_to_model = dict(pre.counts), len(pre.model_doc.blocks)
    if dropped := sum(pre.counts.values()):
        progress.item(
            f"Fragmenty rozpoznane bez modelu (RODO, części papierowe, dane wnioskodawcy): {dropped}"
        )
    with metrics.step("model"):
        spec = call(pre.model_doc, settings)
    return presort_step.apply(spec, pre)


def summarise(m: metrics.Metrics, result: Result) -> None:
    """Size of the result (to compare runs: a faster run must not lose pages or fields)."""
    m.pages = len(result.spec.pages)
    m.sections = sum(len(p.sections) for p in result.spec.pages)
    m.fields = sum(len(s.fields) for p in result.spec.pages for s in p.sections)
    m.lint_errors = sum(i.level == "error" for i in result.issues)
    m.lint_warnings = len(result.issues) - m.lint_errors


def log_metrics(m: metrics.Metrics) -> None:
    """One JSON line per conversion (no file name, no text): `docker compose logs api | grep metrics`."""
    log.info("metrics %s", json.dumps(m.as_dict(), ensure_ascii=False))


def from_file(name: str | None, data: bytes, settings: Settings, llm=generate_spec) -> Result:
    with metrics.collecting() as m:
        try:
            result = _from_file(name, data, settings, llm, m)
        except (llm_module.LLMError, UploadError) as e:
            m.error = e.code
            log_metrics(m)
            raise
        summarise(m, result)
        result.metrics = m
        log_metrics(m)
        return result


def _from_file(name: str | None, data: bytes, settings: Settings, llm, m: metrics.Metrics) -> Result:
    progress.stage("Sprawdzanie pliku")
    with metrics.step("check"):
        kind = validate_upload(name, data, int(settings.max_upload_mb * 1_048_576))
    metrics.file_info(data, kind.value)
    progress.stage("Odczytywanie dokumentu")
    with metrics.step("extract"):  # includes OCR and LibreOffice
        ocr = ocr_from(settings.ocr_bin, settings.ocr_lang, settings.tessdata_dir)
        document = extract(
            kind, data, soffice=settings.soffice_bin, max_pages=settings.max_pdf_pages, ocr=ocr
        )
    progress.item(f"Fragmenty tekstu: {len(document.blocks)}, obrazy stron: {len(document.images)}")
    spec = ask_model(document, settings, llm)
    with metrics.step("compile"):  # canon + compiler + lint + coverage
        result = from_spec(spec, document if settings.copy_source_text else None)
        result.coverage = coverage(spec, document)
    result.notes = document.notes + result.notes
    result.source_format = kind.value
    result.document = document
    return result
