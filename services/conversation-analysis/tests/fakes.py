import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.analysis.models import Judgment, TranscriptTurn

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_turns() -> list[TranscriptTurn]:
    raw = json.loads((FIXTURES / "transcript.json").read_text(encoding="utf-8"))
    return [TranscriptTurn.model_validate(turn) for turn in raw]


def judgment_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "temperature": "cooling",
        "anger_level": 35,
        "fish_pond": "suspicious",
        "signal": "yellow",
        "dominance": "them",
        "reason": "약속을 미루고 다음을 기약한다.",
        "evidence": ["음 오늘은 좀 바쁘고 다음에 보자", "글쎄 그때 연락할게"],
        "recommended_replies": ["알겠어. 편할 때 말해줘.", "오늘은 여기까지 할게."],
        "recommended_action": "오늘은 더 묻지 마",
    }
    payload.update(overrides)
    return payload


def judgment(**overrides: Any) -> Judgment:
    return Judgment.model_validate(judgment_payload(**overrides))


@dataclass
class Call:
    instructions: str
    text: str
    images: Sequence[bytes]
    text_format: type[BaseModel]


@dataclass
class FakeLlm:
    """text_format별로 미리 정한 결과를 돌려주는 LlmClient. 결과가 예외면 던진다."""

    results: dict[type[BaseModel], BaseModel | Exception]
    calls: list[Call] = field(default_factory=list)

    async def parse[T: BaseModel](
        self,
        *,
        instructions: str,
        text: str,
        images: Sequence[bytes] = (),
        text_format: type[T],
    ) -> T:
        self.calls.append(Call(instructions, text, images, text_format))
        result = self.results[text_format]
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, text_format)
        return result
