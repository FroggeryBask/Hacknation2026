"""Generates the deliverable result files in `wyniki/` from the task materials.

    cd api
    uv run python -m autoformularz.results              # forms 2,3,4,6,7,8,9: model only where no spec yet
    uv run python -m autoformularz.results --only 2 3   # selected forms
    uv run python -m autoformularz.results --compile    # NO model: rebuild JSON from saved specs
    uv run python -m autoformularz.results --force      # ask the model again even if a spec exists

Per form `NN`: `NN.json` (COI form, the deliverable), `NN.spec.json` (FormSpec from the model),
`NN.report.json` (source, model, lint issues, notes, coverage). The spec is the only model output:
everything else is rebuilt from it deterministically, so a compiler change costs no model calls.
The model (Ollama or Eden AI) comes from the usual settings (.env.local). Eden AI usage (tokens, cost in
USD as reported by Eden) goes to each report and a summary line for docs/eden-budzet.md is printed."""

import argparse
import datetime
import json
import sys
from pathlib import Path

from autoformularz import llm, pipeline
from autoformularz.check import coverage
from autoformularz.config import Settings
from autoformularz.extract import extract
from autoformularz.lint import as_dicts
from autoformularz.ocr import ocr_from
from autoformularz.spec import FormSpec
from autoformularz.upload import validate_upload

ROOT = Path(__file__).resolve().parents[3]
MATERIALS = ROOT / "materialy"
OUT = ROOT / "wyniki"
FORMS = [2, 3, 4, 6, 7, 8, 9]  # forms to digitise (1 and 5 have reference JSON)
# Best source first: DOCX keeps text boxes and reading order; PDF text next; scans last.
SOURCE_ORDER = [".docx", ".doc", ".pdf", ".xlsx", ".ods", ".png", ".jpg", ".jpeg"]


def source_file(n: int) -> Path:
    folder = next(MATERIALS.glob(f"{n}. *"))
    files = {f.suffix.lower(): f for f in sorted(folder.iterdir()) if "wizualizacja" not in f.name.lower()}
    return next(files[ext] for ext in SOURCE_ORDER if ext in files)


def write(path: Path, data) -> None:
    # newline="\n": the same bytes on Windows and Linux (deterministic files)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def usage_since(start: int) -> dict:
    calls = llm.EDEN_USAGE[start:]
    return {
        "calls": len(calls),
        "promptTokens": sum(c["promptTokens"] for c in calls),
        "completionTokens": sum(c["completionTokens"] for c in calls),
        "costUsd": round(sum(c["cost"] for c in calls), 6),
    }


def run(n: int, settings: Settings, *, compile_only: bool, force: bool) -> str:
    src = source_file(n)
    data = src.read_bytes()
    kind = validate_upload(src.name, data, int(settings.max_upload_mb * 1_048_576))
    ocr = ocr_from(settings.ocr_bin, settings.ocr_lang, settings.tessdata_dir)
    document = extract(kind, data, soffice=settings.soffice_bin, max_pages=settings.max_pdf_pages, ocr=ocr)
    spec_path = OUT / f"{n:02d}.spec.json"
    if spec_path.exists() and not force:
        spec = FormSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
        model = "zapisany FormSpec"
        usage = usage_since(len(llm.EDEN_USAGE))
    elif compile_only:
        return f"{n:02d}: pominięty (brak {spec_path.name}, --compile nie pyta modelu)"
    else:
        start = len(llm.EDEN_USAGE)
        try:
            spec = pipeline.ask_model(document, settings)
        except llm.LLMError as e:
            if e.partial:  # paid for: keep it to see where the model got stuck (not committed)
                (OUT / f"{n:02d}.truncated.txt").write_text(e.partial, encoding="utf-8", newline="\n")
            raise
        write(spec_path, spec.model_dump(mode="json"))
        usage = usage_since(start)
        model = settings.eden_model if settings.llm_provider == "eden" else settings.llm_model
    result = pipeline.from_spec(spec, document if settings.copy_source_text else None)
    errors = sum(i.level == "error" for i in result.issues)
    write(OUT / f"{n:02d}.json", result.form)
    write(
        OUT / f"{n:02d}.report.json",
        {
            "source": src.relative_to(ROOT).as_posix(),
            "sourceFormat": kind.value,
            "model": model,
            "errors": errors,
            "issues": as_dicts(result.issues),
            "notes": document.notes + result.notes,
            "coverage": coverage(spec, document).as_dict(),
            "edenUsage": usage,
        },
    )
    return f"{n:02d}: {src.name} -> błędy lintera: {errors}, ostrzeżenia: {len(result.issues) - errors} ({model})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", type=int, nargs="+", help="numery formularzy, np. --only 2 3")
    ap.add_argument("--compile", action="store_true", help="bez modelu: tylko z zapisanych FormSpec")
    ap.add_argument("--force", action="store_true", help="zapytaj model ponownie mimo zapisanego FormSpec")
    args = ap.parse_args(argv)
    settings = Settings()
    OUT.mkdir(exist_ok=True)
    failed = 0
    start = len(llm.EDEN_USAGE)
    for n in args.only or FORMS:
        try:
            print(run(n, settings, compile_only=args.compile, force=args.force), flush=True)
        except Exception as e:  # one bad form must not stop the others
            failed += 1
            print(f"{n:02d}: BŁĄD {type(e).__name__}: {getattr(e, 'message', e)}", flush=True)
    total = usage_since(start)
    if total["calls"]:
        forms = ",".join(str(n) for n in args.only or FORMS)
        print()
        print(
            f"Eden AI: {total['calls']} zapytań, {total['promptTokens']}+{total['completionTokens']} "
            f"tokenów, {total['costUsd']:.4f} USD. Linia do docs/eden-budzet.md:"
        )
        print(
            f"| {datetime.date.today()} | <kto> | wyniki (formularze {forms}) | {settings.eden_model} | "
            f"{total['calls']} | {total['costUsd']:.4f} |"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
