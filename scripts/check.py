"""Run every check; exit 1 if any fail. Usage:
npm run check            # lint, types, python, db audit
npm run check -- --build # also run `next build`
"""

import subprocess
import sys
import time

from _env import ROOT

STEPS: list[tuple[str, list[str]]] = [
    ("biome (lint + format)", ["npx", "biome", "check", "."]),
    ("typescript", ["npx", "tsc", "--noEmit"]),
    ("ruff lint", ["uv", "run", "--project", "scripts", "ruff", "check", "scripts"]),
    ("ruff format", ["uv", "run", "--project", "scripts", "ruff", "format", "--check", "scripts"]),
    ("supabase audit", ["uv", "run", "--project", "scripts", "python", "scripts/check_db.py"]),
]


def main() -> int:
    steps = list(STEPS)
    if "--build" in sys.argv:
        steps.append(("next build", ["npm", "run", "build"]))

    results = []
    for name, cmd in steps:
        print(f"\n\033[1m▶ {name}\033[0m", flush=True)
        start = time.monotonic()
        code = subprocess.run(cmd, cwd=ROOT).returncode
        results.append((name, code == 0, time.monotonic() - start))

    print("\n\033[1mSummary\033[0m")
    for name, ok, secs in results:
        mark = "\033[32m✔\033[0m" if ok else "\033[31m✘\033[0m"
        print(f"  {mark} {name} ({secs:.1f}s)")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
