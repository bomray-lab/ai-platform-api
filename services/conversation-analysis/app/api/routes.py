import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.analysis.errors import LlmBusy, LlmFailed, LlmQuotaExceeded, UnreadableCapture
from app.analysis.llm import LlmClient, llm_from_settings
from app.analysis.models import DnaType
from app.analysis.pipeline import analyze
from app.analysis.resize import ImageDecodeError
from app.api.auth import require_api_token
from app.api.errors import ERROR_RESPONSES, ApiError
from app.api.images import MAX_IMAGES, invalid_image, read_screenshots
from app.api.rate_limit import DailyLimiter, limiter_from_settings
from app.api.schemas import AnalyzeResponse

router = APIRouter(
    prefix="/v1/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_api_token)],
)

_IMAGES_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "maxItems": MAX_IMAGES,
    "items": {"type": "string", "format": "binary"},
    "description": f"jpeg, png, webp 파일을 1장 이상 {MAX_IMAGES}장 이하로 첨부",
}


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    responses=ERROR_RESPONSES,
)
async def analyze_conversation(
    request: Request,
    my_dna_type: Annotated[DnaType, Form()],
    images: Annotated[list[UploadFile], File(json_schema_extra=_IMAGES_SCHEMA)],
    llm: Annotated[LlmClient, Depends(llm_from_settings)],
    limiter: Annotated[DailyLimiter, Depends(limiter_from_settings)],
) -> AnalyzeResponse:
    screenshots = await read_screenshots(images)
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.try_hit(client_ip):
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "daily_limit_exceeded",
            "오늘 분석 횟수를 다 썼어요. 내일 다시 시도해 주세요.",
        )
    try:
        turns, judgment = await asyncio.to_thread(analyze, my_dna_type, screenshots, llm)
    except UnreadableCapture as error:
        raise ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "read_failed", str(error)) from error
    except ImageDecodeError as error:
        raise invalid_image(str(error)) from error
    except LlmQuotaExceeded as error:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "service_quota_exceeded",
            "오늘 준비된 무료 분석량을 모두 썼어요. 한국 시간 오전 9시 이후에 다시 시도해 주세요.",
        ) from error
    except LlmBusy as error:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "model_busy",
            "지금 분석 요청이 몰려 있어요. 잠시 뒤 다시 시도해 주세요.",
            headers={"Retry-After": "30"},
        ) from error
    except LlmFailed as error:
        raise ApiError(status.HTTP_502_BAD_GATEWAY, "model_failed", str(error)) from error
    return AnalyzeResponse(transcript=turns, **judgment.model_dump())
