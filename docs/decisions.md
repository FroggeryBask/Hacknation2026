# Decisions (current only)

<!-- One line per decision: `- [area] decision (why)`. When a decision changes, EDIT or DELETE
     its line; don't append a correction. Git history is the archive. Keep under ~40 lines. -->

- [stack] API in Python 3.14 + FastAPI in `api/` (task allows only Java 21+/Python 3.14+ and requires REST + Docker); Next.js stays only as the optional frontend
- [stack] No Supabase/Vercel/DB (task bans external SaaS/APIs and storing files; nothing needs persistence)
- [ai] Delivered solution: local model via Ollama, default `qwen3-vl:8b` (Apache-2.0, reads text and scans; API-only LLMs are banned; small = cheap to deploy)
- [ai] Eden AI (organizer-provided) is the only external AI provider, open-weight models only (same model must run locally); no Anthropic API (task rules). Chosen with `AUTOFORMULARZ_LLM_PROVIDER=eden` (plain httpx, no SDK). `docker-compose.yml` alone forces `ollama` and an empty key (delivered default); for the demo (agreed with COI mentors) the `docker-compose.eden.yml` overlay runs `api` on Eden without the ollama/model services, key only in `api`; cost per call in `llm.EDEN_USAGE`, total since start in `/health`. Dev pair: `deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct` ↔ `qwen3-vl:30b` (Eden has no Qwen3-VL 8B)
- [ai] LLM fills a small FormSpec (constrained by JSON Schema); a deterministic compiler builds the COI JSON (long JSON with UUIDs/jsonata from a small model is unreliable; code is testable and repeatable)
- [ai] Predefined sections (office, applicant, address, proxy, stamp duty, contact, consent, preview) come from compiler templates, not the model (standard says use them; same techNames and queries as reference JSON)
- [format] Follow the reference JSON where it differs from the written schema: `repeatingSectionGrid` (not `repetingSectionGrid`), also for plain SECTION; address/contact prefilled from MLPZ but editable
- [format] FINISH page may hold INFO_SECTION and TEXT_BLOCK (agreed with COI mentors; reference 5 uses TEXT_BLOCK), no warning
- [format] Verbatim source text only for instructions and legal basis (TEXT_BLOCK sections on the FINISH page); statements stay short and gender-neutral from the model, the GDPR clause is only linked (design standard, "Oświadczenie"). OFF by default (`AUTOFORMULARZ_COPY_SOURCE_TEXT=false`): on the saved results the model marked paper instructions, the request text and the GDPR clause as INSTRUCTION/LEGAL_BASIS; turn on once roles are reliable (e.g. checked in code)
- [lint] Field order for condition checks comes from grid `y`/`x`, not the JSON array order (reference files store fields out of display order)
- [format] Element ids are UUIDv5 from form title + path (same input gives the same JSON, readable diffs)
- [format] `validation` lists REQUIRED + validators (PESEL, NIP, REGON, ZIP_CODE, EMAIL...); validators also inferred from labels (reference leaves it empty; validation is an extra-points item)
- [extract] DOCX read from XML incl. text boxes (forms 2 and 8 are built from text boxes); .ods read natively from its XML (same output as the LibreOffice path on all 9 materials); only binary .doc via LibreOffice headless (MPL-2.0 external process, not linked, nothing of ours to publish; mentors: allowed only with such a license, be careful); scanned PDF pages rendered with pypdfium2 (PyMuPDF is AGPL)
- [extract] Scans: tall images of stacked pages are cut into A4 pages at blank rows; OCR with Tesseract + `pol` (Apache-2.0, separate process, stdin, one thread) gives the same Document blocks as text files, page images still go to the model (OCR misses empty tick boxes). Deterministic, ~1 s/page, 87-100% word recall vs DOCX on the materials; without Tesseract scans go as images only
- [upload] `.doc` and `.docx` are one format ("DOC (.doc .docx)" in the task): the content decides how it is read (materials 5 and 7 are DOCX named .DOC)
- [api] Contract for parallel work: `extract` returns a `Document` (blocks `b1…` + field candidates), FormSpec points to block IDs (`blocks`, `block_roles`), `?details=true` adds `document` and `coverage` (model classifies, code keeps the text; see docs/pipeline.md "Kontrakt")
- [api] `POST /api/v1/forms` returns the importable JSON as-is; `?details=true` adds FormSpec, lint issues and notes for the UI
- [api] JWT HS256 with shared secret from env; `AUTOFORMULARZ_AUTH_ENABLED=false` only for local dev
- [docker] Debian slim, not Alpine (LibreOffice and PDF/imaging wheels need glibc); LibreOffice optional via build arg
- [tooling] Biome (not ESLint/Prettier); ruff + pytest via uv for `api/` and `scripts/`; lefthook git hooks
- [git] No AI attribution in commits/PRs (team rule): disabled in .claude/settings.json, blocked by lefthook commit-msg hook
- [ui] Design system for forms in `src/components/form` (fields 1:1 with JSON `field.type`), gov.pl-like tokens + Lato; see docs/design-system.md
- [ui] Biome linter off for `src/components/ui/**` (generated shadcn code, kept as upstream); still formatted
