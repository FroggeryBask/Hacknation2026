#!/usr/bin/env bash
# Stop hook: when Claude finishes a turn that changed code, typecheck + lint.
# Exit 2 sends the errors back to Claude so it fixes them before handing off.
input=$(cat)
[ "$(jq -r '.stop_hook_active // false' <<<"$input")" = "true" ] && exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 0
# Skip turns that touched no code (questions, planning).
git status --porcelain -- 'src' 'scripts' 'api' '*.ts' '*.tsx' | grep -q . || exit 0

out=$( { npx tsc --noEmit --pretty false 2>&1 || echo "__FAIL__"; } ;
       { npx biome check --colors=off --max-diagnostics=15 . 2>&1 || echo "__FAIL__"; } ;
       { uv run --project scripts ruff check scripts --output-format concise 2>&1 || echo "__FAIL__"; } ;
       { uv run --project api ruff check api --output-format concise 2>&1 || echo "__FAIL__"; } ;
       { uv run --project api pytest -q -x api 2>&1 | tail -25; [ "${PIPESTATUS[0]}" -eq 0 ] || echo "__FAIL__"; } )
if grep -q "__FAIL__" <<<"$out"; then
  echo "Checks failed. Fix these before finishing:" >&2
  grep -v "__FAIL__" <<<"$out" | tail -60 >&2
  exit 2
fi
exit 0
