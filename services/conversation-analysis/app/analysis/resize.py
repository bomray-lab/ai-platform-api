from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

LONG_SIDE = 1280


class ImageDecodeError(Exception):
    """파일 검사는 통과했지만 이미지로 열리지 않는다."""


def resize_long_side(raw: bytes) -> bytes:
    """긴 변을 LONG_SIDE 이하로 줄인 PNG 바이트를 돌려준다."""
    try:
        with Image.open(BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            width, height = image.size
            long_side = max(width, height)
            if long_side > LONG_SIDE:
                scale = LONG_SIDE / long_side
                image = image.resize(
                    (max(1, int(width * scale)), max(1, int(height * scale))),
                    Image.Resampling.LANCZOS,
                )
            buffer = BytesIO()
            image.save(buffer, format="PNG")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
        raise ImageDecodeError("이미지를 열 수 없습니다.") from error
    return buffer.getvalue()
