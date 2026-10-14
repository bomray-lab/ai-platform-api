from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.errors import ApiError
from app.settings import ApiSettings, get_api_settings

_bearer = HTTPBearer(auto_error=False, description="`.env`의 `API_TOKEN` 값")


def require_api_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[ApiSettings, Depends(get_api_settings)],
) -> None:
    if settings.api_token is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "auth_not_configured",
            "서버에 API_TOKEN이 설정되지 않았습니다.",
        )
    expected = settings.api_token.get_secret_value().encode()
    if credentials is None or not compare_digest(credentials.credentials.encode(), expected):
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "unauthorized",
            "API 토큰이 없거나 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
