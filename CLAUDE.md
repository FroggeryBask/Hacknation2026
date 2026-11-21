# autoformularz: cyfryzacja formularzy (HackNation 2026, zadanie COI)

REST API that turns a paper form file (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) into an e-form JSON in the COI import format.
- `api/`: the solution. Python 3.14 · FastAPI · local LLM via Ollama (Qwen3-VL) · Docker. Managed with uv.
- `src/`: optional frontend (Next.js 16, shadcn/ui + Tailwind, lucide-react, Motion): upload UI and e-form preview from JSON.

## Task materials (MANDATORY)
The hackathon task, forms and reference materials live in `materialy/` (repo root). This is the source of truth: read the relevant files there before planning or building anything, and stick to them strictly (fields, wording, requirements). Don't invent requirements that aren't in `materialy/`; if something is unclear or missing, ask instead of guessing. Full task text: `materialy/COI - Pełna treść zadania konkursowego.pdf`. Research and open questions: `docs/research-cyfryzacja-formularzy.md`.

## AI access (MANDATORY)
Organizers provide LLM/OCR via Eden AI (OpenAI-compatible `https://api.edenai.run/v3/chat/completions`, plus upload and OCR endpoints). Full mail with endpoints, model naming and examples: `materialy/Dostęp do AI (Eden AI) - mail od organizatorów.md`. Key: `EDENAI_API_KEY` (server-only secret). Use it only for the "Cyfryzacja formularzy" task. Eden AI is the ONLY external AI provider: no Anthropic API (`ANTHROPIC_API_KEY`), no other direct provider keys or SDKs.
The task also bans LLMs available only through an API, so through Eden use ONLY open-weight models that can run locally too (e.g. `google/gemma-*`, `mistral/mistral-small-*`, Qwen, Llama), never closed ones (GPT, Gemini, Claude). The same model must work via local Ollama for the final Docker setup.

## Hard constraints from the task (never break)
- No external APIs, MCP or SaaS in the delivered solution, and no LLM reachable only through an API. The deliverable runs the model locally (Ollama); Eden AI (open-weight models only) is for development, testing and speed during the hackathon.
- Dependencies: open source, NOT copyleft (no GPL/AGPL; e.g. PyMuPDF is banned). Note the license next to each new dependency in `api/pyproject.toml`.
- Uploaded files only in memory or a temp dir. No database, no file storage.
- Docker: official base images, pinned tags (never `latest`), non-root user, secrets only via env at runtime.

## Architecture (api/src/autoformularz)
`upload.py` (name/size/MIME checks) → `extract.py` (text in reading order, or page images) → `llm.py` (Ollama; Eden AI only in local dev; output constrained to the `FormSpec` JSON Schema) → `compiler.py` (deterministic FormSpec → COI JSON: predefined sections from the design standard, techNames, jsonata `states`, flow) → `lint.py` (rules from "Reguły techniczne"). The LLM only fills the small `spec.py` model; anything rule-based belongs in the compiler or linter, not in the prompt.

## Commands
- `npm run check`: everything (biome, tsc, ruff + pytest for api and scripts). Add `-- --build` for a full Next build. Must pass before commit.
- `cd api && uv run uvicorn autoformularz.main:app --reload`: API on :8000 (docs at /docs). `uv run pytest`: API tests.
- `npm run dev`: frontend on :3000. `npm run smoke [url]`: hit key routes.
- `docker compose up --build`: whole stack (ollama + model pull + api + web).
- `npx shadcn@latest add <component>`: add UI components (never hand-write what shadcn has).

## Rules
- Output format: match the reference JSON files in `materialy/1.*` and `materialy/5.*` (same keys, techNames, query shape). Tests in `api/tests/test_compiler.py` compare against them; keep them green.
- Every compiler change: add or update a test. Lint must report zero errors on our output.
- Secrets (`AUTOFORMULARZ_JWT_SECRET`, `EDENAI_API_KEY`) are runtime env only: never in code, images, `NEXT_PUBLIC_*` or client components.
- Env vars: add to `.env.example` and `api/src/autoformularz/config.py` (prefix `AUTOFORMULARZ_`).
- Forms UI: build only from `src/components/form` (fields, sections, `FormShell`) and the tokens in `globals.css`; follow docs/design-system.md. No ad-hoc colors.
- Animations: `motion/react`. Icons: `lucide-react`.
- Keep it simple: no new dependencies or abstractions without a reason in decisions.md.
- Git (all agents and tools): never mention AI in commits, PRs, branch names, tags or comments. No `Co-Authored-By` trailers, no "Generated with ..." lines, no AI names or emoji signatures. Author is the human committing.

## Decisions
@docs/decisions.md
