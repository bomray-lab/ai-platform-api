from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import ApiError, api_error_handler
from app.api.routes import router as conversation_router
from app.settings import get_api_settings

app = FastAPI(title="conversation-analysis")
app.add_exception_handler(ApiError, api_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_api_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(conversation_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
