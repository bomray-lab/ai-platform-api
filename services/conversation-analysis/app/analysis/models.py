from typing import Literal

from pydantic import BaseModel, Field

DnaType = Literal[
    "카톡 폭탄러",
    "연애 고수",
    "잠수 장인",
    "선긋기 장인",
    "자유 영혼",
    "걱정 마라토너",
    "밀당 고수",
    "밀당 유목민",
]

Speaker = Literal["me", "other", "unknown"]
Temperature = Literal["hot", "warm", "cooling", "cold"]
FishPond = Literal["definite", "suspicious", "no"]
Signal = Literal["green", "yellow", "red"]
Dominance = Literal["me", "balanced", "them"]


class TranscriptTurn(BaseModel):
    speaker: Speaker
    text: str


class Extraction(BaseModel):
    readable: bool
    turns: list[TranscriptTurn]


class Judgment(BaseModel):
    temperature: Temperature = Field(description="상대 온도: 뜨거움, 미지근, 식어가는 중, 위험")
    anger_level: int = Field(ge=0, le=100, description="빡침 정도 0~100")
    fish_pond: FishPond = Field(description="어장 여부: 어장 확실, 의심됨, 아닌 것 같음")
    signal: Signal = Field(description="그린나이트, 옐로나이트, 레드나이트")
    dominance: Dominance = Field(description="대화 주도권: 내가 주도 중, 균형, 끌려다니는 중")
    reason: str = Field(description="위 판단의 근거")
    evidence: list[str] = Field(description="근거가 된 대본 인용")
    recommended_replies: list[str] = Field(
        min_length=1, max_length=2, description="실제로 보낼 수 있는 답장 1~2개"
    )
    recommended_action: str = Field(description="답장 외에 지금 할 행동 한 줄")
