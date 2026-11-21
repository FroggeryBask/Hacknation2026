"""REST API."""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from formgen import pipeline
from formgen.auth import require_jwt
from formgen.config import Settings, get_settings
from formgen.lint import as_dicts, lint
from formgen.llm import LLMError, llm_status
from formgen.spec import FormSpec
from formgen.upload import UploadError

app = FastAPI(
    title="formgen",
    version="0.1.0",
    description="Zamienia plik formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) "
    "na konfigurację formularza e-usługi w formacie JSON.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Formgen-Errors", "X-Formgen-Warnings"],
)

Auth = Annotated[dict | None, Depends(require_jwt)]
Cfg = Annotated[Settings, Depends(get_settings)]


@app.exception_handler(UploadError)
async def upload_error(_: Request, e: UploadError) -> JSONResponse:
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


@app.exception_handler(LLMError)
async def llm_error(_: Request, e: LLMError) -> JSONResponse:
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


def respond(result: pipeline.Result, details: bool) -> JSONResponse:
    errors = sum(i.level == "error" for i in result.issues)
    headers = {"X-Formgen-Errors": str(errors), "X-Formgen-Warnings": str(len(result.issues) - errors)}
    if not details:
        return JSONResponse(result.form, headers=headers)
    body: dict[str, Any] = {
        "form": result.form,
        "spec": result.spec.model_dump(mode="json"),
        "issues": as_dicts(result.issues),
        "notes": result.notes,
        "sourceFormat": result.source_format,
    }
    return JSONResponse(body, headers=headers)


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


@app.post("/api/v1/forms/compile", summary="FormSpec → JSON (bez modelu, np. po ręcznej korekcie)")
def compile_spec(_: Auth, spec: FormSpec, details: bool = False) -> JSONResponse:
    return respond(pipeline.from_spec(spec), details)


@app.post("/api/v1/forms/validate", summary="Sprawdź JSON formularza względem reguł technicznych")
def validate(_: Auth, form: dict[str, Any]) -> dict:
    issues = lint(form)
    return {"valid": not any(i.level == "error" for i in issues), "issues": as_dicts(issues)}


@app.get("/api/v1/spec/schema", summary="Schemat JSON modelu pośredniego FormSpec")
def spec_schema() -> dict:
    return FormSpec.model_json_schema()


def run() -> None:
    import uvicorn

    uvicorn.run("formgen.main:app", host="0.0.0.0", port=8000)
