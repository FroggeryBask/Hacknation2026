"""Prints a JWT signed with AUTOFORMULARZ_JWT_SECRET, for local testing: `uv run autoformularz-token [hours]`."""

import sys
import time

import jwt

from autoformularz.config import get_settings


def main() -> None:
    settings = get_settings()
    if settings.jwt_secret is None:
        sys.exit("Ustaw AUTOFORMULARZ_JWT_SECRET.")
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 8
    claims = {"sub": "dev", "exp": int(time.time() + hours * 3600)}
    if settings.jwt_audience:
        claims["aud"] = settings.jwt_audience
    print(jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm))


if __name__ == "__main__":
    main()
