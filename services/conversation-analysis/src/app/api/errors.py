from typing import Literal

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

ErrorCode = Literal[
    "unauthorized",
    "auth_not_configured",
    "invalid_image",
    "read_failed",
    "daily_limit_exceeded",
    "service_quota_exceeded",
    "model_busy",
    "model_failed",
]


class ErrorBody(BaseModel):
    error: ErrorCode
    message: str


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        error: ErrorCode,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = ErrorBody(error=error, message=message)
        self.headers = headers


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(
        status_code=exc.status_code, content=exc.body.model_dump(), headers=exc.headers
    )


ERROR_RESPONSES: dict[int | str, dict] = {
    code: {"model": ErrorBody, "description": description}
    for code, description in {
        status.HTTP_401_UNAUTHORIZED: "API 토큰이 없거나 틀림 (unauthorized)",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "이미지가 잘못됐거나(invalid_image) 글자를 읽지 못함(read_failed)",
        status.HTTP_429_TOO_MANY_REQUESTS: "IP별 하루 호출 수 초과 (daily_limit_exceeded)",
        status.HTTP_502_BAD_GATEWAY: "모델 호출 실패 (model_failed)",
        status.HTTP_503_SERVICE_UNAVAILABLE: (
            "모델 무료 한도 소진(service_quota_exceeded), 모델 혼잡(model_busy), "
            "서버에 API 토큰 미설정(auth_not_configured)"
        ),
    }.items()
}
