"""JWT bearer authentication (HS256 shared secret from FORMGEN_JWT_SECRET)."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from formgen.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def require_jwt(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict | None:
    if not settings.auth_enabled:
        return None
    if settings.jwt_secret is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "FORMGEN_JWT_SECRET nie jest ustawiony.")
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Brak tokenu JWT.", {"WWW-Authenticate": "Bearer"})
    try:
        return jwt.decode(
            creds.credentials,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            options={"require": ["exp"], "verify_aud": settings.jwt_audience is not None},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Nieprawidłowy lub wygasły token JWT.",
            {"WWW-Authenticate": "Bearer"},
        ) from e
