#!/bin/sh
# Rejects commit messages with AI attribution (team rule, see CLAUDE.md > Rules).
# A separate file (not inline in lefthook.yml): inline sh -c broke on the emoji on Windows.
if grep -qiE '^co-authored-by:.*(claude|anthropic|copilot|cursor|openai|chatgpt|gpt|gemini|codex|noreply@anthropic)|generated (with|by) .*(claude|ai\b|copilot|cursor|chatgpt|codex)|🤖' "$1"; then
  echo "Commit message contains AI attribution. Remove it (see CLAUDE.md > Rules)."
  exit 1
fi
