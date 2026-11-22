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
USD as reported by Eden) goes to each report and a summary line for docs/eden-budzet.md is printed.
Every model call also appends its metrics (time, tokens, cost, answer shape, settings) to
`wyniki/metrics.jsonl` and keeps the raw answer in `NN.raw.txt` (both not committed): compare runs with
`uv run python -m autoformularz.results --metrics`."""

import argparse
import datetime
import json
import sys
from pathlib import Path

from autoformularz import llm, metrics, pipeline
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


def metrics_file() -> Path:
    """wyniki/metrics.jsonl, from OUT at call time (tests point OUT at a temporary folder)."""
    return OUT / "metrics.jsonl"


def settings_snapshot(settings: Settings) -> dict:
    """What can change between runs and explain a difference."""
    from autoformularz.extract import JPEG_QUALITY, MAX_IMAGE_SIDE

    return {
        "provider": settings.llm_provider,
        "model": settings.eden_model if settings.llm_provider == "eden" else settings.llm_model,
        "presort": settings.presort,
        "maxTokens": settings.llm_max_tokens,
        "numCtx": settings.llm_num_ctx,
        "reasoningEffort": settings.eden_reasoning_effort,
        "maxPdfPages": settings.max_pdf_pages,
        "imageSide": MAX_IMAGE_SIDE,
        "jpegQuality": JPEG_QUALITY,
    }


def save_metrics(n: int, m: metrics.Metrics, settings: Settings) -> None:
    """One line per model run in wyniki/metrics.jsonl and the raw answers in NN.raw.txt (not committed)."""
    line = {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "form": n,
        "settings": settings_snapshot(settings),
        **m.as_dict(),
    }
    with metrics_file().open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    raws = [c.raw for c in m.calls if c.raw]
    if raws:
        (OUT / f"{n:02d}.raw.txt").write_text(
            "\n\n----- next call -----\n\n".join(raws), encoding="utf-8", newline="\n"
        )


def run(n: int, settings: Settings, *, compile_only: bool, force: bool) -> str:
    with metrics.collecting() as m:
        return _run(n, settings, m, compile_only=compile_only, force=force)


def _run(n: int, settings: Settings, m: metrics.Metrics, *, compile_only: bool, force: bool) -> str:
    src = source_file(n)
    data = src.read_bytes()
    kind = validate_upload(src.name, data, int(settings.max_upload_mb * 1_048_576))
    metrics.file_info(data, kind.value)
    ocr = ocr_from(settings.ocr_bin, settings.ocr_lang, settings.tessdata_dir)
    with metrics.step("extract"):
        document = extract(
            kind, data, soffice=settings.soffice_bin, max_pages=settings.max_pdf_pages, ocr=ocr
        )
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
            m.error = e.code
            save_metrics(n, m, settings)
            raise
        write(spec_path, spec.model_dump(mode="json"))
        usage = usage_since(start)
        model = settings.eden_model if settings.llm_provider == "eden" else settings.llm_model
    with metrics.step("compile"):
        result = pipeline.from_spec(spec, document if settings.copy_source_text else None)
    errors = sum(i.level == "error" for i in result.issues)
    if m.calls:  # the model was asked in this run: keep its metrics to compare runs
        pipeline.summarise(m, result)
        save_metrics(n, m, settings)
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


def compare_metrics(path: Path | None = None) -> str:
    """Runs from wyniki/metrics.jsonl side by side (latest last), to see what a change did."""
    path = path or metrics_file()
    if not path.exists():
        return f"Brak {path.name}: metryki zapisują się przy zapytaniu modelu (bez --compile)."
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    head = (
        f"{'czas':19} {'nr':>2} {'model':>8} {'s':>6} {'1. tok':>6} {'in tok':>7} {'out tok':>7} "
        f"{'USD':>8} {'img tok':>7} {'null':>5} {'[]':>4} {'false':>5} {'pola':>4} {'błędy':>5} {'stop':>8}"
    )
    out = [head]
    for r in rows:
        calls = r.get("calls") or [{}]
        model_s = sum(c.get("seconds") or 0 for c in calls)
        first = calls[0].get("firstTokenS")
        out.append(
            f"{r['time']:19} {r['form']:>2} {r['settings']['provider']:>8} {model_s:6.1f} "
            f"{first if first is not None else '-':>6} {r.get('promptTokens') or '-':>7} "
            f"{r.get('completionTokens') or '-':>7} {r.get('costUsd') or 0:8.4f} "
            f"{sum(c.get('imageTokensEst') or 0 for c in calls):>7} "
            f"{sum(c.get('answerNulls') or 0 for c in calls):>5} {sum(c.get('answerEmptyLists') or 0 for c in calls):>4} "
            f"{sum(c.get('answerFalse') or 0 for c in calls):>5} {r.get('fields', 0):>4} "
            f"{r.get('lintErrors', 0):>5} {(r.get('error') or calls[-1].get('finishReason') or '-'):>8}"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", type=int, nargs="+", help="numery formularzy, np. --only 2 3")
    ap.add_argument("--compile", action="store_true", help="bez modelu: tylko z zapisanych FormSpec")
    ap.add_argument("--force", action="store_true", help="zapytaj model ponownie mimo zapisanego FormSpec")
    ap.add_argument(
        "--metrics", action="store_true", help="tabela porównawcza z wyniki/metrics.jsonl (bez modelu)"
    )
    args = ap.parse_args(argv)
    if args.metrics:
        print(compare_metrics())
        return 0
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
