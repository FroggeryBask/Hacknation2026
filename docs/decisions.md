# Decisions (current only)

<!-- One line per decision: `- [area] decision (why)`. When a decision changes, EDIT or DELETE
     its line; don't append a correction. Git history is the archive. Keep under ~40 lines. -->

- [stack] API in Python 3.14 + FastAPI in `api/` (task allows only Java 21+/Python 3.14+ and requires REST + Docker); Next.js stays only as the optional frontend
- [stack] No Supabase/Vercel/DB (task bans external SaaS/APIs and storing files; nothing needs persistence)
- [ai] Delivered solution: local model via Ollama, default `qwen3-vl:8b` (Apache-2.0, reads text and scans; API-only LLMs are banned; small = cheap to deploy)
- [ai] Eden AI (organizer-provided) is the only external AI provider, open-weight models only (same model must run locally); no Anthropic API (task rules)
- [ai] LLM fills a small FormSpec (constrained by JSON Schema); a deterministic compiler builds the COI JSON (long JSON with UUIDs/jsonata from a small model is unreliable; code is testable and repeatable)
- [ai] Predefined sections (office, applicant, address, proxy, stamp duty, contact, consent, preview) come from compiler templates, not the model (standard says use them; same techNames and queries as reference JSON)
- [format] Follow the reference JSON where it differs from the written schema: `repeatingSectionGrid` (not `repetingSectionGrid`), also for plain SECTION; address/contact prefilled from MLPZ but editable
- [format] FINISH page uses INFO_SECTION (written rule), reference uses TEXT_BLOCK: lint gives only a warning for that
- [format] Element ids are UUIDv5 from form title + path (same input gives the same JSON, readable diffs)
- [format] `validation` lists REQUIRED + validators (PESEL, NIP, REGON, ZIP_CODE, EMAIL...); validators also inferred from labels (reference leaves it empty; validation is an extra-points item)
- [extract] DOCX read from XML incl. text boxes (forms 2 and 8 are built from text boxes); .doc/.ods via LibreOffice headless (MPL-2.0 external process, not linked; confirm with COI mentors); scanned PDF pages rendered with pypdfium2 (PyMuPDF is AGPL)
- [api] `POST /api/v1/forms` returns the importable JSON as-is; `?details=true` adds FormSpec, lint issues and notes for the UI
- [api] JWT HS256 with shared secret from env; `FORMGEN_AUTH_ENABLED=false` only for local dev
- [docker] Debian slim, not Alpine (LibreOffice and PDF/imaging wheels need glibc); LibreOffice optional via build arg
- [tooling] Biome (not ESLint/Prettier); ruff + pytest via uv for `api/` and `scripts/`; lefthook git hooks
- [git] No AI attribution in commits/PRs (team rule): disabled in .claude/settings.json, blocked by lefthook commit-msg hook
- [ui] Design system for forms in `src/components/form` (fields 1:1 with JSON `field.type`), gov.pl-like tokens + Lato; see docs/design-system.md
- [ui] Biome linter off for `src/components/ui/**` (generated shadcn code, kept as upstream); still formatted
