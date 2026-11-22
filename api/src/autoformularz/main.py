"""REST API."""

import logging
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from autoformularz import jobs, pipeline
from autoformularz.auth import require_jwt
from autoformularz.config import Settings, get_settings
from autoformularz.lint import as_dicts, lint
from autoformularz.llm import LLMError, llm_status, warn_if_dev_provider
from autoformularz.spec import FormSpec
from autoformularz.upload import UploadError, validate_upload

app = FastAPI(
    title="autoformularz",
    version="0.1.0",
    description="Zamienia plik formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) "
    "na konfigurację formularza e-usługi w formacie JSON.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Autoformularz-Errors", "X-Autoformularz-Warnings"],
)


def setup_logging() -> None:
    """INFO logs of the app (metrics line per conversion, Eden usage) to stderr next to uvicorn's log.
    Without a handler Python shows only warnings, so these lines were lost."""
    app_log = logging.getLogger("autoformularz")
    if not app_log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        app_log.addHandler(handler)
        app_log.setLevel(logging.INFO)
        app_log.propagate = False


setup_logging()
warn_if_dev_provider(get_settings())

Auth = Annotated[dict | None, Depends(require_jwt)]
Cfg = Annotated[Settings, Depends(get_settings)]


@app.exception_handler(UploadError)
async def upload_error(_: Request, e: UploadError) -> JSONResponse:
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


@app.exception_handler(LLMError)
async def llm_error(_: Request, e: LLMError) -> JSONResponse:
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


def body(result: pipeline.Result, details: bool) -> dict[str, Any]:
    """The importable JSON as-is, or with `details` also FormSpec, lint issues, notes and coverage."""
    if not details:
        return result.form
    return {
        "form": result.form,
        "spec": result.spec.model_dump(mode="json"),
        "issues": as_dicts(result.issues),
        "notes": result.notes,
        "sourceFormat": result.source_format,
        "document": result.document.as_dict() if result.document else None,
        "coverage": result.coverage.as_dict() if result.coverage else None,
        # Speed, tokens and cost of this conversion (null for /compile): to compare runs.
        "metrics": result.metrics.as_dict() if result.metrics else None,
    }


def respond(result: pipeline.Result, details: bool) -> JSONResponse:
    errors = sum(i.level == "error" for i in result.issues)
    headers = {
        "X-Autoformularz-Errors": str(errors),
        "X-Autoformularz-Warnings": str(len(result.issues) - errors),
    }
    return JSONResponse(body(result, details), headers=headers)


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@app.get("/health")
def health(settings: Cfg) -> dict:
    return {"status": "ok", "llm": llm_status(settings)}


@app.post("/api/v1/forms", summary="Plik formularza → JSON konfiguracji e-formularza")
async def convert(
    _: Auth,
    settings: Cfg,
    file: Annotated[UploadFile, File(description="Jeden plik: pdf, doc, docx, ods, xlsx, jpg, jpeg, png")],
    details: Annotated[bool, Query(description="Zwróć też FormSpec, raport walidacji i uwagi")] = False,
) -> JSONResponse:
    max_bytes = int(settings.max_upload_mb * 1_048_576)
    data = await file.read(max_bytes + 1)  # read one byte over the limit to detect oversize files
    result = await run_in_threadpool(pipeline.from_file, file.filename, data, settings)
    return respond(result, details)


@app.post(
    "/api/v1/jobs",
    status_code=202,
    summary="Plik formularza → zadanie w tle; postęp i wynik w GET /api/v1/jobs/{id}",
)
async def start_job(
    _: Auth,
    settings: Cfg,
    file: Annotated[UploadFile, File(description="Jeden plik: pdf, doc, docx, ods, xlsx, jpg, jpeg, png")],
    details: Annotated[bool, Query(description="Wynik z FormSpec, raportem walidacji i uwagami")] = False,
) -> JSONResponse:
    max_bytes = int(settings.max_upload_mb * 1_048_576)
    data = await file.read(max_bytes + 1)
    validate_upload(file.filename, data, max_bytes)  # a bad file is a 4xx now, not a failed job
    name = file.filename
    job = jobs.start(lambda: body(pipeline.from_file(name, data, settings), details))
    if job is None:
        return error(429, "BUSY", "Serwer przetwarza już zbyt wiele plików. Spróbuj ponownie za chwilę.")
    return JSONResponse({"id": job.id}, status_code=202)


@app.get("/api/v1/jobs/{job_id}", summary="Postęp zadania (kroki) i wynik, gdy gotowe")
def job_status(_: Auth, job_id: str) -> JSONResponse:
    if (job := jobs.get(job_id)) is None:
        return error(404, "JOB_NOT_FOUND", "Nie ma takiego zadania (mogło wygasnąć).")
    return JSONResponse(job.view())


@app.delete("/api/v1/jobs/{job_id}", status_code=204, summary="Anuluj zadanie (model przestaje pisać)")
def cancel_job(_: Auth, job_id: str) -> Response:
    if not jobs.cancel(job_id):
        return error(404, "JOB_NOT_FOUND", "Nie ma takiego zadania (mogło wygasnąć).")
    return Response(status_code=204)


@app.post("/api/v1/forms/compile", summary="FormSpec → JSON (bez modelu, np. po ręcznej korekcie)")
def compile_spec(_: Auth, spec: FormSpec, details: bool = False) -> JSONResponse:
    return respond(pipeline.from_spec(spec), details)


@app.post("/api/v1/forms/validate", summary="Sprawdź JSON formularza względem reguł technicznych")
def validate(_: Auth, form: dict[str, Any]) -> dict:
    issues = lint(form)
    return {"valid": not any(i.level == "error" for i in issues), "issues": as_dicts(issues)}


@app.get("/api/v1/spec/schema", summary="Schemat JSON modelu pośredniego FormSpec")
def spec_schema() -> dict:
    # What /api/v1/forms/compile accepts (UI editor contract). The stricter model_schema() is only for the
    # model: saved specs (e.g. wyniki/02, 07, 09) have more than 40 roles or FIELD_LABEL/HEADING roles.
    return FormSpec.model_json_schema()


def run() -> None:
    import uvicorn

    uvicorn.run("autoformularz.main:app", host="0.0.0.0", port=8000)
