from app.analysis.errors import LlmRejected, UnreadableCapture
from app.analysis.llm import LlmClient
from app.analysis.models import Extraction, TranscriptTurn
from app.analysis.resize import resize_long_side

_INSTRUCTIONS = """\
카카오톡·인스타그램 등 대화 캡처에서 말만 추출한다.
이미지가 여러 장이면 업로드된 순서대로 한 대화다.
speaker는 me(오른쪽·내 말풍선), other(왼쪽·상대 말풍선), 위치를 모르면 unknown.
없는 대사는 만들지 않는다.
글자를 읽을 수 없으면 readable을 false로 하고 turns는 비운다.
"""


def extract_transcript(images: list[bytes], llm: LlmClient) -> list[TranscriptTurn]:
    try:
        parsed = llm.parse(
            instructions=_INSTRUCTIONS,
            text="이 캡처들의 대화를 순서대로 추출한다.",
            images=[resize_long_side(raw) for raw in images],
            text_format=Extraction,
        )
    except LlmRejected as error:
        raise UnreadableCapture("캡처에서 대화를 읽지 못했습니다.") from error
    if not parsed.readable or not any(turn.text.strip() for turn in parsed.turns):
        raise UnreadableCapture("캡처에서 대화를 읽지 못했습니다.")
    return parsed.turns
