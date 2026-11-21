"""Run every check; exit 1 if any fail. Usage:
npm run check            # frontend lint + types, API lint + tests, scripts lint
npm run check -- --build # also run `next build`
"""

import shutil
import subprocess
import sys
import time

from _env import ROOT

API = ["uv", "run", "--project", "api"]
SCRIPTS = ["uv", "run", "--project", "scripts"]

STEPS: list[tuple[str, list[str]]] = [
    ("biome (lint + format)", ["npx", "biome", "check", "."]),
    ("typescript", ["npx", "tsc", "--noEmit"]),
    ("ruff lint (api)", [*API, "ruff", "check", "api"]),
    ("ruff format (api)", [*API, "ruff", "format", "--check", "api"]),
    ("pytest (api)", [*API, "pytest", "-q", "api"]),
    ("ruff lint (scripts)", [*SCRIPTS, "ruff", "check", "scripts"]),
    ("ruff format (scripts)", [*SCRIPTS, "ruff", "format", "--check", "scripts"]),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1250 (no ▶/✔ glyphs)
    steps = list(STEPS)
    if "--build" in sys.argv:
        steps.append(("next build", ["npm", "run", "build"]))

    results = []
    for name, cmd in steps:
        print(f"\n\033[1m▶ {name}\033[0m", flush=True)
        start = time.monotonic()
        exe = shutil.which(cmd[0]) or cmd[0]  # Windows: npx/npm are .cmd shims
        code = subprocess.run([exe, *cmd[1:]], cwd=ROOT).returncode
        results.append((name, code == 0, time.monotonic() - start))

    print("\n\033[1mSummary\033[0m")
    for name, ok, secs in results:
        mark = "\033[32m✔\033[0m" if ok else "\033[31m✘\033[0m"
        print(f"  {mark} {name} ({secs:.1f}s)")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
