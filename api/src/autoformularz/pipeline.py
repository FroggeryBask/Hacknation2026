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
    """The best of `settings.llm_samples` answers (`score`), completed with sections the other answers
    wrote for places it skipped (`complete_from`); the first answer with temperature 0, the others sampled
    so they differ. A failed answer is skipped while another one succeeds."""
    samples = max(1, settings.llm_samples)
    answers: list[tuple[tuple, FormSpec]] = []
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
        answers.append((value, spec))
    if not answers:
        raise error or llm_module.LLMError("LLM_ERROR", "Model nie odpowiedział.")
    answers.sort(key=lambda a: a[0], reverse=True)
    spec, added = complete_from(answers[0][1], [a[1] for a in answers[1:]], document)
    if added:
        progress.item(f"Uzupełniono z innych wersji: {', '.join(added)}")
    return spec


def _block_no(block_id: str) -> int:
    return int(block_id[1:]) if block_id[1:].isdigit() else 10**9


def complete_from(best: FormSpec, others: list[FormSpec], document: Document) -> tuple[FormSpec, list[str]]:
    """The best answer with the sections other answers wrote for places to fill in on the paper it left
    without a field. Answers differ from run to run in what they skip (form 9: one answer has the club
    representative's and proxy's sections, another the conditions per kind of request); this keeps both. A
    section counts when every field points only to such places; it goes after the section of the best
    answer that comes before it on the paper. Its own conditions stay only if they point inside the
    section (the canon removes broken ones)."""
    missing = set(coverage(from_spec(best, quiet=True).spec, document).candidates_without_field)
    if not missing:
        return best, []
    pages = [p.model_copy(update={"sections": list(p.sections)}) for p in best.pages]
    added: list[str] = []
    for other in others:
        for page in other.pages:
            for section in page.sections:
                blocks = {b for f in section.fields for b in f.blocks}
                if not section.fields or not blocks or not blocks <= missing:
                    continue
                if not all(f.blocks for f in section.fields):
                    continue
                start, end = min(_block_no(b) for b in blocks), max(_block_no(b) for b in blocks)
                # Between the sections of the best answer around it on the paper, next to the closer one:
                # after the previous section, or before the next one (also at the top of the next page).
                before, after = None, None  # ((page, index), distance on the paper)
                for pi, pg in enumerate(pages):
                    for si, sec in enumerate(pg.sections):
                        nos = sorted(_block_no(b) for f in sec.fields for b in f.blocks)
                        if not nos:
                            continue
                        # Where a section is on the paper: the median of its blocks (an attachments section
                        # may start with a line next to this one and go on far below).
                        at = nos[len(nos) // 2]
                        if at < start and (before is None or at >= before[2]):
                            before = ((pi, si + 1), start - max(n for n in nos if n < start), at)
                        if at > end and (after is None or at < after[2]):
                            after = ((pi, si), at - end, at)
                # A heading between the previous section and this one ("1. Wnioskodawca") starts the part of
                # the paper this section belongs to: it goes with the next section.
                headed = before is not None and any(
                    start - before[1] < _block_no(b.id) < start and presort_step.is_heading(b)
                    for b in document.blocks
                )
                # …unless the next section is much farther away than the previous one (form 9: a consent
                # in the middle of the paper is not moved to the coach's part at its end).
                near_next = after is not None and before is not None and after[1] <= 2 * before[1] + 5
                if after and (before is None or (headed and near_next) or after[1] < before[1]):
                    where = after[0]
                else:
                    where = before[0] if before else (0, 0)
                if pages:
                    pi, si = where
                    pages[pi].sections.insert(si, section)
                    missing -= blocks
                    added.append(section.title)
    if not added:
        return best, []
    return best.model_copy(update={"pages": pages}), added


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
