"""Hit key routes on a running app. Usage:
    uv run --project scripts scripts/smoke_test.py [base_url]
Default base_url: http://localhost:3000. Use your Vercel URL before the demo.
Add routes to ROUTES as you build them.
"""

import sys

import httpx

ROUTES: list[tuple[str, int]] = [
    ("/", 200),
    ("/api/health", 200),
    ("/design-system", 200),
    ("/design-system/formularze/numer-porzadkowy", 200),
    ("/design-system/formularze/nadplata-podatku", 200),
    ("/design-system/formularze/swietlica", 200),
]


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000").rstrip("/")
    failures = 0
    with httpx.Client(base_url=base, timeout=15, follow_redirects=True) as http:
        for path, expected in ROUTES:
            try:
                r = http.get(path)
                ok = r.status_code == expected
                print(f"{'OK  ' if ok else 'FAIL'} {path} -> {r.status_code} (want {expected})")
                failures += not ok
            except httpx.HTTPError as e:
                print(f"FAIL {path} -> {type(e).__name__}: {e}")
                failures += 1
    print(f"\n{'FAIL' if failures else 'PASS'}: {failures} failing route(s) on {base}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
