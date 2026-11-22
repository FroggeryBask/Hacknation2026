"""The whole conversion: validate upload -> extract -> LLM (FormSpec) -> check -> compile -> lint."""

from dataclasses import dataclass, field
from typing import Any

from autoformularz import llm as llm_module
from autoformularz import presort as presort_step
from autoformularz import progress
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


def from_spec(spec: FormSpec, document: Document | None = None, *, quiet: bool = False) -> Result:
    """Canon, then compile. `document` (the source file) adds verbatim legal text; None for /compile.
    `quiet`: no progress (scoring several answers)."""
    # Canon: a model's repetitions and copies of the predefined part never reach the form.
    if not quiet:
        progress.stage("Budowanie formularza JSON")
    spec, repeated = dedupe(spec)
    spec, standard = drop_standard_sections(spec)
    spec, amounts = printed_amounts_as_info(spec)
    spec, paper = drop_paper_only_fields(spec)
    spec, conditions = drop_broken_conditions(spec)  # last: the rules above may drop a controlling field
    form, warnings = compile_form(spec, document)
    if not quiet:
        progress.stage("Sprawdzanie reguł technicznych")
    issues = lint(form)
    errors = sum(i.level == "error" for i in issues)
    if not quiet:
        progress.item(f"Błędy: {errors}, ostrzeżenia: {len(issues) - errors}")
    return Result(
        form=form,
        spec=spec,
        issues=issues,
        notes=repeated + standard + amounts + paper + conditions + warnings,
    )


def score(spec: FormSpec, document: Document) -> tuple[int, int, int, int]:
    """How good an answer is, higher is better, compared in this order: lint errors, places to fill in on
    the paper that got no field (the form skipped something), elements the canon had to drop (made-up,
    repeated or template sections and fields), and the number of fields and statements kept."""
    result = from_spec(spec, quiet=True)
    errors = sum(i.level == "error" for i in result.issues)
    missing = len(coverage(result.spec, document).candidates_without_field)
    dropped = sum(n.startswith("Pominięto") for n in result.notes)
    # Statements count with fields: made-up ones are already gone (presort.grounded_consents).
    fields = sum(len(s.fields) for p in result.spec.pages for s in p.sections) + len(result.spec.consents)
    return (-errors, -missing, -dropped, fields)


def ask_model(document: Document, settings: Settings, llm=None) -> FormSpec:
    """The best of `settings.llm_samples` answers (`score`); the first with temperature 0, the others
    sampled so they differ. A failed answer is skipped while another one succeeds."""
    samples = max(1, settings.llm_samples)
    best: tuple[tuple, FormSpec] | None = None
    error: Exception | None = None
    for i in range(samples):
        run = (
            settings
            if i == 0
            else settings.model_copy(update={"llm_temperature": settings.llm_sample_temperature})
        )
        if samples > 1:
            progress.stage(f"Wersja {i + 1} z {samples}")
        try:
            spec = _ask_once(document, run, llm)
        except llm_module.LLMError as e:
            error = e
            continue
        if samples == 1:
            return spec
        value = score(spec, document)
        progress.item(
            f"Ocena: błędy {-value[0]}, pominięte miejsca {-value[1]}, odrzucone {-value[2]}, pola {value[3]}"
        )
        if best is None or value > best[0]:
            best = (value, spec)
    if best is None:
        raise error or llm_module.LLMError("LLM_ERROR", "Model nie odpowiedział.")
    return best[1]


def _ask_once(document: Document, settings: Settings, llm=None) -> FormSpec:
    """The model's FormSpec. With presort on, blocks the code recognised (GDPR clause, paper-only lines,
    the template's applicant data) are left out of the prompt and their roles are added afterwards.
    `llm` defaults to `llm_module.generate_spec`, looked up at call time (tests replace it)."""
    call = llm or llm_module.generate_spec
    if not settings.presort:
        return call(document, settings)
    progress.stage("Rozpoznawanie części standardowej")
    pre = presort_step.presort(document)
    if dropped := sum(pre.counts.values()):
        progress.item(
            f"Fragmenty rozpoznane bez modelu (RODO, części papierowe, dane wnioskodawcy): {dropped}"
        )
    return presort_step.apply(call(pre.model_doc, settings), pre)


def from_file(name: str | None, data: bytes, settings: Settings, llm=generate_spec) -> Result:
    progress.stage("Sprawdzanie pliku")
    kind = validate_upload(name, data, int(settings.max_upload_mb * 1_048_576))
    progress.stage("Odczytywanie dokumentu")
    ocr = ocr_from(settings.ocr_bin, settings.ocr_lang, settings.tessdata_dir)
    document = extract(kind, data, soffice=settings.soffice_bin, max_pages=settings.max_pdf_pages, ocr=ocr)
    progress.item(f"Fragmenty tekstu: {len(document.blocks)}, obrazy stron: {len(document.images)}")
    spec = ask_model(document, settings, llm)
    result = from_spec(spec, document if settings.copy_source_text else None)
    result.notes = document.notes + result.notes
    result.source_format = kind.value
    result.document = document
    result.coverage = coverage(spec, document)
    return result
