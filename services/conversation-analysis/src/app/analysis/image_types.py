_WEBP_HEADER_BYTES = 12


def sniff_media_type(raw: bytes) -> str | None:
    """파일 앞부분으로 jpeg, png, webp를 가린다. 셋 다 아니면 None."""
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(raw) >= _WEBP_HEADER_BYTES and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    return None
