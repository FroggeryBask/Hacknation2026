---
description: Check, review, fix, record decisions, and commit the current work
---

Ship the current changes:

1. Run `npm run check`. Fix every failure.
2. Use the `reviewer` subagent on the diff. Fix every issue it reports that you agree with; briefly say why for any you reject.
3. Update `docs/decisions.md` only if this work made or changed a decision: edit or delete the old line in place, don't append history. Skip if nothing changed.
4. Re-run `npm run check` until it passes.
5. Commit with a short conventional message (`feat:`, `fix:`, `chore:`). No AI attribution: no `Co-Authored-By` trailer, no "Generated with" line. $ARGUMENTS
