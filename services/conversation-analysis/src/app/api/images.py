from fastapi import UploadFile, status

from app.analysis.image_types import sniff_media_type
from app.api.errors import ApiError

MAX_IMAGES = 3
# 서버는 이미지를 줄이지 않는다. 프론트에서 긴 변 1280px 정도로 줄인 jpeg/webp를 보낸다
MAX_IMAGE_BYTES = 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def invalid_image(message: str) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_image", message)


async def read_screenshots(images: list[UploadFile]) -> list[bytes]:
    if not 1 <= len(images) <= MAX_IMAGES:
        raise invalid_image(f"이미지는 1장 이상 {MAX_IMAGES}장 이하로 보내야 합니다.")
    screenshots: list[bytes] = []
    for image in images:
        raw = await image.read(MAX_IMAGE_BYTES + 1)
        _validate_image_bytes(image.content_type, raw)
        screenshots.append(raw)
    return screenshots


def _validate_image_bytes(content_type: str | None, raw: bytes) -> None:
    if not raw:
        raise invalid_image("비어 있는 이미지입니다.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise invalid_image("이미지 한 장은 1MB 이하여야 합니다. 크기를 줄여서 보내 주세요.")
    if sniff_media_type(raw) is None or not _content_type_allowed(content_type):
        raise invalid_image("이미지는 jpeg, png, webp만 받을 수 있습니다.")


def _content_type_allowed(content_type: str | None) -> bool:
    if content_type is None:
        return True
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type in {"", "application/octet-stream"}:
        return True
    return media_type in ALLOWED_CONTENT_TYPES
