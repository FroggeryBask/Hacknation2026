# formgen: cyfryzacja formularzy (HackNation 2026, zadanie COI)

REST API that turns a paper form file (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) into an e-form JSON in the COI import format.
- `api/`: the solution. Python 3.14 · FastAPI · local LLM via Ollama (Qwen3-VL) · Docker. Managed with uv.
- `src/`: optional frontend (Next.js 16, shadcn/ui + Tailwind, lucide-react, Motion): upload UI and e-form preview from JSON.

## Task materials (MANDATORY)
The hackathon task, forms and reference materials live in `materialy/` (repo root). This is the source of truth: read the relevant files there before planning or building anything, and stick to them strictly (fields, wording, requirements). Don't invent requirements that aren't in `materialy/`; if something is unclear or missing, ask instead of guessing. Full task text: `materialy/COI - Pełna treść zadania konkursowego.pdf`. Research and open questions: `docs/research-cyfryzacja-formularzy.md`.

## Hard constraints from the task (never break)
- No external APIs, MCP or SaaS at runtime, and no LLM reachable only through an API (Claude/OpenAI/etc. only for writing code). The model runs locally (Ollama).
- Dependencies: open source, NOT copyleft (no GPL/AGPL; e.g. PyMuPDF is banned). Note the license next to each new dependency in `api/pyproject.toml`.
- Uploaded files only in memory or a temp dir. No database, no file storage.
- Docker: official base images, pinned tags (never `latest`), non-root user, secrets only via env at runtime.

## Architecture (api/src/formgen)
`upload.py` (name/size/MIME checks) → `extract.py` (text in reading order, or page images) → `llm.py` (Ollama, output constrained to the `FormSpec` JSON Schema) → `compiler.py` (deterministic FormSpec → COI JSON: predefined sections from the design standard, techNames, jsonata `states`, flow) → `lint.py` (rules from "Reguły techniczne"). The LLM only fills the small `spec.py` model; anything rule-based belongs in the compiler or linter, not in the prompt.

## Commands
- `npm run check`: everything (biome, tsc, ruff + pytest for api and scripts). Add `-- --build` for a full Next build. Must pass before commit.
- `cd api && uv run uvicorn formgen.main:app --reload`: API on :8000 (docs at /docs). `uv run pytest`: API tests.
- `npm run dev`: frontend on :3000. `npm run smoke [url]`: hit key routes.
- `docker compose up --build`: whole stack (ollama + model pull + api + web).
- `npx shadcn@latest add <component>`: add UI components (never hand-write what shadcn has).

## Rules
- Output format: match the reference JSON files in `materialy/1.*` and `materialy/5.*` (same keys, techNames, query shape). Tests in `api/tests/test_compiler.py` compare against them; keep them green.
- Every compiler change: add or update a test. Lint must report zero errors on our output.
- Secrets (`FORMGEN_JWT_SECRET`) are runtime env only: never in code, images, `NEXT_PUBLIC_*` or client components.
- Env vars: add to `.env.example` and `api/src/formgen/config.py` (prefix `FORMGEN_`).
- Forms UI: build only from `src/components/form` (fields, sections, `FormShell`) and the tokens in `globals.css`; follow docs/design-system.md. No ad-hoc colors.
- Animations: `motion/react`. Icons: `lucide-react`.
- Keep it simple: no new dependencies or abstractions without a reason in decisions.md.
- Git (all agents and tools): never mention AI in commits, PRs, branch names, tags or comments. No `Co-Authored-By` trailers, no "Generated with ..." lines, no AI names or emoji signatures. Author is the human committing.

## Decisions
@docs/decisions.md
