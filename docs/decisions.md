# Decisions (current only)

<!-- One line per decision: `- [area] decision (why)`. When a decision changes, EDIT or DELETE
     its line; don't append a correction. Git history is the archive. Keep under ~40 lines. -->

- [stack] API in Python 3.14 + FastAPI in `api/` (task allows only Java 21+/Python 3.14+ and requires REST + Docker); Next.js stays only as the optional frontend
- [stack] No Supabase/Vercel/DB (task bans external SaaS/APIs and storing files; nothing needs persistence)
- [ai] Delivered solution: local model via Ollama, default `qwen3-vl:8b` (Apache-2.0, reads text and scans; API-only LLMs are banned; small = cheap to deploy)
- [ai] Eden AI (organizer-provided) is the only external AI provider, open-weight models only (same model must run locally); no Anthropic API (task rules). Chosen with `AUTOFORMULARZ_LLM_PROVIDER=eden` in local dev only (plain httpx, no SDK); docker-compose forces `ollama` and an empty key. Dev pair: `deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct` ↔ `qwen3-vl:30b` (Eden has no Qwen3-VL 8B)
- [ai] LLM fills a small FormSpec (constrained by JSON Schema); a deterministic compiler builds the COI JSON (long JSON with UUIDs/jsonata from a small model is unreliable; code is testable and repeatable)
- [ai] Predefined sections (office, applicant, address, proxy, stamp duty, contact, consent, preview) come from compiler templates, not the model (standard says use them; same techNames and queries as reference JSON)
- [format] Follow the reference JSON where it differs from the written schema: `repeatingSectionGrid` (not `repetingSectionGrid`), also for plain SECTION; address/contact prefilled from MLPZ but editable
- [format] FINISH page uses INFO_SECTION (written rule), reference uses TEXT_BLOCK: lint gives only a warning for that
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
- [tooling] Slides in Marp (`docs/prezentacja.md` → PDF via `npm run slides`, MIT, run with npx, not a dependency): versioned with the code, theme modeled on COI visual identity (Behance board in `materialy/inspo_prezentacja`, coi.gov.pl): conic-gradient circles and squares as on coi.gov.pl, Inter Light, navy #04122f, magenta gradient #871c6c→#e10a58, blue #133692, no COI logo
- [git] No AI attribution in commits/PRs (team rule): disabled in .claude/settings.json, blocked by lefthook commit-msg hook
- [ui] Design system for forms in `src/components/form` (fields 1:1 with JSON `field.type`), gov.pl-like tokens + Lato; see docs/design-system.md
- [ui] Renderer `CoiFormView` (`src/components/form/coi-form.tsx`) builds the e-form from COI JSON, not from hand-written forms; `states` evaluated with the `jsonata` package (MIT) on a copy of the JSON with `__userAnswer` injected (exact syntax from "Reguły techniczne", incl. `$repeatingSectionIndex`), so any query from the compiler or the reference files works; preview at `/podglad`
- [ui] Start page `/` uploads the file through the Next route `/api/forms`, which signs a short-lived JWT with `AUTOFORMULARZ_JWT_SECRET` (node:crypto, no new dependency) and forwards to `POST /api/v1/forms?details=true`; the secret and API address never reach the browser
- [ui] JSON `description` HTML is converted to React through an allowlist (no innerHTML, inline styles dropped, so only design-system tokens)
- [ui] Biome linter off for `src/components/ui/**` (generated shadcn code, kept as upstream); still formatted
