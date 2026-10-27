from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.errors import ApiError, api_error_handler
from app.api.routes import API_PREFIX
from app.api.routes import router as conversation_router
from app.settings import get_api_settings


class SettingsCORSMiddleware:
    """허용 주소를 첫 요청 때 설정에서 읽는다. Workers는 import 시점 상태를 스냅샷으로 굳혀서 그때는 설정이 없다."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._cors: CORSMiddleware | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._cors is None:
            self._cors = CORSMiddleware(
                self._app,
                allow_origins=get_api_settings().cors_origins,
                allow_methods=["GET", "POST"],
                allow_headers=["*"],
            )
        await self._cors(scope, receive, send)


app = FastAPI(
    title="conversation-analysis",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
)
app.add_exception_handler(ApiError, api_error_handler)
app.add_middleware(SettingsCORSMiddleware)
app.include_router(conversation_router)


@app.get(f"{API_PREFIX}/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
